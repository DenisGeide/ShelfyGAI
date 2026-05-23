# Overlay Groups Manual Test Notes

Overlay markers are ShelfyGAI-owned frameless PySide6 windows. They must not modify
Windows Explorer, restart Explorer, install shell extensions, or inject into the shell.

## Basic Marker Flow

1. Open ShelfyGAI.
2. Go to **Overlay groups**.
3. Enable overlay groups.
4. Create two overlay groups, for example `Work` and `Chat`.
5. Confirm that two small vertical colored markers appear near the taskbar.
6. Change marker color, width, height, opacity, and corner radius.
7. Confirm the marker updates without restarting ShelfyGAI.

## Drag And Persistence

1. Drag a marker to a different position near the taskbar.
2. Confirm the marker moves only when position is not locked.
3. Restart ShelfyGAI.
4. Confirm the marker returns to its saved position on the same monitor.
5. Lock marker position and confirm dragging no longer moves it.

## Taskbar Position

Repeat the basic marker flow with the Windows taskbar positioned at:

- bottom
- top
- left
- right

Expected result: markers default near the available desktop edge next to the taskbar.
If taskbar edge detection fails, markers should fall back to the bottom screen edge.

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
