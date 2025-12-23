# Skeleton Ripper Feature Backlog

> Partner feedback and feature planning for the Content Skeleton Ripper tool.
> Last updated: 2025-12-23

---

## Feature Ideas

---

### P0. Asset Management + Universal Save/Collect System (FOUNDATION)
**Source:** Partner feedback + architectural requirement
**Problem:** Every feature generates output that users need to optionally save, organize, and retrieve later. Without a universal pattern, each feature implements its own save/discard logic inconsistently. This creates technical debt and poor UX.

**Core Principle:** Build the save/collect system FIRST. All features consume it.

---

#### A. Universal Save/Collect Modal

Every operation (scrape, skeleton, synthesis, future features) ends with a **consistent modal experience**:

```
┌─────────────────────────────────────────────────────────┐
│  ✓ Operation Complete                              [X]  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [Report/Data Preview - scrollable]                     │
│  - Shows the actual generated content                   │
│  - Same rendering as current center-column display      │
│  - But contained in modal instead                       │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [ ] Save to Library                                    │
│                                                         │
│  [ ] Add to Collection  →  [Select or Create ▼]         │
│      (auto-checks Save when selected)                   │
│                                                         │
│  ─────────────────────────────────────────────────      │
│                                                         │
│          [Discard]                    [Done]            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Behavior:**
| Action | Result |
|--------|--------|
| Save checked, Done | Asset saved to general library, no collection |
| Collection selected, Done | Asset saved + tagged with collection (Save auto-checked) |
| Neither checked, Done | Asset discarded (or temp storage 24h?) |
| Discard clicked | Asset immediately removed, modal closes |
| X clicked | Same as "Done" with current checkbox state |

**Reusable Component:**
```javascript
// Usage from ANY feature:
const result = await showSaveCollectModal({
  title: "Skeleton Analysis Complete",
  content: reportMarkdown,        // or React component
  assetType: "skeleton_report",   // for categorization
  metadata: { creators, videoCount, ... }
});

// result: { saved: bool, collectionId: string|null, discarded: bool }
```

---

#### B. Asset Storage System

**Data Model:**
```
Asset {
  id: uuid
  type: "scrape" | "skeleton" | "transcript" | "synthesis" | ...
  created_at: timestamp
  updated_at: timestamp

  // Core content
  content_path: string          // Path to actual file(s)
  preview: string               // Short preview for lists

  // Metadata (type-specific)
  metadata: {
    creators?: string[]
    platform?: string
    video_count?: int
    total_views?: int
    ...
  }

  // Organization
  collections: uuid[]           // Many-to-many
  tags: string[]                // Free-form tags
  starred: bool                 // Quick access
}

