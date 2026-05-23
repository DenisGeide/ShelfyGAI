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
