# ShelfyGAI Roadmap

This roadmap describes the current public alpha direction. It is intentionally
conservative: ShelfyGAI should stay simple, local-first, and safe to recover
from.

## v0.1.0 Public Alpha

- Hide windows.
- Restore windows.
- Pin and unpin windows.
- Groups.
- English and Russian localization.
- Tray support.
- Offline installer.

## v0.2.0

- Better group taskbar windows.
- More stable per-app behavior.
- Better icons.
- Improved recovery.
- More tests.

## v0.3.0

- Workspace profiles.
- Rules and automation.
- Optional hotkeys.
- Better multi-monitor behavior.

## Research And Limits

### Tray Icon Hiding

Tray icon hiding is research/limited. Windows notification-area icons are owned
by the target application and the Windows shell, not always by the top-level
window ShelfyGAI manages.

ShelfyGAI should not use unsafe shell manipulation, Explorer restarts, registry
hacks, or injection to hide arbitrary third-party tray icons. This area should
only move forward if a safe, supported per-app mechanism is found.

### Native Taskbar Folders

Native Windows taskbar folders are not planned unless a safe supported Windows
API exists.

ShelfyGAI group taskbar windows are the safe approach for now: they are normal
ShelfyGAI-owned windows that represent a group without modifying Explorer or the
Windows shell.
