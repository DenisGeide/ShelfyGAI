from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from shelfygai.constants import APP_VERSION
from shelfygai.i18n import tr
from shelfygai.ui.onboarding_dialog import ACCENT_COLORS
from shelfygai.ui.widgets.empty_state_widget import EmptyStateWidget


class CollapsibleSettingsSection(QFrame):
    """Compact settings section with a text header and searchable content."""

    def __init__(
        self,
        *,
        title_key: str,
        description_key: str,
        search_keys: list[str],
        widgets: list[QWidget],
        expanded: bool = False,
    ) -> None:
        super().__init__()
        self.setObjectName("SettingsSection")
        self._title_key = title_key
        self._description_key = description_key
        self._search_keys = [title_key, description_key, *search_keys]
        self._default_expanded = expanded
        self._expanded = expanded

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(3)

        self._title_label = QLabel()
        self._title_label.setObjectName("SettingsSectionTitle")
        self._description_label = QLabel()
        self._description_label.setObjectName("SettingsSectionDescription")
        self._description_label.setWordWrap(True)
        title_box.addWidget(self._title_label)
        title_box.addWidget(self._description_label)

        self._toggle_button = QToolButton()
        self._toggle_button.setObjectName("SettingsSectionToggle")
        self._toggle_button.setCheckable(True)
        self._toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._toggle_button.clicked.connect(
            lambda _checked=False: self.set_expanded(not self._expanded)
        )

        header_layout.addLayout(title_box, 1)
        header_layout.addWidget(self._toggle_button)
        layout.addWidget(header)

        self._body = QWidget()
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(0, 4, 0, 0)
        body_layout.setSpacing(8)
        for widget in widgets:
            body_layout.addWidget(widget)
        layout.addWidget(self._body)

        self.retranslate()
        self.set_expanded(expanded)

    def retranslate(self) -> None:
        self._title_label.setText(tr(self._title_key))
        self._description_label.setText(tr(self._description_key))
        self._toggle_button.setText(
            tr(
                "action.collapse_section"
                if self._expanded
                else "action.expand_section"
            )
        )
        self._toggle_button.setToolTip(tr("tooltip.toggle_settings_section"))

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self._body.setVisible(expanded)
        self._toggle_button.setChecked(expanded)
        self.retranslate()

    def matches_filter(self, query: str) -> bool:
        normalized = query.strip().casefold()
        if not normalized:
            return True
        haystack = " ".join(tr(key).casefold() for key in self._search_keys)
        return normalized in haystack

    def apply_filter(self, query: str) -> bool:
        matches = self.matches_filter(query)
        self.setVisible(matches)
        if query.strip() and matches:
            self.set_expanded(True)
        elif not query.strip():
            self.set_expanded(self._default_expanded)
        return matches


