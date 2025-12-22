"""
ReelRecon - Tactical Content Intelligence
Instagram reel scraping with AI-powered script rewriting

V2.0 - Robust error handling, persistent state, comprehensive logging
"""

import json
import os
import uuid
import subprocess
import time
import atexit
from datetime import datetime
from pathlib import Path
from threading import Thread

from flask import Flask, render_template, request, jsonify, send_file, Response
import requests as http_requests

# Import scrapers
from scraper.core import run_scrape, WHISPER_AVAILABLE, download_video, create_session
from scraper.tiktok import run_tiktok_scrape

# Import utilities for robust error handling
from utils import get_logger, ScrapeStateManager, ScrapePhase, ScrapeState
from utils import check_for_updates, run_update, get_current_version, get_git_status

# Import skeleton ripper
from skeleton_ripper import (
    SkeletonRipperPipeline,
    create_job_config,
    JobProgress,
    get_available_providers
)

# Configuration
BASE_DIR = Path(__file__).parent.resolve()

# Initialize logger and state manager
logger = get_logger()
state_manager = ScrapeStateManager(BASE_DIR / "state")

# Initialize Flask with explicit paths
app = Flask(__name__,
            static_folder=str(BASE_DIR / 'static'),
            template_folder=str(BASE_DIR / 'templates'))
app.secret_key = os.urandom(24)
OUTPUT_DIR = BASE_DIR / "output"
TIKTOK_OUTPUT_DIR = BASE_DIR / "output_tiktok"
COOKIES_FILE = BASE_DIR / "cookies.txt"
TIKTOK_COOKIES_FILE = BASE_DIR / "tiktok_cookies.txt"
HISTORY_FILE = BASE_DIR / "scrape_history.json"
CONFIG_FILE = BASE_DIR / "config.json"

# Default configuration
DEFAULT_CONFIG = {
    'ai_provider': 'copy',  # copy, local, openai, anthropic, google
    'local_model': '',
    'openai_model': 'gpt-4o-mini',
    'anthropic_model': 'claude-3-5-haiku-20241022',
    'google_model': 'gemini-1.5-flash',
    'openai_key': '',
    'anthropic_key': '',
    'google_key': '',
    'output_directory': ''  # Empty = use default (BASE_DIR/output)
}

# Universal prompt template
UNIVERSAL_PROMPT_TEMPLATE = """Rewrite this viral Instagram reel script.

CRITICAL RULES - FOLLOW EXACTLY:
1. Output ONLY the script text - no introductions, explanations, headers, or commentary
2. Do NOT say "Here's your script", "Sure!", "Great!", or any preamble - start directly with the script
3. Keep it SHORT: 30-60 seconds spoken (75-150 words max)
4. Match the original's hook pattern and pacing but make content unique
5. Start your response with the first word of the script, nothing else

ORIGINAL ({views:,} views):
{transcript}
"""

# Active scrapes (for progress tracking)
# Now backed by persistent state_manager for crash recovery
active_scrapes = {}

# Cleanup handler for graceful shutdown
def cleanup_on_exit():
    """Mark any running scrapes as interrupted on server shutdown"""
    logger.info("SYSTEM", "Server shutting down, cleaning up active scrapes")
    for scrape_id in list(active_scrapes.keys()):
        if active_scrapes[scrape_id].get('status') in ('starting', 'running'):
            state_manager.abort_job(scrape_id, "Server shutdown")

atexit.register(cleanup_on_exit)


def load_config():
    """Load configuration from JSON file"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                # Merge with defaults to handle new fields
                config = DEFAULT_CONFIG.copy()
                config.update(saved)
                return config
        except:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config):
    """Save configuration to JSON file"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)


def get_output_directory(platform='instagram'):
    """Get the configured output directory, or default if not set"""
    config = load_config()
    custom_dir = config.get('output_directory', '').strip()
    if custom_dir:
        output_path = Path(custom_dir)
        if platform == 'tiktok':
            output_path = output_path / 'tiktok'
        output_path.mkdir(parents=True, exist_ok=True)
        return output_path
    return TIKTOK_OUTPUT_DIR if platform == 'tiktok' else OUTPUT_DIR


def get_ollama_models():
    """Get list of available Ollama models"""
    try:
        resp = http_requests.get('http://localhost:11434/api/tags', timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            models = [m['name'] for m in data.get('models', [])]
            return sorted(models)
    except:
        pass
    return []


def generate_ai_prompt(reel):
    """Generate a universal AI prompt for rewriting a transcript"""
    transcript = reel.get('transcript') or reel.get('caption') or 'No transcript available'
    return UNIVERSAL_PROMPT_TEMPLATE.format(
        views=reel.get('views', 0),
        likes=reel.get('likes', 0),
        transcript=transcript,
        url=reel.get('url', '')
    )


def strip_thinking_output(text):
    """
    Strip thinking model output (DeepSeek, etc.) from responses.
    Removes <think>...</think> blocks and similar patterns.
    """
    import re
    if not text:
        return text

    # Remove <think>...</think> blocks (DeepSeek R1, etc.)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)

    # Remove <thinking>...</thinking> blocks (alternative format)
    text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL | re.IGNORECASE)

    # Remove any remaining unclosed thinking tags and content before actual response
    text = re.sub(r'^.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'^.*?</thinking>', '', text, flags=re.DOTALL | re.IGNORECASE)

    return text.strip()


def call_ollama(prompt, model):
    """Call Ollama API for local LLM"""
    try:
        resp = http_requests.post(
            'http://localhost:11434/api/generate',
            json={'model': model, 'prompt': prompt, 'stream': False},
            timeout=120
        )
        if resp.status_code == 200:
            result = resp.json().get('response', '')
            return strip_thinking_output(result)
    except Exception as e:
        return f"Error: {e}"
    return "Error: Failed to get response from Ollama"


def call_openai(prompt, model, api_key):
    """Call OpenAI API"""
    try:
        resp = http_requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 2000
            },
            timeout=60
        )
        if resp.status_code == 200:
            result = resp.json()['choices'][0]['message']['content']
            return strip_thinking_output(result)
        else:
            return f"Error: {resp.status_code} - {resp.text}"
    except Exception as e:
        return f"Error: {e}"


