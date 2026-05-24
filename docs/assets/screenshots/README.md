# Screenshot Plan

This folder is reserved for public GitHub screenshots used by `README.md`,
release notes, the GitHub release page, and issue discussions.

Screenshots should be updated before every public release.

Current UX direction: keep captures compact and calm. Prefer screens that show
the cleaner table-first workflow, smaller action bars, tighter empty states,
compact overlay flyouts, and native-looking confirmation dialogs.

## Screenshot Slots

| # | Screenshot | Path | What To Show |
| --- | --- | --- | --- |
| 1 | Main window - Open windows | `docs/assets/screenshots/01-main-open-windows.png` | Open windows page with search, refresh, a selected window, and simple actions. |
| 2 | Hidden windows page | `docs/assets/screenshots/02-hidden-windows.png` | Hidden windows page with one or more hidden windows and restore actions. |
| 3 | Pinned windows page | `docs/assets/screenshots/03-pinned.png` | Pinned page with pinned windows, order controls, and unpin actions. |
| 4 | Groups page | `docs/assets/screenshots/04-groups.png` | Groups page with clear group names, counts, and group actions. |
| 5 | Overlay hub flyout | `docs/assets/screenshots/05-taskbar-group-window.png` | Unified overlay hub near the tray with an expanded group flyout and optional compact group marker. |
| 6 | Settings page | `docs/assets/screenshots/06-settings.png` | Settings page showing General, Appearance, Language, Startup, Tray, Hotkeys, Safety, and About. |
| 7 | Tray menu | `docs/assets/screenshots/07-tray-menu.png` | Windows tray menu with Open ShelfyGAI, Restore all windows, Settings, and Quit. |
| 8 | EN/RU language switch | `docs/assets/screenshots/08-language-switch.png` | Language selector showing English and Russian options. |
| 9 | Installer | `docs/assets/screenshots/09-installer.png` | Inno Setup installer wizard for `ShelfyGAI-Setup-v0.1.0.exe`. |

## Recommended Sizes

- Main README screenshots: `1600x1000` or `1440x900`.
- Wide release preview crops: `1920x1080`.
- Tray menu screenshots: crop around the tray menu, usually `900x700` or
  smaller.
- Installer screenshots: crop the installer window cleanly, usually around
  `900x700`.
- High DPI capture is welcome, but export final PNGs at a readable 1x or 2x
  size so GitHub renders them cleanly.

## Capture Guidance

- Use Windows 11 dark mode when possible.
- Use ShelfyGAI's dark theme.
- Avoid showing personal file paths, private window titles, usernames, emails,
  browser tabs, notifications, or personal account details.
- Prefer ordinary productivity apps such as Notepad, Terminal, Calculator, or a
  browser on a neutral page.
- Keep the taskbar visible for screenshots that explain taskbar behavior.
- Verify text is readable at GitHub README width before committing images.
- Use the same accent color and language across a screenshot set unless the shot
  is specifically about language switching.

## Release Capture Flow

1. Build or run the current release candidate.
2. Open a few safe, ordinary desktop windows.
3. Capture `01-main-open-windows.png` before hiding anything.
4. Hide two or three windows and capture `02-hidden-windows.png`.
5. Pin one or two windows and capture `03-pinned.png`.
6. Create a group, add windows, and capture `04-groups.png`.
7. Capture `05-taskbar-group-window.png` with the unified overlay hub near the
   tray area, one expanded group in the flyout, and, if enabled, one compact
   individual group marker.
8. Open Settings and capture `06-settings.png`.
9. Open the tray menu and capture `07-tray-menu.png`.
10. Switch between English and Russian and capture `08-language-switch.png`.
11. Run the release installer and capture `09-installer.png`.

## Before Commit

- Confirm each path exists and matches the table above.
- Confirm images do not reveal private data.
- Confirm images match the current public UI.
- Confirm screenshots are updated in the same release branch as README changes.
