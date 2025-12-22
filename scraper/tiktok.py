"""
ReelRecon - TikTok Scraping Module
TikTok profile and video extraction using yt-dlp
"""

import json
import os
import time
import hashlib
from datetime import datetime
from pathlib import Path

try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False


def generate_error_code(error_msg, prefix="TIK"):
    """Generate a trackable error code"""
    return f"{prefix}-{int(time.time()) % 100000:05d}-{hashlib.md5(error_msg.encode()).hexdigest()[:4].upper()}"


def scrape_tiktok_profile(username, cookies_file='tiktok_cookies.txt', max_videos=50,
                          headless=True, progress_callback=None):
    """
    Scrape a TikTok profile using yt-dlp

    Args:
        username: TikTok username (without @)
        cookies_file: Path to Netscape format cookies.txt file
        max_videos: Maximum number of videos to scrape
        headless: Ignored (yt-dlp doesn't use browser)
        progress_callback: Optional callback for progress updates

    Returns:
        dict with profile info and video list, or error
    """
    if not YT_DLP_AVAILABLE:
        return {
            'success': False,
            'error': 'yt-dlp not installed. Run: pip install yt-dlp',
            'error_code': generate_error_code('yt-dlp not installed', 'YDL')
        }

    # Check cookies file
    if not os.path.exists(cookies_file):
        err = f'TikTok cookies file not found: {cookies_file}'
        return {
            'success': False,
            'error': err,
            'error_code': generate_error_code(err, 'COOK')
        }

    if progress_callback:
        progress_callback(f"Fetching @{username} videos...")

    # yt-dlp options for playlist extraction
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,  # Get full video info
        'cookiefile': cookies_file,
        'playlistend': max_videos,
        'ignoreerrors': True,
    }

    videos_data = []
    profile_data = {}

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            profile_url = f'https://www.tiktok.com/@{username}'
            result = ydl.extract_info(profile_url, download=False)

            if not result:
                err = f"Could not fetch @{username} - profile may be private or not exist"
                return {
                    'success': False,
                    'error': err,
                    'error_code': generate_error_code(err, 'TIK')
                }

            # Extract profile info
            profile_data = {
                'username': username,
                'full_name': result.get('uploader', username),
                'uploader_id': result.get('uploader_id', username),
                'channel_url': result.get('channel_url', profile_url),
            }

            # Extract videos
            entries = result.get('entries', [])
            if progress_callback:
                progress_callback(f"Found {len(entries)} videos, processing...")

            for i, entry in enumerate(entries):
                if entry is None:
                    continue

                video = {
                    'id': entry.get('id', ''),
                    'url': entry.get('webpage_url', f"https://www.tiktok.com/@{username}/video/{entry.get('id', '')}"),
                    'description': entry.get('description', '') or entry.get('title', ''),
                    'create_time': entry.get('timestamp', 0),
                    'duration': entry.get('duration', 0),
                    'plays': entry.get('view_count', 0) or 0,
                    'likes': entry.get('like_count', 0) or 0,
                    'comments': entry.get('comment_count', 0) or 0,
                    'shares': entry.get('repost_count', 0) or 0,
                    'music': {
                        'title': entry.get('track', '') or entry.get('artist', ''),
                        'author': entry.get('artist', '')
                    },
                    'download_url': entry.get('url'),  # Direct video URL
                    'formats': entry.get('formats', []),
                    'source': 'tiktok'
                }
                videos_data.append(video)

                if progress_callback and (i + 1) % 10 == 0:
                    progress_callback(f"Processed {i + 1}/{len(entries)} videos...")

    except Exception as e:
        err = str(e)
        if 'private' in err.lower():
            err = f"Account @{username} appears to be private"
        elif 'not found' in err.lower() or '404' in err:
            err = f"Account @{username} not found"
        return {
            'success': False,
            'error': err,
            'error_code': generate_error_code(err, 'TIK')
        }

    if not videos_data:
        err = f"No videos found for @{username}"
        return {
            'success': False,
            'error': err,
            'error_code': generate_error_code(err, 'TIK')
        }

    return {
        'success': True,
        'profile': profile_data,
        'videos': videos_data,
        'total_videos': len(videos_data)
    }


def download_tiktok_video(video_url, output_path, cookies_file):
    """
    Download TikTok video using yt-dlp

    Args:
        video_url: URL of the TikTok video page
        output_path: Path to save the video
        cookies_file: Path to cookies.txt file

    Returns:
        True if successful, False otherwise
    """
    if not YT_DLP_AVAILABLE:
        return False

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'cookiefile': cookies_file,
        'outtmpl': str(output_path),
        'format': 'best',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        return os.path.exists(output_path)
    except Exception as e:
        print(f"[TIKTOK] Download failed: {e}")
        return False


