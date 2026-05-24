from __future__ import annotations

import platform
import sys
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from shelfygai.constants import APP_NAME, APP_VERSION, GITHUB_REPOSITORY_URL, resource_path

GITHUB_ISSUES_URL = f"{GITHUB_REPOSITORY_URL}/issues"
GITHUB_RELEASES_URL = f"{GITHUB_REPOSITORY_URL}/releases"
GITHUB_DOCUMENTATION_URL = f"{GITHUB_REPOSITORY_URL}/tree/main/docs"
OPEN_SOURCE_PROJECTS = (
    ("ShelfyGAI", "about.project.shelfygai.description", GITHUB_REPOSITORY_URL),
    (
        "SocketLens",
        "about.project.socketlens.description",
        "https://github.com/DenisGeide/SocketLens",
    ),
    ("Fantik", "about.project.fantik.description", "https://github.com/DenisGeide/Fantik"),
)


def build_about_page(owner: Any) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)

    content = QWidget()
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(0, 0, 8, 0)
    content_layout.setSpacing(14)

    hero = QFrame()
    hero.setObjectName("AboutHero")
    hero_layout = QHBoxLayout(hero)
    hero_layout.setContentsMargins(18, 18, 18, 18)
    hero_layout.setSpacing(14)

    logo = QLabel()
    logo.setObjectName("AboutLogo")
    logo.setFixedSize(72, 72)
    logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    logo.setPixmap(QIcon(str(resource_path("app_icon.svg"))).pixmap(52, 52))

    copy_box = QVBoxLayout()
    copy_box.setSpacing(7)

    title = QLabel(APP_NAME)
    title.setObjectName("HeroTitle")
    description = QLabel()
    description.setObjectName("Muted")
    description.setWordWrap(True)
    owner._bind_text(description, "about.description")

    button_row = QHBoxLayout()
    button_row.setSpacing(8)
    github_button = owner._make_link_button(
        "about.link.github",
        GITHUB_REPOSITORY_URL,
        primary=True,
    )
    button_row.addWidget(github_button)
    button_row.addWidget(owner._make_link_button("about.link.issues", GITHUB_ISSUES_URL))
    button_row.addWidget(
        owner._make_link_button("about.link.releases", GITHUB_RELEASES_URL)
    )
    button_row.addWidget(
        owner._make_link_button("about.link.documentation", GITHUB_DOCUMENTATION_URL)
    )
    button_row.addStretch(1)

    copy_box.addWidget(title)
    copy_box.addWidget(description)
    copy_box.addLayout(button_row)
    hero_layout.addWidget(logo)
    hero_layout.addLayout(copy_box, 1)

    info_grid = QGridLayout()
    info_grid.setContentsMargins(0, 0, 0, 0)
    info_grid.setHorizontalSpacing(10)
    info_grid.setVerticalSpacing(10)
    info_grid.setColumnStretch(0, 1)
    info_grid.setColumnStretch(1, 1)
    info_grid.addWidget(
        build_about_info_tile(owner, "about.version.title", "about.version", APP_VERSION),
        0,
        0,
    )
    info_grid.addWidget(
        build_about_info_tile(owner, "about.license", "about.license.detail"),
        0,
        1,
    )
    info_grid.addWidget(
        build_about_info_tile(owner, "about.build_type.title", build_type_key()),
        1,
        0,
    )
    info_grid.addWidget(
        build_about_value_tile(owner, "about.windows_version.title", windows_version_text()),
        1,
        1,
    )
    info_grid.addWidget(
        build_about_value_tile(
            owner,
            "about.python_runtime.title",
            f"Python {platform.python_version()}",
        ),
        2,
        0,
    )
    info_grid.addWidget(
        build_about_info_tile(owner, "about.privacy.title", "about.privacy"),
        2,
        1,
    )

    projects_panel = QFrame()
    projects_panel.setObjectName("Panel")
    projects_layout = QVBoxLayout(projects_panel)
    projects_layout.setContentsMargins(14, 14, 14, 14)
    projects_layout.setSpacing(8)

    projects_title = QLabel()
    projects_title.setObjectName("SectionTitle")
    owner._bind_text(projects_title, "about.projects.title")
    projects_layout.addWidget(projects_title)
    for name, description_key, url in OPEN_SOURCE_PROJECTS:
        projects_layout.addWidget(
            build_about_project_row(owner, name, description_key, url)
        )
    projects_layout.addStretch(1)

    update_panel = QFrame()
    update_panel.setObjectName("Panel")
    update_layout = QVBoxLayout(update_panel)
    update_layout.setContentsMargins(14, 14, 14, 14)
    update_layout.setSpacing(9)

    update_title = QLabel()
    update_title.setObjectName("SectionTitle")
    owner._bind_text(update_title, "about.updates.title")
    update_copy = QLabel()
    update_copy.setObjectName("Muted")
    update_copy.setWordWrap(True)
    owner._bind_text(update_copy, "about.updates.copy")

    owner._update_status_label.setObjectName("EmptyState")
    owner._update_status_label.setWordWrap(True)

    check_button = owner._make_button("about.update.button", owner._check_for_updates)

    update_layout.addWidget(update_title)
    update_layout.addWidget(update_copy)
    update_layout.addWidget(owner._update_status_label)
    update_layout.addWidget(check_button, alignment=Qt.AlignmentFlag.AlignLeft)

    content_layout.addWidget(hero)
    content_layout.addLayout(info_grid)
    content_layout.addWidget(projects_panel)
    content_layout.addWidget(update_panel)
    content_layout.addStretch(1)

    scroll.setWidget(content)
    layout.addWidget(scroll, 1)
    return page


