from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QSizePolicy, QVBoxLayout

from shelfygai.ui.widgets.animated_button import AnimatedHoverButton


class EmptyStateWidget(QFrame):
    """Calm reusable empty state for pages, tables, and compact popups."""

    def __init__(self, *, minimum_height: int = 108, compact: bool = False) -> None:
        super().__init__()
        self.setObjectName("EmptyState")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(minimum_height)
        self.setVisible(False)

        self._title_label = QLabel()
        self._title_label.setObjectName("EmptyStateTitle")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setWordWrap(True)

        self._body_label = QLabel()
        self._body_label.setObjectName("EmptyStateBody")
        self._body_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._body_label.setWordWrap(True)

        self._action_button: QPushButton = AnimatedHoverButton()
        self._action_button.setVisible(False)
        self._has_action_callback = False

        layout = QVBoxLayout(self)
        side_padding = 12 if compact else 18
        layout.setContentsMargins(side_padding, 10, side_padding, 10)
        layout.setSpacing(6)
        layout.addStretch(1)
        layout.addWidget(self._title_label)
        layout.addWidget(self._body_label)
        layout.addWidget(self._action_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)

    def setText(self, text: str) -> None:
        title, _, body = text.partition("\n")
        self.set_content(title.strip(), body.strip())

    def text(self) -> str:
        body = self._body_label.text().strip()
        if body:
            return f"{self._title_label.text()}\n{body}"
        return self._title_label.text()

    def set_content(self, title: str, body: str = "") -> None:
        self._title_label.setText(title)
        self._body_label.setText(body)
        self._body_label.setVisible(bool(body))

    def set_action(self, text: str, callback: object | None = None) -> None:
        self._has_action_callback = callable(callback)
        self.setActionText(text)
        if callable(callback):
            self._action_button.clicked.connect(callback)

    def setActionText(self, text: str) -> None:
        self._action_button.setText(text)
        self._action_button.setVisible(bool(text) and self._has_action_callback)

    def setAlignment(self, alignment: Qt.AlignmentFlag) -> None:
        self._title_label.setAlignment(alignment)
        self._body_label.setAlignment(alignment)

    def setWordWrap(self, enabled: bool) -> None:
        self._title_label.setWordWrap(enabled)
        self._body_label.setWordWrap(enabled)
