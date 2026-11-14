"""分层架构回归：用 AST 静态校验单向依赖。

对应需求里的硬约束：

    view ──▶ viewmodel ──▶ service ──▶ infra
       ╲         │            │          │
        ╲        ▼            ▼          ▼
         ╲────────────── models ─────────┘

- 只允许箭头方向的依赖，禁止反向与跨层；
- 高层只依赖**抽象接口**：service 只允许碰 ``infra.ports``；
- models / service / viewmodel 三层不得出现任何 UI / 底层技术依赖；
- 视图层的 UI 依赖收敛到 ``ui``：既不 import flet，代码里也不出现 flet 前缀
  （唯一出口是 ``view/components/primitives.py``）。
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parent.parent / "cs_music_player"
PACKAGE_NAME = "cs_music_player"

#: 组装根：唯一允许「认识所有层」的地方，不参与分层约束。
ROOT_MODULES = {"bootstrap", "main"}

LAYERS = ("models", "infra", "service", "viewmodel", "view")

#: 每层允许引用的包内前缀（含同层互引）。
ALLOWED_PACKAGE_PREFIXES: dict[str, tuple[str, ...]] = {
    "models": ("models",),
    "infra": ("models", "infra"),
    # 服务层只认抽象接口：infra 下除 ports 外一律不许碰
    "service": ("models", "service", "infra.ports"),
    "viewmodel": ("models", "service", "viewmodel"),
    "view": ("models", "view", "viewmodel"),
}

#: 每层允许引用的第三方包（标准库不限）。
#:
#: 视图层只认 ``ui``（本地 cs-ui 组件库）：布局、控件、设计令牌、主题运行时
#: 全从它取。**不直接依赖 flet** —— 换 UI 底座时只需要改这一个包。
ALLOWED_THIRD_PARTY: dict[str, tuple[str, ...]] = {
    "models": (),
    "service": (),
    "viewmodel": (),
    "infra": ("flet", "flet_audio", "flet_desktop", "mutagen", "PIL"),
    "view": ("ui",),
}

STDLIB = set(sys.stdlib_module_names)


def _layer_of(rel: Path) -> str | None:
    """相对 ``cs_music_player`` 的路径 → 层名；不在任何层里返回 ``None``。"""
    parts = rel.parts
    if len(parts) >= 2 and parts[0] in LAYERS:
        return parts[0]
    return None


def _is_assembly_root(rel: Path) -> bool:
    """组装根与包级 ``__init__`` 不参与分层约束。"""
    return rel.stem == "__init__" or rel.stem in ROOT_MODULES


def _iter_modules() -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(PACKAGE)
        layer = _layer_of(rel)
        if layer is not None:
            found.append((layer, path))
    return found


def _module_package(path: Path) -> str:
    """文件 → 它所在的包（``a/b/c.py`` → ``cs_music_player.a.b``）。"""
    rel = path.relative_to(PACKAGE).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] != "__init__":
        parts.pop()  # 普通模块名不是包名的一部分
    return ".".join([PACKAGE_NAME, *parts])


def _resolve(node: ast.ImportFrom, package: str) -> str | None:
    """把 ``ImportFrom`` 解析成绝对点分模块名。"""
    if node.level == 0:
        return node.module
    parts = package.split(".")
    drop = node.level - 1
    if drop:
        parts = parts[:-drop] if drop <= len(parts) else []
    base = ".".join(parts)
    if node.module:
        return f"{base}.{node.module}" if base else node.module
    return base


def _dynamic_targets(tree: ast.Module, package: str) -> tuple[set[str], list[str]]:
    """找出「动态导入」的目标。

    Returns:
        ``(可解析出的包内绝对模块名, 无法静态判定的调用描述)``。
        后者用来保证守卫本身不会被绕过去：任何非字面量的
        ``import_module`` / ``__import__`` 都必须显式出现在返回里。
    """
    resolved: set[str] = set()
    opaque: list[str] = []

    def _is_dynamic_call(node: ast.Call) -> bool:
        func = node.func
        if isinstance(func, ast.Name) and func.id in ("__import__", "import_module"):
            return True
        return (
            isinstance(func, ast.Attribute)
            and func.attr in ("import_module", "__import__")
        )

    for node in ast.walk(tree):
        # ``_LAZY_EXPORTS = {"Name": "submodule"}`` —— PEP 562 惰性转出表
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_LAZY_EXPORTS":
                    if isinstance(node.value, ast.Dict):
                        for value in node.value.values:
                            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                                resolved.add(f"{package}.{value.value}")
        if isinstance(node, ast.Call) and _is_dynamic_call(node):
            first = node.args[0] if node.args else None
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                name = first.value.lstrip(".")
                resolved.add(name if name.startswith(PACKAGE_NAME) else f"{package}.{name}")
            else:
                opaque.append(f"line {node.lineno}")
    return resolved, opaque


def _imports(path: Path) -> tuple[set[str], set[str]]:
    """返回 ``(包内绝对模块名, 顶层第三方包名)``。"""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    package = _module_package(path)
    in_package: set[str] = set()
    third_party: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root == PACKAGE_NAME:
                    in_package.add(alias.name)
                elif root not in STDLIB:
                    third_party.add(root)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module is None:
                continue
            resolved = _resolve(node, package)
            if resolved is None:
                continue
            root = resolved.split(".")[0]
            if root == PACKAGE_NAME:
                in_package.add(resolved)
            elif root not in STDLIB:
                third_party.add(root)
    in_package |= _dynamic_targets(tree, package)[0]
    return in_package, third_party


MODULES = _iter_modules()


def test_every_layer_is_populated() -> None:
    """五层都必须真的存在文件，否则下面按层过滤的断言会「空跑通过」。"""
    present = {layer for layer, _ in MODULES}
    assert present == set(LAYERS), f"缺失层：{set(LAYERS) - present}"


@pytest.mark.parametrize("layer,path", MODULES, ids=[str(p) for _, p in MODULES])
def test_package_dependencies_follow_the_layer_order(layer: str, path: Path) -> None:
    allowed = ALLOWED_PACKAGE_PREFIXES[layer]
    in_package, _ = _imports(path)
    offenders = []
    for target in sorted(in_package):
        relative = target[len(PACKAGE_NAME) + 1 :]
        if not any(
            relative == prefix or relative.startswith(f"{prefix}.") for prefix in allowed
        ):
            offenders.append(relative)
    assert not offenders, (
        f"{layer} 层不得引用 {offenders}（允许：{allowed}）——{path.name}"
    )


@pytest.mark.parametrize("layer,path", MODULES, ids=[str(p) for _, p in MODULES])
def test_third_party_dependencies_are_layer_appropriate(layer: str, path: Path) -> None:
    allowed = ALLOWED_THIRD_PARTY[layer]
    _, third_party = _imports(path)
    offenders = sorted(third_party - set(allowed))
    assert not offenders, (
        f"{layer} 层不得引用 {offenders}（允许：{allowed}）——{path.name}"
    )


def test_view_never_imports_flet_directly() -> None:
    """视图层的 UI 依赖必须收敛到 ``ui`` 一个包。

    这条比「允许 flet」更严：``from ui import ft`` 与 ``import flet`` 在实现上
    等价，但在**架构上**后者意味着「这个应用直接绑定了 flet 的 API 面」。约束
    住这一点，换底座（或 cs-ui 内部换实现）时改动面才是可控的。
    """
    offenders: list[str] = []
    for path in PACKAGE.rglob("*.py"):
        if "__pycache__" in path.parts or _layer_of(path.relative_to(PACKAGE)) != "view":
            continue
        _, third_party = _imports(path)
        if "flet" in third_party:
            offenders.append(str(path.relative_to(PACKAGE)))
    assert not offenders, f"视图层不得直接 import flet：{offenders}"


#: 视图层唯一允许点名原生控件的文件（其余一律用 ``ui`` 顶层导出的名字）。
PRIMITIVE_MODULE = Path("view/components/primitives.py")

#: 该文件里允许出现的原生控件名；每加一个都要在模块里写明「为什么 cs-ui 的
#: 同名组件不能替代」。
PRIMITIVE_CONTROLS = {"Chip", "Slider"}


def _attribute_uses(path: Path, holder: str) -> list[tuple[int, str]]:
    """``holder.attr`` 形式的属性访问 → ``[(行号, attr)]``。"""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    return [
        (node.lineno, node.attr)
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == holder
    ]


def test_view_builds_controls_only_through_cs_ui() -> None:
    """视图层的控件与设计令牌一律从 ``ui`` 顶层导入，代码里不出现 flet 前缀。

    为什么卡得这么死：``ui`` 对 cs-ui 没封装的名字是**透传** flet 的，所以两种
    写法功能等价；但「代码里出现 ``ft.``」会让两件事变得不可判定——

    - 这个控件到底来自 cs-ui（可能有更合适的封装）还是被迫用原生？
    - 换 UI 底座时，哪些调用点需要重写？

    收成一个出口（:mod:`cs_music_player.view.components.primitives`）之后，
    ``grep "ft\\." view/`` 的结果就是「cs-ui 的缺口清单」，一眼可数。
    """
    offenders: list[str] = []
    for path in sorted((PACKAGE / "view").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(PACKAGE)
        if rel == PRIMITIVE_MODULE:
            continue
        offenders += [
            f"{rel}:{line} ft.{attr}" for line, attr in _attribute_uses(path, "ft")
        ]
    assert not offenders, (
        "视图层不得出现 flet 前缀（控件 / 值类型都从 ui 顶层导入）："
        f"{offenders}"
    )


def test_primitive_exceptions_stay_explicit() -> None:
    """原生出入口不允许悄悄变宽：新增控件必须同时改白名单并写明理由。"""
    used = {attr for _, attr in _attribute_uses(PACKAGE / PRIMITIVE_MODULE, "ft")}
    unexpected = sorted(used - PRIMITIVE_CONTROLS)
    assert not unexpected, (
        f"{PRIMITIVE_MODULE} 里出现了未登记的原生控件 {unexpected}；"
        "请先确认 cs-ui 没有等价封装，再更新 PRIMITIVE_CONTROLS 与模块说明"
    )
    assert used, "primitives 应当至少登记一个原生控件，否则这个文件可以删掉"


def test_view_ui_imports_resolve() -> None:
    """``from ui import X`` 的每个名字都必须真的存在——否则只会在运行时炸。"""
    import ui  # 延迟导入：本文件的其它用例不依赖 UI 组件库

    missing: list[str] = []
    for path in sorted((PACKAGE / "view").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "ui":
                missing += [
                    f"{path.name}: ui.{alias.name}"
                    for alias in node.names
                    if not hasattr(ui, alias.name)
                ]
    assert not missing, f"ui 里没有这些名字：{missing}"


def test_viewmodel_and_service_never_touch_the_ui_toolkit() -> None:
    """视图模型与服务层必须与 Flet 完全无关（需求原文：纯 Python 类）。"""
    for layer in ("models", "viewmodel", "service"):
        for path in PACKAGE.rglob("*.py"):
            if "__pycache__" in path.parts or _layer_of(path.relative_to(PACKAGE)) != layer:
                continue
            _, third_party = _imports(path)
            assert "flet" not in third_party, f"{path} 引用了 flet"


# 子进程里做「导入期零 UI 依赖」的运行时验证：同进程里 flet 可能已被别的
# 测试导入，只有全新解释器才能证明这件事。
_RUNTIME_CHECK = (
    "import sys;"
    "import {module};"
    "leaked=sorted(m for m in sys.modules if m.split('.')[0] in {{'flet','flet_audio','flet_desktop','PIL','mutagen'}});"
    "assert not leaked, leaked;"
    "print('ok')"
)


@pytest.mark.parametrize(
    "module",
    [
        "cs_music_player.models",
        "cs_music_player.service",
        "cs_music_player.viewmodel",
    ],
)
def test_import_graph_stays_free_of_ui_and_tech(module: str) -> None:
    code = _RUNTIME_CHECK.format(module=module)
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(PACKAGE.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_every_package_file_is_classified() -> None:
    """守卫一下守卫本身：包内每个文件都必须落在某个层或组装根里。

    否则新加一个 ``cs_music_player/helpers.py`` 就能绕开所有分层检查。
    """
    unclassified = [
        str(path.relative_to(PACKAGE))
        for path in sorted(PACKAGE.rglob("*.py"))
        if "__pycache__" not in path.parts
        and _layer_of(path.relative_to(PACKAGE)) is None
        and not _is_assembly_root(path.relative_to(PACKAGE))
    ]
    assert not unclassified, (
        f"这些文件既不属于任何一层也不是组装根：{unclassified}"
        "（新模块请放进 models/infra/service/viewmodel/view）"
    )


def test_no_opaque_dynamic_imports_outside_package_init() -> None:
    """非字面量的动态导入会让分层检查失效，只允许出现在包的 ``__init__`` 里。"""
    offenders: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        if "__pycache__" in path.parts or path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        _, opaque = _dynamic_targets(tree, _module_package(path))
        if opaque:
            offenders.append(f"{path.relative_to(PACKAGE)}: {', '.join(opaque)}")
    assert not offenders, f"无法静态判定的动态导入：{offenders}"


def test_lazy_exports_targets_stay_inside_the_layer() -> None:
    """PEP 562 惰性转出表指向的子模块也必须遵守同一层的依赖规则。"""
    for layer, path in MODULES:
        if path.name != "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        targets, _ = _dynamic_targets(tree, _module_package(path))
        allowed = ALLOWED_PACKAGE_PREFIXES[layer]
        for target in sorted(targets):
            relative = target[len(PACKAGE_NAME) + 1 :]
            assert any(
                relative == prefix or relative.startswith(f"{prefix}.")
                for prefix in allowed
            ), f"{path.name} 的惰性转出指向 {relative}，超出允许范围 {allowed}"


def test_infra_ports_is_importable_without_any_adapter() -> None:
    """抽象接口本身必须零依赖：它被 service 直接引用。"""
    code = (
        "import sys;"
        "import cs_music_player.infra.ports;"
        "leaked=sorted(m for m in sys.modules if m.split('.')[0] in {'flet','flet_audio','PIL','mutagen'});"
        "assert not leaked, leaked;"
        "print('ok')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(PACKAGE.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
