"""
ReelRecon - Core Scraping Module
Instagram reel extraction and transcription with robust error handling
"""

import json
import os
import re
import time
import hashlib
from datetime import datetime
from pathlib import Path
from functools import wraps

import requests

# Import utilities from parent directory
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import get_logger, retry_with_backoff, RetryConfig

# Initialize logger
logger = get_logger()


def generate_error_code(error_msg, prefix="SCR"):
    """Generate a trackable error code"""
    return f"{prefix}-{int(time.time()) % 100000:05d}-{hashlib.md5(error_msg.encode()).hexdigest()[:4].upper()}"


# Retry configuration for network operations
NETWORK_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    initial_delay=1.0,
    max_delay=10.0,
    exponential_base=2.0,
    jitter=True,
    retryable_exceptions=(
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.ChunkedEncodingError,
        ConnectionResetError,
        OSError,
    )
)

# Optional: Whisper for transcription
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


def load_cookies(filepath):
    """Load cookies from Netscape cookies.txt format"""
    cookies = {}
    try:
        with open(filepath, 'r') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                parts = line.strip().split('\t')
                if len(parts) >= 7:
                    name, value = parts[5], parts[6]
                    cookies[name] = value
        logger.debug("COOKIES", f"Loaded {len(cookies)} cookies from {filepath}")
    except FileNotFoundError:
        logger.error("COOKIES", f"Cookies file not found: {filepath}")
        raise
    except Exception as e:
        logger.error("COOKIES", f"Failed to parse cookies file", exception=e)
        raise
    return cookies


def create_session(cookies_path):
    """Create an authenticated Instagram session"""
    logger.debug("SESSION", f"Creating authenticated session from {cookies_path}")

    try:
        cookies = load_cookies(cookies_path)
    except Exception as e:
        error_code = logger.error("SESSION", "Failed to load cookies", exception=e)
        raise RuntimeError(f"[{error_code}] Cookie loading failed: {e}")

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'X-IG-App-ID': '936619743392459',
        'X-Requested-With': 'XMLHttpRequest',
        'X-ASBD-ID': '129477',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Origin': 'https://www.instagram.com',
        'Referer': 'https://www.instagram.com/',
    })

    for name, value in cookies.items():
        session.cookies.set(name, value, domain='.instagram.com')

    if 'csrftoken' in cookies:
        session.headers['X-CSRFToken'] = cookies['csrftoken']
        logger.debug("SESSION", "CSRF token set in session headers")
    else:
        logger.warning("SESSION", "No CSRF token found in cookies - some operations may fail")

    logger.info("SESSION", "Instagram session created successfully")
    return session


def get_reel_info(session, shortcode):
    """Get view count and details for a single reel"""
    url = f"https://www.instagram.com/api/v1/media/{shortcode}/info/"

    try:
        resp = session.get(url)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('items', [])
            if items:
                item = items[0]
                return {
                    'shortcode': shortcode,
                    'url': f"https://www.instagram.com/reel/{shortcode}/",
                    'views': item.get('play_count', 0) or item.get('view_count', 0),
                    'likes': item.get('like_count', 0),
                    'comments': item.get('comment_count', 0),
                    'caption': (item.get('caption', {}) or {}).get('text', ''),
                    'video_url': item.get('video_versions', [{}])[0].get('url') if item.get('video_versions') else None
                }
    except:
        pass

    # Fallback: scrape from page
    try:
        url = f"https://www.instagram.com/reel/{shortcode}/"
        resp = session.get(url)
        html = resp.text

        views_match = re.search(r'"play_count":\s*(\d+)', html) or re.search(r'"video_view_count":\s*(\d+)', html)
        likes_match = re.search(r'"like_count":\s*(\d+)', html)
        caption_match = re.search(r'"text":\s*"([^"]*)', html)

        return {
            'shortcode': shortcode,
            'url': f"https://www.instagram.com/reel/{shortcode}/",
            'views': int(views_match.group(1)) if views_match else 0,
            'likes': int(likes_match.group(1)) if likes_match else 0,
            'caption': caption_match.group(1) if caption_match else '',
            'video_url': None
        }
    except:
        return None


