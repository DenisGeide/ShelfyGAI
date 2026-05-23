# Installer Guide

ShelfyGAI uses Inno Setup for Windows installer builds. The installer wraps the
PyInstaller onedir package and does not enable autostart by default.

## Requirements

- Windows 10 or Windows 11
- Built PyInstaller package under `dist\ShelfyGAI\`
- Inno Setup 6

Install Inno Setup from the official website, then ensure `ISCC.exe` is in
`PATH` or pass its path to the build script.

## Build Executable First

```powershell
.\scripts\build_exe.ps1 -Clean
```

Expected executable:

```text
dist\ShelfyGAI\ShelfyGAI.exe
```

## Build Installer

```powershell
.\scripts\build_installer.ps1 -SkipExeBuild
```

To build the executable and installer in one command:

```powershell
.\scripts\build_installer.ps1 -Clean
```

If `ISCC.exe` is not discoverable:

```powershell
.\scripts\build_installer.ps1 -SkipExeBuild -InnoCompiler "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

Output:

```text
dist\installer\ShelfyGAI-Setup-v0.1.0.exe
```

This is the primary installer for normal users. They download this one `.exe`,
run it, and do not need Python, pip, Git, or any source checkout.

## Experimental Web Installer Bootstrapper

The full installer above is the only recommended public alpha artifact for
normal users. The web installer is an experimental maintainer-only bootstrapper
that downloads the full installer from GitHub Releases, verifies the optional
SHA-256 hash, and launches the full installer. Do not publish it unless the
project explicitly decides to support a downloader path.

Build the full installer first and attach it to a GitHub release draft. Then
compute its SHA-256:

```powershell
Get-FileHash .\dist\installer\ShelfyGAI-Setup-v0.1.0.exe -Algorithm SHA256
```

Build the web installer:

```powershell
.\scripts\build_web_installer.ps1 `
  -DownloadUrl "https://github.com/DenisGeide/ShelfyGAI/releases/download/v0.1.0-alpha/ShelfyGAI-Setup-v0.1.0.exe" `
  -DownloadSha256 "<64-character-sha256>"
```

Output:

```text
dist\installer\ShelfyGAI-WebSetup-0.1.0.exe
```

For release builds, do not skip `-DownloadSha256`. Keep
`ShelfyGAI-Setup-v0.1.0.exe` as the normal-user release artifact.

## Installer Behavior

- Installs to Program Files for all-users installs or a user-local app directory
  for current-user installs.
- Creates a Start Menu shortcut.
- Creates a desktop shortcut by default.
- Adds standard Windows uninstall support.
- Allows launching ShelfyGAI after installation.
- Does not write an autostart registry entry during installation.
- Does not install a background service.

## User Data Preservation

The installer installs application files only under `{app}`. It intentionally
does not delete or migrate:

```text
%APPDATA%\ShelfyGAI\
```

That directory contains local settings, logs, and emergency recovery state.
These files should survive installer upgrades and uninstall/reinstall cycles.

## Source Files

- `installer\ShelfyGAI.iss`
- `installer\ShelfyGAI-WebSetup.iss` experimental
- `installer\README_INSTALLER.md`
- `installer\README_WEB_INSTALLER.md` experimental
- `scripts\build_installer.ps1`
- `scripts\build_web_installer.ps1`
- `packaging\windows\version_info.txt`
- `packaging\windows\ShelfyGAI.manifest`

## Publishing

This repository does not currently include automated release publishing. Build
and attach installer artifacts manually when the release process is ready.
