from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from shelfygai.core.models import OverlayGroup
from shelfygai.i18n import tr


def build_overlay_groups_page(owner: Any) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)

    description = QLabel()
    description.setObjectName("Muted")
    description.setWordWrap(True)
    owner._bind_text(description, "overlay.description")
    layout.addWidget(description)

    content = QHBoxLayout()
    content.setContentsMargins(0, 0, 0, 0)
    content.setSpacing(12)
    content.addWidget(build_overlay_group_list_panel(owner))
    content.addWidget(build_overlay_feature_panel(owner), 1)
    layout.addLayout(content, 1)
    owner._populate_overlay_groups_list()
    return page


def build_overlay_group_list_panel(owner: Any) -> QFrame:
    panel = QFrame()
    panel.setObjectName("Panel")
    panel.setMinimumWidth(250)
    panel.setMaximumWidth(310)
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(14, 14, 14, 14)
    layout.setSpacing(9)

    title = QLabel()
    title.setObjectName("PanelTitle")
    owner._bind_text(title, "label.overlay_groups_list")

    create_button = owner._make_button(
        "action.create_overlay_group",
        owner._create_overlay_group,
        primary=True,
    )

    layout.addWidget(title)
    layout.addWidget(owner._overlay_enabled_checkbox)
    layout.addWidget(owner._overlay_use_hub_checkbox)
    layout.addWidget(owner._overlay_replace_markers_checkbox)
    layout.addWidget(owner._overlay_individual_markers_checkbox)
    layout.addWidget(create_button)
    layout.addWidget(owner._overlay_groups_list, 1)
    layout.addWidget(owner._overlay_empty_label, 1)
    layout.addWidget(owner._overlay_delete_button)
    return panel


def build_overlay_feature_panel(owner: Any) -> QWidget:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)

    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(0, 0, 6, 0)
    layout.setSpacing(10)

    layout.addWidget(build_overlay_preview_panel(owner))

    section_grid = QGridLayout()
    section_grid.setContentsMargins(0, 0, 0, 0)
    section_grid.setHorizontalSpacing(10)
    section_grid.setVerticalSpacing(10)
    section_grid.setColumnStretch(0, 1)
    section_grid.setColumnStretch(1, 1)
    section_grid.addWidget(build_overlay_appearance_section(owner), 0, 0)
    section_grid.addWidget(build_overlay_behavior_section(owner), 0, 1)
    section_grid.addWidget(build_overlay_position_section(owner), 1, 0)
    section_grid.addWidget(build_overlay_visibility_section(owner), 1, 1)
    layout.addLayout(section_grid)
    layout.addStretch(1)

    scroll.setWidget(content)
    return scroll


def build_overlay_preview_panel(owner: Any) -> QFrame:
    panel = QFrame()
    panel.setObjectName("Panel")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(14, 14, 14, 14)
    layout.setSpacing(10)

    title = QLabel()
    title.setObjectName("PanelTitle")
    owner._bind_text(title, "overlay.preview.title")

    stage = QFrame()
    stage.setObjectName("OverlayPreviewStage")
    stage_layout = QHBoxLayout(stage)
    stage_layout.setContentsMargins(14, 12, 14, 12)
    stage_layout.setSpacing(12)

    owner._overlay_preview_marker.setObjectName("OverlayMarkerPreview")
    owner._overlay_preview_marker.setMinimumSize(8, 44)
    owner._overlay_preview_marker.setMaximumWidth(72)

    popup = QFrame()
    popup.setObjectName("OverlayPopupPreview")
    popup_layout = QVBoxLayout(popup)
    popup_layout.setContentsMargins(12, 10, 12, 10)
    popup_layout.setSpacing(6)

    owner._overlay_preview_group_name.setObjectName("CardTitle")
    owner._overlay_preview_window_count.setObjectName("Muted")
    sample_title = QLabel()
    sample_title.setObjectName("Muted")
    owner._bind_text(sample_title, "overlay.preview.sample_window")

    action_row = QHBoxLayout()
    action_row.setSpacing(8)
    open_button = owner._make_button("overlay.popup.open", lambda: None)
    restore_button = owner._make_button("overlay.popup.restore_all", lambda: None)
    action_row.addWidget(open_button)
    action_row.addWidget(restore_button)
    action_row.addStretch(1)

    popup_layout.addWidget(owner._overlay_preview_group_name)
    popup_layout.addWidget(owner._overlay_preview_window_count)
    popup_layout.addWidget(sample_title)
    popup_layout.addLayout(action_row)

    stage_layout.addWidget(owner._overlay_preview_marker)
    stage_layout.addWidget(popup, 1)

    layout.addWidget(title)
    layout.addWidget(stage)
    return panel