def call_anthropic(prompt, model, api_key):
    """Call Anthropic API"""
    try:
        resp = http_requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'Content-Type': 'application/json'
            },
            json={
                'model': model,
                'max_tokens': 2000,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=60
        )
        if resp.status_code == 200:
            result = resp.json()['content'][0]['text']
            return strip_thinking_output(result)
        else:
            return f"Error: {resp.status_code} - {resp.text}"
    except Exception as e:
        return f"Error: {e}"


def call_google(prompt, model, api_key):
    """Call Google Gemini API"""
    try:
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}'
        resp = http_requests.post(
            url,
            headers={'Content-Type': 'application/json'},
            json={
                'contents': [{'parts': [{'text': prompt}]}]
            },
            timeout=60
        )
        if resp.status_code == 200:
            result = resp.json()['candidates'][0]['content']['parts'][0]['text']
            return strip_thinking_output(result)
        else:
            return f"Error: {resp.status_code} - {resp.text}"
    except Exception as e:
        return f"Error: {e}"


def load_history():
    """Load scrape history from JSON file"""
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []


def save_history(history):
    """Save scrape history to JSON file"""
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def add_to_history(scrape_result, include_errors: bool = False):
    """
    Add a scrape result to history.
    Now saves ALL results including errors and partial completions.
    """
    history = load_history()
    platform = scrape_result.get('platform', 'instagram')
    top_reels = scrape_result.get('top_reels', []) or scrape_result.get('top_videos', [])
    status = scrape_result.get('status', 'unknown')

    # Log what we're saving
    transcripts_count = sum(1 for r in top_reels if r.get('transcript'))
    logger.info("HISTORY", f"Saving scrape to history: {platform} @{scrape_result.get('username')}", {
        "reels_count": len(top_reels),
        "transcripts_count": transcripts_count,
        "status": status
    })

    # Keep essential data for history
    entry = {
        'id': scrape_result.get('id', str(uuid.uuid4())),
        'username': scrape_result.get('username'),
        'timestamp': scrape_result.get('timestamp'),
        'profile': scrape_result.get('profile'),
        'total_reels': scrape_result.get('total_reels') or scrape_result.get('total_videos'),
        'top_count': len(top_reels),
        'top_reels': top_reels,
        'output_dir': scrape_result.get('output_dir'),
        'platform': platform,
        'status': status
    }

    # Include error info if present
    if scrape_result.get('error_code'):
        entry['error_code'] = scrape_result.get('error_code')
        entry['error'] = scrape_result.get('error')

    history.insert(0, entry)
    # Keep last 50 scrapes
    history = history[:50]
    save_history(history)
    logger.info("HISTORY", f"Saved history with {len(history)} entries")


@app.route('/')
def index():
    """Main page"""
    history = load_history()
    cookies_exist = COOKIES_FILE.exists()
    tiktok_cookies_exist = TIKTOK_COOKIES_FILE.exists()
    return render_template('index.html',
                         history=history,
                         cookies_exist=cookies_exist,
                         tiktok_cookies_exist=tiktok_cookies_exist,
                         whisper_available=WHISPER_AVAILABLE)


@app.route('/skeleton-ripper')
def skeleton_ripper_page():
    """Skeleton Ripper analysis page"""
    return render_template('skeleton_ripper.html')


