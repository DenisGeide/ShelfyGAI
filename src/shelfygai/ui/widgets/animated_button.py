from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QPushButton

from shelfygai.ui.animations import HOVER_MS, animation_duration


class AnimatedHoverButton(QPushButton):
    """Subtle native-feeling hover polish for regular Qt buttons."""

    def __init__(self, text: str = "") -> None:
        super().__init__(text)
        self._hover_effect = QGraphicsOpacityEffect(self)
        self._hover_effect.setOpacity(0.97)
        self._hover_animation: QPropertyAnimation | None = None
        self.setGraphicsEffect(self._hover_effect)

    def enterEvent(self, event: object) -> None:
        self._animate_opacity(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event: object) -> None:
        self._animate_opacity(0.97)
        super().leaveEvent(event)

    def _animate_opacity(self, target: float) -> None:
        duration = animation_duration(HOVER_MS)
        if duration == 0:
            self._hover_effect.setOpacity(target)
            return
        if self._hover_animation is not None:
            self._hover_animation.stop()
        self._hover_animation = QPropertyAnimation(self._hover_effect, b"opacity", self)
        self._hover_animation.setDuration(duration)
        self._hover_animation.setStartValue(self._hover_effect.opacity())
        self._hover_animation.setEndValue(target)
        self._hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_animation.finished.connect(self._clear_hover_animation)
        self._hover_animation.start()

    def _clear_hover_animation(self) -> None:
        self._hover_animation = None
