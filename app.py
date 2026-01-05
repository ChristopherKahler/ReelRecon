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

# Import storage module for Asset Management (P0)
from storage import init_db, Asset, Collection, AssetCollection

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
STATE_DIR = BASE_DIR / "state"  # Required for skeleton job persistence

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

# Active batch jobs (multiple creators in one batch)
active_batches = {}

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


@app.route('/library')
def library_page():
    """Asset Library page"""
    return render_template('library.html')


@app.route('/workspace')
def workspace_page():
    """V3 Unified Workspace (development)"""
    return render_template('workspace.html')


# =========================================
# Health Check (for auto-reconnect)
# =========================================

@app.route('/api/health')
def health_check():
    """Simple health check endpoint for frontend reconnect detection"""
    return jsonify({'status': 'ok'})


@app.route('/api/debug/routes')
def debug_routes():
    """Debug: list all registered routes"""
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods - {'HEAD', 'OPTIONS'}),
            'path': str(rule)
        })
    routes.sort(key=lambda r: r['path'])
    return jsonify({'routes': routes, 'total': len(routes)})


# =========================================
# V3 Unified Jobs API
# =========================================

@app.route('/api/jobs/active')
def get_active_jobs():
    """Get all active jobs (scrapes + batches + skeleton ripper)"""
    jobs = []

    # Add active batch jobs (these contain multiple scrapes)
    for batch_id, batch in active_batches.items():
        if batch.get('status') == 'running':
            current_username = batch.get('current_username', '')
            current_scrape_id = batch.get('current_scrape_id')
            completed = batch.get('completed', 0)
            total = batch.get('total', 1)

            # Get granular progress from the current running scrape
            current_progress = f"Starting batch..."
            current_progress_pct = 0
            current_phase = 'batch'

            if current_scrape_id and current_scrape_id in active_scrapes:
                current_scrape = active_scrapes[current_scrape_id]
                # Use the actual granular progress from the scraper
                scrape_progress = current_scrape.get('progress', '')
                scrape_pct = current_scrape.get('progress_pct', 0)
                current_phase = current_scrape.get('phase', 'processing')

                # Combine batch context with granular scrape progress
                current_progress = f"@{current_username} ({completed + 1}/{total}): {scrape_progress}"
                # Calculate overall progress: completed batches + current scrape progress
                current_progress_pct = int(((completed + (scrape_pct / 100)) / total) * 100)
            elif current_username:
                current_progress = f"Starting @{current_username} ({completed + 1}/{total})..."

            jobs.append({
                'id': batch_id,
                'type': 'batch_scrape',
                'title': f"Batch: {', '.join(batch.get('usernames', [])[:2])}{'...' if len(batch.get('usernames', [])) > 2 else ''}",
                'platform': batch.get('platform', 'instagram'),
                'status': 'running',
                'progress': current_progress,
                'progress_pct': current_progress_pct,
                'phase': current_phase,
                'created_at': batch.get('created_at', ''),
                'batch_info': {
                    'total': total,
                    'completed': completed,
                    'current_username': current_username,
                    'usernames': batch.get('usernames', [])
                }
            })

    # Add active scrapes (skip those that are part of a batch - they're tracked via batch)
    for scrape_id, scrape in active_scrapes.items():
        if scrape.get('status') in ('starting', 'running'):
            # Skip scrapes that are part of an active batch
            if scrape.get('batch_id') and scrape['batch_id'] in active_batches:
                continue
            jobs.append({
                'id': scrape_id,
                'type': 'scrape',
                'title': f"Scrape: {scrape.get('username', 'unknown')}",
                'platform': scrape.get('platform', 'instagram'),
                'status': scrape.get('status', 'unknown'),
                'progress': scrape.get('progress', ''),
                'progress_pct': scrape.get('progress_pct', 0),
                'phase': scrape.get('phase', ''),
                'created_at': scrape.get('created_at', '')
            })

    # Add active skeleton ripper jobs (now uses 'running' status consistently like regular scrapes)
    for job_id, job in active_skeleton_jobs.items():
        if job.get('status') in ('running', 'starting'):
            progress = job.get('progress') or {}

            # Calculate overall progress percentage based on pipeline status and counts
            # Pipeline phases: scraping (includes download+transcribe) -> extracting -> aggregating -> synthesizing
            total_target = progress.get('total_target', 1) or 1
            videos_downloaded = progress.get('videos_downloaded', 0)
            videos_transcribed = progress.get('videos_transcribed', 0)
            skeletons_extracted = progress.get('skeletons_extracted', 0)
            valid_transcripts = progress.get('valid_transcripts', 0) or total_target

            pipeline_status = progress.get('status', '')
            phase_display = progress.get('phase', '')  # Keep for display

            if job.get('status') == 'complete' or pipeline_status == 'complete':
                progress_pct = 100
            elif pipeline_status == 'synthesizing':
                progress_pct = 95
            elif pipeline_status == 'aggregating':
                progress_pct = 90
            elif pipeline_status == 'extracting':
                # Extracting: 70-90%
                extract_pct = (skeletons_extracted / valid_transcripts) * 100 if valid_transcripts else 0
                progress_pct = 70 + int(extract_pct * 0.20)
            elif pipeline_status == 'scraping':
                # Scraping phase includes fetch, download, transcribe
                # Progress within scraping: download gives 0-35%, transcribe gives 35-70%
                if videos_transcribed > 0:
                    trans_pct = (videos_transcribed / total_target) * 100 if total_target else 0
                    progress_pct = 35 + int(trans_pct * 0.35)
                elif videos_downloaded > 0:
                    dl_pct = (videos_downloaded / total_target) * 100 if total_target else 0
                    progress_pct = int(dl_pct * 0.35)
                else:
                    progress_pct = 5  # Fetching reels
            else:
                progress_pct = 0

            jobs.append({
                'id': job_id,
                'type': 'analysis',
                'title': f"Analysis: {', '.join(job.get('creators', [])[:2])}{'...' if len(job.get('creators', [])) > 2 else ''}",
                'status': job.get('status', 'unknown'),
                'progress': progress.get('message', ''),
                'progress_pct': min(progress_pct, 100),
                'phase': phase_display,  # Human-readable phase text
                'platform': job.get('platform', 'instagram'),
                'creators': job.get('creators', []),
                'videos_per_creator': job.get('videos_per_creator', 3),
                'created_at': job.get('created_at', '')
            })

    # Sort by created_at descending
    jobs.sort(key=lambda j: j.get('created_at', ''), reverse=True)

    return jsonify({'success': True, 'jobs': jobs})


@app.route('/api/jobs/recent')
def get_recent_jobs():
    """Get recently completed jobs (scrapes + skeleton ripper)"""
    jobs = []

    # Get completed scrapes from state manager
    scrape_jobs = state_manager.get_recent_jobs(limit=20)
    for job in scrape_jobs:
        if job.get('state') in ('complete', 'error', 'partial', 'aborted'):
            jobs.append({
                'id': job.get('id'),
                'type': 'scrape',
                'title': f"Scrape: {job.get('username', 'unknown')}",
                'platform': job.get('platform', 'instagram'),
                'status': job.get('state', 'unknown'),
                'created_at': job.get('created_at', ''),
                'completed_at': job.get('completed_at', ''),
                'starred': job.get('starred', False),
                'result': job.get('result')
            })

    # Get completed skeleton ripper jobs
    for job_id, job in active_skeleton_jobs.items():
        if job.get('status') in ('complete', 'failed'):
            jobs.append({
                'id': job_id,
                'type': 'analysis',
                'title': f"Analysis: {', '.join(job.get('creators', [])[:2])}{'...' if len(job.get('creators', [])) > 2 else ''}",
                'status': job.get('status', 'unknown'),
                'platform': job.get('platform', 'instagram'),
                'creators': job.get('creators', []),
                'videos_per_creator': job.get('videos_per_creator', 3),
                'created_at': job.get('created_at', ''),
                'starred': job.get('starred', False),
                'result': job.get('result')
            })

    # Sort by created_at descending, take top 20
    jobs.sort(key=lambda j: j.get('created_at', ''), reverse=True)

    return jsonify({'success': True, 'jobs': jobs[:20]})


@app.route('/api/jobs/<job_id>/star', methods=['POST'])
def toggle_job_star(job_id):
    """Toggle starred status for a job"""
    # Check skeleton ripper jobs
    if job_id in active_skeleton_jobs:
        current = active_skeleton_jobs[job_id].get('starred', False)
        active_skeleton_jobs[job_id]['starred'] = not current
        save_skeleton_jobs()
        return jsonify({
            'success': True,
            'job_id': job_id,
            'starred': active_skeleton_jobs[job_id]['starred']
        })

    # Check scrape jobs in state manager
    job = state_manager.get_job(job_id)
    if job:
        current = job.starred
        state_manager.update_job(job_id, starred=not current)
        return jsonify({
            'success': True,
            'job_id': job_id,
            'starred': not current
        })

    return jsonify({'success': False, 'error': 'Job not found'}), 404


