from __future__ import annotations

from typing import Protocol

from shelfygai.updates.models import UpdateCheckResult


class UpdateService(Protocol):
    def check_for_updates(self) -> UpdateCheckResult:
        """Check for updates without downloading or installing anything."""
