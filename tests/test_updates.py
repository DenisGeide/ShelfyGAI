from __future__ import annotations

import json
from urllib.error import HTTPError, URLError

from shelfygai.constants import APP_VERSION
from shelfygai.updates.github_releases import (
    GitHubReleaseSource,
    GitHubReleasesUpdateService,
    is_newer_version,
)
from shelfygai.updates.models import UpdateCheckStatus


def test_github_release_source_builds_latest_release_api_url() -> None:
    source = GitHubReleaseSource("https://github.com/example/project")

    assert source.latest_release_api_url == (
        "https://api.github.com/repos/example/project/releases/latest"
    )
    assert source.releases_url == "https://github.com/example/project/releases"


def test_github_releases_update_service_reports_available_update() -> None:
    service = GitHubReleasesUpdateService(
        current_version="0.1.0",
        source=GitHubReleaseSource("https://github.com/example/project"),
        http_get=lambda _url, _timeout: json.dumps(
            {
                "tag_name": "v0.2.0",
                "html_url": "https://github.com/example/project/releases/tag/v0.2.0",
            }
        ).encode("utf-8"),
    )

    result = service.check_for_updates()

    assert result.status == UpdateCheckStatus.UPDATE_AVAILABLE
    assert result.current_version == "0.1.0"
    assert result.latest_version == "v0.2.0"
    assert result.release_url == "https://github.com/example/project/releases/tag/v0.2.0"
    assert result.checked_url == "https://api.github.com/repos/example/project/releases/latest"


def test_github_releases_update_service_reports_up_to_date() -> None:
    service = GitHubReleasesUpdateService(
        current_version=APP_VERSION,
        source=GitHubReleaseSource("https://github.com/example/project"),
        http_get=lambda _url, _timeout: json.dumps(
            {
                "tag_name": f"v{APP_VERSION}",
                "html_url": "https://github.com/example/project/releases/tag/current",
            }
        ).encode("utf-8"),
    )

    result = service.check_for_updates()

    assert result.status == UpdateCheckStatus.UP_TO_DATE
    assert result.latest_version == f"v{APP_VERSION}"


def test_github_releases_update_service_reports_offline() -> None:
    def raise_offline(_url: str, _timeout: float) -> bytes:
        raise URLError("offline")

    service = GitHubReleasesUpdateService(
        current_version=APP_VERSION,
        source=GitHubReleaseSource("https://github.com/example/project"),
        http_get=raise_offline,
    )

    result = service.check_for_updates()

    assert result.status == UpdateCheckStatus.OFFLINE
    assert result.release_url == "https://github.com/example/project/releases"


def test_github_releases_update_service_reports_no_releases() -> None:
    def raise_not_found(_url: str, _timeout: float) -> bytes:
        raise HTTPError(
            url="https://api.github.com/repos/example/project/releases/latest",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )

    service = GitHubReleasesUpdateService(
        current_version=APP_VERSION,
        source=GitHubReleaseSource("https://github.com/example/project"),
        http_get=raise_not_found,
    )

    result = service.check_for_updates()

    assert result.status == UpdateCheckStatus.NO_RELEASES
    assert result.release_url == "https://github.com/example/project/releases"


def test_github_releases_update_service_reports_malformed_response() -> None:
    service = GitHubReleasesUpdateService(
        current_version=APP_VERSION,
        source=GitHubReleaseSource("https://github.com/example/project"),
        http_get=lambda _url, _timeout: b"{}",
    )

    result = service.check_for_updates()

    assert result.status == UpdateCheckStatus.ERROR
    assert result.latest_version is None


def test_is_newer_version_handles_leading_v_and_prerelease_suffix() -> None:
    assert is_newer_version("v0.2.0", "0.1.0")
    assert not is_newer_version("v0.1.0-alpha", "0.1.0")
