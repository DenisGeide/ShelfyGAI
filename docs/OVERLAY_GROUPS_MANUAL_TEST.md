# Overlay Groups Manual Test Notes

Overlay markers are ShelfyGAI-owned frameless PySide6 windows. They must not modify
Windows Explorer, restart Explorer, install shell extensions, or inject into the shell.

For detailed unified hub checks around taskbar edges, autohide, DPI scaling, and
multi-monitor behavior, also use `docs/OVERLAY_HUB_QA_CHECKLIST.md`.

## Basic Hub Flow

1. Open ShelfyGAI.
2. Go to **Overlay groups**.
3. Enable overlay groups.
4. Create two overlay groups, for example `Work` and `Chat`.
5. Keep **Use unified overlay hub** enabled.
6. Keep **Replace individual markers with hub** enabled for the default
   one-button workflow.
7. Confirm that one small rounded hub button appears near the taskbar tray or
   overflow area.
8. Click the hub and confirm it opens a compact flyout with all overlay groups.
9. Expand a group inside the flyout and confirm hidden windows appear under it.
10. Use **Open**, **Restore**, and **Bring to front** from the expanded group.

## Individual Marker Flow

1. Enable **Use individual group markers**.
2. Confirm that per-group markers can appear alongside or instead of the hub.
3. Confirm markers are compact, calm, and snapped near the taskbar edge by
   default.
4. Change marker color, width, height, opacity, and corner radius.
5. Confirm the marker updates without restarting ShelfyGAI.

## Drag And Persistence

1. Drag the hub or an individual marker near the taskbar edge.
2. Confirm it snaps to the edge when **Auto-snap to taskbar edge** is enabled.
3. Drag it away from the taskbar edge.
4. Confirm it stays in a free position.
3. Restart ShelfyGAI.
4. Confirm the hub or marker returns to its saved position on the same monitor.
5. Lock marker position and confirm individual markers no longer move.

## Taskbar Position

Repeat the basic marker flow with the Windows taskbar positioned at:

- bottom
- top
- left
- right

Expected result: the hub and markers default near the available desktop edge next
to the taskbar tray or overflow area.
If taskbar edge detection fails, markers should fall back to the bottom screen edge.

## Display Modes

Verify these settings:

- **Use unified overlay hub** shows one compact launcher for all overlay groups.
- **Replace individual markers with hub** keeps the workflow to a single hub
  button even when individual markers are configured.
- **Always show hub** keeps the button clearly visible.
- **Auto-hide hub when idle** dims the button while keeping it clickable.
- **Use individual group markers** shows one marker per group.
- **Compact mode** makes hub and markers smaller and calmer.
- **Hub opacity** changes the unified hub button opacity.
- **Marker spacing** changes the default spacing between per-group markers.
- **Auto-snap to taskbar edge** snaps dragged hub/markers when they are close to
  the taskbar edge.

## Marker Menu

Right-click a marker and verify:

- **Open group** toggles the compact group popup.
- **Pin marker position** locks dragging.
- **Unpin marker position** enables dragging again.
- **Change color** opens the color picker.
- **Settings** opens the Overlay groups page.
- **Hide marker** hides only that marker for the current session.

## Popup

1. Left-click a marker.
2. Confirm the compact popup opens beside the marker.
3. Confirm the popup shows the group name and hidden windows assigned to that group.
4. Use **Open** and confirm the target window is brought forward.
5. Use **Restore** and confirm the target window returns to its original taskbar/Alt+Tab state.
6. Use **Restore all** and confirm all hidden windows assigned to the group are restored.
7. Use **Remove from group** and confirm the window disappears from the popup without closing.
8. Use **Open ShelfyGAI** and confirm the main window opens on the Overlay groups page.
9. Left-click the same marker again and confirm the popup closes.

## Safety Checks

- Marker windows should not appear as managed target windows.
- Marker windows should not cover large taskbar areas.
- Marker windows should not block clicks outside their own small rectangle.
- Hiding a marker must not hide or close target application windows.