Collection {
  id: uuid
  name: string
  description: string
  color: string                 // For UI
  icon: string                  // Optional
  created_at: timestamp
  asset_count: int              // Denormalized for perf
}
```

**Storage Options:**
| Option | Pros | Cons |
|--------|------|------|
| SQLite | Fast queries, full-text search, scales well | Migration from current file-based |
| JSON + Index | Simple, no dependencies | Doesn't scale, slow search |
| TinyDB | Python-native, document-oriented | Less mature than SQLite |

**Recommendation:** SQLite with JSON columns for flexible metadata.

---

#### C. Library UI

New navigation item: **Library** (or "Assets" / "Saved")

**Views:**
1. **All Assets** - Chronological list with filters
2. **By Collection** - Grouped by collection with counts
3. **By Type** - Scrapes, Skeletons, Transcripts, etc.
4. **Starred** - Quick access favorites

**Capabilities:**
- Search (full-text across content + metadata)
- Filter by type, date range, collection, tags
- Sort by date, name, views, etc.
- Bulk actions (delete, move to collection, add tags)
- Preview pane or modal for quick view

---

#### D. Collection Management

**In-flow creation** (from Save/Collect modal):
- Dropdown shows existing collections + "Create New..."
- "Create New" expands inline: name input + optional color picker
- Created collection immediately selected

**Dedicated management** (from Library):
- List all collections with asset counts
- Edit name, description, color
- Delete collection (assets remain, just untagged)
- Merge collections

---

#### E. Implementation Phases

| Phase | Scope | Deliverable |
|-------|-------|-------------|
| **E1** | Data layer | SQLite schema, Asset/Collection models, basic CRUD |
| **E2** | Save/Collect modal | Reusable React component, hooks into existing features |
| **E3** | Library UI | Navigation, list views, basic search |
| **E4** | Migration | Move existing file-based data to SQLite |
| **E5** | Polish | Full-text search, bulk actions, advanced filters |

**Effort:** High (but amortized across all features)
**Status:** P0 - Build first

---
---

### 1. Hybrid Video Selection (Creators + Individual URLs)
**Source:** Partner feedback
**Problem:** Currently must analyze entire creator feeds. Want flexibility to mix creator top-N videos WITH hand-picked individual video URLs.

**Desired Workflow:**
1. Add creators (pulls their top N videos by views) — existing behavior
2. Add individual video URLs (Instagram/TikTok reel links)
3. Mix and match both in any combination
4. **Total cap: 25 videos** (current limit preserved)

**Options:**
| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Unified queue UI | Single input area showing running list of videos (from creators or direct URLs) with live count toward 25 | Clean UX, one mental model | Larger UI refactor |
| B) Two input sections | Keep creator input + add "Individual Videos" section below, both contribute to shared 25 cap | Incremental change, clear separation | Slightly fragmented UX |
| C) Modal-based queue builder | "Build Analysis" modal where you add creators/URLs, see queue, then launch | Focused experience | Extra click to start |

**Recommendation:** Option B first — minimal disruption to existing UI. Add URL input section below creators. Show running total: "12/25 videos queued". Can evolve to Option A later.

**Technical Notes:**
- Individual URLs bypass the "fetch top N" logic — direct download/transcribe
- Need URL validation (Instagram reel format, TikTok video format)
- Queue state: `{ creators: [...], individualUrls: [...] }` merged at analysis time

**Effort:** Medium
**Status:** Proposed

---

### 2. Collections & Save-on-Demand ⚠️ SUPERSEDED → See P0
**Source:** Partner feedback
**Problem:** Reports auto-save to history, creating clutter over time. No way to organize research by topic/client/project. History becomes unmanageable at scale.

> **Note:** This feature has been merged into P0 (Asset Management + Universal Save/Collect System)

**Options:**
| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Save-to-Collection flow | Report stays in "unsaved" state until user clicks "Save to Collection" and picks/creates a collection | Clean history, organized by user intent | Extra step before report persists |
| B) Auto-save + Move to Collection | Keep auto-save but add "Move to Collection" action after | No data loss risk | Still clutters history initially |
| C) Workspace model | Reports live in a "workspace" until filed or discarded | Familiar mental model (like email drafts) | More complex state management |

**Recommendation:** Option A — forces intentional organization. Unsaved reports could persist in session or temp storage with a "Recent (Unsaved)" section. Add "Discard" option for throwaway analysis.

**UX Flow:**
1. Analysis completes → Report shown in review mode
2. User reviews skeleton cards, synthesis, etc.
3. User clicks "Save to Collection" → Modal with collection picker/creator
4. OR clicks "Discard" → Gone (or moved to trash for 24h)
5. Saved reports appear in History grouped by Collection

**Effort:** Medium-High (new collection data model, UI for collection management)
**Status:** Proposed

---

### 3. Unified Asset Management System (Application-Wide) ⚠️ SUPERSEDED → See P0
**Source:** Partner feedback
**Problem:** Content is scattered across Mission History with minimal organization. No search, no filtering, no way to organize scraped creators, videos, transcripts, or reports. Becomes unmanageable as usage grows.

> **Note:** This feature has been merged into P0 (Asset Management + Universal Save/Collect System)

**Scope:** Entire ReelRecon application (not just Skeleton Ripper)

**Assets to Manage:**
- Creators (scraped profiles)
- Videos (downloaded reels)
- Transcripts (generated text)
- Mission reports (scrape results)
- Skeleton analysis reports

**Desired Capabilities:**
| Capability | Description |
|------------|-------------|
| **Search** | Full-text search across transcripts, creator names, report content |
| **Filter** | By date, creator, platform, asset type, tags |
| **Sort** | By date, views, name, custom order |
| **Organize** | Folders/collections, tags, favorites |
| **Save/Bookmark** | Mark important items for quick access |

**Options:**
| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Asset Library panel | New sidebar/section with unified asset browser, search bar, filters | Single source of truth | Significant UI addition |
| B) Enhanced History + Search | Keep existing structure but add global search bar + filters | Incremental, less disruptive | Still fragmented across features |
| C) Database-backed asset system | SQLite/JSON DB for all assets with proper indexing | Enables powerful queries, scales well | Backend work, migration needed |

**Recommendation:** Option C (backend) + Option A (frontend). Need proper data layer to support search/filter at scale. Current file-based storage won't scale.

**Technical Considerations:**
- SQLite for local structured storage (creators, videos, transcripts metadata)
- Full-text search index for transcript content
- Tags table (many-to-many with assets)
- Collections/folders as first-class entities
- Migrate existing file-based data on first run

**Effort:** High (foundational change)
**Status:** Proposed

---

### 4. One-Click Skeleton from Scraped Videos
**Source:** Partner feedback
**Problem:** Skeleton Ripper and basic scraper are separate workflows. After scraping a creator's videos, user must separately run Skeleton Ripper to analyze them. Want seamless integration.

**Desired Workflow:**
1. User runs basic scrape (Mission Control)
2. In results, each video has "Analyze Skeleton" button
3. One click → instant skeleton extraction for that video
4. Option to save the skeleton report to a collection

**Options:**
| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Inline skeleton button | Add button on each video in scrape results → calls skeleton API | Direct, contextual, fast | Need to handle async state per video |
| B) Bulk select + analyze | Checkbox videos in results → "Analyze Selected" button | Batch efficiency | Extra clicks |
| C) Auto-skeleton toggle | Option in scrape settings to auto-generate skeletons | Zero-click for power users | Slower scrapes, may not always want |

**Recommendation:** Option A first — most intuitive UX. Already have transcript (from scrape), so skeleton extraction is just the LLM call. Very fast for single video.

**Technical Notes:**
- Scrape results already have transcript data
- Can call `/api/skeleton-ripper/single` endpoint directly
- Result displays inline or in modal with save option
- Links to Collections feature (P2) for saving

**Effort:** Low-Medium (mostly frontend, reuse existing extraction)
**Status:** Proposed

---

### 5. Quick Scrape (Single Video Download/Transcribe)
**Source:** Partner feedback
**Problem:** Current "basic scrape" only works with creator handles (batch N videos). No way to quickly grab a single video by URL, transcribe it, and decide what to do with it afterward. Users want a lightweight entry point for ad-hoc video analysis.

**Desired Workflow:**
1. User pastes single video URL (Instagram/TikTok)
2. System downloads video + generates transcript
3. User reviews result in a "decision modal":
   - **Generate Skeleton** → Runs skeleton extraction, option to save
   - **Rewrite Script** → Opens in script rewriter tool
   - **Save for Later** → Files to collection for future use
   - **Discard** → Throws away (or trash for 24h)
4. Can chain actions: Skeleton → then Rewrite → then Save

**Naming Discussion:**
Current features need clearer naming:
| Current Name | Proposed Name | Description |
|--------------|---------------|-------------|
| "Basic Scrape" / "Mission Control" | **Creator Scrape** | Batch download top N videos from creator handle |
| _(new)_ | **Quick Scrape** | Single video URL download + transcribe |
| "Skeleton Ripper" | **Skeleton Ripper** (keep) | Pattern extraction from videos |

**Options:**
| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Standalone Quick Scrape page | New nav item "Quick Scrape" with URL input + decision modal | Clear separation, focused UX | Another nav item |
| B) Add to existing Mission Control | URL input tab alongside creator input | Consolidated, less nav clutter | May confuse existing flow |
| C) Universal URL bar | Persistent URL input in header, auto-detects intent | Fast access from anywhere | Complex routing logic |

**Recommendation:** Option A first — clean separation of concerns. "Creator Scrape" for batch, "Quick Scrape" for singles. Can consolidate later if needed.

**Technical Notes:**
- Reuse existing download/transcribe pipeline (already works for single videos)
- Decision modal is new UI component
- Ties into Collections feature (P2) for "Save for Later"
- Ties into Skeleton Ripper for "Generate Skeleton" action
- Script Rewriter integration (existing feature?)

**Effort:** Medium
**Status:** Proposed

---

### 6. _(Next idea)_
**Source:**
**Problem:**

**Options:**
| Option | Description | Pros | Cons |
|--------|-------------|------|------|

**Recommendation:**

**Effort:**
**Status:** Proposed

---

## Priority Matrix

| Feature | Value | Effort | Priority |
|---------|-------|--------|----------|
| **Asset Management + Save/Collect System** | Critical | High | **P0 (Foundation)** |
| Hybrid Video Selection (Creators + URLs) | High | Medium | **P1** |
| Quick Scrape (Single Video) | High | Medium | **P1** |
| One-Click Skeleton from Scrapes | High | Low-Medium | **P2** |
| | | | |

> **Note:** Collections & Save-on-Demand and Unified Asset Management merged into P0 foundation.

### Naming Convention (Proposed)
| Feature Area | Name |
|--------------|------|
| Batch creator download | **Creator Scrape** |
| Single URL download | **Quick Scrape** |
| Pattern extraction | **Skeleton Ripper** |
| Script modification | **Script Rewriter** |

---

## Immediate Next Steps

### Phase E1: Data Layer (Start Here)

1. **Explore current storage patterns**
   - Audit how Skeleton Ripper, Mission Control store data today
   - Document file structure and JSON schemas in use
   - Identify what needs migration

2. **Design SQLite schema**
   - `assets` table (id, type, content_path, preview, metadata JSON, starred, created_at, updated_at)
   - `collections` table (id, name, description, color, icon, created_at)
   - `asset_collections` junction table (asset_id, collection_id)
   - FTS5 virtual table for full-text search on content

3. **Build Python models**
   - `Asset` class with CRUD methods
   - `Collection` class with CRUD methods
   - Database initialization and migration utilities

4. **Create API routes**
   - `POST /api/assets` — Create asset
   - `GET /api/assets` — List/search assets
   - `GET /api/assets/<id>` — Get single asset
   - `PUT /api/assets/<id>` — Update asset
   - `DELETE /api/assets/<id>` — Delete asset
   - Same pattern for `/api/collections`

### Phase E2: Save/Collect Modal

1. **Build modal component** (HTML/JS)
2. **Wire to backend APIs**
3. **Integrate with Skeleton Ripper first** (proof of concept)
4. **Refactor other features to use modal**

### Phase E3+: Library UI, Migration, Polish

_(Details in P0 specification above)_

---

## Notes

### Architectural Decisions

1. **P0 Foundation First** — Asset management + save/collect system must be built before other features. All features depend on it.

2. **Universal Modal Pattern** — Every operation ends with the same Save/Collect modal. Build once, use everywhere. Reduces per-feature development time.

3. **SQLite for Storage** — JSON files don't scale. SQLite provides fast queries, full-text search, and proper indexing.

4. **Collections as Metadata** — Collections don't "contain" assets physically. They're tags/labels for organization. One asset can belong to multiple collections.

5. **Optional Save** — Nothing auto-saves. User explicitly chooses to save or discard. Prevents clutter.

### Superseded Features

- **Feature 2 (Collections & Save-on-Demand)** → Merged into P0
- **Feature 3 (Unified Asset Management)** → Merged into P0

### Open Questions

- [ ] Temp storage for unsaved assets (24h trash?)
- [ ] Export/backup functionality for collections?
- [ ] Sharing collections between users (future multi-user)?

