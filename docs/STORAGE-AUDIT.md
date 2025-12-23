# Storage Audit - E1.1

**Date:** 2025-12-23
**Version:** v2.1.0
**Branch:** feature/asset-management

---

## Current Storage Patterns

### 1. Root-Level State Files

| File | Purpose | Schema |
|------|---------|--------|
| `scrape_history.json` | Historical scrape records (15KB) | Array of ScrapeRecord |
| `state/active_scrapes.json` | Current/recent job queue | `{updated_at, jobs: Job[]}` |

### 2. Directory Structure

```
ReelRecon/
├── output/                          # Instagram scrapes
│   ├── output_{username}/           # Per-creator directories
│   │   ├── reels_{date}.json        # Scrape results
│   │   ├── transcripts/             # .txt transcript files
│   │   └── videos/                  # Downloaded .mp4 files
│   ├── skeleton_reports/            # Skeleton Ripper outputs
│   │   └── {timestamp}_{id}/
│   │       ├── skeletons.json       # Extracted skeletons
│   │       ├── synthesis.json       # Synthesized templates
│   │       ├── report.md            # Markdown report
│   │       └── videos/              # Downloaded videos
│   └── skeleton_temp/               # Temp files during processing
├── output_tiktok/                   # TikTok scrapes
│   └── output_{username}_tiktok/    # Same structure as Instagram
└── cache/                           # Whisper model cache
```

---

## Schema Definitions

### ScrapeRecord (scrape_history.json)

```json
{
  "id": "uuid",
  "username": "string",
  "timestamp": "ISO8601",
  "profile": {
    "username": "string",
    "full_name": "string",
    "followers": "number (optional)"
  },
  "total_reels": "number",
  "top_count": "number",
  "top_reels": [Reel],
  "output_dir": "absolute_path",
  "platform": "instagram | tiktok",
  "status": "complete | error"
}
```

### Reel Object

```json
{
  "shortcode": "string",
  "video_id": "string (TikTok only)",
  "url": "string",
  "views": "number",
  "likes": "number",
  "comments": "number",
  "shares": "number (TikTok only)",
  "caption": "string",
  "video_url": "string (CDN URL)",
  "create_time": "timestamp (TikTok only)",
  "duration": "number (TikTok only)",
  "source": "instagram | tiktok",
  "local_video": "absolute_path | null",
  "transcript": "string",
  "transcript_file": "absolute_path"
}
```

### ActiveJob (state/active_scrapes.json)

```json
{
  "id": "uuid",
  "username": "string",
  "platform": "instagram | tiktok",
  "state": "queued | running | complete | error",
  "progress": {
    "phase": "string",
    "phase_progress": "number (0-100)",
    "overall_progress": "number (0-100)",
    "current_item": "number",
    "total_items": "number",
    "message": "string",
    "started_at": "ISO8601",
    "updated_at": "ISO8601",
    "errors": []
  },
  "config": {
    "username": "string",
    "platform": "string",
    "max_reels": "number",
    "top_n": "number",
    "download": "boolean",
    "transcribe": "boolean",
    "transcribe_provider": "local | openai",
    "whisper_model": "string"
  },
  "result": "ScrapeRecord | null",
  "error_code": "string | null",
  "error_message": "string | null",
  "created_at": "ISO8601",
  "completed_at": "ISO8601 | null"
}
```

### Skeleton Report (skeletons.json)

```json
[{
  "video_id": "string",
  "hook": "string",
  "hook_technique": "curiosity | contrast | shock | ...",
  "hook_word_count": "number",
  "value": "string",
  "value_structure": "transformation | steps | framework | ...",
  "value_points": ["string"],
  "cta": "string",
  "cta_type": "link | comment | none | ...",
  "total_word_count": "number",
  "estimated_duration_seconds": "number",
  "creator_username": "string",
  "platform": "instagram | tiktok",
  "views": "number",
  "likes": "number",
  "url": "string",
  "video_url": "string",
  "transcript": "string",
  "extracted_at": "ISO8601",
  "extraction_model": "string",
  "local_video": "relative_path | null"
}]
```

### Synthesis Report (synthesis.json)

```json
{
  "success": "boolean",
  "analysis": "string (markdown)",
  "templates": [],
  "quick_wins": [],
  "warnings": [],
  "model_used": "string",
  "synthesized_at": "ISO8601"
}
```

---

## Migration Requirements

### Assets to Migrate

| Source | Asset Type | Estimated Count |
|--------|------------|-----------------|
| `scrape_history.json` | scrape | ~10 records |
| `output/skeleton_reports/` | skeleton | 1+ reports |
| Individual `reels_*.json` | scrape (reference) | ~20 files |

### Key Transformations

1. **Scrape Records** → Asset type: `scrape`
   - Extract from `scrape_history.json`
   - Store `top_reels` in `metadata` JSON column
   - Set `content_path` to `output_dir`
   - Generate `preview` from first reel caption

2. **Skeleton Reports** → Asset type: `skeleton`
   - Each `skeleton_reports/{id}/` directory becomes one asset
   - Store `synthesis.analysis` as `preview`
   - Store full `skeletons.json` content in `metadata`
   - Set `content_path` to report directory

3. **Transcripts** → Asset type: `transcript` (future)
   - Individual transcript files can be saved as separate assets
   - Link to parent scrape via collections

### Migration Safety

- **Read-only migration**: Original files remain unchanged
- **Idempotent**: Migration can be re-run safely
- **Flag file**: `state/migration_complete.json` marks completion
- **Validation**: Count check before/after migration

---

## Observations

1. **Duplicate data**: `scrape_history.json` duplicates data from individual `reels_*.json` files
2. **Absolute paths**: Windows paths stored (need normalization)
3. **No indexing**: Linear scan required to find specific records
4. **No collections**: No existing grouping mechanism
5. **No starring**: No way to mark favorites

---

## Next Step

Proceed to **E1.2: Create SQLite Schema** with schema design informed by this audit.
