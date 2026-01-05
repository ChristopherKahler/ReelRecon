# ReelRecon Refactoring Specification

**Version**: 1.0
**Date**: 2026-01-04
**Status**: Post-V3 Roadmap
**Target**: v3.1.0 - v3.4.0 (incremental releases)

---

## Executive Summary

This document outlines the refactoring strategy for ReelRecon after the V3 launch. The codebase has grown organically and now requires architectural improvements to support future development, improve maintainability, and enable team collaboration.

### Current State Metrics

| Metric | Value | Issue |
|--------|-------|-------|
| `app.py` | 3,082 lines | Monolith with 114 functions |
| `workspace.js` | 4,243 lines | No component separation |
| HTTP Routes | 60+ | Mixed concerns in handlers |
| Legacy Systems | 2 | history.json + SQLite coexist |

### Goals

1. **Separation of Concerns** - Routes handle HTTP only, services handle logic
2. **Component Architecture** - Frontend split into reusable modules
3. **Single Source of Truth** - Eliminate legacy data systems
4. **Testability** - Enable unit testing through dependency injection
5. **Developer Experience** - Clear boundaries for multi-developer work

---

## Table of Contents

1. [Dependency Graph](#1-dependency-graph)
2. [Extraction Priority Matrix](#2-extraction-priority-matrix)
3. [Phase R1: Backend Services](#3-phase-r1-backend-services)
4. [Phase R2: Route Blueprints](#4-phase-r2-route-blueprints)
5. [Phase R3: Frontend Components](#5-phase-r3-frontend-components)
6. [Phase R4: Legacy Removal](#6-phase-r4-legacy-removal)
7. [Specific Extraction Targets](#7-specific-extraction-targets)
8. [Risk Assessment](#8-risk-assessment)
9. [Testing Strategy](#9-testing-strategy)
10. [Release Plan](#10-release-plan)

---

## 1. Dependency Graph

### 1.1 Current Module Dependencies

```
                              ┌─────────────────────────────────────────────┐
                              │                  app.py                      │
                              │               (3,082 lines)                  │
                              │  114 functions, 60+ routes, ALL logic       │
                              └─────────────────┬───────────────────────────┘
                                                │
              ┌─────────────────┬───────────────┼───────────────┬─────────────────┐
              │                 │               │               │                 │
              ▼                 ▼               ▼               ▼                 ▼
    ┌─────────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │  scraper/core   │ │   scraper/  │ │  skeleton_  │ │   storage/  │ │    utils/   │
    │   (970 lines)   │ │   tiktok    │ │   ripper/   │ │   models    │ │  (1,173)    │
    │   13 functions  │ │  (470 lines)│ │  (2,798)    │ │  (370 lines)│ │             │
    └────────┬────────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
             │                 │               │               │               │
             │                 │               │               │               │
    ┌────────┴─────────────────┴───────────────┴───────────────┴───────────────┘
    │
    │  CROSS-CUTTING CONCERNS:
    │  - Config loading (scattered)
    │  - Error handling (duplicated)
    │  - Job state (utils/state_manager.py)
    │  - Asset operations (storage/models.py)
    │
    └──────────────────────────────────────────────────────────────────────────────
```

### 1.2 Function Call Chains

#### Scraping Pipeline
```
start_scrape() [app.py:794]
    │
    ├──► Thread spawns ──► run_scrape() [scraper/core.py:666]
    │                           │
    │                           ├──► create_session() [core.py:77]
    │                           ├──► get_user_reels() [core.py:189]
    │                           ├──► download_video() [core.py:334]
    │                           ├──► load_whisper_model() [core.py:602]
    │                           └──► transcribe_video() [core.py:433]
    │
    ├──► state_manager.create_job()
    ├──► state_manager.update_job() [multiple]
    └──► Asset.create() [on completion]
```

#### Skeleton Ripper Pipeline
```
start_skeleton_ripper() [app.py:2556]
    │
    ├──► Thread spawns ──► SkeletonRipperPipeline.run() [pipeline.py:746]
    │                           │
    │                           ├──► Stage 1: run_scrape() [reuses core.py]
    │                           ├──► Stage 2: extractor.extract_single()
    │                           │                  └──► LLMClient.complete()
    │                           ├──► Stage 3: aggregator.aggregate()
    │                           ├──► Stage 4: synthesizer.generate_report()
    │                           │                  └──► LLMClient.complete()
    │                           └──► Stage 5: Asset.create()
    │
    ├──► active_skeleton_jobs[job_id] = {...}
    └──► save_skeleton_jobs()
```

#### LLM Calls (Tangled)
```
rewrite_script() [app.py:2155]
    │
    ├──► call_openai() [app.py:201]
    ├──► call_anthropic() [app.py:226]
    ├──► call_google() [app.py:252]
    └──► call_ollama() [app.py:185]

skeleton_ripper/extractor.py
    └──► LLMClient.complete() [llm_client.py:382]

skeleton_ripper/synthesizer.py
    └──► LLMClient.complete() [llm_client.py:382]

PROBLEM: Two separate LLM calling patterns exist!
         app.py uses direct functions, skeleton_ripper uses LLMClient class
```

### 1.3 Data Flow Dependencies

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA STORES                                     │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌────────────────────┐
                    │  scrape_history.   │  ◄── LEGACY (deprecate)
                    │       json         │
                    └─────────┬──────────┘
                              │ read by: load_history(), add_to_history()
                              │ write by: save_history()
                              ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         state/reelrecon.db                                  │
│                         (PRIMARY - SQLite)                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐                  │
│  │    assets    │  │  collections │  │ asset_collections│                  │
│  └──────────────┘  └──────────────┘  └──────────────────┘                  │
└────────────────────────────────────────────────────────────────────────────┘
        ▲                                    ▲
        │ read/write: Asset.*, Collection.*  │
        │ via storage/models.py              │
        └────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│                         state/active_scrapes.json                           │
│                         (Job Queue - Active)                                │
│  read/write: ScrapeStateManager                                            │
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│                         state/skeleton_jobs.json                            │
│                         (Skeleton Ripper Jobs)                              │
│  read: load_skeleton_jobs()                                                 │
│  write: save_skeleton_jobs()                                                │
│  PROBLEM: Not using ScrapeStateManager!                                     │
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│                         state/archived_jobs.json                            │
│                         (Archived Jobs)                                     │
│  read: load_archived_jobs()                                                 │
│  write: save_archived_jobs()                                                │
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│                              config.json                                    │
│                         (User Settings)                                     │
│  read: load_config() - called 5+ places                                     │
│  write: save_config() - called 1 place                                      │
└────────────────────────────────────────────────────────────────────────────┘
```

### 1.4 Frontend Dependencies

```
workspace.html
    │
    └──► workspace.js (4,243 lines - MONOLITH)
              │
              ├──► utils/api.js (API client)
              ├──► utils/router.js (client routing)
              └──► state/store.js (minimal state)

              INTERNAL DEPENDENCIES (tangled):
              ┌──────────────────────────────────────────────┐
              │  Modal Functions (Lines 2458-3009)           │
              │    └──► renderNewScrapeModal()               │
              │    └──► renderDirectReelModal()              │
              │    └──► renderNewAnalysisModal()             │
              │         └──► calls API.getProviders()        │
              │         └──► calls startAnalysis()           │
              └──────────────────────────────────────────────┘
                              │ depends on
                              ▼
              ┌──────────────────────────────────────────────┐
              │  Job Functions (Lines 408-866)               │
              │    └──► loadJobs()                           │
              │    └──► renderJobs()                         │
              │    └──► pollActiveJobsOnce()                 │
              │         └──► pollSingleJob()                 │
              │              └──► updates DOM directly       │
              └──────────────────────────────────────────────┘
                              │ depends on
                              ▼
              ┌──────────────────────────────────────────────┐
              │  Asset Functions (Lines 1062-1399)           │
              │    └──► reloadAssets()                       │
              │    └──► renderAssets()                       │
              │    └──► renderAssetCard()                    │
              │    └──► openAssetDetail()                    │
              │         └──► renderDetailPanel()             │
              └──────────────────────────────────────────────┘
                              │ depends on
                              ▼
              ┌──────────────────────────────────────────────┐
              │  Detail Panel (Lines 1405-2222)              │
              │    └──► renderAssetContent()                 │
              │    └──► renderReelAccordionItem()            │
              │    └──► renderSkeletonAccordionItem()        │
              │         └──► calls saveTranscriptAsAsset()   │
              │         └──► calls saveSkeletonAsAsset()     │
              └──────────────────────────────────────────────┘
```

---

## 2. Extraction Priority Matrix

### Priority Levels

| Priority | Criteria | Risk Level |
|----------|----------|------------|
| **P0** | Blocking future development, high code duplication | Low |
| **P1** | Improves maintainability, moderate coupling | Medium |
| **P2** | Nice to have, cosmetic improvements | Low |
| **P3** | Future consideration, minimal impact | N/A |

### Extraction Targets

| Target | Current Location | Extract To | Priority | Risk | Lines Affected |
|--------|------------------|------------|----------|------|----------------|
| LLM Service | app.py:152-272 | services/llm_service.py | **P0** | Low | 120 |
| Scrape Service | app.py:794-1255 | services/scrape_service.py | **P1** | Medium | 461 |
| Skeleton Service | app.py:2450-2500, 2556-2740 | services/skeleton_service.py | **P1** | Medium | 300 |
| Video Service | app.py + core.py (scattered) | services/video_service.py | **P2** | Low | 150 |
| Config Service | app.py:105-150 | services/config_service.py | **P2** | Low | 45 |
| History Deprecation | app.py:273-335 | Remove + migrate | **P1** | Medium | 62 |
| JS Modal Components | workspace.js:2458-3009 | modals/*.js | **P0** | Low | 551 |
| JS Job Components | workspace.js:408-866 | jobs/*.js | **P1** | Medium | 458 |
| JS Asset Components | workspace.js:1062-1399 | assets/*.js | **P1** | Medium | 337 |
| JS Detail Components | workspace.js:1405-2222 | panels/*.js | **P1** | Medium | 817 |
| Route Blueprints | app.py (all routes) | routes/*.py | **P2** | High | 2000+ |

---

## 3. Phase R1: Backend Services

**Target Release**: v3.1.0
**Goal**: Extract business logic from route handlers into service modules

### 3.1 New Directory Structure

```
ReelRecon/
├── app.py                    # Reduced to ~500 lines (routes only)
├── services/                 # NEW
│   ├── __init__.py
│   ├── llm_service.py        # All LLM provider calls
│   ├── scrape_service.py     # Scraping orchestration
│   ├── skeleton_service.py   # Skeleton ripper orchestration
│   ├── video_service.py      # Video download/stream
│   ├── asset_service.py      # Asset CRUD wrapper
│   └── config_service.py     # Config load/save
├── scraper/                  # Unchanged
├── skeleton_ripper/          # Unchanged
├── storage/                  # Unchanged
└── utils/                    # Unchanged
```

### 3.2 LLM Service Extraction (P0)

**Current State** (app.py lines 152-272):
```python
# 5 separate functions with duplicated error handling
def call_openai(prompt, model, api_key): ...
def call_anthropic(prompt, model, api_key): ...
def call_google(prompt, model, api_key): ...
def call_ollama(prompt, model): ...
def strip_thinking_output(text): ...
```

**Target State** (services/llm_service.py):
```python
from enum import Enum
from typing import Optional
from dataclasses import dataclass

class LLMProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OLLAMA = "ollama"

@dataclass
class LLMConfig:
    provider: LLMProvider
    model: str
    api_key: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000

class LLMService:
    """Unified LLM interface for all providers."""

    def __init__(self, config: LLMConfig):
        self.config = config

    def complete(self, prompt: str) -> str:
        """Call the configured LLM provider."""
        if self.config.provider == LLMProvider.OPENAI:
            return self._call_openai(prompt)
        elif self.config.provider == LLMProvider.ANTHROPIC:
            return self._call_anthropic(prompt)
        elif self.config.provider == LLMProvider.GOOGLE:
            return self._call_google(prompt)
        elif self.config.provider == LLMProvider.OLLAMA:
            return self._call_ollama(prompt)

    def _call_openai(self, prompt: str) -> str: ...
    def _call_anthropic(self, prompt: str) -> str: ...
    def _call_google(self, prompt: str) -> str: ...
    def _call_ollama(self, prompt: str) -> str: ...

    @staticmethod
    def strip_thinking_tags(text: str) -> str: ...

    @staticmethod
    def get_available_providers() -> list[dict]: ...

    @staticmethod
    def validate_api_key(provider: LLMProvider, api_key: str) -> bool: ...
```

**Migration Steps**:
1. Create `services/llm_service.py` with new class
2. Move function bodies from app.py (lines 152-272)
3. Update `rewrite_script()` to use `LLMService`
4. Update skeleton_ripper to use same service (unify with existing LLMClient)
5. Delete old functions from app.py
6. Test all LLM-calling features

### 3.3 Scrape Service Extraction (P1)

**Current State** (app.py lines 794-1255):
- `start_scrape()` - 222 lines, does HTTP handling + job creation + thread spawning
- `start_batch_scrape()` - 211 lines, similar problems
- `start_direct_scrape()` - 170 lines

**Target State** (services/scrape_service.py):
```python
from dataclasses import dataclass
from typing import Optional, Callable
from pathlib import Path

@dataclass
class ScrapeOptions:
    platform: str = "instagram"
    max_reels: int = 100
    top_n: int = 10
    download_video: bool = True
    transcribe: bool = True
    transcribe_provider: str = "local"
    whisper_model: str = "small.en"
    date_filter_days: Optional[int] = None

class ScrapeService:
    """Orchestrates scraping operations."""

    def __init__(self, state_manager, config):
        self.state_manager = state_manager
        self.config = config

    def start_profile_scrape(
        self,
        username: str,
        options: ScrapeOptions,
        on_progress: Optional[Callable] = None
    ) -> str:
        """Start single profile scrape, returns job_id."""
        job = self.state_manager.create_job(...)
        thread = Thread(target=self._run_scrape, args=(job, options, on_progress))
        thread.start()
        return job.scrape_id

    def start_batch_scrape(
        self,
        usernames: list[str],
        options: ScrapeOptions
    ) -> tuple[str, list[str]]:
        """Start batch scrape, returns (batch_id, job_ids)."""
        ...

    def start_direct_scrape(
        self,
        shortcodes: list[str],
        options: ScrapeOptions
    ) -> str:
        """Scrape specific reels by shortcode."""
        ...

    def get_job_status(self, job_id: str) -> dict:
        """Get current job progress."""
        return self.state_manager.get_job(job_id).to_dict()

    def abort_job(self, job_id: str) -> bool:
        """Cancel running job."""
        return self.state_manager.abort_job(job_id)

    def _run_scrape(self, job, options, on_progress):
        """Background thread execution."""
        # Move logic from app.py run_batch_scrape thread target
        ...
```

**Migration Steps**:
1. Create `services/scrape_service.py`
2. Extract job creation logic from `start_scrape()`
3. Extract thread target logic
4. Update route handlers to be thin wrappers
5. Keep `scraper/core.py` unchanged (low-level functions)

### 3.4 Skeleton Service Extraction (P1)

**Current State**:
- `active_skeleton_jobs` dict in app.py global scope
- `load_skeleton_jobs()` / `save_skeleton_jobs()` (app.py:2450-2487)
- Job tracking separate from `ScrapeStateManager`

**Target State** (services/skeleton_service.py):
```python
class SkeletonService:
    """Orchestrates skeleton ripper operations."""

    def __init__(self, state_manager, llm_service, config):
        self.state_manager = state_manager
        self.llm_service = llm_service
        self.config = config

    def start_analysis(
        self,
        usernames: list[str],
        videos_per_creator: int,
        llm_provider: str,
        llm_model: str
    ) -> str:
        """Start skeleton analysis, returns job_id."""
        ...

    def get_job_status(self, job_id: str) -> dict: ...
    def get_report(self, job_id: str) -> dict: ...
    def get_report_markdown(self, job_id: str) -> str: ...
    def save_skeleton_as_asset(self, skeleton_data: dict) -> str: ...
```

**Key Change**: Unify job tracking with `ScrapeStateManager` instead of separate JSON files.

---

## 4. Phase R2: Route Blueprints

**Target Release**: v3.2.0
**Goal**: Split app.py routes into logical Flask Blueprints

### 4.1 Blueprint Structure

```
routes/
├── __init__.py           # Blueprint registration
├── scrape.py             # /api/scrape/* endpoints
├── skeleton.py           # /api/skeleton-ripper/* endpoints
├── assets.py             # /api/assets/* endpoints
├── collections.py        # /api/collections/* endpoints
├── jobs.py               # /api/jobs/* endpoints
├── settings.py           # /api/settings, /api/version, etc.
├── video.py              # Video streaming endpoints
└── pages.py              # HTML page routes
```

### 4.2 Example Blueprint (routes/scrape.py)

```python
from flask import Blueprint, request, jsonify
from services.scrape_service import ScrapeService, ScrapeOptions

scrape_bp = Blueprint('scrape', __name__, url_prefix='/api/scrape')

# Dependency injection
scrape_service: ScrapeService = None

def init_scrape_routes(service: ScrapeService):
    global scrape_service
    scrape_service = service

@scrape_bp.route('', methods=['POST'])
def start_scrape():
    """Start single profile scrape."""
    data = request.json
    options = ScrapeOptions(
        platform=data.get('platform', 'instagram'),
        max_reels=data.get('max_reels', 100),
        top_n=data.get('top_n', 10),
        download_video=data.get('download', True),
        transcribe=data.get('transcribe', True),
    )
    job_id = scrape_service.start_profile_scrape(data['username'], options)
    return jsonify({'success': True, 'scrape_id': job_id})

@scrape_bp.route('/batch', methods=['POST'])
def start_batch_scrape():
    """Start multi-profile batch scrape."""
    data = request.json
    options = ScrapeOptions(**data.get('options', {}))
    batch_id, job_ids = scrape_service.start_batch_scrape(data['usernames'], options)
    return jsonify({'success': True, 'batch_id': batch_id, 'scrape_ids': job_ids})

@scrape_bp.route('/<scrape_id>/status', methods=['GET'])
def get_status(scrape_id):
    """Poll job progress."""
    status = scrape_service.get_job_status(scrape_id)
    return jsonify(status)

@scrape_bp.route('/<scrape_id>/abort', methods=['POST'])
def abort_scrape(scrape_id):
    """Cancel running scrape."""
    success = scrape_service.abort_job(scrape_id)
    return jsonify({'success': success})
```

### 4.3 Updated app.py

```python
from flask import Flask
from routes import scrape_bp, skeleton_bp, assets_bp, collections_bp, jobs_bp, settings_bp
from services import ScrapeService, SkeletonService, LLMService, ConfigService

def create_app():
    app = Flask(__name__)

    # Initialize services
    config_service = ConfigService()
    llm_service = LLMService(config_service.get_llm_config())
    scrape_service = ScrapeService(state_manager, config_service)
    skeleton_service = SkeletonService(state_manager, llm_service, config_service)

    # Initialize route blueprints with dependencies
    init_scrape_routes(scrape_service)
    init_skeleton_routes(skeleton_service)

    # Register blueprints
    app.register_blueprint(scrape_bp)
    app.register_blueprint(skeleton_bp)
    app.register_blueprint(assets_bp)
    app.register_blueprint(collections_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(settings_bp)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(port=5001)
```

---

## 5. Phase R3: Frontend Components

**Target Release**: v3.3.0
**Goal**: Split workspace.js monolith into component modules

### 5.1 Component Structure

```
static/js/
├── workspace.js              # Main coordinator (~500 lines)
├── components/
│   ├── Modal.js              # Base modal class
│   ├── Toast.js              # Notification component
│   └── LoadingSpinner.js     # Loading indicator
├── modals/
│   ├── NewScrapeModal.js     # Scrape form modal
│   ├── DirectReelModal.js    # Direct reel form
│   ├── NewAnalysisModal.js   # Skeleton ripper form
│   ├── RewriteModal.js       # AI rewrite wizard
│   └── CollectionModal.js    # Add to collection
├── views/
│   ├── LibraryView.js        # Asset grid view
│   ├── JobsView.js           # Jobs list view
│   ├── FavoritesView.js      # Starred items
│   └── SettingsView.js       # Settings panel
├── panels/
│   ├── DetailPanel.js        # Slideout panel base
│   ├── ScrapeDetail.js       # Scrape report detail
│   └── SkeletonDetail.js     # Skeleton report detail
├── cards/
│   ├── AssetCard.js          # Asset grid card
│   └── JobCard.js            # Job list card
├── utils/
│   ├── api.js                # API client (exists)
│   ├── router.js             # Client routing (exists)
│   ├── poller.js             # Job polling logic (NEW)
│   ├── clipboard.js          # Copy functions (NEW)
│   └── helpers.js            # formatNumber, escapeHtml
└── state/
    └── store.js              # State management (exists)
```

### 5.2 Example Component (modals/NewScrapeModal.js)

```javascript
// modals/NewScrapeModal.js
import { Modal } from '../components/Modal.js';
import { API } from '../utils/api.js';

export class NewScrapeModal extends Modal {
    constructor() {
        super('new-scrape-modal');
        this.state = {
            platform: 'instagram',
            usernames: '',
            maxReels: 100,
            topN: 10,
            transcribe: true,
            whisperModel: 'small.en'
        };
    }

    render() {
        return `
            <div class="modal-header">
                <h2>New Scrape</h2>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                ${this.renderPlatformToggle()}
                ${this.renderUsernameInput()}
                ${this.renderOptions()}
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                <button class="btn btn-primary" onclick="newScrapeModal.submit()">
                    Start Scrape
                </button>
            </div>
        `;
    }

    renderPlatformToggle() {
        return `
            <div class="platform-toggle">
                <button class="${this.state.platform === 'instagram' ? 'active' : ''}"
                        onclick="newScrapeModal.setPlatform('instagram')">
                    Instagram
                </button>
                <button class="${this.state.platform === 'tiktok' ? 'active' : ''}"
                        onclick="newScrapeModal.setPlatform('tiktok')">
                    TikTok
                </button>
            </div>
        `;
    }

    renderUsernameInput() { ... }
    renderOptions() { ... }

    setPlatform(platform) {
        this.state.platform = platform;
        this.update();
    }

    async submit() {
        const usernames = this.state.usernames.split('\n').filter(u => u.trim());

        if (usernames.length === 0) {
            showToast('Please enter at least one username', 'error');
            return;
        }

        try {
            const response = await API.startBatchScrape({
                usernames,
                platform: this.state.platform,
                max_reels: this.state.maxReels,
                top_n: this.state.topN,
                transcribe: this.state.transcribe,
                whisper_model: this.state.whisperModel
            });

            if (response.success) {
                this.close();
                navigateTo('jobs');
                showToast(`Started scrape for ${usernames.length} creator(s)`, 'success');
            }
        } catch (error) {
            showToast(`Failed to start scrape: ${error.message}`, 'error');
        }
    }
}

// Export singleton
export const newScrapeModal = new NewScrapeModal();
```

### 5.3 Migration Strategy

1. **Extract utilities first** (lowest risk)
   - Move `copyToClipboard()`, `formatNumber()`, `escapeHtml()` to `utils/helpers.js`
   - Move polling functions to `utils/poller.js`

2. **Extract components second**
   - Create `components/Toast.js` for notifications
   - Create `components/Modal.js` base class

3. **Extract modals third**
   - One modal at a time: scrape → direct → analysis → rewrite
   - Each modal becomes a separate file with same functionality

4. **Extract views last**
   - Views have most dependencies
   - Extract after modals work independently

---

## 6. Phase R4: Legacy Removal

**Target Release**: v3.4.0
**Goal**: Eliminate deprecated code and dual data systems

### 6.1 Remove Legacy Templates

| File | Lines | Action |
|------|-------|--------|
| `templates/index.html` | 689 | Delete (v1/v2 UI) |
| `templates/library.html` | 3,518 | Delete (v1/v2 UI) |
| `templates/skeleton_ripper.html` | 3,171 | Delete (v1/v2 UI) |
| `static/css/tactical.css` | 2,100 | Delete (old theme) |
| `static/js/app.js` | 2,716 | Delete (v1/v2 logic) |

**Total lines removed**: ~12,194

### 6.2 Migrate scrape_history.json to Database

**Current Problem**:
- `scrape_history.json` contains legacy scrape records
- `Asset` table contains new records
- Both are queried in `list_assets()`

**Migration Script**:
```python
# storage/migrate_history.py (already partially exists)

def migrate_history_to_assets():
    """One-time migration of scrape_history.json to Asset table."""
    history = load_history()

    for item in history:
        # Check if already migrated
        existing = Asset.get(item['id'])
        if existing:
            continue

        # Create asset from history item
        Asset.create(
            id=item['id'],
            type='scrape_report',
            title=f"Scrape: @{item['username']}",
            content_path=item.get('output_dir'),
            preview=f"{len(item.get('top_reels', []))} reels",
            metadata={
                'username': item['username'],
                'top_reels': item.get('top_reels', []),
                'platform': item.get('platform', 'instagram'),
                'timestamp': item.get('timestamp')
            },
            created_at=item.get('timestamp')
        )

    # Backup and remove history file
    shutil.move('scrape_history.json', 'scrape_history.json.bak')
```

### 6.3 Unify Job State Management

**Current Problem**:
- Scrapes use `ScrapeStateManager` (active_scrapes.json)
- Skeleton jobs use `active_skeleton_jobs` dict + skeleton_jobs.json
- Archived jobs use `archived_jobs.json`

**Solution**: Extend `ScrapeStateManager` to handle all job types:

```python
# utils/state_manager.py

class UnifiedJobManager:
    """Manages all job types with unified persistence."""

    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.jobs_file = state_dir / 'jobs.json'
        self.archive_file = state_dir / 'jobs_archive.json'

    def create_job(self, job_type: str, **kwargs) -> Job:
        """Create job of any type (scrape, batch, skeleton, direct)."""
        job = Job(
            id=generate_job_id(job_type),
            type=job_type,
            status='pending',
            created_at=datetime.now().isoformat(),
            **kwargs
        )
        self._save_job(job)
        return job

    def list_active(self, job_type: Optional[str] = None) -> list[Job]:
        """List active jobs, optionally filtered by type."""
        ...

    def list_recent(self, limit: int = 20) -> list[Job]:
        """List recently completed jobs."""
        ...

    def archive(self, job_id: str) -> bool:
        """Move job to archive."""
        ...

    def restore(self, job_id: str) -> bool:
        """Restore job from archive."""
        ...
```

---

## 7. Specific Extraction Targets

### 7.1 Functions to Extract from app.py

| Function | Lines | Extract To | Priority |
|----------|-------|------------|----------|
| `call_openai()` | 201-224 | services/llm_service.py | P0 |
| `call_anthropic()` | 226-250 | services/llm_service.py | P0 |
| `call_google()` | 252-271 | services/llm_service.py | P0 |
| `call_ollama()` | 185-199 | services/llm_service.py | P0 |
| `strip_thinking_output()` | 163-182 | services/llm_service.py | P0 |
| `generate_ai_prompt()` | 152-161 | services/llm_service.py | P0 |
| `load_config()` | 105-118 | services/config_service.py | P2 |
| `save_config()` | 120-124 | services/config_service.py | P2 |
| `load_history()` | 273-282 | DEPRECATE | P1 |
| `save_history()` | 284-288 | DEPRECATE | P1 |
| `add_to_history()` | 290-333 | DEPRECATE | P1 |
| `load_skeleton_jobs()` | 2450-2458 | services/skeleton_service.py | P1 |
| `save_skeleton_jobs()` | 2460-2475 | services/skeleton_service.py | P1 |
| `load_archived_jobs()` | 2477-2485 | utils/state_manager.py | P1 |
| `save_archived_jobs()` | 2487-2498 | utils/state_manager.py | P1 |

### 7.2 Functions to Extract from workspace.js

| Function | Lines | Extract To | Priority |
|----------|-------|------------|----------|
| `renderNewScrapeModal()` | 2489-2563 | modals/NewScrapeModal.js | P0 |
| `setupNewScrapeModal()` | 2565-2601 | modals/NewScrapeModal.js | P0 |
| `renderDirectReelModal()` | 2680-2751 | modals/DirectReelModal.js | P0 |
| `setupDirectReelModal()` | 2753-2822 | modals/DirectReelModal.js | P0 |
| `renderNewAnalysisModal()` | 2901-2950 | modals/NewAnalysisModal.js | P0 |
| `setupNewAnalysisModal()` | 2952-3007 | modals/NewAnalysisModal.js | P0 |
| `startJobsPolling()` | 477-480 | utils/poller.js | P1 |
| `stopJobsPolling()` | 552-556 | utils/poller.js | P1 |
| `pollActiveJobsOnce()` | 482-495 | utils/poller.js | P1 |
| `pollSingleJob()` | 497-550 | utils/poller.js | P1 |
| `copyToClipboard()` | 1893-1901 | utils/clipboard.js | P2 |
| `copyReelForAI()` | 1903-1915 | utils/clipboard.js | P2 |
| `formatNumber()` | 2254-2258 | utils/helpers.js | P2 |
| `escapeHtml()` | 2260-2265 | utils/helpers.js | P2 |

### 7.3 Code Duplication to Eliminate

| Duplication | Locations | Solution |
|-------------|-----------|----------|
| `generate_error_code()` | scraper/core.py:26, scraper/tiktok.py:20 | Move to utils/errors.py |
| Modal setup pattern | 3 modals with similar event wiring | Base Modal class |
| Progress callback pattern | app.py:865, 1105 (duplicated) | Extract to helper |
| Field name handling | Multiple reel normalization spots | Helper function |

---

## 8. Risk Assessment

### 8.1 Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking existing features | Medium | High | Comprehensive test suite before refactoring |
| Merge conflicts with active development | High | Medium | Refactor in isolated PRs, coordinate branches |
| Service initialization bugs | Medium | Medium | Dependency injection with clear interfaces |
| Frontend component loading issues | Low | Medium | ES6 module bundling or careful script ordering |
| Performance regression | Low | Low | Profile before/after critical paths |
| Incomplete migration | Medium | Medium | Feature flags to toggle old/new code |

### 8.2 Rollback Strategy

Each phase should be reversible:

1. **Keep old code commented** (not deleted) for first release
2. **Feature flag** for major changes:
   ```python
   USE_SERVICE_LAYER = os.environ.get('USE_SERVICE_LAYER', 'false') == 'true'

   if USE_SERVICE_LAYER:
       result = scrape_service.start_profile_scrape(...)
   else:
       result = start_scrape_legacy(...)
   ```
3. **Semantic versioning** - breaking changes bump major version
4. **Database migrations** - reversible with down migrations

---

## 9. Testing Strategy

### 9.1 Unit Tests (New)

Create test suite before refactoring:

```
tests/
├── test_services/
│   ├── test_llm_service.py
│   ├── test_scrape_service.py
│   └── test_skeleton_service.py
├── test_routes/
│   ├── test_scrape_routes.py
│   └── test_asset_routes.py
└── test_integration/
    ├── test_scrape_flow.py
    └── test_skeleton_flow.py
```

### 9.2 Test Coverage Requirements

| Component | Minimum Coverage | Priority |
|-----------|------------------|----------|
| LLMService | 80% | P0 |
| ScrapeService | 70% | P1 |
| SkeletonService | 70% | P1 |
| Route handlers | 60% | P2 |
| Frontend components | 50% | P2 |

### 9.3 Regression Test Checklist

Before each release:

- [ ] Single profile scrape works (Instagram)
- [ ] Single profile scrape works (TikTok)
- [ ] Batch scrape works (multiple creators)
- [ ] Direct reel scrape works
- [ ] Video download works
- [ ] Transcription works (local Whisper)
- [ ] Transcription works (OpenAI API)
- [ ] Skeleton ripper starts and completes
- [ ] Report generation works
- [ ] Asset creation works
- [ ] Asset deletion works
- [ ] Collection management works
- [ ] Job polling updates UI
- [ ] Progress bar animates correctly
- [ ] Detail panel opens/closes
- [ ] Star/favorite toggle works
- [ ] Rewrite wizard generates content

---

## 10. Release Plan

### Timeline

| Release | Target | Focus | Risk |
|---------|--------|-------|------|
| **v3.0.0** | Current | V3 launch (ship first!) | N/A |
| **v3.1.0** | +2 weeks | Backend services extraction | Low |
| **v3.2.0** | +4 weeks | Route blueprints | Medium |
| **v3.3.0** | +6 weeks | Frontend components | Medium |
| **v3.4.0** | +8 weeks | Legacy removal | Low |

### v3.1.0 Deliverables

1. `services/llm_service.py` - Unified LLM interface
2. `services/scrape_service.py` - Scraping orchestration
3. `services/skeleton_service.py` - Skeleton ripper orchestration
4. Updated app.py using services
5. Unit tests for services

### v3.2.0 Deliverables

1. `routes/` directory with blueprints
2. Thin route handlers
3. Dependency injection setup
4. Updated app.py as app factory

### v3.3.0 Deliverables

1. `static/js/components/` directory
2. `static/js/modals/` directory
3. `static/js/utils/` helpers extracted
4. workspace.js as coordinator only

### v3.4.0 Deliverables

1. Delete legacy templates
2. Delete legacy JS/CSS
3. Migrate scrape_history.json
4. Unify job state management
5. Final cleanup

---

## Appendix: Quick Reference

### File Size Targets (Post-Refactor)

| File | Current | Target |
|------|---------|--------|
| app.py | 3,082 | ~500 |
| workspace.js | 4,243 | ~500 |
| Each service | N/A | ~200-400 |
| Each modal | N/A | ~150-250 |
| Each view | N/A | ~200-300 |

### Commit Message Convention for Refactoring

```
refactor(services): extract LLM functions to llm_service.py
refactor(routes): create scrape blueprint
refactor(frontend): extract NewScrapeModal component
chore(cleanup): remove deprecated index.html
```

---

*This document is the refactoring roadmap. Execute after V3 ships.*

*Last updated: 2026-01-04*
