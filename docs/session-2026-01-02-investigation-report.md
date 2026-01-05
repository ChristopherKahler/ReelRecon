# ReelRecon Investigation Report - January 2, 2026

**Session Duration**: ~2 hours
**Investigator**: Claude (Opus 4.5)
**Purpose**: Comprehensive audit and bug investigation to create definitive roadmap for developers/AI agents

---

## Executive Summary

This session conducted a full audit of the ReelRecon application and investigated three critical bugs reported by the user. All bugs were successfully diagnosed with root causes identified and fix instructions documented.

### Key Findings

| Bug | Severity | Root Cause | Status |
|-----|----------|------------|--------|
| Skeleton jobs not persisting | **CRITICAL** | `STATE_DIR` variable undefined | Fix documented |
| Job filter not working | High | Missing `job_id` parameter in API client | Fix documented |
| Progress bar stuck at 0% | Medium | `elif` vs `if` logic error | Fix documented |

### Deliverables Created

1. `docs/ARCHITECTURE-AUDIT.md` - Comprehensive 1,200+ line audit document
2. `prompt-help.md` - Bug fix instructions for execution
3. `REELRECON.md` - Quick reference guide (in chris-ai-systems workspace)
4. This report

---

## Part 1: Initial Audit

### Objective
Create a single source of truth document to prevent developers and AI agents from "going off the rails" by reinventing existing patterns or creating conflicting implementations.

### Methodology
- Full codebase exploration using grep, glob, and file reads
- Traced data flow from frontend to backend
- Mapped API endpoints to handler functions
- Identified patterns and anti-patterns

### Output: `docs/ARCHITECTURE-AUDIT.md`

The audit document includes:

1. **Golden Rules** - Mandatory patterns that must never be violated
   - Asset creation via `Asset.create()`
   - Job tracking via `ScrapeStateManager`
   - LLM calls via `LLMClient`
   - Transcription via `transcribe_video()`

2. **Common Mistakes** - Documented pitfalls to avoid
   - Field name differences (Instagram vs TikTok)
   - yt-dlp PATH issues
   - Direct reel 0 views bug
   - Caption truncation

3. **Connection Maps** - How components interact
   - Frontend → API → Backend flow
   - Job lifecycle state machines
   - Data persistence paths

4. **File Inventory** - Every significant file with purpose

5. **Database Schema** - SQLite tables and relationships

6. **API Reference** - All 60+ endpoints documented

---

## Part 2: Bug Investigation #1 - Progress Bar

### Symptom
Progress bar stays at 0% during scrape jobs, though text status updates correctly.

### Investigation Path

1. Examined `scraper/core.py` progress callbacks
2. Found callbacks only pass message, not `phase` or `progress_pct`
3. Traced callback handling in `app.py`
4. Discovered logic error in callback handler

### Root Cause

In `app.py` around lines 850 and 1090, the callback handler uses `elif` instead of `if`:

```python
# BROKEN:
if phase:
    active_scrapes[scrape_id]['phase'] = phase
    state_manager.update_progress(...)
elif progress_pct is not None:  # NEVER RUNS when phase is also provided!
    active_scrapes[scrape_id]['progress_pct'] = progress_pct
```

When both `phase` AND `progress_pct` are provided, only the phase branch executes. The progress percentage update is skipped.

### Fix

Change `elif` to `if` in both locations:

```python
# FIXED:
if phase:
    active_scrapes[scrape_id]['phase'] = phase
    state_manager.update_progress(...)
if progress_pct is not None:  # Independent check
    active_scrapes[scrape_id]['progress_pct'] = progress_pct
```

---

## Part 3: Bug Investigation #2 - Job Filter

### Symptom
Clicking "View Assets" on a completed job navigates to Library with filter chip displayed, but ALL assets show instead of filtering to that job's assets.

### Investigation Path

1. Traced click handler in `workspace.js` → `filterLibraryByJob()`
2. Followed call chain to `reloadAssets({ job_id: ... })`
3. Examined `API.getAssets()` in `static/js/utils/api.js`
4. Found `job_id` filter completely missing from implementation

### Root Cause

The `getAssets()` function in `api.js`:
1. Never adds `job_id` to query parameters (line 38-39)
2. Never filters merged results by `job_id` (after line 87)