def build_about_info_tile(
    owner: Any,
    title_key: str,
    body_key: str,
    *args: object,
) -> QFrame:
    tile = QFrame()
    tile.setObjectName("InfoTile")
    layout = QVBoxLayout(tile)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(5)

    title = QLabel()
    title.setObjectName("SectionTitle")
    owner._bind_text(title, title_key)

    body = QLabel()
    body.setObjectName("Muted")
    body.setWordWrap(True)
    if args:
        owner._bind_text(body, body_key, version=args[0])
    else:
        owner._bind_text(body, body_key)

    layout.addWidget(title)
    layout.addWidget(body)
    return tile


def build_about_value_tile(owner: Any, title_key: str, value: str) -> QFrame:
    tile = QFrame()
    tile.setObjectName("InfoTile")
    layout = QVBoxLayout(tile)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(5)

    title = QLabel()
    title.setObjectName("SectionTitle")
    owner._bind_text(title, title_key)

    body = QLabel(value)
    body.setObjectName("Muted")
    body.setWordWrap(True)

    layout.addWidget(title)
    layout.addWidget(body)
    return tile


def build_about_project_row(
    owner: Any,
    name: str,
    description_key: str,
    url: str,
) -> QFrame:
    row = QFrame()
    row.setObjectName("ManagedWindowRow")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 7, 0, 7)
    layout.setSpacing(10)

    copy_box = QVBoxLayout()
    copy_box.setSpacing(3)

    title = QLabel(name)
    title.setObjectName("CardTitle")
    description = QLabel()
    description.setObjectName("Muted")
    description.setWordWrap(True)
    owner._bind_text(description, description_key)

    copy_box.addWidget(title)
    copy_box.addWidget(description)

    open_button = owner._make_link_button("about.project.open", url)
    layout.addLayout(copy_box, 1)
    layout.addWidget(open_button, alignment=Qt.AlignmentFlag.AlignTop)
    return row


def build_type_key() -> str:
    if getattr(sys, "frozen", False):
        return "about.build_type.packaged"
    return "about.build_type.source"


def windows_version_text() -> str:
    if sys.platform == "win32":
        return f"{platform.system()} {platform.release()} ({platform.version()})"
    return platform.platform()
