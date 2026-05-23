from __future__ import annotations

import pytest

from shelfygai.platform.windows.hotkeys import HotkeyParseError, parse_hotkey_sequence


def test_parse_default_hotkey() -> None:
    spec = parse_hotkey_sequence("Ctrl+Shift+Space")

    assert spec.modifiers != 0
    assert spec.virtual_key == 0x20


def test_parse_function_key_hotkey() -> None:
    spec = parse_hotkey_sequence("Alt+F12")

    assert spec.virtual_key == 0x7B


def test_parse_rejects_missing_modifier() -> None:
    with pytest.raises(HotkeyParseError):
        parse_hotkey_sequence("Space")


def test_parse_rejects_unknown_key() -> None:
    with pytest.raises(HotkeyParseError):
        parse_hotkey_sequence("Ctrl+Shift+Banana")
