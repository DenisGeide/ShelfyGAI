from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QCursor, QIcon, QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from shelfygai.i18n import tr
from shelfygai.ui.animations import apply_soft_shadow

SWITCHER_KIND_HIDDEN = "hidden"
SWITCHER_KIND_OVERLAY_GROUP = "overlay_group"
SWITCHER_KIND_PINNED = "pinned"


@dataclass(frozen=True, slots=True)
class SwitcherItem:
    kind: str
    title: str
    subtitle: str
    handle: int | None = None
    group_id: str | None = None
    badge: str = ""
    icon: QIcon | None = None


def matches_switcher_query(item: SwitcherItem, query: str) -> bool:
    tokens = [token for token in query.casefold().split() if token]
    if not tokens:
        return True
    haystack = " ".join(
        (
            item.title,
            item.subtitle,
            item.badge,
            item.kind.replace("_", " "),
        )
    ).casefold()
    return all(token in haystack for token in tokens)


class HiddenWindowSwitcher(QDialog):
    """Compact keyboard-first launcher for hidden, pinned, and overlay-group items."""

    itemActivated = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: tuple[SwitcherItem, ...] = ()
        self.setObjectName("QuickSwitcher")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setModal(False)
        self.setFixedWidth(520)
        apply_soft_shadow(self, blur_radius=34, offset_y=10, alpha=130)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 12, 14, 12)
        root_layout.setSpacing(8)

        self._title = QLabel()
        self._title.setObjectName("PanelTitle")
        self._subtitle = QLabel()
        self._subtitle.setObjectName("Muted")
        self._subtitle.setWordWrap(True)

        self._search = QLineEdit()
        self._search.setObjectName("QuickSwitcherSearch")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._populate)
        self._search.returnPressed.connect(self._activate_current)
        self._search.installEventFilter(self)

        self._list = QListWidget()
        self._list.setObjectName("QuickSwitcherList")
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setMaximumHeight(360)
        self._list.itemActivated.connect(lambda _item: self._activate_current())
        self._list.installEventFilter(self)

        self._empty = QLabel()
        self._empty.setObjectName("EmptyStateBody")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        self._empty.setMinimumHeight(96)

        self._hint = QLabel()
        self._hint.setObjectName("Muted")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        root_layout.addWidget(self._title)
        root_layout.addWidget(self._subtitle)
        root_layout.addWidget(self._search)
        root_layout.addWidget(self._list)
        root_layout.addWidget(self._empty)
        root_layout.addWidget(self._hint)
        self.retranslate()

    def show_switcher(self, items: list[SwitcherItem]) -> None:
        self._items = tuple(items)
        self._search.clear()
        self._populate()
        self._move_to_active_screen()
        self.show()
        self.raise_()
        self.activateWindow()
        self._search.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def retranslate(self) -> None:
        self._title.setText(tr("switcher.title"))
        self._subtitle.setText(tr("switcher.subtitle"))
        self._search.setPlaceholderText(tr("switcher.search_placeholder"))
        self._empty.setText(tr("switcher.empty"))
        self._hint.setText(tr("switcher.hint"))
        self._populate()

    def eventFilter(self, source: object, event: QEvent) -> bool:
        if event.type() != QEvent.Type.KeyPress or not isinstance(event, QKeyEvent):
            return super().eventFilter(source, event)
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.hide()
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._activate_current()
            return True
        if source is self._search and key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            self._move_selection(1 if key == Qt.Key.Key_Down else -1)
            return True
        return super().eventFilter(source, event)

    def _populate(self) -> None:
        query = self._search.text()
        visible_items = [
            item
            for item in self._items
            if matches_switcher_query(item, query)
        ]
        self._list.clear()
        for item in visible_items:
            list_item = QListWidgetItem()
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            list_item.setSizeHint(QSize(0, 54))
            self._list.addItem(list_item)
            self._list.setItemWidget(list_item, _SwitcherRow(item))

        has_items = bool(visible_items)
        self._list.setVisible(has_items)
        self._empty.setVisible(not has_items)
        if has_items:
            self._list.setCurrentRow(0)

    def _move_selection(self, delta: int) -> None:
        count = self._list.count()
        if count == 0:
            return
        current = self._list.currentRow()
        if current < 0:
            current = 0
        self._list.setCurrentRow(max(0, min(current + delta, count - 1)))

    def _activate_current(self) -> None:
        current = self._list.currentItem()
        if current is None:
            return
        item = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(item, SwitcherItem):
            return
        self.hide()
        self.itemActivated.emit(item)

    def _move_to_active_screen(self) -> None:
        app = QApplication.instance()
        screen = app.screenAt(QCursor.pos()) if app is not None else None
        if screen is None and app is not None:
            screen = app.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        size = self.sizeHint()
        self.move(
            available.center().x() - size.width() // 2,
            available.top() + max(72, available.height() // 5),
        )


class _SwitcherRow(QFrame):
    def __init__(self, item: SwitcherItem) -> None:
        super().__init__()
        self.setObjectName("SwitcherRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 6, 9, 6)
        layout.setSpacing(9)

        icon_label = QLabel()
        icon_label.setObjectName("SwitcherIcon")
        icon_label.setFixedSize(28, 28)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if item.icon is not None and not item.icon.isNull():
            icon_label.setPixmap(item.icon.pixmap(20, 20))
        else:
            icon_label.setText(_fallback_letter(item))

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        title = QLabel(item.title)
        title.setObjectName("CardTitle")
        title.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        title.setWordWrap(False)
        subtitle = QLabel(item.subtitle)
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(False)
        text_layout.addWidget(title)
        text_layout.addWidget(subtitle)

        badge = QLabel(item.badge or _badge_for_kind(item.kind))
        badge.setObjectName("SwitcherBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(icon_label)
        layout.addLayout(text_layout, 1)
        layout.addWidget(badge)


def _fallback_letter(item: SwitcherItem) -> str:
    source = item.title.strip() or item.subtitle.strip() or "S"
    return source[:1].upper()


def _badge_for_kind(kind: str) -> str:
    if kind == SWITCHER_KIND_HIDDEN:
        return tr("switcher.badge.hidden")
    if kind == SWITCHER_KIND_OVERLAY_GROUP:
        return tr("switcher.badge.overlay_group")
    if kind == SWITCHER_KIND_PINNED:
        return tr("switcher.badge.pinned")
    return ""