def run_tiktok_scrape(username, cookies_path, max_videos=50, top_n=10, download=False,
                      transcribe=False, whisper_model='small.en', transcribe_provider='local',
                      openai_key=None, output_dir=None, headless=True, progress_callback=None):
    """
    Main TikTok scraping function - returns results dict
    Compatible with the same interface as run_scrape for Instagram
    """
    import uuid
    from .core import WHISPER_AVAILABLE, load_whisper_model, transcribe_video, transcribe_video_openai

    results = {
        'id': str(uuid.uuid4()),
        'username': username,
        'platform': 'tiktok',
        'timestamp': datetime.now().isoformat(),
        'status': 'running',
        'error': None,
        'profile': None,
        'total_reels': 0,
        'top_reels': [],
        'output_dir': None
    }

    # Scrape profile
    if progress_callback:
        progress_callback(f"Scraping TikTok @{username}...")

    scrape_result = scrape_tiktok_profile(
        username=username,
        cookies_file=cookies_path,
        max_videos=max_videos,
        headless=headless,
        progress_callback=progress_callback
    )

    if not scrape_result.get('success'):
        results['status'] = 'error'
        results['error_code'] = scrape_result.get('error_code', generate_error_code(str(scrape_result.get('error', 'Unknown error')), 'TIK'))
        results['error'] = f"[{results['error_code']}] {scrape_result.get('error', 'Unknown error')}"
        return results

    # Set profile and video count
    results['profile'] = scrape_result.get('profile', {})
    videos = scrape_result.get('videos', [])
    results['total_reels'] = len(videos)

    if not videos:
        err = 'No videos found. Check cookies or try again.'
        results['status'] = 'error'
        results['error_code'] = generate_error_code(err, 'TIK')
        results['error'] = f"[{results['error_code']}] {err}"
        return results

    # Sort by plays (views)
    videos_sorted = sorted(videos, key=lambda x: x.get('plays', 0) or 0, reverse=True)
    top_videos = videos_sorted[:top_n]

    if progress_callback:
        progress_callback(f"Top {len(top_videos)} videos selected by view count...")

    # Convert to reel format for compatibility
    top_reels = []
    for video in top_videos:
        reel = {
            'shortcode': video.get('id', ''),
            'video_id': video.get('id', ''),
            'url': video.get('url', ''),
            'views': video.get('plays', 0) or 0,
            'likes': video.get('likes', 0) or 0,
            'comments': video.get('comments', 0) or 0,
            'shares': video.get('shares', 0) or 0,
            'caption': video.get('description', ''),
            'video_url': video.get('download_url'),
            'create_time': video.get('create_time', 0),
            'duration': video.get('duration', 0),
            'source': 'tiktok'
        }
        top_reels.append(reel)

    # Setup output directory
    if output_dir is None:
        output_dir = Path(f"output_{username}_tiktok")
    else:
        output_dir = Path(output_dir)
        if not str(output_dir).endswith(f'_{username}_tiktok'):
            output_dir = output_dir / f"output_{username}_tiktok"
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

            if download_tiktok_video(reel['url'], str(filepath), cookies_path):
                reel['local_video'] = str(filepath)
            else:
                reel['local_video'] = None

            time.sleep(0.5)

    # Transcribe if requested
    if transcribe:
        print(f"[TIKTOK] Transcription requested: provider={transcribe_provider}, whisper_model={whisper_model}, has_openai_key={bool(openai_key)}")
        transcript_dir = output_dir / "transcripts"
        transcript_dir.mkdir(exist_ok=True)

        # Use OpenAI API for transcription
        if transcribe_provider == 'openai' and openai_key:
            print(f"[TIKTOK] Using OpenAI provider for transcription")
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
            print(f"[TIKTOK] Using local Whisper provider with model: {whisper_model}")
            if progress_callback:
                progress_callback(f"Loading Whisper model ({whisper_model})...")

            try:
                model = load_whisper_model(whisper_model, max_retries=3, progress_callback=progress_callback)
            except Exception as e:
                model = None
                print(f"[WHISPER] Exception during model load: {e}")
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
                # Model failed to load
                for reel in top_reels:
                    reel['transcript'] = None
                    reel['transcript_file'] = None
        else:
            # No valid transcription method
            print(f"[TIKTOK] WARNING: No valid transcription method! provider={transcribe_provider}, WHISPER_AVAILABLE={WHISPER_AVAILABLE}, has_openai_key={bool(openai_key)}")
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

    # Log summary
    transcripts_count = sum(1 for r in top_reels if r.get('transcript'))
    print(f"[TIKTOK] Complete: {len(top_reels)} videos, {transcripts_count} transcripts generated")

    # Save JSON report
    try:
        report_path = output_dir / f"tiktok_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        results['report_path'] = str(report_path)
    except Exception as e:
        results['report_path'] = None

    return results
