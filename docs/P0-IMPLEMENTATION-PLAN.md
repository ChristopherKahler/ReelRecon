# P0: Asset Management + Save/Collect System
## Implementation Plan with Validation Checkpoints

**Branch:** `feature/asset-management`
**Target Version:** v2.2.0

---

## Phase E1: Data Layer

### Task E1.1: Audit Current Storage
- [ ] Document output/ directory structure
- [ ] Document skeleton_ripper output format
- [ ] Document scrape_history.json schema
- [ ] List all JSON files that store state
- [ ] Identify migration requirements

**Validation:** Summary document of current storage patterns
**Commit:** `chore(p0): audit current storage patterns`

---

### Task E1.2: Create SQLite Schema
```sql
-- assets table
CREATE TABLE assets (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,  -- 'scrape', 'skeleton', 'transcript', 'synthesis'
    title TEXT,
    content_path TEXT,
    preview TEXT,
    metadata JSON,
    starred INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- collections table
CREATE TABLE collections (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    color TEXT DEFAULT '#6366f1',
    icon TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- junction table
CREATE TABLE asset_collections (
    asset_id TEXT,
    collection_id TEXT,
    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (asset_id, collection_id),
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE
);

-- FTS5 for search
CREATE VIRTUAL TABLE assets_fts USING fts5(
    title, preview, content_path, content='assets'
);
```

**Validation:** Schema runs without errors, tables created
**Commit:** `feat(p0): add SQLite schema for assets and collections`

---

### Task E1.3: Create Python Models
```
storage/
├── __init__.py
├── database.py      # SQLite connection, init
├── models.py        # Asset, Collection classes
└── migrations.py    # Data migration utilities
```

**Models:**
- `Asset` - CRUD: create, get, list, update, delete, search
- `Collection` - CRUD: create, get, list, update, delete
- `AssetCollection` - add_to_collection, remove_from_collection

**Validation:**
- [ ] Unit tests pass for Asset CRUD
- [ ] Unit tests pass for Collection CRUD
- [ ] Database initializes on first run
- [ ] Can create, read, update, delete assets
- [ ] Can add/remove assets from collections

**Commit:** `feat(p0): add storage module with Asset and Collection models`

---

### Task E1.4: Create API Routes
```python
# /api/assets
POST   /api/assets              # Create asset
GET    /api/assets              # List assets (with filters)
GET    /api/assets/<id>         # Get single asset
PUT    /api/assets/<id>         # Update asset
DELETE /api/assets/<id>         # Delete asset
GET    /api/assets/search       # Full-text search

# /api/collections
POST   /api/collections         # Create collection
GET    /api/collections         # List collections
GET    /api/collections/<id>    # Get collection with assets
PUT    /api/collections/<id>    # Update collection
DELETE /api/collections/<id>    # Delete collection

# /api/assets/<id>/collections
POST   /api/assets/<id>/collections    # Add to collection
DELETE /api/assets/<id>/collections/<cid>  # Remove from collection
```

**Validation:**
- [ ] All endpoints return correct status codes
- [ ] Create asset via API works
- [ ] List assets returns JSON array
- [ ] Search returns relevant results
- [ ] Collection CRUD works via API

**Commit:** `feat(p0): add API routes for assets and collections`

---

## Phase E2: Save/Collect Modal

### Task E2.1: Build Modal Component
```
templates/components/
└── save_collect_modal.html    # Jinja2 partial

static/js/
└── save_collect.js            # Modal logic
```

**Features:**
- [ ] Preview pane (scrollable)
- [ ] "Save to Library" checkbox
- [ ] "Add to Collection" dropdown
- [ ] "Create New Collection" inline form
- [ ] "Discard" and "Done" buttons
- [ ] Auto-check Save when collection selected

**Validation:**
- [ ] Modal opens/closes correctly
- [ ] Checkboxes work
- [ ] Dropdown populates with collections
- [ ] Create new collection works inline
- [ ] Returns correct result object

**Commit:** `feat(p0): add universal Save/Collect modal component`

---

### Task E2.2: Integrate with Skeleton Ripper
- [ ] Replace current results display with modal trigger
- [ ] Pass skeleton report to modal
- [ ] Save skeleton as asset via API
- [ ] Discard removes temp files

**Validation:**
- [ ] Skeleton analysis shows modal on complete
- [ ] Saving creates asset in database
- [ ] Asset appears in Library (E3)
- [ ] Discard works without saving

**Commit:** `feat(p0): integrate Save/Collect modal with Skeleton Ripper`

---

## Phase E3: Library UI

### Task E3.1: Add Library Navigation
- [ ] Add "Library" nav item to index.html
- [ ] Create templates/library.html
- [ ] Add /library route to app.py

**Commit:** `feat(p0): add Library navigation and page shell`

---

### Task E3.2: Build List View
- [ ] Asset cards with preview
- [ ] Type icons (scrape, skeleton, transcript)
- [ ] Date, title, collection badges
- [ ] Click to open/view asset

**Commit:** `feat(p0): add Library asset list view`

---

### Task E3.3: Add Search and Filters
- [ ] Search bar with FTS5 query
- [ ] Filter by type dropdown
- [ ] Filter by collection dropdown
- [ ] Sort by date/name

**Commit:** `feat(p0): add Library search and filters`

---

### Task E3.4: Collection Management
- [ ] Collection sidebar
- [ ] Create/edit/delete collections
- [ ] Collection detail view with assets

**Commit:** `feat(p0): add collection management UI`

---

## Phase E4: Migration

### Task E4.1: Migrate Existing Data
- [ ] Scan output/ for existing scrapes
- [ ] Scan skeleton_ripper output
- [ ] Import scrape_history.json
- [ ] Create assets for existing files
- [ ] Mark migration complete flag

**Validation:**
- [ ] Existing data appears in Library
- [ ] No duplicate imports on re-run
- [ ] Original files unchanged

**Commit:** `feat(p0): migrate existing file-based data to SQLite`

---

## Summary Checkpoints

| Phase | Commits | Validation |
|-------|---------|------------|
| E1.1 | Audit storage | Documentation complete |
| E1.2 | SQLite schema | Tables created |
| E1.3 | Python models | CRUD tests pass |
| E1.4 | API routes | Endpoints respond correctly |
| E2.1 | Modal component | UI works |
| E2.2 | Skeleton integration | Save/discard works |
| E3.1 | Library nav | Page loads |
| E3.2 | List view | Assets display |
| E3.3 | Search/filter | Queries work |
| E3.4 | Collection UI | CRUD works |
| E4.1 | Migration | Existing data visible |

---

## Start Command

```bash
cd /mnt/c/Users/Chris/Documents/ReelRecon
git checkout feature/asset-management
# Begin with E1.1: Audit current storage
```
