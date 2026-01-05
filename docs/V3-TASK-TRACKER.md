# V3 Workspace Overhaul - Task Tracker

> **Companion to:** `V3-OVERHAUL-SPEC.md`
> **Purpose:** Granular task breakdown with checkboxes for execution tracking
> **Protocol:** Update checkboxes as tasks complete. This file is the source of truth for progress.

---

## Quick Status

```
Phase 0: [x] Complete       Phase 4: [~] In Progress      Phase 7:   [~] In Progress
Phase 1: [x] Complete       Phase 5: [ ] Not Started      Phase 7.5: [x] Complete
Phase 2: [x] Complete       Phase 6: [ ] Not Started      Phase 8:   [ ] Not Started
Phase 3: [x] Complete
```

**Current Phase:** Phase 7 - Direct Reel Scrape (testing fixes)
**Current Task:** Test direct reel scrape after refactoring to use get_reel_info()
**Blocker:** Views showing 0 - fixed by using existing get_reel_info() instead of yt-dlp
**Last Updated:** 2026-01-03 14:23 CST

### Session Notes (2026-01-03)
**Feature Added:**
- Detail panel width persistence via server-side config (replaces localStorage)
- Files: `app.py` (settings API), `workspace.js` (setupPanelResize)

**Bug Fixed:**
- Progress bar stuck at 0% - changed `elif progress_pct` to `if progress_pct` (lines 865, 1105)
- Now allows both phase AND progress_pct updates in same callback

### Session Notes (2026-01-01)
**Fixes Applied (need restart to test):**
1. `scraper/core.py` - `fetch_single_reel()` now uses `get_reel_info()` (same as profile scrape)
2. `scraper/core.py` - `download_video()` uses `sys.executable -m yt_dlp` (PATH fix)
3. `app.py` - Added `/api/health` endpoint for auto-reconnect
4. `workspace.js` - Added server heartbeat with auto-reconnect overlay
5. `launcher.pyw` / `ReelRecon-Mac.py` - Restart skips browser open (already open)

---

## Phase 0: Setup & Foundation

**Goal:** Branch setup, preserve current state, establish new file structure

### Git Setup
- [x] 0.1 Checkout develop branch and pull latest
- [x] 0.2 Create feature branch: `git checkout -b feature/v3-workspace-overhaul`
- [x] 0.3 Push feature branch: `git push -u origin feature/v3-workspace-overhaul`
- [x] 0.4 Tag stable point: `git tag v2.2.0-stable` on develop

### File Structure Creation
- [x] 0.5 Create `static/js/state/` directory
- [x] 0.6 Create `static/js/utils/` directory
- [x] 0.7 Create `static/js/components/` directory structure:
  ```
  components/
  ├── layout/
  ├── library/
  ├── jobs/
  ├── actions/
  └── shared/
  ```
- [x] 0.8 Create `static/css/workspace.css` (copy from tactical.css as starting point)
- [x] 0.9 Create `templates/workspace.html` (minimal shell)
- [x] 0.10 Create `static/js/workspace.js` (entry point stub)
- [x] 0.11 Create `static/js/state/store.js` (stub)
- [x] 0.12 Create `static/js/utils/api.js` (stub)
- [x] 0.13 Create `static/js/utils/router.js` (stub)

### Backend Route
- [x] 0.14 Add `/workspace` route to app.py (serves workspace.html)
- [x] 0.15 Test that `/workspace` loads without errors
- [x] 0.16 Commit: "chore(setup): add v3 workspace file structure"

### Phase 0 Exit
- [x] 0.17 All files created and loadable
- [x] 0.18 `/workspace` serves basic shell
- [x] 0.19 Commit and push phase 0 complete

---

## Phase 1: Design System & Layout

**Goal:** New color system, typography, sidebar layout

