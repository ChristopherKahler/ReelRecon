#!/bin/bash
cd "$(dirname "$0")"

echo "========================================"
echo "  IG REEL SCRAPER // TACTICAL"
echo "  Flask Application"
echo "========================================"
echo ""

echo "[1/4] Checking Flask..."
python3 -m pip install flask --quiet
echo "[2/4] Checking requests..."
python3 -m pip install requests --quiet
echo "[3/4] Checking whisper (optional)..."
python3 -m pip install openai-whisper --quiet 2>/dev/null || true
echo "[4/4] Checking yt-dlp (fallback)..."
python3 -m pip install yt-dlp --quiet 2>/dev/null || true

echo ""
echo "========================================"
echo "  Starting server at http://localhost:5000"
echo "  Press Ctrl+C to stop"
echo "========================================"
echo ""

# Open browser (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    open http://localhost:5000 &
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    xdg-open http://localhost:5000 &>/dev/null &
fi

# Start Flask app
python3 app.py
