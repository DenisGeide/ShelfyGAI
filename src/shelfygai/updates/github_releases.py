from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from shelfygai.constants import APP_NAME, APP_VERSION, GITHUB_REPOSITORY_URL
from shelfygai.updates.models import UpdateCheckResult, UpdateCheckStatus

LOGGER = logging.getLogger(__name__)
DEFAULT_TIMEOUT_SECONDS = 6.0
HttpGet = Callable[[str, float], bytes]


@dataclass(frozen=True, slots=True)
class GitHubReleaseSource:
    repository_url: str = GITHUB_REPOSITORY_URL

    @property
    def owner_repo(self) -> str:
        return self.repository_url.rstrip("/").removeprefix("https://github.com/")

    @property
    def latest_release_api_url(self) -> str:
        return f"https://api.github.com/repos/{self.owner_repo}/releases/latest"

    @property
    def releases_url(self) -> str:
        return f"{self.repository_url.rstrip('/')}/releases"


class GitHubReleasesUpdateService:
    """Manual GitHub Releases checker.

    The service only reads public release metadata. It never downloads installers,
    installs updates, or changes user settings.
    """

    def __init__(
        self,
        *,
        current_version: str = APP_VERSION,
        source: GitHubReleaseSource | None = None,
        http_get: HttpGet | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.current_version = current_version
        self.source = source or GitHubReleaseSource()
        self._http_get = http_get or _http_get
        self._timeout_seconds = timeout_seconds

    def check_for_updates(self) -> UpdateCheckResult:
        url = self.source.latest_release_api_url
        LOGGER.info(
            "Checking GitHub Releases: current_version=%s source=%s",
            self.current_version,
            url,
        )
        try:
            payload = self._http_get(url, self._timeout_seconds)
            release = json.loads(payload.decode("utf-8"))
        except TimeoutError as exc:
            return self._offline_result(url, exc)
        except HTTPError as exc:
            if exc.code == 404:
                LOGGER.info("GitHub Releases check found no published releases")
                return UpdateCheckResult(
                    status=UpdateCheckStatus.NO_RELEASES,
                    current_version=self.current_version,
                    checked_url=url,
                    release_url=self.source.releases_url,
                    message="No public GitHub Releases were found.",
                )
            LOGGER.warning("GitHub Releases check failed: status=%s", exc.code)
            return self._error_result(url, f"GitHub returned HTTP {exc.code}.")
        except URLError as exc:
            return self._offline_result(url, exc)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            LOGGER.warning("GitHub Releases check failed: %s", exc)
            return self._error_result(url, str(exc))

        latest_version = _release_tag(release)
        release_url = _release_url(release) or self.source.releases_url
        if not latest_version:
            LOGGER.warning("GitHub Releases response did not include tag_name")
            return self._error_result(url, "Latest release response did not include a tag.")

        status = (
            UpdateCheckStatus.UPDATE_AVAILABLE
            if is_newer_version(latest_version, self.current_version)
            else UpdateCheckStatus.UP_TO_DATE
        )
        LOGGER.info(
            "GitHub Releases check complete: status=%s latest=%s release_url=%s",
            status,
            latest_version,
            release_url,
        )
        return UpdateCheckResult(
            status=status,
            current_version=self.current_version,
            latest_version=latest_version,
            release_url=release_url,
            checked_url=url,
            message="GitHub Releases check completed.",
        )

    def _offline_result(self, url: str, exc: BaseException) -> UpdateCheckResult:
        LOGGER.info("GitHub Releases check could not reach network: %s", exc)
        return UpdateCheckResult(
            status=UpdateCheckStatus.OFFLINE,
            current_version=self.current_version,
            checked_url=url,
            release_url=self.source.releases_url,
            message=str(exc),
        )

    def _error_result(self, url: str, message: str) -> UpdateCheckResult:
        return UpdateCheckResult(
            status=UpdateCheckStatus.ERROR,
            current_version=self.current_version,
            checked_url=url,
            release_url=self.source.releases_url,
            message=message,
        )


def _http_get(url: str, timeout_seconds: float) -> bytes:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{APP_NAME}/{APP_VERSION}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


def _release_tag(payload: object) -> str | None:
    if isinstance(payload, dict):
        tag = payload.get("tag_name")
        if isinstance(tag, str) and tag.strip():
            return tag.strip()
    return None


def _release_url(payload: object) -> str | None:
    if isinstance(payload, dict):
        url = payload.get("html_url")
        if isinstance(url, str) and url.strip():
            return url.strip()
    return None


def is_newer_version(candidate: str, current: str) -> bool:
    candidate_parts = _version_key(candidate)
    current_parts = _version_key(current)
    if not candidate_parts or not current_parts:
        return candidate.casefold() != current.casefold()
    return candidate_parts > current_parts


def _version_key(version: str) -> tuple[int, ...]:
    normalized = version.strip().casefold()
    if normalized.startswith("v"):
        normalized = normalized[1:]
    normalized = normalized.split("-", 1)[0].split("+", 1)[0]
    parts: list[int] = []
    for part in normalized.split("."):
        if not part.isdigit():
            return ()
        parts.append(int(part))
    return tuple(parts)
