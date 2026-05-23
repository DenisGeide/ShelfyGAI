from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

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
