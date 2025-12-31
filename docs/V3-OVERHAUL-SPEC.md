# ReelRecon V3.0 - Unified Workspace Overhaul

## Technical Specification & Job Scope Requirements

**Version:** 1.0
**Date:** December 31, 2024
**Branch:** `feature/v3-workspace-overhaul`
**Target Release:** v3.0.0

---

## SESSION STATE (Living Document Protocol)

> **Purpose:** This section is updated each session to maintain continuity across context compactions.
> **Protocol:** At session end, update this section. At session start, read this section first.

### Current Status

| Field | Value |
|-------|-------|
| **Current Phase** | Phase 1 Complete, Ready for Phase 2 |
| **Branch Created** | Yes - `feature/v3-workspace-overhaul` |
| **Last Updated** | 2024-12-31 14:15 CST |
| **Blocker** | None |

### Last Session Summary

_2024-12-31: Phase 0 + Phase 1 complete. Design system updated (Zinc colors, better typography, no scan-lines). Sidebar working with navigation. Ready for Phase 2 (Library View)._

### Active Task

None - Phase 1 complete. Ready to start Phase 2.

### Next Actions

1. Start Phase 2: Build Library view components
2. Create asset grid and cards
3. Implement search and filter functionality
4. Add asset detail panel

### Session Notes

