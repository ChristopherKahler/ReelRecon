# Changelog - 2026-01-04

## Modal Utilities - Reusable Drag & Resize System

### Overview

Added a reusable modal utility system (`ModalUtils`) that provides drag, resize, and server-side persistence functionality for any modal in the application. This replaces ad-hoc modal positioning with a consistent, maintainable approach.

### New Files

| File | Purpose |
|------|---------|
| `static/js/modal-utils.js` | Reusable drag/resize module |

### Modified Files

| File | Changes |
|------|---------|
| `static/css/workspace.css` | Added resize handles CSS (lines 6996-7093), responsive modal content styles |
| `app.py` | Added `/api/modal-bounds` GET/POST endpoints (lines 2004-2036) |
| `templates/workspace.html` | Added `modal-utils.js` script import |
| `static/js/workspace.js` | Added ModalUtils initialization for rewrite modal |

---

## Architecture: ModalUtils Module

### Purpose

Provides a declarative API to make any modal draggable and resizable with optional server-side persistence of position/size.

### Usage

```javascript
// Basic usage
ModalUtils.makeDraggableResizable('#myModal', {
    persistKey: 'myModalBounds',    // Server-side persistence key (optional)
    minWidth: 400,                  // Minimum width in pixels
    minHeight: 300,                 // Minimum height in pixels
    dragHandle: '.modal-header'     // Element to use as drag handle
});

// Returns control object
const modal = ModalUtils.makeDraggableResizable('#myModal', options);
modal.reset();           // Reset to default position/size
modal.getBounds();       // Get current {x, y, width, height}
modal.setBounds({...});  // Manually set bounds
modal.destroy();         // Remove functionality and cleanup
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `minWidth` | number | 400 | Minimum modal width |
| `minHeight` | number | 300 | Minimum modal height |
| `maxWidth` | number | null | Maximum width (null = viewport) |
| `maxHeight` | number | null | Maximum height (null = viewport) |
| `dragHandle` | string | '.modal-header' | CSS selector for drag handle |
| `contentSelector` | string | '.modal-content' | CSS selector for modal content |
| `persistKey` | string | null | Key for server-side persistence |
| `onResize` | function | null | Callback after resize |
| `onMove` | function | null | Callback after move |
| `onBoundsChange` | function | null | Callback after any bounds change |

### Features

1. **Dragging**: Click and drag the modal header to reposition
2. **Resizing**: 8 resize handles (4 corners + 4 edges) with appropriate cursors
3. **Constraints**: Modal cannot be dragged/resized outside viewport
4. **Minimum Size**: Enforced minimum dimensions prevent unusable states
5. **Server Persistence**: Position/size saved to server, restored on app restart
6. **Responsive Content**: Modal body scrolls when height is restricted

### Resize Handles

```
    [n]           ← North (top edge)
[nw]   [ne]       ← Northwest/Northeast corners
[w]       [e]     ← West/East edges
[sw]   [se]       ← Southwest/Southeast corners
    [s]           ← South (bottom edge)
```

### CSS Classes

| Class | Purpose |
|-------|---------|
| `.modal-draggable-resizable` | Applied to modal content when initialized |
| `.modal-drag-handle` | Applied to drag handle element |
| `.modal-dragging` | Applied during drag operation |
| `.modal-resizing` | Applied during resize operation |
| `.modal-resize-handles` | Container for resize handle elements |
| `.modal-resize-{n,ne,e,se,s,sw,w,nw}` | Individual resize handles |

### API Endpoints

#### GET `/api/modal-bounds/<key>`
Returns saved bounds for a modal.

**Response:**
```json
{
    "bounds": {
        "x": 100,
        "y": 50,
        "width": 800,
        "height": 600
    }
}
```

#### POST `/api/modal-bounds`
Saves modal bounds to server.

**Request:**
```json
{
    "key": "rewriteModalBounds",
    "bounds": {
        "x": 100,
        "y": 50,
        "width": 800,
        "height": 600
    }
}
```

**Response:**
```json
{
    "success": true
}
```

---

## Current Implementation

### Rewrite Modal

The AI Script Rewriter modal (`#rewriteModal`) is initialized with:

```javascript
ModalUtils.makeDraggableResizable('#rewriteModal', {
    persistKey: 'rewriteModalBounds',
    minWidth: 500,
    minHeight: 400,
    dragHandle: '.modal-header'
});
```

Location: `static/js/workspace.js:4194-4202`

---

## Future Use Cases

Apply to other modals as needed:

1. **Add to Collection Modal** (`#addCollectionModal`)
2. **Asset Detail Modal** (when implemented)
3. **Settings Modal** (on index.html)
4. **Confirm Dialogs** (optional)

### Example Addition

```javascript
// In workspace.js initialization
ModalUtils.makeDraggableResizable('#addCollectionModal', {
    persistKey: 'addCollectionModalBounds',
    minWidth: 350,
    minHeight: 250,
    dragHandle: '.modal-header'
});
```

---

## Other Changes (2026-01-04)

### Rewrite Button Added to Workspace

- Added "REWRITE WITH AI" button to scrape report accordion items
- Located in transcript section alongside COPY and SAVE TO LIBRARY buttons
- Opens rewrite wizard modal for script generation

### Files Modified

| File | Changes |
|------|---------|
| `static/js/workspace.js` | Added button HTML, all rewrite functions (lines 3601-4173), window exports |
| `static/css/workspace.css` | Added `.btn-rewrite-sm` styling |
| `templates/workspace.html` | Added rewrite modal HTML, removed broken `app.js` import |

### CSS Fixes

- Fixed `.btn-rewrite-sm:hover` using undefined `--color-accent-secondary` (changed to `--color-accent-hover`)
- Increased `.reel-section-actions` margin-top for better spacing

---

*Last updated: 2026-01-04 21:37 CST*
