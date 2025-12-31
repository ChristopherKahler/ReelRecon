/**
 * ReelRecon Workspace - Main Entry Point
 * V3.0 Unified Workspace UI
 */

import { Store } from './state/store.js';
import { Router } from './utils/router.js';
import { API } from './utils/api.js';

// Initialize app when DOM ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('[Workspace] Initializing ReelRecon v3.0...');

    // Initialize store
    Store.init();

    // Initialize router
    Router.init();

    // Set up event listeners
    setupEventListeners();

    // Load initial data (non-blocking)
    loadInitialData();

    console.log('[Workspace] Ready.');
});

function setupEventListeners() {
    // Quick action buttons
    const newScrapeBtn = document.getElementById('btn-new-scrape');
    const newAnalysisBtn = document.getElementById('btn-new-analysis');

    if (newScrapeBtn) {
        newScrapeBtn.addEventListener('click', () => {
            console.log('[Workspace] New Scrape clicked');
            Store.dispatch({ type: 'SET_MODAL', payload: 'new-scrape' });
            // TODO: Open modal in Phase 3
        });
    }

    if (newAnalysisBtn) {
        newAnalysisBtn.addEventListener('click', () => {
            console.log('[Workspace] New Analysis clicked');
            Store.dispatch({ type: 'SET_MODAL', payload: 'new-analysis' });
            // TODO: Open modal in Phase 3
        });
    }

    // Filter chips
    document.querySelectorAll('.filter-chip').forEach(chip => {
        chip.addEventListener('click', (e) => {
            // Remove active from all chips
            document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
            // Add active to clicked chip
            e.target.classList.add('active');
            // Update filter
            const filterType = e.target.dataset.filterType || null;
            Store.dispatch({ type: 'SET_FILTER', payload: { type: filterType } });
            console.log('[Workspace] Filter changed:', filterType || 'all');
        });
    });

    // Search input
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        let debounceTimer;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                Store.dispatch({ type: 'SET_FILTER', payload: { search: e.target.value } });
                console.log('[Workspace] Search:', e.target.value);
            }, 300);
        });
    }

    // Tab switching (Jobs view)
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');
            console.log('[Workspace] Tab switched:', e.target.dataset.tab);
        });
    });

    // Detail panel controls
    const closeDetailBtn = document.getElementById('btn-close-detail');
    const starAssetBtn = document.getElementById('btn-star-asset');
    const copyAssetBtn = document.getElementById('btn-copy-asset');
    const deleteAssetBtn = document.getElementById('btn-delete-asset');

    if (closeDetailBtn) {
        closeDetailBtn.addEventListener('click', closeAssetDetail);
    }

    if (starAssetBtn) {
        starAssetBtn.addEventListener('click', toggleStarAsset);
    }

    if (copyAssetBtn) {
        copyAssetBtn.addEventListener('click', copyAssetContent);
    }

    if (deleteAssetBtn) {
        deleteAssetBtn.addEventListener('click', deleteAsset);
    }

    // Close detail panel with Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const panel = document.getElementById('detail-panel');
            if (panel.classList.contains('open')) {
                closeAssetDetail();
            }
        }
    });
}

async function loadInitialData() {
    try {
        // Load collections for sidebar
        const collectionsResponse = await API.getCollections();
        const collections = collectionsResponse.collections || collectionsResponse || [];
        Store.dispatch({ type: 'SET_COLLECTIONS', payload: collections });
        renderCollections(collections);
        console.log('[Workspace] Loaded', collections.length, 'collections');

        // Load initial assets
        const assetsResponse = await API.getAssets();
        const assets = assetsResponse.assets || assetsResponse || [];
        Store.dispatch({ type: 'SET_ASSETS', payload: assets });
        renderAssets(assets);
        console.log('[Workspace] Loaded', assets.length, 'assets');

        // Update sidebar count
        updateAssetCount(assets.length);
    } catch (error) {
        console.warn('[Workspace] Failed to load initial data:', error.message);
        renderAssets([]); // Show empty state
    }
}

// Subscribe to store changes for filtering
Store.subscribe((state) => {
    const filtered = filterAssets(state.assets, state.filters);
    renderAssets(filtered);
});

function filterAssets(assets, filters) {
    let result = assets;

    if (filters.type) {
        result = result.filter(a => a.type === filters.type);
    }

    if (filters.search) {
        const query = filters.search.toLowerCase();
        result = result.filter(a =>
            (a.title && a.title.toLowerCase().includes(query)) ||
            (a.preview && a.preview.toLowerCase().includes(query))
        );
    }

    return result;
}

