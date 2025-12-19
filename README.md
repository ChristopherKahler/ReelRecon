# ReelRecon

**Tactical Content Intelligence** — Scrape Instagram reels, extract transcripts, and generate AI-powered script rewrites.

![ReelRecon](https://img.shields.io/badge/ReelRecon-Tactical-00ff88?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.8+-blue?style=flat-square)
![Flask](https://img.shields.io/badge/Flask-2.0+-green?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

---

## Features

- **Bulk Reel Scraping** — Extract multiple reels from any Instagram profile
- **Automatic Transcription** — Convert audio to text using OpenAI Whisper
- **AI Script Rewriting** — Generate new scripts based on viral content patterns
- **Multi-Provider AI** — Supports OpenAI, Anthropic (Claude), and Google (Gemini)
- **Guided Wizard** — Step-by-step context builder for tailored rewrites
- **Export Options** — Copy transcripts, download videos, save to files
- **Tactical UI** — Clean, dark theme with scan-line aesthetics

---

## Quick Start

### Windows
1. Run `python app.py`
2. Open http://localhost:5001

### Mac
1. Double-click `START-HERE.py`
2. If it opens in a text editor: Right-click → Open With → Python Launcher

See [SETUP-MAC.md](SETUP-MAC.md) for detailed Mac instructions.

---

## Installation

### Prerequisites
- Python 3.8+
- Instagram cookies (for authentication)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/ChristopherKahler/ReelRecon.git
   cd ReelRecon
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Instagram cookies** (see [Getting Cookies](#getting-cookies))

4. **Run the app**
   ```bash
   python app.py
   ```

5. **Open in browser**
   ```
   http://localhost:5001
   ```

---

## Getting Cookies

ReelRecon requires your Instagram session cookies to access reels.

### Method 1: Browser Extension (Recommended)
1. Install "Get cookies.txt LOCALLY" extension:
   - [Chrome](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
   - [Firefox](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)
2. Log into Instagram in your browser
3. Navigate to instagram.com
4. Click the extension icon → Export
5. Save as `cookies.txt` in the ReelRecon folder

### Method 2: Manual Export
Use browser DevTools to export cookies in Netscape format.

---

## Configuration

### AI Providers
Configure AI providers in the Settings panel (gear icon):

| Provider | Model Options | API Key Required |
|----------|--------------|------------------|
| OpenAI | gpt-4o-mini, gpt-4o, gpt-4-turbo | Yes |
| Anthropic | claude-3-5-haiku, claude-3-5-sonnet | Yes |
| Google | gemini-1.5-flash, gemini-1.5-pro | Yes |
| Local (Ollama) | Any installed model | No |
| Copy Only | N/A | No |

### Transcription
- **Whisper** (local) — Requires ffmpeg installed
- Works offline, processes audio locally

---

## Usage

### Scraping Reels
1. Enter an Instagram username
2. Set the number of reels to scrape
3. Click "INITIATE SCRAPE"
4. View results with transcripts and metadata

### AI Rewrites
1. Click "REWRITE" on any scraped reel
2. Choose **GUIDED** mode for step-by-step context, or **QUICK** for freeform
3. Configure your niche, voice, angle, and CTA
4. Click "GENERATE" to create a new script

---

## Project Structure

```
ReelRecon/
├── app.py                 # Flask application
├── scraper/
│   ├── __init__.py
│   └── core.py            # Instagram scraping logic
├── static/
│   ├── css/tactical.css   # UI styles
│   └── js/app.js          # Frontend logic
├── templates/
│   └── index.html         # Main UI template
├── output/                # Scraped data (gitignored)
├── cookies.txt            # Instagram auth (gitignored)
├── config.json            # Settings (gitignored)
├── requirements.txt
├── START-HERE.py          # Mac launcher
├── start-mac.command      # Mac startup script
├── SETUP-MAC.md           # Mac setup guide
└── README.md
```

---

## Troubleshooting

### Port 5000 in use (Mac)
macOS Monterey+ uses port 5000 for AirPlay. ReelRecon defaults to port 5001.

### Transcription not working
Install ffmpeg:
- **Mac**: `brew install ffmpeg`
- **Windows**: Download from https://ffmpeg.org/download.html

### "Login required" or empty results
Your cookies may have expired. Re-export `cookies.txt` from your browser.

### Rate limiting
Instagram may rate-limit requests. Wait a few minutes and try again with fewer reels.

---

## Contributing

Pull requests welcome. For major changes, please open an issue first.

---

## License

[MIT](LICENSE)

---

## Disclaimer

This tool is for educational and personal use. Respect Instagram's Terms of Service and the privacy of content creators. Do not use for spam, harassment, or commercial scraping at scale.
