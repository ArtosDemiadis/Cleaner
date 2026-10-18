@echo off
chcp 6501 >nul
title Build Cleaner.exe
cd /d "%~dp0"

rem ============================================================
rem  Samosborka Cleaner.exe na Windows (esli ne hochetsya
rem  skachivat gotovyy .exe s GitHub Releases):
rem    1) Ustanovlen Python 3.10+  (python.org, galka Add to PATH)
rem    2) Zapustit etot .bat - on postavit PyInstaller i soberot
rem       dist\Cleaner.exe (odin fayl, zapros prav admina, GUI
rem       po dvoynomu kliku, CLI: Cleaner.exe --dry-run --all)
rem ============================================================

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python ne nayden. Ustanovite s https://python.org
    pause
    exit /b 1
)

python -m pip install --upgrade pyinstaller
if %errorlevel% neq 0 (
    echo [!] Ne udalos ustanovit PyInstaller
    pause
    exit /b 1
)

python -m PyInstaller --onefile --name Cleaner --uac-admin ^
    --hidden-import tkinter --hidden-import _tkinter ^
    cleaner.py
if %errorlevel% neq 0 (
    echo [!] Sborka ne udalas
    pause
    exit /b 1
)

copy /y ccleaner.ini dist\ >nul
copy /y README.md dist\ >nul
echo.
echo Gotovo: dist\Cleaner.exe
echo Zapusk: dvoynoy klik - GUI; Cleaner.exe --dry-run --all - CLI
pause
