from __future__ import annotations

import logging
import sys
from collections.abc import Sequence
from time import perf_counter

from PySide6.QtCore import (
    QByteArray,
    QEasingCurve,
    QMimeData,
    QPoint,
    QPropertyAnimation,
    QSize,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDesktopServices,
    QDrag,
    QIcon,
    QKeySequence,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from shelfygai.constants import APP_NAME, APP_VERSION, GITHUB_REPOSITORY_URL, resource_path
from shelfygai.core.errors import ShelfyGAIError
from shelfygai.core.models import DEFAULT_GROUP_ID, PinnedItem, ShelfItem, WindowGroup, WindowInfo
from shelfygai.core.shelf import ShelfService
from shelfygai.crash import EmergencyRecoveryStore
from shelfygai.i18n import SUPPORTED_LANGUAGES, set_language, tr
from shelfygai.logging_config import AppLogger
from shelfygai.performance import elapsed_ms, log_performance, memory_usage_mb
from shelfygai.settings.settings_manager import (
    DEFAULT_GLOBAL_HOTKEYS,
    HOTKEY_QUICK_HIDE,
    HOTKEY_RESTORE_LAST,
    HOTKEY_TOGGLE_VISIBILITY,
    AppSettings,
    SettingsManager,
    current_boot_id,
)
from shelfygai.ui.icons import AppIconProvider
from shelfygai.ui.onboarding_dialog import ACCENT_COLORS, SettingsDialog
from shelfygai.ui.theme import apply_theme
from shelfygai.updates.service import UpdateService

LOGGER = logging.getLogger(__name__)

HANDLE_ROLE = Qt.ItemDataRole.UserRole
EXE_PATH_ROLE = Qt.ItemDataRole.UserRole + 1
WINDOW_HANDLE_MIME = "application/x-shelfygai-window-handle"
FILTER_ROLE = Qt.ItemDataRole.UserRole + 2
HOTKEY_ACTION_LABEL_KEYS = {
    HOTKEY_QUICK_HIDE: "hotkey.label.quick_hide",
    HOTKEY_RESTORE_LAST: "hotkey.label.restore_last",
    HOTKEY_TOGGLE_VISIBILITY: "hotkey.label.toggle_visibility",
}
HOTKEY_ACTION_DESCRIPTION_KEYS = {
    HOTKEY_QUICK_HIDE: "hotkey.desc.quick_hide",
    HOTKEY_RESTORE_LAST: "hotkey.desc.restore_last",
    HOTKEY_TOGGLE_VISIBILITY: "hotkey.desc.toggle_visibility",
}
NAVIGATION_KEYS = (
    "label.open_windows",
    "label.managed",
    "label.settings",
    "label.safety",
    "label.about",
)
NAVIGATION_ICONS = (
    QStyle.StandardPixmap.SP_ComputerIcon,
    QStyle.StandardPixmap.SP_DirIcon,
    QStyle.StandardPixmap.SP_FileDialogDetailedView,
    QStyle.StandardPixmap.SP_MessageBoxWarning,
    QStyle.StandardPixmap.SP_MessageBoxInformation,
)
PAGE_COPY_KEYS = {
    0: ("label.open_windows", "page.open_windows.subtitle"),
    1: ("label.managed_windows", "page.managed_windows.subtitle"),
    2: ("label.settings", "page.settings.subtitle"),
    3: ("label.safety", "page.safety.subtitle"),
    4: ("label.about", "page.about.subtitle"),
}


class MainWindow(QMainWindow):
    def __init__(
        self,
        shelf_service: ShelfService,
        settings_store: SettingsManager,
        settings: AppSettings,
        update_service: UpdateService,
    ) -> None:
        super().__init__()
        self._shelf_service = shelf_service
        self._settings_store = settings_store
        self._settings = settings
        self._update_service = update_service
        self._recovery_store = EmergencyRecoveryStore()
        self._app_icon = QIcon(str(resource_path("app_icon.svg")))
        self._i18n_bindings: list[tuple[object, str, str, dict[str, object]]] = []
        set_language(self._settings.language)

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setWindowIcon(self._app_icon)
        self.resize(1120, 720)
        self.setMinimumSize(920, 600)

        self._available_table = self._build_table()
        self._shelf_table = self._build_table()
        self._pinned_table = self._build_table()
        self._icon_provider = AppIconProvider(self)
        self._icon_refresh_timer = QTimer(self)
        self._icon_refresh_timer.setSingleShot(True)
        self._icon_refresh_timer.setInterval(60)
        self._icon_refresh_timer.timeout.connect(self._refresh_cached_icons)
        self._icon_provider.iconLoaded.connect(lambda _path: self._icon_refresh_timer.start())
        self._selected_group_id = self._valid_group_id(self._settings.selected_group_id)
        self._group_buttons: dict[str, GroupButton] = {}
        self._groups_container = QWidget()
        self._groups_layout = QVBoxLayout(self._groups_container)
        self._groups_layout.setContentsMargins(0, 0, 0, 0)
        self._groups_layout.setSpacing(8)
        self._managed_cards_container = QWidget()
        self._managed_cards_layout = QVBoxLayout(self._managed_cards_container)
        self._managed_cards_layout.setContentsMargins(0, 0, 0, 0)
        self._managed_cards_layout.setSpacing(12)
        self._managed_cards_scroll = QScrollArea()
        self._managed_cards_scroll.setObjectName("CardScroll")
        self._managed_cards_scroll.setWidgetResizable(True)
        self._managed_cards_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._managed_cards_scroll.setWidget(self._managed_cards_container)
        self._open_windows_search = QLineEdit()
        self._managed_windows_search = QLineEdit()
        self._open_windows_auto_refresh_checkbox = QCheckBox()
        self._open_windows_refresh_timer = QTimer(self)
        self._pinned_watcher_timer = QTimer(self)
        self._header_title = QLabel()
        self._header_subtitle = QLabel()
        self._loading_label = QLabel()
        self._open_windows_empty_label = QLabel()
        self._shelf_empty_label = QLabel()
        self._pinned_empty_label = QLabel()
        self._restore_on_exit_checkbox = QCheckBox()
        self._restore_pinned_on_exit_checkbox = QCheckBox()
        self._focus_restored_checkbox = QCheckBox()
        self._confirm_checkbox = QCheckBox()
        self._confirm_quit_checkbox = QCheckBox()
        self._prevent_minimize_watcher_checkbox = QCheckBox()
        self._allow_pin_self_checkbox = QCheckBox()
        self._pinned_watcher_interval_spin = QSpinBox()
        self._settings_language_combo = QComboBox()
        self._settings_theme_combo = QComboBox()
        self._settings_accent_group = QButtonGroup(self)
        self._settings_accent_group.setExclusive(True)
        self._settings_accent_buttons: dict[str, QToolButton] = {}
        self._launch_with_windows_checkbox = QCheckBox()
        self._minimize_to_tray_checkbox = QCheckBox()
        self._startup_notification_checkbox = QCheckBox()
        self._debug_mode_checkbox = QCheckBox()
        self._startup_status_label = QLabel()
        self._startup_status_label.setObjectName("Muted")
        self._startup_status_label.setWordWrap(True)
        self._settings_controls_syncing = False
        self._hotkey_enabled_checkboxes: dict[str, QCheckBox] = {}
        self._hotkey_sequence_edits: dict[str, QKeySequenceEdit] = {}
        self._hotkey_status_label = QLabel()
        self._update_status_label = QLabel()
        self._hotkey_registration_errors: list[str] = []
        self._hotkey_manager = None
        self._syncing_hotkey_controls = False
        self._stack = QStackedWidget()
        self._sidebar: QFrame | None = None
        self._content_layout: QVBoxLayout | None = None
        self._nav_buttons: list[QPushButton] = []
        self._card_animation: QPropertyAnimation | None = None
        self._page_animation: QPropertyAnimation | None = None
        self._tray_icon: QSystemTrayIcon | None = None
        self._tray_restore_all_action: QAction | None = None
        self._is_quitting = False
        self._tray_hint_shown = False
        self._initial_refresh_done = False
        self._initial_refresh_scheduled = False
        self._managed_cards_dirty = True
        self._last_shelf_items: tuple[ShelfItem, ...] = ()
        self._last_pinned_items: tuple[PinnedItem, ...] = ()

        self._open_windows_refresh_timer.setInterval(5_000)
        self._open_windows_refresh_timer.setTimerType(Qt.TimerType.VeryCoarseTimer)
        self._open_windows_refresh_timer.timeout.connect(lambda: self._refresh(reason="auto"))
        self._pinned_watcher_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._pinned_watcher_timer.timeout.connect(self._check_pinned_windows)
        self._configure_table_context_menus()
        self._bind_text(self._open_windows_search, "placeholder.open_search", "setPlaceholderText")
        self._bind_text(self._open_windows_search, "placeholder.open_search", "setAccessibleName")
        self._open_windows_search.setClearButtonEnabled(True)
        self._open_windows_search.textChanged.connect(self._apply_open_windows_filter)
        self._bind_text(
            self._managed_windows_search,
            "placeholder.hidden_search",
            "setPlaceholderText",
        )
        self._bind_text(
            self._managed_windows_search,
            "placeholder.hidden_search",
            "setAccessibleName",
        )
        self._managed_windows_search.setClearButtonEnabled(True)
        self._managed_windows_search.textChanged.connect(
            lambda: self._populate_managed_cards(self._last_shelf_items)
        )
        self._loading_label.setObjectName("LoadingPill")
        self._loading_label.setVisible(False)
        self._loading_label.setMinimumHeight(28)
        self._open_windows_empty_label.setObjectName("EmptyState")
        self._open_windows_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._open_windows_empty_label.setWordWrap(True)
        self._open_windows_empty_label.setMinimumHeight(76)
        self._open_windows_empty_label.setVisible(False)
        self._shelf_empty_label.setObjectName("EmptyState")
        self._shelf_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._shelf_empty_label.setWordWrap(True)
        self._shelf_empty_label.setMinimumHeight(76)
        self._shelf_empty_label.setVisible(False)
        self._pinned_empty_label.setObjectName("EmptyState")
        self._pinned_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pinned_empty_label.setWordWrap(True)
        self._pinned_empty_label.setMinimumHeight(76)
        self._pinned_empty_label.setVisible(False)
        self._pinned_watcher_interval_spin.setRange(100, 10_000)
        self._pinned_watcher_interval_spin.setSingleStep(100)
        self._pinned_watcher_interval_spin.setSuffix(" ms")
        self._bind_text(self._open_windows_auto_refresh_checkbox, "label.auto_refresh")
        self._bind_text(self._restore_on_exit_checkbox, "label.restore_on_exit")
        self._bind_text(self._restore_pinned_on_exit_checkbox, "label.restore_pinned_on_exit")
        self._bind_text(self._focus_restored_checkbox, "label.focus_restored_windows")
        self._bind_text(self._confirm_checkbox, "label.confirm_before_hiding")
        self._bind_text(self._confirm_quit_checkbox, "label.confirm_quit_with_hidden_windows")
        self._bind_text(
            self._prevent_minimize_watcher_checkbox,
            "label.prevent_minimize_watcher",
        )
        self._bind_text(self._allow_pin_self_checkbox, "label.allow_pin_shelfygai")
        self._bind_text(
            self._pinned_watcher_interval_spin,
            "label.pinned_watcher_interval",
            "setAccessibleName",
        )
        self._bind_text(self._launch_with_windows_checkbox, "label.launch_with_windows")
        self._bind_text(self._minimize_to_tray_checkbox, "label.minimize_to_tray")
        self._bind_text(self._startup_notification_checkbox, "label.startup_notification")
        self._bind_text(self._debug_mode_checkbox, "label.debug_logging")
        self._bind_text(self._hotkey_status_label, "hotkey.default_status")
        self._bind_text(self._update_status_label, "about.update.default")
        self._open_windows_auto_refresh_checkbox.setChecked(
            self._settings.open_windows_auto_refresh
        )
        self._open_windows_auto_refresh_checkbox.toggled.connect(
            self._set_open_windows_auto_refresh
        )
        self._focus_restored_checkbox.setChecked(self._settings.focus_restored_windows)
        self._focus_restored_checkbox.toggled.connect(self._set_focus_restored_windows)
        self._restore_on_exit_checkbox.toggled.connect(self._set_restore_windows_on_exit)
        self._restore_pinned_on_exit_checkbox.toggled.connect(
            self._set_restore_pinned_windows_on_exit
        )
        self._confirm_checkbox.toggled.connect(self._set_confirm_before_hiding)
        self._confirm_quit_checkbox.toggled.connect(self._set_confirm_quit_with_hidden_windows)
        self._prevent_minimize_watcher_checkbox.toggled.connect(
            self._set_prevent_minimize_watcher
        )
        self._allow_pin_self_checkbox.toggled.connect(self._set_allow_pin_self)
        self._pinned_watcher_interval_spin.valueChanged.connect(
            self._set_pinned_watcher_interval
        )
        self._launch_with_windows_checkbox.toggled.connect(self._set_launch_with_windows)
        self._minimize_to_tray_checkbox.toggled.connect(self._set_minimize_to_tray_on_close)
        self._startup_notification_checkbox.toggled.connect(self._set_startup_notification)
        self._debug_mode_checkbox.toggled.connect(self._set_debug_mode)
        self._settings_language_combo.currentIndexChanged.connect(self._set_language_from_settings)
        self._settings_theme_combo.currentIndexChanged.connect(self._set_theme_from_settings)

        self._build_actions()
        self._build_layout()
        self._build_tray()
        self._sync_tray_actions()
        self._restore_settings()
        self._configure_open_windows_auto_refresh(self._settings.open_windows_auto_refresh)
        self._configure_global_hotkeys()
        self._configure_pinned_watcher()
        qt_app = QApplication.instance()
        if qt_app is not None:
            qt_app.aboutToQuit.connect(self._cleanup_global_hotkeys)

    def _bind_text(
        self,
        target: object,
        key: str,
        setter: str = "setText",
        **kwargs: object,
    ) -> None:
        self._i18n_bindings.append((target, setter, key, kwargs))
        self._apply_text_binding(target, setter, key, kwargs)

    def _apply_text_binding(
        self,
        target: object,
        setter: str,
        key: str,
        kwargs: dict[str, object],
    ) -> None:
        method = getattr(target, setter, None)
        if callable(method):
            try:
                method(tr(key, **kwargs))
            except RuntimeError:
                LOGGER.debug("Skipped stale localized widget binding: key=%s", key)

    def _retranslate(self) -> None:
        for target, setter, key, kwargs in list(self._i18n_bindings):
            self._apply_text_binding(target, setter, key, kwargs)
        self._refresh_settings_choice_labels()
        self._set_table_headers(self._available_table)
        self._set_table_headers(self._shelf_table)
        self._set_table_headers(self._pinned_table)
        self._show_page(self._stack.currentIndex())
        self._rebuild_group_sidebar()
        self._populate_managed_cards(self._last_shelf_items)
        self._populate_pinned(self._last_pinned_items)
        for action_id, checkbox in self._hotkey_enabled_checkboxes.items():
            checkbox.setToolTip(
                tr("tooltip.enable_hotkey", label=self._hotkey_label(action_id).lower())
            )

    def _set_table_headers(self, table: QTableWidget) -> None:
        table.setHorizontalHeaderLabels(
            [
                tr("label.table.app"),
                tr("label.table.title"),
                tr("label.table.pid"),
                tr("label.table.hwnd"),
            ]
        )

    def _hotkey_label(self, action_id: str) -> str:
        return tr(HOTKEY_ACTION_LABEL_KEYS.get(action_id, action_id))

    def _hotkey_description(self, action_id: str) -> str:
        return tr(HOTKEY_ACTION_DESCRIPTION_KEYS.get(action_id, action_id))

    def _group_display_name(self, group: WindowGroup | None) -> str:
        if group is None:
            return tr("group.this_group")
        if group.id == DEFAULT_GROUP_ID:
            return tr("group.ungrouped")
        return group.name

    def _refresh_settings_choice_labels(self) -> None:
        self._populate_settings_language_combo()
        self._populate_settings_theme_combo()
        for _color, button in self._settings_accent_buttons.items():
            key = str(button.property("i18n_key"))
            button.setToolTip(tr(key))
            button.setAccessibleName(f"{tr(key)} {tr('label.accent_color')}")
        self._sync_settings_accent_buttons()

    def _populate_settings_language_combo(self) -> None:
        current = self._settings_language_combo.currentData() or self._settings.language
        self._settings_language_combo.blockSignals(True)
        self._settings_language_combo.clear()
        for language, label in SUPPORTED_LANGUAGES.items():
            self._settings_language_combo.addItem(label, language)
        index = self._settings_language_combo.findData(current)
        self._settings_language_combo.setCurrentIndex(max(index, 0))
        self._settings_language_combo.blockSignals(False)

    def _populate_settings_theme_combo(self) -> None:
        current = self._settings_theme_combo.currentData() or self._settings.theme
        self._settings_theme_combo.blockSignals(True)
        self._settings_theme_combo.clear()
        for key, value in (
            ("theme.system", "system"),
            ("theme.dark", "dark"),
            ("theme.light", "light"),
        ):
            self._settings_theme_combo.addItem(tr(key), value)
        index = self._settings_theme_combo.findData(current)
        self._settings_theme_combo.setCurrentIndex(max(index, 0))
        self._settings_theme_combo.blockSignals(False)

    def _sync_settings_accent_buttons(self) -> None:
        for color, button in self._settings_accent_buttons.items():
            button.setChecked(color == self._settings.accent_color)

    def _build_actions(self) -> None:
        refresh_action = QAction(self)
        self._bind_text(refresh_action, "action.refresh")
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._refresh)
        self.addAction(refresh_action)

        settings_action = QAction(self)
        self._bind_text(settings_action, "action.settings")
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._show_settings_page)
        self.addAction(settings_action)

        search_action = QAction(self)
        self._bind_text(search_action, "action.search")
        search_action.setShortcut("Ctrl+F")
        search_action.triggered.connect(self._focus_active_search)
        self.addAction(search_action)

        hide_action = QAction(self)
        self._bind_text(hide_action, "action.hide_selected")
        hide_action.setShortcut("Ctrl+H")
        hide_action.triggered.connect(self._shelve_selected)
        self.addAction(hide_action)

        pin_action = QAction(self)
        self._bind_text(pin_action, "action.pin_selected")
        pin_action.setShortcut("Ctrl+P")
        pin_action.triggered.connect(self._pin_selected)
        self.addAction(pin_action)

        restore_action = QAction(self)
        self._bind_text(restore_action, "action.restore_selected")
        restore_action.setShortcut("Ctrl+R")
        restore_action.triggered.connect(lambda: self._restore_selected(self._shelf_table))
        self.addAction(restore_action)

        restore_all_action = QAction(self)
        self._bind_text(restore_all_action, "action.restore_all")
        restore_all_action.setShortcut("Ctrl+Shift+R")
        restore_all_action.triggered.connect(self._restore_all)
        self.addAction(restore_all_action)

        clear_search_action = QAction(self)
        self._bind_text(clear_search_action, "action.clear_search")
        clear_search_action.setShortcut("Esc")
        clear_search_action.triggered.connect(self._clear_active_search)
        self.addAction(clear_search_action)

        for index in range(len(NAVIGATION_KEYS)):
            page_action = QAction(self)
            self._bind_text(page_action, "action.open_page", number=index + 1)
            page_action.setShortcut(f"Ctrl+{index + 1}")
            page_action.triggered.connect(lambda _checked=False, page=index: self._show_page(page))
            self.addAction(page_action)

    def _configure_table_context_menus(self) -> None:
        for table in (self._available_table, self._shelf_table, self._pinned_table):
            table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            table.customContextMenuRequested.connect(
                lambda position, current_table=table: self._show_window_context_menu(
                    current_table,
                    position,
                )
            )

    def _build_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            LOGGER.warning("System tray is unavailable; tray support disabled")
            return

        tray_menu = QMenu(self)

        open_action = QAction(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon),
            "",
            self,
        )
        self._bind_text(open_action, "tray.open")
        open_action.triggered.connect(self._show_from_tray)

        restore_all_action = QAction(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogResetButton),
            "",
            self,
        )
        self._bind_text(restore_all_action, "tray.restore_all")
        restore_all_action.triggered.connect(self._restore_all)
        self._tray_restore_all_action = restore_all_action

        settings_action = QAction(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView),
            "",
            self,
        )
        self._bind_text(settings_action, "action.settings")
        settings_action.triggered.connect(self._open_settings_from_tray)

        quit_action = QAction(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton),
            "",
            self,
        )
        self._bind_text(quit_action, "tray.quit")
        quit_action.triggered.connect(self._quit_from_tray)

        tray_menu.addAction(open_action)
        tray_menu.addAction(restore_all_action)
        tray_menu.addSeparator()
        tray_menu.addAction(settings_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)

        self._tray_icon = QSystemTrayIcon(self._app_icon, self)
        self._bind_text(self._tray_icon, "tray.tooltip", "setToolTip", version=APP_VERSION)
        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()
        LOGGER.info("System tray icon initialized")

    def _build_layout(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._sidebar = self._build_sidebar()
        root_layout.addWidget(self._sidebar)
        root_layout.addWidget(self._build_content(), 1)

        self.setCentralWidget(root)
        self.statusBar().showMessage(tr("status.ready"))
        self._apply_adaptive_layout()

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(248)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 24, 20, 20)
        layout.setSpacing(12)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(12)

        brand_icon = QLabel()
        brand_icon.setObjectName("IconBadge")
        brand_icon.setFixedSize(48, 48)
        brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_icon.setPixmap(QIcon(str(resource_path("app_icon.svg"))).pixmap(34, 34))

        brand_text = QVBoxLayout()
        brand_text.setSpacing(2)
        brand_title = QLabel(APP_NAME)
        brand_title.setObjectName("BrandTitle")
        brand_subtitle = QLabel()
        brand_subtitle.setObjectName("BrandSubtitle")
        self._bind_text(brand_subtitle, "app.window_manager")

        brand_text.addWidget(brand_title)
        brand_text.addWidget(brand_subtitle)
        brand_row.addWidget(brand_icon)
        brand_row.addLayout(brand_text, 1)

        layout.addLayout(brand_row)
        layout.addSpacing(16)

        for index, label_key in enumerate(NAVIGATION_KEYS):
            button = QPushButton()
            button.setObjectName("SidebarButton")
            button.setCheckable(True)
            button.setIcon(self.style().standardIcon(NAVIGATION_ICONS[index]))
            button.setIconSize(QSize(18, 18))
            self._bind_text(button, label_key)
            button.clicked.connect(lambda _checked=False, page=index: self._show_page(page))
            self._nav_buttons.append(button)
            layout.addWidget(button)

        layout.addSpacing(14)
        groups_header = QHBoxLayout()
        groups_label = QLabel()
        groups_label.setObjectName("SectionTitle")
        self._bind_text(groups_label, "label.groups")
        groups_header.addWidget(groups_label)
        groups_header.addStretch(1)
        layout.addLayout(groups_header)

        group_actions = QHBoxLayout()
        group_actions.setSpacing(8)
        add_group_button = self._make_tool_button(
            "tooltip.create_group",
            self._create_group,
            QStyle.StandardPixmap.SP_FileDialogNewFolder,
        )
        rename_group_button = self._make_tool_button(
            "tooltip.rename_group",
            self._rename_selected_group,
            QStyle.StandardPixmap.SP_FileDialogDetailedView,
        )
        delete_group_button = self._make_tool_button(
            "tooltip.delete_group",
            self._delete_selected_group,
            QStyle.StandardPixmap.SP_DialogCloseButton,
        )
        group_actions.addWidget(add_group_button)
        group_actions.addWidget(rename_group_button)
        group_actions.addWidget(delete_group_button)
        group_actions.addStretch(1)
        layout.addLayout(group_actions)
        layout.addWidget(self._groups_container)
        self._rebuild_group_sidebar()

        layout.addStretch(1)

        version = QLabel(f"v{APP_VERSION}")
        version.setObjectName("BrandSubtitle")
        layout.addWidget(version)

        self._show_page(0)
        return sidebar

    def _build_content(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(20)
        self._content_layout = layout

        layout.addLayout(self._build_header())

        self._stack.addWidget(self._build_windows_page())
        self._stack.addWidget(self._build_shelf_page())
        self._stack.addWidget(self._build_settings_page())
        self._stack.addWidget(self._build_safety_page())
        self._stack.addWidget(self._build_about_page())
        layout.addWidget(self._stack, 1)

        return content

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)

        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        self._header_title.setObjectName("HeaderTitle")
        self._header_subtitle.setObjectName("HeaderSubtitle")
        self._header_subtitle.setWordWrap(True)
        title_box.addWidget(self._header_title)
        title_box.addWidget(self._header_subtitle)

        refresh_button = self._make_quick_action_button(
            "action.refresh",
            self._refresh,
            QStyle.StandardPixmap.SP_BrowserReload,
            "tooltip.refresh",
        )
        hide_button = self._make_quick_action_button(
            "action.hide",
            self._shelve_selected,
            QStyle.StandardPixmap.SP_ArrowForward,
            "tooltip.hide_selected",
        )
        restore_button = self._make_quick_action_button(
            "action.restore_all",
            self._restore_all,
            QStyle.StandardPixmap.SP_DialogResetButton,
            "tooltip.restore_all",
        )
        settings_button = self._make_quick_action_button(
            "action.settings",
            self._show_settings_page,
            QStyle.StandardPixmap.SP_FileDialogDetailedView,
            "tooltip.open_settings",
        )

        layout.addLayout(title_box)
        layout.addStretch(1)
        layout.addWidget(self._loading_label)
        layout.addWidget(refresh_button)
        layout.addWidget(hide_button)
        layout.addWidget(restore_button)
        layout.addWidget(settings_button)
        return layout

    def _build_windows_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        available_panel = self._build_open_windows_panel()
        shelf_panel = self._build_panel(
            title_key="label.managed_windows",
            table=self._shelf_table,
            buttons=[
                self._make_button(
                    "action.restore_selected",
                    lambda: self._restore_selected(self._shelf_table),
                    primary=True,
                    icon=QStyle.StandardPixmap.SP_ArrowBack,
                ),
                self._make_button(
                    "action.restore_all_sentence",
                    self._restore_all,
                    icon=QStyle.StandardPixmap.SP_DialogResetButton,
                ),
            ],
        )
        pinned_panel = self._build_panel(
            title_key="label.pinned_windows",
            table=self._pinned_table,
            buttons=[
                self._make_button(
                    "action.unpin_selected",
                    self._unpin_selected,
                    primary=True,
                    icon=QStyle.StandardPixmap.SP_DialogResetButton,
                ),
                self._make_button(
                    "action.bring_forward",
                    lambda: self._bring_selected_forward(self._pinned_table),
                    icon=QStyle.StandardPixmap.SP_ArrowUp,
                ),
            ],
        )
        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(16)
        right_layout.addWidget(shelf_panel, 1)
        right_layout.addWidget(pinned_panel, 1)

        layout.addWidget(available_panel, 3)
        layout.addWidget(right_column, 2)
        return page

    def _build_open_windows_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(13)

        panel_title = QLabel()
        panel_title.setObjectName("PanelTitle")
        self._bind_text(panel_title, "label.open_windows")

        control_row = QHBoxLayout()
        control_row.setSpacing(10)
        control_row.addWidget(self._open_windows_search, 1)

        refresh_button = QPushButton()
        self._bind_text(refresh_button, "action.refresh")
        refresh_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        refresh_button.clicked.connect(self._refresh)
        control_row.addWidget(refresh_button)
        control_row.addWidget(self._open_windows_auto_refresh_checkbox)

        layout.addWidget(panel_title)
        layout.addLayout(control_row)
        layout.addWidget(self._available_table, 1)
        layout.addWidget(self._open_windows_empty_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        button_row.addStretch(1)
        button_row.addWidget(
            self._make_button(
                "action.pin_selected",
                self._pin_selected,
                icon=QStyle.StandardPixmap.SP_ArrowUp,
            )
        )
        button_row.addWidget(
            self._make_button(
                "action.hide_selected",
                self._shelve_selected,
                primary=True,
                icon=QStyle.StandardPixmap.SP_ArrowForward,
            )
        )
        button_row.addWidget(
            self._make_button(
                "action.bring_forward",
                self._bring_selected_forward,
                icon=QStyle.StandardPixmap.SP_ArrowUp,
            )
        )
        layout.addLayout(button_row)
        return panel

    def _build_shelf_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        action_row.addWidget(self._managed_windows_search, 1)
        action_row.addStretch(1)
        action_row.addWidget(
            self._make_button(
                "action.restore_all",
                self._restore_all,
                primary=True,
                icon=QStyle.StandardPixmap.SP_DialogResetButton,
            )
        )
        layout.addLayout(action_row)
        layout.addWidget(self._managed_cards_scroll, 1)
        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QGridLayout(content)
        content_layout.setContentsMargins(0, 0, 8, 0)
        content_layout.setHorizontalSpacing(14)
        content_layout.setVerticalSpacing(14)
        content_layout.setColumnStretch(0, 1)
        content_layout.setColumnStretch(1, 1)

        general_panel = self._build_settings_section(
            "settings.section.general",
            [
                self._open_windows_auto_refresh_checkbox,
                self._debug_mode_checkbox,
            ],
        )
        appearance_panel = self._build_settings_section(
            "settings.section.appearance",
            [
                self._build_settings_combo_row("label.theme", self._settings_theme_combo),
                self._build_settings_accent_row(),
            ],
        )
        language_panel = self._build_settings_section(
            "settings.section.language",
            [
                self._build_settings_combo_row(
                    "label.language",
                    self._settings_language_combo,
                ),
            ],
        )
        startup_panel = self._build_settings_section(
            "settings.section.startup",
            [
                self._launch_with_windows_checkbox,
                self._startup_notification_checkbox,
                self._startup_status_label,
            ],
        )
        tray_panel = self._build_settings_section(
            "settings.section.tray",
            [self._minimize_to_tray_checkbox],
        )
        safety_panel = self._build_settings_section(
            "settings.section.safety",
            [
                self._restore_on_exit_checkbox,
                self._focus_restored_checkbox,
                self._confirm_quit_checkbox,
                self._confirm_checkbox,
            ],
        )
        pin_panel = self._build_settings_section(
            "settings.section.pin_windows",
            [
                self._restore_pinned_on_exit_checkbox,
                self._prevent_minimize_watcher_checkbox,
                self._build_settings_spin_row(
                    "label.pinned_watcher_interval",
                    self._pinned_watcher_interval_spin,
                ),
                self._allow_pin_self_checkbox,
            ],
        )

        content_layout.addWidget(general_panel, 0, 0)
        content_layout.addWidget(appearance_panel, 0, 1)
        content_layout.addWidget(language_panel, 1, 0)
        content_layout.addWidget(startup_panel, 1, 1)
        content_layout.addWidget(tray_panel, 2, 0)
        content_layout.addWidget(safety_panel, 2, 1)
        content_layout.addWidget(pin_panel, 3, 0, 1, 2)
        content_layout.addWidget(self._build_hotkeys_panel(), 4, 0, 1, 2)
        content_layout.addWidget(self._build_settings_about_section(), 5, 0, 1, 2)
        content_layout.setRowStretch(6, 1)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        self._sync_settings_controls()
        return page

    def _build_settings_section(self, title_key: str, widgets: list[QWidget]) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(11)

        title = QLabel()
        title.setObjectName("PanelTitle")
        self._bind_text(title, title_key)
        panel_layout.addWidget(title)

        for widget in widgets:
            panel_layout.addWidget(widget)

        return panel

    def _build_settings_combo_row(self, label_key: str, combo: QComboBox) -> QWidget:
        row = QWidget()
        layout = QGridLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(12)
        layout.setColumnStretch(1, 1)

        label = QLabel()
        label.setObjectName("Muted")
        self._bind_text(label, label_key)
        self._bind_text(combo, label_key, "setAccessibleName")

        layout.addWidget(label, 0, 0)
        layout.addWidget(combo, 0, 1)
        return row

    def _build_settings_spin_row(self, label_key: str, spin_box: QSpinBox) -> QWidget:
        row = QWidget()
        layout = QGridLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(12)
        layout.setColumnStretch(1, 1)

        label = QLabel()
        label.setObjectName("Muted")
        self._bind_text(label, label_key)
        self._bind_text(spin_box, label_key, "setAccessibleName")

        layout.addWidget(label, 0, 0)
        layout.addWidget(spin_box, 0, 1)
        return row

    def _build_settings_accent_row(self) -> QWidget:
        row = QWidget()
        layout = QGridLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(12)
        layout.setColumnStretch(1, 1)

        label = QLabel()
        label.setObjectName("Muted")
        self._bind_text(label, "label.accent_color")

        chips = QWidget()
        chips_layout = QHBoxLayout(chips)
        chips_layout.setContentsMargins(0, 0, 0, 0)
        chips_layout.setSpacing(10)

        for name_key, color in ACCENT_COLORS:
            button = QToolButton()
            button.setCheckable(True)
            button.setProperty("i18n_key", name_key)
            button.setFixedSize(34, 34)
            button.setStyleSheet(
                f"""
                QToolButton {{
                    background: {color};
                    border: 2px solid transparent;
                    border-radius: 17px;
                }}
                QToolButton:checked {{
                    border: 3px solid #ffffff;
                }}
                QToolButton:hover {{
                    border: 3px solid rgba(255, 255, 255, 0.72);
                }}
                """
            )
            button.clicked.connect(
                lambda _checked=False, selected=color: self._set_accent_from_settings(selected)
            )
            self._settings_accent_buttons[color] = button
            self._settings_accent_group.addButton(button)
            chips_layout.addWidget(button)

        chips_layout.addStretch(1)
        layout.addWidget(label, 0, 0)
        layout.addWidget(chips, 0, 1)
        return row

    def _build_settings_about_section(self) -> QFrame:
        version_label = QLabel()
        version_label.setObjectName("CardTitle")
        self._bind_text(version_label, "about.version", version=APP_VERSION)

        license_label = QLabel()
        license_label.setObjectName("Muted")
        self._bind_text(license_label, "about.license.detail")

        privacy_label = QLabel()
        privacy_label.setObjectName("Muted")
        privacy_label.setWordWrap(True)
        self._bind_text(privacy_label, "about.privacy")

        storage_label = QLabel()
        storage_label.setObjectName("Muted")
        storage_label.setWordWrap(True)
        self._bind_text(storage_label, "settings.storage_path")

        github_button = self._make_button(
            "github.repository",
            self._open_github,
            icon=QStyle.StandardPixmap.SP_DialogOpenButton,
        )

        return self._build_settings_section(
            "settings.section.about",
            [version_label, license_label, privacy_label, storage_label, github_button],
        )

    def _build_safety_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 8, 0)
        content_layout.setSpacing(14)

        for title_key, body_key in (
            ("safety.can.title", "safety.can.body"),
            ("safety.cannot.title", "safety.cannot.body"),
            ("safety.why.title", "safety.why.body"),
            ("safety.restore.title", "safety.restore.body"),
        ):
            content_layout.addWidget(self._build_safety_card(title_key, body_key))

        content_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return page

    def _build_safety_card(self, title_key: str, body_key: str) -> QFrame:
        card = QFrame()
        card.setObjectName("Panel")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title = QLabel()
        title.setObjectName("PanelTitle")
        self._bind_text(title, title_key)

        body = QLabel()
        body.setObjectName("Muted")
        body.setWordWrap(True)
        self._bind_text(body, body_key)

        layout.addWidget(title)
        layout.addWidget(body)
        return card

    def _build_about_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 8, 0)
        content_layout.setSpacing(14)

        hero = QFrame()
        hero.setObjectName("AboutHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(22, 22, 22, 22)
        hero_layout.setSpacing(18)

        logo = QLabel()
        logo.setObjectName("AboutLogo")
        logo.setFixedSize(72, 72)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setPixmap(QIcon(str(resource_path("app_icon.svg"))).pixmap(52, 52))

        copy_box = QVBoxLayout()
        copy_box.setSpacing(7)

        title = QLabel(APP_NAME)
        title.setObjectName("HeroTitle")
        description = QLabel()
        description.setObjectName("Muted")
        description.setWordWrap(True)
        self._bind_text(description, "about.description")

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        github_button = self._make_button(
            "github.repository",
            self._open_github,
            icon=QStyle.StandardPixmap.SP_DialogOpenButton,
        )
        github_button.setObjectName("PrimaryButton")
        button_row.addWidget(github_button)
        button_row.addStretch(1)

        copy_box.addWidget(title)
        copy_box.addWidget(description)
        copy_box.addLayout(button_row)
        hero_layout.addWidget(logo)
        hero_layout.addLayout(copy_box, 1)

        info_grid = QGridLayout()
        info_grid.setContentsMargins(0, 0, 0, 0)
        info_grid.setHorizontalSpacing(14)
        info_grid.setVerticalSpacing(14)
        info_grid.setColumnStretch(0, 1)
        info_grid.setColumnStretch(1, 1)
        info_grid.addWidget(
            self._build_about_info_tile("about.version.title", "about.version", APP_VERSION),
            0,
            0,
        )
        info_grid.addWidget(
            self._build_about_info_tile("about.license", "about.license.detail"),
            0,
            1,
        )
        info_grid.addWidget(
            self._build_about_info_tile("about.privacy.title", "about.privacy"),
            1,
            0,
            1,
            2,
        )
        info_grid.addWidget(
            self._build_about_info_tile("about.github.title", "about.github.copy"),
            2,
            0,
            1,
            2,
        )

        update_panel = QFrame()
        update_panel.setObjectName("Panel")
        update_layout = QVBoxLayout(update_panel)
        update_layout.setContentsMargins(18, 18, 18, 18)
        update_layout.setSpacing(12)

        update_title = QLabel()
        update_title.setObjectName("SectionTitle")
        self._bind_text(update_title, "about.updates.title")
        update_copy = QLabel()
        update_copy.setObjectName("Muted")
        update_copy.setWordWrap(True)
        self._bind_text(update_copy, "about.updates.copy")

        self._update_status_label.setObjectName("EmptyState")
        self._update_status_label.setWordWrap(True)

        check_button = QPushButton()
        self._bind_text(check_button, "about.update.button")
        check_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        check_button.clicked.connect(self._check_for_updates)

        update_layout.addWidget(update_title)
        update_layout.addWidget(update_copy)
        update_layout.addWidget(self._update_status_label)
        update_layout.addWidget(check_button, alignment=Qt.AlignmentFlag.AlignLeft)

        content_layout.addWidget(hero)
        content_layout.addLayout(info_grid)
        content_layout.addWidget(update_panel)
        content_layout.addStretch(1)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return page

    def _build_about_info_tile(
        self,
        title_key: str,
        body_key: str,
        *args: object,
    ) -> QFrame:
        tile = QFrame()
        tile.setObjectName("InfoTile")
        layout = QVBoxLayout(tile)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(7)

        title = QLabel()
        title.setObjectName("SectionTitle")
        self._bind_text(title, title_key)

        body = QLabel()
        body.setObjectName("Muted")
        body.setWordWrap(True)
        if args:
            self._bind_text(body, body_key, version=args[0])
        else:
            self._bind_text(body, body_key)

        layout.addWidget(title)
        layout.addWidget(body)
        return tile

    def _build_hotkeys_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel()
        title.setObjectName("PanelTitle")
        self._bind_text(title, "settings.section.hotkeys")
        self._hotkey_status_label.setObjectName("Muted")
        self._hotkey_status_label.setWordWrap(True)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)

        for row, action_id in enumerate(HOTKEY_ACTION_LABEL_KEYS):
            enabled_checkbox = QCheckBox()
            enabled_checkbox.setToolTip(
                tr("tooltip.enable_hotkey", label=self._hotkey_label(action_id).lower())
            )
            enabled_checkbox.toggled.connect(self._save_hotkey_settings)

            label_box = QVBoxLayout()
            action_label = QLabel()
            action_label.setObjectName("CardTitle")
            self._bind_text(action_label, HOTKEY_ACTION_LABEL_KEYS[action_id])
            action_description = QLabel()
            action_description.setObjectName("Muted")
            action_description.setWordWrap(True)
            self._bind_text(action_description, HOTKEY_ACTION_DESCRIPTION_KEYS[action_id])
            label_box.addWidget(action_label)
            label_box.addWidget(action_description)

            sequence_edit = QKeySequenceEdit()
            sequence_edit.setMaximumSequenceLength(1)
            sequence_edit.editingFinished.connect(self._save_hotkey_settings)

            clear_button = QPushButton()
            self._bind_text(clear_button, "action.clear")
            clear_button.clicked.connect(
                lambda _checked=False, current_action=action_id: self._clear_hotkey(
                    current_action
                )
            )

            self._hotkey_enabled_checkboxes[action_id] = enabled_checkbox
            self._hotkey_sequence_edits[action_id] = sequence_edit

            grid.addWidget(enabled_checkbox, row, 0, Qt.AlignmentFlag.AlignTop)
            grid.addLayout(label_box, row, 1)
            grid.addWidget(sequence_edit, row, 2)
            grid.addWidget(clear_button, row, 3)

        restore_defaults_button = QPushButton()
        self._bind_text(restore_defaults_button, "action.restore_default_hotkeys")
        restore_defaults_button.clicked.connect(self._restore_default_hotkeys)

        layout.addWidget(title)
        layout.addLayout(grid)
        layout.addWidget(self._hotkey_status_label)
        layout.addWidget(restore_defaults_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self._sync_hotkey_controls()
        return panel

    def _build_panel(
        self,
        title_key: str,
        table: QTableWidget,
        buttons: list[QPushButton],
    ) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(13)

        panel_title = QLabel()
        panel_title.setObjectName("PanelTitle")
        self._bind_text(panel_title, title_key)
        layout.addWidget(panel_title)
        layout.addWidget(table, 1)
        if table is self._shelf_table:
            layout.addWidget(self._shelf_empty_label)
        elif table is self._pinned_table:
            layout.addWidget(self._pinned_empty_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        button_row.addStretch(1)
        for button in buttons:
            button_row.addWidget(button)
        layout.addLayout(button_row)

        return panel

    def _build_table(self) -> QTableWidget:
        table = QTableWidget(0, 4)
        self._set_table_headers(table)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSortingEnabled(True)
        table.setShowGrid(False)
        table.setWordWrap(False)
        table.setIconSize(QSize(20, 20))
        table.setCornerButtonEnabled(False)
        table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        table.verticalHeader().setDefaultSectionSize(38)
        table.horizontalHeader().setHighlightSections(False)
        table.horizontalHeader().setMinimumSectionSize(72)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        return table

    def _make_button(
        self,
        text_key: str,
        callback: object,
        *,
        primary: bool = False,
        icon: QStyle.StandardPixmap | None = None,
    ) -> QPushButton:
        button = QPushButton()
        self._bind_text(button, text_key)
        if primary:
            button.setObjectName("PrimaryButton")
        if icon is not None:
            button.setIcon(self.style().standardIcon(icon))
            button.setIconSize(QSize(17, 17))
        button.clicked.connect(callback)  # type: ignore[arg-type]
        return button

    def _make_tool_button(
        self,
        tooltip_key: str,
        callback: object,
        icon: QStyle.StandardPixmap,
    ) -> QToolButton:
        button = QToolButton()
        button.setObjectName("ToolIconButton")
        button.setIcon(self.style().standardIcon(icon))
        button.setIconSize(QSize(18, 18))
        button.setFixedSize(34, 34)
        self._bind_text(button, tooltip_key, "setToolTip")
        self._bind_text(button, tooltip_key, "setAccessibleName")
        button.clicked.connect(callback)  # type: ignore[arg-type]
        return button

    def _make_quick_action_button(
        self,
        text_key: str,
        callback: object,
        icon: QStyle.StandardPixmap,
        tooltip_key: str,
    ) -> QPushButton:
        button = QPushButton()
        button.setObjectName("IconButton")
        button.setIcon(self.style().standardIcon(icon))
        button.setIconSize(QSize(17, 17))
        self._bind_text(button, text_key)
        self._bind_text(button, tooltip_key, "setToolTip")
        button.clicked.connect(callback)  # type: ignore[arg-type]
        return button

    def _show_page(self, page: int) -> None:
        if hasattr(self, "_stack"):
            self._stack.setCurrentIndex(page)
            self._animate_page(self._stack.currentWidget())
            if page == 1 and self._managed_cards_dirty:
                self._populate_managed_cards(self._last_shelf_items)
            if hasattr(self, "_open_windows_refresh_timer"):
                self._configure_open_windows_auto_refresh(
                    self._settings.open_windows_auto_refresh
                )
        if hasattr(self, "_header_title"):
            title_key, subtitle_key = PAGE_COPY_KEYS.get(page, PAGE_COPY_KEYS[0])
            self._header_title.setText(tr(title_key))
            self._header_subtitle.setText(tr(subtitle_key))
        for index, button in enumerate(self._nav_buttons):
            active = index == page
            button.setChecked(active)
            button.setProperty("active", active)
            button.style().unpolish(button)
            button.style().polish(button)

    def _show_settings_page(self, _checked: bool = False) -> None:
        self._show_page(2)

    def _animate_page(self, widget: QWidget | None) -> None:
        if widget is None:
            return
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        self._page_animation = QPropertyAnimation(effect, b"opacity", self)
        self._page_animation.setDuration(120)
        self._page_animation.setStartValue(0.72)
        self._page_animation.setEndValue(1.0)
        self._page_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._page_animation.finished.connect(lambda: widget.setGraphicsEffect(None))
        self._page_animation.start()

    def _focus_active_search(self) -> None:
        search = self._active_search_box()
        if search is not None:
            search.setFocus(Qt.FocusReason.ShortcutFocusReason)
            search.selectAll()

    def _clear_active_search(self) -> None:
        search = self._active_search_box()
        if search is not None and search.text():
            search.clear()

    def _active_search_box(self) -> QLineEdit | None:
        current_page = self._stack.currentIndex()
        if current_page == 0:
            return self._open_windows_search
        if current_page == 1:
            return self._managed_windows_search
        return None

    def _apply_adaptive_layout(self) -> None:
        compact = self.width() < 980
        if self._sidebar is not None:
            self._sidebar.setFixedWidth(218 if compact else 248)
        if self._content_layout is not None:
            if compact:
                self._content_layout.setContentsMargins(18, 18, 18, 14)
                self._content_layout.setSpacing(14)
            else:
                self._content_layout.setContentsMargins(28, 24, 28, 20)
                self._content_layout.setSpacing(20)

    def resizeEvent(self, event: object) -> None:
        self._apply_adaptive_layout()
        super().resizeEvent(event)

    def showEvent(self, event: object) -> None:
        super().showEvent(event)
        self._schedule_initial_refresh()
        self._configure_open_windows_auto_refresh(self._settings.open_windows_auto_refresh)

    def hideEvent(self, event: object) -> None:
        self._configure_open_windows_auto_refresh(False)
        super().hideEvent(event)

    def _schedule_initial_refresh(self) -> None:
        if self._initial_refresh_done or self._initial_refresh_scheduled:
            return
        self._initial_refresh_scheduled = True
        QTimer.singleShot(0, self._run_initial_refresh)

    def _run_initial_refresh(self) -> None:
        self._initial_refresh_scheduled = False
        if self._initial_refresh_done:
            return
        self._initial_refresh_done = True
        self._refresh(reason="startup")

    def _valid_group_id(self, group_id: str) -> str:
        group_ids = {group.id for group in self._shelf_service.groups()}
        if group_id in group_ids:
            return group_id
        return DEFAULT_GROUP_ID

    def _rebuild_group_sidebar(self) -> None:
        self._clear_layout(self._groups_layout)
        self._group_buttons.clear()
        counts = self._shelf_service.group_counts()
        group_windows: dict[str, list[WindowInfo]] = {}
        for item in self._shelf_service.shelved_items():
            group_windows.setdefault(item.group_id, []).append(item.window)
        for group in self._shelf_service.groups():
            count = counts.get(group.id, 0)
            button = GroupButton(group.id, f"{self._group_display_name(group)} ({count})")
            button.setObjectName("GroupButton")
            button.setIcon(self._icon_provider.group_icon(group_windows.get(group.id, [])))
            button.setIconSize(QSize(18, 18))
            button.clicked.connect(
                lambda _checked=False, group_id=group.id: self._select_group(group_id)
            )
            button.windowDropped.connect(self._assign_window_to_group)
            self._group_buttons[group.id] = button
            self._groups_layout.addWidget(button)
        self._groups_layout.addStretch(1)
        self._sync_group_button_state()

    def _sync_group_button_state(self) -> None:
        for group_id, button in self._group_buttons.items():
            active = group_id == self._selected_group_id
            button.setProperty("active", active)
            button.style().unpolish(button)
            button.style().polish(button)

    def _select_group(self, group_id: str) -> None:
        self._selected_group_id = self._valid_group_id(group_id)
        self._settings.selected_group_id = self._selected_group_id
        self._settings_store.save(self._settings, reason="selected group changed")
        self._sync_group_button_state()
        self._populate_managed_cards(self._last_shelf_items)
        self._show_page(1)

    def _create_group(self) -> None:
        name, accepted = QInputDialog.getText(
            self,
            tr("dialog.create_group.title"),
            tr("dialog.create_group.message"),
        )
        if not accepted:
            return
        try:
            group = self._shelf_service.create_group(name)
        except ShelfyGAIError as exc:
            self._show_error(str(exc))
            return
        self._selected_group_id = group.id
        self._persist_managed_state("group created")
        self._refresh()
        self._show_page(1)

    def _rename_selected_group(self) -> None:
        current_group = self._group_by_id(self._selected_group_id)
        if current_group is None:
            return
        name, accepted = QInputDialog.getText(
            self,
            tr("dialog.rename_group.title"),
            tr("dialog.rename_group.message"),
            text=current_group.name,
        )
        if not accepted:
            return
        try:
            self._shelf_service.rename_group(current_group.id, name)
        except ShelfyGAIError as exc:
            self._show_error(str(exc))
            return
        self._persist_managed_state("group renamed")
        self._refresh()

    def _delete_selected_group(self) -> None:
        current_group = self._group_by_id(self._selected_group_id)
        if current_group is None:
            return
        answer = QMessageBox.question(
            self,
            tr("dialog.delete_group.title"),
            tr("dialog.delete_group.message", name=self._group_display_name(current_group)),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._shelf_service.delete_group(current_group.id)
        except ShelfyGAIError as exc:
            self._show_error(str(exc))
            return
        self._selected_group_id = DEFAULT_GROUP_ID
        self._persist_managed_state("group deleted")
        self._refresh()

    def _group_by_id(self, group_id: str) -> WindowGroup | None:
        for group in self._shelf_service.groups():
            if group.id == group_id:
                return group
        return None

    def _assign_window_to_group(self, handle: int, group_id: str) -> None:
        try:
            if self._shelf_service.assign_to_group(handle, group_id):
                self._selected_group_id = group_id
                self._persist_managed_state("window assigned to group")
                self._refresh()
                self.statusBar().showMessage(tr("status.moved_to_group"))
        except ShelfyGAIError as exc:
            self._show_error(str(exc))

    def _set_loading(self, enabled: bool, message: str = "") -> None:
        self._loading_label.setText(message)
        self._loading_label.setVisible(enabled)
        if enabled:
            self.statusBar().showMessage(message)

    def _refresh(self, _checked: bool = False, *, reason: str = "manual") -> None:
        refresh_started = perf_counter()
        self._set_loading(True, tr("status.loading_refreshing"))
        try:
            prune_started = perf_counter()
            pruned_count = self._shelf_service.prune_missing()
            prune_ms = elapsed_ms(prune_started)
            if pruned_count:
                self._persist_managed_state("closed windows pruned")

            available_started = perf_counter()
            available_windows = tuple(self._shelf_service.available_windows())
            available_ms = elapsed_ms(available_started)

            shelf_items = tuple(self._shelf_service.shelved_items())
            self._last_shelf_items = shelf_items
            pinned_items = tuple(self._shelf_service.pinned_items())
            self._last_pinned_items = pinned_items

            populate_started = perf_counter()
            self._populate_available(available_windows)
            self._populate_shelf(self._shelf_table, shelf_items)
            self._populate_pinned(pinned_items)
            if self._stack.currentIndex() == 1:
                self._populate_managed_cards(shelf_items)
            else:
                self._managed_cards_dirty = True
            self._rebuild_group_sidebar()
            populate_ms = elapsed_ms(populate_started)

            available_count = self._available_table.rowCount()
            shelf_count = self._shelf_table.rowCount()
            self.statusBar().showMessage(
                tr(
                    "status.refresh_counts",
                    available=available_count,
                    managed=shelf_count,
                    pinned=len(pinned_items),
                )
            )
            self._sync_tray_actions()
            icon_stats = self._icon_provider.cache_stats()
            log_performance(
                "refresh",
                elapsed_ms=elapsed_ms(refresh_started),
                memory_mb=memory_usage_mb(),
                level=logging.DEBUG if reason == "auto" else logging.INFO,
                reason=reason,
                available_count=available_count,
                managed_count=shelf_count,
                pinned_count=len(pinned_items),
                pruned_count=pruned_count,
                available_ms=f"{available_ms:.1f}",
                prune_ms=f"{prune_ms:.1f}",
                populate_ms=f"{populate_ms:.1f}",
                icon_cache=icon_stats["cached"],
                icon_pending=icon_stats["pending"],
            )
        except ShelfyGAIError as exc:
            LOGGER.exception("Refresh failed")
            self._show_error(str(exc))
        except Exception:
            LOGGER.exception("Unexpected refresh failure")
            self._show_error(tr("error.windows_refresh"))
        finally:
            self._set_loading(False)

    def _populate_available(self, windows: Sequence[WindowInfo]) -> None:
        self._populate_table(self._available_table, windows)
        self._apply_open_windows_filter()

    def _populate_shelf(
        self,
        table: QTableWidget,
        items: Sequence[ShelfItem],
    ) -> None:
        windows = [item.window for item in items]
        self._populate_table(table, windows)
        self._apply_table_icons(table)
        if table is self._shelf_table:
            self._update_table_empty_state(
                table,
                self._shelf_empty_label,
                tr("empty.managed_windows"),
            )

    def _populate_pinned(self, items: Sequence[PinnedItem]) -> None:
        windows = [item.window for item in items]
        self._populate_table(self._pinned_table, windows)
        self._apply_table_icons(self._pinned_table)
        self._update_table_empty_state(
            self._pinned_table,
            self._pinned_empty_label,
            tr("empty.pinned_windows"),
        )
        self._configure_pinned_watcher()

    def _populate_managed_cards(self, items: Sequence[ShelfItem]) -> None:
        self._clear_layout(self._managed_cards_layout)
        grouped: dict[str, list[ShelfItem]] = {}
        query = self._managed_windows_search.text().strip().lower()
        visible_items = [
            item
            for item in items
            if item.group_id == self._selected_group_id and self._managed_item_matches(item, query)
        ]
        self._icon_provider.preload_windows([item.window for item in visible_items])
        for item in visible_items:
            grouped.setdefault(item.window.process_name, []).append(item)

        if not grouped:
            group = self._group_by_id(self._selected_group_id)
            group_name = self._group_display_name(group)
            message = tr(
                "empty.managed_group_search" if query else "empty.managed_group",
                group=group_name,
            )
            empty_label = QLabel(message)
            empty_label.setObjectName("EmptyState")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setWordWrap(True)
            empty_label.setMinimumHeight(96)
            self._managed_cards_layout.addWidget(empty_label)
            self._managed_cards_layout.addStretch(1)
            self._animate_managed_cards()
            self._managed_cards_dirty = False
            return

        for process_name, group_items in sorted(grouped.items(), key=lambda pair: pair[0].lower()):
            self._managed_cards_layout.addWidget(
                self._build_managed_group_card(process_name, group_items)
            )
        self._managed_cards_layout.addStretch(1)
        self._animate_managed_cards()
        self._managed_cards_dirty = False

    def _managed_item_matches(self, item: ShelfItem, query: str) -> bool:
        if not query:
            return True
        window = item.window
        values = (
            window.process_name,
            window.title,
            str(window.process_id),
            f"0x{window.handle:08X}",
        )
        return query in " ".join(values).lower()

    def _build_managed_group_card(self, process_name: str, items: list[ShelfItem]) -> QFrame:
        card = QFrame()
        card.setObjectName("ManagedGroupCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(11)

        first_window = items[0].window
        header = QHBoxLayout()

        icon_label = QLabel()
        icon_label.setObjectName("IconBadge")
        icon_label.setFixedSize(34, 34)
        icon_label.setPixmap(self._icon_pixmap(first_window, 24, icon_label))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_box = QVBoxLayout()
        app_label = QLabel(process_name)
        app_label.setObjectName("CardTitle")
        count_label = QLabel(tr("label.hidden_count", count=len(items)))
        count_label.setObjectName("Muted")
        title_box.addWidget(app_label)
        title_box.addWidget(count_label)

        header.addWidget(icon_label)
        header.addLayout(title_box)
        header.addStretch(1)
        layout.addLayout(header)

        for item in items:
            layout.addWidget(self._build_managed_window_row(item))

        return card

    def _build_managed_window_row(self, item: ShelfItem) -> QWidget:
        row = DraggableManagedWindowRow(item.window.handle)
        row.setObjectName("ManagedWindowRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 11, 0, 0)
        layout.setSpacing(12)

        icon_label = QLabel()
        icon_label.setObjectName("IconBadge")
        icon_label.setFixedSize(30, 30)
        icon_label.setPixmap(self._icon_pixmap(item.window, 20, icon_label))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_box = QVBoxLayout()
        title = QLabel(item.window.title)
        title.setWordWrap(True)
        meta = QLabel(
            tr("label.pid_hwnd", pid=item.window.process_id, hwnd=f"0x{item.window.handle:08X}")
        )
        meta.setObjectName("Muted")
        title_box.addWidget(title)
        title_box.addWidget(meta)

        restore_button = QPushButton()
        restore_button.setText(tr("action.restore"))
        restore_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack))
        restore_button.clicked.connect(
            lambda _checked=False, handle=item.window.handle: self._restore_handles([handle])
        )

        layout.addWidget(icon_label)
        layout.addLayout(title_box, 1)
        layout.addWidget(restore_button)
        return row

    def _icon_for_window(self, window: WindowInfo, *, queue: bool = True) -> QIcon:
        return self._icon_provider.icon_for_window(window, queue=queue)

    def _icon_pixmap(self, window: WindowInfo, size: int, widget: QWidget) -> QPixmap:
        return self._icon_provider.pixmap(self._icon_for_window(window), size, widget)

    def _clear_layout(self, layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _animate_managed_cards(self) -> None:
        effect = QGraphicsOpacityEffect(self._managed_cards_container)
        self._managed_cards_container.setGraphicsEffect(effect)
        self._card_animation = QPropertyAnimation(effect, b"opacity", self)
        self._card_animation.setDuration(140)
        self._card_animation.setStartValue(0.0)
        self._card_animation.setEndValue(1.0)
        self._card_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._card_animation.finished.connect(
            lambda: self._managed_cards_container.setGraphicsEffect(None)
        )
        self._card_animation.start()

    def _populate_table(self, table: QTableWidget, windows: Sequence[WindowInfo]) -> None:
        table.setUpdatesEnabled(False)
        table.setSortingEnabled(False)
        table.setRowCount(len(windows))

        try:
            for row, window in enumerate(windows):
                values = [
                    window.process_name,
                    window.title,
                    str(window.process_id),
                    f"0x{window.handle:08X}",
                ]
                filter_text = " ".join(values).lower()
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setData(HANDLE_ROLE, window.handle)
                    item.setData(EXE_PATH_ROLE, window.executable_path or "")
                    item.setData(FILTER_ROLE, filter_text)
                    item.setToolTip(value)
                    if column == 0:
                        item.setIcon(self._icon_for_window(window, queue=False))
                    if column >= 2:
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                        )
                    table.setItem(row, column, item)
        finally:
            table.setSortingEnabled(True)
            table.setUpdatesEnabled(True)

    def _refresh_cached_icons(self) -> None:
        self._apply_table_icons(self._available_table, visible_only=True)
        self._apply_table_icons(self._shelf_table)
        self._apply_table_icons(self._pinned_table)
        if self._stack.currentIndex() == 1:
            self._populate_managed_cards(self._last_shelf_items)
        else:
            self._managed_cards_dirty = True
        self._rebuild_group_sidebar()

    def _apply_table_icons(self, table: QTableWidget, *, visible_only: bool = False) -> None:
        for row in range(table.rowCount()):
            if visible_only and table.isRowHidden(row):
                continue
            item = table.item(row, 0)
            if item is None:
                continue
            executable_path = item.data(EXE_PATH_ROLE)
            if isinstance(executable_path, str):
                item.setIcon(self._icon_provider.icon_for_executable(executable_path))

    def _apply_open_windows_filter(self) -> None:
        query = self._open_windows_search.text().strip().lower()
        visible_count = 0
        for row in range(self._available_table.rowCount()):
            item = self._available_table.item(row, 0)
            filter_text = item.data(FILTER_ROLE) if item is not None else ""
            if not isinstance(filter_text, str):
                filter_text = ""
            should_hide = bool(query) and query not in filter_text
            self._available_table.setRowHidden(row, should_hide)
            if not should_hide:
                visible_count += 1
        self._apply_table_icons(self._available_table, visible_only=True)
        empty_text = tr("empty.open_windows_search" if query else "empty.open_windows")
        self._update_table_empty_state(
            self._available_table,
            self._open_windows_empty_label,
            empty_text,
            visible_count=visible_count,
        )

    def _update_table_empty_state(
        self,
        table: QTableWidget,
        label: QLabel,
        message: str,
        *,
        visible_count: int | None = None,
    ) -> None:
        label.setText(message)
        if visible_count is None:
            visible_count = self._visible_row_count(table)
        label.setVisible(visible_count == 0)

    def _visible_row_count(self, table: QTableWidget) -> int:
        return sum(1 for row in range(table.rowCount()) if not table.isRowHidden(row))

    def _set_open_windows_auto_refresh(self, enabled: bool) -> None:
        if self._settings_controls_syncing:
            return
        self._settings.open_windows_auto_refresh = enabled
        self._save_runtime_settings("open windows auto-refresh changed")
        self._configure_open_windows_auto_refresh(enabled)
        state_key = (
            "status.open_auto_refresh.enabled"
            if enabled
            else "status.open_auto_refresh.disabled"
        )
        self.statusBar().showMessage(
            tr("status.open_auto_refresh", state=tr(state_key))
        )

    def _set_focus_restored_windows(self, enabled: bool) -> None:
        if self._settings_controls_syncing:
            return
        self._settings.focus_restored_windows = enabled
        self._save_runtime_settings("focus restored windows changed")

    def _set_restore_windows_on_exit(self, enabled: bool) -> None:
        if self._settings_controls_syncing:
            return
        self._settings.restore_windows_on_exit = enabled
        self._save_runtime_settings("restore windows on exit changed")

    def _set_restore_pinned_windows_on_exit(self, enabled: bool) -> None:
        if self._settings_controls_syncing:
            return
        self._settings.restore_pinned_windows_on_exit = enabled
        self._save_runtime_settings("restore pinned windows on exit changed")

    def _set_confirm_before_hiding(self, enabled: bool) -> None:
        if self._settings_controls_syncing:
            return
        self._settings.confirm_before_hiding = enabled
        self._save_runtime_settings("confirm before hiding changed")

    def _set_confirm_quit_with_hidden_windows(self, enabled: bool) -> None:
        if self._settings_controls_syncing:
            return
        self._settings.confirm_quit_with_hidden_windows = enabled
        self._save_runtime_settings("confirm quit with hidden windows changed")

    def _set_prevent_minimize_watcher(self, enabled: bool) -> None:
        if self._settings_controls_syncing:
            return
        self._settings.prevent_minimize_watcher_enabled = enabled
        self._save_runtime_settings("prevent-minimize watcher changed")
        self._configure_pinned_watcher()

    def _set_allow_pin_self(self, enabled: bool) -> None:
        if self._settings_controls_syncing:
            return
        self._settings.allow_pin_shelfygai_window = enabled
        self._save_runtime_settings("allow pin ShelfyGAI changed")

    def _set_pinned_watcher_interval(self, value: int) -> None:
        if self._settings_controls_syncing:
            return
        self._settings.pinned_watcher_interval_ms = value
        self._save_runtime_settings("pinned watcher interval changed")
        self._configure_pinned_watcher()

    def _set_minimize_to_tray_on_close(self, enabled: bool) -> None:
        if self._settings_controls_syncing:
            return
        self._settings.minimize_to_tray_on_close = enabled
        self._save_runtime_settings("minimize to tray changed")

    def _set_startup_notification(self, enabled: bool) -> None:
        if self._settings_controls_syncing:
            return
        self._settings.startup_notification_enabled = enabled
        self._save_runtime_settings("startup notification changed")

    def _set_debug_mode(self, enabled: bool) -> None:
        if self._settings_controls_syncing:
            return
        self._settings.debug_mode = enabled
        AppLogger().set_debug_mode(enabled)
        self._save_runtime_settings("debug mode changed")

    def _set_language_from_settings(self) -> None:
        if self._settings_controls_syncing:
            return
        language = self._settings_language_combo.currentData()
        if not isinstance(language, str):
            return
        self._settings.language = set_language(language)
        self._save_runtime_settings("language changed")
        self._retranslate()

    def _set_theme_from_settings(self) -> None:
        if self._settings_controls_syncing:
            return
        theme = self._settings_theme_combo.currentData()
        if not isinstance(theme, str):
            return
        self._settings.theme = theme
        self._apply_current_theme()
        self._save_runtime_settings("theme changed")

    def _set_accent_from_settings(self, color: str) -> None:
        if self._settings_controls_syncing:
            return
        self._settings.accent_color = color
        self._sync_settings_accent_buttons()
        self._apply_current_theme()
        self._save_runtime_settings("accent color changed")

    def _set_launch_with_windows(self, enabled: bool) -> None:
        if self._settings_controls_syncing:
            return
        if sys.platform != "win32":
            self._settings.launch_with_windows = False
            self._sync_settings_controls()
            return

        try:
            from shelfygai.platform.windows.startup import set_launch_with_windows_enabled

            set_launch_with_windows_enabled(enabled, silent_startup=self._settings.silent_startup)
        except OSError as exc:
            LOGGER.exception("Could not update launch-with-Windows setting")
            self._show_error(tr("error.save_settings_detail", error=exc))
            self._sync_settings_controls()
            return

        self._settings.launch_with_windows = enabled
        self._save_runtime_settings("launch with Windows changed")
        self._refresh_startup_status_label()

    def _apply_current_theme(self) -> None:
        qt_app = QApplication.instance()
        if qt_app is not None:
            apply_theme(qt_app, self._settings.theme, self._settings.accent_color)

    def _refresh_startup_status_label(self) -> None:
        if sys.platform != "win32":
            self._launch_with_windows_checkbox.setEnabled(False)
            self._startup_status_label.setText(tr("startup.status.read_error"))
            return

        from shelfygai.platform.windows.startup import get_startup_status

        try:
            status = get_startup_status()
        except OSError:
            self._launch_with_windows_checkbox.setEnabled(False)
            self._startup_status_label.setText(tr("startup.status.read_error"))
            return

        self._launch_with_windows_checkbox.setEnabled(True)
        self._settings.launch_with_windows = status.enabled and status.path_valid
        self._settings.silent_startup = status.silent_startup
        self._startup_status_label.setText(_startup_status_text(status))

    def _configure_open_windows_auto_refresh(self, enabled: bool) -> None:
        if enabled and self._should_run_open_windows_auto_refresh():
            self._open_windows_refresh_timer.start()
        else:
            self._open_windows_refresh_timer.stop()

    def _should_run_open_windows_auto_refresh(self) -> bool:
        return (
            self._settings.open_windows_auto_refresh
            and self.isVisible()
            and self._stack.currentIndex() == 0
        )

    def _configure_pinned_watcher(self) -> None:
        interval = max(100, min(self._settings.pinned_watcher_interval_ms, 10_000))
        self._pinned_watcher_timer.setInterval(interval)
        should_run = (
            self._settings.prevent_minimize_watcher_enabled
            and self._shelf_service.has_pinned_windows()
        )
        if should_run:
            self._pinned_watcher_timer.start()
        else:
            self._pinned_watcher_timer.stop()

    def _check_pinned_windows(self) -> None:
        try:
            restored, removed = self._shelf_service.enforce_pinned_windows()
        except Exception:
            LOGGER.exception("Pinned-window watcher failed")
            self.statusBar().showMessage(tr("error.pinned_watcher"))
            return
        if removed:
            self._refresh(reason="pinned watcher")
            self.statusBar().showMessage(tr("status.pinned_removed_closed", count=removed))
        elif restored:
            self.statusBar().showMessage(tr("status.pinned_restored", count=restored))
        self._configure_pinned_watcher()

    def _selected_handles(self, table: QTableWidget) -> list[int]:
        handles = set()
        for item in table.selectedItems():
            handle = item.data(HANDLE_ROLE)
            if isinstance(handle, int):
                handles.add(handle)
        return sorted(handles)

    def _context_handles(self, table: QTableWidget, position: QPoint) -> list[int]:
        row = table.rowAt(position.y())
        if row >= 0 and not table.selectionModel().isRowSelected(row):
            table.clearSelection()
            table.selectRow(row)
        return self._selected_handles(table)

    def _show_window_context_menu(self, table: QTableWidget, position: QPoint) -> None:
        handles = self._context_handles(table, position)
        if not handles:
            return

        menu = QMenu(self)
        if table is self._available_table:
            pin_action = menu.addAction(
                self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp),
                tr("action.pin_window"),
            )
            pin_action.triggered.connect(lambda _checked=False: self._pin_handles(handles))
            prevent_action = menu.addAction(tr("action.prevent_minimize"))
            prevent_action.triggered.connect(
                lambda _checked=False: self._pin_handles(handles, prevent_minimize=True)
            )
            menu.addSeparator()
            bring_action = menu.addAction(tr("action.bring_to_front"))
            bring_action.triggered.connect(
                lambda _checked=False: self._bring_handles_forward(handles)
            )
            hide_action = menu.addAction(tr("action.hide_selected"))
            hide_action.triggered.connect(
                lambda _checked=False: self._shelve_handles(
                    handles,
                    confirm=self._confirm_checkbox.isChecked(),
                )
            )
        elif table is self._pinned_table:
            unpin_action = menu.addAction(tr("action.unpin_window"))
            unpin_action.triggered.connect(lambda _checked=False: self._unpin_handles(handles))
            prevent_action = menu.addAction(tr("action.prevent_minimize"))
            prevent_action.triggered.connect(
                lambda _checked=False: self._set_prevent_minimize_for_handles(handles, True)
            )
            allow_action = menu.addAction(tr("action.allow_minimize"))
            allow_action.triggered.connect(
                lambda _checked=False: self._set_prevent_minimize_for_handles(handles, False)
            )
            menu.addSeparator()
            bring_action = menu.addAction(tr("action.bring_to_front"))
            bring_action.triggered.connect(
                lambda _checked=False: self._bring_handles_forward(handles)
            )
        elif table is self._shelf_table:
            restore_action = menu.addAction(tr("action.restore_selected"))
            restore_action.triggered.connect(
                lambda _checked=False: self._restore_handles(handles)
            )
            bring_action = menu.addAction(tr("action.bring_to_front"))
            bring_action.triggered.connect(
                lambda _checked=False: self._bring_handles_forward(handles)
            )

        if menu.actions():
            menu.exec(table.viewport().mapToGlobal(position))

    def _pin_selected(self) -> None:
        handles = self._selected_handles(self._available_table)
        if not handles:
            self.statusBar().showMessage(tr("status.select_open_pin"))
            return
        self._pin_handles(handles)

    def _pin_handles(self, handles: list[int], *, prevent_minimize: bool = False) -> int:
        if not handles:
            return 0

        self._set_loading(True, tr("status.loading_pinning"))
        pinned_count = 0
        try:
            for handle in handles:
                self._shelf_service.pin(
                    handle,
                    prevent_minimize=prevent_minimize,
                    allow_own_window=self._settings.allow_pin_shelfygai_window,
                )
                pinned_count += 1
            self._refresh(reason="windows pinned")
            self.statusBar().showMessage(tr("status.pinned_count", count=pinned_count))
            self._tray_notify(
                tr("tray.notification.pinned.title"),
                tr("tray.notification.pinned.message", count=pinned_count),
            )
            return pinned_count
        except ShelfyGAIError as exc:
            LOGGER.exception("Pin failed")
            if pinned_count:
                self._refresh(reason="partial pin failure")
            self._show_error(str(exc))
        except Exception:
            LOGGER.exception("Unexpected pin failure")
            if pinned_count:
                self._refresh(reason="partial pin failure")
            self._show_error(tr("error.pin"))
        finally:
            self._set_loading(False)
        return pinned_count

    def _unpin_selected(self) -> None:
        handles = self._selected_handles(self._pinned_table)
        if not handles:
            self.statusBar().showMessage(tr("status.select_pinned_unpin"))
            return
        self._unpin_handles(handles)

    def _unpin_handles(self, handles: list[int]) -> tuple[int, int]:
        if not handles:
            return 0, 0

        self._set_loading(True, tr("status.loading_unpinning"))
        unpinned = 0
        skipped = 0
        try:
            for handle in handles:
                if self._shelf_service.unpin(handle):
                    unpinned += 1
                else:
                    skipped += 1
            self._refresh(reason="windows unpinned")
            self.statusBar().showMessage(self._unpin_summary(unpinned, skipped))
            self._tray_notify(
                tr("tray.notification.unpinned.title"),
                self._unpin_summary(unpinned, skipped),
            )
        except ShelfyGAIError as exc:
            LOGGER.exception("Unpin failed")
            if unpinned or skipped:
                self._refresh(reason="partial unpin failure")
            self._show_error(str(exc))
        except Exception:
            LOGGER.exception("Unexpected unpin failure")
            if unpinned or skipped:
                self._refresh(reason="partial unpin failure")
            self._show_error(tr("error.unpin"))
        finally:
            self._set_loading(False)
        return unpinned, skipped

    def _set_prevent_minimize_for_handles(self, handles: list[int], enabled: bool) -> None:
        if not handles:
            return

        updated = 0
        try:
            pinned_handles = {item.window.handle for item in self._shelf_service.pinned_items()}
            for handle in handles:
                if handle not in pinned_handles:
                    if enabled:
                        self._shelf_service.pin(
                            handle,
                            prevent_minimize=True,
                            allow_own_window=self._settings.allow_pin_shelfygai_window,
                        )
                        updated += 1
                        pinned_handles.add(handle)
                    continue
                if self._shelf_service.set_prevent_minimize(handle, enabled):
                    updated += 1
            self._refresh(reason="pinned prevent-minimize changed")
            status_key = (
                "status.prevent_minimize_enabled"
                if enabled
                else "status.prevent_minimize_disabled"
            )
            self.statusBar().showMessage(tr(status_key, count=updated))
        except ShelfyGAIError as exc:
            LOGGER.exception("Prevent-minimize update failed")
            self._show_error(str(exc))
        except Exception:
            LOGGER.exception("Unexpected prevent-minimize update failure")
            self._show_error(tr("error.prevent_minimize"))

    def _shelve_selected(self) -> None:
        handles = self._selected_handles(self._available_table)
        if not handles:
            self.statusBar().showMessage(tr("status.select_open_hide"))
            return
        self._shelve_handles(handles, confirm=self._confirm_checkbox.isChecked())

    def _shelve_handles(
        self,
        handles: list[int],
        *,
        confirm: bool = True,
        reason: str = "windows hidden",
    ) -> int:
        if not handles:
            return 0

        if confirm:
            answer = QMessageBox.question(
                self,
                tr("dialog.hide_windows.title"),
                tr("dialog.hide_windows.message", count=len(handles)),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return 0

        self._set_loading(True, tr("status.loading_hiding"))
        hidden_count = 0
        try:
            for handle in handles:
                self._shelf_service.shelve(handle, group_id=self._selected_group_id)
                hidden_count += 1
                self._sync_recovery_state("window hidden")
            self._persist_managed_state(reason)
            self._refresh()
            self.statusBar().showMessage(
                tr("status.hidden_count", count=hidden_count)
            )
            self._tray_notify(
                tr("tray.notification.hidden.title"),
                tr("tray.notification.hidden.message", count=hidden_count),
            )
            return hidden_count
        except ShelfyGAIError as exc:
            LOGGER.exception("Shelve failed")
            if hidden_count:
                self._persist_managed_state("partial hide failure")
            self._show_error(str(exc))
        except Exception:
            LOGGER.exception("Unexpected shelve failure")
            if hidden_count:
                self._persist_managed_state("partial hide failure")
            self._show_error(tr("error.shelve"))
        finally:
            self._set_loading(False)
        return 0

    def _quick_hide_from_hotkey(self) -> None:
        handles = self._selected_handles(self._available_table) if self.isActiveWindow() else []
        if handles:
            self._shelve_handles(handles, confirm=False, reason="windows hidden by hotkey")
            return

        try:
            item = self._shelf_service.shelve_foreground(group_id=self._selected_group_id)
            self._sync_recovery_state("foreground window hidden by hotkey")
            self._persist_managed_state("foreground window hidden by hotkey")
            self._refresh()
            self.statusBar().showMessage(tr("status.hidden_title", title=item.window.title))
            self._tray_notify(
                tr("tray.notification.window_hidden.title"),
                tr("tray.notification.window_hidden.message", title=item.window.title),
            )
        except ShelfyGAIError as exc:
            LOGGER.info("Global quick-hide hotkey did not hide a window: %s", exc)
            self._sync_recovery_state("quick-hide hotkey failed")
            self.statusBar().showMessage(str(exc))
        except Exception:
            LOGGER.exception("Unexpected global quick-hide failure")
            self._sync_recovery_state("quick-hide hotkey failed")
            self._show_error(tr("error.foreground_hide"))

    def _restore_last_from_hotkey(self) -> None:
        try:
            restored = self._shelf_service.restore_last(
                focus=self._settings.focus_restored_windows
            )
            self._persist_managed_state("last window restored by hotkey")
            self._refresh()
            if restored:
                self.statusBar().showMessage(tr("status.last_restored"))
                self._tray_notify(
                    tr("tray.notification.window_restored.title"),
                    tr("tray.notification.window_restored.message"),
                )
            else:
                self.statusBar().showMessage(tr("status.no_managed_restore"))
        except ShelfyGAIError as exc:
            LOGGER.exception("Restore-last hotkey failed")
            self._show_error(str(exc))
        except Exception:
            LOGGER.exception("Unexpected restore-last hotkey failure")
            self._show_error(tr("error.restore_last"))

    def _toggle_visibility_from_hotkey(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide()
            self.statusBar().showMessage(tr("status.hidden_app"))
            LOGGER.info("Main window hidden by global hotkey")
        else:
            self._show_from_tray()
            self.statusBar().showMessage(tr("status.shown"))
            LOGGER.info("Main window shown by global hotkey")

    def _restore_selected(self, table: QTableWidget) -> None:
        handles = self._selected_handles(table)
        self._restore_handles(handles)

    def _restore_handles(self, handles: list[int]) -> None:
        if not handles:
            self.statusBar().showMessage(tr("status.select_managed_restore"))
            return

        self._set_loading(True, tr("status.loading_restoring"))
        try:
            restored = 0
            skipped = 0
            for handle in handles:
                if self._shelf_service.restore(
                    handle,
                    focus=self._settings.focus_restored_windows,
                ):
                    restored += 1
                else:
                    skipped += 1
            self._persist_managed_state("windows restored")
            self._refresh()
            self.statusBar().showMessage(self._restore_summary(restored, skipped))
            self._tray_notify(
                tr("tray.notification.restore.title"),
                self._restore_summary(restored, skipped),
            )
        except ShelfyGAIError as exc:
            LOGGER.exception("Restore failed")
            self._persist_managed_state("restore failure state sync")
            self._show_error(str(exc))
        except Exception:
            LOGGER.exception("Unexpected restore failure")
            self._persist_managed_state("restore failure state sync")
            self._show_error(tr("error.restore"))
        finally:
            self._set_loading(False)

    def _restore_all(self) -> None:
        managed_count = len(self._shelf_service.shelved_items())
        if managed_count == 0:
            self.statusBar().showMessage(tr("status.no_managed_restore"))
            return
        if managed_count > 1:
            answer = QMessageBox.question(
                self,
                tr("dialog.restore_all.title"),
                tr("dialog.restore_all.message", count=managed_count),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self._set_loading(True, tr("status.loading_restoring"))
        try:
            restored, skipped = self._shelf_service.restore_all(
                focus=self._settings.focus_restored_windows
            )
            self._persist_managed_state("all windows restored")
            self._refresh()
            self.statusBar().showMessage(self._restore_summary(restored, skipped))
            self._tray_notify(
                tr("tray.notification.restore.title"),
                self._restore_summary(restored, skipped),
            )
        except ShelfyGAIError as exc:
            LOGGER.exception("Restore-all failed")
            self._persist_managed_state("restore-all failure state sync")
            self._show_error(str(exc))
        except Exception:
            LOGGER.exception("Unexpected restore-all failure")
            self._persist_managed_state("restore-all failure state sync")
            self._show_error(tr("error.restore_all"))
        finally:
            self._set_loading(False)

    def _bring_selected_forward(self, table: QTableWidget | None = None) -> None:
        handles = self._selected_handles(table or self._available_table)
        if not handles:
            self.statusBar().showMessage(tr("status.select_open_forward"))
            return

        self._bring_handles_forward(handles)

    def _bring_handles_forward(self, handles: list[int]) -> None:
        if not handles:
            self.statusBar().showMessage(tr("status.select_open_forward"))
            return

        try:
            self._shelf_service.bring_to_front(handles[0])
            self.statusBar().showMessage(tr("status.foreground_activation"))
        except ShelfyGAIError as exc:
            LOGGER.exception("Foreground activation failed")
            self._show_error(str(exc))
        except Exception:
            LOGGER.exception("Unexpected foreground failure")
            self._show_error(tr("error.bring_forward"))

    def _show_error(self, message: str) -> None:
        self.statusBar().showMessage(message)
        self._tray_notify(
            tr("error.notification.title"),
            message,
            icon=QSystemTrayIcon.MessageIcon.Warning,
            duration_ms=6_000,
        )
        QMessageBox.warning(self, APP_NAME, message)

    def _open_github(self) -> None:
        QDesktopServices.openUrl(QUrl(GITHUB_REPOSITORY_URL))

    def _check_for_updates(self) -> None:
        self._set_loading(True, tr("status.loading_checking"))
        try:
            result = self._update_service.check_for_updates()
            details = tr("about.update.placeholder_result")
            if result.checked_url:
                details = tr(
                    "update.future_endpoint",
                    message=details,
                    url=result.checked_url,
                )
            self._update_status_label.setText(details)
            self.statusBar().showMessage(tr("status.update_check_complete"))
            LOGGER.info("Update check placeholder result: status=%s", result.status)
        except Exception:
            LOGGER.exception("Update check placeholder failed")
            self._update_status_label.setText(tr("error.update_check"))
            self.statusBar().showMessage(tr("status.update_check_failed"))
        finally:
            self._set_loading(False)

    def show_startup_notification(self) -> None:
        if self._settings.startup_notification_enabled:
            self._tray_notify(
                tr("tray.notification.startup.title"),
                tr("tray.notification.startup.message"),
            )

    def start_hidden_in_tray(self) -> bool:
        if not self._tray_available():
            LOGGER.warning("Silent startup requested, but the system tray is unavailable")
            return False
        self.hide()
        LOGGER.info("Silent startup: main window hidden to tray")
        return True

    def _show_from_tray(self) -> None:
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()
        LOGGER.debug("Main window opened from tray")

    def _open_settings_from_tray(self) -> None:
        self._show_from_tray()
        self._show_settings_page()

    def _quit_from_tray(self) -> None:
        LOGGER.info("Quit requested from tray")
        self._is_quitting = True
        if not self._cleanup_before_exit():
            self._is_quitting = False
            return

        self._cleanup_global_hotkeys()
        self._hide_tray_icon()
        qt_app = QApplication.instance()
        if qt_app is not None:
            qt_app.quit()
        else:
            self.close()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            self._show_from_tray()

    def _tray_available(self) -> bool:
        return self._tray_icon is not None and self._tray_icon.isVisible()

    def _tray_notify(
        self,
        title: str,
        message: str,
        *,
        icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information,
        duration_ms: int = 4_000,
    ) -> None:
        if not self._tray_available() or not QSystemTrayIcon.supportsMessages():
            return
        self._tray_icon.showMessage(
            title,
            message,
            icon,
            duration_ms,
        )

    def _restore_summary(self, restored: int, skipped: int) -> str:
        if skipped:
            return tr("status.all_restored_skipped", restored=restored, skipped=skipped)
        return tr("status.all_restored", restored=restored)

    def _unpin_summary(self, unpinned: int, skipped: int) -> str:
        if skipped:
            return tr("status.unpinned_skipped", unpinned=unpinned, skipped=skipped)
        return tr("status.unpinned_count", count=unpinned)

    def _sync_tray_actions(self) -> None:
        if self._tray_restore_all_action is not None:
            self._tray_restore_all_action.setEnabled(self._shelf_service.has_shelved_windows())

    def _hide_tray_icon(self) -> None:
        if self._tray_icon is not None:
            self._tray_icon.hide()

    def _configure_global_hotkeys(self) -> None:
        if sys.platform != "win32":
            self._hotkey_status_label.setText(tr("hotkey.windows_only"))
            return

        qt_app = QApplication.instance()
        if qt_app is not None and qt_app.platformName().lower() == "offscreen":
            self._hotkey_status_label.setText(tr("hotkey.disabled_offscreen"))
            return

        try:
            from shelfygai.platform.windows.hotkeys import GlobalHotkeyManager
        except Exception:
            LOGGER.exception("Could not initialize global hotkey support")
            self._hotkey_status_label.setText(tr("error.hotkey_init"))
            return

        if self._hotkey_manager is None:
            self._hotkey_manager = GlobalHotkeyManager(self)
            self._hotkey_manager.activated.connect(self._handle_global_hotkey)
            self._hotkey_manager.registrationFailed.connect(self._on_hotkey_registration_failed)
            self._hotkey_manager.registrationChanged.connect(self._on_hotkey_registration_changed)

        self._hotkey_registration_errors = []
        self._hotkey_manager.register_hotkeys(self._settings.global_hotkeys)

    def _cleanup_global_hotkeys(self) -> None:
        if self._hotkey_manager is not None:
            self._hotkey_manager.unregister_all()

    def _on_hotkey_registration_failed(self, action_id: str, message: str) -> None:
        label = self._hotkey_label(action_id)
        self._hotkey_registration_errors.append(f"{label}: {message}")
        self._hotkey_status_label.setText("; ".join(self._hotkey_registration_errors))

    def _on_hotkey_registration_changed(self, summary: str) -> None:
        if self._hotkey_registration_errors:
            self._hotkey_status_label.setText("; ".join(self._hotkey_registration_errors))
        else:
            count = getattr(self._hotkey_manager, "registered_count", lambda: None)()
            if isinstance(count, int):
                self._hotkey_status_label.setText(tr("hotkey.status.count", count=count))
            else:
                self._hotkey_status_label.setText(summary)

    def _handle_global_hotkey(self, action_id: str) -> None:
        if action_id == HOTKEY_QUICK_HIDE:
            self._quick_hide_from_hotkey()
        elif action_id == HOTKEY_RESTORE_LAST:
            self._restore_last_from_hotkey()
        elif action_id == HOTKEY_TOGGLE_VISIBILITY:
            self._toggle_visibility_from_hotkey()

    def _open_settings_dialog(self) -> None:
        self._save_settings()
        dialog = SettingsDialog(self._settings_store, self._settings, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._settings = dialog.settings
            set_language(self._settings.language)
            AppLogger().set_debug_mode(self._settings.debug_mode)
            self._sync_settings_controls()
            self._retranslate()
            self._configure_global_hotkeys()
            self._configure_pinned_watcher()
            self._sync_tray_actions()
            self.statusBar().showMessage(tr("status.settings_saved"))

    def _sync_settings_controls(self) -> None:
        self._settings_controls_syncing = True
        try:
            self._refresh_settings_choice_labels()
            self._refresh_startup_status_label()
            self._settings_language_combo.setCurrentIndex(
                max(self._settings_language_combo.findData(self._settings.language), 0)
            )
            self._settings_theme_combo.setCurrentIndex(
                max(self._settings_theme_combo.findData(self._settings.theme), 0)
            )
            self._open_windows_auto_refresh_checkbox.setChecked(
                self._settings.open_windows_auto_refresh
            )
            self._restore_on_exit_checkbox.setChecked(self._settings.restore_windows_on_exit)
            self._restore_pinned_on_exit_checkbox.setChecked(
                self._settings.restore_pinned_windows_on_exit
            )
            self._focus_restored_checkbox.setChecked(self._settings.focus_restored_windows)
            self._confirm_checkbox.setChecked(self._settings.confirm_before_hiding)
            self._confirm_quit_checkbox.setChecked(
                self._settings.confirm_quit_with_hidden_windows
            )
            self._prevent_minimize_watcher_checkbox.setChecked(
                self._settings.prevent_minimize_watcher_enabled
            )
            self._allow_pin_self_checkbox.setChecked(self._settings.allow_pin_shelfygai_window)
            self._pinned_watcher_interval_spin.setValue(
                self._settings.pinned_watcher_interval_ms
            )
            self._launch_with_windows_checkbox.setChecked(self._settings.launch_with_windows)
            self._minimize_to_tray_checkbox.setChecked(
                self._settings.minimize_to_tray_on_close
            )
            self._startup_notification_checkbox.setChecked(
                self._settings.startup_notification_enabled
            )
            self._debug_mode_checkbox.setChecked(self._settings.debug_mode)
            self._sync_settings_accent_buttons()
        finally:
            self._settings_controls_syncing = False
        self._sync_hotkey_controls()

    def _sync_hotkey_controls(self) -> None:
        if not self._hotkey_sequence_edits:
            return
        self._syncing_hotkey_controls = True
        try:
            for action_id, edit in self._hotkey_sequence_edits.items():
                config = self._settings.global_hotkeys.get(
                    action_id,
                    DEFAULT_GLOBAL_HOTKEYS[action_id],
                )
                checkbox = self._hotkey_enabled_checkboxes[action_id]
                checkbox.setChecked(bool(config.get("enabled", False)))
                edit.setKeySequence(QKeySequence(str(config.get("sequence", ""))))
        finally:
            self._syncing_hotkey_controls = False

    def _save_hotkey_settings(self, *_args: object) -> None:
        if self._syncing_hotkey_controls:
            return
        self._apply_hotkey_controls_to_settings()
        self._settings_store.save(self._settings, reason="global hotkeys changed")
        self._configure_global_hotkeys()

    def _apply_hotkey_controls_to_settings(self) -> None:
        if not self._hotkey_sequence_edits:
            return
        hotkeys = {}
        for action_id, edit in self._hotkey_sequence_edits.items():
            sequence = edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
            checkbox = self._hotkey_enabled_checkboxes[action_id]
            enabled = checkbox.isChecked() and bool(sequence.strip())
            if checkbox.isChecked() != enabled:
                self._syncing_hotkey_controls = True
                checkbox.setChecked(enabled)
                self._syncing_hotkey_controls = False
            hotkeys[action_id] = {
                "enabled": enabled,
                "sequence": sequence.strip(),
            }
        self._settings.global_hotkeys = hotkeys

    def _clear_hotkey(self, action_id: str) -> None:
        edit = self._hotkey_sequence_edits[action_id]
        checkbox = self._hotkey_enabled_checkboxes[action_id]
        self._syncing_hotkey_controls = True
        edit.clear()
        checkbox.setChecked(False)
        self._syncing_hotkey_controls = False
        self._save_hotkey_settings()

    def _restore_default_hotkeys(self) -> None:
        self._settings.global_hotkeys = {
            action_id: dict(config)
            for action_id, config in DEFAULT_GLOBAL_HOTKEYS.items()
        }
        self._sync_hotkey_controls()
        self._settings_store.save(self._settings, reason="global hotkeys reset")
        self._configure_global_hotkeys()

    def _sync_settings_from_controls(self) -> None:
        language = self._settings_language_combo.currentData()
        theme = self._settings_theme_combo.currentData()
        if isinstance(language, str):
            self._settings.language = language
        if isinstance(theme, str):
            self._settings.theme = theme
        for color, button in self._settings_accent_buttons.items():
            if button.isChecked():
                self._settings.accent_color = color
                break
        self._settings.open_windows_auto_refresh = (
            self._open_windows_auto_refresh_checkbox.isChecked()
        )
        self._settings.restore_windows_on_exit = self._restore_on_exit_checkbox.isChecked()
        self._settings.restore_pinned_windows_on_exit = (
            self._restore_pinned_on_exit_checkbox.isChecked()
        )
        self._settings.focus_restored_windows = self._focus_restored_checkbox.isChecked()
        self._settings.confirm_before_hiding = self._confirm_checkbox.isChecked()
        self._settings.confirm_quit_with_hidden_windows = (
            self._confirm_quit_checkbox.isChecked()
        )
        self._settings.prevent_minimize_watcher_enabled = (
            self._prevent_minimize_watcher_checkbox.isChecked()
        )
        self._settings.allow_pin_shelfygai_window = self._allow_pin_self_checkbox.isChecked()
        self._settings.pinned_watcher_interval_ms = self._pinned_watcher_interval_spin.value()
        self._settings.launch_with_windows = self._launch_with_windows_checkbox.isChecked()
        self._settings.minimize_to_tray_on_close = (
            self._minimize_to_tray_checkbox.isChecked()
        )
        self._settings.startup_notification_enabled = (
            self._startup_notification_checkbox.isChecked()
        )
        self._settings.debug_mode = self._debug_mode_checkbox.isChecked()

    def _save_runtime_settings(self, reason: str) -> None:
        self._apply_hotkey_controls_to_settings()
        self._sync_settings_from_controls()
        self._apply_runtime_state_to_settings()
        if self._settings_store.save(self._settings, reason=reason):
            self._sync_recovery_state(reason)
        else:
            self._show_error(tr("error.save_settings"))

    def _restore_settings(self) -> None:
        if self._settings.window_geometry:
            geometry = QByteArray.fromBase64(self._settings.window_geometry.encode("ascii"))
            self.restoreGeometry(geometry)

    def _save_settings(self) -> None:
        self._apply_hotkey_controls_to_settings()
        self._sync_settings_from_controls()
        self._settings.window_geometry = bytes(self.saveGeometry().toBase64()).decode("ascii")
        self._apply_runtime_state_to_settings()
        self._settings_store.save(self._settings)
        self._sync_recovery_state("settings saved")

    def closeEvent(self, event: QCloseEvent) -> None:
        if (
            self._settings.minimize_to_tray_on_close
            and not self._is_quitting
            and self._tray_available()
        ):
            self._save_settings()
            event.ignore()
            self.hide()
            LOGGER.info("Main window minimized to tray")
            if not self._tray_hint_shown:
                self._tray_notify(
                    tr("tray.notification.still_running.title"),
                    tr("tray.notification.still_running.message"),
                )
                self._tray_hint_shown = True
            return

        self._is_quitting = True
        if self._cleanup_before_exit():
            self._cleanup_global_hotkeys()
            self._hide_tray_icon()
            event.accept()
        else:
            self._is_quitting = False
            event.ignore()

    def _cleanup_before_exit(self) -> bool:
        self._save_settings()
        if self._settings.restore_pinned_windows_on_exit:
            self._restore_pinned_for_exit()
        if not self._shelf_service.has_shelved_windows():
            self._recovery_store.clear(reason="normal exit")
            return True

        if (
            not self._settings.restore_windows_on_exit
            and self._settings.confirm_quit_with_hidden_windows
        ):
            answer = QMessageBox.question(
                self,
                tr("dialog.restore_before_exit.title"),
                tr("dialog.restore_before_exit.message"),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False

        try:
            restored, skipped = self._shelf_service.restore_all(focus=False)
        except ShelfyGAIError as exc:
            LOGGER.exception("Restore on exit failed")
            self._show_error(tr("error.restore_exit_detail", error=exc))
            return False
        except Exception:
            LOGGER.exception("Unexpected restore on exit failure")
            self._show_error(tr("error.restore_exit"))
            return False

        self._persist_managed_state("normal exit restore")
        if self._shelf_service.has_shelved_windows():
            LOGGER.error(
                "Normal exit blocked because managed windows remain after restore: "
                "restored=%s skipped=%s remaining=%s",
                restored,
                skipped,
                len(self._shelf_service.shelved_items()),
            )
            self._show_error(tr("error.restore_exit"))
            return False

        self._recovery_store.clear(reason="normal exit")
        LOGGER.info(
            "Normal exit restore completed: restored=%s skipped=%s",
            restored,
            skipped,
        )
        return True

    def _restore_pinned_for_exit(self) -> None:
        if not self._shelf_service.has_pinned_windows():
            return
        try:
            unpinned, skipped = self._shelf_service.unpin_all()
            LOGGER.info(
                "Pinned-window exit cleanup completed: unpinned=%s skipped=%s",
                unpinned,
                skipped,
            )
            self._configure_pinned_watcher()
        except Exception:
            LOGGER.exception("Unexpected pinned-window exit cleanup failure")

    def emergency_restore_for_crash(self) -> dict[str, object]:
        """Best-effort non-interactive cleanup for fatal Python exceptions."""

        self._is_quitting = True
        self._cleanup_global_hotkeys()
        self._hide_tray_icon()
        try:
            self._shelf_service.unpin_all()
        except Exception:
            LOGGER.exception("Fatal-crash pinned-window cleanup failed")
        managed_count = len(self._shelf_service.shelved_items())
        self._sync_recovery_state("fatal crash before restore")
        if managed_count == 0:
            return {"attempted": False, "managed_count": 0, "reason": "no managed windows"}

        try:
            restored, skipped = self._shelf_service.restore_all(focus=False)
        except Exception as exc:
            LOGGER.exception("Fatal-crash restore failed")
            return {
                "attempted": True,
                "managed_count": managed_count,
                "restored": 0,
                "skipped": 0,
                "failed": True,
                "error": str(exc),
            }

        try:
            self._persist_managed_state("fatal crash restore")
        except Exception:
            LOGGER.exception("Could not persist state after fatal-crash restore")

        LOGGER.critical(
            "Fatal-crash restore completed: managed=%s restored=%s skipped=%s",
            managed_count,
            restored,
            skipped,
        )
        return {
            "attempted": True,
            "managed_count": managed_count,
            "restored": restored,
            "skipped": skipped,
            "failed": False,
        }

    def _persist_managed_state(self, reason: str) -> None:
        self._apply_runtime_state_to_settings()
        self._settings_store.save(self._settings, reason=reason)
        self._sync_recovery_state(reason)

    def _sync_recovery_state(self, reason: str) -> None:
        records = self._recovery_records()
        if records:
            self._recovery_store.save(records, reason=reason)
        else:
            self._recovery_store.clear(reason=reason)

    def _recovery_records(self) -> list[dict[str, object]]:
        styles = self._shelf_service.managed_style_snapshot()
        boot_id = current_boot_id()
        records: list[dict[str, object]] = []
        for item in self._shelf_service.shelved_items():
            style = styles.get(item.window.handle)
            original_extended_style = getattr(style, "original_extended_style", None)
            if not isinstance(original_extended_style, int):
                LOGGER.warning(
                    "Skipping recovery state for managed window without original style: "
                    "handle=%s",
                    item.window.handle,
                )
                continue
            record = {
                "boot_id": boot_id,
                "handle": item.window.handle,
                "title": item.window.title,
                "process_id": item.window.process_id,
                "process_name": item.window.process_name,
                "executable_path": item.window.executable_path,
                "group_id": item.group_id,
                "hidden_at": item.hidden_at.isoformat(),
                "original_extended_style": original_extended_style,
            }
            managed_extended_style = getattr(style, "managed_extended_style", None)
            if isinstance(managed_extended_style, int):
                record["managed_extended_style"] = managed_extended_style
            records.append(record)
        return records

    def _apply_runtime_state_to_settings(self) -> None:
        self._settings.selected_group_id = self._valid_group_id(self._selected_group_id)
        self._settings.window_groups = [
            {
                "id": group.id,
                "name": group.name,
                "sort_order": group.sort_order,
            }
            for group in self._shelf_service.groups()
        ]
        boot_id = current_boot_id()
        self._settings.managed_windows = [
            {
                "boot_id": boot_id,
                "handle": item.window.handle,
                "title": item.window.title,
                "process_id": item.window.process_id,
                "process_name": item.window.process_name,
                "executable_path": item.window.executable_path,
                "group_id": item.group_id,
                "hidden_at": item.hidden_at.isoformat(),
            }
            for item in self._shelf_service.shelved_items()
        ]


def _startup_status_text(status: object) -> str:
    if getattr(status, "error", None):
        return tr("startup.status.unavailable", error=status.error)
    if not getattr(status, "enabled", False):
        return tr("startup.status.disabled")
    if not getattr(status, "path_valid", False):
        return tr("startup.status.invalid_path")
    if not getattr(status, "command_valid", False):
        return tr("startup.status.invalid_command")
    if getattr(status, "silent_startup", False):
        return tr("startup.status.enabled_silent")
    return tr("startup.status.enabled")


class GroupButton(QPushButton):
    windowDropped = Signal(int, str)

    def __init__(self, group_id: str, label: str) -> None:
        super().__init__(label)
        self.group_id = group_id
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: object) -> None:
        if _drag_has_window_handle(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: object) -> None:
        handle = _window_handle_from_drop(event)
        if handle is None:
            event.ignore()
            return
        self.windowDropped.emit(handle, self.group_id)
        event.acceptProposedAction()


class DraggableManagedWindowRow(QFrame):
    def __init__(self, handle: int) -> None:
        super().__init__()
        self._handle = handle
        self._drag_start_position = QPoint()

    def mousePressEvent(self, event: object) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_position = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: object) -> None:
        if not event.buttons() & Qt.MouseButton.LeftButton:
            return
        distance = (event.position().toPoint() - self._drag_start_position).manhattanLength()
        if distance < QApplication.startDragDistance():
            return

        mime_data = QMimeData()
        mime_data.setData(WINDOW_HANDLE_MIME, str(self._handle).encode("ascii"))

        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(Qt.DropAction.MoveAction)


def _drag_has_window_handle(event: object) -> bool:
    return event.mimeData().hasFormat(WINDOW_HANDLE_MIME)


def _window_handle_from_drop(event: object) -> int | None:
    if not _drag_has_window_handle(event):
        return None
    try:
        return int(bytes(event.mimeData().data(WINDOW_HANDLE_MIME)).decode("ascii"))
    except ValueError:
        return None
