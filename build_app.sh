#!/bin/bash
cd "$(dirname "$0")"

echo "========================================"
echo "  Building macOS Application"
echo "========================================"
echo ""

# Install PyInstaller if needed
python3 -m pip install pyinstaller --quiet

# Build the application
python3 -m PyInstaller \
    --name "IG-Reel-Scraper" \
    --onefile \
    --windowed \
    --add-data "templates:templates" \
    --add-data "static:static" \
    app.py

echo ""
echo "========================================"
echo "  Build complete! Check dist/ folder"
echo "========================================"
