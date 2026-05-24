from __future__ import annotations

STATE_HIDDEN = "state.on_shelf"
STATE_MINIMIZED = "state.minimized"
STATE_OPEN = "state.open"
STATE_PINNED = "state.pinned"


def window_state_key(
    *,
    is_hidden: bool = False,
    is_pinned: bool = False,
    is_minimized: bool = False,
) -> str:
    if is_hidden:
        return STATE_HIDDEN
    if is_pinned:
        return STATE_PINNED
    if is_minimized:
        return STATE_MINIMIZED
    return STATE_OPEN
