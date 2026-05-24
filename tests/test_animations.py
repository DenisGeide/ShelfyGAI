from __future__ import annotations

from shelfygai.ui import animations


def test_animation_duration_respects_reduced_motion(monkeypatch) -> None:
    monkeypatch.setattr(animations, "reduced_motion_enabled", lambda: True)

    assert animations.animation_duration(120) == 0


def test_animation_duration_keeps_fast_default(monkeypatch) -> None:
    monkeypatch.setattr(animations, "reduced_motion_enabled", lambda: False)

    assert animations.animation_duration(120) == 120
