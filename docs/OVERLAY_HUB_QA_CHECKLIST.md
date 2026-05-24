# Overlay Hub QA Checklist

Use this checklist before public builds that change the unified overlay hub.

## Taskbar Positions

- Bottom taskbar: hub appears above the taskbar and avoids the clock/tray area.
- Top taskbar: hub appears below the taskbar and avoids the clock/tray area.
- Left taskbar: hub appears beside the taskbar and avoids the taskbar end area.
- Right taskbar: hub appears beside the taskbar and avoids the taskbar end area.
- Dragging near a taskbar edge snaps smoothly into a safe position.
- Dragging away from the taskbar leaves the hub in free position.

## Taskbar Autohide

- Enable Windows taskbar autohide.
- Confirm the hub does not sit on the exact screen edge that reveals the taskbar.
- Reveal and hide the taskbar several times.
- Confirm the hub follows the usable taskbar area without jumping aggressively.
- Confirm clicking the hub does not block the taskbar reveal area.

## Multi-Monitor

- Test with the taskbar on the primary monitor.
- Test with the taskbar on a secondary monitor if available.
- Drag the hub to each monitor and restart ShelfyGAI.
- Confirm saved hub position restores on the correct monitor.
- Confirm snapping uses the active monitor bounds, not the primary monitor only.

## DPI Scaling

- Test at 100%, 125%, 150%, and 200% scaling where available.
- Confirm the hub size remains compact and clickable.
- Confirm popup placement remains on screen.
- Confirm the hub does not overlap the taskbar clock or notification area.

## Fullscreen

- Start a fullscreen app or video.
- Confirm overlay markers and the hub hide when hide-during-fullscreen is enabled.
- Exit fullscreen and confirm the hub returns.
- Confirm the hub returns to the safe snapped position near the taskbar.

## Popup Interaction

- Click the hub and confirm the flyout opens immediately.
- Confirm the flyout does not cover large taskbar areas.
- Expand/collapse groups.
- Open, restore, and remove hidden windows from the flyout.
- Close the flyout and confirm the hub remains responsive.
