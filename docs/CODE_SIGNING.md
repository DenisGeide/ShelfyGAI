# Code Signing

This document explains how ShelfyGAI maintainers should think about Windows
code signing and SmartScreen warnings for public releases.

## Why Windows SmartScreen May Warn Users

Windows SmartScreen is designed to protect users from unfamiliar or potentially
unsafe downloads. It can show warnings when an executable has little or no
download reputation, even if the application is open source and built with good
intentions.

For a new project like ShelfyGAI, early release artifacts may trigger warnings
because:

- The executable is unsigned.
- The signing certificate has little established reputation.
- The file has not been downloaded by many users yet.
- The app is new and Windows has limited reputation data for it.
- The installer or executable was rebuilt, changing its file hash.

A SmartScreen warning does not automatically mean an app is harmful. It does
mean Windows does not yet have enough trust information to present it as a
well-known application.

## Why Unsigned Open-Source Apps Can Trigger Warnings

Open-source projects often start without a paid code signing certificate.
Unsigned Windows executables are common during early development, but they are
less friendly for end users because Windows cannot verify the publisher.

Unsigned builds also make it harder for users to distinguish official project
artifacts from modified or redistributed copies. For public releases,
maintainers should work toward signed builds as soon as practical.

## Maintainer Signing Guidance

For production releases, maintainers should use a legitimate code signing
certificate issued by a trusted certificate authority.

Recommended approach:

1. Decide who legally maintains the release identity.
2. Obtain an OV or EV code signing certificate from a reputable certificate
   authority.
3. Protect private keys carefully, preferably using a hardware token or secure
   signing service.
4. Sign the PyInstaller executable and the installer produced by Inno Setup.
5. Timestamp signatures so releases remain verifiable after certificate expiry.
6. Verify signatures before publishing release artifacts.
7. Publish checksums for release files.
8. Keep signing credentials out of the repository and CI logs.

Typical artifacts to sign:

- `dist/ShelfyGAI/ShelfyGAI.exe`
- `dist/installer/ShelfyGAI-Setup-<version>.exe`

Example tools maintainers may use:

- Microsoft SignTool from the Windows SDK.
- A certificate-authority-supported hardware token workflow.
- A trusted signing service integrated with the release process.

Exact commands depend on the certificate provider and signing environment, so
this repository intentionally does not hardcode a fake or universal signing
command.

## What Not To Do

Do not:

- Commit private keys, `.pfx` files, passwords, tokens, or certificate secrets.
- Use fake certificates for public releases.
- Tell users to disable SmartScreen.
- Tell users to bypass Windows security warnings as a normal installation step.
- Repackage unofficial binaries as official releases.
- Add scripts that weaken Windows security settings.
- Add undocumented post-install behavior to avoid warnings.

ShelfyGAI should remain transparent and local-first. Trust should come from
clear source code, reproducible build practices where possible, published
release notes, checksums, and proper signing.

## Release Checklist

Before publishing a signed release:

- Build from a clean release tag.
- Run lint and tests.
- Build the PyInstaller executable.
- Build the Inno Setup installer.
- Sign the executable.
- Sign the installer.
- Verify both signatures.
- Generate and publish checksums.
- Upload artifacts only through the official GitHub release.
- Document whether the release is signed or unsigned in the release notes.

## Communicating With Users

Release notes should be clear when builds are unsigned or newly signed. A good
open-source message is:

> This release is unsigned, so Windows SmartScreen may show a warning. The
> source code and build scripts are available in this repository. Future releases
> are planned to use proper code signing.

Once signing is available, release notes should state the verified publisher
name users should expect to see.