@app.route('/api/scrape', methods=['POST'])
def start_scrape():
    """Start a new scrape for Instagram or TikTok"""
    data = request.json
    username = data.get('username', '').strip().lstrip('@')
    platform = data.get('platform', 'instagram').lower()

    if not username:
        error_code = logger.error("API", "Scrape request missing username")
        return jsonify({'error': 'Username required', 'error_code': error_code}), 400

    # Check cookies based on platform
    cookies_file = TIKTOK_COOKIES_FILE if platform == 'tiktok' else COOKIES_FILE
    if not cookies_file.exists():
        error_code = logger.error("API", f"Cookies file not found for {platform}", {
            "cookies_file": str(cookies_file)
        })
        return jsonify({
            'error': f'{platform.title()} cookies file not found ({cookies_file.name})',
            'error_code': error_code
        }), 400

    # Create scrape ID
    scrape_id = str(uuid.uuid4())
    logger.info("SCRAPE", f"Creating scrape job for @{username} on {platform}", {
        "scrape_id": scrape_id,
        "username": username,
        "platform": platform
    })

    # Create persistent job in state manager (survives server restarts)
    scrape_config = {
        'username': username,
        'platform': platform,
        'max_reels': data.get('max_reels', 100),
        'top_n': data.get('top_n', 10),
        'download': data.get('download', False),
        'transcribe': data.get('transcribe', False),
        'transcribe_provider': data.get('transcribe_provider', 'local'),
        'whisper_model': data.get('whisper_model', 'small.en')
    }
    state_manager.create_job(scrape_id, username, platform, scrape_config)

    # Also maintain in-memory cache for fast access
    active_scrapes[scrape_id] = {
        'status': 'starting',
        'progress': f'Initializing {platform.title()} scrape...',
        'progress_pct': 0,
        'phase': 'initializing',
        'result': None,
        'platform': platform,
        'errors': []
    }
    logger.debug("SCRAPE", f"Active scrapes: {list(active_scrapes.keys())}")

    # Get transcription settings
    transcribe_provider = data.get('transcribe_provider', 'local')
    transcribe_requested = data.get('transcribe', False)
    openai_key = None
    if transcribe_provider == 'openai':
        config = load_config()
        openai_key = config.get('openai_key')

    logger.info("SCRAPE", f"{platform} @{username}", {
        "transcribe": transcribe_requested,
        "provider": transcribe_provider,
        "has_key": bool(openai_key)
    })

    # Run scrape in background thread with comprehensive error handling
    def run_in_background():
        """Background scrape with robust error handling and state persistence"""
        accumulated_errors = []

        def progress_callback(msg, phase=None, progress_pct=None):
            """Enhanced progress callback with phase and percentage tracking"""
            try:
                active_scrapes[scrape_id]['progress'] = msg
                active_scrapes[scrape_id]['status'] = 'running'

                if phase:
                    active_scrapes[scrape_id]['phase'] = phase
                    state_manager.update_progress(
                        scrape_id,
                        ScrapePhase(phase) if isinstance(phase, str) else phase,
                        progress_pct or 0,
                        msg
                    )
                elif progress_pct is not None:
                    active_scrapes[scrape_id]['progress_pct'] = progress_pct

                logger.progress(scrape_id, active_scrapes[scrape_id].get('phase', 'processing'),
                              progress_pct or 0, msg)
            except Exception as e:
                logger.warning("SCRAPE", f"Progress callback error: {e}")

        def error_callback(error_msg, error_code=None, is_fatal=False):
            """Track errors during scrape"""
            code = error_code or logger.error("SCRAPE", error_msg, {"scrape_id": scrape_id})
            error_entry = {
                'code': code,
                'message': error_msg,
                'timestamp': datetime.now().isoformat(),
                'fatal': is_fatal
            }
            accumulated_errors.append(error_entry)
            active_scrapes[scrape_id]['errors'] = accumulated_errors
            state_manager.add_error(scrape_id, code, error_msg, is_fatal)

        try:
            logger.scrape_event(scrape_id, "Starting scrape", {"platform": platform, "username": username})

            if platform == 'tiktok':
                # TikTok scrape
                result = run_tiktok_scrape(
                    username=username,
                    cookies_path=str(TIKTOK_COOKIES_FILE),
                    max_videos=data.get('max_reels', 50),
                    top_n=data.get('top_n', 10),
                    download=data.get('download', False),
                    transcribe=data.get('transcribe', False),
                    whisper_model=data.get('whisper_model', 'small.en'),
                    transcribe_provider=transcribe_provider,
                    openai_key=openai_key,
                    output_dir=str(get_output_directory('tiktok')),
                    headless=True,
                    progress_callback=progress_callback
                )
            else:
                # Instagram scrape
                result = run_scrape(
                    username=username,
                    cookies_path=str(COOKIES_FILE),
                    max_reels=data.get('max_reels', 100),
                    top_n=data.get('top_n', 10),
                    download=data.get('download', False),
                    transcribe=data.get('transcribe', False),
                    whisper_model=data.get('whisper_model', 'small.en'),
                    transcribe_provider=transcribe_provider,
                    openai_key=openai_key,
                    output_dir=str(get_output_directory('instagram')),
                    progress_callback=progress_callback
                )

            # Add platform and any accumulated errors to result
            result['platform'] = platform
            if accumulated_errors:
                result['errors'] = accumulated_errors

            # Update in-memory state
            active_scrapes[scrape_id]['result'] = result
            active_scrapes[scrape_id]['status'] = result.get('status', 'complete')
            active_scrapes[scrape_id]['progress_pct'] = 100

            # Determine final state
            had_errors = len(accumulated_errors) > 0
            if result.get('status') == 'error':
                state_manager.fail_job(scrape_id, result.get('error_code', 'UNKNOWN'),
                                      result.get('error', 'Unknown error'))
            else:
                state_manager.complete_job(scrape_id, result, had_errors)

            # ALWAYS save to history now (including errors and partial results)
            add_to_history(result, include_errors=True)

            logger.scrape_event(scrape_id, "Scrape completed", {
                "status": result.get('status'),
                "reels_count": len(result.get('top_reels', [])),
                "errors_count": len(accumulated_errors)
            })

        except Exception as e:
            import traceback
            error_msg = str(e)
            prefix = "TIK" if platform == 'tiktok' else "IG"
            error_code = logger.critical(prefix, f"Scrape failed: {error_msg}", {
                "scrape_id": scrape_id,
                "username": username
            }, exception=e)

            # Update in-memory state
            active_scrapes[scrape_id]['status'] = 'error'
            active_scrapes[scrape_id]['result'] = {
                'id': scrape_id,
                'status': 'error',
                'error': f'[{error_code}] {error_msg}',
                'error_code': error_code,
                'platform': platform,
                'username': username,
                'timestamp': datetime.now().isoformat(),
                'errors': accumulated_errors + [{'code': error_code, 'message': error_msg, 'fatal': True}]
            }
            active_scrapes[scrape_id]['progress'] = f'Error [{error_code}]: {error_msg}'

            # Update persistent state
            state_manager.fail_job(scrape_id, error_code, error_msg)

            # Save error to history so user can see what happened
            add_to_history(active_scrapes[scrape_id]['result'], include_errors=True)

    thread = Thread(target=run_in_background, daemon=True)
    thread.start()

    return jsonify({'scrape_id': scrape_id, 'platform': platform})


@app.route('/api/scrape/<scrape_id>/status')
def scrape_status(scrape_id):
    """Get scrape status - checks memory first, then persistent state"""
    # First check in-memory active scrapes
    if scrape_id in active_scrapes:
        scrape = active_scrapes[scrape_id]
        return jsonify({
            'status': scrape['status'],
            'progress': scrape['progress'],
            'result': scrape['result'],
            'error_code': scrape.get('error_code'),
            'error_message': scrape.get('error_message')
        })

    # Fallback to persistent state manager (handles server restarts)
    job_status = state_manager.get_job_status(scrape_id)
    if job_status:
        logger.debug("API", f"Scrape {scrape_id} recovered from persistent state", {
            "status": job_status.get('status')
        })
        return jsonify({
            'status': job_status['status'],
            'progress': job_status['progress'],
            'progress_pct': job_status.get('progress_pct', 0),
            'phase': job_status.get('phase'),
            'current_item': job_status.get('current_item', 0),
            'total_items': job_status.get('total_items', 0),
            'result': job_status.get('result'),
            'error_code': job_status.get('error_code'),
            'error_message': job_status.get('error_message'),
            'errors': job_status.get('errors', [])
        })

    logger.warning("API", f"Scrape {scrape_id} not found in memory or persistent state")
    return jsonify({'error': 'Scrape not found', 'error_code': 'SCRAPE-NOT-FOUND'}), 404


@app.route('/api/scrape/<scrape_id>/abort', methods=['POST'])
def abort_scrape(scrape_id):
    """Abort a running scrape"""
    if scrape_id in active_scrapes:
        active_scrapes[scrape_id]['status'] = 'aborted'
        state_manager.abort_job(scrape_id, "User cancelled")
        logger.info("API", f"Scrape {scrape_id} aborted by user")
        return jsonify({'success': True, 'message': 'Scrape aborted'})

    return jsonify({'error': 'Scrape not found or already completed'}), 404


