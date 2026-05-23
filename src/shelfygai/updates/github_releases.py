from __future__ import annotations

import logging
from dataclasses import dataclass

from shelfygai.constants import APP_VERSION, GITHUB_REPOSITORY_URL
from shelfygai.updates.models import UpdateCheckResult, UpdateCheckStatus

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GitHubReleaseSource:
    repository_url: str = GITHUB_REPOSITORY_URL

    @property
    def latest_release_api_url(self) -> str:
        owner_repo = self.repository_url.rstrip("/").removeprefix("https://github.com/")
        return f"https://api.github.com/repos/{owner_repo}/releases/latest"

    @property
    def releases_url(self) -> str:
        return f"{self.repository_url.rstrip('/')}/releases"


class GitHubReleasesUpdateService:
    """Future GitHub Releases update checker placeholder.

    This intentionally does not perform network requests, download installers, or install updates.
    """

    def __init__(
        self,
        *,
        current_version: str = APP_VERSION,
        source: GitHubReleaseSource | None = None,
    ) -> None:
        self.current_version = current_version
        self.source = source or GitHubReleaseSource()

    def check_for_updates(self) -> UpdateCheckResult:
        LOGGER.info(
            "Update check placeholder invoked: current_version=%s source=%s",
            self.current_version,
            self.source.latest_release_api_url,
        )
        return UpdateCheckResult(
            status=UpdateCheckStatus.NOT_IMPLEMENTED,
            current_version=self.current_version,
            checked_url=self.source.latest_release_api_url,
            release_url=self.source.releases_url,
            message=(
                "Update checks are prepared for future GitHub Releases integration, "
                "but no network request was made in this build."
            ),
        )
