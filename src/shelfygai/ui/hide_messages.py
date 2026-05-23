from __future__ import annotations

from shelfygai.core.models import HideOptions
from shelfygai.i18n import tr

_CONFIRMATION_KEYS = {
    (True, False, False): "dialog.hide_windows.confirm.taskbar",
    (False, True, False): "dialog.hide_windows.confirm.alt_tab",
    (False, False, True): "dialog.hide_windows.confirm.tray",
    (True, True, False): "dialog.hide_windows.confirm.taskbar_alt_tab",
    (True, False, True): "dialog.hide_windows.confirm.taskbar_tray",
    (False, True, True): "dialog.hide_windows.confirm.alt_tab_tray",
    (True, True, True): "dialog.hide_windows.confirm.taskbar_alt_tab_tray",
}


def hide_confirmation_message(count: int, options: HideOptions) -> str:
    if not options.has_any_target:
        return tr("error.hide_options_empty")

    key = _CONFIRMATION_KEYS[
        (options.hide_taskbar, options.hide_alt_tab, options.hide_tray)
    ]
    plural_key = "one" if count == 1 else "many"
    message = tr(f"{key}.{plural_key}", count=count)
    limitation = hide_limitation_message(options)
    if limitation:
        return f"{message}\n\n{limitation}"
    return message


def hide_limitation_message(options: HideOptions) -> str:
    limitations: list[str] = []
    if options.hide_taskbar and not options.hide_alt_tab:
        limitations.append(tr("dialog.hide_windows.limitation_taskbar_only"))
    if options.hide_alt_tab and not options.hide_taskbar:
        limitations.append(tr("dialog.hide_windows.limitation_alt_tab_only"))
    if options.hide_tray:
        limitations.append(tr("dialog.hide_windows.limitation_tray"))
    return "\n\n".join(limitations)