The filter chip appears because the frontend state is set, but the API client ignores the filter entirely.

### Fix

Two changes to `static/js/utils/api.js`:

**Change 1** - Add job_id to query params (line 38-39):
```javascript
if (filters.starred) params.set('starred', 'true');
if (filters.job_id) params.set('job_id', filters.job_id);  // ADD THIS
const query = params.toString();
```

**Change 2** - Add job_id filtering for merged results (after line 87):
```javascript
if (filters.job_id) {
    assets = assets.filter(a => {
        if (a.id === filters.job_id) return true;
        const meta = a.metadata || {};
        return meta.job_id === filters.job_id || meta.source_report_id === filters.job_id;
    });
}
```

---

## Part 4: Bug Investigation #3 - Skeleton Ripper Jobs

### Symptom
- Started analysis with 2 creators
- Did not redirect to active jobs
- No active job shown in list
- Analysis appeared to "fail"

### Investigation Path

1. Checked `state/skeleton_jobs.json` - **FILE DOES NOT EXIST**
2. Examined server logs - job actually completed successfully!
3. Verified output files exist in `output/skeleton_reports/`
4. Searched for `STATE_DIR` definition in `app.py` - **NOT FOUND**
5. Tested module import - **NAMEERROR**

### Evidence of Successful Completion

From `logs/reelrecon.log`:
```
16:34:40 - Starting skeleton ripper job sr_87f412e6
16:35:20 - Job sr_9c93dac2 complete: 5 skeletons extracted
16:35:20 - Total time: 39.83s | Scrape: 0.0s | Extract: 24.0s | Aggregate: 0.0s | Synthesize: 15.8s
```

Output files confirmed:
```
output/skeleton_reports/20260102_223520_sr_9c93dac2/
├── report.md
├── skeletons.json
└── synthesis.json
```

### Root Cause

**CRITICAL BUG**: `STATE_DIR` is referenced but never defined in `app.py`.

Line 2375:
```python
SKELETON_JOBS_FILE = STATE_DIR / 'skeleton_jobs.json'  # NameError!
```

This causes:
1. Module import failure with `NameError: name 'STATE_DIR' is not defined`
2. Server runs from cached bytecode, masking the error
3. `save_skeleton_jobs()` silently fails (caught by try/except)
4. Jobs only exist in memory, lost on any server restart
5. No persistence = jobs "disappear" = appears to fail

### Verification

```bash
cd /mnt/c/Users/Chris/Documents/ReelRecon && python3 -c "import app"
# Output:
# NameError: name 'STATE_DIR' is not defined. Did you mean: 'BASE_DIR'?
```

### Fix

Add `STATE_DIR` definition after line 57 in `app.py`:

```python
OUTPUT_DIR = BASE_DIR / "output"
TIKTOK_OUTPUT_DIR = BASE_DIR / "output_tiktok"
COOKIES_FILE = BASE_DIR / "cookies.txt"
TIKTOK_COOKIES_FILE = BASE_DIR / "tiktok_cookies.txt"
HISTORY_FILE = BASE_DIR / "scrape_history.json"
CONFIG_FILE = BASE_DIR / "config.json"
STATE_DIR = BASE_DIR / "state"  # ADD THIS LINE
```

---

## Part 5: Files Modified/Created

### Created This Session

| File | Purpose |
|------|---------|
| `docs/ARCHITECTURE-AUDIT.md` | Comprehensive codebase audit (1,200+ lines) |
| `docs/session-2026-01-02-investigation-report.md` | This report |
| `prompt-help.md` | Bug fix instructions for other Claude session |
| `~/chris-ai-systems/REELRECON.md` | Quick reference guide |

### Files Requiring Modification

| File | Change Required | Priority |
|------|-----------------|----------|
| `app.py` | Add `STATE_DIR = BASE_DIR / "state"` after line 57 | CRITICAL |
| `app.py` | Change `elif progress_pct` to `if progress_pct` (2 locations) | Medium |
| `static/js/utils/api.js` | Add job_id parameter handling | High |

---

## Part 6: Architectural Observations

### Strengths
- Clear separation of concerns (scraper, skeleton_ripper, storage)
- Unified logging system with structured output
- State manager pattern for job tracking
- Dual data source merge (DB + legacy history)

