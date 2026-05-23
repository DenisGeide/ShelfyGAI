# ShelfyGAI Experimental Web Installer

The ShelfyGAI web installer is an experimental maintainer-only bootstrapper. It
is not the recommended public alpha download.

For public alpha releases, normal users should download the offline installer:

```text
ShelfyGAI-Setup-v0.1.0.exe
```

Keep this web installer unpublished unless the project explicitly decides to
support a downloader bootstrapper and has tested it against the final GitHub
Release asset.

## Output

```text
dist\installer\ShelfyGAI-WebSetup-0.1.0.exe
```

This output is for internal release experiments only. Do not present it as the
normal-user installer for the public alpha.

## How It Works

- The web installer is built with Inno Setup.
- It downloads `ShelfyGAI-Setup-v0.1.0.exe` from an HTTPS GitHub Releases URL.
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
dist\installer\ShelfyGAI-Setup-v0.1.0.exe
```

Compute the checksum:

```powershell
Get-FileHash .\dist\installer\ShelfyGAI-Setup-v0.1.0.exe -Algorithm SHA256
```

Create a GitHub release draft for `v0.1.0` and upload the full offline
installer. The release asset URL should look like:

```text
https://github.com/DenisGeide/ShelfyGAI/releases/download/v0.1.0-alpha/ShelfyGAI-Setup-v0.1.0.exe
```

Build the web installer with that URL and SHA-256:

```powershell
.\scripts\build_web_installer.ps1 `
  -DownloadUrl "https://github.com/DenisGeide/ShelfyGAI/releases/download/v0.1.0-alpha/ShelfyGAI-Setup-v0.1.0.exe" `
  -DownloadSha256 "<64-character-sha256>"
```

Upload `ShelfyGAI-WebSetup-0.1.0.exe` only if maintainers intentionally enable
the experimental downloader path. The recommended normal-user download remains
the full installer, `ShelfyGAI-Setup-v0.1.0.exe`, because it is transparent,
works offline after download, and does not require a second download step.

## Safety Notes

- Use HTTPS only.
- Embed SHA-256 for release builds.
- Do not download from personal cloud links or mutable URLs.
- Do not bypass Windows SmartScreen.
- Do not hide that the installer downloads another installer.
- Keep the offline installer available for transparency and archival use.