@app.route('/api/jobs/starred', methods=['GET'])
def get_starred_jobs():
    """Get all starred jobs"""
    jobs = []

    # Get starred scrape jobs from state manager
    scrape_jobs = state_manager.get_recent_jobs(limit=100)
    for job in scrape_jobs:
        if job.get('starred'):
            jobs.append({
                'id': job.get('id'),
                'type': 'scrape',
                'title': f"Scrape: {job.get('username', 'unknown')}",
                'platform': job.get('platform', 'instagram'),
                'status': job.get('state', 'unknown'),
                'created_at': job.get('created_at', ''),
                'completed_at': job.get('completed_at', ''),
                'starred': True,
                'result': job.get('result')
            })

    # Get starred skeleton ripper jobs
    for job_id, job in active_skeleton_jobs.items():
        if job.get('starred'):
            jobs.append({
                'id': job_id,
                'type': 'analysis',
                'title': f"Analysis: {', '.join(job.get('creators', [])[:2])}{'...' if len(job.get('creators', [])) > 2 else ''}",
                'status': job.get('status', 'unknown'),
                'platform': job.get('platform', 'instagram'),
                'creators': job.get('creators', []),
                'videos_per_creator': job.get('videos_per_creator', 3),
                'created_at': job.get('created_at', ''),
                'starred': True,
                'result': job.get('result')
            })

    jobs.sort(key=lambda j: j.get('created_at', ''), reverse=True)
    return jsonify({'success': True, 'jobs': jobs})


@app.route('/api/jobs/<job_id>/archive', methods=['POST'])
def archive_job(job_id):
    """Archive a job (soft delete)"""
    job_data = None

    # Check skeleton ripper jobs
    if job_id in active_skeleton_jobs:
        job = active_skeleton_jobs[job_id]
        job_data = {
            'id': job_id,
            'type': 'analysis',
            'title': f"Analysis: {', '.join(job.get('creators', [])[:2])}{'...' if len(job.get('creators', [])) > 2 else ''}",
            'status': job.get('status', 'unknown'),
            'platform': job.get('platform', 'instagram'),
            'creators': job.get('creators', []),
            'videos_per_creator': job.get('videos_per_creator', 3),
            'created_at': job.get('created_at', ''),
            'archived_at': datetime.now().isoformat(),
            'starred': job.get('starred', False),
            'result': job.get('result'),
            'original_data': job
        }
        del active_skeleton_jobs[job_id]
        save_skeleton_jobs()

    # Check scrape jobs in state manager
    if not job_data:
        job = state_manager.get_job(job_id)
        if job:
            job_data = {
                'id': job_id,
                'type': 'scrape',
                'title': f"Scrape: {job.get('username', 'unknown')}",
                'platform': job.get('platform', 'instagram'),
                'status': job.get('state', 'unknown'),
                'created_at': job.get('created_at', ''),
                'archived_at': datetime.now().isoformat(),
                'starred': job.get('starred', False),
                'result': job.get('result'),
                'original_data': job
            }
            state_manager.delete_job(job_id)

    if job_data:
        archived_jobs.append(job_data)
        save_archived_jobs()
        return jsonify({'success': True, 'job_id': job_id})

    return jsonify({'success': False, 'error': 'Job not found'}), 404


@app.route('/api/jobs/<job_id>/restore', methods=['POST'])
def restore_job(job_id):
    """Restore a job from archive"""
    job_to_restore = None
    job_index = None

    for i, job in enumerate(archived_jobs):
        if job.get('id') == job_id:
            job_to_restore = job
            job_index = i
            break

    if not job_to_restore:
        return jsonify({'success': False, 'error': 'Job not found in archive'}), 404

    # Restore based on job type
    if job_to_restore.get('type') == 'analysis':
        original_data = job_to_restore.get('original_data', {})
        active_skeleton_jobs[job_id] = original_data
        save_skeleton_jobs()
    else:
        # Restore scrape job
        original_data = job_to_restore.get('original_data', {})
        state_manager.restore_job(job_id, original_data)

    # Remove from archive
    archived_jobs.pop(job_index)
    save_archived_jobs()

    return jsonify({'success': True, 'job_id': job_id})


@app.route('/api/jobs/archived', methods=['GET'])
def get_archived_jobs():
    """Get all archived jobs"""
    jobs = []
    for job in archived_jobs:
        jobs.append({
            'id': job.get('id'),
            'type': job.get('type'),
            'title': job.get('title'),
            'platform': job.get('platform'),
            'status': job.get('status'),
            'created_at': job.get('created_at'),
            'archived_at': job.get('archived_at'),
            'starred': job.get('starred', False)
        })

    jobs.sort(key=lambda j: j.get('archived_at', ''), reverse=True)
    return jsonify({'success': True, 'jobs': jobs})


@app.route('/api/jobs/clear-all', methods=['POST'])
def clear_all_jobs():
    """Archive all recent jobs (soft delete)"""
    global archived_jobs
    archived_count = 0

    # Archive skeleton ripper jobs
    skeleton_ids = list(active_skeleton_jobs.keys())
    for job_id in skeleton_ids:
        job = active_skeleton_jobs[job_id]
        if job.get('status') in ('complete', 'failed'):
            job_data = {
                'id': job_id,
                'type': 'analysis',
                'title': f"Analysis: {', '.join(job.get('creators', [])[:2])}{'...' if len(job.get('creators', [])) > 2 else ''}",
                'status': job.get('status', 'unknown'),
                'platform': job.get('platform', 'instagram'),
                'creators': job.get('creators', []),
                'videos_per_creator': job.get('videos_per_creator', 3),
                'created_at': job.get('created_at', ''),
                'archived_at': datetime.now().isoformat(),
                'starred': job.get('starred', False),
                'result': job.get('result'),
                'original_data': job
            }
            archived_jobs.append(job_data)
            del active_skeleton_jobs[job_id]
            archived_count += 1

    save_skeleton_jobs()

    # Archive completed scrape jobs from state manager
    scrape_jobs = state_manager.get_recent_jobs(limit=100)
    for job in scrape_jobs:
        if job.get('state') in ('complete', 'error', 'partial', 'aborted'):
            job_id = job.get('id')
            job_data = {
                'id': job_id,
                'type': 'scrape',
                'title': f"Scrape: {job.get('username', 'unknown')}",
                'platform': job.get('platform', 'instagram'),
                'status': job.get('state', 'unknown'),
                'created_at': job.get('created_at', ''),
                'archived_at': datetime.now().isoformat(),
                'starred': job.get('starred', False),
                'result': job.get('result'),
                'original_data': job
            }
            archived_jobs.append(job_data)
            state_manager.delete_job(job_id)
            archived_count += 1

    save_archived_jobs()

    return jsonify({'success': True, 'archived_count': archived_count})


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
        'username': username,
        'created_at': datetime.now().isoformat(),
        'errors': [],
        'temp_files': [],  # Track downloaded files for cleanup on abort
        'abort_requested': False  # Flag to signal abort to running thread
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
                if progress_pct is not None:  # Changed from elif to if - allows both phase AND progress_pct updates
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

            # Track downloaded video files for potential cleanup on abort
            reels = result.get('top_reels', []) or result.get('top_videos', [])
            for reel in reels:
                local_video = reel.get('local_video')
                if local_video and Path(local_video).exists():
                    active_scrapes[scrape_id]['temp_files'].append(local_video)

            # Check if abort was requested during scrape
            if active_scrapes[scrape_id].get('abort_requested'):
                logger.info("SCRAPE", f"Scrape {scrape_id} was aborted during execution")
                return  # Don't save to history, abort endpoint handles cleanup

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


