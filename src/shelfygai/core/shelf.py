from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from shelfygai.core.errors import GroupOperationError, WindowNotFoundError, WindowOperationError
from shelfygai.core.models import (
    DEFAULT_GROUP_ID,
    HideOptions,
    PinnedItem,
    ShelfItem,
    WindowGroup,
    WindowInfo,
)
from shelfygai.core.ports import WindowGateway
from shelfygai.i18n import tr

LOGGER = logging.getLogger(__name__)


class ShelfService:
    def __init__(
        self,
        window_gateway: WindowGateway,
        clock: Callable[[], datetime] | None = None,
        groups: Sequence[WindowGroup] | None = None,
    ) -> None:
        self._window_gateway = window_gateway
        self._clock = clock or (lambda: datetime.now(UTC))
        self._items: dict[int, ShelfItem] = {}
        self._pinned_items: dict[int, PinnedItem] = {}
        self._groups = _normalize_groups(groups)

    def available_windows(self) -> Sequence[WindowInfo]:
        shelved_handles = set(self._items)
        windows = [
            window
            for window in self._window_gateway.list_windows()
            if window.handle not in shelved_handles
        ]
        LOGGER.debug("Listed %s available windows", len(windows))
        return windows

    def shelved_items(self) -> Sequence[ShelfItem]:
        return sorted(self._items.values(), key=lambda item: item.hidden_at)

    def pinned_items(self) -> Sequence[PinnedItem]:
        return sorted(self._pinned_items.values(), key=lambda item: item.pinned_at)

    def shelve(
        self,
        handle: int,
        group_id: str = DEFAULT_GROUP_ID,
        hide_options: HideOptions | None = None,
    ) -> ShelfItem:
        if handle in self._pinned_items:
            LOGGER.info("Refusing to hide pinned window: handle=%s", handle)
            raise WindowOperationError(tr("error.hide_pinned_window"))
        if handle in self._items:
            LOGGER.debug("Window already managed: handle=%s", handle)
            return self._items[handle]
        if group_id not in self._groups:
            group_id = DEFAULT_GROUP_ID

        window = self._window_gateway.get_window(handle)
        LOGGER.info("Managing window: handle=%s", window.handle)
        self._window_gateway.hide_window(handle, hide_options)
        item = ShelfItem(window=window, hidden_at=self._clock(), group_id=group_id)
        self._items[handle] = item
        return item

    def pin(
        self,
        handle: int,
        *,
        prevent_minimize: bool = False,
        allow_own_window: bool = False,
    ) -> PinnedItem:
        if handle in self._pinned_items:
            LOGGER.debug("Window already pinned: handle=%s", handle)
            if prevent_minimize and not self._pinned_items[handle].prevent_minimize:
                self.set_prevent_minimize(handle, True)
            return self._pinned_items[handle]

        window = self._window_gateway.get_window(handle)
        LOGGER.info(
            "Pinning window: handle=%s prevent_minimize=%s",
            window.handle,
            prevent_minimize,
        )
        self._window_gateway.pin_window(
            handle,
            prevent_minimize=prevent_minimize,
            allow_own_window=allow_own_window,
        )
        item = PinnedItem(
            window=window,
            pinned_at=self._clock(),
            prevent_minimize=prevent_minimize,
        )
        self._pinned_items[handle] = item
        return item

    def unpin(self, handle: int) -> bool:
        if handle not in self._pinned_items:
            LOGGER.info("Ignoring unpin request for unpinned window: handle=%s", handle)
            return False
        if not self._window_gateway.is_window_available(handle):
            LOGGER.info("Pinned window closed before unpin: handle=%s", handle)
            self._pinned_items.pop(handle, None)
            return False

        LOGGER.info("Unpinning window: handle=%s", handle)
        try:
            self._window_gateway.unpin_window(handle)
        except WindowNotFoundError:
            LOGGER.info("Pinned window disappeared during unpin: handle=%s", handle)
            self._pinned_items.pop(handle, None)
            return False
        self._pinned_items.pop(handle, None)
        return True

    def unpin_all(self) -> tuple[int, int]:
        unpinned = 0
        skipped = 0
        for handle in list(self._pinned_items):
            try:
                if self.unpin(handle):
                    unpinned += 1
                else:
                    skipped += 1
            except Exception:
                LOGGER.exception("Could not unpin window: handle=%s", handle)
                skipped += 1
        return unpinned, skipped

    def pin_diagnostics(self, handle: int) -> str:
        LOGGER.info("Collecting pin diagnostics: handle=%s", handle)
        return self._window_gateway.pin_diagnostics_text(handle)

    def apply_pinned_order(self, handles: Sequence[int]) -> Sequence[int]:
        self.prune_missing()
        pinned_handles = [handle for handle in handles if handle in self._pinned_items]
        LOGGER.info("Applying pinned order: top_to_bottom=%s", pinned_handles)
        applied = self._window_gateway.apply_pinned_order(pinned_handles)
        self.prune_missing()
        return applied

    def set_prevent_minimize(self, handle: int, enabled: bool) -> bool:
        item = self._pinned_items.get(handle)
        if item is None:
            LOGGER.info("Ignoring prevent-minimize request for unpinned window: handle=%s", handle)
            return False
        if not self._window_gateway.is_window_available(handle):
            LOGGER.info("Pinned window closed before prevent-minimize update: handle=%s", handle)
            self._pinned_items.pop(handle, None)
            return False
        if item.prevent_minimize == enabled:
            return True

        self._window_gateway.set_prevent_minimize(handle, enabled)
        self._pinned_items[handle] = PinnedItem(
            window=item.window,
            pinned_at=item.pinned_at,
            prevent_minimize=enabled,
        )
        LOGGER.info(
            "Updated pinned window prevent-minimize mode: handle=%s enabled=%s",
            handle,
            enabled,
        )
        return True

    def shelve_foreground(
        self,
        group_id: str = DEFAULT_GROUP_ID,
        hide_options: HideOptions | None = None,
    ) -> ShelfItem:
        handle = self._window_gateway.foreground_window_handle()
        if handle is None:
            raise WindowNotFoundError(tr("error.foreground_not_manageable"))
        return self.shelve(handle, group_id=group_id, hide_options=hide_options)

    def restore(self, handle: int, *, focus: bool = True) -> bool:
        if handle not in self._items:
            LOGGER.info("Ignoring restore request for unknown hidden window: handle=%s", handle)
            return False

        item = self._items[handle]
        if not self._window_gateway.is_window_available(handle):
            LOGGER.info("Managed window closed before restore: handle=%s", handle)
            self._items.pop(handle, None)
            return False

        LOGGER.info("Restoring hidden window: handle=%s", item.window.handle)
        try:
            self._window_gateway.restore_window(handle, focus=focus)
        except WindowNotFoundError:
            LOGGER.info("Managed window disappeared during restore: handle=%s", handle)
            self._items.pop(handle, None)
            return False
        self._items.pop(handle, None)
        return True

    def restore_last(self, *, focus: bool = True) -> bool:
        if not self._items:
            LOGGER.info("Ignoring restore-last request with no hidden windows")
            return False
        last_item = max(self._items.values(), key=lambda item: item.hidden_at)
        return self.restore(last_item.window.handle, focus=focus)

    def restore_all(self, *, focus: bool = True) -> tuple[int, int]:
        restored = 0
        skipped = 0
        for handle in list(self._items):
            item = self._items[handle]
            LOGGER.info(
                "Restoring hidden window during restore-all: handle=%s",
                item.window.handle,
            )
            try:
                if self.restore(handle, focus=focus):
                    restored += 1
                else:
                    skipped += 1
            except Exception:
                LOGGER.exception("Could not restore hidden window: handle=%s", handle)
                skipped += 1
                continue
        return restored, skipped

    def bring_to_front(self, handle: int) -> None:
        LOGGER.info("Requesting foreground activation: handle=%s", handle)
        self._window_gateway.bring_to_front(handle)

    def prune_missing(self) -> int:
        missing_count = 0
        for handle in list(self._items):
            if not self._window_gateway.is_window_available(handle):
                LOGGER.info("Pruning missing hidden window: handle=%s", handle)
                self._items.pop(handle, None)
                missing_count += 1
        for handle in list(self._pinned_items):
            if not self._window_gateway.is_window_available(handle):
                LOGGER.info("Pruning missing pinned window: handle=%s", handle)
                self._pinned_items.pop(handle, None)
                missing_count += 1
        return missing_count

    def enforce_pinned_windows(self) -> tuple[int, int]:
        restored = 0
        removed = 0
        for handle, item in list(self._pinned_items.items()):
            if not self._window_gateway.is_window_available(handle):
                LOGGER.info("Pinned window closed; removing from registry: handle=%s", handle)
                self._pinned_items.pop(handle, None)
                removed += 1
                continue
            if not item.prevent_minimize:
                continue
            try:
                if self._window_gateway.is_window_minimized(handle):
                    LOGGER.info("Restoring minimized pinned window: handle=%s", handle)
                    self._window_gateway.restore_minimized_window(handle)
                    restored += 1
            except Exception:
                LOGGER.exception("Could not enforce pinned window state: handle=%s", handle)
        return restored, removed

    def has_shelved_windows(self) -> bool:
        return bool(self._items)

    def has_pinned_windows(self) -> bool:
        return bool(self._pinned_items)

    def has_prevent_minimize_pinned_windows(self) -> bool:
        return any(item.prevent_minimize for item in self._pinned_items.values())

    def managed_style_snapshot(self) -> dict[int, Any]:
        snapshotter = getattr(self._window_gateway, "managed_styles_snapshot", None)
        if not callable(snapshotter):
            return {}
        try:
            return dict(snapshotter())
        except Exception:
            LOGGER.exception("Could not capture managed native window styles")
            return {}

    def groups(self) -> Sequence[WindowGroup]:
        return sorted(
            self._groups.values(),
            key=lambda group: (group.sort_order, group.name.lower()),
        )

    def group_counts(self) -> dict[str, int]:
        counts = {group_id: 0 for group_id in self._groups}
        for item in self._items.values():
            counts[item.group_id] = counts.get(item.group_id, 0) + 1
        return counts

    def create_group(self, name: str) -> WindowGroup:
        clean_name = name.strip()
        if not clean_name:
            raise GroupOperationError(tr("error.group_name_empty"))
        sort_order = max((group.sort_order for group in self._groups.values()), default=0) + 1
        group = WindowGroup(id=f"group-{uuid4().hex}", name=clean_name, sort_order=sort_order)
        self._groups[group.id] = group
        LOGGER.info("Created group: id=%s name=%r", group.id, group.name)
        return group

    def rename_group(self, group_id: str, name: str) -> WindowGroup:
        if group_id == DEFAULT_GROUP_ID:
            raise GroupOperationError(tr("error.default_group_rename"))
        if group_id not in self._groups:
            raise GroupOperationError(tr("error.group_missing"))
        clean_name = name.strip()
        if not clean_name:
            raise GroupOperationError(tr("error.group_name_empty"))
        existing = self._groups[group_id]
        renamed = WindowGroup(id=existing.id, name=clean_name, sort_order=existing.sort_order)
        self._groups[group_id] = renamed
        LOGGER.info("Renamed group: id=%s name=%r", renamed.id, renamed.name)
        return renamed

    def delete_group(self, group_id: str) -> None:
        if group_id == DEFAULT_GROUP_ID:
            raise GroupOperationError(tr("error.default_group_delete"))
        if group_id not in self._groups:
            raise GroupOperationError(tr("error.group_missing"))
        if any(item.group_id == group_id for item in self._items.values()):
            raise GroupOperationError(tr("error.group_not_empty"))
        self._groups.pop(group_id)
        LOGGER.info("Deleted empty group: id=%s", group_id)

    def assign_to_group(self, handle: int, group_id: str) -> bool:
        if handle not in self._items:
            LOGGER.info("Ignoring group assignment for unknown hidden window: handle=%s", handle)
            return False
        if group_id not in self._groups:
            raise GroupOperationError(tr("error.group_missing"))
        item = self._items[handle]
        if item.group_id == group_id:
            return True
        self._items[handle] = ShelfItem(
            window=item.window,
            hidden_at=item.hidden_at,
            group_id=group_id,
        )
        LOGGER.info("Assigned hidden window to group: handle=%s group_id=%s", handle, group_id)
        return True


def _normalize_groups(groups: Sequence[WindowGroup] | None) -> dict[str, WindowGroup]:
    normalized = {
        DEFAULT_GROUP_ID: WindowGroup(DEFAULT_GROUP_ID, "Ungrouped", 0),
    }
    if groups is None:
        return normalized
    for group in groups:
        if not group.id or not group.name.strip():
            continue
        if group.id == DEFAULT_GROUP_ID:
            normalized[DEFAULT_GROUP_ID] = WindowGroup(DEFAULT_GROUP_ID, "Ungrouped", 0)
            continue
        normalized[group.id] = group
    return normalized
