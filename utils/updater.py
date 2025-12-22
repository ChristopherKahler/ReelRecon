"""
ReelRecon Auto-Updater
Checks GitHub for new releases and handles updates via git pull.
"""

import subprocess
import requests
import os
import time
from pathlib import Path
from .logger import get_logger

logger = get_logger()

# GitHub repo info
GITHUB_OWNER = "ChristopherKahler"
GITHUB_REPO = "ReelRecon"
# Use /releases instead of /releases/latest to include pre-releases
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases"

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # Exponential backoff in seconds

def get_current_version():
    """Read current version from VERSION file."""
    version_file = Path(__file__).parent.parent / "VERSION"
    try:
        if version_file.exists():
            return version_file.read_text().strip()
        return "unknown"
    except Exception as e:
        logger.warning("UPDATER", f"Could not read VERSION file: {e}")
        return "unknown"

def _fetch_github_releases():
    """
    Fetch releases from GitHub API with retry logic.
    Returns (response, error_message) tuple.
    """
    last_error = None
    logger.info("UPDATER", f"Checking GitHub API (will retry up to {MAX_RETRIES} times if needed)")

    for attempt in range(MAX_RETRIES):
        logger.debug("UPDATER", f"Attempt {attempt + 1}/{MAX_RETRIES}")
        try:
            response = requests.get(GITHUB_API_URL, timeout=10)

            # Success or definitive failure (404 = no releases)
            if response.status_code in [200, 404]:
                return response, None

            # Server error - worth retrying
            if response.status_code >= 500:
                last_error = f"GitHub API returned status {response.status_code}"
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[attempt]
                    logger.warning("UPDATER", f"{last_error}, retrying in {delay}s... (attempt {attempt + 1}/{MAX_RETRIES})")
                    time.sleep(delay)
                    continue
            else:
                # Client error (4xx except 404) - don't retry
                return response, None

        except requests.exceptions.Timeout:
            last_error = "GitHub API request timed out"
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[attempt]
                logger.warning("UPDATER", f"{last_error}, retrying in {delay}s... (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(delay)
            continue

        except requests.exceptions.RequestException as e:
            last_error = f"Network error: {e}"
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[attempt]
                logger.warning("UPDATER", f"{last_error}, retrying in {delay}s... (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(delay)
            continue

    # All retries exhausted
    logger.error("UPDATER", f"Failed after {MAX_RETRIES} attempts: {last_error}")
    return None, last_error

def check_for_updates():
    """
    Check GitHub API for latest release with automatic retries.
    Returns dict with update info or None if check fails.
    """
    current_version = get_current_version()

    try:
        response, error = _fetch_github_releases()

        if response is None:
            # All retries failed
            return None

        if response.status_code == 200:
            releases = response.json()

            # Handle empty releases list
            if not releases or len(releases) == 0:
                logger.debug("UPDATER", "No releases found on GitHub")
                return {
                    "update_available": False,
                    "current_version": current_version,
                    "latest_version": current_version,
                    "message": "No releases published yet"
                }

            # Get the most recent release (first in list - includes pre-releases)
            release = releases[0]
            latest_version = release.get("tag_name", "").lstrip("v")
            current_clean = current_version.lstrip("v")

            # Check if versions differ
            update_available = latest_version != current_clean

            result = {
                "update_available": update_available,
                "current_version": current_version,
                "latest_version": latest_version,
                "release_name": release.get("name", f"v{latest_version}"),
                "changelog": release.get("body", "No changelog available."),
                "release_url": release.get("html_url", ""),
                "published_at": release.get("published_at", ""),
                "is_prerelease": release.get("prerelease", False)
            }

            if update_available:
                logger.info("UPDATER", f"Update available: {current_version} -> {latest_version}")
            else:
                logger.debug("UPDATER", f"Already on latest version: {current_version}")

            return result

        elif response.status_code == 404:
            # No releases yet
            logger.debug("UPDATER", "No releases found on GitHub")
            return {
                "update_available": False,
                "current_version": current_version,
                "latest_version": current_version,
                "message": "No releases published yet"
            }
        else:
            logger.warning("UPDATER", f"GitHub API returned status {response.status_code}")
            return None

    except Exception as e:
        logger.error("UPDATER", f"Unexpected error checking for updates", exception=e)
        return None

def run_update():
    """
    Run git pull to update the application.
    Returns dict with success status and details.
    """
    repo_dir = Path(__file__).parent.parent

    try:
        # First, check if we're in a git repo
        result = subprocess.run(
            ["git", "status"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": "Not a git repository",
                "details": result.stderr
            }

        # Run git pull
        logger.info("UPDATER", "Running git pull...")
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            output = result.stdout.strip()

            # Check if already up to date
            if "Already up to date" in output:
                logger.info("UPDATER", "Already up to date")
                return {
                    "success": True,
                    "already_current": True,
                    "message": "Already up to date",
                    "details": output
                }

            # Successfully pulled updates
            logger.info("UPDATER", f"Update successful: {output}")

            # Update VERSION file if it was changed
            new_version = get_current_version()

            return {
                "success": True,
                "already_current": False,
                "message": "Update complete! Please restart the application.",
                "new_version": new_version,
                "details": output,
                "restart_required": True
            }
        else:
            error_msg = result.stderr.strip() or result.stdout.strip()
            logger.error("UPDATER", f"Git pull failed: {error_msg}")
            return {
                "success": False,
                "error": "Git pull failed",
                "details": error_msg
            }

    except subprocess.TimeoutExpired:
        logger.error("UPDATER", "Git pull timed out")
        return {
            "success": False,
            "error": "Update timed out",
            "details": "The update process took too long. Please try again or update manually."
        }
    except FileNotFoundError:
        logger.error("UPDATER", "Git not found")
        return {
            "success": False,
            "error": "Git not installed",
            "details": "Git is required for automatic updates. Please install Git or update manually."
        }
    except Exception as e:
        logger.error("UPDATER", f"Update failed", exception=e)
        return {
            "success": False,
            "error": str(e),
            "details": "An unexpected error occurred during update."
        }

def get_git_status():
    """Get current git status for debugging."""
    repo_dir = Path(__file__).parent.parent

    try:
        # Get current branch
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=10
        )

        # Get latest commit
        commit_result = subprocess.run(
            ["git", "log", "-1", "--oneline"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=10
        )

        return {
            "branch": branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown",
            "latest_commit": commit_result.stdout.strip() if commit_result.returncode == 0 else "unknown",
            "version": get_current_version()
        }
    except Exception as e:
        return {
            "error": str(e),
            "version": get_current_version()
        }