@app.route('/api/scrape/batch', methods=['POST'])
def start_batch_scrape():
    """Start a batch scrape for multiple usernames"""
    data = request.json
    usernames = data.get('usernames', [])
    platform = data.get('platform', 'instagram').lower()

    # Clean usernames
    usernames = [u.strip().lstrip('@') for u in usernames if u and u.strip()]

    if not usernames:
        return jsonify({'error': 'At least one username required'}), 400

    if len(usernames) > 5:
        return jsonify({'error': 'Maximum 5 usernames per batch'}), 400

    # Check cookies based on platform
    cookies_file = TIKTOK_COOKIES_FILE if platform == 'tiktok' else COOKIES_FILE
    if not cookies_file.exists():
        return jsonify({
            'error': f'{platform.title()} cookies file not found ({cookies_file.name})'
        }), 400

    # Create batch ID
    batch_id = str(uuid.uuid4())
    logger.info("BATCH", f"Creating batch scrape for {len(usernames)} creators on {platform}", {
        "batch_id": batch_id,
        "usernames": usernames,
        "platform": platform
    })

    # Track batch
    active_batches[batch_id] = {
        'status': 'running',
        'platform': platform,
        'usernames': usernames,
        'total': len(usernames),
        'completed': 0,
        'current_username': None,
        'current_scrape_id': None,
        'scrape_ids': [],
        'created_at': datetime.now().isoformat()
    }

    # Scrape config (same for all in batch)
    scrape_config = {
        'platform': platform,
        'max_reels': data.get('max_reels', 100),
        'top_n': data.get('top_n', 10),
        'download': data.get('download', False),
        'transcribe': data.get('transcribe', False),
        'transcribe_provider': data.get('transcribe_provider', 'local'),
        'whisper_model': data.get('whisper_model', 'small.en')
    }

    # Get transcription settings
    openai_key = None
    if scrape_config['transcribe_provider'] == 'openai':
        config = load_config()
        openai_key = config.get('openai_key')

    def run_batch():
        """Process each username sequentially"""
        for i, username in enumerate(usernames):
            # Check if batch was aborted
            if active_batches[batch_id].get('status') == 'aborted':
                logger.info("BATCH", f"Batch {batch_id} was aborted, stopping at creator {i+1}/{len(usernames)}")
                break

            scrape_id = str(uuid.uuid4())
            active_batches[batch_id]['current_username'] = username
            active_batches[batch_id]['current_scrape_id'] = scrape_id
            active_batches[batch_id]['scrape_ids'].append(scrape_id)

            logger.info("BATCH", f"Starting scrape {i+1}/{len(usernames)}: @{username}", {
                "batch_id": batch_id,
                "scrape_id": scrape_id
            })

            # Create scrape job
            state_manager.create_job(scrape_id, username, platform, {**scrape_config, 'username': username})
            active_scrapes[scrape_id] = {
                'status': 'starting',
                'progress': f'Initializing {platform.title()} scrape...',
                'progress_pct': 0,
                'phase': 'initializing',
                'result': None,
                'platform': platform,
                'username': username,
                'created_at': datetime.now().isoformat(),
                'errors': [],
                'batch_id': batch_id,
                'temp_files': [],  # Track downloaded files for cleanup on abort
                'abort_requested': False  # Flag to signal abort to running thread
            }

            accumulated_errors = []

            def progress_callback(msg, phase=None, progress_pct=None):
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
                    if progress_pct is not None:  # Changed from elif to if - allows both phase AND progress_pct updates
                        active_scrapes[scrape_id]['progress_pct'] = progress_pct
                except Exception as e:
                    logger.warning("BATCH", f"Progress callback error: {e}")

            try:
                if platform == 'tiktok':
                    result = run_tiktok_scrape(
                        username=username,
                        cookies_path=str(TIKTOK_COOKIES_FILE),
                        max_videos=scrape_config['max_reels'],
                        top_n=scrape_config['top_n'],
                        download=scrape_config['download'],
                        transcribe=scrape_config['transcribe'],
                        whisper_model=scrape_config['whisper_model'],
                        transcribe_provider=scrape_config['transcribe_provider'],
                        openai_key=openai_key,
                        output_dir=str(get_output_directory('tiktok')),
                        headless=True,
                        progress_callback=progress_callback
                    )
                else:
                    result = run_scrape(
                        username=username,
                        cookies_path=str(COOKIES_FILE),
                        max_reels=scrape_config['max_reels'],
                        top_n=scrape_config['top_n'],
                        download=scrape_config['download'],
                        transcribe=scrape_config['transcribe'],
                        whisper_model=scrape_config['whisper_model'],
                        transcribe_provider=scrape_config['transcribe_provider'],
                        openai_key=openai_key,
                        output_dir=str(get_output_directory('instagram')),
                        progress_callback=progress_callback
                    )

                result['platform'] = platform
                if accumulated_errors:
                    result['errors'] = accumulated_errors

                # Track downloaded video files for potential cleanup on abort
                reels = result.get('top_reels', []) or result.get('top_videos', [])
                for reel in reels:
                    local_video = reel.get('local_video')
                    if local_video and Path(local_video).exists():
                        active_scrapes[scrape_id]['temp_files'].append(local_video)

                # Check if abort was requested during scrape
                if active_scrapes[scrape_id].get('abort_requested'):
                    logger.info("BATCH", f"Scrape {scrape_id} was aborted during execution")
                    continue  # Skip saving to history, move to next (which will also check batch abort)

                active_scrapes[scrape_id]['result'] = result
                active_scrapes[scrape_id]['status'] = result.get('status', 'complete')
                active_scrapes[scrape_id]['progress_pct'] = 100

                had_errors = len(accumulated_errors) > 0
                if result.get('status') == 'error':
                    state_manager.fail_job(scrape_id, result.get('error_code', 'UNKNOWN'),
                                          result.get('error', 'Unknown error'))
                else:
                    state_manager.complete_job(scrape_id, result, had_errors)

                add_to_history(result, include_errors=True)

            except Exception as e:
                error_msg = str(e)
                prefix = "TIK" if platform == 'tiktok' else "IG"
                error_code = logger.critical(prefix, f"Batch scrape failed: {error_msg}", {
                    "batch_id": batch_id,
                    "scrape_id": scrape_id,
                    "username": username
                }, exception=e)

                active_scrapes[scrape_id]['status'] = 'error'
                active_scrapes[scrape_id]['result'] = {
                    'id': scrape_id,
                    'status': 'error',
                    'error': f'[{error_code}] {error_msg}',
                    'error_code': error_code,
                    'platform': platform,
                    'username': username,
                    'timestamp': datetime.now().isoformat()
                }
                state_manager.fail_job(scrape_id, error_code, error_msg)
                add_to_history(active_scrapes[scrape_id]['result'], include_errors=True)

            # Update batch progress
            active_batches[batch_id]['completed'] = i + 1

        # Batch complete
        active_batches[batch_id]['status'] = 'complete'
        active_batches[batch_id]['current_username'] = None
        active_batches[batch_id]['current_scrape_id'] = None
        logger.info("BATCH", f"Batch scrape completed: {len(usernames)} creators", {"batch_id": batch_id})

    thread = Thread(target=run_batch, daemon=True)
    thread.start()

    return jsonify({'batch_id': batch_id, 'platform': platform, 'total': len(usernames)})


@app.route('/api/scrape/batch/<batch_id>/status')
def batch_status(batch_id):
    """Get batch scrape status"""
    if batch_id not in active_batches:
        return jsonify({'error': 'Batch not found'}), 404

    batch = active_batches[batch_id]

    # Get current scrape status if one is running
    current_scrape_status = None
    if batch['current_scrape_id'] and batch['current_scrape_id'] in active_scrapes:
        current = active_scrapes[batch['current_scrape_id']]
        current_scrape_status = {
            'username': batch['current_username'],
            'progress': current.get('progress', ''),
            'progress_pct': current.get('progress_pct', 0),
            'phase': current.get('phase', 'processing')
        }

    return jsonify({
        'status': batch['status'],
        'platform': batch['platform'],
        'total': batch['total'],
        'completed': batch['completed'],
        'current': current_scrape_status,
        'scrape_ids': batch['scrape_ids']
    })


