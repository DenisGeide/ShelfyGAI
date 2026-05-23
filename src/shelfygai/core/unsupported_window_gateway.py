from __future__ import annotations

from collections.abc import Sequence

from shelfygai.core.errors import WindowOperationError
from shelfygai.core.models import WindowInfo
from shelfygai.i18n import tr


class UnsupportedWindowGateway:
    def list_windows(self) -> Sequence[WindowInfo]:
        return []

    def get_window(self, handle: int) -> WindowInfo:
        raise WindowOperationError(tr("error.windows_only_management"))

    def hide_window(self, handle: int) -> None:
        raise WindowOperationError(tr("error.windows_only_management"))

    def restore_window(self, handle: int, *, focus: bool = True) -> None:
        raise WindowOperationError(tr("error.windows_only_management"))

    def pin_window(
        self,
        handle: int,
        *,
        prevent_minimize: bool = False,
        allow_own_window: bool = False,
    ) -> None:
        raise WindowOperationError(tr("error.windows_only_management"))

    def unpin_window(self, handle: int) -> None:
        raise WindowOperationError(tr("error.windows_only_management"))

    def set_prevent_minimize(self, handle: int, enabled: bool) -> None:
        raise WindowOperationError(tr("error.windows_only_management"))

    def is_window_minimized(self, handle: int) -> bool:
        return False

    def restore_minimized_window(self, handle: int) -> None:
        raise WindowOperationError(tr("error.windows_only_management"))

    def bring_to_front(self, handle: int) -> None:
        raise WindowOperationError(tr("error.windows_only_management"))

    def is_window_available(self, handle: int) -> bool:
        return False

    def foreground_window_handle(self) -> int | None:
        return None
