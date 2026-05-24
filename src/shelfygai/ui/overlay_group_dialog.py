from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
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

from shelfygai.core.models import OverlayGroup
from shelfygai.i18n import tr
from shelfygai.ui.widgets.animated_button import AnimatedHoverButton

GROUP_ID_ROLE = Qt.ItemDataRole.UserRole


class OverlayGroupChoiceRow(QFrame):
    def __init__(self, group: OverlayGroup, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._group_id = group.id
        self._search_text = group.name.lower()
        self.setObjectName("OverlayGroupChoiceRow")
        self.setProperty("selected", False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        swatch = QFrame()
        swatch.setObjectName("OverlayGroupColorSwatch")
        swatch.setFixedSize(12, 30)
        swatch.setStyleSheet(
            "QFrame#OverlayGroupColorSwatch {"
            f"background: {group.color};"
            "border: 1px solid rgba(255, 255, 255, 0.18);"
            "border-radius: 5px;"
            "}"
        )

        copy_box = QVBoxLayout()
        copy_box.setContentsMargins(0, 0, 0, 0)
        copy_box.setSpacing(2)

        name_label = QLabel(group.name)
        name_label.setObjectName("CardTitle")
        name_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

        count = len(group.assigned_window_ids)
        count_key = (
            "dialog.choose_overlay_group.count_one"
            if count == 1
            else "dialog.choose_overlay_group.count_many"
        )
        count_label = QLabel(tr(count_key, count=count))
        count_label.setObjectName("Muted")
        count_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

        copy_box.addWidget(name_label)
        copy_box.addWidget(count_label)

        layout.addWidget(swatch)
        layout.addLayout(copy_box, 1)

    @property
    def group_id(self) -> str:
        return self._group_id

    @property
    def search_text(self) -> str:
        return self._search_text

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)


class OverlayGroupChoiceDialog(QDialog):
    def __init__(
        self,
        groups: Sequence[OverlayGroup],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._groups = list(groups)
        self._rows_by_group_id: dict[str, OverlayGroupChoiceRow] = {}
        self._search_edit: QLineEdit | None = None

        self.setObjectName("OverlayGroupChoiceDialog")
        self.setWindowTitle(tr("dialog.choose_overlay_group.title"))
        self.setModal(True)
        self.setMinimumWidth(380)
        self.setMaximumWidth(460)
        self.resize(420, 280 if len(self._groups) <= 5 else 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(12)

        title = QLabel(tr("dialog.choose_overlay_group.title"))
        title.setObjectName("PanelTitle")
        subtitle = QLabel(tr("dialog.choose_overlay_group.message"))
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        if len(self._groups) > 5:
            self._search_edit = QLineEdit()
            self._search_edit.setPlaceholderText(tr("placeholder.overlay_group_search"))
            self._search_edit.textChanged.connect(self._filter_groups)
            layout.addWidget(self._search_edit)

        self._list = QListWidget()
        self._list.setObjectName("OverlayGroupChoiceList")
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setUniformItemSizes(False)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._list.currentItemChanged.connect(self._sync_selected_rows)
        self._list.itemDoubleClicked.connect(lambda _item: self._accept_selected())
        self._list.setMaximumHeight(min(300, max(120, len(self._groups) * 58 + 8)))
        layout.addWidget(self._list)

        for group in self._groups:
            item = QListWidgetItem()
            item.setData(GROUP_ID_ROLE, group.id)
            item.setSizeHint(QSize(0, 56))
            row = OverlayGroupChoiceRow(group)
            self._rows_by_group_id[group.id] = row
            self._list.addItem(item)
            self._list.setItemWidget(item, row)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        button_row.addStretch(1)

        self._cancel_button = AnimatedHoverButton(tr("action.cancel"))
        self._cancel_button.clicked.connect(self.reject)

        self._add_button = AnimatedHoverButton(tr("action.add"))
        self._add_button.setObjectName("PrimaryButton")
        self._add_button.setDefault(True)
        self._add_button.clicked.connect(self._accept_selected)

        button_row.addWidget(self._cancel_button)
        button_row.addWidget(self._add_button)
        layout.addLayout(button_row)

        if self._list.count() > 0:
            self._list.setCurrentRow(0)
        self._sync_add_button()

    @property
    def selected_group_id(self) -> str | None:
        item = self._list.currentItem()
        if item is None or item.isHidden():
            return None
        group_id = item.data(GROUP_ID_ROLE)
        return str(group_id) if group_id else None

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self._accept_selected()
            return
        super().keyPressEvent(event)

    def _accept_selected(self) -> None:
        if self.selected_group_id is None:
            return
        self.accept()

    def _filter_groups(self, text: str) -> None:
        query = text.strip().lower()
        first_visible_row = -1
        for row in range(self._list.count()):
            item = self._list.item(row)
            widget = self._list.itemWidget(item)
            visible = True
            if isinstance(widget, OverlayGroupChoiceRow) and query:
                visible = query in widget.search_text
            item.setHidden(not visible)
            if visible and first_visible_row == -1:
                first_visible_row = row

        current = self._list.currentItem()
        if current is None or current.isHidden():
            self._list.setCurrentRow(first_visible_row)
        self._sync_add_button()

    def _sync_selected_rows(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        current_group_id = str(current.data(GROUP_ID_ROLE)) if current is not None else ""
        for group_id, row in self._rows_by_group_id.items():
            row.set_selected(group_id == current_group_id)
        self._sync_add_button()

    def _sync_add_button(self) -> None:
        self._add_button.setEnabled(self.selected_group_id is not None)
