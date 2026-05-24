from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

from shelfygai.ui.widgets.animated_button import AnimatedHoverButton


def build_header(owner: Any) -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setSpacing(8)

    title_box = QVBoxLayout()
    title_box.setSpacing(3)
    owner._header_title.setObjectName("HeaderTitle")
    owner._header_subtitle.setObjectName("HeaderSubtitle")
    owner._header_subtitle.setWordWrap(True)
    title_box.addWidget(owner._header_title)
    title_box.addWidget(owner._header_subtitle)

    layout.addLayout(title_box)
    layout.addStretch(1)
    layout.addWidget(owner._loading_label)

    unpin_all_button = AnimatedHoverButton()
    owner._bind_text(unpin_all_button, "action.unpin_all")
    unpin_all_button.clicked.connect(owner._unpin_all)
    layout.addWidget(unpin_all_button)

    reset_button = AnimatedHoverButton()
    reset_button.setObjectName("DangerButton")
    owner._bind_text(reset_button, "action.reset_everything")
    reset_button.clicked.connect(owner._reset_everything)
    layout.addWidget(reset_button)
    return layout