- Phase 0 committed: `6772eaf`
- Phase 1 committed: `a888628`
- User is restarting server themselves after each phase - no need to provide startup instructions
- See `docs/V3-TASK-TRACKER.md` for granular task breakdown

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Analysis](#2-current-state-analysis)
3. [Target State Design](#3-target-state-design)
4. [Scope of Work](#4-scope-of-work)
5. [Technical Architecture](#5-technical-architecture)
6. [Implementation Phases](#6-implementation-phases)
7. [Git Workflow & Release Strategy](#7-git-workflow--release-strategy)
8. [Migration & Data Preservation](#8-migration--data-preservation)
9. [Testing Strategy](#9-testing-strategy)
10. [Risk Assessment & Mitigation](#10-risk-assessment--mitigation)
11. [Success Criteria](#11-success-criteria)
12. [Appendices](#12-appendices)

---

## 1. Executive Summary

### 1.1 Background

ReelRecon began as a single-purpose MVP: scrape Instagram reels, transcribe audio, and generate AI script rewrites. As features were added (Skeleton Ripper, Asset Library), they were bolted on as separate pages with minimal integration, resulting in a fragmented user experience.

### 1.2 Problem Statement

| Issue | Impact |
|-------|--------|
| **Feature Silos** | Skeleton Ripper and Library feel like separate applications |
| **Disconnected Navigation** | Users must mentally context-switch between features |
| **Underutilized Library** | Powerful asset system exists but isn't central to workflow |
| **Visual Fatigue** | "Tactical" green theme is overwhelming for daily use |
| **Readability Issues** | Small text hard to read at low brightness |
| **Missing Features** | No date-range filtering, incomplete caption capture |

### 1.3 Solution Overview

Transform ReelRecon from a "feature collection" into an **integrated workspace** where:

- The **Library** becomes the central hub
- **Scraping** and **Skeleton Ripper** are actions launched from the library
- Results flow back into the library automatically
- Visual design prioritizes readability and professional aesthetics

### 1.4 Version Scope

| Version | Focus |
|---------|-------|
| **v3.0.0** | Architecture overhaul, unified workspace, visual redesign |
| v3.1.0 | Date-range filtering, enhanced search |
| v3.2.0 | Additional UX refinements based on user feedback |

---

## 2. Current State Analysis

### 2.1 Application Statistics

| Metric | Value |
|--------|-------|
| Current Version | 2.2.0 |
| app.py Lines | ~1,850 |
| Total Template Lines | 7,379 |
| CSS Lines | ~2,100 |
| JavaScript Lines | ~4,000 |
| API Routes | 47 |
| Python Modules | 4 (scraper, skeleton_ripper, storage, utils) |

### 2.2 Current Route Structure

```
PAGE ROUTES (3 separate entry points):
/                    → index.html      (688 lines)  - Main scrape UI
/skeleton-ripper     → skeleton_ripper.html (3,171 lines) - Separate app
/library             → library.html    (3,520 lines) - Asset management

API ROUTES (47 endpoints):
├── Scraping (10 routes)
│   ├── POST   /api/scrape
│   ├── GET    /api/scrape/<id>/status
│   ├── POST   /api/scrape/<id>/abort
│   ├── GET    /api/history
│   ├── DELETE /api/history/<id>
│   ├── POST   /api/history/clear
│   ├── GET    /api/download/video/<id>/<shortcode>
│   ├── POST   /api/fetch/video/<id>/<shortcode>
│   ├── GET    /api/download/transcript/<id>/<shortcode>
│   └── POST   /api/transcribe/video
│
├── Skeleton Ripper (11 routes)
│   ├── GET    /api/skeleton-ripper/providers
│   ├── POST   /api/skeleton-ripper/start
│   ├── GET    /api/skeleton-ripper/status/<job_id>
│   ├── GET    /api/skeleton-ripper/report/<job_id>
│   ├── GET    /api/skeleton-ripper/report/<job_id>/json
│   ├── GET    /api/skeleton-ripper/history
│   ├── GET    /api/skeleton-ripper/history/<report_id>
│   ├── GET    /api/skeleton-ripper/history/<report_id>/json
│   ├── POST   /api/skeleton-ripper/video/<id>/<vid>/download
│   ├── GET    /api/skeleton-ripper/video/<id>/<vid>
│   └── GET    /api/skeleton-ripper/video/<id>/<vid>/status
│
├── Assets & Library (8 routes)
│   ├── POST   /api/assets
│   ├── POST   /api/assets/save-skeleton
│   ├── POST   /api/assets/save-transcript
│   ├── GET    /api/assets
│   ├── GET    /api/assets/<id>
│   ├── PUT    /api/assets/<id>
│   ├── DELETE /api/assets/<id>
│   └── GET    /api/assets/search
│
├── Collections (6 routes)
│   ├── POST   /api/collections
│   ├── GET    /api/collections
│   ├── GET    /api/collections/<id>
│   ├── PUT    /api/collections/<id>
│   ├── DELETE /api/collections/<id>
│   └── POST   /api/collections/<id>/assets
│
├── Configuration (8 routes)
│   ├── GET    /api/cookies/status
│   ├── GET    /api/settings
│   ├── POST   /api/settings
│   ├── GET    /api/version
│   ├── GET    /api/update/check
│   ├── POST   /api/update/install
│   ├── GET    /api/ollama/models
│   └── GET    /api/whisper/check/<model>
│
├── AI/Rewriting (3 routes)
│   ├── GET    /api/generate-prompt/<id>/<shortcode>
│   ├── POST   /api/rewrite
│   └── GET    /api/videos
│
└── Error Handling (2 routes)
    ├── GET    /api/errors/<error_code>
    └── GET    /api/errors/recent
```

### 2.3 Data Layer

#### 2.3.1 SQLite Database Schema

```sql
-- Location: state/reelrecon.db

assets (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,  -- 'skeleton_report', 'scrape_report', 'skeleton', 'transcript', 'synthesis'
    title TEXT,
    content_path TEXT,
    preview TEXT,
    metadata JSON,
    starred INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
)

collections (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    color TEXT DEFAULT '#6366f1',
    icon TEXT,
    created_at TEXT
)

asset_collections (
    asset_id TEXT,
    collection_id TEXT,
    added_at TEXT,
    PRIMARY KEY (asset_id, collection_id)
)

assets_fts (FTS5 virtual table for full-text search)
```

#### 2.3.2 File-Based Storage

```
output/
├── {username}/
│   ├── {shortcode}_full.mp4      # Downloaded video
│   ├── {shortcode}_audio.mp3     # Extracted audio
│   └── {shortcode}_transcript.txt # Transcript file

cache/
├── reel_data_{username}.json     # Scraped reel metadata
└── transcript_cache.json         # Cached transcripts

state/
├── reelrecon.db                  # SQLite database
├── active_scrapes.json           # In-progress job state
└── skeleton_jobs/
    └── {job_id}/
        ├── report.json           # Analysis results
        └── report.html           # Rendered report
```

### 2.4 Module Dependencies

```
app.py (Main Flask Application)
    ├── scraper/
    │   ├── core.py              # Instagram scraping, Whisper transcription
    │   └── tiktok.py            # TikTok scraping (parallel implementation)
    │
    ├── skeleton_ripper/
    │   ├── pipeline.py          # Main orchestration
    │   ├── extractor.py         # Video/transcript extraction
    │   ├── synthesizer.py       # Pattern synthesis
    │   ├── aggregator.py        # Cross-creator aggregation
    │   ├── llm_client.py        # AI provider abstraction
    │   ├── prompts.py           # LLM prompt templates
    │   └── cache.py             # Transcript caching
    │
    ├── storage/
    │   ├── database.py          # SQLite connection management
    │   ├── models.py            # Asset, Collection, AssetCollection
    │   └── migrate.py           # Data migration utilities
    │
    └── utils/
        ├── logger.py            # Structured logging
        ├── state_manager.py     # Persistent job state
        ├── retry.py             # Exponential backoff
        └── updater.py           # Auto-update functionality
```

### 2.5 Current UI/UX Pain Points

| Issue | Location | Severity |
|-------|----------|----------|
| Skeleton Ripper is isolated | Top-right button → separate page | High |
| Library not discoverable | Hidden in navigation | High |
| No unified job view | Scrapes vs Ripper jobs separate | Medium |
| Green everywhere | All UI elements green-tinted | Medium |
| Small text size | Labels, metadata, timestamps | Medium |
| Poor contrast | Secondary text on dark backgrounds | Medium |
| Caption truncation | Scraper limits to 200 chars | Low |
| No date filtering | Cannot filter by recency | Low |

### 2.6 Known Bugs

#### 2.6.1 Caption Truncation Bug

**Location:** `scraper/core.py`

```python
# Line 129
'caption': (item.get('caption', {}) or {}).get('text', '')[:200],

# Line 150
'caption': caption_match.group(1) if caption_match else '',

# Line 235
'caption': (media.get('caption', {}) or {}).get('text', '')[:200],
```

**Issue:** Captions are arbitrarily truncated to 200 characters. Instagram captions can be up to 2,200 characters.

**Fix:** Store full caption, truncate only for preview display.

---

## 3. Target State Design

### 3.1 Design Philosophy

```
FROM: Feature Collection (separate tools stitched together)
  TO: Integrated Workspace (unified experience with library at center)
```

**Core Principles:**

1. **Library-First** - Library is home base, not a side feature
2. **Actions in Context** - Start jobs from where you'll view results
3. **Visual Clarity** - Readability over style, accents over saturation
4. **Progressive Disclosure** - Simple by default, powerful when needed

### 3.2 Target Information Architecture

```
ReelRecon Workspace
│
├── [SIDEBAR - Always Visible]
│   ├── Logo/Brand
│   ├── Quick Actions
│   │   ├── + New Scrape
│   │   └── + New Analysis (Skeleton Ripper)
│   ├── Navigation
│   │   ├── Library (Home)
│   │   ├── Active Jobs
│   │   └── Settings
│   └── Collections (Dynamic)
│       ├── All Assets
│       ├── Starred
│       └── [User Collections...]
│
├── [MAIN CONTENT AREA]
│   ├── Library View (Default)
│   │   ├── Search Bar
│   │   ├── Filter Chips (Type, Date, Tags)
│   │   ├── Asset Grid/List
│   │   └── Asset Detail Panel (Slideout)
│   │
│   ├── Active Jobs View
│   │   ├── Running Jobs (Scrapes + Ripper)
│   │   ├── Recent Completed
│   │   └── Job Detail (Expandable)
│   │
│   └── Settings View
│       ├── AI Providers
│       ├── Cookies Status
│       ├── Output Directory
│       └── Updates
│
└── [MODALS - Overlay Actions]
    ├── New Scrape Modal
    │   ├── Username Input
    │   ├── Parameters (count, date range)
    │   └── Platform Toggle (IG/TikTok)
    │
    ├── New Analysis Modal (Skeleton Ripper)
    │   ├── Creator Input (up to 5)
    │   ├── Videos per Creator
    │   ├── LLM Provider Selection
    │   └── Advanced Options
    │
    └── Asset Detail Modal
        ├── Full Content View
        ├── Rewrite Actions
        ├── Collection Management
        └── Export Options
```

### 3.3 Target Route Structure

```
PAGE ROUTES (Single Entry Point):
/                    → workspace.html (Unified SPA-like experience)

LEGACY ROUTES (Redirect for backwards compatibility):
/skeleton-ripper     → Redirect to / with ?view=analysis
/library             → Redirect to / with ?view=library

API ROUTES (Unchanged, add new):
├── Existing routes preserved
└── NEW routes:
    ├── GET  /api/jobs/active      # Unified active jobs (scrapes + ripper)
    ├── GET  /api/jobs/recent      # Recent completed jobs
    └── GET  /api/stats/dashboard  # Quick stats for workspace
```

### 3.4 Target Visual Design

#### 3.4.1 Color System Overhaul

```css
/* FROM: Heavy green saturation */
:root {
    --color-accent-primary: #10B981;  /* Used EVERYWHERE */
}

/* TO: Neutral base with green accents */
:root {
    /* Backgrounds - Warmer, less harsh */
    --color-bg-deep: #09090B;       /* Zinc-950 */
    --color-bg-base: #18181B;       /* Zinc-900 */
    --color-bg-elevated: #27272A;   /* Zinc-800 */
    --color-bg-panel: #3F3F46;      /* Zinc-700 */
    --color-bg-input: #27272A;

    /* Accent - Green reserved for actions/success */
    --color-accent-primary: #10B981;    /* Emerald - buttons, links */
    --color-accent-hover: #059669;      /* Darker on hover */
    --color-accent-subtle: rgba(16, 185, 129, 0.1);

    /* Text - Better contrast */
    --color-text-primary: #FAFAFA;      /* Zinc-50 */
    --color-text-secondary: #A1A1AA;    /* Zinc-400 */
    --color-text-muted: #71717A;        /* Zinc-500 */
    --color-text-accent: #34D399;       /* Emerald-400 */

    /* Borders - Subtle, not green */
    --color-border: #3F3F46;            /* Zinc-700 */
    --color-border-subtle: #27272A;     /* Zinc-800 */

    /* Semantic */
    --color-success: #10B981;
    --color-warning: #F59E0B;
    --color-danger: #EF4444;
    --color-info: #3B82F6;
}
```

#### 3.4.2 Typography Improvements

```css
/* FROM */
body { font-family: var(--font-mono); }  /* Everything monospace */
font-size: 0.75rem;  /* Too small */

/* TO */
body { font-family: var(--font-body); }  /* Sans-serif for UI */
code, .mono { font-family: var(--font-mono); }  /* Mono for data */

/* Font scale */
--text-xs: 0.75rem;     /* 12px - timestamps, metadata */
--text-sm: 0.875rem;    /* 14px - secondary text */
--text-base: 1rem;      /* 16px - body text */
--text-lg: 1.125rem;    /* 18px - subheadings */
--text-xl: 1.25rem;     /* 20px - headings */
--text-2xl: 1.5rem;     /* 24px - page titles */
```

#### 3.4.3 Remove Visual Noise

- **Remove:** Scan-line overlay effect
- **Remove:** Corner HUD brackets
- **Remove:** Excessive glow effects
- **Keep:** Clean dark theme with subtle elevation
- **Add:** Focus states for accessibility
- **Add:** Consistent spacing scale

### 3.5 Component Architecture

```
components/
├── layout/
│   ├── Sidebar.js
│   ├── MainContent.js
│   ├── Header.js
│   └── Modal.js
│
├── library/
│   ├── AssetGrid.js
│   ├── AssetCard.js
│   ├── AssetDetail.js
│   ├── SearchBar.js
│   ├── FilterChips.js
│   └── CollectionList.js
│
├── jobs/
│   ├── JobList.js
│   ├── JobCard.js
│   ├── JobProgress.js
│   └── JobDetail.js
│
├── actions/
│   ├── NewScrapeModal.js
│   ├── NewAnalysisModal.js
│   ├── RewritePanel.js
│   └── SaveCollectModal.js (existing)
│
└── shared/
    ├── Button.js
    ├── Input.js
    ├── Select.js
    ├── Badge.js
    ├── Spinner.js
    └── Toast.js
```

---

## 4. Scope of Work

### 4.1 In Scope

#### 4.1.1 UX/Architecture Overhaul

| Item | Description | Priority |
|------|-------------|----------|
| Unified Template | Single workspace.html replacing 3 templates | P0 |
| Sidebar Navigation | Persistent nav with collections | P0 |
| Library as Home | Library view is default landing | P0 |
| Modal-based Actions | Scrape & Analysis via modals, not pages | P0 |
| Active Jobs View | Unified job tracking (scrapes + ripper) | P0 |
| Route Consolidation | Single `/` with client-side routing | P1 |
| Legacy Redirects | Backwards compat for old URLs | P1 |

#### 4.1.2 Visual Design Overhaul

| Item | Description | Priority |
|------|-------------|----------|
| Color System | Neutral base, green accents only | P0 |
| Typography | Larger text, better contrast | P0 |
| Remove Scan Lines | Eliminate CRT effect | P0 |
| Clean Aesthetics | Professional, not "hacker" | P0 |
| Consistent Spacing | 4px/8px grid system | P1 |
| Focus States | Keyboard accessibility | P1 |

#### 4.1.3 Bug Fixes

| Bug | Description | Priority |
|-----|-------------|----------|
| Caption Truncation | Store full captions, truncate only in preview | P0 |
| Auto-hide Errors | Errors should require manual dismissal | P2 |

#### 4.1.4 New Features

| Feature | Description | Priority |
|---------|-------------|----------|
| Date Range Filter | Filter scrapes by 30/60/90 days | P1 |
| Unified Search | Search across all asset types | P1 |
| Quick Stats | Dashboard metrics in sidebar | P2 |

### 4.2 Out of Scope (Future Releases)

- TikTok feature parity (separate track)
- Mobile responsive design
- User accounts / multi-tenancy
- Cloud sync / backup
- New AI provider integrations
- Browser extension integration

### 4.3 Deliverables

1. **Code Changes**
   - New `templates/workspace.html` (unified template)
   - Updated `static/css/tactical.css` → `static/css/workspace.css`
   - New `static/js/workspace.js` (client-side routing)
   - Updated `app.py` (new routes, redirects)
   - Fixed `scraper/core.py` (caption bug)

2. **Documentation**
   - Updated README.md
   - Architecture decision record
   - Component documentation

3. **Testing**
   - Manual test checklist
   - Regression test for existing features

---

## 5. Technical Architecture

### 5.1 Frontend Architecture

#### 5.1.1 Current (Monolithic Templates)

```
templates/
├── index.html          # 688 lines, inline JS
├── library.html        # 3,520 lines, inline JS
└── skeleton_ripper.html # 3,171 lines, inline JS

static/js/
├── app.js              # 4,000+ lines, global state
└── save_collect.js     # Modal component
```

**Problems:**
- Massive duplication across templates
- No code sharing between pages
- Global state management
- Hard to maintain

#### 5.1.2 Target (Component-Based)

```
templates/
└── workspace.html      # Shell template only (~200 lines)

static/js/
├── workspace.js        # Main entry, router
├── state/
│   └── store.js        # Centralized state
├── components/
│   ├── layout/         # Sidebar, Header, Modal
│   ├── library/        # Asset views
│   ├── jobs/           # Job tracking
│   └── actions/        # Scrape, Analysis modals
└── utils/
    ├── api.js          # API client
    └── router.js       # Client-side routing

static/css/
└── workspace.css       # Consolidated styles
```

### 5.2 Client-Side Routing

```javascript
// Simple hash-based routing (no build step required)
const routes = {
    '':           () => showLibraryView(),
    'library':    () => showLibraryView(),
    'jobs':       () => showJobsView(),
    'settings':   () => showSettingsView(),
    'asset/:id':  (id) => showAssetDetail(id),
};

window.addEventListener('hashchange', handleRoute);
```

### 5.3 State Management

```javascript
// Lightweight reactive store
const Store = {
    state: {
        assets: [],
        collections: [],
        activeJobs: [],
        filters: { type: null, collection: null, search: '' },
        ui: { modal: null, sidebarCollapsed: false }
    },

    subscribe(listener) { /* ... */ },
    dispatch(action) { /* ... */ }
};
```

### 5.4 API Client

```javascript
// Unified API client
const API = {
    // Assets
    getAssets: (filters) => fetch('/api/assets?' + params(filters)),
    getAsset: (id) => fetch(`/api/assets/${id}`),
    searchAssets: (query) => fetch(`/api/assets/search?q=${query}`),

    // Jobs (unified)
    getActiveJobs: () => fetch('/api/jobs/active'),
    getRecentJobs: () => fetch('/api/jobs/recent'),

    // Actions
    startScrape: (data) => fetch('/api/scrape', { method: 'POST', body: data }),
    startAnalysis: (data) => fetch('/api/skeleton-ripper/start', { method: 'POST', body: data }),

    // Existing endpoints preserved...
};
```

### 5.5 New Backend Routes

```python
# Add to app.py

@app.route('/api/jobs/active')
def get_active_jobs():
    """Unified active jobs from both scrapes and skeleton ripper."""
    scrape_jobs = [...]  # From active_scrapes
    ripper_jobs = [...]  # From skeleton ripper state
    return jsonify({
        'scrapes': scrape_jobs,
        'analyses': ripper_jobs,
        'total': len(scrape_jobs) + len(ripper_jobs)
    })

@app.route('/api/jobs/recent')
def get_recent_jobs():
    """Recent completed jobs from both sources."""
    # Query from history + skeleton reports
    pass

@app.route('/api/stats/dashboard')
def get_dashboard_stats():
    """Quick stats for workspace sidebar."""
    return jsonify({
        'total_assets': Asset.count(),
        'total_collections': Collection.count(),
        'recent_scrapes': len(load_history()[-10:]),
        'active_jobs': len(active_scrapes)
    })
```

---

## 6. Implementation Phases

### Phase 0: Setup & Foundation (Day 1)

**Goal:** Branch setup, preserve current state, establish new file structure

**Tasks:**
1. Create feature branch `feature/v3-workspace-overhaul`
2. Tag current develop as `v2.2.0-stable` for rollback
3. Create new file structure:
   ```
   static/css/workspace.css    (copy of tactical.css to start)
   static/js/workspace.js      (new)
   static/js/state/store.js    (new)
   static/js/utils/api.js      (new)
   static/js/utils/router.js   (new)
   templates/workspace.html    (new shell)
   ```
4. Add new route `/workspace` (parallel development)

**Exit Criteria:**
- [ ] Feature branch created
- [ ] New files in place
- [ ] `/workspace` route serves basic shell

---

### Phase 1: Design System & Layout (Days 2-3)

**Goal:** New color system, typography, sidebar layout

**Tasks:**
1. Update CSS variables (color system overhaul)
2. Remove scan-line effect
3. Update typography scale
4. Build sidebar component
5. Build main content container
6. Implement basic client-side routing

**Exit Criteria:**
- [ ] New color palette active
- [ ] Sidebar with navigation working
- [ ] Hash-based routing functional
- [ ] Views switch without page reload

---

### Phase 2: Library View (Days 4-6)

**Goal:** Library becomes the central hub

**Tasks:**
1. Build asset grid/list component
2. Build filter chips (type, date, collection)
3. Build search bar with debounced search
4. Build asset card component
5. Build asset detail slideout panel
6. Implement collection filtering
7. Add new API endpoints for unified queries

**Exit Criteria:**
- [ ] Assets display in grid/list
- [ ] Filtering by type works
- [ ] Search returns results
- [ ] Collection filter works
- [ ] Asset detail opens in panel

---

### Phase 3: Actions & Modals (Days 7-9)

**Goal:** Scrape and Analysis actions work from modals

**Tasks:**
1. Build modal container component
2. Build New Scrape modal
   - Username input
   - Count selector
   - Date range filter (new feature)
   - Platform toggle (Instagram/TikTok)
3. Build New Analysis modal (Skeleton Ripper)
   - Multi-creator input
   - Videos per creator
   - LLM provider selection
4. Connect modals to existing API endpoints
5. Show job started → navigate to jobs view

**Exit Criteria:**
- [ ] New Scrape modal works end-to-end
- [ ] New Analysis modal works end-to-end
- [ ] Jobs start and progress shows
- [ ] Results appear in library when done

---

### Phase 4: Jobs View (Days 10-11)

**Goal:** Unified view of active and recent jobs

**Tasks:**
1. Build jobs list component
2. Build job card (with progress for active)
3. Add `/api/jobs/active` endpoint
4. Add `/api/jobs/recent` endpoint
5. Implement job detail expansion
6. Connect to existing status polling

**Exit Criteria:**
- [ ] Active jobs (both types) show
- [ ] Progress updates in real-time
- [ ] Completed jobs show in recent
- [ ] Can click through to results

---

### Phase 5: Integration & Polish (Days 12-14)

**Goal:** Connect everything, fix edge cases, polish

**Tasks:**
1. Port rewrite functionality to new UI
2. Port video playback
3. Integrate save/collect modal
4. Add settings view
5. Fix caption truncation bug
6. Add loading states everywhere
7. Add error handling/toasts
8. Add keyboard shortcuts
9. Clean up legacy code

**Exit Criteria:**
- [ ] All existing features work in new UI
- [ ] Caption bug fixed
- [ ] Errors display correctly
- [ ] Loading states smooth

---

### Phase 6: Migration & Cutover (Days 15-16)

**Goal:** Swap new UI to be default, redirect legacy routes

**Tasks:**
1. Move `/workspace` to `/`
2. Add redirects for `/skeleton-ripper`, `/library`
3. Update README documentation
4. Create migration notes
5. Test upgrade from v2.2.0
6. Final regression testing

**Exit Criteria:**
- [ ] `/` serves new workspace
- [ ] Old URLs redirect correctly
- [ ] All features pass testing
- [ ] Documentation updated

---

## 7. Git Workflow & Release Strategy

### 7.1 Branching Strategy

```
main                    (production releases)
  │
  └── develop           (integration branch)
        │
        └── feature/v3-workspace-overhaul
              │
              ├── feat/phase-1-design-system
              ├── feat/phase-2-library-view
              ├── feat/phase-3-modals
              ├── feat/phase-4-jobs
              └── feat/phase-5-polish
```

### 7.2 Commit Convention

```
<type>(<scope>): <subject>

Types:
- feat:     New feature
- fix:      Bug fix
- refactor: Code restructuring
- style:    CSS/visual changes
- docs:     Documentation
- chore:    Build, config changes

Examples:
feat(ui): add sidebar navigation component
fix(scraper): store full caption without truncation
style(css): implement new color system
refactor(js): extract API client module
```

### 7.3 Pull Request Process

1. **Phase Sub-branches** merge into `feature/v3-workspace-overhaul`
2. **Feature Branch** merges into `develop` when complete
3. **Develop** merges into `main` for release

### 7.4 Version Tagging

```bash
# Pre-release tags during development
git tag -a v3.0.0-alpha.1 -m "Phase 1: Design system complete"
git tag -a v3.0.0-alpha.2 -m "Phase 2: Library view complete"
git tag -a v3.0.0-beta.1 -m "All features complete, testing"

# Release tag
git tag -a v3.0.0 -m "v3.0.0: Unified Workspace Release"
```

### 7.5 Release Process

1. **Alpha Testing** (feature branch)
   - Developer testing after each phase
   - Fix issues before merging phases

2. **Beta Testing** (develop branch)
   - Merge feature branch to develop
   - Tester(s) validate all functionality
   - Collect feedback, create issues

3. **Release Candidate** (develop branch)
   - All issues resolved
   - Final regression pass
   - Documentation complete

4. **Production Release** (main branch)
   - Create PR: develop → main
   - Squash merge with release notes
   - Tag release
   - Update VERSION file

---

## 8. Migration & Data Preservation

### 8.1 Data Compatibility

| Data Type | Location | Migration Needed |
|-----------|----------|------------------|
| SQLite Database | `state/reelrecon.db` | None (schema unchanged) |
| Scrape History | `scrape_history.json` | None (format unchanged) |
| Output Files | `output/` | None |
| Skeleton Reports | `state/skeleton_jobs/` | None |
| Configuration | `config.json` | None |
| Cookies | `cookies.txt` | None |

**Conclusion:** No data migration required. All existing data works with new UI.

### 8.2 URL Compatibility

```python
# Legacy URL redirects in app.py

@app.route('/skeleton-ripper')
def legacy_skeleton_ripper():
    return redirect('/#/jobs?start=analysis')

@app.route('/library')
def legacy_library():
    return redirect('/')
```

### 8.3 Rollback Procedure

If critical issues discovered post-release:

```bash
# 1. Checkout previous stable version
git checkout v2.2.0

# 2. Deploy/run previous version
python app.py

# 3. Document issues for resolution
# 4. Fix in feature branch
# 5. Re-release when ready
```

---

## 9. Testing Strategy

### 9.1 Test Categories

| Category | Scope | Approach |
|----------|-------|----------|
| Smoke Test | Critical paths work | Manual, each phase |
| Regression | Existing features | Manual checklist |
| Visual | UI renders correctly | Manual, screenshot compare |
| Functional | Features work as designed | Manual per requirement |

### 9.2 Regression Test Checklist

```markdown
## Core Scraping
- [ ] Can enter username and start scrape
- [ ] Progress updates during scrape
- [ ] Results display with transcripts
- [ ] Can download video
- [ ] Can play video in UI
- [ ] Transcript displays correctly
- [ ] Full caption displays (bug fix)

## AI Rewrite
- [ ] Can open rewrite panel
- [ ] Guided wizard works
- [ ] Quick rewrite works
- [ ] Each AI provider works (OpenAI, Anthropic, Google, Ollama)
- [ ] Copy-only mode works

## Skeleton Ripper
- [ ] Can enter multiple creators
- [ ] Job starts and shows progress
- [ ] Report generates successfully
- [ ] Can view report
- [ ] Can save skeletons to library

## Library/Assets
- [ ] Assets list displays
- [ ] Can filter by type
- [ ] Can search assets
- [ ] Can create collection
- [ ] Can add asset to collection
- [ ] Can star/unstar assets
- [ ] Can delete assets

## Settings
- [ ] Can update AI provider
- [ ] Can enter API keys
- [ ] Keys persist after restart
- [ ] Cookies status shows correctly

## System
- [ ] App starts without errors
- [ ] State persists across restarts
- [ ] Logs write correctly
- [ ] Update check works
```

### 9.3 Visual Testing

Compare screenshots between:
- v2.2.0 stable
- v3.0.0 workspace

Verify:
- All text readable
- Sufficient contrast
- Consistent spacing
- No visual regressions

---

## 10. Risk Assessment & Mitigation

### 10.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking existing features | Medium | High | Comprehensive regression testing |
| Data loss during migration | Low | Critical | No schema changes, rollback procedure |
| Browser compatibility issues | Low | Medium | Test Chrome, Firefox, Safari |
| Performance degradation | Low | Medium | Monitor load times, optimize if needed |
| CSS conflicts | Medium | Low | Namespace new styles, gradual migration |

### 10.2 Schedule Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Scope creep | High | Medium | Strict phase boundaries, defer to v3.1 |
| Underestimated complexity | Medium | Medium | Buffer time in Phase 5 |
| Integration issues | Medium | Medium | Frequent integration testing |

### 10.3 User Impact Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Learning curve for new UI | High | Low | Familiar patterns, good defaults |
| Missing feature | Medium | High | Full regression checklist |
| User preference for old UI | Low | Low | Cannot support both long-term |

---

## 11. Success Criteria

### 11.1 Functional Success

- [ ] All existing features work in new UI
- [ ] Library is default landing page
- [ ] Scrape and Analysis launch from modals
- [ ] Jobs show unified progress
- [ ] Full captions captured and displayed

### 11.2 UX Success

- [ ] User can accomplish primary task (scrape → rewrite) without page navigation
- [ ] All features discoverable from sidebar
- [ ] Results flow into library automatically

### 11.3 Visual Success

- [ ] Text readable at 50% brightness
- [ ] Green used as accent only (not dominant)
- [ ] Professional appearance
- [ ] No visual regressions

### 11.4 Technical Success

- [ ] No data loss during upgrade
- [ ] Legacy URLs redirect correctly
- [ ] Page load time ≤ 2 seconds
- [ ] No JavaScript errors in console

---

## 12. Appendices

### Appendix A: File Inventory

**Files to Create:**
```
templates/workspace.html
static/css/workspace.css
static/js/workspace.js
static/js/state/store.js
static/js/utils/api.js
static/js/utils/router.js
static/js/components/layout/Sidebar.js
static/js/components/layout/Modal.js
static/js/components/library/AssetGrid.js
static/js/components/library/AssetCard.js
static/js/components/library/AssetDetail.js
static/js/components/jobs/JobList.js
static/js/components/jobs/JobCard.js
static/js/components/actions/NewScrapeModal.js
static/js/components/actions/NewAnalysisModal.js
```

**Files to Modify:**
```
app.py                    # Add new routes, redirects
scraper/core.py           # Fix caption truncation
static/css/tactical.css   # Phase out (optional keep for reference)
VERSION                   # Update to 3.0.0
README.md                 # Update documentation
```

**Files to Deprecate (Keep for Reference):**
```
templates/index.html          # Replaced by workspace.html
templates/library.html        # Merged into workspace.html
templates/skeleton_ripper.html # Merged into workspace.html
static/js/app.js              # Replaced by workspace.js modules
```

### Appendix B: API Endpoint Summary

**New Endpoints:**
```
GET  /api/jobs/active       # Unified active jobs
GET  /api/jobs/recent       # Recent completed jobs
GET  /api/stats/dashboard   # Sidebar stats
```

**Modified Behavior:**
```
GET  /                      # Now serves workspace.html
GET  /skeleton-ripper       # Redirects to /#/jobs?start=analysis
GET  /library               # Redirects to /
```

### Appendix C: Color Palette Reference

**Current (v2.x):**
```
Background: #060A0E, #080C12, #0C1218, #101820
Accent: #10B981 (everywhere)
Text: #E5E7EB, #9CA3AF, #6B7280
Border: rgba(16, 185, 129, 0.2)
```

**Target (v3.0):**
```
Background: #09090B, #18181B, #27272A, #3F3F46 (Zinc scale)
Accent: #10B981 (actions only), #059669 (hover)
Text: #FAFAFA, #A1A1AA, #71717A (better contrast)
Border: #3F3F46 (neutral, not green)
```

### Appendix D: Tester Feedback Reference

> **Dhaniyal Ansari (Dec 25):**
> 1. the text could be more clear if you have the brightness turned down a bit its hard to read the field titles or the smaller text
> 2. i also feel like theres too much green
> 3. It doesnt capture the entire caption from the instagram videos
> 4. would be nice to have a dates/range feature where we only pull vids from the last 90 days, 30 days etc

**Response in This Spec:**
1. Typography overhaul (Section 3.4.2)
2. Color system overhaul (Section 3.4.1)
3. Caption bug fix (Section 4.1.3)
4. Date range filter (Section 4.1.4)

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Dec 31, 2024 | Claude + Chris | Initial specification |

---

*End of Specification*