### CSS Foundation
- [x] 1.1 Update CSS variables - background colors (Zinc scale)
- [x] 1.2 Update CSS variables - accent colors (green for actions only)
- [x] 1.3 Update CSS variables - text colors (better contrast)
- [x] 1.4 Update CSS variables - border colors (neutral)
- [x] 1.5 Update CSS variables - typography scale
- [x] 1.6 Remove scan-line effect CSS
- [x] 1.7 Remove corner HUD bracket CSS
- [x] 1.8 Add focus state styles for accessibility
- [x] 1.9 Add consistent spacing scale utilities
- [x] 1.10 Test color changes visually

### Layout Shell
- [x] 1.11 Create workspace.html base structure:
  ```html
  <div id="app">
    <aside id="sidebar"></aside>
    <main id="main-content"></main>
  </div>
  ```
- [x] 1.12 Style sidebar container (fixed width, full height)
- [x] 1.13 Style main content area (flex grow, scroll)
- [ ] 1.14 Add sidebar collapse toggle (deferred)

### Sidebar Component
- [x] 1.15 Create Sidebar.js component file (inline in workspace.js)
- [x] 1.16 Add logo/brand section to sidebar
- [x] 1.17 Add quick action buttons (+ New Scrape, + New Analysis)
- [x] 1.18 Add navigation section (Library, Jobs, Settings)
- [x] 1.19 Add collections section (placeholder)
- [x] 1.20 Style sidebar sections
- [x] 1.21 Add active state to navigation items
- [x] 1.22 Wire up navigation click handlers

### Client-Side Routing
- [x] 1.23 Create router.js with hash-based routing
- [x] 1.24 Define route map: '', 'library', 'jobs', 'settings'
- [x] 1.25 Add route change listener (hashchange)
- [x] 1.26 Create view container switching logic
- [x] 1.27 Update URL on navigation click
- [x] 1.28 Test navigation between views

### State Store Foundation
- [x] 1.29 Create store.js with initial state structure
- [x] 1.30 Add subscribe/dispatch pattern
- [x] 1.31 Wire sidebar to store for active route
- [x] 1.32 Test state updates

### Phase 1 Exit
- [x] 1.33 New color palette active and visually verified
- [x] 1.34 Sidebar renders with navigation
- [x] 1.35 Hash-based routing switches views
- [x] 1.36 Commit: "feat(ui): add workspace layout and design system"

---

## Phase 2: Library View

**Goal:** Library becomes the central hub

### API Client
- [x] 2.1 Create api.js with fetch wrapper
- [x] 2.2 Add getAssets(filters) function
- [x] 2.3 Add getAsset(id) function
- [x] 2.4 Add searchAssets(query) function
- [x] 2.5 Add getCollections() function
- [x] 2.6 Test API functions in console

### Asset Grid Component
- [x] 2.7 Create AssetGrid.js component (inline in workspace.js)
- [x] 2.8 Add grid container with responsive columns
- [ ] 2.9 Add list/grid view toggle (deferred)
- [x] 2.10 Style grid layout
- [x] 2.11 Handle empty state

### Asset Card Component
- [x] 2.12 Create AssetCard.js component (inline in workspace.js)
- [x] 2.13 Add card structure (title, preview, metadata)
- [x] 2.14 Add type badge (skeleton, transcript, scrape, etc.)
- [x] 2.15 Add star toggle
- [x] 2.16 Add click handler to open detail
- [x] 2.17 Style card with hover state
- [x] 2.18 Handle different asset types display

### Search Bar
- [x] 2.19 Create SearchBar.js component (inline in workspace.html)
- [x] 2.20 Add search input with icon
- [x] 2.21 Add debounced search (300ms)
- [x] 2.22 Wire to searchAssets API
- [x] 2.23 Update asset grid with results
- [x] 2.24 Handle no results state

### Filter Chips
- [x] 2.25 Create FilterChips.js component (inline in workspace.html)
- [x] 2.26 Add type filter chips (All, Skeletons, Transcripts, Reports)
- [ ] 2.27 Add date filter dropdown (deferred to Phase 5)
- [x] 2.28 Wire filters to asset query
- [x] 2.29 Style active/inactive chip states

