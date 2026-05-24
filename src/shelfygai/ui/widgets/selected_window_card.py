from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout


def build_selected_window_card(owner: Any) -> QFrame:
    card = QFrame()
    card.setObjectName("Panel")
    card.setMinimumWidth(280)
    card.setMaximumWidth(324)

    layout = QVBoxLayout(card)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    title = QLabel()
    title.setObjectName("PanelTitle")
    owner._bind_text(title, "label.selected_window")

    identity_row = QHBoxLayout()
    identity_row.setSpacing(8)
    text_box = QVBoxLayout()
    text_box.setSpacing(1)
    text_box.addWidget(owner._selected_window_app)
    text_box.addWidget(owner._selected_window_title)
    text_box.addWidget(owner._selected_window_state)
    identity_row.addWidget(owner._selected_window_icon)
    identity_row.addLayout(text_box, 1)

    actions_title = QLabel()
    actions_title.setObjectName("SectionTitle")
    owner._bind_text(actions_title, "label.actions")

    move_button = owner._make_button(
        "action.move_to_shelf",
        owner._shelve_selected,
        primary=True,
    )
    owner._selected_hide_button = move_button
    overlay_group_button = owner._make_button(
        "action.add_to_overlay_group",
        owner._add_selected_to_overlay_group,
    )
    owner._selected_overlay_group_button = overlay_group_button
    pin_button = owner._make_button("action.pin", owner._pin_selected)
    front_button = owner._make_button(
        "action.bring_to_front",
        owner._bring_selected_forward,
    )

    options_title = QLabel()
    options_title.setObjectName("SectionTitle")
    owner._bind_text(options_title, "label.hide_options")

    tray_note = QLabel()
    tray_note.setObjectName("Muted")
    tray_note.setWordWrap(True)
    owner._bind_text(tray_note, "text.tray_hiding_limited")

    layout.addWidget(title)
    layout.addLayout(identity_row)
    layout.addWidget(owner._selected_window_hint)
    layout.addWidget(actions_title)
    layout.addWidget(move_button)
    layout.addWidget(overlay_group_button)
    layout.addWidget(pin_button)
    layout.addWidget(front_button)
    layout.addSpacing(2)
    layout.addWidget(options_title)
    layout.addWidget(owner._hide_taskbar_checkbox)
    layout.addWidget(owner._hide_alt_tab_checkbox)
    layout.addWidget(owner._hide_tray_checkbox)
    layout.addWidget(tray_note)
    layout.addStretch(1)
    owner._update_selected_window_card()
    return card
