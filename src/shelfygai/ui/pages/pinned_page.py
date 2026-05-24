from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget


def build_pinned_page(owner: Any) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    action_row = QHBoxLayout()
    action_row.setSpacing(7)
    action_row.addStretch(1)
    action_row.addWidget(
        owner._make_button("action.move_up", lambda: owner._move_pinned_selection(-1))
    )
    action_row.addWidget(
        owner._make_button("action.move_down", lambda: owner._move_pinned_selection(1))
    )
    action_row.addWidget(
        owner._make_button(
            "action.bring_to_front",
            owner._bring_pinned_selection_to_front,
        )
    )
    action_row.addWidget(
        owner._make_button("action.unpin", owner._unpin_selected, primary=True)
    )
    action_row.addWidget(owner._make_button("action.unpin_all", owner._unpin_all))
    layout.addLayout(action_row)
    layout.addWidget(owner._pinned_table, 1)
    layout.addWidget(owner._pinned_empty_label, 1)
    return page
