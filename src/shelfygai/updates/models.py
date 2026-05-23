from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class UpdateCheckStatus(StrEnum):
    NOT_IMPLEMENTED = "not_implemented"
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
