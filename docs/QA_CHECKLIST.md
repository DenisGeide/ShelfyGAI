# QA Checklist

Use this checklist before publishing a ShelfyGAI release. Test both the source app and the packaged executable when possible.

## Build Under Test

- [ ] Version:
- [ ] Commit or tag:
- [ ] Package tested:
  - [ ] Source run with `python -m shelfygai`
  - [ ] Packaged `dist\ShelfyGAI\ShelfyGAI.exe`
  - [ ] Installer `dist\installer\ShelfyGAI-Setup-v0.1.0.exe`
- [ ] Tester:
- [ ] Date:

## Test Environment Matrix

- [ ] Windows 10, current supported patch level.
- [ ] Windows 11, current supported patch level.
- [ ] Standard user account.
- [ ] Administrator account.
- [ ] Single monitor at 100 percent scaling.
- [ ] Single monitor at 125 percent or 150 percent scaling.
- [ ] Multi-monitor with matching DPI.
- [ ] Multi-monitor with mixed DPI.
- [ ] Light Windows theme.
- [ ] Dark Windows theme.

Record environment notes:

```text

```

## Preflight

- [ ] Install dependencies or unpack release ZIP into a clean folder.
- [ ] Confirm no old `ShelfyGAI.exe` instance is running.
- [ ] Back up or remove `%APPDATA%\ShelfyGAI` for first-launch testing.
- [ ] Confirm settings are stored at `%APPDATA%\ShelfyGAI\settings.json`.
- [ ] Confirm logs are stored under `%APPDATA%\ShelfyGAI\logs\`.
- [ ] Confirm no admin permission is required for normal startup.
- [ ] Confirm Windows Defender or SmartScreen prompts, if any, are expected for an unsigned build.

## First Launch And Settings

- [ ] First-launch onboarding appears before the main window.
- [ ] Theme selector saves `System`, `Dark`, and `Light`.
- [ ] Accent color selection persists after restart.
- [ ] `Launch with Windows` toggle updates HKCU only.
- [ ] `Minimize to tray on close` toggle persists after restart.
- [ ] `Restore hidden windows on exit` toggle persists after restart.
- [ ] `Restore pinned windows on exit` toggle persists after restart.
- [ ] `Restore pinned windows if minimized` watcher toggle persists after restart.
- [ ] Pinned watcher interval persists and clamps invalid values safely.
- [ ] `Enable startup notification` toggle persists after restart.
- [ ] GitHub button opens the configured repository in the default browser.
- [ ] Settings can be reopened from the app after onboarding.
- [ ] Invalid setting values fall back safely to defaults.

## Windows 10

- [ ] App launches from source.
- [ ] App launches from packaged EXE.
- [ ] Main window renders correctly.
- [ ] System tray icon appears when tray is available.
- [ ] Open windows enumeration works.
- [ ] Hide and restore works for normal desktop apps.
- [ ] Logs are created without errors.
- [ ] App exits cleanly.

## Windows 11

- [ ] App launches from source.
- [ ] App launches from packaged EXE.
- [ ] Main window renders correctly.
- [ ] System tray icon appears when tray is available.
- [ ] Open windows enumeration works.
- [ ] Hide and restore works for normal desktop apps.
- [ ] Logs are created without errors.
- [ ] App exits cleanly.

## Multi-Monitor

- [ ] Main window opens on a visible display.
- [ ] Moving ShelfyGAI between monitors keeps layout intact.
- [ ] Opening Settings on each monitor keeps dialogs visible.
- [ ] Hiding a window on monitor 1 restores it to its original location.
- [ ] Hiding a window on monitor 2 restores it to its original location.
- [ ] Mixed-DPI monitor moves do not blur icons excessively.
- [ ] No controls overlap after dragging between monitors.

## DPI Scaling

- [ ] 100 percent scaling: text is readable and not clipped.
- [ ] 125 percent scaling: text is readable and not clipped.
- [ ] 150 percent scaling: text is readable and not clipped.
- [ ] 200 percent scaling, if available: text is readable and not clipped.
- [ ] Sidebar counters remain aligned.
- [ ] Tables remain usable.
- [ ] Buttons and toggles remain clickable.
- [ ] App icons appear crisp enough for high-DPI displays.

## Tray Behavior

- [ ] Tray menu contains `Open ShelfyGAI`.
- [ ] Tray menu contains `Restore All Windows`.
- [ ] Tray menu contains `Settings`.
- [ ] Tray menu contains `Quit`.
- [ ] Closing the main window minimizes to tray when enabled.
- [ ] Closing the main window exits when minimize-to-tray is disabled.
- [ ] `Open ShelfyGAI` restores and focuses the main window.
- [ ] `Settings` opens the settings window.
- [ ] `Restore All Windows` restores all hidden windows.
- [ ] `Quit` performs safe cleanup.
- [ ] Startup notification appears when enabled.
- [ ] Startup notification does not appear when disabled or silent startup is enabled.
- [ ] Tray notifications appear for hide and restore events.
- [ ] No duplicate tray icons remain after quit or crash recovery.

## Open Window Enumeration

- [ ] Refresh lists normal visible top-level application windows.
- [ ] Search filters by app name.
- [ ] Search filters by title.
- [ ] Search filters by PID.
- [ ] Empty title windows are ignored.
- [ ] Invisible windows are ignored.
- [ ] Explorer shell windows are ignored.
- [ ] ShelfyGAI itself is ignored.
- [ ] Closed windows disappear after refresh.
- [ ] Auto-refresh can be enabled and disabled.
- [ ] Enumeration errors are logged without crashing.

## Hide And Restore

- [ ] Hide a Notepad window.
- [ ] Hidden window disappears from the Windows taskbar.
- [ ] Hidden window disappears from Alt+Tab.
- [ ] Hidden window remains running in Task Manager.
- [ ] Hidden window appears in the Hidden windows section.
- [ ] Duplicate hide attempts are prevented.
- [ ] Multiple windows can be hidden at the same time.
- [ ] Restore returns the window to the taskbar.
- [ ] Restore returns the window to Alt+Tab.
- [ ] Restore optionally focuses the window.
- [ ] Restore All restores every hidden window.
- [ ] Original extended window styles are restored exactly.
- [ ] Hide and restore events are logged.
- [ ] Status notifications appear for successful hide and restore.

## Pin Windows

- [ ] Pin a normal desktop app from the Open Windows table.
- [ ] Pinned window stays above normal windows.
- [ ] Pinned window appears in the Pinned Windows section.
- [ ] Duplicate pin attempts are prevented.
- [ ] Unpin restores the original always-on-top state.
- [ ] Enable Prevent Minimize for a pinned window.
- [ ] Minimize button is unavailable or ignored while prevent-minimize is enabled.
- [ ] With watcher enabled, a minimized pinned window is restored automatically.
- [ ] With watcher disabled, ShelfyGAI does not poll minimized pinned windows.
- [ ] Closed pinned windows are removed from the pinned list without crashing.
- [ ] ShelfyGAI does not pin its own window unless explicitly enabled in Settings.
- [ ] Explorer shell windows and Start Menu surfaces cannot be pinned.
- [ ] Pinned window styles are restored on normal app exit when enabled.
- [ ] Pin, unpin, prevent-minimize, allow-minimize, and bring-to-front context menu actions work.
- [ ] Pin and unpin events are logged.

## Alt+Tab Behavior

- [ ] Before hiding, target window appears in Alt+Tab.
- [ ] After hiding, target window no longer appears in Alt+Tab.
- [ ] After restore, target window appears in Alt+Tab again.
- [ ] ShelfyGAI remains visible in Alt+Tab when appropriate.
- [ ] Switching apps while windows are hidden does not restore them unexpectedly.

## Groups And Drag And Drop

- [ ] Default `Ungrouped` group exists.
- [ ] New group can be created.
- [ ] Group can be renamed.
- [ ] Empty group can be deleted.
- [ ] Non-empty group cannot be deleted without moving windows first.
- [ ] Hidden window can be dragged between groups.
- [ ] Group counters update after hide, restore, and drag operations.
- [ ] Group metadata persists after restart.
- [ ] Stale HWND entries are not restored after reboot.

## Startup Integration

- [ ] Enabling startup writes to `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.
- [ ] Startup command points to the current executable path.
- [ ] Startup path is quoted when needed.
- [ ] Disabling startup removes only the ShelfyGAI entry.
- [ ] Startup status detection matches Registry state.
- [ ] No admin prompt appears.
- [ ] Packaged EXE can start from the Registry entry.
- [ ] Moving the EXE causes path validation to report the stale startup path safely.
- [ ] Startup cleanup handles missing Registry keys gracefully.

