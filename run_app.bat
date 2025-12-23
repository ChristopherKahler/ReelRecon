@echo off
cd /d %~dp0

echo ========================================
echo  REELRECON // TACTICAL
echo  Flask Application
echo ========================================
echo.

REM Create config.json from template if it doesn't exist
if not exist "config.json" (
    if exist "config.template.json" (
        copy "config.template.json" "config.json" >nul
        echo [CONFIG] Created config.json from template
        echo          Add your API keys to config.json for cloud AI features
        echo.
    ) else (
        echo [CONFIG] Creating default config.json...
        echo { > config.json
        echo   "ai_provider": "local", >> config.json
        echo   "local_model": "qwen3:8B", >> config.json
        echo   "openai_model": "gpt-4o-mini", >> config.json
        echo   "anthropic_model": "claude-3-5-haiku-20241022", >> config.json
        echo   "google_model": "gemini-1.5-flash", >> config.json
        echo   "openai_key": "", >> config.json
        echo   "anthropic_key": "", >> config.json
        echo   "google_key": "" >> config.json
        echo } >> config.json
        echo [CONFIG] Created default config.json
        echo          Add your API keys for cloud AI features
        echo.
    )
)

echo [1/4] Checking Flask...
C:\Python312\python.exe -m pip install flask --quiet
echo [2/4] Checking requests...
C:\Python312\python.exe -m pip install requests --quiet
echo [3/4] Checking whisper (optional)...
C:\Python312\python.exe -m pip install openai-whisper --quiet 2>nul
echo [4/4] Checking yt-dlp (fallback)...
C:\Python312\python.exe -m pip install yt-dlp --quiet 2>nul

echo.
echo [MIGRATE] Running asset library migrations...
C:\Python312\python.exe -m storage.migrate 2>nul
echo [MIGRATE] Updating asset metadata...
C:\Python312\python.exe -m storage.update_metadata 2>nul

echo.
echo ========================================
echo  Starting server at http://localhost:5000
echo  Press Ctrl+C to stop
echo ========================================
echo.

start http://localhost:5000
C:\Python312\python.exe app.py

pause
