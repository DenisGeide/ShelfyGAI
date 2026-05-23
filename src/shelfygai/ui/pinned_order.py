from __future__ import annotations

from collections.abc import Sequence

from shelfygai.core.models import PinnedItem


def ordered_pinned_handles(
    items: Sequence[PinnedItem],
    current_order: Sequence[int],
) -> list[int]:
    """Return UI order, preserving existing user order and appending new pins."""
    item_handles = [item.window.handle for item in items]
    item_handle_set = set(item_handles)
    ordered = [handle for handle in current_order if handle in item_handle_set]
    ordered.extend(handle for handle in item_handles if handle not in ordered)
    return ordered


def ordered_pinned_items(
    items: Sequence[PinnedItem],
    current_order: Sequence[int],
) -> list[PinnedItem]:
    by_handle = {item.window.handle: item for item in items}
    return [
        by_handle[handle]
        for handle in ordered_pinned_handles(items, current_order)
        if handle in by_handle
    ]


def move_handle(order: Sequence[int], handle: int, direction: int) -> list[int]:
    """Move one handle by one row. Negative direction means higher priority."""
    reordered = list(order)
    if handle not in reordered:
        return reordered
    index = reordered.index(handle)
    target = index + direction
    if target < 0 or target >= len(reordered):
        return reordered
    reordered[index], reordered[target] = reordered[target], reordered[index]
    return reordered


def bring_handle_to_front(order: Sequence[int], handle: int) -> list[int]:
    """Put one handle at the top of the pinned priority order."""
    if handle not in order:
        return list(order)
    return [handle, *(existing for existing in order if existing != handle)]
