#!/bin/bash
# ReelRecon Self-Bootstrapping Installer for Mac
# Downloads Homebrew, Git, and Python if needed, then installs ReelRecon

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}                ${GREEN}REELRECON INSTALLER${NC}                          ${CYAN}║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Get the directory where this script lives
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Check for Xcode Command Line Tools (required for git on fresh Mac)
check_xcode_tools() {
    if ! xcode-select -p &> /dev/null; then
        echo -e "${YELLOW}Installing Xcode Command Line Tools...${NC}"
        echo "A dialog will appear - click 'Install' to continue."
        xcode-select --install
        echo ""
        echo -e "${YELLOW}After installation completes, please run this installer again.${NC}"
        read -p "Press Enter to exit..."
        exit 0
    fi
}

# Check for Homebrew
check_homebrew() {
    if ! command -v brew &> /dev/null; then
        echo -e "${YELLOW}Homebrew not found.${NC}"
        echo ""
        read -p "Would you like to install Homebrew? (recommended) [Y/n]: " response
        response=${response:-Y}
        if [[ "$response" =~ ^[Yy]$ ]]; then
            echo -e "${CYAN}Installing Homebrew...${NC}"
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

            # Add Homebrew to PATH for this session
            if [[ -f /opt/homebrew/bin/brew ]]; then
                eval "$(/opt/homebrew/bin/brew shellenv)"
            elif [[ -f /usr/local/bin/brew ]]; then
                eval "$(/usr/local/bin/brew shellenv)"
            fi

            echo -e "${GREEN}Homebrew installed!${NC}"
        fi
    else
        echo -e "${GREEN}✓ Homebrew found${NC}"
    fi
}

# Check for Python 3
check_python() {
    if ! command -v python3 &> /dev/null; then
        echo -e "${YELLOW}Python 3 not found.${NC}"
        echo ""

        if command -v brew &> /dev/null; then
            read -p "Would you like to install Python 3 via Homebrew? [Y/n]: " response
            response=${response:-Y}
            if [[ "$response" =~ ^[Yy]$ ]]; then
                echo -e "${CYAN}Installing Python 3...${NC}"
                brew install python3
                echo -e "${GREEN}Python 3 installed!${NC}"
            else
                echo -e "${RED}Python 3 is required. Please install it manually.${NC}"
                echo "Download from: https://python.org/downloads"
                read -p "Press Enter to exit..."
                exit 1
            fi
        else
            echo -e "${RED}Python 3 is required.${NC}"
            echo "Please install Python from: https://python.org/downloads"
            read -p "Press Enter to exit..."
            exit 1
        fi
    else
        echo -e "${GREEN}✓ Python 3 found${NC}"
    fi
}

# Check for Git
check_git() {
    if ! command -v git &> /dev/null; then
        echo -e "${YELLOW}Git not found.${NC}"
        echo ""

        if command -v brew &> /dev/null; then
            read -p "Would you like to install Git via Homebrew? [Y/n]: " response
            response=${response:-Y}
            if [[ "$response" =~ ^[Yy]$ ]]; then
                echo -e "${CYAN}Installing Git...${NC}"
                brew install git
                echo -e "${GREEN}Git installed!${NC}"
            else
                echo -e "${RED}Git is required. Please install it manually.${NC}"
                read -p "Press Enter to exit..."
                exit 1
            fi
        else
            # Git comes with Xcode Command Line Tools
            check_xcode_tools
        fi
    else
        echo -e "${GREEN}✓ Git found${NC}"
    fi
}

# Main installation
main() {
    echo -e "${CYAN}Checking dependencies...${NC}"
    echo ""

    # Check all dependencies
    check_xcode_tools
    check_homebrew
    check_python
    check_git

    echo ""
    echo -e "${GREEN}All dependencies satisfied!${NC}"
    echo ""
    echo -e "${CYAN}Launching ReelRecon installer...${NC}"
    echo ""

    # Run the Python installer
    INSTALLER="$SCRIPT_DIR/lib/ReelRecon-Installer-Mac.py"

    if [[ -f "$INSTALLER" ]]; then
        # Run installer and close terminal
        python3 "$INSTALLER" &

        # Give it a moment to start
        sleep 2

        echo -e "${GREEN}Installer launched! You can close this terminal window.${NC}"
        echo ""

        # Try to close terminal window
        osascript -e 'tell application "Terminal" to close first window' &> /dev/null || true
    else
        echo -e "${RED}Installer not found at: $INSTALLER${NC}"
        echo "Please ensure the installer files are intact."
        read -p "Press Enter to exit..."
        exit 1
    fi
}

# Run main
main
