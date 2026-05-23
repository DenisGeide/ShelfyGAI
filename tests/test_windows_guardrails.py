from __future__ import annotations

import sys
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows guardrails")

win32con = pytest.importorskip("win32con")

from shelfygai.core.errors import WindowOperationError  # noqa: E402
from shelfygai.core.models import WindowInfo  # noqa: E402
from shelfygai.i18n import set_language  # noqa: E402
from shelfygai.platform.windows import window_gateway as gateway_module  # noqa: E402
from shelfygai.platform.windows.window_gateway import (  # noqa: E402
    ManagedWindowStyle,
    PinnedWindowStyle,
    WindowsWindowGateway,
)


@pytest.fixture(autouse=True)
def english_locale() -> Iterator[None]:
    set_language("en")
    yield
    set_language("en")


def test_hide_window_applies_reversible_taskbar_style(monkeypatch: pytest.MonkeyPatch) -> None:
    gateway, calls = _make_gateway(monkeypatch)

    gateway.hide_window(100)

    expected_style = win32con.WS_EX_TOOLWINDOW
    assert calls["set_styles"] == [expected_style]
    assert calls["verify_styles"] == [expected_style]
    assert calls["refresh"] == [100]
    assert gateway.managed_styles_snapshot()[100] == ManagedWindowStyle(
        handle=100,
        original_extended_style=win32con.WS_EX_APPWINDOW,
        managed_extended_style=expected_style,
        process_id=42,
        process_name="editor.exe",
        class_name="Chrome_WidgetWin_1",
    )


def test_hide_window_ignores_duplicate_management(monkeypatch: pytest.MonkeyPatch) -> None:
    gateway, calls = _make_gateway(monkeypatch)

    gateway.hide_window(100)
    gateway.hide_window(100)

    expected_style = win32con.WS_EX_TOOLWINDOW
    assert calls["set_styles"] == [expected_style]
    assert calls["refresh"] == [100]
    assert list(gateway.managed_styles_snapshot()) == [100]


def test_restore_window_restores_original_style_and_clears_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway, calls = _make_gateway(monkeypatch)

    gateway.hide_window(100)
    gateway.restore_window(100, focus=False)

    assert calls["set_styles"] == [
        win32con.WS_EX_TOOLWINDOW,
        win32con.WS_EX_APPWINDOW,
    ]
    assert calls["refresh"] == [100, 100]
    assert gateway.managed_styles_snapshot() == {}


def test_pin_window_sets_topmost_and_preserves_original_styles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway, calls = _make_gateway(
        monkeypatch,
        style=0,
        normal_style=win32con.WS_MINIMIZEBOX,
    )

    gateway.pin_window(100, prevent_minimize=True)

    assert calls["set_normal_styles"] == [0]
    assert calls["topmost"] == [True]
    assert gateway.pinned_styles_snapshot()[100] == PinnedWindowStyle(
        handle=100,
        original_style=win32con.WS_MINIMIZEBOX,
        original_extended_style=0,
        pinned_extended_style=win32con.WS_EX_TOPMOST,
        process_id=42,
        process_name="editor.exe",
        class_name="Chrome_WidgetWin_1",
        prevent_minimize=True,
    )


def test_unpin_window_restores_original_styles_and_topmost_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway, calls = _make_gateway(
        monkeypatch,
        style=win32con.WS_EX_TOPMOST,
        normal_style=win32con.WS_MINIMIZEBOX,
    )

    gateway.pin_window(100, prevent_minimize=True)
    gateway.unpin_window(100)

    assert calls["set_normal_styles"] == [0, win32con.WS_MINIMIZEBOX]
    assert calls["set_styles"] == [win32con.WS_EX_TOPMOST]
    assert calls["topmost"] == [True, True]
    assert gateway.pinned_styles_snapshot() == {}


