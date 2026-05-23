from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import replace
from uuid import uuid4

from shelfygai.core.errors import GroupOperationError
from shelfygai.core.models import OverlayGroup
from shelfygai.i18n import tr

LOGGER = logging.getLogger(__name__)


class OverlayGroupService:
    """Runtime model manager for safe ShelfyGAI-owned overlay markers."""

    def __init__(self, groups: Sequence[OverlayGroup] | None = None) -> None:
        self._groups = {group.id: group for group in groups or [] if group.id}

    def groups(self) -> Sequence[OverlayGroup]:
        return sorted(self._groups.values(), key=lambda group: group.name.lower())

    def create_group(self, name: str, *, color: str = "#2f81f7") -> OverlayGroup:
        clean_name = name.strip()
        if not clean_name:
            raise GroupOperationError(tr("error.group_name_empty"))
        group = OverlayGroup(id=f"overlay-{uuid4().hex}", name=clean_name, color=color)
        self._groups[group.id] = group
        LOGGER.info("Created overlay group: id=%s name=%r", group.id, group.name)
        return group

    def rename_group(self, group_id: str, name: str) -> OverlayGroup:
        group = self._require_group(group_id)
        clean_name = name.strip()
        if not clean_name:
            raise GroupOperationError(tr("error.group_name_empty"))
        renamed = replace(group, name=clean_name)
        self._groups[group_id] = renamed
        LOGGER.info("Renamed overlay group: id=%s name=%r", group_id, clean_name)
        return renamed

    def delete_group(self, group_id: str) -> None:
        self._require_group(group_id)
        self._groups.pop(group_id, None)
        LOGGER.info("Deleted overlay group: id=%s", group_id)

    def update_color(self, group_id: str, color: str) -> OverlayGroup:
        group = self._require_group(group_id)
        updated = replace(group, color=color)
        self._groups[group_id] = updated
        LOGGER.info("Updated overlay group color: id=%s color=%s", group_id, color)
        return updated

    def update_group(self, group_id: str, **changes: object) -> OverlayGroup:
        group = self._require_group(group_id)
        updated = replace(group, **changes)
        self._groups[group_id] = updated
        LOGGER.info("Updated overlay group settings: id=%s fields=%s", group_id, sorted(changes))
        return updated

    def update_marker_position(
        self,
        group_id: str,
        monitor_id: str,
        *,
        x: int,
        y: int,
        edge: str = "bottom",
    ) -> OverlayGroup:
        group = self._require_group(group_id)
        positions = {
            key: dict(value)
            for key, value in group.position_by_monitor.items()
        }
        positions[monitor_id] = {"x": x, "y": y, "edge": edge}
        updated = replace(group, position_by_monitor=positions)
        self._groups[group_id] = updated
        LOGGER.info(
            "Updated overlay group marker position: id=%s monitor=%s",
            group_id,
            monitor_id,
        )
        return updated

    def assign_window(self, group_id: str, handle: int) -> OverlayGroup:
        group = self._require_group(group_id)
        handles = list(group.assigned_window_ids)
        if handle not in handles:
            handles.append(handle)
        updated = replace(group, assigned_window_ids=handles)
        self._groups[group_id] = updated
        LOGGER.info("Assigned hidden window to overlay group: id=%s handle=%s", group_id, handle)
        return updated

    def remove_window(self, group_id: str, handle: int) -> OverlayGroup:
        group = self._require_group(group_id)
        handles = [
            assigned_handle
            for assigned_handle in group.assigned_window_ids
            if assigned_handle != handle
        ]
        updated = replace(group, assigned_window_ids=handles)
        self._groups[group_id] = updated
        LOGGER.info("Removed window from overlay group: id=%s handle=%s", group_id, handle)
        return updated

    def remove_window_from_all(self, handle: int) -> int:
        removed = 0
        for group in list(self._groups.values()):
            if handle not in group.assigned_window_ids:
                continue
            self.remove_window(group.id, handle)
            removed += 1
        return removed

    def prune_stale_window_ids(self, valid_handles: set[int]) -> int:
        removed = 0
        for group in list(self._groups.values()):
            handles = [
                handle
                for handle in group.assigned_window_ids
                if handle in valid_handles
            ]
            removed += len(group.assigned_window_ids) - len(handles)
            if handles != group.assigned_window_ids:
                self._groups[group.id] = replace(group, assigned_window_ids=handles)
        if removed:
            LOGGER.info("Pruned stale overlay group window ids: count=%s", removed)
        return removed

    def _require_group(self, group_id: str) -> OverlayGroup:
        group = self._groups.get(group_id)
        if group is None:
            raise GroupOperationError(tr("error.group_missing"))
        return group
