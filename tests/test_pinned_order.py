from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shelfygai.core.models import PinnedItem, WindowInfo
from shelfygai.ui.pinned_order import (
    bring_handle_to_front,
    move_handle,
    ordered_pinned_handles,
    ordered_pinned_items,
)


def test_ordered_pinned_handles_preserves_user_order_and_appends_new_items() -> None:
    items = [_item(100, 0), _item(200, 1), _item(300, 2)]

    assert ordered_pinned_handles(items, [300, 100]) == [300, 100, 200]
    assert [item.window.handle for item in ordered_pinned_items(items, [300, 100])] == [
        300,
        100,
        200,
    ]


def test_move_up_changes_order_correctly() -> None:
    assert move_handle([100, 200, 300], 200, -1) == [200, 100, 300]
    assert move_handle([100, 200, 300], 100, -1) == [100, 200, 300]


def test_move_down_changes_order_correctly() -> None:
    assert move_handle([100, 200, 300], 200, 1) == [100, 300, 200]
    assert move_handle([100, 200, 300], 300, 1) == [100, 200, 300]


def test_bring_to_front_puts_selected_handle_first() -> None:
    assert bring_handle_to_front([100, 200, 300], 300) == [300, 100, 200]
    assert bring_handle_to_front([100, 200, 300], 404) == [100, 200, 300]


def _item(handle: int, seconds: int) -> PinnedItem:
    return PinnedItem(
        window=WindowInfo(handle, f"Window {handle}", handle, f"app-{handle}.exe"),
        pinned_at=datetime(2026, 5, 23, tzinfo=UTC) + timedelta(seconds=seconds),
    )
