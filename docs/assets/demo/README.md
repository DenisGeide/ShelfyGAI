# Demo Assets

This folder is reserved for short demo recordings used by `README.md`, release
notes, and GitHub discussions.

## Expected Files

- `shelfygai-demo.gif` - Short README-friendly demo loop.
- `shelfygai-demo.mp4` - Optional higher-quality source recording for releases.

## Recommended Demo Length

- GIF: 10 to 20 seconds.
- MP4: 20 to 45 seconds.
- Keep the final GIF under roughly 10 MB when possible so GitHub loads it
  quickly.

## Recording A Short Demo GIF

1. Use a clean Windows 11 desktop with dark mode enabled.
2. Set the ShelfyGAI window to about `1280x800` or `1440x900`.
3. Record the app area rather than the entire desktop when possible.
4. Show cursor movement deliberately and pause briefly after each action.
5. Export an MP4 first, then convert to GIF only for README embedding.

Suggested tools:

- ScreenToGif for direct GIF recording and trimming.
- OBS Studio for MP4 capture.
- ShareX for quick region recording.
- `ffmpeg` for conversion:

```powershell
ffmpeg -i shelfygai-demo.mp4 -vf "fps=12,scale=1200:-1:flags=lanczos" shelfygai-demo.gif
```

## Scenarios To Show

- Search open windows, select one, and move it into ShelfyGAI.
- Show the window disappearing from the taskbar organization flow.
- Switch to Hidden windows and restore the window.
- Create or select a group and show grouped hidden-window cards.
- Open Settings and switch between English and Russian.
- Open the tray menu and show Restore All Windows.

## Safety Notes

- Do not record private apps, credentials, chat windows, emails, or local paths.
- Do not use elevated/admin windows in public demos.
- Avoid rapid flashing animations or distracting cursor movement.
- Keep captions neutral and focused on productivity, workspace cleanup, and
  taskbar organization.