@app.route('/api/errors/<error_code>')
def get_error_details(error_code):
    """Get detailed error information by error code"""
    error_info = logger.get_error_details(error_code)
    if error_info:
        return jsonify({
            'error_code': error_code,
            'category': error_info.get('category'),
            'message': error_info.get('message'),
            'timestamp': error_info.get('timestamp'),
            'details': error_info.get('data', {})
        })
    return jsonify({'error': 'Error code not found'}), 404


@app.route('/api/errors/recent')
def get_recent_errors():
    """Get recent errors for debugging"""
    errors = logger.get_recent_errors(limit=20)
    return jsonify([
        {
            'error_code': code,
            'category': info.get('category'),
            'message': info.get('message'),
            'timestamp': info.get('timestamp'),
            'critical': info.get('critical', False)
        }
        for code, info in errors
    ])


@app.route('/api/scrapes/active')
def get_active_scrapes():
    """Get all active/running scrapes"""
    return jsonify(state_manager.get_active_jobs())


@app.route('/api/history')
def get_history():
    """Get scrape history"""
    return jsonify(load_history())


@app.route('/api/history/<scrape_id>', methods=['DELETE'])
def delete_history_item(scrape_id):
    """Delete a history item"""
    history = load_history()
    history = [h for h in history if h.get('id') != scrape_id]
    save_history(history)
    return jsonify({'success': True})


@app.route('/api/history/clear', methods=['POST'])
def clear_history():
    """Clear all history"""
    save_history([])
    return jsonify({'success': True})


@app.route('/api/download/video/<scrape_id>/<shortcode>')
def download_video_file(scrape_id, shortcode):
    """Download a video file"""
    history = load_history()
    scrape = next((h for h in history if h.get('id') == scrape_id), None)

    if not scrape:
        return jsonify({'error': 'Scrape not found'}), 404

    reel = next((r for r in scrape.get('top_reels', []) if r.get('shortcode') == shortcode), None)

    if not reel:
        return jsonify({'error': 'Reel not found'}), 404

    video_path = reel.get('local_video')
    if video_path and os.path.exists(video_path):
        return send_file(video_path, as_attachment=True)

    return jsonify({'error': 'Video file not found'}), 404


@app.route('/api/fetch/video/<scrape_id>/<shortcode>', methods=['POST'])
def fetch_video(scrape_id, shortcode):
    """Fetch/download a video on-demand"""
    history = load_history()
    scrape = next((h for h in history if h.get('id') == scrape_id), None)

    if not scrape:
        return jsonify({'error': 'Scrape not found'}), 404

    reel_idx = None
    reel = None
    for i, r in enumerate(scrape.get('top_reels', [])):
        if r.get('shortcode') == shortcode:
            reel_idx = i
            reel = r
            break

    if not reel:
        return jsonify({'error': 'Reel not found'}), 404

    # Create output directory - use scrape's output_dir if set, otherwise use configured output directory
    configured_output = get_output_directory()
    output_dir = Path(scrape.get('output_dir', configured_output / f"output_{scrape.get('username')}"))
    video_dir = output_dir / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)

    # Download video
    filename = f"{reel_idx + 1:02d}_{reel.get('views', 0)}views_{shortcode}.mp4"
    filepath = video_dir / filename

    session = create_session(str(COOKIES_FILE))
    success = download_video(reel.get('url'), str(filepath), str(COOKIES_FILE), reel.get('video_url'))

    if success:
        # Update history
        scrape['top_reels'][reel_idx]['local_video'] = str(filepath)
        save_history(history)
        return jsonify({'success': True, 'path': str(filepath)})

    return jsonify({'error': 'Download failed'}), 500


@app.route('/api/download/transcript/<scrape_id>/<shortcode>')
def download_transcript_file(scrape_id, shortcode):
    """Download a transcript file"""
    history = load_history()
    scrape = next((h for h in history if h.get('id') == scrape_id), None)

    if not scrape:
        return jsonify({'error': 'Scrape not found'}), 404

    reel = next((r for r in scrape.get('top_reels', []) if r.get('shortcode') == shortcode), None)

    if not reel:
        return jsonify({'error': 'Reel not found'}), 404

    # Try transcript file first
    transcript_path = reel.get('transcript_file')
    if transcript_path and os.path.exists(transcript_path):
        return send_file(transcript_path, as_attachment=True)

    # Generate from memory
    transcript = reel.get('transcript')
    if transcript:
        return Response(
            transcript,
            mimetype='text/plain',
            headers={'Content-Disposition': f'attachment; filename={shortcode}.txt'}
        )

    return jsonify({'error': 'Transcript not found'}), 404


@app.route('/api/transcribe/video', methods=['POST'])
def transcribe_video_on_demand():
    """Transcribe a video on-demand from the gallery"""
    from scraper.core import transcribe_video_openai, transcribe_video, load_whisper_model, WHISPER_AVAILABLE

    data = request.get_json()
    video_path = data.get('video_path')
    provider = data.get('provider', 'openai')
    shortcode = data.get('shortcode', '')

    if not video_path or not os.path.exists(video_path):
        return jsonify({'error': 'Video file not found', 'path': video_path}), 404

    transcript = None

    if provider == 'openai':
        config = load_config()
        openai_key = config.get('openai_key')
        if not openai_key:
            return jsonify({'error': 'OpenAI API key not configured'}), 400

        print(f"[TRANSCRIBE] On-demand OpenAI transcription: {video_path}")
        transcript = transcribe_video_openai(video_path, openai_key)

    elif provider == 'local':
        if not WHISPER_AVAILABLE:
            return jsonify({'error': 'Whisper not installed. Install with: pip install openai-whisper'}), 400

        whisper_model = data.get('whisper_model', 'small.en')
        print(f"[TRANSCRIBE] On-demand local transcription: {video_path} with model={whisper_model}")

        try:
            print(f"[TRANSCRIBE] Loading Whisper model: {whisper_model}")
            model = load_whisper_model(whisper_model, max_retries=2)
            if model:
                print(f"[TRANSCRIBE] Model loaded successfully, starting transcription...")
                transcript = transcribe_video(video_path, model)
                print(f"[TRANSCRIBE] Transcription complete: {len(transcript) if transcript else 0} chars")
            else:
                print(f"[TRANSCRIBE] Model returned None - check if model '{whisper_model}' needs to be downloaded")
                return jsonify({
                    'error': f'Failed to load Whisper model "{whisper_model}". Model may need to be downloaded first. Try using OpenAI provider or run a scrape with local transcription to download the model.'
                }), 500
        except Exception as e:
            import traceback
            print(f"[TRANSCRIBE] Exception during local transcription: {e}")
            traceback.print_exc()
            return jsonify({'error': f'Local transcription failed: {str(e)}'}), 500
    else:
        return jsonify({'error': f'Unknown provider: {provider}'}), 400

    if transcript:
        # Try to update history with new transcript
        print(f"[TRANSCRIBE] Got transcript ({len(transcript)} chars), updating history for shortcode={shortcode}")
        history = load_history()
        updated = False
        scrape_id_found = None

        for scrape in history:
            for reel in scrape.get('top_reels', []):
                sc = reel.get('shortcode') or reel.get('video_id')
                print(f"[TRANSCRIBE] Checking reel: sc={sc} vs shortcode={shortcode}")
                if sc == shortcode:
                    reel['transcript'] = transcript
                    updated = True
                    scrape_id_found = scrape.get('id')
                    print(f"[TRANSCRIBE] MATCH FOUND! Updated reel in scrape {scrape_id_found}")
                    break
            if updated:
                break

        if updated:
            save_history(history)
            print(f"[TRANSCRIBE] History saved successfully for {shortcode} in scrape {scrape_id_found}")
        else:
            print(f"[TRANSCRIBE] WARNING: Could not find reel with shortcode={shortcode} in any scrape")
            # Debug: print all shortcodes in history
            all_shortcodes = []
            for scrape in history:
                for reel in scrape.get('top_reels', []):
                    all_shortcodes.append(reel.get('shortcode') or reel.get('video_id'))
            print(f"[TRANSCRIBE] Available shortcodes in history: {all_shortcodes[:20]}")

        return jsonify({
            'success': True,
            'transcript': transcript,
            'provider': provider,
            'shortcode': shortcode,
            'persisted': updated
        })
    else:
        return jsonify({'error': 'Transcription failed - no audio detected or API error'}), 500


