from __future__ import annotations

import sys
from dataclasses import replace

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from shelfygai.constants import (
    APP_NAME,
    GITHUB_REPOSITORY_URL,
    resource_path,
)
from shelfygai.i18n import SUPPORTED_LANGUAGES, set_language, tr
from shelfygai.settings.settings_manager import AppSettings, SettingsManager
from shelfygai.ui.notifications import NotificationManager
from shelfygai.ui.theme import apply_theme
from shelfygai.ui.widgets.animated_button import AnimatedHoverButton

ACCENT_COLORS = [
    ("accent.blue", "#2f81f7"),
    ("accent.teal", "#55c2a2"),
    ("accent.amber", "#f0b429"),
    ("accent.rose", "#e85d75"),
    ("accent.violet", "#8b5cf6"),
    ("accent.slate", "#64748b"),
]

ONBOARDING_STEPS = (
    (
        "onboarding.step.what.title",
        "onboarding.step.what.body",
        "onboarding.step.what.visual",
    ),
    (
        "onboarding.step.hidden.title",
        "onboarding.step.hidden.body",
        "onboarding.step.hidden.visual",
    ),
    (
        "onboarding.step.overlay.title",
        "onboarding.step.overlay.body",
        "onboarding.step.overlay.visual",
    ),
    (
        "onboarding.step.pinned.title",
        "onboarding.step.pinned.body",
        "onboarding.step.pinned.visual",
    ),
    (
        "onboarding.step.safety.title",
        "onboarding.step.safety.body",
        "onboarding.step.safety.visual",
    ),
)