def build_settings_page(owner: Any) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)

    search = QLineEdit()
    search.setClearButtonEnabled(True)
    search.setObjectName("SettingsSearch")
    owner._settings_search = search
    owner._bind_text(search, "placeholder.settings_search", "setPlaceholderText")
    owner._bind_text(search, "placeholder.settings_search", "setAccessibleName")
    layout.addWidget(search)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)

    content = QWidget()
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(0, 0, 8, 0)
    content_layout.setSpacing(10)

    sections = [
        CollapsibleSettingsSection(
            title_key="settings.category.general",
            description_key="settings.description.general",
            search_keys=[
                "label.language",
                "label.theme",
                "label.accent_color",
                "label.launch_with_windows",
                "label.minimize_to_tray",
            ],
            widgets=[
                build_settings_combo_row(owner, "label.language", owner._settings_language_combo),
                build_settings_combo_row(owner, "label.theme", owner._settings_theme_combo),
                build_settings_accent_row(owner),
                build_setting_note(owner, "settings.note.general_startup"),
                owner._launch_with_windows_checkbox,
                owner._startup_status_label,
                owner._minimize_to_tray_checkbox,
            ],
            expanded=True,
        ),
        CollapsibleSettingsSection(
            title_key="settings.category.hidden_windows",
            description_key="settings.description.hidden_windows",
            search_keys=[
                "label.restore_on_exit",
                "label.focus_restored_windows",
                "label.confirm_before_hiding",
                "label.confirm_quit_with_hidden_windows",
            ],
            widgets=[
                owner._restore_on_exit_checkbox,
                owner._focus_restored_checkbox,
                owner._confirm_checkbox,
                owner._confirm_quit_checkbox,
            ],
            expanded=True,
        ),
        CollapsibleSettingsSection(
            title_key="settings.category.overlay",
            description_key="settings.description.overlay",
            search_keys=[
                "label.groups",
                "label.overlay_use_unified_hub",
                "label.overlay_use_individual_markers",
                "label.overlay_hide_fullscreen",
            ],
            widgets=[
                build_setting_note(owner, "settings.note.overlay"),
                owner._make_button(
                    "action.open_overlay_groups",
                    lambda: owner._show_page(3),
                ),
            ],
        ),
        CollapsibleSettingsSection(
            title_key="settings.category.notifications",
            description_key="settings.description.notifications",
            search_keys=[
                "label.startup_notification",
                "label.notifications_enabled",
                "label.show_tray_notifications",
                "label.show_overlay_notifications",
                "label.show_restore_notifications",
                "label.show_pin_unpin_notifications",
                "label.silent_mode",
            ],
            widgets=[
                owner._startup_notification_checkbox,
                owner._notifications_enabled_checkbox,
                owner._tray_notifications_checkbox,
                owner._overlay_notifications_checkbox,
                owner._restore_notifications_checkbox,
                owner._pin_notifications_checkbox,
                build_described_control(
                    owner,
                    owner._silent_mode_checkbox,
                    "settings.note.silent_mode",
                ),
            ],
        ),
        CollapsibleSettingsSection(
            title_key="settings.category.performance",
            description_key="settings.description.performance",
            search_keys=[
                "label.auto_refresh",
                "label.prevent_minimize_watcher",
                "label.pinned_watcher_interval",
            ],
            widgets=[
                build_described_control(
                    owner,
                    owner._open_windows_auto_refresh_checkbox,
                    "settings.note.auto_refresh",
                ),
                owner._prevent_minimize_watcher_checkbox,
                build_settings_spin_row(
                    owner,
                    "label.pinned_watcher_interval",
                    owner._pinned_watcher_interval_spin,
                ),
            ],
        ),
        CollapsibleSettingsSection(
            title_key="settings.category.advanced",
            description_key="settings.description.advanced",
            search_keys=[
                "settings.section.hotkeys",
                "label.debug_logging",
                "label.allow_pin_shelfygai",
                "label.restore_pinned_on_exit",
                "action.reset_everything",
                "about.version",
                "github.repository",
            ],
            widgets=[
                build_setting_note(owner, "settings.note.advanced"),
                owner._build_hotkeys_panel(),
                owner._debug_mode_checkbox,
                owner._allow_pin_self_checkbox,
                owner._restore_pinned_on_exit_checkbox,
                owner._make_button("action.reset_everything", owner._reset_everything),
                build_settings_about_section(owner),
            ],
        ),
    ]
    owner._settings_sections = sections

    empty_search = EmptyStateWidget(minimum_height=120)
    empty_search.setText(tr("settings.search_empty"))
    owner._bind_text(empty_search, "settings.search_empty")
    empty_search.setVisible(False)

    for section in sections:
        content_layout.addWidget(section)
    content_layout.addWidget(empty_search, 1)
    content_layout.addStretch(1)

    def apply_search_filter(query: str) -> None:
        matches = [section.apply_filter(query) for section in sections]
        empty_search.setText(tr("settings.search_empty"))
        empty_search.setVisible(not any(matches))

    search.textChanged.connect(apply_search_filter)

    scroll.setWidget(content)
    layout.addWidget(scroll, 1)
    owner._sync_settings_controls()
    return page


def build_settings_section(owner: Any, title_key: str, widgets: list[QWidget]) -> QFrame:
    return CollapsibleSettingsSection(
        title_key=title_key,
        description_key="settings.description.generic",
        search_keys=[title_key],
        widgets=widgets,
        expanded=True,
    )


