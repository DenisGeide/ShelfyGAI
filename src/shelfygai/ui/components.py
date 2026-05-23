from __future__ import annotations

from PySide6.QtCore import QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QApplication, QFrame, QPushButton

WINDOW_HANDLE_MIME = "application/x-shelfygai-window-handle"


class GroupButton(QPushButton):
    windowDropped = Signal(int, str)

    def __init__(self, group_id: str, label: str) -> None:
        super().__init__(label)
        self.group_id = group_id
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: object) -> None:
        if _drag_has_window_handle(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: object) -> None:
        handle = _window_handle_from_drop(event)
        if handle is None:
            event.ignore()
            return
        self.windowDropped.emit(handle, self.group_id)
        event.acceptProposedAction()


class DraggableManagedWindowRow(QFrame):
    def __init__(self, handle: int) -> None:
        super().__init__()
        self._handle = handle
        self._drag_start_position = QPoint()

    def mousePressEvent(self, event: object) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_position = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: object) -> None:
        if not event.buttons() & Qt.MouseButton.LeftButton:
            return
        distance = (event.position().toPoint() - self._drag_start_position).manhattanLength()
        if distance < QApplication.startDragDistance():
            return

        mime_data = QMimeData()
        mime_data.setData(WINDOW_HANDLE_MIME, str(self._handle).encode("ascii"))

        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(Qt.DropAction.MoveAction)


def _drag_has_window_handle(event: object) -> bool:
    return event.mimeData().hasFormat(WINDOW_HANDLE_MIME)


def _window_handle_from_drop(event: object) -> int | None:
    if not _drag_has_window_handle(event):
        return None
    try:
        return int(bytes(event.mimeData().data(WINDOW_HANDLE_MIME)).decode("ascii"))
    except ValueError:
        return None