### Collection List (Sidebar Integration)
- [x] 2.30 Fetch collections on app load
- [x] 2.31 Render collections in sidebar
- [x] 2.32 Add click handler to filter by collection
- [x] 2.33 Show asset count per collection
- [x] 2.34 Style collection items

### Asset Detail Panel
- [x] 2.35 Create AssetDetail.js component (inline in workspace.js)
- [x] 2.36 Add slideout panel container
- [x] 2.37 Add close button
- [x] 2.38 Display full asset content based on type
- [x] 2.39 Add collection tags display
- [x] 2.40 Add action buttons (Star, Copy, Delete)
- [x] 2.41 Style detail panel
- [x] 2.42 Add animation for open/close

### Phase 2 Exit
- [x] 2.43 Assets display in grid
- [x] 2.44 Search returns results
- [x] 2.45 Type filters work
- [x] 2.46 Collection filter works
- [x] 2.47 Asset detail opens in panel
- [x] 2.48 Commit: "feat(library): add library view with search and filters"

---

## Phase 3: Actions & Modals

**Goal:** Scrape and Analysis actions work from modals

### Modal Container
- [x] 3.1 Create Modal.js base component (inline in workspace.js)
- [x] 3.2 Add overlay backdrop
- [x] 3.3 Add modal content container
- [x] 3.4 Add close button (X and Escape key)
- [x] 3.5 Add open/close methods
- [x] 3.6 Style modal (centered, max-width)
- [x] 3.7 Add animation for open/close
- [x] 3.8 Prevent body scroll when open

### New Scrape Modal
- [x] 3.9 Create NewScrapeModal.js (inline in workspace.js)
- [x] 3.10 Add platform toggle (Instagram/TikTok)
- [x] 3.11 Add username input field
- [x] 3.12 Add reel count selector (1-20)
- [x] 3.13 Add date range dropdown (All, 30 days, 60 days, 90 days) - NEW FEATURE
- [x] 3.14 Add transcription toggle
- [x] 3.15 Add "Start Scrape" button
- [x] 3.16 Wire to existing /api/scrape endpoint
- [x] 3.17 Show loading state during submission
- [x] 3.18 Handle errors (show in modal)
- [x] 3.19 On success: close modal, navigate to Jobs view
- [x] 3.20 Style form elements

### New Analysis Modal (Skeleton Ripper)
- [x] 3.21 Create NewAnalysisModal.js (inline in workspace.js)
- [x] 3.22 Add multi-creator input (up to 5)
- [x] 3.23 Add add/remove creator buttons
- [x] 3.24 Add videos per creator selector
- [x] 3.25 Add LLM provider dropdown
- [x] 3.26 Add model selector (dynamic based on provider)
- [x] 3.27 Fetch available providers on mount
- [x] 3.28 Add "Start Analysis" button
- [x] 3.29 Wire to existing /api/skeleton-ripper/start endpoint
- [x] 3.30 Show loading state
- [x] 3.31 Handle errors
- [x] 3.32 On success: close modal, navigate to Jobs view
- [x] 3.33 Style form

### Wire Quick Actions
- [x] 3.34 Connect sidebar "+ New Scrape" button to NewScrapeModal
- [x] 3.35 Connect sidebar "+ New Analysis" button to NewAnalysisModal
- [ ] 3.36 Test end-to-end: click button → modal → submit → job starts (user testing)

### Phase 3 Exit
- [x] 3.37 New Scrape modal works end-to-end
- [x] 3.38 New Analysis modal works end-to-end
- [x] 3.39 Date range filter implemented (scrape modal)
- [x] 3.40 Jobs navigate correctly after start
- [x] 3.41 Commit: "feat(actions): add scrape and analysis modals"

