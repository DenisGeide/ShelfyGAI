# ShelfyGAI

<p align="center">
  <a href="https://github.com/DenisGeide/ShelfyGAI/releases/latest/download/ShelfyGAI-Setup-v0.1.0.exe">
    <img alt="Download ShelfyGAI for Windows" src="https://img.shields.io/badge/Download%20for%20Windows-ShelfyGAI--Setup--v0.1.0.exe-2f81f7?style=for-the-badge&logo=windows">
  </a>
</p>

<p align="center">
  <strong>One Windows installer. No Python, pip, or Git required.</strong><br>
  <a href="https://github.com/DenisGeide/ShelfyGAI/releases/latest/download/ShelfyGAI-Setup-v0.1.0.exe">Direct download: ShelfyGAI-Setup-v0.1.0.exe</a>
</p>

ShelfyGAI is a simple open-source Windows window organizer. It helps you move
selected application windows to a Shelf, keep important windows above others,
and reduce taskbar clutter without closing your apps.

ShelfyGAI is local-first: settings and logs stay on your computer. There is no
telemetry, advertising, account system, cloud sync, or background service
installed without user action.

## Screenshots

Screenshots should be updated before every public release. The paths below are
reserved for release assets. The current UI is organized into Open windows,
Shelf, Pinned, Groups, Settings, and About.

**Main window - Open windows**

![Main window - Open windows](docs/assets/screenshots/01-main-open-windows.png)

**Shelf page**

![Shelf page](docs/assets/screenshots/02-shelf.png)

**Pinned windows page**

![Pinned windows page](docs/assets/screenshots/03-pinned.png)

**Groups page**

![Groups page](docs/assets/screenshots/04-groups.png)

**Group taskbar window**

![Group taskbar window](docs/assets/screenshots/05-taskbar-group-window.png)

**Settings page**

![Settings page](docs/assets/screenshots/06-settings.png)

**Tray menu**

![Tray menu](docs/assets/screenshots/07-tray-menu.png)

**EN/RU language switch**

![EN/RU language switch](docs/assets/screenshots/08-language-switch.png)

**Installer**

![Installer](docs/assets/screenshots/09-installer.png)

Screenshot planning notes are in
[docs/assets/screenshots/README.md](docs/assets/screenshots/README.md).

## Features

- Move selected windows to the Shelf.
- Hide shelved windows from the Windows taskbar.
- Hide shelved windows from Alt+Tab when supported by the target window.
- Restore one window, the last shelved window, or everything safely.
- Pin windows above other windows.
- Create groups to organize shelved windows.
- Optionally show a ShelfyGAI-owned group window as one Windows taskbar item.
- Use English or Russian interface text.
- Save settings locally under `%APPDATA%\ShelfyGAI`.
- Keep logs locally under `%APPDATA%\ShelfyGAI\logs`.

## Installation

For normal users, the recommended public alpha download is one offline installer:

```text
ShelfyGAI-Setup-v0.1.0.exe
```

Download it from GitHub Releases, run it, and open ShelfyGAI from the Start
Menu. You do not need Python, pip, Git, or source code.

The installer:

- creates a Start Menu shortcut
- creates a desktop shortcut by default
- adds a normal Windows uninstaller
- does not enable launch with Windows by default
- keeps user settings in `%APPDATA%\ShelfyGAI`

See [docs/INSTALL_FOR_USERS.md](docs/INSTALL_FOR_USERS.md) for the short user
install guide.

## Run From Source

Requirements:

