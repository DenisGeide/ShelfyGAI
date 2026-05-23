from __future__ import annotations

from shelfygai.constants import APP_VERSION
from shelfygai.updates.github_releases import GitHubReleaseSource, GitHubReleasesUpdateService
from shelfygai.updates.models import UpdateCheckStatus


def test_github_release_source_builds_latest_release_api_url() -> None:
    source = GitHubReleaseSource("https://github.com/example/project")

    assert source.latest_release_api_url == (
        "https://api.github.com/repos/example/project/releases/latest"
    )
    assert source.releases_url == "https://github.com/example/project/releases"


def test_github_releases_update_service_is_offline_placeholder() -> None:
    service = GitHubReleasesUpdateService(
        current_version=APP_VERSION,
        source=GitHubReleaseSource("https://github.com/example/project"),
    )

    result = service.check_for_updates()

    assert result.status == UpdateCheckStatus.NOT_IMPLEMENTED
    assert result.current_version == APP_VERSION
    assert result.latest_version is None
    assert result.checked_url == "https://api.github.com/repos/example/project/releases/latest"
    assert "no network request" in result.message.lower()
