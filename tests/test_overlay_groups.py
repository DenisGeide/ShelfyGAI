from __future__ import annotations

import pytest

from shelfygai.core.errors import GroupOperationError
from shelfygai.core.overlay_groups import OverlayGroupService


def test_create_overlay_group_uses_marker_defaults() -> None:
    service = OverlayGroupService()

    group = service.create_group("Work", color="#55c2a2")

    assert group.name == "Work"
    assert group.color == "#55c2a2"
    assert group.marker_width == 8
    assert group.marker_height == 64
    assert group.opacity == 0.9
    assert group.corner_radius == 8
    assert group.hover_delay_ms == 1200
    assert group.locked_position is False
    assert group.hide_during_fullscreen is True
    assert group.show_quick_controls is True
    assert service.groups() == [group]


def test_rename_overlay_group() -> None:
    service = OverlayGroupService()
    group = service.create_group("Work")

    renamed = service.rename_group(group.id, "Deep Work")

    assert renamed.name == "Deep Work"
    assert service.groups()[0].name == "Deep Work"


def test_delete_overlay_group() -> None:
    service = OverlayGroupService()
    group = service.create_group("Work")

    service.delete_group(group.id)

    assert service.groups() == []
    with pytest.raises(GroupOperationError):
        service.delete_group(group.id)


def test_overlay_group_marker_position_update() -> None:
    service = OverlayGroupService()
    group = service.create_group("Work")

    updated = service.update_marker_position(
        group.id,
        "monitor-1",
        x=1440,
        y=1000,
        edge="bottom",
    )

    assert updated.position_by_monitor == {
        "monitor-1": {"x": 1440, "y": 1000, "edge": "bottom"}
    }


def test_update_overlay_group_marker_settings() -> None:
    service = OverlayGroupService()
    group = service.create_group("Work")

    updated = service.update_group(
        group.id,
        marker_width=16,
        marker_height=96,
        opacity=0.75,
        corner_radius=10,
        hover_delay_ms=1500,
        locked_position=True,
        hide_during_fullscreen=False,
        show_quick_controls=False,
    )

    assert updated.marker_width == 16
    assert updated.marker_height == 96
    assert updated.opacity == 0.75
    assert updated.corner_radius == 10
    assert updated.hover_delay_ms == 1500
    assert updated.locked_position is True
    assert updated.hide_during_fullscreen is False
    assert updated.show_quick_controls is False


def test_overlay_group_assignment_deduplicates_window_ids() -> None:
    service = OverlayGroupService()
    group = service.create_group("Work")

    service.assign_window(group.id, 100)
    updated = service.assign_window(group.id, 100)

    assert updated.assigned_window_ids == [100]


def test_remove_window_from_overlay_group() -> None:
    service = OverlayGroupService()
    group = service.create_group("Work")

    service.assign_window(group.id, 100)
    service.assign_window(group.id, 200)
    updated = service.remove_window(group.id, 100)

    assert updated.assigned_window_ids == [200]


def test_clear_assigned_windows_preserves_overlay_groups() -> None:
    service = OverlayGroupService()
    work = service.create_group("Work")
    chat = service.create_group("Chat")
    service.assign_window(work.id, 100)
    service.assign_window(work.id, 200)
    service.assign_window(chat.id, 300)

    removed = service.clear_assigned_windows()

    assert removed == 3
    assert [group.name for group in service.groups()] == ["Chat", "Work"]
    assert all(group.assigned_window_ids == [] for group in service.groups())
