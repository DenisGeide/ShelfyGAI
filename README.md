# ShelfyGAI

ShelfyGAI is an open-source Windows productivity utility for taskbar organization
and cleaner desktop workspaces. It lets you move selected application windows
into a local shelf so your taskbar and Alt+Tab view stay focused while the
applications continue running. You can restore individual windows, the latest
shelved window, or everything at once.

ShelfyGAI is local-first: no telemetry, no ads, no cloud sync, and no background
service installed without user action.

## English

### Project Description

ShelfyGAI is built for people who keep many applications open and want a calmer
Windows desktop. It organizes ordinary top-level application windows into a
reversible shelf, with groups, search, tray actions, startup preferences, safety
guardrails, and emergency recovery.

Supported platforms:

- Windows 10
- Windows 11

### Features

- Move selected open windows out of the Windows taskbar and Alt+Tab.
- Restore selected windows, the latest shelved window, or all managed windows.
- Pin selected windows so they stay above other windows, with optional
  minimize prevention.
- Group managed windows into folders, including the default Ungrouped group.
- Search open windows and managed windows.
- Show application icons extracted from executable files, with safe fallbacks.
- Use a modern dark PySide6 interface with sidebar navigation.
- Reopen Settings later and change theme, language, accent color, startup,
  tray, hotkey, and safety preferences.
- Switch language between English and Russian.
- Use optional system tray actions: Open ShelfyGAI, Restore All Windows,
  Settings, and Quit.
- Configure global hotkeys using Windows `RegisterHotKey`.
- Enable current-user Windows startup integration through the HKCU Run key.
- Keep settings, logs, and recovery state under `%APPDATA%\ShelfyGAI`.
- Use emergency recovery on next startup if a previous session ended while
  windows were still managed.

### Screenshots

Screenshots will be added as public preview builds stabilize. Placeholder paths
are reserved now so release notes, the README, and GitHub discussions can use a
consistent asset layout.

| View | Placeholder |
| --- | --- |
| Main window screenshot | `docs/assets/screenshots/main-window.png` |
| Settings screenshot | `docs/assets/screenshots/settings.png` |
| Managed windows screenshot | `docs/assets/screenshots/managed-windows.png` |
| Tray menu screenshot | `docs/assets/screenshots/tray-menu.png` |
| Language switch screenshot | `docs/assets/screenshots/language-switch.png` |

Recommended screenshot sizes:

- Main README screenshots: `1600x1000` or `1440x900`.
- Wide release preview crops: `1920x1080`.
- Tray menu screenshots: crop around the tray menu, usually `900x700` or
  smaller.

See [docs/assets/screenshots/README.md](docs/assets/screenshots/README.md) for
capture guidance.

### Demo Placeholder

Demo assets will live in `docs/assets/demo/`.

| Asset | Placeholder |
| --- | --- |
| Short demo GIF | `docs/assets/demo/shelfygai-demo.gif` |
| Optional source video | `docs/assets/demo/shelfygai-demo.mp4` |

Recommended demo GIF:

- 10 to 20 seconds.
- Capture ShelfyGAI at about `1280x800` or `1440x900`.
- Keep the GIF under roughly 10 MB when possible.
- Record MP4 first, then convert to GIF for README embedding.

Suggested demo scenarios:

- Search open windows, select one, and move it into ShelfyGAI.
- Show managed windows grouped into cards.
- Restore a selected managed window.
- Open Settings and switch language between English and Russian.
- Open the tray menu and show Restore All Windows.

See [docs/assets/demo/README.md](docs/assets/demo/README.md) for recording and
conversion notes.

### Installation

When releases are published, use the installer from the project releases page.
The installer:

- Installs ShelfyGAI to Program Files or a user-local app directory.
- Creates a Start Menu shortcut.
- Offers an optional desktop shortcut.
- Supports normal Windows uninstall.
- Does not enable autostart by default.
- Preserves `%APPDATA%\ShelfyGAI` across upgrades and uninstall/reinstall cycles.

You can also use the onedir package created by PyInstaller:

```text
dist\ShelfyGAI\ShelfyGAI.exe
```

