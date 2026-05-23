# Updates

ShelfyGAI currently does not download, install, or apply updates.

The project includes an offline-safe update service abstraction so a future release can add a GitHub Releases checker without changing the UI boundary. The current `GitHubReleasesUpdateService` only prepares the expected GitHub Releases endpoint and returns a local placeholder result. No network request is made.

The About page shows the installed version and exposes a placeholder "Check for updates" action. That action is intentionally informational in this build.
