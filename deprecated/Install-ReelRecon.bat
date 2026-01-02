@echo off
title ReelRecon Installer
cd /d %~dp0

REM Check for Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Opening download page...
    start https://python.org/downloads
    echo Please install Python and run this installer again.
    pause
    exit /b 1
)

REM Run the installer
python ReelRecon-Installer.pyw