### Running From Source

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m shelfygai
```

For development:

```powershell
python -m pip install -e ".[dev]"
python -m ruff check .
python -m pytest
```

### Building Executable

PyInstaller packaging creates a Windows onedir build:

```powershell
python -m pip install -e ".[build]"
.\scripts\build_exe.ps1 -Clean
```

Output:

```text
dist\ShelfyGAI\ShelfyGAI.exe
```

To verify the packaged application can start, load translations, load resources,
write settings, and write logs:

```powershell
.\scripts\build_exe.ps1 -Clean -SmokeTest
```

### Building Installer

Install Inno Setup 6, then run:

```powershell
.\scripts\build_installer.ps1
```

If the executable is already built:

```powershell
.\scripts\build_installer.ps1 -SkipExeBuild
```

Expected installer output:

```text
dist\installer\ShelfyGAI-Setup-0.1.0.exe
```

See [docs/PACKAGING.md](docs/PACKAGING.md) and
[installer/README_INSTALLER.md](installer/README_INSTALLER.md).

For the simplest public download, maintainers can also publish a small one-file
web installer:

```powershell
.\scripts\build_web_installer.ps1 `
  -DownloadUrl "https://github.com/shelfygai/shelfygai/releases/download/v0.1.0/ShelfyGAI-Setup-0.1.0.exe" `
  -DownloadSha256 "<64-character-sha256>"
```

Output:

```text
dist\installer\ShelfyGAI-WebSetup-0.1.0.exe
```

The web installer downloads the full offline installer from GitHub Releases and
then launches it. The offline installer remains available for users who need a
no-network install path.

### How It Works Technically

ShelfyGAI uses Windows APIs to enumerate user-facing top-level windows and to
adjust reversible extended window styles. When a window is moved into the shelf,
ShelfyGAI:

1. Enumerates top-level windows with WinAPI calls.
2. Filters out empty-title windows, system shell surfaces, Start Menu surfaces,
   protected system windows, ShelfyGAI itself, and other unsafe targets.
3. Reads the original extended style with `GetWindowLong`.
4. Stores the original style in memory and in local recovery state while needed.
5. Removes `WS_EX_APPWINDOW`.
6. Adds `WS_EX_TOOLWINDOW`.
7. Calls `SetWindowLong` and `SetWindowPos` with `SWP_FRAMECHANGED`.

Restoring a window writes the exact original extended style back and refreshes
the frame. If the target window has already closed, ShelfyGAI removes the stale
entry safely and continues.

Pinning uses `SetWindowPos(hwnd, HWND_TOPMOST, ...)` to keep selected windows
above normal windows. Unpinning restores the original topmost state. Optional
prevent-minimize mode removes `WS_MINIMIZEBOX` while pinned and can run a
lightweight watcher that restores pinned windows if they are minimized.

### Privacy

ShelfyGAI stores data locally:

- Settings: `%APPDATA%\ShelfyGAI\settings.json`
- Logs: `%APPDATA%\ShelfyGAI\logs\`
- Emergency recovery: `%APPDATA%\ShelfyGAI\recovery.json`

The app does not collect analytics, does not transmit usage data, does not sync
window information to a server, and does not include cloud features. See
[docs/PRIVACY.md](docs/PRIVACY.md).

### Safety

ShelfyGAI is designed to keep the desktop recoverable:

- It refuses to manage its own windows.
- It refuses Windows taskbar shell windows.
- It refuses Start Menu surfaces.
- It refuses critical system windows.
- It warns when a target appears to require administrator elevation from a
  non-elevated ShelfyGAI process.
- It warns when an application may not support taskbar style changes.
- It restores managed windows on normal exit by default.
- It restores pinned window styles on normal exit by default.
- It writes local emergency recovery state and presents a recovery screen on the
  next startup when needed.

The Safety page in the app explains what ShelfyGAI can do, what it cannot do,
why some windows cannot be managed, and how to restore windows safely.

### Known Limitations

- Window handles are only meaningful during the current Windows boot.
- Some applications use custom window frameworks that may not behave like
  standard taskbar applications.
- Windows permission boundaries can prevent a non-elevated ShelfyGAI process
  from managing elevated applications.
- Some applications may ignore always-on-top or minimize-box style changes.
- Global hotkeys can conflict with shortcuts already registered by other apps.
- Installer artifacts are not signed yet.
- The update check is currently an offline-safe placeholder.

### Roadmap

- Signed release artifacts.
- Polished screenshots and release assets.
- More group management refinements.
- Optional richer restore history.
- Future GitHub Releases update checks with explicit user action.
- Broader manual testing across Windows 10 and Windows 11 configurations.

### Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before
opening a pull request.

Project expectations:

- Keep ShelfyGAI local-first.
- Do not add telemetry, advertising, cloud sync, or surprise background services.
- Keep Windows-specific behavior isolated behind platform adapters.
- Add focused tests for settings, shelf behavior, recovery, and Windows API
  safety logic.
- Treat restore and recovery behavior as high-risk code.

### License

ShelfyGAI is released under the MIT License. See [LICENSE](LICENSE).

## Русский

### Описание проекта

ShelfyGAI - это утилита с открытым исходным кодом для продуктивной работы и
организации панели задач Windows. Она помогает перемещать выбранные окна
приложений в локальную полку, чтобы панель задач и Alt+Tab оставались аккуратнее,
а сами приложения продолжали работать. В любой момент можно вернуть отдельное
окно, последнее окно из полки или все управляемые окна сразу.

ShelfyGAI работает локально: без телеметрии, рекламы, облачной синхронизации и
фоновой службы без явного действия пользователя.

Поддерживаемые платформы:

- Windows 10
- Windows 11

### Возможности

- Перемещение выбранных окон из панели задач Windows и Alt+Tab в локальную
  полку.
- Восстановление выбранных окон, последнего окна из полки или всех управляемых
  окон.
- Закрепление выбранных окон поверх остальных с дополнительной защитой от
  случайного сворачивания.
- Группы и папки для управляемых окон, включая группу Без группы.
- Поиск по открытым и управляемым окнам.
- Значки приложений из исполняемых файлов с безопасной заменой при ошибках.
- Современный темный интерфейс PySide6 с боковой навигацией.
- Настройки темы, языка, акцентного цвета, автозапуска, трея, горячих клавиш и
  безопасности.
- Переключение языка между English и Русский.
- Действия в системном трее: открыть ShelfyGAI, восстановить все окна,
  настройки и выход.
- Настраиваемые глобальные горячие клавиши через Windows `RegisterHotKey`.
- Автозапуск для текущего пользователя через ключ HKCU Run.
- Локальные настройки, журналы и файл восстановления в `%APPDATA%\ShelfyGAI`.
- Аварийное восстановление при следующем запуске, если предыдущий сеанс
  завершился с управляемыми окнами.

### Скриншоты

Скриншоты будут добавлены после стабилизации публичных preview-сборок.

| Экран | Заглушка |
| --- | --- |
| Главное окно | `docs/assets/screenshots/main-window.png` |
| Настройки | `docs/assets/screenshots/settings.png` |
| Управляемые окна | `docs/assets/screenshots/managed-windows.png` |
| Меню трея | `docs/assets/screenshots/tray-menu.png` |
| Переключение языка | `docs/assets/screenshots/language-switch.png` |

### Установка

После публикации релизов используйте установщик со страницы Releases проекта.
Установщик:

- Устанавливает ShelfyGAI в Program Files или пользовательский каталог.
- Создает ярлык в меню Пуск.
- Предлагает необязательный ярлык на рабочем столе.
- Поддерживает обычное удаление через Windows.
- Не включает автозапуск по умолчанию.
- Сохраняет `%APPDATA%\ShelfyGAI` при обновлениях и повторной установке.

Также можно использовать onedir-сборку PyInstaller:

```text
dist\ShelfyGAI\ShelfyGAI.exe
```

### Запуск из исходного кода

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m shelfygai
```

