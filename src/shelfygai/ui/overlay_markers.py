from __future__ import annotations

import ctypes
import logging
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QGuiApplication,
    QIcon,
    QMouseEvent,
    QPainter,
    QPainterPath,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from shelfygai.core.models import OverlayGroup
from shelfygai.i18n import tr
from shelfygai.performance import log_performance

LOGGER = logging.getLogger(__name__)
FULLSCREEN_CHECK_INTERVAL_MS = 1_000
MONITOR_DEFAULTTONEAREST = 2


class _RECT(ctypes.Structure):
    _fields_ = (
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    )


class _MONITORINFO(ctypes.Structure):
    _fields_ = (
        ("cbSize", ctypes.c_ulong),
        ("rcMonitor", _RECT),
        ("rcWork", _RECT),
        ("dwFlags", ctypes.c_ulong),
    )


@dataclass(frozen=True, slots=True)
class OverlayPopupItem:
    handle: int
    app_name: str
    title: str
    icon: QIcon | None = None


class NativeFullscreenDetector:
    def __init__(self, ignored_window_ids_provider: Callable[[], set[int]]) -> None:
        self._ignored_window_ids_provider = ignored_window_ids_provider

    def is_fullscreen_active(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            hwnd = int(ctypes.windll.user32.GetForegroundWindow())
            if hwnd <= 0 or hwnd in self._ignored_window_ids_provider():
                return False
            window_rect = _foreground_window_rect(hwnd)
            monitor_rect = _monitor_rect_for_window(hwnd)
        except OSError:
            LOGGER.debug("Could not inspect foreground fullscreen state", exc_info=True)
            return False
        except Exception:
            LOGGER.debug("Unexpected fullscreen detection failure", exc_info=True)
            return False
        return is_fullscreen_window_rect(window_rect, monitor_rect)


def is_fullscreen_window_rect(
    window_rect: QRect | tuple[int, int, int, int],
    monitor_rect: QRect | tuple[int, int, int, int],
    *,
    tolerance: int = 2,
) -> bool:
    """Return True when a foreground window covers a monitor rectangle."""

    window_left, window_top, window_right, window_bottom = _rect_edges(window_rect)
    monitor_left, monitor_top, monitor_right, monitor_bottom = _rect_edges(monitor_rect)
    return (
        window_left <= monitor_left + tolerance
        and window_top <= monitor_top + tolerance
        and window_right >= monitor_right - tolerance
        and window_bottom >= monitor_bottom - tolerance
    )


def fullscreen_hidden_group_ids(
    groups: Sequence[OverlayGroup],
    *,
    fullscreen_active: bool,
) -> set[str]:
    if not fullscreen_active:
        return set()
    return {group.id for group in groups if group.hide_during_fullscreen}


class OverlayMarkerWindow(QWidget):
    """Small app-owned marker window used as a safe taskbar-group affordance."""

    positionSaved = Signal(str, str, int, int, str)
    openRequested = Signal(str)
    settingsRequested = Signal(str)
    colorChangeRequested = Signal(str)
    lockChanged = Signal(str, bool)
    hideRequested = Signal(str)
    hoverRequested = Signal(str)
    hoverLeft = Signal(str)

    def __init__(self, group: OverlayGroup, index: int) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self._group = group
        self._index = index
        self._drag_start_global: QPoint | None = None
        self._drag_start_pos: QPoint | None = None
        self._dragged = False
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._hover_timer.timeout.connect(self._emit_hover_requested)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowTitle(f"ShelfyGAI - {group.name}")
        self.setMouseTracking(True)
        self._apply_group(group)
        self._place_at_saved_or_default()
        LOGGER.info("Overlay marker created: group_id=%s name=%r", group.id, group.name)

    @property
    def group_id(self) -> str:
        return self._group.id

    def update_group(self, group: OverlayGroup, index: int) -> None:
        self._group = group
        self._index = index
        self._apply_group(group)

    def show_marker(self) -> None:
        was_visible = self.isVisible()
        self.show()
        self.raise_()
        if not was_visible:
            LOGGER.info("Overlay marker shown: group_id=%s", self._group.id)

    def hide_marker(self) -> None:
        was_visible = self.isVisible()
        self.hide()
        if was_visible:
            LOGGER.info("Overlay marker hidden: group_id=%s", self._group.id)

    def enterEvent(self, event: object) -> None:
        if self._group.show_quick_controls and self.isVisible():
            self._hover_timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event: object) -> None:
        self._hover_timer.stop()
        self.hoverLeft.emit(self._group.id)
        super().leaveEvent(event)

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._group.color))
        path = QPainterPath()
        radius = max(0, min(self._group.corner_radius, min(self.width(), self.height()) // 2))
        path.addRoundedRect(self.rect(), radius, radius)
        painter.drawPath(path)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            LOGGER.info("Overlay marker clicked: group_id=%s button=left", self._group.id)
            self._hover_timer.stop()
            self._drag_start_global = event.globalPosition().toPoint()
            self._drag_start_pos = self.pos()
            self._dragged = False
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            event.buttons() & Qt.MouseButton.LeftButton
            and self._drag_start_global is not None
            and self._drag_start_pos is not None
            and not self._group.locked_position
        ):
            delta = event.globalPosition().toPoint() - self._drag_start_global
            if delta.manhattanLength() > 2:
                self._dragged = True
            self.move(_clamp_point_to_screen(self._drag_start_pos + delta, self.size()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._dragged:
                screen = _screen_for_point(self.frameGeometry().center())
                monitor_id = monitor_id_for_screen(screen)
                edge = taskbar_edge_for_screen(screen)
                self.positionSaved.emit(self._group.id, monitor_id, self.x(), self.y(), edge)
                LOGGER.info(
                    "Overlay marker moved: group_id=%s monitor=%s x=%s y=%s edge=%s",
                    self._group.id,
                    monitor_id,
                    self.x(),
                    self.y(),
                    edge,
                )
            else:
                self.openRequested.emit(self._group.id)
            self._drag_start_global = None
            self._drag_start_pos = None
            self._dragged = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: object) -> None:
        menu = QMenu(self)
        open_action = menu.addAction(tr("overlay.marker.open_group"))
        lock_key = (
            "overlay.marker.unpin_position"
            if self._group.locked_position
            else "overlay.marker.pin_position"
        )
        lock_action = menu.addAction(tr(lock_key))
        color_action = menu.addAction(tr("overlay.marker.change_color"))
        settings_action = menu.addAction(tr("overlay.marker.settings"))
        hide_action = menu.addAction(tr("overlay.marker.hide"))
        chosen = menu.exec(event.globalPos())
        if chosen == open_action:
            self.openRequested.emit(self._group.id)
        elif chosen == lock_action:
            self.lockChanged.emit(self._group.id, not self._group.locked_position)
        elif chosen == color_action:
            self.colorChangeRequested.emit(self._group.id)
        elif chosen == settings_action:
            self.settingsRequested.emit(self._group.id)
        elif chosen == hide_action:
            self.hideRequested.emit(self._group.id)

    def _apply_group(self, group: OverlayGroup) -> None:
        self.setFixedSize(group.marker_width, group.marker_height)
        self.setWindowOpacity(group.opacity)
        self.setWindowTitle(f"ShelfyGAI - {group.name}")
        self._hover_timer.setInterval(max(0, group.hover_delay_ms))
        if group.locked_position:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.update()

    def _place_at_saved_or_default(self) -> None:
        screen = _screen_for_point(self.frameGeometry().center()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        monitor_id = monitor_id_for_screen(screen)
        saved = self._group.position_by_monitor.get(monitor_id)
        if isinstance(saved, dict):
            x = saved.get("x")
            y = saved.get("y")
            if isinstance(x, int) and isinstance(y, int):
                self.move(_clamp_point_to_screen(QPoint(x, y), self.size()))
                return
        self.move(
            default_marker_position(
                screen,
                self.size().width(),
                self.size().height(),
                self._index,
            )
        )

    def _emit_hover_requested(self) -> None:
        if not self._group.show_quick_controls or not self.isVisible():
            return
        LOGGER.info("Overlay marker hover quick controls requested: group_id=%s", self._group.id)
        self.hoverRequested.emit(self._group.id)


class OverlayQuickControls(QWidget):
    openRequested = Signal(str)
    lockChanged = Signal(str, bool)
    settingsRequested = Signal(str)
    leftControls = Signal(str)

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self._group: OverlayGroup | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setObjectName("OverlayQuickControls")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._title = QLabel()
        self._title.setObjectName("CardTitle")
        layout.addWidget(self._title)

        self._group_label = QLabel()
        self._group_label.setObjectName("Muted")
        layout.addWidget(self._group_label)

        self._open_button = _quick_controls_button("overlay.marker.open_group")
        self._lock_button = _quick_controls_button("overlay.marker.pin_position")
        self._settings_button = _quick_controls_button("overlay.marker.settings")
        layout.addWidget(self._open_button)
        layout.addWidget(self._lock_button)
        layout.addWidget(self._settings_button)

        self._open_button.clicked.connect(self._emit_open)
        self._lock_button.clicked.connect(self._emit_lock_change)
        self._settings_button.clicked.connect(self._emit_settings)
        self.setMinimumWidth(190)
        self.setMaximumWidth(240)
        self.setStyleSheet(
            """
            QWidget#OverlayQuickControls {
                background: #1a1f25;
                border: 1px solid #2d333b;
                border-radius: 8px;
            }
            QLabel {
                color: #f3f6f8;
            }
            QLabel#Muted {
                color: #a5afb9;
            }
            QLabel#CardTitle {
                font-weight: 700;
            }
            QPushButton {
                background: #252b33;
                border: 1px solid #2d333b;
                border-radius: 7px;
                padding: 5px 8px;
                color: #f3f6f8;
                text-align: left;
            }
            QPushButton:hover {
                background: #303845;
            }
            """
        )

    def update_group(self, group: OverlayGroup) -> None:
        self._group = group
        self.setProperty("group_id", group.id)
        self._title.setText(tr("overlay.quick_controls.title"))
        self._group_label.setText(group.name)
        lock_key = (
            "overlay.marker.unpin_position"
            if group.locked_position
            else "overlay.marker.pin_position"
        )
        self._open_button.setText(tr("overlay.marker.open_group"))
        self._lock_button.setText(tr(lock_key))
        self._settings_button.setText(tr("overlay.marker.settings"))
        self.adjustSize()

    def leaveEvent(self, event: object) -> None:
        if self._group is not None:
            self.leftControls.emit(self._group.id)
        super().leaveEvent(event)

    def _emit_open(self) -> None:
        if self._group is not None:
            self.openRequested.emit(self._group.id)

    def _emit_lock_change(self) -> None:
        if self._group is not None:
            self.lockChanged.emit(self._group.id, not self._group.locked_position)

    def _emit_settings(self) -> None:
        if self._group is not None:
            self.settingsRequested.emit(self._group.id)


class OverlayGroupPopup(QWidget):
    openWindowRequested = Signal(str, int)
    restoreWindowRequested = Signal(str, int)
    removeWindowRequested = Signal(str, int)
    restoreAllRequested = Signal(str)
    hideAllRequested = Signal(str)
    openShelfyRequested = Signal()

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setObjectName("OverlayGroupPopup")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(10)
        self._title = QLabel()
        self._title.setObjectName("CardTitle")
        self._layout.addWidget(self._title)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setMaximumHeight(260)
        self._items_widget = QWidget()
        self._items_layout = QVBoxLayout(self._items_widget)
        self._items_layout.setContentsMargins(0, 0, 0, 0)
        self._items_layout.setSpacing(8)
        self._scroll.setWidget(self._items_widget)
        self._layout.addWidget(self._scroll)

        self._empty_label = QLabel()
        self._empty_label.setObjectName("Muted")
        self._empty_label.setWordWrap(True)
        self._layout.addWidget(self._empty_label)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self._restore_all_button = _popup_button("overlay.popup.restore_all")
        self._hide_all_button = _popup_button("overlay.popup.hide_all")
        self._open_app_button = _popup_button("overlay.popup.open_shelfygai")
        footer.addWidget(self._restore_all_button)
        footer.addWidget(self._hide_all_button)
        footer.addWidget(self._open_app_button)
        self._layout.addLayout(footer)

        self._restore_all_button.clicked.connect(self._emit_restore_all)
        self._hide_all_button.clicked.connect(self._emit_hide_all)
        self._open_app_button.clicked.connect(self.openShelfyRequested)
        self.setMinimumWidth(360)
        self.setMaximumWidth(460)
        self.setStyleSheet(
            """
            QWidget#OverlayGroupPopup {
                background: #1a1f25;
                border: 1px solid #2d333b;
                border-radius: 8px;
            }
            QLabel {
                color: #f3f6f8;
            }
            QLabel#Muted {
                color: #a5afb9;
            }
            QLabel#CardTitle {
                font-weight: 700;
            }
            QFrame#OverlayPopupRow {
                background: #11161c;
                border: 1px solid #2d333b;
                border-radius: 8px;
            }
            QPushButton {
                background: #252b33;
                border: 1px solid #2d333b;
                border-radius: 7px;
                padding: 5px 8px;
                color: #f3f6f8;
            }
            QPushButton:hover {
                background: #303845;
            }
            """
        )

    def update_content(self, group: OverlayGroup, items: Sequence[OverlayPopupItem]) -> None:
        self.setProperty("group_id", group.id)
        self._title.setText(group.name)
        _clear_layout(self._items_layout)
        self._empty_label.setText(tr("overlay.popup.empty"))
        self._empty_label.setVisible(not items)
        self._scroll.setVisible(bool(items))
        for item in items[:8]:
            self._items_layout.addWidget(self._build_item_row(group.id, item))
        self._items_layout.addStretch(1)
        self._restore_all_button.setEnabled(bool(items))
        self._hide_all_button.setEnabled(True)
        self.adjustSize()

    def _build_item_row(self, group_id: str, item: OverlayPopupItem) -> QFrame:
        row = QFrame()
        row.setObjectName("OverlayPopupRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(8, 8, 8, 8)
        row_layout.setSpacing(8)

        icon_label = QLabel()
        icon_label.setFixedSize(22, 22)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if item.icon is not None and not item.icon.isNull():
            icon_label.setPixmap(item.icon.pixmap(18, 18))
        else:
            icon_label.setText(item.app_name[:1].upper() if item.app_name else "?")
        row_layout.addWidget(icon_label)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        app_label = QLabel(item.app_name or tr("recovery.unknown_app"))
        app_label.setObjectName("CardTitle")
        title_label = QLabel(item.title)
        title_label.setObjectName("Muted")
        title_label.setWordWrap(True)
        text_box.addWidget(app_label)
        text_box.addWidget(title_label)
        row_layout.addLayout(text_box, 1)

        open_button = _popup_button("overlay.popup.open")
        restore_button = _popup_button("overlay.popup.restore")
        remove_button = _popup_button("overlay.popup.remove_from_group")
        open_button.clicked.connect(
            lambda _checked=False, handle=item.handle: self.openWindowRequested.emit(
                group_id,
                handle,
            )
        )
        restore_button.clicked.connect(
            lambda _checked=False, handle=item.handle: self.restoreWindowRequested.emit(
                group_id,
                handle,
            )
        )
        remove_button.clicked.connect(
            lambda _checked=False, handle=item.handle: self.removeWindowRequested.emit(
                group_id,
                handle,
            )
        )
        row_layout.addWidget(open_button)
        row_layout.addWidget(restore_button)
        row_layout.addWidget(remove_button)
        return row

    def _emit_restore_all(self) -> None:
        group_id = self.property("group_id")
        if isinstance(group_id, str):
            self.restoreAllRequested.emit(group_id)

    def _emit_hide_all(self) -> None:
        group_id = self.property("group_id")
        if isinstance(group_id, str):
            self.hideAllRequested.emit(group_id)


class OverlayMarkerManager(QWidget):
    positionSaved = Signal(str, str, int, int, str)
    settingsRequested = Signal(str)
    colorChangeRequested = Signal(str)
    lockChanged = Signal(str, bool)
    windowOpenRequested = Signal(str, int)
    windowRestoreRequested = Signal(str, int)
    windowRemoveRequested = Signal(str, int)
    restoreAllRequested = Signal(str)
    hideAllRequested = Signal(str)
    openShelfyRequested = Signal()

    def __init__(
        self,
        popup_items_provider: Callable[[OverlayGroup], Sequence[OverlayPopupItem]],
        fullscreen_detector: NativeFullscreenDetector | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._popup_items_provider = popup_items_provider
        self._markers: dict[str, OverlayMarkerWindow] = {}
        self._groups: dict[str, OverlayGroup] = {}
        self._hidden_group_ids: set[str] = set()
        self._enabled = False
        self._fullscreen_active = False
        self._fullscreen_detector = fullscreen_detector or NativeFullscreenDetector(
            self._ignored_window_ids
        )
        self._fullscreen_timer = QTimer(self)
        self._fullscreen_timer.setTimerType(Qt.TimerType.VeryCoarseTimer)
        self._fullscreen_timer.setInterval(FULLSCREEN_CHECK_INTERVAL_MS)
        self._fullscreen_timer.timeout.connect(self._check_fullscreen_state)
        self._popup = OverlayGroupPopup()
        self._quick_controls = OverlayQuickControls()
        self._quick_controls_hide_timer = QTimer(self)
        self._quick_controls_hide_timer.setSingleShot(True)
        self._quick_controls_hide_timer.setInterval(350)
        self._quick_controls_hide_timer.timeout.connect(
            self._hide_quick_controls_if_unhovered
        )
        self._popup.openWindowRequested.connect(self.windowOpenRequested)
        self._popup.restoreWindowRequested.connect(self.windowRestoreRequested)
        self._popup.removeWindowRequested.connect(self.windowRemoveRequested)
        self._popup.restoreAllRequested.connect(self.restoreAllRequested)
        self._popup.hideAllRequested.connect(self.hideAllRequested)
        self._popup.openShelfyRequested.connect(self.openShelfyRequested)
        self._quick_controls.openRequested.connect(self._open_group_from_quick_controls)
        self._quick_controls.lockChanged.connect(self._set_marker_lock_from_quick_controls)
        self._quick_controls.settingsRequested.connect(self._open_settings_from_quick_controls)
        self._quick_controls.leftControls.connect(self._schedule_quick_controls_hide)

    def sync(self, groups: Sequence[OverlayGroup], *, enabled: bool) -> None:
        previous_marker_count = len(self._markers)
        self._enabled = enabled
        groups_by_id = {group.id: group for group in groups}
        self._groups = groups_by_id

        if not enabled:
            self._hidden_group_ids.clear()
            self._fullscreen_active = False
            self._configure_fullscreen_timer()
            self.hide_all()
            return

        for group_id in list(self._markers):
            if group_id not in groups_by_id:
                self._markers.pop(group_id).hide_marker()
                if self._quick_controls.property("group_id") == group_id:
                    self._quick_controls.hide()

        for index, group in enumerate(groups):
            if group.id in self._hidden_group_ids:
                marker = self._markers.get(group.id)
                if marker is not None:
                    marker.hide_marker()
                continue
            marker = self._markers.get(group.id)
            if marker is None:
                marker = OverlayMarkerWindow(group, index)
                marker.positionSaved.connect(self.positionSaved)
                marker.openRequested.connect(self.toggle_popup)
                marker.settingsRequested.connect(self.settingsRequested)
                marker.colorChangeRequested.connect(self.colorChangeRequested)
                marker.lockChanged.connect(self.lockChanged)
                marker.hideRequested.connect(self.hide_marker)
                marker.hoverRequested.connect(self.show_quick_controls)
                marker.hoverLeft.connect(self._schedule_quick_controls_hide)
                self._markers[group.id] = marker
            else:
                marker.update_group(group, index)
        self._apply_fullscreen_visibility()
        self._configure_fullscreen_timer()
        self._refresh_open_popup()
        if len(self._markers) != previous_marker_count:
            log_performance(
                "overlay.markers",
                level=logging.DEBUG,
                marker_count=len(self._markers),
                visible_marker_count=self.visible_marker_count(),
                fullscreen_watcher_active=int(self.fullscreen_watcher_active()),
            )

    def marker_count(self) -> int:
        return len(self._markers)

    def visible_marker_count(self) -> int:
        return sum(1 for marker in self._markers.values() if marker.isVisible())

    def fullscreen_watcher_active(self) -> bool:
        return self._fullscreen_timer.isActive()

    def hide_all(self) -> None:
        self._popup.hide()
        self._quick_controls.hide()
        self._quick_controls_hide_timer.stop()
        for marker in self._markers.values():
            marker.hide_marker()

    def hide_marker(self, group_id: str) -> None:
        self._hidden_group_ids.add(group_id)
        marker = self._markers.get(group_id)
        if marker is not None:
            marker.hide_marker()
        if self._popup.isVisible():
            self._popup.hide()
        if self._quick_controls.property("group_id") == group_id:
            self._quick_controls.hide()

    def toggle_popup(self, group_id: str) -> None:
        group = self._groups.get(group_id)
        marker = self._markers.get(group_id)
        if group is None or marker is None:
            return
        if self._group_hidden_by_fullscreen(group):
            return
        self._quick_controls.hide()
        if self._popup.isVisible() and self._popup.property("group_id") == group_id:
            self._popup.hide()
            return
        self._popup.update_content(group, self._popup_items_provider(group))
        self._popup.move(_popup_position_near_marker(marker, self._popup.sizeHint().width()))
        self._popup.show()
        self._popup.raise_()

    def show_quick_controls(self, group_id: str) -> None:
        group = self._groups.get(group_id)
        marker = self._markers.get(group_id)
        if group is None or marker is None:
            return
        if not group.show_quick_controls or self._group_hidden_by_fullscreen(group):
            return
        if not marker.isVisible():
            return
        self._quick_controls_hide_timer.stop()
        self._quick_controls.update_group(group)
        self._quick_controls.move(
            quick_controls_position_near_marker(
                marker,
                self._quick_controls.sizeHint().width(),
                self._quick_controls.sizeHint().height(),
            )
        )
        self._quick_controls.show()
        self._quick_controls.raise_()
        LOGGER.info("Overlay quick controls shown: group_id=%s", group_id)

    def _configure_fullscreen_timer(self) -> None:
        should_run = self._should_run_fullscreen_timer()
        if should_run and not self._fullscreen_timer.isActive():
            self._fullscreen_timer.start()
            log_performance(
                "overlay.fullscreen_watcher",
                level=logging.DEBUG,
                active=1,
                marker_count=len(self._markers),
                visible_marker_count=self.visible_marker_count(),
            )
        elif not should_run and self._fullscreen_timer.isActive():
            self._fullscreen_timer.stop()
            log_performance(
                "overlay.fullscreen_watcher",
                level=logging.DEBUG,
                active=0,
                marker_count=len(self._markers),
                visible_marker_count=self.visible_marker_count(),
            )
        if not should_run and self._fullscreen_active:
            self._fullscreen_active = False
            LOGGER.info("Fullscreen overlay hiding disabled; restoring overlay markers")
            self._apply_fullscreen_visibility()

    def _should_run_fullscreen_timer(self) -> bool:
        if not self._enabled:
            return False
        if self._fullscreen_active:
            return True
        return any(
            group.hide_during_fullscreen
            and group.id not in self._hidden_group_ids
            and group.id in self._markers
            and self._markers[group.id].isVisible()
            for group in self._groups.values()
        )

    def _check_fullscreen_state(self) -> None:
        fullscreen_active = self._fullscreen_detector.is_fullscreen_active()
        if fullscreen_active == self._fullscreen_active:
            return
        self._fullscreen_active = fullscreen_active
        if fullscreen_active:
            LOGGER.info("Fullscreen detected; hiding eligible overlay markers")
        else:
            LOGGER.info("Fullscreen ended; restoring eligible overlay markers")
        self._apply_fullscreen_visibility()

    def _apply_fullscreen_visibility(self) -> None:
        if not self._enabled:
            return
        fullscreen_hidden_ids = fullscreen_hidden_group_ids(
            self._groups.values(),
            fullscreen_active=self._fullscreen_active,
        )
        hidden_count = 0
        restored_count = 0
        if self._fullscreen_active:
            self._popup.hide()
            self._quick_controls.hide()
        for group_id, marker in self._markers.items():
            group = self._groups.get(group_id)
            if group is None:
                continue
            if group_id in self._hidden_group_ids:
                marker.hide_marker()
                continue
            if group_id in fullscreen_hidden_ids:
                if marker.isVisible():
                    hidden_count += 1
                marker.hide_marker()
            else:
                if not marker.isVisible():
                    restored_count += 1
                marker.show_marker()
        if self._fullscreen_active and hidden_count:
            LOGGER.info("Overlay markers hidden due to fullscreen: count=%s", hidden_count)
        elif not self._fullscreen_active and restored_count:
            LOGGER.info("Overlay markers restored after fullscreen: count=%s", restored_count)

    def _group_hidden_by_fullscreen(self, group: OverlayGroup) -> bool:
        return group.id in fullscreen_hidden_group_ids(
            (group,),
            fullscreen_active=self._fullscreen_active,
        )

    def _ignored_window_ids(self) -> set[int]:
        ignored = {int(marker.winId()) for marker in self._markers.values()}
        ignored.add(int(self._popup.winId()))
        ignored.add(int(self._quick_controls.winId()))
        return ignored

    def _open_group_from_quick_controls(self, group_id: str) -> None:
        self._quick_controls.hide()
        self.toggle_popup(group_id)

    def _set_marker_lock_from_quick_controls(self, group_id: str, locked: bool) -> None:
        self._quick_controls.hide()
        self.lockChanged.emit(group_id, locked)

    def _open_settings_from_quick_controls(self, group_id: str) -> None:
        self._quick_controls.hide()
        self.settingsRequested.emit(group_id)

    def _schedule_quick_controls_hide(self, _group_id: str) -> None:
        if self._quick_controls.isVisible():
            self._quick_controls_hide_timer.start()

    def _hide_quick_controls_if_unhovered(self) -> None:
        if not self._quick_controls.isVisible():
            return
        group_id = self._quick_controls.property("group_id")
        marker = self._markers.get(group_id) if isinstance(group_id, str) else None
        cursor_pos = QCursor.pos()
        if marker is not None and marker.frameGeometry().contains(cursor_pos):
            return
        if self._quick_controls.frameGeometry().contains(cursor_pos):
            return
        self._quick_controls.hide()
        LOGGER.info("Overlay quick controls hidden: group_id=%s", group_id)

    def _refresh_open_popup(self) -> None:
        if not self._popup.isVisible():
            return
        group_id = self._popup.property("group_id")
        if not isinstance(group_id, str):
            self._popup.hide()
            return
        group = self._groups.get(group_id)
        if group is None:
            self._popup.hide()
            return
        self._popup.update_content(group, self._popup_items_provider(group))


def monitor_id_for_screen(screen: object | None) -> str:
    if screen is None:
        return "primary"
    name = getattr(screen, "name", lambda: "")()
    geometry = getattr(screen, "geometry", lambda: QRect())()
    if name:
        return f"{name}:{geometry.x()},{geometry.y()},{geometry.width()}x{geometry.height()}"
    return f"screen:{geometry.x()},{geometry.y()},{geometry.width()}x{geometry.height()}"


def _foreground_window_rect(hwnd: int) -> tuple[int, int, int, int]:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetWindowRect.argtypes = (ctypes.c_void_p, ctypes.POINTER(_RECT))
    user32.GetWindowRect.restype = ctypes.c_bool
    rect = _RECT()
    if not user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(rect)):
        error_code = ctypes.get_last_error()
        raise OSError(error_code, f"GetWindowRect failed for hwnd={hwnd}")
    return rect.left, rect.top, rect.right, rect.bottom


def _monitor_rect_for_window(hwnd: int) -> tuple[int, int, int, int]:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.MonitorFromWindow.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
    user32.MonitorFromWindow.restype = ctypes.c_void_p
    user32.GetMonitorInfoW.argtypes = (ctypes.c_void_p, ctypes.POINTER(_MONITORINFO))
    user32.GetMonitorInfoW.restype = ctypes.c_bool

    monitor = user32.MonitorFromWindow(
        ctypes.c_void_p(hwnd),
        MONITOR_DEFAULTTONEAREST,
    )
    if not monitor:
        error_code = ctypes.get_last_error()
        raise OSError(error_code, f"MonitorFromWindow failed for hwnd={hwnd}")

    monitor_info = _MONITORINFO()
    monitor_info.cbSize = ctypes.sizeof(_MONITORINFO)
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(monitor_info)):
        error_code = ctypes.get_last_error()
        raise OSError(error_code, f"GetMonitorInfoW failed for hwnd={hwnd}")

    monitor_rect = monitor_info.rcMonitor
    return (
        monitor_rect.left,
        monitor_rect.top,
        monitor_rect.right,
        monitor_rect.bottom,
    )


def _rect_edges(rect: QRect | tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    if isinstance(rect, QRect):
        return rect.left(), rect.top(), rect.right() + 1, rect.bottom() + 1
    return rect


def taskbar_edge_for_screen(screen: object | None) -> str:
    if screen is None:
        return "bottom"
    return taskbar_edge_from_geometries(screen.geometry(), screen.availableGeometry())


def taskbar_edge_from_geometries(geometry: QRect, available: QRect) -> str:
    margins = {
        "left": max(0, available.left() - geometry.left()),
        "top": max(0, available.top() - geometry.top()),
        "right": max(0, geometry.right() - available.right()),
        "bottom": max(0, geometry.bottom() - available.bottom()),
    }
    edge, size = max(margins.items(), key=lambda item: item[1])
    return edge if size > 0 else "bottom"


def default_marker_position(screen: object, width: int, height: int, index: int) -> QPoint:
    geometry = screen.geometry()
    available = screen.availableGeometry()
    edge = taskbar_edge_from_geometries(geometry, available)
    spacing = 8
    offset = 18 + index * (max(width, 10) + spacing)
    if edge == "top":
        return QPoint(available.left() + offset, available.top() + spacing)
    if edge == "left":
        return QPoint(available.left() + spacing, available.top() + offset)
    if edge == "right":
        return QPoint(available.right() - width - spacing + 1, available.top() + offset)
    return QPoint(available.left() + offset, available.bottom() - height - spacing + 1)


def quick_controls_position_near_marker(
    marker: QWidget,
    popup_width: int,
    popup_height: int,
) -> QPoint:
    marker_rect = marker.frameGeometry()
    screen = _screen_for_point(marker_rect.center())
    available = screen.availableGeometry() if screen is not None else marker_rect
    edge = taskbar_edge_for_screen(screen)
    return quick_controls_position_from_rect(
        marker_rect,
        available,
        edge,
        popup_width,
        popup_height,
    )


def quick_controls_position_from_rect(
    marker_rect: QRect,
    available: QRect,
    edge: str,
    popup_width: int,
    popup_height: int,
) -> QPoint:
    spacing = 8
    if edge == "top":
        x = marker_rect.center().x() - popup_width // 2
        y = marker_rect.bottom() + spacing + 1
        if y + popup_height > available.bottom() + 1:
            y = marker_rect.top() - popup_height - spacing
    elif edge == "left":
        x = marker_rect.right() + spacing + 1
        y = marker_rect.center().y() - popup_height // 2
        if x + popup_width > available.right() + 1:
            x = marker_rect.left() - popup_width - spacing
    elif edge == "right":
        x = marker_rect.left() - popup_width - spacing
        y = marker_rect.center().y() - popup_height // 2
        if x < available.left():
            x = marker_rect.right() + spacing + 1
    else:
        x = marker_rect.center().x() - popup_width // 2
        y = marker_rect.top() - popup_height - spacing
        if y < available.top():
            y = marker_rect.bottom() + spacing + 1

    max_x = available.right() - popup_width + 1
    max_y = available.bottom() - popup_height + 1
    return QPoint(
        max(available.left(), min(x, max_x)),
        max(available.top(), min(y, max_y)),
    )


def _screen_for_point(point: QPoint) -> object | None:
    return QGuiApplication.screenAt(point) or QGuiApplication.primaryScreen()


def _clamp_point_to_screen(point: QPoint, size: object) -> QPoint:
    screen = _screen_for_point(point)
    if screen is None:
        return point
    available = screen.availableGeometry()
    max_x = available.right() - size.width() + 1
    max_y = available.bottom() - size.height() + 1
    return QPoint(
        max(available.left(), min(point.x(), max_x)),
        max(available.top(), min(point.y(), max_y)),
    )


def _popup_position_near_marker(marker: QWidget, popup_width: int) -> QPoint:
    marker_rect = marker.frameGeometry()
    screen = _screen_for_point(marker_rect.center())
    available = screen.availableGeometry() if screen is not None else marker_rect
    x = marker_rect.right() + 10
    y = marker_rect.top()
    if x + popup_width > available.right():
        x = marker_rect.left() - popup_width - 10
    return QPoint(max(available.left(), x), max(available.top(), y))


def _popup_button(text_key: str) -> QPushButton:
    button = QPushButton(tr(text_key))
    button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return button


def _quick_controls_button(text_key: str) -> QPushButton:
    button = QPushButton(tr(text_key))
    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return button


def _clear_layout(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
