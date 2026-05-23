from __future__ import annotations

from PySide6.QtCore import QRect

from shelfygai.core.models import OverlayGroup
from shelfygai.ui.overlay_markers import (
    fullscreen_hidden_group_ids,
    is_fullscreen_window_rect,
    quick_controls_position_from_rect,
    taskbar_edge_from_geometries,
)


def test_taskbar_edge_detection_bottom() -> None:
    assert (
        taskbar_edge_from_geometries(
            QRect(0, 0, 1920, 1080),
            QRect(0, 0, 1920, 1040),
        )
        == "bottom"
    )


def test_taskbar_edge_detection_top() -> None:
    assert (
        taskbar_edge_from_geometries(
            QRect(0, 0, 1920, 1080),
            QRect(0, 40, 1920, 1040),
        )
        == "top"
    )


def test_taskbar_edge_detection_left() -> None:
    assert (
        taskbar_edge_from_geometries(
            QRect(0, 0, 1920, 1080),
            QRect(80, 0, 1840, 1080),
        )
        == "left"
    )


def test_taskbar_edge_detection_right() -> None:
    assert (
        taskbar_edge_from_geometries(
            QRect(0, 0, 1920, 1080),
            QRect(0, 0, 1840, 1080),
        )
        == "right"
    )


def test_taskbar_edge_detection_falls_back_to_bottom_without_margin() -> None:
    assert (
        taskbar_edge_from_geometries(
            QRect(0, 0, 1920, 1080),
            QRect(0, 0, 1920, 1080),
        )
        == "bottom"
    )


def test_fullscreen_detection_matches_monitor_rect() -> None:
    assert is_fullscreen_window_rect(
        (0, 0, 1920, 1080),
        (0, 0, 1920, 1080),
    )


def test_fullscreen_detection_allows_small_window_border_variance() -> None:
    assert is_fullscreen_window_rect(
        (-1, -1, 1921, 1081),
        (0, 0, 1920, 1080),
    )


def test_fullscreen_detection_rejects_normal_window() -> None:
    assert not is_fullscreen_window_rect(
        (120, 80, 1600, 950),
        (0, 0, 1920, 1080),
    )


def test_fullscreen_detection_accepts_qrect_values() -> None:
    assert is_fullscreen_window_rect(
        QRect(0, 0, 1920, 1080),
        QRect(0, 0, 1920, 1080),
    )


def test_fullscreen_hidden_group_ids_respects_group_setting() -> None:
    groups = [
        OverlayGroup(id="work", name="Work", hide_during_fullscreen=True),
        OverlayGroup(id="chat", name="Chat", hide_during_fullscreen=False),
    ]

    assert fullscreen_hidden_group_ids(groups, fullscreen_active=True) == {"work"}
    assert fullscreen_hidden_group_ids(groups, fullscreen_active=False) == set()


def test_quick_controls_position_for_bottom_taskbar_stays_above_marker() -> None:
    position = quick_controls_position_from_rect(
        QRect(100, 950, 10, 88),
        QRect(0, 0, 1920, 1040),
        "bottom",
        200,
        120,
    )

    assert position.y() < 950
    assert position.x() >= 0


def test_quick_controls_position_for_top_taskbar_stays_below_marker() -> None:
    position = quick_controls_position_from_rect(
        QRect(100, 48, 10, 88),
        QRect(0, 40, 1920, 1040),
        "top",
        200,
        120,
    )

    assert position.y() > 48
    assert position.x() >= 0


def test_quick_controls_position_for_left_taskbar_stays_right_of_marker() -> None:
    position = quick_controls_position_from_rect(
        QRect(88, 200, 10, 88),
        QRect(80, 0, 1840, 1080),
        "left",
        200,
        120,
    )

    assert position.x() > 88


def test_quick_controls_position_for_right_taskbar_stays_left_of_marker() -> None:
    position = quick_controls_position_from_rect(
        QRect(1800, 200, 10, 88),
        QRect(0, 0, 1840, 1080),
        "right",
        200,
        120,
    )

    assert position.x() < 1800
