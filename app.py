"""
ReelRecon - Tactical Content Intelligence
Instagram reel scraping with AI-powered script rewriting
"""

import json
import os
import uuid
import subprocess
from datetime import datetime
from pathlib import Path
from threading import Thread

from flask import Flask, render_template, request, jsonify, send_file, Response
import requests as http_requests

# Import scraper
from scraper.core import run_scrape, WHISPER_AVAILABLE, download_video, create_session

# Configuration
BASE_DIR = Path(__file__).parent.resolve()

# Initialize Flask with explicit paths
app = Flask(__name__,
            static_folder=str(BASE_DIR / 'static'),
            template_folder=str(BASE_DIR / 'templates'))
app.secret_key = os.urandom(24)
OUTPUT_DIR = BASE_DIR / "output"
COOKIES_FILE = BASE_DIR / "cookies.txt"
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
active_scrapes = {}


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


def get_output_directory():
    """Get the configured output directory, or default if not set"""
    config = load_config()
    custom_dir = config.get('output_directory', '').strip()
    if custom_dir:
        output_path = Path(custom_dir)
        # Create directory if it doesn't exist
        output_path.mkdir(parents=True, exist_ok=True)
        return output_path
    return OUTPUT_DIR


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


def add_to_history(scrape_result):
    """Add a scrape result to history"""
    history = load_history()
    # Keep essential data for history
    entry = {
        'id': scrape_result.get('id', str(uuid.uuid4())),
        'username': scrape_result.get('username'),
        'timestamp': scrape_result.get('timestamp'),
        'profile': scrape_result.get('profile'),
        'total_reels': scrape_result.get('total_reels'),
        'top_count': len(scrape_result.get('top_reels', [])),
        'top_reels': scrape_result.get('top_reels', []),
        'output_dir': scrape_result.get('output_dir')
    }
    history.insert(0, entry)
    # Keep last 50 scrapes
    history = history[:50]
    save_history(history)


@app.route('/')
def index():
    """Main page"""
    history = load_history()
    cookies_exist = COOKIES_FILE.exists()
    return render_template('index.html',
                         history=history,
                         cookies_exist=cookies_exist,
                         whisper_available=WHISPER_AVAILABLE)


@app.route('/api/scrape', methods=['POST'])
def start_scrape():
    """Start a new scrape"""
    data = request.json
    username = data.get('username', '').strip().lstrip('@')

    if not username:
        return jsonify({'error': 'Username required'}), 400

    if not COOKIES_FILE.exists():
        return jsonify({'error': 'Cookies file not found'}), 400

    # Create scrape ID
    scrape_id = str(uuid.uuid4())
    print(f"[DEBUG] Created scrape {scrape_id} for @{username}")

    # Initialize progress tracking
    active_scrapes[scrape_id] = {
        'status': 'starting',
        'progress': 'Initializing...',
        'result': None
    }
    print(f"[DEBUG] Active scrapes after add: {list(active_scrapes.keys())}")

    # Get transcription settings
    transcribe_provider = data.get('transcribe_provider', 'local')
    openai_key = None
    if transcribe_provider == 'openai':
        config = load_config()
        openai_key = config.get('openai_key')

    # Run scrape in background thread
    def run_in_background():
        def progress_callback(msg):
            active_scrapes[scrape_id]['progress'] = msg

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
            output_dir=str(get_output_directory()),
            progress_callback=progress_callback
        )

        active_scrapes[scrape_id]['result'] = result
        active_scrapes[scrape_id]['status'] = result.get('status', 'complete')

        if result.get('status') == 'complete':
            add_to_history(result)

    thread = Thread(target=run_in_background)
    thread.start()

    return jsonify({'scrape_id': scrape_id})