## Corrupted Config

- [ ] Replace `%APPDATA%\ShelfyGAI\settings.json` with invalid JSON.
- [ ] App starts without crashing.
- [ ] Default settings are recreated or loaded.
- [ ] Corruption is logged.
- [ ] User can save settings again.
- [ ] Missing settings file is recreated automatically.
- [ ] Missing settings directory is recreated automatically.
- [ ] Read-only settings file produces a handled error and user-visible feedback.

## App Crash Recovery

- [ ] Force close ShelfyGAI from Task Manager while no windows are hidden.
- [ ] Relaunch works normally.
- [ ] Force close ShelfyGAI while one test window is hidden.
- [ ] Relaunch does not crash when reading persisted hidden-window metadata.
- [ ] Stale HWND metadata is not restored after reboot.
- [ ] Logs include the next startup event.
- [ ] Restore-on-exit behavior is applied during normal quit.
- [ ] Unexpected crash does not corrupt settings.

## Closed Target Window

- [ ] Hide a test window.
- [ ] Close the target process from Task Manager.
- [ ] Refresh hidden windows.
- [ ] Hidden windows list marks or removes the closed target safely.
- [ ] Restore on the closed target does not crash.
- [ ] Restore All skips the closed target.
- [ ] A clear status message is shown.
- [ ] Event is logged.

