# Cleaner

Компактная утилита очистки Windows на базе **CCleaner64.exe**: реестр от мусора,
файлы куки, трекеры и другие следы присутствия в сети. Один файл на чистом
Python (stdlib, без зависимостей) + готовый конфиг для CCleaner.

## Состав

| Файл | Назначение |
|---|---|
| `cleaner.py` | Основная утилита (CLI + `--gui`). Работает и без CCleaner |
| `ccleaner.ini` | Портативный конфиг для `CCleaner64.exe /AUTO` (реестр + куки + мусор) |
| `Cleaner.bat` | Лаунчер для Windows: права админа → CCleaner → `cleaner.py` |
| `Clean.ps1` | То же через PowerShell (`-DryRun -Cookies -Network` и т.д.) |
| `backup/` | Сюда пишутся `.reg`-бэкапы реестра (создаётся при очистке, в .gitignore) |

## Быстрый старт (Windows)

1. Положите портативный `CCleaner64.exe` рядом с `cleaner.py`
   (или установите CCleaner в `C:\Program Files\CCleaner`) — он нужен для
   **глубокой** чистки реестра. Без него утилита чистит встроенными средствами.
2. Предпросмотр (ничего не удаляется):

   ```bat
   python cleaner.py --dry-run --all
   ```

3. Полная очистка:

   ```bat
   Cleaner.bat --all
   :: или
   python cleaner.py --all
   python cleaner.py --gui        :: простой графический интерфейс
   ```

## Что чистится

- **Реестр** — CCleaner (`/AUTO`, все проверки из `ccleaner.ini`: ActiveX, битые DLL,
  несуществующие пути, MUI Cache…) + встроенно: только безопасные MRU-ветки
  `HKCU` (RunMRU, RecentDocs, TypedURLs, ComDlg32, MuiCache). Перед встроенной
  очисткой ветки экспортируются в `backup/<дата>/*.reg` — откат двойным кликом.
- **Куки и трекеры** — Chrome, Edge, Brave, Yandex, Opera, Firefox:
  `Cookies`, `Network\Cookies`, `cookies.sqlite`, `Cache`, `Code Cache`,
  `GPUCache`, `Local/Session Storage`, `IndexedDB`, `Service Worker`.
  **Пароли (`Login Data`) не трогаются.** Браузеры перед очисткой закрыть.
- **Следы в сети/системе** — сброс DNS-кэша (`ipconfig /flushdns`), `Recent`,
  буфер обмена, Temp пользователя и Windows, кэш эскизов/иконок, корзина.

## Флаги

```
--all            всё сразу (CCleaner + реестр + браузеры + temp + сеть + корзина)
--registry       только реестр          --cookies   только куки/трекеры/кэш
--temp           только временные файлы --network   только DNS/Recent/буфер
--history        + история посещений    --recycle   + корзина
--dry-run        только показать план   --yes       без подтверждения
--no-ccleaner    не запускать CCleaner  --ccleaner PATH   путь к CCleaner64.exe
--gui            графический интерфейс
```

Примеры: `python cleaner.py --cookies --network --dry-run` ·
`python cleaner.py --registry --no-ccleaner -y`

## Безопасность

Начинайте с `--dry-run`. Реестр без бэкапа не чистится: CCleaner предлагает свой
`.reg`-бэкап, `cleaner.py` — свой в `backup/`. Занятые запущенным браузером
файлы пропускаются с пометкой, а не падают с ошибкой.

> Утилита рассчитана на Windows 10/11. На Linux/macOS доступен `--dry-run`
> для проверки плана очистки.
