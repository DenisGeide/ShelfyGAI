# Build Guide

This guide covers local development checks and production packaging for
ShelfyGAI. It does not publish releases.

## Requirements

- Windows 10 or Windows 11
- Python 3.11 or newer
- PowerShell
- Git

## Development Setup

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Local Checks

```powershell
python -m ruff check . --no-cache
python -m pytest -p no:cacheprovider
python -m compileall src tests scripts
```

## Basic Import Check

```powershell
python -c "import shelfygai; print(shelfygai.__version__)"
python -c "from shelfygai.settings.settings_manager import AppSettings; print(AppSettings().app_version)"
```

## Build Executable

Install build dependencies:

```powershell
python -m pip install -e ".[build]"
```

Build the onedir executable package:

```powershell
.\scripts\build_exe.ps1 -Clean
```

Output:

```text
dist\ShelfyGAI\ShelfyGAI.exe
```

## Packaged App Smoke Test

```powershell
.\scripts\build_exe.ps1 -Clean -SmokeTest
```

The smoke test launches the packaged executable with a temporary `APPDATA`
directory and verifies:

- the application starts
- translations load
- bundled icon resources load
- settings write to `%APPDATA%\ShelfyGAI\settings.json`
- logs write to `%APPDATA%\ShelfyGAI\logs\shelfygai.log`

## Build Release Installer

The normal user-facing release artifact is the full Inno Setup installer:

```text
dist\installer\ShelfyGAI-Setup-v0.1.0.exe
```

Build it with:

```powershell
.\scripts\build_installer.ps1 -Clean
```

Users who download this installer do not need Python, pip, Git, or source code.
The installer creates Start Menu and desktop shortcuts, adds a Windows
uninstaller, and preserves `%APPDATA%\ShelfyGAI` on uninstall.

## Clean Build Artifacts

```powershell
.\scripts\clean_build.ps1
```

This removes `build\` and `dist\` after validating the resolved paths remain
inside the repository.

## Experimental Web Installer Bootstrapper

The full Inno Setup installer above is the public alpha release download. A web
installer bootstrapper exists only as an experimental maintainer tool for a
future downloader flow. Do not publish it for normal users unless the project
explicitly decides to support that path:

```powershell
.\scripts\build_web_installer.ps1 `
  -DownloadUrl "https://github.com/DenisGeide/ShelfyGAI/releases/download/v0.1.0-alpha/ShelfyGAI-Setup-v0.1.0.exe" `
  -DownloadSha256 "<64-character-sha256>"
```

Output:

```text
dist\installer\ShelfyGAI-WebSetup-0.1.0.exe
```

## Continuous Integration

GitHub Actions runs `.github/workflows/python-check.yml` on Windows. The workflow
installs development dependencies, runs import checks, runs `ruff`, and runs the
test suite. It intentionally does not publish release artifacts.

## Related Docs

- [Packaging](PACKAGING.md)
- [Installer](INSTALLER.md)
- [User install guide](INSTALL_FOR_USERS.md)
- [Release build guide](BUILD_RELEASE.md)
- [QA checklist](QA_CHECKLIST.md)