## Elevated Windows

- [ ] Run ShelfyGAI as a standard user.
- [ ] Open an elevated test app, such as an elevated Notepad.
- [ ] Enumeration handles access-denied process metadata safely.
- [ ] Hiding an elevated window fails safely if Windows blocks the operation.
- [ ] Restore does not crash if the elevated target cannot be modified.
- [ ] Run ShelfyGAI as administrator.
- [ ] Elevated window hide and restore behavior is verified.
- [ ] Logs do not include sensitive command-line data.

## Explorer Restart

- [ ] Hide a test window.
- [ ] Restart Explorer from Task Manager.
- [ ] ShelfyGAI remains running.
- [ ] Tray icon returns after Explorer restarts.
- [ ] Hidden windows list remains accurate.
- [ ] Restore still works after Explorer restart.
- [ ] Restored window returns to the taskbar.
- [ ] No duplicate tray icons remain.

## Keyboard Shortcuts And Hotkeys

- [ ] Default global hotkey `Ctrl+Shift+Space` registers.
- [ ] Hotkey can toggle ShelfyGAI visibility.
- [ ] Configured hotkey persists after restart.
- [ ] Invalid hotkey config falls back safely.
- [ ] Hotkey unregisters on quit.
- [ ] Hotkey conflict is reported without crashing.

## Packaging And Update Survival

- [ ] `.\scripts\build_exe.ps1 -Clean` creates `dist\ShelfyGAI\ShelfyGAI.exe`.
- [ ] `.\scripts\build_installer.ps1 -SkipExeBuild` creates `dist\installer\ShelfyGAI-Setup-v0.1.0.exe` when Inno Setup is installed.
- [ ] `.\scripts\release.ps1` creates a ZIP and `SHA256SUMS.txt`.
- [ ] Packaged EXE contains version metadata.
- [ ] Packaged EXE contains the application icon.
- [ ] Replace `ShelfyGAI.exe` with a newly built copy.
- [ ] Existing `%APPDATA%\ShelfyGAI\settings.json` remains intact.
- [ ] Existing `%APPDATA%\ShelfyGAI\logs\` remains intact.
- [ ] App starts after replacement.

## Privacy And Network

- [ ] App does not send telemetry.
- [ ] App does not show ads.
- [ ] App does not require cloud services.
- [ ] App works while offline.
- [ ] GitHub and update placeholder actions do not run automatically.
- [ ] Logs stay local under `%APPDATA%\ShelfyGAI\logs\`.

## Pass Or Fail Summary

- [ ] PASS: Ready for release.
- [ ] FAIL: Block release.
- [ ] NEEDS RETEST: Fixes required, then rerun affected sections.

Notes:

```text

```
