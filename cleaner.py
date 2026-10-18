#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cleaner — компактная утилита очистки Windows на базе CCleaner64.exe.

Что делает:
  1) Если рядом лежит CCleaner64.exe — запускает его в тихом режиме (/AUTO)
     с готовым ccleaner.ini (реестр, куки, кэш, временные файлы).
  2) Если CCleaner64.exe нет — чистит сама средствами Python (stdlib, без зависимостей):
     • реестр: только безопасные MRU/история (RunMRU, RecentDocs, TypedURLs, MuiCache...),
       перед очисткой — экспорт веток в backup/*.reg (откат двойным кликом);
     • куки и трекеры: Chrome / Edge / Brave / Opera / Yandex / Firefox
       (Cookies, Network\\Cookies, cookies.sqlite, Cache, Local/Session Storage,
        Service Worker, Code Cache, GPUCache);
     • следы в сети и системе: DNS-кэш, Recent, Temp, кэш эскизов, буфер обмена,
       корзина (опционально).

Безопасность:
  --dry-run   ничего не удаляет, только показывает, что было бы удалено (по умолчанию
              при запуске без флагов секции — тоже dry-run с подтверждением).
  Пароли, логины (Login Data) и автозаполнение НЕ трогаются.

Примеры:
  Cleaner.exe                                # двойной клик -> GUI (собранный .exe)
  Cleaner.exe --dry-run --all                # предпросмотр из консоли
  python cleaner.py --dry-run --all          # предпросмотр
  python cleaner.py --all                    # полная очистка (+ CCleaner, если найден)
  python cleaner.py --cookies --network      # только куки/трекеры и сетевые следы
  python cleaner.py --registry --no-ccleaner # только реестр, без CCleaner
  Cleaner.bat --all                          # то же через лаунчер (просит права админа)

Требуется: Windows 10/11. Для Cleaner.exe Python не нужен (всё внутри .exe),
для cleaner.py — Python 3.8+. Для глубокой чистки реестра — CCleaner64.exe рядом.
"""

from __future__ import annotations

import argparse
import ctypes
import datetime as _dt
import glob
import os
import shutil
import subprocess
import sys

IS_WIN = sys.platform.startswith("win")
try:
    import winreg  # type: ignore
except ImportError:  # Linux/macOS — только dry-run/диагностика
    winreg = None

# Русский вывод не должен падать на Windows с нерусской кодовой страницей
# (напр. cp437/cp1252 на en-US системах): форсим UTF-8 с заменой символов.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass

# ----------------------------------------------------------------------------- утилиты

def human(n: int) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.1f} {u}" if u != "B" else f"{n} B"
        n /= 1024
    return f"{n} GB"


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


FROZEN = bool(getattr(sys, "frozen", False))  # True внутри PyInstaller .exe


def app_dir() -> str:
    """Папка, где лежит Cleaner.exe (или cleaner.py при обычном запуске).

    В PyInstaller __file__ указывает во временную папку распаковки _MEIPASS,
    поэтому для .exe соседние файлы (CCleaner64.exe, ccleaner.ini, backup/)
    ищем рядом с самим .exe через sys.executable.
    """
    if FROZEN:
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def hide_console() -> None:
    """Спрятать консольное окно при GUI-запуске собранного .exe."""
    if IS_WIN:
        try:
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception:
            pass


class Cleaner:
    def __init__(self, dry_run: bool = False, verbose: bool = True):
        self.dry_run = dry_run
        self.verbose = verbose
        self.freed = 0
        self.count = 0
        self.errors = 0
        stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_dir = os.path.join(app_dir(), "backup", stamp)

    def log(self, msg: str = "") -> None:
        if self.verbose:
            print(msg)

    @staticmethod
    def _size(path: str) -> int:
        try:
            if os.path.isfile(path):
                return os.path.getsize(path)
            total = 0
            for root, _, files in os.walk(path):
                for f in files:
                    try:
                        total += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        pass
            return total
        except OSError:
            return 0

    def remove(self, path: str, label: str = "") -> None:
        """Удалить файл/папку (в dry-run — только отчёт)."""
        if not path or not os.path.lexists(path):
            return
        size = self._size(path)
        tag = "[DRY-RUN] " if self.dry_run else ""
        self.log(f"  {tag}- {label or path}  ({human(size)})")
        if self.dry_run:
            self.freed += size
            self.count += 1
            return
        try:
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path, ignore_errors=False)
            else:
                os.remove(path)
            self.freed += size
            self.count += 1
        except (PermissionError, OSError) as e:
            # Файл занят запущенным браузером — это норма, подсказываем закрыть его.
            self.errors += 1
            self.log(f"    ! пропущено (занято/нет доступа): {e.filename or path}")

    def remove_glob(self, pattern: str, label: str = "") -> None:
        for p in glob.glob(pattern):
            self.remove(p, label or p)

    # ------------------------------------------------------------------ реестр

    # Только безопасные ветки истории/MRU текущего пользователя.
    # Значения очищаются, сами ключи не удаляются. Глубокую чистку реестра
    # (битые DLL, ActiveX, несуществующие пути) делает CCleaner64.exe /AUTO.
    REG_MRU_KEYS = [
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU",
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\RecentDocs",
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\ComDlg32\LastVisitedPidlMRU",
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\ComDlg32\OpenSavePidlMRU",
        r"Software\Microsoft\Internet Explorer\TypedURLs",
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\TypedPaths",
        r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache",
    ]

    def _backup_reg(self, subkey: str) -> None:
        if self.dry_run or not IS_WIN:
            return
        os.makedirs(self.backup_dir, exist_ok=True)
        name = subkey.replace("\\", "_") + ".reg"
        out = os.path.join(self.backup_dir, name)
        subprocess.run(["reg", "export", f"HKCU\\{subkey}", out, "/y"],
                       capture_output=True, text=True)

    def clean_registry(self) -> None:
        self.log("\n[1] Реестр — история и MRU (безопасная очистка)")
        if not IS_WIN or winreg is None:
            self.log("  ! Не Windows — пропускаю (на целевой машине нужен winreg).")
            # В dry-run на не-Windows всё равно покажем план:
            for k in self.REG_MRU_KEYS:
                self.log(f"  [план] очистить значения HKCU\\{k}")
            return
        for sub in self.REG_MRU_KEYS:
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub, 0,
                                     winreg.KEY_READ | winreg.KEY_WRITE)
            except FileNotFoundError:
                continue
            except OSError as e:
                self.log(f"  ! {sub}: {e}")
                continue
            with key:
                values = []
                try:
                    i = 0
                    while True:
                        values.append(winreg.EnumValue(key, i)[0])
                        i += 1
                except OSError:
                    pass
                if not values:
                    continue
                self.log(f"  {'[DRY-RUN] ' if self.dry_run else ''}HKCU\\{sub}: "
                         f"{len(values)} знач. -> backup + очистка")
                if not self.dry_run:
                    self._backup_reg(sub)
                    for v in values:
                        try:
                            winreg.DeleteValue(key, v)
                            self.count += 1
                        except OSError:
                            self.errors += 1
        self.log(f"  Бэкапы реестра: {self.backup_dir} (откат — двойной клик по .reg)")

    # ------------------------------------------------------------------ браузеры: куки/трекеры

    # Chromium-браузеры: (имя, User Data относительно LOCALAPPDATA/APPDATA)
    CHROMIUM = [
        ("Chrome",  os.path.join(env("LOCALAPPDATA"), "Google", "Chrome", "User Data")),
        ("Edge",    os.path.join(env("LOCALAPPDATA"), "Microsoft", "Edge", "User Data")),
        ("Brave",   os.path.join(env("LOCALAPPDATA"), "BraveSoftware", "Brave-Browser", "User Data")),
        ("Yandex",  os.path.join(env("LOCALAPPDATA"), "Yandex", "YandexBrowser", "User Data")),
        ("Opera",   os.path.join(env("APPDATA"), "Opera Software", "Opera Stable")),
    ]
    # Внутри профиля: куки + трекерные хранилища + кэш. Login Data/пароли НЕ трогаем.
    # Кортежи — чтобы путь собирался через os.path.join на любой ОС.
    PROFILE_JUNK = [
        ("Cookies",), ("Network", "Cookies"),                       # куки
        ("Cache",), ("Code Cache",), ("GPUCache",),                 # кэш
        ("Local Storage",), ("Session Storage",), ("IndexedDB",),   # трекеры/хранилища
        ("Service Worker", "CacheStorage"), ("Service Worker", "ScriptCache"),
        ("blob_storage",), ("databases",),
    ]

    def _profiles(self, base: str):
        if not base or not os.path.isdir(base):
            return
        yield base  # Opera и др. без подпапок-профилей
        for pat in ("Default", "Profile *", "Guest Profile"):
            yield from glob.glob(os.path.join(base, pat))

    def clean_browsers(self, history: bool = False) -> None:
        self.log("\n[2] Браузеры — куки, трекеры, кэш (пароли не трогаются)")
        self.log("    Закройте браузеры перед очисткой, иначе файлы будут заняты.")
        for name, base in self.CHROMIUM:
            profs = [p for p in self._profiles(base) if os.path.isdir(p)]
            if not profs:
                continue
            self.log(f"  {name}: {base}")
            for prof in profs:
                for junk in self.PROFILE_JUNK:
                    self.remove(os.path.join(prof, *junk),
                                f"{name}/{os.path.basename(prof)}/{'/'.join(junk)}")
                if history:
                    self.remove(os.path.join(prof, "History"),
                                f"{name}/{os.path.basename(prof)}/History")
        # Firefox
        ff = os.path.join(env("APPDATA"), "Mozilla", "Firefox", "Profiles")
        for prof in glob.glob(os.path.join(ff, "*")):
            if not os.path.isdir(prof):
                continue
            self.log(f"  Firefox: {prof}")
            for f in ("cookies.sqlite", "cookies.sqlite-wal", "cookies.sqlite-shm",
                      "webappsstore.sqlite", "places.sqlite-wal"):
                self.remove(os.path.join(prof, f), f"Firefox/{f}")
            for d in (("cache2",), ("startupCache",), ("storage", "default")):
                self.remove(os.path.join(prof, *d), f"Firefox/{'/'.join(d)}")
            if history:
                self.remove(os.path.join(prof, "places.sqlite"), "Firefox/places.sqlite")

    # ------------------------------------------------------------------ система и сеть

    def clean_temp(self) -> None:
        self.log("\n[3] Временные файлы и кэш Windows")
        for label, path in [
            ("User Temp", env("TEMP")),
            ("Windows Temp", os.path.join(env("SystemRoot", r"C:\Windows"), "Temp")),
            ("Кэш эскизов", os.path.join(env("LOCALAPPDATA"),
                                         "Microsoft", "Windows", "Explorer")),
            ("WER-отчёты", os.path.join(env("LOCALAPPDATA"),
                                        "Microsoft", "Windows", "WER")),
        ]:
            if not path or not os.path.isdir(path):
                continue
            if "Explorer" in path:  # только файлы кэша, не всю папку
                self.remove_glob(os.path.join(path, "thumbcache_*.db"), label)
                self.remove_glob(os.path.join(path, "iconcache_*.db"), label)
            else:
                self.remove_glob(os.path.join(path, "*"), label)

    def clean_network(self, recycle: bool = False) -> None:
        self.log("\n[4] Следы присутствия в сети и системе")
        # История открытых файлов/папок
        recent = os.path.join(env("APPDATA"), "Microsoft", "Windows", "Recent")
        self.remove_glob(os.path.join(recent, "*"), "Recent (история файлов)")
        # Prefetch — опционально шумно, не трогаем по умолчанию.
        if IS_WIN and not self.dry_run:
            r = subprocess.run(["ipconfig", "/flushdns"],
                               capture_output=True, text=True)
            self.log("  - DNS-кэш сброшен" if r.returncode == 0
                     else f"  ! ipconfig /flushdns: {r.returncode}")
            # Буфер обмена
            subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $null"],
                           capture_output=True)
            self.log("  - Буфер обмена очищен")
        elif self.dry_run:
            self.log("  [DRY-RUN] - ipconfig /flushdns; очистка буфера обмена")
        if recycle:
            if IS_WIN and not self.dry_run:
                try:  # SHEmptyRecycleBinW
                    ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x7)
                    self.log("  - Корзина очищена")
                except Exception as e:  # noqa: BLE001
                    self.log(f"  ! Корзина: {e}")
            else:
                self.log("  [DRY-RUN] - Очистка корзины")

    # ------------------------------------------------------------------ CCleaner

    @staticmethod
    def find_ccleaner(explicit: str = "") -> str:
        cands = [explicit] if explicit else []
        here = app_dir()
        cands += [
            os.path.join(here, "CCleaner64.exe"),
            os.path.join(here, "CCleaner", "CCleaner64.exe"),
            os.path.join(env("ProgramFiles", r"C:\Program Files"), "CCleaner", "CCleaner64.exe"),
            r"C:\Program Files\CCleaner\CCleaner64.exe",
        ]
        return next((c for c in cands if c and os.path.isfile(c)), "")

    def run_ccleaner(self, path: str) -> None:
        self.log(f"\n[0] CCleaner64.exe /AUTO -> {path}")
        self.log("    (реестр + файлы по ccleaner.ini рядом со скриптом)")
        if self.dry_run:
            self.log("  [DRY-RUN] запуск пропущен")
            return
        try:
            r = subprocess.run([path, "/AUTO"], timeout=900)
            self.log(f"  CCleaner завершён, код {r.returncode}")
        except Exception as e:  # noqa: BLE001
            self.errors += 1
            self.log(f"  ! Не удалось запустить CCleaner: {e}")

    def report(self) -> None:
        self.log("\n" + "=" * 56)
        self.log(f"Готово. Объектов: {self.count}, освобождено/к освобождению: "
                 f"{human(self.freed)}, ошибок (занято): {self.errors}")
        if self.dry_run:
            self.log("Это был DRY-RUN — ничего не удалено. Запуск без --dry-run выполнит очистку.")


# ----------------------------------------------------------------------------- CLI / GUI

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cleaner", description="Очистка реестра, куки, трекеров и следов в сети "
                                     "(на базе CCleaner64.exe + встроенный fallback).")
    p.add_argument("--all", action="store_true", help="всё: CCleaner + реестр + браузеры + temp + сеть")
    p.add_argument("--registry", action="store_true", help="только реестр (MRU/история, с бэкапом)")
    p.add_argument("--cookies", action="store_true", help="только куки/трекеры/кэш браузеров")
    p.add_argument("--history", action="store_true", help="заодно удалить историю посещений браузеров")
    p.add_argument("--temp", action="store_true", help="только временные файлы Windows")
    p.add_argument("--network", action="store_true", help="только сетевые следы: DNS, Recent, буфер")
    p.add_argument("--recycle", action="store_true", help="очистить корзину")
    p.add_argument("--dry-run", action="store_true", help="ничего не удалять, только показать план")
    p.add_argument("--yes", "-y", action="store_true", help="без подтверждения")
    p.add_argument("--no-ccleaner", action="store_true", help="не запускать CCleaner64.exe")
    p.add_argument("--ccleaner", metavar="PATH", default="", help="путь к CCleaner64.exe")
    p.add_argument("--gui", action="store_true", help="простой графический интерфейс (tkinter)")
    return p


def run(args) -> int:
    c = Cleaner(dry_run=args.dry_run)
    do_all = args.all or not any([args.registry, args.cookies, args.temp, args.network])
    if not (args.yes or args.dry_run):
        ans = input("Начать очистку? [y/N] ").strip().lower()
        if ans not in ("y", "yes", "д", "да"):
            print("Отменено.")
            return 1
    cc = "" if args.no_ccleaner else c.find_ccleaner(args.ccleaner)
    if cc and (do_all or args.registry or args.cookies):
        c.run_ccleaner(cc)
    elif not args.no_ccleaner:
        c.log("CCleaner64.exe не найден рядом/в Program Files — работаю встроенными средствами.")
        c.log("Положите портативный CCleaner64.exe рядом с cleaner.py для глубокой чистки реестра.")
    if do_all or args.registry:
        c.clean_registry()
    if do_all or args.cookies:
        c.clean_browsers(history=args.history)
    if do_all or args.temp:
        c.clean_temp()
    if do_all or args.network:
        c.clean_network(recycle=args.recycle or do_all)
    c.report()
    return 0


def gui() -> None:  # минимальный GUI, stdlib tkinter
    hide_console()
    import tkinter as tk
    from tkinter import messagebox, ttk

    root = tk.Tk()
    root.title("Cleaner — реестр, куки, трекеры")
    root.geometry("460x340")
    dry = tk.BooleanVar(value=True)
    opts = {k: tk.BooleanVar(value=True) for k in ("registry", "cookies", "temp", "network")}
    labels = {"registry": "Реестр (MRU, с бэкапом)", "cookies": "Куки, трекеры, кэш браузеров",
              "temp": "Временные файлы", "network": "Сеть: DNS, Recent, буфер, корзина"}
    for k, v in opts.items():
        ttk.Checkbutton(root, text=labels[k], variable=v).pack(anchor="w", padx=12, pady=2)
    ttk.Checkbutton(root, text="Dry-run (только показать)", variable=dry).pack(anchor="w", padx=12, pady=6)
    logbox = tk.Text(root, height=8, width=52)
    logbox.pack(padx=12, pady=6)

    def go():
        class A:  # noqa: D401 - простой namespace под run()
            pass
        a = A()
        a.dry_run, a.yes, a.no_ccleaner, a.ccleaner = dry.get(), True, False, ""
        a.all, a.history, a.recycle = False, False, True
        a.registry, a.cookies, a.temp, a.network = (opts[k].get() for k in
                                                    ("registry", "cookies", "temp", "network"))
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run(a)
        logbox.delete("1.0", "end")
        logbox.insert("end", buf.getvalue())
        messagebox.showinfo("Cleaner", "Готово. Подробности — в окне выше.")

    ttk.Button(root, text="Очистить", command=go).pack(pady=4)
    root.mainloop()


if __name__ == "__main__":
    # Двойной клик по Cleaner.exe (без аргументов) -> сразу GUI, без консоли.
    # С аргументами из cmd/PowerShell -> обычный CLI (Cleaner.exe --all и т.д.)
    if FROZEN and len(sys.argv) == 1:
        gui()
    else:
        args = build_parser().parse_args()
        if args.gui:
            gui()
        else:
            sys.exit(run(args))
