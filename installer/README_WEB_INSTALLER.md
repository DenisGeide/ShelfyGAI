# ShelfyGAI Web Installer

The ShelfyGAI web installer is a small one-file bootstrapper for non-technical
users. The user opens one EXE, sees a normal setup wizard, and the bootstrapper
downloads the full offline installer from GitHub Releases.

## Output

```text
dist\installer\ShelfyGAI-WebSetup-0.1.0.exe
```

This is the file to share as the simple "download and install" option.

## How It Works

- The web installer is built with Inno Setup.
- It downloads `ShelfyGAI-Setup-0.1.0.exe` from an HTTPS GitHub Releases URL.
- It can verify the downloaded installer with an embedded SHA-256 hash.
- It launches the downloaded offline installer.
- It does not install a service.
- It does not enable autostart.
- It does not write ShelfyGAI user settings itself.

User settings, logs, and recovery state remain in:

```text
%APPDATA%\ShelfyGAI\
```

## Release Build Flow

Build the normal offline installer first:

```powershell
.\scripts\build_installer.ps1 -Clean
```

Expected output:

```text
dist\installer\ShelfyGAI-Setup-0.1.0.exe
```

Compute the checksum:

```powershell
Get-FileHash .\dist\installer\ShelfyGAI-Setup-0.1.0.exe -Algorithm SHA256
```

Create a GitHub release draft for `v0.1.0` and upload the full offline
installer. The release asset URL should look like:

```text
https://github.com/shelfygai/shelfygai/releases/download/v0.1.0/ShelfyGAI-Setup-0.1.0.exe
```

Build the web installer with that URL and SHA-256:

```powershell
.\scripts\build_web_installer.ps1 `
  -DownloadUrl "https://github.com/shelfygai/shelfygai/releases/download/v0.1.0/ShelfyGAI-Setup-0.1.0.exe" `
  -DownloadSha256 "<64-character-sha256>"
```

Upload `ShelfyGAI-WebSetup-0.1.0.exe` to the same GitHub release. For users who
want the simplest path, link to the web installer first. Keep the full offline
installer available for users who cannot or do not want to install through a
downloader.

## Safety Notes

- Use HTTPS only.
- Embed SHA-256 for release builds.
- Do not download from personal cloud links or mutable URLs.
- Do not bypass Windows SmartScreen.
- Do not hide that the installer downloads another installer.
- Keep the offline installer available for transparency and archival use.
