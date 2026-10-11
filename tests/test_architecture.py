"""分层架构回归：用 AST 静态校验单向依赖。

对应需求里的硬约束：

    view ──▶ viewmodel ──▶ service ──▶ infra
       ╲         │            │          │
        ╲        ▼            ▼          ▼
         ╲────────────── models ─────────┘

- 只允许箭头方向的依赖，禁止反向与跨层；
- 高层只依赖**抽象接口**：service 只允许碰 ``infra.ports``；
- models / service / viewmodel 三层不得出现任何 UI / 底层技术依赖。
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
ALLOWED_THIRD_PARTY: dict[str, tuple[str, ...]] = {
    "models": (),
    "service": (),
    "viewmodel": (),
    "infra": ("flet", "flet_audio", "flet_desktop", "mutagen", "PIL"),
    "view": ("flet",),
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
