from __future__ import annotations

from PySide6.QtWidgets import QSystemTrayIcon

from shelfygai.settings.settings_manager import AppSettings
from shelfygai.ui.notifications import NotificationKind, NotificationManager


class FakeStatusBar:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def showMessage(self, message: str, timeout: int = 0) -> None:
        self.messages.append(message)


class FakeTrayIcon:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, QSystemTrayIcon.MessageIcon, int]] = []

    def isVisible(self) -> bool:
        return True

    def showMessage(
        self,
        title: str,
        message: str,
        icon: QSystemTrayIcon.MessageIcon,
        msecs: int,
    ) -> None:
        self.messages.append((title, message, icon, msecs))


def test_notifications_disabled_suppresses_noncritical_notifications() -> None:
    settings = AppSettings(notifications_enabled=False)
    manager = NotificationManager(settings, tray_messages_supported=lambda: True)
    status_bar = FakeStatusBar()
    tray_icon = FakeTrayIcon()

    assert not manager.show_status(status_bar, "Saved")
    assert not manager.show_tray(tray_icon, "ShelfyGAI", "Hidden")

    assert status_bar.messages == []
    assert tray_icon.messages == []


def test_silent_mode_suppresses_noncritical_notifications() -> None:
    settings = AppSettings(silent_mode=True)
    manager = NotificationManager(settings, tray_messages_supported=lambda: True)
    status_bar = FakeStatusBar()
    tray_icon = FakeTrayIcon()

    assert not manager.show_status(status_bar, "Pinned", kind=NotificationKind.PIN)
    assert not manager.show_tray(
        tray_icon,
        "ShelfyGAI",
        "Restored",
        kind=NotificationKind.RESTORE,
    )

    assert status_bar.messages == []
    assert tray_icon.messages == []


def test_critical_notifications_bypass_silent_mode() -> None:
    settings = AppSettings(notifications_enabled=False, silent_mode=True)
    manager = NotificationManager(settings, tray_messages_supported=lambda: True)
    status_bar = FakeStatusBar()
    tray_icon = FakeTrayIcon()

    assert manager.show_status(status_bar, "Failed restore", critical=True)
    assert manager.show_tray(tray_icon, "ShelfyGAI", "Failed restore", critical=True)

    assert status_bar.messages == ["Failed restore"]
    assert tray_icon.messages[0][0] == "ShelfyGAI"
    assert tray_icon.messages[0][1] == "Failed restore"


def test_notification_category_toggles_are_respected() -> None:
    settings = AppSettings(
        show_restore_notifications=False,
        show_pin_unpin_notifications=False,
    )
    manager = NotificationManager(settings, tray_messages_supported=lambda: True)
    status_bar = FakeStatusBar()

    assert not manager.show_status(
        status_bar,
        "Restored",
        kind=NotificationKind.RESTORE,
    )
    assert not manager.show_status(status_bar, "Pinned", kind=NotificationKind.PIN)
    assert manager.show_status(status_bar, "Saved")

    assert status_bar.messages == ["Saved"]
