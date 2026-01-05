# ReelRecon Refactoring Collaboration Guide

**Version**: 1.0
**Date**: 2026-01-04
**Participants**: Chris (Lead) + Partner
**Prerequisite**: V3 must ship first

---

## Overview

This document outlines how to divide the refactoring work between two developers. The goal is parallel execution with minimal merge conflicts and clear ownership.

### Why This Works for Two Developers

| Aspect | V3 Development | Refactoring |
|--------|----------------|-------------|
| Context Required | Deep (full app flow) | Moderate (isolated modules) |
| Risk of Conflicts | High | Low |
| Parallelization | Difficult | **Natural** |
| Onboarding Time | Long | Short per module |
| Deliverable Type | Features | Modules |

---

## Phase 0: Pre-Work (Do Together - 2 hours)

### 0.1 Kickoff Meeting Agenda

Before any code is written, meet to:

1. **Review REFACTORING-SPEC.md together** (30 min)
   - Walk through dependency graphs
   - Discuss extraction priorities
   - Clarify any questions

2. **Define service interfaces** (45 min)
   - Agree on method signatures
   - Agree on data types
   - Document in `services/interfaces.py`

3. **Assign ownership** (15 min)
   - Use the split defined in this document
   - Confirm comfort levels
   - Adjust if needed

4. **Set up coordination** (30 min)
   - Create feature branches
   - Set up communication channel
   - Schedule check-ins

### 0.2 Create Interface Contracts

Before splitting up, create this file together:

```python
# services/interfaces.py
"""
Service interface contracts for ReelRecon refactoring.
ALL services must implement these interfaces.
Do not modify without partner agreement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Callable
from enum import Enum


# ============================================================
# LLM SERVICE INTERFACE
# Owner: Partner
# ============================================================

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

class ILLMService(ABC):
    """Interface for LLM operations."""

    @abstractmethod
    def complete(self, prompt: str) -> str:
        """Send prompt to LLM, return response."""
        pass

    @abstractmethod
    def get_available_providers(self) -> list[dict]:
        """Return list of configured providers with models."""
        pass

    @abstractmethod
    def validate_api_key(self, provider: LLMProvider, api_key: str) -> bool:
        """Test if API key is valid for provider."""
        pass

    @staticmethod
    @abstractmethod
    def strip_thinking_tags(text: str) -> str:
        """Remove Claude thinking tags from response."""
        pass


# ============================================================
# CONFIG SERVICE INTERFACE
# Owner: Partner
# ============================================================

@dataclass
class AppConfig:
    ai_provider: str
    ai_model: str
    openai_key: Optional[str]
    anthropic_key: Optional[str]
    google_key: Optional[str]
    whisper_model: str
    detail_panel_width: int

class IConfigService(ABC):
    """Interface for configuration management."""

    @abstractmethod
    def load(self) -> AppConfig:
        """Load config from disk."""
        pass

    @abstractmethod
    def save(self, config: AppConfig) -> bool:
        """Save config to disk."""
        pass

    @abstractmethod
    def get(self, key: str, default=None):
        """Get single config value."""
        pass

    @abstractmethod
    def set(self, key: str, value) -> bool:
        """Set single config value and save."""
        pass


# ============================================================
# VIDEO SERVICE INTERFACE
# Owner: Partner
# ============================================================

from pathlib import Path

class IVideoService(ABC):
    """Interface for video operations."""

    @abstractmethod
    def download(self, url: str, output_path: Path, cookies_file: Optional[Path] = None) -> Path:
        """Download video from URL, return local path."""
        pass

    @abstractmethod
    def stream(self, video_path: Path):
        """Return file stream for video."""
        pass

    @abstractmethod
    def list_videos(self, username: Optional[str] = None) -> list[dict]:
        """List downloaded videos, optionally filtered by username."""
        pass

    @abstractmethod
    def delete(self, video_path: Path) -> bool:
        """Delete video file."""
        pass

    @abstractmethod
    def extract_audio(self, video_path: Path) -> Path:
        """Extract audio track from video."""
        pass


# ============================================================
# SCRAPE SERVICE INTERFACE
# Owner: Chris
# ============================================================

@dataclass
class ScrapeOptions:
    platform: str = "instagram"
    max_reels: int = 100
    top_n: int = 10
    download_video: bool = True
    transcribe: bool = True
    transcribe_provider: str = "local"  # 'local' or 'openai'
    whisper_model: str = "small.en"
    date_filter_days: Optional[int] = None

class IScrapeService(ABC):
    """Interface for scraping operations."""

    @abstractmethod
    def start_profile_scrape(
        self,
        username: str,
        options: ScrapeOptions,
        on_progress: Optional[Callable] = None
    ) -> str:
        """Start single profile scrape, return job_id."""
        pass

    @abstractmethod
    def start_batch_scrape(
        self,
        usernames: list[str],
        options: ScrapeOptions
    ) -> tuple[str, list[str]]:
        """Start batch scrape, return (batch_id, job_ids)."""
        pass

    @abstractmethod
    def start_direct_scrape(
        self,
        shortcodes: list[str],
        options: ScrapeOptions
    ) -> str:
        """Scrape specific reels, return job_id."""
        pass

    @abstractmethod
    def get_job_status(self, job_id: str) -> dict:
        """Get current job progress."""
        pass

    @abstractmethod
    def abort_job(self, job_id: str) -> bool:
        """Cancel running job."""
        pass


# ============================================================
# SKELETON SERVICE INTERFACE
# Owner: Chris
# ============================================================

@dataclass
class SkeletonConfig:
    usernames: list[str]
    videos_per_creator: int = 3
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"

class ISkeletonService(ABC):
    """Interface for skeleton ripper operations."""

    @abstractmethod
    def start_analysis(
        self,
        config: SkeletonConfig,
        on_progress: Optional[Callable] = None
    ) -> str:
        """Start skeleton analysis, return job_id."""
        pass

    @abstractmethod
    def get_job_status(self, job_id: str) -> dict:
        """Get analysis progress."""
        pass

    @abstractmethod
    def get_report(self, job_id: str) -> dict:
        """Get completed report data."""
        pass

    @abstractmethod
    def get_report_markdown(self, job_id: str) -> str:
        """Get report as markdown."""
        pass

    @abstractmethod
    def save_skeleton_as_asset(self, skeleton_data: dict, source_job_id: str) -> str:
        """Save individual skeleton to library, return asset_id."""
        pass
```

