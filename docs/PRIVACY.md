# Privacy

ShelfyGAI is local-only.

## What Is Stored

ShelfyGAI stores local settings such as window geometry, safety preferences, groups, and current-boot hidden-window metadata in:

```text
%APPDATA%\ShelfyGAI\settings.json
```

Local logs are stored in:

```text
%APPDATA%\ShelfyGAI\logs\shelfygai.log
```

Crash diagnostics are stored locally in:

```text
%APPDATA%\ShelfyGAI\logs\crashes\
```

Emergency recovery state is stored locally in:

```text
%APPDATA%\ShelfyGAI\recovery.json
```

Logs are local diagnostic files. They may include app lifecycle events, settings field names that changed, exception traces, and window operation handles. Emergency recovery state and crash diagnostics may include window titles, process names, process ids, executable paths, and HWND values so ShelfyGAI can restore hidden windows after an unexpected failure.

## What Is Not Collected

ShelfyGAI does not collect, transmit, sell, or share:

- Window titles outside local ShelfyGAI files
- Application names outside local ShelfyGAI files
- Process metadata outside local ShelfyGAI files
- Usage analytics
- Crash reports outside the local computer
- Personal files

## Network

ShelfyGAI does not require network access for normal operation and does not include cloud features.
