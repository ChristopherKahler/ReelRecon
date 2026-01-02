#!/bin/bash
# ReelRecon Mac Installer Launcher
# Double-click this file to install ReelRecon

# Get the directory where this script lives
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
INSTALLER="$SCRIPT_DIR/lib/ReelRecon-Installer-Mac.py"

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    osascript -e 'display dialog "Python 3 is not installed.\n\nPlease install Python from python.org or via Homebrew:\nbrew install python3" with title "ReelRecon Installer" buttons {"OK"} default button 1 with icon stop'
    exit 1
fi

# Run the installer and close this terminal window
# Using osascript to run Python in background without terminal
osascript <<EOF
do shell script "cd '$SCRIPT_DIR' && /usr/bin/python3 '$INSTALLER' &> /dev/null &"
EOF

# Close this terminal window
osascript -e 'tell application "Terminal" to close first window' &> /dev/null

exit 0
