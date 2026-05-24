from __future__ import annotations

from datetime import UTC, datetime

from shelfygai.core.models import DEFAULT_GROUP_ID, PinnedItem, WindowGroup, WindowInfo
from shelfygai.settings.settings_manager import AppSettings
from shelfygai.ui.main_window import MainWindow


class FakeLifecycleShelfService:
    def __init__(self) -> None:
        self.unpin_all_calls = 0

    def has_pinned_windows(self) -> bool:
        return True

    def unpin_all(self) -> tuple[int, int]:
        self.unpin_all_calls += 1
        return 1, 0

    def has_shelved_windows(self) -> bool:
        return False


class FakeRecoveryStore:
    def __init__(self) -> None:
        self.clear_reasons: list[str] = []

    def clear(self, *, reason: str) -> bool:
        self.clear_reasons.append(reason)
        return True


class FakeRuntimeStateShelfService:
    def groups(self):
        return [WindowGroup(DEFAULT_GROUP_ID, "Ungrouped", 0)]

    def shelved_items(self):
        return []

    def pinned_items(self):
        return [
            PinnedItem(
                window=WindowInfo(100, "Editor", 42, "editor.exe"),
                pinned_at=datetime.now(UTC),
            )
        ]


class FakeResetShelfService:
    def __init__(self) -> None:
        self.unpin_all_calls = 0
        self.restore_all_focus_values: list[bool] = []

    def unpin_all(self) -> tuple[int, int]:
        self.unpin_all_calls += 1
        return 2, 1

    def restore_all(self, *, focus: bool = True) -> tuple[int, int]:
        self.restore_all_focus_values.append(focus)
        return 3, 0


class FakeOverlayGroupService:
    def __init__(self) -> None:
        self.clear_calls = 0

    def clear_assigned_windows(self) -> int:
        self.clear_calls += 1
        return 4


class FakeOverlayMarkerManager:
    def __init__(self) -> None:
        self.reset_calls = 0

    def reset_runtime(self) -> int:
        self.reset_calls += 1
        return 5


class FakeTimer:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


def test_cleanup_before_exit_always_unpins_runtime_pinned_windows() -> None:
    window = MainWindow.__new__(MainWindow)
    shelf_service = FakeLifecycleShelfService()
    recovery_store = FakeRecoveryStore()
    window._shelf_service = shelf_service
    window._recovery_store = recovery_store
    window._settings = AppSettings(restore_pinned_windows_on_exit=False)
    window._save_settings = lambda: None
    window._configure_pinned_watcher = lambda: None

    assert MainWindow._cleanup_before_exit(window) is True

    assert shelf_service.unpin_all_calls == 1
    assert recovery_store.clear_reasons == ["normal exit"]


def test_runtime_settings_do_not_persist_pinned_windows_for_startup() -> None:
    window = MainWindow.__new__(MainWindow)
    window._settings = AppSettings()
    window._selected_group_id = DEFAULT_GROUP_ID
    window._shelf_service = FakeRuntimeStateShelfService()

    MainWindow._apply_runtime_state_to_settings(window)

    assert window._settings.managed_windows == []
    assert not hasattr(window._settings, "pinned_windows")


def test_global_reset_restores_unpins_and_clears_runtime_state() -> None:
    window = MainWindow.__new__(MainWindow)
    shelf_service = FakeResetShelfService()
    overlay_service = FakeOverlayGroupService()
    marker_manager = FakeOverlayMarkerManager()
    recovery_store = FakeRecoveryStore()
    persist_reasons: list[str] = []
    timers = [FakeTimer() for _ in range(6)]

    window._shelf_service = shelf_service
    window._overlay_group_service = overlay_service
    window._overlay_marker_manager = marker_manager
    window._recovery_store = recovery_store
    window._pinned_order = [100, 200]
    window._last_shelf_items = ("hidden",)
    window._last_pinned_items = ("pinned",)
    window._pending_refresh_reason = "manual"
    (
        window._open_windows_refresh_timer,
        window._pinned_watcher_timer,
        window._window_state_refresh_timer,
        window._refresh_debounce_timer,
        window._open_windows_filter_timer,
        window._icon_refresh_timer,
    ) = timers
    window._persist_managed_state = persist_reasons.append

    result = MainWindow._perform_global_reset(window)

    assert result == {
        "restored": 3,
        "restore_skipped": 0,
        "unpinned": 2,
        "unpin_skipped": 1,
        "overlay_markers_removed": 5,
        "overlay_assignments_removed": 4,
    }
    assert shelf_service.unpin_all_calls == 1
    assert shelf_service.restore_all_focus_values == [False]
    assert overlay_service.clear_calls == 1
    assert marker_manager.reset_calls == 1
    assert all(timer.stopped for timer in timers)
    assert window._pinned_order == []
    assert window._last_shelf_items == ()
    assert window._last_pinned_items == ()
    assert window._pending_refresh_reason is None
    assert persist_reasons == ["global emergency reset"]
    assert recovery_store.clear_reasons == ["global emergency reset"]