- Windows 10 or Windows 11
- Python 3.11 or newer

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m shelfygai
```

For development checks:

```powershell
python -m pip install -e ".[dev]"
python -m ruff check .
python -m pytest
```

## Build

Build the standalone app folder:

```powershell
python -m pip install -e ".[build]"
.\scripts\build_exe.ps1 -Clean
```

Expected output:

```text
dist\ShelfyGAI\ShelfyGAI.exe
```

Build the Windows installer with Inno Setup:

```powershell
.\scripts\build_installer.ps1 -SkipExeBuild
```

Expected output:

```text
dist\installer\ShelfyGAI-Setup-v0.1.0.exe
```

Maintainer build notes are in [docs/BUILD_RELEASE.md](docs/BUILD_RELEASE.md),
[docs/BUILD.md](docs/BUILD.md), and [docs/INSTALLER.md](docs/INSTALLER.md).

## How It Works

ShelfyGAI enumerates normal top-level Windows application windows and lets the
user choose what to do with a selected window.

When a window is moved to the Shelf, ShelfyGAI stores the original window style
and applies reversible Windows extended-style changes. It can remove
`WS_EX_APPWINDOW` for taskbar visibility and add `WS_EX_TOOLWINDOW` for Alt+Tab
visibility. On restore, ShelfyGAI writes the original style back.

Pinning uses `SetWindowPos(hwnd, HWND_TOPMOST, ...)`. Unpinning uses
`HWND_NOTOPMOST`, and ShelfyGAI cleans up pinned windows on exit by default.

Groups are managed inside ShelfyGAI. Optional group taskbar windows are normal
ShelfyGAI-owned windows that represent a group safely without modifying the
Windows shell.

## Safety

ShelfyGAI is designed to keep windows recoverable:

- it does not close target apps when moving windows to the Shelf
- it avoids managing its own windows
- it avoids Windows taskbar shell windows and Start Menu surfaces
- it stores recovery state while windows are managed
- it can restore managed windows on normal exit
- it ignores stale window handles after a restart

If something looks wrong, open ShelfyGAI and use Restore all.

## Limitations

- Tray icon hiding is limited and may not be supported for third-party apps.
- Some apps recreate windows and may reappear in the taskbar or Alt+Tab.
- Admin or elevated windows may require running ShelfyGAI as administrator.
- Native Windows taskbar folders are not implemented because they require unsafe
  shell-level modifications.
- ShelfyGAI group taskbar windows are safe app-owned windows, not native Windows
  taskbar folders.
- Some apps use custom window frameworks and may not respond to standard Windows
  style changes.
- Window handles are valid only for the current Windows session.
- Alpha builds may be unsigned, so Windows SmartScreen may show a warning.

## Privacy

ShelfyGAI stores data locally:

- settings: `%APPDATA%\ShelfyGAI\settings.json`
- logs: `%APPDATA%\ShelfyGAI\logs\`
- recovery state: `%APPDATA%\ShelfyGAI\recovery.json`

The app does not collect analytics, sync data, or require an account. See
[docs/PRIVACY.md](docs/PRIVACY.md).

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for the current public alpha roadmap.

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before
opening a pull request.

Project expectations:

- keep ShelfyGAI simple and local-first
- keep window restore and recovery behavior safe
- avoid surprise background behavior
- keep Windows-specific code isolated behind platform adapters
- add tests for settings, shelf behavior, pinning, recovery, and guardrails

## License

ShelfyGAI is released under the MIT License. See [LICENSE](LICENSE).

---

# ShelfyGAI на русском

ShelfyGAI - простая open-source утилита для организации окон в Windows. Она
помогает переносить выбранные окна на Полку, закреплять важные окна поверх
остальных и очищать панель задач, не закрывая приложения.

ShelfyGAI работает локально: настройки и журналы остаются на вашем компьютере.
В приложении нет телеметрии, рекламы, аккаунтов, облачной синхронизации и
фоновой службы без действия пользователя.

## Скриншоты

Скриншоты нужно обновлять перед каждым публичным релизом. Пути ниже
зарезервированы для релизных материалов. Текущий интерфейс разделен на
Открытые окна, Полку, Закрепленные, Группы, Настройки и О программе.

**Главное окно - открытые окна**

![Главное окно - открытые окна](docs/assets/screenshots/01-main-open-windows.png)

**Полка**

![Полка](docs/assets/screenshots/02-shelf.png)

**Закрепленные окна**

![Закрепленные окна](docs/assets/screenshots/03-pinned.png)

**Группы**

![Группы](docs/assets/screenshots/04-groups.png)

**Окно группы на панели задач**

![Окно группы на панели задач](docs/assets/screenshots/05-taskbar-group-window.png)

**Настройки**

![Настройки](docs/assets/screenshots/06-settings.png)

**Меню трея**

![Меню трея](docs/assets/screenshots/07-tray-menu.png)

**Переключение языка EN/RU**

![Переключение языка EN/RU](docs/assets/screenshots/08-language-switch.png)

**Установщик**

![Установщик](docs/assets/screenshots/09-installer.png)

План скриншотов находится в
[docs/assets/screenshots/README.md](docs/assets/screenshots/README.md).

## Возможности

- Перемещение выбранных окон на Полку.
- Скрытие окон на Полке с панели задач Windows.
- Скрытие окон на Полке из Alt+Tab, если целевое окно это поддерживает.
- Безопасный возврат одного окна, последнего окна или всех окон сразу.
- Закрепление окон поверх остальных.
- Создание групп для окон на Полке.
- Необязательное окно группы ShelfyGAI как один элемент панели задач Windows.
- Интерфейс на английском и русском языках.
- Локальные настройки в `%APPDATA%\ShelfyGAI`.
- Локальные журналы в `%APPDATA%\ShelfyGAI\logs`.

## Установка

Для обычных пользователей рекомендуемый public alpha файл - один офлайн
установщик:

```text
ShelfyGAI-Setup-v0.1.0.exe
```

Скачайте его со страницы GitHub Releases, запустите и откройте ShelfyGAI из
меню Пуск. Python, pip, Git и исходный код не нужны.

Установщик:

- создает ярлык в меню Пуск
- создает ярлык на рабочем столе по умолчанию
- добавляет обычное удаление через Windows
- не включает автозапуск по умолчанию
- хранит пользовательские настройки в `%APPDATA%\ShelfyGAI`

Короткая инструкция: [docs/INSTALL_FOR_USERS.md](docs/INSTALL_FOR_USERS.md).

## Запуск из исходников

Требования:

- Windows 10 или Windows 11
- Python 3.11 или новее

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m shelfygai
```