@app.route('/api/scrape/<scrape_id>/status')
def scrape_status(scrape_id):
    """Get scrape status"""
    if scrape_id not in active_scrapes:
        print(f"[DEBUG] Scrape {scrape_id} not found. Active scrapes: {list(active_scrapes.keys())}")
        return jsonify({'error': 'Scrape not found'}), 404

    scrape = active_scrapes[scrape_id]
    return jsonify({
        'status': scrape['status'],
        'progress': scrape['progress'],
        'result': scrape['result']
    })


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


@app.route('/api/cookies/status')
def cookies_status():
    """Check cookies file status"""
    return jsonify({'exists': COOKIES_FILE.exists()})


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

    # Whisper uses ~/.cache/whisper/ on ALL platforms (including Windows)
    # This matches the whisper library's default: os.path.join(os.path.expanduser("~"), ".cache", "whisper")
    cache_dir = Path.home() / '.cache' / 'whisper'

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
    """List downloaded videos, optionally filtered by username"""
    videos = []
    seen_paths = set()  # Track seen paths to avoid duplicates
    filter_username = request.args.get('username', '').strip()

    # Scan both configured output directory and default (if different)
    output_dirs_to_scan = [get_output_directory()]
    if get_output_directory() != OUTPUT_DIR and OUTPUT_DIR.exists():
        output_dirs_to_scan.append(OUTPUT_DIR)

    # Build a lookup map of shortcode -> transcript from history
    transcript_map = {}
    history = load_history()
    for scrape in history:
        for reel in scrape.get('top_reels', []):
            sc = reel.get('shortcode')
            if sc and reel.get('transcript'):
                transcript_map[sc] = {
                    'transcript': reel.get('transcript'),
                    'caption': reel.get('caption', ''),
                    'scrape_id': scrape.get('id'),
                    'reel_url': reel.get('url', '')
                }

    # Scan all output directories for videos
    for output_dir in output_dirs_to_scan:
        if not output_dir.exists():
            continue

        for user_dir in output_dir.iterdir():
            if user_dir.is_dir() and user_dir.name.startswith('output_'):
                username = user_dir.name.replace('output_', '')

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
                                'reel_url': transcript_data.get('reel_url', '')
                            })

    # Sort by creation time (newest first)
    videos.sort(key=lambda x: x['created'], reverse=True)

    return jsonify({
        'videos': videos,
        'filtered': bool(filter_username),
        'filter_username': filter_username if filter_username else None,
        'output_directory': str(output_dir)
    })


@app.route('/api/videos/stream/<username>/<filename>')
def stream_video(username, filename):
    """Stream a video file"""
    # Security: Validate path to prevent traversal
    safe_username = ''.join(c for c in username if c.isalnum() or c in '._-')
    safe_filename = ''.join(c for c in filename if c.isalnum() or c in '._-')

    # Try configured output dir first, then default
    output_dirs_to_try = [get_output_directory()]
    if get_output_directory() != OUTPUT_DIR:
        output_dirs_to_try.append(OUTPUT_DIR)

    for output_dir in output_dirs_to_try:
        video_path = output_dir / f'output_{safe_username}' / 'videos' / safe_filename

        try:
            video_path = video_path.resolve()
            # Verify the file is within a valid output directory
            if not (str(video_path).startswith(str(output_dir.resolve())) or
                    str(video_path).startswith(str(OUTPUT_DIR.resolve()))):
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
        configured_output = get_output_directory().resolve()
        default_output = OUTPUT_DIR.resolve()

        # Check if video path is within allowed directories using parent chain
        is_valid = False
        for parent in video_path.parents:
            if parent == configured_output or parent == default_output:
                is_valid = True
                break
            # Also check if parent starts with output directory (for nested structures)
            try:
                parent.relative_to(configured_output)
                is_valid = True
                break
            except ValueError:
                pass
            try:
                parent.relative_to(default_output)
                is_valid = True
                break
            except ValueError:
                pass

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


if __name__ == '__main__':
    OUTPUT_DIR.mkdir(exist_ok=True)
    app.run(debug=True, port=5000)
