# ShelfyGAI Feedback Round 02

This document captures the second round of product corrections after reviewing
the simplified UI, current hide behavior, groups direction, pin stability, and
future overlay group concept.

No code changes are included in this document. It is a planning and product
feedback artifact for the next implementation pass.

## Context

- Version reviewed: ShelfyGAI 0.1.0 alpha
- Platform: Windows desktop
- Feedback source: hands-on testing, screenshots, and updated product direction
- Scope: naming, hide behavior, confirmation text, groups, sidebar clarity,
  pinning reliability, performance, and overlay group concept

## Corrections

### 1. Rename Shelf To Hidden Windows

The term "Shelf" is still not clear enough for normal users.

Rename everywhere:

- English: `Shelf` -> `Hidden windows`
- Russian: `Полка` -> `Скрытые окна`

This should apply to:

- sidebar navigation
- buttons
- dialogs
- empty states
- settings text
- tray menu text
- documentation
- README
- localization files

The product action should become easier to understand immediately: users are
not moving a window to an abstract shelf; they are managing hidden windows.

### 2. Hide Options Are Currently Wrong

The hide option behavior must match the selected toggles exactly.

Current issue:

- if `Hide from Alt+Tab` is unchecked, the target window must remain visible in
  Alt+Tab
- confirmation text must not claim the window will be hidden from Alt+Tab when
  that option is disabled

Expected behavior:

- selected options determine the exact style changes
- unselected options are not applied
- restore reverses only the changes ShelfyGAI made
- UI text accurately describes what will happen

### 3. Confirmation Dialog Must Be Dynamic

The confirmation dialog shown before hiding a window must be generated from the
selected options.

Required dialog states:

- taskbar only
- Alt+Tab only
- taskbar + Alt+Tab
- tray option included if enabled
- no selected options should block the action

If no hide options are selected, the action should be blocked with a clear,
friendly message explaining that at least one hide target must be selected.

The dialog should never use a generic warning that does not match the actual
selected behavior.

### 4. Current Groups Page Is Not Desired Behavior

The current Groups page is useful as a management surface, but it does not yet
match the desired product behavior.

The current page feels like a simple metadata list. The desired behavior is a
window organization feature that changes how grouped windows are represented in
the workspace.

### 5. Desired Group Behavior

Desired group flow:

1. User creates a group, for example `Work`.
2. User adds 2-3 windows to the group.
3. Those windows hide from the normal taskbar by default.
4. One ShelfyGAI group marker/window represents them.
5. Clicking the group marker opens a small popup.
6. The popup shows apps/windows in that group.
7. User can open one window or restore all windows in the group.

Important product point:

The group should feel like a simple taskbar organization container, while still
being safe and owned by ShelfyGAI. It should not require shell injection,
Explorer modification, or native taskbar folder hacks.

### 6. Remove Sidebar Icons

Sidebar icons should be removed.

Reason:

- icons add noise
- text labels are already clear
- the app should feel calmer and more minimal
- fewer visual elements make the product easier to understand

Sidebar should use simple text navigation:

- Open windows
- Hidden windows
- Pinned
- Groups
- Settings
- About

### 7. UI Should Be Calmer And More Minimal

The interface should continue moving toward a calmer Windows utility feel.

Direction:

- fewer borders
- fewer nested cards
- fewer simultaneous controls
- clearer selected state
- more whitespace
- less decoration
- no important icon-only actions
- short and direct labels

The app should be understandable in under five seconds.

### 8. Pin Must Be Stable

Pinning must be reliable, reversible, and runtime-only by default.

Rules:

- Pin means `always on top` only.
- Unpin means `not always on top`.
- All pinned windows must be unpinned on ShelfyGAI exit.
- No pinned state should be restored automatically after reboot.
- ShelfyGAI must not pin windows unless the user explicitly presses Pin.
- ShelfyGAI must not modify unrelated windows.

Add WinAPI debug logging for pin issues:

- pin requested
- target HWND
- target process name
- target title
- previous topmost-related state where detectable
- `SetWindowPos(HWND_TOPMOST)` result
- `SetWindowPos(HWND_NOTOPMOST)` result
- WinAPI error code when available
- shutdown cleanup result

This is important because previous testing showed windows could remain
always-on-top unexpectedly.

### 9. Optimization Direction

Performance should be improved as the UI becomes simpler.

Optimization requirements:

- avoid frequent full scans of open windows
- lazy-load icons
- cache icons efficiently
- avoid unnecessary watchers
- do not repaint the whole UI unnecessarily
- only run the pin prevent-minimize watcher when at least one pinned window has
  that advanced option enabled
- avoid refresh loops that consume CPU when the app is idle

The app should feel quiet when sitting in the background.

### 10. Overlay Groups Concept

Explore a safe overlay group marker concept.

Desired behavior:

- safe overlay marker above the Windows taskbar
- vertical colored marker
- draggable
- saved position
- supports bottom, top, left, and right taskbar layouts
- hides during fullscreen applications
- hover quick controls appear after 1-2 seconds
- highly customizable

Potential controls:

- open group popup
- restore one window
- restore all
- hide all
- group settings

Safety requirements:

- no Explorer injection
- no shell extension
- no registry hacks
- no forced Explorer restart
- no unsafe taskbar manipulation

This should be treated as a ShelfyGAI-owned overlay, not a native Windows
taskbar folder.

## Decisions

- Rename `Shelf` / `Полка` to `Hidden windows` / `Скрытые окна`.
- Fix hide option logic before adding more hiding features.
- Make confirmation dialogs fully dynamic and option-aware.
- Keep groups, but redesign them around group markers/popups.
- Remove sidebar icons.
- Continue reducing visual noise.
- Prioritize pin stability and cleanup.
- Add deeper WinAPI debug logging for pin behavior.
- Optimize refresh, icon loading, and watchers.
- Research overlay groups as a safe app-owned representation.

## Next Recommended Implementation Order

1. Rename Shelf to Hidden windows across UI, docs, and translations.
2. Fix hide option logic and dynamic confirmation dialogs.
3. Add pin debug logging and verify exit cleanup.
4. Remove sidebar icons and simplify remaining visual noise.
5. Redesign groups around the desired marker/popup behavior.
6. Add performance improvements around scanning, icons, and watchers.
7. Prototype overlay groups only after the core group model is stable.
