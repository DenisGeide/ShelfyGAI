from __future__ import annotations

import json
from pathlib import Path

from shelfygai.ui.onboarding_dialog import ONBOARDING_STEPS

LOCALES_DIR = Path("src/shelfygai/i18n/locales")


def test_first_run_onboarding_has_five_compact_steps() -> None:
    assert len(ONBOARDING_STEPS) == 5
    assert all(len(step) == 3 for step in ONBOARDING_STEPS)


def test_first_run_onboarding_steps_are_localized() -> None:
    english = json.loads((LOCALES_DIR / "en.json").read_text(encoding="utf-8"))
    russian = json.loads((LOCALES_DIR / "ru.json").read_text(encoding="utf-8"))

    for step in ONBOARDING_STEPS:
        for key in step:
            assert key in english
            assert key in russian
