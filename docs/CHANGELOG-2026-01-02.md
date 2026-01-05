# ReelRecon Changelog - January 2, 2026

## Session Summary

Major UI/UX improvements to the V3 Workspace, focusing on the Library asset cards, Jobs management, and overall consistency. Also includes critical bug fixes for job persistence and filtering.

---

## Critical Bug Fixes

### FIX: STATE_DIR Not Defined
- **File**: `app.py` line 58
- **Impact**: Skeleton ripper jobs didn't persist to disk, disappeared on server restart
- **Root Cause**: `STATE_DIR` referenced but never defined
- **Solution**: Added `STATE_DIR = BASE_DIR / "state"` after CONFIG_FILE definition
- **Status**: ✅ FIXED - App imports successfully verified

### FIX: Job Filter Not Working
- **File**: `static/js/utils/api.js`
- **Problem**: "View Assets" button showed all assets instead of filtering by job
- **Changes**:
  - Added `job_id` to query params (line 39)
  - Added client-side job_id filtering for merged results (lines 88-96)
  - Fixed `filterLibraryByJob()` to use `job.result.id` instead of `job.id`

### FIX: Asset Deletion Not Persisting
- **File**: `app.py` - `delete_asset()` function
- **Problem**: Deleted skeleton_report assets reappeared after restart
- **Solution**: Now removes job from `active_skeleton_jobs` dict and saves to `skeleton_jobs.json`

---

## New Features

### Job Management

#### Archive System (Soft Delete)
- **Files**: `app.py`, `workspace.js`, `workspace.html`, `workspace.css`
- **New Endpoints**:
  - `POST /api/jobs/<job_id>/archive` - Archive a job
  - `POST /api/jobs/<job_id>/restore` - Restore from archive
  - `GET /api/jobs/archived` - List archived jobs
  - `POST /api/jobs/clear-all` - Archive all completed jobs
- **UI Changes**:
  - Added "Archived" tab in Jobs view
  - Delete button on recent job cards
  - "Clear All" button in jobs header
  - Restore button on archived jobs
- **Persistence**: `state/archived_jobs.json`

#### Rerun Job Feature
- **File**: `workspace.js`
- **Function**: `rerunJob(jobId, jobType)`
- Allows re-running completed scrape jobs with same parameters
- Button appears on completed scrape job cards

### Asset Card Rename
- **Files**: `workspace.js`, `workspace.css`
- **Function**: `renameAsset(assetId, currentTitle)`
- Pencil icon (✏️) appears on card hover
- Uses `PUT /api/assets/:id` to update title
- Immediate UI update without page refresh

### Collection Management
- **Files**: `workspace.js`, `workspace.html`, `workspace.css`
- Collections with 0 items now hidden from sidebar
- Delete button (×) on collection items
- Custom confirmation modal (replaces browser alert)
- Functions: `openDeleteCollectionModal()`, `confirmDeleteCollection()`

---

## UI/UX Improvements

### Asset Card Redesign

#### New Card Structure
```
┌─────────────────────────────────────┐
│ [TYPE] 1/2/2026          ✏️ ★      │  ← Header
├─────────────────────────────────────┤
│ Title                               │
│ @creator1, @creator2 (if report)    │  ← Body
├─────────────────────────────────────┤
│ ● TXT 2  ● VID 0         2 reels   │  ← Metadata badges
│ [Collection Tags] [+]               │  ← Collections
└─────────────────────────────────────┘
```

#### Metadata Badges
- **Scrape Reports**: TXT (transcript count), VID (video count), reel total
- **Skeleton Reports**: SKL (skeleton count), SRC (source/creator count)
- Green dot = has items, Red dot = none
- Badges aligned horizontally across all card types

#### Reduced Redundancy
- Skeleton reports: Preview shows creator handles only (counts in badges)
- Scrape reports: No preview text (title has username, badges show counts)
- Removed duplicate "X reels scraped" text

#### Date Moved to Header
- Date now appears next to type badge in header
- Cleaner body section focused on title and preview

### CSS Changes
- **File**: `static/css/workspace.css`
- New classes:
  - `.asset-card-body` - Flex container for body content
  - `.asset-card-footer` - Footer with border-top, contains badges + collections
  - `.asset-card-header-left` - Groups type badge and date
  - `.asset-card-actions` - Groups rename button and star
  - `.btn-icon-sm` - Small icon button, visible on hover
  - `.asset-indicator` - Badge indicators with dot and label

---

## Files Modified

### Backend (`app.py`)
- Added archive job endpoints
- Added archive persistence functions
- Fixed `delete_asset()` to clean up skeleton_jobs.json
- Added `starred` field support for jobs

### State Manager (`utils/state_manager.py`)
- Added `delete_job()` method
- Added `restore_job()` method
- Added `starred` field to `ScrapeJob` dataclass

### Frontend JavaScript
- `static/js/workspace.js`:
  - `renderAssetCard()` - Complete redesign with new structure
  - `renderJobCard()` - Added delete, restore, rerun buttons
  - `renameAsset()` - New function
  - `archiveJob()`, `restoreJob()`, `clearAllJobs()` - New functions
  - `rerunJob()` - New function
  - Collection delete modal functions
  - Updated `renderCollections()` to filter empty collections

- `static/js/utils/api.js`:
  - Added `job_id` to `getAssets()` query params
  - Added client-side job_id filtering
  - Added `transcript_count` and `video_count` to history asset transform

### Frontend HTML (`templates/workspace.html`)
- Added "Archived" tab in jobs view
- Added "Clear All" button
- Added delete collection confirmation modal

### Frontend CSS (`static/css/workspace.css`)
- New card structure styles
- Metadata badge styles
- Small icon button styles
- Footer and header-left styles
- Removed obsolete `.asset-meta` styles

---

## API Changes

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/jobs/<id>/archive` | POST | Archive a job (soft delete) |
| `/api/jobs/<id>/restore` | POST | Restore job from archive |
| `/api/jobs/archived` | GET | List all archived jobs |
| `/api/jobs/clear-all` | POST | Archive all completed jobs |

---

## Known Issues

1. **Progress bar** - May still not update (elif vs if issue in progress_callback needs verification)

---

## Testing Checklist

- [ ] Verify app imports: `python3 -c "import app; print('OK')"`
- [ ] Test job archive/restore/clear-all
- [ ] Test "View Assets" filters correctly by job
- [ ] Test asset rename functionality
- [ ] Test collection delete with confirmation modal
- [ ] Verify skeleton jobs persist after server restart
- [ ] Check metadata badges display correctly on cards

---

## Migration Notes

No database migrations required. New features use existing storage mechanisms:
- `state/archived_jobs.json` - Created automatically
- `state/skeleton_jobs.json` - Already exists (requires STATE_DIR fix)