class SettingsDialog(QDialog):
    def __init__(
        self,
        settings_store: SettingsManager,
        settings: AppSettings,
        *,
        first_launch: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings_store = settings_store
        self._original_settings = replace(settings)
        self._settings = replace(settings)
        self._notifications = NotificationManager(lambda: self._settings)
        self._first_launch = first_launch
        self._startup_toggle_available = True
        self._accent_buttons: dict[str, QToolButton] = {}

        set_language(self._settings.language)
        self.setWindowTitle(tr("onboarding.title") if first_launch else tr("settings.title"))
        self.setWindowIcon(QIcon(str(resource_path("app_icon.svg"))))
        self.setModal(True)
        self.resize(900, 640)
        self.setMinimumSize(780, 560)

        self._language_combo = QComboBox()
        self._theme_combo = QComboBox()
        self._accent_group = QButtonGroup(self)
        self._accent_group.setExclusive(True)
        self._launch_with_windows_checkbox = QCheckBox()
        self._minimize_to_tray_checkbox = QCheckBox()
        self._silent_startup_checkbox = QCheckBox()
        self._restore_on_exit_checkbox = QCheckBox()
        self._focus_restored_windows_checkbox = QCheckBox()
        self._startup_notification_checkbox = QCheckBox()
        self._debug_mode_checkbox = QCheckBox()
        self._notifications_enabled_checkbox = QCheckBox()
        self._tray_notifications_checkbox = QCheckBox()
        self._overlay_notifications_checkbox = QCheckBox()
        self._restore_notifications_checkbox = QCheckBox()
        self._pin_notifications_checkbox = QCheckBox()
        self._silent_mode_checkbox = QCheckBox()
        self._startup_status_label = QLabel()
        self._startup_status_label.setObjectName("Muted")
        self._startup_status_label.setWordWrap(True)
        self._launch_with_windows_checkbox.toggled.connect(self._sync_startup_options)
        self._notifications_enabled_checkbox.toggled.connect(
            self._sync_notification_control_state
        )
        self._silent_mode_checkbox.toggled.connect(self._sync_notification_control_state)
        self._hero_description_label: QLabel | None = None
        self._privacy_note_label: QLabel | None = None
        self._github_button: QPushButton | None = None
        self._header_label: QLabel | None = None
        self._subtitle_label: QLabel | None = None
        self._cancel_button: QPushButton | None = None
        self._save_button: QPushButton | None = None
        self._skip_button: QPushButton | None = None
        self._onboarding_back_button: QPushButton | None = None
        self._onboarding_next_button: QPushButton | None = None
        self._onboarding_progress_label: QLabel | None = None
        self._onboarding_stack: QStackedWidget | None = None
        self._onboarding_step_labels: list[tuple[QLabel, QLabel, QLabel]] = []
        self._language_label: QLabel | None = None
        self._theme_label: QLabel | None = None
        self._accent_label: QLabel | None = None
        self._card_title_labels: dict[str, QLabel] = {}

        self._load_platform_state()
        self._build_layout()
        self._load_form_values()
        self._retranslate()

    @property
    def settings(self) -> AppSettings:
        return self._settings

    def _build_layout(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_hero_panel())
        layout.addWidget(self._build_settings_panel(), 1)

    def _build_hero_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("HeroPanel")
        panel.setMinimumWidth(292)
        panel.setMaximumWidth(360)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(26, 30, 26, 24)
        layout.setSpacing(14)

        logo = QLabel()
        logo.setObjectName("AboutLogo")
        logo.setPixmap(QIcon(str(resource_path("app_icon.svg"))).pixmap(76, 76))
        logo.setFixedSize(88, 88)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel(APP_NAME)
        title.setObjectName("HeroTitle")

        description = QLabel()
        description.setObjectName("HeroDescription")
        description.setWordWrap(True)
        self._hero_description_label = description

        privacy_note = QLabel()
        privacy_note.setObjectName("EmptyState")
        privacy_note.setWordWrap(True)
        self._privacy_note_label = privacy_note

        github_button = AnimatedHoverButton()
        github_button.clicked.connect(self._open_github)
        self._github_button = github_button

        layout.addWidget(logo)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(privacy_note)
        layout.addStretch(1)
        layout.addWidget(github_button)
        return panel

    def _build_settings_panel(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(14)

        header = QLabel()
        header.setObjectName("HeaderTitle")
        subtitle = QLabel()
        subtitle.setObjectName("HeaderSubtitle")
        subtitle.setWordWrap(True)
        self._header_label = header
        self._subtitle_label = subtitle

        layout.addWidget(header)
        layout.addWidget(subtitle)
        if self._first_launch:
            layout.addWidget(self._build_onboarding_flow())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self._build_settings_content())
        layout.addWidget(scroll, 1)

        footer = QHBoxLayout()
        if self._first_launch:
            skip_button = AnimatedHoverButton()
            skip_button.clicked.connect(self._skip_onboarding)
            self._skip_button = skip_button
            footer.addWidget(skip_button)
        footer.addStretch(1)

        if self._first_launch:
            back_button = AnimatedHoverButton()
            back_button.clicked.connect(self._previous_onboarding_step)
            next_button = AnimatedHoverButton()
            next_button.clicked.connect(self._next_onboarding_step)
            self._onboarding_back_button = back_button
            self._onboarding_next_button = next_button
            footer.addWidget(back_button)
            footer.addWidget(next_button)

        cancel_button = AnimatedHoverButton()
        cancel_button.clicked.connect(self.reject)

        save_button = AnimatedHoverButton()
        save_button.setObjectName("PrimaryButton")
        save_button.clicked.connect(self._save_and_accept)
        self._cancel_button = cancel_button
        self._save_button = save_button

        if not self._first_launch:
            footer.addWidget(cancel_button)
        footer.addWidget(save_button)
        layout.addLayout(footer)

        return wrapper

    def _build_onboarding_flow(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("OnboardingPanel")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel()
        title.setObjectName("SectionTitle")
        title.setText(tr("onboarding.quick_start"))
        progress = QLabel()
        progress.setObjectName("Muted")
        progress.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._onboarding_progress_label = progress
        header.addWidget(title, 1)
        header.addWidget(progress)

        stack = QStackedWidget()
        stack.setObjectName("OnboardingStack")
        self._onboarding_stack = stack
        for title_key, body_key, visual_key in ONBOARDING_STEPS:
            stack.addWidget(self._build_onboarding_step(title_key, body_key, visual_key))

        layout.addLayout(header)
        layout.addWidget(stack)
        self._sync_onboarding_step()
        return panel

    def _build_onboarding_step(
        self,
        title_key: str,
        body_key: str,
        visual_key: str,
    ) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        visual = QFrame()
        visual.setObjectName("OnboardingVisual")
        visual.setMinimumWidth(180)
        visual_layout = QVBoxLayout(visual)
        visual_layout.setContentsMargins(14, 12, 14, 12)
        visual_layout.setSpacing(8)

        visual_logo = QLabel()
        visual_logo.setObjectName("IconBadge")
        visual_logo.setFixedSize(42, 42)
        visual_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        visual_logo.setPixmap(QIcon(str(resource_path("app_icon.svg"))).pixmap(28, 28))
        visual_text = QLabel()
        visual_text.setObjectName("OnboardingVisualText")
        visual_text.setWordWrap(True)
        visual_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        visual_layout.addStretch(1)
        visual_layout.addWidget(visual_logo, alignment=Qt.AlignmentFlag.AlignCenter)
        visual_layout.addWidget(visual_text)
        visual_layout.addStretch(1)

        copy = QWidget()
        copy_layout = QVBoxLayout(copy)
        copy_layout.setContentsMargins(0, 0, 0, 0)
        copy_layout.setSpacing(7)
        title = QLabel()
        title.setObjectName("CardTitle")
        title.setWordWrap(True)
        body = QLabel()
        body.setObjectName("Muted")
        body.setWordWrap(True)
        copy_layout.addStretch(1)
        copy_layout.addWidget(title)
        copy_layout.addWidget(body)
        copy_layout.addStretch(1)

        layout.addWidget(visual)
        layout.addWidget(copy, 1)
        self._onboarding_step_labels.append((title, body, visual_text))
        title.setProperty("i18n_key", title_key)
        body.setProperty("i18n_key", body_key)
        visual_text.setProperty("i18n_key", visual_key)
        return page

    def _build_settings_content(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(16)

        layout.addWidget(
            self._build_card(
                "label.appearance",
                [
                    self._build_language_row(),
                    self._build_theme_row(),
                    self._build_accent_row(),
                ],
            )
        )
        layout.addWidget(
            self._build_card(
                "label.behavior",
                [
                    self._launch_with_windows_checkbox,
                    self._minimize_to_tray_checkbox,
                    self._silent_startup_checkbox,
                    self._restore_on_exit_checkbox,
                    self._focus_restored_windows_checkbox,
                    self._startup_notification_checkbox,
                    self._debug_mode_checkbox,
                    self._startup_status_label,
                ],
            )
        )
        layout.addWidget(
            self._build_card(
                "settings.section.notifications",
                [
                    self._notifications_enabled_checkbox,
                    self._tray_notifications_checkbox,
                    self._overlay_notifications_checkbox,
                    self._restore_notifications_checkbox,
                    self._pin_notifications_checkbox,
                    self._silent_mode_checkbox,
                ],
            )
        )
        layout.addStretch(1)
        return content

    def _build_card(self, title_key: str, widgets: list[QWidget]) -> QFrame:
        card = QFrame()
        card.setObjectName("OnboardingPanel")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(13)

        title_label = QLabel()
        title_label.setObjectName("SectionTitle")
        self._card_title_labels[title_key] = title_label
        layout.addWidget(title_label)

        for widget in widgets:
            layout.addWidget(widget)

        return card

    def _build_language_row(self) -> QWidget:
        row = QWidget()
        layout = QGridLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(12)
        layout.setColumnStretch(1, 1)

        label = QLabel()
        label.setObjectName("Muted")
        self._language_label = label

        self._language_combo.setAccessibleName(tr("label.language"))
        self._language_combo.currentIndexChanged.connect(self._preview_language)

        layout.addWidget(label, 0, 0)
        layout.addWidget(self._language_combo, 0, 1)
        return row

    def _build_theme_row(self) -> QWidget:
        row = QWidget()
        layout = QGridLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(12)
        layout.setColumnStretch(1, 1)

        label = QLabel()
        label.setObjectName("Muted")
        self._theme_label = label

        self._theme_combo.setAccessibleName(tr("label.theme"))
        self._theme_combo.currentIndexChanged.connect(self._preview_theme)

        layout.addWidget(label, 0, 0)
        layout.addWidget(self._theme_combo, 0, 1)
        return row

    def _build_accent_row(self) -> QWidget:
        row = QWidget()
        layout = QGridLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(12)
        layout.setColumnStretch(1, 1)

        label = QLabel()
        label.setObjectName("Muted")
        self._accent_label = label

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
            self._accent_buttons[color] = button
            self._accent_group.addButton(button)
            button.clicked.connect(
                lambda _checked=False, selected=color: self._set_accent(selected)
            )
            chips_layout.addWidget(button)

        chips_layout.addStretch(1)

        layout.addWidget(label, 0, 0)
        layout.addWidget(chips, 0, 1)
        return row

    def _load_form_values(self) -> None:
        self._populate_language_combo()
        language_index = self._language_combo.findData(self._settings.language)
        self._language_combo.setCurrentIndex(max(language_index, 0))
        self._populate_theme_combo()
        theme_index = self._theme_combo.findData(self._settings.theme)
        self._theme_combo.setCurrentIndex(max(theme_index, 0))

        accent_button = self._accent_buttons.get(self._settings.accent_color)
        if accent_button is None:
            accent_button = self._accent_buttons["#2f81f7"]
            self._settings.accent_color = "#2f81f7"
        accent_button.setChecked(True)

        self._launch_with_windows_checkbox.setChecked(self._settings.launch_with_windows)
        self._minimize_to_tray_checkbox.setChecked(self._settings.minimize_to_tray_on_close)
        self._silent_startup_checkbox.setChecked(self._settings.silent_startup)
        self._restore_on_exit_checkbox.setChecked(self._settings.restore_windows_on_exit)
        self._focus_restored_windows_checkbox.setChecked(self._settings.focus_restored_windows)
        self._startup_notification_checkbox.setChecked(
            self._settings.startup_notification_enabled
        )
        self._debug_mode_checkbox.setChecked(self._settings.debug_mode)
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
        self._sync_startup_options()
        self._preview_theme()

    def _load_platform_state(self) -> None:
        if sys.platform != "win32":
            self._settings.launch_with_windows = False
            self._startup_toggle_available = False
            self._launch_with_windows_checkbox.setEnabled(False)
            self._silent_startup_checkbox.setEnabled(False)
            self._startup_status_label.setText(tr("startup.status.read_error"))
            return

        from shelfygai.platform.windows.startup import get_startup_status

        try:
            status = get_startup_status()
        except OSError:
            self._settings.launch_with_windows = False
            self._startup_toggle_available = False
            self._launch_with_windows_checkbox.setEnabled(False)
            self._silent_startup_checkbox.setEnabled(False)
            self._startup_status_label.setText(tr("startup.status.read_error"))
            return

        self._settings.launch_with_windows = status.enabled and status.path_valid
        self._settings.silent_startup = status.silent_startup
        self._startup_status_label.setText(_startup_status_text(status))

    def _collect_settings(self) -> AppSettings:
        settings = replace(self._settings)
        settings.onboarding_completed = True
        settings.language = str(self._language_combo.currentData() or self._settings.language)
        settings.theme = str(self._theme_combo.currentData() or self._settings.theme)
        settings.accent_color = self._selected_accent_color()
        settings.launch_with_windows = self._launch_with_windows_checkbox.isChecked()
        settings.minimize_to_tray_on_close = self._minimize_to_tray_checkbox.isChecked()
        settings.silent_startup = self._silent_startup_checkbox.isChecked()
        settings.restore_windows_on_exit = self._restore_on_exit_checkbox.isChecked()
        settings.focus_restored_windows = self._focus_restored_windows_checkbox.isChecked()
        settings.startup_notification_enabled = self._startup_notification_checkbox.isChecked()
        settings.debug_mode = self._debug_mode_checkbox.isChecked()
        settings.notifications_enabled = self._notifications_enabled_checkbox.isChecked()
        settings.show_tray_notifications = self._tray_notifications_checkbox.isChecked()
        settings.show_overlay_notifications = (
            self._overlay_notifications_checkbox.isChecked()
        )
        settings.show_restore_notifications = (
            self._restore_notifications_checkbox.isChecked()
        )
        settings.show_pin_unpin_notifications = self._pin_notifications_checkbox.isChecked()
        settings.silent_mode = self._silent_mode_checkbox.isChecked()
        return settings

    def _save_and_accept(self) -> None:
        new_settings = self._collect_settings()

        try:
            self._save_platform_state(
                new_settings.launch_with_windows,
                new_settings.silent_startup,
            )
            saved = self._settings_store.save(new_settings)
        except OSError as exc:
            self._notifications.show_warning_popup(
                self,
                APP_NAME,
                tr("error.save_settings_detail", error=exc),
                critical=True,
            )
            return
        if not saved:
            self._notifications.show_warning_popup(
                self,
                APP_NAME,
                tr("error.save_settings"),
                critical=True,
            )
            return

        self._settings = new_settings
        set_language(new_settings.language)
        qt_app = QApplication.instance()
        if qt_app is not None:
            apply_theme(qt_app, new_settings.theme, new_settings.accent_color)
        self.accept()

    def _skip_onboarding(self) -> None:
        self._save_and_accept()

    def reject(self) -> None:
        set_language(self._original_settings.language)
        qt_app = QApplication.instance()
        if qt_app is not None:
            apply_theme(
                qt_app,
                self._original_settings.theme,
                self._original_settings.accent_color,
            )
        super().reject()

    def _save_platform_state(self, launch_with_windows: bool, silent_startup: bool) -> None:
        if sys.platform != "win32" or not self._startup_toggle_available:
            return

        from shelfygai.platform.windows.startup import set_launch_with_windows_enabled

        set_launch_with_windows_enabled(
            launch_with_windows,
            silent_startup=silent_startup,
        )

    def _sync_startup_options(self) -> None:
        if not self._startup_toggle_available:
            self._silent_startup_checkbox.setEnabled(False)
            return
        self._silent_startup_checkbox.setEnabled(self._launch_with_windows_checkbox.isChecked())

    def _sync_notification_control_state(self) -> None:
        enabled = self._notifications_enabled_checkbox.isChecked()
        silent = self._silent_mode_checkbox.isChecked()
        for checkbox in (
            self._tray_notifications_checkbox,
            self._overlay_notifications_checkbox,
            self._restore_notifications_checkbox,
            self._pin_notifications_checkbox,
        ):
            checkbox.setEnabled(enabled and not silent)

    def _set_accent(self, color: str) -> None:
        self._settings.accent_color = color
        self._preview_theme()

    def _preview_language(self) -> None:
        language = self._language_combo.currentData()
        if not isinstance(language, str):
            return
        self._settings.language = set_language(language)
        self._retranslate()
        self._preview_theme()

    def _selected_accent_color(self) -> str:
        for color, button in self._accent_buttons.items():
            if button.isChecked():
                return color
        return "#2f81f7"

    def _preview_theme(self) -> None:
        qt_app = QApplication.instance()
        if qt_app is None:
            return
        apply_theme(
            qt_app,
            str(self._theme_combo.currentData() or self._settings.theme),
            self._selected_accent_color(),
        )

    def _open_github(self) -> None:
        QDesktopServices.openUrl(QUrl(GITHUB_REPOSITORY_URL))

    def _previous_onboarding_step(self) -> None:
        if self._onboarding_stack is None:
            return
        self._onboarding_stack.setCurrentIndex(max(0, self._onboarding_stack.currentIndex() - 1))
        self._sync_onboarding_step()

    def _next_onboarding_step(self) -> None:
        if self._onboarding_stack is None:
            return
        last_index = self._onboarding_stack.count() - 1
        self._onboarding_stack.setCurrentIndex(
            min(last_index, self._onboarding_stack.currentIndex() + 1)
        )
        self._sync_onboarding_step()

    def _sync_onboarding_step(self) -> None:
        if self._onboarding_stack is None:
            return
        current = self._onboarding_stack.currentIndex()
        total = self._onboarding_stack.count()
        if self._onboarding_progress_label is not None:
            self._onboarding_progress_label.setText(
                tr("onboarding.progress", current=current + 1, total=total)
            )
        if self._onboarding_back_button is not None:
            self._onboarding_back_button.setEnabled(current > 0)
        if self._onboarding_next_button is not None:
            self._onboarding_next_button.setEnabled(current < total - 1)

    def _populate_language_combo(self) -> None:
        current = self._language_combo.currentData() or self._settings.language
        self._language_combo.blockSignals(True)
        self._language_combo.clear()
        for language, label in SUPPORTED_LANGUAGES.items():
            self._language_combo.addItem(label, language)
        index = self._language_combo.findData(current)
        self._language_combo.setCurrentIndex(max(index, 0))
        self._language_combo.blockSignals(False)

    def _populate_theme_combo(self) -> None:
        current = self._theme_combo.currentData() or self._settings.theme
        self._theme_combo.blockSignals(True)
        self._theme_combo.clear()
        for key, value in (
            ("theme.system", "system"),
            ("theme.dark", "dark"),
            ("theme.light", "light"),
        ):
            self._theme_combo.addItem(tr(key), value)
        index = self._theme_combo.findData(current)
        self._theme_combo.setCurrentIndex(max(index, 0))
        self._theme_combo.blockSignals(False)

    def _retranslate(self) -> None:
        self.setWindowTitle(tr("onboarding.title") if self._first_launch else tr("settings.title"))
        if self._hero_description_label is not None:
            self._hero_description_label.setText(tr("app.description"))
        if self._privacy_note_label is not None:
            self._privacy_note_label.setText(tr("about.privacy"))
        if self._github_button is not None:
            self._github_button.setText(tr("github.repository"))
        if self._header_label is not None:
            self._header_label.setText(
                tr("onboarding.first_run") if self._first_launch else tr("onboarding.settings")
            )
        if self._subtitle_label is not None:
            self._subtitle_label.setText(tr("onboarding.subtitle"))
        if self._cancel_button is not None:
            self._cancel_button.setText(tr("action.cancel"))
        if self._save_button is not None:
            self._save_button.setText(
                tr("action.save_continue") if self._first_launch else tr("action.save")
            )
        if self._skip_button is not None:
            self._skip_button.setText(tr("action.skip"))
        if self._onboarding_back_button is not None:
            self._onboarding_back_button.setText(tr("action.back"))
        if self._onboarding_next_button is not None:
            self._onboarding_next_button.setText(tr("action.next"))
        for title, body, visual in self._onboarding_step_labels:
            title_key = title.property("i18n_key")
            body_key = body.property("i18n_key")
            visual_key = visual.property("i18n_key")
            if isinstance(title_key, str):
                title.setText(tr(title_key))
            if isinstance(body_key, str):
                body.setText(tr(body_key))
            if isinstance(visual_key, str):
                visual.setText(tr(visual_key))
        self._sync_onboarding_step()
        if self._language_label is not None:
            self._language_label.setText(tr("label.language"))
        if self._theme_label is not None:
            self._theme_label.setText(tr("label.theme"))
        if self._accent_label is not None:
            self._accent_label.setText(tr("label.accent_color"))
        for key, label in self._card_title_labels.items():
            label.setText(tr(key))
        self._launch_with_windows_checkbox.setText(tr("label.launch_with_windows"))
        self._minimize_to_tray_checkbox.setText(tr("label.minimize_to_tray"))
        self._silent_startup_checkbox.setText(tr("label.silent_startup"))
        self._restore_on_exit_checkbox.setText(tr("label.restore_on_exit"))
        self._focus_restored_windows_checkbox.setText(tr("label.focus_restored_windows"))
        self._startup_notification_checkbox.setText(tr("label.startup_notification"))
        self._debug_mode_checkbox.setText(tr("label.debug_logging"))
        self._notifications_enabled_checkbox.setText(tr("label.notifications_enabled"))
        self._tray_notifications_checkbox.setText(tr("label.show_tray_notifications"))
        self._overlay_notifications_checkbox.setText(
            tr("label.show_overlay_notifications")
        )
        self._restore_notifications_checkbox.setText(
            tr("label.show_restore_notifications")
        )
        self._pin_notifications_checkbox.setText(
            tr("label.show_pin_unpin_notifications")
        )
        self._silent_mode_checkbox.setText(tr("label.silent_mode"))
        self._language_combo.setAccessibleName(tr("label.language"))
        self._theme_combo.setAccessibleName(tr("label.theme"))
        for _color, button in self._accent_buttons.items():
            key = str(button.property("i18n_key"))
            button.setToolTip(tr(key))
            button.setAccessibleName(f"{tr(key)} {tr('label.accent_color')}")
        self._populate_language_combo()
        self._populate_theme_combo()


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
