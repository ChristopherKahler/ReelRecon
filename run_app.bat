@echo off
cd /d %~dp0

echo ========================================
echo  IG REEL SCRAPER // TACTICAL
echo  Flask Application
echo ========================================
echo.

echo [1/4] Checking Flask...
C:\Python312\python.exe -m pip install flask --quiet
echo [2/4] Checking requests...
C:\Python312\python.exe -m pip install requests --quiet
echo [3/4] Checking whisper (optional)...
C:\Python312\python.exe -m pip install openai-whisper --quiet 2>nul
echo [4/4] Checking yt-dlp (fallback)...
C:\Python312\python.exe -m pip install yt-dlp --quiet 2>nul

echo.
echo ========================================
echo  Starting server at http://localhost:5000
echo  Press Ctrl+C to stop
echo ========================================
echo.

start http://localhost:5000
C:\Python312\python.exe app.py

pause
