from __future__ import annotations

import logging
from collections.abc import Callable
from enum import StrEnum
from typing import Protocol

from PySide6.QtWidgets import QMessageBox, QSystemTrayIcon, QWidget

from shelfygai.settings.settings_manager import AppSettings

LOGGER = logging.getLogger(__name__)


class NotificationKind(StrEnum):
    STATUS = "status"
    TRAY = "tray"
    OVERLAY = "overlay"
    RESTORE = "restore"
    PIN = "pin"
    CRITICAL = "critical"


class _TrayIconLike(Protocol):
    def isVisible(self) -> bool:
        ...

    def showMessage(
        self,
        title: str,
        message: str,
        icon: QSystemTrayIcon.MessageIcon,
        msecs: int,
    ) -> None:
        ...


class _StatusBarLike(Protocol):
    def showMessage(self, message: str, timeout: int = 0) -> None:
        ...


class NotificationManager:
    """Central notification policy for tray balloons, status messages, and popups."""

    def __init__(
        self,
        settings_provider: Callable[[], AppSettings] | AppSettings,
        *,
        tray_messages_supported: Callable[[], bool] | None = None,
    ) -> None:
        self._settings_provider = settings_provider
        self._tray_messages_supported = (
            tray_messages_supported or QSystemTrayIcon.supportsMessages
        )

    @property
    def settings(self) -> AppSettings:
        if callable(self._settings_provider):
            return self._settings_provider()
        return self._settings_provider

    def allows(self, kind: NotificationKind, *, critical: bool = False) -> bool:
        settings = self.settings
        if critical or kind == NotificationKind.CRITICAL:
            return True
        if settings.silent_mode:
            self._debug_suppressed(kind, "silent mode")
            return False
        if not settings.notifications_enabled:
            self._debug_suppressed(kind, "notifications disabled")
            return False
        if kind == NotificationKind.TRAY and not settings.show_tray_notifications:
            self._debug_suppressed(kind, "tray notifications disabled")
            return False
        if kind == NotificationKind.OVERLAY and not settings.show_overlay_notifications:
            self._debug_suppressed(kind, "overlay notifications disabled")
            return False
        if kind == NotificationKind.RESTORE and not settings.show_restore_notifications:
            self._debug_suppressed(kind, "restore notifications disabled")
            return False
        if kind == NotificationKind.PIN and not settings.show_pin_unpin_notifications:
            self._debug_suppressed(kind, "pin notifications disabled")
            return False
        return True

    def show_status(
        self,
        status_bar: _StatusBarLike,
        message: str,
        *,
        kind: NotificationKind = NotificationKind.STATUS,
        critical: bool = False,
        timeout_ms: int = 0,
    ) -> bool:
        if not self.allows(kind, critical=critical):
            return False
        status_bar.showMessage(message, timeout_ms)
        return True

    def show_tray(
        self,
        tray_icon: _TrayIconLike | None,
        title: str,
        message: str,
        *,
        kind: NotificationKind = NotificationKind.TRAY,
        critical: bool = False,
        icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information,
        duration_ms: int = 4_000,
    ) -> bool:
        if not self.allows(kind, critical=critical):
            return False
        if tray_icon is None or not tray_icon.isVisible() or not self._tray_messages_supported():
            return False
        tray_icon.showMessage(title, message, icon, duration_ms)
        return True

    def show_warning_popup(
        self,
        parent: QWidget | None,
        title: str,
        message: str,
        *,
        critical: bool = False,
    ) -> bool:
        kind = NotificationKind.CRITICAL if critical else NotificationKind.STATUS
        if not self.allows(kind, critical=critical):
            return False
        QMessageBox.warning(parent, title, message)
        return True

    def _debug_suppressed(self, kind: NotificationKind, reason: str) -> None:
        if self.settings.debug_mode:
            LOGGER.debug("Notification suppressed: kind=%s reason=%s", kind.value, reason)
