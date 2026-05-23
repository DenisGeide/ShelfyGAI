# Changelog

All notable changes to ShelfyGAI will be documented in this file.

The format follows Keep a Changelog and this project aims to follow Semantic Versioning after the first stable release.

## [Unreleased]

### Added

- One-file Inno Setup web installer bootstrapper that downloads the full
  ShelfyGAI installer from GitHub Releases with optional SHA-256 verification.

## [0.1.0] - 2026-05-23

### Added

- Initial PySide6 desktop application.
- Dark modern shell with sidebar, header, status bar, and navigation areas.
- Windows top-level window enumeration.
- Hide and restore operations for selected windows using extended window styles.
- Local-only JSON settings.
- Robust `SettingsManager` and `AppLogger` services.
- Debug mode, settings version metadata, and rotating logs under `%APPDATA%\ShelfyGAI\logs`.
- Grouped managed-window restore cards with app icons when available.
- Optional focus behavior for restored windows.
- Local groups with sidebar counters and drag-and-drop window assignment.
- Boot-scoped managed-window metadata to avoid restoring stale HWND entries after reboot.
- System tray icon with open, restore-all, settings, and quit actions.
- Close-to-tray behavior, tray notifications, startup notification, and silent startup option.
- UI polish pass with smoother page/card transitions, improved hover states, search, shortcuts,
  quick actions, loading indicators, and clearer empty states.
- Cached executable icon extraction with fallback icons across open-window lists, managed windows,
  and group buttons.
- Configurable global hotkeys for quick hide, restore last hidden window, and toggling ShelfyGAI
  visibility using the Windows `RegisterHotKey` API.
- Hardened current-user Windows startup integration with HKCU Run status detection, safe cleanup,
  silent-startup command support, and executable path validation.
- Added offline-safe updater architecture placeholder and About page with version information and
  a future GitHub Releases check action.
- English and Russian localization support with runtime language switching.
- First-launch onboarding, settings sections, Safety page, About page, and privacy note.
- Safety guardrails for ShelfyGAI's own window, Windows shell/taskbar, Start Menu, critical system
  windows, elevated-window warnings, and safer user-facing error messages.
- Emergency recovery file under `%APPDATA%\ShelfyGAI\recovery.json` to help restore managed windows
  after an unexpected shutdown.
- Inno Setup installer configuration and installer documentation.
- PyInstaller packaging configuration, Windows executable metadata, and release build scripts.
- Open-source project documentation.
- GitHub issue templates, pull request template, and Python check workflow for lint, tests, and
  import checks.
- Code of Conduct.
- Build, installer, code signing, screenshot/demo placeholder, QA, release checklist, and first
  release notes documentation.
- Starter pytest coverage for settings, translations, window registry logic, groups, recovery file
  handling, and startup registry helper behavior.

### Changed

- Expanded contributor, security, architecture, QA, packaging, and release documentation for public
  repository readiness.
- Documented standalone executable packaging and user data persistence across updates.
- Updated repository docs for the `dist\ShelfyGAI\ShelfyGAI.exe` onedir package.
