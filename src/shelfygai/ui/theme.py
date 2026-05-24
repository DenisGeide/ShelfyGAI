from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True, slots=True)
class ThemeColors:
    window: str
    surface: str
    surface_alt: str
    panel: str
    border: str
    text: str
    muted: str
    button: str
    button_hover: str
    button_pressed: str
    disabled: str


DARK_COLORS = ThemeColors(
    window="#101318",
    surface="#13171d",
    surface_alt="#181d24",
    panel="#1a1f26",
    border="#2a3038",
    text="#f4f7fa",
    muted="#a8b0bb",
    button="#222832",
    button_hover="#2a323d",
    button_pressed="#1d232b",
    disabled="#69727c",
)

LIGHT_COLORS = ThemeColors(
    window="#f5f7fa",
    surface="#ffffff",
    surface_alt="#eef2f6",
    panel="#ffffff",
    border="#d8dee6",
    text="#161a1f",
    muted="#65717e",
    button="#eef2f6",
    button_hover="#e2e8f0",
    button_pressed="#d7dee8",
    disabled="#9aa5b1",
)


def apply_theme(
    app: QApplication,
    theme: str = "dark",
    accent_color: str = "#2f81f7",
) -> None:
    resolved_theme = _resolve_theme(app, theme)
    colors = LIGHT_COLORS if resolved_theme == "light" else DARK_COLORS
    accent = accent_color if _is_hex_color(accent_color) else "#2f81f7"
    accent_hover = QColor(accent).lighter(116).name()
    accent_pressed = QColor(accent).darker(112).name()

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(colors.window))
    palette.setColor(QPalette.WindowText, QColor(colors.text))
    palette.setColor(QPalette.Base, QColor(colors.surface))
    palette.setColor(QPalette.AlternateBase, QColor(colors.surface_alt))
    palette.setColor(QPalette.ToolTipBase, QColor(colors.button))
    palette.setColor(QPalette.ToolTipText, QColor(colors.text))
    palette.setColor(QPalette.Text, QColor(colors.text))
    palette.setColor(QPalette.Button, QColor(colors.button))
    palette.setColor(QPalette.ButtonText, QColor(colors.text))
    palette.setColor(QPalette.Highlight, QColor(accent))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    app.setStyleSheet(
        f"""
        QWidget {{
            font-family: "Segoe UI", Arial, sans-serif;
            font-size: 9.5pt;
            color: {colors.text};
            selection-background-color: {accent};
            selection-color: #ffffff;
        }}
        QWidget:disabled {{
            color: {colors.disabled};
        }}
        QDialog, QMainWindow, QMessageBox {{
            background: {colors.window};
        }}
        QMessageBox QLabel {{
            color: {colors.text};
            font-size: 10pt;
        }}
        QToolTip {{
            background: {colors.button};
            color: {colors.text};
            border: 1px solid {colors.border};
            border-radius: 7px;
            padding: 5px 8px;
        }}
        QMenu {{
            background: {colors.panel};
            border: 1px solid {colors.border};
            border-radius: 10px;
            padding: 5px;
        }}
        QMenu::item {{
            border-radius: 7px;
            padding: 6px 20px 6px 10px;
        }}
        QMenu::item:selected {{
            background: {colors.button_hover};
        }}
        #Sidebar {{
            background: {colors.surface};
            border-right: 1px solid {colors.border};
        }}
        #BrandTitle {{
            font-size: 16pt;
            font-weight: 700;
        }}
        #BrandSubtitle, #HeaderSubtitle, #Muted {{
            color: {colors.muted};
        }}
        #BrandSubtitle {{
            font-size: 9pt;
        }}
        #HeaderTitle {{
            font-size: 17pt;
            font-weight: 700;
        }}
        #HeaderSubtitle {{
            font-size: 9.5pt;
        }}
        #HeroTitle {{
            font-size: 22pt;
            font-weight: 750;
        }}
        #HeroDescription {{
            color: {colors.muted};
            font-size: 11pt;
            line-height: 150%;
        }}
        QPushButton {{
            background: {colors.button};
            border: 1px solid {colors.border};
            border-radius: 8px;
            padding: 5px 10px;
            min-height: 24px;
        }}
        QPushButton:hover {{
            background: {colors.button_hover};
            border-color: {accent};
        }}
        QPushButton:pressed {{
            background: {colors.button_pressed};
        }}
        QPushButton:disabled {{
            color: {colors.disabled};
            background: {colors.surface_alt};
            border-color: {colors.border};
        }}
        QPushButton#PrimaryButton {{
            background: {accent};
            border-color: {accent};
            color: #ffffff;
            font-weight: 650;
        }}
        QPushButton#PrimaryButton:hover {{
            background: {accent_hover};
        }}
        QPushButton#PrimaryButton:pressed {{
            background: {accent_pressed};
        }}
        QPushButton#DangerButton {{
            color: #ffb4ab;
            border-color: #8c3a32;
        }}
        QPushButton#DangerButton:hover {{
            background: #3a1f1d;
            border-color: #e5534b;
        }}
        QPushButton#SidebarButton {{
            background: transparent;
            border: none;
            border-left: 3px solid transparent;
            border-radius: 8px;
            text-align: left;
            padding: 8px 11px 8px 13px;
            min-height: 23px;
            font-weight: 500;
        }}
        QPushButton#SidebarButton:hover {{
            background: {colors.surface_alt};
            border-left-color: {colors.border};
        }}
        QPushButton#SidebarButton[active="true"] {{
            background: {colors.button};
            border-left-color: {accent};
            font-weight: 650;
        }}
        QPushButton#GroupButton {{
            background: transparent;
            border: 1px solid {colors.border};
            border-radius: 8px;
            text-align: left;
            padding: 7px 9px;
        }}
        QPushButton#GroupButton:hover {{
            background: {colors.surface_alt};
            border-color: {accent};
        }}
        QPushButton#GroupButton[active="true"] {{
            background: {colors.button};
            border-color: {accent};
            font-weight: 650;
        }}
        QPushButton#IconButton {{
            min-width: 32px;
            min-height: 30px;
            padding: 5px 8px;
        }}
        QToolButton#ToolIconButton {{
            background: {colors.button};
            border: 1px solid {colors.border};
            border-radius: 8px;
            padding: 5px;
        }}
        QToolButton#ToolIconButton:hover {{
            background: {colors.button_hover};
            border-color: {accent};
        }}
        QToolButton#ToolIconButton:pressed {{
            background: {colors.button_pressed};
        }}
        QFrame#Panel, QFrame#OnboardingPanel {{
            background: {colors.panel};
            border: 1px solid {colors.border};
            border-radius: 10px;
        }}
        QFrame#OnboardingVisual {{
            background: {colors.surface};
            border: 1px solid {colors.border};
            border-radius: 10px;
        }}
        QLabel#OnboardingVisualText {{
            color: {colors.muted};
            font-size: 9pt;
            line-height: 140%;
        }}
        QFrame#AboutHero {{
            background: {colors.panel};
            border: 1px solid {colors.border};
            border-radius: 10px;
        }}
        QFrame#InfoTile {{
            background: {colors.surface_alt};
            border: 1px solid {colors.border};
            border-radius: 10px;
        }}
        QFrame#InfoTile:hover {{
            border-color: {colors.border};
        }}
        QFrame#ManagedGroupCard {{
            background: {colors.panel};
            border: 1px solid {colors.border};
            border-radius: 10px;
        }}
        QFrame#ManagedGroupCard:hover {{
            border-color: {accent};
            background: {colors.surface_alt};
        }}
        QFrame#ManagedWindowRow {{
            background: transparent;
            border-top: 1px solid {colors.surface_alt};
        }}
        QFrame#OverlayGroupChoiceRow {{
            background: transparent;
            border: 1px solid transparent;
            border-radius: 10px;
        }}
        QFrame#OverlayGroupChoiceRow:hover {{
            background: {colors.button_hover};
            border-color: {colors.border};
        }}
        QFrame#OverlayGroupChoiceRow[selected="true"] {{
            background: {accent_pressed};
            border-color: {accent};
        }}
        QDialog#QuickSwitcher {{
            background: {colors.panel};
            border: 1px solid {colors.border};
            border-radius: 10px;
        }}
        QLineEdit#QuickSwitcherSearch {{
            min-height: 30px;
            padding-left: 10px;
            padding-right: 10px;
        }}
        QListWidget#QuickSwitcherList {{
            background: {colors.surface};
            border: 1px solid {colors.border};
            border-radius: 10px;
            padding: 4px;
            outline: none;
        }}
        QListWidget#QuickSwitcherList::item {{
            border-radius: 9px;
            margin: 2px;
        }}
        QListWidget#QuickSwitcherList::item:selected {{
            background: {accent_pressed};
        }}
        QFrame#SwitcherRow {{
            background: transparent;
            border: 1px solid transparent;
            border-radius: 9px;
        }}
        QLabel#SwitcherIcon {{
            background: {colors.button};
            border: 1px solid {colors.border};
            border-radius: 8px;
            font-weight: 700;
        }}
        QLabel#SwitcherBadge {{
            color: {colors.muted};
            background: {colors.button};
            border: 1px solid {colors.border};
            border-radius: 10px;
            padding: 3px 8px;
            font-size: 8.5pt;
        }}
        QFrame#HeroPanel {{
            background: {colors.surface};
            border-right: 1px solid {colors.border};
        }}
        QLabel#AboutLogo {{
            background: {colors.button};
            border: 1px solid {colors.border};
            border-radius: 10px;
        }}
        QLabel#PanelTitle {{
            font-size: 10.5pt;
            font-weight: 700;
        }}
        QLabel#CardTitle {{
            font-size: 10pt;
            font-weight: 700;
        }}
        QLabel#SectionTitle {{
            font-size: 10pt;
            font-weight: 700;
        }}
        QFrame#SettingsSection {{
            background: {colors.panel};
            border: 1px solid {colors.border};
            border-radius: 10px;
        }}
        QFrame#SettingsSubPanel {{
            background: {colors.surface};
            border: 1px solid {colors.border};
            border-radius: 10px;
        }}
        QLabel#SettingsSectionTitle {{
            color: {colors.text};
            font-size: 11pt;
            font-weight: 700;
        }}
        QLabel#SettingsSectionDescription,
        QLabel#SettingDescription {{
            color: {colors.muted};
            font-size: 9pt;
        }}
        QWidget#SettingRow {{
            background: transparent;
        }}
        QToolButton#SettingsSectionToggle {{
            background: {colors.button};
            border: 1px solid {colors.border};
            border-radius: 8px;
            color: {colors.text};
            padding: 4px 9px;
            min-width: 68px;
        }}
        QToolButton#SettingsSectionToggle:hover {{
            background: {colors.button_hover};
            border-color: {accent};
        }}
        QLineEdit#SettingsSearch {{
            min-height: 27px;
            padding-left: 10px;
            padding-right: 10px;
        }}
        QLabel#LoadingPill {{
            color: {colors.muted};
            background: {colors.button};
            border: 1px solid {colors.border};
            border-radius: 13px;
            padding: 5px 11px;
        }}
        QFrame#EmptyState {{
            background: transparent;
            border: none;
        }}
        QLabel#EmptyStateTitle {{
            color: {colors.text};
            font-size: 11pt;
            font-weight: 700;
        }}
        QLabel#EmptyStateBody {{
            color: {colors.muted};
            background: transparent;
            font-size: 9.5pt;
        }}
        QLabel#EmptyState {{
            color: {colors.muted};
            background: transparent;
            border: none;
            padding: 8px;
        }}
        QLabel#IconBadge {{
            background: {colors.button};
            border: 1px solid {colors.border};
            border-radius: 10px;
        }}
        QComboBox, QLineEdit, QKeySequenceEdit, QSpinBox, QDoubleSpinBox {{
            background: {colors.button};
            border: 1px solid {colors.border};
            border-radius: 8px;
            padding: 5px 8px;
            min-height: 23px;
        }}
        QComboBox:hover,
        QLineEdit:hover,
        QKeySequenceEdit:hover,
        QSpinBox:hover,
        QDoubleSpinBox:hover {{
            border-color: {accent};
        }}
        QLineEdit:focus,
        QComboBox:focus,
        QKeySequenceEdit:focus,
        QSpinBox:focus,
        QDoubleSpinBox:focus {{
            border-color: {accent};
        }}
        QComboBox QAbstractItemView {{
            background: {colors.panel};
            border: 1px solid {colors.border};
            selection-background-color: {accent};
            selection-color: #ffffff;
        }}
        QListWidget#OverlayGroupChoiceList {{
            background: {colors.surface};
            border: 1px solid {colors.border};
            border-radius: 10px;
            padding: 4px;
            outline: none;
        }}
        QListWidget#OverlayGroupChoiceList::item {{
            border: none;
            margin: 2px;
        }}
        QListWidget#OverlayGroupChoiceList::item:selected {{
            background: transparent;
        }}
        QListWidget#OverlayGroupsList {{
            background: {colors.surface};
            border: 1px solid {colors.border};
            border-radius: 10px;
            padding: 4px;
            outline: none;
        }}
        QListWidget#OverlayGroupsList::item {{
            border-radius: 8px;
            padding: 6px;
            margin: 2px;
        }}
        QListWidget#OverlayGroupsList::item:hover {{
            background: {colors.button_hover};
        }}
        QListWidget#OverlayGroupsList::item:selected {{
            background: {accent_pressed};
            color: #ffffff;
        }}
        QFrame#OverlayPreviewStage {{
            background: {colors.surface};
            border: 1px solid {colors.border};
            border-radius: 10px;
        }}
        QFrame#OverlayPopupPreview {{
            background: {colors.surface_alt};
            border: 1px solid {colors.border};
            border-radius: 10px;
        }}
        QSlider::groove:horizontal {{
            height: 5px;
            background: {colors.button};
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: {accent};
            width: 14px;
            height: 14px;
            margin: -5px 0;
            border-radius: 7px;
        }}
        QSlider::handle:horizontal:hover {{
            background: {accent_hover};
        }}
        QTableWidget {{
            background: {colors.surface};
            alternate-background-color: {colors.surface_alt};
            border: 1px solid {colors.border};
            border-radius: 10px;
            gridline-color: transparent;
            selection-background-color: {accent_pressed};
            selection-color: #ffffff;
        }}
        QTableWidget::item {{
            padding: 4px 6px;
            border: none;
        }}
        QTableWidget::item:hover {{
            background: {colors.button_hover};
        }}
        QTableWidget::item:selected {{
            background: {accent};
            color: #ffffff;
        }}
        QTableWidget::item:selected:hover {{
            background: {accent_pressed};
        }}
        QHeaderView::section {{
            background: {colors.surface_alt};
            color: {colors.text};
            border: none;
            border-right: 1px solid {colors.border};
            padding: 6px;
            font-weight: 600;
        }}
        QStatusBar {{
            background: {colors.surface};
            border-top: 1px solid {colors.surface_alt};
            color: {colors.muted};
        }}
        QCheckBox {{
            spacing: 8px;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border-radius: 5px;
            border: 1px solid {colors.border};
            background: {colors.surface};
        }}
        QCheckBox::indicator:checked {{
            background: {accent};
            border-color: {accent};
        }}
        QScrollArea {{
            border: none;
            background: transparent;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 10px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical {{
            background: {colors.button_hover};
            border-radius: 5px;
            min-height: 36px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        """
    )


def apply_dark_theme(app: QApplication) -> None:
    apply_theme(app, "dark", "#2f81f7")


def _resolve_theme(app: QApplication, theme: str) -> str:
    if theme == "light":
        return "light"
    if theme == "system":
        color_scheme = app.styleHints().colorScheme()
        if color_scheme == Qt.ColorScheme.Light:
            return "light"
    return "dark"


def _is_hex_color(value: str) -> bool:
    if len(value) != 7 or not value.startswith("#"):
        return False
    return all(character in "0123456789abcdefABCDEF" for character in value[1:])
