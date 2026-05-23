from __future__ import annotations

from shelfygai.core.errors import WindowNotFoundError
from shelfygai.core.models import HideOptions, WindowInfo
from shelfygai.core.overlay_groups import OverlayGroupService
from shelfygai.core.shelf import ShelfService


class FakeOverlayAssignmentGateway:
    def __init__(self) -> None:
        self.windows = {
            100: WindowInfo(100, "Editor", 10, "editor.exe"),
            200: WindowInfo(200, "Browser", 20, "browser.exe"),
        }
        self.hidden: set[int] = set()
        self.hide_calls: list[tuple[int, HideOptions | None]] = []
        self.restore_calls: list[tuple[int, bool]] = []

    def list_windows(self):
        return [window for handle, window in self.windows.items() if handle not in self.hidden]

    def get_window(self, handle: int) -> WindowInfo:
        if handle not in self.windows:
            raise WindowNotFoundError(str(handle))
        return self.windows[handle]

    def hide_window(self, handle: int, options: HideOptions | None = None) -> None:
        self.hide_calls.append((handle, options))
        self.hidden.add(handle)

    def restore_window(self, handle: int, *, focus: bool = True) -> None:
        self.restore_calls.append((handle, focus))
        self.hidden.discard(handle)

    def is_window_available(self, handle: int) -> bool:
        return handle in self.windows

    def bring_to_front(self, _handle: int) -> None:
        return

    def foreground_window_handle(self) -> int | None:
        return 100


def test_assign_window_to_overlay_group_hides_taskbar_without_alt_tab() -> None:
    gateway = FakeOverlayAssignmentGateway()
    shelf = ShelfService(gateway)
    overlays = OverlayGroupService()
    group = overlays.create_group("Work")
    options = HideOptions(hide_taskbar=True, hide_alt_tab=False, hide_tray=False)

    shelf.shelve(100, hide_options=options)
    updated = overlays.assign_window(group.id, 100)

    assert gateway.hide_calls == [(100, options)]
    assert updated.assigned_window_ids == [100]
    assert [item.window.handle for item in shelf.shelved_items()] == [100]


def test_restore_assigned_overlay_window_restores_original_window_state() -> None:
    gateway = FakeOverlayAssignmentGateway()
    shelf = ShelfService(gateway)
    overlays = OverlayGroupService()
    group = overlays.create_group("Work")

    shelf.shelve(100, hide_options=HideOptions(hide_taskbar=True, hide_alt_tab=False))
    overlays.assign_window(group.id, 100)

    assert shelf.restore(100, focus=True) is True
    assert gateway.restore_calls == [(100, True)]
    assert overlays.groups()[0].assigned_window_ids == [100]


def test_remove_window_from_overlay_group_assignment() -> None:
    overlays = OverlayGroupService()
    group = overlays.create_group("Work")
    overlays.assign_window(group.id, 100)

    removed = overlays.remove_window_from_all(100)

    assert removed == 1
    assert overlays.groups()[0].assigned_window_ids == []


def test_stale_overlay_hwnd_cleanup_after_target_window_closes() -> None:
    gateway = FakeOverlayAssignmentGateway()
    shelf = ShelfService(gateway)
    overlays = OverlayGroupService()
    group = overlays.create_group("Work")
    shelf.shelve(100)
    overlays.assign_window(group.id, 100)

    gateway.windows.pop(100)
    shelf.prune_missing()
    valid_handles = {window.handle for window in shelf.available_windows()}
    valid_handles.update(item.window.handle for item in shelf.shelved_items())

    assert overlays.prune_stale_window_ids(valid_handles) == 1
    assert overlays.groups()[0].assigned_window_ids == []
