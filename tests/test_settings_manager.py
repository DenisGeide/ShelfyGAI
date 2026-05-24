from __future__ import annotations

import json

from shelfygai.settings.settings_manager import (
    DEFAULT_GLOBAL_HOTKEYS,
    HOTKEY_HIDE_SELECTED_WINDOW,
    HOTKEY_OPEN_SWITCHER,
    HOTKEY_PIN_UNPIN_FOCUSED,
    HOTKEY_RESET_EVERYTHING,
    HOTKEY_RESTORE_LAST,
    HOTKEY_TOGGLE_OVERLAY_HUB,
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
        notifications_enabled=False,
        show_tray_notifications=False,
        show_overlay_notifications=False,
        show_restore_notifications=False,
        show_pin_unpin_notifications=False,
        silent_mode=True,
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
            HOTKEY_HIDE_SELECTED_WINDOW: {"enabled": True, "sequence": "Ctrl+Shift+H"},
            "restore_last": {"enabled": True, "sequence": "Ctrl+Alt+Backspace"},
            HOTKEY_TOGGLE_OVERLAY_HUB: {"enabled": True, "sequence": "Ctrl+Alt+O"},
            HOTKEY_OPEN_SWITCHER: {"enabled": True, "sequence": "Ctrl+Alt+J"},
            HOTKEY_PIN_UNPIN_FOCUSED: {"enabled": True, "sequence": "Ctrl+Alt+P"},
            HOTKEY_RESET_EVERYTHING: {"enabled": False, "sequence": "Ctrl+Alt+E"},
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

    assert settings.global_hotkeys[HOTKEY_HIDE_SELECTED_WINDOW] == {
        "enabled": True,
        "sequence": "Ctrl+Alt+H",
    }
    assert settings.global_hotkeys[HOTKEY_RESTORE_LAST] == {
        "enabled": True,
        "sequence": "Ctrl+Shift+R",
    }
    assert set(settings.global_hotkeys) == set(DEFAULT_GLOBAL_HOTKEYS)


def test_settings_migrates_legacy_toggle_visibility_to_overlay_hub(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "global_hotkeys": {
                    "toggle_visibility": {"enabled": True, "sequence": "Ctrl+Alt+S"},
                }
            }
        ),
        encoding="utf-8",
    )

    settings = SettingsManager(path).load()

    assert settings.global_hotkeys[HOTKEY_TOGGLE_OVERLAY_HUB] == {
        "enabled": True,
        "sequence": "Ctrl+Alt+S",
    }


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


def test_overlay_group_color_persistence(tmp_path) -> None:
    path = tmp_path / "settings.json"
    store = SettingsManager(path)
    settings = AppSettings(
        overlay_groups_enabled=True,
        selected_overlay_group_id="overlay-work",
        overlay_groups=[
            {
                "id": "overlay-work",
                "name": "Work",
                "color": "#55c2a2",
            }
        ],
    )

    store.save(settings)
    loaded = store.load()

    assert loaded.overlay_groups[0]["id"] == "overlay-work"
    assert loaded.overlay_groups_enabled is True
    assert loaded.selected_overlay_group_id == "overlay-work"
    assert loaded.overlay_groups[0]["color"] == "#55c2a2"
    assert loaded.overlay_groups[0]["marker_width"] == 8
    assert loaded.overlay_groups[0]["marker_height"] == 64
    assert loaded.overlay_groups[0]["opacity"] == 0.9


def test_overlay_marker_position_persistence(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "overlay_groups": [
                    {
                        "id": "overlay-work",
                        "name": "Work",
                        "color": "#2f81f7",
                        "position_by_monitor": {
                            "monitor-1": {"x": 1440, "y": 1000, "edge": "bottom"},
                            "monitor-2": {"x": 300, "y": 300, "edge": "free"},
                        },
                        "assigned_window_ids": [100, 100, 200, "bad"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    settings = SettingsManager(path).load()

    group = settings.overlay_groups[0]
    assert group["position_by_monitor"] == {
        "monitor-1": {"x": 1440, "y": 1000, "edge": "bottom"},
        "monitor-2": {"x": 300, "y": 300, "edge": "free"},
    }
    assert group["assigned_window_ids"] == [100, 200]


def test_overlay_default_config_migration(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"settings_schema_version": 1, "theme": "dark"}', encoding="utf-8")

    settings = SettingsManager(path).load()
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert settings.overlay_groups == []
    assert settings.overlay_groups_enabled is False
    assert settings.selected_overlay_group_id == ""
    assert payload["overlay_groups"] == []
    assert payload["overlay_groups_enabled"] is False
    assert payload["selected_overlay_group_id"] == ""
    assert payload["overlay_use_unified_hub"] is True
    assert payload["overlay_use_individual_markers"] is False
    assert payload["overlay_replace_individual_markers"] is True
    assert payload["overlay_auto_snap_to_taskbar"] is True
    assert payload["overlay_compact_mode"] is True
    assert payload["overlay_marker_spacing"] == 8
    assert payload["overlay_hub_always_visible"] is True
    assert payload["overlay_hub_auto_hide"] is False
    assert payload["overlay_hub_opacity"] == 0.94
    assert payload["overlay_hub_position_by_monitor"] == {}
    assert payload["settings_schema_version"] == AppSettings().settings_schema_version


def test_overlay_display_settings_are_normalized(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "overlay_use_unified_hub": False,
                "overlay_use_individual_markers": True,
                "overlay_replace_individual_markers": False,
                "overlay_hub_always_visible": False,
                "overlay_hub_auto_hide": True,
                "overlay_hub_opacity": 2.5,
                "overlay_auto_snap_to_taskbar": False,
                "overlay_compact_mode": False,
                "overlay_marker_spacing": 500,
                "overlay_hub_position_by_monitor": {
                    "monitor-1": {"x": 1400, "y": 990, "edge": "bottom"},
                    "monitor-free": {"x": 400, "y": 350, "edge": "free"},
                },
            }
        ),
        encoding="utf-8",
    )

    settings = SettingsManager(path).load()

    assert settings.overlay_use_unified_hub is False
    assert settings.overlay_use_individual_markers is True
    assert settings.overlay_replace_individual_markers is False
    assert settings.overlay_hub_always_visible is False
    assert settings.overlay_hub_auto_hide is True
    assert settings.overlay_hub_opacity == 1.0
    assert settings.overlay_auto_snap_to_taskbar is False
    assert settings.overlay_compact_mode is False
    assert settings.overlay_marker_spacing == 48
    assert settings.overlay_hub_position_by_monitor == {
        "monitor-1": {"x": 1400, "y": 990, "edge": "bottom"},
        "monitor-free": {"x": 400, "y": 350, "edge": "free"},
    }