@app.route('/api/scrape/direct', methods=['POST'])
def start_direct_scrape():
    """Scrape specific reels by URL or ID"""
    import re
    data = request.json
    platform = data.get('platform', 'instagram').lower()
    input_type = data.get('input_type', 'url')  # 'url' or 'id'
    inputs = data.get('inputs', [])

    if not inputs:
        return jsonify({'error': 'At least one reel URL or ID required'}), 400

    if len(inputs) > 5:
        return jsonify({'error': 'Maximum 5 reels per request'}), 400

    # Check cookies
    cookies_file = TIKTOK_COOKIES_FILE if platform == 'tiktok' else COOKIES_FILE
    if not cookies_file.exists():
        return jsonify({
            'error': f'{platform.title()} cookies file not found ({cookies_file.name})'
        }), 400

    # Parse inputs to get shortcodes/IDs
    reel_ids = []
    for inp in inputs:
        inp = inp.strip()
        if not inp:
            continue

        if input_type == 'url':
            # Extract shortcode from URL
            if platform == 'instagram':
                # Match patterns like /reel/ABC123/ or /p/ABC123/
                match = re.search(r'/(reel|p)/([A-Za-z0-9_-]+)', inp)
                if match:
                    reel_ids.append(match.group(2))
                else:
                    reel_ids.append(inp)  # Fallback to raw input
            else:  # tiktok
                # Match patterns like /video/1234567890
                match = re.search(r'/video/(\d+)', inp)
                if match:
                    reel_ids.append(match.group(1))
                else:
                    reel_ids.append(inp)
        else:
            # Direct ID input
            reel_ids.append(inp)

    if not reel_ids:
        return jsonify({'error': 'Could not parse any valid reel IDs'}), 400

    logger.info("DIRECT", f"Starting direct scrape for {len(reel_ids)} reels on {platform}", {
        "reel_ids": reel_ids,
        "platform": platform
    })

    # Scrape config
    scrape_config = {
        'platform': platform,
        'download': data.get('download', False),
        'transcribe': data.get('transcribe', False),
        'transcribe_provider': data.get('transcribe_provider', 'local'),
        'whisper_model': data.get('whisper_model', 'small.en')
    }

    # Get transcription settings
    openai_key = None
    if scrape_config['transcribe_provider'] == 'openai':
        config = load_config()
        openai_key = config.get('openai_key')

    # Pre-generate scrape IDs so we can return them immediately
    scrape_ids = [str(uuid.uuid4()) for _ in reel_ids]

    def run_direct_scrapes():
        """Process each reel individually"""
        for i, reel_id in enumerate(reel_ids):
            scrape_id = scrape_ids[i]

            logger.info("DIRECT", f"Scraping reel: {reel_id}", {
                "scrape_id": scrape_id,
                "platform": platform
            })

            # Create scrape job
            state_manager.create_job(scrape_id, f"reel:{reel_id}", platform, {**scrape_config, 'reel_id': reel_id})
            active_scrapes[scrape_id] = {
                'status': 'starting',
                'progress': f'Fetching reel {reel_id}...',
                'progress_pct': 0,
                'phase': 'initializing',
                'result': None,
                'platform': platform,
                'username': f'reel:{reel_id}',
                'reel_id': reel_id,
                'created_at': datetime.now().isoformat(),
                'errors': [],
                'temp_files': [],
                'abort_requested': False
            }

            def progress_callback(msg, phase=None, progress_pct=None):
                try:
                    active_scrapes[scrape_id]['progress'] = msg
                    active_scrapes[scrape_id]['status'] = 'running'
                    if phase:
                        active_scrapes[scrape_id]['phase'] = phase
                    if progress_pct is not None:
                        active_scrapes[scrape_id]['progress_pct'] = progress_pct
                except Exception:
                    pass

            try:
                # Step 1: Fetch reel metadata
                if platform == 'instagram':
                    from scraper.core import fetch_single_reel, download_video, transcribe_video_openai
                    reel, error = fetch_single_reel(reel_id, str(COOKIES_FILE), progress_callback)
                    cookies_path = str(COOKIES_FILE)
                    output_dir = get_output_directory('instagram')
                else:
                    from scraper.tiktok import fetch_single_video, download_tiktok_video
                    reel, error = fetch_single_video(reel_id, str(TIKTOK_COOKIES_FILE), progress_callback)
                    cookies_path = str(TIKTOK_COOKIES_FILE)
                    output_dir = get_output_directory('tiktok')

                if error or not reel:
                    raise Exception(error or "Failed to fetch reel metadata")

                # Build result structure matching run_scrape output
                result = {
                    'id': scrape_id,
                    'username': reel.get('owner', f'reel:{reel_id}'),
                    'timestamp': datetime.now().isoformat(),
                    'status': 'complete',
                    'platform': platform,
                    'total_reels': 1,
                    'top_reels': [reel] if platform == 'instagram' else [],
                    'top_videos': [reel] if platform == 'tiktok' else [],
                    'output_dir': str(output_dir),
                    'download_errors': [],
                    'transcription_errors': []
                }

                # Step 2: Download video if requested (reuse existing logic from run_scrape)
                if scrape_config['download'] or scrape_config['transcribe']:
                    progress_callback(f"Downloading video...", phase='downloading', progress_pct=30)

                    video_dir = output_dir / f"direct_{reel_id}"
                    video_dir.mkdir(parents=True, exist_ok=True)
                    filename = f"01_{reel.get('views', 0)}views_{reel_id}.mp4"
                    filepath = video_dir / filename

                    if platform == 'instagram':
                        success = download_video(reel['url'], filepath, cookies_path, reel.get('video_url'))
                    else:
                        success = download_tiktok_video(reel['url'], str(filepath), cookies_path)

                    if success:
                        reel['local_video'] = str(filepath)
                        active_scrapes[scrape_id]['temp_files'].append(str(filepath))
                    else:
                        reel['local_video'] = None
                        result['download_errors'].append({'shortcode': reel_id, 'error': 'Download failed'})

                # Step 3: Transcribe if requested
                if scrape_config['transcribe'] and reel.get('local_video'):
                    progress_callback(f"Transcribing video...", phase='transcribing', progress_pct=60)

                    transcript_dir = video_dir / "transcripts"
                    transcript_dir.mkdir(exist_ok=True)
                    transcript_file = transcript_dir / f"01_{reel_id}.txt"

                    # Transcription progress callback wrapper
                    def transcribe_progress(msg):
                        progress_callback(msg, phase='transcribing', progress_pct=70)

                    try:
                        if scrape_config['transcribe_provider'] == 'openai' and openai_key:
                            # OpenAI: use heartbeat thread for progress updates
                            import threading
                            transcribe_start = time.time()
                            stop_heartbeat = threading.Event()

                            def openai_heartbeat():
                                tick = 0
                                while not stop_heartbeat.is_set():
                                    stop_heartbeat.wait(5)
                                    if not stop_heartbeat.is_set():
                                        tick += 1
                                        elapsed = int(time.time() - transcribe_start)
                                        progress_callback(f"Transcribing (OpenAI) - {elapsed}s elapsed...", phase='transcribing', progress_pct=70)

                            heartbeat_thread = threading.Thread(target=openai_heartbeat, daemon=True)
                            heartbeat_thread.start()

                            try:
                                transcript = transcribe_video_openai(reel['local_video'], openai_key, transcript_file)
                            finally:
                                stop_heartbeat.set()
                                heartbeat_thread.join(timeout=1)
                        else:
                            # Local whisper - pass progress callback for heartbeat updates
                            from scraper.core import transcribe_video, load_whisper_model
                            progress_callback(f"Loading Whisper model ({scrape_config['whisper_model']})...", phase='transcribing', progress_pct=65)
                            model = load_whisper_model(scrape_config['whisper_model'])
                            transcript = transcribe_video(
                                reel['local_video'], model, transcript_file,
                                progress_callback=transcribe_progress,
                                video_index=1, total_videos=1
                            )

                        reel['transcript'] = transcript
                        reel['transcript_file'] = str(transcript_file) if transcript else None
                    except Exception as e:
                        reel['transcript'] = None
                        result['transcription_errors'].append({'shortcode': reel_id, 'error': str(e)})

                # Clean up video if not keeping it (same logic as core.py)
                if not scrape_config['download']:
                    video_path = reel.get('local_video')
                    if video_path and os.path.exists(video_path):
                        try:
                            os.remove(video_path)
                            progress_callback(f"Cleaned up temporary video", phase='cleanup', progress_pct=95)
                        except Exception as e:
                            print(f"[DIRECT] Failed to remove temp video: {video_path}")
                    reel['local_video'] = None

                progress_callback(f"Complete", phase='complete', progress_pct=100)

                active_scrapes[scrape_id]['result'] = result
                active_scrapes[scrape_id]['status'] = 'complete'
                active_scrapes[scrape_id]['progress_pct'] = 100

                state_manager.complete_job(scrape_id, result, False)
                add_to_history(result, include_errors=True)

            except Exception as e:
                error_msg = str(e)
                error_code = logger.error("DIRECT", f"Direct scrape failed: {error_msg}", {
                    "scrape_id": scrape_id,
                    "reel_id": reel_id
                })

                active_scrapes[scrape_id]['status'] = 'error'
                active_scrapes[scrape_id]['result'] = {
                    'id': scrape_id,
                    'status': 'error',
                    'error': f'[{error_code}] {error_msg}',
                    'error_code': error_code,
                    'platform': platform,
                    'username': f'reel:{reel_id}',
                    'timestamp': datetime.now().isoformat()
                }
                state_manager.fail_job(scrape_id, error_code, error_msg)
                add_to_history(active_scrapes[scrape_id]['result'], include_errors=True)

    thread = Thread(target=run_direct_scrapes, daemon=True)
    thread.start()

    return jsonify({'scrape_ids': scrape_ids, 'platform': platform, 'total': len(reel_ids)})


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
    """Abort a running scrape with comprehensive cleanup"""
    if scrape_id not in active_scrapes:
        return jsonify({'error': 'Scrape not found or already completed'}), 404

    scrape = active_scrapes[scrape_id]
    username = scrape.get('username', 'unknown')
    platform = scrape.get('platform', 'instagram')

    logger.info("ABORT", f"Aborting scrape {scrape_id} (@{username})")

    # 1. Set abort flag so running thread knows to stop
    scrape['abort_requested'] = True
    scrape['status'] = 'aborted'
    scrape['progress'] = 'Aborted by user'

    # 2. Update state manager
    state_manager.abort_job(scrape_id, "User cancelled")

    # 3. Clean up any downloaded temp files
    temp_files = scrape.get('temp_files', [])
    files_deleted = 0
    for file_path in temp_files:
        try:
            if Path(file_path).exists():
                Path(file_path).unlink()
                files_deleted += 1
                logger.debug("ABORT", f"Deleted temp file: {file_path}")
        except Exception as e:
            logger.warning("ABORT", f"Failed to delete temp file {file_path}: {e}")

    # 4. Remove any partial data from history (if it was saved)
    history = load_history()
    original_len = len(history)
    history = [h for h in history if h.get('id') != scrape_id]
    if len(history) < original_len:
        save_history(history)
        logger.debug("ABORT", f"Removed partial data from history for {scrape_id}")

    logger.info("ABORT", f"Scrape {scrape_id} aborted successfully", {
        "files_deleted": files_deleted,
        "history_cleaned": len(history) < original_len
    })

    return jsonify({
        'success': True,
        'message': 'Scrape aborted',
        'files_cleaned': files_deleted
    })


