# ShelfyGAI v0.1.0-alpha Release Notes

## English

ShelfyGAI v0.1.0-alpha is the first public alpha of a simple Windows window
organizer. It helps users hide selected windows, reduce taskbar and
Alt+Tab clutter, pin important windows above others, and restore everything
safely.

### Highlights

- Hide windows.
- Restore hidden windows.
- Pin and unpin windows.
- Organize windows with groups.
- Optionally show a ShelfyGAI-owned group window as one taskbar item.
- Use English or Russian interface text.
- Configure local settings.
- Use tray actions for opening ShelfyGAI, restoring windows, settings, and quit.
- Install with the offline `ShelfyGAI-Setup-v0.1.0.exe` installer.

### Safety Notes

- ShelfyGAI stores settings, logs, and recovery data locally.
- ShelfyGAI avoids managing its own windows, Windows shell surfaces, Start Menu
  surfaces, and critical system windows.
- Pinning is designed to be reversible. ShelfyGAI unpins currently pinned
  windows on exit by default so windows should not remain always-on-top.
- Restore cleanup and stale HWND handling were improved for safer alpha testing.

### Known Limitations

- Tray icon hiding is limited and may not be supported for third-party apps.
- Some apps recreate windows and may reappear in the taskbar or Alt+Tab.
- Elevated windows may require running ShelfyGAI as administrator.
- Native Windows taskbar folders are not supported because they require unsafe
  shell-level modifications.
- ShelfyGAI group taskbar windows are safe app-owned windows, not native Windows
  taskbar folders.
- Alpha builds may be unsigned, so Windows SmartScreen may show a warning.

### How To Report Bugs

Please report bugs through GitHub Issues. Helpful reports include:

- Windows version.
- Whether ShelfyGAI was run from source, packaged app folder, or installer.
- Steps to reproduce.
- Expected and actual behavior.
- Logs from `%APPDATA%\ShelfyGAI\logs\`, with private data removed if needed.
- Screenshots or a short screen recording when useful.

## Русский

ShelfyGAI v0.1.0-alpha - первая публичная alpha-версия простой утилиты для
организации окон в Windows. Она помогает скрывать выбранные окна,
уменьшать clutter на панели задач и в Alt+Tab, закреплять важные окна поверх
остальных и безопасно возвращать окна обратно.

### Главное

- Скрытие окон.
- Возврат скрытых окон.
- Закрепление и открепление окон.
- Организация окон через группы.
- Необязательное окно группы ShelfyGAI как один элемент панели задач.
- Интерфейс на английском и русском языках.
- Локальные настройки.
- Действия в трее: открыть ShelfyGAI, вернуть окна, настройки и выход.
- Установка через офлайн-инсталлятор `ShelfyGAI-Setup-v0.1.0.exe`.

### Безопасность

- ShelfyGAI хранит настройки, журналы и recovery-данные локально.
- ShelfyGAI избегает собственных окон, поверхностей оболочки Windows, меню Пуск
  и критических системных окон.
- Закрепление спроектировано обратимым. По умолчанию при выходе ShelfyGAI
  открепляет текущие закрепленные окна, чтобы они не оставались поверх
  остальных.
- Улучшены cleanup при возврате окон и обработка устаревших HWND.

### Известные ограничения

- Скрытие значков трея ограничено и может не поддерживаться для сторонних
  приложений.
- Некоторые приложения пересоздают окна и могут снова появляться на панели задач
  или в Alt+Tab.
- Для окон с повышенными правами может потребоваться запуск ShelfyGAI от имени
  администратора.
- Нативные папки панели задач Windows не поддерживаются, потому что требуют
  небезопасных изменений на уровне оболочки.
- Окна групп ShelfyGAI на панели задач - это безопасные окна самого приложения,
  а не нативные папки панели задач Windows.
- Alpha-сборки могут быть неподписанными, поэтому Windows SmartScreen может
  показать предупреждение.

### Как сообщать об ошибках

Сообщайте об ошибках через GitHub Issues. Полезно приложить:

- версию Windows
- способ запуска: из исходников, packaged app folder или installer
- шаги для воспроизведения
- ожидаемое и фактическое поведение
- логи из `%APPDATA%\ShelfyGAI\logs\`, предварительно удалив приватные данные
- скриншоты или короткую запись экрана, если они помогают понять проблему
