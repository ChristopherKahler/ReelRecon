"""
ReelRecon - Core Scraping Module
Instagram reel extraction and transcription
"""

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import requests

# Optional: Whisper for transcription
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


def load_cookies(filepath):
    """Load cookies from Netscape cookies.txt format"""
    cookies = {}
    with open(filepath, 'r') as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            parts = line.strip().split('\t')
            if len(parts) >= 7:
                name, value = parts[5], parts[6]
                cookies[name] = value
    return cookies


def create_session(cookies_path):
    """Create an authenticated Instagram session"""
    cookies = load_cookies(cookies_path)
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
                    'caption': (item.get('caption', {}) or {}).get('text', '')[:200],
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
        caption_match = re.search(r'"text":\s*"([^"]{0,200})', html)

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
                    'caption': (media.get('caption', {}) or {}).get('text', '')[:200],
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


def download_video(reel_url, output_path, cookies_file, video_url=None):
    """Download video - tries direct URL first, then yt-dlp"""
    # Try direct download from video_url first (fastest)
    if video_url:
        try:
            resp = requests.get(video_url, stream=True, timeout=120)
            if resp.status_code == 200:
                with open(output_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    return True
        except:
            pass

    # Fallback to yt-dlp
    try:
        import subprocess
        result = subprocess.run([
            'yt-dlp',
            '--cookies', cookies_file,
            '-o', str(output_path),
            '--quiet',
            '--no-warnings',
            reel_url
        ], capture_output=True, text=True, timeout=120)

        if result.returncode == 0 and os.path.exists(output_path):
            return True
    except:
        pass

    return False


def transcribe_video(video_path, model, output_path=None):
    """Transcribe video using local Whisper. Returns transcript text."""
    try:
        result = model.transcribe(str(video_path), language="en")
        transcript = result["text"].strip()

        # Save transcript if output path provided
        if output_path and transcript:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(transcript)

        return transcript
    except Exception as e:
        return None


def transcribe_video_openai(video_path, api_key, output_path=None):
    """Transcribe video using OpenAI Whisper API. Returns transcript text."""
    try:
        # OpenAI Whisper API endpoint
        url = "https://api.openai.com/v1/audio/transcriptions"

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

                # Save transcript if output path provided
                if output_path and transcript:
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(transcript)

                return transcript
            else:
                return None
    except Exception as e:
        return None


def load_whisper_model(model_name='small.en'):
    """Load Whisper model"""
    if not WHISPER_AVAILABLE:
        return None
    try:
        return whisper.load_model(model_name)
    except:
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

    results = {
        'id': str(uuid.uuid4()),
        'username': username,
        'timestamp': datetime.now().isoformat(),
        'status': 'running',
        'error': None,
        'profile': None,
        'total_reels': 0,
        'top_reels': [],
        'output_dir': None
    }

    # Check cookies
    if not os.path.exists(cookies_path):
        results['status'] = 'error'
        results['error'] = 'Cookies file not found'
        return results

    # Create session
    if progress_callback:
        progress_callback("Creating session...")
    session = create_session(cookies_path)

    # Get reels
    if progress_callback:
        progress_callback(f"Fetching reels from @{username}...")
    reels, profile, error = get_user_reels(session, username, max_reels, progress_callback)

    if error:
        results['status'] = 'error'
        results['error'] = error
        return results

    if not reels:
        results['status'] = 'error'
        results['error'] = 'No reels found. Check cookies or try again.'
        return results

    results['profile'] = profile
    results['total_reels'] = len(reels)

    # Sort by views
    reels_sorted = sorted(reels, key=lambda x: x.get('views', 0), reverse=True)
    top_reels = reels_sorted[:top_n]

    # Setup output directory
    if output_dir is None:
        output_dir = Path(f"output_{username}")
    else:
        output_dir = Path(output_dir) / f"output_{username}"
    output_dir.mkdir(parents=True, exist_ok=True)
    results['output_dir'] = str(output_dir)

    # Download videos if requested
    if download or transcribe:
        if progress_callback:
            progress_callback("Downloading videos...")

        video_dir = output_dir / "videos"
        video_dir.mkdir(exist_ok=True)

        for i, reel in enumerate(top_reels, 1):
            if progress_callback:
                progress_callback(f"Downloading video {i}/{len(top_reels)}...")

            filename = f"{i:02d}_{reel['views']}views_{reel['shortcode']}.mp4"
            filepath = video_dir / filename

            if download_video(reel['url'], filepath, cookies_path, reel.get('video_url')):
                reel['local_video'] = str(filepath)
            else:
                reel['local_video'] = None

            time.sleep(0.5)

    # Transcribe if requested
    if transcribe:
        transcript_dir = output_dir / "transcripts"
        transcript_dir.mkdir(exist_ok=True)

        # Use OpenAI API for transcription
        if transcribe_provider == 'openai' and openai_key:
            if progress_callback:
                progress_callback("Transcribing with OpenAI Whisper API...")

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
                    else:
                        reel['transcript'] = None
                        reel['transcript_file'] = None
                except Exception as e:
                    reel['transcript'] = None
                    reel['transcript_file'] = None
                    if progress_callback:
                        progress_callback(f"Transcription failed for {reel.get('shortcode')}, continuing...")

        # Use local Whisper model
        elif transcribe_provider == 'local' and WHISPER_AVAILABLE:
            if progress_callback:
                progress_callback(f"Loading Whisper model ({whisper_model})...")

            try:
                model = load_whisper_model(whisper_model)
            except Exception as e:
                model = None
                if progress_callback:
                    progress_callback(f"Failed to load Whisper model: {e}")

            if model:
                for i, reel in enumerate(top_reels, 1):
                    if progress_callback:
                        progress_callback(f"Transcribing {i}/{len(top_reels)} (Local)...")

                    try:
                        video_path = reel.get('local_video')
                        if video_path and os.path.exists(video_path):
                            transcript_file = transcript_dir / f"{i:02d}_{reel['shortcode']}.txt"
                            transcript = transcribe_video(video_path, model, transcript_file)
                            reel['transcript'] = transcript
                            reel['transcript_file'] = str(transcript_file) if transcript else None
                        else:
                            reel['transcript'] = None
                            reel['transcript_file'] = None
                    except Exception as e:
                        reel['transcript'] = None
                        reel['transcript_file'] = None
                        if progress_callback:
                            progress_callback(f"Transcription failed for {reel.get('shortcode')}, continuing...")
            else:
                # Model failed to load - mark all as no transcript but don't fail
                for reel in top_reels:
                    reel['transcript'] = None
                    reel['transcript_file'] = None
        else:
            # No valid transcription method available
            for reel in top_reels:
                reel['transcript'] = None
                reel['transcript_file'] = None

        # Clean up videos if not keeping them
        if not download:
            if progress_callback:
                progress_callback("Cleaning up temporary videos...")
            for reel in top_reels:
                video_path = reel.get('local_video')
                if video_path and os.path.exists(video_path):
                    try:
                        os.remove(video_path)
                    except:
                        pass
                reel['local_video'] = None

    results['top_reels'] = top_reels
    results['status'] = 'complete'

    # Save JSON report
    try:
        report_path = output_dir / f"reels_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        results['report_path'] = str(report_path)
    except Exception as e:
        # Report saving failed but we still have results
        results['report_path'] = None

    return results
