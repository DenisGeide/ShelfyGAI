<p align="center">
  <img src="src/shelfygai/resources/app_icon.svg" width="96" height="96" alt="ShelfyGAI app icon">
</p>

<h1 align="center">ShelfyGAI</h1>

<p align="center">
  A simple Windows window organizer for a cleaner taskbar and calmer workspace.
</p>

<p align="center">
  <a href="https://github.com/DenisGeide/ShelfyGAI/actions/workflows/python-check.yml">
    <img alt="CI status" src="https://img.shields.io/github/actions/workflow/status/DenisGeide/ShelfyGAI/python-check.yml?branch=main&label=CI&style=flat-square">
  </a>
  <a href="https://github.com/DenisGeide/ShelfyGAI/releases">
    <img alt="Release" src="https://img.shields.io/badge/release-v0.1.0--alpha-2f81f7?style=flat-square">
  </a>
  <a href="LICENSE">
    <img alt="License MIT" src="https://img.shields.io/badge/license-MIT-green?style=flat-square">
  </a>
  <img alt="Windows 10 and 11" src="https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078d4?style=flat-square&logo=windows">
</p>

<p align="center">
  <a href="https://github.com/DenisGeide/ShelfyGAI/releases/download/v0.1.0-alpha/ShelfyGAI-Setup-v0.1.0.exe">
    <img alt="Download ShelfyGAI for Windows" src="https://img.shields.io/badge/Download%20for%20Windows-ShelfyGAI--Setup--v0.1.0.exe-2f81f7?style=for-the-badge&logo=windows">
  </a>
</p>

<p align="center">
  One installer. No Python, pip, or Git required.
</p>

## Overview

ShelfyGAI helps you hide selected application windows, pin important windows
above others, and restore everything safely when you need it again. It is
designed as a productivity utility, not a background monitoring tool.

ShelfyGAI is local-first:

- no telemetry
- no ads
- no account system
- no cloud sync
- no background service installed without user action
- settings and logs stay under `%APPDATA%\ShelfyGAI`

## Download

For normal users, use the offline Windows installer:

