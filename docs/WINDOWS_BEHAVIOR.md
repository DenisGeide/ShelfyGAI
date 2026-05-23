# Windows Behavior

ShelfyGAI manages top-level windows in the current desktop session.

## Hiding From Taskbar And Alt+Tab

Hiding a selected top-level window does not terminate, suspend, minimize, or primarily call `SW_HIDE` on the target process. ShelfyGAI reads the original extended window style with `GetWindowLong`, removes `WS_EX_APPWINDOW`, adds `WS_EX_TOOLWINDOW`, writes the new style with `SetWindowLong`, and calls `SetWindowPos` with `SWP_FRAMECHANGED`.

The original style is stored in the in-memory managed-window registry and mirrored to local emergency recovery state while the window is managed. Restoring a managed window writes that exact original style back and refreshes the frame again. If the target window has already closed, ShelfyGAI removes it from the managed list and continues without crashing.

Restoring can optionally request foreground focus. Restore-on-exit intentionally restores styles without requesting focus.

## Groups And Saved Metadata

Groups are local organization metadata. The `Ungrouped` group always exists. User-created groups persist across launches, but managed windows are only restored from the live in-memory registry. Saved window metadata is tagged with the current Windows boot ID and is discarded after reboot to avoid acting on stale HWND values.

## Open Window Enumeration

The Open Windows page enumerates top-level windows with WinAPI calls. ShelfyGAI skips invisible windows, empty-title windows, known Windows shell surfaces, owned tool windows, critical system windows, and its own window. For each remaining window it gathers the HWND, title, process ID, process name, executable path when accessible, visibility state, and minimized state.

## Restoring

Restoring shows the window again, requests a normal restored state, and asks Windows to bring it forward. Windows may deny foreground activation in some focus-stealing scenarios; the window should still become visible.

## Global Hotkeys

ShelfyGAI registers configurable global hotkeys with the Windows `RegisterHotKey` API. It does not install low-level keyboard hooks. The default quick-hide hotkey is `Ctrl+Shift+Space`. Optional hotkeys can restore the last hidden window or toggle ShelfyGAI visibility. Windows may reject a hotkey if another application already owns the same key combination.

## Startup Integration

Launch with Windows uses the current user's `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` key and does not require administrator rights. ShelfyGAI validates the executable path before writing the startup command, detects missing or malformed startup entries, and removes its own startup value safely when startup is disabled. Silent startup appends `--silent-startup` to the saved command.

## Elevated Applications

Windows may restrict interactions with elevated applications when ShelfyGAI is not elevated. Run ShelfyGAI normally unless you understand why elevation is needed.

## Emergency Recovery

While windows are managed, ShelfyGAI persists local emergency recovery state under `%APPDATA%\ShelfyGAI\recovery.json`. The state includes the current boot id, HWND, process id, and original extended style for each managed window.

If ShelfyGAI encounters a fatal Python exception, it attempts a non-interactive restore before shutdown. On the next launch, it also checks emergency recovery state and restores still-live windows from the same boot when possible. Recovery state from earlier Windows boots is ignored because HWND values are not stable across restarts.

## Safety

The default setting restores managed windows on exit. Fatal exception handling and next-launch emergency recovery reduce the chance of a managed window remaining inaccessible, but force-killing the process can still require relaunching ShelfyGAI to run recovery.
