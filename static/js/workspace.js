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
            openModal('new-scrape');
        });
    }

    if (newAnalysisBtn) {
        newAnalysisBtn.addEventListener('click', () => {
            console.log('[Workspace] New Analysis clicked');
            openModal('new-analysis');
        });
    }

    // Filter chips - multi-select
    document.querySelectorAll('.filter-chip').forEach(chip => {
        chip.addEventListener('click', (e) => {
            const clickedType = e.target.dataset.filterType || null;
            const allChip = document.querySelector('.filter-chip[data-filter-type=""]');

            if (!clickedType) {
                // Clicked "All" - clear all selections
                document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
                e.target.classList.add('active');
                Store.dispatch({ type: 'SET_FILTER', payload: { types: [] } });
            } else {
                // Toggle this chip
                e.target.classList.toggle('active');
                // Remove "All" active state
                allChip.classList.remove('active');

                // Gather all active types
                const activeTypes = Array.from(document.querySelectorAll('.filter-chip.active'))
                    .map(c => c.dataset.filterType)
                    .filter(t => t); // exclude empty string

                // If none selected, reactivate "All"
                if (activeTypes.length === 0) {
                    allChip.classList.add('active');
                }

                Store.dispatch({ type: 'SET_FILTER', payload: { types: activeTypes } });
            }
            console.log('[Workspace] Filters changed:', Store.getState().filters.types || 'all');
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

    // Close detail panel or modal with Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            // Check modal first (higher z-index)
            const modalOverlay = document.getElementById('modal-overlay');
            if (modalOverlay.classList.contains('open')) {
                closeModal();
                return;
            }

            // Then check detail panel
            const panel = document.getElementById('detail-panel');
            if (panel.classList.contains('open')) {
                closeAssetDetail();
            }
        }
    });

    // Close modal when clicking overlay
    const modalOverlay = document.getElementById('modal-overlay');
    if (modalOverlay) {
        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay) {
                closeModal();
            }
        });
    }
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

    // Multi-select type filter - show assets matching ANY selected type
    if (filters.types && filters.types.length > 0) {
        result = result.filter(a => filters.types.includes(a.type));
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

    // Render collection tags
    const collections = asset.collections || [];
    const collectionTags = collections.map(col => `
        <span class="collection-tag" style="background: ${col.color || '#6366f1'}20; color: ${col.color || '#6366f1'}; border-color: ${col.color || '#6366f1'}40">
            ${col.name}
        </span>
    `).join('');

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
            ${collections.length > 0 ? `<div class="asset-collections">${collectionTags}</div>` : ''}
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

// =========================================
// MODAL SYSTEM (Phase 3)
// =========================================

function openModal(modalType) {
    const overlay = document.getElementById('modal-overlay');
    const content = document.getElementById('modal-content');

    // Prevent body scroll
    document.body.style.overflow = 'hidden';

    // Render modal content
    if (modalType === 'new-scrape') {
        content.innerHTML = renderNewScrapeModal();
        setupNewScrapeModal();
    } else if (modalType === 'new-analysis') {
        content.innerHTML = renderNewAnalysisModal();
        setupNewAnalysisModal();
    }

    overlay.classList.add('open');
    Store.dispatch({ type: 'SET_MODAL', payload: modalType });
}

function closeModal() {
    const overlay = document.getElementById('modal-overlay');
    document.body.style.overflow = '';
    overlay.classList.remove('open');
    Store.dispatch({ type: 'SET_MODAL', payload: null });
}

// New Scrape Modal
function renderNewScrapeModal() {
    return `
        <div class="modal-header">
            <h2 class="modal-title">New Scrape</h2>
            <button class="btn-icon" id="btn-close-modal">×</button>
        </div>
        <div class="modal-body">
            <div id="modal-error" class="modal-error" style="display: none;"></div>

            <div class="form-group">
                <label class="form-label">Platform</label>
                <div class="toggle-group">
                    <button type="button" class="toggle-btn active" data-platform="instagram">Instagram</button>
                    <button type="button" class="toggle-btn" data-platform="tiktok">TikTok</button>
                </div>
            </div>

            <div class="form-group">
                <label class="form-label">Username</label>
                <input type="text" id="scrape-username" class="form-input" placeholder="@username or profile URL">
                <p class="form-hint">Enter username without @ or paste profile URL</p>
            </div>

            <div class="form-group">
                <label class="form-label">Number of Reels</label>
                <div class="number-input-group">
                    <input type="number" id="scrape-count" class="form-input" value="5" min="1" max="20">
                    <span class="form-hint">Max 20</span>
                </div>
            </div>

            <div class="form-group">
                <label class="form-label">Date Range</label>
                <select id="scrape-date-range" class="form-select">
                    <option value="">All time</option>
                    <option value="30">Last 30 days</option>
                    <option value="60">Last 60 days</option>
                    <option value="90">Last 90 days</option>
                </select>
            </div>

            <div class="form-group">
                <label class="checkbox-group">
                    <input type="checkbox" id="scrape-transcribe" checked>
                    <span>Transcribe audio with Whisper</span>
                </label>
            </div>
        </div>
        <div class="modal-footer">
            <button class="btn btn-secondary" id="btn-cancel-scrape">Cancel</button>
            <button class="btn btn-primary" id="btn-start-scrape">Start Scrape</button>
        </div>
    `;
}

function setupNewScrapeModal() {
    // Close buttons
    document.getElementById('btn-close-modal').addEventListener('click', closeModal);
    document.getElementById('btn-cancel-scrape').addEventListener('click', closeModal);

    // Platform toggle
    document.querySelectorAll('.toggle-btn[data-platform]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.toggle-btn[data-platform]').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
        });
    });

    // Start scrape
    document.getElementById('btn-start-scrape').addEventListener('click', startScrape);
}

