from __future__ import annotations

import ctypes
import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from shelfygai.constants import APP_ID, APP_NAME, APP_ORGANIZATION, APP_VERSION, resource_path
from shelfygai.core.models import WindowGroup
from shelfygai.core.shelf import ShelfService
from shelfygai.i18n import set_language
from shelfygai.settings.settings_manager import AppSettings, SettingsManager
from shelfygai.ui.main_window import MainWindow
from shelfygai.ui.theme import apply_theme
from shelfygai.updates.github_releases import GitHubReleasesUpdateService

LOGGER = logging.getLogger(__name__)


def build_application(argv: list[str], settings: AppSettings | None = None) -> QApplication:
    _set_windows_app_user_model_id()
    QApplication.setApplicationName(APP_NAME)
    QApplication.setApplicationDisplayName(APP_NAME)
    QApplication.setOrganizationName(APP_ORGANIZATION)
    QApplication.setApplicationVersion(APP_VERSION)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(argv)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(str(resource_path("app_icon.svg"))))
    active_settings = settings or AppSettings()
    set_language(active_settings.language)
    apply_theme(app, active_settings.theme, active_settings.accent_color)
    return app


def _set_windows_app_user_model_id() -> None:
    if sys.platform != "win32":
        return
    app_user_model_id = f"{APP_ORGANIZATION}.{APP_ID}"
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_user_model_id)
    except (AttributeError, OSError):
        LOGGER.debug("Could not set Windows AppUserModelID", exc_info=True)


def build_main_window(
    settings_store: SettingsManager | None = None,
    settings: AppSettings | None = None,
) -> MainWindow:
    active_settings_store = settings_store or SettingsManager()
    active_settings = settings or active_settings_store.load()
    if sys.platform == "win32":
        from shelfygai.platform.windows.window_gateway import WindowsWindowGateway

        window_gateway = WindowsWindowGateway()
    else:
        from shelfygai.core.unsupported_window_gateway import UnsupportedWindowGateway

        window_gateway = UnsupportedWindowGateway()

    shelf_service = ShelfService(window_gateway, groups=_groups_from_settings(active_settings))
    return MainWindow(
        shelf_service=shelf_service,
        settings_store=active_settings_store,
        settings=active_settings,
        update_service=GitHubReleasesUpdateService(),
    )


def _groups_from_settings(settings: AppSettings) -> list[WindowGroup]:
    groups: list[WindowGroup] = []
    for group in settings.window_groups:
        try:
            groups.append(
                WindowGroup(
                    id=str(group["id"]),
                    name=str(group["name"]),
                    sort_order=int(group.get("sort_order", len(groups))),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return groups