Для разработки:

```powershell
python -m pip install -e ".[dev]"
python -m ruff check .
python -m pytest
```

### Сборка исполняемого файла

PyInstaller создает onedir-сборку для Windows:

```powershell
python -m pip install -e ".[build]"
.\scripts\build_exe.ps1 -Clean
```

Результат:

```text
dist\ShelfyGAI\ShelfyGAI.exe
```

Проверка packaged-сборки:

```powershell
.\scripts\build_exe.ps1 -Clean -SmokeTest
```

Эта проверка запускает собранное приложение и проверяет загрузку переводов,
ресурсов, запись настроек и запись журналов.

### Сборка установщика

Установите Inno Setup 6 и выполните:

```powershell
.\scripts\build_installer.ps1
```

Если исполняемый файл уже собран:

```powershell
.\scripts\build_installer.ps1 -SkipExeBuild
```

Ожидаемый результат:

```text
dist\installer\ShelfyGAI-Setup-0.1.0.exe
```

Подробнее: [docs/PACKAGING.md](docs/PACKAGING.md) и
[installer/README_INSTALLER.md](installer/README_INSTALLER.md).

Для самого простого публичного сценария сопровождающие также могут опубликовать
маленький web-installer в один файл:

```powershell
.\scripts\build_web_installer.ps1 `
  -DownloadUrl "https://github.com/shelfygai/shelfygai/releases/download/v0.1.0/ShelfyGAI-Setup-0.1.0.exe" `
  -DownloadSha256 "<64-character-sha256>"
```

Результат:

```text
dist\installer\ShelfyGAI-WebSetup-0.1.0.exe
```

