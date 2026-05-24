from __future__ import annotations

import pytest

from shelfygai.platform.windows.hotkeys import (
    HotkeyParseError,
    parse_hotkey_sequence,
    validate_hotkey_configs,
)


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


def test_validate_hotkey_configs_reports_duplicates() -> None:
    errors = validate_hotkey_configs(
        {
            "hide_selected_window": {"enabled": True, "sequence": "Ctrl+Shift+H"},
            "restore_last": {"enabled": True, "sequence": "Control+Shift+H"},
            "toggle_overlay_hub": {"enabled": False, "sequence": "Ctrl+Shift+H"},
        }
    )

    assert set(errors) == {"hide_selected_window", "restore_last"}


def test_validate_hotkey_configs_reports_invalid_enabled_sequence() -> None:
    errors = validate_hotkey_configs(
        {
            "pin_unpin_focused": {"enabled": True, "sequence": "Ctrl+Shift+Banana"},
        }
    )

    assert "pin_unpin_focused" in errors