def get_user_reels(session, username, max_reels=50, progress_callback=None):
    """Get list of reel shortcodes from user profile"""
    reels = []

    # First get user ID
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    try:
        resp = session.get(url)

        # Check for non-200 status codes
        if resp.status_code == 404:
            return None, None, f"Account '@{username}' not found. Check the spelling."
        if resp.status_code == 401:
            return None, None, "Authentication failed. Your cookies may be expired - please re-export them."
        if resp.status_code == 429:
            return None, None, "Rate limited by Instagram. Wait a few minutes and try again."
        if resp.status_code != 200:
            return None, None, f"Instagram returned error {resp.status_code}. Try again later."

        # Try to parse JSON
        try:
            data = resp.json()
        except:
            return None, None, f"Account '@{username}' not found or cookies expired. Check spelling and re-export cookies if needed."

        user = data.get('data', {}).get('user')

        # Check if user exists in response
        if not user:
            return None, None, f"Account '@{username}' not found. Check the spelling."

        user_id = user.get('id')
        full_name = user.get('full_name', username)
        followers = user.get('edge_followed_by', {}).get('count', 0)
        is_private = user.get('is_private', False)

        if is_private:
            return None, None, f"Account '@{username}' is private. Can only scrape public profiles."

        profile = {'full_name': full_name, 'followers': followers, 'username': username}

    except Exception as e:
        error_str = str(e)
        if 'Expecting value' in error_str or 'JSONDecodeError' in error_str:
            return None, None, f"Account '@{username}' not found or cookies expired."
        return None, None, f"Failed to fetch account: {error_str}"

    # Get reels via clips endpoint
    max_id = None

    for page in range(max_reels // 12 + 1):
        url = "https://www.instagram.com/api/v1/clips/user/"
        data = {
            'target_user_id': user_id,
            'page_size': 12,
        }
        if max_id:
            data['max_id'] = max_id

        try:
            resp = session.post(url, data=data)
            if resp.status_code != 200:
                break

            result = resp.json()
            items = result.get('items', [])

            if not items:
                break

            for item in items:
                media = item.get('media', {})
                reel = {
                    'shortcode': media.get('code'),
                    'url': f"https://www.instagram.com/reel/{media.get('code')}/",
                    'views': media.get('play_count', 0),
                    'likes': media.get('like_count', 0),
                    'comments': media.get('comment_count', 0),
                    'caption': (media.get('caption', {}) or {}).get('text', ''),
                    'video_url': media.get('video_versions', [{}])[0].get('url') if media.get('video_versions') else None
                }
                reels.append(reel)

                if progress_callback:
                    progress_callback(f"Found {len(reels)} reels...")

            if len(reels) >= max_reels:
                break

            paging = result.get('paging_info', {})
            if not paging.get('more_available'):
                break
            max_id = paging.get('max_id')

            time.sleep(1)

        except Exception as e:
            break

    return reels, profile, None


def fetch_single_reel(shortcode, cookies_path, progress_callback=None):
    """
    Fetch a single Instagram reel by its shortcode using yt-dlp.

    Args:
        shortcode: The reel shortcode (e.g., 'DQ4Y454kUoa' from instagram.com/reel/DQ4Y454kUoa/)
        cookies_path: Path to cookies.txt file
        progress_callback: Optional callback for progress updates

    Returns:
        tuple: (reel_data, error_message)
        - reel_data: Dict with reel info if successful, None if failed
        - error_message: Error string if failed, None if successful
    """
    logger.info("REEL", f"Fetching single reel: {shortcode}")

    if progress_callback:
        progress_callback(f"Fetching reel {shortcode}...")

    reel_url = f"https://www.instagram.com/reel/{shortcode}/"

    try:
        # Use the same method that works for profile scrapes - get_reel_info()
        session = create_session(cookies_path)
        reel = get_reel_info(session, shortcode)

        if reel:
            # Add owner field (get_reel_info doesn't include it, but we can leave it as unknown)
            reel['owner'] = reel.get('owner', 'unknown')
            logger.info("REEL", f"Successfully fetched reel {shortcode}", {
                "views": reel.get('views', 0),
                "likes": reel.get('likes', 0)
            })
            return reel, None
        else:
            return None, f"Could not fetch reel '{shortcode}'. It may be private, deleted, or the shortcode is invalid."

    except Exception as e:
        logger.warning("REEL", f"Failed to fetch reel {shortcode}: {e}")
        return None, f"Failed to fetch reel: {e}"


def download_video(reel_url, output_path, cookies_file, video_url=None, max_retries=3):
    """Download video - tries direct URL first with retries, then yt-dlp"""
    shortcode = os.path.basename(str(output_path)).split('_')[-1].replace('.mp4', '')
    logger.debug("DOWNLOAD", f"Starting download for {shortcode}", {
        "output_path": str(output_path),
        "has_direct_url": bool(video_url)
    })

    # Try direct download from video_url first (fastest)
    if video_url:
        for attempt in range(max_retries):
            try:
                logger.debug("DOWNLOAD", f"Direct download attempt {attempt + 1}/{max_retries} for {shortcode}")
                resp = requests.get(video_url, stream=True, timeout=120)

                if resp.status_code == 200:
                    with open(output_path, 'wb') as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            f.write(chunk)

                    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                        file_size = os.path.getsize(output_path)
                        logger.info("DOWNLOAD", f"Direct download successful: {shortcode}", {
                            "file_size": file_size,
                            "attempts": attempt + 1
                        })
                        return True
                    else:
                        logger.warning("DOWNLOAD", f"Downloaded file empty or missing: {shortcode}")
                else:
                    logger.warning("DOWNLOAD", f"Direct download failed with status {resp.status_code}", {
                        "shortcode": shortcode,
                        "attempt": attempt + 1
                    })

            except requests.exceptions.Timeout:
                logger.warning("DOWNLOAD", f"Direct download timeout for {shortcode} (attempt {attempt + 1})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff

            except requests.exceptions.ConnectionError as e:
                logger.warning("DOWNLOAD", f"Connection error for {shortcode}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)

            except Exception as e:
                logger.warning("DOWNLOAD", f"Direct download exception for {shortcode}", {
                    "error": str(e),
                    "attempt": attempt + 1
                })
                if attempt < max_retries - 1:
                    time.sleep(1)

    # Fallback to yt-dlp (use python -m yt_dlp to avoid PATH issues on Windows)
    logger.debug("DOWNLOAD", f"Trying yt-dlp fallback for {shortcode}")
    for attempt in range(max_retries):
        try:
            import subprocess
            result = subprocess.run([
                sys.executable, '-m', 'yt_dlp',
                '--cookies', cookies_file,
                '-o', str(output_path),
                '--quiet',
                '--no-warnings',
                reel_url
            ], capture_output=True, text=True, timeout=180)

            if result.returncode == 0 and os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                logger.info("DOWNLOAD", f"yt-dlp download successful: {shortcode}", {
                    "file_size": file_size,
                    "attempts": attempt + 1
                })
                return True
            else:
                logger.warning("DOWNLOAD", f"yt-dlp failed for {shortcode}", {
                    "returncode": result.returncode,
                    "stderr": result.stderr[:200] if result.stderr else None,
                    "attempt": attempt + 1
                })

        except subprocess.TimeoutExpired:
            logger.warning("DOWNLOAD", f"yt-dlp timeout for {shortcode} (attempt {attempt + 1})")
        except Exception as e:
            logger.warning("DOWNLOAD", f"yt-dlp exception for {shortcode}", {
                "error": str(e),
                "attempt": attempt + 1
            })

        if attempt < max_retries - 1:
            time.sleep(2)

    error_code = logger.error("DOWNLOAD", f"All download methods failed for {shortcode}", {
        "reel_url": reel_url,
        "max_retries": max_retries
    })
    return False


def transcribe_video(video_path, model, output_path=None, progress_callback=None, video_index=None, total_videos=None):
    """Transcribe video using local Whisper with heartbeat updates."""
    import threading

    video_name = os.path.basename(str(video_path))
    logger.debug("TRANSCRIBE", f"Starting local transcription: {video_name}")

    # Heartbeat mechanism to show progress during long transcriptions
    stop_heartbeat = threading.Event()
    start_time = time.time()

    def heartbeat():
        """Send periodic updates while transcription is running"""
        tick = 0
        while not stop_heartbeat.is_set():
            stop_heartbeat.wait(5)  # Update every 5 seconds
            if not stop_heartbeat.is_set():
                tick += 1
                elapsed = int(time.time() - start_time)
                prefix = f"{video_index}/{total_videos}" if video_index and total_videos else ""
                if progress_callback:
                    progress_callback(f"Transcribing {prefix} - {elapsed}s elapsed (processing audio)...")
                logger.debug("TRANSCRIBE", f"Heartbeat: {video_name} - {elapsed}s elapsed")

    heartbeat_thread = None
    if progress_callback:
        heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
        heartbeat_thread.start()

    try:
        result = model.transcribe(str(video_path), language="en")
        transcript = result["text"].strip()

        # Save transcript if output path provided
        if output_path and transcript:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(transcript)

        elapsed = int(time.time() - start_time)
        logger.info("TRANSCRIBE", f"Local transcription complete: {video_name}", {
            "transcript_length": len(transcript) if transcript else 0,
            "elapsed_seconds": elapsed
        })
        return transcript

    except Exception as e:
        logger.error("TRANSCRIBE", f"Local transcription failed: {video_name}", exception=e)
        return None
    finally:
        stop_heartbeat.set()
        if heartbeat_thread:
            heartbeat_thread.join(timeout=1)


def transcribe_video_openai(video_path, api_key, output_path=None, max_retries=3):
    """Transcribe video using OpenAI Whisper API with retry logic."""
    video_name = os.path.basename(str(video_path))
    url = "https://api.openai.com/v1/audio/transcriptions"

    logger.debug("TRANSCRIBE", f"Starting OpenAI transcription: {video_name}")

    for attempt in range(max_retries):
        try:
            # Read the video file
            with open(video_path, 'rb') as audio_file:
                files = {
                    'file': (os.path.basename(video_path), audio_file, 'video/mp4')
                }
                data = {
                    'model': 'whisper-1',
                    'language': 'en',
                    'response_format': 'text'
                }
                headers = {
                    'Authorization': f'Bearer {api_key}'
                }

                response = requests.post(url, headers=headers, files=files, data=data, timeout=300)

                if response.status_code == 200:
                    transcript = response.text.strip()
                    logger.info("TRANSCRIBE", f"OpenAI transcription complete: {video_name}", {
                        "transcript_length": len(transcript),
                        "attempts": attempt + 1
                    })

                    # Save transcript if output path provided
                    if output_path and transcript:
                        with open(output_path, 'w', encoding='utf-8') as f:
                            f.write(transcript)

                    return transcript

                elif response.status_code == 429:
                    # Rate limited - wait and retry
                    logger.warning("TRANSCRIBE", f"OpenAI rate limited for {video_name}, waiting...", {
                        "attempt": attempt + 1
                    })
                    time.sleep(5 * (attempt + 1))  # Longer wait for rate limits

                elif response.status_code >= 500:
                    # Server error - retry
                    logger.warning("TRANSCRIBE", f"OpenAI server error {response.status_code}", {
                        "video": video_name,
                        "attempt": attempt + 1
                    })
                    time.sleep(2 ** attempt)

                else:
                    # Client error - don't retry
                    logger.error("TRANSCRIBE", f"OpenAI API error for {video_name}", {
                        "status_code": response.status_code,
                        "response": response.text[:200] if response.text else None
                    })
                    return None

        except requests.exceptions.Timeout:
            logger.warning("TRANSCRIBE", f"OpenAI timeout for {video_name} (attempt {attempt + 1})")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

        except Exception as e:
            logger.error("TRANSCRIBE", f"OpenAI exception for {video_name}", exception=e)
            if attempt < max_retries - 1:
                time.sleep(2)

    logger.error("TRANSCRIBE", f"OpenAI transcription failed after {max_retries} attempts: {video_name}")
    return None


def get_whisper_cache_dir():
    """Get whisper cache directory - use Windows path in WSL"""
    windows_cache = Path('/mnt/c/Users/Chris/.cache/whisper')
    linux_cache = Path.home() / '.cache' / 'whisper'
    return str(windows_cache) if windows_cache.exists() else str(linux_cache)


def load_whisper_model(model_name='small.en', max_retries=3, progress_callback=None):
    """Load Whisper model with retry logic - forces CPU mode for WSL compatibility"""
    if not WHISPER_AVAILABLE:
        logger.warning("WHISPER", "whisper module not available - install with: pip install openai-whisper")
        return None

    import torch
    last_error = None
    cache_dir = get_whisper_cache_dir()

    # Force CPU mode for WSL compatibility (CUDA often fails in WSL)
    device = "cpu"
    logger.info("WHISPER", f"Loading model '{model_name}'", {
        "cache_dir": cache_dir,
        "device": device
    })

    for attempt in range(max_retries):
        try:
            if progress_callback and attempt > 0:
                progress_callback(f"Loading Whisper model ({model_name}) - retry {attempt + 1}/{max_retries}...")

            # Force CPU to avoid CUDA issues in WSL
            model = whisper.load_model(model_name, device=device, download_root=cache_dir)
            if model is not None:
                logger.info("WHISPER", f"Model '{model_name}' loaded successfully", {
                    "device": device,
                    "attempts": attempt + 1
                })
                return model
            else:
                logger.warning("WHISPER", f"Model load returned None on attempt {attempt + 1}")

        except RuntimeError as e:
            # PyTorch/CUDA specific errors
            last_error = e
            error_str = str(e)
            logger.warning("WHISPER", f"RuntimeError on attempt {attempt + 1}", {
                "error": error_str[:200],
                "cuda_related": 'CUDA' in error_str or 'cuda' in error_str
            })

            if attempt < max_retries - 1:
                time.sleep(1)

        except Exception as e:
            last_error = e
            logger.warning("WHISPER", f"Load attempt {attempt + 1} failed", {
                "error_type": type(e).__name__,
                "error": str(e)[:200]
            })
            if attempt < max_retries - 1:
                time.sleep(1)

    if last_error:
        error_code = logger.error("WHISPER", f"All {max_retries} attempts failed", {
            "model_name": model_name,
            "last_error": str(last_error)[:200]
        }, exception=last_error)
        import traceback
        traceback.print_exc()
    return None


def run_scrape(username, cookies_path, max_reels=100, top_n=10, download=False,
               transcribe=False, whisper_model='small.en', transcribe_provider='local',
               openai_key=None, output_dir=None, progress_callback=None):
    """
    Main scraping function - returns results dict

    Args:
        transcribe_provider: 'local' for local Whisper, 'openai' for OpenAI API
        openai_key: OpenAI API key (required if transcribe_provider='openai')
    """
    import uuid

    scrape_id = str(uuid.uuid4())
    logger.info("SCRAPE", f"Starting scrape for @{username}", {
        "scrape_id": scrape_id,
        "max_reels": max_reels,
        "top_n": top_n,
        "download": download,
        "transcribe": transcribe,
        "transcribe_provider": transcribe_provider if transcribe else None
    })

    results = {
        'id': scrape_id,
        'username': username,
        'timestamp': datetime.now().isoformat(),
        'status': 'running',
        'error': None,
        'error_code': None,
        'profile': None,
        'total_reels': 0,
        'top_reels': [],
        'output_dir': None,
        'download_errors': [],
        'transcription_errors': []
    }

    # Check cookies
    if not os.path.exists(cookies_path):
        err = 'Cookies file not found. Please ensure cookies.txt exists.'
        error_code = logger.error("SCRAPE", f"Cookies file missing for @{username}", {
            "cookies_path": cookies_path
        })
        results['status'] = 'error'
        results['error_code'] = error_code
        results['error'] = f"[{error_code}] {err}"
        return results

    # Create session
    if progress_callback:
        progress_callback("Creating authenticated session...")
    try:
        session = create_session(cookies_path)
    except Exception as e:
        error_code = logger.error("SCRAPE", f"Session creation failed for @{username}", exception=e)
        results['status'] = 'error'
        results['error_code'] = error_code
        results['error'] = f"[{error_code}] Failed to create session: {e}"
        return results

    # Get reels
    if progress_callback:
        progress_callback(f"Fetching reels from @{username}...")

    logger.debug("SCRAPE", f"Fetching reels for @{username}")
    reels, profile, error = get_user_reels(session, username, max_reels, progress_callback)

    if error:
        error_code = logger.error("SCRAPE", f"Failed to fetch reels for @{username}", {
            "error": error
        })
        results['status'] = 'error'
        results['error_code'] = error_code
        results['error'] = f"[{error_code}] {error}"
        return results

    if not reels:
        err = 'No reels found. The account may have no reels or cookies may be expired.'
        error_code = logger.error("SCRAPE", f"No reels found for @{username}")
        results['status'] = 'error'
        results['error_code'] = error_code
        results['error'] = f"[{error_code}] {err}"
        return results

    results['profile'] = profile
    results['total_reels'] = len(reels)

    logger.info("SCRAPE", f"Found {len(reels)} reels for @{username}", {
        "full_name": profile.get('full_name') if profile else None,
        "followers": profile.get('followers') if profile else None
    })

    # Sort by views
    reels_sorted = sorted(reels, key=lambda x: x.get('views', 0), reverse=True)
    top_reels = reels_sorted[:top_n]

    logger.debug("SCRAPE", f"Selected top {len(top_reels)} reels by views")

    # Setup output directory
    if output_dir is None:
        output_dir = Path(f"output_{username}")
    else:
        output_dir = Path(output_dir) / f"output_{username}"
    output_dir.mkdir(parents=True, exist_ok=True)
    results['output_dir'] = str(output_dir)

    # Download videos if requested
    if download or transcribe:
        logger.info("SCRAPE", f"Starting video downloads for @{username}", {
            "video_count": len(top_reels)
        })

        if progress_callback:
            progress_callback("Downloading videos...")

        video_dir = output_dir / "videos"
        video_dir.mkdir(exist_ok=True)
        download_success = 0
        download_failed = 0

        for i, reel in enumerate(top_reels, 1):
            if progress_callback:
                progress_callback(f"Downloading video {i}/{len(top_reels)}...")

            filename = f"{i:02d}_{reel['views']}views_{reel['shortcode']}.mp4"
            filepath = video_dir / filename

            if download_video(reel['url'], filepath, cookies_path, reel.get('video_url')):
                reel['local_video'] = str(filepath)
                download_success += 1
            else:
                reel['local_video'] = None
                download_failed += 1
                results['download_errors'].append({
                    'shortcode': reel['shortcode'],
                    'error': 'Download failed after retries'
                })

            time.sleep(0.5)

        logger.info("SCRAPE", f"Downloads complete for @{username}", {
            "success": download_success,
            "failed": download_failed
        })

    # Transcribe if requested
    if transcribe:
        logger.info("SCRAPE", f"Starting transcriptions for @{username}", {
            "provider": transcribe_provider,
            "whisper_model": whisper_model if transcribe_provider == 'local' else None,
            "has_openai_key": bool(openai_key)
        })
        transcript_dir = output_dir / "transcripts"
        transcript_dir.mkdir(exist_ok=True)

        # Use OpenAI API for transcription
        if transcribe_provider == 'openai' and openai_key:
            logger.debug("SCRAPE", "Using OpenAI Whisper API for transcription")
            if progress_callback:
                progress_callback("Transcribing with OpenAI Whisper API...")

            transcription_success = 0
            for i, reel in enumerate(top_reels, 1):
                if progress_callback:
                    progress_callback(f"Transcribing {i}/{len(top_reels)} (OpenAI API)...")

                try:
                    video_path = reel.get('local_video')
                    if video_path and os.path.exists(video_path):
                        transcript_file = transcript_dir / f"{i:02d}_{reel['shortcode']}.txt"
                        transcript = transcribe_video_openai(video_path, openai_key, transcript_file)
                        reel['transcript'] = transcript
                        reel['transcript_file'] = str(transcript_file) if transcript else None
                        if transcript:
                            transcription_success += 1
                    else:
                        reel['transcript'] = None
                        reel['transcript_file'] = None
                        logger.warning("SCRAPE", f"Video file missing for transcription: {reel.get('shortcode')}")
                except Exception as e:
                    reel['transcript'] = None
                    reel['transcript_file'] = None
                    results['transcription_errors'].append({
                        'shortcode': reel.get('shortcode'),
                        'error': str(e)
                    })
                    logger.warning("SCRAPE", f"Transcription failed for {reel.get('shortcode')}", exception=e)
                    if progress_callback:
                        progress_callback(f"Transcription failed for {reel.get('shortcode')}, continuing...")

        # Use local Whisper model
        elif transcribe_provider == 'local' and WHISPER_AVAILABLE:
            logger.debug("SCRAPE", f"Using local Whisper with model: {whisper_model}")
            if progress_callback:
                progress_callback(f"Loading Whisper model ({whisper_model})...")

            try:
                model = load_whisper_model(whisper_model, max_retries=3, progress_callback=progress_callback)
            except Exception as e:
                model = None
                logger.error("SCRAPE", f"Exception during Whisper model load", exception=e)
                if progress_callback:
                    progress_callback(f"Failed to load Whisper model: {e}")

            if model:
                transcription_success = 0
                for i, reel in enumerate(top_reels, 1):
                    if progress_callback:
                        progress_callback(f"Transcribing {i}/{len(top_reels)} (Local)...")

                    try:
                        video_path = reel.get('local_video')
                        if video_path and os.path.exists(video_path):
                            transcript_file = transcript_dir / f"{i:02d}_{reel['shortcode']}.txt"
                            transcript = transcribe_video(
                                video_path, model, transcript_file,
                                progress_callback=progress_callback,
                                video_index=i,
                                total_videos=len(top_reels)
                            )
                            reel['transcript'] = transcript
                            reel['transcript_file'] = str(transcript_file) if transcript else None
                            if transcript:
                                transcription_success += 1
                        else:
                            logger.warning("SCRAPE", f"Video file missing for transcription: {reel.get('shortcode')}")
                            reel['transcript'] = None
                            reel['transcript_file'] = None
                    except Exception as e:
                        logger.warning("SCRAPE", f"Transcription failed for {reel.get('shortcode')}", exception=e)
                        reel['transcript'] = None
                        reel['transcript_file'] = None
                        results['transcription_errors'].append({
                            'shortcode': reel.get('shortcode'),
                            'error': str(e)
                        })
                        if progress_callback:
                            progress_callback(f"Transcription failed for {reel.get('shortcode')}, continuing...")

                logger.info("SCRAPE", f"Local transcriptions complete for @{username}", {
                    "success": transcription_success,
                    "total": len(top_reels)
                })
            else:
                # Model failed to load - mark all as no transcript but don't fail
                logger.warning("SCRAPE", "Whisper model failed to load - skipping transcriptions")
                for reel in top_reels:
                    reel['transcript'] = None
                    reel['transcript_file'] = None
        else:
            # No valid transcription method available
            logger.warning("SCRAPE", "No valid transcription method available", {
                "provider": transcribe_provider,
                "whisper_available": WHISPER_AVAILABLE,
                "has_openai_key": bool(openai_key)
            })
            for reel in top_reels:
                reel['transcript'] = None
                reel['transcript_file'] = None

        # Clean up videos if not keeping them
        if not download:
            logger.debug("SCRAPE", "Cleaning up temporary video files")
            if progress_callback:
                progress_callback("Cleaning up temporary videos...")
            for reel in top_reels:
                video_path = reel.get('local_video')
                if video_path and os.path.exists(video_path):
                    try:
                        os.remove(video_path)
                    except Exception as e:
                        logger.warning("SCRAPE", f"Failed to remove temp video: {video_path}")
                reel['local_video'] = None

    results['top_reels'] = top_reels

    # Determine final status based on errors
    has_download_errors = len(results.get('download_errors', [])) > 0
    has_transcription_errors = len(results.get('transcription_errors', [])) > 0

    if has_download_errors or has_transcription_errors:
        results['status'] = 'partial'  # Completed with some errors
    else:
        results['status'] = 'complete'

    # Log summary
    transcripts_count = sum(1 for r in top_reels if r.get('transcript'))
    videos_count = sum(1 for r in top_reels if r.get('local_video'))

    logger.info("SCRAPE", f"Scrape complete for @{username}", {
        "status": results['status'],
        "total_reels": len(top_reels),
        "videos_downloaded": videos_count if download else 0,
        "transcripts_generated": transcripts_count,
        "download_errors": len(results.get('download_errors', [])),
        "transcription_errors": len(results.get('transcription_errors', []))
    })

    # Save JSON report
    try:
        report_path = output_dir / f"reels_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        results['report_path'] = str(report_path)
        logger.debug("SCRAPE", f"Report saved to {report_path}")
    except Exception as e:
        logger.warning("SCRAPE", f"Failed to save report", exception=e)
        results['report_path'] = None

    return results