async function startScrape() {
    const errorEl = document.getElementById('modal-error');
    const submitBtn = document.getElementById('btn-start-scrape');

    // Get form values
    const platform = document.querySelector('.toggle-btn[data-platform].active').dataset.platform;
    const username = document.getElementById('scrape-username').value.trim();
    const count = parseInt(document.getElementById('scrape-count').value) || 5;
    const dateRange = document.getElementById('scrape-date-range').value;
    const transcribe = document.getElementById('scrape-transcribe').checked;

    // Validate
    if (!username) {
        errorEl.textContent = 'Please enter a username';
        errorEl.style.display = 'block';
        return;
    }

    // Show loading
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Starting...';
    errorEl.style.display = 'none';

    try {
        const result = await API.startScrape({
            platform,
            username: username.replace('@', ''),
            count,
            date_range_days: dateRange ? parseInt(dateRange) : null,
            transcribe
        });

        console.log('[Workspace] Scrape started:', result);
        closeModal();

        // Navigate to jobs view
        window.location.hash = '#jobs';
    } catch (error) {
        console.error('[Workspace] Failed to start scrape:', error);
        errorEl.textContent = error.message || 'Failed to start scrape';
        errorEl.style.display = 'block';
        submitBtn.disabled = false;
        submitBtn.textContent = 'Start Scrape';
    }
}

// New Analysis Modal (Skeleton Ripper)
function renderNewAnalysisModal() {
    return `
        <div class="modal-header">
            <h2 class="modal-title">New Analysis</h2>
            <button class="btn-icon" id="btn-close-modal">×</button>
        </div>
        <div class="modal-body">
            <div id="modal-error" class="modal-error" style="display: none;"></div>

            <div class="form-group">
                <label class="form-label">Creators to Analyze</label>
                <div id="creators-list" class="multi-input-list">
                    <div class="multi-input-row">
                        <input type="text" class="form-input creator-input" placeholder="@username">
                    </div>
                </div>
                <button type="button" id="btn-add-creator" class="btn-add-row">+ Add Creator</button>
                <p class="form-hint">Up to 5 creators</p>
            </div>

            <div class="form-group">
                <label class="form-label">Videos per Creator</label>
                <div class="number-input-group">
                    <input type="number" id="analysis-videos" class="form-input" value="3" min="1" max="10">
                    <span class="form-hint">1-10 videos</span>
                </div>
            </div>

            <div class="form-group">
                <label class="form-label">LLM Provider</label>
                <select id="analysis-provider" class="form-select">
                    <option value="">Loading providers...</option>
                </select>
            </div>

            <div class="form-group">
                <label class="form-label">Model</label>
                <select id="analysis-model" class="form-select" disabled>
                    <option value="">Select a provider first</option>
                </select>
            </div>
        </div>
        <div class="modal-footer">
            <button class="btn btn-secondary" id="btn-cancel-analysis">Cancel</button>
            <button class="btn btn-primary" id="btn-start-analysis">Start Analysis</button>
        </div>
    `;
}

