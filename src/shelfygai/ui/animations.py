from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable
from functools import lru_cache
from typing import Any

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QWidget

FADE_IN_MS = 110
FADE_OUT_MS = 90
HOVER_MS = 90
MOVE_MS = 120
SPI_GETCLIENTAREAANIMATION = 0x1042


@lru_cache(maxsize=1)
def reduced_motion_enabled() -> bool:
    """Return True when the OS asks apps to avoid nonessential animation."""

    if sys.platform != "win32":
        return False
    enabled = ctypes.c_int(1)
    try:
        result = ctypes.windll.user32.SystemParametersInfoW(
            SPI_GETCLIENTAREAANIMATION,
            0,
            ctypes.byref(enabled),
            0,
        )
    except (AttributeError, OSError):
        return False
    return bool(result) and enabled.value == 0


def animation_duration(duration_ms: int) -> int:
    if reduced_motion_enabled():
        return 0
    return max(0, duration_ms)


def fade_widget_in(widget: QWidget, *, duration_ms: int = FADE_IN_MS) -> None:
    duration = animation_duration(duration_ms)
    if duration == 0:
        widget.setGraphicsEffect(None)
        return
    _animate_graphics_opacity(widget, 0.0, 1.0, duration)


def fade_widget_out(
    widget: QWidget,
    *,
    duration_ms: int = FADE_OUT_MS,
    on_finished: Callable[[], None] | None = None,
) -> None:
    duration = animation_duration(duration_ms)
    if duration == 0:
        widget.setGraphicsEffect(None)
        if on_finished is not None:
            on_finished()
        return
    _animate_graphics_opacity(widget, 1.0, 0.0, duration, on_finished=on_finished)


def animate_window_opacity(
    widget: QWidget,
    start: float,
    end: float,
    *,
    duration_ms: int = HOVER_MS,
    on_finished: Callable[[], None] | None = None,
) -> None:
    duration = animation_duration(duration_ms)
    if duration == 0:
        widget.setWindowOpacity(end)
        if on_finished is not None:
            on_finished()
        return
    previous = getattr(widget, "_shelfy_window_opacity_animation", None)
    if isinstance(previous, QPropertyAnimation):
        previous.stop()
    animation = QPropertyAnimation(widget, b"windowOpacity", widget)
    animation.setDuration(duration)
    animation.setStartValue(start)
    animation.setEndValue(end)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.finished.connect(
        lambda: _finish_animation(widget, "_shelfy_window_opacity_animation", on_finished)
    )
    widget._shelfy_window_opacity_animation = animation
    animation.start()


def animate_property(
    target: Any,
    property_name: bytes,
    start: float,
    end: float,
    *,
    duration_ms: int = HOVER_MS,
) -> None:
    duration = animation_duration(duration_ms)
    property_text = property_name.decode("ascii", errors="ignore")
    if duration == 0:
        target.setProperty(property_text, end)
        return
    attr_name = f"_shelfy_{property_text}_animation"
    previous = getattr(target, attr_name, None)
    if isinstance(previous, QPropertyAnimation):
        previous.stop()
    animation = QPropertyAnimation(target, property_name, target)
    animation.setDuration(duration)
    animation.setStartValue(start)
    animation.setEndValue(end)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.finished.connect(lambda: _finish_animation(target, attr_name))
    setattr(target, attr_name, animation)
    animation.start()


def apply_soft_shadow(
    widget: QWidget,
    *,
    blur_radius: int = 28,
    offset_y: int = 8,
    alpha: int = 140,
) -> None:
    """Apply a subtle Windows-utility style shadow to compact popups."""

    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(max(0, blur_radius))
    effect.setOffset(0, offset_y)
    effect.setColor(QColor(0, 0, 0, max(0, min(alpha, 255))))
    widget.setGraphicsEffect(effect)


def _animate_graphics_opacity(
    widget: QWidget,
    start: float,
    end: float,
    duration_ms: int,
    *,
    on_finished: Callable[[], None] | None = None,
) -> None:
    existing_effect = widget.graphicsEffect()
    effect = (
        existing_effect
        if isinstance(existing_effect, QGraphicsOpacityEffect)
        else QGraphicsOpacityEffect(widget)
    )
    effect.setOpacity(start)
    widget.setGraphicsEffect(effect)
    previous = getattr(widget, "_shelfy_fade_animation", None)
    if isinstance(previous, QPropertyAnimation):
        previous.stop()
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration_ms)
    animation.setStartValue(start)
    animation.setEndValue(end)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def finish() -> None:
        if end >= 1.0:
            widget.setGraphicsEffect(None)
        _finish_animation(widget, "_shelfy_fade_animation", on_finished)

    animation.finished.connect(finish)
    widget._shelfy_fade_animation = animation
    animation.start()


def _finish_animation(
    owner: Any,
    attr_name: str,
    callback: Callable[[], None] | None = None,
) -> None:
    setattr(owner, attr_name, None)
    if callback is not None:
        callback()
