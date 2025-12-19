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

# Change to script directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("=" * 40)
print("  REELRECON // TACTICAL")
print("=" * 40)
print()

# Install dependencies
print("[SETUP] Installing dependencies...")
subprocess.run([sys.executable, "-m", "pip", "install", "flask", "requests", "-q"])
subprocess.run([sys.executable, "-m", "pip", "install", "yt-dlp", "-q"], capture_output=True)

# Create output directory
os.makedirs("output", exist_ok=True)

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
