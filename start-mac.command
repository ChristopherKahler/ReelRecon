#!/bin/bash
# ReelRecon - Mac Startup Script
# Double-click this file to start the app

cd "$(dirname "$0")"

echo ""
echo "======================================"
echo "  REELRECON // TACTICAL"
echo "======================================"
echo ""

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 not found!"
    echo ""
    echo "Install Python 3 from: https://www.python.org/downloads/"
    echo "Or via Homebrew: brew install python3"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

echo "[OK] Python 3 found: $(python3 --version)"

# Check for pip
if ! python3 -m pip --version &> /dev/null; then
    echo "[ERROR] pip not found!"
    echo ""
    echo "Install pip: python3 -m ensurepip --upgrade"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

echo "[OK] pip found"

# Check for ffmpeg (required for whisper)
if ! command -v ffmpeg &> /dev/null; then
    echo ""
    echo "[WARNING] ffmpeg not found - transcription won't work!"
    echo ""
    echo "To enable transcription, install ffmpeg:"
    echo "  brew install ffmpeg"
    echo ""
    echo "Continuing without transcription support..."
    echo ""
    sleep 2
else
    echo "[OK] ffmpeg found"
fi

# Install/upgrade dependencies
echo ""
echo "[SETUP] Installing dependencies..."
python3 -m pip install --upgrade pip --quiet 2>/dev/null
python3 -m pip install flask requests --quiet

# Try to install optional dependencies
if command -v ffmpeg &> /dev/null; then
    echo "[SETUP] Installing transcription support..."
    python3 -m pip install openai-whisper --quiet 2>/dev/null || echo "[SKIP] whisper install failed (optional)"
fi

python3 -m pip install yt-dlp --quiet 2>/dev/null || echo "[SKIP] yt-dlp install failed (optional)"

# Create output directory
mkdir -p output

# Run database migrations (safe to run multiple times)
echo ""
echo "[MIGRATE] Running asset library migrations..."
python3 -m storage.migrate 2>/dev/null || echo "[SKIP] Migration skipped"
echo "[MIGRATE] Updating asset metadata..."
python3 -m storage.update_metadata 2>/dev/null || echo "[SKIP] Metadata update skipped"

echo ""
echo "[READY] Starting server..."
echo ""
echo "Opening browser to: http://localhost:5000"
echo ""
echo "Press Ctrl+C to stop the server"
echo "======================================"
echo ""

# Open browser after short delay
(sleep 2 && open http://localhost:5000) &

# Start Flask app
python3 app.py
