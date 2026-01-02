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

    // Start server heartbeat (for auto-reconnect on restart)
    startServerHeartbeat();

    console.log('[Workspace] Ready.');
});

function setupEventListeners() {
    // Quick action buttons
    const newScrapeBtn = document.getElementById('btn-new-scrape');
    const directReelBtn = document.getElementById('btn-direct-reel');
    const newAnalysisBtn = document.getElementById('btn-new-analysis');

    if (newScrapeBtn) {
        newScrapeBtn.addEventListener('click', () => {
            console.log('[Workspace] New Scrape clicked');
            openModal('new-scrape');
        });
    }

    if (directReelBtn) {
        directReelBtn.addEventListener('click', () => {
            console.log('[Workspace] Direct Reel clicked');
            openModal('direct-reel');
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
    document.querySelectorAll('.jobs-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            document.querySelectorAll('.jobs-tab').forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');
            const tabType = e.target.dataset.tab;
            console.log('[Workspace] Tab switched:', tabType);
            loadJobs(tabType);
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

    // Close modal when clicking overlay (but not on drag)
    const modalOverlay = document.getElementById('modal-overlay');
    if (modalOverlay) {
        let mouseDownTarget = null;

        modalOverlay.addEventListener('mousedown', (e) => {
            mouseDownTarget = e.target;
        });

        modalOverlay.addEventListener('mouseup', (e) => {
            // Only close if both mousedown AND mouseup were on the overlay itself
            if (e.target === modalOverlay && mouseDownTarget === modalOverlay) {
                closeModal();
            }
            mouseDownTarget = null;
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

        // Update favorites count
        const favoritesCount = assets.filter(a => a.starred).length;
        updateFavoritesCount(favoritesCount);
    } catch (error) {
        console.warn('[Workspace] Failed to load initial data:', error.message);
        renderAssets([]); // Show empty state
    }
}

function updateFavoritesCount(count) {
    const countEl = document.getElementById('favorites-count');
    if (countEl) {
        countEl.textContent = count;
    }
}

// Subscribe to view changes to render favorites
Store.subscribe((state) => {
    if (state.ui.activeView === 'favorites') {
        const favorites = state.assets.filter(a => a.starred);
        renderFavorites(favorites);
    }
});

function renderFavorites(assets) {
    const grid = document.getElementById('favorites-grid');
    if (!grid) return;

    if (!assets || assets.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <p>No favorites yet. Star assets to see them here.</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = assets.map(asset => renderAssetCard(asset)).join('');

    // Add click handlers to cards
    grid.querySelectorAll('.asset-card').forEach(card => {
        card.addEventListener('click', (e) => {
            // Don't open if clicking remove button
            if (e.target.closest('.collection-remove')) return;
            const assetId = card.dataset.assetId;
            openAssetDetail(assetId);
        });
    });

    // Add remove from collection handlers
    setupCollectionRemoveHandlers(grid);
}

// =========================================
// JOBS VIEW (Phase 4)
// =========================================

// Subscribe to view changes to load jobs
Store.subscribe((state) => {
    if (state.ui.activeView === 'jobs') {
        // Load active jobs by default when entering jobs view
        const activeTab = document.querySelector('.jobs-tab.active');
        const tabType = activeTab ? activeTab.dataset.tab : 'active';
        loadJobs(tabType);
    }
});

let jobsPollingInterval = null;
let trackedActiveJobs = new Set(); // Track job IDs to detect completion

async function loadJobs(type = 'active') {
    const list = document.getElementById('jobs-list');
    if (!list) return;

    try {
        const endpoint = type === 'active' ? '/api/jobs/active' : '/api/jobs/recent';
        const response = await fetch(endpoint);
        const data = await response.json();

        if (data.success) {
            if (type === 'active') {
                // Check for completed jobs (were tracked but no longer in active list)
                const currentJobIds = new Set(data.jobs.map(j => j.id));
                for (const trackedId of trackedActiveJobs) {
                    if (!currentJobIds.has(trackedId)) {
                        // Job finished! Notify user
                        showJobCompletionNotification(trackedId);
                        trackedActiveJobs.delete(trackedId);
                    }
                }
                // Update tracked jobs
                data.jobs.forEach(j => trackedActiveJobs.add(j.id));
            }

            renderJobs(data.jobs, type);

            // Start polling for active jobs
            if (type === 'active' && data.jobs.length > 0) {
                startJobsPolling();
            } else if (type === 'active' && data.jobs.length === 0) {
                stopJobsPolling();
            } else {
                stopJobsPolling();
            }
        }
    } catch (error) {
        console.error('[Workspace] Failed to load jobs:', error);
        list.innerHTML = '<div class="empty-state"><p>Failed to load jobs</p></div>';
    }
}

function showJobCompletionNotification(jobId) {
    console.log('[Workspace] Job completed:', jobId);

    // Flash the nav items to indicate completion
    const jobsNav = document.querySelector('[data-nav="jobs"]');
    const libraryNav = document.querySelector('[data-nav="library"]');

    if (jobsNav) {
        jobsNav.classList.add('job-completed');
        setTimeout(() => jobsNav.classList.remove('job-completed'), 3000);
    }
    if (libraryNav) {
        libraryNav.classList.add('job-completed');
        setTimeout(() => libraryNav.classList.remove('job-completed'), 3000);
    }

    // Reload library to show new assets
    reloadAssets();

    // If on jobs view, refresh to show updated state
    if (Store.getState().ui.activeView === 'jobs') {
        loadJobs('active');
    }
}

function startJobsPolling() {
    stopJobsPolling();
    // Poll every 1 second like the original scraper
    jobsPollingInterval = setInterval(() => {
        const activeView = Store.getState().ui.activeView;
        const activeTab = document.querySelector('.jobs-tab.active');
        if (activeView === 'jobs' && activeTab?.dataset.tab === 'active') {
            loadJobs('active');
        } else if (trackedActiveJobs.size > 0) {
            // Keep polling even if not on jobs view, to detect completion
            pollActiveJobsBackground();
        } else {
            stopJobsPolling();
        }
    }, 1000); // Poll every 1 second
}

async function pollActiveJobsBackground() {
    try {
        const response = await fetch('/api/jobs/active');
        const data = await response.json();
        if (data.success) {
            const currentJobIds = new Set(data.jobs.map(j => j.id));
            for (const trackedId of trackedActiveJobs) {
                if (!currentJobIds.has(trackedId)) {
                    showJobCompletionNotification(trackedId);
                    trackedActiveJobs.delete(trackedId);
                }
            }
            if (trackedActiveJobs.size === 0) {
                stopJobsPolling();
            }
        }
    } catch (e) {
        console.error('[Workspace] Background poll failed:', e);
    }
}

function stopJobsPolling() {
    if (jobsPollingInterval) {
        clearInterval(jobsPollingInterval);
        jobsPollingInterval = null;
    }
}

function renderJobs(jobs, type) {
    const list = document.getElementById('jobs-list');
    if (!list) return;

    if (!jobs || jobs.length === 0) {
        const emptyMsg = type === 'active'
            ? 'No active jobs. Start a scrape or analysis to see progress here.'
            : 'No recent jobs.';
        list.innerHTML = `<div class="empty-state"><p>${emptyMsg}</p></div>`;
        return;
    }

    list.innerHTML = jobs.map(job => renderJobCard(job, type)).join('');

    // Add click handlers
    list.querySelectorAll('.job-card').forEach(card => {
        card.addEventListener('click', () => {
            const jobId = card.dataset.jobId;
            const jobType = card.dataset.jobType;
            openJobDetail(jobId, jobType);
        });
    });
}

function renderJobCard(job, listType) {
    const statusColors = {
        'running': '#3B82F6',
        'starting': '#3B82F6',
        'complete': '#10B981',
        'failed': '#F87171',
        'error': '#F87171',
        'partial': '#F59E0B',
        'aborted': '#6B7280'
    };

    const typeIcons = {
        'scrape': '📥',
        'analysis': '🔬'
    };

    const statusColor = statusColors[job.status] || '#6B7280';
    const typeIcon = typeIcons[job.type] || '📋';
    const createdDate = job.created_at ? new Date(job.created_at).toLocaleString() : '';
    const isRunning = job.status === 'running' || job.status === 'starting';
    const progressPct = job.progress_pct || 0;

    // Always show progress bar for active jobs (use existing progress-bar styles with pulse)
    const progressBar = listType === 'active' ? `
        <div class="progress-bar" style="margin: var(--space-sm) 0;">
            <div class="progress-fill" style="width: ${progressPct}%"></div>
        </div>
    ` : '';

    const progressText = job.progress || job.phase || '';

    // Abort button for active jobs
    const abortButton = listType === 'active' ? `
        <button class="btn btn-abort" onclick="abortJob('${job.id}', '${job.type}', '${job.batch_id || ''}'); event.stopPropagation();">
            Abort
        </button>
    ` : '';

    return `
        <div class="job-card${isRunning ? ' running' : ''}" data-job-id="${job.id}" data-job-type="${job.type}">
            <div class="job-card-header">
                <span class="job-type-icon">${typeIcon}</span>
                <span class="job-title">${job.title}</span>
                <span class="job-status" style="background: ${statusColor}20; color: ${statusColor}">
                    ${job.status}
                </span>
            </div>
            ${progressBar}
            ${progressText ? `<p class="job-progress-text">${progressText}</p>` : ''}
            <div class="job-meta">
                <span class="job-date">${createdDate}</span>
                ${job.platform ? `<span class="job-platform">${job.platform}</span>` : ''}
            </div>
            ${abortButton}
        </div>
    `;
}

function openJobDetail(jobId, jobType) {
    console.log('[Workspace] Opening job:', jobId, jobType);
    // TODO: Open job detail panel or navigate to results
    // For now, could navigate to the existing report page
    if (jobType === 'analysis') {
        window.open(`/skeleton-ripper/report/${jobId}`, '_blank');
    }
}

async function abortJob(jobId, jobType, batchId) {
    console.log('[Workspace] Aborting job:', jobId, jobType, batchId ? `(batch: ${batchId})` : '');

    // Confirm with user
    const confirmMessage = batchId
        ? 'Abort this batch? This will stop the current scrape and cancel all pending items.'
        : 'Abort this job? Any partial data will be cleaned up.';

    if (!confirm(confirmMessage)) {
        return;
    }

    try {
        let result;
        if (batchId) {
            // Abort entire batch
            result = await API.abortBatch(batchId);
        } else if (jobType === 'scrape') {
            result = await API.abortScrape(jobId);
        } else if (jobType === 'analysis') {
            result = await API.abortAnalysis(jobId);
        }

        console.log('[Workspace] Abort result:', result);

        // Refresh jobs list
        loadJobs('active');
    } catch (error) {
        console.error('[Workspace] Abort failed:', error);
        alert('Failed to abort job: ' + error.message);
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
        card.addEventListener('click', (e) => {
            // Don't open if clicking remove button
            if (e.target.closest('.collection-remove')) return;
            const assetId = card.dataset.assetId;
            openAssetDetail(assetId);
        });
    });

    // Add remove from collection handlers
    setupCollectionRemoveHandlers(grid);
}

function setupCollectionRemoveHandlers(container) {
    container.querySelectorAll('.collection-remove').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const tag = btn.closest('.collection-tag');
            const assetId = tag.dataset.assetId;
            const collectionId = tag.dataset.collectionId;

            try {
                await API.removeFromCollection(assetId, collectionId);
                // Remove the tag from UI
                tag.remove();
                console.log('[Workspace] Removed from collection:', collectionId);
            } catch (error) {
                console.error('[Workspace] Failed to remove from collection:', error);
            }
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

    // Render collection tags with remove button
    const collections = asset.collections || [];
    const collectionTags = collections.map(col => `
        <span class="collection-tag" style="background: ${col.color || '#6366f1'}20; color: ${col.color || '#6366f1'}; border-color: ${col.color || '#6366f1'}40" data-collection-id="${col.id}" data-asset-id="${asset.id}">
            ${col.name}
            <button class="collection-remove" title="Remove from collection">×</button>
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

    // Store the assetId immediately so delete works even if load fails
    content.dataset.assetId = assetId;

    // Show loading state
    content.innerHTML = '<div class="detail-loading">Loading...</div>';
    panel.classList.add('open');

    try {
        // Fetch full asset data
        const asset = await API.getAsset(assetId);
        renderDetailPanel(asset);
    } catch (error) {
        console.error('[Workspace] Failed to load asset:', error);
        // Show error state but keep assetId so delete still works
        content.innerHTML = `
            <div class="detail-error">
                <p>Failed to load asset</p>
                <p class="detail-error-hint">You can still delete this item using the trash icon above.</p>
            </div>
        `;
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
                ${renderAssetContent(asset)}
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

function renderAssetContent(asset) {
    // Handle scrape reports - show full reel details like v2 modal
    if (asset.type === 'scrape_report' && asset.top_reels && asset.top_reels.length > 0) {
        return `
            <div class="scrape-results">
                <div class="scrape-summary">
                    <strong>${asset.top_reels.length} reels</strong> from @${asset.username}
                </div>
                <div class="reels-accordion">
                    ${asset.top_reels.map((reel, i) => renderReelAccordionItem(reel, i, asset.id)).join('')}
                </div>
            </div>
        `;
    }

    // Handle other asset types with text content
    if (typeof asset.content === 'string') {
        return `<div class="detail-body">${escapeHtml(asset.content)}</div>`;
    }

    // Fallback
    return `<div class="detail-body">${escapeHtml(asset.preview || 'No content available')}</div>`;
}

function renderReelAccordionItem(reel, index, scrapeId) {
    const views = reel.play_count || reel.plays || reel.views || 0;
    const likes = reel.like_count || reel.likes || 0;
    const comments = reel.comment_count || reel.comments || 0;
    const caption = reel.caption || 'No caption';
    const transcript = reel.transcript || null;
    const url = reel.url || reel.video_url || '';
    const shortcode = reel.shortcode || reel.id || '';

    return `
        <div class="reel-accordion-item" data-index="${index}">
            <div class="reel-accordion-header" onclick="toggleReelAccordion(${index})">
                <div class="reel-header-left">
                    <span class="reel-index">#${index + 1}</span>
                    <span class="reel-header-caption">${escapeHtml(caption.substring(0, 60))}${caption.length > 60 ? '...' : ''}</span>
                </div>
                <div class="reel-header-right">
                    <span class="reel-stat-mini">${formatNumber(views)} views</span>
                    ${transcript ? '<span class="reel-has-transcript">📝</span>' : ''}
                    <span class="reel-accordion-arrow">▼</span>
                </div>
            </div>
            <div class="reel-accordion-body" id="reel-body-${index}" style="display: none;">
                <!-- Stats Row -->
                <div class="reel-stats-row">
                    <div class="reel-stat">
                        <span class="reel-stat-value">${formatNumber(views)}</span>
                        <span class="reel-stat-label">VIEWS</span>
                    </div>
                    <div class="reel-stat">
                        <span class="reel-stat-value">${formatNumber(likes)}</span>
                        <span class="reel-stat-label">LIKES</span>
                    </div>
                    <div class="reel-stat">
                        <span class="reel-stat-value">${formatNumber(comments)}</span>
                        <span class="reel-stat-label">COMMENTS</span>
                    </div>
                </div>

                <!-- URL -->
                ${url ? `
                <div class="reel-section">
                    <div class="reel-section-title">URL</div>
                    <div class="reel-url-row">
                        <code class="reel-url">${escapeHtml(url)}</code>
                        <button class="btn-copy-sm" onclick="copyUrlFromReel(${index})">COPY</button>
                    </div>
                </div>
                ` : ''}

                <!-- Caption -->
                <div class="reel-section">
                    <div class="reel-section-title">CAPTION / HOOK</div>
                    <div class="reel-caption-full">${escapeHtml(caption)}</div>
                </div>

                <!-- Transcript -->
                ${transcript ? `
                <div class="reel-section">
                    <div class="reel-section-title">TRANSCRIPT</div>
                    <div class="reel-transcript">${escapeHtml(transcript)}</div>
                    <button class="btn-copy-sm" onclick="copyTranscriptFromReel(${index})">COPY TRANSCRIPT</button>
                </div>
                ` : `
                <div class="reel-section reel-no-transcript">
                    <div class="reel-section-title">TRANSCRIPT</div>
                    <div class="reel-transcript-empty">No transcript available</div>
                </div>
                `}

                <!-- Actions -->
                <div class="reel-actions">
                    ${url ? `<a href="${escapeHtml(url)}" target="_blank" class="btn btn-secondary btn-sm">OPEN IN IG</a>` : ''}
                    <button class="btn btn-secondary btn-sm" onclick="copyReelForAI(${index})">COPY FOR AI</button>
                </div>
            </div>
        </div>
    `;
}

function toggleReelAccordion(index) {
    const body = document.getElementById(`reel-body-${index}`);
    const item = body.closest('.reel-accordion-item');
    const arrow = item.querySelector('.reel-accordion-arrow');

    if (body.style.display === 'none') {
        body.style.display = 'block';
        item.classList.add('expanded');
        arrow.textContent = '▲';
    } else {
        body.style.display = 'none';
        item.classList.remove('expanded');
        arrow.textContent = '▼';
    }
}

function copyToClipboard(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
        if (btn) {
            const original = btn.textContent;
            btn.textContent = '✓ COPIED';
            setTimeout(() => btn.textContent = original, 1500);
        }
    });
}

function copyReelForAI(index) {
    const item = document.querySelector(`.reel-accordion-item[data-index="${index}"]`);
    if (!item) return;

    const caption = item.querySelector('.reel-caption-full')?.textContent || '';
    const transcript = item.querySelector('.reel-transcript')?.textContent || '';

    let text = '';
    if (caption) text += `CAPTION:\n${caption}\n\n`;
    if (transcript) text += `TRANSCRIPT:\n${transcript}`;

    copyToClipboard(text.trim(), item.querySelector('.reel-actions .btn:last-child'));
}

function copyTranscriptFromReel(index) {
    const item = document.querySelector(`.reel-accordion-item[data-index="${index}"]`);
    if (!item) return;

    const transcript = item.querySelector('.reel-transcript')?.textContent || '';
    const btn = item.querySelector('.reel-section .btn-copy-sm');
    copyToClipboard(transcript, btn);
}

function copyUrlFromReel(index) {
    const item = document.querySelector(`.reel-accordion-item[data-index="${index}"]`);
    if (!item) return;

    const url = item.querySelector('.reel-url')?.textContent || '';
    const btn = item.querySelector('.reel-url-row .btn-copy-sm');
    copyToClipboard(url, btn);
}

function formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
}

function escapeHtml(text) {
    if (typeof text !== 'string') return '';
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

    console.log('[Workspace] Delete requested for asset:', assetId);

    if (!assetId) {
        console.error('[Workspace] No asset ID found in detail panel');
        return;
    }

    try {
        console.log('[Workspace] Sending delete request for:', assetId);
        await API.deleteAsset(assetId);
        closeAssetDetail();
        // Remove from store
        const state = Store.getState();
        const assets = state.assets.filter(a => a.id !== assetId);
        Store.dispatch({ type: 'SET_ASSETS', payload: assets });
        updateAssetCount(assets.length);
        console.log('[Workspace] Asset deleted successfully:', assetId);

        // Reload assets to ensure UI is in sync
        loadInitialData();
    } catch (error) {
        console.error('[Workspace] Failed to delete:', error);
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
    } else if (modalType === 'direct-reel') {
        content.innerHTML = renderDirectReelModal();
        setupDirectReelModal();
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
                <label class="form-label">Target Creators</label>
                <textarea id="scrape-usernames" class="form-input form-textarea" rows="3" placeholder="garyvee&#10;hormozi&#10;nathanbarry"></textarea>
                <p class="form-hint">One username per line (up to 5 creators). No @ needed.</p>
            </div>

            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Max Reels</label>
                    <input type="number" id="scrape-max-reels" class="form-input" value="100" min="1" max="500">
                </div>
                <div class="form-group">
                    <label class="form-label">Top N</label>
                    <input type="number" id="scrape-top-n" class="form-input" value="10" min="1" max="100">
                    <p class="form-hint">Filter to top performing</p>
                </div>
            </div>

            <div class="form-group">
                <label class="form-label">Extraction Options</label>
                <div class="checkbox-stack">
                    <label class="checkbox-group">
                        <input type="checkbox" id="scrape-download-videos">
                        <span>Download Videos</span>
                    </label>
                    <label class="checkbox-group">
                        <input type="checkbox" id="scrape-transcribe">
                        <span>Transcribe</span>
                    </label>
                </div>
            </div>

            <div id="transcription-config" class="form-group conditional-section" style="display: none;">
                <label class="form-label">Transcription Method</label>
                <select id="scrape-transcription-method" class="form-select">
                    <option value="local">Local (Whisper)</option>
                    <option value="openai">OpenAI API</option>
                </select>
                <p class="form-hint" id="transcription-method-hint">Uses local Whisper model (free, requires download)</p>

                <div id="local-model-config" class="form-group" style="margin-top: var(--space-md);">
                    <label class="form-label">Local Model</label>
                    <select id="scrape-local-model" class="form-select">
                        <option value="tiny.en">tiny.en (39MB, fastest)</option>
                        <option value="base.en">base.en (74MB, fast)</option>
                        <option value="small.en" selected>small.en (244MB, recommended)</option>
                        <option value="medium.en">medium.en (769MB, accurate)</option>
                        <option value="large">large (1.5GB, most accurate)</option>
                    </select>
                </div>
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

    // Transcribe checkbox → show/hide transcription config
    const transcribeCheckbox = document.getElementById('scrape-transcribe');
    const transcriptionConfig = document.getElementById('transcription-config');

    transcribeCheckbox.addEventListener('change', () => {
        transcriptionConfig.style.display = transcribeCheckbox.checked ? 'block' : 'none';
    });

    // Transcription method → show/hide local model config
    const methodSelect = document.getElementById('scrape-transcription-method');
    const localModelConfig = document.getElementById('local-model-config');
    const methodHint = document.getElementById('transcription-method-hint');

    methodSelect.addEventListener('change', () => {
        const isLocal = methodSelect.value === 'local';
        localModelConfig.style.display = isLocal ? 'block' : 'none';
        methodHint.textContent = isLocal
            ? 'Uses local Whisper model (free, requires download)'
            : 'Uses OpenAI Whisper API (requires API key, fast)';
    });

    // Start scrape
    document.getElementById('btn-start-scrape').addEventListener('click', startScrape);
}

async function startScrape() {
    const errorEl = document.getElementById('modal-error');
    const submitBtn = document.getElementById('btn-start-scrape');

    // Get form values
    const platform = document.querySelector('.toggle-btn[data-platform].active').dataset.platform;
    const usernamesRaw = document.getElementById('scrape-usernames').value.trim();
    const maxReels = parseInt(document.getElementById('scrape-max-reels').value) || 100;
    const topN = parseInt(document.getElementById('scrape-top-n').value) || 10;
    const downloadVideos = document.getElementById('scrape-download-videos').checked;
    const transcribe = document.getElementById('scrape-transcribe').checked;
    const transcriptionMethod = document.getElementById('scrape-transcription-method').value;
    const localModel = document.getElementById('scrape-local-model').value;

    // Parse usernames (one per line, clean up)
    const usernames = usernamesRaw
        .split('\n')
        .map(u => u.trim().replace('@', '').replace(/^https?:\/\/(www\.)?(instagram|tiktok)\.com\//, '').replace(/\/$/, ''))
        .filter(u => u.length > 0);

    // Validate
    if (usernames.length === 0) {
        errorEl.textContent = 'Please enter at least one username';
        errorEl.style.display = 'block';
        return;
    }

    if (usernames.length > 5) {
        errorEl.textContent = 'Maximum 5 creators per batch';
        errorEl.style.display = 'block';
        return;
    }

    // Show loading
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Starting...';
    errorEl.style.display = 'none';

    try {
        const result = await API.startBatchScrape({
            platform,
            usernames,
            max_reels: maxReels,
            top_n: topN,
            download: downloadVideos,
            transcribe,
            transcribe_provider: transcribe ? transcriptionMethod : null,
            whisper_model: transcribe && transcriptionMethod === 'local' ? localModel : null
        });

        console.log('[Workspace] Batch scrape started:', result);

        // Track batch job for completion detection
        if (result.batch_id) {
            trackedActiveJobs.add(result.batch_id);
            startJobsPolling();
        }

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

// Direct Reel Modal
function renderDirectReelModal() {
    return `
        <div class="modal-header">
            <h2 class="modal-title">Direct Reel</h2>
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
                <label class="form-label">Input Type</label>
                <div class="toggle-group">
                    <button type="button" class="toggle-btn active" data-input-type="url">URL</button>
                    <button type="button" class="toggle-btn" data-input-type="id">ID</button>
                </div>
                <p class="form-hint" id="input-type-hint">Paste full reel/video URLs</p>
            </div>

            <div class="form-group">
                <label class="form-label">Reels</label>
                <textarea id="direct-reel-inputs" class="form-input form-textarea" rows="5" placeholder="https://instagram.com/reel/ABC123&#10;https://instagram.com/reel/XYZ789"></textarea>
                <p class="form-hint">One per line (up to 5 reels)</p>
            </div>

            <div class="form-group">
                <label class="form-label">Extraction Options</label>
                <div class="checkbox-stack">
                    <label class="checkbox-group">
                        <input type="checkbox" id="direct-download-videos">
                        <span>Download Videos</span>
                    </label>
                    <label class="checkbox-group">
                        <input type="checkbox" id="direct-transcribe">
                        <span>Transcribe</span>
                    </label>
                </div>
            </div>

            <div id="direct-transcription-config" class="form-group conditional-section" style="display: none;">
                <label class="form-label">Transcription Method</label>
                <select id="direct-transcription-method" class="form-select">
                    <option value="local">Local (Whisper)</option>
                    <option value="openai">OpenAI API</option>
                </select>
                <p class="form-hint" id="direct-transcription-hint">Uses local Whisper model (free, requires download)</p>

                <div id="direct-local-model-config" class="form-group" style="margin-top: var(--space-md);">
                    <label class="form-label">Local Model</label>
                    <select id="direct-local-model" class="form-select">
                        <option value="tiny.en">tiny.en (39MB, fastest)</option>
                        <option value="base.en">base.en (74MB, fast)</option>
                        <option value="small.en" selected>small.en (244MB, recommended)</option>
                        <option value="medium.en">medium.en (769MB, accurate)</option>
                        <option value="large">large (1.5GB, most accurate)</option>
                    </select>
                </div>
            </div>
        </div>
        <div class="modal-footer">
            <button class="btn btn-secondary" id="btn-cancel-direct">Cancel</button>
            <button class="btn btn-primary" id="btn-start-direct">Grab Reels</button>
        </div>
    `;
}

function setupDirectReelModal() {
    // Close buttons
    document.getElementById('btn-close-modal').addEventListener('click', closeModal);
    document.getElementById('btn-cancel-direct').addEventListener('click', closeModal);

    // Platform toggle
    document.querySelectorAll('.toggle-btn[data-platform]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.toggle-btn[data-platform]').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            updateDirectReelPlaceholder();
        });
    });

    // Input type toggle (URL/ID)
    document.querySelectorAll('.toggle-btn[data-input-type]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.toggle-btn[data-input-type]').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            updateDirectReelPlaceholder();
        });
    });

    // Transcribe checkbox → show/hide config
    const transcribeCheckbox = document.getElementById('direct-transcribe');
    const transcriptionConfig = document.getElementById('direct-transcription-config');

    transcribeCheckbox.addEventListener('change', () => {
        transcriptionConfig.style.display = transcribeCheckbox.checked ? 'block' : 'none';
    });

    // Transcription method toggle
    const methodSelect = document.getElementById('direct-transcription-method');
    const localModelConfig = document.getElementById('direct-local-model-config');
    const methodHint = document.getElementById('direct-transcription-hint');

    methodSelect.addEventListener('change', () => {
        const isLocal = methodSelect.value === 'local';
        localModelConfig.style.display = isLocal ? 'block' : 'none';
        methodHint.textContent = isLocal
            ? 'Uses local Whisper model (free, requires download)'
            : 'Uses OpenAI Whisper API (requires API key, fast)';
    });

    // Start button
    document.getElementById('btn-start-direct').addEventListener('click', startDirectScrape);
}

function updateDirectReelPlaceholder() {
    const platform = document.querySelector('.toggle-btn[data-platform].active')?.dataset.platform || 'instagram';
    const inputType = document.querySelector('.toggle-btn[data-input-type].active')?.dataset.inputType || 'url';
    const textarea = document.getElementById('direct-reel-inputs');
    const hint = document.getElementById('input-type-hint');

    if (inputType === 'url') {
        hint.textContent = 'Paste full reel/video URLs';
        if (platform === 'instagram') {
            textarea.placeholder = 'https://instagram.com/reel/ABC123\nhttps://instagram.com/reel/XYZ789';
        } else {
            textarea.placeholder = 'https://tiktok.com/@user/video/123456\nhttps://tiktok.com/@user/video/789012';
        }
    } else {
        hint.textContent = 'Enter reel/video shortcodes or IDs';
        if (platform === 'instagram') {
            textarea.placeholder = 'ABC123\nXYZ789';
        } else {
            textarea.placeholder = '123456789\n987654321';
        }
    }
}

async function startDirectScrape() {
    const errorEl = document.getElementById('modal-error');
    const submitBtn = document.getElementById('btn-start-direct');

    // Get form values
    const platform = document.querySelector('.toggle-btn[data-platform].active').dataset.platform;
    const inputType = document.querySelector('.toggle-btn[data-input-type].active').dataset.inputType;
    const inputsRaw = document.getElementById('direct-reel-inputs').value.trim();
    const downloadVideos = document.getElementById('direct-download-videos').checked;
    const transcribe = document.getElementById('direct-transcribe').checked;
    const transcriptionMethod = document.getElementById('direct-transcription-method').value;
    const localModel = document.getElementById('direct-local-model').value;

    // Parse inputs (one per line)
    const inputs = inputsRaw
        .split('\n')
        .map(i => i.trim())
        .filter(i => i.length > 0);

    // Validate
    if (inputs.length === 0) {
        errorEl.textContent = 'Please enter at least one reel URL or ID';
        errorEl.style.display = 'block';
        return;
    }

    if (inputs.length > 5) {
        errorEl.textContent = 'Maximum 5 reels per request';
        errorEl.style.display = 'block';
        return;
    }

    // Show loading
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Starting...';
    errorEl.style.display = 'none';

    try {
        const result = await API.startDirectScrape({
            platform,
            input_type: inputType,
            inputs,
            download: downloadVideos,
            transcribe,
            transcribe_provider: transcribe ? transcriptionMethod : null,
            whisper_model: transcribe && transcriptionMethod === 'local' ? localModel : null
        });

        console.log('[Workspace] Direct scrape started:', result);

        // Track jobs
        if (result.scrape_ids) {
            result.scrape_ids.forEach(id => {
                trackedActiveJobs.add(id);
            });
            startJobsPolling();
        }

        closeModal();
        window.location.hash = '#jobs';
    } catch (error) {
        console.error('[Workspace] Failed to start direct scrape:', error);
        errorEl.textContent = error.message || 'Failed to start scrape';
        errorEl.style.display = 'block';
        submitBtn.disabled = false;
        submitBtn.textContent = 'Grab Reels';
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
                <div class="add-row-container">
                    <button type="button" id="btn-add-creator" class="btn-add-row">+ Add Creator</button>
                    <span class="form-hint">Up to 5 creators</span>
                </div>
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
        row.className = 'multi-input-row has-remove';
        row.innerHTML = `
            <div class="input-with-remove">
                <input type="text" class="form-input creator-input" placeholder="@username">
                <button type="button" class="btn-remove-row">×</button>
            </div>
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

// =========================================
// SERVER HEARTBEAT (Auto-reconnect)
// =========================================

let heartbeatInterval = null;
let serverWasDown = false;
let reconnectOverlay = null;

function startServerHeartbeat() {
    // Check server every 3 seconds
    heartbeatInterval = setInterval(checkServerHealth, 3000);
}

async function checkServerHealth() {
    try {
        const response = await fetch('/api/health', {
            method: 'GET',
            cache: 'no-store',
            signal: AbortSignal.timeout(2000) // 2 second timeout
        });

        if (response.ok) {
            if (serverWasDown) {
                // Server came back! Auto-refresh
                console.log('[Workspace] Server reconnected - refreshing...');
                hideReconnectOverlay();
                window.location.reload();
            }
        } else {
            handleServerDown();
        }
    } catch (error) {
        handleServerDown();
    }
}

function handleServerDown() {
    if (!serverWasDown) {
        console.log('[Workspace] Server connection lost - showing reconnect overlay');
        serverWasDown = true;
        showReconnectOverlay();
    }
}

function showReconnectOverlay() {
    if (reconnectOverlay) return;

    reconnectOverlay = document.createElement('div');
    reconnectOverlay.id = 'reconnect-overlay';
    reconnectOverlay.innerHTML = `
        <div class="reconnect-content">
            <div class="reconnect-spinner"></div>
            <h3>Reconnecting...</h3>
            <p>Server restarting. Will auto-refresh when ready.</p>
        </div>
    `;
    reconnectOverlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(24, 24, 27, 0.95);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
    `;

    const content = reconnectOverlay.querySelector('.reconnect-content');
    content.style.cssText = `
        text-align: center;
        color: #fafafa;
    `;

    const spinner = reconnectOverlay.querySelector('.reconnect-spinner');
    spinner.style.cssText = `
        width: 48px;
        height: 48px;
        border: 4px solid #27272a;
        border-top-color: #10b981;
        border-radius: 50%;
        margin: 0 auto 16px;
        animation: spin 1s linear infinite;
    `;

    // Add keyframes for spinner
    if (!document.getElementById('reconnect-styles')) {
        const style = document.createElement('style');
        style.id = 'reconnect-styles';
        style.textContent = `@keyframes spin { to { transform: rotate(360deg); } }`;
        document.head.appendChild(style);
    }

    document.body.appendChild(reconnectOverlay);
}

function hideReconnectOverlay() {
    if (reconnectOverlay) {
        reconnectOverlay.remove();
        reconnectOverlay = null;
    }
    serverWasDown = false;
}

// Export for debugging
window.ReelRecon = { Store, Router, API };

// Expose accordion functions globally for onclick handlers
window.toggleReelAccordion = toggleReelAccordion;
window.copyToClipboard = copyToClipboard;
window.copyReelForAI = copyReelForAI;
window.copyTranscriptFromReel = copyTranscriptFromReel;
window.copyUrlFromReel = copyUrlFromReel;
window.abortJob = abortJob;
