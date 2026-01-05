# ReelRecon Changelog - January 3, 2026

## Session Summary

Continued V3 workspace polish with focus on user preferences persistence and bug fixes.

---

## Bug Fixes

### FIX: Progress Bar Not Updating
- **File**: `app.py` lines 865 and 1105
- **Problem**: Progress bar stayed at 0% during scrapes (text updates worked fine)
- **Root Cause**: Progress callback used `elif progress_pct` instead of `if progress_pct`
- **Impact**: When both `phase` AND `progress_pct` were provided, only the phase branch ran
- **Solution**: Changed `elif` to `if` at both locations in the callback handlers
- **Status**: ✅ FIXED

### FIX: Job Not Appearing in Active Tab After Starting
- **File**: `static/js/workspace.js`
- **Problem**: When starting an analysis (skeleton ripper), batch scrape, or direct scrape, the job redirected to recent tab instead of active, and the job wasn't visible in active jobs
- **Root Cause**: Three issues combined:
  1. `setTimeout` delay was only 50ms (too fast for DOM rendering)
  2. Only `.click()` was called on active tab - didn't explicitly load jobs
  3. Jobs started but weren't tracked for polling
- **Solution**: Updated `startAnalysis()`, `startBatchScrape()`, and `startDirectScrape()` functions:
  - Track job ID with `trackedActiveJobs.add()`
  - Start polling with `startJobsPolling()`
  - Increased timeout from 50ms to 100ms
  - Added explicit `loadJobs('active')` call after clicking the tab
- **Lines Changed**:
  - `startBatchScrape()`: lines 2208-2212
  - `startDirectScrape()`: lines 2428-2433
  - `startAnalysis()`: lines 2600-2605
- **Status**: ✅ FIXED (frontend)

### FIX: Skeleton Ripper Status Handling Made Consistent with Regular Scrapes
- **File**: `app.py` lines 463, 2604-2605, 475-495
- **Problem**: Skeleton ripper jobs used different status values than regular scrapes, causing inconsistent behavior
- **Root Cause**:
  - Skeleton ripper set `status = progress.status.value` (e.g., 'scraping', 'transcribing')
  - Regular scrapes use `status = 'running'` consistently
  - Progress calculation used `progress.get('phase')` which contains display text like "Scraping videos..." not enum values like 'scraping'
- **Solution**: Made skeleton ripper consistent with regular scrapes:
  1. Progress callback now sets `status = 'running'` (line 2604-2605)
  2. Simplified `/api/jobs/active` to check `status in ('running', 'starting')` for all job types (line 463)
  3. Fixed progress calculation to use `progress.get('status')` (enum value) not `progress.get('phase')` (display text)
  4. Added missing 'aggregating' phase to progress calculation
- **Status**: ✅ FIXED

### FIX: Job Card Flashing During Polling
- **File**: `static/js/workspace.js` lines 397-455
- **Problem**: Active job cards flashed in/out during polling due to full DOM replacement
- **Root Cause**: `loadJobs()` called `list.innerHTML = ...` on every poll, replacing entire DOM
- **Solution**: Rewrote polling to match original scraper pattern:
  1. Poll individual job status endpoints (`/api/skeleton-ripper/status/{id}`, `/api/scrape/{id}/status`)
  2. Update DOM elements directly (progress bar width, progress text) without innerHTML replacement
  3. Use recursive `setTimeout` instead of `setInterval`
  4. Track jobs by ID in `trackedActiveJobs` Set
- **Key Functions**:
  - `startJobsPolling()` - Starts polling loop
  - `pollActiveJobsOnce()` - Polls all tracked jobs
  - `pollSingleJob(jobId)` - Polls one job, updates DOM directly
- **Status**: ✅ FIXED