def test_is_window_available_drops_closed_managed_style(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway, _calls = _make_gateway(monkeypatch)
    gateway.hide_window(100)
    monkeypatch.setattr(gateway_module.win32gui, "IsWindow", lambda _handle: False)

    assert gateway.is_window_available(100) is False
    assert gateway.managed_styles_snapshot() == {}


@pytest.mark.parametrize(
    ("window", "class_name", "style", "owner", "elevation", "message"),
    [
        (
            WindowInfo(100, "ShelfyGAI", 999, "python.exe"),
            "QtWindow",
            win32con.WS_EX_APPWINDOW,
            0,
            False,
            "ShelfyGAI cannot hide its own window",
        ),
        (
            WindowInfo(100, "Taskbar", 42, "explorer.exe"),
            "Shell_TrayWnd",
            win32con.WS_EX_APPWINDOW,
            0,
            False,
            "Explorer shell windows cannot be managed",
        ),
        (
            WindowInfo(100, "Start", 42, "StartMenuExperienceHost.exe"),
            "Windows.UI.Core.CoreWindow",
            win32con.WS_EX_APPWINDOW,
            0,
            False,
            "The Windows Start Menu cannot be managed",
        ),
        (
            WindowInfo(100, "Secure Desktop", 42, "LogonUI.exe"),
            "Credential Dialog",
            win32con.WS_EX_APPWINDOW,
            0,
            False,
            "Critical system windows cannot be managed",
        ),
        (
            WindowInfo(100, "Admin Tool", 42, "admin-tool.exe"),
            "Chrome_WidgetWin_1",
            win32con.WS_EX_APPWINDOW,
            0,
            True,
            "running as administrator",
        ),
        (
            WindowInfo(100, "Palette", 42, "palette.exe"),
            "PaletteWindow",
            win32con.WS_EX_APPWINDOW | win32con.WS_EX_NOACTIVATE,
            0,
            False,
            "may not support taskbar style changes",
        ),
        (
            WindowInfo(100, "Owned Utility", 42, "utility.exe"),
            "UtilityWindow",
            0,
            200,
            False,
            "Owned utility windows cannot be managed",
        ),
    ],
)
def test_hide_window_refuses_unsafe_targets(
    monkeypatch: pytest.MonkeyPatch,
    window: WindowInfo,
    class_name: str,
    style: int,
    owner: int,
    elevation: bool | None,
    message: str,
) -> None:
    gateway, calls = _make_gateway(
        monkeypatch,
        window=window,
        class_name=class_name,
        style=style,
        owner=owner,
        elevation=elevation,
    )

    with pytest.raises(WindowOperationError, match=message):
        gateway.hide_window(100)

    assert calls["set_styles"] == []
    assert gateway.managed_styles_snapshot() == {}


def test_hide_window_refuses_when_owner_check_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway, calls = _make_gateway(monkeypatch, owner_error=True)

    with pytest.raises(WindowOperationError, match="Could not verify whether this window"):
        gateway.hide_window(100)

    assert calls["set_styles"] == []
    assert gateway.managed_styles_snapshot() == {}


def _make_gateway(
    monkeypatch: pytest.MonkeyPatch,
    *,
    window: WindowInfo | None = None,
    class_name: str = "Chrome_WidgetWin_1",
    style: int = win32con.WS_EX_APPWINDOW,
    normal_style: int = win32con.WS_MINIMIZEBOX,
    owner: int = 0,
    owner_error: bool = False,
    elevation: bool | None = False,
) -> tuple[WindowsWindowGateway, dict[str, list[int]]]:
    gateway = object.__new__(WindowsWindowGateway)
    gateway._own_process_id = 999
    gateway._own_process_elevated = False
    gateway._managed_styles = {}
    gateway._pinned_styles = {}

    active_window = window or WindowInfo(100, "Editor", 42, "editor.exe")
    calls: dict[str, list[int]] = {
        "set_styles": [],
        "set_normal_styles": [],
        "verify_styles": [],
        "refresh": [],
        "topmost": [],
    }

    monkeypatch.setattr(gateway, "_ensure_window", lambda _handle: None)
    monkeypatch.setattr(gateway, "get_window", lambda _handle, **_kwargs: active_window)
    monkeypatch.setattr(gateway, "_window_class_name", lambda _handle: class_name)
    monkeypatch.setattr(gateway, "_get_extended_style", lambda _handle: style)
    monkeypatch.setattr(gateway, "_get_style", lambda _handle: normal_style)
    monkeypatch.setattr(gateway, "_process_elevation_state", lambda _pid: elevation)

    def set_extended_style(_handle: int, value: int) -> None:
        calls["set_styles"].append(value)

    def set_style(_handle: int, value: int) -> None:
        calls["set_normal_styles"].append(value)

    def verify_extended_style(_handle: int, value: int) -> None:
        calls["verify_styles"].append(value)

    def refresh_window_frame(handle: int) -> None:
        calls["refresh"].append(handle)

    def set_topmost(_handle: int, *, enabled: bool) -> None:
        calls["topmost"].append(enabled)

    monkeypatch.setattr(gateway, "_set_extended_style", set_extended_style)
    monkeypatch.setattr(gateway, "_set_style", set_style)
    monkeypatch.setattr(gateway, "_verify_extended_style", verify_extended_style)
    monkeypatch.setattr(gateway, "_refresh_window_frame", refresh_window_frame)
    monkeypatch.setattr(gateway, "_set_topmost", set_topmost)

    def fake_get_window(_handle: int, _command: int) -> int:
        if owner_error:
            raise gateway_module.win32gui.error("owner read failed")
        return owner

    monkeypatch.setattr(gateway_module.win32gui, "GetWindow", fake_get_window)
    monkeypatch.setattr(gateway_module.win32gui, "IsWindow", lambda _handle: True)
    return gateway, calls