@app.route('/api/scrape/batch/<batch_id>/abort', methods=['POST'])
def abort_batch(batch_id):
    """Abort a batch scrape - stops current and cancels pending"""
    if batch_id not in active_batches:
        return jsonify({'error': 'Batch not found or already completed'}), 404

    batch = active_batches[batch_id]
    logger.info("ABORT", f"Aborting batch {batch_id}", {
        "total": batch.get('total', 0),
        "completed": batch.get('completed', 0)
    })

    # 1. Mark batch as aborted
    batch['status'] = 'aborted'

    # 2. Abort the current running scrape if any
    current_scrape_id = batch.get('current_scrape_id')
    files_cleaned = 0
    if current_scrape_id and current_scrape_id in active_scrapes:
        # Abort the current scrape (this cleans up its files)
        scrape = active_scrapes[current_scrape_id]
        scrape['abort_requested'] = True
        scrape['status'] = 'aborted'
        state_manager.abort_job(current_scrape_id, "Batch cancelled")

        # Clean up temp files
        for file_path in scrape.get('temp_files', []):
            try:
                if Path(file_path).exists():
                    Path(file_path).unlink()
                    files_cleaned += 1
            except Exception as e:
                logger.warning("ABORT", f"Failed to delete temp file {file_path}: {e}")

        # Remove from history
        history = load_history()
        history = [h for h in history if h.get('id') != current_scrape_id]
        save_history(history)

    # 3. Pending scrapes are never started, so just clear the batch
    batch['current_username'] = None
    batch['current_scrape_id'] = None

    logger.info("ABORT", f"Batch {batch_id} aborted successfully", {
        "scrapes_cancelled": batch.get('total', 0) - batch.get('completed', 0),
        "files_cleaned": files_cleaned
    })

    return jsonify({
        'success': True,
        'message': 'Batch aborted',
        'completed_before_abort': batch.get('completed', 0),
        'total': batch.get('total', 0),
        'files_cleaned': files_cleaned
    })


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


@app.route('/api/history/<scrape_id>', methods=['GET'])
def get_history_item(scrape_id):
    """Get a specific history item"""
    history = load_history()
    item = next((h for h in history if h.get('id') == scrape_id), None)
    if not item:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(item)


@app.route('/api/history/<scrape_id>', methods=['DELETE'])
def delete_history_item(scrape_id):
    """Delete a history item"""
    history = load_history()
    history = [h for h in history if h.get('id') != scrape_id]
    save_history(history)
    return jsonify({'success': True})


@app.route('/api/history/<scrape_id>/star', methods=['POST'])
def toggle_history_star(scrape_id):
    """Toggle starred status of a history item"""
    history = load_history()
    for item in history:
        if item.get('id') == scrape_id:
            item['starred'] = not item.get('starred', False)
            save_history(history)
            return jsonify({'success': True, 'starred': item['starred']})
    return jsonify({'error': 'Not found'}), 404


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
        'default_output_directory': str(OUTPUT_DIR),
        'detail_panel_width': config.get('detail_panel_width', 600),
        'jobs_view_mode': config.get('jobs_view_mode', 'list'),
        'asset_view_mode': config.get('asset_view_mode', 'grid-4')
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
    if 'detail_panel_width' in data:
        config['detail_panel_width'] = int(data['detail_panel_width'])
    if 'jobs_view_mode' in data:
        config['jobs_view_mode'] = data['jobs_view_mode']
    if 'asset_view_mode' in data:
        config['asset_view_mode'] = data['asset_view_mode']

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

# Active skeleton ripper jobs (persisted to disk)
SKELETON_JOBS_FILE = STATE_DIR / 'skeleton_jobs.json'