def build_overlay_appearance_section(owner: Any) -> QFrame:
    section = build_overlay_settings_section(owner, "overlay.section.appearance")
    layout = section.layout()
    if isinstance(layout, QVBoxLayout):
        layout.addWidget(owner._overlay_compact_mode_checkbox)
        layout.addWidget(
            build_overlay_slider_setting(
                owner,
                "label.overlay_hub_opacity",
                owner._overlay_hub_opacity_slider,
                owner._overlay_hub_opacity_spin,
            )
        )
        layout.addWidget(
            build_overlay_field(owner, "label.overlay_group_name", owner._overlay_name_edit)
        )
        layout.addWidget(
            build_overlay_field(
                owner,
                "label.overlay_group_color",
                owner._overlay_color_button,
            )
        )
        layout.addWidget(
            build_overlay_slider_setting(
                owner,
                "label.overlay_marker_width",
                owner._overlay_marker_width_slider,
                owner._overlay_marker_width_spin,
            )
        )
        layout.addWidget(
            build_overlay_slider_setting(
                owner,
                "label.overlay_marker_height",
                owner._overlay_marker_height_slider,
                owner._overlay_marker_height_spin,
            )
        )
        layout.addWidget(
            build_overlay_slider_setting(
                owner,
                "label.overlay_opacity",
                owner._overlay_opacity_slider,
                owner._overlay_opacity_spin,
            )
        )
        layout.addWidget(
            build_overlay_slider_setting(
                owner,
                "label.overlay_corner_radius",
                owner._overlay_corner_radius_slider,
                owner._overlay_corner_radius_spin,
            )
        )
    return section


def build_overlay_behavior_section(owner: Any) -> QFrame:
    section = build_overlay_settings_section(owner, "overlay.section.behavior")
    layout = section.layout()
    if isinstance(layout, QVBoxLayout):
        layout.addWidget(owner._overlay_hub_always_visible_checkbox)
        layout.addWidget(owner._overlay_hub_auto_hide_checkbox)
        layout.addWidget(owner._overlay_quick_controls_checkbox)
        layout.addWidget(
            build_overlay_slider_setting(
                owner,
                "label.overlay_hover_delay",
                owner._overlay_hover_delay_slider,
                owner._overlay_hover_delay_spin,
            )
        )
    return section


def build_overlay_position_section(owner: Any) -> QFrame:
    section = build_overlay_settings_section(owner, "overlay.section.position")
    layout = section.layout()
    if isinstance(layout, QVBoxLayout):
        layout.addWidget(owner._overlay_auto_snap_checkbox)
        layout.addWidget(
            build_overlay_slider_setting(
                owner,
                "label.overlay_marker_spacing",
                owner._overlay_marker_spacing_slider,
                owner._overlay_marker_spacing_spin,
            )
        )
        layout.addWidget(owner._overlay_locked_position_checkbox)
        layout.addWidget(
            owner._overlay_reset_position_button,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )
    return section


def build_overlay_visibility_section(owner: Any) -> QFrame:
    section = build_overlay_settings_section(owner, "overlay.section.visibility")
    layout = section.layout()
    if isinstance(layout, QVBoxLayout):
        layout.addWidget(owner._overlay_hide_fullscreen_checkbox)
    return section