### Concerns

1. **Silent Failures**: Exception handlers log warnings but don't propagate errors
2. **Variable Undefined**: Critical `STATE_DIR` undefined shows inadequate testing
3. **Dual Data Sources**: Merging DB assets with `scrape_history.json` adds complexity
4. **3,000+ Line app.py**: Monolithic file makes maintenance difficult

### Recommendations

1. **Immediate**: Apply the three fixes documented in `prompt-help.md`
2. **Short-term**: Add startup validation to catch undefined variables
3. **Medium-term**: Split `app.py` into blueprint modules
4. **Long-term**: Complete migration from `scrape_history.json` to database

---

## Part 7: Testing Recommendations

After applying fixes:

```bash
# 1. Verify app imports cleanly
cd /mnt/c/Users/Chris/Documents/ReelRecon
python3 -c "import app; print('OK')"

# 2. Restart server (kill old process completely)
# Windows: taskkill /f /im python.exe
# Then start fresh

# 3. Run skeleton ripper analysis
# Verify skeleton_jobs.json is created in state/

# 4. Test job filter
# Click "View Assets" on a completed job
# Verify only that job's assets appear

# 5. Test progress bar (optional)
# Run a scrape and watch progress percentage
```

---

## Appendix A: Key Code Locations

### Skeleton Ripper Job Persistence
- `app.py:2375` - `SKELETON_JOBS_FILE` definition (needs STATE_DIR)
- `app.py:2381-2388` - `save_skeleton_jobs()` function
- `app.py:2371-2379` - `load_skeleton_jobs()` function
- `app.py:2546` - Save after job creation
- `app.py:2627` - Save after job completion

### Progress Callback
- `app.py:~850` - First callback handler (scrape endpoint)
- `app.py:~1090` - Second callback handler (batch endpoint)
- `scraper/core.py:~855` - Progress callback calls

### Job Filter
- `static/js/utils/api.js:33-102` - `getAssets()` function
- `static/js/workspace.js:482` - `filterLibraryByJob()` handler
- `static/js/workspace.js:676` - `reloadAssets()` with filters

---

## Appendix B: Session Timeline

| Time | Activity |
|------|----------|
| Start | Initial audit request received |
| +30m | Created `ARCHITECTURE-AUDIT.md` |
| +45m | Bug #1 investigation (progress bar) |
| +60m | Bug #2 investigation (job filter) |
| +90m | Bug #3 investigation (skeleton jobs) |
| +100m | Discovered STATE_DIR root cause |
| +110m | Updated `prompt-help.md` with all fixes |
| +120m | Created this comprehensive report |

---

## Conclusion

All three reported bugs have been successfully diagnosed:

1. **STATE_DIR undefined** - Critical bug preventing skeleton job persistence
2. **Job filter missing** - Frontend API client ignores job_id filter
3. **Progress bar stuck** - Logic error using elif instead of if

The fixes are documented in `prompt-help.md` and ready for implementation. The `ARCHITECTURE-AUDIT.md` document provides a comprehensive reference to prevent future "off the rails" development.

**Next Action**: Execute fixes from `prompt-help.md` in priority order, then restart server and verify all three issues are resolved.

---

## Addendum: January 3, 2026 - Detail Panel Width Persistence

### Feature Request
User requested that the detail panel width persist across application restarts when resized.

### Investigation
- Found existing `setupPanelResize()` function with localStorage persistence
- localStorage may not work reliably in PyWebView desktop app
- App already has server-side settings API (`/api/settings`)

### Solution Implemented
Changed from localStorage to server-side config file persistence:

**Backend (`app.py`)**:
- Added `detail_panel_width` to GET `/api/settings` (defaults to 600px)
- Added `detail_panel_width` handling in POST `/api/settings`

**Frontend (`workspace.js`)**:
- `setupPanelResize()` now loads width from `API.getSettings()` on init
- Saves width via `API.updateSettings()` after resize (500ms debounce)

### Files Modified
- `app.py` - Lines 1941 and 1971-1972
- `static/js/workspace.js` - `setupPanelResize()` function (lines 2699-2766)

### V3 Release Notes
Include under **User Preferences**:
> Detail panel width now persists across application restarts
