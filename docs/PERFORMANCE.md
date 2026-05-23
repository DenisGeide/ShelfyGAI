# ShelfyGAI Performance Strategy

ShelfyGAI should feel quiet and lightweight while it manages ordinary Windows desktop
windows. The app avoids background work unless the user enables it or a safety feature
requires it.

## Window Scanning

- Open-window scanning runs on startup and when the user presses Refresh.
- Optional auto-refresh is intentionally low frequency and only runs while ShelfyGAI is
  visible on the Open windows page.
- Search filtering is debounced so typing in the search field does not repaint the table
  on every keystroke.
- Process metadata is cached briefly during native window inspection to avoid repeated
  `psutil` lookups during bursts of refreshes.

## Icons

- Icons are lazy-loaded from executable paths.
- The UI shows a fallback icon immediately and queues real icon extraction.
- Icons are cached by normalized executable path.
- Icon extraction is paced by a small timer so a large window list does not block the UI.
- Performance logs include cache size, pending loads, hits, misses, loaded icons, and
  failed icon loads.

## Watchers

- The prevent-minimize watcher only runs when at least one pinned window has
  prevent-minimize enabled.
- Overlay fullscreen detection only runs when overlay groups are enabled and at least one
  visible marker can be hidden during fullscreen.
- The fullscreen watcher remains active while markers are hidden by fullscreen so it can
  restore them when fullscreen ends.
- Timers use coarse timing where precise timing is not needed.

## UI Updates

- Tables keep a lightweight row signature. If a refresh returns the same visible data,
  ShelfyGAI skips rebuilding those rows.
- Icon updates are applied separately from table rebuilding.
- Empty states and selected-window details are updated after filtering and refreshes.

## Logging

Performance logs include:

- startup settings load, Qt build, main window build, and UI-ready time
- window refresh time with prune, enumeration, and populate timing
- icon cache hit/miss and load counters
- overlay marker count
- active watcher count

Timer paths should avoid repeated info-level logs. State-change logs are useful; repeated
unchanged timer ticks should stay silent or debug-level.

## Maintenance Notes

- Keep auto-refresh optional.
- Prefer event-driven updates after explicit user actions.
- Do not add polling unless the feature needs it for safety.
- If a new watcher is added, include it in active watcher performance logging.
- If a new table is added, use lazy icon loading and avoid rebuilding rows when the data
  did not change.
