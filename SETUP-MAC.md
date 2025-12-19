# ReelRecon - Mac Setup Guide

## Quick Start (No Terminal Required)

### Double-click `START-HERE.py`

If it opens in a text editor instead of running:
- Right-click the file
- Choose "Open With" → "Python Launcher"

The app will install dependencies, start the server, and open your browser to http://localhost:5001

---

## Alternative Methods (if above doesn't work)

### Terminal one-liner
```bash
cd ~/Downloads/ReelRecon && python3 -m pip install flask requests && python3 app.py
```

### Run the startup script
```bash
bash start-mac.command
```

---

## Set up your cookies.txt

ReelRecon requires Instagram authentication cookies to scrape reels.

### How to get cookies.txt:
1. Install the browser extension "Get cookies.txt LOCALLY" ([Chrome](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) / [Firefox](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/))
2. Log into Instagram in your browser
3. Click the extension icon while on instagram.com
4. Click "Export" to download cookies.txt
5. Move the `cookies.txt` file to the ReelRecon folder

---

## Prerequisites

### Required
- **Python 3.8+** - Check with: `python3 --version`
  - Install: https://www.python.org/downloads/ or `brew install python3`

### Optional (for transcription)
- **ffmpeg** - Required for Whisper transcription
  - Install: `brew install ffmpeg`

### Optional (for AI rewrites)
- API key from OpenAI, Anthropic, or Google (configure in Settings)

---

## Troubleshooting

### "Port 5000 already in use" / AirPlay Receiver
macOS uses port 5000 for AirPlay. ReelRecon uses port 5001 by default to avoid this.

If you still have issues:
- System Settings → General → AirDrop & Handoff → Disable "AirPlay Receiver"

### "Permission denied" when running start-mac.command
```bash
chmod +x start-mac.command
```

### "Python 3 not found"
Install Python from https://www.python.org/downloads/
Or via Homebrew: `brew install python3`

### "zsh: bad interpreter"
The file may have Windows line endings. Fix with:
```bash
sed -i '' 's/\r$//' start-mac.command
```

### Transcription not working
Install ffmpeg:
```bash
brew install ffmpeg
```

### "Module not found" errors
Manually install dependencies:
```bash
python3 -m pip install flask requests openai-whisper yt-dlp
```

---

## Manual Start (Alternative)
If the script doesn't work, start manually:
```bash
cd /path/to/ReelRecon
python3 -m pip install flask requests
python3 app.py
```
Then open http://localhost:5001 in your browser.
