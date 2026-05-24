from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class UpdateCheckStatus(StrEnum):
    UPDATE_AVAILABLE = "update_available"
    UP_TO_DATE = "up_to_date"
    NO_RELEASES = "no_releases"
    OFFLINE = "offline"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class UpdateCheckResult:
    status: UpdateCheckStatus
    current_version: str
    message: str
    latest_version: str | None = None
    release_url: str | None = None
    checked_url: str | None = None
