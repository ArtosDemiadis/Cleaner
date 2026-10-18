# Clean.ps1 — PowerShell-обёртка (альтернатива Cleaner.bat)
# Запуск:  powershell -ExecutionPolicy Bypass -File .\Clean.ps1 -All
#          powershell -ExecutionPolicy Bypass -File .\Clean.ps1 -DryRun -Cookies -Network
[CmdletBinding()]
param(
    [switch]$All, [switch]$Registry, [switch]$Cookies, [switch]$Temp,
    [switch]$Network, [switch]$History, [switch]$DryRun, [switch]$NoCCleaner
)
$ErrorActionPreference = 'Continue'
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
           ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Start-Process powershell -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`" $($MyInvocation.BoundParameters.Keys -join ' -')"
    exit
}
Set-Location $PSScriptRoot

# 1) CCleaner64.exe /AUTO (глубокий реестр + файлы по ccleaner.ini)
if (-not $NoCCleaner) {
    $cc = @("$PSScriptRoot\CCleaner64.exe", "$PSScriptRoot\CCleaner\CCleaner64.exe",
            "$env:ProgramFiles\CCleaner\CCleaner64.exe") |
          Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($cc -and -not $DryRun) { Write-Host "[CCleaner] $cc /AUTO"; & $cc /AUTO }
    elseif ($cc) { Write-Host "[DRY-RUN] CCleaner: $cc /AUTO" }
    else { Write-Host "[CCleaner] не найден — встроенная очистка (cleaner.py)" }
}

# 2) Встроенная очистка на Python (куки/трекеры/MRU-реестр/temp/сеть)
$pyArgs = @("$PSScriptRoot\cleaner.py", '--no-ccleaner', '--yes')
if ($All)      { $pyArgs += '--all' }
if ($Registry) { $pyArgs += '--registry' }
if ($Cookies)  { $pyArgs += '--cookies' }
if ($Temp)     { $pyArgs += '--temp' }
if ($Network)  { $pyArgs += '--network' }
if ($History)  { $pyArgs += '--history' }
if ($DryRun)   { $pyArgs += '--dry-run' }
if (Get-Command python -ErrorAction SilentlyContinue) { & python @pyArgs }
elseif (Get-Command py -ErrorAction SilentlyContinue) { & py @pyArgs }
else { Write-Warning 'Python не найден — выполнился только CCleaner (если был).' }
