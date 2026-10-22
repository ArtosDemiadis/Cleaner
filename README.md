# Cleaner

Компактная утилита очистки Windows на базе **CCleaner64.exe**: реестр от мусора,
файлы куки, трекеры и другие следы присутствия в сети. Запуск — **двойным
кликом по `Cleaner.exe`** (Python не нужен), внутри — чистый Python (stdlib).

## Состав

| Файл | Назначение |
|---|---|
| **`Cleaner.exe`** | **Главный запуск: двойной клик → GUI**. Скачать: [Releases](https://github.com/ArtosDemiadis/Cleaner/releases) / `Cleaner-exe.zip` |
| `cleaner.py` | Исходник утилиты (CLI + `--gui`). Работает и без CCleaner |
| `ccleaner.ini` | Портативный конфиг для `CCleaner64.exe /AUTO` (реестр + куки + мусор) |
| `build_exe.bat` | Самостоятельная пересборка `Cleaner.exe` на Windows (PyInstaller) |
| `Cleaner.bat` / `Clean.ps1` | Лаунчеры без .exe: права админа → CCleaner → `cleaner.py` |
| `.github/workflows/build-exe.yml` | Автосборка `Cleaner.exe` на Windows-раннере GitHub Actions |
| `backup/` | Сюда пишутся `.reg`-бэкапы реестра (создаётся при очистке, в .gitignore) |

## Быстрый старт (Windows) — через .exe

1. Скачайте **`Cleaner.exe`** из
   [Releases](https://github.com/ArtosDemiadis/Cleaner/releases/download/v1.0.2/Cleaner.exe)
   (или весь архив `Cleaner-exe.zip`) и положите рядом `ccleaner.ini`.
2. **Двойной клик по `Cleaner.exe`** → откроется окно, по умолчанию включён
   Dry-run — сначала «Очистить» (для полной очистки системных папок — правый
   клик → «Запуск от имени администратора»),
   покажет план, затем снимите галочку Dry-run для реальной очистки.
3. Опционально: портативный `CCleaner64.exe` рядом с `Cleaner.exe`
   (или установленный в `C:\Program Files\CCleaner`) — для **глубокой**
   чистки реестра. Без него утилита чистит встроенными средствами.

Из консоли `.exe` принимает те же флаги, что и скрипт:

```bat
Cleaner.exe --dry-run --all
Cleaner.exe --all
Cleaner.exe --cookies --network
```

### Проверка локации / страны — отключение (`--no-geo`)

В самом `Cleaner.exe` **определителя локации и запретов по странам нет**:
он не делает сетевых обращений и не определяет страну (проверяется по
открытому исходнику `cleaner.py`). Единственный компонент, где теоретически
может быть своя проверка страны, — внешний проприетарный `CCleaner64.exe`,
который `Cleaner.exe` запускает только если находит рядом. Отключается при запуске:

```bat
Cleaner.exe --no-geo                    :: GUI с отключённой проверкой (ярлык с этим флагом)
Cleaner.exe --no-geo --dry-run --all    :: CLI: план очистки без CCleaner64.exe
Cleaner.exe --no-geo --all              :: CLI: полная очистка встроенными средствами
set CLEANER_NO_GEO=1                    :: то же для двойного клика без ярлыка
```

В GUI это галочка «Без проверки локации (--no-geo…)». С флагом очистка идёт
встроенными средствами (реестр-MRU, куки/трекеры, temp, DNS) — без запуска
`CCleaner64.exe`. Патчить/взламывать сам проприетарный `CCleaner64.exe`
утилита не будет.

Без `.exe` (нужен Python): `python cleaner.py --dry-run --all` ·
`python cleaner.py --gui` · пересборка: `build_exe.bat` → `dist\Cleaner.exe`

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
- **Последняя геопозиция и IP-геометки (`--geo`)** — кэш службы геолокации
  Windows `%ProgramData%\Microsoft\Windows\LfSvc\Cache` (последняя известная
  позиция; служба `lfsvc` на время очистки останавливается), отметки
  использования геолокации `LastUsedTime*` в
  `HKCU\…\CapabilityAccessManager\ConsentStore\location` (рекурсивно, с
  `.reg`-бэкапом), даты `DateCreated`/`DateLastConnected` у сетевых профилей
  `HKLM\…\NetworkList\Profiles` (SSID + последняя отметка подключения, сами
  профили Wi-Fi и подписи сетей с MAC шлюза не удаляются — иначе Windows
  забудет сети), гео-разрешения сайтов: `geolocation` в Chromium `Preferences`
  и строки `type='geo'` в Firefox `permissions.sqlite`. Город/регион по
  публичному IP сайты считают у себя и кладут в cookies/Local Storage —
  те сносит секция `--cookies`. Облачную историю местоположений Microsoft
  локально не стереть: account.microsoft.com → Privacy → Location activity.

## Флаги

```
--all            всё сразу (CCleaner + реестр + браузеры + temp + сеть + корзина)
--registry       только реестр          --cookies   только куки/трекеры/кэш
--temp           только временные файлы --network   только DNS/Recent/буфер
--history        + история посещений    --recycle   + корзина
--geo            + последняя геопозиция и IP-геометки (входит в --network и --all)
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
