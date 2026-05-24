from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

DEFAULT_GROUP_ID = "ungrouped"


@dataclass(frozen=True, slots=True)
class WindowInfo:
    handle: int
    title: str
    process_id: int
    process_name: str
    executable_path: str | None = None
    is_visible: bool = True
    is_minimized: bool = False


@dataclass(frozen=True, slots=True)
class HideOptions:
    hide_taskbar: bool = True
    hide_alt_tab: bool = True
    hide_tray: bool = False

    @property
    def has_any_target(self) -> bool:
        return self.hide_taskbar or self.hide_alt_tab or self.hide_tray

    @property
    def has_style_target(self) -> bool:
        return self.hide_taskbar or self.hide_alt_tab


@dataclass(frozen=True, slots=True)
class ShelfItem:
    window: WindowInfo
    hidden_at: datetime
    group_id: str = DEFAULT_GROUP_ID


@dataclass(frozen=True, slots=True)
class PinnedItem:
    window: WindowInfo
    pinned_at: datetime
    prevent_minimize: bool = False


@dataclass(frozen=True, slots=True)
class WindowGroup:
    id: str
    name: str
    sort_order: int = 0


@dataclass(frozen=True, slots=True)
class OverlayGroup:
    id: str
    name: str
    color: str = "#2f81f7"
    marker_width: int = 8
    marker_height: int = 64
    opacity: float = 0.9
    corner_radius: int = 8
    hover_delay_ms: int = 1200
    locked_position: bool = False
    hide_during_fullscreen: bool = True
    show_quick_controls: bool = True
    position_by_monitor: dict[str, dict[str, Any]] = field(default_factory=dict)
    assigned_window_ids: list[int] = field(default_factory=list)
