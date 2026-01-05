# Feature Spec: Discover Creators

**Status:** Ready for Implementation
**Priority:** High
**Created:** 2026-01-02
**Author:** Claude Code Session

---

## Overview

Add a "Discover Creators" feature to the ReelRecon workspace that allows users to search Instagram for creators by keyword and filter by follower count range. This enables users to find new creators to scrape without leaving the app.

### User Story

> As a ReelRecon user, I want to discover Instagram creators by searching keywords and filtering by follower count, so I can find relevant accounts to scrape without manually searching Instagram.

---

## What Already Exists

### `discover_creators.py` (COMPLETE)

A fully working standalone script located at `/mnt/c/Users/Chris/Documents/ReelRecon/discover_creators.py`.

**Core Functions:**

```python
# Cookie/Session handling (same pattern as core.py)
load_cookies(filepath)           # Loads Netscape cookies.txt format
create_session(cookies_path)     # Creates authenticated requests.Session

# Profile lookup via Instagram API
get_profile_info_api(session, username)  # Returns profile dict or None
format_follower_count(count)             # Formats 1500000 -> "1.5M"

# Search methods
search_instagram_api(session, keyword, max_results=50)  # Fast API search
search_hashtag_for_creators(page, keyword, max_profiles=30)  # Playwright fallback

# Main discovery function
async discover_creators(
    keyword: str,
    min_followers: int = 0,
    max_followers: int = 10000000,
    category_filter: str | None = None,
    limit: int = 10,
    cookies_path: str = 'cookies.txt',
    headless: bool = False
) -> list[dict]
```

**Return Data Structure:**

```python
{
    'username': str,           # e.g., "fitnessguru"
    'followers': int,          # e.g., 150000
    'followers_display': str,  # e.g., "150.0K"
    'full_name': str,          # e.g., "John Smith"
    'bio': str,                # Full bio text
    'category': str | None,    # e.g., "Fitness Model", "Coach"
    'is_verified': bool,
    'profile_pic': str,        # URL to profile picture
    'url': str                 # e.g., "https://www.instagram.com/fitnessguru/"
}
```

**Tested Successfully:**

```bash
python discover_creators.py --keyword fitness --min 100000 --max 500000 --limit 10 --output discovered_fitness.json
```

Result: 10 matching creators found and saved.

---

## Instagram API Endpoints Used

### 1. Search API (Primary)

```
GET https://www.instagram.com/web/search/topsearch/?query={keyword}
```

Returns users matching the keyword. Response includes:
- `users[]` array with username, full_name, is_verified, is_private, profile_pic_url

### 2. Profile Info API

```
GET https://www.instagram.com/api/v1/users/web_profile_info/?username={username}
```

Returns full profile data including:
- Follower count (`edge_followed_by.count`)
- Category (`category_name`)
- Bio (`biography`)
- Verification status

### Required Headers

```python
{
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'X-IG-App-ID': '936619743392459',
    'X-Requested-With': 'XMLHttpRequest',
    'X-ASBD-ID': '129477',
    'X-CSRFToken': cookies['csrftoken']  # From cookies.txt
}
```

### Critical Cookies

From `cookies.txt` (Netscape format):
- `sessionid` - Authentication session
- `csrftoken` - CSRF protection
- `ds_user_id` - User identifier
- `mid`, `ig_did`, `datr`, `rur` - Secondary tracking cookies

---

## Implementation Plan

### Files to Modify

| File | Changes |
|------|---------|
| `templates/workspace.html` | Add "Discover Creators" button to sidebar |
| `static/js/workspace.js` | Add modal render/setup functions |
| `static/js/utils/api.js` | Add `startDiscovery()` API method |
| `app.py` | Add `/api/discover` endpoint |

---

## 1. workspace.html Changes

**Location:** Sidebar Quick Actions section (lines 26-36)

**Add after "New Analysis" button:**

```html
<!-- Quick Actions -->
<div class="sidebar-section">
    <button id="btn-new-scrape" class="btn btn-primary btn-block">
        + New Scrape
    </button>
    <button id="btn-direct-reel" class="btn btn-secondary btn-block">
        + Direct Reel
    </button>
    <button id="btn-new-analysis" class="btn btn-secondary btn-block">
        + New Analysis
    </button>
    <!-- ADD THIS -->
    <button id="btn-discover-creators" class="btn btn-secondary btn-block">
        + Discover Creators
    </button>
</div>
```

