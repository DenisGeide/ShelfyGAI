from __future__ import annotations

import json
import locale
import logging
import os
from contextlib import suppress
from importlib import resources
from typing import Any

LOGGER = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {
    "en": "English",
    "ru": "Русский",
}
FALLBACK_LANGUAGE = "en"


class Translator:
    """Small JSON-backed translator with English fallback strings."""

    def __init__(self, language: str | None = None) -> None:
        self._cache: dict[str, dict[str, str]] = {}
        self._language = _normalize_language(language or default_language())

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, language: str) -> str:
        self._language = _normalize_language(language)
        LOGGER.info("Language set: %s", self._language)
        return self._language

    def tr(self, key: str, **kwargs: Any) -> str:
        text = self._catalog(self._language).get(key)
        if text is None:
            text = self._catalog(FALLBACK_LANGUAGE).get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                LOGGER.debug("Could not format translation key: %s", key, exc_info=True)
        return text

    def _catalog(self, language: str) -> dict[str, str]:
        language = _normalize_language(language)
        if language in self._cache:
            return self._cache[language]
        try:
            locale_file = resources.files("shelfygai.i18n.locales").joinpath(
                f"{language}.json"
            )
            payload = json.loads(locale_file.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            LOGGER.exception("Could not load locale: %s", language)
            payload = {}
        catalog = {
            str(key): str(value)
            for key, value in payload.items()
            if isinstance(key, str) and isinstance(value, str)
        }
        self._cache[language] = catalog
        return catalog


def system_language() -> str:
    candidates = []
    with suppress(ValueError, TypeError):
        candidates.append(locale.getlocale()[0])
    for environment_name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(environment_name)
        if value:
            candidates.extend(value.split(":"))
    for candidate in candidates:
        if not candidate:
            continue
        language = candidate.split("_", 1)[0].split("-", 1)[0].lower()
        if language in SUPPORTED_LANGUAGES:
            return language
    return FALLBACK_LANGUAGE


def default_language() -> str:
    return system_language()


def language_name(language: str) -> str:
    return SUPPORTED_LANGUAGES.get(_normalize_language(language), SUPPORTED_LANGUAGES["en"])


def set_language(language: str) -> str:
    return translator.set_language(language)


def tr(key: str, **kwargs: Any) -> str:
    return translator.tr(key, **kwargs)


def _normalize_language(language: str | None) -> str:
    if not language:
        return FALLBACK_LANGUAGE
    normalized = language.split("_", 1)[0].split("-", 1)[0].lower()
    if normalized in SUPPORTED_LANGUAGES:
        return normalized
    return FALLBACK_LANGUAGE


translator = Translator()