def load_skeleton_jobs() -> dict:
    """Load skeleton jobs from disk."""
    if SKELETON_JOBS_FILE.exists():
        try:
            with open(SKELETON_JOBS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning("SKELETON", f"Failed to load skeleton jobs: {e}")
    return {}

def save_skeleton_jobs():
    """Save skeleton jobs to disk."""
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(SKELETON_JOBS_FILE, 'w') as f:
            json.dump(active_skeleton_jobs, f, indent=2, default=str)
    except Exception as e:
        logger.warning("SKELETON", f"Failed to save skeleton jobs: {e}")

# Initialize from disk
active_skeleton_jobs = load_skeleton_jobs()

# =========================================
# ARCHIVED JOBS PERSISTENCE
# =========================================
ARCHIVED_JOBS_FILE = STATE_DIR / 'archived_jobs.json'

def load_archived_jobs() -> list:
    """Load archived jobs from disk."""
    if ARCHIVED_JOBS_FILE.exists():
        try:
            with open(ARCHIVED_JOBS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning("ARCHIVE", f"Failed to load archived jobs: {e}")
    return []

def save_archived_jobs():
    """Save archived jobs to disk."""
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(ARCHIVED_JOBS_FILE, 'w') as f:
            json.dump(archived_jobs, f, indent=2, default=str)
    except Exception as e:
        logger.warning("ARCHIVE", f"Failed to save archived jobs: {e}")

# Initialize archived jobs from disk
archived_jobs = load_archived_jobs()


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
        'result': None,
        'creators': usernames,
        'platform': platform,
        'videos_per_creator': videos_per_creator,
        'created_at': datetime.now().isoformat(),
        'starred': False
    }
    save_skeleton_jobs()

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
            # Store detailed progress info (phase info for display)
            active_skeleton_jobs[job_id]['progress'] = {
                'status': progress.status.value,  # Keep pipeline status in progress for display
                'phase': progress.phase,
                'message': progress.message,
                # Core counts
                'videos_scraped': progress.videos_scraped,
                'videos_downloaded': progress.videos_downloaded,
                'videos_transcribed': progress.videos_transcribed,
                'transcripts_from_cache': progress.transcripts_from_cache,
                'valid_transcripts': progress.valid_transcripts,
                'skeletons_extracted': progress.skeletons_extracted,
                'total_target': progress.total_target,
                # Granular progress
                'current_creator': progress.current_creator,
                'current_creator_index': progress.current_creator_index,
                'total_creators': progress.total_creators,
                'reels_fetched': progress.reels_fetched,
                'current_video_index': progress.current_video_index,
                'extraction_batch': progress.extraction_batch,
                'extraction_total_batches': progress.extraction_total_batches,
                # Errors
                'errors': progress.errors
            }
            # Use 'running' status consistently (like regular scrapes) - only change on completion
            active_skeleton_jobs[job_id]['status'] = 'running'

        try:
            result = pipeline.run(job_config, on_progress=progress_callback, job_id=job_id)

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

            # Create skeleton_report asset in library
            if result.success and result.report_path:
                try:
                    creators = active_skeleton_jobs[job_id].get('creators', [])
                    report_title = f"Skeleton Report - {', '.join(creators[:2])}{'...' if len(creators) > 2 else ''}"
                    preview_text = f"{len(result.skeletons)} skeletons extracted from {len(creators)} creators"

                    # Calculate aggregate stats for card display
                    total_views = sum(s.get('views', 0) for s in result.skeletons)
                    avg_views = total_views // len(result.skeletons) if result.skeletons else 0
                    hook_words = [s.get('hook_word_count', 0) for s in result.skeletons if s.get('hook_word_count')]
                    avg_hook_words = round(sum(hook_words) / len(hook_words), 1) if hook_words else 0

                    asset = Asset.create(
                        type='skeleton_report',
                        title=report_title,
                        content_path=str(Path(result.report_path).parent),
                        preview=preview_text,
                        metadata={
                            'job_id': result.job_id,
                            'creators': creators,
                            'skeletons_count': len(result.skeletons),
                            'report_path': result.report_path,
                            'skeletons_path': result.skeletons_path,
                            'synthesis_path': result.synthesis_path,
                            # Aggregate stats for card display
                            'total_views': total_views,
                            'avg_views': avg_views,
                            'avg_hook_words': avg_hook_words
                        }
                    )
                    logger.info("SKELETON", f"Created skeleton_report asset: {asset.id}")
                except Exception as asset_err:
                    logger.warning("SKELETON", f"Failed to create asset for job {job_id}: {asset_err}")

            logger.info("SKELETON", f"Job {job_id} completed", {
                "success": result.success,
                "skeletons": len(result.skeletons)
            })
            save_skeleton_jobs()

        except Exception as e:
            logger.error("SKELETON", f"Job {job_id} failed: {e}")
            active_skeleton_jobs[job_id]['status'] = 'failed'
            active_skeleton_jobs[job_id]['result'] = {
                'success': False,
                'error': str(e)
            }
            save_skeleton_jobs()

    thread = Thread(target=run_skeleton_job, daemon=True)
    thread.start()

    return jsonify({
        'success': True,
        'job_id': job_id,
        'status': 'pending',
        'message': 'Skeleton ripper job started'
    })


@app.route('/api/skeleton-ripper/status/<job_id>')
def skeleton_ripper_status(job_id):
    """Get skeleton ripper job status"""
    if job_id not in active_skeleton_jobs:
        return jsonify({'success': False, 'error': 'Job not found'}), 404

    job = active_skeleton_jobs[job_id]
    progress = job.get('progress') or {}

    # Calculate progress percentage based on pipeline status and counts
    # Pipeline phases: scraping (includes download+transcribe) -> extracting -> aggregating -> synthesizing
    pipeline_status = progress.get('status', '')
    total_target = progress.get('total_target', 1) or 1
    videos_downloaded = progress.get('videos_downloaded', 0)
    videos_transcribed = progress.get('videos_transcribed', 0)
    skeletons_extracted = progress.get('skeletons_extracted', 0)
    valid_transcripts = progress.get('valid_transcripts', 0) or total_target

    if job.get('status') == 'complete' or pipeline_status == 'complete':
        progress_pct = 100
    elif pipeline_status == 'synthesizing':
        progress_pct = 95
    elif pipeline_status == 'aggregating':
        progress_pct = 90
    elif pipeline_status == 'extracting':
        # Extracting: 70-90%
        extract_pct = (skeletons_extracted / valid_transcripts) * 100 if valid_transcripts else 0
        progress_pct = 70 + int(extract_pct * 0.20)
    elif pipeline_status == 'scraping':
        # Scraping phase includes fetch, download, transcribe
        # Progress within scraping: download gives 0-35%, transcribe gives 35-70%
        if videos_transcribed > 0:
            # In transcription part of scraping phase
            trans_pct = (videos_transcribed / total_target) * 100 if total_target else 0
            progress_pct = 35 + int(trans_pct * 0.35)
        elif videos_downloaded > 0:
            # In download part of scraping phase
            dl_pct = (videos_downloaded / total_target) * 100 if total_target else 0
            progress_pct = int(dl_pct * 0.35)
        else:
            # Still fetching reels (0-5%)
            progress_pct = 5
    else:
        progress_pct = 0

    return jsonify({
        'success': True,
        'job_id': job_id,
        'status': job['status'],
        'progress': job['progress'],
        'progress_pct': min(progress_pct, 100),
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


@app.route('/api/skeleton-ripper/report/<job_id>/json')
def skeleton_ripper_report_json(job_id):
    """Get the skeletons JSON for a completed job"""
    if job_id not in active_skeleton_jobs:
        return jsonify({'error': 'Job not found'}), 404

    job = active_skeleton_jobs[job_id]
    if not job.get('result') or not job['result'].get('report_path'):
        return jsonify({'error': 'Report not available'}), 404

    # The report_path points to report.md, we need skeletons.json in the same dir
    report_path = Path(job['result']['report_path'])
    skeletons_path = report_path.parent / 'skeletons.json'

    if not skeletons_path.exists():
        return jsonify([])  # Return empty array if no skeletons

    return send_file(skeletons_path, mimetype='application/json')


@app.route('/api/skeleton-ripper/history')
def skeleton_ripper_history():
    """Get list of past skeleton ripper reports"""
    import json
    from datetime import datetime

    history = []
    reports_dir = Path('output/skeleton_reports')

    if not reports_dir.exists():
        return jsonify({'success': True, 'history': []})

    # Get all report directories, sorted by newest first
    report_dirs = sorted(reports_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)

    for report_dir in report_dirs[:20]:  # Limit to 20 most recent
        if not report_dir.is_dir():
            continue

        report_path = report_dir / 'report.md'
        skeletons_path = report_dir / 'skeletons.json'

        if not report_path.exists():
            continue

        # Parse directory name for timestamp and job_id
        dir_name = report_dir.name
        parts = dir_name.split('_')
        if len(parts) >= 3:
            timestamp_str = f"{parts[0]}_{parts[1]}"
            job_id = parts[2]
        else:
            timestamp_str = dir_name
            job_id = dir_name

        # Try to get more info from skeletons.json
        creators = []
        skeleton_count = 0
        platform = 'unknown'
        if skeletons_path.exists():
            try:
                with open(skeletons_path, 'r') as f:
                    skeletons = json.load(f)
                    skeleton_count = len(skeletons)
                    creators = list(set(s.get('creator_username', 'unknown') for s in skeletons))
                    platform = skeletons[0].get('platform', 'unknown') if skeletons else 'unknown'
            except:
                pass

        # Parse timestamp
        try:
            dt = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
            formatted_date = dt.strftime('%b %d, %Y %H:%M')
        except:
            formatted_date = timestamp_str

        history.append({
            'id': dir_name,
            'job_id': job_id,
            'date': formatted_date,
            'creators': creators,
            'skeleton_count': skeleton_count,
            'platform': platform,
            'report_path': str(report_path)
        })

    return jsonify({'success': True, 'history': history})


@app.route('/api/skeleton-ripper/history/<report_id>')
def skeleton_ripper_history_report(report_id):
    """Get a specific historical report"""
    report_path = Path('output/skeleton_reports') / report_id / 'report.md'

    if not report_path.exists():
        return jsonify({'error': 'Report not found'}), 404

    return send_file(report_path, mimetype='text/markdown')


@app.route('/api/skeleton-ripper/history/<report_id>/json')
def skeleton_ripper_history_report_json(report_id):
    """Get the skeletons JSON for a historical report"""
    skeletons_path = Path('output/skeleton_reports') / report_id / 'skeletons.json'

    if not skeletons_path.exists():
        return jsonify([])  # Return empty array if no skeletons

    return send_file(skeletons_path, mimetype='application/json')


# =============================================================================
# SKELETON RIPPER - VIDEO ENDPOINTS
# =============================================================================

@app.route('/api/skeleton-ripper/video/<report_id>/<video_id>/download', methods=['POST'])
def skeleton_ripper_download_video(report_id, video_id):
    """Download a video on-demand for a skeleton report"""
    skeletons_path = Path('output/skeleton_reports') / report_id / 'skeletons.json'

    if not skeletons_path.exists():
        return jsonify({'success': False, 'error': 'Report not found'}), 404

    try:
        skeletons = json.loads(skeletons_path.read_text())
        skeleton = next((s for s in skeletons if s.get('video_id') == video_id), None)

        if not skeleton:
            return jsonify({'success': False, 'error': 'Skeleton not found'}), 404

        video_url = skeleton.get('video_url', '')
        reel_url = skeleton.get('url', '')

        if not video_url and not reel_url:
            return jsonify({'success': False, 'error': 'No video URL available'}), 400

        # Create videos directory for this report
        videos_dir = Path('output/skeleton_reports') / report_id / 'videos'
        videos_dir.mkdir(exist_ok=True)

        output_path = videos_dir / f"{video_id}.mp4"

        success = download_video(
            reel_url=reel_url,
            output_path=str(output_path),
            cookies_file=str(COOKIES_FILE),
            video_url=video_url
        )

        if success and output_path.exists():
            skeleton['local_video'] = str(output_path)
            skeletons_path.write_text(json.dumps(skeletons, indent=2))

            return jsonify({
                'success': True,
                'video_path': str(output_path),
                'message': 'Video downloaded successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'Download failed'}), 500

    except Exception as e:
        print(f"[SKELETON] Video download error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/skeleton-ripper/video/<report_id>/<video_id>')
def skeleton_ripper_serve_video(report_id, video_id):
    """Serve a downloaded skeleton video"""
    video_path = Path('output/skeleton_reports') / report_id / 'videos' / f"{video_id}.mp4"

    if not video_path.exists():
        return jsonify({'error': 'Video not found'}), 404

    return send_file(video_path, mimetype='video/mp4')


@app.route('/api/skeleton-ripper/video/<report_id>/<video_id>/status')
def skeleton_ripper_video_status(report_id, video_id):
    """Check if a video is downloaded"""
    video_path = Path('output/skeleton_reports') / report_id / 'videos' / f"{video_id}.mp4"

    return jsonify({
        'downloaded': video_path.exists(),
        'path': str(video_path) if video_path.exists() else None
    })


# ============================================================================
# ASSET MANAGEMENT API (P0)
# ============================================================================

@app.route('/api/assets', methods=['POST'])
def create_asset():
    """Create a new asset"""
    data = request.get_json()

    required = ['type', 'title']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields: type, title'}), 400

    try:
        asset = Asset.create(
            type=data['type'],
            title=data['title'],
            content_path=data.get('content_path'),
            preview=data.get('preview'),
            metadata=data.get('metadata')
        )
        return jsonify(asset.to_dict()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/assets/save-skeleton', methods=['POST'])
def save_skeleton_asset():
    """Save an individual skeleton from a skeleton report as a separate asset"""
    data = request.get_json()

    required = ['skeleton_data', 'source_report_id']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields: skeleton_data, source_report_id'}), 400

    sk = data['skeleton_data']
    source_report_id = data['source_report_id']

    # Build title from hook
    hook = sk.get('hook', 'Unknown hook')[:50]
    creator = sk.get('creator_username', 'unknown')
    title = f"@{creator}: {hook}..." if len(sk.get('hook', '')) > 50 else f"@{creator}: {hook}"

    # Build preview
    preview_parts = []
    if sk.get('hook'):
        preview_parts.append(f"HOOK: {sk['hook'][:100]}")
    if sk.get('problem'):
        preview_parts.append(f"PROBLEM: {sk['problem'][:100]}")
    if sk.get('cta'):
        preview_parts.append(f"CTA: {sk['cta'][:100]}")
    preview = '\n'.join(preview_parts) if preview_parts else 'No preview available'

    try:
        asset = Asset.create(
            type='skeleton',
            title=title,
            preview=preview,
            metadata={
                'hook': sk.get('hook'),
                'problem': sk.get('problem'),
                'key_points': sk.get('key_points', []),
                'cta': sk.get('cta'),
                'value': sk.get('value'),
                'creator_username': sk.get('creator_username'),
                'views': sk.get('views') or sk.get('metrics', {}).get('views', 0),
                'likes': sk.get('likes') or sk.get('metrics', {}).get('likes', 0),
                'video_url': sk.get('video_url'),
                'source_report_id': source_report_id
            }
        )
        return jsonify(asset.to_dict()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/assets/save-transcript', methods=['POST'])
def save_transcript_asset():
    """Save an individual transcript from a scrape report as a separate asset"""
    data = request.get_json()

    required = ['reel_data', 'source_report_id', 'username']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields: reel_data, source_report_id, username'}), 400

    reel = data['reel_data']
    source_report_id = data['source_report_id']
    username = data['username']

    # Build title from caption
    caption = reel.get('caption', 'No caption')[:50]
    title = f"@{username}: {caption}..." if len(reel.get('caption', '')) > 50 else f"@{username}: {caption}"

    # Preview is the transcript itself (truncated)
    transcript = reel.get('transcript', '')
    preview = transcript[:500] + '...' if len(transcript) > 500 else transcript

    try:
        asset = Asset.create(
            type='transcript',
            title=title,
            preview=preview,
            metadata={
                'transcript': transcript,
                'caption': reel.get('caption'),
                'views': reel.get('views', 0),
                'likes': reel.get('likes', 0),
                'comments': reel.get('comments', 0),
                'video_url': reel.get('url'),
                'username': username,
                'source_report_id': source_report_id
            }
        )
        return jsonify(asset.to_dict()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/assets', methods=['GET'])
def list_assets():
    """List assets with optional filters"""
    asset_type = request.args.get('type')
    starred = request.args.get('starred')
    collection_id = request.args.get('collection_id')
    job_id = request.args.get('job_id')  # Filter by source job
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))

    if starred is not None:
        starred = starred.lower() == 'true'

    assets = Asset.list(
        type=asset_type,
        starred=starred,
        collection_id=collection_id,
        limit=limit,
        offset=offset
    )

    # Include collections for each asset
    result = []
    for asset in assets:
        asset_dict = asset.to_dict()
        asset_dict['collections'] = [c.to_dict() for c in asset.get_collections()]

        # Filter by job_id if provided (check metadata.job_id or metadata.source_job_id)
        if job_id:
            meta = asset.metadata or {}
            asset_job_id = meta.get('job_id') or meta.get('source_job_id')
            # Also check source_report's job_id for child assets
            source_report_id = meta.get('source_report_id')
            if asset_job_id != job_id and source_report_id != job_id:
                continue

        result.append(asset_dict)

    return jsonify(result)


@app.route('/api/assets/search', methods=['GET'])
def search_assets():
    """Full-text search across assets"""
    query = request.args.get('q', '')
    limit = int(request.args.get('limit', 20))

    if not query:
        return jsonify([])

    assets = Asset.search(query, limit=limit)
    return jsonify([a.to_dict() for a in assets])


@app.route('/api/assets/<asset_id>', methods=['GET'])
def get_asset(asset_id):
    """Get a single asset by ID"""
    asset = Asset.get(asset_id)
    if not asset:
        return jsonify({'error': 'Asset not found'}), 404

    result = asset.to_dict()
    result['collections'] = [c.to_dict() for c in asset.get_collections()]
    return jsonify(result)


@app.route('/api/assets/<asset_id>', methods=['PUT'])
def update_asset(asset_id):
    """Update an asset"""
    asset = Asset.get(asset_id)
    if not asset:
        return jsonify({'error': 'Asset not found'}), 404

    data = request.get_json()
    allowed = {'title', 'content_path', 'preview', 'metadata', 'starred'}
    updates = {k: v for k, v in data.items() if k in allowed}

    if updates:
        asset.update(**updates)

    return jsonify(asset.to_dict())


@app.route('/api/assets/<asset_id>/star', methods=['POST'])
def toggle_asset_star(asset_id):
    """Toggle starred status for an asset"""
    asset = Asset.get(asset_id)
    if not asset:
        return jsonify({'error': 'Asset not found'}), 404

    new_starred = not asset.starred
    asset.update(starred=new_starred)

    return jsonify({
        'success': True,
        'asset_id': asset_id,
        'starred': new_starred
    })


@app.route('/api/assets/<asset_id>', methods=['DELETE'])
def delete_asset(asset_id):
    """Delete an asset and clean up associated files"""
    asset = Asset.get(asset_id)
    if not asset:
        return jsonify({'error': 'Asset not found'}), 404

    cleaned_files = []
    metadata = asset.metadata or {}

    # Clean up video files for scrape_report assets
    if asset.type == 'scrape_report':
        original_id = metadata.get('original_id')

        if original_id:
            history = load_history()
            scrape_data = next((h for h in history if h.get('id') == original_id), None)

            if scrape_data:
                top_reels = scrape_data.get('top_reels', [])
                for reel in top_reels:
                    video_path = reel.get('local_video')
                    if video_path and os.path.exists(video_path):
                        try:
                            os.remove(video_path)
                            cleaned_files.append(video_path)
                            print(f"[DELETE] Cleaned up video: {video_path}")
                        except Exception as e:
                            print(f"[DELETE] Failed to remove video {video_path}: {e}")

                # Also remove the scrape from history
                history = [h for h in history if h.get('id') != original_id]
                save_history(history)
                print(f"[DELETE] Removed scrape {original_id} from history")

        # Clean up content_path directory
        if asset.content_path:
            content_dir = Path(asset.content_path)
            if content_dir.exists() and content_dir.is_dir():
                try:
                    import shutil
                    shutil.rmtree(content_dir)
                    cleaned_files.append(str(content_dir))
                    print(f"[DELETE] Cleaned up directory: {content_dir}")
                except Exception as e:
                    print(f"[DELETE] Failed to remove directory {content_dir}: {e}")

    # Clean up skeleton_report assets
    elif asset.type == 'skeleton_report':
        job_id = metadata.get('job_id')

        # Remove from skeleton_jobs.json
        if job_id and job_id in active_skeleton_jobs:
            del active_skeleton_jobs[job_id]
            save_skeleton_jobs()
            print(f"[DELETE] Removed skeleton job: {job_id}")

        # Clean up content_path directory
        if asset.content_path:
            content_dir = Path(asset.content_path)
            if content_dir.exists() and content_dir.is_dir():
                try:
                    import shutil
                    shutil.rmtree(content_dir)
                    cleaned_files.append(str(content_dir))
                    print(f"[DELETE] Cleaned up directory: {content_dir}")
                except Exception as e:
                    print(f"[DELETE] Failed to remove directory {content_dir}: {e}")

    # Clean up individual skeleton assets (no files, just metadata)
    elif asset.type == 'skeleton':
        # Nothing to clean up on disk, just delete from DB
        print(f"[DELETE] Removing skeleton asset: {asset.title}")

    # Clean up transcript assets
    elif asset.type == 'transcript':
        # Transcript content is stored in metadata, no files to clean
        print(f"[DELETE] Removing transcript asset: {asset.title}")

    asset.delete()
    return jsonify({'success': True, 'cleaned_files': cleaned_files})


def normalize_path(path_str):
    """
    Normalize paths for cross-platform compatibility.
    - WSL paths (/mnt/c/...) -> Windows paths (C:/...)
    - Relative paths -> Absolute paths based on BASE_DIR
    - Mac/Linux native paths stay as-is
    """
    import platform

    if not path_str:
        return path_str

    # If running on Windows and path looks like WSL format, convert it
    if platform.system() == 'Windows' and path_str.startswith('/mnt/'):
        if len(path_str) > 6:
            drive_letter = path_str[5].upper()
            rest_of_path = path_str[7:]
            return f"{drive_letter}:/{rest_of_path}"

    # If the path doesn't exist and is absolute, try resolving relative to BASE_DIR
    test_path = Path(path_str)
    if not test_path.exists():
        # Try as relative path from BASE_DIR
        relative_attempt = BASE_DIR / path_str.lstrip('/')
        if relative_attempt.exists():
            return str(relative_attempt)

        # On Mac/Linux, WSL paths won't work - try extracting relative portion
        if path_str.startswith('/mnt/'):
            # Extract everything after /mnt/X/Users/.../ReelRecon/
            parts = path_str.split('ReelRecon/')
            if len(parts) > 1:
                relative_path = parts[1]
                mac_attempt = BASE_DIR / relative_path
                if mac_attempt.exists():
                    return str(mac_attempt)

    return path_str


@app.route('/api/assets/<asset_id>/content', methods=['GET'])
def get_asset_content(asset_id):
    """Get the full content for an asset (skeleton data or scrape data)"""
    asset = Asset.get(asset_id)
    if not asset:
        return jsonify({'error': 'Asset not found'}), 404

    content_path = normalize_path(asset.content_path)
    asset_type = asset.type
    metadata = asset.metadata or {}

    if asset_type == 'skeleton_report':
        # Skeleton Report: read skeletons.json and report.md from the directory
        content_dir = Path(content_path)

        skeletons = []
        markdown = ''

        # Read skeletons.json
        skeletons_file = content_dir / 'skeletons.json'
        if skeletons_file.exists():
            try:
                skeletons = json.loads(skeletons_file.read_text(encoding='utf-8'))
            except Exception as e:
                print(f"[ASSET CONTENT] Error reading skeletons.json: {e}")

        # Read report.md
        report_file = content_dir / 'report.md'
        if report_file.exists():
            try:
                markdown = report_file.read_text(encoding='utf-8')
            except Exception as e:
                print(f"[ASSET CONTENT] Error reading report.md: {e}")

        return jsonify({
            'type': 'skeleton_report',
            'skeletons': skeletons,
            'markdown': markdown,
            'report_id': metadata.get('report_id', content_dir.name),
            'video_count': len(skeletons),
            'creators': metadata.get('creators', [])
        })

    elif asset_type == 'scrape_report':
        # Scrape: find matching entry in scrape_history.json
        original_id = metadata.get('original_id')
        username = metadata.get('username')

        history = load_history()

        # Find matching scrape entry
        scrape_data = None
        if original_id:
            scrape_data = next((h for h in history if h.get('id') == original_id), None)

        if not scrape_data and username:
            # Fallback: find by username
            scrape_data = next((h for h in history if h.get('username') == username), None)

        if not scrape_data:
            return jsonify({
                'type': 'scrape_report',
                'error': 'Scrape data not found in history',
                'metadata': metadata
            })

        # Return the full scrape data
        return jsonify({
            'type': 'scrape_report',
            'scrape_id': scrape_data.get('id'),
            'username': scrape_data.get('username'),
            'platform': scrape_data.get('platform', 'instagram'),
            'timestamp': scrape_data.get('timestamp'),
            'profile': scrape_data.get('profile', {}),
            'total_reels': scrape_data.get('total_reels', 0),
            'top_count': scrape_data.get('top_count', 0),
            'top_reels': scrape_data.get('top_reels', []),
            'status': scrape_data.get('status', 'unknown')
        })

    else:
        return jsonify({
            'type': asset_type,
            'error': f'Unknown asset type: {asset_type}',
            'content_path': content_path,
            'metadata': metadata
        })


@app.route('/api/assets/<asset_id>/collections', methods=['POST'])
def add_asset_to_collection(asset_id):
    """Add an asset to a collection"""
    asset = Asset.get(asset_id)
    if not asset:
        return jsonify({'error': 'Asset not found'}), 404

    data = request.get_json()
    collection_id = data.get('collection_id')

    if not collection_id:
        return jsonify({'error': 'collection_id is required'}), 400

    collection = Collection.get(collection_id)
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404

    asset.add_to_collection(collection_id)
    return jsonify({'success': True})


@app.route('/api/assets/<asset_id>/collections/<collection_id>', methods=['DELETE'])
def remove_asset_from_collection(asset_id, collection_id):
    """Remove an asset from a collection"""
    asset = Asset.get(asset_id)
    if not asset:
        return jsonify({'error': 'Asset not found'}), 404

    asset.remove_from_collection(collection_id)
    return jsonify({'success': True})


# ============================================================================
# COLLECTION MANAGEMENT API (P0)
# ============================================================================

@app.route('/api/collections', methods=['POST'])
def create_collection():
    """Create a new collection"""
    data = request.get_json()

    if 'name' not in data:
        return jsonify({'error': 'name is required'}), 400

    try:
        collection = Collection.create(
            name=data['name'],
            description=data.get('description'),
            color=data.get('color', '#6366f1'),
            icon=data.get('icon')
        )
        return jsonify(collection.to_dict()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/collections', methods=['GET'])
def list_collections():
    """List all collections"""
    collections = Collection.list()
    return jsonify([c.to_dict() for c in collections])


@app.route('/api/collections/<collection_id>', methods=['GET'])
def get_collection(collection_id):
    """Get a collection with its assets"""
    collection = Collection.get(collection_id)
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404

    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))

    result = collection.to_dict()
    result['assets'] = [a.to_dict() for a in collection.get_assets(limit=limit, offset=offset)]
    return jsonify(result)


@app.route('/api/collections/<collection_id>', methods=['PUT'])
def update_collection(collection_id):
    """Update a collection"""
    collection = Collection.get(collection_id)
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404

    data = request.get_json()
    allowed = {'name', 'description', 'color', 'icon'}
    updates = {k: v for k, v in data.items() if k in allowed}

    if updates:
        collection.update(**updates)

    return jsonify(collection.to_dict())


@app.route('/api/collections/<collection_id>', methods=['DELETE'])
def delete_collection(collection_id):
    """Delete a collection (assets are preserved)"""
    collection = Collection.get(collection_id)
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404

    collection.delete()
    return jsonify({'success': True})


if __name__ == '__main__':
    OUTPUT_DIR.mkdir(exist_ok=True)
    TIKTOK_OUTPUT_DIR.mkdir(exist_ok=True)

    # Initialize asset database (P0)
    init_db()
    logger.info("SYSTEM", "Asset database initialized")

    # Debug: Print all job-related routes
    print("\n=== Registered Job Routes ===")
    for rule in app.url_map.iter_rules():
        if 'jobs' in rule.rule:
            print(f"  {list(rule.methods - {'OPTIONS', 'HEAD'})} {rule.rule}")
    print("=============================\n")

    # IMPORTANT: use_reloader=False prevents Flask from restarting when Whisper
    # or other libraries touch their own files during import/execution.
    # The watchdog was incorrectly detecting whisper/transcribe.py access as a change.
    app.run(debug=True, port=5000, use_reloader=False)
