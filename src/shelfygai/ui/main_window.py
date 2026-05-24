from __future__ import annotations

import logging
import sys
from collections.abc import Sequence
from dataclasses import asdict, replace
from time import perf_counter

from PySide6.QtCore import (
    QByteArray,
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QSize,
    Qt,
    QTimer,
    QUrl,
)
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QDesktopServices,
    QIcon,
    QKeySequence,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from shelfygai.constants import APP_NAME, APP_VERSION, GITHUB_REPOSITORY_URL, resource_path
from shelfygai.core.errors import ShelfyGAIError
from shelfygai.core.models import (
    DEFAULT_GROUP_ID,
    HideOptions,
    OverlayGroup,
    PinnedItem,
    ShelfItem,
    WindowGroup,
    WindowInfo,
)
from shelfygai.core.overlay_groups import OverlayGroupService
from shelfygai.core.shelf import ShelfService
from shelfygai.crash import EmergencyRecoveryStore
from shelfygai.i18n import SUPPORTED_LANGUAGES, set_language, tr
from shelfygai.logging_config import AppLogger
from shelfygai.performance import elapsed_ms, log_performance, memory_usage_mb
from shelfygai.settings.settings_manager import (
    DEFAULT_GLOBAL_HOTKEYS,
    HOTKEY_HIDE_SELECTED_WINDOW,
    HOTKEY_OPEN_SWITCHER,
    HOTKEY_PIN_UNPIN_FOCUSED,
    HOTKEY_RESET_EVERYTHING,
    HOTKEY_RESTORE_LAST,
    HOTKEY_TOGGLE_OVERLAY_HUB,
    AppSettings,
    SettingsManager,
    current_boot_id,
)
from shelfygai.ui.animations import animation_duration
from shelfygai.ui.components import GroupButton
from shelfygai.ui.hide_messages import hide_confirmation_message, hide_limitation_message
from shelfygai.ui.icons import AppIconProvider
from shelfygai.ui.notifications import NotificationKind, NotificationManager
from shelfygai.ui.onboarding_dialog import SettingsDialog
from shelfygai.ui.overlay_group_dialog import OverlayGroupChoiceDialog
from shelfygai.ui.overlay_markers import (
    OverlayDisplayConfig,
    OverlayMarkerManager,
    OverlayPopupItem,
)
from shelfygai.ui.pages.about_page import build_about_page
from shelfygai.ui.pages.hidden_windows_page import build_hidden_windows_page
from shelfygai.ui.pages.open_windows_page import (
    build_open_windows_page,
    build_open_windows_panel,
)
from shelfygai.ui.pages.overlay_groups_page import (
    build_overlay_appearance_section,
    build_overlay_behavior_section,
    build_overlay_feature_panel,
    build_overlay_field,
    build_overlay_group_list_panel,
    build_overlay_groups_page,
    build_overlay_position_section,
    build_overlay_preview_panel,
    build_overlay_settings_section,
    build_overlay_slider_setting,
    build_overlay_visibility_section,
    configure_int_slider_pair,
    configure_opacity_slider_pair,
    set_slider_value,
    update_overlay_preview,
)
from shelfygai.ui.pages.pinned_page import build_pinned_page
from shelfygai.ui.pages.settings_page import (
    build_settings_about_section,
    build_settings_accent_row,
    build_settings_combo_row,
    build_settings_page,
    build_settings_section,
    build_settings_spin_row,
)
from shelfygai.ui.pinned_order import (
    bring_handle_to_front,
    move_handle,
    ordered_pinned_handles,
    ordered_pinned_items,
)
from shelfygai.ui.theme import apply_theme
from shelfygai.ui.widgets.animated_button import AnimatedHoverButton
from shelfygai.ui.widgets.empty_state_widget import EmptyStateWidget
from shelfygai.ui.widgets.hidden_window_switcher import (
    SWITCHER_KIND_HIDDEN,
    SWITCHER_KIND_OVERLAY_GROUP,
    SWITCHER_KIND_PINNED,
    HiddenWindowSwitcher,
    SwitcherItem,
)
from shelfygai.ui.widgets.selected_window_card import build_selected_window_card
from shelfygai.ui.widgets.toolbar_actions import build_header
from shelfygai.ui.window_state import window_state_key
from shelfygai.updates.models import UpdateCheckStatus
from shelfygai.updates.service import UpdateService

LOGGER = logging.getLogger(__name__)

