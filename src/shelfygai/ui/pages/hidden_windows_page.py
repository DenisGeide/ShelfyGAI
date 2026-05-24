from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget


def build_hidden_windows_page(owner: Any) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    action_row = QHBoxLayout()
    action_row.setSpacing(7)
    action_row.addStretch(1)
    action_row.addWidget(
        owner._make_button(
            "action.restore",
            lambda: owner._restore_selected(owner._shelf_table),
            primary=True,
        )
    )
    action_row.addWidget(owner._make_button("action.restore_all", owner._restore_all))
    action_row.addWidget(
        owner._make_button(
            "action.move_to_overlay_group",
            owner._move_selected_hidden_to_overlay_group,
        )
    )
    action_row.addWidget(
        owner._make_button(
            "action.remove_from_overlay_group",
            owner._remove_selected_from_overlay_group,
        )
    )
    layout.addLayout(action_row)
    layout.addWidget(owner._shelf_table, 1)
    layout.addWidget(owner._shelf_empty_label, 1)
    return page