Он скачивает полный офлайн-инсталлятор из GitHub Releases и запускает его.
Офлайн-инсталлятор остается доступным для пользователей, которым нужна установка
без сети.

### Как это работает технически

ShelfyGAI использует Windows API для перечисления верхнеуровневых окон и
обратимого изменения расширенных стилей окна. Когда окно перемещается в полку,
ShelfyGAI:

1. Перечисляет верхнеуровневые окна через WinAPI.
2. Исключает окна без заголовка, поверхности системной оболочки, меню Пуск,
   защищенные системные окна, собственные окна ShelfyGAI и другие небезопасные
   цели.
3. Читает исходный расширенный стиль через `GetWindowLong`.
4. Сохраняет исходный стиль в памяти и во временном локальном состоянии
   восстановления.
5. Убирает `WS_EX_APPWINDOW`.
6. Добавляет `WS_EX_TOOLWINDOW`.
7. Вызывает `SetWindowLong` и `SetWindowPos` с `SWP_FRAMECHANGED`.

При восстановлении ShelfyGAI записывает точный исходный расширенный стиль
обратно и обновляет рамку окна. Если окно уже закрыто, устаревшая запись
безопасно удаляется.

Закрепление использует `SetWindowPos(hwnd, HWND_TOPMOST, ...)`, чтобы выбранные
окна оставались поверх обычных окон. При откреплении восстанавливается исходное
состояние поверх остальных. Дополнительный режим запрета сворачивания временно
убирает `WS_MINIMIZEBOX`, а легкий наблюдатель может восстановить закрепленное
окно, если оно было свернуто.

### Приватность

ShelfyGAI хранит данные локально:

- Настройки: `%APPDATA%\ShelfyGAI\settings.json`
- Журналы: `%APPDATA%\ShelfyGAI\logs\`
- Аварийное восстановление: `%APPDATA%\ShelfyGAI\recovery.json`

Приложение не собирает аналитику, не отправляет данные об использовании, не
синхронизирует сведения об окнах с сервером и не содержит облачных функций.
Подробнее: [docs/PRIVACY.md](docs/PRIVACY.md).

### Безопасность

ShelfyGAI спроектирован так, чтобы рабочий стол оставался восстановимым:

- Не управляет собственными окнами.
- Не управляет окнами панели задач и системной оболочки Windows.
- Не управляет поверхностями меню Пуск.
- Не управляет критическими системными окнами.
- Предупреждает, если цель требует прав администратора, а ShelfyGAI запущен без
  повышения прав.
- Предупреждает, если приложение может не поддерживать изменение стилей панели
  задач.
- По умолчанию восстанавливает управляемые окна при штатном выходе.
- По умолчанию восстанавливает стили закрепленных окон при штатном выходе.
- Сохраняет локальное состояние аварийного восстановления и показывает экран
  восстановления при следующем запуске, если это необходимо.

Страница Безопасность в приложении объясняет, что ShelfyGAI может делать, чего
не делает, почему некоторые окна нельзя взять в управление и как безопасно
вернуть окна обратно.

### Известные ограничения

- Дескрипторы окон имеют смысл только в рамках текущей загрузки Windows.
- Некоторые приложения используют нестандартные оконные фреймворки и могут
  отличаться от обычных приложений панели задач.
- Ограничения прав Windows могут мешать управлять приложениями с повышенными
  правами из обычного процесса ShelfyGAI.
- Некоторые приложения могут игнорировать режим поверх остальных окон или
  изменение кнопки сворачивания.
- Глобальные горячие клавиши могут конфликтовать с сочетаниями, уже занятыми
  другими приложениями.
- Релизные артефакты пока не подписаны.
- Проверка обновлений пока является локальной заготовкой.

### Дорожная карта

- Подписанные релизные артефакты.
- Скриншоты и материалы для релизов.
- Улучшения управления группами.
- Дополнительная история восстановления.
- Будущая проверка GitHub Releases только по явному действию пользователя.
- Расширенное ручное тестирование на Windows 10 и Windows 11.

### Участие в разработке

Вклады приветствуются. Перед pull request прочитайте
[CONTRIBUTING.md](CONTRIBUTING.md).

Ожидания проекта:

- Сохранять локальный подход.
- Не добавлять телеметрию, рекламу, облачную синхронизацию или неожиданные
  фоновые службы.
- Изолировать Windows-специфичное поведение за платформенными адаптерами.
- Добавлять целевые тесты для настроек, полки, восстановления и безопасной
  работы с Windows API.
- Считать код восстановления окон зоной повышенного внимания.

### Лицензия

ShelfyGAI распространяется по лицензии MIT. См. [LICENSE](LICENSE).