---

## 2. api.js Changes

**Location:** `/static/js/utils/api.js`

**Add to API object (after `startAnalysis`):**

```javascript
// Creator Discovery
startDiscovery(data) {
    return request('/api/discover', { method: 'POST', body: data });
},

getDiscoveryStatus(id) {
    return request(`/api/discover/${id}/status`);
},
```

**Request Payload:**

```javascript
{
    keyword: string,        // Required: search term
    min_followers: number,  // Default: 0
    max_followers: number,  // Default: 10000000
    category: string|null,  // Optional: filter by category/bio match
    limit: number           // Default: 10, max: 50
}
```

**Response:**

```javascript
{
    success: true,
    job_id: string,  // For async polling
    // OR for sync response:
    creators: [
        {
            username: string,
            followers: number,
            followers_display: string,
            full_name: string,
            bio: string,
            category: string|null,
            is_verified: boolean,
            profile_pic: string,
            url: string
        }
    ]
}
```

---

## 3. workspace.js Changes

**Location:** `/static/js/workspace.js`

### 3.1 Add Button Event Listener

Find the `setupEventListeners()` function and add:

```javascript
document.getElementById('btn-discover-creators')?.addEventListener('click', () => {
    openModal(renderDiscoverModal());
    setupDiscoverModal();
});
```

### 3.2 Add Modal Render Function

```javascript
function renderDiscoverModal() {
    return `
        <div class="modal-header">
            <h2>Discover Creators</h2>
            <button class="btn-icon btn-close-modal">×</button>
        </div>
        <div class="modal-body">
            <div class="form-group">
                <label for="discover-keyword">Search Keyword</label>
                <input type="text" id="discover-keyword" placeholder="e.g., fitness, cooking, travel" required>
            </div>

            <div class="form-row">
                <div class="form-group">
                    <label for="discover-min-followers">Min Followers</label>
                    <input type="number" id="discover-min-followers" value="10000" min="0">
                </div>
                <div class="form-group">
                    <label for="discover-max-followers">Max Followers</label>
                    <input type="number" id="discover-max-followers" value="500000" min="0">
                </div>
            </div>

            <div class="form-group">
                <label for="discover-category">Category Filter (optional)</label>
                <input type="text" id="discover-category" placeholder="e.g., coach, trainer, creator">
                <small class="form-hint">Matches against Instagram category or bio text</small>
            </div>

            <div class="form-group">
                <label for="discover-limit">Number of Results</label>
                <select id="discover-limit">
                    <option value="10" selected>10 creators</option>
                    <option value="25">25 creators</option>
                    <option value="50">50 creators</option>
                </select>
            </div>
        </div>
        <div class="modal-footer">
            <button class="btn btn-secondary btn-close-modal">Cancel</button>
            <button id="btn-start-discovery" class="btn btn-primary">Search</button>
        </div>
    `;
}
```

### 3.3 Add Modal Setup Function

```javascript
function setupDiscoverModal() {
    const btnStart = document.getElementById('btn-start-discovery');

    btnStart?.addEventListener('click', async () => {
        const keyword = document.getElementById('discover-keyword').value.trim();
        const minFollowers = parseInt(document.getElementById('discover-min-followers').value) || 0;
        const maxFollowers = parseInt(document.getElementById('discover-max-followers').value) || 10000000;
        const category = document.getElementById('discover-category').value.trim() || null;
        const limit = parseInt(document.getElementById('discover-limit').value) || 10;

        if (!keyword) {
            alert('Please enter a search keyword');
            return;
        }

        if (minFollowers >= maxFollowers) {
            alert('Min followers must be less than max followers');
            return;
        }

        btnStart.disabled = true;
        btnStart.textContent = 'Searching...';

        try {
            const result = await API.startDiscovery({
                keyword,
                min_followers: minFollowers,
                max_followers: maxFollowers,
                category,
                limit
            });

            closeModal();

            if (result.creators && result.creators.length > 0) {
                // Show results modal or panel
                openModal(renderDiscoveryResultsModal(result.creators, keyword));
                setupDiscoveryResultsModal(result.creators);
            } else {
                alert('No creators found matching your criteria. Try adjusting the filters.');
            }
        } catch (error) {
            console.error('Discovery failed:', error);
            alert(`Discovery failed: ${error.message}`);
            btnStart.disabled = false;
            btnStart.textContent = 'Search';
        }
    });
}
```

