@echo off
chcp 6501 >nul
title Cleaner - reestr, cookie, trekery
setlocal EnableDelayedExpansion
cd /d "%~dp0"

rem --- Права администратора (нужны для Temp Windows и CCleaner) ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Zapusk ot imeni administratora...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '%*' -Verb RunAs"
    exit /b
)

echo ============================================================
echo   Cleaner: reestr + cookie + trekery + sledy v seti
echo   Rezhim po umolchaniyu: polnyy. Podderzhka: --dry-run --help
echo ============================================================

rem --- 1) CCleaner64.exe, esli lezhit ryadom ili v Program Files ---
set "CC="
if exist "%~dp0CCleaner64.exe" set "CC=%~dp0CCleaner64.exe"
if exist "%~dp0CCleaner\CCleaner64.exe" set "CC=%~dp0CCleaner\CCleaner64.exe"
if exist "%ProgramFiles%\CCleaner\CCleaner64.exe" set "CC=%ProgramFiles%\CCleaner\CCleaner64.exe"

if defined CC (
    echo [CCleaner] %CC% /AUTO
    "%CC%" /AUTO
) else (
    echo [CCleaner] CCleaner64.exe ne nayden - chistim vstroennymi sredstvami.
    echo            Polozhite portativnyy CCleaner64.exe ryadom s Cleaner.bat
    echo            dlya glubokoy chistki reestra.
)

rem --- 2) Vstroennaya ochistka (cookie/trekery/temp/set) ---
where python >nul 2>&1
if %errorlevel% equ 0 (
    python "%~dp0cleaner.py" --no-ccleaner %*
) else (
    where py >nul 2>&1
    if !errorlevel! equ 0 (
        py "%~dp0cleaner.py" --no-ccleaner %*
    ) else (
        echo [!] Python ne nayden. Ustanovite Python 3 s python.org
        echo     ili polozhite CCleaner64.exe ryadom - on otrabotaet sam.
    )
)

rem --- 3) Sbroc DNS, esli cleaner.py ne zapuskalsya ---
ipconfig /flushdns >nul

echo.
echo Gotovo. Logi i bekapy reestra: backup\
pause
endlocal