**Commit this together before splitting up.**

---

## Work Division

### Partner's Assignments

| Service | Priority | Complexity | Est. Time |
|---------|----------|------------|-----------|
| `config_service.py` | P2 | Low | 2-3 hours |
| `llm_service.py` | P0 | Medium | 4-6 hours |
| `video_service.py` | P2 | Medium | 3-4 hours |

**Total: ~10-13 hours**

#### Partner Task 1: Config Service

**Source**: `app.py` lines 105-124

**Extract these functions**:
- `load_config()` → `ConfigService.load()`
- `save_config()` → `ConfigService.save()`

**File to create**: `services/config_service.py`

```python
# services/config_service.py
"""Configuration management service."""

import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

from .interfaces import IConfigService, AppConfig

class ConfigService(IConfigService):
    """Manages application configuration."""

    def __init__(self, config_path: Path = None):
        self.config_path = config_path or Path(__file__).parent.parent / 'config.json'
        self._cache: Optional[AppConfig] = None

    def load(self) -> AppConfig:
        """Load config from disk."""
        if self._cache:
            return self._cache

        if not self.config_path.exists():
            return self._default_config()

        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
            self._cache = AppConfig(**data)
            return self._cache
        except Exception:
            return self._default_config()

    def save(self, config: AppConfig) -> bool:
        """Save config to disk."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(asdict(config), f, indent=2)
            self._cache = config
            return True
        except Exception:
            return False

    def get(self, key: str, default=None):
        """Get single config value."""
        config = self.load()
        return getattr(config, key, default)

    def set(self, key: str, value) -> bool:
        """Set single config value and save."""
        config = self.load()
        if hasattr(config, key):
            setattr(config, key, value)
            return self.save(config)
        return False

    def _default_config(self) -> AppConfig:
        return AppConfig(
            ai_provider='openai',
            ai_model='gpt-4o-mini',
            openai_key=None,
            anthropic_key=None,
            google_key=None,
            whisper_model='small.en',
            detail_panel_width=600
        )
```

**Testing checklist**:
- [ ] Load returns config from file
- [ ] Load returns defaults when file missing
- [ ] Save persists to disk
- [ ] Get retrieves single values
- [ ] Set updates and saves

---

#### Partner Task 2: LLM Service

**Source**: `app.py` lines 152-272

**Extract these functions**:
- `call_openai()` → `LLMService._call_openai()`
- `call_anthropic()` → `LLMService._call_anthropic()`
- `call_google()` → `LLMService._call_google()`
- `call_ollama()` → `LLMService._call_ollama()`
- `strip_thinking_output()` → `LLMService.strip_thinking_tags()`
- `generate_ai_prompt()` → Keep in app.py or move to prompts module

**File to create**: `services/llm_service.py`

