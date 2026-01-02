@echo off
REM ReelRecon Desktop Shortcut Setup
REM Run this once to create a desktop shortcut that you can pin to taskbar

echo ========================================
echo   ReelRecon Shortcut Setup
echo ========================================
echo.

REM Get the directory where this script lives
set SCRIPT_DIR=%~dp0

REM Find Python
set PYTHON_PATH=
if exist "C:\Python312\pythonw.exe" (
    set PYTHON_PATH=C:\Python312\pythonw.exe
) else if exist "C:\Python311\pythonw.exe" (
    set PYTHON_PATH=C:\Python311\pythonw.exe
) else if exist "C:\Python310\pythonw.exe" (
    set PYTHON_PATH=C:\Python310\pythonw.exe
) else (
    REM Try to find pythonw in PATH
    for /f "delims=" %%i in ('where pythonw.exe 2^>nul') do set PYTHON_PATH=%%i
)

if "%PYTHON_PATH%"=="" (
    echo ERROR: Could not find pythonw.exe
    echo Please ensure Python is installed from python.org
    pause
    exit /b 1
)

echo Found Python at: %PYTHON_PATH%
echo.

REM Create shortcut using PowerShell
echo Creating desktop shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$WshShell = New-Object -ComObject WScript.Shell; ^
    $Shortcut = $WshShell.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\ReelRecon.lnk'); ^
    $Shortcut.TargetPath = '%PYTHON_PATH%'; ^
    $Shortcut.Arguments = 'launcher.pyw'; ^
    $Shortcut.WorkingDirectory = '%SCRIPT_DIR:~0,-1%'; ^
    $Shortcut.IconLocation = '%SCRIPT_DIR%ReelRecon.ico,0'; ^
    $Shortcut.Description = 'ReelRecon - Instagram Reel Research Tool'; ^
    $Shortcut.Save()"

if errorlevel 1 (
    echo ERROR: Failed to create shortcut
    pause
    exit /b 1
)

echo.
echo ========================================
echo   SUCCESS!
echo ========================================
echo.
echo Desktop shortcut created: ReelRecon.lnk
echo.
echo You can now:
echo   1. Double-click the shortcut on your desktop to launch
echo   2. Right-click the shortcut and "Pin to taskbar"
echo.
pause