function renderAssets(assets) {
    const grid = document.getElementById('asset-grid');
    if (!grid) return;

    if (!assets || assets.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <p>No assets yet. Start a scrape or analysis to populate your library.</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = assets.map(asset => renderAssetCard(asset)).join('');

    // Add click handlers to cards
    grid.querySelectorAll('.asset-card').forEach(card => {
        card.addEventListener('click', () => {
            const assetId = card.dataset.assetId;
            openAssetDetail(assetId);
        });
    });
}

function renderAssetCard(asset) {
    const typeLabels = {
        'skeleton': 'Skeleton',
        'transcript': 'Transcript',
        'skeleton_report': 'Analysis',
        'scrape_report': 'Scrape',
        'synthesis': 'Synthesis'
    };

    const typeColors = {
        'skeleton': '#8B5CF6',
        'transcript': '#3B82F6',
        'skeleton_report': '#10B981',
        'scrape_report': '#F59E0B',
        'synthesis': '#EC4899'
    };

    const typeLabel = typeLabels[asset.type] || asset.type;
    const typeColor = typeColors[asset.type] || '#6B7280';
    const preview = asset.preview ? asset.preview.substring(0, 120) + '...' : 'No preview available';
    const date = asset.created_at ? new Date(asset.created_at).toLocaleDateString() : '';

    return `
        <div class="asset-card" data-asset-id="${asset.id}">
            <div class="asset-card-header">
                <span class="asset-type-badge" style="background: ${typeColor}20; color: ${typeColor}">
                    ${typeLabel}
                </span>
                ${asset.starred ? '<span class="asset-starred">★</span>' : ''}
            </div>
            <h3 class="asset-title">${asset.title || 'Untitled'}</h3>
            <p class="asset-preview">${preview}</p>
            <div class="asset-meta">
                <span class="asset-date">${date}</span>
            </div>
        </div>
    `;
}

function renderCollections(collections) {
    const list = document.getElementById('collections-list');
    if (!list) return;

    const allAssetsItem = `
        <div class="collection-item active" data-collection-id="">
            <span class="collection-color" style="background: #6366f1"></span>
            <span>All Assets</span>
            <span class="collection-count">0</span>
        </div>
    `;

    const collectionItems = collections.map(col => `
        <div class="collection-item" data-collection-id="${col.id}">
            <span class="collection-color" style="background: ${col.color || '#6366f1'}"></span>
            <span>${col.name}</span>
            <span class="collection-count">${col.asset_count || 0}</span>
        </div>
    `).join('');

    list.innerHTML = allAssetsItem + collectionItems;

    // Add click handlers
    list.querySelectorAll('.collection-item').forEach(item => {
        item.addEventListener('click', () => {
            list.querySelectorAll('.collection-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            const collectionId = item.dataset.collectionId || null;
            Store.dispatch({ type: 'SET_FILTER', payload: { collection: collectionId } });
            // Reload assets with collection filter
            reloadAssets({ collection: collectionId });
        });
    });
}

async function reloadAssets(filters = {}) {
    try {
        const response = await API.getAssets(filters);
        const assets = response.assets || response || [];
        Store.dispatch({ type: 'SET_ASSETS', payload: assets });
        renderAssets(assets);
        updateAssetCount(assets.length);
    } catch (error) {
        console.warn('[Workspace] Failed to reload assets:', error.message);
    }
}

async function openAssetDetail(assetId) {
    console.log('[Workspace] Opening asset:', assetId);
    Store.dispatch({ type: 'SELECT_ASSET', payload: assetId });

    const panel = document.getElementById('detail-panel');
    const content = document.getElementById('detail-panel-content');

    // Show loading state
    content.innerHTML = '<div class="detail-loading">Loading...</div>';
    panel.classList.add('open');

    try {
        // Fetch full asset data
        const asset = await API.getAsset(assetId);
        renderDetailPanel(asset);
    } catch (error) {
        console.error('[Workspace] Failed to load asset:', error);
        content.innerHTML = '<div class="detail-loading">Failed to load asset</div>';
    }
}

function closeAssetDetail() {
    const panel = document.getElementById('detail-panel');
    panel.classList.remove('open');
    Store.dispatch({ type: 'SELECT_ASSET', payload: null });
}

function renderDetailPanel(asset) {
    const content = document.getElementById('detail-panel-content');
    const starBtn = document.getElementById('btn-star-asset');

    const typeLabels = {
        'skeleton': 'Skeleton',
        'transcript': 'Transcript',
        'skeleton_report': 'Analysis Report',
        'scrape_report': 'Scrape Report',
        'synthesis': 'Synthesis'
    };

    const typeColors = {
        'skeleton': '#8B5CF6',
        'transcript': '#3B82F6',
        'skeleton_report': '#10B981',
        'scrape_report': '#F59E0B',
        'synthesis': '#EC4899'
    };

    const typeLabel = typeLabels[asset.type] || asset.type;
    const typeColor = typeColors[asset.type] || '#6B7280';
    const createdDate = asset.created_at ? new Date(asset.created_at).toLocaleString() : 'Unknown';

    // Update star button state
    if (starBtn) {
        starBtn.textContent = asset.starred ? '★' : '☆';
        starBtn.classList.toggle('starred', asset.starred);
    }

    // Store current asset ID for actions
    content.dataset.assetId = asset.id;

    content.innerHTML = `
        <div class="detail-section">
            <span class="asset-type-badge" style="background: ${typeColor}20; color: ${typeColor}">
                ${typeLabel}
            </span>
            <h2 class="detail-title">${asset.title || 'Untitled'}</h2>
            <div class="detail-meta">
                <div class="detail-meta-item">
                    <span class="detail-meta-label">Created:</span>
                    <span>${createdDate}</span>
                </div>
                ${asset.source_url ? `
                <div class="detail-meta-item">
                    <span class="detail-meta-label">Source:</span>
                </div>
                ` : ''}
            </div>
            ${asset.source_url ? `
            <div class="detail-source">
                <a href="${asset.source_url}" target="_blank" rel="noopener">${asset.source_url}</a>
            </div>
            ` : ''}
        </div>

        <div class="detail-section">
            <div class="detail-section-title">Content</div>
            <div class="detail-body-content">
                <div class="detail-body">${escapeHtml(asset.content || asset.preview || 'No content available')}</div>
            </div>
        </div>

        ${asset.metadata ? `
        <div class="detail-section">
            <div class="detail-section-title">Metadata</div>
            <div class="detail-body-content">
                <pre class="detail-body">${JSON.stringify(asset.metadata, null, 2)}</pre>
            </div>
        </div>
        ` : ''}
    `;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function toggleStarAsset() {
    const content = document.getElementById('detail-panel-content');
    const assetId = content.dataset.assetId;
    if (!assetId) return;

    try {
        const result = await API.toggleStar(assetId);
        const starBtn = document.getElementById('btn-star-asset');
        if (starBtn) {
            starBtn.textContent = result.starred ? '★' : '☆';
            starBtn.classList.toggle('starred', result.starred);
        }
        // Update in store
        const state = Store.getState();
        const assets = state.assets.map(a =>
            a.id === assetId ? { ...a, starred: result.starred } : a
        );
        Store.dispatch({ type: 'SET_ASSETS', payload: assets });
        console.log('[Workspace] Toggled star:', result.starred);
    } catch (error) {
        console.error('[Workspace] Failed to toggle star:', error);
    }
}

async function copyAssetContent() {
    const content = document.getElementById('detail-panel-content');
    const bodyEl = content.querySelector('.detail-body');
    if (!bodyEl) return;

    try {
        await navigator.clipboard.writeText(bodyEl.textContent);
        const copyBtn = document.getElementById('btn-copy-asset');
        if (copyBtn) {
            const original = copyBtn.textContent;
            copyBtn.textContent = '✓';
            setTimeout(() => copyBtn.textContent = original, 1500);
        }
        console.log('[Workspace] Content copied to clipboard');
    } catch (error) {
        console.error('[Workspace] Failed to copy:', error);
    }
}

async function deleteAsset() {
    const content = document.getElementById('detail-panel-content');
    const assetId = content.dataset.assetId;
    if (!assetId) return;

    if (!confirm('Are you sure you want to delete this asset?')) return;

    try {
        await API.deleteAsset(assetId);
        closeAssetDetail();
        // Remove from store
        const state = Store.getState();
        const assets = state.assets.filter(a => a.id !== assetId);
        Store.dispatch({ type: 'SET_ASSETS', payload: assets });
        updateAssetCount(assets.length);
        console.log('[Workspace] Asset deleted:', assetId);
    } catch (error) {
        console.error('[Workspace] Failed to delete:', error);
        alert('Failed to delete asset');
    }
}

function updateAssetCount(count) {
    const countEl = document.querySelector('.collection-item.active .collection-count');
    if (countEl) {
        countEl.textContent = count;
    }
}

// Export for debugging
window.ReelRecon = { Store, Router, API };
