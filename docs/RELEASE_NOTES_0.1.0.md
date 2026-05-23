# ShelfyGAI 0.1.0 Public Alpha Release Notes

ShelfyGAI 0.1.0 is the first public alpha of a local-first Windows taskbar organization utility.
It is intended for users who want a cleaner workspace while keeping selected applications running
locally on their own PC.

## What ShelfyGAI Does

- Moves selected open application windows into an internal ShelfyGAI shelf.
- Removes managed windows from the Windows taskbar and Alt+Tab without terminating or suspending the
  application process.
- Restores individual windows, restores the last hidden window, or restores all managed windows.
- Organizes managed windows into local groups with sidebar counters and drag-and-drop assignment.
- Uses a modern dark PySide6 interface with search, quick actions, system tray support, app icons,
  and configurable hotkeys.
- Stores settings and logs locally under the user's roaming AppData directory.
- Captures local crash diagnostics and emergency recovery state to restore managed windows after
  unexpected failures when possible.

## Windows 10/11 Support

- Supports Windows 10 and Windows 11 desktop sessions.
- Uses current-user settings, logs, recovery files, and startup integration under the user's profile.
- Does not require administrator rights for normal use or the HKCU startup toggle.
- Elevated application windows may require elevated ShelfyGAI permissions to manage them; normal use
  should remain non-admin whenever possible.

## Windows Integration

- Uses WinAPI extended window styles to remove `WS_EX_APPWINDOW`, add `WS_EX_TOOLWINDOW`, and refresh the frame with `SetWindowPos`.
- Preserves original extended styles for exact restore.
- Enumerates top-level visible application windows while skipping shell, critical system, empty-title, tool, and ShelfyGAI windows.
- Uses current-user HKCU Run startup integration without administrator rights.
- Uses `RegisterHotKey` for global hotkeys instead of low-level keyboard hooks.
- Uses lazy icon loading, bounded icon caching, and deferred window refresh to keep startup and idle CPU usage low.

## Privacy

ShelfyGAI has no telemetry, analytics, ads, cloud sync, or background service without consent. The updater architecture in this release is a placeholder only and does not make network requests or download updates.

## Safety Notes

- ShelfyGAI refuses to manage its own windows, the Windows taskbar shell, Start Menu, and known
  critical system windows.
- Original window styles are saved before a window is managed and restored when the window is
  returned to the desktop.
- Restore-on-exit and emergency recovery are designed to reduce the risk of leaving windows
  inaccessible after a crash or forced shutdown.
- Some applications may not support taskbar style changes consistently; ShelfyGAI reports safe
  errors instead of treating this as a fatal condition.
- Unsigned open-source alpha builds may trigger Windows SmartScreen warnings. The project documents
  proper code signing for maintainers and does not include bypass instructions.

## Known Limitations

- This is an alpha release and should be tested carefully before daily use.
- Release artifacts may be unsigned, so Windows may warn before running the executable or installer.
- Managing elevated applications may require running ShelfyGAI elevated, which is not recommended for normal use.
- Force-killing ShelfyGAI cannot run immediate cleanup, but next-launch emergency recovery attempts to restore still-live managed windows from the same Windows boot.
- The update check button is informational only in this release.
- Some applications with custom shells, protected windows, or unusual window ownership may not appear
  in the open-window list or may not respond to taskbar style changes.
- Manual QA is still recommended across multi-monitor setups, DPI scaling levels, Explorer restarts,
  tray behavior, hotkeys, startup integration, and installer upgrades.

## How To Report Bugs

Please report bugs through GitHub Issues:

- [https://github.com/shelfygai/shelfygai/issues](https://github.com/shelfygai/shelfygai/issues)

Helpful reports include:

- Windows version and build number.
- Whether ShelfyGAI was run from source, from `dist\ShelfyGAI\ShelfyGAI.exe`, or from the installer.
- Steps to reproduce the issue.
- Expected behavior and actual behavior.
- Relevant logs from `%APPDATA%\ShelfyGAI\logs\`, after removing private window titles or file paths
  if needed.
- Screenshots or a short screen recording when they help explain the problem.

## Verification

The release candidate should pass:

```powershell
python -m ruff check . --no-cache
python -m pytest -p no:cacheprovider
python -m compileall src tests
```

Manual smoke testing should include Windows 10 or Windows 11 hide/restore, tray quit, startup toggle, and hotkey registration checks.
