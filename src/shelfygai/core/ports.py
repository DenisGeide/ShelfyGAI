from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from shelfygai.core.models import WindowInfo


class WindowGateway(Protocol):
    def list_windows(self) -> Sequence[WindowInfo]:
        """Return user-facing top-level windows that can be managed."""

    def get_window(self, handle: int) -> WindowInfo:
        """Return information for a single window handle."""

    def hide_window(self, handle: int) -> None:
        """Remove a window from taskbar and Alt+Tab while keeping it running."""

    def restore_window(self, handle: int, *, focus: bool = True) -> None:
        """Restore a managed window's original taskbar and Alt+Tab behavior."""

    def pin_window(
        self,
        handle: int,
        *,
        prevent_minimize: bool = False,
        allow_own_window: bool = False,
    ) -> None:
        """Keep a window above normal windows and optionally remove minimize affordances."""

    def unpin_window(self, handle: int) -> None:
        """Restore a pinned window's original topmost and style state."""

    def set_prevent_minimize(self, handle: int, enabled: bool) -> None:
        """Toggle the pinned window's minimize-box protection."""

    def is_window_minimized(self, handle: int) -> bool:
        """Return whether a live window is minimized."""

    def restore_minimized_window(self, handle: int) -> None:
        """Restore a minimized window without changing shelf membership."""

    def bring_to_front(self, handle: int) -> None:
        """Try to activate a visible window."""

    def is_window_available(self, handle: int) -> bool:
        """Return whether the handle still points at a live window."""

    def foreground_window_handle(self) -> int | None:
        """Return the active top-level application window handle, if one is manageable."""