[Download ShelfyGAI-Setup-v0.1.0.exe](https://github.com/DenisGeide/ShelfyGAI/releases/download/v0.1.0-alpha/ShelfyGAI-Setup-v0.1.0.exe)

After installation, ShelfyGAI appears in the Start Menu and creates a desktop
shortcut by default.

## Features

- Hide selected windows.
- Hide windows from the Windows taskbar.
- Hide windows from Alt+Tab when supported by the target window.
- Restore one window, the latest hidden window, or everything safely.
- Pin windows above other windows.
- Create groups for organized window workflows.
- Optionally show a ShelfyGAI-owned group window as one taskbar item.
- Switch the app interface between English and Russian.
- Keep settings, logs, and recovery state locally.

## Screenshots

Screenshots are intentionally not embedded until real release images are ready.
This avoids a wall of broken placeholders and keeps the project page clean.

Planned screenshot slots are documented in
[docs/assets/screenshots/README.md](docs/assets/screenshots/README.md).

## Installation

1. Download `ShelfyGAI-Setup-v0.1.0.exe` from the release page.
2. Run the installer.
3. Choose **Install for me only** unless you need a machine-wide install.
4. Open ShelfyGAI from the Start Menu or desktop shortcut.

The installer:

- does not require Python
- does not require Git
- creates a Start Menu shortcut
- creates a desktop shortcut by default
- installs a normal Windows uninstaller
- does not enable startup by default
- preserves user settings in `%APPDATA%\ShelfyGAI`

## Run From Source

Requirements:

- Windows 10 or Windows 11
- Python 3.11 or newer

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m shelfygai
```

Development checks:

```powershell
python -m pip install -e ".[dev]"
python -m ruff check .
python -m pytest
```

## Build

Build the standalone application folder:

```powershell
python -m pip install -e ".[build]"
.\scripts\build_exe.ps1 -Clean
```

Expected output:

```text
dist\ShelfyGAI\ShelfyGAI.exe
```

Build the user installer:

```powershell
.\scripts\build_installer.ps1 -SkipExeBuild
```

Expected output:

```text
dist\installer\ShelfyGAI-Setup-v0.1.0.exe
```

More build notes:

- [docs/BUILD_RELEASE.md](docs/BUILD_RELEASE.md)
- [docs/BUILD.md](docs/BUILD.md)
- [docs/INSTALLER.md](docs/INSTALLER.md)

## How It Works

ShelfyGAI enumerates normal top-level Windows application windows and lets the
user choose what to do with a selected window.

When a window is hidden, ShelfyGAI stores the original extended window style
before changing anything. Hide options are applied with reversible Windows style
updates and `SetWindowPos(..., SWP_FRAMECHANGED)`. On restore, ShelfyGAI writes
the exact original style back.

The two reliable cases are documented clearly:

- hiding from both taskbar and Alt+Tab removes `WS_EX_APPWINDOW` and adds
  `WS_EX_TOOLWINDOW`
- hiding from taskbar only avoids `WS_EX_TOOLWINDOW`, so the window should stay
  visible in Alt+Tab, but some apps may remain on the taskbar

Alt+Tab-only hiding is best effort because Windows does not expose a fully
reliable style for every app that removes only Alt+Tab while preserving taskbar
behavior. Tray icon hiding is stored as a preference only; ShelfyGAI does not use
unsafe shell injection, Explorer restarts, or registry hacks to remove third-party
notification area icons.

Pinning uses `SetWindowPos(hwnd, HWND_TOPMOST, ...)`. Unpinning uses
`HWND_NOTOPMOST`, and ShelfyGAI unpins currently pinned windows on exit by
default.

Optional group taskbar windows are normal ShelfyGAI-owned windows. They provide
a safe group representation without modifying Explorer or the Windows shell.

## Safety

ShelfyGAI is designed to keep windows recoverable:

- it does not close target apps when hiding windows
- it avoids managing its own windows
- it avoids Windows taskbar shell windows and Start Menu surfaces
- it stores recovery state while windows are hidden
- it can restore hidden windows on normal exit
- it ignores stale window handles after restart

If something looks wrong, open ShelfyGAI and use **Restore all**.

## Limitations

- Tray icon hiding is limited and may not work for third-party apps. In the alpha,
  ShelfyGAI does not perform unsafe tray icon removal.
- Taskbar-only and Alt+Tab-only hiding are constrained by Windows shell behavior.
  If a combination cannot be guaranteed, ShelfyGAI warns before applying it.
- Some apps recreate windows and may reappear in the taskbar or Alt+Tab.
- Admin or elevated windows may require running ShelfyGAI as administrator.
- Native Windows taskbar folders are not implemented because they require unsafe
  shell-level modifications.
- ShelfyGAI group taskbar windows are safe app-owned windows, not native Windows
  taskbar folders.
- Some custom window frameworks may not respond to standard Windows style
  changes.
- Window handles are valid only for the current Windows session.
- Alpha builds may be unsigned, so Windows SmartScreen may show a warning.

## Privacy

ShelfyGAI stores data locally:

- settings: `%APPDATA%\ShelfyGAI\settings.json`
- logs: `%APPDATA%\ShelfyGAI\logs\`
- recovery state: `%APPDATA%\ShelfyGAI\recovery.json`

The app does not collect analytics, sync data, or require an account.

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md).

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before
opening a pull request.

Project expectations:

- keep ShelfyGAI simple and local-first
- keep restore and recovery behavior safe
- avoid surprise background behavior
- keep Windows-specific code isolated behind platform adapters
- add tests for settings, hidden-window behavior, pinning, recovery, and guardrails

## License

ShelfyGAI is released under the MIT License. See [LICENSE](LICENSE).
