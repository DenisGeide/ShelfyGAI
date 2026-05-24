from __future__ import annotations

import ctypes
import logging
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QTimer,
    Signal,
)
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
from shelfygai.ui.animations import (
    FADE_IN_MS,
    FADE_OUT_MS,
    HOVER_MS,
    MOVE_MS,
    animate_property,
    animate_window_opacity,
    animation_duration,
    apply_soft_shadow,
)
from shelfygai.ui.widgets.animated_button import AnimatedHoverButton
from shelfygai.ui.widgets.empty_state_widget import EmptyStateWidget

LOGGER = logging.getLogger(__name__)
FULLSCREEN_CHECK_INTERVAL_MS = 1_000
MONITOR_DEFAULTTONEAREST = 2
HUB_BUTTON_SIZE = 38
SNAP_DISTANCE_PX = 72
HUB_TRAY_AVOIDANCE_PX = 128
TASKBAR_REVEAL_GAP_PX = 8


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


@dataclass(frozen=True, slots=True)
class OverlayDisplayConfig:
    use_unified_hub: bool = True
    use_individual_markers: bool = False
    replace_individual_markers: bool = True
    auto_snap_to_taskbar: bool = True
    compact_mode: bool = True
    marker_spacing: int = 8
    hub_always_visible: bool = True
    hub_auto_hide: bool = False
    hub_opacity: float = 0.94
    hub_position_by_monitor: dict[str, dict[str, object]] = field(default_factory=dict)


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

    def __init__(
        self,
        group: OverlayGroup,
        index: int,
        display_config: OverlayDisplayConfig,
    ) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self._group = group
        self._index = index
        self._display_config = display_config
        self._drag_start_global: QPoint | None = None
        self._drag_start_pos: QPoint | None = None
        self._dragged = False
        self._base_opacity = 0.95
        self._hover_progress = 0.0
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

    def update_group(
        self,
        group: OverlayGroup,
        index: int,
        display_config: OverlayDisplayConfig,
    ) -> None:
        self._group = group
        self._index = index
        self._display_config = display_config
        self._apply_group(group)

    def show_marker(self) -> None:
        was_visible = self.isVisible()
        target_opacity = self._target_opacity()
        if not was_visible:
            self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        animate_window_opacity(
            self,
            self.windowOpacity(),
            target_opacity,
            duration_ms=FADE_IN_MS,
        )
        if not was_visible:
            LOGGER.info("Overlay marker shown: group_id=%s", self._group.id)

    def hide_marker(self) -> None:
        was_visible = self.isVisible()
        if was_visible:
            animate_window_opacity(
                self,
                self.windowOpacity(),
                0.0,
                duration_ms=FADE_OUT_MS,
                on_finished=lambda: self._finish_hide(self._base_opacity),
            )
        else:
            self.hide()
        if was_visible:
            LOGGER.info("Overlay marker hidden: group_id=%s", self._group.id)

    def enterEvent(self, event: object) -> None:
        self._animate_hover(1.0)
        if self._group.show_quick_controls and self.isVisible():
            self._hover_timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event: object) -> None:
        self._animate_hover(0.0)
        self._hover_timer.stop()
        self.hoverLeft.emit(self._group.id)
        super().leaveEvent(event)

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        base_color = QColor(self._group.color)
        hover_color = QColor(base_color).lighter(116)
        painter.setBrush(_mix_color(base_color, hover_color, self._hover_progress))
        path = QPainterPath()
        _, _, _, radius = effective_marker_visuals(self._group, self._display_config)
        radius = max(0, min(radius, min(self.width(), self.height()) // 2))
        path.addRoundedRect(self.rect(), radius, radius)
        painter.drawPath(path)
        if self._hover_progress > 0:
            border = QColor("#ffffff")
            border.setAlphaF(0.08 * self._hover_progress)
            painter.setPen(border)
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
                edge = "free"
                position = self.pos()
                if self._display_config.auto_snap_to_taskbar and screen is not None:
                    position, edge, snapped = snap_point_to_taskbar_edge(
                        self.pos(),
                        self.size(),
                        screen,
                        spacing=self._display_config.marker_spacing,
                    )
                    if snapped:
                        self.move(position)
                self.positionSaved.emit(
                    self._group.id,
                    monitor_id,
                    position.x(),
                    position.y(),
                    edge,
                )
                LOGGER.info(
                    "Overlay marker moved: group_id=%s monitor=%s x=%s y=%s edge=%s",
                    self._group.id,
                    monitor_id,
                    position.x(),
                    position.y(),
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
        width, height, opacity, radius = effective_marker_visuals(
            group,
            self._display_config,
        )
        self.setFixedSize(width, height)
        self._base_opacity = opacity
        self.setWindowOpacity(self._target_opacity())
        self.setWindowTitle(f"ShelfyGAI - {group.name}")
        self._hover_timer.setInterval(max(0, group.hover_delay_ms))
        if group.locked_position:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.update()

    def _get_hover_progress(self) -> float:
        return self._hover_progress

    def _set_hover_progress(self, value: float) -> None:
        self._hover_progress = max(0.0, min(1.0, value))
        self.update()

    hoverProgress = Property(float, _get_hover_progress, _set_hover_progress)

    def _target_opacity(self) -> float:
        return min(1.0, self._base_opacity + (0.06 * self._hover_progress))

    def _animate_hover(self, target: float) -> None:
        animate_property(
            self,
            b"hoverProgress",
            self._hover_progress,
            target,
            duration_ms=HOVER_MS,
        )
        animate_window_opacity(
            self,
            self.windowOpacity(),
            min(1.0, self._base_opacity + (0.06 * target)),
            duration_ms=HOVER_MS,
        )

    def _finish_hide(self, restore_opacity: float) -> None:
        QWidget.hide(self)
        self.setWindowOpacity(restore_opacity)

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
                spacing=self._display_config.marker_spacing,
            )
        )

    def _emit_hover_requested(self) -> None:
        if not self._group.show_quick_controls or not self.isVisible():
            return
        LOGGER.info("Overlay marker hover quick controls requested: group_id=%s", self._group.id)
        self.hoverRequested.emit(self._group.id)


class OverlayHubButton(QWidget):
    """Compact ShelfyGAI-owned hub button placed near the taskbar tray area."""

    positionSaved = Signal(str, int, int, str)
    openRequested = Signal()
    settingsRequested = Signal()
    hideRequested = Signal()

    def __init__(self, display_config: OverlayDisplayConfig) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self._display_config = display_config
        self._groups: tuple[OverlayGroup, ...] = ()
        self._drag_start_global: QPoint | None = None
        self._drag_start_pos: QPoint | None = None
        self._move_animation: QPropertyAnimation | None = None
        self._hovered = False
        self._hover_progress = 0.0
        self._dragged = False
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setWindowTitle(tr("overlay.hub.title"))
        self._apply_config(display_config)
        self._place_at_saved_or_default()
        LOGGER.info("Overlay hub created")

    def update_content(
        self,
        groups: Sequence[OverlayGroup],
        display_config: OverlayDisplayConfig,
    ) -> None:
        self._groups = tuple(groups)
        previous_size = self.size()
        self._display_config = display_config
        self._apply_config(display_config)
        if self.size() != previous_size:
            self._place_at_saved_or_default()
        self.update()

    def show_hub(self) -> None:
        was_visible = self.isVisible()
        target_opacity = self._idle_opacity()
        if not was_visible:
            self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        animate_window_opacity(
            self,
            self.windowOpacity(),
            target_opacity,
            duration_ms=FADE_IN_MS,
        )
        if not was_visible:
            LOGGER.info("Overlay hub shown")

    def hide_hub(self) -> None:
        was_visible = self.isVisible()
        if was_visible:
            target_opacity = self._idle_opacity()
            animate_window_opacity(
                self,
                self.windowOpacity(),
                0.0,
                duration_ms=FADE_OUT_MS,
                on_finished=lambda: self._finish_hide(target_opacity),
            )
        else:
            self.hide()
        if was_visible:
            LOGGER.info("Overlay hub hidden")

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)

        background = _mix_color(
            QColor("#1a1f26"),
            QColor("#252d37"),
            self._hover_progress,
        )
        background.setAlphaF(0.96 + (0.02 * self._hover_progress))
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)
        painter.setBrush(background)
        painter.drawPath(path)

        border = QColor("#303946")
        border.setAlphaF(0.72 + (0.16 * self._hover_progress))
        painter.setPen(border)
        painter.drawPath(path)
        painter.setPen(Qt.PenStyle.NoPen)

        colors = [QColor(group.color) for group in self._groups[:3]]
        if not colors:
            colors = [QColor("#2f81f7"), QColor("#55c2a2"), QColor("#f0b429")]
        line_width = max(14, self.width() - 16)
        x = (self.width() - line_width) // 2
        y = 10
        for index, color in enumerate(colors):
            color.setAlphaF(0.95)
            painter.setBrush(color)
            painter.drawRoundedRect(x, y + index * 7, line_width, 4, 2, 2)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
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
        ):
            self._stop_move_animation()
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
                edge = "free"
                position = self.pos()
                if self._display_config.auto_snap_to_taskbar and screen is not None:
                    position, edge, snapped = snap_point_to_taskbar_edge(
                        self.pos(),
                        self.size(),
                        screen,
                        spacing=self._display_config.marker_spacing,
                        avoid_tray=True,
                    )
                    if snapped:
                        self._move_to(position, animate=True)
                self.positionSaved.emit(monitor_id, position.x(), position.y(), edge)
                LOGGER.info(
                    "Overlay hub moved: monitor=%s x=%s y=%s edge=%s",
                    monitor_id,
                    position.x(),
                    position.y(),
                    edge,
                )
            else:
                LOGGER.info("Overlay hub clicked")
                self.openRequested.emit()
            self._drag_start_global = None
            self._drag_start_pos = None
            self._dragged = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: object) -> None:
        menu = QMenu(self)
        open_action = menu.addAction(tr("overlay.hub.open"))
        settings_action = menu.addAction(tr("overlay.marker.settings"))
        hide_action = menu.addAction(tr("overlay.hub.hide"))
        chosen = menu.exec(event.globalPos())
        if chosen == open_action:
            self.openRequested.emit()
        elif chosen == settings_action:
            self.settingsRequested.emit()
        elif chosen == hide_action:
            self.hideRequested.emit()

    def enterEvent(self, event: object) -> None:
        self._hovered = True
        self._animate_hover(1.0)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: object) -> None:
        self._hovered = False
        self._animate_hover(0.0)
        self.update()
        super().leaveEvent(event)

    def refresh_taskbar_bounds(self) -> None:
        if self._drag_start_global is not None:
            return
        screen = _screen_for_point(self.frameGeometry().center())
        if screen is None:
            return
        monitor_id = monitor_id_for_screen(screen)
        saved = self._display_config.hub_position_by_monitor.get(monitor_id)
        saved_edge = saved.get("edge") if isinstance(saved, dict) else None
        if saved_edge == "free" or not self._display_config.auto_snap_to_taskbar:
            target = _clamp_point_to_screen(self.pos(), self.size())
        else:
            edge = taskbar_edge_for_screen(screen)
            target = smart_hub_edge_point(
                self.pos(),
                self.size(),
                screen.availableGeometry(),
                edge,
                spacing=self._display_config.marker_spacing,
            )
        if target != self.pos():
            self._move_to(target, animate=True)

    def _apply_config(self, display_config: OverlayDisplayConfig) -> None:
        size = HUB_BUTTON_SIZE if display_config.compact_mode else 44
        self.setFixedSize(size, size)
        self._apply_idle_opacity()

    def _apply_idle_opacity(self) -> None:
        if self.isVisible():
            animate_window_opacity(
                self,
                self.windowOpacity(),
                self._idle_opacity(),
                duration_ms=HOVER_MS,
            )
        else:
            self.setWindowOpacity(self._idle_opacity())

    def _active_opacity(self) -> float:
        return _clamp_float(self._display_config.hub_opacity, 0.25, 1.0)

    def _idle_opacity(self) -> float:
        active_opacity = self._active_opacity()
        if (
            self._display_config.hub_auto_hide
            and not self._display_config.hub_always_visible
        ):
            return min(active_opacity, 0.34)
        return active_opacity

    def _place_at_saved_or_default(self) -> None:
        screen = _screen_for_point(self.frameGeometry().center()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        monitor_id = monitor_id_for_screen(screen)
        saved = self._display_config.hub_position_by_monitor.get(monitor_id)
        if isinstance(saved, dict):
            x = saved.get("x")
            y = saved.get("y")
            edge = saved.get("edge")
            if isinstance(x, int) and isinstance(y, int):
                if edge == "free" or not self._display_config.auto_snap_to_taskbar:
                    self._move_to(
                        _clamp_point_to_screen(QPoint(x, y), self.size()),
                        animate=False,
                    )
                    return
                self._move_to(
                    smart_hub_edge_point(
                        QPoint(x, y),
                        self.size(),
                        screen.availableGeometry(),
                        taskbar_edge_for_screen(screen),
                        spacing=self._display_config.marker_spacing,
                    ),
                    animate=False,
                )
                return
        self._move_to(
            default_hub_position(
                screen,
                self.size().width(),
                self.size().height(),
                spacing=self._display_config.marker_spacing,
            ),
            animate=False,
        )

    def _move_to(self, position: QPoint, *, animate: bool) -> None:
        if not animate or not self.isVisible() or animation_duration(MOVE_MS) == 0:
            self.move(position)
            return
        self._stop_move_animation()
        self._move_animation = QPropertyAnimation(self, b"pos", self)
        self._move_animation.setDuration(MOVE_MS)
        self._move_animation.setStartValue(self.pos())
        self._move_animation.setEndValue(position)
        self._move_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._move_animation.finished.connect(self._clear_move_animation)
        self._move_animation.start()

    def _stop_move_animation(self) -> None:
        if self._move_animation is not None:
            self._move_animation.stop()
            self._move_animation = None

    def _clear_move_animation(self) -> None:
        self._move_animation = None

    def _get_hover_progress(self) -> float:
        return self._hover_progress

    def _set_hover_progress(self, value: float) -> None:
        self._hover_progress = max(0.0, min(1.0, value))
        self.update()

    hoverProgress = Property(float, _get_hover_progress, _set_hover_progress)

    def _animate_hover(self, target: float) -> None:
        animate_property(
            self,
            b"hoverProgress",
            self._hover_progress,
            target,
            duration_ms=HOVER_MS,
        )
        target_opacity = self._active_opacity() if target else self._idle_opacity()
        animate_window_opacity(
            self,
            self.windowOpacity(),
            target_opacity,
            duration_ms=HOVER_MS,
        )

    def _finish_hide(self, restore_opacity: float) -> None:
        QWidget.hide(self)
        self.setWindowOpacity(restore_opacity)


class OverlayHubPopup(QWidget):
    groupOpenRequested = Signal(str)
    openWindowRequested = Signal(str, int)
    restoreWindowRequested = Signal(str, int)
    removeWindowRequested = Signal(str, int)
    bringToFrontRequested = Signal(str, int)
    restoreAllRequested = Signal(str)
    hideAllRequested = Signal(str)
    openShelfyRequested = Signal()

    def __init__(
        self,
        popup_items_provider: Callable[[OverlayGroup], Sequence[OverlayPopupItem]],
    ) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self._popup_items_provider = popup_items_provider
        self._groups: tuple[OverlayGroup, ...] = ()
        self._expanded_group_ids: set[str] = set()
        self._fade_closing = False
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setObjectName("OverlayHubPopup")
        apply_soft_shadow(self, blur_radius=30, offset_y=8, alpha=130)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 9)
        layout.setSpacing(7)

        self._title = QLabel()
        self._title.setObjectName("CardTitle")
        layout.addWidget(self._title)

        self._groups_widget = QWidget()
        self._groups_layout = QVBoxLayout(self._groups_widget)
        self._groups_layout.setContentsMargins(0, 0, 0, 0)
        self._groups_layout.setSpacing(6)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setMaximumHeight(310)
        self._scroll.setWidget(self._groups_widget)
        layout.addWidget(self._scroll)

        self._empty_label = EmptyStateWidget(minimum_height=96, compact=True)
        layout.addWidget(self._empty_label)

        self._open_app_button = _popup_button("overlay.popup.open_shelfygai")
        layout.addWidget(self._open_app_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self._open_app_button.clicked.connect(self.openShelfyRequested)

        self.setMinimumWidth(315)
        self.setMaximumWidth(410)
        self.setStyleSheet(
            """
            QWidget#OverlayHubPopup {
                background: #1a1f26;
                border: 1px solid #2a3038;
                border-radius: 10px;
            }
            QLabel {
                color: #f4f7fa;
            }
            QLabel#Muted {
                color: #a8b0bb;
            }
            QFrame#EmptyState {
                background: transparent;
                border: none;
            }
            QLabel#EmptyStateTitle {
                color: #f4f7fa;
                font-weight: 700;
                font-size: 13px;
            }
            QLabel#EmptyStateBody {
                color: #a8b0bb;
                font-size: 12px;
            }
            QLabel#CardTitle {
                font-weight: 700;
                font-size: 13px;
            }
            QFrame#OverlayHubGroupRow {
                background: #151a20;
                border: 1px solid #252c35;
                border-radius: 9px;
            }
            QFrame#OverlayHubWindowRow {
                background: #13181e;
                border: 1px solid #242b34;
                border-radius: 9px;
            }
            QFrame#OverlayHubWindowRow:hover,
            QFrame#OverlayHubGroupRow:hover {
                background: #202730;
                border-color: #343c48;
            }
            QFrame#OverlayHubSwatch {
                border-radius: 5px;
            }
            QLabel#OverlayIconFallback {
                background: #222832;
                border: 1px solid #2f3742;
                border-radius: 6px;
                color: #d8dee6;
                font-weight: 700;
            }
            QPushButton {
                background: #222832;
                border: 1px solid #2f3742;
                border-radius: 8px;
                padding: 3px 8px;
                color: #f4f7fa;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #2a323d;
                border-color: #3c4654;
            }
            QPushButton:disabled {
                color: #7d8793;
                background: #1d232b;
                border-color: #252c35;
            }
            QScrollArea {
                background: transparent;
                border: none;
            }
            """
        )

    def update_content(self, groups: Sequence[OverlayGroup]) -> None:
        previous_ids = {group.id for group in groups}
        self._expanded_group_ids.intersection_update(previous_ids)
        self._groups = tuple(groups)
        self._title.setText(tr("overlay.hub.title"))
        self._render_groups()
        self.adjustSize()

    def show_flyout(self) -> None:
        self._fade_closing = False
        if not self.isVisible():
            self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        animate_window_opacity(self, self.windowOpacity(), 1.0, duration_ms=FADE_IN_MS)

    def hide(self) -> None:
        if self._fade_closing or not self.isVisible():
            QWidget.hide(self)
            return
        self._fade_closing = True
        animate_window_opacity(
            self,
            self.windowOpacity(),
            0.0,
            duration_ms=FADE_OUT_MS,
            on_finished=self._finish_hide,
        )

    def _finish_hide(self) -> None:
        QWidget.hide(self)
        self.setWindowOpacity(1.0)
        self._fade_closing = False

    def _render_groups(self) -> None:
        _clear_layout(self._groups_layout)
        self._empty_label.setText(tr("overlay.hub.empty"))
        self._empty_label.setVisible(not self._groups)
        self._scroll.setVisible(bool(self._groups))
        for group in self._groups[:12]:
            self._groups_layout.addWidget(self._build_group_row(group))
            if group.id in self._expanded_group_ids:
                self._groups_layout.addWidget(self._build_windows_panel(group))
        self._groups_layout.addStretch(1)

    def _build_group_row(self, group: OverlayGroup) -> QFrame:
        row = QFrame()
        row.setObjectName("OverlayHubGroupRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(7)

        swatch = QFrame()
        swatch.setObjectName("OverlayHubSwatch")
        swatch.setFixedSize(8, 24)
        swatch.setStyleSheet(
            "QFrame#OverlayHubSwatch {"
            f"background: {group.color};"
            "border-radius: 5px;"
            "}"
        )
        layout.addWidget(swatch)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        name_label = QLabel(group.name)
        name_label.setObjectName("CardTitle")
        count = len(self._popup_items_provider(group))
        count_key = (
            "dialog.choose_overlay_group.count_one"
            if count == 1
            else "dialog.choose_overlay_group.count_many"
        )
        count_label = QLabel(tr(count_key, count=count))
        count_label.setObjectName("Muted")
        text_box.addWidget(name_label)
        text_box.addWidget(count_label)
        layout.addLayout(text_box, 1)

        action_key = (
            "overlay.hub.collapse"
            if group.id in self._expanded_group_ids
            else "overlay.hub.expand"
        )
        open_button = _popup_button(action_key)
        open_button.clicked.connect(
            lambda _checked=False, group_id=group.id: self._toggle_group(group_id)
        )
        layout.addWidget(open_button)
        return row

    def _build_windows_panel(self, group: OverlayGroup) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(5, 0, 5, 2)
        layout.setSpacing(4)

        items = list(self._popup_items_provider(group))
        if not items:
            empty_label = EmptyStateWidget(minimum_height=64, compact=True)
            empty_label.setText(tr("overlay.hub.no_windows"))
            empty_label.setVisible(True)
            layout.addWidget(empty_label)
            return container

        layout.addWidget(self._build_group_action_row(group.id, bool(items)))
        for item in items[:8]:
            layout.addWidget(self._build_window_row(group.id, item))
        if len(items) > 8:
            more_label = QLabel(tr("overlay.hub.more_windows", count=len(items) - 8))
            more_label.setObjectName("Muted")
            layout.addWidget(more_label)
        return container

    def _build_group_action_row(self, group_id: str, has_items: bool) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 1)
        layout.setSpacing(6)

        restore_all_button = _popup_button("overlay.popup.restore_all")
        hide_all_button = _popup_button("overlay.popup.hide_all")
        restore_all_button.setEnabled(has_items)
        restore_all_button.clicked.connect(
            lambda _checked=False: self.restoreAllRequested.emit(group_id)
        )
        hide_all_button.clicked.connect(
            lambda _checked=False: self.hideAllRequested.emit(group_id)
        )
        layout.addWidget(restore_all_button)
        layout.addWidget(hide_all_button)
        layout.addStretch(1)
        return container

    def _build_window_row(self, group_id: str, item: OverlayPopupItem) -> QFrame:
        row = QFrame()
        row.setObjectName("OverlayHubWindowRow")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(7)

        icon_label = QLabel()
        icon_label.setFixedSize(21, 21)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if item.icon is not None and not item.icon.isNull():
            icon_label.setPixmap(item.icon.pixmap(17, 17))
        else:
            icon_label.setObjectName("OverlayIconFallback")
            icon_label.setText(item.app_name[:1].upper() if item.app_name else "?")
        title_row.addWidget(icon_label)

        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        app_label = QLabel(item.app_name)
        app_label.setObjectName("CardTitle")
        title_label = QLabel(item.title)
        title_label.setObjectName("Muted")
        title_label.setWordWrap(True)
        title_label.setMaximumHeight(34)
        text_box.addWidget(app_label)
        text_box.addWidget(title_label)
        title_row.addLayout(text_box, 1)
        layout.addLayout(title_row)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(6)
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
        action_row.addWidget(open_button)
        action_row.addWidget(restore_button)
        action_row.addWidget(remove_button)
        action_row.addStretch(1)
        layout.addLayout(action_row)
        return row

    def _toggle_group(self, group_id: str) -> None:
        if group_id in self._expanded_group_ids:
            self._expanded_group_ids.remove(group_id)
        else:
            self._expanded_group_ids.add(group_id)
        self._render_groups()
        self.adjustSize()


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
        self._fade_closing = False
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setObjectName("OverlayQuickControls")
        apply_soft_shadow(self, blur_radius=26, offset_y=7, alpha=120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)

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
        self.setMinimumWidth(180)
        self.setMaximumWidth(230)
        self.setStyleSheet(
            """
            QWidget#OverlayQuickControls {
                background: #1a1f26;
                border: 1px solid #2a3038;
                border-radius: 10px;
            }
            QLabel {
                color: #f4f7fa;
            }
            QLabel#Muted {
                color: #a8b0bb;
            }
            QLabel#CardTitle {
                font-weight: 700;
            }
            QPushButton {
                background: #222832;
                border: 1px solid #2f3742;
                border-radius: 8px;
                padding: 3px 8px;
                color: #f4f7fa;
                font-size: 12px;
                text-align: left;
            }
            QPushButton:hover {
                background: #2a323d;
                border-color: #3c4654;
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

    def show_controls(self) -> None:
        self._fade_closing = False
        if not self.isVisible():
            self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        animate_window_opacity(self, self.windowOpacity(), 1.0, duration_ms=FADE_IN_MS)

    def hide(self) -> None:
        if self._fade_closing or not self.isVisible():
            QWidget.hide(self)
            return
        self._fade_closing = True
        animate_window_opacity(
            self,
            self.windowOpacity(),
            0.0,
            duration_ms=FADE_OUT_MS,
            on_finished=self._finish_hide,
        )

    def _finish_hide(self) -> None:
        QWidget.hide(self)
        self.setWindowOpacity(1.0)
        self._fade_closing = False

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
        self._fade_closing = False
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setObjectName("OverlayGroupPopup")
        apply_soft_shadow(self, blur_radius=30, offset_y=8, alpha=130)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(10, 10, 10, 9)
        self._layout.setSpacing(7)
        self._title = QLabel()
        self._title.setObjectName("CardTitle")
        self._layout.addWidget(self._title)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setMaximumHeight(300)
        self._items_widget = QWidget()
        self._items_layout = QVBoxLayout(self._items_widget)
        self._items_layout.setContentsMargins(0, 0, 0, 0)
        self._items_layout.setSpacing(6)
        self._scroll.setWidget(self._items_widget)
        self._layout.addWidget(self._scroll)

        self._empty_label = EmptyStateWidget(minimum_height=96, compact=True)
        self._layout.addWidget(self._empty_label)

        footer = QHBoxLayout()
        footer.setSpacing(6)
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
        self.setMinimumWidth(315)
        self.setMaximumWidth(410)
        self.setStyleSheet(
            """
            QWidget#OverlayGroupPopup {
                background: #1a1f26;
                border: 1px solid #2a3038;
                border-radius: 10px;
            }
            QLabel {
                color: #f4f7fa;
            }
            QLabel#Muted {
                color: #a8b0bb;
            }
            QFrame#EmptyState {
                background: transparent;
                border: none;
            }
            QLabel#EmptyStateTitle {
                color: #f4f7fa;
                font-weight: 700;
                font-size: 13px;
            }
            QLabel#EmptyStateBody {
                color: #a8b0bb;
                font-size: 12px;
            }
            QLabel#CardTitle {
                font-weight: 700;
                font-size: 13px;
            }
            QFrame#OverlayPopupRow {
                background: #13181e;
                border: 1px solid #242b34;
                border-radius: 9px;
            }
            QFrame#OverlayPopupRow:hover {
                background: #202730;
                border-color: #343c48;
            }
            QLabel#OverlayIconFallback {
                background: #222832;
                border: 1px solid #2f3742;
                border-radius: 6px;
                color: #d8dee6;
                font-weight: 700;
            }
            QPushButton {
                background: #222832;
                border: 1px solid #2f3742;
                border-radius: 8px;
                padding: 3px 8px;
                color: #f4f7fa;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #2a323d;
                border-color: #3c4654;
            }
            QPushButton:disabled {
                color: #7d8793;
                background: #1d232b;
                border-color: #252c35;
            }
            QScrollArea {
                background: transparent;
                border: none;
            }
            """
        )

    def show_flyout(self) -> None:
        self._fade_closing = False
        if not self.isVisible():
            self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        animate_window_opacity(self, self.windowOpacity(), 1.0, duration_ms=FADE_IN_MS)

    def hide(self) -> None:
        if self._fade_closing or not self.isVisible():
            QWidget.hide(self)
            return
        self._fade_closing = True
        animate_window_opacity(
            self,
            self.windowOpacity(),
            0.0,
            duration_ms=FADE_OUT_MS,
            on_finished=self._finish_hide,
        )

    def _finish_hide(self) -> None:
        QWidget.hide(self)
        self.setWindowOpacity(1.0)
        self._fade_closing = False

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
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(8, 6, 8, 6)
        row_layout.setSpacing(5)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(8)

        icon_label = QLabel()
        icon_label.setFixedSize(22, 22)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if item.icon is not None and not item.icon.isNull():
            icon_label.setPixmap(item.icon.pixmap(18, 18))
        else:
            icon_label.setObjectName("OverlayIconFallback")
            icon_label.setText(item.app_name[:1].upper() if item.app_name else "?")
        content_row.addWidget(icon_label)

        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        app_label = QLabel(item.app_name or tr("recovery.unknown_app"))
        app_label.setObjectName("CardTitle")
        title_label = QLabel(item.title)
        title_label.setObjectName("Muted")
        title_label.setWordWrap(True)
        title_label.setMaximumHeight(34)
        text_box.addWidget(app_label)
        text_box.addWidget(title_label)
        content_row.addLayout(text_box, 1)
        row_layout.addLayout(content_row)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(6)

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
        action_row.addWidget(open_button)
        action_row.addWidget(restore_button)
        action_row.addWidget(remove_button)
        action_row.addStretch(1)
        row_layout.addLayout(action_row)
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
    hubPositionSaved = Signal(str, int, int, str)
    settingsRequested = Signal(str)
    colorChangeRequested = Signal(str)
    lockChanged = Signal(str, bool)
    windowOpenRequested = Signal(str, int)
    windowRestoreRequested = Signal(str, int)
    windowRemoveRequested = Signal(str, int)
    windowBringToFrontRequested = Signal(str, int)
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
        self._hub_hidden = False
        self._enabled = False
        self._fullscreen_active = False
        self._display_config = OverlayDisplayConfig()
        self._hub: OverlayHubButton | None = None
        self._fullscreen_detector = fullscreen_detector or NativeFullscreenDetector(
            self._ignored_window_ids
        )
        self._fullscreen_timer = QTimer(self)
        self._fullscreen_timer.setTimerType(Qt.TimerType.VeryCoarseTimer)
        self._fullscreen_timer.setInterval(FULLSCREEN_CHECK_INTERVAL_MS)
        self._fullscreen_timer.timeout.connect(self._check_fullscreen_state)
        self._popup = OverlayGroupPopup()
        self._hub_popup = OverlayHubPopup(self._popup_items_provider)
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
        self._hub_popup.groupOpenRequested.connect(self._open_group_from_hub)
        self._hub_popup.openWindowRequested.connect(self.windowOpenRequested)
        self._hub_popup.restoreWindowRequested.connect(self.windowRestoreRequested)
        self._hub_popup.removeWindowRequested.connect(self.windowRemoveRequested)
        self._hub_popup.bringToFrontRequested.connect(self.windowBringToFrontRequested)
        self._hub_popup.restoreAllRequested.connect(self.restoreAllRequested)
        self._hub_popup.hideAllRequested.connect(self.hideAllRequested)
        self._hub_popup.openShelfyRequested.connect(self.openShelfyRequested)
        self._quick_controls.openRequested.connect(self._open_group_from_quick_controls)
        self._quick_controls.lockChanged.connect(self._set_marker_lock_from_quick_controls)
        self._quick_controls.settingsRequested.connect(self._open_settings_from_quick_controls)
        self._quick_controls.leftControls.connect(self._schedule_quick_controls_hide)

    def sync(
        self,
        groups: Sequence[OverlayGroup],
        *,
        enabled: bool,
        display_config: OverlayDisplayConfig | None = None,
    ) -> None:
        previous_marker_count = len(self._markers)
        self._enabled = enabled
        self._display_config = display_config or OverlayDisplayConfig()
        groups_by_id = {group.id: group for group in groups}
        self._groups = groups_by_id

        if not enabled:
            self._hidden_group_ids.clear()
            self._hub_hidden = False
            self._fullscreen_active = False
            self._configure_fullscreen_timer()
            self.hide_all()
            return

        self._sync_hub(groups)
        self._sync_individual_markers(groups, groups_by_id)
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
        return len(self._markers) + (1 if self._hub is not None else 0)

    def visible_marker_count(self) -> int:
        marker_count = sum(1 for marker in self._markers.values() if marker.isVisible())
        if self._hub is not None and self._hub.isVisible():
            marker_count += 1
        return marker_count

    def fullscreen_watcher_active(self) -> bool:
        return self._fullscreen_timer.isActive()

    def hide_all(self) -> None:
        self._popup.hide()
        self._hub_popup.hide()
        self._quick_controls.hide()
        self._quick_controls_hide_timer.stop()
        if self._hub is not None:
            self._hub.hide_hub()
        for marker in self._markers.values():
            marker.hide_marker()

    def reset_runtime(self) -> int:
        removed_count = self.marker_count()
        self._fullscreen_timer.stop()
        self._fullscreen_active = False
        self._hidden_group_ids.clear()
        self._hub_hidden = False
        self._popup.hide()
        self._hub_popup.hide()
        self._quick_controls.hide()
        self._quick_controls_hide_timer.stop()
        if self._hub is not None:
            self._hub.hide_hub()
            self._hub.close()
            self._hub.deleteLater()
            self._hub = None
        for marker in self._markers.values():
            marker.hide_marker()
            marker.close()
            marker.deleteLater()
        self._markers.clear()
        LOGGER.info("Overlay marker runtime reset: removed=%s", removed_count)
        return removed_count

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
        self._hub_popup.hide()
        if self._popup.isVisible() and self._popup.property("group_id") == group_id:
            self._popup.hide()
            return
        self._show_group_popup(group, marker)

    def toggle_hub_popup(self) -> None:
        if self._hub is None or self._hub_hidden or self._hub_hidden_by_fullscreen():
            return
        self._quick_controls.hide()
        self._popup.hide()
        if self._hub_popup.isVisible():
            self._hub_popup.hide()
            return
        groups = list(self._groups.values())
        self._hub_popup.update_content(groups)
        self._hub_popup.move(
            _popup_position_near_marker(
                self._hub,
                self._hub_popup.sizeHint().width(),
                self._hub_popup.sizeHint().height(),
            )
        )
        self._hub_popup.show_flyout()
        LOGGER.info("Overlay hub popup shown: group_count=%s", len(groups))

    def toggle_hub_from_hotkey(self) -> bool:
        if (
            not self._enabled
            or self._hub is None
            or self._hub_hidden
            or self._hub_hidden_by_fullscreen()
        ):
            return False
        self.toggle_hub_popup()
        return True

    def open_group_from_switcher(self, group_id: str) -> bool:
        group = self._groups.get(group_id)
        if group is None or not self._enabled or self._group_hidden_by_fullscreen(group):
            return False
        self._quick_controls.hide()
        self._hub_popup.hide()
        anchor = self._markers.get(group_id)
        if anchor is None:
            anchor = self._hub
        if anchor is None or not anchor.isVisible():
            return False
        self._show_group_popup(group, anchor)
        return True

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
        self._quick_controls.show_controls()
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
        if (
            self._hub is not None
            and self._hub.isVisible()
            and self._display_config.use_unified_hub
        ):
            return True
        if (
            self._hub is not None
            and self._hub.isVisible()
            and self._display_config.use_unified_hub
            and any(group.hide_during_fullscreen for group in self._groups.values())
        ):
            return True
        return any(
            group.hide_during_fullscreen
            and group.id not in self._hidden_group_ids
            and group.id in self._markers
            and self._markers[group.id].isVisible()
            for group in self._groups.values()
        )

    def _check_fullscreen_state(self) -> None:
        self._refresh_hub_taskbar_state()
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
            self._hub_popup.hide()
            self._quick_controls.hide()
        if self._hub is not None:
            if self._hub_hidden or self._hub_hidden_by_fullscreen():
                if self._hub.isVisible():
                    hidden_count += 1
                self._hub.hide_hub()
            elif self._display_config.use_unified_hub:
                if not self._hub.isVisible():
                    restored_count += 1
                self._hub.show_hub()
                self._hub.refresh_taskbar_bounds()
        if not self._individual_markers_enabled():
            for marker in self._markers.values():
                marker.hide_marker()
        for group_id, marker in self._markers.items():
            if not self._individual_markers_enabled():
                continue
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

    def _refresh_hub_taskbar_state(self) -> None:
        if self._hub is None or not self._display_config.use_unified_hub:
            return
        if not self._hub.isVisible():
            return
        self._hub.refresh_taskbar_bounds()

    def _group_hidden_by_fullscreen(self, group: OverlayGroup) -> bool:
        return group.id in fullscreen_hidden_group_ids(
            (group,),
            fullscreen_active=self._fullscreen_active,
        )

    def _hub_hidden_by_fullscreen(self) -> bool:
        if not self._fullscreen_active:
            return False
        return any(group.hide_during_fullscreen for group in self._groups.values())

    def _ignored_window_ids(self) -> set[int]:
        ignored = {int(marker.winId()) for marker in self._markers.values()}
        if self._hub is not None:
            ignored.add(int(self._hub.winId()))
        ignored.add(int(self._popup.winId()))
        ignored.add(int(self._hub_popup.winId()))
        ignored.add(int(self._quick_controls.winId()))
        return ignored

    def _sync_hub(self, groups: Sequence[OverlayGroup]) -> None:
        if not self._display_config.use_unified_hub or not groups:
            if self._hub is not None:
                self._hub.hide_hub()
            self._hub_popup.hide()
            return
        if self._hub is None:
            self._hub = OverlayHubButton(self._display_config)
            self._hub.positionSaved.connect(self.hubPositionSaved)
            self._hub.openRequested.connect(self.toggle_hub_popup)
            self._hub.settingsRequested.connect(self._open_hub_settings)
            self._hub.hideRequested.connect(self._hide_hub)
        self._hub.update_content(groups, self._display_config)

    def _sync_individual_markers(
        self,
        groups: Sequence[OverlayGroup],
        groups_by_id: dict[str, OverlayGroup],
    ) -> None:
        if not self._individual_markers_enabled():
            for marker in self._markers.values():
                marker.hide_marker()
            if self._quick_controls.isVisible():
                self._quick_controls.hide()
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
                marker = OverlayMarkerWindow(group, index, self._display_config)
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
                marker.update_group(group, index, self._display_config)

    def _individual_markers_enabled(self) -> bool:
        return self._display_config.use_individual_markers and not (
            self._display_config.use_unified_hub
            and self._display_config.replace_individual_markers
        )

    def _show_group_popup(self, group: OverlayGroup, anchor: QWidget) -> None:
        self._popup.update_content(group, self._popup_items_provider(group))
        self._popup.move(
            _popup_position_near_marker(
                anchor,
                self._popup.sizeHint().width(),
                self._popup.sizeHint().height(),
            )
        )
        self._popup.show_flyout()
        LOGGER.info("Overlay group popup shown: group_id=%s", group.id)

    def _open_group_from_hub(self, group_id: str) -> None:
        group = self._groups.get(group_id)
        if group is None or self._hub is None:
            return
        if self._group_hidden_by_fullscreen(group):
            return
        self._hub_popup.hide()
        self._show_group_popup(group, self._hub)

    def _open_hub_settings(self) -> None:
        group_id = next(iter(self._groups), "")
        self.settingsRequested.emit(group_id)

    def _hide_hub(self) -> None:
        self._hub_hidden = True
        self._hub_popup.hide()
        if self._hub is not None:
            self._hub.hide_hub()

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
        if self._hub_popup.isVisible():
            self._hub_popup.update_content(list(self._groups.values()))
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


def effective_marker_visuals(
    group: OverlayGroup,
    display_config: OverlayDisplayConfig,
) -> tuple[int, int, float, int]:
    if not display_config.compact_mode:
        return (
            group.marker_width,
            group.marker_height,
            group.opacity,
            group.corner_radius,
        )
    return (
        max(6, min(group.marker_width, 10)),
        max(42, min(group.marker_height, 72)),
        max(0.35, min(group.opacity, 0.92)),
        max(8, min(group.corner_radius, 14)),
    )


def default_marker_position(
    screen: object,
    width: int,
    height: int,
    index: int,
    *,
    spacing: int = 8,
) -> QPoint:
    geometry = screen.geometry()
    available = screen.availableGeometry()
    edge = taskbar_edge_from_geometries(geometry, available)
    return default_marker_position_from_rect(
        available,
        edge,
        width,
        height,
        index,
        spacing=spacing,
    )


def default_marker_position_from_rect(
    available: QRect,
    edge: str,
    width: int,
    height: int,
    index: int,
    *,
    spacing: int = 8,
) -> QPoint:
    spacing = max(2, spacing)
    offset = spacing + index * (max(width, 10) + spacing)
    if edge == "top":
        return QPoint(available.right() - width - offset + 1, available.top() + spacing)
    if edge == "left":
        return QPoint(available.left() + spacing, available.bottom() - height - offset + 1)
    if edge == "right":
        return QPoint(
            available.right() - width - spacing + 1,
            available.bottom() - height - offset + 1,
        )
    return QPoint(
        available.right() - width - offset + 1,
        available.bottom() - height - spacing + 1,
    )


def default_hub_position(
    screen: object,
    width: int,
    height: int,
    *,
    spacing: int = 8,
) -> QPoint:
    return default_hub_position_from_rect(
        screen.availableGeometry(),
        taskbar_edge_for_screen(screen),
        width,
        height,
        spacing=spacing,
    )


def default_hub_position_from_rect(
    available: QRect,
    edge: str,
    width: int,
    height: int,
    *,
    spacing: int = 8,
) -> QPoint:
    spacing = _hub_edge_spacing(spacing)
    return smart_hub_edge_point(
        _default_hub_anchor_point(available, edge, width, height, spacing),
        QSize(width, height),
        available,
        edge,
        spacing=spacing,
    )


def _default_hub_anchor_point(
    available: QRect,
    edge: str,
    width: int,
    height: int,
    spacing: int,
) -> QPoint:
    if edge == "top":
        return QPoint(available.right() - width - spacing + 1, available.top() + spacing)
    if edge == "left":
        return QPoint(available.left() + spacing, available.bottom() - height - spacing + 1)
    if edge == "right":
        return QPoint(
            available.right() - width - spacing + 1,
            available.bottom() - height - spacing + 1,
        )
    return QPoint(
        available.right() - width - spacing + 1,
        available.bottom() - height - spacing + 1,
    )


def smart_hub_edge_point(
    point: QPoint,
    size: object,
    available: QRect,
    edge: str,
    *,
    spacing: int = 8,
) -> QPoint:
    spacing = _hub_edge_spacing(spacing)
    clamped = _clamp_point_to_rect(point, size, available)
    width = size.width()
    height = size.height()
    if edge == "top":
        return QPoint(
            _safe_hub_x(clamped.x(), available, width, spacing),
            available.top() + spacing,
        )
    if edge == "left":
        return QPoint(
            available.left() + spacing,
            _safe_hub_y(clamped.y(), available, height, spacing),
        )
    if edge == "right":
        return QPoint(
            available.right() - width - spacing + 1,
            _safe_hub_y(clamped.y(), available, height, spacing),
        )
    return QPoint(
        _safe_hub_x(clamped.x(), available, width, spacing),
        available.bottom() - height - spacing + 1,
    )


def _safe_hub_x(value: int, available: QRect, width: int, spacing: int) -> int:
    minimum = available.left() + spacing
    maximum = available.right() - width - spacing - HUB_TRAY_AVOIDANCE_PX + 1
    if maximum < minimum:
        maximum = available.right() - width - spacing + 1
    return max(minimum, min(value, maximum))


def _safe_hub_y(value: int, available: QRect, height: int, spacing: int) -> int:
    minimum = available.top() + spacing
    maximum = available.bottom() - height - spacing - HUB_TRAY_AVOIDANCE_PX + 1
    if maximum < minimum:
        maximum = available.bottom() - height - spacing + 1
    return max(minimum, min(value, maximum))


def _hub_edge_spacing(spacing: int) -> int:
    return max(TASKBAR_REVEAL_GAP_PX, spacing)


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
    return _clamp_point_to_rect(point, size, screen.availableGeometry())


def _clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def _mix_color(start: QColor, end: QColor, progress: float) -> QColor:
    progress = _clamp_float(progress, 0.0, 1.0)
    mixed = QColor(
        round(start.red() + ((end.red() - start.red()) * progress)),
        round(start.green() + ((end.green() - start.green()) * progress)),
        round(start.blue() + ((end.blue() - start.blue()) * progress)),
    )
    mixed.setAlphaF(start.alphaF() + ((end.alphaF() - start.alphaF()) * progress))
    return mixed


def _clamp_point_to_rect(point: QPoint, size: object, available: QRect) -> QPoint:
    max_x = available.right() - size.width() + 1
    max_y = available.bottom() - size.height() + 1
    return QPoint(
        max(available.left(), min(point.x(), max_x)),
        max(available.top(), min(point.y(), max_y)),
    )


def snap_point_to_taskbar_edge(
    point: QPoint,
    size: object,
    screen: object,
    *,
    spacing: int = 8,
    threshold: int = SNAP_DISTANCE_PX,
    avoid_tray: bool = False,
) -> tuple[QPoint, str, bool]:
    return snap_point_to_taskbar_edge_from_rect(
        point,
        size,
        screen.availableGeometry(),
        taskbar_edge_for_screen(screen),
        spacing=spacing,
        threshold=threshold,
        avoid_tray=avoid_tray,
    )


def snap_point_to_taskbar_edge_from_rect(
    point: QPoint,
    size: object,
    available: QRect,
    edge: str,
    *,
    spacing: int = 8,
    threshold: int = SNAP_DISTANCE_PX,
    avoid_tray: bool = False,
) -> tuple[QPoint, str, bool]:
    spacing = _hub_edge_spacing(spacing) if avoid_tray else max(2, spacing)
    clamped = _clamp_point_to_rect(point, size, available)
    width = size.width()
    height = size.height()
    if edge == "top":
        target_y = available.top() + spacing
        if abs(clamped.y() - target_y) <= threshold:
            target = (
                smart_hub_edge_point(clamped, size, available, "top", spacing=spacing)
                if avoid_tray
                else QPoint(clamped.x(), target_y)
            )
            return target, "top", True
    elif edge == "left":
        target_x = available.left() + spacing
        if abs(clamped.x() - target_x) <= threshold:
            target = (
                smart_hub_edge_point(clamped, size, available, "left", spacing=spacing)
                if avoid_tray
                else QPoint(target_x, clamped.y())
            )
            return target, "left", True
    elif edge == "right":
        target_x = available.right() - width - spacing + 1
        if abs(clamped.x() - target_x) <= threshold:
            target = (
                smart_hub_edge_point(clamped, size, available, "right", spacing=spacing)
                if avoid_tray
                else QPoint(target_x, clamped.y())
            )
            return target, "right", True
    else:
        target_y = available.bottom() - height - spacing + 1
        if abs(clamped.y() - target_y) <= threshold:
            target = (
                smart_hub_edge_point(clamped, size, available, "bottom", spacing=spacing)
                if avoid_tray
                else QPoint(clamped.x(), target_y)
            )
            return target, "bottom", True
    return clamped, "free", False


def _popup_position_near_marker(
    marker: QWidget,
    popup_width: int,
    popup_height: int | None = None,
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
        popup_height or 220,
    )


def _popup_button(text_key: str) -> QPushButton:
    button = AnimatedHoverButton(tr(text_key))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    button.setMinimumHeight(26)
    button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return button


def _quick_controls_button(text_key: str) -> QPushButton:
    button = AnimatedHoverButton(tr(text_key))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    button.setMinimumHeight(26)
    button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return button


def _clear_layout(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
