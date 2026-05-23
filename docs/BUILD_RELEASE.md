# Build A ShelfyGAI Release

This guide is for maintainers building the public Windows installer. Normal users
should download `ShelfyGAI-Setup-v0.1.0.exe` and do not need these steps.

## Requirements

- Windows 10 or Windows 11
- Python 3.11 or newer
- PowerShell
- Git
- Inno Setup 6

Install Inno Setup 6 and make sure `ISCC.exe` is available in `PATH`, or pass
its full path to `scripts\build_installer.ps1`.

## Build Steps

From the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[build]"
.\scripts\build_exe.ps1 -Clean
.\scripts\build_installer.ps1 -SkipExeBuild
```

The PyInstaller step creates:

```text
dist\ShelfyGAI\ShelfyGAI.exe
```

The Inno Setup step creates the user-facing installer:

```text
dist\installer\ShelfyGAI-Setup-v0.1.0.exe
```

## One-Command Build

If build dependencies are already installed, the executable and installer can be
built together:

```powershell
.\scripts\build_installer.ps1 -Clean
```

If Inno Setup is not on `PATH`:

```powershell
.\scripts\build_installer.ps1 -Clean -InnoCompiler "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

## Release Smoke Checks

Before uploading the installer:

```powershell
python -m ruff check . --no-cache
python -m pytest -p no:cacheprovider
python -m compileall src tests scripts
.\scripts\build_exe.ps1 -Clean -SmokeTest
.\scripts\build_installer.ps1 -SkipExeBuild
```

Then install `dist\installer\ShelfyGAI-Setup-v0.1.0.exe` on a clean Windows
profile or VM and verify:

- ShelfyGAI starts without Python installed.
- The Start Menu shortcut opens the app.
- The desktop shortcut is created by default and opens the app.
- The uninstaller removes app files.
- `%APPDATA%\ShelfyGAI` remains after uninstall unless manually deleted.

## Installer Behavior

The release installer is the primary artifact for normal users. It wraps the
PyInstaller onedir package, installs app files, creates Windows shortcuts, and
keeps user settings outside the install directory so updates and uninstall/reinstall
cycles do not erase local preferences.
