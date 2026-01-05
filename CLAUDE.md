# CLAUDE.md - ReelRecon Development Guide

This file provides guidance to Claude Code when working with ReelRecon.

## CRITICAL: Read Before Any Work

**STOP.** Before making ANY code changes, read `docs/ARCHITECTURE-AUDIT.md`. This is the **SINGLE SOURCE OF TRUTH** for development patterns.

Key sections to understand:
- Section 2: Golden Rules (what systems to use)
- Section 3: Common Mistakes (what keeps going wrong)
- Section 4: Connection Map (how everything links)

## Project Overview

ReelRecon is an Instagram/TikTok content intelligence platform with:
- **Scraper** - Fetch top-performing reels from creators
- **Skeleton Ripper** - Analyze patterns across multiple creators via LLM
- **Library** - Asset management with collections and favorites
- **Direct Reel** - Scrape specific reels by URL/ID

**Tech Stack**: Python 3.8+ / Flask / SQLite / Vanilla JS / CSS

## Current Development Status

| Branch | Status |
|--------|--------|
| `main` | Production releases (v2.2.0) |
| `develop` | Integration branch |
| `feature/v3-workspace-overhaul` | **ACTIVE** - V3 unified workspace |

### V3 Phase Progress

```
Phase 0-4: Complete     (Setup, Design, Library, Actions, Jobs)
Phase 5:   Not Started  (Integration & Polish)
Phase 6:   Not Started  (Migration & Cutover)
Phase 7:   IN PROGRESS  (Batch & Direct Scraping)
Phase 7.5: Complete     (Desktop Launchers)
Phase 8:   Not Started  (Asset Extraction)
```

**Current Task**: Phase 7 - Testing direct reel scrape after bug fixes

See `docs/V3-TASK-TRACKER.md` for granular task breakdown.

## Golden Rules (NEVER Violate)

| Need | USE THIS | NOT THIS |
|------|----------|----------|
| Save an asset | `Asset.create()` from `storage/models.py` | Custom file writes |
| Track job progress | `ScrapeStateManager` from `utils/state_manager.py` | Custom JSON files |
| Call any LLM | `LLMClient` from `skeleton_ripper/llm_client.py` | Direct API calls |
| Transcribe audio | `transcribe_video()` from `scraper/core.py` | New transcription code |
| Log errors | `logger` from `utils/logger.py` | print() statements |
| Retry operations | `retry_with_backoff()` from `utils/retry.py` | Custom retry loops |

## Common Mistakes to Avoid

### 1. Field Name Differences (Instagram vs TikTok)
```python
# CORRECT - handle both:
views = reel.get('play_count') or reel.get('plays') or reel.get('views') or 0
likes = reel.get('like_count') or reel.get('likes') or 0
```

### 2. yt-dlp PATH Issues
```python
# WRONG:
subprocess.run(['yt-dlp', url])

# CORRECT:
import sys
subprocess.run([sys.executable, '-m', 'yt_dlp', url])
```

### 3. Caption Truncation
Known issue at `scraper/core.py` lines 129, 143, 235. Store full caption, truncate only for UI display.

### 4. Not Creating Assets After Job Completion
**CRITICAL**: Every completed job MUST call `Asset.create()` to appear in library.

### 5. Direct Reel Returns 0 Views
Use `get_reel_info()` for metadata, NOT yt-dlp metadata extraction.

## Key File Locations

```
Main server:         app.py (3,082 lines, 60+ routes)
Scraper logic:       scraper/core.py
TikTok scraper:      scraper/tiktok.py
Skeleton pipeline:   skeleton_ripper/pipeline.py
LLM abstraction:     skeleton_ripper/llm_client.py
Asset ORM:           storage/models.py
State tracking:      utils/state_manager.py
V3 Frontend:         static/js/workspace.js
Database:            state/reelrecon.db
```

## Import Quick Reference

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
from scraper.core import run_scrape, get_reel_info, transcribe_video
```

## API Endpoints Quick Reference

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

Assets & Collections:
GET  /api/assets              - List (with filters)
GET  /api/assets/{id}         - Get one
POST /api/assets              - Create
PUT  /api/assets/{id}         - Update
DELETE /api/assets/{id}       - Delete
GET  /api/collections         - List

Jobs (V3):
GET  /api/jobs/active         - Active jobs
GET  /api/jobs/recent         - Recent completed
GET  /api/health              - Health check
```

## Asset Types (Fixed - Don't Invent New Ones)

| Type | Description | Created By |
|------|-------------|------------|
| `scrape_report` | Complete scrape job result | `/api/scrape` completion |
| `skeleton_report` | Complete skeleton ripper analysis | `/api/skeleton-ripper/start` completion |
| `skeleton` | Single extracted pattern | User save action |
| `transcript` | Single video transcript | User save action |
| `synthesis` | AI-generated template | User save action |

## Data Flow Rule

**Every operation MUST create an asset in the database:**

```python
Asset.create(
    type='scrape_report',
    title=f"Scrape: @{username}",
    content_path=output_dir,
    preview=f"{len(top_reels)} reels from @{username}",
    metadata={'username': username, 'top_reels': top_reels, 'platform': platform}
)
```

## Session Handoff Protocol

When ending a session:
1. Update checkboxes in `docs/V3-TASK-TRACKER.md`
2. Update Quick Status section at top of tracker
3. Create changelog entry if significant changes made

When starting a session:
1. Read `docs/V3-TASK-TRACKER.md` Quick Status
2. Read `docs/V3-OVERHAUL-SPEC.md` SESSION STATE section
3. Find first unchecked task in current phase

## Debugging Checklist

1. **Assets not appearing?** Check `Asset.create()` called, `/api/assets` merges DB + history
2. **Job progress stuck?** Check `state_manager.update_job()` calls, frontend polling
3. **Views showing 0?** Use `get_reel_info()`, handle both field name conventions
4. **Video download failing?** Use `sys.executable -m yt_dlp`, check cookies
5. **Transcript empty?** Check transcribe enabled, video downloaded first

## Documentation Reference

| Document | Purpose |
|----------|---------|
| `docs/ARCHITECTURE-AUDIT.md` | **Single source of truth** - Read first |
| `docs/V3-OVERHAUL-SPEC.md` | V3 technical specification |
| `docs/V3-TASK-TRACKER.md` | Granular task checkboxes |
| `docs/CHANGELOG-*.md` | Recent changes and fixes |

## Running the Application

```bash
# Development
python app.py
# Opens at http://localhost:5001

# Desktop launcher (Windows)
pythonw launcher.pyw

# Desktop launcher (Mac)
python ReelRecon-Mac.py
```

## Testing Changes

After making changes:
1. Restart the Flask server (`Ctrl+C` then `python app.py`)
2. Hard refresh browser (`Ctrl+Shift+R`)
3. Test the specific feature modified
4. Check browser console for JS errors
5. Check terminal for Python errors

## Commit Convention

```
<type>(<scope>): <subject>

Types: feat, fix, refactor, style, docs, chore
Examples:
- feat(ui): add sidebar navigation
- fix(scraper): store full caption
- docs: update architecture audit
```

---

*When in doubt, consult `docs/ARCHITECTURE-AUDIT.md` first.*
