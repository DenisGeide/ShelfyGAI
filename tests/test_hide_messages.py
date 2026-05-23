from __future__ import annotations

import pytest

from shelfygai.core.models import HideOptions
from shelfygai.i18n import set_language
from shelfygai.ui.hide_messages import hide_confirmation_message


@pytest.fixture(autouse=True)
def english_locale():
    set_language("en")
    yield
    set_language("en")


def first_line(text: str) -> str:
    return text.splitlines()[0]


def test_english_confirmation_mentions_only_taskbar_when_selected() -> None:
    message = hide_confirmation_message(
        1,
        HideOptions(hide_taskbar=True, hide_alt_tab=False),
    )

    assert first_line(message) == "Hide 1 selected window from the taskbar?"
    assert "Alt+Tab" not in message


def test_english_confirmation_mentions_only_alt_tab_when_selected() -> None:
    message = hide_confirmation_message(
        1,
        HideOptions(hide_taskbar=False, hide_alt_tab=True),
    )

    assert first_line(message) == "Hide 1 selected window from Alt+Tab?"
    assert "taskbar" not in message.lower()


def test_english_confirmation_mentions_taskbar_and_alt_tab() -> None:
    message = hide_confirmation_message(
        1,
        HideOptions(hide_taskbar=True, hide_alt_tab=True),
    )

    assert message == "Hide 1 selected window from the taskbar and Alt+Tab?"


def test_english_confirmation_mentions_all_selected_targets_and_tray_limitation() -> None:
    message = hide_confirmation_message(
        1,
        HideOptions(hide_taskbar=True, hide_alt_tab=True, hide_tray=True),
    )

    assert first_line(message) == (
        "Hide 1 selected window from the taskbar, Alt+Tab, and notification area?"
    )
    assert "experimental" in message


def test_english_confirmation_uses_plural_for_multiple_windows() -> None:
    message = hide_confirmation_message(
        3,
        HideOptions(hide_taskbar=True, hide_alt_tab=True),
    )

    assert message == "Hide 3 selected windows from the taskbar and Alt+Tab?"


def test_confirmation_blocks_empty_options() -> None:
    message = hide_confirmation_message(
        1,
        HideOptions(hide_taskbar=False, hide_alt_tab=False, hide_tray=False),
    )

    assert message == "Select at least one hide option."


def test_russian_confirmation_mentions_only_taskbar_when_selected() -> None:
    set_language("ru")
    message = hide_confirmation_message(
        1,
        HideOptions(hide_taskbar=True, hide_alt_tab=False),
    )

    assert first_line(message) == "Скрыть 1 выбранное окно с панели задач?"
    assert "Alt+Tab" not in message


def test_russian_confirmation_mentions_only_alt_tab_when_selected() -> None:
    set_language("ru")
    message = hide_confirmation_message(
        1,
        HideOptions(hide_taskbar=False, hide_alt_tab=True),
    )

    assert first_line(message) == "Скрыть 1 выбранное окно из Alt+Tab?"
    assert "панели задач" not in message


def test_russian_confirmation_mentions_taskbar_and_alt_tab() -> None:
    set_language("ru")
    message = hide_confirmation_message(
        1,
        HideOptions(hide_taskbar=True, hide_alt_tab=True),
    )

    assert message == "Скрыть 1 выбранное окно с панели задач и из Alt+Tab?"


def test_russian_confirmation_mentions_all_selected_targets_and_tray_limitation() -> None:
    set_language("ru")
    message = hide_confirmation_message(
        1,
        HideOptions(hide_taskbar=True, hide_alt_tab=True, hide_tray=True),
    )

    assert first_line(message) == (
        "Скрыть 1 выбранное окно с панели задач, из Alt+Tab и области уведомлений?"
    )
    assert "экспериментально" in message


def test_russian_confirmation_uses_plural_for_multiple_windows() -> None:
    set_language("ru")
    message = hide_confirmation_message(
        3,
        HideOptions(hide_taskbar=True, hide_alt_tab=True),
    )

    assert message == "Скрыть 3 выбранных окон с панели задач и из Alt+Tab?"