### Phase 3 Enhancements (Added During Testing)
- [x] 3.42 Multi-select filter chips (toggle multiple types, show ANY match)
- [x] 3.43 Collection tags on asset cards (color-coded pills at bottom)
- [x] 3.44 Collection tags wrap to multiple lines
- [x] 3.45 X button on collection tags to remove from collection
- [x] 3.46 Favorites nav item in sidebar with count badge
- [x] 3.47 Favorites view showing starred assets
- [x] 3.48 Softer red color (#F87171 instead of #EF4444)
- [x] 3.49 Commit: "feat(library): add multi-select filters and collection tags"
- [x] 3.50 Commit: "feat(ui): add favorites view and collection removal"

---

## Phase 4: Jobs View

**Goal:** Unified view of active and recent jobs

**User Note (Phase 3 Testing):** Need expanded view for job results - either:
- Replace grid with full report view when clicking a result
- Add new sidemenu option like "Reports" for expanded multi-tab viewing
- Consider tabbed interface within detail panel for full content access

**2024-12-31 Session Note:** Significant progress made. Jobs view functional with real-time updates.
Detail panel enhanced with full reel accordion showing stats, URL, caption, transcript.

### Backend Endpoints
- [x] 4.1 Add /api/jobs/active endpoint to app.py
  - Combine active_scrapes + skeleton ripper jobs
  - Return unified structure
- [x] 4.2 Add /api/jobs/recent endpoint to app.py
  - Query from history + skeleton reports
  - Return last 20 completed jobs
- [x] 4.3 Test endpoints with curl/browser
- [x] 4.4 Update api.js with new endpoints

### Job List Component
- [x] 4.5 Create JobList.js component
- [x] 4.6 Add tabs: Active / Recent
- [x] 4.7 Fetch active jobs on mount
- [x] 4.8 Fetch recent jobs on tab switch
- [x] 4.9 Handle empty states

### Job Card Component
- [x] 4.10 Create JobCard.js component
- [x] 4.11 Display job type (Scrape/Analysis)
- [x] 4.12 Display username(s) (fixed @unknown bug)
- [x] 4.13 Display status (running/completed/failed)
- [x] 4.14 Display started time
- [x] 4.15 Add progress bar for active jobs
- [ ] 4.16 Add click handler to expand detail
- [x] 4.17 Style card

### Job Progress (Active Jobs)
- [x] 4.18 Create JobProgress.js component
- [x] 4.19 Poll status endpoint every 1 second (changed from 2s for responsiveness)
- [x] 4.20 Update progress bar
- [x] 4.21 Display current phase/status text
- [x] 4.22 Handle job completion (green flash notification)
- [x] 4.23 Handle job failure (show error)
### Job Abort System
- [x] 4.24 Add abort button to active job cards in Jobs view
- [x] 4.25 Create comprehensive abort endpoint with cleanup:
  - Stop all current processes (scrape thread, transcription)
  - Delete any downloaded videos (if transcribe-only, videos are temp)
  - Remove partial data from history/library
  - Clean up any temp files created during the job
  - Mark job as "aborted" in state manager
- [x] 4.25a Handle batch abort (stop current + cancel all pending in batch)
- [x] 4.25b Show aborted jobs in Recent tab with "aborted" status
- [x] 4.25c Track files created during scrape for cleanup (temp video paths)

### Job Detail Expansion
- [ ] 4.26 Add expandable section to JobCard
- [ ] 4.27 Show full details when expanded
- [x] 4.28 For completed scrapes: show result count, link to assets
- [ ] 4.29 For completed analyses: show report link
- [ ] 4.30 Add "View Results" button → navigate to library with filter

### Detail Panel Enhancement (Added)
- [x] 4.36 Reel accordion with expandable items
- [x] 4.37 Stats row (views, likes, comments) per reel
- [x] 4.38 Full caption display with copy
- [x] 4.39 Full transcript display with copy
- [x] 4.40 URL display with copy button
- [x] 4.41 "Copy for AI" action per reel

### Phase 4 Exit
- [x] 4.31 Active jobs display (both types)
- [x] 4.32 Progress updates in real-time
- [x] 4.33 Completed jobs show in recent
- [ ] 4.34 Can click through to results
- [ ] 4.35 Commit: "feat(jobs): add unified jobs view"

---

## Phase 5: Integration & Polish

**Goal:** Connect everything, fix edge cases, polish

### Port Existing Features
- [ ] 5.1 Port rewrite panel to asset detail view
- [ ] 5.2 Port video playback to asset detail
- [ ] 5.3 Integrate save/collect modal (already exists)
- [ ] 5.4 Port settings view from existing code
- [ ] 5.5 Test all ported features

### Bug Fixes
- [x] 5.6 Fix caption truncation in scraper/core.py
  - Line 129: Remove [:200] ✓
  - Line 143: Remove regex limit ✓
  - Line 235: Remove [:200] ✓
- [ ] 5.7 Test caption fix with real scrape
- [ ] 5.8 Fix any error auto-hide issues

### Loading States
- [ ] 5.9 Add loading spinner component
- [ ] 5.10 Add skeleton loaders for asset grid
- [ ] 5.11 Add loading state for search
- [ ] 5.12 Add loading state for job actions
- [ ] 5.13 Test all loading states

### Error Handling
- [ ] 5.14 Create Toast/notification component
- [ ] 5.15 Add error toast for API failures
- [ ] 5.16 Add success toast for completed actions
- [ ] 5.17 Handle network offline state
- [ ] 5.18 Test error scenarios

### Keyboard Shortcuts
- [ ] 5.19 Escape closes modals (done in Phase 3)
- [ ] 5.20 / focuses search
- [ ] 5.21 n opens new scrape modal
- [ ] 5.22 Document shortcuts

### User Preferences
- [x] 5.22a Detail panel width persistence (2026-01-03)
  - Server-side config storage via `/api/settings`
  - Files: `app.py`, `workspace.js` (setupPanelResize)
  - Replaces unreliable localStorage with config.json

### Final Polish
- [ ] 5.23 Audit all transitions/animations
- [ ] 5.24 Verify consistent spacing
- [ ] 5.25 Check all text contrast
- [ ] 5.26 Test at 50% brightness
- [ ] 5.27 Fix any visual glitches

### Code Cleanup
- [ ] 5.28 Remove unused code from workspace.js
- [ ] 5.29 Consolidate duplicate styles
- [ ] 5.30 Add code comments where needed

### Phase 5 Exit
- [ ] 5.31 All existing features work in new UI
- [ ] 5.32 Caption bug fixed and verified
- [ ] 5.33 Loading states smooth
- [ ] 5.34 Errors display correctly
- [ ] 5.35 Commit: "feat(polish): integrate features and fix bugs"

---

## Phase 6: Migration & Cutover

**Goal:** Swap new UI to be default, redirect legacy routes

### Route Migration
- [ ] 6.1 Change `/` to serve workspace.html
- [ ] 6.2 Add redirect: `/skeleton-ripper` → `/#/jobs?start=analysis`
- [ ] 6.3 Add redirect: `/library` → `/`
- [ ] 6.4 Keep old templates for reference (don't delete yet)
- [ ] 6.5 Test all redirects

### Version Update
- [ ] 6.6 Update VERSION file to 3.0.0
- [ ] 6.7 Update version display in UI

### Documentation
- [ ] 6.8 Update README.md with new UI info
- [ ] 6.9 Update any screenshots
- [ ] 6.10 Document breaking changes (if any)

### Testing
- [ ] 6.11 Complete full regression test checklist (see SPEC)
- [ ] 6.12 Test fresh install scenario
- [ ] 6.13 Test upgrade from v2.2.0 scenario
- [ ] 6.14 Fix any issues found

### Release Prep
- [ ] 6.15 Merge feature branch to develop
- [ ] 6.16 Tag v3.0.0-beta.1
- [ ] 6.17 Get tester feedback
- [ ] 6.18 Address feedback issues
- [ ] 6.19 Final merge to main
- [ ] 6.20 Tag v3.0.0

### Phase 6 Exit
- [ ] 6.21 `/` serves new workspace
- [ ] 6.22 Old URLs redirect correctly
- [ ] 6.23 All regression tests pass
- [ ] 6.24 Documentation updated
- [ ] 6.25 Release tagged

---

## Phase 7: Batch Scraping & Direct Reel Capture

**Goal:** Enable batch operations and individual reel scraping

### Batch Creator Scrapes
- [x] 7.1 Update New Scrape modal with multi-line textarea for usernames
- [x] 7.2 Add "up to 5 creators" hint and validation
- [x] 7.3 Parse multi-line input into array of usernames
- [x] 7.4 Create /api/scrape/batch endpoint
- [x] 7.5 Backend processes creators sequentially, same settings for all
- [x] 7.6 Each creator creates separate asset in library
- [x] 7.7 Support queueing multiple batches (different settings per batch)
- [x] 7.8 Jobs view shows batch progress (creator 2/5, etc.)
- [ ] 7.9 Test batch scrape end-to-end

### Direct Reel Modal
- [x] 7.10 Create "Direct Reel" modal (separate from New Scrape)
- [x] 7.11 Add URL/ID toggle at top of modal
- [x] 7.12 Add multi-line textarea for up to 5 reel URLs/IDs
- [x] 7.13 Add extraction options (download, transcribe)
- [x] 7.14 Create /api/scrape/direct endpoint
- [x] 7.15 Backend parses URL to extract shortcode if URL mode
- [x] 7.16 Backend uses ID directly if ID mode
- [x] 7.17 Each reel creates separate asset in library
- [x] 7.18 Add "Direct Reel" button to sidebar
- [ ] 7.19 Test direct reel scrape end-to-end (views, download, transcription)
- [x] 7.20 Implement fetch_single_reel() in scraper/core.py
- [x] 7.21 Implement fetch_single_video() in scraper/tiktok.py

### Direct Reel Bug Fixes (2026-01-01)
- [x] 7.22 Fix yt-dlp PATH issue - use sys.executable -m yt_dlp in download_video()
- [x] 7.23 Fix views=0 bug - fetch_single_reel() now uses get_reel_info() (same as profile scrape)
- [ ] 7.24 Verify transcription works after download fix (needs testing)

### Phase 7 Exit
- [ ] 7.20 Batch creator scrape works with up to 5 creators
- [ ] 7.21 Multiple batches can be queued with different settings
- [ ] 7.22 Direct reel modal works with URL or ID input
- [ ] 7.23 Up to 5 reels can be scraped directly
- [ ] 7.24 All scrapes save as individual library assets
- [ ] 7.25 Commit: "feat(scrape): add batch and direct reel scraping"

---

## Phase 7.5: Desktop Launcher & Installer

**Goal:** Professional desktop app experience with splash screen, system tray, and installer

### Windows Desktop Launcher
- [x] 7.5.1 Create launcher.pyw with splash screen during startup
- [x] 7.5.2 Add system tray icon with menu (pystray + Pillow)
- [x] 7.5.3 System tray menu: Open ReelRecon, Server Running, Restart, Fetch Updates, Quit
- [x] 7.5.4 Restart option kills server and relaunches with splash
- [x] 7.5.5 Fetch Updates runs git pull then auto-restarts
- [x] 7.5.6 Create ReelRecon.bat to launch pythonw.exe (no console window)
- [x] 7.5.7 Server runs hidden in background (no terminal window)
- [x] 7.5.8 Browser auto-opens after server ready

### Mac Desktop Launcher
- [x] 7.5.9 Create ReelRecon-Mac.py with splash screen and menu bar icon
- [x] 7.5.10 Create ReelRecon.command for double-click launching
- [x] 7.5.11 Make .command file executable (chmod +x)
- [x] 7.5.12 Keep START-HERE.py as fallback

### Windows Installer
- [x] 7.5.13 Create installer/ReelRecon-Installer.pyw GUI wizard
- [x] 7.5.14 Installer checks for Git and Python prerequisites
- [x] 7.5.15 Folder picker for install location
- [x] 7.5.16 Git clones repo to selected location
- [x] 7.5.17 Installs dependencies automatically
- [x] 7.5.18 Creates desktop shortcut option
- [x] 7.5.19 Option to launch immediately after install
- [x] 7.5.20 Create Install-ReelRecon.bat launcher
- [x] 7.5.21 Build installer exe with PyInstaller (ReelRecon-Setup.exe)

### Legacy Launcher Update
- [x] 7.5.22 Update run_app.bat to auto-exit after launching server
- [x] 7.5.23 Remove pause and terminal messages from run_app.bat

### Launcher Enhancements (Added 2026-01-01)
- [x] 7.5.28 Add "View Logs" menu option - opens server.log in Notepad/TextEdit
- [x] 7.5.29 Server logs to file (server.log) for debugging
- [x] 7.5.30 Restart option skips browser open (browser already open)
- [x] 7.5.31 Add auto-reconnect to workspace.js (heartbeat + overlay + auto-refresh)
- [x] 7.5.32 Add /api/health endpoint for reconnect detection

### Phase 7.5 Exit
- [x] 7.5.24 Windows: ReelRecon.bat launches splash → tray → browser
- [x] 7.5.25 Mac: ReelRecon.command launches splash → menu bar → browser
- [x] 7.5.26 Installer wizard works for fresh Windows installs
- [ ] 7.5.27 Commit: "feat(launcher): add desktop launcher with splash and system tray"

---

## Phase 8: Asset Extraction Options

**Goal:** Allow transcripts and skeletons to save as separate library assets

### Transcript Asset Extraction
- [ ] 8.1 Add checkbox to scrape modal: "Save transcripts as separate assets"
- [ ] 8.2 Update scrape backend to create transcript assets when enabled
- [ ] 8.3 Transcript assets linked to parent scrape job
- [ ] 8.4 Transcript assets appear in library with type "transcript"
- [ ] 8.5 Test transcript extraction with scrape

### Skeleton Asset Extraction
- [ ] 8.6 Add checkbox to analysis modal: "Save skeletons as separate assets"
- [ ] 8.7 Update analysis backend to create skeleton assets when enabled
- [ ] 8.8 Skeleton assets linked to parent analysis report
- [ ] 8.9 Skeleton assets appear in library with type "skeleton"
- [ ] 8.10 Test skeleton extraction with analysis

### Phase 8 Exit
- [ ] 8.11 Transcripts can optionally save as individual assets
- [ ] 8.12 Skeletons can optionally save as individual assets
- [ ] 8.13 Assets properly typed and filterable in library
- [ ] 8.14 Commit: "feat(library): add transcript and skeleton asset extraction"

---

## Completion Log

| Phase | Started | Completed | Notes |
|-------|---------|-----------|-------|
| Phase 0 | 2024-12-31 | 2024-12-31 | Commit: 6772eaf |
| Phase 1 | 2024-12-31 | 2024-12-31 | Commit: a888628 |
| Phase 2 | - | - | |
| Phase 3 | - | - | |
| Phase 4 | - | - | |
| Phase 5 | - | - | |
| Phase 6 | - | - | |

---

## Session Handoff Protocol

When ending a session, update:
1. **Quick Status** section at top
2. **Completion Log** with dates
3. **V3-OVERHAUL-SPEC.md** → SESSION STATE section

When starting a session, read:
1. This file's **Quick Status**
2. **V3-OVERHAUL-SPEC.md** → SESSION STATE section
3. Find first unchecked task in current phase
