# GitHub Release Checklist

Use this checklist before manually publishing a ShelfyGAI GitHub release. Do not publish or upload
artifacts automatically during release preparation.

## Version And Changelog

- [ ] Confirm `src/shelfygai/__init__.py` version matches `pyproject.toml`.
- [ ] Confirm `installer\ShelfyGAI.iss` version metadata matches the release version.
- [ ] Confirm `packaging\windows\version_info.txt` version metadata matches the release version.
- [ ] Move completed items from `CHANGELOG.md` `[Unreleased]` into the release section.
- [ ] Confirm release notes match the changelog.
- [ ] Tag format is `vMAJOR.MINOR.PATCH`, for example `v0.1.0`.

## Documentation

- [ ] README links render correctly.
- [ ] README includes English and Russian sections.
- [ ] `LICENSE` contains the MIT license.
- [ ] `CONTRIBUTING.md`, `SECURITY.md`, and `CODE_OF_CONDUCT.md` are present.
- [ ] Build instructions in `docs\BUILD.md` are current.
- [ ] Installer instructions in `docs\INSTALLER.md` and `installer\README_INSTALLER.md` are current.
- [ ] Code signing guidance in `docs\CODE_SIGNING.md` is honest and does not include unsafe workarounds.
- [ ] Screenshot and demo placeholders are documented under `docs\assets\`.
- [ ] Release notes include what ShelfyGAI does, Windows 10/11 support, known limitations, safety
  notes, and bug reporting instructions.

## Quality Gates

- [ ] `python -m ruff check . --no-cache`
- [ ] `python -m pytest -p no:cacheprovider`
- [ ] `python -m compileall src tests`
- [ ] Launch app on Windows 10.
- [ ] Launch app on Windows 11.
- [ ] Hide and restore a normal application window.
- [ ] Restore all managed windows.
- [ ] Close-to-tray and Quit behavior verified.
- [ ] Startup entry add/remove verified under HKCU only.
- [ ] Global hotkeys register and unregister cleanly.
- [ ] English and Russian localization files load.
- [ ] English and Russian localization keys match.
- [ ] Language switch works without restarting where possible.

## Privacy And Security

- [ ] No telemetry, analytics, ads, cloud sync, or network listeners added.
- [ ] No secrets, tokens, credentials, private keys, or certificates committed.
- [ ] No local settings, logs, generated files, cache files, or virtual environments committed.
- [ ] No private usernames, local machine paths, window titles, or process data in docs or tests.
- [ ] Security policy and issue templates are present.

## Packaging

- [ ] `python -m pip install -e ".[build]"`
- [ ] `.\scripts\clean_build.ps1`
- [ ] `.\scripts\build_exe.ps1 -Clean`
- [ ] `dist\ShelfyGAI\ShelfyGAI.exe` launches on Windows.
- [ ] `.\scripts\build_installer.ps1 -SkipExeBuild` succeeds when Inno Setup is installed.
- [ ] Full installer SHA-256 is calculated with `Get-FileHash`.
- [ ] `dist\installer\ShelfyGAI-Setup-v0.1.0.exe` is the primary user-facing installer.
- [ ] Installer creates Start Menu and desktop shortcuts.
- [ ] Installer uninstalls app files while preserving `%APPDATA%\ShelfyGAI`.
- [ ] Experimental web installer is left unpublished unless a downloader path is explicitly supported.
- [ ] `.\scripts\release.ps1`
- [ ] Release ZIP is generated under `dist\release\`.
- [ ] `SHA256SUMS.txt` is generated for release artifacts.
- [ ] Settings and logs under `%APPDATA%\ShelfyGAI` survive replacing the executable.
- [ ] Full installer remains attached to the GitHub release.
- [ ] Release artifacts are attached to the GitHub release only after local smoke testing.

## Final Publish

- [ ] Create release branch or signed tag.
- [ ] Draft GitHub release manually.
- [ ] Mark `v0.1.0` as a pre-release/public alpha.
- [ ] Attach release notes from `docs\RELEASE_NOTES_0.1.0.md`.
- [ ] Attach artifacts and checksums only if they were built and verified locally.
- [ ] Verify release links and documentation render correctly.
- [ ] Open a post-release issue for follow-up bugs or packaging improvements.