Проверки для разработки:

```powershell
python -m pip install -e ".[dev]"
python -m ruff check .
python -m pytest
```

## Сборка

Сборка standalone-папки приложения:

```powershell
python -m pip install -e ".[build]"
.\scripts\build_exe.ps1 -Clean
```

Ожидаемый результат:

```text
dist\ShelfyGAI\ShelfyGAI.exe
```

Сборка Windows-установщика через Inno Setup:

```powershell
.\scripts\build_installer.ps1 -SkipExeBuild
```

Ожидаемый результат:

```text
dist\installer\ShelfyGAI-Setup-v0.1.0.exe
```

Документация для мейнтейнеров:
[docs/BUILD_RELEASE.md](docs/BUILD_RELEASE.md),
[docs/BUILD.md](docs/BUILD.md) и [docs/INSTALLER.md](docs/INSTALLER.md).

## Как это работает

ShelfyGAI находит обычные верхнеуровневые окна приложений Windows и позволяет
пользователю выбрать действие для конкретного окна.

Когда окно переносится на Полку, ShelfyGAI сохраняет исходный стиль окна и
применяет обратимые изменения расширенных стилей Windows. Приложение может
убрать `WS_EX_APPWINDOW` для панели задач и добавить `WS_EX_TOOLWINDOW` для
Alt+Tab. При возврате ShelfyGAI записывает исходный стиль обратно.

Закрепление использует `SetWindowPos(hwnd, HWND_TOPMOST, ...)`. Открепление
использует `HWND_NOTOPMOST`, а при выходе ShelfyGAI по умолчанию очищает
закрепленные окна.

Группы управляются внутри ShelfyGAI. Необязательные окна групп на панели задач -
это обычные окна, принадлежащие ShelfyGAI. Они безопасно представляют группу и
не изменяют оболочку Windows.

## Безопасность

ShelfyGAI спроектирован так, чтобы окна можно было вернуть:

- приложение не закрывает целевые программы при переносе окон на Полку
- оно не управляет собственными окнами
- оно избегает окон панели задач Windows и поверхностей меню Пуск
- оно хранит состояние восстановления, пока окна находятся в управлении
- оно может вернуть управляемые окна при штатном выходе
- оно игнорирует устаревшие дескрипторы окон после перезапуска Windows

Если что-то выглядит неправильно, откройте ShelfyGAI и используйте Вернуть все.

## Ограничения

- Скрытие значков трея ограничено и может не поддерживаться для сторонних
  приложений.
- Некоторые приложения пересоздают окна, поэтому они могут снова появиться на
  панели задач или в Alt+Tab.
- Для окон с правами администратора может потребоваться запуск ShelfyGAI от
  имени администратора.
- Нативные папки панели задач Windows не реализованы, потому что требуют
  небезопасных изменений на уровне оболочки.
- Окна групп ShelfyGAI на панели задач - это безопасные окна самого приложения,
  а не нативные папки панели задач Windows.
- Некоторые приложения используют нестандартные оконные фреймворки и могут не
  реагировать на стандартные изменения стилей Windows.
- Дескрипторы окон действительны только в текущем сеансе Windows.
- Alpha-сборки могут быть неподписанными, поэтому Windows SmartScreen может
  показать предупреждение.

## Приватность

ShelfyGAI хранит данные локально:

- настройки: `%APPDATA%\ShelfyGAI\settings.json`
- журналы: `%APPDATA%\ShelfyGAI\logs\`
- состояние восстановления: `%APPDATA%\ShelfyGAI\recovery.json`

Приложение не собирает аналитику, не синхронизирует данные и не требует аккаунт.
Подробнее: [docs/PRIVACY.md](docs/PRIVACY.md).

## Планы

Текущая дорожная карта public alpha находится в
[docs/ROADMAP.md](docs/ROADMAP.md).

## Участие в разработке

Вклады приветствуются. Перед pull request прочитайте
[CONTRIBUTING.md](CONTRIBUTING.md).

Ожидания проекта:

- сохранять ShelfyGAI простым и локальным
- бережно относиться к восстановлению окон
- избегать неожиданного фонового поведения
- изолировать Windows-specific код за платформенными адаптерами
- добавлять тесты для настроек, Полки, закрепления, восстановления и guardrails

## Лицензия

ShelfyGAI распространяется по лицензии MIT. См. [LICENSE](LICENSE).
