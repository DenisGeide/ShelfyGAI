# Changelog

All notable changes to ShelfyGAI will be documented in this file.

The format follows Keep a Changelog, and this project aims to follow Semantic
Versioning after the first stable release.

## [Unreleased]

- Nothing yet.

## v0.1.0-alpha - 2026-05-23

### Added

- Hidden windows workflow.
- Pin/unpin windows.
- Window groups.
- Optional group taskbar windows.
- EN/RU localization.
- Settings page.
- Tray support.
- Offline installer docs.
- Screenshot placeholders.

### Changed

- Simplified main UI.
- Updated user-facing hidden-window wording across the app.
- Reworked group UI.
- Reworked pin behavior to be reversible and safe.
- Simplified installer strategy.

### Fixed

- Prevented windows from staying always-on-top after app exit.
- Improved restore cleanup.
- Improved stale HWND handling.
- Improved corrupted settings handling.

### Known limitations

- Tray icon hiding is limited.
- Some apps may recreate windows.
- Elevated windows may require admin.
- Native Windows taskbar folders are not supported.