def build_settings_combo_row(owner: Any, label_key: str, combo: QWidget) -> QWidget:
    row = QWidget()
    row.setObjectName("SettingRow")
    layout = QGridLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setHorizontalSpacing(12)
    layout.setColumnStretch(1, 1)

    label = QLabel()
    label.setObjectName("Muted")
    owner._bind_text(label, label_key)
    owner._bind_text(combo, label_key, "setAccessibleName")

    layout.addWidget(label, 0, 0)
    layout.addWidget(combo, 0, 1)
    return row


def build_settings_spin_row(owner: Any, label_key: str, spin_box: QSpinBox) -> QWidget:
    row = QWidget()
    row.setObjectName("SettingRow")
    layout = QGridLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setHorizontalSpacing(12)
    layout.setColumnStretch(1, 1)

    label = QLabel()
    label.setObjectName("Muted")
    owner._bind_text(label, label_key)
    owner._bind_text(spin_box, label_key, "setAccessibleName")

    layout.addWidget(label, 0, 0)
    layout.addWidget(spin_box, 0, 1)
    return row


def build_described_control(owner: Any, control: QWidget, description_key: str) -> QWidget:
    container = QWidget()
    container.setObjectName("SettingRow")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(3)
    layout.addWidget(control)
    layout.addWidget(build_setting_note(owner, description_key))
    return container


def build_setting_note(owner: Any, key: str) -> QLabel:
    note = QLabel()
    note.setObjectName("SettingDescription")
    note.setWordWrap(True)
    owner._bind_text(note, key)
    return note


def build_settings_accent_row(owner: Any) -> QWidget:
    row = QWidget()
    row.setObjectName("SettingRow")
    layout = QGridLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setHorizontalSpacing(12)
    layout.setColumnStretch(1, 1)

    label = QLabel()
    label.setObjectName("Muted")
    owner._bind_text(label, "label.accent_color")

    chips = QWidget()
    chips_layout = QHBoxLayout(chips)
    chips_layout.setContentsMargins(0, 0, 0, 0)
    chips_layout.setSpacing(8)

    for name_key, color in ACCENT_COLORS:
        button = QToolButton()
        button.setCheckable(True)
        button.setProperty("i18n_key", name_key)
        button.setFixedSize(28, 28)
        button.setStyleSheet(
            f"""
            QToolButton {{
                background: {color};
                border: 2px solid transparent;
                border-radius: 14px;
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
            lambda _checked=False, selected=color: owner._set_accent_from_settings(
                selected
            )
        )
        owner._settings_accent_buttons[color] = button
        owner._settings_accent_group.addButton(button)
        chips_layout.addWidget(button)

    chips_layout.addStretch(1)
    layout.addWidget(label, 0, 0)
    layout.addWidget(chips, 0, 1)
    return row


def build_settings_about_section(owner: Any) -> QFrame:
    version_label = QLabel()
    version_label.setObjectName("CardTitle")
    owner._bind_text(version_label, "about.version", version=APP_VERSION)

    license_label = QLabel()
    license_label.setObjectName("Muted")
    owner._bind_text(license_label, "about.license.detail")

    privacy_label = QLabel()
    privacy_label.setObjectName("Muted")
    privacy_label.setWordWrap(True)
    owner._bind_text(privacy_label, "about.privacy")

    storage_label = QLabel()
    storage_label.setObjectName("Muted")
    storage_label.setWordWrap(True)
    owner._bind_text(storage_label, "settings.storage_path")

    github_button = owner._make_button("github.repository", owner._open_github)

    panel = QFrame()
    panel.setObjectName("SettingsSubPanel")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(10, 9, 10, 9)
    layout.setSpacing(7)
    layout.addWidget(version_label)
    layout.addWidget(license_label)
    layout.addWidget(privacy_label)
    layout.addWidget(storage_label)
    layout.addWidget(github_button, alignment=Qt.AlignmentFlag.AlignLeft)
    return panel
