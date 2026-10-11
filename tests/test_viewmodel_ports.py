"""DIP 契约测试：具体服务必须满足视图模型声明的 ``Protocol``。"""
from __future__ import annotations

import inspect
from typing import Protocol

import pytest

from cs_music_player.service.desktop_lyric import DesktopLyricService
from cs_music_player.service.folders import FolderHistoryService
from cs_music_player.service.library import LibraryService
from cs_music_player.service.lyrics import LyricsService
from cs_music_player.service.playback import PlaybackService
from cs_music_player.service.settings import SettingsService
from cs_music_player.viewmodel import ports

#: (视图模型声明的能力, service 层实现)
CONTRACTS = [
    (ports.PlaybackOps, PlaybackService),
    (ports.LibraryOps, LibraryService),
    (ports.FolderHistoryOps, FolderHistoryService),
    (ports.LyricsOps, LyricsService),
    (ports.SettingsOps, SettingsService),
    (ports.DesktopLyricOps, DesktopLyricService),
]


def _protocol_members(proto: type) -> list[str]:
    return sorted(
        name
        for name, value in vars(proto).items()
        if not name.startswith("_") and callable(value)
    )


@pytest.mark.parametrize("proto,impl", CONTRACTS, ids=[p.__name__ for p, _ in CONTRACTS])
def test_protocol_members_exist_on_the_implementation(proto: type, impl: type) -> None:
    missing = [n for n in _protocol_members(proto) if not hasattr(impl, n)]
    assert not missing, f"{impl.__name__} 缺少 {proto.__name__} 要求的成员：{missing}"


@pytest.mark.parametrize("proto,impl", CONTRACTS, ids=[p.__name__ for p, _ in CONTRACTS])
def test_signatures_stay_compatible(proto: type, impl: type) -> None:
    """参数名 / 种类 / 默认值必须一致——接口漂移要在这里被拦住。"""
    problems: list[str] = []
    for name in _protocol_members(proto):
        proto_params = list(inspect.signature(getattr(proto, name)).parameters.values())
        impl_params = list(inspect.signature(getattr(impl, name)).parameters.values())
        if len(proto_params) != len(impl_params):
            problems.append(f"{name}: 参数个数 {len(impl_params)} != {len(proto_params)}")
            continue
        for expected, actual in zip(proto_params, impl_params):
            if expected.name != actual.name:
                problems.append(f"{name}: 参数名 {actual.name!r} != {expected.name!r}")
            if expected.kind != actual.kind:
                problems.append(f"{name}: 参数 {actual.name} 的种类不一致")
            if (expected.default is inspect.Parameter.empty) != (
                actual.default is inspect.Parameter.empty
            ):
                problems.append(f"{name}: 参数 {actual.name} 的默认值有无不一致")
    assert not problems, f"{impl.__name__} 与 {proto.__name__} 不兼容：{problems}"


@pytest.mark.parametrize("proto,impl", CONTRACTS, ids=[p.__name__ for p, _ in CONTRACTS])
def test_runtime_checkable_isinstance_passes(proto: type, impl: type) -> None:
    """``runtime_checkable`` 的 ``isinstance`` 只查名字，作为最外层冒烟。"""
    assert issubclass(impl, proto)


def test_viewmodel_ports_declare_no_implementation() -> None:
    """契约模块只允许 ``Protocol``，不许出现具体实现。"""
    classes = [
        value
        for value in vars(ports).values()
        if isinstance(value, type) and value.__module__ == ports.__name__
    ]
    assert classes, "没有找到任何契约"
    for cls in classes:
        assert issubclass(cls, Protocol), f"{cls.__name__} 不是 Protocol"
