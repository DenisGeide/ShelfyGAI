from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget


def ask_confirmation(parent: QWidget, title: str, message: str) -> bool:
    """Return True when the user accepts a destructive or state-changing action."""

    answer = QMessageBox.question(parent, title, message)
    return answer == QMessageBox.StandardButton.Yes

