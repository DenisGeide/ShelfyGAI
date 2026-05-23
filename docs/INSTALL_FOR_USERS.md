# Install ShelfyGAI

ShelfyGAI is distributed as a normal Windows installer. You do not need Python,
pip, Git, or any developer tools.

## Quick Install

1. Download `ShelfyGAI-Setup-v0.1.0.exe` from the GitHub Releases page.
2. Run `ShelfyGAI-Setup-v0.1.0.exe`.
3. Follow the setup wizard.
4. Open ShelfyGAI from the Start Menu.
5. Done.

## What The Installer Does

- Installs ShelfyGAI as a Windows desktop application.
- Creates a Start Menu shortcut.
- Creates a desktop shortcut by default.
- Adds a normal Windows uninstaller.
- Does not enable launch-with-Windows by default.
- Does not require Python, pip, or Git.

## Uninstalling

Use Windows Settings or Control Panel to uninstall ShelfyGAI like any other
desktop application.

Uninstalling removes the installed application files, but it intentionally keeps
your local user data:

```text
%APPDATA%\ShelfyGAI
```

That folder contains settings, logs, and recovery state. Delete it manually only
if you want to fully reset ShelfyGAI data for your Windows account.

## Notes

Unsigned open-source alpha builds may show a Windows SmartScreen warning. This
does not mean the app uses telemetry or cloud services. ShelfyGAI is local-first:
settings and logs stay on your computer.