@app.route('/api/cookies/status')
def cookies_status():
    """Check cookies file status for both platforms"""
    return jsonify({
        'instagram': COOKIES_FILE.exists(),
        'tiktok': TIKTOK_COOKIES_FILE.exists(),
        'exists': COOKIES_FILE.exists()  # Backwards compat
    })


@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get current settings"""
    config = load_config()
    # Don't expose API keys in full
    return jsonify({
        'ai_provider': config.get('ai_provider', 'copy'),
        'local_model': config.get('local_model', ''),
        'openai_model': config.get('openai_model', 'gpt-4o-mini'),
        'anthropic_model': config.get('anthropic_model', 'claude-3-5-haiku-20241022'),
        'google_model': config.get('google_model', 'gemini-1.5-flash'),
        'has_openai_key': bool(config.get('openai_key')),
        'has_anthropic_key': bool(config.get('anthropic_key')),
        'has_google_key': bool(config.get('google_key')),
        'output_directory': config.get('output_directory', ''),
        'default_output_directory': str(OUTPUT_DIR)
    })


@app.route('/api/settings', methods=['POST'])
def update_settings():
    """Update settings"""
    data = request.json
    config = load_config()

    # Update only provided fields
    if 'ai_provider' in data:
        config['ai_provider'] = data['ai_provider']
    if 'local_model' in data:
        config['local_model'] = data['local_model']
    if 'openai_model' in data:
        config['openai_model'] = data['openai_model']
    if 'anthropic_model' in data:
        config['anthropic_model'] = data['anthropic_model']
    if 'google_model' in data:
        config['google_model'] = data['google_model']
    if 'openai_key' in data and data['openai_key']:
        config['openai_key'] = data['openai_key']
    if 'anthropic_key' in data and data['anthropic_key']:
        config['anthropic_key'] = data['anthropic_key']
    if 'google_key' in data and data['google_key']:
        config['google_key'] = data['google_key']
    if 'output_directory' in data:
        # Allow empty string to reset to default
        config['output_directory'] = data['output_directory'].strip()

    save_config(config)
    return jsonify({'success': True})


# ============================================================================
# UPDATE ENDPOINTS
# ============================================================================

@app.route('/api/version')
def get_version():
    """Get current application version and git status"""
    return jsonify({
        'version': get_current_version(),
        'git': get_git_status()
    })


@app.route('/api/update/check')
def check_update():
    """Check GitHub for available updates"""
    result = check_for_updates()
    if result is None:
        return jsonify({
            'success': False,
            'error': 'Could not check for updates. Check your internet connection.'
        }), 503
    return jsonify({
        'success': True,
        **result
    })


@app.route('/api/update/install', methods=['POST'])
def install_update():
    """Run git pull to install updates"""
    logger.info("UPDATER", "User initiated update installation")
    result = run_update()

    if result.get('success'):
        logger.info("UPDATER", f"Update result: {result.get('message')}")
        return jsonify(result)
    else:
        logger.error("UPDATER", f"Update failed: {result.get('error')}")
        return jsonify(result), 500


@app.route('/api/ollama/models')
def get_ollama_models_endpoint():
    """Get available Ollama models"""
    models = get_ollama_models()
    return jsonify({'models': models, 'available': len(models) > 0})


@app.route('/api/whisper/check/<model>')
def check_whisper_model(model):
    """Check if a Whisper model is installed locally"""
    if not WHISPER_AVAILABLE:
        return jsonify({
            'installed': False,
            'whisper_available': False,
            'message': 'Whisper not installed'
        })

    # Model file names (Whisper uses .pt extension)
    model_files = {
        'tiny': 'tiny.pt',
        'tiny.en': 'tiny.en.pt',
        'base': 'base.pt',
        'base.en': 'base.en.pt',
        'small': 'small.pt',
        'small.en': 'small.en.pt',
        'medium': 'medium.pt',
        'medium.en': 'medium.en.pt',
        'large': 'large-v3.pt',
        'large-v1': 'large-v1.pt',
        'large-v2': 'large-v2.pt',
        'large-v3': 'large-v3.pt',
    }

    model_file = model_files.get(model, f"{model}.pt")

    # In WSL, use Windows-level whisper cache
    # Windows path: /mnt/c/Users/Chris/.cache/whisper/
    windows_cache = Path('/mnt/c/Users/Chris/.cache/whisper')
    linux_cache = Path.home() / '.cache' / 'whisper'
    cache_dir = windows_cache if windows_cache.exists() else linux_cache

    model_path = cache_dir / model_file
    installed = model_path.exists()

    # Debug: Log the path being checked
    print(f"[Whisper Check] Model: {model}, Path: {model_path}, Exists: {installed}")

    return jsonify({
        'installed': installed,
        'whisper_available': True,
        'model': model,
        'path': str(model_path) if installed else None
    })


@app.route('/api/generate-prompt/<scrape_id>/<shortcode>')
def generate_prompt(scrape_id, shortcode):
    """Generate AI rewrite prompt for a reel"""
    history = load_history()
    scrape = next((h for h in history if h.get('id') == scrape_id), None)

    if not scrape:
        return jsonify({'error': 'Scrape not found'}), 404

    reel = next((r for r in scrape.get('top_reels', []) if r.get('shortcode') == shortcode), None)

    if not reel:
        return jsonify({'error': 'Reel not found'}), 404

    prompt = generate_ai_prompt(reel)
    return jsonify({'prompt': prompt})


@app.route('/api/rewrite', methods=['POST'])
def rewrite_script():
    """Generate AI rewrite using specified or default provider"""
    data = request.json
    scrape_id = data.get('scrape_id')
    shortcode = data.get('shortcode')
    user_context = data.get('context', '')  # Optional user context
    override_provider = data.get('provider')  # Optional provider override
    override_model = data.get('model')  # Optional model override

    if not scrape_id or not shortcode:
        return jsonify({'error': 'Missing scrape_id or shortcode'}), 400

    history = load_history()
    scrape = next((h for h in history if h.get('id') == scrape_id), None)

    if not scrape:
        return jsonify({'error': 'Scrape not found'}), 404

    reel = next((r for r in scrape.get('top_reels', []) if r.get('shortcode') == shortcode), None)

    if not reel:
        return jsonify({'error': 'Reel not found'}), 404

    config = load_config()

    # Use override provider/model if provided, otherwise fall back to config
    provider = override_provider or config.get('ai_provider', 'copy')

    if provider == 'copy':
        return jsonify({'error': 'AI provider not configured. Set provider in settings.'}), 400

    # Build prompt
    base_prompt = generate_ai_prompt(reel)
    if user_context:
        full_prompt = f"{base_prompt}\nMY CONTEXT (adapt script for this):\n{user_context}\n\nRemember: Output ONLY the script, no preamble."
    else:
        full_prompt = base_prompt

    # Call appropriate provider
    if provider == 'local':
        model = override_model or config.get('local_model')
        if not model:
            return jsonify({'error': 'No local model selected'}), 400
        result = call_ollama(full_prompt, model)

    elif provider == 'openai':
        api_key = config.get('openai_key')
        if not api_key:
            return jsonify({'error': 'OpenAI API key not configured'}), 400
        model = override_model or config.get('openai_model', 'gpt-4o-mini')
        result = call_openai(full_prompt, model, api_key)

    elif provider == 'anthropic':
        api_key = config.get('anthropic_key')
        if not api_key:
            return jsonify({'error': 'Anthropic API key not configured'}), 400
        model = override_model or config.get('anthropic_model', 'claude-3-5-haiku-20241022')
        result = call_anthropic(full_prompt, model, api_key)

    elif provider == 'google':
        api_key = config.get('google_key')
        if not api_key:
            return jsonify({'error': 'Google API key not configured'}), 400
        model = override_model or config.get('google_model', 'gemini-1.5-flash')
        result = call_google(full_prompt, model, api_key)

    else:
        return jsonify({'error': f'Unknown provider: {provider}'}), 400

    return jsonify({'result': result, 'provider': provider, 'model': model})


# =====================
# VIDEO GALLERY ENDPOINTS
# =====================

@app.route('/api/videos')
def list_videos():
    """List downloaded videos, optionally filtered by username or platform"""
    videos = []
    seen_paths = set()  # Track seen paths to avoid duplicates
    filter_username = request.args.get('username', '').strip()
    filter_platform = request.args.get('platform', '').strip().lower()

    # Scan all output directories (IG and TikTok)
    output_dirs_to_scan = [
        (get_output_directory('instagram'), 'instagram'),
        (get_output_directory('tiktok'), 'tiktok'),
    ]
    # Also check defaults if different
    if get_output_directory('instagram') != OUTPUT_DIR and OUTPUT_DIR.exists():
        output_dirs_to_scan.append((OUTPUT_DIR, 'instagram'))
    if get_output_directory('tiktok') != TIKTOK_OUTPUT_DIR and TIKTOK_OUTPUT_DIR.exists():
        output_dirs_to_scan.append((TIKTOK_OUTPUT_DIR, 'tiktok'))

    # Build a lookup map of shortcode/video_id -> transcript from history
    transcript_map = {}
    history = load_history()
    for scrape in history:
        platform = scrape.get('platform', 'instagram')
        for reel in scrape.get('top_reels', []):
            sc = reel.get('shortcode') or reel.get('video_id')
            if sc and reel.get('transcript'):
                transcript_map[sc] = {
                    'transcript': reel.get('transcript'),
                    'caption': reel.get('caption', ''),
                    'scrape_id': scrape.get('id'),
                    'reel_url': reel.get('url', ''),
                    'platform': platform
                }

    # Scan all output directories for videos
    for output_dir, platform in output_dirs_to_scan:
        if not output_dir.exists():
            continue

        # Skip if filtering by platform and this isn't a match
        if filter_platform and platform != filter_platform:
            continue

        for user_dir in output_dir.iterdir():
            if user_dir.is_dir() and user_dir.name.startswith('output_'):
                # Extract username, handling both IG (output_user) and TikTok (output_user_tiktok)
                username = user_dir.name.replace('output_', '')
                if username.endswith('_tiktok'):
                    username = username[:-7]  # Remove '_tiktok' suffix

                # Skip if filtering by username and this isn't a match
                if filter_username and username.lower() != filter_username.lower():
                    continue

                video_dir = user_dir / 'videos'
                if video_dir.exists():
                    for video_file in video_dir.iterdir():
                        # Skip if we've already seen this file
                        if str(video_file) in seen_paths:
                            continue
                        seen_paths.add(str(video_file))

                        if video_file.suffix.lower() in ['.mp4', '.mov', '.webm']:
                            # Parse filename to extract info
                            # Format: {rank}_{views}views_{shortcode}.mp4
                            parts = video_file.stem.split('_')
                            shortcode = parts[-1] if len(parts) >= 3 else video_file.stem
                            views = 0
                            if len(parts) >= 2:
                                views_part = parts[1].replace('views', '')
                                try:
                                    views = int(views_part)
                                except:
                                    pass

                            # Get transcript data if available
                            transcript_data = transcript_map.get(shortcode, {})

                            videos.append({
                                'filename': video_file.name,
                                'path': str(video_file),
                                'username': username,
                                'shortcode': shortcode,
                                'views': views,
                                'size': video_file.stat().st_size,
                                'created': video_file.stat().st_mtime,
                                'url': f'/api/videos/stream/{username}/{video_file.name}',
                                'transcript': transcript_data.get('transcript'),
                                'caption': transcript_data.get('caption', ''),
                                'scrape_id': transcript_data.get('scrape_id'),
                                'reel_url': transcript_data.get('reel_url', ''),
                                'platform': platform
                            })

    # Sort by creation time (newest first)
    videos.sort(key=lambda x: x['created'], reverse=True)

    return jsonify({
        'videos': videos,
        'filtered': bool(filter_username or filter_platform),
        'filter_username': filter_username if filter_username else None,
        'filter_platform': filter_platform if filter_platform else None
    })


@app.route('/api/videos/stream/<username>/<filename>')
def stream_video(username, filename):
    """Stream a video file"""
    # Security: Validate path to prevent traversal
    safe_username = ''.join(c for c in username if c.isalnum() or c in '._-')
    safe_filename = ''.join(c for c in filename if c.isalnum() or c in '._-')

    # Try all output directories (IG and TikTok)
    output_dirs_to_try = [
        get_output_directory('instagram'),
        get_output_directory('tiktok'),
        OUTPUT_DIR,
        TIKTOK_OUTPUT_DIR
    ]

    for output_dir in output_dirs_to_try:
        if not output_dir.exists():
            continue

        # Try both IG format (output_user) and TikTok format (output_user_tiktok)
        paths_to_try = [
            output_dir / f'output_{safe_username}' / 'videos' / safe_filename,
            output_dir / f'output_{safe_username}_tiktok' / 'videos' / safe_filename
        ]

        for video_path in paths_to_try:
            try:
                video_path = video_path.resolve()
                # Verify the file is within a valid output directory
                if not (str(video_path).startswith(str(output_dir.resolve())) or
                        str(video_path).startswith(str(OUTPUT_DIR.resolve())) or
                        str(video_path).startswith(str(TIKTOK_OUTPUT_DIR.resolve()))):
                    continue
            except:
                continue

            if video_path.exists():
                return send_file(video_path, mimetype='video/mp4')

    return jsonify({'error': 'Video not found'}), 404


@app.route('/api/videos/delete', methods=['POST'])
def delete_video():
    """Delete a video file from filesystem"""
    data = request.json
    video_path = data.get('path')

    if not video_path:
        return jsonify({'error': 'No path provided'}), 400

    video_path = Path(video_path)

    # Security: Verify the file is within a valid output directory (configured or default)
    try:
        video_path = video_path.resolve()
        allowed_dirs = [
            get_output_directory('instagram').resolve(),
            get_output_directory('tiktok').resolve(),
            OUTPUT_DIR.resolve(),
            TIKTOK_OUTPUT_DIR.resolve()
        ]

        # Check if video path is within allowed directories using parent chain
        is_valid = False
        for parent in video_path.parents:
            for allowed_dir in allowed_dirs:
                if parent == allowed_dir:
                    is_valid = True
                    break
                try:
                    parent.relative_to(allowed_dir)
                    is_valid = True
                    break
                except ValueError:
                    pass
            if is_valid:
                break

        if not is_valid:
            return jsonify({'error': 'Invalid path - outside allowed directory'}), 403
    except Exception as e:
        return jsonify({'error': f'Invalid path: {str(e)}'}), 403

    if not video_path.exists():
        return jsonify({'error': 'File not found'}), 404

    # Delete the file
    try:
        video_path.unlink()

        # Also update history to remove the local_video reference
        history = load_history()
        shortcode = video_path.stem.split('_')[-1]
        for scrape in history:
            for reel in scrape.get('top_reels', []):
                if reel.get('local_video') == str(video_path):
                    reel['local_video'] = None
                    break
        save_history(history)

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': f'Failed to delete: {str(e)}'}), 500


# =====================
# SKELETON RIPPER ENDPOINTS
# =====================

# Active skeleton ripper jobs
active_skeleton_jobs = {}


@app.route('/api/skeleton-ripper/providers')
def get_skeleton_providers():
    """Get available LLM providers for skeleton ripper"""
    try:
        from skeleton_ripper.llm_client import PROVIDERS

        # Check which providers have API keys configured
        config = load_config()
        providers = get_available_providers()

        # Update availability based on configured keys AND populate models
        for p in providers:
            if p['id'] == 'openai':
                has_key = bool(config.get('openai_key'))
                p['available'] = has_key
                if has_key and not p['models']:
                    # Populate models from PROVIDERS config
                    p['models'] = [
                        {'id': m.id, 'name': m.name, 'cost_tier': m.cost_tier}
                        for m in PROVIDERS['openai'].models
                    ]
            elif p['id'] == 'anthropic':
                has_key = bool(config.get('anthropic_key'))
                p['available'] = has_key
                if has_key and not p['models']:
                    p['models'] = [
                        {'id': m.id, 'name': m.name, 'cost_tier': m.cost_tier}
                        for m in PROVIDERS['anthropic'].models
                    ]
            elif p['id'] == 'google':
                has_key = bool(config.get('google_key'))
                p['available'] = has_key
                if has_key and not p['models']:
                    p['models'] = [
                        {'id': m.id, 'name': m.name, 'cost_tier': m.cost_tier}
                        for m in PROVIDERS['google'].models
                    ]
            elif p['id'] == 'local':
                # For local, show ALL installed Ollama models (not just predefined ones)
                ollama_models = get_ollama_models()  # Returns list of strings
                if ollama_models:
                    p['available'] = True
                    p['models'] = [
                        {'id': model_name, 'name': model_name, 'cost_tier': 'free'}
                        for model_name in ollama_models
                    ]

        return jsonify({'providers': providers})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'providers': []}), 500


@app.route('/api/skeleton-ripper/start', methods=['POST'])
def start_skeleton_ripper():
    """Start a new skeleton ripper job"""
    data = request.json

    usernames = data.get('usernames', [])
    if not usernames or len(usernames) < 1 or len(usernames) > 5:
        return jsonify({'error': 'Provide 1-5 usernames'}), 400

    # Validate usernames
    usernames = [u.strip().lstrip('@') for u in usernames if u.strip()]
    if not usernames:
        return jsonify({'error': 'No valid usernames provided'}), 400

    videos_per_creator = min(max(int(data.get('videos_per_creator', 3)), 1), 5)
    platform = data.get('platform', 'instagram').lower()
    llm_provider = data.get('llm_provider', 'openai')
    llm_model = data.get('llm_model', 'gpt-4o-mini')

    # Transcription settings
    transcribe_provider = data.get('transcribe_provider', 'openai')  # 'openai' or 'local'
    whisper_model = data.get('whisper_model', 'small.en')

    # Validate LLM provider has API key
    config = load_config()
    if llm_provider == 'openai' and not config.get('openai_key'):
        return jsonify({'error': 'OpenAI API key not configured'}), 400
    elif llm_provider == 'anthropic' and not config.get('anthropic_key'):
        return jsonify({'error': 'Anthropic API key not configured'}), 400
    elif llm_provider == 'google' and not config.get('google_key'):
        return jsonify({'error': 'Google API key not configured'}), 400

    # OpenAI key needed for transcription if using OpenAI Whisper
    openai_api_key = config.get('openai_key') if transcribe_provider == 'openai' else None
    if transcribe_provider == 'openai' and not openai_api_key:
        return jsonify({'error': 'OpenAI API key required for Whisper transcription'}), 400

    # Set API key in environment for LLM client
    if llm_provider == 'openai':
        os.environ['OPENAI_API_KEY'] = config.get('openai_key')
    elif llm_provider == 'anthropic':
        os.environ['ANTHROPIC_API_KEY'] = config.get('anthropic_key')
    elif llm_provider == 'google':
        os.environ['GOOGLE_API_KEY'] = config.get('google_key')

    # Create job config with transcription settings
    job_config = create_job_config(
        usernames=usernames,
        videos_per_creator=videos_per_creator,
        platform=platform,
        llm_provider=llm_provider,
        llm_model=llm_model,
        transcribe_provider=transcribe_provider,
        whisper_model=whisper_model,
        openai_api_key=openai_api_key
    )

    # Initialize pipeline
    pipeline = SkeletonRipperPipeline(str(BASE_DIR))

    # Track job
    job_id = f"sr_{uuid.uuid4().hex[:8]}"
    active_skeleton_jobs[job_id] = {
        'status': 'starting',
        'progress': None,
        'result': None
    }

    logger.info("SKELETON", f"Starting skeleton ripper job {job_id}", {
        "usernames": usernames,
        "provider": llm_provider,
        "model": llm_model,
        "transcribe_provider": transcribe_provider,
        "platform": platform
    })

    # Run in background thread
    def run_skeleton_job():
        def progress_callback(progress: JobProgress):
            active_skeleton_jobs[job_id]['progress'] = {
                'status': progress.status.value,
                'phase': progress.phase,
                'message': progress.message,
                'videos_scraped': progress.videos_scraped,
                'videos_transcribed': progress.videos_transcribed,
                'transcripts_from_cache': progress.transcripts_from_cache,
                'valid_transcripts': progress.valid_transcripts,
                'skeletons_extracted': progress.skeletons_extracted,
                'total_target': progress.total_target,
                'errors': progress.errors
            }
            active_skeleton_jobs[job_id]['status'] = progress.status.value

        try:
            result = pipeline.run(job_config, on_progress=progress_callback)

            active_skeleton_jobs[job_id]['result'] = {
                'success': result.success,
                'job_id': result.job_id,
                'skeletons_count': len(result.skeletons),
                'report_path': result.report_path,
                'skeletons_path': result.skeletons_path,
                'synthesis_path': result.synthesis_path,
                'synthesis_analysis': result.synthesis.analysis if result.synthesis else None
            }
            active_skeleton_jobs[job_id]['status'] = 'complete' if result.success else 'failed'

            logger.info("SKELETON", f"Job {job_id} completed", {
                "success": result.success,
                "skeletons": len(result.skeletons)
            })

        except Exception as e:
            logger.error("SKELETON", f"Job {job_id} failed: {e}")
            active_skeleton_jobs[job_id]['status'] = 'failed'
            active_skeleton_jobs[job_id]['result'] = {
                'success': False,
                'error': str(e)
            }

    thread = Thread(target=run_skeleton_job, daemon=True)
    thread.start()

    return jsonify({
        'job_id': job_id,
        'status': 'pending',
        'message': 'Skeleton ripper job started'
    })


@app.route('/api/skeleton-ripper/status/<job_id>')
def skeleton_ripper_status(job_id):
    """Get skeleton ripper job status"""
    if job_id not in active_skeleton_jobs:
        return jsonify({'error': 'Job not found'}), 404

    job = active_skeleton_jobs[job_id]
    return jsonify({
        'job_id': job_id,
        'status': job['status'],
        'progress': job['progress'],
        'result': job['result']
    })


@app.route('/api/skeleton-ripper/report/<job_id>')
def skeleton_ripper_report(job_id):
    """Get the generated report for a completed job"""
    if job_id not in active_skeleton_jobs:
        return jsonify({'error': 'Job not found'}), 404

    job = active_skeleton_jobs[job_id]
    if not job.get('result') or not job['result'].get('report_path'):
        return jsonify({'error': 'Report not available'}), 404

    report_path = Path(job['result']['report_path'])
    if not report_path.exists():
        return jsonify({'error': 'Report file not found'}), 404

    return send_file(report_path, mimetype='text/markdown')


if __name__ == '__main__':
    OUTPUT_DIR.mkdir(exist_ok=True)
    TIKTOK_OUTPUT_DIR.mkdir(exist_ok=True)
    # IMPORTANT: use_reloader=False prevents Flask from restarting when Whisper
    # or other libraries touch their own files during import/execution.
    # The watchdog was incorrectly detecting whisper/transcribe.py access as a change.
    app.run(debug=True, port=5000, use_reloader=False)