### 3.4 Add Results Modal

```javascript
function renderDiscoveryResultsModal(creators, keyword) {
    const creatorCards = creators.map((c, i) => `
        <div class="discovery-result-card" data-username="${c.username}">
            <div class="discovery-result-avatar">
                <img src="${c.profile_pic}" alt="@${c.username}" onerror="this.src='/static/img/default-avatar.png'">
                ${c.is_verified ? '<span class="verified-badge">✓</span>' : ''}
            </div>
            <div class="discovery-result-info">
                <div class="discovery-result-header">
                    <strong>@${c.username}</strong>
                    <span class="follower-count">${c.followers_display}</span>
                </div>
                ${c.full_name ? `<div class="full-name">${c.full_name}</div>` : ''}
                ${c.category ? `<div class="category-tag">${c.category}</div>` : ''}
                ${c.bio ? `<div class="bio-preview">${c.bio.substring(0, 100)}${c.bio.length > 100 ? '...' : ''}</div>` : ''}
            </div>
            <div class="discovery-result-actions">
                <input type="checkbox" class="creator-select" data-username="${c.username}">
            </div>
        </div>
    `).join('');

    return `
        <div class="modal-header">
            <h2>Discovery Results: "${keyword}"</h2>
            <button class="btn-icon btn-close-modal">×</button>
        </div>
        <div class="modal-body discovery-results">
            <div class="discovery-results-header">
                <span>Found ${creators.length} creators</span>
                <label class="select-all-label">
                    <input type="checkbox" id="select-all-creators"> Select All
                </label>
            </div>
            <div class="discovery-results-list">
                ${creatorCards}
            </div>
        </div>
        <div class="modal-footer">
            <button class="btn btn-secondary btn-close-modal">Close</button>
            <button id="btn-scrape-selected" class="btn btn-primary" disabled>
                Scrape Selected (0)
            </button>
        </div>
    `;
}

function setupDiscoveryResultsModal(creators) {
    const selectAll = document.getElementById('select-all-creators');
    const scrapeBtn = document.getElementById('btn-scrape-selected');
    const checkboxes = document.querySelectorAll('.creator-select');

    function updateScrapeButton() {
        const selected = document.querySelectorAll('.creator-select:checked');
        scrapeBtn.textContent = `Scrape Selected (${selected.length})`;
        scrapeBtn.disabled = selected.length === 0;
    }

    selectAll?.addEventListener('change', (e) => {
        checkboxes.forEach(cb => cb.checked = e.target.checked);
        updateScrapeButton();
    });

    checkboxes.forEach(cb => {
        cb.addEventListener('change', updateScrapeButton);
    });

    scrapeBtn?.addEventListener('click', async () => {
        const selectedUsernames = Array.from(document.querySelectorAll('.creator-select:checked'))
            .map(cb => cb.dataset.username);

        if (selectedUsernames.length === 0) return;

        closeModal();

        // Start batch scrape with selected usernames
        try {
            await API.startBatchScrape({
                usernames: selectedUsernames,
                platform: 'instagram'
            });

            // Navigate to jobs view
            navigateTo('jobs');
        } catch (error) {
            console.error('Batch scrape failed:', error);
            alert(`Failed to start scrape: ${error.message}`);
        }
    });
}
```

---

## 4. app.py Changes

**Add Discovery Endpoint:**

```python
from discover_creators import discover_creators

@app.route('/api/discover', methods=['POST'])
async def api_discover():
    """
    Discover Instagram creators by keyword and follower range.
    """
    data = request.get_json()

    keyword = data.get('keyword')
    if not keyword:
        return jsonify({'error': 'keyword is required'}), 400

    min_followers = data.get('min_followers', 0)
    max_followers = data.get('max_followers', 10000000)
    category = data.get('category')
    limit = min(data.get('limit', 10), 50)  # Cap at 50

    try:
        creators = await discover_creators(
            keyword=keyword,
            min_followers=min_followers,
            max_followers=max_followers,
            category_filter=category,
            limit=limit,
            cookies_path='cookies.txt',
            headless=True
        )

        return jsonify({
            'success': True,
            'creators': creators,
            'count': len(creators)
        })

    except FileNotFoundError:
        return jsonify({'error': 'Authentication cookies not found. Please update cookies.txt'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

**Note:** Flask doesn't natively support async routes. Options:
1. Use `flask[async]` with `pip install flask[async]`
2. Use `asyncio.run()` wrapper
3. Refactor `discover_creators()` to be synchronous

**Synchronous Wrapper Option:**

```python
import asyncio

