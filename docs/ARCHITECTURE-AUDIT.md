# ReelRecon Architecture Audit & Definitive Roadmap

**Version**: 1.0
**Date**: 2026-01-02
**Purpose**: SINGLE SOURCE OF TRUTH for all development - developers and AI agents MUST read this before making changes

---

## STOP AND READ THIS FIRST

If you are a developer or AI agent working on ReelRecon, **DO NOT** start coding until you have read and understood:

1. Section 2: Golden Rules (prevents reinventing the wheel)
2. Section 3: Common Mistakes (what keeps going wrong)
3. Section 4: The Connection Map (how everything links)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Golden Rules - NEVER Violate](#2-golden-rules---never-violate)
3. [Common Mistakes - What Keeps Going Wrong](#3-common-mistakes---what-keeps-going-wrong)
4. [The Connection Map - How Everything Links](#4-the-connection-map---how-everything-links)
5. [Complete File Inventory](#5-complete-file-inventory)
6. [Database Schema & Data Flow](#6-database-schema--data-flow)
7. [API Endpoint Reference](#7-api-endpoint-reference)
8. [Module Deep Dive](#8-module-deep-dive)
9. [Frontend Architecture](#9-frontend-architecture)
10. [Job Lifecycle & State Management](#10-job-lifecycle--state-management)
11. [Current Development Status](#11-current-development-status)
12. [Critical Patterns & Anti-Patterns](#12-critical-patterns--anti-patterns)
    - 12.4 [Job Status & Progress Patterns](#124-job-status--progress-patterns-added-2026-01-03)

---

## 1. Executive Summary

### 1.1 What Is ReelRecon?

ReelRecon is an Instagram/TikTok content intelligence platform with these core features:

| Feature | Purpose | Entry Point |
|---------|---------|-------------|
| **Scraper** | Fetch top-performing reels from creators | `/workspace` → New Scrape modal |
| **Skeleton Ripper** | Analyze patterns across multiple creators, generate templates | `/workspace` → New Analysis modal |
| **Library** | Asset management, collections, favorites | `/workspace` → Library view |
| **Direct Reel** | Scrape specific reels by URL/ID | `/workspace` → Direct Reel modal |

### 1.2 Current State Summary

```
Version: v2.2.0 stable, v3.0 in development (branch: feature/v3-workspace-overhaul)
Lines of Code: 22,421 total
  - app.py: 3,082 lines (Flask server + 60+ API routes)
  - Python modules: 5,669 lines (scraper, skeleton_ripper, storage, utils)
  - HTML templates: 7,564 lines
  - JavaScript: 5,201 lines
  - CSS: 2,500+ lines

Database: SQLite (state/reelrecon.db)
Storage: File-based output + SQLite assets
Active Branch: feature/v3-workspace-overhaul (Phase 7 in progress)
```

### 1.3 Architecture Overview

```
                                    +------------------+
                                    |   workspace.js   |
                                    |   (Frontend SPA) |
                                    +--------+---------+
                                             |
                                             | HTTP API calls
                                             v
+------------------+              +------------------+
|  scraper/core.py |<------------|     app.py       |-------------> state/reelrecon.db
|  scraper/tiktok  |   imports   |  (Flask Server)  |   SQLite      (Assets, Collections)
+------------------+              |   60+ routes     |
                                  +--------+---------+
+------------------+                       |
| skeleton_ripper/ |<----------------------+
|  pipeline.py     |   imports             |
|  extractor.py    |                       v
|  synthesizer.py  |              +------------------+
|  llm_client.py   |              |    storage/      |
+------------------+              |   models.py      |
                                  |  (Asset ORM)     |
+------------------+              +------------------+
|     utils/       |
|  state_manager   |<-------- Persistent job tracking
|     logger       |
|     retry        |
+------------------+
```

---

## 2. Golden Rules - NEVER Violate

### Rule 1: Use Existing Systems, Don't Reinvent

| Need | USE THIS | NOT THIS |
|------|----------|----------|
| Save an asset | `Asset.create()` from `storage/models.py` | Custom file writes |
| Track job progress | `ScrapeStateManager` from `utils/state_manager.py` | Custom JSON files |
| Call any LLM | `LLMClient` from `skeleton_ripper/llm_client.py` | Direct API calls |
| Transcribe audio | `transcribe_video()` or `transcribe_video_openai()` from `scraper/core.py` | New transcription code |
| Log errors | `logger` from `utils/logger.py` | print() statements |
| Retry failed operations | `retry_with_backoff()` from `utils/retry.py` | Custom retry loops |

### Rule 2: Data Flows Into the Library

**Every operation MUST create an asset in the database:**

```python
# CORRECT: Scrape creates asset
Asset.create(
    type='scrape_report',
    title=f"Scrape: @{username}",
    content_path=output_dir,
    preview=f"{len(top_reels)} reels from @{username}",
    metadata={'username': username, 'top_reels': top_reels, 'platform': platform}
)

# WRONG: Saving to JSON file without creating asset
with open('scrape_history.json', 'w') as f:
    json.dump(scrape_data, f)  # This is LEGACY - still works but assets are the source of truth
```

### Rule 3: Asset Types Are Fixed

Only these asset types exist in the system:

| Type | Description | Created By |
|------|-------------|------------|
| `scrape_report` | Complete scrape job result with all reels | `/api/scrape` completion |
| `skeleton_report` | Complete skeleton ripper analysis | `/api/skeleton-ripper/start` completion |
| `skeleton` | Single extracted pattern (hook/value/CTA) | User save action |
| `transcript` | Single video transcript | User save action |
| `synthesis` | AI-generated template/synthesis | User save action |

### Rule 4: The Database Is Source of Truth

```
state/reelrecon.db  <-- PRIMARY source for assets and collections
scrape_history.json <-- LEGACY, kept for backwards compat, BEING PHASED OUT
state/active_scrapes.json <-- Active/recent job tracking
output/*            <-- File artifacts (videos, transcripts, reports)
```

### Rule 5: State Transitions Are Explicit

Job states follow this progression:

```
SCRAPE JOBS:
pending → running → [scraping → transcribing → processing] → complete|error|aborted

SKELETON RIPPER JOBS:
pending → scraping → transcribing → extracting → aggregating → synthesizing → complete|error
```

**NEVER skip states.** Always transition through the state manager:

```python
state_manager.update_job(job_id,
    state='running',
    progress=ScrapeProgress(
        overall=25,
        phase='scraping',
        current_item=1,
        total_items=10,
        message='Fetching reels...'
    )
)
```

---

## 3. Common Mistakes - What Keeps Going Wrong

### Mistake 1: Not Reading From Both Sources

**Problem**: Assets page shows nothing / jobs show incomplete data

**Why**: The library needs to merge database assets WITH legacy scrape_history.json

**Location**: `app.py:get_assets()` around line 1650

```python
# CORRECT approach in /api/assets endpoint:
def get_assets():
    # 1. Get database assets
    db_assets = Asset.list(type=asset_type, starred=starred, collection_id=collection_id)

    # 2. ALSO get legacy history items and convert
    if not asset_type or asset_type == 'scrape_report':
        history = load_history()
        for item in history:
            if not any(a.id == item['id'] for a in db_assets):
                # Convert history item to asset format
                db_assets.append(convert_history_to_asset(item))

    return jsonify({'assets': [a.to_dict() for a in db_assets]})
```

### Mistake 2: Using Wrong Field Names

**Problem**: Views show as 0, usernames show as @unknown

**The reel object has DIFFERENT field names depending on source:**

```python
# Instagram API response:
{
    "play_count": 58769,     # Use this for views
    "like_count": 91,        # Use this for likes
    "comment_count": 20,     # Use this for comments
}

# TikTok yt-dlp response:
{
    "views": 58769,          # Different field name!
    "likes": 91,
    "comments": 20,
}

# CORRECT: Handle both:
views = reel.get('play_count') or reel.get('plays') or reel.get('views') or 0
likes = reel.get('like_count') or reel.get('likes') or 0
```

### Mistake 3: Caption Truncation

**Problem**: Captions are cut off at 200 characters

**Location**: `scraper/core.py` at THREE places (lines 129, 143, 235)

```python
# WRONG (still in code - needs fixing):
'caption': caption_text[:200]

# CORRECT:
'caption': caption_text  # Store full caption, truncate only for UI display
```

### Mistake 4: Not Tracking Jobs in State Manager

**Problem**: Job progress doesn't update, jobs get lost on restart

**ALWAYS use state_manager:**

```python
from utils.state_manager import state_manager

# When starting a job:
job = state_manager.create_job(
    scrape_id=job_id,
    username=username,
    platform=platform,
    config={'max_reels': 100, 'transcribe': True}
)

# When updating progress:
state_manager.update_job(job_id,
    state='running',
    progress=ScrapeProgress(overall=50, phase='transcribing', ...)
)

# When completing:
state_manager.complete_job(job_id, result=result_data)
```

### Mistake 5: yt-dlp PATH Issues

**Problem**: Video downloads fail with "yt-dlp not found"

**Solution**: Use sys.executable for reliable PATH

```python
# WRONG:
subprocess.run(['yt-dlp', url])

# CORRECT:
import sys
subprocess.run([sys.executable, '-m', 'yt_dlp', url])
```

### Mistake 6: Direct Reel Fetching Returns 0 Views

**Problem**: fetch_single_reel() returns views=0

**Why**: Using yt-dlp for metadata instead of get_reel_info()

**Solution**: Use the SAME function as profile scrapes:

```python
# WRONG:
def fetch_single_reel(shortcode, session):
    # Custom yt-dlp based fetch - returns incomplete data
    ...

# CORRECT - reuse existing function:
def fetch_single_reel(shortcode, session):
    return get_reel_info(session, shortcode)  # Same as profile scrape uses
```

### Mistake 7: Forgetting to Create Assets After Jobs Complete

**Problem**: Scrape completes but nothing appears in library

**CRITICAL**: Every job completion MUST create an asset:

```python
# In scrape completion handler:
if result['status'] == 'complete':
    # Create the asset
    Asset.create(
        type='scrape_report',
        title=f"Scrape: @{result['username']}",
        content_path=result['output_dir'],
        preview=f"{len(result['top_reels'])} reels",
        metadata={
            'username': result['username'],
            'top_reels': result['top_reels'],
            'platform': result.get('platform', 'instagram'),
            'timestamp': result['timestamp']
        }
    )
```

---

## 4. The Connection Map - How Everything Links

### 4.1 Scrape Flow

```
USER ACTION                    FRONTEND                     BACKEND                      STORAGE
-----------                    --------                     -------                      -------
Click "New Scrape"       -->   openModal('new-scrape')
Fill form, click Start   -->   startScrape()
                               API.startBatchScrape()  -->  POST /api/scrape/batch
                                                            |
                                                            +--> state_manager.create_job()
                                                            +--> Thread: run_batch_scrape()
                                                                     |
                                                                     +--> scraper/core.py:run_scrape()
                                                                     |       |
                                                                     |       +--> get_user_reels()
                                                                     |       +--> download_video()
                                                                     |       +--> transcribe_video()
                                                                     |
                                                                     +--> On complete:
                                                                             |
                                                                             +--> Asset.create(type='scrape_report')
                                                                             +--> save_to_history() [legacy]
                                                                             +--> state_manager.complete_job()

Poll /api/jobs/active    <--   loadJobs('active')      <--  GET /api/jobs/active
                                                            +--> state_manager.list_active()

On complete: refresh     <--   showJobCompletionNotification()
                               reloadAssets()          -->  GET /api/assets
```

### 4.2 Skeleton Ripper Flow

```
USER ACTION                    FRONTEND                     BACKEND                          STORAGE
-----------                    --------                     -------                          -------
Click "New Analysis"     -->   openModal('new-analysis')
Add creators, Start      -->   startAnalysis()
                               API.startAnalysis()    -->   POST /api/skeleton-ripper/start
                                                            |
                                                            +--> SkeletonRipperPipeline.run()
                                                                    |
                                                                    +--> Stage 0: Cache check
                                                                    +--> Stage 1: Scrape (reuses core.py)
                                                                    +--> Stage 2: BatchedExtractor
                                                                    |       +--> LLMClient.complete()
                                                                    +--> Stage 3: SkeletonAggregator
                                                                    +--> Stage 4: PatternSynthesizer
                                                                    |       +--> LLMClient.complete()
                                                                    +--> Stage 5: Save outputs
                                                                            |
                                                                            +--> Asset.create(type='skeleton_report')
                                                                            +--> Write to output/skeleton_reports/

Poll status              <--   loadJobs('active')     <--   GET /api/skeleton-ripper/status/{id}
View report              <--   openJobDetail()        <--   GET /api/skeleton-ripper/report/{id}
```

### 4.3 Library Asset Flow

```
USER ACTION                    FRONTEND                     BACKEND                      STORAGE
-----------                    --------                     -------                      -------
Open Library view        -->   loadInitialData()
                               API.getAssets()        -->   GET /api/assets
                                                            |
                                                            +--> Asset.list()           <-- state/reelrecon.db
                                                            +--> load_history()         <-- scrape_history.json [legacy]
                                                            +--> Merge and return

Click asset card         -->   openAssetDetail(id)
                               API.getAsset(id)       -->   GET /api/assets/{id}
                                                            |
                                                            +--> Asset.get(id)
                                                            +--> If scrape_report: load top_reels from metadata
                                                            +--> Return full asset data

Star asset               -->   toggleStarAsset()
                               API.toggleStar(id)     -->   PUT /api/assets/{id}
                                                            +--> asset.update(starred=True)

Delete asset             -->   deleteAsset()
                               API.deleteAsset(id)    -->   DELETE /api/assets/{id}
                                                            +--> asset.delete()
```

### 4.4 Data Structure Relationships

```
scrape_history.json (LEGACY)          state/reelrecon.db (PRIMARY)
-----------------------               -----------------------
[                                     assets table:
  {                                   +-------------+------------+
    "id": "uuid",         <========>  | id          | uuid       |
    "username": "...",                | type        | scrape_report/skeleton_report/... |
    "top_reels": [...],               | title       | "Scrape: @user" |
    "output_dir": "..."               | content_path| output dir |
  }                                   | metadata    | {top_reels, username, ...} JSON |
]                                     | starred     | 0/1        |
                                      +-------------+------------+

output/output_{username}/             collections table:
├── reels_{timestamp}.json            +-------------+------------+
├── transcripts/                      | id          | uuid       |
│   └── 01_SHORTCODE.txt              | name        | "Favorites"|
└── videos/                           | color       | "#6366f1"  |
    └── SHORTCODE.mp4                 +-------------+------------+

output/skeleton_reports/{id}/         asset_collections (junction):
├── report.md                         +-------------+---------------+
├── skeletons.json                    | asset_id    | collection_id |
└── synthesis.json                    +-------------+---------------+
```

---

## 5. Complete File Inventory

### 5.1 Root Directory

| File | Lines | Purpose |
|------|-------|---------|
| `app.py` | 3,082 | Flask server, all API routes, main entry point |
| `launcher.pyw` | ~500 | Windows desktop launcher with system tray |
| `ReelRecon-Mac.py` | ~400 | macOS desktop launcher with menu bar |
| `config.json` | ~15 | User AI provider settings (gitignored) |
| `config.template.json` | ~15 | Template for config.json |
| `cookies.txt` | - | Instagram auth cookies (Netscape format) |
| `tiktok_cookies.txt` | - | TikTok auth cookies |
| `scrape_history.json` | var | Legacy scrape history (being phased out) |
| `requirements.txt` | ~20 | Python dependencies |
| `VERSION` | 1 | Current version string |

### 5.2 Python Modules

#### `scraper/` - Instagram & TikTok Scraping (1,445 lines)

| File | Lines | Key Functions |
|------|-------|---------------|
| `core.py` | 970 | `run_scrape()`, `get_user_reels()`, `get_reel_info()`, `download_video()`, `transcribe_video()`, `transcribe_video_openai()` |
| `tiktok.py` | 470 | `scrape_tiktok_profile()`, `download_tiktok_video()` |
| `__init__.py` | 5 | Module exports |

#### `skeleton_ripper/` - Pattern Analysis Pipeline (2,798 lines)

| File | Lines | Key Classes/Functions |
|------|-------|----------------------|
| `pipeline.py` | 794 | `SkeletonRipperPipeline`, `JobConfig`, `JobProgress`, `JobStatus` enum |
| `extractor.py` | 361 | `BatchedExtractor`, `ExtractionResult` |
| `aggregator.py` | 261 | `SkeletonAggregator`, `CreatorStats`, `AggregatedData` |
| `synthesizer.py` | 325 | `PatternSynthesizer`, `SynthesisResult`, `generate_report()` |
| `llm_client.py` | 461 | `LLMClient` (OpenAI, Anthropic, Google, Ollama) |
| `prompts.py` | 290 | `SKELETON_EXTRACT_BATCH_PROMPT`, `SYNTHESIS_SYSTEM_PROMPT`, etc. |
| `cache.py` | 306 | `TranscriptCache` |

#### `storage/` - Database & Models (1,104 lines)

| File | Lines | Key Classes |
|------|-------|-------------|
| `database.py` | 114 | `init_db()`, `get_db_connection()`, `db_transaction()` |
| `models.py` | 370 | `Asset`, `Collection`, `AssetCollection` |
| `migrate.py` | 266 | `migrate_history_to_db()` |
| `update_metadata.py` | 174 | Metadata utilities |
| `test_storage.py` | 163 | Storage tests |

#### `utils/` - Utilities (1,173 lines)

| File | Lines | Key Classes/Functions |
|------|-------|----------------------|
| `state_manager.py` | 384 | `ScrapeStateManager`, `ScrapeJob`, `ScrapeProgress`, `ScrapePhase`, `ScrapeState` |
| `logger.py` | 248 | `ReelReconLogger`, structured logging |
| `retry.py` | 246 | `retry_with_backoff()`, `RetryConfig` |
| `updater.py` | 279 | `check_for_updates()`, `run_update()` |

### 5.3 Frontend Templates

| File | Lines | Purpose |
|------|-------|---------|
| `templates/workspace.html` | 186 | V3 unified workspace shell |
| `templates/index.html` | 689 | Legacy scraper UI |
| `templates/library.html` | 3,518 | Legacy library UI |
| `templates/skeleton_ripper.html` | 3,171 | Legacy skeleton ripper UI |
| `templates/components/save_collect_modal.html` | - | Modal component |

### 5.4 JavaScript

| File | Lines | Purpose |
|------|-------|---------|
| `static/js/workspace.js` | 2,178 | V3 unified workspace logic |
| `static/js/app.js` | 2,716 | Legacy scraper logic |
| `static/js/save_collect.js` | 307 | Save/collection modal |
| `static/js/state/store.js` | ~100 | State management |
| `static/js/utils/api.js` | ~150 | API client |
| `static/js/utils/router.js` | ~100 | Client-side routing |

### 5.5 CSS

| File | Lines | Purpose |
|------|-------|---------|
| `static/css/tactical.css` | ~2,100 | Legacy green tactical theme |
| `static/css/workspace.css` | ~400 | V3 professional theme |

### 5.6 Output Directories

```
output/
├── output_{username}/           # Per-creator scrape results
│   ├── reels_{timestamp}.json   # Scrape metadata
│   ├── transcripts/             # .txt transcript files
│   └── videos/                  # .mp4 video files

output_tiktok/
├── output_{username}_tiktok/    # Same structure for TikTok

output/skeleton_reports/
├── {timestamp}_{id}/            # Per-analysis results
│   ├── report.md                # Markdown report
│   ├── skeletons.json           # Extracted patterns
│   └── synthesis.json           # AI synthesis

cache/
└── transcripts/                 # Cached transcripts
    └── instagram_{user}_{id}.txt

state/
├── reelrecon.db                 # SQLite database
├── active_scrapes.json          # Active job queue
└── scrape_archive.json          # Historical jobs

logs/
├── reelrecon.log                # Main log file
└── errors.log                   # Error registry
```

---

## 6. Database Schema & Data Flow

### 6.1 SQLite Schema (state/reelrecon.db)

```sql
-- Main assets table
CREATE TABLE assets (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    title TEXT,
    content_path TEXT,
    preview TEXT,
    metadata JSON,
    starred INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);

-- Collections for organizing assets
CREATE TABLE collections (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    color TEXT DEFAULT '#6366f1',
    icon TEXT,
    created_at TEXT
);

-- Many-to-many: assets <-> collections
CREATE TABLE asset_collections (
    asset_id TEXT,
    collection_id TEXT,
    added_at TEXT,
    PRIMARY KEY (asset_id, collection_id),
    FOREIGN KEY (asset_id) REFERENCES assets(id),
    FOREIGN KEY (collection_id) REFERENCES collections(id)
);

-- Full-text search index
CREATE VIRTUAL TABLE assets_fts USING fts5(
    title, preview, content='assets', content_rowid='rowid'
);
```

### 6.2 Asset Type Schemas

#### `scrape_report` Metadata

```json
{
  "type": "scrape_report",
  "title": "Scrape: @username",
  "content_path": "/path/to/output_username",
  "preview": "10 reels from @username",
  "metadata": {
    "username": "username",
    "platform": "instagram",
    "timestamp": "2026-01-02T14:30:00Z",
    "total_reels": 100,
    "top_count": 10,
    "top_reels": [
      {
        "shortcode": "ABC123",
        "url": "https://instagram.com/reel/ABC123",
        "views": 58769,
        "likes": 91,
        "comments": 20,
        "caption": "Full caption text...",
        "video_url": "https://cdn.url/video.mp4",
        "local_video": "/path/to/video.mp4 or null",
        "transcript": "Transcript text...",
        "transcript_file": "/path/to/transcript.txt"
      }
    ],
    "profile": {
      "username": "username",
      "full_name": "Display Name",
      "followers": 14713
    }
  }
}
```

#### `skeleton_report` Metadata

```json
{
  "type": "skeleton_report",
  "title": "Analysis: @user1, @user2",
  "content_path": "/path/to/skeleton_reports/timestamp_id",
  "preview": "5 patterns from 2 creators",
  "metadata": {
    "creators": ["user1", "user2"],
    "videos_per_creator": 3,
    "llm_provider": "openai",
    "llm_model": "gpt-4o-mini",
    "skeletons": [
      {
        "video_id": "ABC123",
        "creator_username": "user1",
        "hook": "Opening line...",
        "hook_technique": "curiosity",
        "hook_word_count": 15,
        "value": "Main teaching...",
        "value_structure": "steps",
        "value_points": ["point1", "point2"],
        "cta": "Call to action...",
        "cta_type": "follow",
        "total_word_count": 120,
        "views": 50000
      }
    ],
    "synthesis": {
      "analysis": "Markdown analysis...",
      "templates": ["Template 1...", "Template 2..."],
      "quick_wins": ["Do this...", "Try that..."],
      "warnings": ["Avoid this..."]
    }
  }
}
```

#### `skeleton` (Individual Pattern)

```json
{
  "type": "skeleton",
  "title": "@creator - Hook preview...",
  "preview": "Full hook text...",
  "metadata": {
    "source_report_id": "uuid of skeleton_report",
    "hook": "Full hook...",
    "hook_technique": "curiosity",
    "value": "Main value...",
    "value_points": ["..."],
    "cta": "...",
    "creator_username": "creator"
  }
}
```

#### `transcript` (Individual Transcript)

```json
{
  "type": "transcript",
  "title": "@creator - shortcode",
  "content_path": "/path/to/transcript.txt",
  "preview": "First 200 chars of transcript...",
  "metadata": {
    "source_report_id": "uuid of scrape_report",
    "shortcode": "ABC123",
    "creator_username": "creator",
    "video_url": "https://..."
  }
}
```

---

## 7. API Endpoint Reference

### 7.1 Page Routes

| Route | Template | Status |
|-------|----------|--------|
| `GET /` | `workspace.html` (v3) OR `index.html` (v2) | Active |
| `GET /workspace` | `workspace.html` | Active |
| `GET /skeleton-ripper` | `skeleton_ripper.html` | Legacy |
| `GET /library` | `library.html` | Legacy |

### 7.2 Scraping API

| Method | Route | Purpose | Request | Response |
|--------|-------|---------|---------|----------|
| `POST` | `/api/scrape` | Start single scrape | `{username, platform, max_reels, top_n, download, transcribe, ...}` | `{success, scrape_id}` |
| `POST` | `/api/scrape/batch` | Start multi-creator scrape | `{usernames[], platform, ...}` | `{success, batch_id, scrape_ids[]}` |
| `GET` | `/api/scrape/{id}/status` | Poll progress | - | `{status, progress, phase, ...}` |
| `POST` | `/api/scrape/{id}/abort` | Cancel job | - | `{success}` |
| `POST` | `/api/scrape/batch/{id}/abort` | Cancel batch | - | `{success}` |
| `POST` | `/api/scrape/direct` | Scrape by URL/ID | `{platform, input_type, inputs[], ...}` | `{success, scrape_ids[]}` |
| `GET` | `/api/history` | List scrape history | - | `{history[]}` |
| `DELETE` | `/api/history/{id}` | Delete history item | - | `{success}` |
| `POST` | `/api/history/{id}/star` | Toggle favorite | - | `{starred}` |

### 7.3 Skeleton Ripper API

| Method | Route | Purpose | Request | Response |
|--------|-------|---------|---------|----------|
| `GET` | `/api/skeleton-ripper/providers` | List LLM providers | - | `{providers[{id, name, models[]}]}` |
| `POST` | `/api/skeleton-ripper/start` | Start analysis | `{usernames[], videos_per_creator, llm_provider, llm_model}` | `{success, job_id}` |
| `GET` | `/api/skeleton-ripper/status/{id}` | Poll progress | - | `{status, progress, phase, ...}` |
| `GET` | `/api/skeleton-ripper/report/{id}` | Get HTML report | - | HTML content |
| `GET` | `/api/skeleton-ripper/report/{id}/json` | Get JSON report | - | `{report data}` |
| `GET` | `/api/skeleton-ripper/history` | List past reports | - | `{reports[]}` |

### 7.4 Assets API

| Method | Route | Purpose | Request | Response |
|--------|-------|---------|---------|----------|
| `POST` | `/api/assets` | Create asset | `{type, title, ...}` | `{success, asset}` |
| `GET` | `/api/assets` | List assets | `?type=&starred=&collection=` | `{assets[]}` |
| `GET` | `/api/assets/search` | Search assets | `?q=query` | `{assets[]}` |
| `GET` | `/api/assets/{id}` | Get single asset | - | `{asset}` |
| `PUT` | `/api/assets/{id}` | Update asset | `{title?, starred?, ...}` | `{asset}` |
| `DELETE` | `/api/assets/{id}` | Delete asset | - | `{success}` |
| `POST` | `/api/assets/save-skeleton` | Save skeleton from report | `{skeleton_data, source_report_id}` | `{success, asset}` |
| `POST` | `/api/assets/save-transcript` | Save transcript from report | `{reel_data, source_report_id, username}` | `{success, asset}` |
| `POST` | `/api/assets/{id}/collections/{cid}` | Add to collection | - | `{success}` |
| `DELETE` | `/api/assets/{id}/collections/{cid}` | Remove from collection | - | `{success}` |

### 7.5 Collections API

| Method | Route | Purpose | Request | Response |
|--------|-------|---------|---------|----------|
| `POST` | `/api/collections` | Create collection | `{name, description?, color?, icon?}` | `{success, collection}` |
| `GET` | `/api/collections` | List collections | - | `{collections[]}` |
| `GET` | `/api/collections/{id}` | Get collection | - | `{collection}` |
| `PUT` | `/api/collections/{id}` | Update collection | `{name?, ...}` | `{collection}` |
| `DELETE` | `/api/collections/{id}` | Delete collection | - | `{success}` |

### 7.6 Jobs API (V3)

| Method | Route | Purpose | Response |
|--------|-------|---------|----------|
| `GET` | `/api/jobs/active` | Active jobs (scrapes + analyses) | `{success, jobs[]}` |
| `GET` | `/api/jobs/recent` | Recent completed jobs | `{success, jobs[]}` |
| `GET` | `/api/health` | Server health check | `{status: 'ok'}` |

### 7.7 Configuration API

| Method | Route | Purpose |
|--------|-------|---------|
| `GET` | `/api/settings` | Get AI provider settings |
| `POST` | `/api/settings` | Save AI provider settings |
| `GET` | `/api/cookies/status` | Check cookies validity |
| `GET` | `/api/ollama/models` | List local Ollama models |
| `GET` | `/api/version` | Get app version |
| `GET` | `/api/update/check` | Check for updates |

---

## 8. Module Deep Dive

### 8.1 scraper/core.py - Key Functions

#### `run_scrape(username, max_reels, top_n, download, transcribe, ...)`

Main orchestration function:

```python
def run_scrape(username, max_reels=100, top_n=10, download=True,
               transcribe=True, transcribe_provider='local', ...):
    """
    1. Create authenticated session with cookies
    2. Fetch user profile and reel list
    3. Sort by play_count, take top N
    4. Optionally download videos
    5. Optionally transcribe (local Whisper or OpenAI API)
    6. Return result dict with top_reels
    """
```

#### `get_reel_info(session, shortcode)`

Fetches metadata for a single reel:

```python
def get_reel_info(session, shortcode):
    """
    Makes authenticated request to Instagram graphql endpoint
    Returns: {shortcode, url, play_count, like_count, comment_count, caption, video_url}

    CRITICAL: This is the CORRECT way to get reel metadata.
    Do NOT use yt-dlp for metadata - it returns 0 for views.
    """
```

#### `download_video(url, output_path)`

Downloads video using yt-dlp:

```python
def download_video(url, output_path):
    """
    Uses yt-dlp via sys.executable to avoid PATH issues:
    subprocess.run([sys.executable, '-m', 'yt_dlp', ...])
    """
```

#### `transcribe_video(video_path, model='small.en')`

Local Whisper transcription:

```python
def transcribe_video(video_path, model='small.en'):
    """
    Uses openai-whisper library locally
    Requires: pip install openai-whisper, ffmpeg installed
    """
```

#### `transcribe_video_openai(api_key, video_path_or_url)`

Cloud transcription:

```python
def transcribe_video_openai(api_key, video_path_or_url):
    """
    Uses OpenAI Whisper API
    Faster but requires API key
    """
```

### 8.2 skeleton_ripper/pipeline.py - Pipeline Stages

```python
class SkeletonRipperPipeline:
    """
    5-stage pipeline for content pattern analysis:

    Stage 0: Cache Check
        - Check TranscriptCache for existing transcripts
        - Skip re-scraping if cached

    Stage 1: Scrape & Transcribe
        - Calls scraper.core.run_scrape() for each creator
        - Downloads videos, transcribes

    Stage 2: Batched Extraction
        - Groups 3-5 transcripts per batch
        - Sends to LLM for skeleton extraction
        - Returns: List[ExtractionResult]

    Stage 3: Aggregation
        - Groups skeletons by creator
        - Calculates statistics (avg views, common techniques)
        - Returns: AggregatedData

    Stage 4: Synthesis
        - Sends aggregated data to LLM
        - Generates templates and analysis
        - Returns: SynthesisResult

    Stage 5: Output
        - Saves to output/skeleton_reports/{id}/
        - Creates Asset in database
    """
```

### 8.3 skeleton_ripper/llm_client.py - Multi-Provider LLM

```python
class LLMClient:
    """
    Unified interface for multiple LLM providers.

    Supported:
    - OpenAI: gpt-4o-mini, gpt-4o, gpt-4-turbo
    - Anthropic: claude-3-haiku, claude-3-sonnet, claude-3-opus
    - Google: gemini-1.5-flash, gemini-1.5-pro
    - Ollama: qwen3, llama3, mistral, mixtral, phi3 (local)

    Usage:
        client = LLMClient(provider='openai', model='gpt-4o-mini', api_key=key)
        response = client.complete(prompt, max_tokens=2000)
    """
```

### 8.4 storage/models.py - Asset ORM

```python
@dataclass
class Asset:
    """
    CRITICAL: Use this class for ALL asset operations.

    Class Methods:
        Asset.create(type, title, content_path, preview, metadata) -> Asset
        Asset.get(asset_id) -> Asset
        Asset.list(type, starred, collection_id, limit, offset) -> List[Asset]
        Asset.search(query, limit) -> List[Asset]

    Instance Methods:
        asset.update(**kwargs) -> Asset
        asset.delete()
        asset.add_to_collection(collection_id)
        asset.remove_from_collection(collection_id)
        asset.get_collections() -> List[Collection]
        asset.to_dict() -> Dict
    """

@dataclass
class Collection:
    """
    User-defined groupings for assets.

    Class Methods:
        Collection.create(name, description, color, icon) -> Collection
        Collection.get(collection_id) -> Collection
        Collection.list() -> List[Collection]

    Instance Methods:
        collection.update(**kwargs) -> Collection
        collection.delete()  # Preserves assets
        collection.get_assets(limit, offset) -> List[Asset]
        collection.asset_count() -> int
    """

class AssetCollection:
    """
    Many-to-many junction table operations.

    Static Methods:
        AssetCollection.add(asset_id, collection_id)
        AssetCollection.remove(asset_id, collection_id)
        AssetCollection.get_collections_for_asset(asset_id) -> List[str]
        AssetCollection.get_assets_for_collection(collection_id) -> List[str]
    """
```

### 8.5 utils/state_manager.py - Job Tracking

```python
class ScrapeStateManager:
    """
    Persistent job state management.

    CRITICAL: Use this for ALL job tracking.

    Methods:
        create_job(scrape_id, username, platform, config) -> ScrapeJob
        update_job(scrape_id, state, progress, result) -> ScrapeJob
        get_job(scrape_id) -> ScrapeJob
        list_active() -> List[ScrapeJob]
        list_recent(limit) -> List[ScrapeJob]
        abort_job(scrape_id, reason)
        complete_job(scrape_id, result)
        fail_job(scrape_id, error)

    Storage:
        state/active_scrapes.json - Current jobs
        state/scrape_archive.json - Historical jobs
    """

class ScrapeProgress:
    """Progress tracking with phase information."""
    overall: int  # 0-100
    phase: str  # 'scraping', 'transcribing', etc.
    current_item: int
    total_items: int
    message: str

class ScrapePhase(Enum):
    """Valid job phases."""
    INITIALIZING = 'initializing'
    AUTHENTICATING = 'authenticating'
    FETCHING_PROFILE = 'fetching_profile'
    DISCOVERING_CONTENT = 'discovering_content'
    DOWNLOADING = 'downloading'
    TRANSCRIBING = 'transcribing'
    PROCESSING = 'processing'
    FINALIZING = 'finalizing'
    COMPLETE = 'complete'
    ERROR = 'error'
    ABORTED = 'aborted'

class ScrapeState(Enum):
    """Valid job states."""
    QUEUED = 'queued'
    RUNNING = 'running'
    COMPLETE = 'complete'
    ERROR = 'error'
    PARTIAL = 'partial'
    ABORTED = 'aborted'
```

---

## 9. Frontend Architecture

### 9.1 V3 Workspace Architecture

```
workspace.html (shell)
├── #sidebar
│   ├── Logo
│   ├── Quick Actions (New Scrape, Direct Reel, New Analysis)
│   ├── Navigation (Library, Favorites, Jobs, Settings)
│   └── Collections list
├── #main-content
│   ├── #search-bar
│   ├── #filter-chips
│   ├── #asset-grid OR #jobs-list OR #favorites-grid
│   └── (view-specific content)
├── #detail-panel (slideout)
│   ├── Header (close, star, copy, delete)
│   └── #detail-panel-content
└── #modal-overlay
    └── #modal-content (rendered dynamically)
```

### 9.2 State Management (store.js)

```javascript
const Store = {
    state: {
        assets: [],
        collections: [],
        filters: {
            types: [],       // Multi-select type filter
            search: '',      // Search query
            collection: null // Selected collection ID
        },
        ui: {
            activeView: 'library',  // library, favorites, jobs, settings
            selectedAsset: null,
            modal: null
        }
    },

    dispatch(action) {
        switch (action.type) {
            case 'SET_ASSETS':
                this.state.assets = action.payload;
                break;
            case 'SET_FILTER':
                Object.assign(this.state.filters, action.payload);
                break;
            case 'SET_MODAL':
                this.state.ui.modal = action.payload;
                break;
            // ...
        }
        this.notify();
    },

    subscribe(listener) { ... },
    getState() { return this.state; }
};
```

### 9.3 API Client (api.js)

```javascript
const API = {
    // Assets
    getAssets: (filters) => fetch('/api/assets?' + new URLSearchParams(filters)).then(r => r.json()),
    getAsset: (id) => fetch(`/api/assets/${id}`).then(r => r.json()),
    deleteAsset: (id) => fetch(`/api/assets/${id}`, { method: 'DELETE' }).then(r => r.json()),
    toggleStar: (id) => fetch(`/api/assets/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ starred: 'toggle' })
    }).then(r => r.json()),

    // Scraping
    startBatchScrape: (data) => fetch('/api/scrape/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    }).then(r => r.json()),

    startDirectScrape: (data) => fetch('/api/scrape/direct', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    }).then(r => r.json()),

    abortScrape: (id) => fetch(`/api/scrape/${id}/abort`, { method: 'POST' }).then(r => r.json()),

    // Analysis
    startAnalysis: (data) => fetch('/api/skeleton-ripper/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    }).then(r => r.json()),

    getProviders: () => fetch('/api/skeleton-ripper/providers').then(r => r.json()),

    // Collections
    getCollections: () => fetch('/api/collections').then(r => r.json()),
    removeFromCollection: (assetId, collectionId) => fetch(
        `/api/assets/${assetId}/collections/${collectionId}`,
        { method: 'DELETE' }
    ).then(r => r.json())
};
```

### 9.4 Key UI Patterns

#### Reel Accordion (scrape_report detail view)

```javascript
function renderReelAccordionItem(reel, index, scrapeId) {
    // Fields to use (handles Instagram vs TikTok naming):
    const views = reel.play_count || reel.plays || reel.views || 0;
    const likes = reel.like_count || reel.likes || 0;
    const comments = reel.comment_count || reel.comments || 0;

    // Returns accordion HTML with:
    // - Header (preview, stats indicators)
    // - Body (full stats, URL, caption, transcript)
    // - Actions (copy, save to library)
}
```

#### Job Polling (Individual Endpoint Pattern)

**CRITICAL**: Poll individual job status endpoints and update DOM directly.
Do NOT use `innerHTML` replacement on poll - it causes visual flashing.

```javascript
let jobsPollingInterval = null;
let trackedActiveJobs = new Set();

function startJobsPolling() {
    if (jobsPollingInterval) return; // Already polling
    pollActiveJobsOnce(); // Start immediately
}

async function pollActiveJobsOnce() {
    if (trackedActiveJobs.size === 0) {
        stopJobsPolling();
        return;
    }
    for (const jobId of trackedActiveJobs) {
        await pollSingleJob(jobId);
    }
    // Recursive setTimeout (NOT setInterval)
    jobsPollingInterval = setTimeout(pollActiveJobsOnce, 1000);
}

async function pollSingleJob(jobId) {
    // Determine endpoint based on job ID prefix
    const isAnalysis = jobId.startsWith('sr_');
    let endpoint = isAnalysis
        ? `/api/skeleton-ripper/status/${jobId}`
        : `/api/scrape/${jobId}/status`;

    const response = await fetch(endpoint);
    const data = await response.json();

    // Check completion
    if (['complete', 'failed', 'error', 'partial', 'aborted'].includes(data.status)) {
        showJobCompletionNotification(jobId);
        trackedActiveJobs.delete(jobId);
        return;
    }

    // Update DOM directly (no innerHTML replacement!)
    const card = document.querySelector(`.job-card[data-job-id="${jobId}"]`);
    if (card) {
        const progressFill = card.querySelector('.progress-fill');
        if (progressFill && data.progress_pct !== undefined) {
            progressFill.style.width = `${data.progress_pct}%`;
        }
        const progressText = card.querySelector('.job-progress-text');
        if (progressText) {
            progressText.textContent = data.progress?.message || data.progress?.phase || '';
        }
    }
}
```

---

## 10. Job Lifecycle & State Management

### 10.1 Scrape Job Lifecycle

```
1. USER INITIATES
   └── Modal: Fill form, click "Start Scrape"

2. FRONTEND
   └── API.startBatchScrape() or API.startDirectScrape()

3. BACKEND: /api/scrape/batch or /api/scrape/direct
   ├── Generate batch_id and scrape_ids
   ├── state_manager.create_job() for each
   ├── Start Thread(run_batch_scrape)
   └── Return {success, batch_id, scrape_ids}

4. BACKGROUND THREAD: run_batch_scrape()
   └── For each username:
       ├── state_manager.update_job(state='running', phase='scraping')
       ├── scraper.core.run_scrape()
       │   ├── Load cookies, create session
       │   ├── get_user_reels() → sort by play_count → take top N
       │   ├── For each reel:
       │   │   ├── state_manager.update_job(phase='downloading', current_item=i)
       │   │   ├── download_video() [if enabled]
       │   │   ├── state_manager.update_job(phase='transcribing')
       │   │   └── transcribe_video() [if enabled]
       │   └── Return result dict
       ├── save_to_history(result)  [legacy]
       ├── Asset.create(type='scrape_report', metadata={...})  [PRIMARY]
       └── state_manager.complete_job()

5. FRONTEND POLLING
   └── /api/jobs/active every 1 second
   └── On completion detected:
       ├── showJobCompletionNotification()
       └── reloadAssets()
```

### 10.2 Skeleton Ripper Job Lifecycle

```
1. USER INITIATES
   └── Modal: Add creators, select LLM, click "Start Analysis"

2. FRONTEND
   └── API.startAnalysis()

3. BACKEND: /api/skeleton-ripper/start
   ├── Create job_id
   ├── Start Thread(SkeletonRipperPipeline.run)
   └── Return {success, job_id}

4. PIPELINE: SkeletonRipperPipeline.run()
   ├── Stage 0: Check transcript cache
   ├── Stage 1: Scrape & Transcribe
   │   └── For each creator: scraper.core.run_scrape()
   ├── Stage 2: Batched Extraction
   │   ├── Group transcripts into batches of 3-5
   │   └── BatchedExtractor.extract_all()
   │       └── LLMClient.complete(EXTRACTION_PROMPT)
   ├── Stage 3: Aggregation
   │   └── SkeletonAggregator.aggregate()
   ├── Stage 4: Synthesis
   │   └── PatternSynthesizer.synthesize()
   │       └── LLMClient.complete(SYNTHESIS_PROMPT)
   └── Stage 5: Output
       ├── Write to output/skeleton_reports/{id}/
       │   ├── report.md
       │   ├── skeletons.json
       │   └── synthesis.json
       └── Asset.create(type='skeleton_report', metadata={...})

5. FRONTEND POLLING
   └── /api/skeleton-ripper/status/{id} every 1 second
   └── On complete: redirect to report view
```

### 10.3 State Persistence Points

```
ALWAYS PERSISTED (crash-safe):
├── state/active_scrapes.json    <-- ScrapeStateManager
├── state/reelrecon.db           <-- Asset, Collection tables
└── output/                      <-- Downloaded files

LEGACY (being phased out):
└── scrape_history.json          <-- Old history format
```

---

## 11. Current Development Status

### 11.1 V3 Workspace Overhaul Progress

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 0: Setup | Complete | Commit: 6772eaf |
| Phase 1: Design System | Complete | Commit: a888628 |
| Phase 2: Library View | Complete | Commit: 2b95452 |
| Phase 3: Actions & Modals | Complete | Commits: 68c4b01, 813e86d, 18452ba |
| Phase 4: Jobs View | Complete | Real-time polling, detail panels |
| Phase 5: Integration & Polish | Not Started | Port rewrite, video playback |
| Phase 6: Migration & Cutover | Not Started | Make workspace default |
| Phase 7: Batch & Direct | In Progress | Batch working, direct reel fixing |
| Phase 7.5: Desktop Launcher | Complete | System tray, auto-reconnect |
| Phase 8: Asset Extraction | Not Started | Save transcripts/skeletons separately |

### 11.2 Known Issues (as of 2026-01-03)

| Issue | Location | Status |
|-------|----------|--------|
| Direct reel views = 0 | `scraper/core.py:fetch_single_reel()` | Fixed: Use get_reel_info() |
| yt-dlp PATH issues | `scraper/core.py:download_video()` | Fixed: Use sys.executable |
| Caption truncation | `scraper/core.py` (lines 129, 235) | Needs fix |
| Library not merging sources | `app.py:/api/assets` | Fixed in v3 |
| Progress bar stuck at 0% | `app.py` (lines 865, 1105) | Fixed: `elif` → `if` for progress_pct |
| Job not in active tab | `workspace.js` | Fixed: Track job, call loadJobs('active') |
| Skeleton ripper status mismatch | `app.py` (line 2604) | Fixed: Use 'running' consistently |
| Job card flashing | `workspace.js` | Fixed: Direct DOM updates, not innerHTML |
| Progress bar jumping | `app.py` (lines 2677-2721) | Fixed: Backend progress_pct calculation |
| Reel count not showing | `pipeline.py` (line 412) | Fixed: Forward progress callback to get_user_reels |

### 11.3 Files Currently Being Modified

```
ACTIVE DEVELOPMENT:
├── app.py                      <-- Adding /api/scrape/direct, /api/jobs/*
├── scraper/core.py             <-- fetch_single_reel() refactor
├── static/js/workspace.js      <-- Direct reel modal, job tracking
└── templates/workspace.html    <-- Modal containers

DO NOT TOUCH (stable):
├── storage/models.py           <-- Asset ORM is stable
├── skeleton_ripper/*           <-- Pipeline is stable
└── utils/state_manager.py      <-- State management is stable
```

---

## 12. Critical Patterns & Anti-Patterns

### 12.1 DO THIS

```python
# Always use Asset.create() for new assets
Asset.create(
    type='scrape_report',
    title=f"Scrape: @{username}",
    content_path=output_dir,
    preview=f"{count} reels",
    metadata={'top_reels': reels, 'username': username}
)

# Always use state_manager for job tracking
state_manager.update_job(job_id, state='running', progress=ScrapeProgress(...))

# Always use LLMClient for AI calls
client = LLMClient(provider='openai', model='gpt-4o-mini', api_key=key)
response = client.complete(prompt)

# Always use retry_with_backoff for network calls
from utils.retry import retry_with_backoff, RetryConfig
result = retry_with_backoff(risky_network_call, RetryConfig(max_attempts=3))

# Always handle both field naming conventions
views = reel.get('play_count') or reel.get('views') or 0
```

### 12.2 DON'T DO THIS

```python
# DON'T write directly to history JSON
with open('scrape_history.json', 'w') as f:  # WRONG
    json.dump(data, f)

# DON'T call LLM APIs directly
response = openai.chat.completions.create(...)  # WRONG - use LLMClient

# DON'T use print() for logging
print(f"Error: {e}")  # WRONG - use logger.error()

# DON'T create custom job tracking
job_status = {}  # WRONG - use state_manager

# DON'T use yt-dlp CLI directly
subprocess.run(['yt-dlp', url])  # WRONG - use sys.executable -m yt_dlp

# DON'T assume field names
views = reel['play_count']  # WRONG - might be 'views' for TikTok
```

### 12.3 Debugging Checklist

When something doesn't work:

1. **Assets not appearing in library?**
   - Check: Was `Asset.create()` called on job completion?
   - Check: Is `/api/assets` merging database AND history?
   - Check: Is the asset type in the filter list?

2. **Job progress not updating?**
   - Check: Is `state_manager.update_job()` being called?
   - Check: Is the frontend polling `/api/jobs/active`?
   - Check: Is the job ID being tracked in `trackedActiveJobs`?

3. **Views/likes showing 0?**
   - Check: Are you using `get_reel_info()` or custom yt-dlp fetch?
   - Check: Are you handling both `play_count` and `views` field names?

4. **Video download failing?**
   - Check: Is yt-dlp being called via `sys.executable -m yt_dlp`?
   - Check: Are cookies loaded correctly?

5. **Transcript empty?**
   - Check: Was `transcribe` option enabled?
   - Check: Was video downloaded first (transcription needs local file)?
   - Check: Is Whisper model available / API key set?

### 12.4 Job Status & Progress Patterns (Added 2026-01-03)

**CRITICAL LEARNINGS** from skeleton ripper consistency work:

#### Status Consistency Rule

**All job types MUST use the same status values.** Both regular scrapes and skeleton ripper use:
- `status = 'running'` while active
- `status = 'starting'` during initialization
- `status = 'complete'` / `'error'` / `'aborted'` on finish

**WRONG** (skeleton ripper was doing this):
```python
# DON'T set status to phase-specific values
active_skeleton_jobs[job_id]['status'] = progress.status.value  # 'scraping', 'transcribing'
```

**CORRECT**:
```python
# DO set status to 'running' consistently
active_skeleton_jobs[job_id]['status'] = 'running'
# Detailed phase info goes in the progress object, not status
active_skeleton_jobs[job_id]['progress']['phase'] = progress.status.value
```

#### Backend Progress Calculation

**Progress percentage (`progress_pct`) should be calculated on the backend**, not frontend.
This ensures consistent progress display and prevents jumps/resets.

For skeleton ripper, the phases map to these ranges:

| Pipeline Phase | Progress Range | Based On |
|----------------|----------------|----------|
| Fetching reels | 0-5% | Fixed (brief phase) |
| Downloading | 5-35% | `videos_downloaded / total_target` |
| Transcribing | 35-70% | `videos_transcribed / total_target` |
| Extracting | 70-90% | Extraction completion |
| Aggregating | 90-95% | Fixed |
| Synthesizing | 95-100% | Fixed |

**Example backend calculation** (`/api/skeleton-ripper/status`):
```python
pipeline_status = progress.get('status')  # 'scraping', 'transcribing', etc.

if pipeline_status == 'scraping':
    # Scraping phase includes fetch+download+transcribe internally
    if videos_transcribed > 0:
        trans_pct = (videos_transcribed / total_target) * 100 if total_target else 0
        progress_pct = 35 + int(trans_pct * 0.35)  # 35-70%
    elif videos_downloaded > 0:
        dl_pct = (videos_downloaded / total_target) * 100 if total_target else 0
        progress_pct = 5 + int(dl_pct * 0.30)  # 5-35%
    else:
        progress_pct = 5  # Still fetching reels
elif pipeline_status == 'extracting':
    progress_pct = 75
elif pipeline_status == 'aggregating':
    progress_pct = 92
elif pipeline_status == 'synthesizing':
    progress_pct = 97
```

#### Progress Callback Forwarding

**Always forward progress callbacks to underlying functions** for granular updates.

**WRONG** (skeleton ripper was missing reel count updates):
```python
# No callback passed - user sees "Fetching reels..." with no count
reels, profile, error = get_user_reels(session, username, max_reels=100)
```

**CORRECT**:
```python
# Create callback that forwards to main progress handler
def fetch_progress(msg, phase=None, progress_pct=None):
    progress.message = msg  # e.g., "Found 47 reels..."
    self._notify(on_progress, progress)

reels, profile, error = get_user_reels(session, username, max_reels=100,
                                        progress_callback=fetch_progress)
```

#### Phase vs Status Fields

The progress object has TWO similar-sounding fields with different purposes:

| Field | Purpose | Example Values |
|-------|---------|----------------|
| `progress.status` | Enum value for internal state machine | `'scraping'`, `'transcribing'`, `'extracting'` |
| `progress.phase` | Display text for UI | `"Scraping videos..."`, `"Found 47 reels..."` |
| `progress.message` | Detailed status message | `"Transcribing video 3 of 10..."` |

**Use `status` for logic, `phase`/`message` for display.**

---

## Appendix: Quick Reference

### API Endpoints Quick List

```
Scraping:
POST /api/scrape              - Single scrape
POST /api/scrape/batch        - Multi-creator batch
POST /api/scrape/direct       - Direct URL/ID scrape
GET  /api/scrape/{id}/status  - Poll progress
POST /api/scrape/{id}/abort   - Cancel

Skeleton Ripper:
GET  /api/skeleton-ripper/providers     - List LLM providers
POST /api/skeleton-ripper/start         - Start analysis
GET  /api/skeleton-ripper/status/{id}   - Poll progress
GET  /api/skeleton-ripper/report/{id}   - Get report

Assets:
GET  /api/assets              - List (with filters)
GET  /api/assets/{id}         - Get one
POST /api/assets              - Create
PUT  /api/assets/{id}         - Update
DELETE /api/assets/{id}       - Delete

Collections:
GET  /api/collections         - List
POST /api/collections         - Create

Jobs (V3):
GET  /api/jobs/active         - Active jobs
GET  /api/jobs/recent         - Recent completed
GET  /api/health              - Health check
```

### Key File Locations

```
Main server:         app.py
Scraper logic:       scraper/core.py
Pipeline:            skeleton_ripper/pipeline.py
Asset ORM:           storage/models.py
State tracking:      utils/state_manager.py
Frontend logic:      static/js/workspace.js
Frontend state:      static/js/state/store.js
Database:            state/reelrecon.db
Active jobs:         state/active_scrapes.json
```

### Import Quick Reference

```python
# Assets
from storage.models import Asset, Collection, AssetCollection

# State management
from utils.state_manager import state_manager, ScrapeProgress, ScrapePhase, ScrapeState

# Logging
from utils.logger import logger

# Retry
from utils.retry import retry_with_backoff, RetryConfig

# LLM
from skeleton_ripper.llm_client import LLMClient

# Scraping
from scraper.core import run_scrape, get_reel_info, transcribe_video, transcribe_video_openai
from scraper.tiktok import scrape_tiktok_profile
```

---

*This document is the SINGLE SOURCE OF TRUTH. When in doubt, consult this file first.*

*Last updated: 2026-01-03*