async function setupNewAnalysisModal() {
    // Close buttons
    document.getElementById('btn-close-modal').addEventListener('click', closeModal);
    document.getElementById('btn-cancel-analysis').addEventListener('click', closeModal);

    // Add creator button
    document.getElementById('btn-add-creator').addEventListener('click', () => {
        const list = document.getElementById('creators-list');
        const rows = list.querySelectorAll('.multi-input-row');
        if (rows.length >= 5) return;

        const row = document.createElement('div');
        row.className = 'multi-input-row';
        row.innerHTML = `
            <input type="text" class="form-input creator-input" placeholder="@username">
            <button type="button" class="btn-remove-row">×</button>
        `;
        list.appendChild(row);

        row.querySelector('.btn-remove-row').addEventListener('click', () => row.remove());
    });

    // Load providers
    try {
        const providersData = await API.getProviders();
        const providers = providersData.providers || providersData || [];
        const providerSelect = document.getElementById('analysis-provider');

        providerSelect.innerHTML = '<option value="">Select a provider</option>' +
            providers.map(p => `<option value="${p.id}" data-models='${JSON.stringify(p.models)}'>${p.name}</option>`).join('');

        // Provider change handler
        providerSelect.addEventListener('change', (e) => {
            const modelSelect = document.getElementById('analysis-model');
            const option = e.target.selectedOptions[0];

            if (!option.value) {
                modelSelect.disabled = true;
                modelSelect.innerHTML = '<option value="">Select a provider first</option>';
                return;
            }

            const models = JSON.parse(option.dataset.models || '[]');
            modelSelect.disabled = false;
            modelSelect.innerHTML = models.map(m => `<option value="${m.id}">${m.name}</option>`).join('');
        });
    } catch (error) {
        console.error('[Workspace] Failed to load providers:', error);
        document.getElementById('analysis-provider').innerHTML = '<option value="">Failed to load</option>';
    }

    // Start analysis
    document.getElementById('btn-start-analysis').addEventListener('click', startAnalysis);
}

async function startAnalysis() {
    const errorEl = document.getElementById('modal-error');
    const submitBtn = document.getElementById('btn-start-analysis');

    // Get creators
    const creatorInputs = document.querySelectorAll('.creator-input');
    const creators = Array.from(creatorInputs)
        .map(input => input.value.trim().replace('@', ''))
        .filter(c => c.length > 0);

    const videosPerCreator = parseInt(document.getElementById('analysis-videos').value) || 3;
    const provider = document.getElementById('analysis-provider').value;
    const model = document.getElementById('analysis-model').value;

    // Validate
    if (creators.length === 0) {
        errorEl.textContent = 'Please enter at least one creator';
        errorEl.style.display = 'block';
        return;
    }

    if (!provider || !model) {
        errorEl.textContent = 'Please select a provider and model';
        errorEl.style.display = 'block';
        return;
    }

    // Show loading
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Starting...';
    errorEl.style.display = 'none';

    try {
        const result = await API.startAnalysis({
            creators,
            videos_per_creator: videosPerCreator,
            provider_id: provider,
            model_id: model
        });

        console.log('[Workspace] Analysis started:', result);
        closeModal();

        // Navigate to jobs view
        window.location.hash = '#jobs';
    } catch (error) {
        console.error('[Workspace] Failed to start analysis:', error);
        errorEl.textContent = error.message || 'Failed to start analysis';
        errorEl.style.display = 'block';
        submitBtn.disabled = false;
        submitBtn.textContent = 'Start Analysis';
    }
}

// Export for debugging
window.ReelRecon = { Store, Router, API };
