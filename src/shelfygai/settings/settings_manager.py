from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

import psutil

from shelfygai.constants import APP_VERSION, SETTINGS_SCHEMA_VERSION, default_settings_path
from shelfygai.core.models import DEFAULT_GROUP_ID
from shelfygai.i18n import default_language

LOGGER = logging.getLogger(__name__)

DEFAULT_GROUP = {"id": DEFAULT_GROUP_ID, "name": "Ungrouped", "sort_order": 0}
OVERLAY_MARKER_DEFAULTS = {
    "marker_width": 10,
    "marker_height": 88,
    "opacity": 0.95,
    "corner_radius": 6,
    "hover_delay_ms": 1200,
    "locked_position": False,
    "hide_during_fullscreen": True,
    "show_quick_controls": True,
}
OVERLAY_POSITION_EDGES = {"bottom", "top", "left", "right"}
HOTKEY_QUICK_HIDE = "quick_hide"
HOTKEY_RESTORE_LAST = "restore_last"
HOTKEY_TOGGLE_VISIBILITY = "toggle_visibility"
HOTKEY_ACTIONS = (HOTKEY_QUICK_HIDE, HOTKEY_RESTORE_LAST, HOTKEY_TOGGLE_VISIBILITY)
DEFAULT_GLOBAL_HOTKEYS = {
    HOTKEY_QUICK_HIDE: {"enabled": True, "sequence": "Ctrl+Shift+Space"},
    HOTKEY_RESTORE_LAST: {"enabled": False, "sequence": "Ctrl+Shift+Backspace"},
    HOTKEY_TOGGLE_VISIBILITY: {"enabled": False, "sequence": "Ctrl+Shift+S"},
}


@dataclass(slots=True)
class AppSettings:
    settings_schema_version: int = SETTINGS_SCHEMA_VERSION
    app_version: str = APP_VERSION
    debug_mode: bool = False
    onboarding_completed: bool = False
    language: str = field(default_factory=default_language)
    theme: str = "dark"
    accent_color: str = "#2f81f7"
    launch_with_windows: bool = False
    minimize_to_tray_on_close: bool = False
    startup_notification_enabled: bool = True
    silent_startup: bool = False
    open_windows_auto_refresh: bool = False
    focus_restored_windows: bool = True
    confirm_before_hiding: bool = True
    confirm_quit_with_hidden_windows: bool = True
    restore_windows_on_exit: bool = True
    restore_pinned_windows_on_exit: bool = True
    prevent_minimize_watcher_enabled: bool = True
    pinned_watcher_interval_ms: int = 500
    allow_pin_shelfygai_window: bool = False
    selected_group_id: str = DEFAULT_GROUP_ID
    window_groups: list[dict[str, Any]] = field(default_factory=lambda: [DEFAULT_GROUP.copy()])
    overlay_groups_enabled: bool = False
    selected_overlay_group_id: str = ""
    overlay_groups: list[dict[str, Any]] = field(default_factory=list)
    managed_windows: list[dict[str, Any]] = field(default_factory=list)
    global_hotkeys: dict[str, dict[str, Any]] = field(
        default_factory=lambda: _copy_hotkey_defaults()
    )
    window_geometry: str | None = None