**Key considerations**:
- Each provider has different error handling
- Ollama doesn't need API key
- Claude responses may have `<thinking>` tags to strip
- Should unify with `skeleton_ripper/llm_client.py` eventually

**Testing checklist**:
- [ ] OpenAI calls work with valid key
- [ ] Anthropic calls work with valid key
- [ ] Google calls work with valid key
- [ ] Ollama calls work (if installed locally)
- [ ] Invalid keys return appropriate errors
- [ ] Thinking tags stripped from Claude responses
- [ ] get_available_providers returns correct list

---

#### Partner Task 3: Video Service

**Source**:
- `scraper/core.py:download_video()` lines 334-431
- `app.py:stream_video()` line 2338
- `app.py:list_videos()` line 2232
- `app.py:delete_video()` line 2380

**File to create**: `services/video_service.py`

**Key considerations**:
- Download has two strategies: direct URL vs yt-dlp fallback
- Must use `sys.executable -m yt_dlp` for PATH safety
- Stream needs proper Content-Type headers
- Delete should clean up related files (audio, transcript)

**Testing checklist**:
- [ ] Download works with direct video URL
- [ ] Download works with Instagram reel URL (yt-dlp)
- [ ] Download works with TikTok URL
- [ ] Stream returns proper video response
- [ ] List returns all downloaded videos
- [ ] Delete removes video and related files

---

### Chris's Assignments

| Service | Priority | Complexity | Est. Time |
|---------|----------|------------|-----------|
| `scrape_service.py` | P1 | High | 6-8 hours |
| `skeleton_service.py` | P1 | High | 6-8 hours |
| Route blueprints | P2 | Medium | 4-6 hours |

**Total: ~16-22 hours**

#### Chris Task 1: Scrape Service

**Source**: `app.py` lines 794-1255

**Extract these**:
- `start_scrape()` route logic → `ScrapeService.start_profile_scrape()`
- `start_batch_scrape()` route logic → `ScrapeService.start_batch_scrape()`
- `start_direct_scrape()` route logic → `ScrapeService.start_direct_scrape()`
- Thread target logic → `ScrapeService._run_scrape()`

**Key considerations**:
- Keep `scraper/core.py` unchanged (low-level functions stay there)
- Service handles job creation, threading, state management
- Routes become thin wrappers
- Must integrate with `state_manager` for job tracking

---

#### Chris Task 2: Skeleton Service

**Source**: `app.py` lines 2450-2740

**Extract these**:
- `start_skeleton_ripper()` logic → `SkeletonService.start_analysis()`
- `active_skeleton_jobs` dict → Unified job manager
- `load_skeleton_jobs()` / `save_skeleton_jobs()` → Unified persistence

**Key considerations**:
- Should use same job tracking as scrape service (unify)
- Pipeline module (`skeleton_ripper/pipeline.py`) stays unchanged
- Service handles orchestration only

---

#### Chris Task 3: Route Blueprints

**After services are done**, split `app.py` routes into blueprints:

```
routes/
├── __init__.py
├── scrape.py         # /api/scrape/*
├── skeleton.py       # /api/skeleton-ripper/*
├── assets.py         # /api/assets/*
├── collections.py    # /api/collections/*
├── jobs.py           # /api/jobs/*
├── settings.py       # /api/settings, /api/version
└── pages.py          # HTML routes
```

---

## Timeline

### Week 1: Services (Parallel Work)

| Day | Partner | Chris |
|-----|---------|-------|
| Mon | Config service | Scrape service (start) |
| Tue | LLM service (start) | Scrape service (complete) |
| Wed | LLM service (complete) | Skeleton service (start) |
| Thu | Video service | Skeleton service (complete) |
| Fri | **Integration testing** | **Integration testing** |

### Week 2: Blueprints + Integration

| Day | Partner | Chris |
|-----|---------|-------|
| Mon | Code review partner services | Route blueprints (start) |
| Tue | Fix issues from review | Route blueprints (complete) |
| Wed | **Integration testing together** | **Integration testing together** |
| Thu | Bug fixes | Bug fixes |
| Fri | **Release v3.1.0** | **Release v3.1.0** |

---

## Coordination Protocol

### Daily Check-in (5 minutes)

Each day, post in your coordination channel:

```
Status: [Working on X]
Progress: [What I completed]
Blockers: [Any issues]
Today: [What I'll work on]
```

### Interface Changes

**If you need to change an interface**:

1. **Stop** - Don't change it unilaterally
2. **Discuss** - Message partner with proposed change
3. **Agree** - Both confirm the change makes sense
4. **Update** - One person updates `interfaces.py`
5. **Notify** - Confirm the update is pushed

