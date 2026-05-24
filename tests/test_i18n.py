from __future__ import annotations

import json
from pathlib import Path

from shelfygai.i18n import Translator, set_language, tr

LOCALES_DIR = Path("src/shelfygai/i18n/locales")


def test_locale_files_have_matching_keys() -> None:
    english = json.loads((LOCALES_DIR / "en.json").read_text(encoding="utf-8"))
    russian = json.loads((LOCALES_DIR / "ru.json").read_text(encoding="utf-8"))

    assert set(english) == set(russian)


def test_locale_files_do_not_contain_replacement_question_marks() -> None:
    for locale_path in LOCALES_DIR.glob("*.json"):
        catalog = json.loads(locale_path.read_text(encoding="utf-8"))
        broken = {
            key: value
            for key, value in catalog.items()
            if isinstance(value, str) and "???" in value
        }

        assert broken == {}


def test_translator_loads_russian_catalog() -> None:
    translator = Translator("ru")

    assert translator.tr("action.save") == "Сохранить"


def test_translator_falls_back_to_english_for_missing_locale_key() -> None:
    translator = Translator("ru")
    translator._cache["ru"] = {}

    assert translator.tr("action.save") == "Save"


def test_global_language_normalizes_regional_tags() -> None:
    try:
        assert set_language("ru-RU") == "ru"
        assert tr("language.ru") == "Русский"
    finally:
        set_language("en")
