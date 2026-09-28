@echo off
REM Mock HTTPS Server Launcher per Sysmon
title Sysmon Mock HTTPS Server
echo Avvio del Mock HTTPS Server...
"%~dp0.venv\Scripts\python.exe" "%~dp0mock_server.py" %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Si e' verificato un errore durante l'esecuzione del server.
    pause
)