def build_overlay_settings_section(owner: Any, title_key: str) -> QFrame:
    section = QFrame()
    section.setObjectName("InfoTile")
    layout = QVBoxLayout(section)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(8)

    title = QLabel()
    title.setObjectName("SectionTitle")
    owner._bind_text(title, title_key)
    layout.addWidget(title)
    return section


def build_overlay_field(owner: Any, label_key: str, widget: QWidget) -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    label = QLabel()
    label.setObjectName("Muted")
    owner._bind_text(label, label_key)
    layout.addWidget(label)
    layout.addWidget(widget)
    return container


def build_overlay_slider_setting(
    owner: Any,
    label_key: str,
    slider: QSlider,
    spinbox: QWidget,
) -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    label = QLabel()
    label.setObjectName("Muted")
    owner._bind_text(label, label_key)

    control_row = QHBoxLayout()
    control_row.setContentsMargins(0, 0, 0, 0)
    control_row.setSpacing(8)
    control_row.addWidget(slider, 1)
    control_row.addWidget(spinbox)

    layout.addWidget(label)
    layout.addLayout(control_row)
    return container


def configure_int_slider_pair(slider: QSlider, spinbox: QSpinBox) -> None:
    slider.setRange(spinbox.minimum(), spinbox.maximum())
    slider.setSingleStep(max(1, spinbox.singleStep()))
    slider.setPageStep(max(5, spinbox.singleStep() * 5))
    slider.valueChanged.connect(spinbox.setValue)
    spinbox.valueChanged.connect(
        lambda value, current_slider=slider: set_slider_value(
            current_slider,
            int(value),
        )
    )


def configure_opacity_slider_pair(owner: Any) -> None:
    owner._overlay_opacity_slider.setRange(20, 100)
    owner._overlay_opacity_slider.setSingleStep(5)
    owner._overlay_opacity_slider.setPageStep(10)
    owner._overlay_opacity_slider.valueChanged.connect(
        lambda value: owner._overlay_opacity_spin.setValue(value / 100)
    )
    owner._overlay_opacity_spin.valueChanged.connect(
        lambda value: set_slider_value(
            owner._overlay_opacity_slider,
            int(round(float(value) * 100)),
        )
    )


def set_slider_value(slider: QSlider, value: int) -> None:
    previous = slider.blockSignals(True)
    slider.setValue(value)
    slider.blockSignals(previous)


def update_overlay_preview(owner: Any, group: OverlayGroup | None = None) -> None:
    group = group or owner._selected_overlay_group()
    if group is None:
        color = "#2f81f7"
        marker_width = 8
        marker_height = 64
        opacity = 0.55
        corner_radius = 8
        owner._overlay_preview_group_name.setText(tr("overlay.preview.no_group"))
        owner._overlay_preview_window_count.setText(tr("overlay.preview.no_group_hint"))
    else:
        color = group.color
        marker_width = group.marker_width
        marker_height = group.marker_height
        opacity = group.opacity
        corner_radius = group.corner_radius
        owner._overlay_preview_group_name.setText(group.name)
        count = len(group.assigned_window_ids)
        count_key = (
            "dialog.choose_overlay_group.count_one"
            if count == 1
            else "dialog.choose_overlay_group.count_many"
        )
        owner._overlay_preview_window_count.setText(tr(count_key, count=count))

    preview_width = max(8, min(44, int(marker_width * 1.4)))
    preview_height = max(52, min(138, int(marker_height * 1.1)))
    preview_radius = max(0, min(18, corner_radius))
    color_value = QColor(color)
    if not color_value.isValid():
        color_value = QColor("#2f81f7")
    color_value.setAlphaF(max(0.2, min(1.0, opacity)))
    owner._overlay_preview_marker.setFixedSize(preview_width, preview_height)
    owner._overlay_preview_marker.setStyleSheet(
        "QFrame#OverlayMarkerPreview {"
        f"background: rgba({color_value.red()}, {color_value.green()}, "
        f"{color_value.blue()}, {color_value.alphaF():.2f});"
        f"border-radius: {preview_radius}px;"
        "border: 1px solid rgba(255, 255, 255, 0.18);"
        "}"
    )
