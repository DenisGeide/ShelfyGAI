# ShelfyGAI Feedback Round 01

This document captures the first round of hands-on feedback from screenshots and
local testing. It is intended to guide the next product iteration before
additional features are added.

## Context

- Version tested: ShelfyGAI 0.1.0 alpha
- Platform: Windows desktop
- Feedback source: screenshots, manual testing, and observed behavior during
  normal app usage
- Scope: UI clarity, pin behavior, hide behavior, groups, installer
  expectations, and documentation needs

## Current Feedback

### 1. Main UI Feels Too Complex

The main UI currently feels too complex and visually noisy for a normal user.
There are many visible sections, buttons, tables, and controls competing for
attention at the same time.

The app should feel more like a simple Windows utility:

- clear primary action
- fewer visible controls by default
- simpler grouping of advanced options
- calmer visual hierarchy

### 2. Layout Is Not Immediately Understandable

The current layout is not immediately understandable for a normal user. It is
not obvious what the user should do first, what each section means, and which
actions affect open windows versus shelf windows versus pinned windows.

The first screen should make the workflow obvious:

1. Select a window.
2. Choose what to do with it.
3. See where the window went.
4. Restore or manage it later.

### 3. UI Looks Overdesigned

The app currently looks overdesigned and not minimal enough. The dark theme,
cards, tables, sidebars, grouped panels, and many buttons create a heavy
interface.

The next design pass should simplify the main screen and reduce visual density
while keeping the Windows 11 utility feel.

### 4. Pin Window Feature Works Incorrectly

The current pin window feature is not reliable enough for release.

Observed issues:

- some windows are pinned correctly
- some windows are not pinned
- some windows become always-on-top unexpectedly
- a browser window stayed always-on-top even after ShelfyGAI was restarted

This is a high-priority safety and usability issue. Pinning must be predictable,
reversible, and never leave windows in an unexpected state.

### 5. Pinned Windows List Ordering Matters

Pinned windows need a clear order model.

Expected behavior:

- the top item in the pinned list should stay visually and behaviorally above
  lower items
- the user must be able to reorder pinned windows
- ordering should be reflected in the always-on-top stack where technically
  possible
- the UI should make the current order obvious

### 6. Hide Destination Control Is Needed

When hiding a window, the user should be able to control where it disappears
from.

Desired hide targets:

- taskbar
- Alt+Tab
- tray overflow / notification area, if technically possible

The current behavior should be split into explicit choices instead of being
hidden behind one action.

### 7. Main Page Needs Three Clear Toggles

The main page should include three clear toggles:

- Hide from taskbar
- Hide from Alt+Tab
- Hide from tray / notification area, if supported

These options should be visible near the hide action so the user understands
exactly what will happen before hiding a window.

### 8. Groups Are Useful

Groups are useful and should stay. The group/folder concept matches the core
product idea of organizing the taskbar and workspace.

The group system should be simplified visually, but the feature direction is
good.

### 9. Need Taskbar Group / Folder Concept

ShelfyGAI should support a taskbar group or folder concept.

Desired behavior:

- user can create a group that appears as one ShelfyGAI taskbar item
- user can put 2-3 windows into that group
- user can open or restore group contents from ShelfyGAI
- user can hide or close group contents from ShelfyGAI
- groups should help reduce taskbar clutter without making windows inaccessible

This should be explored carefully because Windows taskbar grouping behavior has
platform limitations.

### 10. Installer Must Be Simple

The installer flow must be simple for normal users.

Expected user experience:

1. User downloads one `.exe`.
2. User runs it.
3. ShelfyGAI installs.
4. ShelfyGAI launches and works.

The installation experience should not require users to understand Python,
PyInstaller, Inno Setup, source builds, or command-line tools.

### 11. Current Group Buttons Are Unclear

The current group buttons are unclear. Icon-only buttons in the groups area do
not communicate their purpose strongly enough.

Needed improvements:

- clearer labels or tooltips
- more recognizable icons
- simpler button count
- safer confirmation for destructive group actions

Fixed in the next UI pass:

- icon-only group action buttons were replaced with labeled buttons
- group actions now use clear labels: New group, Rename, Delete
- every group action has a tooltip
- group deletion now requires confirmation
- non-empty group deletion asks whether to move windows to Ungrouped or cancel
- group list rows show group name and window count
- selected group state is visually clear
- group rows now support a right-click context menu with Rename, Delete, Move all
  to shelf, and Restore all

### 12. Screenshot Documentation Is Needed

The project needs screenshot documentation with placeholders and descriptions.

Screenshots should cover:

- main window
- open windows list
- shelf windows
- pinned windows
- group controls
- settings page
- tray menu
- installer flow
- language switching
- safety and recovery screens

Each screenshot placeholder should include a short description of what the image
should demonstrate.

## Screenshot Notes

Screenshots from this feedback round should be stored in
`docs/assets/feedback/round-01/`. Use relative links in this document and avoid
embedding large images directly in Markdown.

### Screenshot 01: Current Main UI

Reference: [01-current-main-ui.png](assets/feedback/round-01/01-current-main-ui.png)

Shows the current main UI with sidebar navigation, open windows table, shelf
section, pinned windows section, and quick actions.

What it demonstrates: the UI is visually dense and has too many visible controls
for a first-time user.

### Screenshot 02: Current Pinned List

Reference: [02-current-pinned-list.png](assets/feedback/round-01/02-current-pinned-list.png)

Shows pinned windows with multiple entries and action buttons.

What it demonstrates: pinned window ordering is visible but not controllable,
and the always-on-top behavior needs clearer rules.

### Screenshot 03: Current Tray Overflow

Reference: [03-current-tray-overflow.png](assets/feedback/round-01/03-current-tray-overflow.png)

Shows the Windows tray overflow area with multiple application icons.

What it demonstrates: users expect ShelfyGAI to clarify whether hiding can
affect tray or notification area visibility.

### Screenshot 04: Current Taskbar

Reference: [04-current-taskbar.png](assets/feedback/round-01/04-current-taskbar.png)

Shows several active taskbar items.

What it demonstrates: ShelfyGAI should help reduce taskbar clutter while keeping
user control clear and reversible.

### Screenshot 05: Current Installer Files

Reference: [05-current-installer-files.png](assets/feedback/round-01/05-current-installer-files.png)

Shows installer-related files currently present in the project.

What it demonstrates: developer packaging exists, but the end-user goal should
be one simple downloadable `.exe`.

### Screenshot 06: Current Groups Sidebar

Reference: [06-current-groups-sidebar.png](assets/feedback/round-01/06-current-groups-sidebar.png)

Shows the current group controls in the sidebar.

What it demonstrates: group buttons are unclear and need better labels,
tooltips, or simplified interaction.

## Decision

- Simplify the UI.
- Fix pin logic before adding new features.
- Separate "hide from taskbar", "hide from Alt+Tab", and "hide from tray" as
  explicit options.
- Keep groups.
- Improve installer.
- Update README and GitHub docs.
