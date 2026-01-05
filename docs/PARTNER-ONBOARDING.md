# ReelRecon Partner Developer Onboarding Guide

**Welcome to the ReelRecon development team!**

This document will get you up to speed on the codebase, development workflow, and how to collaborate effectively using Claude Code.

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Project Overview](#2-project-overview)
3. [Codebase Architecture](#3-codebase-architecture)
4. [Development Workflow](#4-development-workflow)
5. [Your Assigned Work: Phase 5](#5-your-assigned-work-phase-5)
6. [Claude Code Setup](#6-claude-code-setup)
7. [Communication Protocol](#7-communication-protocol)
8. [Common Gotchas](#8-common-gotchas)
9. [Quick Reference](#9-quick-reference)

---

## 1. Quick Start

### Clone and Setup

```bash
# Clone the repository
git clone git@github.com:ChristopherKahler/ReelRecon.git
cd ReelRecon

# Switch to the active development branch
git checkout feature/v3-workspace-overhaul

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
# Opens at http://localhost:5001
```

### Essential Reading (In Order)

Before writing ANY code, read these documents:

| Priority | Document | Purpose | Time |
|----------|----------|---------|------|
| 1 | `CLAUDE.md` | Quick reference for Claude Code | 5 min |
| 2 | `docs/ARCHITECTURE-AUDIT.md` | **THE BIBLE** - Everything about the codebase | 30 min |
| 3 | `docs/V3-OVERHAUL-SPEC.md` | V3 design decisions and architecture | 20 min |
| 4 | `docs/V3-TASK-TRACKER.md` | Current task status and your assignments | 10 min |
| 5 | `docs/CHANGELOG-2026-01-03.md` | Most recent changes | 5 min |

**Total onboarding read time: ~70 minutes**

---

## 2. Project Overview

### What Is ReelRecon?

ReelRecon is an Instagram/TikTok content intelligence platform for content creators and marketers. It helps users:

1. **Scrape** top-performing reels from any creator
2. **Transcribe** video audio using Whisper
3. **Analyze** content patterns across multiple creators (Skeleton Ripper)
4. **Generate** AI-powered script rewrites based on viral patterns

### Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.8+ / Flask |
| Database | SQLite (state/reelrecon.db) |
| Frontend | Vanilla JavaScript / CSS |
| Transcription | OpenAI Whisper (local or API) |
| LLM | OpenAI, Anthropic, Google, Ollama |
| Desktop | PyWebView + pystray (system tray) |

### Current Version Status

- **Stable**: v2.2.0 (on `main` branch)
- **In Development**: v3.0.0 (on `feature/v3-workspace-overhaul`)
- **Your Work**: Phase 5 of the V3 overhaul

---

## 3. Codebase Architecture

### Directory Structure

```
ReelRecon/
├── app.py                 # Flask server (3,082 lines, 60+ routes)
├── CLAUDE.md              # Claude Code context file
├── config.json            # User settings (gitignored)
├── cookies.txt            # Instagram auth (gitignored)
│
├── scraper/               # Instagram/TikTok scraping
│   ├── core.py            # Main scraping logic (970 lines)
│   └── tiktok.py          # TikTok-specific (470 lines)
│
├── skeleton_ripper/       # Content pattern analysis
│   ├── pipeline.py        # 5-stage orchestration (794 lines)
│   ├── extractor.py       # Skeleton extraction
│   ├── synthesizer.py     # Pattern synthesis
│   ├── llm_client.py      # Multi-provider LLM client
│   └── prompts.py         # LLM prompt templates
│
├── storage/               # Database layer
│   ├── models.py          # Asset, Collection ORM
│   └── database.py        # SQLite connection
│
├── utils/                 # Utilities
│   ├── state_manager.py   # Job state persistence
│   ├── logger.py          # Structured logging
│   └── retry.py           # Exponential backoff
│
├── static/
│   ├── js/
│   │   ├── workspace.js   # V3 frontend (2,178 lines) <- YOUR FOCUS
│   │   ├── utils/api.js   # API client
│   │   └── utils/router.js # Client-side routing
│   └── css/
│       └── workspace.css  # V3 styles <- YOUR FOCUS
│
├── templates/
│   └── workspace.html     # V3 unified template
│
├── state/                 # Persistent state
│   ├── reelrecon.db       # SQLite database
│   └── active_scrapes.json # Job queue
│
├── output/                # Scraped content (gitignored)
│
└── docs/                  # Documentation
    ├── ARCHITECTURE-AUDIT.md  # Single source of truth
    ├── V3-OVERHAUL-SPEC.md    # V3 specification
    ├── V3-TASK-TRACKER.md     # Task checkboxes
    └── CHANGELOG-*.md         # Change history
```

### Data Flow

```
User Action → workspace.js → API (app.py) → Module (scraper/skeleton_ripper)
                                        ↓
                               state_manager (job tracking)
                                        ↓
                               Asset.create() → SQLite
                                        ↓
                               output/ (files)
```

### The Golden Rules

**NEVER violate these patterns:**

| Need | USE THIS | NOT THIS |
|------|----------|----------|
| Save an asset | `Asset.create()` | Custom file writes |
| Track jobs | `state_manager` | Custom JSON |
| Call LLM | `LLMClient` | Direct API calls |
| Log errors | `logger` | print() |
| Retry network | `retry_with_backoff()` | Custom loops |

---

## 4. Development Workflow

### Git Workflow

We use a modified Git Flow:

```
main                    ← Production (don't touch)
  │
  └── develop           ← Integration (don't touch directly)
        │
        └── feature/v3-workspace-overhaul  ← Our working branch
```

**Your workflow:**

```bash
# 1. Always pull latest before starting work
git pull origin feature/v3-workspace-overhaul

# 2. Make your changes

# 3. Commit with conventional format
git add -A
git commit -m "feat(ui): add loading spinner component"

# 4. Push to shared branch
git push origin feature/v3-workspace-overhaul
```

### Commit Convention

```
<type>(<scope>): <subject>

Types:
- feat:     New feature
- fix:      Bug fix
- refactor: Code restructuring
- style:    CSS/visual changes
- docs:     Documentation
- chore:    Build, config

Examples:
- feat(ui): add keyboard shortcuts
- fix(jobs): handle empty job list
- style(css): improve loading spinner animation
```

### Before/After Each Session

**Starting a session:**
1. `git pull origin feature/v3-workspace-overhaul`
2. Read `docs/V3-TASK-TRACKER.md` Quick Status section
3. Check if Chris updated anything in the changelog
4. Find your next unchecked task

**Ending a session:**
1. Commit all work
2. Update task checkboxes in `docs/V3-TASK-TRACKER.md`
3. If significant changes, add entry to `docs/CHANGELOG-YYYY-MM-DD.md`
4. Push to remote
5. Message Chris about what you completed

---

## 5. Your Assigned Work: Phase 5

### Phase 5 Overview

**Goal**: Integration & Polish - Connect everything, fix edge cases, improve UX

**Files you'll primarily touch:**
- `static/js/workspace.js` (UI logic)
- `static/css/workspace.css` (styling)
- `templates/workspace.html` (HTML structure)

### Your Tasks

From `docs/V3-TASK-TRACKER.md`:

#### Port Existing Features
- [ ] 5.1 Port rewrite panel to asset detail view
- [ ] 5.2 Port video playback to asset detail
- [ ] 5.3 Integrate save/collect modal (already exists)
- [ ] 5.4 Port settings view from existing code
- [ ] 5.5 Test all ported features

#### Loading States
- [ ] 5.9 Add loading spinner component
- [ ] 5.10 Add skeleton loaders for asset grid
- [ ] 5.11 Add loading state for search
- [ ] 5.12 Add loading state for job actions
- [ ] 5.13 Test all loading states

#### Error Handling
- [ ] 5.14 Create Toast/notification component
- [ ] 5.15 Add error toast for API failures
- [ ] 5.16 Add success toast for completed actions
- [ ] 5.17 Handle network offline state
- [ ] 5.18 Test error scenarios

#### Keyboard Shortcuts
- [ ] 5.19 Escape closes modals (done in Phase 3)
- [ ] 5.20 `/` focuses search
- [ ] 5.21 `n` opens new scrape modal
- [ ] 5.22 Document shortcuts

#### Final Polish
- [ ] 5.23 Audit all transitions/animations
- [ ] 5.24 Verify consistent spacing
- [ ] 5.25 Check all text contrast
- [ ] 5.26 Test at 50% brightness
- [ ] 5.27 Fix any visual glitches

### Where to Find Reference Code

For porting features, look at the legacy files:

| Feature | Legacy Location | Port To |
|---------|-----------------|---------|
| Rewrite panel | `templates/index.html` | `workspace.js` |
| Video playback | `templates/library.html` | `workspace.js` |
| Settings view | `templates/index.html` | `workspace.js` |

---

## 6. Claude Code Setup

### Create Your Context

Claude Code will read `CLAUDE.md` automatically. For additional context, you can reference files:

```
# In your prompts to Claude, reference:
@docs/ARCHITECTURE-AUDIT.md
@docs/V3-TASK-TRACKER.md
```

### Effective Claude Code Usage

**DO:**
```
"Add a loading spinner to the asset grid. The spinner should match our design
system in workspace.css. Reference the existing .job-card loading pattern."
```

**DON'T:**
```
"Add a loading spinner." (too vague)
```

**Session Start Prompt:**
```
I'm working on ReelRecon Phase 5. Read CLAUDE.md and docs/V3-TASK-TRACKER.md.
My current task is [5.9 Add loading spinner component].
Show me the existing loading patterns first, then implement.
```

**Session End Prompt:**
```
I've completed [tasks]. Update docs/V3-TASK-TRACKER.md checkboxes for:
- 5.9 loading spinner
- 5.10 skeleton loaders
Then create a brief changelog entry.
```

---

## 7. Communication Protocol

### Coordination with Chris

Chris is working on **Phase 7 (Direct Reel Scraping)** which touches:
- `app.py` (backend endpoints)
- `scraper/core.py` (scraping logic)
- `static/js/workspace.js` (some job-related functions)

**Conflict zones** (check with Chris before editing):
- `app.py` (always coordinate)
- `workspace.js` functions: `startBatchScrape()`, `startDirectScrape()`, `pollActiveJobsOnce()`

**Safe zones** (work freely):
- CSS files
- UI components not related to scraping
- Loading states, toasts, keyboard shortcuts

### Communication Channels

- **Before starting work**: Post what files you'll touch
- **After completing work**: Post summary of changes
- **Questions**: Ask anytime, don't assume

### Daily Check-in Template

```
Starting work on: [task description]
Files I'll touch: [list]
ETA: [rough estimate]
Blockers: [any questions/issues]
```

---

## 8. Common Gotchas

### JavaScript Patterns

**State Management:**
```javascript
// Use the store for state
import { Store } from './state/store.js';
Store.dispatch({ type: 'SET_LOADING', payload: true });
```

**API Calls:**
```javascript
// Use the API client
import { API } from './utils/api.js';
const assets = await API.getAssets({ type: 'scrape_report' });
```

**DOM Updates:**
```javascript
// DON'T replace innerHTML during polling (causes flash)
list.innerHTML = newHTML; // BAD

// DO update specific elements
element.textContent = newValue; // GOOD
element.style.width = `${percent}%`; // GOOD
```

### CSS Patterns

**Variables to use:**
```css
/* Backgrounds */
--color-bg-deep: #09090B;
--color-bg-base: #18181B;
--color-bg-elevated: #27272A;

/* Accent (green for actions only) */
--color-accent-primary: #10B981;

/* Text */
--color-text-primary: #FAFAFA;
--color-text-secondary: #A1A1AA;
```

**Spacing scale:**
```css
/* Use 4px/8px grid */
padding: 8px;     /* or 0.5rem */
margin: 16px;     /* or 1rem */
gap: 12px;        /* or 0.75rem */
```

### Testing Changes

After ANY change:

1. Restart Flask server: `Ctrl+C` then `python app.py`
2. Hard refresh browser: `Ctrl+Shift+R` (clears cache)
3. Check browser console for JS errors
4. Check terminal for Python errors

---

## 9. Quick Reference

### Files You'll Edit Most

```
static/js/workspace.js     # UI logic
static/css/workspace.css   # Styles
templates/workspace.html   # HTML
docs/V3-TASK-TRACKER.md    # Progress tracking
```

### Common Commands

```bash
# Run app
python app.py

# Pull latest
git pull origin feature/v3-workspace-overhaul

# Commit
git add -A && git commit -m "feat(ui): description"

# Push
git push origin feature/v3-workspace-overhaul

# Check branch
git branch --show-current
```

### Key Functions in workspace.js

| Function | Purpose |
|----------|---------|
| `loadInitialData()` | Fetches assets, collections on page load |
| `renderAssetCard()` | Creates asset card HTML |
| `renderJobCard()` | Creates job card HTML |
| `openModal()` | Opens modal dialogs |
| `closeModal()` | Closes modal dialogs |
| `startJobsPolling()` | Starts progress polling |
| `showToast()` | Shows notifications (you'll create) |

### Support

- **Stuck?** Ask Chris or use Claude Code with good context
- **Bug?** Check `docs/ARCHITECTURE-AUDIT.md` Common Mistakes section
- **Confused?** Read the spec and tracker docs first

---

## Welcome Aboard!

You're joining at an exciting time - V3 is coming together and your work on Phase 5 will make the app feel polished and professional.

**First Steps:**
1. Clone the repo
2. Read `CLAUDE.md` and `docs/ARCHITECTURE-AUDIT.md`
3. Run the app and explore the UI
4. Pick task 5.9 (loading spinner) and start!

Questions? Don't hesitate to reach out.

---

*Last updated: 2026-01-04*
