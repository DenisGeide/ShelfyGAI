from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from shelfygai.ui.widgets.selected_window_card import build_selected_window_card


def build_open_windows_page(owner: Any) -> QWidget:
    page = QWidget()
    layout = QHBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)

    layout.addWidget(build_open_windows_panel(owner), 3)
    layout.addWidget(build_selected_window_card(owner), 1)
    return page


def build_open_windows_panel(owner: Any) -> QFrame:
    panel = QFrame()
    panel.setObjectName("Panel")
    panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    layout = QVBoxLayout(panel)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    panel_title = QLabel()
    panel_title.setObjectName("PanelTitle")
    owner._bind_text(panel_title, "label.open_windows")

    control_row = QHBoxLayout()
    control_row.setSpacing(8)
    control_row.addWidget(owner._open_windows_search, 1)

    refresh_button = owner._make_button("action.refresh", owner._request_refresh)
    control_row.addWidget(refresh_button)
    control_row.addWidget(owner._open_windows_auto_refresh_checkbox)

    layout.addWidget(panel_title)
    layout.addLayout(control_row)
    layout.addWidget(owner._available_table, 1)
    layout.addWidget(owner._open_windows_empty_label, 1)
    return panel
