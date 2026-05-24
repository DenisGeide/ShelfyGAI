from __future__ import annotations

from shelfygai.ui.window_state import (
    STATE_HIDDEN,
    STATE_MINIMIZED,
    STATE_OPEN,
    STATE_PINNED,
    window_state_key,
)


def test_window_state_restored_is_open() -> None:
    assert window_state_key(is_minimized=False) == STATE_OPEN


def test_window_state_minimized() -> None:
    assert window_state_key(is_minimized=True) == STATE_MINIMIZED


def test_window_state_hidden() -> None:
    assert window_state_key(is_hidden=True, is_minimized=True) == STATE_HIDDEN


def test_window_state_pinned() -> None:
    assert window_state_key(is_pinned=True, is_minimized=True) == STATE_PINNED
