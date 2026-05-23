# Packaging

ShelfyGAI uses PyInstaller to produce a standalone Windows executable and
Inno Setup to wrap that executable in a standard Windows installer.

## Build Prerequisites

- Windows 10 or Windows 11
- Python 3.11 or newer
- Project dependencies installed
- PyInstaller installed through the build extra

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[build]"
```

## Build Executable

```powershell
.\scripts\build_exe.ps1 -Clean
```

Output:

```text
dist\ShelfyGAI\ShelfyGAI.exe
```

The build script renders `src\shelfygai\resources\app_icon.svg` into a temporary Windows `.ico` file under `build\assets\app_icon.ico` before invoking PyInstaller. The generated icon is not committed.

To run a package smoke test after building:

```powershell
.\scripts\build_exe.ps1 -Clean -SmokeTest
```

The smoke test launches the packaged executable with `--packaging-smoke-test`
and a temporary `APPDATA` directory to verify startup, translations, icon
resources, settings writes, and log writes.

## Build Installer

Install Inno Setup 6, then make sure `ISCC.exe` is available in `PATH`.
Build the executable first because the installer consumes the full
`dist\ShelfyGAI\` onedir package and `build\assets\app_icon.ico`.

```powershell
.\scripts\build_exe.ps1 -Clean
.\scripts\build_installer.ps1 -SkipExeBuild
```

Output:

```text
dist\installer\ShelfyGAI-Setup-0.1.0.exe
```

The Inno Setup script lives at:

```text
installer\ShelfyGAI.iss
```

Installer behavior:

- Installs to Program Files for all-users installs or a user-local app directory for current-user installs.
- Creates a Start Menu shortcut.
- Offers an optional desktop shortcut.
- Provides normal Windows uninstall support.
- Offers to launch ShelfyGAI after install.
- Does not enable Windows autostart by default.
- Does not remove `%APPDATA%\ShelfyGAI` on uninstall.

More details are in `installer\README_INSTALLER.md`.

## Release Package

```powershell
.\scripts\release.ps1
```

Output:

```text
dist\release\ShelfyGAI-0.1.0-win-x64.zip
dist\release\SHA256SUMS.txt
```

The release ZIP contains:

- `ShelfyGAI.exe`
- `LICENSE`
- `README.md`
- `RELEASE_NOTES.md`

## Cleanup

```powershell
.\scripts\clean_build.ps1
```

This removes `build\` and `dist\` only after validating the resolved paths stay inside the project.

`scripts\clean_dist.ps1` remains as a compatibility wrapper around
`scripts\clean_build.ps1`.

## Version Metadata

Windows executable metadata lives in:

```text
packaging\windows\version_info.txt
packaging\windows\ShelfyGAI.manifest
```

The PyInstaller build definition lives at:

```text
shelfygai.spec
```

When bumping a release, update:

- `src\shelfygai\__init__.py`
- `pyproject.toml`
- `packaging\windows\version_info.txt`
- `packaging\windows\ShelfyGAI.manifest`
- `installer\ShelfyGAI.iss`
- `CHANGELOG.md`
- release notes under `docs\`

## User Data Persistence

Packaged updates replace the application executable only. ShelfyGAI stores user data outside the install directory:

- Settings: `%APPDATA%\ShelfyGAI\settings.json`
- Logs: `%APPDATA%\ShelfyGAI\logs\`
- Emergency recovery: `%APPDATA%\ShelfyGAI\recovery.json`

Because settings, logs, and recovery state are in roaming AppData, they survive executable replacement, release ZIP extraction, installer upgrades, and uninstall/reinstall cycles.
