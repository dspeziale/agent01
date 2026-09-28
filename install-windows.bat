@echo off
REM ==============================================================================
REM Sysmon Agent - Windows Installer Launcher
REM Esegui con doppio clic (o con Esegui come amministratore) oppure da riga di comando:
REM   install-windows.bat
REM   install-windows.bat --status
REM   install-windows.bat --uninstall
REM   install-windows.bat -ServerUrl "https://simei.dsc-italy.app/api/v1/metrics"
REM ==============================================================================
title Installatore Sysmon Agent per Windows
cd /d "%~dp0"

set "TARGET_PS=%~dp0scripts\install-windows.ps1"
if not exist "%TARGET_PS%" (
    if exist "%~dp0install-windows.ps1" (
        set "TARGET_PS=%~dp0install-windows.ps1"
    )
)

REM Mappatura argomenti comuni stile Linux/CMD in switch PowerShell
set "ARGS=%*"
if /I "%~1"=="--uninstall" set "ARGS=-Uninstall"
if /I "%~1"=="-uninstall"  set "ARGS=-Uninstall"
if /I "%~1"=="/uninstall"  set "ARGS=-Uninstall"
if /I "%~1"=="--status"    set "ARGS=-Status"
if /I "%~1"=="-status"     set "ARGS=-Status"
if /I "%~1"=="/status"     set "ARGS=-Status"

powershell -NoProfile -ExecutionPolicy Bypass -File "%TARGET_PS%" %ARGS%
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ATTENZIONE] Il comando e' terminato con codice di errore %ERRORLEVEL%.
)

echo.
pause