def run_discovery_sync(**kwargs):
    """Synchronous wrapper for async discover_creators."""
    return asyncio.run(discover_creators(**kwargs))

@app.route('/api/discover', methods=['POST'])
def api_discover():
    # ... validation ...

    creators = run_discovery_sync(
        keyword=keyword,
        min_followers=min_followers,
        max_followers=max_followers,
        category_filter=category,
        limit=limit,
        cookies_path='cookies.txt',
        headless=True
    )

    return jsonify({
        'success': True,
        'creators': creators,
        'count': len(creators)
    })
```

---

## 5. CSS Additions (Optional)

Add to `workspace.css`:

```css
/* Discovery Results Modal */
.discovery-results {
    max-height: 60vh;
    overflow-y: auto;
}

.discovery-results-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border-color);
}

.discovery-results-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}

.discovery-result-card {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.75rem;
    background: var(--card-bg);
    border-radius: 8px;
    border: 1px solid var(--border-color);
}

.discovery-result-avatar {
    position: relative;
    flex-shrink: 0;
}

.discovery-result-avatar img {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    object-fit: cover;
}

.verified-badge {
    position: absolute;
    bottom: -2px;
    right: -2px;
    background: #3897f0;
    color: white;
    font-size: 10px;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
}

.discovery-result-info {
    flex: 1;
    min-width: 0;
}

.discovery-result-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.follower-count {
    font-size: 0.875rem;
    color: var(--text-muted);
}

.full-name {
    font-size: 0.875rem;
    color: var(--text-secondary);
}

.category-tag {
    display: inline-block;
    font-size: 0.75rem;
    padding: 0.125rem 0.5rem;
    background: var(--accent-bg);
    color: var(--accent-color);
    border-radius: 4px;
    margin-top: 0.25rem;
}

.bio-preview {
    font-size: 0.8125rem;
    color: var(--text-muted);
    margin-top: 0.25rem;
    line-height: 1.4;
}

.discovery-result-actions {
    flex-shrink: 0;
}

.creator-select {
    width: 18px;
    height: 18px;
    cursor: pointer;
}

.form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
}

.form-hint {
    display: block;
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: 0.25rem;
}
```

---

## Testing Checklist

- [ ] Button appears in sidebar
- [ ] Modal opens on click
- [ ] Form validation works (keyword required, min < max)
- [ ] API endpoint returns creators
- [ ] Results display in modal
- [ ] Select all/individual selection works
- [ ] "Scrape Selected" triggers batch scrape
- [ ] Job appears in Jobs view
- [ ] Error states handled (no results, auth failure, rate limit)

---

## Rate Limiting Considerations

Instagram's API has rate limits. The script includes:
- 0.3s delay between profile lookups
- 5s wait on 429 responses
- Headless Playwright fallback for hashtag search

Consider adding:
- Request queuing for multiple discoveries
- Caching of recent search results
- User feedback on rate limit status

---

## Future Enhancements

1. **Save Searches** - Store search criteria for repeat use
2. **Export Results** - CSV/JSON export of discovered creators
3. **Profile Preview** - Click to see full profile in detail panel
4. **Follower Presets** - Quick buttons for common ranges (Micro: 10K-50K, Mid: 50K-200K, etc.)
5. **Category Dropdown** - Pre-populated Instagram category options
6. **Async Job Queue** - Run discovery in background like scraping jobs

---

## Related Files

| File | Purpose |
|------|---------|
| `discover_creators.py` | Core discovery logic |
| `scraper/core.py` | Reference for cookie/session patterns |
| `templates/workspace.html` | Main workspace template |
| `static/js/workspace.js` | Frontend logic |
| `static/js/utils/api.js` | API client |
| `app.py` | Flask backend |
| `cookies.txt` | Instagram authentication |
| `discovered_fitness.json` | Test output (10 fitness creators) |

---

## Session Context

This feature was developed in a Claude Code session on 2026-01-02. The standalone `discover_creators.py` script was created and tested successfully. Integration into the workspace UI was planned but not implemented.

Key decisions:
- Use Instagram's internal search API (fast, no browser needed)
- Fall back to Playwright hashtag scraping if API returns insufficient results
- Sync response (not async job queue) for simplicity
- Results modal with multi-select for batch scraping
