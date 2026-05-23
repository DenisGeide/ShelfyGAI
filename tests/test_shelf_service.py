from __future__ import annotations

from datetime import UTC, datetime

import pytest

from shelfygai.core.errors import GroupOperationError, WindowNotFoundError, WindowOperationError
from shelfygai.core.models import DEFAULT_GROUP_ID, HideOptions, WindowGroup, WindowInfo
from shelfygai.core.shelf import ShelfService
from shelfygai.i18n import set_language


class FakeWindowGateway:
    def __init__(self) -> None:
        self.windows = {
            100: WindowInfo(100, "Editor", 10, "editor.exe"),
            200: WindowInfo(200, "Browser", 20, "browser.exe"),
        }
        self.hidden: set[int] = set()
        self.foreground: list[int] = []
        self.hide_calls: list[tuple[int, HideOptions | None]] = []
        self.restore_calls: list[int] = []
        self.restore_focus_values: list[bool] = []
        self.pin_calls: list[tuple[int, bool, bool]] = []
        self.unpin_calls: list[int] = []
        self.pinned_order_calls: list[list[int]] = []
        self.prevent_minimize_calls: list[tuple[int, bool]] = []
        self.minimized: set[int] = set()
        self.restored_minimized: list[int] = []
        self.active_handle: int | None = 100

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
        self.restore_calls.append(handle)
        self.restore_focus_values.append(focus)
        self.hidden.discard(handle)

    def pin_window(
        self,
        handle: int,
        *,
        prevent_minimize: bool = False,
        allow_own_window: bool = False,
    ) -> None:
        self.pin_calls.append((handle, prevent_minimize, allow_own_window))

    def unpin_window(self, handle: int) -> None:
        self.unpin_calls.append(handle)

    def apply_pinned_order(self, handles):
        call = list(handles)
        self.pinned_order_calls.append(call)
        return tuple(reversed(call))

    def pin_diagnostics_text(self, handle: int) -> str:
        return f"pin diagnostics for {handle}"

    def set_prevent_minimize(self, handle: int, enabled: bool) -> None:
        self.prevent_minimize_calls.append((handle, enabled))

    def is_window_minimized(self, handle: int) -> bool:
        return handle in self.minimized

    def restore_minimized_window(self, handle: int) -> None:
        self.restored_minimized.append(handle)
        self.minimized.discard(handle)

    def bring_to_front(self, handle: int) -> None:
        self.foreground.append(handle)

    def is_window_available(self, handle: int) -> bool:
        return handle in self.windows

    def foreground_window_handle(self) -> int | None:
        return self.active_handle


def test_shelve_hides_window_and_tracks_item() -> None:
    gateway = FakeWindowGateway()
    service = ShelfService(gateway, clock=lambda: datetime(2026, 5, 23, tzinfo=UTC))

    item = service.shelve(100)

    assert item.window.title == "Editor"
    assert 100 in gateway.hidden
    assert [window.handle for window in service.available_windows()] == [200]


def test_shelve_prevents_duplicate_management() -> None:
    gateway = FakeWindowGateway()
    service = ShelfService(gateway)

    first = service.shelve(100)
    second = service.shelve(100)

    assert first == second
    assert gateway.hide_calls == [(100, None)]
    assert len(service.shelved_items()) == 1


def test_shelve_supports_multiple_windows() -> None:
    gateway = FakeWindowGateway()
    service = ShelfService(gateway)

    service.shelve(100)
    service.shelve(200)

    assert gateway.hide_calls == [(100, None), (200, None)]
    assert [item.window.handle for item in service.shelved_items()] == [100, 200]


def test_shelve_passes_hide_options_to_gateway() -> None:
    gateway = FakeWindowGateway()
    service = ShelfService(gateway)
    options = HideOptions(hide_taskbar=True, hide_alt_tab=False)

    service.shelve(100, hide_options=options)

    assert gateway.hide_calls == [(100, options)]


def test_shelve_refuses_pinned_window_until_unpinned() -> None:
    set_language("en")
    gateway = FakeWindowGateway()
    service = ShelfService(gateway)
    service.pin(100)

    with pytest.raises(WindowOperationError, match="Unpin this window before hiding it."):
        service.shelve(100)

    assert gateway.hide_calls == []


def test_shelve_foreground_refuses_runtime_pinned_window() -> None:
    gateway = FakeWindowGateway()
    service = ShelfService(gateway)
    service.pin(100)

    with pytest.raises(WindowOperationError):
        service.shelve_foreground()

    assert gateway.hide_calls == []


def test_pin_window_sets_topmost_and_tracks_item() -> None:
    gateway = FakeWindowGateway()
    service = ShelfService(gateway, clock=lambda: datetime(2026, 5, 23, tzinfo=UTC))

    item = service.pin(100, prevent_minimize=True, allow_own_window=True)

    assert item.window.title == "Editor"
    assert item.prevent_minimize is True
    assert gateway.pin_calls == [(100, True, True)]
    assert [item.window.handle for item in service.pinned_items()] == [100]


def test_pin_prevents_duplicate_management() -> None:
    gateway = FakeWindowGateway()
    service = ShelfService(gateway)

    first = service.pin(100)
    second = service.pin(100)

    assert first == second
    assert gateway.pin_calls == [(100, False, False)]
    assert len(service.pinned_items()) == 1


def test_unpin_restores_original_pin_state() -> None:
    gateway = FakeWindowGateway()
    service = ShelfService(gateway)

    service.pin(100)
    assert service.unpin(100) is True

    assert gateway.unpin_calls == [100]
    assert service.pinned_items() == []


