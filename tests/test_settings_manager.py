from __future__ import annotations

import json

from shelfygai.settings.settings_manager import (
    AppSettings,
    SettingsManager,
    current_boot_id,
    default_settings_path,
)


def test_settings_round_trip(tmp_path) -> None:
    path = tmp_path / "settings.json"
    store = SettingsManager(path)
    settings = AppSettings(
        debug_mode=True,
        onboarding_completed=True,
        theme="light",
        accent_color="#55c2a2",
        launch_with_windows=True,
        minimize_to_tray_on_close=True,
        startup_notification_enabled=False,
        silent_startup=True,
        open_windows_auto_refresh=True,
        focus_restored_windows=False,
        confirm_before_hiding=False,
        restore_windows_on_exit=False,
        restore_pinned_windows_on_exit=False,
        prevent_minimize_watcher_enabled=False,
        pinned_watcher_interval_ms=750,
        allow_pin_shelfygai_window=True,
        selected_group_id="group-work",
        window_groups=[
            {"id": "ungrouped", "name": "Ungrouped", "sort_order": 0},
            {"id": "group-work", "name": "Work", "sort_order": 1},
        ],
        managed_windows=[
            {
                "boot_id": current_boot_id(),
                "handle": 1234,
                "title": "Editor",
                "process_id": 99,
                "process_name": "editor.exe",
                "executable_path": None,
                "group_id": "group-work",
                "hidden_at": "2026-05-23T00:00:00+00:00",
            }
        ],
        global_hotkeys={
            "quick_hide": {"enabled": True, "sequence": "Ctrl+Shift+Space"},
            "restore_last": {"enabled": True, "sequence": "Ctrl+Alt+Backspace"},
            "toggle_visibility": {"enabled": True, "sequence": "Ctrl+Alt+S"},
        },
        window_geometry="abc123",
    )

    store.save(settings)
    loaded = store.load()

    assert loaded == settings


def test_settings_ignores_unknown_fields(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"confirm_before_hiding": false, "future": true}', encoding="utf-8")

    settings = SettingsManager(path).load()

    assert settings.confirm_before_hiding is False
    assert settings.restore_windows_on_exit is True


def test_default_settings_path_uses_appdata(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))

    assert default_settings_path() == tmp_path / "ShelfyGAI" / "settings.json"


def test_settings_normalize_invalid_theme_and_accent(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"theme": "neon", "accent_color": "blue"}', encoding="utf-8")

    settings = SettingsManager(path).load()

    assert settings.theme == "dark"
    assert settings.accent_color == "#2f81f7"


def test_settings_normalizes_invalid_language(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"language": "fr"}', encoding="utf-8")

    settings = SettingsManager(path).load()

    assert settings.language in {"en", "ru"}


def test_settings_auto_create_default_config(tmp_path) -> None:
    path = tmp_path / "settings.json"
    settings = SettingsManager(path).load()

    assert settings == AppSettings()
    assert json.loads(path.read_text(encoding="utf-8"))["theme"] == "dark"


def test_settings_fallback_for_corrupted_json(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{not-valid-json", encoding="utf-8")

    settings = SettingsManager(path).load()

    assert settings == AppSettings()
    assert json.loads(path.read_text(encoding="utf-8"))["accent_color"] == "#2f81f7"


def test_settings_reject_invalid_value_types(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        '{"debug_mode": "yes", "settings_schema_version": true, "window_geometry": 123}',
        encoding="utf-8",
    )

    settings = SettingsManager(path).load()

    assert settings.debug_mode is False
    assert settings.settings_schema_version == AppSettings().settings_schema_version
    assert settings.window_geometry is None


def test_settings_normalizes_hotkeys(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "global_hotkeys": {
                    "quick_hide": {"enabled": True, "sequence": "Ctrl+Alt+H"},
                    "restore_last": {"enabled": "yes", "sequence": 123},
                    "unknown": {"enabled": True, "sequence": "Ctrl+U"},
                }
            }
        ),
        encoding="utf-8",
    )

    settings = SettingsManager(path).load()

    assert settings.global_hotkeys["quick_hide"] == {
        "enabled": True,
        "sequence": "Ctrl+Alt+H",
    }
    assert settings.global_hotkeys["restore_last"] == {
        "enabled": False,
        "sequence": "Ctrl+Shift+Backspace",
    }
    assert set(settings.global_hotkeys) == {"quick_hide", "restore_last", "toggle_visibility"}


def test_settings_normalizes_pinned_watcher_interval(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"pinned_watcher_interval_ms": 5}', encoding="utf-8")

    settings = SettingsManager(path).load()

    assert settings.pinned_watcher_interval_ms == 100


def test_settings_filters_stale_hwnd_metadata_after_reboot(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "window_groups": [
                    {"id": "ungrouped", "name": "Ungrouped", "sort_order": 0},
                    {"id": "group-work", "name": "Work", "sort_order": 1},
                ],
                "managed_windows": [
                    {
                        "boot_id": "previous-boot",
                        "handle": 1234,
                        "title": "Editor",
                        "process_id": 99,
                        "process_name": "editor.exe",
                        "group_id": "group-work",
                        "hidden_at": "2026-05-23T00:00:00+00:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    settings = SettingsManager(path).load()

    assert settings.managed_windows == []
    assert [group["id"] for group in settings.window_groups] == ["ungrouped", "group-work"]