HANDLE_ROLE = Qt.ItemDataRole.UserRole
EXE_PATH_ROLE = Qt.ItemDataRole.UserRole + 1
FILTER_ROLE = Qt.ItemDataRole.UserRole + 2
STATE_KEY_ROLE = Qt.ItemDataRole.UserRole + 3
HOTKEY_ACTION_LABEL_KEYS = {
    HOTKEY_HIDE_SELECTED_WINDOW: "hotkey.label.hide_selected",
    HOTKEY_RESTORE_LAST: "hotkey.label.restore_last",
    HOTKEY_TOGGLE_OVERLAY_HUB: "hotkey.label.toggle_overlay_hub",
    HOTKEY_OPEN_SWITCHER: "hotkey.label.open_switcher",
    HOTKEY_PIN_UNPIN_FOCUSED: "hotkey.label.pin_unpin_focused",
    HOTKEY_RESET_EVERYTHING: "hotkey.label.reset_everything",
}
HOTKEY_ACTION_DESCRIPTION_KEYS = {
    HOTKEY_HIDE_SELECTED_WINDOW: "hotkey.desc.hide_selected",
    HOTKEY_RESTORE_LAST: "hotkey.desc.restore_last",
    HOTKEY_TOGGLE_OVERLAY_HUB: "hotkey.desc.toggle_overlay_hub",
    HOTKEY_OPEN_SWITCHER: "hotkey.desc.open_switcher",
    HOTKEY_PIN_UNPIN_FOCUSED: "hotkey.desc.pin_unpin_focused",
    HOTKEY_RESET_EVERYTHING: "hotkey.desc.reset_everything",
}
OPEN_WINDOWS_AUTO_REFRESH_INTERVAL_MS = 15_000
SEARCH_FILTER_DEBOUNCE_MS = 180
WINDOW_STATE_REFRESH_INTERVAL_MS = 1_000
REFRESH_DEBOUNCE_MS = 160
NAVIGATION_KEYS = (
    "label.open_windows",
    "label.shelf",
    "label.pinned",
    "label.groups",
    "label.settings",
    "label.about",
)
PAGE_COPY_KEYS = {
    0: ("label.open_windows", "page.open_windows.subtitle"),
    1: ("label.shelf", "page.shelf.subtitle"),
    2: ("label.pinned", "page.pinned.subtitle"),
    3: ("label.groups", "page.groups.subtitle"),
    4: ("label.settings", "page.settings.subtitle"),
    5: ("label.about", "page.about.subtitle"),
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
        self._notifications = NotificationManager(lambda: self._settings)
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
        self._group_table = self._build_table()
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
        self._overlay_group_service = OverlayGroupService(
            _overlay_groups_from_settings(self._settings.overlay_groups)
        )
        self._selected_overlay_group_id = self._valid_overlay_group_id(
            self._settings.selected_overlay_group_id
        )
        self._overlay_controls_syncing = False
        self._overlay_enabled_checkbox = QCheckBox()
        self._overlay_use_hub_checkbox = QCheckBox()
        self._overlay_individual_markers_checkbox = QCheckBox()
        self._overlay_replace_markers_checkbox = QCheckBox()
        self._overlay_hub_always_visible_checkbox = QCheckBox()
        self._overlay_hub_auto_hide_checkbox = QCheckBox()
        self._overlay_auto_snap_checkbox = QCheckBox()
        self._overlay_compact_mode_checkbox = QCheckBox()
        self._overlay_groups_list = QListWidget()
        self._overlay_name_edit = QLineEdit()
        self._overlay_color_button = AnimatedHoverButton()
        self._overlay_marker_width_spin = QSpinBox()
        self._overlay_marker_height_spin = QSpinBox()
        self._overlay_opacity_spin = QDoubleSpinBox()
        self._overlay_corner_radius_spin = QSpinBox()
        self._overlay_hover_delay_spin = QSpinBox()
        self._overlay_marker_width_slider = QSlider(Qt.Orientation.Horizontal)
        self._overlay_marker_height_slider = QSlider(Qt.Orientation.Horizontal)
        self._overlay_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._overlay_corner_radius_slider = QSlider(Qt.Orientation.Horizontal)
        self._overlay_hover_delay_slider = QSlider(Qt.Orientation.Horizontal)
        self._overlay_marker_spacing_spin = QSpinBox()
        self._overlay_marker_spacing_slider = QSlider(Qt.Orientation.Horizontal)
        self._overlay_hub_opacity_spin = QDoubleSpinBox()
        self._overlay_hub_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._overlay_locked_position_checkbox = QCheckBox()
        self._overlay_hide_fullscreen_checkbox = QCheckBox()
        self._overlay_quick_controls_checkbox = QCheckBox()
        self._overlay_reset_position_button = AnimatedHoverButton()
        self._overlay_delete_button = AnimatedHoverButton()
        self._overlay_empty_label = EmptyStateWidget(minimum_height=116)
        self._overlay_preview_marker = QFrame()
        self._overlay_preview_group_name = QLabel()
        self._overlay_preview_window_count = QLabel()
        self._overlay_marker_manager = OverlayMarkerManager(
            self._overlay_popup_items,
            parent=self,
        )
        self._overlay_marker_manager.positionSaved.connect(self._save_overlay_marker_position)
        self._overlay_marker_manager.hubPositionSaved.connect(self._save_overlay_hub_position)
        self._overlay_marker_manager.settingsRequested.connect(
            self._show_overlay_group_settings
        )
        self._overlay_marker_manager.colorChangeRequested.connect(
            self._choose_overlay_color_for_group
        )
        self._overlay_marker_manager.lockChanged.connect(self._set_overlay_group_locked)
        self._overlay_marker_manager.windowOpenRequested.connect(self._open_overlay_window)
        self._overlay_marker_manager.windowRestoreRequested.connect(
            self._restore_overlay_window
        )
        self._overlay_marker_manager.windowBringToFrontRequested.connect(
            self._open_overlay_window
        )
        self._overlay_marker_manager.windowRemoveRequested.connect(
            self._remove_overlay_window_from_group
        )
        self._overlay_marker_manager.restoreAllRequested.connect(
            self._restore_overlay_group_windows
        )
        self._overlay_marker_manager.hideAllRequested.connect(
            self._hide_overlay_group_windows
        )
        self._overlay_marker_manager.openShelfyRequested.connect(self._open_from_overlay_popup)
        self._quick_switcher = HiddenWindowSwitcher(self)
        self._quick_switcher.itemActivated.connect(self._activate_switcher_item)
        self._open_windows_search = QLineEdit()
        self._open_windows_auto_refresh_checkbox = QCheckBox()
        self._open_windows_refresh_timer = QTimer(self)
        self._open_windows_filter_timer = QTimer(self)
        self._window_state_refresh_timer = QTimer(self)
        self._refresh_debounce_timer = QTimer(self)
        self._pinned_watcher_timer = QTimer(self)
        self._header_title = QLabel()
        self._header_subtitle = QLabel()
        self._loading_label = QLabel()
        self._open_windows_empty_label = EmptyStateWidget(minimum_height=132)
        self._shelf_empty_label = EmptyStateWidget(minimum_height=132)
        self._pinned_empty_label = EmptyStateWidget(minimum_height=132)
        self._group_empty_label = EmptyStateWidget(minimum_height=108)
        self._selected_window_icon = QLabel()
        self._selected_window_app = QLabel()
        self._selected_window_title = QLabel()
        self._selected_window_state = QLabel()
        self._selected_window_hint = QLabel()
        self._selected_hide_button: QPushButton | None = None
        self._selected_overlay_group_button: QPushButton | None = None
        self._hide_taskbar_checkbox = QCheckBox()
        self._hide_alt_tab_checkbox = QCheckBox()
        self._hide_tray_checkbox = QCheckBox()
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
        self._notifications_enabled_checkbox = QCheckBox()
        self._tray_notifications_checkbox = QCheckBox()
        self._overlay_notifications_checkbox = QCheckBox()
        self._restore_notifications_checkbox = QCheckBox()
        self._pin_notifications_checkbox = QCheckBox()
        self._silent_mode_checkbox = QCheckBox()
        self._debug_mode_checkbox = QCheckBox()
        self._startup_status_label = QLabel()
        self._startup_status_label.setObjectName("Muted")
        self._startup_status_label.setWordWrap(True)
        self._settings_controls_syncing = False
        self._settings_sections: list[object] = []
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
        self._page_animation: QPropertyAnimation | None = None
        self._tray_icon: QSystemTrayIcon | None = None
        self._tray_hidden_windows_action: QAction | None = None
        self._tray_overlay_groups_action: QAction | None = None
        self._tray_restore_all_action: QAction | None = None
        self._tray_unpin_all_action: QAction | None = None
        self._tray_reset_action: QAction | None = None
        self._is_quitting = False
        self._tray_hint_shown = False
        self._initial_refresh_done = False
        self._initial_refresh_scheduled = False
        self._last_available_windows: tuple[WindowInfo, ...] = ()
        self._last_shelf_items: tuple[ShelfItem, ...] = ()
        self._last_pinned_items: tuple[PinnedItem, ...] = ()
        self._pinned_order: list[int] = []
        self._pending_refresh_reason: str | None = None

        self._open_windows_refresh_timer.setInterval(OPEN_WINDOWS_AUTO_REFRESH_INTERVAL_MS)
        self._open_windows_refresh_timer.setTimerType(Qt.TimerType.VeryCoarseTimer)
        self._open_windows_refresh_timer.timeout.connect(
            lambda: self._request_refresh(reason="auto")
        )
        self._open_windows_filter_timer.setSingleShot(True)
        self._open_windows_filter_timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._open_windows_filter_timer.setInterval(SEARCH_FILTER_DEBOUNCE_MS)
        self._open_windows_filter_timer.timeout.connect(self._apply_open_windows_filter)
        self._window_state_refresh_timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._window_state_refresh_timer.setInterval(WINDOW_STATE_REFRESH_INTERVAL_MS)
        self._window_state_refresh_timer.timeout.connect(self._refresh_window_states)
        self._refresh_debounce_timer.setSingleShot(True)
        self._refresh_debounce_timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._refresh_debounce_timer.setInterval(REFRESH_DEBOUNCE_MS)
        self._refresh_debounce_timer.timeout.connect(self._run_debounced_refresh)
        self._pinned_watcher_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._pinned_watcher_timer.timeout.connect(self._check_pinned_windows)
        self._configure_table_context_menus()
        self._bind_text(self._open_windows_search, "placeholder.open_search", "setPlaceholderText")
        self._bind_text(self._open_windows_search, "placeholder.open_search", "setAccessibleName")
        self._open_windows_search.setClearButtonEnabled(True)
        self._open_windows_search.textChanged.connect(self._schedule_open_windows_filter)
        self._available_table.itemSelectionChanged.connect(self._update_selected_window_card)
        self._loading_label.setObjectName("LoadingPill")
        self._loading_label.setVisible(False)
        self._loading_label.setMinimumHeight(28)
        self._open_windows_empty_label.set_action("", self._request_refresh)
        self._overlay_empty_label.set_action("", self._create_overlay_group)
        self._bind_text(
            self._open_windows_empty_label,
            "action.refresh",
            "setActionText",
        )
        self._bind_text(
            self._overlay_empty_label,
            "action.create_overlay_group",
            "setActionText",
        )
        self._overlay_groups_list.setObjectName("OverlayGroupsList")
        self._overlay_groups_list.setIconSize(QSize(16, 16))
        self._overlay_groups_list.setSpacing(4)
        self._overlay_groups_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._overlay_groups_list.setAlternatingRowColors(False)
        self._overlay_groups_list.currentItemChanged.connect(
            self._select_overlay_group_from_list
        )
        self._overlay_name_edit.editingFinished.connect(self._update_overlay_name)
        self._overlay_marker_width_spin.setRange(4, 64)
        self._overlay_marker_width_spin.setSuffix(" px")
        self._overlay_marker_height_spin.setRange(24, 256)
        self._overlay_marker_height_spin.setSuffix(" px")
        self._overlay_opacity_spin.setRange(0.2, 1.0)
        self._overlay_opacity_spin.setSingleStep(0.05)
        self._overlay_opacity_spin.setDecimals(2)
        self._overlay_corner_radius_spin.setRange(0, 32)
        self._overlay_corner_radius_spin.setSuffix(" px")
        self._overlay_hover_delay_spin.setRange(0, 5_000)
        self._overlay_hover_delay_spin.setSingleStep(100)
        self._overlay_hover_delay_spin.setSuffix(" ms")
        self._overlay_marker_spacing_spin.setRange(2, 48)
        self._overlay_marker_spacing_spin.setSingleStep(1)
        self._overlay_marker_spacing_spin.setSuffix(" px")
        self._overlay_hub_opacity_spin.setRange(0.25, 1.0)
        self._overlay_hub_opacity_spin.setSingleStep(0.05)
        self._overlay_hub_opacity_spin.setDecimals(2)
        self._configure_int_slider_pair(
            self._overlay_marker_width_slider,
            self._overlay_marker_width_spin,
        )
        self._configure_int_slider_pair(
            self._overlay_marker_height_slider,
            self._overlay_marker_height_spin,
        )
        self._configure_opacity_slider_pair()
        self._configure_int_slider_pair(
            self._overlay_corner_radius_slider,
            self._overlay_corner_radius_spin,
        )
        self._configure_int_slider_pair(
            self._overlay_hover_delay_slider,
            self._overlay_hover_delay_spin,
        )
        self._configure_int_slider_pair(
            self._overlay_marker_spacing_slider,
            self._overlay_marker_spacing_spin,
        )
        self._overlay_hub_opacity_slider.setRange(25, 100)
        self._overlay_hub_opacity_slider.setSingleStep(5)
        self._overlay_hub_opacity_slider.valueChanged.connect(
            lambda value: self._overlay_hub_opacity_spin.setValue(value / 100)
        )
        self._overlay_hub_opacity_spin.valueChanged.connect(
            lambda value: self._set_slider_value(
                self._overlay_hub_opacity_slider,
                int(round(float(value) * 100)),
            )
        )
        self._overlay_enabled_checkbox.setChecked(self._settings.overlay_groups_enabled)
        self._overlay_enabled_checkbox.toggled.connect(self._set_overlay_groups_enabled)
        self._overlay_use_hub_checkbox.toggled.connect(
            lambda _checked: self._update_overlay_display_settings()
        )
        self._overlay_individual_markers_checkbox.toggled.connect(
            lambda _checked: self._update_overlay_display_settings()
        )
        self._overlay_replace_markers_checkbox.toggled.connect(
            lambda _checked: self._update_overlay_display_settings()
        )
        self._overlay_hub_always_visible_checkbox.toggled.connect(
            lambda _checked: self._update_overlay_display_settings()
        )
        self._overlay_hub_auto_hide_checkbox.toggled.connect(
            lambda _checked: self._update_overlay_display_settings()
        )
        self._overlay_auto_snap_checkbox.toggled.connect(
            lambda _checked: self._update_overlay_display_settings()
        )
        self._overlay_compact_mode_checkbox.toggled.connect(
            lambda _checked: self._update_overlay_display_settings()
        )
        self._overlay_marker_spacing_spin.valueChanged.connect(
            lambda _value: self._update_overlay_display_settings()
        )
        self._overlay_hub_opacity_spin.valueChanged.connect(
            lambda _value: self._update_overlay_display_settings()
        )
        self._overlay_marker_width_spin.valueChanged.connect(
            lambda _value: self._update_overlay_numeric_settings()
        )
        self._overlay_marker_height_spin.valueChanged.connect(
            lambda _value: self._update_overlay_numeric_settings()
        )
        self._overlay_opacity_spin.valueChanged.connect(
            lambda _value: self._update_overlay_numeric_settings()
        )
        self._overlay_corner_radius_spin.valueChanged.connect(
            lambda _value: self._update_overlay_numeric_settings()
        )
        self._overlay_hover_delay_spin.valueChanged.connect(
            lambda _value: self._update_overlay_numeric_settings()
        )
        self._overlay_locked_position_checkbox.toggled.connect(
            lambda _checked: self._update_overlay_boolean_settings()
        )
        self._overlay_hide_fullscreen_checkbox.toggled.connect(
            lambda _checked: self._update_overlay_boolean_settings()
        )
        self._overlay_quick_controls_checkbox.toggled.connect(
            lambda _checked: self._update_overlay_boolean_settings()
        )
        self._overlay_color_button.clicked.connect(self._choose_overlay_color)
        self._overlay_reset_position_button.clicked.connect(self._reset_overlay_marker_position)
        self._overlay_delete_button.clicked.connect(self._delete_selected_overlay_group)
        self._selected_window_icon.setObjectName("IconBadge")
        self._selected_window_icon.setFixedSize(42, 42)
        self._selected_window_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._selected_window_app.setObjectName("CardTitle")
        self._selected_window_title.setObjectName("Muted")
        self._selected_window_title.setWordWrap(True)
        self._selected_window_state.setObjectName("Muted")
        self._selected_window_hint.setObjectName("EmptyState")
        self._selected_window_hint.setWordWrap(True)
        self._selected_window_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hide_taskbar_checkbox.setChecked(True)
        self._hide_alt_tab_checkbox.setChecked(True)
        self._hide_tray_checkbox.setChecked(False)
        self._hide_tray_checkbox.setEnabled(False)
        self._bind_text(self._hide_taskbar_checkbox, "label.hide_taskbar")
        self._bind_text(self._hide_alt_tab_checkbox, "label.hide_alt_tab")
        self._bind_text(self._hide_tray_checkbox, "label.hide_tray")
        self._bind_text(self._hide_tray_checkbox, "tooltip.hide_tray_limited", "setToolTip")
        self._pinned_watcher_interval_spin.setRange(100, 10_000)
        self._pinned_watcher_interval_spin.setSingleStep(100)
        self._pinned_watcher_interval_spin.setSuffix(" ms")
        self._bind_text(self._open_windows_auto_refresh_checkbox, "label.auto_refresh")
        self._bind_text(self._restore_on_exit_checkbox, "label.restore_on_exit")
        self._bind_text(self._restore_pinned_on_exit_checkbox, "label.restore_pinned_on_exit")
        self._restore_pinned_on_exit_checkbox.setEnabled(False)
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
        self._bind_text(
            self._notifications_enabled_checkbox,
            "label.notifications_enabled",
        )
        self._bind_text(
            self._tray_notifications_checkbox,
            "label.show_tray_notifications",
        )
        self._bind_text(
            self._overlay_notifications_checkbox,
            "label.show_overlay_notifications",
        )
        self._bind_text(
            self._restore_notifications_checkbox,
            "label.show_restore_notifications",
        )
        self._bind_text(
            self._pin_notifications_checkbox,
            "label.show_pin_unpin_notifications",
        )
        self._bind_text(self._silent_mode_checkbox, "label.silent_mode")
        self._bind_text(self._debug_mode_checkbox, "label.debug_logging")
        self._bind_text(self._hotkey_status_label, "hotkey.default_status")
        self._bind_text(self._update_status_label, "about.update.default")
        self._bind_text(self._overlay_enabled_checkbox, "label.overlay_groups_enabled")
        self._bind_text(self._overlay_use_hub_checkbox, "label.overlay_use_unified_hub")
        self._bind_text(
            self._overlay_individual_markers_checkbox,
            "label.overlay_use_individual_markers",
        )
        self._bind_text(
            self._overlay_replace_markers_checkbox,
            "label.overlay_replace_individual_markers",
        )
        self._bind_text(
            self._overlay_hub_always_visible_checkbox,
            "label.overlay_hub_always_visible",
        )
        self._bind_text(
            self._overlay_hub_auto_hide_checkbox,
            "label.overlay_hub_auto_hide",
        )
        self._bind_text(self._overlay_auto_snap_checkbox, "label.overlay_auto_snap")
        self._bind_text(self._overlay_compact_mode_checkbox, "label.overlay_compact_mode")
        self._bind_text(self._overlay_color_button, "action.choose_color")
        self._bind_text(
            self._overlay_reset_position_button,
            "action.reset_marker_position",
        )
        self._overlay_delete_button.setObjectName("DangerButton")
        self._bind_text(self._overlay_delete_button, "action.delete_overlay_group")
        self._bind_text(self._overlay_empty_label, "empty.overlay_groups")
        self._bind_text(self._overlay_name_edit, "label.overlay_group_name", "setAccessibleName")
        self._bind_text(
            self._overlay_marker_width_spin,
            "label.overlay_marker_width",
            "setAccessibleName",
        )
        self._bind_text(
            self._overlay_marker_height_spin,
            "label.overlay_marker_height",
            "setAccessibleName",
        )
        self._bind_text(
            self._overlay_opacity_spin,
            "label.overlay_opacity",
            "setAccessibleName",
        )
        self._bind_text(
            self._overlay_corner_radius_spin,
            "label.overlay_corner_radius",
            "setAccessibleName",
        )
        self._bind_text(
            self._overlay_hover_delay_spin,
            "label.overlay_hover_delay",
            "setAccessibleName",
        )
        self._bind_text(
            self._overlay_marker_spacing_spin,
            "label.overlay_marker_spacing",
            "setAccessibleName",
        )
        self._bind_text(
            self._overlay_hub_opacity_spin,
            "label.overlay_hub_opacity",
            "setAccessibleName",
        )
        self._bind_text(
            self._overlay_locked_position_checkbox,
            "label.overlay_lock_position",
        )
        self._bind_text(
            self._overlay_hide_fullscreen_checkbox,
            "label.overlay_hide_fullscreen",
        )
        self._bind_text(
            self._overlay_quick_controls_checkbox,
            "label.overlay_show_quick_controls",
        )
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
        self._notifications_enabled_checkbox.toggled.connect(self._set_notification_settings)
        self._tray_notifications_checkbox.toggled.connect(self._set_notification_settings)
        self._overlay_notifications_checkbox.toggled.connect(self._set_notification_settings)
        self._restore_notifications_checkbox.toggled.connect(self._set_notification_settings)
        self._pin_notifications_checkbox.toggled.connect(self._set_notification_settings)
        self._silent_mode_checkbox.toggled.connect(self._set_notification_settings)
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
        self._sync_overlay_markers()
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
        for section in self._settings_sections:
            retranslate = getattr(section, "retranslate", None)
            if callable(retranslate):
                retranslate()
        self._refresh_settings_choice_labels()
        self._set_table_headers(self._available_table)
        self._set_table_headers(self._shelf_table)
        self._set_table_headers(self._pinned_table)
        self._set_table_headers(self._group_table)
        self._refresh_table_state_translations()
        self._show_page(self._stack.currentIndex())
        self._rebuild_group_sidebar()
        self._populate_pinned(self._last_pinned_items)
        self._populate_group_table(self._last_shelf_items)
        self._quick_switcher.retranslate()
        self._refresh_empty_states()
        self._update_selected_window_card()
        for action_id, checkbox in self._hotkey_enabled_checkboxes.items():
            checkbox.setToolTip(
                tr("tooltip.enable_hotkey", label=self._hotkey_label(action_id).lower())
            )
        self._sync_tray_actions()

    def _set_table_headers(self, table: QTableWidget) -> None:
        table.setHorizontalHeaderLabels(
            [
                tr("label.table.icon"),
                tr("label.table.app"),
                tr("label.table.title"),
                tr("label.table.state"),
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
        refresh_action.triggered.connect(self._request_refresh)
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
        for table in (
            self._available_table,
            self._shelf_table,
            self._pinned_table,
            self._group_table,
        ):
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
        tray_menu.setSeparatorsCollapsible(True)
        tray_menu.setStyleSheet(
            """
            QMenu {
                background: #1a1f26;
                border: 1px solid #2a3038;
                border-radius: 10px;
                padding: 5px;
                color: #f4f7fa;
            }
            QMenu::item {
                padding: 6px 24px 6px 11px;
                border-radius: 7px;
            }
            QMenu::item:selected {
                background: #2a323d;
            }
            QMenu::item:disabled {
                color: #7d8793;
            }
            QMenu::separator {
                height: 1px;
                background: #242a32;
                margin: 5px 6px;
            }
            """
        )

        open_action = QAction(self)
        self._bind_text(open_action, "tray.open")
        open_action.triggered.connect(self._show_from_tray)

        hidden_windows_action = QAction(self)
        hidden_windows_action.triggered.connect(self._open_hidden_windows_from_tray)
        self._tray_hidden_windows_action = hidden_windows_action

        overlay_groups_action = QAction(self)
        overlay_groups_action.triggered.connect(self._open_overlay_groups_from_tray)
        self._tray_overlay_groups_action = overlay_groups_action

        restore_all_action = QAction(self)
        self._bind_text(restore_all_action, "tray.restore_all")
        restore_all_action.triggered.connect(self._restore_all)
        self._tray_restore_all_action = restore_all_action

        unpin_all_action = QAction(self)
        self._bind_text(unpin_all_action, "action.unpin_all")
        unpin_all_action.triggered.connect(self._unpin_all)
        self._tray_unpin_all_action = unpin_all_action

        reset_action = QAction(self)
        self._bind_text(reset_action, "action.reset_everything")
        reset_action.triggered.connect(self._reset_everything)
        self._tray_reset_action = reset_action

        settings_action = QAction(self)
        self._bind_text(settings_action, "action.settings")
        settings_action.triggered.connect(self._open_settings_from_tray)

        quit_action = QAction(self)
        self._bind_text(quit_action, "tray.quit")
        quit_action.triggered.connect(self._quit_from_tray)

        tray_menu.addAction(open_action)
        tray_menu.addAction(hidden_windows_action)
        tray_menu.addAction(overlay_groups_action)
        tray_menu.addSeparator()
        tray_menu.addAction(restore_all_action)
        tray_menu.addAction(unpin_all_action)
        tray_menu.addAction(reset_action)
        tray_menu.addSeparator()
        tray_menu.addAction(settings_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)

        self._tray_icon = QSystemTrayIcon(self._app_icon, self)
        self._bind_text(self._tray_icon, "tray.tooltip", "setToolTip", version=APP_VERSION)
        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()
        self._sync_tray_actions()
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
        self._show_status(tr("status.ready"))
        self._apply_adaptive_layout()

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(232)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 22, 18, 18)
        layout.setSpacing(9)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(12)

        brand_icon = QLabel()
        brand_icon.setObjectName("IconBadge")
        brand_icon.setFixedSize(44, 44)
        brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_icon.setPixmap(QIcon(str(resource_path("app_icon.svg"))).pixmap(30, 30))

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
        layout.addSpacing(12)

        for index, label_key in enumerate(NAVIGATION_KEYS):
            button = AnimatedHoverButton()
            button.setObjectName("SidebarButton")
            button.setCheckable(True)
            button.setFlat(True)
            self._bind_text(button, label_key)
            button.clicked.connect(lambda _checked=False, page=index: self._show_page(page))
            self._nav_buttons.append(button)
            layout.addWidget(button)

        layout.addStretch(1)

        version = QLabel(f"v{APP_VERSION}")
        version.setObjectName("BrandSubtitle")
        layout.addWidget(version)

        self._show_page(0)
        return sidebar

    def _build_content(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(16)
        self._content_layout = layout

        layout.addLayout(self._build_header())

        self._stack.addWidget(self._build_windows_page())
        self._stack.addWidget(self._build_shelf_page())
        self._stack.addWidget(self._build_pinned_page())
        self._stack.addWidget(self._build_groups_page())
        self._stack.addWidget(self._build_settings_page())
        self._stack.addWidget(self._build_about_page())
        layout.addWidget(self._stack, 1)

        return content

    def _build_header(self) -> QHBoxLayout:
        return build_header(self)

    def _build_windows_page(self) -> QWidget:
        return build_open_windows_page(self)

    def _build_open_windows_panel(self) -> QFrame:
        return build_open_windows_panel(self)

    def _build_selected_window_card(self) -> QFrame:
        return build_selected_window_card(self)

    def _build_shelf_page(self) -> QWidget:
        return build_hidden_windows_page(self)

    def _build_pinned_page(self) -> QWidget:
        return build_pinned_page(self)

    def _build_groups_page(self) -> QWidget:
        return build_overlay_groups_page(self)

    def _build_overlay_group_list_panel(self) -> QFrame:
        return build_overlay_group_list_panel(self)

    def _build_overlay_feature_panel(self) -> QWidget:
        return build_overlay_feature_panel(self)

    def _build_overlay_preview_panel(self) -> QFrame:
        return build_overlay_preview_panel(self)

    def _build_overlay_appearance_section(self) -> QFrame:
        return build_overlay_appearance_section(self)

    def _build_overlay_behavior_section(self) -> QFrame:
        return build_overlay_behavior_section(self)

    def _build_overlay_position_section(self) -> QFrame:
        return build_overlay_position_section(self)

    def _build_overlay_visibility_section(self) -> QFrame:
        return build_overlay_visibility_section(self)

    def _build_overlay_settings_section(self, title_key: str) -> QFrame:
        return build_overlay_settings_section(self, title_key)

    def _build_overlay_field(self, label_key: str, widget: QWidget) -> QWidget:
        return build_overlay_field(self, label_key, widget)

    def _build_overlay_slider_setting(
        self,
        label_key: str,
        slider: QSlider,
        spinbox: QWidget,
    ) -> QWidget:
        return build_overlay_slider_setting(self, label_key, slider, spinbox)

    def _configure_int_slider_pair(self, slider: QSlider, spinbox: QSpinBox) -> None:
        configure_int_slider_pair(slider, spinbox)

    def _configure_opacity_slider_pair(self) -> None:
        configure_opacity_slider_pair(self)

    def _set_slider_value(self, slider: QSlider, value: int) -> None:
        set_slider_value(slider, value)

    def _update_overlay_preview(self, group: OverlayGroup | None = None) -> None:
        update_overlay_preview(self, group)

    def _build_settings_page(self) -> QWidget:
        return build_settings_page(self)

    def _build_settings_section(self, title_key: str, widgets: list[QWidget]) -> QFrame:
        return build_settings_section(self, title_key, widgets)

    def _build_settings_combo_row(self, label_key: str, combo: QComboBox) -> QWidget:
        return build_settings_combo_row(self, label_key, combo)

    def _build_settings_spin_row(self, label_key: str, spin_box: QSpinBox) -> QWidget:
        return build_settings_spin_row(self, label_key, spin_box)

    def _build_settings_accent_row(self) -> QWidget:
        return build_settings_accent_row(self)

    def _build_settings_about_section(self) -> QFrame:
        return build_settings_about_section(self)

    def _build_about_page(self) -> QWidget:
        return build_about_page(self)

    def _build_hotkeys_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

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

            clear_button = AnimatedHoverButton()
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

        restore_defaults_button = AnimatedHoverButton()
        self._bind_text(restore_defaults_button, "action.restore_default_hotkeys")
        restore_defaults_button.clicked.connect(self._restore_default_hotkeys)

        layout.addWidget(title)
        layout.addLayout(grid)
        layout.addWidget(self._hotkey_status_label)
        layout.addWidget(restore_defaults_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self._sync_hotkey_controls()
        return panel

    def _build_table(self) -> QTableWidget:
        table = QTableWidget(0, 4)
        self._set_table_headers(table)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSortingEnabled(False)
        table.setShowGrid(False)
        table.setWordWrap(False)
        table.setIconSize(QSize(18, 18))
        table.setCornerButtonEnabled(False)
        table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        table.verticalHeader().setDefaultSectionSize(32)
        table.horizontalHeader().setHighlightSections(False)
        table.horizontalHeader().setSectionsClickable(False)
        table.horizontalHeader().setSortIndicatorShown(False)
        table.horizontalHeader().setMinimumSectionSize(48)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, 40)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        return table

    def _make_button(
        self,
        text_key: str,
        callback: object,
        *,
        primary: bool = False,
    ) -> QPushButton:
        button = AnimatedHoverButton()
        self._bind_text(button, text_key)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        if primary:
            button.setObjectName("PrimaryButton")
        button.clicked.connect(callback)  # type: ignore[arg-type]
        return button

    def _make_link_button(
        self,
        text_key: str,
        url: str,
        *,
        primary: bool = False,
    ) -> QPushButton:
        button = AnimatedHoverButton()
        self._bind_text(button, text_key)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        if primary:
            button.setObjectName("PrimaryButton")
        button.clicked.connect(lambda _checked=False, current_url=url: self._open_url(current_url))
        return button

    def _show_page(self, page: int) -> None:
        if hasattr(self, "_stack"):
            self._stack.setCurrentIndex(page)
            self._animate_page(self._stack.currentWidget())
            if hasattr(self, "_open_windows_refresh_timer"):
                self._configure_open_windows_auto_refresh(
                    self._settings.open_windows_auto_refresh
                )
            if hasattr(self, "_window_state_refresh_timer"):
                self._configure_window_state_refresh()
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
        self._show_page(4)

    def _animate_page(self, widget: QWidget | None) -> None:
        if widget is None:
            return
        duration = animation_duration(120)
        if duration == 0:
            widget.setGraphicsEffect(None)
            return
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        self._page_animation = QPropertyAnimation(effect, b"opacity", self)
        self._page_animation.setDuration(duration)
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
        return None

    def _apply_adaptive_layout(self) -> None:
        compact = self.width() < 980
        if self._sidebar is not None:
            self._sidebar.setFixedWidth(208 if compact else 232)
        if self._content_layout is not None:
            if compact:
                self._content_layout.setContentsMargins(16, 16, 16, 14)
                self._content_layout.setSpacing(12)
            else:
                self._content_layout.setContentsMargins(24, 22, 24, 18)
                self._content_layout.setSpacing(16)

    def resizeEvent(self, event: object) -> None:
        self._apply_adaptive_layout()
        super().resizeEvent(event)

    def showEvent(self, event: object) -> None:
        super().showEvent(event)
        self._schedule_initial_refresh()
        self._configure_open_windows_auto_refresh(self._settings.open_windows_auto_refresh)
        self._configure_window_state_refresh()

    def hideEvent(self, event: object) -> None:
        self._configure_open_windows_auto_refresh(False)
        self._configure_window_state_refresh(False)
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

    def _valid_overlay_group_id(self, group_id: str) -> str:
        group_ids = {group.id for group in self._overlay_group_service.groups()}
        if group_id in group_ids:
            return group_id
        groups = list(self._overlay_group_service.groups())
        return groups[0].id if groups else ""

    def _selected_overlay_group(self) -> OverlayGroup | None:
        for group in self._overlay_group_service.groups():
            if group.id == self._selected_overlay_group_id:
                return group
        return None

    def _populate_overlay_groups_list(self) -> None:
        if not hasattr(self, "_overlay_groups_list"):
            return
        groups = list(self._overlay_group_service.groups())
        self._overlay_controls_syncing = True
        self._overlay_groups_list.clear()
        for group in groups:
            count = len(group.assigned_window_ids)
            count_key = (
                "dialog.choose_overlay_group.count_one"
                if count == 1
                else "dialog.choose_overlay_group.count_many"
            )
            item = QListWidgetItem(f"{group.name}\n{tr(count_key, count=count)}")
            item.setData(Qt.ItemDataRole.UserRole, group.id)
            item.setToolTip(group.name)
            item.setSizeHint(QSize(0, 52))
            swatch = QPixmap(16, 16)
            swatch.fill(QColor(group.color))
            item.setIcon(QIcon(swatch))
            self._overlay_groups_list.addItem(item)
        self._selected_overlay_group_id = self._valid_overlay_group_id(
            self._selected_overlay_group_id
        )
        selected_row = -1
        for row, group in enumerate(groups):
            if group.id == self._selected_overlay_group_id:
                selected_row = row
                break
        self._overlay_groups_list.setCurrentRow(selected_row)
        self._overlay_empty_label.setText(tr("empty.overlay_groups"))
        self._overlay_empty_label.setVisible(not groups)
        self._overlay_groups_list.setVisible(bool(groups))
        self._overlay_controls_syncing = False
        self._sync_overlay_group_controls()

    def _select_overlay_group_from_list(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if self._overlay_controls_syncing:
            return
        group_id = current.data(Qt.ItemDataRole.UserRole) if current is not None else ""
        self._selected_overlay_group_id = str(group_id) if group_id else ""
        self._sync_overlay_group_controls()
        self._persist_overlay_groups("selected overlay group changed")

    def _sync_overlay_group_controls(self) -> None:
        group = self._selected_overlay_group()
        enabled = group is not None
        self._overlay_controls_syncing = True
        self._overlay_name_edit.setEnabled(enabled)
        self._overlay_color_button.setEnabled(enabled)
        self._overlay_marker_width_spin.setEnabled(enabled)
        self._overlay_marker_height_spin.setEnabled(enabled)
        self._overlay_opacity_spin.setEnabled(enabled)
        self._overlay_corner_radius_spin.setEnabled(enabled)
        self._overlay_hover_delay_spin.setEnabled(enabled)
        self._overlay_marker_width_slider.setEnabled(enabled)
        self._overlay_marker_height_slider.setEnabled(enabled)
        self._overlay_opacity_slider.setEnabled(enabled)
        self._overlay_corner_radius_slider.setEnabled(enabled)
        self._overlay_hover_delay_slider.setEnabled(enabled)
        self._overlay_marker_spacing_slider.setEnabled(True)
        self._overlay_marker_spacing_spin.setEnabled(True)
        self._overlay_hub_opacity_slider.setEnabled(True)
        self._overlay_hub_opacity_spin.setEnabled(True)
        self._overlay_locked_position_checkbox.setEnabled(enabled)
        self._overlay_hide_fullscreen_checkbox.setEnabled(enabled)
        self._overlay_quick_controls_checkbox.setEnabled(enabled)
        self._overlay_reset_position_button.setEnabled(enabled)
        self._overlay_delete_button.setEnabled(enabled)
        self._overlay_use_hub_checkbox.setChecked(self._settings.overlay_use_unified_hub)
        self._overlay_individual_markers_checkbox.setChecked(
            self._settings.overlay_use_individual_markers
        )
        self._overlay_replace_markers_checkbox.setChecked(
            self._settings.overlay_replace_individual_markers
        )
        self._overlay_hub_always_visible_checkbox.setChecked(
            self._settings.overlay_hub_always_visible
        )
        self._overlay_hub_auto_hide_checkbox.setChecked(
            self._settings.overlay_hub_auto_hide
        )
        self._overlay_auto_snap_checkbox.setChecked(
            self._settings.overlay_auto_snap_to_taskbar
        )
        self._overlay_compact_mode_checkbox.setChecked(self._settings.overlay_compact_mode)
        self._overlay_marker_spacing_spin.setValue(self._settings.overlay_marker_spacing)
        self._overlay_hub_opacity_spin.setValue(self._settings.overlay_hub_opacity)
        if group is None:
            self._overlay_name_edit.clear()
            self._overlay_marker_width_spin.setValue(8)
            self._overlay_marker_height_spin.setValue(64)
            self._overlay_opacity_spin.setValue(0.9)
            self._overlay_corner_radius_spin.setValue(8)
            self._overlay_hover_delay_spin.setValue(1200)
            self._overlay_locked_position_checkbox.setChecked(False)
            self._overlay_hide_fullscreen_checkbox.setChecked(True)
            self._overlay_quick_controls_checkbox.setChecked(True)
            self._update_overlay_color_button("#2f81f7")
        else:
            self._overlay_name_edit.setText(group.name)
            self._overlay_marker_width_spin.setValue(group.marker_width)
            self._overlay_marker_height_spin.setValue(group.marker_height)
            self._overlay_opacity_spin.setValue(group.opacity)
            self._overlay_corner_radius_spin.setValue(group.corner_radius)
            self._overlay_hover_delay_spin.setValue(group.hover_delay_ms)
            self._overlay_locked_position_checkbox.setChecked(group.locked_position)
            self._overlay_hide_fullscreen_checkbox.setChecked(group.hide_during_fullscreen)
            self._overlay_quick_controls_checkbox.setChecked(group.show_quick_controls)
            self._update_overlay_color_button(group.color)
        self._update_overlay_preview(group)
        self._overlay_controls_syncing = False

    def _set_overlay_groups_enabled(self, enabled: bool) -> None:
        if self._settings_controls_syncing or self._overlay_controls_syncing:
            return
        self._settings.overlay_groups_enabled = enabled
        self._persist_overlay_groups("overlay groups enabled changed")

    def _create_overlay_group(self) -> None:
        group = self._prompt_create_overlay_group()
        if group is None:
            return
        self._selected_overlay_group_id = group.id
        self._populate_overlay_groups_list()
        self._persist_overlay_groups("overlay group created")
        self._show_status(tr("status.overlay_group_created"), kind=NotificationKind.OVERLAY)

    def _prompt_create_overlay_group(self) -> OverlayGroup | None:
        name, accepted = QInputDialog.getText(
            self,
            tr("dialog.create_overlay_group.title"),
            tr("dialog.create_overlay_group.message"),
        )
        if not accepted:
            return None
        try:
            return self._overlay_group_service.create_group(name)
        except ShelfyGAIError as exc:
            self._show_error(str(exc))
            return None

    def _choose_overlay_group_for_assignment(self) -> OverlayGroup | None:
        groups = list(self._overlay_group_service.groups())
        if not groups:
            answer = QMessageBox.question(
                self,
                tr("dialog.no_overlay_groups.title"),
                tr("dialog.no_overlay_groups.message"),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return None
            return self._prompt_create_overlay_group()

        dialog = OverlayGroupChoiceDialog(groups, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        selected_group_id = dialog.selected_group_id
        for group in groups:
            if group.id == selected_group_id:
                return group
        return None

    def _update_overlay_name(self) -> None:
        if self._overlay_controls_syncing:
            return
        group = self._selected_overlay_group()
        if group is None:
            return
        name = self._overlay_name_edit.text().strip()
        if name == group.name:
            return
        try:
            updated = self._overlay_group_service.rename_group(group.id, name)
        except ShelfyGAIError as exc:
            self._show_error(str(exc))
            self._sync_overlay_group_controls()
            return
        self._selected_overlay_group_id = updated.id
        self._populate_overlay_groups_list()
        self._persist_overlay_groups("overlay group renamed")
        self._show_status(tr("status.overlay_group_updated"), kind=NotificationKind.OVERLAY)

    def _update_overlay_numeric_settings(self) -> None:
        if self._overlay_controls_syncing:
            return
        group = self._selected_overlay_group()
        if group is None:
            return
        updated = self._overlay_group_service.update_group(
            group.id,
            marker_width=self._overlay_marker_width_spin.value(),
            marker_height=self._overlay_marker_height_spin.value(),
            opacity=self._overlay_opacity_spin.value(),
            corner_radius=self._overlay_corner_radius_spin.value(),
            hover_delay_ms=self._overlay_hover_delay_spin.value(),
        )
        self._update_overlay_preview(updated)
        self._persist_overlay_groups("overlay group numeric settings changed")

    def _update_overlay_boolean_settings(self) -> None:
        if self._overlay_controls_syncing:
            return
        group = self._selected_overlay_group()
        if group is None:
            return
        updated = self._overlay_group_service.update_group(
            group.id,
            locked_position=self._overlay_locked_position_checkbox.isChecked(),
            hide_during_fullscreen=self._overlay_hide_fullscreen_checkbox.isChecked(),
            show_quick_controls=self._overlay_quick_controls_checkbox.isChecked(),
        )
        self._update_overlay_preview(updated)
        self._persist_overlay_groups("overlay group behavior changed")

    def _update_overlay_display_settings(self) -> None:
        if self._settings_controls_syncing or self._overlay_controls_syncing:
            return
        self._settings.overlay_use_unified_hub = self._overlay_use_hub_checkbox.isChecked()
        self._settings.overlay_use_individual_markers = (
            self._overlay_individual_markers_checkbox.isChecked()
        )
        self._settings.overlay_replace_individual_markers = (
            self._overlay_replace_markers_checkbox.isChecked()
        )
        self._settings.overlay_hub_always_visible = (
            self._overlay_hub_always_visible_checkbox.isChecked()
        )
        self._settings.overlay_hub_auto_hide = (
            self._overlay_hub_auto_hide_checkbox.isChecked()
        )
        self._settings.overlay_auto_snap_to_taskbar = self._overlay_auto_snap_checkbox.isChecked()
        self._settings.overlay_compact_mode = self._overlay_compact_mode_checkbox.isChecked()
        self._settings.overlay_marker_spacing = self._overlay_marker_spacing_spin.value()
        self._settings.overlay_hub_opacity = self._overlay_hub_opacity_spin.value()
        self._settings_store.save(self._settings, reason="overlay display settings changed")
        self._sync_overlay_markers()
        self._update_overlay_preview()
        self._show_status(tr("status.overlay_group_updated"), kind=NotificationKind.OVERLAY)

    def _choose_overlay_color(self) -> None:
        group = self._selected_overlay_group()
        if group is None:
            return
        self._choose_overlay_color_for_group(group.id)

    def _choose_overlay_color_for_group(self, group_id: str) -> None:
        group = self._overlay_group_by_id(group_id)
        if group is None:
            return
        color = QColorDialog.getColor(QColor(group.color), self, tr("dialog.choose_color.title"))
        if not color.isValid():
            return
        updated = self._overlay_group_service.update_color(group.id, color.name())
        self._selected_overlay_group_id = updated.id
        self._populate_overlay_groups_list()
        self._persist_overlay_groups("overlay group color changed")
        self._show_status(tr("status.overlay_group_updated"), kind=NotificationKind.OVERLAY)

    def _reset_overlay_marker_position(self) -> None:
        group = self._selected_overlay_group()
        if group is None:
            return
        self._overlay_group_service.update_group(group.id, position_by_monitor={})
        self._persist_overlay_groups("overlay group marker position reset")
        self._show_status(
            tr("status.overlay_group_position_reset"),
            kind=NotificationKind.OVERLAY,
        )

    def _delete_selected_overlay_group(self) -> None:
        group = self._selected_overlay_group()
        if group is None:
            return
        answer = QMessageBox.question(
            self,
            tr("dialog.delete_overlay_group.title"),
            tr("dialog.delete_overlay_group.message", name=group.name),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._overlay_group_service.delete_group(group.id)
        except ShelfyGAIError as exc:
            self._show_error(str(exc))
            return
        self._selected_overlay_group_id = self._valid_overlay_group_id("")
        self._populate_overlay_groups_list()
        self._persist_overlay_groups("overlay group deleted")
        self._show_status(tr("status.overlay_group_deleted"), kind=NotificationKind.OVERLAY)

    def _update_overlay_color_button(self, color: str) -> None:
        self._overlay_color_button.setText(color)
        self._overlay_color_button.setStyleSheet(
            "QPushButton {"
            f"background: {color};"
            "border-radius: 8px;"
            "font-weight: 650;"
            "color: #ffffff;"
            "}"
        )

    def _persist_overlay_groups(self, reason: str) -> None:
        self._settings.overlay_groups_enabled = self._overlay_enabled_checkbox.isChecked()
        self._settings.selected_overlay_group_id = self._selected_overlay_group_id
        self._settings.overlay_use_unified_hub = self._overlay_use_hub_checkbox.isChecked()
        self._settings.overlay_use_individual_markers = (
            self._overlay_individual_markers_checkbox.isChecked()
        )
        self._settings.overlay_replace_individual_markers = (
            self._overlay_replace_markers_checkbox.isChecked()
        )
        self._settings.overlay_hub_always_visible = (
            self._overlay_hub_always_visible_checkbox.isChecked()
        )
        self._settings.overlay_hub_auto_hide = (
            self._overlay_hub_auto_hide_checkbox.isChecked()
        )
        self._settings.overlay_auto_snap_to_taskbar = self._overlay_auto_snap_checkbox.isChecked()
        self._settings.overlay_compact_mode = self._overlay_compact_mode_checkbox.isChecked()
        self._settings.overlay_marker_spacing = self._overlay_marker_spacing_spin.value()
        self._settings.overlay_hub_opacity = self._overlay_hub_opacity_spin.value()
        self._settings.overlay_groups = [
            asdict(group)
            for group in self._overlay_group_service.groups()
        ]
        self._settings_store.save(self._settings, reason=reason)
        self._sync_overlay_markers()

    def _overlay_group_by_id(self, group_id: str) -> OverlayGroup | None:
        for group in self._overlay_group_service.groups():
            if group.id == group_id:
                return group
        return None

    def _save_overlay_marker_position(
        self,
        group_id: str,
        monitor_id: str,
        x: int,
        y: int,
        edge: str,
    ) -> None:
        try:
            self._overlay_group_service.update_marker_position(
                group_id,
                monitor_id,
                x=x,
                y=y,
                edge=edge,
            )
        except ShelfyGAIError as exc:
            self._show_error(str(exc))
            return
        self._persist_overlay_groups("overlay marker position saved")
        LOGGER.info(
            "Overlay marker position saved: group_id=%s monitor=%s x=%s y=%s edge=%s",
            group_id,
            monitor_id,
            x,
            y,
            edge,
        )

    def _save_overlay_hub_position(
        self,
        monitor_id: str,
        x: int,
        y: int,
        edge: str,
    ) -> None:
        positions = {
            key: dict(value)
            for key, value in self._settings.overlay_hub_position_by_monitor.items()
        }
        positions[monitor_id] = {"x": x, "y": y, "edge": edge}
        self._settings.overlay_hub_position_by_monitor = positions
        self._settings_store.save(self._settings, reason="overlay hub position saved")
        self._sync_overlay_markers()
        LOGGER.info(
            "Overlay hub position saved: monitor=%s x=%s y=%s edge=%s",
            monitor_id,
            x,
            y,
            edge,
        )

    def _set_overlay_group_locked(self, group_id: str, locked: bool) -> None:
        try:
            self._overlay_group_service.update_group(group_id, locked_position=locked)
        except ShelfyGAIError as exc:
            self._show_error(str(exc))
            return
        if group_id == self._selected_overlay_group_id:
            self._sync_overlay_group_controls()
        self._persist_overlay_groups("overlay marker lock changed")

    def _show_overlay_group_settings(self, group_id: str) -> None:
        self._selected_overlay_group_id = self._valid_overlay_group_id(group_id)
        self._populate_overlay_groups_list()
        self._show_page(3)

    def _sync_overlay_markers(self) -> None:
        if not hasattr(self, "_overlay_marker_manager"):
            return
        self._overlay_marker_manager.sync(
            list(self._overlay_group_service.groups()),
            enabled=self._settings.overlay_groups_enabled,
            display_config=OverlayDisplayConfig(
                use_unified_hub=self._settings.overlay_use_unified_hub,
                use_individual_markers=self._settings.overlay_use_individual_markers,
                replace_individual_markers=(
                    self._settings.overlay_replace_individual_markers
                ),
                auto_snap_to_taskbar=self._settings.overlay_auto_snap_to_taskbar,
                compact_mode=self._settings.overlay_compact_mode,
                marker_spacing=self._settings.overlay_marker_spacing,
                hub_always_visible=self._settings.overlay_hub_always_visible,
                hub_auto_hide=self._settings.overlay_hub_auto_hide,
                hub_opacity=self._settings.overlay_hub_opacity,
                hub_position_by_monitor=self._settings.overlay_hub_position_by_monitor,
            ),
        )

    def _overlay_popup_items(self, group: OverlayGroup) -> list[OverlayPopupItem]:
        assigned_handles = set(group.assigned_window_ids)
        if not assigned_handles:
            return []
        popup_items: list[OverlayPopupItem] = []
        for item in self._shelf_service.shelved_items():
            if item.window.handle not in assigned_handles:
                continue
            title = item.window.title or tr("recovery.unknown_window", handle=item.window.handle)
            popup_items.append(
                OverlayPopupItem(
                    handle=item.window.handle,
                    app_name=item.window.process_name,
                    title=title,
                    icon=self._icon_provider.icon_for_window(item.window),
                )
            )
        return popup_items

    def _overlay_assigned_handles(self, group_id: str) -> list[int]:
        group = self._overlay_group_by_id(group_id)
        if group is None:
            return []
        return list(group.assigned_window_ids)

    def _overlay_hidden_handles(self, group_id: str) -> list[int]:
        assigned = set(self._overlay_assigned_handles(group_id))
        return [
            item.window.handle
            for item in self._shelf_service.shelved_items()
            if item.window.handle in assigned
        ]

    def _open_overlay_window(self, _group_id: str, handle: int) -> None:
        self._bring_handles_forward([handle])

    def _restore_overlay_window(self, _group_id: str, handle: int) -> None:
        self._restore_handles([handle])
        self._sync_overlay_markers()

    def _restore_overlay_group_windows(self, group_id: str) -> None:
        handles = self._overlay_hidden_handles(group_id)
        if not handles:
            self._show_status(
                tr("status.overlay_group_no_hidden_windows"),
                kind=NotificationKind.OVERLAY,
            )
            return
        self._restore_handles(handles)
        self._sync_overlay_markers()

    def _hide_overlay_group_windows(self, group_id: str) -> None:
        assigned = set(self._overlay_assigned_handles(group_id))
        hidden = set(self._overlay_hidden_handles(group_id))
        handles = [
            window.handle
            for window in self._shelf_service.available_windows()
            if window.handle in assigned and window.handle not in hidden
        ]
        if not handles:
            self._show_status(
                tr("status.overlay_group_no_open_windows"),
                kind=NotificationKind.OVERLAY,
            )
            return

        self._set_loading(True, tr("status.loading_hiding"))
        hidden_count = 0
        try:
            for handle in handles:
                self._shelf_service.shelve(
                    handle,
                    group_id=DEFAULT_GROUP_ID,
                    hide_options=HideOptions(),
                )
                hidden_count += 1
                self._sync_recovery_state("overlay group window hidden")
            self._persist_managed_state("overlay group windows hidden")
            self._refresh()
            self._show_status(
                tr("status.overlay_group_hidden_count", count=hidden_count),
                kind=NotificationKind.OVERLAY,
            )
        except ShelfyGAIError as exc:
            LOGGER.exception("Overlay group hide-all failed")
            self._show_error(str(exc))
        except Exception:
            LOGGER.exception("Unexpected overlay group hide-all failure")
            self._show_error(tr("error.shelve"))
        finally:
            self._set_loading(False)

    def _remove_overlay_window_from_group(self, group_id: str, handle: int) -> None:
        try:
            self._overlay_group_service.remove_window(group_id, handle)
        except ShelfyGAIError as exc:
            self._show_error(str(exc))
            return
        self._persist_overlay_groups("window removed from overlay group")
        self._show_status(tr("status.overlay_window_removed"), kind=NotificationKind.OVERLAY)

    def _open_from_overlay_popup(self) -> None:
        self._show_from_tray()
        self._show_page(3)

    def _rebuild_group_sidebar(self) -> None:
        self._clear_layout(self._groups_layout)
        self._group_buttons.clear()
        counts = self._shelf_service.group_counts()
        for group in self._shelf_service.groups():
            count = counts.get(group.id, 0)
            button = GroupButton(group.id, f"{self._group_display_name(group)} ({count})")
            button.setObjectName("GroupButton")
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
        self._populate_group_table(self._last_shelf_items)
        self._show_page(3)

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
        self._show_page(3)

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
        self._show_page(3)

    def _group_by_id(self, group_id: str) -> WindowGroup | None:
        for group in self._shelf_service.groups():
            if group.id == group_id:
                return group
        return None

    def _assign_window_to_group(self, handle: int, group_id: str) -> None:
        try:
            needs_unpin = self._is_pinned_handle(handle)
            if needs_unpin and not self._confirm_unpin_before_group_action(handle):
                return
            if self._shelf_service.assign_to_group(handle, group_id):
                self._selected_group_id = group_id
                self._persist_managed_state("window assigned to group")
                self._refresh()
                self._show_page(3)
                self._show_status(tr("status.moved_to_group"), kind=NotificationKind.OVERLAY)
        except ShelfyGAIError as exc:
            self._show_error(str(exc))

    def _confirm_unpin_before_group_action(self, handle: int) -> bool:
        answer = QMessageBox.question(
            self,
            tr("dialog.unpin_before_group.title"),
            tr("dialog.unpin_before_group.message"),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False
        if not self._shelf_service.unpin(handle):
            self._show_hide_pinned_message()
            return False
        self._sync_recovery_state("window unpinned before group action")
        return True

    def _restore_selected_group_windows(self) -> None:
        handles = self._selected_handles(self._group_table)
        if not handles:
            handles = [
                item.window.handle
                for item in self._last_shelf_items
                if item.group_id == self._selected_group_id
            ]
        self._restore_handles(handles)

    def _group_taskbar_placeholder(self) -> None:
        self._show_status(tr("status.group_taskbar_placeholder"))

    def _set_loading(self, enabled: bool, message: str = "") -> None:
        self._loading_label.setText(message)
        self._loading_label.setVisible(enabled)
        if enabled:
            self._show_status(message)

    def _request_refresh(self, _checked: bool = False, *, reason: str = "manual") -> None:
        self._pending_refresh_reason = reason
        self._refresh_debounce_timer.start()

    def _run_debounced_refresh(self) -> None:
        reason = self._pending_refresh_reason or "manual"
        self._pending_refresh_reason = None
        self._refresh(reason=reason)

    def _refresh(
        self,
        _checked: bool = False,
        *,
        reason: str = "manual",
        sync_overlays: bool = True,
    ) -> None:
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
            self._last_available_windows = available_windows
            available_ms = elapsed_ms(available_started)

            shelf_items = tuple(self._shelf_service.shelved_items())
            self._last_shelf_items = shelf_items
            pinned_items = tuple(self._shelf_service.pinned_items())
            self._last_pinned_items = pinned_items
            overlay_pruned = self._prune_stale_overlay_group_entries(
                available_windows,
                shelf_items,
            )

            populate_started = perf_counter()
            self._populate_available(available_windows)
            self._populate_shelf(self._shelf_table, shelf_items)
            self._populate_pinned(pinned_items)
            self._populate_group_table(shelf_items)
            self._rebuild_group_sidebar()
            self._update_selected_window_card()
            populate_ms = elapsed_ms(populate_started)

            available_count = self._available_table.rowCount()
            shelf_count = self._shelf_table.rowCount()
            self._show_status(
                tr(
                    "status.refresh_counts",
                    available=available_count,
                    managed=shelf_count,
                    pinned=len(pinned_items),
                )
            )
            self._sync_tray_actions()
            if sync_overlays:
                self._sync_overlay_markers()
            self._configure_window_state_refresh()
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
                overlay_pruned_count=overlay_pruned,
                available_ms=f"{available_ms:.1f}",
                prune_ms=f"{prune_ms:.1f}",
                populate_ms=f"{populate_ms:.1f}",
                icon_cache=icon_stats["cached"],
                icon_pending=icon_stats["pending"],
                icon_hits=icon_stats["hits"],
                icon_misses=icon_stats["misses"],
                icon_loaded=icon_stats["loaded"],
                icon_failed=icon_stats["failed"],
                overlay_marker_count=self._overlay_marker_manager.marker_count(),
                active_watcher_count=self._active_watcher_count(),
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
        self._refresh_window_states()
        self._update_selected_window_card()

    def _prune_stale_overlay_group_entries(
        self,
        available_windows: Sequence[WindowInfo],
        shelf_items: Sequence[ShelfItem],
    ) -> int:
        valid_handles = {window.handle for window in available_windows}
        valid_handles.update(item.window.handle for item in shelf_items)
        pruned = self._overlay_group_service.prune_stale_window_ids(valid_handles)
        if pruned:
            self._persist_overlay_groups("stale overlay group windows pruned")
        return pruned

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
        ordered_items = self._ordered_pinned_items(items)
        windows = [item.window for item in ordered_items]
        self._populate_table(self._pinned_table, windows)
        self._pinned_table.setSortingEnabled(False)
        self._apply_table_icons(self._pinned_table)
        self._update_table_empty_state(
            self._pinned_table,
            self._pinned_empty_label,
            tr("empty.pinned_windows"),
        )
        self._apply_pinned_z_order()
        self._configure_pinned_watcher()

    def _ordered_pinned_items(self, items: Sequence[PinnedItem]) -> list[PinnedItem]:
        self._pinned_order = ordered_pinned_handles(items, self._pinned_order)
        return ordered_pinned_items(items, self._pinned_order)

    def _populate_group_table(self, items: Sequence[ShelfItem]) -> None:
        windows = [
            item.window
            for item in items
            if item.group_id == self._selected_group_id
        ]
        self._populate_table(self._group_table, windows)
        self._apply_table_icons(self._group_table)
        group = self._group_by_id(self._selected_group_id)
        group_name = self._group_display_name(group)
        self._update_table_empty_state(
            self._group_table,
            self._group_empty_label,
            tr("empty.group_windows", group=group_name),
        )

    def _selected_available_window(self) -> WindowInfo | None:
        handles = self._selected_handles(self._available_table)
        if not handles:
            return None
        selected = handles[0]
        for window in self._last_available_windows:
            if window.handle == selected:
                return window
        return None

    def _update_selected_window_card(self) -> None:
        window = self._selected_available_window()
        if window is None:
            self._selected_window_icon.setPixmap(self._app_icon.pixmap(24, 24))
            self._selected_window_app.setText(tr("selected.none.title"))
            self._selected_window_title.setText(tr("selected.none.body"))
            self._selected_window_state.setText("")
            self._selected_window_hint.setVisible(True)
            self._selected_window_hint.setText(tr("selected.none.hint"))
            if self._selected_hide_button is not None:
                self._selected_hide_button.setEnabled(False)
                self._selected_hide_button.setToolTip("")
            if self._selected_overlay_group_button is not None:
                self._selected_overlay_group_button.setEnabled(False)
                self._selected_overlay_group_button.setToolTip("")
            return

        is_pinned = self._is_pinned_handle(window.handle)
        self._selected_window_icon.setPixmap(
            self._icon_pixmap(window, 24, self._selected_window_icon)
        )
        self._selected_window_app.setText(window.process_name)
        self._selected_window_title.setText(window.title)
        self._selected_window_state.setText(self._window_state_text(self._available_table, window))
        self._selected_window_hint.setVisible(False)
        if self._selected_hide_button is not None:
            self._selected_hide_button.setEnabled(not is_pinned)
            self._selected_hide_button.setToolTip(
                tr("error.hide_pinned_window") if is_pinned else tr("tooltip.hide_selected")
            )
        if self._selected_overlay_group_button is not None:
            self._selected_overlay_group_button.setEnabled(not is_pinned)
            self._selected_overlay_group_button.setToolTip(
                tr("error.hide_pinned_window")
                if is_pinned
                else tr("tooltip.add_to_overlay_group")
            )

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

    def _populate_table(self, table: QTableWidget, windows: Sequence[WindowInfo]) -> None:
        signature = tuple(
            (
                window.handle,
                window.process_name,
                window.title,
                window.process_id,
                window.executable_path or "",
            )
            for window in windows
        )
        if table.property("shelfygai_signature") == signature:
            return

        table.setUpdatesEnabled(False)
        table.setSortingEnabled(False)
        table.setRowCount(len(windows))
        table.setProperty("shelfygai_signature", signature)

        try:
            for row, window in enumerate(windows):
                state_key = self._window_state_key(table, window)
                values = [
                    "",
                    window.process_name,
                    window.title,
                    tr(state_key),
                ]
                filter_text = " ".join(
                    [
                        window.process_name,
                        window.title,
                        str(window.process_id),
                        f"0x{window.handle:08X}",
                    ]
                ).lower()
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setData(HANDLE_ROLE, window.handle)
                    item.setData(EXE_PATH_ROLE, window.executable_path or "")
                    item.setData(FILTER_ROLE, filter_text)
                    item.setData(STATE_KEY_ROLE, state_key)
                    item.setToolTip(value)
                    if column == 0:
                        item.setIcon(self._icon_for_window(window, queue=False))
                    if column == 3:
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignCenter
                        )
                    table.setItem(row, column, item)
        finally:
            table.setSortingEnabled(False)
            table.horizontalHeader().setSortIndicatorShown(False)
            table.setUpdatesEnabled(True)

    def _window_state_key(self, table: QTableWidget, window: WindowInfo) -> str:
        return self._state_key_for_table(
            table,
            handle=window.handle,
            is_minimized=window.is_minimized,
        )

    def _state_key_for_table(
        self,
        table: QTableWidget,
        *,
        handle: int,
        is_minimized: bool,
    ) -> str:
        if table in (self._shelf_table, self._group_table):
            return window_state_key(is_hidden=True)
        return window_state_key(
            is_pinned=table is self._pinned_table or self._is_pinned_handle(handle),
            is_minimized=is_minimized,
        )

    def _window_state_text(self, table: QTableWidget, window: WindowInfo) -> str:
        return tr(self._window_state_key(table, window))

    def _refresh_window_states(self) -> None:
        if not self._should_run_window_state_refresh():
            self._configure_window_state_refresh(False)
            return

        selected_handle = self._first_selected_handle(self._available_table)
        changed_selected = False
        missing_handles: set[int] = set()
        updated_states: dict[int, bool] = {}

        for row in range(self._available_table.rowCount()):
            item = self._available_table.item(row, 0)
            if item is None:
                continue
            handle = item.data(HANDLE_ROLE)
            if not isinstance(handle, int):
                continue
            try:
                is_minimized = self._shelf_service.window_is_minimized(handle)
            except ShelfyGAIError:
                missing_handles.add(handle)
                continue
            except Exception:
                LOGGER.debug(
                    "Could not refresh lightweight window state: hwnd=%s",
                    handle,
                    exc_info=True,
                )
                missing_handles.add(handle)
                continue

            updated_states[handle] = is_minimized
            new_key = self._state_key_for_table(
                self._available_table,
                handle=handle,
                is_minimized=is_minimized,
            )
            if self._update_table_row_state(self._available_table, row, new_key):
                changed_selected = changed_selected or handle == selected_handle

        if updated_states:
            self._last_available_windows = tuple(
                replace(window, is_minimized=updated_states.get(window.handle, window.is_minimized))
                for window in self._last_available_windows
            )

        if changed_selected:
            self._update_selected_window_card()

        if missing_handles:
            LOGGER.debug(
                "Scheduling full refresh after missing lightweight state handles: hwnds=%s",
                sorted(missing_handles),
            )
            self._request_refresh(reason="window state cleanup")

    def _update_table_row_state(
        self,
        table: QTableWidget,
        row: int,
        state_key: str,
    ) -> bool:
        item = table.item(row, 3)
        if item is None:
            return False
        previous_key = item.data(STATE_KEY_ROLE)
        if previous_key == state_key:
            return False
        handle_item = table.item(row, 0)
        handle = handle_item.data(HANDLE_ROLE) if handle_item is not None else None
        previous_text = item.text()
        new_text = tr(state_key)
        item.setText(new_text)
        item.setToolTip(new_text)
        item.setData(STATE_KEY_ROLE, state_key)
        LOGGER.info(
            "Window state changed: hwnd=%s previous_state=%s new_state=%s",
            handle,
            previous_text,
            new_text,
        )
        return True

    def _refresh_table_state_translations(self) -> None:
        for table in (
            self._available_table,
            self._shelf_table,
            self._pinned_table,
            self._group_table,
        ):
            for row in range(table.rowCount()):
                item = table.item(row, 3)
                if item is None:
                    continue
                state_key = item.data(STATE_KEY_ROLE)
                if isinstance(state_key, str):
                    text = tr(state_key)
                    item.setText(text)
                    item.setToolTip(text)

    def _refresh_cached_icons(self) -> None:
        self._apply_table_icons(self._available_table, visible_only=True)
        self._apply_table_icons(self._shelf_table)
        self._apply_table_icons(self._pinned_table)
        self._apply_table_icons(self._group_table)
        self._update_selected_window_card()
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

    def _schedule_open_windows_filter(self) -> None:
        self._open_windows_filter_timer.start()

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
        self._update_selected_window_card()

    def _update_table_empty_state(
        self,
        table: QTableWidget,
        label: QWidget,
        message: str,
        *,
        visible_count: int | None = None,
    ) -> None:
        label.setText(message)
        if visible_count is None:
            visible_count = self._visible_row_count(table)
        has_rows = visible_count > 0
        table.setVisible(has_rows)
        label.setVisible(not has_rows)

    def _refresh_empty_states(self) -> None:
        self._apply_open_windows_filter()
        self._update_table_empty_state(
            self._shelf_table,
            self._shelf_empty_label,
            tr("empty.managed_windows"),
        )
        self._update_table_empty_state(
            self._pinned_table,
            self._pinned_empty_label,
            tr("empty.pinned_windows"),
        )
        group = self._group_by_id(self._selected_group_id)
        self._update_table_empty_state(
            self._group_table,
            self._group_empty_label,
            tr("empty.group_windows", group=self._group_display_name(group)),
        )
        self._overlay_empty_label.setText(tr("empty.overlay_groups"))

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
        self._show_status(
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

    def _set_notification_settings(self, _enabled: bool) -> None:
        if self._settings_controls_syncing:
            return
        self._settings.notifications_enabled = self._notifications_enabled_checkbox.isChecked()
        self._settings.show_tray_notifications = self._tray_notifications_checkbox.isChecked()
        self._settings.show_overlay_notifications = (
            self._overlay_notifications_checkbox.isChecked()
        )
        self._settings.show_restore_notifications = (
            self._restore_notifications_checkbox.isChecked()
        )
        self._settings.show_pin_unpin_notifications = self._pin_notifications_checkbox.isChecked()
        self._settings.silent_mode = self._silent_mode_checkbox.isChecked()
        self._sync_notification_control_state()
        self._save_runtime_settings("notification settings changed")

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

    def _configure_window_state_refresh(self, enabled: bool | None = None) -> None:
        should_run = self._should_run_window_state_refresh() if enabled is None else enabled
        if should_run:
            self._window_state_refresh_timer.start()
        else:
            self._window_state_refresh_timer.stop()

    def _should_run_open_windows_auto_refresh(self) -> bool:
        return (
            self._settings.open_windows_auto_refresh
            and self.isVisible()
            and self._stack.currentIndex() == 0
            and not self._is_quitting
        )

    def _should_run_window_state_refresh(self) -> bool:
        return (
            self.isVisible()
            and self._stack.currentIndex() == 0
            and self._available_table.rowCount() > 0
            and not self._is_quitting
        )

    def _configure_pinned_watcher(self) -> None:
        interval = max(100, min(self._settings.pinned_watcher_interval_ms, 10_000))
        self._pinned_watcher_timer.setInterval(interval)
        should_run = (
            self._settings.prevent_minimize_watcher_enabled
            and self._shelf_service.has_prevent_minimize_pinned_windows()
        )
        if should_run:
            self._pinned_watcher_timer.start()
        else:
            self._pinned_watcher_timer.stop()

    def _active_watcher_count(self) -> int:
        count = 0
        if self._open_windows_refresh_timer.isActive():
            count += 1
        if self._open_windows_filter_timer.isActive():
            count += 1
        if self._window_state_refresh_timer.isActive():
            count += 1
        if self._refresh_debounce_timer.isActive():
            count += 1
        if self._pinned_watcher_timer.isActive():
            count += 1
        if self._overlay_marker_manager.fullscreen_watcher_active():
            count += 1
        if self._icon_provider.cache_stats()["timer_active"]:
            count += 1
        return count

    def _check_pinned_windows(self) -> None:
        try:
            restored, removed = self._shelf_service.enforce_pinned_windows()
        except Exception:
            LOGGER.exception("Pinned-window watcher failed")
            self._show_status(tr("error.pinned_watcher"), kind=NotificationKind.PIN)
            return
        if removed:
            self._refresh(reason="pinned watcher")
            self._show_status(
                tr("status.pinned_removed_closed", count=removed),
                kind=NotificationKind.PIN,
            )
        elif restored:
            self._show_status(
                tr("status.pinned_restored", count=restored),
                kind=NotificationKind.PIN,
            )
        self._configure_pinned_watcher()

    def _selected_handles(self, table: QTableWidget) -> list[int]:
        handles = set()
        for item in table.selectedItems():
            handle = item.data(HANDLE_ROLE)
            if isinstance(handle, int):
                handles.add(handle)
        return sorted(handles)

    def _first_selected_handle(self, table: QTableWidget) -> int | None:
        selection_model = table.selectionModel()
        if selection_model is None:
            return None
        rows = sorted(index.row() for index in selection_model.selectedRows())
        for row in rows:
            item = table.item(row, 0)
            if item is None:
                continue
            handle = item.data(HANDLE_ROLE)
            if isinstance(handle, int):
                return handle
        return None

    def _select_table_handle(self, table: QTableWidget, handle: int) -> None:
        table.clearSelection()
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item is not None and item.data(HANDLE_ROLE) == handle:
                table.selectRow(row)
                break

    def _pinned_handle_set(self) -> set[int]:
        return {item.window.handle for item in self._shelf_service.pinned_items()}

    def _is_pinned_handle(self, handle: int) -> bool:
        return handle in self._pinned_handle_set()

    def _handles_include_pinned(self, handles: Sequence[int]) -> bool:
        pinned_handles = self._pinned_handle_set()
        return any(handle in pinned_handles for handle in handles)

    def _show_hide_pinned_message(self) -> None:
        message = tr("error.hide_pinned_window")
        self._show_status(message, kind=NotificationKind.PIN)
        self._tray_notify(
            tr("error.notification.title"),
            message,
            kind=NotificationKind.PIN,
            icon=QSystemTrayIcon.MessageIcon.Warning,
            duration_ms=5_000,
        )

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
            pin_action = menu.addAction(tr("action.pin_window"))
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
            diagnostics_action = menu.addAction(tr("action.copy_pin_diagnostics"))
            diagnostics_action.triggered.connect(
                lambda _checked=False: self._copy_pin_diagnostics(handles)
            )
            hide_action = menu.addAction(tr("action.hide_selected"))
            hide_blocked = self._handles_include_pinned(handles)
            hide_action.setEnabled(not hide_blocked)
            if hide_blocked:
                hide_action.setToolTip(tr("error.hide_pinned_window"))
            hide_action.triggered.connect(
                lambda _checked=False: self._shelve_handles(
                    handles,
                    confirm=self._confirm_checkbox.isChecked(),
                )
            )
            overlay_group_action = menu.addAction(tr("action.add_to_overlay_group"))
            overlay_group_action.setEnabled(not hide_blocked)
            if hide_blocked:
                overlay_group_action.setToolTip(tr("error.hide_pinned_window"))
            overlay_group_action.triggered.connect(
                lambda _checked=False: self._add_handles_to_overlay_group(handles)
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
                lambda _checked=False: self._bring_pinned_handles_to_front(handles)
            )
            diagnostics_action = menu.addAction(tr("action.copy_pin_diagnostics"))
            diagnostics_action.triggered.connect(
                lambda _checked=False: self._copy_pin_diagnostics(handles)
            )
        elif table in (self._shelf_table, self._group_table):
            restore_action = menu.addAction(tr("action.restore_selected"))
            restore_action.triggered.connect(
                lambda _checked=False: self._restore_handles(handles)
            )
            bring_action = menu.addAction(tr("action.bring_to_front"))
            bring_action.triggered.connect(
                lambda _checked=False: self._bring_handles_forward(handles)
            )
            move_overlay_action = menu.addAction(tr("action.move_to_overlay_group"))
            move_overlay_action.triggered.connect(
                lambda _checked=False: self._move_hidden_handles_to_overlay_group(handles)
            )
            remove_overlay_action = menu.addAction(tr("action.remove_from_overlay_group"))
            remove_overlay_action.triggered.connect(
                lambda _checked=False: self._remove_handles_from_overlay_groups(handles)
            )

        if menu.actions():
            menu.exec(table.viewport().mapToGlobal(position))

    def _pin_selected(self) -> None:
        handles = self._selected_handles(self._available_table)
        if not handles:
            self._show_status(tr("status.select_open_pin"), kind=NotificationKind.PIN)
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
                self._sync_recovery_state("window pinned")
            self._refresh(reason="windows pinned")
            self._show_status(
                tr("status.pinned_count", count=pinned_count),
                kind=NotificationKind.PIN,
            )
            self._tray_notify(
                tr("tray.notification.pinned.title"),
                tr("tray.notification.pinned.message", count=pinned_count),
                kind=NotificationKind.PIN,
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
            self._show_status(tr("status.select_pinned_unpin"), kind=NotificationKind.PIN)
            return
        self._unpin_handles(handles)

    def _move_pinned_selection(self, direction: int) -> None:
        handle = self._first_selected_handle(self._pinned_table)
        if handle is None:
            self._show_status(tr("status.select_pinned_unpin"), kind=NotificationKind.PIN)
            return
        reordered = move_handle(self._pinned_order, handle, direction)
        if reordered == self._pinned_order:
            return
        self._pinned_order = reordered
        self._populate_pinned(self._last_pinned_items)
        self._select_table_handle(self._pinned_table, handle)
        self._show_status(tr("status.pinned_order_changed"), kind=NotificationKind.PIN)

    def _bring_pinned_selection_to_front(self) -> None:
        handle = self._first_selected_handle(self._pinned_table)
        if handle is None:
            self._show_status(tr("status.select_pinned_unpin"), kind=NotificationKind.PIN)
            return
        self._bring_pinned_handles_to_front([handle])

    def _bring_pinned_handles_to_front(self, handles: list[int]) -> None:
        pinned_handles = [handle for handle in handles if handle in self._pinned_order]
        if not pinned_handles:
            self._show_status(tr("status.select_pinned_unpin"), kind=NotificationKind.PIN)
            return
        handle = pinned_handles[0]
        self._pinned_order = bring_handle_to_front(self._pinned_order, handle)
        self._populate_pinned(self._last_pinned_items)
        self._select_table_handle(self._pinned_table, handle)
        self._bring_handles_forward([handle])
        self._show_status(tr("status.pinned_order_changed"), kind=NotificationKind.PIN)

    def _apply_pinned_z_order(self) -> None:
        if not self._pinned_order:
            return
        try:
            applied = self._shelf_service.apply_pinned_order(self._pinned_order)
            LOGGER.debug("Applied pinned z-order bottom_to_top=%s", list(applied))
        except Exception:
            LOGGER.exception("Could not apply pinned z-order")

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
            self._sync_recovery_state("windows unpinned")
            self._refresh(reason="windows unpinned")
            self._configure_pinned_watcher()
            self._show_status(
                self._unpin_summary(unpinned, skipped),
                kind=NotificationKind.PIN,
            )
            self._tray_notify(
                tr("tray.notification.unpinned.title"),
                self._unpin_summary(unpinned, skipped),
                kind=NotificationKind.PIN,
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

    def _unpin_all(
        self,
        _checked: bool = False,
        *,
        confirm: bool = True,
    ) -> None:
        if not self._shelf_service.has_pinned_windows():
            self._show_status(tr("status.no_pinned_unpin"), kind=NotificationKind.PIN)
            return

        if confirm:
            answer = QMessageBox.question(
                self,
                tr("dialog.unpin_all.title"),
                tr("dialog.unpin_all.message"),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self._set_loading(True, tr("status.loading_unpinning"))
        pinned_before = [item.window.handle for item in self._shelf_service.pinned_items()]
        LOGGER.info(
            "Unpin all requested from UI: pinned_count=%s hwnds=%s",
            len(pinned_before),
            pinned_before,
        )
        try:
            unpinned, skipped = self._shelf_service.unpin_all()
            pinned_after = {item.window.handle for item in self._shelf_service.pinned_items()}
            unpinned_handles = [
                handle for handle in pinned_before if handle not in pinned_after
            ]
            LOGGER.info(
                "Unpin all completed from UI: unpinned=%s skipped=%s "
                "unpinned_hwnds=%s",
                unpinned,
                skipped,
                unpinned_handles,
            )
            self._pinned_order = [
                handle for handle in self._pinned_order if handle in pinned_after
            ]
            self._configure_pinned_watcher()
            self._sync_recovery_state("all windows unpinned")
            self._refresh(reason="all windows unpinned")
            self._sync_tray_actions()
            message = self._unpin_summary(unpinned, skipped)
            self._show_status(message, kind=NotificationKind.PIN)
            self._tray_notify(
                tr("tray.notification.unpinned.title"),
                message,
                kind=NotificationKind.PIN,
            )
        except ShelfyGAIError as exc:
            LOGGER.exception("Unpin all failed")
            self._show_error(str(exc))
        except Exception:
            LOGGER.exception("Unexpected unpin-all failure")
            self._show_error(tr("error.unpin_all"))
        finally:
            self._set_loading(False)

    def _copy_pin_diagnostics(self, handles: list[int]) -> None:
        if not handles:
            return
        try:
            diagnostics = [
                self._shelf_service.pin_diagnostics(handle)
                for handle in handles
            ]
            clipboard = QApplication.clipboard()
            clipboard.setText("\n\n---\n\n".join(diagnostics))
            self._show_status(
                tr("status.pin_diagnostics_copied", count=len(handles))
            )
        except Exception:
            LOGGER.exception("Could not copy pin diagnostics")
            self._show_error(tr("error.pin_diagnostics"))

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
            self._sync_recovery_state("pinned prevent-minimize changed")
            self._refresh(reason="pinned prevent-minimize changed")
            status_key = (
                "status.prevent_minimize_enabled"
                if enabled
                else "status.prevent_minimize_disabled"
            )
            self._show_status(tr(status_key, count=updated), kind=NotificationKind.PIN)
        except ShelfyGAIError as exc:
            LOGGER.exception("Prevent-minimize update failed")
            self._show_error(str(exc))
        except Exception:
            LOGGER.exception("Unexpected prevent-minimize update failure")
            self._show_error(tr("error.prevent_minimize"))

    def _add_selected_to_overlay_group(self) -> None:
        handles = self._selected_handles(self._available_table)
        if not handles:
            self._show_status(tr("status.select_open_hide"))
            return
        self._add_handles_to_overlay_group(handles)

    def _add_handles_to_overlay_group(self, handles: list[int]) -> int:
        if not handles:
            return 0
        if self._handles_include_pinned(handles):
            self._show_hide_pinned_message()
            return 0
        group = self._choose_overlay_group_for_assignment()
        if group is None:
            return 0
        self._enable_overlay_groups_for_assignment()

        hide_options = HideOptions(
            hide_taskbar=True,
            hide_alt_tab=self._hide_alt_tab_checkbox.isChecked(),
            hide_tray=False,
        )
        assigned_count = 0
        self._set_loading(True, tr("status.loading_hiding"))
        try:
            for handle in handles:
                self._shelf_service.shelve(
                    handle,
                    group_id=DEFAULT_GROUP_ID,
                    hide_options=hide_options,
                )
                self._overlay_group_service.assign_window(group.id, handle)
                assigned_count += 1
                self._sync_recovery_state("window added to overlay group")
            self._selected_overlay_group_id = group.id
            self._persist_managed_state("windows added to overlay group")
            self._refresh(reason="windows added to overlay group")
            self._show_status(
                tr("status.overlay_assigned_count", count=assigned_count),
                kind=NotificationKind.OVERLAY,
            )
            return assigned_count
        except ShelfyGAIError as exc:
            LOGGER.exception("Add to overlay group failed")
            if assigned_count:
                self._persist_managed_state("partial overlay assignment failure")
                self._refresh(reason="partial overlay assignment failure")
            self._show_error(str(exc))
        except Exception:
            LOGGER.exception("Unexpected add to overlay group failure")
            if assigned_count:
                self._persist_managed_state("partial overlay assignment failure")
                self._refresh(reason="partial overlay assignment failure")
            self._show_error(tr("error.shelve"))
        finally:
            self._set_loading(False)
        return assigned_count

    def _move_selected_hidden_to_overlay_group(self) -> None:
        handles = self._selected_handles(self._shelf_table)
        self._move_hidden_handles_to_overlay_group(handles)

    def _move_hidden_handles_to_overlay_group(self, handles: list[int]) -> int:
        if not handles:
            self._show_status(
                tr("status.select_managed_restore"),
                kind=NotificationKind.OVERLAY,
            )
            return 0
        group = self._choose_overlay_group_for_assignment()
        if group is None:
            return 0
        self._enable_overlay_groups_for_assignment()
        for handle in handles:
            self._overlay_group_service.assign_window(group.id, handle)
        self._selected_overlay_group_id = group.id
        self._persist_overlay_groups("hidden windows moved to overlay group")
        self._show_status(
            tr("status.overlay_assigned_count", count=len(handles)),
            kind=NotificationKind.OVERLAY,
        )
        return len(handles)

    def _remove_selected_from_overlay_group(self) -> None:
        handles = self._selected_handles(self._shelf_table)
        self._remove_handles_from_overlay_groups(handles)

    def _remove_handles_from_overlay_groups(self, handles: list[int]) -> int:
        if not handles:
            self._show_status(
                tr("status.select_managed_restore"),
                kind=NotificationKind.OVERLAY,
            )
            return 0
        removed = 0
        for handle in handles:
            removed += self._overlay_group_service.remove_window_from_all(handle)
        if removed:
            self._persist_overlay_groups("windows removed from overlay groups")
            self._show_status(
                tr("status.overlay_removed_count", count=removed),
                kind=NotificationKind.OVERLAY,
            )
        else:
            self._show_status(tr("status.overlay_not_assigned"), kind=NotificationKind.OVERLAY)
        return removed

    def _enable_overlay_groups_for_assignment(self) -> None:
        if self._settings.overlay_groups_enabled:
            return
        self._settings.overlay_groups_enabled = True
        previous = self._overlay_enabled_checkbox.blockSignals(True)
        self._overlay_enabled_checkbox.setChecked(True)
        self._overlay_enabled_checkbox.blockSignals(previous)

    def _shelve_selected(self) -> None:
        handles = self._selected_handles(self._available_table)
        if not handles:
            self._show_status(tr("status.select_open_hide"))
            return
        if self._handles_include_pinned(handles):
            self._show_hide_pinned_message()
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
        if self._handles_include_pinned(handles):
            self._show_hide_pinned_message()
            return 0

        hide_options = self._selected_hide_options()
        if not hide_options.has_any_target:
            self._show_error(tr("error.hide_options_empty"))
            return 0

        limitation = self._hide_options_limitation_message(hide_options)
        if confirm or limitation:
            message = self._hide_confirmation_message(len(handles), hide_options)
            answer = QMessageBox.question(
                self,
                tr("dialog.hide_windows.title"),
                message,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return 0

        self._set_loading(True, tr("status.loading_hiding"))
        hidden_count = 0
        try:
            for handle in handles:
                self._shelf_service.shelve(
                    handle,
                    group_id=self._selected_group_id,
                    hide_options=hide_options,
                )
                hidden_count += 1
                self._sync_recovery_state("window hidden")
            self._persist_managed_state(reason)
            self._refresh()
            self._show_status(
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

    def _selected_hide_options(self) -> HideOptions:
        return HideOptions(
            hide_taskbar=self._hide_taskbar_checkbox.isChecked(),
            hide_alt_tab=self._hide_alt_tab_checkbox.isChecked(),
            hide_tray=self._hide_tray_checkbox.isChecked(),
        )

    def _hide_confirmation_message(self, count: int, options: HideOptions) -> str:
        return hide_confirmation_message(count, options)

    def _hide_options_limitation_message(self, options: HideOptions) -> str:
        return hide_limitation_message(options)

    def _quick_hide_from_hotkey(self) -> None:
        handles = self._selected_handles(self._available_table) if self.isActiveWindow() else []
        if handles:
            self._shelve_handles(handles, confirm=False, reason="windows hidden by hotkey")
            return

        try:
            item = self._shelf_service.shelve_foreground(
                group_id=self._selected_group_id,
                hide_options=HideOptions(),
            )
            self._sync_recovery_state("foreground window hidden by hotkey")
            self._persist_managed_state("foreground window hidden by hotkey")
            self._refresh()
            self._show_status(tr("status.hidden_title", title=item.window.title))
            self._tray_notify(
                tr("tray.notification.window_hidden.title"),
                tr("tray.notification.window_hidden.message", title=item.window.title),
            )
        except ShelfyGAIError as exc:
            LOGGER.info("Global quick-hide hotkey did not hide a window: %s", exc)
            self._sync_recovery_state("quick-hide hotkey failed")
            self._show_status(str(exc))
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
                self._show_status(tr("status.last_restored"), kind=NotificationKind.RESTORE)
                self._tray_notify(
                    tr("tray.notification.window_restored.title"),
                    tr("tray.notification.window_restored.message"),
                    kind=NotificationKind.RESTORE,
                )
            else:
                self._show_status(
                    tr("status.no_managed_restore"),
                    kind=NotificationKind.RESTORE,
                )
        except ShelfyGAIError as exc:
            LOGGER.exception("Restore-last hotkey failed")
            self._show_error(str(exc))
        except Exception:
            LOGGER.exception("Unexpected restore-last hotkey failure")
            self._show_error(tr("error.restore_last"))

    def _toggle_visibility_from_hotkey(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide()
            self._show_status(tr("status.hidden_app"))
            LOGGER.info("Main window hidden by global hotkey")
        else:
            self._show_from_tray()
            self._show_status(tr("status.shown"))
            LOGGER.info("Main window shown by global hotkey")

    def _toggle_overlay_hub_from_hotkey(self) -> None:
        self._sync_overlay_markers()
        if self._overlay_marker_manager.toggle_hub_from_hotkey():
            self._show_status(tr("status.overlay_hub_toggled"))
            LOGGER.info("Overlay hub toggled by global hotkey")
            return
        self._show_status(tr("status.overlay_hub_unavailable"))
        LOGGER.info("Overlay hub hotkey ignored because hub is unavailable")

    def _pin_unpin_focused_from_hotkey(self) -> None:
        try:
            result, item = self._shelf_service.toggle_pin_foreground(
                allow_own_window=self._settings.allow_pin_shelfygai_window
            )
            self._sync_recovery_state("focused window pin toggled by hotkey")
            self._refresh(reason="focused window pin toggled by hotkey")
            if result == "pinned" and item is not None:
                self._show_status(
                    tr("status.hotkey_focused_pinned", title=item.window.title),
                    kind=NotificationKind.PIN,
                )
                self._tray_notify(
                    tr("tray.notification.pinned.title"),
                    tr("status.hotkey_focused_pinned", title=item.window.title),
                    kind=NotificationKind.PIN,
                )
            elif result == "unpinned":
                self._show_status(
                    tr("status.hotkey_focused_unpinned"),
                    kind=NotificationKind.PIN,
                )
                self._tray_notify(
                    tr("tray.notification.unpinned.title"),
                    tr("status.hotkey_focused_unpinned"),
                    kind=NotificationKind.PIN,
                )
            else:
                self._show_status(tr("status.no_pinned_unpin"), kind=NotificationKind.PIN)
        except ShelfyGAIError as exc:
            LOGGER.info("Pin/unpin focused hotkey did not change a window: %s", exc)
            self._show_status(str(exc), kind=NotificationKind.PIN)
        except Exception:
            LOGGER.exception("Unexpected pin/unpin focused hotkey failure")
            self._show_error(tr("error.pin"))

    def _show_quick_switcher_from_hotkey(self) -> None:
        try:
            self._show_quick_switcher()
        except Exception:
            LOGGER.exception("Unexpected quick switcher hotkey failure")
            self._show_error(tr("error.quick_switcher"))

    def _show_quick_switcher(self) -> None:
        pruned_count = self._shelf_service.prune_missing()
        if pruned_count:
            self._persist_managed_state("closed windows pruned before quick switcher")
        shelf_items = tuple(self._shelf_service.shelved_items())
        pinned_items = tuple(self._shelf_service.pinned_items())
        self._last_shelf_items = shelf_items
        self._last_pinned_items = pinned_items
        self._quick_switcher.show_switcher(
            self._quick_switcher_items(shelf_items, pinned_items)
        )
        LOGGER.info(
            "Quick hidden-window switcher opened: hidden=%s pinned=%s overlay_groups=%s",
            len(shelf_items),
            len(pinned_items),
            len(list(self._overlay_group_service.groups())),
        )

    def _quick_switcher_items(
        self,
        shelf_items: Sequence[ShelfItem],
        pinned_items: Sequence[PinnedItem],
    ) -> list[SwitcherItem]:
        items: list[SwitcherItem] = []
        group_names = {
            group.id: self._group_display_name(group)
            for group in self._shelf_service.groups()
        }
        overlay_groups = list(self._overlay_group_service.groups())
        overlay_by_handle = self._overlay_group_names_by_handle(overlay_groups)
        for shelf_item in sorted(
            shelf_items,
            key=lambda item: item.hidden_at,
            reverse=True,
        ):
            window = shelf_item.window
            group_label = overlay_by_handle.get(window.handle) or group_names.get(
                shelf_item.group_id,
                tr("group.ungrouped"),
            )
            items.append(
                SwitcherItem(
                    kind=SWITCHER_KIND_HIDDEN,
                    title=window.title or tr("recovery.unknown_window", handle=window.handle),
                    subtitle=tr(
                        "switcher.item.hidden.subtitle",
                        app=window.process_name,
                        group=group_label,
                    ),
                    handle=window.handle,
                    badge=tr("switcher.badge.hidden"),
                    icon=self._icon_provider.icon_for_window(window),
                )
            )
        hidden_handles = {item.window.handle for item in shelf_items}
        for group in overlay_groups:
            count = sum(
                1
                for handle in group.assigned_window_ids
                if handle in hidden_handles
            )
            items.append(
                SwitcherItem(
                    kind=SWITCHER_KIND_OVERLAY_GROUP,
                    title=group.name,
                    subtitle=tr(
                        "switcher.item.overlay_group.subtitle",
                        count=count,
                    ),
                    group_id=group.id,
                    badge=tr("switcher.badge.overlay_group"),
                    icon=self._icon_provider.folder_icon(),
                )
            )
        for pinned_item in self._ordered_pinned_items(pinned_items):
            window = pinned_item.window
            items.append(
                SwitcherItem(
                    kind=SWITCHER_KIND_PINNED,
                    title=window.title or tr("recovery.unknown_window", handle=window.handle),
                    subtitle=tr(
                        "switcher.item.pinned.subtitle",
                        app=window.process_name,
                    ),
                    handle=window.handle,
                    badge=tr("switcher.badge.pinned"),
                    icon=self._icon_provider.icon_for_window(window),
                )
            )
        return items

    def _overlay_group_names_by_handle(
        self,
        groups: Sequence[OverlayGroup],
    ) -> dict[int, str]:
        names: dict[int, str] = {}
        for group in groups:
            for handle in group.assigned_window_ids:
                names[handle] = group.name
        return names

    def _activate_switcher_item(self, item: object) -> None:
        if not isinstance(item, SwitcherItem):
            return
        if item.kind == SWITCHER_KIND_HIDDEN and item.handle is not None:
            self._restore_handles([item.handle])
            return
        if item.kind == SWITCHER_KIND_PINNED and item.handle is not None:
            self._bring_pinned_handles_to_front([item.handle])
            return
        if item.kind == SWITCHER_KIND_OVERLAY_GROUP and item.group_id is not None:
            self._open_overlay_group_from_switcher(item.group_id)

    def _open_overlay_group_from_switcher(self, group_id: str) -> None:
        self._sync_overlay_markers()
        if self._overlay_marker_manager.open_group_from_switcher(group_id):
            self._show_status(
                tr("switcher.status.overlay_group_opened"),
                kind=NotificationKind.OVERLAY,
            )
            return
        self._show_status(
            tr("switcher.status.overlay_group_unavailable"),
            kind=NotificationKind.OVERLAY,
        )

    def _restore_selected(self, table: QTableWidget) -> None:
        handles = self._selected_handles(table)
        self._restore_handles(handles)

    def _restore_handles(self, handles: list[int]) -> None:
        if not handles:
            self._show_status(
                tr("status.select_managed_restore"),
                kind=NotificationKind.RESTORE,
            )
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
            self._show_status(
                self._restore_summary(restored, skipped),
                kind=NotificationKind.RESTORE,
            )
            self._tray_notify(
                tr("tray.notification.restore.title"),
                self._restore_summary(restored, skipped),
                kind=NotificationKind.RESTORE,
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
            self._show_status(
                tr("status.no_managed_restore"),
                kind=NotificationKind.RESTORE,
            )
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
            self._show_status(
                self._restore_summary(restored, skipped),
                kind=NotificationKind.RESTORE,
            )
            self._tray_notify(
                tr("tray.notification.restore.title"),
                self._restore_summary(restored, skipped),
                kind=NotificationKind.RESTORE,
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

    def _reset_everything(
        self,
        _checked: bool = False,
        *,
        confirm: bool = True,
    ) -> None:
        if confirm:
            answer = QMessageBox.question(
                self,
                tr("dialog.reset_everything.title"),
                tr("dialog.reset_everything.message"),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self._set_loading(True, tr("status.loading_resetting"))
        try:
            result = self._perform_global_reset()
            self._refresh(reason="global reset", sync_overlays=False)
            self._sync_tray_actions()
            message = tr(
                "status.reset_complete",
                restored=result["restored"],
                unpinned=result["unpinned"],
            )
            self._show_status(message, kind=NotificationKind.RESTORE)
            self._tray_notify(
                tr("tray.notification.reset.title"),
                message,
                kind=NotificationKind.RESTORE,
            )
        except Exception:
            LOGGER.exception("Unexpected global emergency reset failure")
            self._show_error(tr("error.reset_everything"))
        finally:
            self._set_loading(False)

    def _perform_global_reset(self) -> dict[str, int]:
        LOGGER.info("Global emergency reset requested")

        unpinned = 0
        unpin_skipped = 0
        try:
            unpinned, unpin_skipped = self._shelf_service.unpin_all()
        except Exception:
            LOGGER.exception("Global reset could not unpin all windows")

        restored = 0
        restore_skipped = 0
        try:
            restored, restore_skipped = self._shelf_service.restore_all(focus=False)
        except Exception:
            LOGGER.exception("Global reset could not restore all hidden windows")

        overlay_assignments_removed = 0
        if hasattr(self, "_overlay_group_service"):
            try:
                overlay_assignments_removed = (
                    self._overlay_group_service.clear_assigned_windows()
                )
            except Exception:
                LOGGER.exception("Global reset could not clear overlay group assignments")

        overlay_markers_removed = 0
        if hasattr(self, "_overlay_marker_manager"):
            try:
                overlay_markers_removed = self._overlay_marker_manager.reset_runtime()
            except Exception:
                LOGGER.exception("Global reset could not remove overlay markers")
                try:
                    self._overlay_marker_manager.hide_all()
                except Exception:
                    LOGGER.exception("Global reset overlay fallback cleanup failed")

        self._clear_temporary_runtime_state()
        self._persist_managed_state("global emergency reset")
        self._recovery_store.clear(reason="global emergency reset")

        LOGGER.info(
            "Global emergency reset completed: restored_windows_count=%s "
            "restore_skipped_count=%s unpinned_windows_count=%s "
            "unpin_skipped_count=%s overlay_markers_removed=%s "
            "overlay_assignments_removed=%s runtime_state_cleared=1",
            restored,
            restore_skipped,
            unpinned,
            unpin_skipped,
            overlay_markers_removed,
            overlay_assignments_removed,
        )
        return {
            "restored": restored,
            "restore_skipped": restore_skipped,
            "unpinned": unpinned,
            "unpin_skipped": unpin_skipped,
            "overlay_markers_removed": overlay_markers_removed,
            "overlay_assignments_removed": overlay_assignments_removed,
        }

    def _clear_temporary_runtime_state(self) -> None:
        for timer_name in (
            "_open_windows_refresh_timer",
            "_pinned_watcher_timer",
            "_window_state_refresh_timer",
            "_refresh_debounce_timer",
            "_open_windows_filter_timer",
            "_icon_refresh_timer",
        ):
            timer = getattr(self, timer_name, None)
            if timer is not None:
                timer.stop()
        self._pending_refresh_reason = None
        if hasattr(self, "_pinned_order"):
            self._pinned_order.clear()
        self._last_shelf_items = ()
        self._last_pinned_items = ()
        LOGGER.info("Global emergency reset runtime state cleared")

    def _bring_selected_forward(self, table: QTableWidget | None = None) -> None:
        handles = self._selected_handles(table or self._available_table)
        if not handles:
            self._show_status(tr("status.select_open_forward"))
            return

        self._bring_handles_forward(handles)

    def _bring_handles_forward(self, handles: list[int]) -> None:
        if not handles:
            self._show_status(tr("status.select_open_forward"))
            return

        try:
            self._shelf_service.bring_to_front(handles[0])
            self._show_status(tr("status.foreground_activation"))
        except ShelfyGAIError as exc:
            LOGGER.exception("Foreground activation failed")
            self._show_error(str(exc))
        except Exception:
            LOGGER.exception("Unexpected foreground failure")
            self._show_error(tr("error.bring_forward"))

    def _show_error(self, message: str) -> None:
        self._show_status(message, critical=True)
        self._tray_notify(
            tr("error.notification.title"),
            message,
            critical=True,
            icon=QSystemTrayIcon.MessageIcon.Warning,
            duration_ms=6_000,
        )
        self._notifications.show_warning_popup(
            self,
            APP_NAME,
            message,
            critical=True,
        )

    def _open_github(self) -> None:
        self._open_url(GITHUB_REPOSITORY_URL)

    def _open_url(self, url: str) -> None:
        if not QDesktopServices.openUrl(QUrl(url)):
            LOGGER.warning("Could not open external URL: %s", url)

    def _check_for_updates(self) -> None:
        self._set_loading(True, tr("status.loading_checking"))
        try:
            result = self._update_service.check_for_updates()
            details = self._update_result_text(result)
            self._update_status_label.setText(details)
            self._show_status(tr("status.update_check_complete"))
            LOGGER.info(
                "Update check result: status=%s latest=%s release_url=%s",
                result.status,
                result.latest_version,
                result.release_url,
            )
        except Exception:
            LOGGER.exception("Update check failed")
            self._update_status_label.setText(tr("error.update_check"))
            self._show_status(tr("status.update_check_failed"))
        finally:
            self._set_loading(False)

    def _update_result_text(self, result: object) -> str:
        status = getattr(result, "status", UpdateCheckStatus.ERROR)
        latest_version = getattr(result, "latest_version", None)
        release_url = getattr(result, "release_url", None)
        checked_url = getattr(result, "checked_url", None)
        message = getattr(result, "message", "")
        if status == UpdateCheckStatus.UPDATE_AVAILABLE:
            text = tr(
                "about.update.available",
                current=APP_VERSION,
                latest=latest_version or tr("label.unknown"),
            )
        elif status == UpdateCheckStatus.UP_TO_DATE:
            text = tr("about.update.up_to_date", current=APP_VERSION)
        elif status == UpdateCheckStatus.NO_RELEASES:
            text = tr("about.update.no_releases")
        elif status == UpdateCheckStatus.OFFLINE:
            text = tr("about.update.offline")
        else:
            text = tr("about.update.error", error=message or tr("label.unknown"))
        if release_url:
            text = tr("update.with_release_url", message=text, url=release_url)
        if checked_url:
            text = tr("update.with_checked_url", message=text, url=checked_url)
        return text

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

    def _open_hidden_windows_from_tray(self) -> None:
        self._show_from_tray()
        self._show_page(1)
        LOGGER.debug("Hidden windows page opened from tray")

    def _open_overlay_groups_from_tray(self) -> None:
        self._show_from_tray()
        self._show_page(3)
        LOGGER.debug("Overlay groups page opened from tray")

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

    def _show_status(
        self,
        message: str,
        *,
        kind: NotificationKind = NotificationKind.STATUS,
        critical: bool = False,
        timeout_ms: int = 0,
    ) -> None:
        self._notifications.show_status(
            self.statusBar(),
            message,
            kind=kind,
            critical=critical,
            timeout_ms=timeout_ms,
        )

    def _tray_notify(
        self,
        title: str,
        message: str,
        *,
        kind: NotificationKind = NotificationKind.TRAY,
        critical: bool = False,
        icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information,
        duration_ms: int = 4_000,
    ) -> None:
        self._notifications.show_tray(
            self._tray_icon,
            title,
            message,
            kind=kind,
            critical=critical,
            icon=icon,
            duration_ms=duration_ms,
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
        hidden_count = len(self._shelf_service.shelved_items())
        pinned_count = len(self._shelf_service.pinned_items())
        overlay_group_count = (
            len(list(self._overlay_group_service.groups()))
            if hasattr(self, "_overlay_group_service")
            else 0
        )
        if self._tray_hidden_windows_action is not None:
            self._tray_hidden_windows_action.setText(
                tr("tray.hidden_windows", count=hidden_count)
            )
        if self._tray_overlay_groups_action is not None:
            self._tray_overlay_groups_action.setText(
                tr("tray.overlay_groups", count=overlay_group_count)
            )
        if self._tray_restore_all_action is not None:
            self._tray_restore_all_action.setText(
                tr("tray.restore_all", count=hidden_count)
            )
            self._tray_restore_all_action.setEnabled(hidden_count > 0)
        if self._tray_unpin_all_action is not None:
            self._tray_unpin_all_action.setText(tr("tray.unpin_all", count=pinned_count))
            self._tray_unpin_all_action.setEnabled(pinned_count > 0)
        if self._tray_reset_action is not None:
            self._tray_reset_action.setEnabled(hidden_count > 0 or pinned_count > 0)

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
        if action_id == HOTKEY_HIDE_SELECTED_WINDOW:
            self._quick_hide_from_hotkey()
        elif action_id == HOTKEY_RESTORE_LAST:
            self._restore_last_from_hotkey()
        elif action_id == HOTKEY_TOGGLE_OVERLAY_HUB:
            self._toggle_overlay_hub_from_hotkey()
        elif action_id == HOTKEY_OPEN_SWITCHER:
            self._show_quick_switcher_from_hotkey()
        elif action_id == HOTKEY_PIN_UNPIN_FOCUSED:
            self._pin_unpin_focused_from_hotkey()
        elif action_id == HOTKEY_RESET_EVERYTHING:
            self._reset_everything(confirm=False)

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
            self._show_status(tr("status.settings_saved"))

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
                True
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
            self._notifications_enabled_checkbox.setChecked(
                self._settings.notifications_enabled
            )
            self._tray_notifications_checkbox.setChecked(
                self._settings.show_tray_notifications
            )
            self._overlay_notifications_checkbox.setChecked(
                self._settings.show_overlay_notifications
            )
            self._restore_notifications_checkbox.setChecked(
                self._settings.show_restore_notifications
            )
            self._pin_notifications_checkbox.setChecked(
                self._settings.show_pin_unpin_notifications
            )
            self._silent_mode_checkbox.setChecked(self._settings.silent_mode)
            self._sync_notification_control_state()
            self._debug_mode_checkbox.setChecked(self._settings.debug_mode)
            self._overlay_enabled_checkbox.setChecked(self._settings.overlay_groups_enabled)
            self._overlay_use_hub_checkbox.setChecked(
                self._settings.overlay_use_unified_hub
            )
            self._overlay_individual_markers_checkbox.setChecked(
                self._settings.overlay_use_individual_markers
            )
            self._overlay_replace_markers_checkbox.setChecked(
                self._settings.overlay_replace_individual_markers
            )
            self._overlay_hub_always_visible_checkbox.setChecked(
                self._settings.overlay_hub_always_visible
            )
            self._overlay_hub_auto_hide_checkbox.setChecked(
                self._settings.overlay_hub_auto_hide
            )
            self._overlay_auto_snap_checkbox.setChecked(
                self._settings.overlay_auto_snap_to_taskbar
            )
            self._overlay_compact_mode_checkbox.setChecked(
                self._settings.overlay_compact_mode
            )
            self._overlay_marker_spacing_spin.setValue(
                self._settings.overlay_marker_spacing
            )
            self._overlay_hub_opacity_spin.setValue(self._settings.overlay_hub_opacity)
            self._sync_settings_accent_buttons()
        finally:
            self._settings_controls_syncing = False
        self._sync_hotkey_controls()

    def _sync_notification_control_state(self) -> None:
        notifications_enabled = self._notifications_enabled_checkbox.isChecked()
        silent_mode = self._silent_mode_checkbox.isChecked()
        for checkbox in (
            self._tray_notifications_checkbox,
            self._overlay_notifications_checkbox,
            self._restore_notifications_checkbox,
            self._pin_notifications_checkbox,
        ):
            checkbox.setEnabled(not silent_mode and notifications_enabled)

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
        validation_errors = self._hotkey_validation_errors()
        if validation_errors:
            self._hotkey_registration_errors = validation_errors
            self._hotkey_status_label.setText("; ".join(validation_errors))
            LOGGER.warning("Global hotkey validation failed: %s", validation_errors)
            return
        self._settings_store.save(self._settings, reason="global hotkeys changed")
        self._configure_global_hotkeys()

    def _hotkey_validation_errors(self) -> list[str]:
        try:
            from shelfygai.platform.windows.hotkeys import validate_hotkey_configs
        except Exception:
            LOGGER.debug("Could not import hotkey validator", exc_info=True)
            return []
        errors = validate_hotkey_configs(self._settings.global_hotkeys)
        return [
            f"{self._hotkey_label(action_id)}: {message}"
            for action_id, message in errors.items()
        ]

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
        self._settings.restore_pinned_windows_on_exit = True
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
        self._settings.notifications_enabled = self._notifications_enabled_checkbox.isChecked()
        self._settings.show_tray_notifications = self._tray_notifications_checkbox.isChecked()
        self._settings.show_overlay_notifications = (
            self._overlay_notifications_checkbox.isChecked()
        )
        self._settings.show_restore_notifications = (
            self._restore_notifications_checkbox.isChecked()
        )
        self._settings.show_pin_unpin_notifications = self._pin_notifications_checkbox.isChecked()
        self._settings.silent_mode = self._silent_mode_checkbox.isChecked()
        self._settings.debug_mode = self._debug_mode_checkbox.isChecked()
        self._settings.overlay_groups_enabled = self._overlay_enabled_checkbox.isChecked()
        self._settings.overlay_use_unified_hub = self._overlay_use_hub_checkbox.isChecked()
        self._settings.overlay_use_individual_markers = (
            self._overlay_individual_markers_checkbox.isChecked()
        )
        self._settings.overlay_replace_individual_markers = (
            self._overlay_replace_markers_checkbox.isChecked()
        )
        self._settings.overlay_hub_always_visible = (
            self._overlay_hub_always_visible_checkbox.isChecked()
        )
        self._settings.overlay_hub_auto_hide = (
            self._overlay_hub_auto_hide_checkbox.isChecked()
        )
        self._settings.overlay_auto_snap_to_taskbar = self._overlay_auto_snap_checkbox.isChecked()
        self._settings.overlay_compact_mode = self._overlay_compact_mode_checkbox.isChecked()
        self._settings.overlay_marker_spacing = self._overlay_marker_spacing_spin.value()
        self._settings.overlay_hub_opacity = self._overlay_hub_opacity_spin.value()

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
        if hasattr(self, "_overlay_marker_manager"):
            self._overlay_marker_manager.hide_all()
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
                "Normal exit blocked because hidden windows remain after restore: "
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
        if hasattr(self, "_overlay_marker_manager"):
            self._overlay_marker_manager.hide_all()
        try:
            self._shelf_service.unpin_all()
        except Exception:
            LOGGER.exception("Fatal-crash pinned-window cleanup failed")
        managed_count = len(self._shelf_service.shelved_items())
        self._sync_recovery_state("fatal crash before restore")
        if managed_count == 0:
            return {"attempted": False, "managed_count": 0, "reason": "no hidden windows"}

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
        pinned_records = self._pinned_recovery_records()
        if records or pinned_records:
            self._recovery_store.save(records, pinned_records=pinned_records, reason=reason)
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
                    "Skipping recovery state for hidden window without original style: "
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

    def _pinned_recovery_records(self) -> list[dict[str, object]]:
        boot_id = current_boot_id()
        return [
            {
                "boot_id": boot_id,
                "handle": item.window.handle,
                "title": item.window.title,
                "process_id": item.window.process_id,
                "process_name": item.window.process_name,
                "executable_path": item.window.executable_path,
                "pinned_at": item.pinned_at.isoformat(),
                "prevent_minimize": item.prevent_minimize,
            }
            for item in self._shelf_service.pinned_items()
        ]

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
        if hasattr(self, "_overlay_group_service"):
            self._settings.overlay_groups_enabled = self._overlay_enabled_checkbox.isChecked()
            self._settings.selected_overlay_group_id = self._selected_overlay_group_id
            self._settings.overlay_use_unified_hub = self._overlay_use_hub_checkbox.isChecked()
            self._settings.overlay_use_individual_markers = (
                self._overlay_individual_markers_checkbox.isChecked()
            )
            self._settings.overlay_replace_individual_markers = (
                self._overlay_replace_markers_checkbox.isChecked()
            )
            self._settings.overlay_hub_always_visible = (
                self._overlay_hub_always_visible_checkbox.isChecked()
            )
            self._settings.overlay_hub_auto_hide = (
                self._overlay_hub_auto_hide_checkbox.isChecked()
            )
            self._settings.overlay_auto_snap_to_taskbar = (
                self._overlay_auto_snap_checkbox.isChecked()
            )
            self._settings.overlay_compact_mode = self._overlay_compact_mode_checkbox.isChecked()
            self._settings.overlay_marker_spacing = self._overlay_marker_spacing_spin.value()
            self._settings.overlay_hub_opacity = self._overlay_hub_opacity_spin.value()
            self._settings.overlay_groups = [
                asdict(group)
                for group in self._overlay_group_service.groups()
            ]


def _overlay_groups_from_settings(groups: Sequence[dict[str, object]]) -> list[OverlayGroup]:
    parsed: list[OverlayGroup] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        group_id = group.get("id")
        name = group.get("name")
        if not isinstance(group_id, str) or not group_id.strip():
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        position_by_monitor = group.get("position_by_monitor", {})
        assigned_window_ids = group.get("assigned_window_ids", [])
        parsed.append(
            OverlayGroup(
                id=group_id.strip(),
                name=name.strip(),
                color=_overlay_string(group.get("color"), "#2f81f7"),
                marker_width=_overlay_int(group.get("marker_width"), 8),
                marker_height=_overlay_int(group.get("marker_height"), 64),
                opacity=_overlay_float(group.get("opacity"), 0.9),
                corner_radius=_overlay_int(group.get("corner_radius"), 8),
                hover_delay_ms=_overlay_int(group.get("hover_delay_ms"), 1200),
                locked_position=_overlay_bool(group.get("locked_position"), False),
                hide_during_fullscreen=_overlay_bool(
                    group.get("hide_during_fullscreen"),
                    True,
                ),
                show_quick_controls=_overlay_bool(group.get("show_quick_controls"), True),
                position_by_monitor=(
                    dict(position_by_monitor)
                    if isinstance(position_by_monitor, dict)
                    else {}
                ),
                assigned_window_ids=(
                    [handle for handle in assigned_window_ids if isinstance(handle, int)]
                    if isinstance(assigned_window_ids, list)
                    else []
                ),
            )
        )
    return parsed


def _overlay_string(value: object, default: str) -> str:
    return value if isinstance(value, str) else default


def _overlay_int(value: object, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _overlay_float(value: object, default: float) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return default


def _overlay_bool(value: object, default: bool) -> bool:
    return value if isinstance(value, bool) else default


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