### FIX: Progress Bar Jumping/Going Backward
- **File**: `app.py` lines 2677-2721 (status endpoint), 466-499 (active jobs)
- **Problem**: Progress bar jumped from 0→100→70% between phases
- **Root Cause**: Progress calculation didn't account for skeleton ripper's phase structure (scraping includes fetch+download+transcribe)
- **Solution**: Proper progress percentage calculation:
  - 0-5%: Fetching reels
  - 5-35%: Downloading videos (based on `videos_downloaded`)
  - 35-70%: Transcribing videos (based on `videos_transcribed`)
  - 70-90%: Extracting skeletons
  - 90-95%: Aggregating patterns
  - 95-100%: Synthesizing
- **Backend now calculates `progress_pct`** and sends with status response
- **Status**: ✅ FIXED

### FIX: Reel Fetch Count Not Showing
- **File**: `skeleton_ripper/pipeline.py` lines 412-418
- **Problem**: During fetching, UI showed "Fetching reels from @X..." but no count of reels found
- **Root Cause**: `get_user_reels()` was called without progress callback
- **Solution**: Added `fetch_progress` callback that forwards messages to main progress:
  ```python
  def fetch_progress(msg, phase=None, progress_pct=None):
      progress.message = msg
      self._notify(on_progress, progress)
  reels, profile, error = get_user_reels(session, username, max_reels=100, progress_callback=fetch_progress)
  ```
- **Status**: ✅ FIXED

---

## New Features

### Detail Panel Width Persistence
- **Files**: `app.py`, `static/js/workspace.js`
- **Problem**: Panel resize didn't persist across app restarts (localStorage unreliable in PyWebView)
- **Solution**: Server-side config persistence via settings API

#### Backend Changes (`app.py`)
- Added `detail_panel_width` to GET `/api/settings` response (line 1941)
- Added `detail_panel_width` handling in POST `/api/settings` (line 1971-1972)
- Default value: 600px
- Saved to `config.json` file

#### Frontend Changes (`workspace.js`)
- Replaced localStorage with server API calls
- `setupPanelResize()` now:
  - Loads saved width from `API.getSettings()` on page load
  - Saves width to `API.updateSettings()` after resize (500ms debounce)
- Graceful error handling if API calls fail

#### Why Server-Side Persistence
- PyWebView may not reliably preserve localStorage between sessions
- `config.json` is filesystem-based, guaranteed persistence
- Consistent with other app settings (AI provider, API keys, etc.)

#### Usage
1. Open any asset detail panel
2. Drag the left edge to resize
3. Close and restart the application
4. Panel width is preserved

---

## Files Modified

| File | Changes |
|------|---------|
| `app.py` | Added `detail_panel_width` to settings API; Fixed progress callback `elif` → `if`; Skeleton ripper status = 'running'; Backend progress_pct calculation |
| `static/js/workspace.js` | Panel resize API; Job start functions; Rewrote polling to per-job with direct DOM updates |
| `skeleton_ripper/pipeline.py` | Added fetch_progress callback to get_user_reels() for reel count updates |

---

## API Changes

### GET `/api/settings`
New field in response:
```json
{
  "detail_panel_width": 600
}
```

### POST `/api/settings`
Now accepts:
```json
{
  "detail_panel_width": 750
}
```

---

## Testing Checklist

- [x] Detail panel resize works
- [x] Width saved to config.json after resize
- [x] Width restored on page reload
- [ ] Width persists after full app restart (needs user verification)
- [x] Progress bar callback logic fixed (`elif` → `if`)
- [ ] Progress bar visually updates during scrapes (needs user verification)
- [x] Job start functions updated to track job IDs and start polling
- [x] Job start functions redirect to active tab with explicit `loadJobs('active')` call
- [x] Skeleton ripper status filter updated to include all active statuses
- [ ] Analysis job appears in active tab after starting (needs user verification)
- [ ] Batch scrape job appears in active tab after starting (needs user verification)
- [ ] Direct scrape job appears in active tab after starting (needs user verification)

---

## Related Documentation

- `docs/session-2026-01-02-investigation-report.md` - Bug investigation session
- `docs/ARCHITECTURE-AUDIT.md` - Codebase reference

---

## V3 Release Notes Inclusion

This feature should be included in V3 release notes under **User Preferences**:

> **Persistent Panel Width**: The detail panel width now remembers your preferred size across application restarts. Resize the panel once, and it stays that way.