def test_pin_diagnostics_delegates_to_gateway() -> None:
    service = ShelfService(FakeWindowGateway())

    assert service.pin_diagnostics(100) == "pin diagnostics for 100"


def test_apply_pinned_order_only_uses_registered_live_windows() -> None:
    gateway = FakeWindowGateway()
    service = ShelfService(gateway)
    service.pin(100)
    service.pin(200)
    gateway.windows.pop(200)

    applied = service.apply_pinned_order([200, 100, 999])

    assert applied == (100,)
    assert gateway.pinned_order_calls == [[100]]
    assert [item.window.handle for item in service.pinned_items()] == [100]


def test_prevent_minimize_update_is_tracked() -> None:
    gateway = FakeWindowGateway()
    service = ShelfService(gateway)

    service.pin(100)
    assert service.set_prevent_minimize(100, True) is True

    assert gateway.prevent_minimize_calls == [(100, True)]
    assert service.pinned_items()[0].prevent_minimize is True


def test_prevent_minimize_watcher_needed_only_for_protected_pins() -> None:
    gateway = FakeWindowGateway()
    service = ShelfService(gateway)

    assert service.has_prevent_minimize_pinned_windows() is False
    service.pin(100)
    assert service.has_prevent_minimize_pinned_windows() is False
    service.set_prevent_minimize(100, True)
    assert service.has_prevent_minimize_pinned_windows() is True


def test_pinned_watcher_restores_minimized_windows_and_prunes_closed() -> None:
    gateway = FakeWindowGateway()
    service = ShelfService(gateway)
    service.pin(100, prevent_minimize=True)
    service.pin(200, prevent_minimize=True)
    gateway.minimized.add(100)
    gateway.windows.pop(200)

    restored, removed = service.enforce_pinned_windows()

    assert (restored, removed) == (1, 1)
    assert gateway.restored_minimized == [100]
    assert [item.window.handle for item in service.pinned_items()] == [100]


def test_shelve_foreground_hides_active_window() -> None:
    gateway = FakeWindowGateway()
    service = ShelfService(gateway)

    item = service.shelve_foreground()

    assert item.window.handle == 100
    assert gateway.hide_calls == [(100, None)]


def test_shelve_foreground_requires_manageable_active_window() -> None:
    gateway = FakeWindowGateway()
    gateway.active_handle = None
    service = ShelfService(gateway)

    with pytest.raises(WindowNotFoundError):
        service.shelve_foreground()


def test_create_rename_delete_empty_group() -> None:
    service = ShelfService(FakeWindowGateway())

    group = service.create_group("Work")
    renamed = service.rename_group(group.id, "Deep Work")
    service.delete_group(group.id)

    assert renamed.name == "Deep Work"
    assert [group.id for group in service.groups()] == [DEFAULT_GROUP_ID]


def test_delete_non_empty_group_is_rejected() -> None:
    service = ShelfService(FakeWindowGateway())
    group = service.create_group("Work")
    service.shelve(100, group_id=group.id)

    with pytest.raises(GroupOperationError):
        service.delete_group(group.id)


def test_assign_window_to_group() -> None:
    service = ShelfService(
        FakeWindowGateway(),
        groups=[WindowGroup(DEFAULT_GROUP_ID, "Ungrouped", 0), WindowGroup("focus", "Focus", 1)],
    )
    service.shelve(100)

    assert service.assign_to_group(100, "focus") is True

    [item] = service.shelved_items()
    assert item.group_id == "focus"
    assert service.group_counts()["focus"] == 1


def test_restore_shows_window_and_removes_item() -> None:
    gateway = FakeWindowGateway()
    service = ShelfService(gateway)

    service.shelve(100)
    restored = service.restore(100, focus=False)

    assert restored is True
    assert 100 not in gateway.hidden
    assert gateway.restore_focus_values == [False]
    assert service.shelved_items() == []


def test_restore_unknown_handle_is_ignored() -> None:
    service = ShelfService(FakeWindowGateway())

    assert service.restore(404) is False


def test_prune_missing_removes_closed_windows() -> None:
    gateway = FakeWindowGateway()
    service = ShelfService(gateway)

    service.shelve(100)
    gateway.windows.pop(100)

    service.prune_missing()

    assert service.shelved_items() == []


def test_restore_closed_window_is_removed_without_error() -> None:
    gateway = FakeWindowGateway()
    service = ShelfService(gateway)

    service.shelve(100)
    gateway.windows.pop(100)

    restored = service.restore(100)

    assert restored is False
    assert service.shelved_items() == []


def test_restore_all_reports_restored_and_skipped_counts() -> None:
    gateway = FakeWindowGateway()
    service = ShelfService(gateway)

    service.shelve(100)
    service.shelve(200)
    gateway.windows.pop(200)

    restored, skipped = service.restore_all(focus=False)

    assert (restored, skipped) == (1, 1)
    assert gateway.restore_calls == [100]
    assert gateway.restore_focus_values == [False]
    assert service.shelved_items() == []


def test_restore_last_restores_most_recent_hidden_window() -> None:
    times = iter(
        [
            datetime(2026, 5, 23, 10, 0, tzinfo=UTC),
            datetime(2026, 5, 23, 10, 5, tzinfo=UTC),
        ]
    )
    gateway = FakeWindowGateway()
    service = ShelfService(gateway, clock=lambda: next(times))

    service.shelve(100)
    service.shelve(200)

    assert service.restore_last(focus=False) is True
    assert gateway.restore_calls == [200]
    assert [item.window.handle for item in service.shelved_items()] == [100]