class SettingsManager:
    """Robust JSON settings manager with safe defaults and corruption fallback."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_settings_path()
        self._settings = AppSettings()

    @property
    def settings(self) -> AppSettings:
        return _copy_settings(self._settings)

    def load(self) -> AppSettings:
        default_settings = AppSettings()

        try:
            settings_file_exists = self.path.exists()
        except OSError as exc:
            LOGGER.warning("Could not inspect settings file; using defaults: %s", exc)
            self._settings = default_settings
            return _copy_settings(self._settings)

        if not settings_file_exists:
            self._settings = default_settings
            self.save(default_settings, reason="created default settings")
            return _copy_settings(self._settings)

        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            LOGGER.warning("Settings file is unavailable or invalid; using defaults: %s", exc)
            self._settings = default_settings
            self.save(default_settings, reason="recovered from invalid settings")
            return _copy_settings(self._settings)

        if not isinstance(payload, dict):
            LOGGER.warning("Settings file did not contain a JSON object; using defaults")
            self._settings = default_settings
            self.save(default_settings, reason="recovered from invalid settings shape")
            return _copy_settings(self._settings)

        self._settings = _settings_from_payload(payload, default_settings)
        if payload != asdict(self._settings):
            self.save(self._settings, reason="normalized settings")
        else:
            LOGGER.debug("Settings loaded without normalization write")
        return _copy_settings(self._settings)

    def save(self, settings: AppSettings, *, reason: str = "settings changed") -> bool:
        previous_settings = _copy_settings(self._settings)
        normalized = _normalize_settings(_copy_settings(settings))
        payload = json.dumps(asdict(normalized), indent=2, sort_keys=True)
        temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_text(payload, encoding="utf-8")
            temp_path.replace(self.path)
        except OSError as exc:
            LOGGER.exception("Could not save settings to %s: %s", self.path, exc)
            return False

        self._settings = normalized
        changed_fields = _changed_fields(previous_settings, normalized)
        if changed_fields:
            LOGGER.info(
                "Settings saved (%s): %s",
                reason,
                ", ".join(changed_fields),
            )
        else:
            LOGGER.debug("Settings saved (%s): no value changes", reason)
        return True

    def reset_to_defaults(self) -> AppSettings:
        defaults = AppSettings()
        self.save(defaults, reason="reset to defaults")
        return _copy_settings(self._settings)


JsonSettingsStore = SettingsManager


def _settings_from_payload(payload: dict[str, Any], defaults: AppSettings) -> AppSettings:
    values = asdict(defaults)
    for app_field in fields(AppSettings):
        if app_field.name not in payload:
            continue
        values[app_field.name] = _coerce_setting(
            app_field.name,
            payload[app_field.name],
            values[app_field.name],
        )
    return _normalize_settings(AppSettings(**values))


def _coerce_setting(name: str, value: Any, default: Any) -> Any:
    if isinstance(default, bool):
        return value if isinstance(value, bool) else default
    if isinstance(default, int):
        return value if isinstance(value, int) and not isinstance(value, bool) else default
    if default is None and name == "window_geometry":
        return value if isinstance(value, str) or value is None else None
    if isinstance(default, str):
        return value if isinstance(value, str) else default
    if isinstance(default, list):
        return value if isinstance(value, list) else default
    if isinstance(default, dict):
        return value if isinstance(value, dict) else default
    return default


def _normalize_settings(settings: AppSettings) -> AppSettings:
    settings.settings_schema_version = SETTINGS_SCHEMA_VERSION
    settings.app_version = APP_VERSION
    if settings.language not in {"en", "ru"}:
        settings.language = default_language()
    if settings.theme not in {"system", "dark", "light"}:
        settings.theme = "dark"
    if not _is_hex_color(settings.accent_color):
        settings.accent_color = "#2f81f7"
    settings.window_groups = _normalize_groups(settings.window_groups)
    settings.overlay_groups = _normalize_overlay_groups(settings.overlay_groups)
    group_ids = {group["id"] for group in settings.window_groups}
    if settings.selected_group_id not in group_ids:
        settings.selected_group_id = DEFAULT_GROUP_ID
    overlay_group_ids = {group["id"] for group in settings.overlay_groups}
    if settings.selected_overlay_group_id not in overlay_group_ids:
        settings.selected_overlay_group_id = (
            settings.overlay_groups[0]["id"] if settings.overlay_groups else ""
        )
    settings.managed_windows = _normalize_managed_windows(settings.managed_windows, group_ids)
    settings.global_hotkeys = _normalize_hotkeys(settings.global_hotkeys)
    settings.pinned_watcher_interval_ms = _clamp_int(
        settings.pinned_watcher_interval_ms,
        minimum=100,
        maximum=10_000,
        default=500,
    )
    return settings


def _normalize_hotkeys(hotkeys: dict[str, Any]) -> dict[str, dict[str, Any]]:
    normalized = _copy_hotkey_defaults()
    if not isinstance(hotkeys, dict):
        return normalized

    for action_id in HOTKEY_ACTIONS:
        raw_hotkey = hotkeys.get(action_id)
        if not isinstance(raw_hotkey, dict):
            continue
        enabled = raw_hotkey.get("enabled", normalized[action_id]["enabled"])
        sequence = raw_hotkey.get("sequence", normalized[action_id]["sequence"])
        normalized[action_id] = {
            "enabled": enabled if isinstance(enabled, bool) else normalized[action_id]["enabled"],
            "sequence": _normalize_hotkey_sequence(sequence, normalized[action_id]["sequence"]),
        }
    return normalized


def _normalize_hotkey_sequence(value: Any, default: str) -> str:
    if not isinstance(value, str):
        return default
    stripped = value.strip()
    if len(stripped) > 80:
        return default
    return stripped


def _normalize_groups(groups: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = [DEFAULT_GROUP.copy()]
    seen = {DEFAULT_GROUP_ID}

    for raw_group in groups:
        if not isinstance(raw_group, dict):
            continue
        group_id = raw_group.get("id")
        name = raw_group.get("name")
        sort_order = raw_group.get("sort_order", len(normalized))
        if not isinstance(group_id, str) or not group_id.strip():
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        if group_id == DEFAULT_GROUP_ID or group_id in seen:
            continue
        if not isinstance(sort_order, int) or isinstance(sort_order, bool):
            sort_order = len(normalized)
        normalized.append(
            {
                "id": group_id.strip(),
                "name": name.strip(),
                "sort_order": sort_order,
            }
        )
        seen.add(group_id)

    return sorted(
        normalized,
        key=lambda group: (
            group["id"] != DEFAULT_GROUP_ID,
            group["sort_order"],
            group["name"].lower(),
        ),
    )


def _normalize_overlay_groups(groups: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw_group in groups:
        if not isinstance(raw_group, dict):
            continue
        group_id = raw_group.get("id")
        name = raw_group.get("name")
        if not isinstance(group_id, str) or not group_id.strip():
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        group_id = group_id.strip()
        if group_id in seen:
            continue
        seen.add(group_id)
        normalized.append(
            {
                "id": group_id,
                "name": name.strip(),
                "color": _normalize_color(raw_group.get("color"), "#2f81f7"),
                "marker_width": _clamp_int(
                    raw_group.get("marker_width"),
                    minimum=4,
                    maximum=64,
                    default=OVERLAY_MARKER_DEFAULTS["marker_width"],
                ),
                "marker_height": _clamp_int(
                    raw_group.get("marker_height"),
                    minimum=24,
                    maximum=256,
                    default=OVERLAY_MARKER_DEFAULTS["marker_height"],
                ),
                "opacity": _clamp_float(
                    raw_group.get("opacity"),
                    minimum=0.2,
                    maximum=1.0,
                    default=OVERLAY_MARKER_DEFAULTS["opacity"],
                ),
                "corner_radius": _clamp_int(
                    raw_group.get("corner_radius"),
                    minimum=0,
                    maximum=32,
                    default=OVERLAY_MARKER_DEFAULTS["corner_radius"],
                ),
                "hover_delay_ms": _clamp_int(
                    raw_group.get("hover_delay_ms"),
                    minimum=0,
                    maximum=5_000,
                    default=OVERLAY_MARKER_DEFAULTS["hover_delay_ms"],
                ),
                "locked_position": _normalize_bool(
                    raw_group.get("locked_position"),
                    OVERLAY_MARKER_DEFAULTS["locked_position"],
                ),
                "hide_during_fullscreen": _normalize_bool(
                    raw_group.get("hide_during_fullscreen"),
                    OVERLAY_MARKER_DEFAULTS["hide_during_fullscreen"],
                ),
                "show_quick_controls": _normalize_bool(
                    raw_group.get("show_quick_controls"),
                    OVERLAY_MARKER_DEFAULTS["show_quick_controls"],
                ),
                "position_by_monitor": _normalize_overlay_positions(
                    raw_group.get("position_by_monitor")
                ),
                "assigned_window_ids": _normalize_overlay_window_ids(
                    raw_group.get("assigned_window_ids")
                ),
            }
        )

    return sorted(normalized, key=lambda group: group["name"].lower())


def _normalize_overlay_positions(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for monitor_id, raw_position in value.items():
        if not isinstance(monitor_id, str) or not monitor_id.strip():
            continue
        if not isinstance(raw_position, dict):
            continue
        x = raw_position.get("x")
        y = raw_position.get("y")
        edge = raw_position.get("edge", "bottom")
        if not isinstance(x, int) or isinstance(x, bool):
            continue
        if not isinstance(y, int) or isinstance(y, bool):
            continue
        if edge not in OVERLAY_POSITION_EDGES:
            edge = "bottom"
        normalized[monitor_id.strip()] = {"x": x, "y": y, "edge": edge}
    return normalized


def _normalize_overlay_window_ids(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    normalized: list[int] = []
    for handle in value:
        if not isinstance(handle, int) or isinstance(handle, bool) or handle <= 0:
            continue
        if handle not in normalized:
            normalized.append(handle)
    return normalized


def _normalize_managed_windows(
    windows: list[Any],
    group_ids: set[str],
) -> list[dict[str, Any]]:
    boot_id = current_boot_id()
    normalized: list[dict[str, Any]] = []
    for raw_window in windows:
        if not isinstance(raw_window, dict):
            continue
        if raw_window.get("boot_id") != boot_id:
            continue
        handle = raw_window.get("handle")
        title = raw_window.get("title")
        process_id = raw_window.get("process_id")
        process_name = raw_window.get("process_name")
        group_id = raw_window.get("group_id", DEFAULT_GROUP_ID)
        hidden_at = raw_window.get("hidden_at")
        executable_path = raw_window.get("executable_path")
        if not isinstance(handle, int) or isinstance(handle, bool):
            continue
        if not isinstance(title, str) or not title:
            continue
        if not isinstance(process_id, int) or isinstance(process_id, bool):
            continue
        if not isinstance(process_name, str) or not process_name:
            continue
        if not isinstance(group_id, str) or group_id not in group_ids:
            group_id = DEFAULT_GROUP_ID
        if not isinstance(hidden_at, str):
            hidden_at = ""
        if executable_path is not None and not isinstance(executable_path, str):
            executable_path = None
        normalized.append(
            {
                "boot_id": boot_id,
                "handle": handle,
                "title": title,
                "process_id": process_id,
                "process_name": process_name,
                "executable_path": executable_path,
                "group_id": group_id,
                "hidden_at": hidden_at,
            }
        )
    return normalized


def _changed_fields(before: AppSettings, after: AppSettings) -> list[str]:
    return [
        field.name
        for field in fields(AppSettings)
        if getattr(before, field.name) != getattr(after, field.name)
    ]


def _normalize_bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _normalize_color(value: Any, default: str) -> str:
    return value if isinstance(value, str) and _is_hex_color(value) else default


def _is_hex_color(value: str) -> bool:
    if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
        return False
    return all(character in "0123456789abcdefABCDEF" for character in value[1:])


def _clamp_int(value: Any, *, minimum: int, maximum: int, default: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        return default
    return max(minimum, min(value, maximum))


def _clamp_float(value: Any, *, minimum: float, maximum: float, default: float) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return default
    return max(minimum, min(float(value), maximum))


def _copy_settings(settings: AppSettings) -> AppSettings:
    return AppSettings(**asdict(settings))


def _copy_hotkey_defaults() -> dict[str, dict[str, Any]]:
    return {
        action_id: dict(config)
        for action_id, config in DEFAULT_GLOBAL_HOTKEYS.items()
    }


def current_boot_id() -> str:
    try:
        return str(int(psutil.boot_time()))
    except (OSError, RuntimeError):
        return "unknown"