### Code Reviews

Before merging any service:

1. Create PR to `feature/v3-workspace-overhaul`
2. Partner reviews the PR
3. Must pass:
   - [ ] Implements interface correctly
   - [ ] Has test coverage
   - [ ] No regressions in existing features
4. Merge after approval

### Merge Strategy

```
feature/refactor-config-service     ──┐
feature/refactor-llm-service        ──┼──► feature/v3-workspace-overhaul ──► develop
feature/refactor-video-service      ──┤
feature/refactor-scrape-service     ──┤
feature/refactor-skeleton-service   ──┘
```

**Branch naming**: `feature/refactor-{service-name}`

---

## Testing Requirements

### Unit Tests (Each Service)

Each service must have tests in `tests/test_services/`:

```
tests/
├── test_services/
│   ├── test_config_service.py    # Partner
│   ├── test_llm_service.py       # Partner
│   ├── test_video_service.py     # Partner
│   ├── test_scrape_service.py    # Chris
│   └── test_skeleton_service.py  # Chris
```

**Minimum coverage**: 70% per service

### Integration Test (Together)

After all services merged, run through:

1. Start fresh (delete `state/` folder)
2. Configure API keys via settings
3. Run single scrape
4. Run batch scrape
5. Run direct reel scrape
6. Run skeleton analysis
7. Verify assets created
8. Verify videos downloadable
9. Verify transcripts generated
10. Run AI rewrite

---

## Definition of Done

### Service is "Done" When:

- [ ] Implements interface from `interfaces.py`
- [ ] Has 70%+ test coverage
- [ ] Old functions removed from `app.py` (or marked deprecated)
- [ ] Routes updated to use service
- [ ] PR reviewed and approved
- [ ] Merged to feature branch
- [ ] No regressions in manual testing

### v3.1.0 is "Done" When:

- [ ] All 5 services extracted
- [ ] app.py reduced to ~1000 lines (from 3082)
- [ ] All tests passing
- [ ] Full regression test passed
- [ ] Documentation updated
- [ ] Tagged and released

---

## Troubleshooting

### Merge Conflicts

**If you get conflicts in `app.py`**:
1. Pull latest from feature branch
2. Resolve conflicts (keep both changes if possible)
3. Re-test the affected feature
4. Push resolved version

**Prevention**: Communicate when you're touching `app.py`

### Service Dependency Issues

**If Service A needs Service B**:
```python
# Use dependency injection
class ScrapeService:
    def __init__(self, config_service: ConfigService, video_service: VideoService):
        self.config = config_service
        self.video = video_service
```

Don't create circular dependencies. If needed, extract shared logic to `utils/`.

### Interface Mismatch

**If implementation doesn't match interface**:
1. Check if interface needs updating (discuss first)
2. Or fix implementation to match interface
3. Never silently deviate from interface

---

## Quick Reference

### Partner's Files to Create

```
services/
├── __init__.py           # Export all services
├── config_service.py     # Task 1
├── llm_service.py        # Task 2
└── video_service.py      # Task 3

tests/test_services/
├── test_config_service.py
├── test_llm_service.py
└── test_video_service.py
```

### Chris's Files to Create

```
services/
├── scrape_service.py     # Task 1
└── skeleton_service.py   # Task 2

routes/
├── __init__.py
├── scrape.py
├── skeleton.py
├── assets.py
├── collections.py
├── jobs.py
├── settings.py
└── pages.py

tests/test_services/
├── test_scrape_service.py
└── test_skeleton_service.py
```

### Key Commands

```bash
# Start work
git checkout feature/v3-workspace-overhaul
git pull origin feature/v3-workspace-overhaul
git checkout -b feature/refactor-{service-name}

# Test
python -m pytest tests/test_services/test_{service}_service.py -v

# Submit for review
git push origin feature/refactor-{service-name}
# Create PR via GitHub

# After approval
git checkout feature/v3-workspace-overhaul
git merge feature/refactor-{service-name}
git push origin feature/v3-workspace-overhaul
```

---

## Summary

| Who | What | When |
|-----|------|------|
| **Together** | Define interfaces, kickoff meeting | Day 0 |
| **Partner** | config_service, llm_service, video_service | Week 1 |
| **Chris** | scrape_service, skeleton_service | Week 1 |
| **Chris** | Route blueprints | Week 2 |
| **Together** | Integration testing, release | Week 2 |

**Success criteria**: app.py goes from 3,082 lines to ~1,000 lines with no feature regressions.

---

*This is your collaboration playbook. Follow it and you'll ship v3.1.0 together smoothly.*
