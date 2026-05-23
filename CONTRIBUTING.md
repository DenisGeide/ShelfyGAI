# Contributing

Thanks for helping improve ShelfyGAI.

Please follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) in all project spaces.

## Project Principles

- Keep the app local-only.
- Do not add telemetry, analytics, advertising SDKs, cloud sync, or surprise background services.
- Prefer small, testable changes.
- Keep Windows integration isolated behind core protocols.
- Restore hidden windows safely when changing hidden-window behavior.
- Treat user window titles, process names, paths, settings, and logs as private local data.

## Development Setup

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Checks

Run these before opening a pull request:

```powershell
python -m ruff check . --no-cache
python -m pytest -p no:cacheprovider
python -m compileall src tests
```

For packaging changes, also run:

```powershell
.\scripts\build_exe.ps1 -SmokeTest
```

For UI or Windows behavior changes, also start the app on Windows 10 or Windows 11:

```powershell
python -m shelfygai
```

## Architecture Expectations

- Put business rules in `src/shelfygai/core`.
- Put Windows API calls in `src/shelfygai/platform/windows`.
- Put persistence in `src/shelfygai/settings`.
- Put PySide6 widgets and styles in `src/shelfygai/ui`.
- Keep updater code offline-safe unless a future issue explicitly scopes network behavior.

## Pull Requests

Please include:

- What changed
- Why it changed
- How it was tested
- Manual test notes on Windows 10 or Windows 11 when relevant
- Any risks involving hidden or restored windows

Do not include generated files, local settings, logs, screenshots with private window titles, or machine-specific paths.

## Code Style

The project uses type hints, dataclasses for simple value objects, and `ruff` for linting. Comments should explain non-obvious Windows API behavior, safety decisions, or lifecycle constraints rather than restating simple assignments.
