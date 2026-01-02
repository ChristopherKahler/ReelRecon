@echo off
echo ========================================
echo  Building Windows Executable
echo ========================================
echo.

REM Install PyInstaller if needed
C:\Python312\python.exe -m pip install pyinstaller --quiet

REM Build the executable
C:\Python312\python.exe -m PyInstaller ^
    --name "IG-Reel-Scraper" ^
    --onefile ^
    --windowed ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --icon "static/icon.ico" ^
    app.py

echo.
echo ========================================
echo  Build complete! Check dist/ folder
echo ========================================

pause
