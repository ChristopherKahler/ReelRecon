#!/usr/bin/env python3
"""
ReelRecon - Double-click to start (Mac)
If this opens in a text editor instead of running:
  Right-click → Open With → Python Launcher
"""
import subprocess
import sys
import os
import webbrowser
import time
import shutil

# Change to script directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("=" * 40)
print("  REELRECON // TACTICAL")
print("=" * 40)
print()

# Check for ffmpeg
ffmpeg_available = shutil.which("ffmpeg") is not None

if not ffmpeg_available:
    print("[WARNING] ffmpeg not found!")
    print("          Transcription requires ffmpeg.")
    print()

    # Check if Homebrew is available
    if not shutil.which("brew"):
        print("[SETUP] Homebrew not found. Installing Homebrew first...")
        print("        (You may need to press RETURN and enter your password)")
        print()
        result = subprocess.run(
            ["/bin/bash", "-c", 'NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'],
            shell=False
        )
        # Add brew to PATH for this session (Apple Silicon vs Intel)
        if os.path.exists("/opt/homebrew/bin/brew"):
            os.environ["PATH"] = "/opt/homebrew/bin:" + os.environ.get("PATH", "")
        elif os.path.exists("/usr/local/bin/brew"):
            os.environ["PATH"] = "/usr/local/bin:" + os.environ.get("PATH", "")

    if shutil.which("brew"):
        print("[SETUP] Installing ffmpeg via Homebrew...")
        result = subprocess.run(["brew", "install", "ffmpeg"])
        if result.returncode == 0:
            print("[OK] ffmpeg installed successfully!")
            ffmpeg_available = True
        else:
            print("[SKIP] ffmpeg install failed. Install manually: brew install ffmpeg")
    else:
        print("[SKIP] Homebrew installation failed or not in PATH.")
        print("       Restart terminal and run this script again, or install manually:")
        print("       /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
    print()

# Install dependencies
print("[SETUP] Installing core dependencies...")
subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "-q"], capture_output=True)
subprocess.run([sys.executable, "-m", "pip", "install", "flask", "requests", "-q"])

print("[SETUP] Installing optional dependencies...")
subprocess.run([sys.executable, "-m", "pip", "install", "yt-dlp", "-q"], capture_output=True)

# Install whisper for transcription
if ffmpeg_available:
    print("[SETUP] Installing transcription support (this may take a minute)...")
    result = subprocess.run([sys.executable, "-m", "pip", "install", "openai-whisper", "-q"], capture_output=True)
    if result.returncode == 0:
        print("[OK] Whisper installed - transcription enabled!")
    else:
        print("[SKIP] Whisper install failed (optional)")
else:
    print("[SKIP] Skipping Whisper (requires ffmpeg)")

# Create output directory
os.makedirs("output", exist_ok=True)

print()
print("[READY] Starting server...")
print()
print("Opening browser to: http://localhost:5001")
print("Close this window to stop the server")
print("=" * 40)

# Open browser after delay
def open_browser():
    time.sleep(2)
    webbrowser.open("http://localhost:5001")

import threading
threading.Thread(target=open_browser, daemon=True).start()

# Start Flask (import and run)
from app import app
app.run(host="0.0.0.0", port=5001, debug=False)
