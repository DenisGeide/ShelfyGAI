from __future__ import annotations

from shelfygai.ui.widgets.hidden_window_switcher import (
    SWITCHER_KIND_HIDDEN,
    SWITCHER_KIND_OVERLAY_GROUP,
    SWITCHER_KIND_PINNED,
    SwitcherItem,
    matches_switcher_query,
)


def test_switcher_query_matches_title_subtitle_badge_and_kind() -> None:
    item = SwitcherItem(
        kind=SWITCHER_KIND_HIDDEN,
        title="Project Notes",
        subtitle="notepad.exe · Work",
        badge="Hidden",
    )

    assert matches_switcher_query(item, "project")
    assert matches_switcher_query(item, "notepad work")
    assert matches_switcher_query(item, "hidden")


def test_switcher_query_rejects_unmatched_tokens() -> None:
    item = SwitcherItem(
        kind=SWITCHER_KIND_PINNED,
        title="Browser",
        subtitle="browser.exe · always on top",
    )

    assert not matches_switcher_query(item, "telegram")


def test_switcher_query_matches_overlay_group_kind_words() -> None:
    item = SwitcherItem(
        kind=SWITCHER_KIND_OVERLAY_GROUP,
        title="Work",
        subtitle="2 hidden windows",
    )

    assert matches_switcher_query(item, "overlay group")
