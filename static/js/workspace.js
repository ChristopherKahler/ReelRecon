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
                // Persist to server
                API.updateSettings({ library_filter_types: [] }).catch(err => {
                    console.warn('[Workspace] Failed to save filter preference:', err);
                });
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
                // Persist to server
                API.updateSettings({ library_filter_types: activeTypes }).catch(err => {
                    console.warn('[Workspace] Failed to save filter preference:', err);
                });
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

    // Jobs view mode toggle (list, grid-2, grid-3) - synced between Jobs and Starred Jobs panels
    document.querySelectorAll('#jobs-view-toggle .view-toggle-btn, #starred-jobs-view-toggle .view-toggle-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const mode = e.currentTarget.dataset.viewMode;
            if (mode) {
                currentJobsViewMode = mode;

                // Save to server (like panel resize does)
                API.updateSettings({ jobs_view_mode: mode }).catch(err => {
                    console.warn('[Workspace] Failed to save jobs view mode:', err);
                });

                // Update jobs toggle buttons across both panels to sync state
                document.querySelectorAll('#jobs-view-toggle .view-toggle-btn, #starred-jobs-view-toggle .view-toggle-btn').forEach(b => {
                    b.classList.toggle('active', b.dataset.viewMode === mode);
                });

                // Apply to main jobs list
                const jobsList = document.getElementById('jobs-list');
                if (jobsList) {
                    jobsList.classList.remove('view-list', 'view-grid-2', 'view-grid-3');
                    jobsList.classList.add(`view-${mode}`);
                }

                // Apply to starred jobs list (keep them synced)
                const starredJobsList = document.getElementById('starred-jobs-list');
                if (starredJobsList) {
                    starredJobsList.classList.remove('view-list', 'view-grid-2', 'view-grid-3');
                    starredJobsList.classList.add(`view-${mode}`);
                }
            }
        });
    });

    // Asset view toggle click handlers
    document.querySelectorAll('#library-view-toggle .view-toggle-btn, #favorites-view-toggle .view-toggle-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const mode = e.currentTarget.dataset.viewMode;
            if (mode) {
                currentAssetViewMode = mode;

                // Save to server (like panel resize does)
                API.updateSettings({ asset_view_mode: mode }).catch(err => {
                    console.warn('[Workspace] Failed to save asset view mode:', err);
                });

                // Update ALL asset toggle buttons across both panels to sync state
                document.querySelectorAll('#library-view-toggle .view-toggle-btn, #favorites-view-toggle .view-toggle-btn').forEach(b => {
                    b.classList.toggle('active', b.dataset.viewMode === mode);
                });

                // Apply to library asset grid
                const assetGrid = document.getElementById('asset-grid');
                if (assetGrid) {
                    assetGrid.classList.remove('view-list', 'view-grid-2', 'view-grid-3', 'view-grid-4');
                    assetGrid.classList.add(`view-${mode}`);
                }

                // Apply to favorites asset grid (keep them synced)
                const favoritesGrid = document.getElementById('favorites-grid');
                if (favoritesGrid) {
                    favoritesGrid.classList.remove('view-list', 'view-grid-2', 'view-grid-3', 'view-grid-4');
                    favoritesGrid.classList.add(`view-${mode}`);
                }
            }
        });
    });

    // Load view preferences from server and apply them
    loadViewPreferences();

    // Clear All Jobs button
    const clearAllJobsBtn = document.getElementById('btn-clear-all-jobs');
    if (clearAllJobsBtn) {
        clearAllJobsBtn.addEventListener('click', clearAllJobs);
    }

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

    // Custom right-click context menu for PyWebView compatibility
    setupContextMenu();

    // Setup resizable detail panel
    setupPanelResize();

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

    // Apply current view mode (persisted from server settings)
    grid.classList.remove('view-list', 'view-grid-2', 'view-grid-3', 'view-grid-4');
    grid.classList.add(`view-${currentAssetViewMode}`);

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
let currentJobsViewMode = 'list'; // list, grid-2, grid-3 (loaded from server settings)
let currentAssetViewMode = 'grid-3'; // list, grid-2, grid-3 (loaded from server settings)

// Load view preferences from server and apply them (called on page load)
async function loadViewPreferences() {
    try {
        const settings = await API.getSettings();

        // Apply jobs view mode
        if (settings.jobs_view_mode) {
            currentJobsViewMode = settings.jobs_view_mode;

            // Update button states
            document.querySelectorAll('#jobs-view-toggle .view-toggle-btn, #starred-jobs-view-toggle .view-toggle-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.viewMode === currentJobsViewMode);
            });

            // Apply to job lists
            const jobsList = document.getElementById('jobs-list');
            const starredJobsList = document.getElementById('starred-jobs-list');
            if (jobsList) {
                jobsList.classList.remove('view-list', 'view-grid-2', 'view-grid-3');
                jobsList.classList.add(`view-${currentJobsViewMode}`);
            }
            if (starredJobsList) {
                starredJobsList.classList.remove('view-list', 'view-grid-2', 'view-grid-3');
                starredJobsList.classList.add(`view-${currentJobsViewMode}`);
            }
        }

        // Apply asset view mode
        if (settings.asset_view_mode) {
            currentAssetViewMode = settings.asset_view_mode;

            // Update button states
            document.querySelectorAll('#library-view-toggle .view-toggle-btn, #favorites-view-toggle .view-toggle-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.viewMode === currentAssetViewMode);
            });

            // Apply to asset grids
            const assetGrid = document.getElementById('asset-grid');
            const favoritesGrid = document.getElementById('favorites-grid');
            if (assetGrid) {
                assetGrid.classList.remove('view-list', 'view-grid-2', 'view-grid-3', 'view-grid-4');
                assetGrid.classList.add(`view-${currentAssetViewMode}`);
            }
            if (favoritesGrid) {
                favoritesGrid.classList.remove('view-list', 'view-grid-2', 'view-grid-3', 'view-grid-4');
                favoritesGrid.classList.add(`view-${currentAssetViewMode}`);
            }
        }

        // Apply library filter types
        if (settings.library_filter_types && settings.library_filter_types.length > 0) {
            const filterTypes = settings.library_filter_types;

            // Update filter chip UI
            const allChip = document.querySelector('.filter-chip[data-filter-type=""]');
            if (allChip) allChip.classList.remove('active');

            filterTypes.forEach(type => {
                const chip = document.querySelector(`.filter-chip[data-filter-type="${type}"]`);
                if (chip) chip.classList.add('active');
            });

            // Update store
            Store.dispatch({ type: 'SET_FILTER', payload: { types: filterTypes } });
            console.log('[Workspace] Restored library filter:', filterTypes);
        }

        console.log('[Workspace] Loaded view preferences:', { jobs: currentJobsViewMode, assets: currentAssetViewMode });
    } catch (err) {
        console.warn('[Workspace] Failed to load view preferences:', err);
    }
}

async function loadJobs(type = 'recent') {
    const list = document.getElementById('jobs-list');
    if (!list) return;

    // Apply current view mode
    list.classList.remove('view-list', 'view-grid-2', 'view-grid-3');
    list.classList.add(`view-${currentJobsViewMode}`);

    // Show/hide Clear All button only on Recent tab
    const clearAllBtn = document.getElementById('btn-clear-all-jobs');
    if (clearAllBtn) {
        clearAllBtn.style.display = type === 'recent' ? 'block' : 'none';
    }

    try {
        let endpoint;
        if (type === 'active') {
            endpoint = '/api/jobs/active';
        } else if (type === 'archived') {
            endpoint = '/api/jobs/archived';
        } else {
            endpoint = '/api/jobs/recent';
        }

        const response = await fetch(endpoint);
        const data = await response.json();

        if (data.success) {
            renderJobs(data.jobs, type);

            // For active jobs, track IDs and start polling if needed
            if (type === 'active') {
                data.jobs.forEach(j => trackedActiveJobs.add(j.id));
                if (trackedActiveJobs.size > 0) {
                    startJobsPolling();
                }
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
    if (jobsPollingInterval) return; // Already polling
    pollActiveJobsOnce(); // Start immediately
}

async function pollActiveJobsOnce() {
    if (trackedActiveJobs.size === 0) {
        stopJobsPolling();
        return;
    }

    // Poll each tracked job individually (like original scraper)
    for (const jobId of trackedActiveJobs) {
        await pollSingleJob(jobId);
    }

    // Schedule next poll
    jobsPollingInterval = setTimeout(pollActiveJobsOnce, 1000);
}

async function pollSingleJob(jobId) {
    try {
        // Determine job type from ID prefix
        const isAnalysis = jobId.startsWith('sr_');
        const isBatch = jobId.startsWith('batch_');

        let endpoint;
        if (isAnalysis) {
            endpoint = `/api/skeleton-ripper/status/${jobId}`;
        } else if (isBatch) {
            endpoint = `/api/scrape/batch/${jobId}/status`;
        } else {
            endpoint = `/api/scrape/${jobId}/status`;
        }

        const response = await fetch(endpoint);
        if (!response.ok) {
            if (response.status === 404) {
                // Job gone - mark complete
                showJobCompletionNotification(jobId);
                trackedActiveJobs.delete(jobId);
            }
            return;
        }

        const data = await response.json();

        // Check if job is finished
        if (['complete', 'failed', 'error', 'partial', 'aborted'].includes(data.status)) {
            showJobCompletionNotification(jobId);
            trackedActiveJobs.delete(jobId);
            return;
        }

        // Update the job card in the DOM directly
        const card = document.querySelector(`.job-card[data-job-id="${jobId}"]`);
        if (card) {
            // Update progress bar (backend calculates progress_pct)
            const progressFill = card.querySelector('.progress-fill');
            if (progressFill && data.progress_pct !== undefined) {
                progressFill.style.width = `${data.progress_pct}%`;
            }

            // Update progress text with message from progress
            const progressText = card.querySelector('.job-progress-text');
            if (progressText) {
                const text = data.progress?.message || data.progress?.phase || '';
                progressText.textContent = text;
            }
        }
    } catch (e) {
        console.error(`[Workspace] Poll failed for ${jobId}:`, e);
    }
}

function stopJobsPolling() {
    if (jobsPollingInterval) {
        clearTimeout(jobsPollingInterval);
        jobsPollingInterval = null;
    }
}

function renderJobs(jobs, type) {
    const list = document.getElementById('jobs-list');
    if (!list) return;

    // Apply current view mode (persisted from localStorage)
    list.classList.remove('view-list', 'view-grid-2', 'view-grid-3');
    list.classList.add(`view-${currentJobsViewMode}`);

    if (!jobs || jobs.length === 0) {
        let emptyMsg;
        if (type === 'active') {
            emptyMsg = 'No active jobs. Start a scrape or analysis to see progress here.';
        } else if (type === 'archived') {
            emptyMsg = 'No archived jobs. Deleted jobs will appear here.';
        } else {
            emptyMsg = 'No recent jobs.';
        }
        list.innerHTML = `<div class="empty-state"><p>${emptyMsg}</p></div>`;
        return;
    }

    // For active jobs, update in-place to prevent flashing during polling
    if (type === 'active') {
        const currentIds = new Set(jobs.map(j => j.id));
        const existingCards = list.querySelectorAll('.job-card');
        const existingIds = new Set();

        // Update existing cards or remove stale ones
        existingCards.forEach(card => {
            const cardId = card.dataset.jobId;
            existingIds.add(cardId);

            if (!currentIds.has(cardId)) {
                // Job no longer active, remove card
                card.remove();
            } else {
                // Update existing card in-place
                const job = jobs.find(j => j.id === cardId);
                if (job) {
                    updateJobCardInPlace(card, job);
                }
            }
        });

        // Add new cards that don't exist yet
        jobs.forEach(job => {
            if (!existingIds.has(job.id)) {
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = renderJobCard(job, type);
                const newCard = tempDiv.firstElementChild;
                list.appendChild(newCard);
                // Add click handler
                newCard.addEventListener('click', () => {
                    openJobDetail(job.id, job.type);
                });
            }
        });
    } else {
        // For recent/archived, full replace is fine (not polling)
        list.innerHTML = jobs.map(job => renderJobCard(job, type)).join('');

        // Add click handlers (not for archived jobs)
        if (type !== 'archived') {
            list.querySelectorAll('.job-card').forEach(card => {
                card.addEventListener('click', () => {
                    // Use assetFilterId for library filtering (matches history/asset IDs)
                    const assetFilterId = card.dataset.assetFilterId;
                    const jobType = card.dataset.jobType;
                    openJobDetail(assetFilterId, jobType);
                });
            });
        }
    }
}

// Update job card elements in-place without replacing DOM
function updateJobCardInPlace(card, job) {
    // Update progress bar
    const progressFill = card.querySelector('.progress-fill');
    if (progressFill) {
        progressFill.style.width = `${job.progress_pct || 0}%`;
    }

    // Update progress text
    const progressText = card.querySelector('.job-progress-text');
    if (progressText) {
        progressText.textContent = job.progress || job.phase || '';
    }

    // Update phase text
    const phaseText = card.querySelector('.job-phase');
    if (phaseText) {
        phaseText.textContent = job.phase || '';
    }
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

    // Job type colors matching library asset badges
    const typeColors = {
        'scrape': '#F59E0B',      // Yellow/amber for scrapes
        'analysis': '#10B981',    // Green for analysis
        'batch_scrape': '#F59E0B'
    };

    const typeLabels = {
        'scrape': 'SCRAPE',
        'analysis': 'ANALYSIS',
        'batch_scrape': 'BATCH'
    };

    const statusColor = statusColors[job.status] || '#6B7280';
    const typeColor = typeColors[job.type] || '#6B7280';
    const typeLabel = typeLabels[job.type] || job.type.toUpperCase();
    const createdDate = job.created_at ? new Date(job.created_at).toLocaleString() : '';
    const isRunning = job.status === 'running' || job.status === 'starting';
    const progressPct = job.progress_pct || 0;
    const isCompleted = ['complete', 'failed', 'error', 'partial'].includes(job.status);

    // Extract creator names from title (remove "Scrape: " or "Analysis: " prefix)
    let creatorNames = job.title || '';
    if (creatorNames.startsWith('Scrape: ')) {
        creatorNames = creatorNames.replace('Scrape: ', '');
    } else if (creatorNames.startsWith('Analysis: ')) {
        creatorNames = creatorNames.replace('Analysis: ', '');
    } else if (creatorNames.startsWith('Batch: ')) {
        creatorNames = creatorNames.replace('Batch: ', '');
    }

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

    // Star button for recent/starred jobs (not archived)
    const starButton = listType !== 'active' && listType !== 'archived' ? `
        <button class="btn-icon job-star${job.starred ? ' starred' : ''}"
                onclick="toggleJobStar('${job.id}'); event.stopPropagation();"
                title="${job.starred ? 'Unfavorite' : 'Favorite'}">
            ${job.starred ? '★' : '☆'}
        </button>
    ` : '';

    // View assets button for completed jobs (not archived)
    // Use result.id for scrape jobs since that's what's stored in history
    const assetFilterId = job.result?.id || job.id;
    const viewAssetsButton = isCompleted && listType !== 'archived' ? `
        <button class="btn btn-view-assets" onclick="filterLibraryByJob('${assetFilterId}'); event.stopPropagation();" title="View job assets in library">
            VIEW ASSETS
        </button>
    ` : '';

    // Delete button for recent jobs (archives them)
    const deleteButton = listType === 'recent' ? `
        <button class="btn btn-delete-job" onclick="archiveJob('${job.id}'); event.stopPropagation();" title="Delete job">
            DELETE
        </button>
    ` : '';

    // Rerun button for completed recent jobs (scrape and analysis)
    const rerunButton = listType === 'recent' && isCompleted && (job.type === 'scrape' || job.type === 'analysis') ? `
        <button class="btn btn-rerun-job" onclick="rerunJob('${job.id}', '${job.type}'); event.stopPropagation();" title="Rerun job">
            RERUN
        </button>
    ` : '';

    // Restore button for archived jobs
    const restoreButton = listType === 'archived' ? `
        <button class="btn btn-restore-job" onclick="restoreJob('${job.id}'); event.stopPropagation();" title="Restore job">
            RESTORE
        </button>
    ` : '';

    // Archived date for archived jobs
    const archivedDate = job.archived_at ? new Date(job.archived_at).toLocaleString() : '';
    const dateDisplay = listType === 'archived' && archivedDate
        ? `<span class="job-date">Archived: ${archivedDate}</span>`
        : `<span class="job-date">${createdDate}</span>`;

    return `
        <div class="job-card${isRunning ? ' running' : ''}${listType === 'archived' ? ' archived' : ''}" data-job-id="${job.id}" data-job-type="${job.type}" data-asset-filter-id="${assetFilterId}">
            <div class="job-card-header">
                <span class="job-type-badge" style="background: ${typeColor}20; color: ${typeColor}">
                    ${typeLabel}
                </span>
                <span class="job-title">${creatorNames}</span>
                ${starButton}
                <span class="job-status" style="background: ${statusColor}20; color: ${statusColor}">
                    ${job.status}
                </span>
            </div>
            ${progressBar}
            ${progressText ? `<p class="job-progress-text">${progressText}</p>` : ''}
            <div class="job-meta">
                ${dateDisplay}
                ${job.platform ? `<span class="job-platform">${job.platform.toUpperCase()}</span>` : ''}
            </div>
            <div class="job-actions">
                ${viewAssetsButton}
                ${rerunButton}
                ${deleteButton}
                ${restoreButton}
                ${abortButton}
            </div>
        </div>
    `;
}

// Toggle job star status
async function toggleJobStar(jobId) {
    console.log('[Workspace] Toggling star for job:', jobId);
    try {
        const response = await fetch(`/api/jobs/${jobId}/star`, { method: 'POST' });
        const result = await response.json();
        console.log('[Workspace] Star toggle response:', result);
        if (result.success) {
            // Refresh the jobs list
            const currentTab = document.querySelector('.jobs-tab.active')?.dataset.tab || 'recent';
            loadJobs(currentTab);
            updateStarredJobsCount();
        } else {
            console.error('[Workspace] Star toggle failed:', result.error);
        }
    } catch (error) {
        console.error('[Workspace] Failed to toggle job star:', error);
    }
}

// Archive (soft delete) a job
async function archiveJob(jobId) {
    try {
        const response = await fetch(`/api/jobs/${jobId}/archive`, { method: 'POST' });
        const result = await response.json();
        if (result.success) {
            console.log('[Workspace] Job archived:', jobId);
            // Refresh the jobs list
            loadJobs('recent');
            updateStarredJobsCount();
        } else {
            console.error('[Workspace] Failed to archive job:', result.error);
        }
    } catch (error) {
        console.error('[Workspace] Failed to archive job:', error);
    }
}

// Restore a job from archive
async function restoreJob(jobId) {
    try {
        const response = await fetch(`/api/jobs/${jobId}/restore`, { method: 'POST' });
        const result = await response.json();
        if (result.success) {
            console.log('[Workspace] Job restored:', jobId);
            // Refresh the archived list
            loadJobs('archived');
            updateStarredJobsCount();
        } else {
            console.error('[Workspace] Failed to restore job:', result.error);
        }
    } catch (error) {
        console.error('[Workspace] Failed to restore job:', error);
    }
}

// Clear all recent jobs (archive them all)
async function clearAllJobs() {
    if (!confirm('Archive all recent jobs? They can be restored from the Archived tab.')) {
        return;
    }

    try {
        const response = await fetch('/api/jobs/clear-all', { method: 'POST' });
        const result = await response.json();
        if (result.success) {
            console.log('[Workspace] Archived', result.archived_count, 'jobs');
            // Refresh the jobs list
            loadJobs('recent');
            updateStarredJobsCount();
        } else {
            console.error('[Workspace] Failed to clear jobs:', result.error);
        }
    } catch (error) {
        console.error('[Workspace] Failed to clear jobs:', error);
    }
}

// Rerun a job with the same parameters
async function rerunJob(jobId, jobType) {
    try {
        // Get the job details to get original config
        let config;

        if (jobType === 'scrape') {
            // Fetch job details from recent jobs
            const response = await fetch('/api/jobs/recent');
            const data = await response.json();
            const job = data.jobs?.find(j => j.id === jobId);

            if (!job || !job.result) {
                console.error('[Workspace] Could not find job config for rerun');
                alert('Could not find job configuration. Try starting a new scrape.');
                return;
            }

            // Get original config from result
            const result = job.result;
            config = {
                username: result.username || job.title?.replace('@', ''),
                platform: job.platform || 'instagram',
                max_reels: result.max_reels || 100,
                top_n: result.top_n || 10,
                download: result.download || false,
                transcribe: result.transcribe || false,
                transcribe_provider: result.transcribe_provider || 'local',
                whisper_model: result.whisper_model || 'small.en'
            };

            // Start new scrape with same config
            const scrapeResponse = await fetch('/api/scrape', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });

            const scrapeResult = await scrapeResponse.json();
            if (scrapeResult.scrape_id) {
                console.log('[Workspace] Rerun scrape started:', scrapeResult.scrape_id);
                // Switch to active jobs
                document.querySelector('.jobs-tab[data-tab="active"]')?.click();
                loadJobs('active');
            } else {
                alert('Failed to start scrape: ' + (scrapeResult.error || 'Unknown error'));
            }
        } else if (jobType === 'analysis') {
            // Fetch job details from recent jobs
            const response = await fetch('/api/jobs/recent');
            const data = await response.json();
            const job = data.jobs?.find(j => j.id === jobId);

            if (!job) {
                console.error('[Workspace] Could not find job config for rerun');
                alert('Could not find job configuration. Try starting a new analysis.');
                return;
            }

            // Get original config - analysis jobs store creators and settings
            const creators = job.creators || [];
            const platform = job.platform || 'instagram';

            if (creators.length === 0) {
                alert('Could not find creators for this analysis. Try starting a new analysis.');
                return;
            }

            // Get current AI settings
            const settingsResponse = await fetch('/api/settings');
            const settings = await settingsResponse.json();

            // Build analysis config
            const analysisConfig = {
                usernames: creators,
                platform: platform,
                videos_per_creator: job.videos_per_creator || 3,
                llm_provider: settings.llm_provider || 'openai',
                llm_model: settings.llm_model || 'gpt-4o-mini'
            };

            // Start new analysis with same config
            const analysisResponse = await fetch('/api/skeleton-ripper/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(analysisConfig)
            });

            const analysisResult = await analysisResponse.json();
            if (analysisResult.job_id) {
                console.log('[Workspace] Rerun analysis started:', analysisResult.job_id);
                // Track the job and switch to active tab
                trackedActiveJobs.add(analysisResult.job_id);
                startJobsPolling();
                document.querySelector('.jobs-tab[data-tab="active"]')?.click();
                setTimeout(() => loadJobs('active'), 100);
            } else {
                alert('Failed to start analysis: ' + (analysisResult.error || 'Unknown error'));
            }
        } else {
            alert('Rerun is not available for this job type.');
        }
    } catch (error) {
        console.error('[Workspace] Failed to rerun job:', error);
        alert('Failed to rerun job. See console for details.');
    }
}

// Navigate to library filtered by job
function filterLibraryByJob(jobId) {
    // Switch to library view
    switchView('library');
    // Reload assets with job filter
    reloadAssets({ job_id: jobId });
    // Update UI to show filter is active
    showJobFilter(jobId);
}

// Show job filter indicator in library
function showJobFilter(jobId) {
    const filterBar = document.querySelector('.filter-bar');
    if (!filterBar) return;

    // Remove existing job filter chip
    filterBar.querySelector('.job-filter-chip')?.remove();

    // Add job filter chip
    const chip = document.createElement('button');
    chip.className = 'filter-chip job-filter-chip active';
    chip.innerHTML = `Job: ${jobId.substring(0, 8)}... <span class="remove-filter">×</span>`;
    chip.onclick = (e) => {
        if (e.target.classList.contains('remove-filter')) {
            chip.remove();
            reloadAssets({});
        }
    };
    filterBar.appendChild(chip);
}

// Update starred jobs count in sidebar
async function updateStarredJobsCount() {
    try {
        const response = await fetch('/api/jobs/starred');
        const result = await response.json();
        const count = result.jobs?.length || 0;
        const countEl = document.getElementById('starred-jobs-count');
        if (countEl) countEl.textContent = count;
    } catch (error) {
        console.error('[Workspace] Failed to get starred jobs count:', error);
    }
}

function openJobDetail(jobId, jobType) {
    console.log('[Workspace] Opening job:', jobId, jobType);
    // Navigate to library filtered by this job's assets
    filterLibraryByJob(jobId);
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
    // If transcript visibility filter is active, use that instead of normal filtering
    if (typeof visibleTranscriptIds !== 'undefined' && visibleTranscriptIds.size > 0) {
        const visibleAssets = state.assets.filter(a => visibleTranscriptIds.has(a.id));
        renderAssets(visibleAssets);
        updateAssetCount(visibleAssets.length);
    } else {
        const filtered = filterAssets(state.assets, state.filters);
        renderAssets(filtered);
    }
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

    // Apply current view mode (persisted from server settings)
    grid.classList.remove('view-list', 'view-grid-2', 'view-grid-3', 'view-grid-4');
    grid.classList.add(`view-${currentAssetViewMode}`);

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
                // Refresh sidebar collections to update counts
                loadCollections();
                console.log('[Workspace] Removed from collection:', collectionId);
            } catch (error) {
                console.error('[Workspace] Failed to remove from collection:', error);
            }
        });
    });
}

// Remove asset from collection (called from inline onclick in asset cards)
async function removeFromCollection(assetId, collectionId) {
    try {
        await API.removeFromCollection(assetId, collectionId);
        // Refresh the assets to update UI
        await loadAssets();
        // Refresh sidebar collections to update counts
        loadCollections();
        console.log('[Workspace] Removed asset', assetId, 'from collection:', collectionId);
    } catch (error) {
        console.error('[Workspace] Failed to remove from collection:', error);
    }
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
    // Compact date format to prevent wrapping (e.g., "1/5/26 7:53am")
    const dateObj = asset.created_at ? new Date(asset.created_at) : null;
    const createdDate = dateObj ? `${dateObj.getMonth()+1}/${dateObj.getDate()}/${String(dateObj.getFullYear()).slice(-2)} ${dateObj.getHours() % 12 || 12}:${String(dateObj.getMinutes()).padStart(2,'0')}${dateObj.getHours() >= 12 ? 'pm' : 'am'}` : '';

    // Extract creator name(s) based on asset type (similar to job card title extraction)
    let creatorName = '';
    if (asset.type === 'scrape_report') {
        // Title format: "@username - Instagram" or similar
        creatorName = asset.title || 'Unknown';
        // Extract just the @username part if present
        const match = creatorName.match(/@[\w.]+/);
        if (match) creatorName = match[0];
    } else if (asset.type === 'skeleton_report') {
        // Use metadata.creators array
        const meta = asset.metadata || {};
        const creators = meta.creators || [];
        if (creators.length > 0) {
            creatorName = creators.slice(0, 3).map(c => `@${c}`).join(', ');
            if (creators.length > 3) creatorName += ` +${creators.length - 3}`;
        } else {
            creatorName = asset.title || 'Analysis';
        }
    } else if (asset.type === 'transcript' || asset.type === 'skeleton') {
        // Title format: "@creator: Content title..."
        const titleMatch = asset.title?.match(/^@[\w.]+/);
        creatorName = titleMatch ? titleMatch[0] : (asset.title?.substring(0, 40) || 'Untitled');
    } else {
        creatorName = asset.title?.substring(0, 40) || 'Untitled';
    }

    // Detect platform from metadata or title
    const platform = asset.metadata?.platform ||
                     asset.platform ||
                     (asset.title?.toLowerCase().includes('instagram') ? 'INSTAGRAM' :
                      asset.title?.toLowerCase().includes('tiktok') ? 'TIKTOK' : '');

    // Helper for proper pluralization
    const pluralize = (count, singular, plural) => count === 1 ? singular : plural;

    // Generate engagement stats and completion indicators
    let engagementBadges = [];
    let completionIndicators = []; // Compact icons for upper-right (conditional)

    if (asset.type === 'scrape_report') {
        const totalViews = asset.total_views || 0;
        const totalLikes = asset.total_likes || 0;
        const totalComments = asset.total_comments || 0;
        const totalReels = asset.reel_count || (asset.top_reels ? asset.top_reels.length : 0);
        const transcriptCount = asset.transcript_count ?? (asset.top_reels ? asset.top_reels.filter(r => r.transcript).length : 0);
        const videoCount = asset.video_count ?? (asset.top_reels ? asset.top_reels.filter(r => r.local_video).length : 0);

        // Engagement stats (views, likes, comments)
        if (totalViews > 0) engagementBadges.push(`<span class="stat-badge">${formatNumber(totalViews)} ${pluralize(totalViews, 'view', 'views')}</span>`);
        if (totalLikes > 0) engagementBadges.push(`<span class="stat-badge">${formatNumber(totalLikes)} ${pluralize(totalLikes, 'like', 'likes')}</span>`);
        if (totalComments > 0) engagementBadges.push(`<span class="stat-badge">${formatNumber(totalComments)} ${pluralize(totalComments, 'comment', 'comments')}</span>`);

        // Completion indicators (conditional - only show if incomplete or always show for context)
        // Format: icon + current/total with tooltip
        if (totalReels > 0) {
            const transcriptComplete = transcriptCount >= totalReels;
            const videoComplete = videoCount >= totalReels;

            // Always show these for scrape reports (useful context)
            completionIndicators.push(`<span class="completion-indicator ${transcriptComplete ? 'complete' : 'incomplete'}" title="Transcripts: ${transcriptCount} of ${totalReels} reels">📝${transcriptCount}/${totalReels}</span>`);
            completionIndicators.push(`<span class="completion-indicator ${videoComplete ? 'complete' : 'incomplete'}" title="Videos: ${videoCount} of ${totalReels} reels">🎬${videoCount}/${totalReels}</span>`);
        }

    } else if (asset.type === 'skeleton_report') {
        const meta = asset.metadata || {};
        const totalViews = meta.total_views || 0;
        const avgViews = meta.avg_views || 0;
        const skeletonCount = meta.skeletons_count || meta.video_count || 0;
        const creators = meta.creators || [];

        // Engagement/performance stats
        if (totalViews > 0) engagementBadges.push(`<span class="stat-badge">${formatNumber(totalViews)} ${pluralize(totalViews, 'view', 'views')}</span>`);
        if (avgViews > 0) engagementBadges.push(`<span class="stat-badge">${formatNumber(avgViews)} avg</span>`);

        // Completion indicators for skeleton reports
        if (skeletonCount > 0) completionIndicators.push(`<span class="completion-indicator complete" title="Skeletons extracted">🦴${skeletonCount}</span>`);
        if (creators.length > 0) completionIndicators.push(`<span class="completion-indicator complete" title="Creators analyzed">👤${creators.length}</span>`);

    } else if (asset.type === 'transcript') {
        // Show word count if available
        const wordCount = asset.metadata?.word_count || (asset.preview ? asset.preview.split(/\s+/).length : 0);
        if (wordCount > 0) engagementBadges.push(`<span class="stat-badge">${formatNumber(wordCount)} ${pluralize(wordCount, 'word', 'words')}</span>`);

    } else if (asset.type === 'skeleton') {
        const views = asset.metadata?.views || 0;
        if (views > 0) engagementBadges.push(`<span class="stat-badge">${formatNumber(views)} ${pluralize(views, 'view', 'views')}</span>`);
    }

    // Build completion indicators for upper-right of title row
    const completionHtml = completionIndicators.length > 0
        ? `<span class="header-completion">${completionIndicators.join('')}</span>`
        : '';

    // Build preview section (only for transcripts)
    let previewHtml = '';
    if (asset.type === 'transcript' && asset.preview) {
        // Truncate preview to ~150 chars for bird's eye view
        const truncatedPreview = asset.preview.length > 150
            ? asset.preview.substring(0, 150).trim() + '...'
            : asset.preview;
        previewHtml = `<div class="asset-preview">${truncatedPreview}</div>`;
    }

    // Render collection buttons (styled like job action buttons)
    const collections = asset.collections || [];
    const collectionButtons = collections.map(col => `
        <button class="btn-collection"
                style="background: ${col.color || '#6366f1'}15; color: ${col.color || '#6366f1'}; border-color: ${col.color || '#6366f1'}40"
                data-collection-id="${col.id}"
                data-asset-id="${asset.id}"
                onclick="event.stopPropagation();">
            ${col.name}
            <span class="collection-remove-x" onclick="removeFromCollection('${asset.id}', '${col.id}'); event.stopPropagation();" title="Remove">×</span>
        </button>
    `).join('');

    const addCollectionBtn = `
        <button class="btn-add-collection" onclick="openAddCollectionModal('${asset.id}'); event.stopPropagation();" title="Add to collection">
            +
        </button>
    `;

    // Build engagement stats for header meta row
    const allStatsHtml = engagementBadges.join('');

    return `
        <div class="asset-card" data-asset-id="${asset.id}">
            <div class="asset-card-header">
                <div class="header-top-row">
                    <span class="asset-type-badge" style="background: ${typeColor}20; color: ${typeColor}">
                        ${typeLabel}
                    </span>
                    <span class="asset-title">${creatorName}</span>
                    ${completionHtml}
                </div>
                <div class="header-meta-row">
                    <span class="asset-date">${createdDate}</span>
                    ${platform ? `<span class="asset-platform">${platform}</span>` : ''}
                    <span class="header-stats">${allStatsHtml}</span>
                </div>
            </div>
            ${previewHtml}
            <div class="asset-actions">
                ${collectionButtons}
                ${addCollectionBtn}
                <button class="btn-icon asset-star${asset.starred ? ' starred' : ''}"
                        onclick="toggleAssetStar('${asset.id}'); event.stopPropagation();"
                        title="${asset.starred ? 'Unfavorite' : 'Favorite'}">
                    ${asset.starred ? '★' : '☆'}
                </button>
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
            <span class="collection-name">All Assets</span>
            <span class="collection-count">0</span>
        </div>
    `;

    // Filter out collections with 0 assets
    const nonEmptyCollections = collections.filter(col => (col.asset_count || 0) > 0);

    const collectionItems = nonEmptyCollections.map(col => `
        <div class="collection-item" data-collection-id="${col.id}">
            <span class="collection-color" style="background: ${col.color || '#6366f1'}"></span>
            <span class="collection-name">${col.name}</span>
            <span class="collection-count">${col.asset_count || 0}</span>
            <button class="collection-delete-btn" data-collection-id="${col.id}" data-collection-name="${col.name}" title="Delete collection">×</button>
        </div>
    `).join('');

    list.innerHTML = allAssetsItem + collectionItems;

    // Add click handlers for collection items
    list.querySelectorAll('.collection-item').forEach(item => {
        item.addEventListener('click', (e) => {
            // Don't trigger if clicking delete button
            if (e.target.classList.contains('collection-delete-btn')) return;

            list.querySelectorAll('.collection-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            const collectionId = item.dataset.collectionId || null;
            Store.dispatch({ type: 'SET_FILTER', payload: { collection: collectionId } });
            // Reload assets with collection filter
            reloadAssets({ collection: collectionId });
        });
    });

    // Add click handlers for delete buttons
    list.querySelectorAll('.collection-delete-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const collectionId = btn.dataset.collectionId;
            const collectionName = btn.dataset.collectionName;
            openDeleteCollectionModal(collectionId, collectionName);
        });
    });
}

async function reloadAssets(filters = null) {
    try {
        // Always fetch all assets - filtering is done client-side via Store subscription
        const response = await API.getAssets({});
        const assets = response.assets || response || [];
        // Store subscription at line ~1083 will apply filters and call renderAssets
        Store.dispatch({ type: 'SET_ASSETS', payload: assets });
        // Update count based on filtered results
        const currentFilters = Store.getState().filters || {};
        const filtered = filterAssets(assets, currentFilters);
        updateAssetCount(filtered.length);
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

    // Clear transcript visibility filter and restore normal filtering
    if (visibleTranscriptIds.size > 0) {
        visibleTranscriptIds.clear();
        applyTranscriptVisibilityFilter();
    }
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

    // Store full asset for save operations (transcripts, skeletons)
    currentDetailAsset = asset;

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

        <div class="detail-section detail-section-content">
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

    // Sync eye toggle buttons with current visibility state
    syncTranscriptVisibilityToggles();
}

function calculateSkeletonStats(skeletons) {
    const totalVideos = skeletons.length;
    const totalViews = skeletons.reduce((sum, s) => sum + (s.views || 0), 0);
    const totalLikes = skeletons.reduce((sum, s) => sum + (s.likes || 0), 0);

    // Hook stats
    const hookWordCounts = skeletons.map(s => s.hook_word_count || 0).filter(c => c > 0);
    const avgHookWords = hookWordCounts.length > 0
        ? Math.round(hookWordCounts.reduce((a, b) => a + b, 0) / hookWordCounts.length * 10) / 10
        : 0;

    // Duration stats
    const durations = skeletons.map(s => s.estimated_duration_seconds || 0).filter(d => d > 0);
    const avgDuration = durations.length > 0
        ? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length)
        : 0;

    // Total word count stats
    const wordCounts = skeletons.map(s => s.total_word_count || 0).filter(c => c > 0);
    const avgWordCount = wordCounts.length > 0
        ? Math.round(wordCounts.reduce((a, b) => a + b, 0) / wordCounts.length)
        : 0;

    // Hook technique distribution
    const hookTechniques = {};
    skeletons.forEach(s => {
        const tech = s.hook_technique || 'unknown';
        hookTechniques[tech] = (hookTechniques[tech] || 0) + 1;
    });

    // Value structure distribution
    const valueStructures = {};
    skeletons.forEach(s => {
        const struct = s.value_structure || 'unknown';
        valueStructures[struct] = (valueStructures[struct] || 0) + 1;
    });

    // CTA type distribution
    const ctaTypes = {};
    skeletons.forEach(s => {
        const cta = s.cta_type || 'unknown';
        ctaTypes[cta] = (ctaTypes[cta] || 0) + 1;
    });

    // Get dominant patterns
    const dominantHook = Object.entries(hookTechniques).sort((a, b) => b[1] - a[1])[0];
    const dominantValue = Object.entries(valueStructures).sort((a, b) => b[1] - a[1])[0];
    const dominantCta = Object.entries(ctaTypes).sort((a, b) => b[1] - a[1])[0];

    return {
        totalVideos,
        totalViews,
        totalLikes,
        avgViews: totalVideos > 0 ? Math.round(totalViews / totalVideos) : 0,
        avgHookWords,
        avgDuration,
        avgWordCount,
        hookTechniques,
        valueStructures,
        ctaTypes,
        dominantHook: dominantHook ? { name: dominantHook[0], count: dominantHook[1], pct: Math.round(dominantHook[1] / totalVideos * 100) } : null,
        dominantValue: dominantValue ? { name: dominantValue[0], count: dominantValue[1], pct: Math.round(dominantValue[1] / totalVideos * 100) } : null,
        dominantCta: dominantCta ? { name: dominantCta[0], count: dominantCta[1], pct: Math.round(dominantCta[1] / totalVideos * 100) } : null
    };
}

function calculateScrapeStats(reels) {
    const totalReels = reels.length;
    const totalViews = reels.reduce((sum, r) => sum + (r.views || r.play_count || 0), 0);
    const totalLikes = reels.reduce((sum, r) => sum + (r.likes || r.like_count || 0), 0);
    const totalComments = reels.reduce((sum, r) => sum + (r.comments || r.comment_count || 0), 0);

    return {
        totalReels,
        totalViews,
        totalLikes,
        totalComments,
        avgViews: totalReels > 0 ? Math.round(totalViews / totalReels) : 0,
        avgLikes: totalReels > 0 ? Math.round(totalLikes / totalReels) : 0,
        avgComments: totalReels > 0 ? Math.round(totalComments / totalReels) : 0
    };
}

function renderScrapeMetadataHeader(stats, username, platform = 'instagram') {
    const profileUrl = platform === 'tiktok'
        ? `https://www.tiktok.com/@${username}`
        : `https://www.instagram.com/${username}/`;

    return `
        <div class="skeleton-metadata-header scrape-metadata-header">
            <div class="metadata-row primary">
                <div class="metadata-stat highlight">
                    <span class="stat-value">${stats.totalReels}</span>
                    <span class="stat-label">Reels</span>
                </div>
                <div class="metadata-stat highlight">
                    <span class="stat-value">${formatNumber(stats.totalViews)}</span>
                    <span class="stat-label">Total Views</span>
                </div>
                <div class="metadata-stat">
                    <span class="stat-value">${formatNumber(stats.totalLikes)}</span>
                    <span class="stat-label">Total Likes</span>
                </div>
                <div class="metadata-stat">
                    <span class="stat-value">${formatNumber(stats.totalComments)}</span>
                    <span class="stat-label">Total Comments</span>
                </div>
            </div>
            <div class="metadata-row secondary">
                <div class="metadata-stat small">
                    <span class="stat-value">${formatNumber(stats.avgViews)}</span>
                    <span class="stat-label">Avg Views</span>
                </div>
                <div class="metadata-stat small">
                    <span class="stat-value">${formatNumber(stats.avgLikes)}</span>
                    <span class="stat-label">Avg Likes</span>
                </div>
                <div class="metadata-stat small">
                    <span class="stat-value">${formatNumber(stats.avgComments)}</span>
                    <span class="stat-label">Avg Comments</span>
                </div>
            </div>
            <div class="metadata-creators">
                <a href="${profileUrl}" target="_blank" rel="noopener noreferrer" class="creator-tag" onclick="event.stopPropagation();">@${username}</a>
            </div>
        </div>
    `;
}

function renderSkeletonMetadataHeader(stats, creators, platform = 'instagram') {
    const creatorLinks = creators.map(c => {
        const profileUrl = platform === 'tiktok'
            ? `https://www.tiktok.com/@${c}`
            : `https://www.instagram.com/${c}/`;
        return `<a href="${profileUrl}" target="_blank" rel="noopener noreferrer" class="creator-tag" onclick="event.stopPropagation();">@${c}</a>`;
    }).join('');

    return `
        <div class="skeleton-metadata-header">
            <div class="metadata-row primary">
                <div class="metadata-stat highlight">
                    <span class="stat-value">${stats.totalVideos}</span>
                    <span class="stat-label">Videos Analyzed</span>
                </div>
                <div class="metadata-stat highlight">
                    <span class="stat-value">${formatNumber(stats.totalViews)}</span>
                    <span class="stat-label">Total Views</span>
                </div>
                <div class="metadata-stat">
                    <span class="stat-value">${formatNumber(stats.avgViews)}</span>
                    <span class="stat-label">Avg Views</span>
                </div>
                <div class="metadata-stat">
                    <span class="stat-value">${creators.length}</span>
                    <span class="stat-label">Creators</span>
                </div>
            </div>
            <div class="metadata-row secondary">
                <div class="metadata-stat small">
                    <span class="stat-value">${stats.avgHookWords}</span>
                    <span class="stat-label">Avg Hook Words</span>
                </div>
                <div class="metadata-stat small">
                    <span class="stat-value">${stats.avgWordCount}</span>
                    <span class="stat-label">Avg Total Words</span>
                </div>
                <div class="metadata-stat small">
                    <span class="stat-value">${stats.avgDuration}s</span>
                    <span class="stat-label">Avg Duration</span>
                </div>
            </div>
            <div class="metadata-row patterns">
                ${stats.dominantHook ? `
                    <div class="pattern-stat">
                        <span class="pattern-label">Top Hook:</span>
                        <span class="pattern-value">${stats.dominantHook.name}</span>
                        <span class="pattern-pct">(${stats.dominantHook.pct}%)</span>
                    </div>
                ` : ''}
                ${stats.dominantValue ? `
                    <div class="pattern-stat">
                        <span class="pattern-label">Top Structure:</span>
                        <span class="pattern-value">${stats.dominantValue.name}</span>
                        <span class="pattern-pct">(${stats.dominantValue.pct}%)</span>
                    </div>
                ` : ''}
                ${stats.dominantCta ? `
                    <div class="pattern-stat">
                        <span class="pattern-label">Top CTA:</span>
                        <span class="pattern-value">${stats.dominantCta.name}</span>
                        <span class="pattern-pct">(${stats.dominantCta.pct}%)</span>
                    </div>
                ` : ''}
            </div>
            <div class="metadata-creators">
                ${creatorLinks}
            </div>
        </div>
    `;
}

function renderAssetContent(asset) {
    // Handle scrape reports - show full reel details like v2 modal
    if (asset.type === 'scrape_report' && asset.top_reels && asset.top_reels.length > 0) {
        const stats = calculateScrapeStats(asset.top_reels);
        const platform = asset.metadata?.platform || 'instagram';
        const profileUrl = platform === 'tiktok'
            ? `https://www.tiktok.com/@${asset.username}`
            : `https://www.instagram.com/${asset.username}/`;

        // Build map of video URLs to transcript asset IDs
        const allAssets = Store.getState().assets || [];
        const savedTranscriptMap = new Map(
            allAssets
                .filter(a => a.type === 'transcript' && a.metadata?.video_url)
                .map(a => [a.metadata.video_url, a.id])
        );

        return `
            <div class="scrape-results">
                ${renderScrapeMetadataHeader(stats, asset.username, platform)}
                <div class="scrape-summary">
                    <strong>${asset.top_reels.length} reel${asset.top_reels.length === 1 ? '' : 's'}</strong> from <a href="${profileUrl}" target="_blank" rel="noopener noreferrer" class="creator-link" onclick="event.stopPropagation();">@${asset.username}</a>
                </div>
                <div class="reels-accordion">
                    ${asset.top_reels.map((reel, i) => renderReelAccordionItem(reel, i, asset.id, savedTranscriptMap, asset.username, platform)).join('')}
                </div>
            </div>
        `;
    }

    // Handle skeleton reports - tabbed view with Report and Skeletons
    if (asset.type === 'skeleton_report') {
        const hasSkeletons = asset.skeletons && asset.skeletons.length > 0;
        const hasMarkdown = asset.markdown && asset.markdown.trim().length > 0;
        const creators = hasSkeletons ? [...new Set(asset.skeletons.map(s => s.creator_username || 'unknown'))] : [];
        const platform = asset?.metadata?.platform || 'instagram';

        // Calculate accurate stats from skeleton data
        const stats = hasSkeletons ? calculateSkeletonStats(asset.skeletons) : null;

        // Build creator links for skeleton summary
        const creatorSummaryLinks = creators.map(c => {
            const profileUrl = platform === 'tiktok'
                ? `https://www.tiktok.com/@${c}`
                : `https://www.instagram.com/${c}/`;
            return `<a href="${profileUrl}" target="_blank" rel="noopener noreferrer" class="creator-link" onclick="event.stopPropagation();">@${c}</a>`;
        }).join(', ');

        return `
            <div class="skeleton-report-container">
                ${stats ? renderSkeletonMetadataHeader(stats, creators, platform) : ''}

                <div class="skeleton-report-tabs">
                    <button class="skeleton-tab active" data-tab="report" onclick="switchSkeletonTab('report')">
                        📊 Analysis Report
                    </button>
                    <button class="skeleton-tab" data-tab="skeletons" onclick="switchSkeletonTab('skeletons')">
                        🦴 Raw Skeletons (${hasSkeletons ? asset.skeletons.length : 0})
                    </button>
                </div>

                <div class="skeleton-tab-content" id="skeleton-tab-report">
                    ${hasMarkdown ? `
                        <div class="skeleton-report-markdown">
                            ${renderMarkdown(asset.markdown)}
                        </div>
                    ` : `
                        <div class="skeleton-report-empty">
                            <p>No analysis report available.</p>
                            <p class="text-muted">The synthesis may have failed or this is an older report.</p>
                        </div>
                    `}
                </div>

                <div class="skeleton-tab-content" id="skeleton-tab-skeletons" style="display: none;">
                    ${hasSkeletons ? `
                        <div class="skeleton-results">
                            <div class="skeleton-summary">
                                <strong>${asset.skeletons.length} skeleton${asset.skeletons.length === 1 ? '' : 's'}</strong> from ${creatorSummaryLinks}
                            </div>
                            <div class="skeletons-accordion">
                                ${asset.skeletons.map((sk, i) => renderSkeletonAccordionItem(sk, i, asset.id)).join('')}
                            </div>
                        </div>
                    ` : `
                        <div class="skeleton-report-empty">
                            <p>No skeletons extracted.</p>
                        </div>
                    `}
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

function renderReelAccordionItem(reel, index, scrapeId, savedTranscriptMap = new Map(), username = 'unknown', platform = 'instagram') {
    const views = reel.play_count || reel.plays || reel.views || 0;
    const likes = reel.like_count || reel.likes || 0;
    const comments = reel.comment_count || reel.comments || 0;
    const caption = reel.caption || 'No caption';
    const transcript = reel.transcript || null;
    const hasVideo = reel.local_video ? true : false;
    const url = reel.url || reel.video_url || '';
    const shortcode = reel.shortcode || reel.id || '';
    const savedTranscriptId = url ? savedTranscriptMap.get(url) : null;
    const transcriptAlreadySaved = !!savedTranscriptId;

    // Encode reel data for menu actions
    const reelDataAttr = escapeHtml(JSON.stringify({
        index,
        scrapeId,
        shortcode,
        url,
        hasVideo,
        hasTranscript: !!transcript
    }));

    return `
        <div class="reel-accordion-item" data-index="${index}">
            <div class="reel-accordion-row">
                <div class="reel-accordion-header" onclick="toggleReelAccordion(${index})">
                    <div class="reel-header-content">
                        <div class="reel-header-title">
                            <span class="reel-index">#${index + 1}</span>
                            <span class="reel-stat-primary">${formatNumber(views)} views</span>
                            <span class="reel-stat-primary">${formatNumber(likes)} likes</span>
                            <span class="reel-stat-primary">${formatNumber(comments)} comments</span>
                        </div>
                        <div class="reel-header-caption-subtitle">
                            ${escapeHtml(caption.substring(0, 80))}${caption.length > 80 ? '...' : ''}
                        </div>
                    </div>
                    <div class="reel-header-indicators">
                        <div class="reel-indicator ${transcript ? 'active' : ''}" title="${transcript ? 'Transcript available' : 'No transcript'}">
                            <span class="indicator-dot"></span>
                            <span class="indicator-label">${transcript ? 'Transcript' : 'No Transcript'}</span>
                        </div>
                        ${transcript ? `
                        <div class="reel-indicator reel-indicator-library ${transcriptAlreadySaved ? 'active' : 'not-saved'}"
                             data-transcript-id="${savedTranscriptId || ''}"
                             title="${transcriptAlreadySaved ? 'Saved to Library' : 'Not saved to Library'}">
                            <span class="indicator-dot"></span>
                            <span class="indicator-label">${transcriptAlreadySaved ? 'Library' : 'Not Saved'}</span>
                            ${transcriptAlreadySaved && visibleTranscriptIds.has(savedTranscriptId) ? `
                            <svg class="indicator-eye-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                                <circle cx="12" cy="12" r="3"/>
                            </svg>` : ''}
                        </div>
                        ` : ''}
                        <div class="reel-indicator ${hasVideo ? 'active' : ''}" title="${hasVideo ? 'Video downloaded' : 'Video not downloaded'}">
                            <span class="indicator-dot"></span>
                            <span class="indicator-label">${hasVideo ? 'Video' : 'No Video'}</span>
                        </div>
                        <span class="reel-accordion-arrow">▼</span>
                    </div>
                </div>
                <div class="reel-options-wrapper">
                    <button class="reel-options-btn" onclick="toggleReelOptionsMenu(event, ${index})" title="Options">
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                            <circle cx="8" cy="3" r="1.5"/>
                            <circle cx="8" cy="8" r="1.5"/>
                            <circle cx="8" cy="13" r="1.5"/>
                        </svg>
                    </button>
                    <div class="reel-options-menu" id="reel-options-menu-${index}" data-reel='${reelDataAttr}'>
                        ${hasVideo
                            ? '<div class="reel-menu-item" onclick="handleReelMenuAction(event, \'watch-video\')"><span class="menu-icon">▶</span>Watch Video</div>'
                            : '<div class="reel-menu-item" onclick="handleReelMenuAction(event, \'download-video\')"><span class="menu-icon">⬇</span>Download Video</div>'
                        }
                        ${url ? '<div class="reel-menu-item" onclick="handleReelMenuAction(event, \'view-instagram\')"><span class="menu-icon">↗</span>View in Instagram</div>' : ''}
                        <div class="reel-menu-separator"></div>
                        ${transcript
                            ? '<div class="reel-menu-item" onclick="handleReelMenuAction(event, \'copy-transcript\')"><span class="menu-icon">📋</span>Copy Transcript</div>'
                            : '<div class="reel-menu-item" onclick="handleReelMenuAction(event, \'transcribe\')"><span class="menu-icon">🎙</span>Transcribe</div>'
                        }
                        ${transcript
                            ? (transcriptAlreadySaved
                                ? `<div class="reel-menu-item reel-menu-item-saved">
                                    <span class="menu-icon">✓</span>Saved
                                    <button class="transcript-visibility-toggle" onclick="toggleTranscriptVisibility(event, '${savedTranscriptId}')" title="Toggle visibility in library">
                                        <svg class="eye-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                                            <circle cx="12" cy="12" r="3"/>
                                        </svg>
                                    </button>
                                   </div>`
                                : '<div class="reel-menu-item" onclick="handleReelMenuAction(event, \'save-transcript\')"><span class="menu-icon">💾</span>Save as Transcript</div>')
                            : ''}
                        <div class="reel-menu-item" onclick="handleReelMenuAction(event, \'rewrite-ai\')"><span class="menu-icon">✨</span>Rewrite with AI</div>
                        <div class="reel-menu-separator"></div>
                        <div class="reel-menu-item" onclick="handleReelMenuAction(event, \'copy-for-ai\')"><span class="menu-icon">📄</span>Copy for AI</div>
                        <div class="reel-menu-separator"></div>
                        <div class="reel-menu-item reel-menu-item-danger" onclick="handleReelMenuAction(event, \'delete-reel\')"><span class="menu-icon">🗑</span>Delete Reel</div>
                    </div>
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

                <!-- Caption (collapsible) -->
                <div class="reel-section reel-collapsible-section">
                    <div class="reel-section-title reel-section-toggle" onclick="toggleReelSection(${index}, 'caption')">
                        <span>CAPTION / HOOK</span>
                        <span class="section-toggle-arrow" id="caption-arrow-${index}">▼</span>
                    </div>
                    <div class="reel-section-content" id="reel-caption-${index}">
                        <div class="reel-caption-full">${escapeHtml(caption)}</div>
                    </div>
                </div>

                <!-- Transcript (collapsible) -->
                ${transcript ? `
                <div class="reel-section reel-collapsible-section">
                    <div class="reel-section-title reel-section-toggle" onclick="toggleReelSection(${index}, 'transcript')">
                        <span>TRANSCRIPT</span>
                        <span class="section-toggle-arrow" id="transcript-arrow-${index}">▼</span>
                    </div>
                    <div class="reel-section-content" id="reel-transcript-${index}">
                        <div class="reel-transcript">${escapeHtml(transcript)}</div>
                        <div class="reel-section-actions">
                            <button class="btn-copy-sm" onclick="copyTranscriptFromReel(${index})">COPY</button>
                            ${transcriptAlreadySaved
                                ? '<button class="btn-save-sm saved" disabled>✓ SAVED</button>'
                                : `<button class="btn-save-sm" onclick="saveTranscriptAsAsset(${index}, '${scrapeId}')">SAVE TO LIBRARY</button>`
                            }
                            <button class="btn-rewrite-sm" onclick="openRewriteModal('${scrapeId}', '${shortcode}')">REWRITE WITH AI</button>
                        </div>
                    </div>
                </div>
                ` : `
                <div class="reel-section reel-collapsible-section reel-no-transcript">
                    <div class="reel-section-title reel-section-toggle" onclick="toggleReelSection(${index}, 'transcript')">
                        <span>TRANSCRIPT</span>
                        <span class="section-toggle-arrow" id="transcript-arrow-${index}">▼</span>
                    </div>
                    <div class="reel-section-content" id="reel-transcript-${index}">
                        <div class="reel-transcript-empty">No transcript available</div>
                    </div>
                </div>
                `}

                <!-- Metadata (collapsible, open by default) -->
                <div class="reel-section reel-collapsible-section reel-metadata-section">
                    <div class="reel-section-title reel-section-toggle" onclick="toggleReelSection(${index}, 'metadata')">
                        <span>METADATA</span>
                        <span class="section-toggle-arrow" id="metadata-arrow-${index}">▼</span>
                    </div>
                    <div class="reel-section-content" id="reel-metadata-${index}">
                        <pre class="reel-metadata-json">${escapeHtml(JSON.stringify({
                            username: username,
                            platform: platform,
                            video_url: url || null,
                            views: views,
                            likes: likes,
                            comments: comments,
                            caption: caption,
                            transcript: transcript || null,
                            shortcode: shortcode || null,
                            has_video: hasVideo,
                            source_report_id: scrapeId
                        }, null, 2))}</pre>
                        <button class="btn-copy-sm" onclick="copyReelMetadata(${index})">COPY JSON</button>
                    </div>
                </div>

                <!-- Actions -->
                <div class="reel-actions">
                    ${url ? `<a href="${escapeHtml(url)}" target="_blank" class="btn btn-secondary btn-sm btn-ig"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg> OPEN IN IG</a>` : ''}
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

// Reel Options Menu Functions
let activeReelMenu = null;

// Track which transcript assets are currently visible in the library filter
let visibleTranscriptIds = new Set();

window.toggleTranscriptVisibility = function(event, transcriptId) {
    event.stopPropagation();

    const btn = event.currentTarget;
    const isActive = visibleTranscriptIds.has(transcriptId);

    if (isActive) {
        // Remove from visible set
        visibleTranscriptIds.delete(transcriptId);
        btn.classList.remove('active');
    } else {
        // Add to visible set
        visibleTranscriptIds.add(transcriptId);
        btn.classList.add('active');
    }

    // Update all header indicators to show/hide eye icons
    syncHeaderIndicatorEyes();

    // Update the library filter to show/hide these specific assets
    applyTranscriptVisibilityFilter();
};

function syncHeaderIndicatorEyes() {
    // Find all library indicators and update their eye icons
    document.querySelectorAll('.reel-indicator-library[data-transcript-id]').forEach(indicator => {
        const transcriptId = indicator.dataset.transcriptId;
        const existingEye = indicator.querySelector('.indicator-eye-icon');

        if (visibleTranscriptIds.has(transcriptId)) {
            // Add eye if not present
            if (!existingEye) {
                const eyeSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
                eyeSvg.classList.add('indicator-eye-icon');
                eyeSvg.setAttribute('width', '12');
                eyeSvg.setAttribute('height', '12');
                eyeSvg.setAttribute('viewBox', '0 0 24 24');
                eyeSvg.setAttribute('fill', 'none');
                eyeSvg.setAttribute('stroke', 'currentColor');
                eyeSvg.setAttribute('stroke-width', '2');
                eyeSvg.innerHTML = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>';
                indicator.appendChild(eyeSvg);
            }
        } else {
            // Remove eye if present
            if (existingEye) {
                existingEye.remove();
            }
        }
    });
}

function applyTranscriptVisibilityFilter() {
    const assets = Store.getState().assets || [];
    const currentFilters = Store.getState().filters || {};

    if (visibleTranscriptIds.size === 0) {
        // No specific transcripts selected - use normal filtering
        const filtered = filterAssets(assets, currentFilters);
        renderAssets(filtered);
        updateAssetCount(filtered.length);
    } else {
        // Filter to show ONLY the selected transcript IDs
        const visibleAssets = assets.filter(a => visibleTranscriptIds.has(a.id));
        renderAssets(visibleAssets);
        updateAssetCount(visibleAssets.length);
    }
}

// Update all eye toggle buttons to reflect current state when panel opens
function syncTranscriptVisibilityToggles() {
    document.querySelectorAll('.transcript-visibility-toggle').forEach(btn => {
        const onclick = btn.getAttribute('onclick');
        const match = onclick?.match(/toggleTranscriptVisibility\(event, '([^']+)'\)/);
        if (match) {
            const transcriptId = match[1];
            if (visibleTranscriptIds.has(transcriptId)) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        }
    });
}

window.toggleReelOptionsMenu = function(event, index) {
    event.stopPropagation();

    const menu = document.getElementById(`reel-options-menu-${index}`);
    const btn = event.currentTarget;

    // Close any other open menu
    if (activeReelMenu && activeReelMenu !== menu) {
        activeReelMenu.classList.remove('visible');
        document.querySelector('.reel-options-btn.active')?.classList.remove('active');
    }

    // Toggle this menu
    const isOpen = menu.classList.contains('visible');
    if (isOpen) {
        menu.classList.remove('visible');
        btn.classList.remove('active');
        activeReelMenu = null;
    } else {
        // Position the menu using fixed positioning
        const btnRect = btn.getBoundingClientRect();
        menu.style.top = `${btnRect.bottom + 4}px`;
        menu.style.right = `${window.innerWidth - btnRect.right}px`;

        menu.classList.add('visible');
        btn.classList.add('active');
        activeReelMenu = menu;
    }
}

function closeAllReelMenus() {
    document.querySelectorAll('.reel-options-menu.visible').forEach(menu => {
        menu.classList.remove('visible');
        menu.previousElementSibling?.classList.remove('active');
    });
    activeReelMenu = null;
}

// Close menu when clicking outside
document.addEventListener('click', (e) => {
    if (activeReelMenu && !e.target.closest('.reel-options-wrapper')) {
        closeAllReelMenus();
    }
});

// Close menu on Escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && activeReelMenu) {
        closeAllReelMenus();
    }
});

window.handleReelMenuAction = function(event, action) {
    event.stopPropagation();

    const menu = event.target.closest('.reel-options-menu');
    const reelData = JSON.parse(menu.dataset.reel);
    const { index, scrapeId, shortcode, url, hasVideo, hasTranscript } = reelData;

    // Menu stays open - user closes manually by clicking outside or three-dots

    switch (action) {
        case 'watch-video':
            // Placeholder - video viewer not yet implemented
            console.log('Watch video:', index, scrapeId);
            alert('Video viewer coming soon!');
            break;

        case 'download-video':
            downloadReelVideo(index, scrapeId, shortcode);
            break;

        case 'view-instagram':
            if (url) {
                window.open(url, '_blank', 'noopener,noreferrer');
            }
            break;

        case 'copy-transcript':
            copyTranscriptFromReel(index);
            showMenuItemFeedback(event.target.closest('.reel-menu-item'), 'Copied');
            return; // Don't close menu immediately

        case 'transcribe':
            transcribeReel(index, scrapeId, shortcode);
            break;

        case 'rewrite-ai':
            openRewriteModal(scrapeId, shortcode);
            break;

        case 'copy-for-ai':
            copyReelForAI(index);
            showMenuItemFeedback(event.target.closest('.reel-menu-item'), 'Copied');
            return; // Don't close menu immediately

        case 'save-transcript':
            // saveTranscriptAsAsset handles its own UI updates - don't use showMenuItemFeedback
            // as it would restore the original HTML and overwrite the permanent "Saved" state
            saveTranscriptAsAsset(index, scrapeId, event.target.closest('.reel-menu-item'));
            return;

        case 'delete-reel':
            deleteReelFromAsset(index, scrapeId);
            break;
    }
}

function showMenuItemFeedback(menuItem, message) {
    if (!menuItem) return;

    const originalHTML = menuItem.innerHTML;
    menuItem.innerHTML = `<span class="menu-icon" style="color: #10b981;">✓</span><span style="color: #10b981;">${message}</span>`;
    menuItem.style.pointerEvents = 'none';

    setTimeout(() => {
        menuItem.innerHTML = originalHTML;
        menuItem.style.pointerEvents = '';
        // Menu stays open - user closes manually
    }, 1500);
}

// Delete reel modal state
let pendingDeleteReel = null;

function openDeleteReelModal(index, scrapeId) {
    if (!currentDetailAsset || !currentDetailAsset.top_reels) {
        console.error('[Workspace] Cannot delete: asset data not loaded');
        return;
    }

    const reel = currentDetailAsset.top_reels[index];
    if (!reel) {
        console.error('[Workspace] Reel not found at index:', index);
        return;
    }

    // Check if this reel has a saved transcript in the library
    const reelUrl = reel.url || reel.video_url || '';
    const allAssets = Store.getState().assets || [];
    const savedTranscript = allAssets.find(a =>
        a.type === 'transcript' && a.metadata?.video_url === reelUrl
    );

    // Store pending delete info including transcript ID if it exists
    pendingDeleteReel = {
        index,
        scrapeId,
        reel,
        savedTranscriptId: savedTranscript?.id || null
    };

    // Update modal message
    const messageEl = document.getElementById('deleteReelMessage');
    if (messageEl) {
        const caption = (reel.caption || 'No caption').substring(0, 50);
        messageEl.innerHTML = `Delete <strong>Reel #${index + 1}</strong> from this scrape report?<br><br><span style="color: var(--color-text-muted); font-size: var(--text-xs);">"${caption}${reel.caption?.length > 50 ? '...' : ''}"</span>`;
    }

    // Show/hide transcript deletion option
    const transcriptOption = document.getElementById('deleteTranscriptOption');
    const transcriptCheckbox = document.getElementById('deleteTranscriptCheckbox');
    if (transcriptOption && transcriptCheckbox) {
        if (savedTranscript) {
            transcriptOption.style.display = 'block';
            transcriptCheckbox.checked = false; // Default unchecked
        } else {
            transcriptOption.style.display = 'none';
            transcriptCheckbox.checked = false;
        }
    }

    // Reset confirm button
    const confirmBtn = document.getElementById('confirmDeleteReelBtn');
    if (confirmBtn) {
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'Delete Reel';
    }

    // Show modal
    const modal = document.getElementById('deleteReelModal');
    if (modal) {
        modal.classList.add('active');
    }

    // Close the options menu
    closeAllReelMenus();
}

function closeDeleteReelModal() {
    const modal = document.getElementById('deleteReelModal');
    if (modal) {
        modal.classList.remove('active');
    }
    pendingDeleteReel = null;
}

window.openDeleteReelModal = openDeleteReelModal;
window.closeDeleteReelModal = closeDeleteReelModal;

async function confirmDeleteReel() {
    if (!pendingDeleteReel) {
        closeDeleteReelModal();
        return;
    }

    const { index, scrapeId, savedTranscriptId } = pendingDeleteReel;
    const confirmBtn = document.getElementById('confirmDeleteReelBtn');

    // Check if user wants to delete the transcript too
    const deleteTranscriptCheckbox = document.getElementById('deleteTranscriptCheckbox');
    const deleteTranscript = savedTranscriptId && deleteTranscriptCheckbox?.checked;

    // Show loading state
    if (confirmBtn) {
        confirmBtn.disabled = true;
        confirmBtn.textContent = 'Deleting...';
    }

    try {
        // Call API to delete just this reel from the scrape report (not the whole scrape)
        const response = await API.deleteReelFromAsset(scrapeId, index, deleteTranscript ? savedTranscriptId : null);

        if (response.success) {
            // If transcript was also deleted, remove it from visibility filter if active
            if (deleteTranscript && savedTranscriptId) {
                visibleTranscriptIds.delete(savedTranscriptId);
            }

            closeDeleteReelModal();
            // Refresh the detail panel to show remaining reels
            await openAssetDetail(scrapeId);
            // Refresh library to update reel counts (and remove deleted transcript)
            reloadAssets();
        } else {
            throw new Error(response.error || 'Unknown error');
        }
    } catch (error) {
        console.error('[Workspace] Error deleting reel:', error);
        // Show error in modal instead of alert
        const messageEl = document.getElementById('deleteReelMessage');
        if (messageEl) {
            messageEl.innerHTML = `<span style="color: #ef4444;">Failed to delete reel: ${error.message}</span>`;
        }
        if (confirmBtn) {
            confirmBtn.disabled = false;
            confirmBtn.textContent = 'Try Again';
        }
    }
}

window.confirmDeleteReel = confirmDeleteReel;

// Opens the delete confirmation modal
async function deleteReelFromAsset(index, scrapeId) {
    openDeleteReelModal(index, scrapeId);
}

async function downloadReelVideo(index, scrapeId, shortcode) {
    // TODO: Implement video download via API
    console.log('Download video:', index, scrapeId, shortcode);
    alert('Video download functionality coming soon!');
}

async function transcribeReel(index, scrapeId, shortcode) {
    // TODO: Implement transcription via API
    console.log('Transcribe reel:', index, scrapeId, shortcode);
    alert('Transcription functionality coming soon!');
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
    // Use stored asset data for complete metadata
    if (!currentDetailAsset || !currentDetailAsset.top_reels) {
        // Fallback to DOM scraping if asset not loaded
        const item = document.querySelector(`.reel-accordion-item[data-index="${index}"]`);
        if (!item) return;
        const caption = item.querySelector('.reel-caption-full')?.textContent || '';
        const transcript = item.querySelector('.reel-transcript')?.textContent || '';
        let text = '';
        if (caption) text += `CAPTION:\n${caption}\n\n`;
        if (transcript) text += `TRANSCRIPT:\n${transcript}`;
        copyToClipboard(text.trim());
        return;
    }

    const reel = currentDetailAsset.top_reels[index];
    if (!reel) return;

    // Get all metadata
    const username = currentDetailAsset.username || currentDetailAsset.metadata?.username || 'unknown';
    const platform = currentDetailAsset.platform || currentDetailAsset.metadata?.platform || 'instagram';
    const videoUrl = reel.url || reel.video_url || reel.permalink || '';
    const views = reel.play_count || reel.plays || reel.views || 0;
    const likes = reel.like_count || reel.likes || 0;
    const comments = reel.comment_count || reel.comments || 0;
    const caption = reel.caption || '';
    const transcript = reel.transcript || '';

    // Format for AI with full context
    let text = `CREATOR: @${username}\n`;
    text += `PLATFORM: ${platform.charAt(0).toUpperCase() + platform.slice(1)}\n`;
    text += `URL: ${videoUrl}\n`;
    text += `VIEWS: ${views.toLocaleString()}\n`;
    text += `LIKES: ${likes.toLocaleString()}\n`;
    text += `COMMENTS: ${comments.toLocaleString()}\n`;
    text += `\n---\n\n`;
    if (caption) text += `CAPTION:\n${caption}\n\n`;
    if (transcript) text += `TRANSCRIPT:\n${transcript}`;

    copyToClipboard(text.trim());
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

function toggleReelSection(index, section) {
    const content = document.getElementById(`reel-${section}-${index}`);
    const arrow = document.getElementById(`${section}-arrow-${index}`);
    if (!content) return;

    const isHidden = content.style.display === 'none';
    content.style.display = isHidden ? 'block' : 'none';
    if (arrow) arrow.textContent = isHidden ? '▼' : '▶';
}

// Legacy alias for backwards compatibility
function toggleReelMetadata(index) {
    toggleReelSection(index, 'metadata');
}

function copyReelMetadata(index) {
    // Use stored asset data for complete metadata including username/platform
    if (!currentDetailAsset || !currentDetailAsset.top_reels) {
        // Fallback to DOM scraping
        const item = document.querySelector(`.reel-accordion-item[data-index="${index}"]`);
        if (!item) return;
        const json = item.querySelector('.reel-metadata-json')?.textContent || '{}';
        const btn = item.querySelector('.reel-metadata-content .btn-copy-sm');
        copyToClipboard(json, btn);
        return;
    }

    const reel = currentDetailAsset.top_reels[index];
    if (!reel) return;

    // Build complete metadata object with asset-level context
    const username = currentDetailAsset.username || currentDetailAsset.metadata?.username || 'unknown';
    const platform = currentDetailAsset.platform || currentDetailAsset.metadata?.platform || 'instagram';

    const metadata = {
        username: username,
        platform: platform,
        video_url: reel.url || reel.video_url || reel.permalink || null,
        views: reel.play_count || reel.plays || reel.views || 0,
        likes: reel.like_count || reel.likes || 0,
        comments: reel.comment_count || reel.comments || 0,
        caption: reel.caption || null,
        transcript: reel.transcript || null,
        shortcode: reel.shortcode || reel.id || null,
        has_video: !!reel.local_video,
        source_report_id: currentDetailAsset.id || null
    };

    const item = document.querySelector(`.reel-accordion-item[data-index="${index}"]`);
    const btn = item?.querySelector('.reel-metadata-content .btn-copy-sm');
    copyToClipboard(JSON.stringify(metadata, null, 2), btn);
}

// Store current asset for save operations
let currentDetailAsset = null;

async function saveTranscriptAsAsset(index, scrapeId, menuItemElement = null) {
    if (!currentDetailAsset || !currentDetailAsset.top_reels) {
        alert('Unable to save: asset data not loaded');
        return;
    }

    const reel = currentDetailAsset.top_reels[index];
    if (!reel || !reel.transcript) {
        alert('No transcript available to save');
        return;
    }

    const btn = document.querySelector(`.reel-accordion-item[data-index="${index}"] .btn-save-sm`);
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'SAVING...';
    }

    // Show saving state in menu item immediately
    if (menuItemElement) {
        menuItemElement.innerHTML = `<span class="menu-icon" style="color: #10b981;">⏳</span><span style="color: var(--color-text-secondary);">Saving...</span>`;
        menuItemElement.style.pointerEvents = 'none';
    }

    try {
        const response = await fetch('/api/assets/save-transcript', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                reel_data: reel,
                source_report_id: scrapeId,
                username: currentDetailAsset.username || 'unknown'
            })
        });

        const result = await response.json();
        if (response.ok) {
            const newAssetId = result.id;
            if (btn) {
                btn.textContent = '✓ SAVED';
                btn.classList.add('saved');
            }
            // Update the menu item to show "Saved" state with eye toggle
            const menuItem = menuItemElement || document.querySelector(`#reel-options-menu-${index} .reel-menu-item[onclick*="save-transcript"]`);
            if (menuItem) {
                menuItem.className = 'reel-menu-item reel-menu-item-saved';
                menuItem.removeAttribute('onclick');
                menuItem.style.pointerEvents = '';
                menuItem.innerHTML = `<span class="menu-icon">✓</span>Saved
                    <button class="transcript-visibility-toggle" onclick="toggleTranscriptVisibility(event, '${newAssetId}')" title="Toggle visibility in library">
                        <svg class="eye-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                            <circle cx="12" cy="12" r="3"/>
                        </svg>
                    </button>`;
            }

            // Update the header indicator to show "Library" (green) with data-transcript-id
            const accordionItem = document.querySelector(`.reel-accordion-item[data-index="${index}"]`);
            if (accordionItem) {
                const libraryIndicator = accordionItem.querySelector('.reel-indicator-library');
                if (libraryIndicator) {
                    // Update existing indicator
                    libraryIndicator.classList.remove('not-saved');
                    libraryIndicator.classList.add('active');
                    libraryIndicator.dataset.transcriptId = newAssetId;
                    libraryIndicator.title = 'Saved to Library';
                    libraryIndicator.querySelector('.indicator-label').textContent = 'Library';
                }
            }

            // Refresh library to show new asset
            reloadAssets();
        } else {
            throw new Error(result.error || 'Failed to save');
        }
    } catch (error) {
        console.error('[Workspace] Failed to save transcript:', error);
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'SAVE TO LIBRARY';
        }
        // Restore menu item on failure
        if (menuItemElement) {
            menuItemElement.style.pointerEvents = '';
            menuItemElement.innerHTML = '<span class="menu-icon">💾</span>Save as Transcript';
        }
        alert('Failed to save transcript: ' + error.message);
    }
}

window.saveTranscriptAsAsset = saveTranscriptAsAsset;

function renderSkeletonAccordionItem(skeleton, index, reportId) {
    const hook = skeleton.hook || 'No hook';
    const hookTechnique = skeleton.hook_technique || '';
    const hookWordCount = skeleton.hook_word_count || 0;
    const value = skeleton.value || '';
    const valueStructure = skeleton.value_structure || '';
    const valuePoints = skeleton.value_points || [];
    const cta = skeleton.cta || '';
    const ctaType = skeleton.cta_type || '';
    const creator = skeleton.creator_username || 'unknown';
    const views = skeleton.views || skeleton.metrics?.views || 0;
    const totalWords = skeleton.total_word_count || 0;
    const duration = skeleton.estimated_duration_seconds || 0;

    return `
        <div class="skeleton-accordion-item" data-index="${index}">
            <div class="skeleton-accordion-header" onclick="toggleSkeletonAccordion(${index})">
                <div class="skeleton-header-content">
                    <div class="skeleton-header-title">
                        <span class="skeleton-index">#${index + 1}</span>
                        <span class="skeleton-creator">@${creator}</span>
                        <span class="skeleton-header-hook">${escapeHtml(hook.substring(0, 60))}${hook.length > 60 ? '...' : ''}</span>
                    </div>
                    <div class="skeleton-header-meta">
                        ${hookTechnique ? `<span class="skeleton-tag technique">${hookTechnique}</span>` : ''}
                        ${views > 0 ? `<span class="skeleton-tag views">${formatNumber(views)} views</span>` : ''}
                    </div>
                </div>
                <span class="skeleton-accordion-arrow">▼</span>
            </div>
            <div class="skeleton-accordion-body" id="skeleton-body-${index}" style="display: none;">
                <!-- Hook Section -->
                <div class="skeleton-section">
                    <div class="skeleton-section-header">
                        <div class="skeleton-section-title">HOOK</div>
                        <div class="skeleton-section-meta">
                            ${hookTechnique ? `<span class="meta-tag">${hookTechnique}</span>` : ''}
                            ${hookWordCount > 0 ? `<span class="meta-tag">${hookWordCount} words</span>` : ''}
                        </div>
                    </div>
                    <div class="skeleton-content">${escapeHtml(hook)}</div>
                </div>

                <!-- Value Section -->
                ${value ? `
                <div class="skeleton-section">
                    <div class="skeleton-section-header">
                        <div class="skeleton-section-title">VALUE DELIVERY</div>
                        <div class="skeleton-section-meta">
                            ${valueStructure ? `<span class="meta-tag">${valueStructure}</span>` : ''}
                        </div>
                    </div>
                    <div class="skeleton-content">${escapeHtml(value)}</div>
                </div>
                ` : ''}

                <!-- Value Points -->
                ${valuePoints.length > 0 ? `
                <div class="skeleton-section">
                    <div class="skeleton-section-title">KEY POINTS</div>
                    <ul class="skeleton-key-points">
                        ${valuePoints.map(vp => `<li>${escapeHtml(vp)}</li>`).join('')}
                    </ul>
                </div>
                ` : ''}

                <!-- CTA -->
                ${cta ? `
                <div class="skeleton-section">
                    <div class="skeleton-section-header">
                        <div class="skeleton-section-title">CTA</div>
                        <div class="skeleton-section-meta">
                            ${ctaType ? `<span class="meta-tag">${ctaType}</span>` : ''}
                        </div>
                    </div>
                    <div class="skeleton-content">${escapeHtml(cta)}</div>
                </div>
                ` : ''}

                <!-- Stats Footer -->
                ${(totalWords > 0 || duration > 0) ? `
                <div class="skeleton-stats-footer">
                    ${totalWords > 0 ? `<span class="stat-item">${totalWords} words</span>` : ''}
                    ${duration > 0 ? `<span class="stat-item">~${duration}s</span>` : ''}
                </div>
                ` : ''}

                <!-- Actions -->
                <div class="skeleton-section-actions">
                    <button class="btn-copy-sm" onclick="copySkeletonContent(${index})">COPY</button>
                    <button class="btn-save-sm" onclick="saveSkeletonAsAsset(${index}, '${reportId}')">SAVE TO LIBRARY</button>
                </div>
            </div>
        </div>
    `;
}

function toggleSkeletonAccordion(index) {
    const body = document.getElementById(`skeleton-body-${index}`);
    const item = body.closest('.skeleton-accordion-item');
    const arrow = item.querySelector('.skeleton-accordion-arrow');

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

function copySkeletonContent(index) {
    if (!currentDetailAsset || !currentDetailAsset.skeletons) return;
    const sk = currentDetailAsset.skeletons[index];
    if (!sk) return;

    let text = `HOOK (${sk.hook_technique || 'unknown'}):\n${sk.hook || 'N/A'}\n\n`;
    if (sk.value) text += `VALUE (${sk.value_structure || 'unknown'}):\n${sk.value}\n\n`;
    if (sk.value_points && sk.value_points.length > 0) {
        text += `KEY POINTS:\n${sk.value_points.map(vp => `• ${vp}`).join('\n')}\n\n`;
    }
    if (sk.cta) text += `CTA (${sk.cta_type || 'unknown'}):\n${sk.cta}`;

    navigator.clipboard.writeText(text.trim()).then(() => {
        const btn = document.querySelector(`.skeleton-accordion-item[data-index="${index}"] .btn-copy-sm`);
        if (btn) {
            const original = btn.textContent;
            btn.textContent = '✓ COPIED';
            setTimeout(() => btn.textContent = original, 1500);
        }
    });
}

async function saveSkeletonAsAsset(index, reportId) {
    if (!currentDetailAsset || !currentDetailAsset.skeletons) {
        alert('Unable to save: asset data not loaded');
        return;
    }

    const skeleton = currentDetailAsset.skeletons[index];
    if (!skeleton) {
        alert('No skeleton available to save');
        return;
    }

    const btn = document.querySelector(`.skeleton-accordion-item[data-index="${index}"] .btn-save-sm`);
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'SAVING...';
    }

    try {
        const response = await fetch('/api/assets/save-skeleton', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                skeleton_data: skeleton,
                source_report_id: reportId
            })
        });

        const result = await response.json();
        if (response.ok) {
            if (btn) {
                btn.textContent = '✓ SAVED';
                btn.classList.add('saved');
            }
            reloadAssets();
        } else {
            throw new Error(result.error || 'Failed to save');
        }
    } catch (error) {
        console.error('[Workspace] Failed to save skeleton:', error);
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'SAVE TO LIBRARY';
        }
        alert('Failed to save skeleton: ' + error.message);
    }
}

window.toggleSkeletonAccordion = toggleSkeletonAccordion;
window.copySkeletonContent = copySkeletonContent;
window.saveSkeletonAsAsset = saveSkeletonAsAsset;

// Tab switching for skeleton reports
function switchSkeletonTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.skeleton-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabName);
    });

    // Update tab content
    document.querySelectorAll('.skeleton-tab-content').forEach(content => {
        content.style.display = content.id === `skeleton-tab-${tabName}` ? 'block' : 'none';
    });
}
window.switchSkeletonTab = switchSkeletonTab;

// Simple markdown to HTML renderer
function renderMarkdown(markdown) {
    if (!markdown) return '';

    // First, extract code blocks and replace with placeholders
    const codeBlocks = [];
    let processedMd = markdown.replace(/```([\s\S]*?)```/g, (match, code) => {
        const index = codeBlocks.length;
        // Preserve code content, add extra spacing between lines that look like labeled items
        let processedCode = code.trim()
            // Add blank line before lines that start with common labels
            .replace(/\n(Template:|Example|Why it works:|Use when:|Structure:|Step \d|Hook:|Value:|CTA:|Best for:|Duration:)/g, '\n\n$1');
        codeBlocks.push(processedCode);
        return `__CODE_BLOCK_${index}__`;
    });

    let html = processedMd
        // Escape HTML first
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        // Headers
        .replace(/^### (.*$)/gm, '<h3>$1</h3>')
        .replace(/^## (.*$)/gm, '<h2>$1</h2>')
        .replace(/^# (.*$)/gm, '<h1>$1</h1>')
        // Bold and italic
        .replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        // Inline code
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        // Horizontal rules
        .replace(/^---$/gm, '<hr>')
        // Unordered lists
        .replace(/^\s*[-*]\s+(.*)$/gm, '<li>$1</li>')
        // Paragraphs (double newlines)
        .replace(/\n\n/g, '</p><p>')
        // Line breaks
        .replace(/\n/g, '<br>');

    // Restore code blocks
    codeBlocks.forEach((code, index) => {
        const escapedCode = code
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        html = html.replace(`__CODE_BLOCK_${index}__`, `<pre><code>${escapedCode}</code></pre>`);
    });

    // Wrap list items in ul
    html = html.replace(/(<li>.*<\/li>)/gs, (match) => {
        if (!match.includes('<ul>')) {
            return '<ul>' + match + '</ul>';
        }
        return match;
    });

    // Clean up consecutive ul tags
    html = html.replace(/<\/ul>\s*<ul>/g, '');

    return '<div class="markdown-content"><p>' + html + '</p></div>';
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

// Toggle asset star from library card (takes assetId as parameter)
async function toggleAssetStar(assetId) {
    console.log('[Workspace] Toggling star for asset:', assetId);
    try {
        const result = await API.toggleStar(assetId);

        // Update in store (this triggers re-render of library and favorites)
        const state = Store.getState();
        const assets = state.assets.map(a =>
            a.id === assetId ? { ...a, starred: result.starred } : a
        );
        Store.dispatch({ type: 'SET_ASSETS', payload: assets });

        // Update favorites count in sidebar
        updateFavoritesCount(assets.filter(a => a.starred).length);

        // Also update detail panel star button if this asset is currently open
        const content = document.getElementById('detail-panel-content');
        if (content && content.dataset.assetId === assetId) {
            const starBtn = document.getElementById('btn-star-asset');
            if (starBtn) {
                starBtn.textContent = result.starred ? '★' : '☆';
                starBtn.classList.toggle('starred', result.starred);
            }
        }

        console.log('[Workspace] Toggled asset star:', result.starred);
    } catch (error) {
        console.error('[Workspace] Failed to toggle asset star:', error);
    }
}

function startInlineEdit(assetId) {
    const titleEl = document.querySelector(`.asset-title[data-asset-id="${assetId}"]`);
    if (!titleEl || titleEl.querySelector('input')) return; // Already editing

    const currentTitle = titleEl.textContent;
    const editBtn = titleEl.parentElement.querySelector('.btn-edit-title');

    // Hide the edit button while editing
    if (editBtn) editBtn.style.display = 'none';

    // Create input field
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'inline-title-input';
    input.value = currentTitle;

    // Replace title text with input
    titleEl.textContent = '';
    titleEl.appendChild(input);
    input.focus();
    input.select();

    // Handle save on blur or Enter
    const saveEdit = async () => {
        const newTitle = input.value.trim();
        if (newTitle && newTitle !== currentTitle) {
            try {
                const response = await fetch(`/api/assets/${assetId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: newTitle })
                });

                if (!response.ok) throw new Error('Failed to rename');

                // Update in store and re-render
                const state = Store.getState();
                const assets = state.assets.map(a =>
                    a.id === assetId ? { ...a, title: newTitle } : a
                );
                Store.dispatch({ type: 'SET_ASSETS', payload: assets });
                renderAssets(assets);

                console.log('[Workspace] Renamed asset:', newTitle);
            } catch (error) {
                console.error('[Workspace] Failed to rename:', error);
                titleEl.textContent = currentTitle;
            }
        } else {
            titleEl.textContent = currentTitle;
        }
        if (editBtn) editBtn.style.display = '';
    };

    const cancelEdit = () => {
        titleEl.textContent = currentTitle;
        if (editBtn) editBtn.style.display = '';
    };

    input.addEventListener('blur', saveEdit);
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            input.blur();
        } else if (e.key === 'Escape') {
            input.removeEventListener('blur', saveEdit);
            cancelEdit();
        }
    });
}

// Legacy function kept for compatibility
async function renameAsset(assetId, currentTitle) {
    startInlineEdit(assetId);
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

        // Navigate to jobs view and switch to active tab
        window.location.hash = '#jobs';
        // Ensure active tab is selected and jobs are loaded after navigation
        setTimeout(() => {
            document.querySelector('.jobs-tab[data-tab="active"]')?.click();
            loadJobs('active');
        }, 100);
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

        // Navigate to jobs view and switch to active tab
        window.location.hash = '#jobs';
        // Ensure active tab is selected and jobs are loaded after navigation
        setTimeout(() => {
            document.querySelector('.jobs-tab[data-tab="active"]')?.click();
            loadJobs('active');
        }, 100);
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
            usernames: creators,
            videos_per_creator: videosPerCreator,
            llm_provider: provider,
            llm_model: model
        });

        console.log('[Workspace] Analysis started:', result);

        // Track job for completion detection
        if (result.job_id) {
            trackedActiveJobs.add(result.job_id);
            startJobsPolling();
        }

        closeModal();

        // Navigate to jobs view and switch to active tab
        window.location.hash = '#jobs';
        // Ensure active tab is selected and jobs are loaded after navigation
        setTimeout(() => {
            document.querySelector('.jobs-tab[data-tab="active"]')?.click();
            loadJobs('active');
        }, 100);
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

// Resizable detail panel
function setupPanelResize() {
    const panel = document.getElementById('detail-panel');
    const resizeHandle = document.getElementById('detail-panel-resize');

    if (!panel || !resizeHandle) return;

    let isResizing = false;
    let startX = 0;
    let startWidth = 0;
    let saveTimeout = null;

    resizeHandle.addEventListener('mousedown', (e) => {
        isResizing = true;
        startX = e.clientX;
        startWidth = panel.offsetWidth;

        panel.classList.add('resizing');
        resizeHandle.classList.add('dragging');
        document.body.style.cursor = 'ew-resize';
        document.body.style.userSelect = 'none';

        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;

        // Calculate new width (dragging left increases width since panel is on right)
        const deltaX = startX - e.clientX;
        let newWidth = startWidth + deltaX;

        // Clamp to min/max
        const minWidth = 400;
        const maxWidth = window.innerWidth * 0.8;
        newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));

        panel.style.width = newWidth + 'px';
    });

    document.addEventListener('mouseup', () => {
        if (!isResizing) return;

        isResizing = false;
        panel.classList.remove('resizing');
        resizeHandle.classList.remove('dragging');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';

        // Save width preference to server (debounced)
        const currentWidth = parseInt(panel.style.width);
        if (saveTimeout) clearTimeout(saveTimeout);
        saveTimeout = setTimeout(() => {
            API.updateSettings({ detail_panel_width: currentWidth }).catch(err => {
                console.warn('[Workspace] Failed to save panel width:', err);
            });
        }, 500);
    });

    // Restore saved width from server settings
    API.getSettings().then(settings => {
        if (settings.detail_panel_width) {
            panel.style.width = settings.detail_panel_width + 'px';
        }
    }).catch(err => {
        console.warn('[Workspace] Failed to load panel width:', err);
    });
}

// Custom context menu for PyWebView (right-click copy/paste)
function setupContextMenu() {
    // Create context menu element
    const menu = document.createElement('div');
    menu.id = 'custom-context-menu';
    menu.innerHTML = `
        <div class="ctx-item" data-action="refresh">🔄 Refresh</div>
        <div class="ctx-divider"></div>
        <div class="ctx-item" data-action="copy">Copy</div>
        <div class="ctx-item" data-action="cut">Cut</div>
        <div class="ctx-item" data-action="paste">Paste</div>
        <div class="ctx-divider"></div>
        <div class="ctx-item" data-action="selectall">Select All</div>
    `;
    menu.style.cssText = `
        display: none;
        position: fixed;
        background: #27272a;
        border: 1px solid #3f3f46;
        border-radius: 6px;
        padding: 4px 0;
        min-width: 120px;
        z-index: 99999;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    `;
    document.body.appendChild(menu);

    // Style menu items
    const style = document.createElement('style');
    style.textContent = `
        #custom-context-menu .ctx-item {
            padding: 8px 16px;
            cursor: pointer;
            color: #fafafa;
            font-size: 13px;
        }
        #custom-context-menu .ctx-item:hover {
            background: #10b981;
        }
        #custom-context-menu .ctx-divider {
            height: 1px;
            background: #3f3f46;
            margin: 4px 0;
        }
    `;
    document.head.appendChild(style);

    // Store selection when menu opens (before it gets cleared by clicking menu)
    let savedSelection = '';
    let savedActiveElement = null;

    // Show menu on right-click
    document.addEventListener('contextmenu', (e) => {
        e.preventDefault();

        // Save selection NOW before clicking menu clears it
        savedSelection = window.getSelection().toString();
        savedActiveElement = document.activeElement;

        menu.style.display = 'block';
        menu.style.left = e.clientX + 'px';
        menu.style.top = e.clientY + 'px';

        // Adjust if menu goes off screen
        const rect = menu.getBoundingClientRect();
        if (rect.right > window.innerWidth) {
            menu.style.left = (e.clientX - rect.width) + 'px';
        }
        if (rect.bottom > window.innerHeight) {
            menu.style.top = (e.clientY - rect.height) + 'px';
        }
    });

    // Hide menu on click elsewhere
    document.addEventListener('click', (e) => {
        if (!menu.contains(e.target)) {
            menu.style.display = 'none';
        }
    });

    // Handle menu actions
    menu.addEventListener('click', async (e) => {
        const action = e.target.dataset.action;
        if (!action) return;

        try {
            switch (action) {
                case 'refresh':
                    window.location.reload();
                    break;
                case 'copy':
                    if (savedSelection) {
                        await navigator.clipboard.writeText(savedSelection);
                    }
                    break;
                case 'cut':
                    if (savedSelection && (savedActiveElement.tagName === 'INPUT' || savedActiveElement.tagName === 'TEXTAREA')) {
                        await navigator.clipboard.writeText(savedSelection);
                        savedActiveElement.focus();
                        document.execCommand('delete');
                    }
                    break;
                case 'paste':
                    if (savedActiveElement.tagName === 'INPUT' || savedActiveElement.tagName === 'TEXTAREA') {
                        const text = await navigator.clipboard.readText();
                        savedActiveElement.focus();
                        document.execCommand('insertText', false, text);
                    }
                    break;
                case 'selectall':
                    document.execCommand('selectAll');
                    break;
            }
        } catch (err) {
            console.error('Context menu action failed:', err);
        }
        menu.style.display = 'none';
    });
}

// =========================================
// STARRED JOBS VIEW
// =========================================

async function loadStarredJobs() {
    const list = document.getElementById('starred-jobs-list');
    if (!list) return;

    // Apply current view mode (same as main jobs list)
    list.classList.remove('view-list', 'view-grid-2', 'view-grid-3');
    list.classList.add(`view-${currentJobsViewMode}`);

    try {
        const response = await fetch('/api/jobs/starred');
        const data = await response.json();

        if (data.success && data.jobs.length > 0) {
            list.innerHTML = data.jobs.map(job => renderJobCard(job, 'starred')).join('');

            // Add click handlers
            list.querySelectorAll('.job-card').forEach(card => {
                card.addEventListener('click', () => {
                    // Use assetFilterId for library filtering (matches history/asset IDs)
                    const assetFilterId = card.dataset.assetFilterId;
                    const jobType = card.dataset.jobType;
                    openJobDetail(assetFilterId, jobType);
                });
            });
        } else {
            list.innerHTML = `<div class="empty-state"><p>No favorite jobs yet. Star jobs to see them here.</p></div>`;
        }
    } catch (error) {
        console.error('[Workspace] Failed to load starred jobs:', error);
        list.innerHTML = `<div class="empty-state"><p>Failed to load favorite jobs.</p></div>`;
    }
}

// Switch view programmatically
function switchView(viewName) {
    Router.navigate(viewName);
}

// =========================================
// COLLECTION MODAL FUNCTIONS
// =========================================

let addCollectionTargetAssetId = null;
let addCollectionSelectedColor = '#10B981';

function openAddCollectionModal(assetId) {
    addCollectionTargetAssetId = assetId;
    loadCollectionsForModal();
    document.getElementById('addCollectionModal').classList.add('active');
}

function closeAddCollectionModal() {
    document.getElementById('addCollectionModal').classList.remove('active');
    addCollectionTargetAssetId = null;
    cancelNewCollectionForm();
}

async function loadCollectionsForModal() {
    try {
        const response = await fetch('/api/collections');
        const collections = await response.json();

        const select = document.getElementById('addCollectionDropdown');
        select.innerHTML = '<option value="">-- Select Collection --</option>';

        collections.forEach(c => {
            const option = document.createElement('option');
            option.value = c.id;
            option.textContent = c.name;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('[Workspace] Failed to load collections:', error);
    }
}

function showNewCollectionForm() {
    document.getElementById('addCollectionNewForm').style.display = 'block';
    document.getElementById('addCollectionNewName').focus();
}

function cancelNewCollectionForm() {
    const form = document.getElementById('addCollectionNewForm');
    const input = document.getElementById('addCollectionNewName');
    if (form) form.style.display = 'none';
    if (input) input.value = '';
    selectCollectionColor('#10B981');
}

function selectCollectionColor(color) {
    addCollectionSelectedColor = color;
    document.querySelectorAll('#addCollectionColors .color-swatch').forEach(swatch => {
        swatch.classList.toggle('active', swatch.dataset.color === color);
    });
}

async function createNewCollection() {
    const name = document.getElementById('addCollectionNewName').value.trim();
    if (!name) {
        alert('Please enter a collection name');
        return;
    }

    try {
        const response = await fetch('/api/collections', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                color: addCollectionSelectedColor
            })
        });

        if (!response.ok) throw new Error('Failed to create collection');

        const collection = await response.json();

        // Reload collections and select the new one
        await loadCollectionsForModal();
        document.getElementById('addCollectionDropdown').value = collection.id;

        // Hide form
        cancelNewCollectionForm();

        // Also refresh sidebar collections
        loadCollections();
    } catch (error) {
        console.error('[Workspace] Failed to create collection:', error);
        alert('Failed to create collection');
    }
}

async function confirmAddToCollection() {
    const select = document.getElementById('addCollectionDropdown');
    const collectionId = select.value;

    if (!collectionId) {
        alert('Please select a collection');
        return;
    }

    if (!addCollectionTargetAssetId) {
        alert('No asset selected');
        return;
    }

    try {
        const response = await fetch(`/api/assets/${addCollectionTargetAssetId}/collections`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ collection_id: collectionId })
        });

        if (!response.ok) throw new Error('Failed to add to collection');

        closeAddCollectionModal();
        reloadAssets();
        loadCollections();
        console.log('[Workspace] Added asset to collection');
    } catch (error) {
        console.error('[Workspace] Failed to add to collection:', error);
        alert('Failed to add to collection');
    }
}

// Reload sidebar collections
async function loadCollections() {
    try {
        const response = await fetch('/api/collections');
        const collections = await response.json();
        renderCollections(collections);
    } catch (error) {
        console.error('[Workspace] Failed to load collections:', error);
    }
}

// =========================================
// DELETE COLLECTION MODAL FUNCTIONS
// =========================================

let deleteCollectionTargetId = null;

function openDeleteCollectionModal(collectionId, collectionName) {
    deleteCollectionTargetId = collectionId;
    document.getElementById('deleteCollectionName').textContent = collectionName;
    document.getElementById('deleteCollectionModal').classList.add('active');
}

function closeDeleteCollectionModal() {
    document.getElementById('deleteCollectionModal').classList.remove('active');
    deleteCollectionTargetId = null;
}

async function confirmDeleteCollection() {
    if (!deleteCollectionTargetId) {
        console.error('[Workspace] No collection selected for deletion');
        return;
    }

    try {
        const response = await fetch(`/api/collections/${deleteCollectionTargetId}`, {
            method: 'DELETE'
        });

        if (!response.ok) throw new Error('Failed to delete collection');

        console.log('[Workspace] Deleted collection:', deleteCollectionTargetId);
        closeDeleteCollectionModal();

        // Refresh sidebar collections
        loadCollections();

        // If viewing the deleted collection, switch to All Assets
        const activeCollection = document.querySelector('.collection-item.active');
        if (activeCollection?.dataset.collectionId === deleteCollectionTargetId) {
            reloadAssets({});
        }
    } catch (error) {
        console.error('[Workspace] Failed to delete collection:', error);
        alert('Failed to delete collection');
    }
}

// Initialize starred jobs count on page load
async function initStarredJobsCount() {
    await updateStarredJobsCount();
}

// =====================
// REWRITE FUNCTIONALITY
// =====================

// Rewrite state variables
let currentRewriteReel = null;
let cachedSettings = null;
const TOTAL_WIZARD_STEPS = 8;
let wizardStep = 0;
let wizardData = {};
let wizardMode = 'guided'; // 'guided' or 'quick'

// Models for each provider (used in rewrite modal)
const providerModels = {
    local: [], // Populated dynamically from Ollama
    openai: ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo'],
    anthropic: ['claude-3-5-haiku-20241022', 'claude-3-5-sonnet-20241022', 'claude-3-opus-20240229'],
    google: ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash-exp']
};

// =====================
// SPIN BUTTONS
// =====================

// Default spin suggestions
const DEFAULT_SPIN_BUTTONS = [
    'Instead of paying, get it all free',
    'No coding required',
    'Works in under 5 minutes',
    'The lazy way to do it',
    'What nobody tells you about this'
];

// Current spin buttons (loaded from server or defaults)
let spinButtons = [...DEFAULT_SPIN_BUTTONS];
let spinEditMode = false;
const MAX_SPIN_BUTTONS = 8;

// Load custom spin buttons from server
async function loadSpinButtons() {
    try {
        const response = await fetch('/api/settings');
        const settings = await response.json();
        if (settings.spin_buttons && settings.spin_buttons.length > 0) {
            spinButtons = settings.spin_buttons;
        }
    } catch (error) {
        console.warn('Failed to load spin buttons, using defaults');
    }
    renderSpinButtons();
}

// Save spin buttons to server
async function saveSpinButtons() {
    try {
        await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ spin_buttons: spinButtons })
        });
    } catch (error) {
        console.warn('Failed to save spin buttons:', error);
    }
}

// Render spin buttons
function renderSpinButtons() {
    const container = document.getElementById('spinButtonsContainer');
    if (!container) return;

    container.innerHTML = spinButtons.map((text, index) => `
        <button class="spin-btn ${spinEditMode ? 'editing' : ''}"
                onclick="${spinEditMode ? '' : `insertSpinText('${escapeHtml(text.replace(/'/g, "\\'"))}')`}"
                data-index="${index}">
            <span class="plus-icon">+</span>
            <span class="spin-text">${escapeHtml(text)}</span>
            ${spinEditMode ? `<button class="delete-btn" onclick="event.stopPropagation(); deleteSpinButton(${index})">×</button>` : ''}
        </button>
    `).join('');

    // Add "Add new" button if under limit and in edit mode
    if (spinEditMode && spinButtons.length < MAX_SPIN_BUTTONS) {
        container.innerHTML += `
            <button class="spin-btn spin-btn-add" onclick="addNewSpinButton()">
                <span class="plus-icon">+</span>
                <span>Add new...</span>
            </button>
        `;
    }

    // Update edit toggle state
    const toggle = document.getElementById('spinEditToggle');
    if (toggle) {
        toggle.classList.toggle('active', spinEditMode);
        toggle.querySelector('span').textContent = spinEditMode ? 'Done' : 'Customize';
    }
}

// Insert spin text into the angle input
function insertSpinText(text) {
    const input = document.getElementById('wizardAngle');
    if (input) {
        input.value = text;
        input.focus();
    }
}

// Toggle edit mode
function toggleSpinEditMode() {
    spinEditMode = !spinEditMode;
    renderSpinButtons();
}

// Add new spin button
function addNewSpinButton() {
    if (spinButtons.length >= MAX_SPIN_BUTTONS) return;

    const container = document.getElementById('spinButtonsContainer');
    const addBtn = container.querySelector('.spin-btn-add');

    // Replace add button with input
    const inputHtml = `
        <input type="text" class="spin-btn-input"
               placeholder="Enter your spin..."
               onkeydown="handleSpinInput(event)"
               onblur="cancelSpinInput(this)"
               autofocus>
    `;

    if (addBtn) {
        addBtn.outerHTML = inputHtml;
        const input = container.querySelector('.spin-btn-input');
        if (input) input.focus();
    }
}

// Handle spin input keydown
function handleSpinInput(event) {
    if (event.key === 'Enter') {
        const value = event.target.value.trim();
        if (value && spinButtons.length < MAX_SPIN_BUTTONS) {
            spinButtons.push(value);
            saveSpinButtons();
        }
        renderSpinButtons();
    } else if (event.key === 'Escape') {
        renderSpinButtons();
    }
}

// Cancel spin input on blur
function cancelSpinInput(input) {
    // Small delay to allow Enter key to process
    setTimeout(() => {
        const value = input.value.trim();
        if (value && spinButtons.length < MAX_SPIN_BUTTONS) {
            spinButtons.push(value);
            saveSpinButtons();
        }
        renderSpinButtons();
    }, 100);
}

// Delete spin button
function deleteSpinButton(index) {
    spinButtons.splice(index, 1);
    saveSpinButtons();
    renderSpinButtons();
}

// Fetch settings and Ollama models for rewrite modal
async function fetchRewriteSettings() {
    try {
        const [settingsRes, ollamaRes] = await Promise.all([
            fetch('/api/settings'),
            fetch('/api/ollama/models').catch(() => ({ json: () => ({ available: false, models: [] }) }))
        ]);

        cachedSettings = await settingsRes.json();

        try {
            const ollamaData = await ollamaRes.json();
            if (ollamaData.available && ollamaData.models.length > 0) {
                providerModels.local = ollamaData.models;
            }
        } catch (e) {
            providerModels.local = [];
        }
    } catch (error) {
        console.error('Failed to fetch rewrite settings:', error);
    }
}

// Update rewrite model dropdown based on selected provider
function updateRewriteModel() {
    const provider = document.getElementById('rewriteProvider').value;
    const modelSelect = document.getElementById('rewriteModel');
    const statusDiv = document.getElementById('rewriteProviderStatus');

    modelSelect.innerHTML = '';

    if (provider === 'local') {
        if (providerModels.local.length > 0) {
            providerModels.local.forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                modelSelect.appendChild(option);
            });
            statusDiv.textContent = `${providerModels.local.length} local models available`;
            statusDiv.style.color = 'var(--color-accent-primary)';
        } else {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = '-- No models --';
            modelSelect.appendChild(option);
            statusDiv.textContent = 'Ollama not running or no models installed';
            statusDiv.style.color = 'var(--color-danger)';
        }
    } else {
        const models = providerModels[provider] || [];
        models.forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            option.textContent = model;
            modelSelect.appendChild(option);
        });

        if (cachedSettings) {
            const keyField = `has_${provider}_key`;
            if (cachedSettings[keyField]) {
                statusDiv.textContent = 'API key configured';
                statusDiv.style.color = 'var(--color-accent-primary)';
            } else {
                statusDiv.textContent = 'API key not configured - set in Settings';
                statusDiv.style.color = 'var(--color-warning)';
            }
        } else {
            statusDiv.textContent = '';
        }
    }

    // Set default model from settings if available
    if (cachedSettings) {
        const modelKey = `${provider}_model`;
        if (cachedSettings[modelKey]) {
            modelSelect.value = cachedSettings[modelKey];
        }
    }
}

// Open rewrite modal
function openRewriteModal(scrapeId, shortcode) {
    const rewriteModal = document.getElementById('rewriteModal');
    currentRewriteReel = { scrapeId, shortcode };

    // Fetch settings if not cached
    if (!cachedSettings) {
        fetchRewriteSettings().then(() => {
            setupRewriteModal();
        });
    } else {
        setupRewriteModal();
    }

    rewriteModal.classList.add('active');
}

// Setup rewrite modal after settings are loaded
function setupRewriteModal() {
    resetWizardState();

    const providerSelect = document.getElementById('rewriteProvider');
    if (cachedSettings && cachedSettings.ai_provider && cachedSettings.ai_provider !== 'copy') {
        providerSelect.value = cachedSettings.ai_provider;
    } else {
        if (cachedSettings?.has_openai_key) {
            providerSelect.value = 'openai';
        } else if (cachedSettings?.has_anthropic_key) {
            providerSelect.value = 'anthropic';
        } else if (cachedSettings?.has_google_key) {
            providerSelect.value = 'google';
        } else if (providerModels.local.length > 0) {
            providerSelect.value = 'local';
        }
    }

    // Load spin buttons from cached settings or server
    if (cachedSettings?.spin_buttons && cachedSettings.spin_buttons.length > 0) {
        spinButtons = cachedSettings.spin_buttons;
    }
    spinEditMode = false;
    renderSpinButtons();

    updateRewriteModel();
    initWizardOptionButtons();
}

// Reset wizard state
function resetWizardState() {
    wizardStep = 0;
    wizardData = {
        niche: '',
        voice: '',
        angle: '',
        product: '',
        setup: '',
        cta: '',
        timeLimit: 'Under 60 seconds'
    };

    const inputs = ['wizardNiche', 'wizardVoice', 'wizardAngle', 'wizardProduct', 'wizardSetup', 'wizardCta'];
    inputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });

    document.querySelectorAll('.voice-btn, .cta-btn').forEach(btn => btn.classList.remove('selected'));
    document.querySelectorAll('.time-btn').forEach(btn => {
        btn.classList.toggle('selected', btn.dataset.time === 'Under 60 seconds');
    });

    const resultEl = document.getElementById('rewriteResult');
    const outputEl = document.getElementById('rewriteOutput');
    const placeholderEl = document.getElementById('resultPlaceholder');

    if (resultEl) resultEl.style.display = 'none';
    if (outputEl) outputEl.textContent = '';
    if (placeholderEl) placeholderEl.style.display = 'flex';

    updateWizardUI();
}

// Initialize option button click handlers
function initWizardOptionButtons() {
    document.querySelectorAll('.voice-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.voice-btn').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            document.getElementById('wizardVoice').value = btn.dataset.voice;
        };
    });

    document.querySelectorAll('.cta-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.cta-btn').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            document.getElementById('wizardCta').value = btn.dataset.cta;
        };
    });

    document.querySelectorAll('.time-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            wizardData.timeLimit = btn.dataset.time;
        };
    });
}

// Update wizard UI based on current step
function updateWizardUI() {
    const progressBar = document.getElementById('wizardProgressBar');
    const stepCount = document.getElementById('wizardStepCount');

    if (progressBar) {
        const progress = ((wizardStep + 1) / TOTAL_WIZARD_STEPS) * 100;
        progressBar.style.width = `${progress}%`;
    }

    if (stepCount) {
        stepCount.textContent = `Step ${wizardStep + 1} of ${TOTAL_WIZARD_STEPS}`;
    }

    document.querySelectorAll('.wizard-step').forEach(step => {
        step.classList.toggle('active', parseInt(step.dataset.step) === wizardStep);
    });

    const backBtn = document.getElementById('wizardBackBtn');
    const skipBtn = document.getElementById('wizardSkipBtn');
    const nextBtn = document.getElementById('wizardNextBtn');

    if (backBtn) backBtn.style.display = wizardStep > 0 ? 'inline-flex' : 'none';

    if (wizardStep === TOTAL_WIZARD_STEPS - 1) {
        if (nextBtn) {
            nextBtn.textContent = 'GENERATE';
            nextBtn.classList.add('primary');
        }
        if (skipBtn) skipBtn.style.display = 'none';
    } else {
        if (nextBtn) nextBtn.textContent = 'NEXT';
        if (skipBtn) skipBtn.style.display = wizardStep === 0 ? 'none' : 'inline-flex';
    }
}

// Collect current step data
function collectStepData() {
    switch(wizardStep) {
        case 1:
            wizardData.niche = document.getElementById('wizardNiche')?.value.trim() || '';
            break;
        case 2:
            wizardData.voice = document.getElementById('wizardVoice')?.value.trim() || '';
            break;
        case 3:
            wizardData.angle = document.getElementById('wizardAngle')?.value.trim() || '';
            break;
        case 4:
            wizardData.product = document.getElementById('wizardProduct')?.value.trim() || '';
            break;
        case 5:
            wizardData.setup = document.getElementById('wizardSetup')?.value.trim() || '';
            break;
        case 6:
            wizardData.cta = document.getElementById('wizardCta')?.value.trim() || '';
            break;
    }
}

// Build context string from wizard data
function buildContextFromWizard() {
    const parts = [];

    if (wizardData.niche) parts.push(`NICHE: ${wizardData.niche}`);
    if (wizardData.voice) parts.push(`BRAND VOICE: ${wizardData.voice}`);
    if (wizardData.angle) parts.push(`ANGLE: ${wizardData.angle}`);
    if (wizardData.product) parts.push(`PRODUCT/SERVICE: ${wizardData.product}`);
    if (wizardData.setup) parts.push(`SETUP/HOW IT WORKS:\n${wizardData.setup}`);
    if (wizardData.cta) parts.push(`CTA: ${wizardData.cta}`);
    if (wizardData.timeLimit) parts.push(`TIME LIMIT: ${wizardData.timeLimit}`);

    return parts.join('\n\n');
}

// Wizard navigation
function wizardNext() {
    collectStepData();

    if (wizardStep === 0) {
        const model = document.getElementById('rewriteModel')?.value;
        if (!model) {
            alert('Please select a model');
            return;
        }
    }

    if (wizardStep < TOTAL_WIZARD_STEPS - 1) {
        wizardStep++;
        updateWizardUI();
    } else {
        generateRewrite();
    }
}

function wizardBack() {
    collectStepData();
    if (wizardStep > 0) {
        wizardStep--;
        updateWizardUI();
    }
}

function wizardSkip() {
    if (wizardStep < TOTAL_WIZARD_STEPS - 1) {
        wizardStep++;
        updateWizardUI();
    }
}

function resetWizard() {
    resetWizardState();
}

function editWizardContext() {
    wizardStep = 1;

    const resultEl = document.getElementById('rewriteResult');
    const placeholderEl = document.getElementById('resultPlaceholder');

    if (resultEl) resultEl.style.display = 'none';
    if (placeholderEl) {
        placeholderEl.style.display = 'flex';
        placeholderEl.innerHTML = `
            <div class="placeholder-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                </svg>
            </div>
            <div class="placeholder-text">Your rewritten script will appear here</div>
            <div class="placeholder-hint">Edit your context and click Generate</div>
        `;
    }

    updateWizardUI();
}

// Switch between guided and quick mode
function setWizardMode(mode) {
    wizardMode = mode;

    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
    });

    const guidedMode = document.getElementById('guidedMode');
    const quickMode = document.getElementById('quickMode');

    if (guidedMode) guidedMode.style.display = mode === 'guided' ? 'flex' : 'none';
    if (quickMode) quickMode.style.display = mode === 'quick' ? 'flex' : 'none';

    if (mode === 'quick') {
        const guidedProvider = document.getElementById('rewriteProvider')?.value;
        const quickProvider = document.getElementById('quickProvider');
        if (guidedProvider && quickProvider) {
            quickProvider.value = guidedProvider;
            updateQuickModel();
        }
    }

    const resultEl = document.getElementById('rewriteResult');
    const placeholderEl = document.getElementById('resultPlaceholder');
    if (resultEl) resultEl.style.display = 'none';
    if (placeholderEl) placeholderEl.style.display = 'flex';
}

// Update quick mode model dropdown
function updateQuickModel() {
    const provider = document.getElementById('quickProvider')?.value;
    const modelSelect = document.getElementById('quickModel');
    if (!modelSelect) return;

    modelSelect.innerHTML = '';

    const models = providerModels[provider] || [];
    models.forEach(model => {
        const option = document.createElement('option');
        option.value = model;
        option.textContent = model;
        modelSelect.appendChild(option);
    });

    if (cachedSettings && cachedSettings[`${provider}_model`]) {
        modelSelect.value = cachedSettings[`${provider}_model`];
    }
}

// Generate rewrite in quick mode
async function generateQuickRewrite() {
    if (!currentRewriteReel) return;

    const btn = document.querySelector('#quickMode .modal-btn.primary');
    const resultDiv = document.getElementById('rewriteResult');
    const outputDiv = document.getElementById('rewriteOutput');
    const placeholder = document.getElementById('resultPlaceholder');
    const context = document.getElementById('quickContext')?.value.trim() || '';
    const provider = document.getElementById('quickProvider')?.value;
    const model = document.getElementById('quickModel')?.value;

    if (!model) {
        alert('Please select a model');
        return;
    }

    if (btn) {
        btn.disabled = true;
        btn.textContent = 'GENERATING...';
    }

    if (placeholder) {
        placeholder.innerHTML = `
            <div class="placeholder-icon" style="opacity: 0.6;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M12 2v4m0 12v4m-8-10H0m24 0h-4m-2.343-5.657l-2.828 2.828m-5.658 5.658l-2.828 2.828m0-11.314l2.828 2.828m5.658 5.658l2.828 2.828"/>
                </svg>
            </div>
            <div class="placeholder-text">Generating your script...</div>
            <div class="placeholder-hint">This may take a few seconds</div>
        `;
    }

    try {
        const response = await fetch('/api/rewrite', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                scrape_id: currentRewriteReel.scrapeId,
                shortcode: currentRewriteReel.shortcode,
                context: context,
                provider: provider,
                model: model
            })
        });

        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        if (outputDiv) outputDiv.textContent = data.result;
        if (placeholder) placeholder.style.display = 'none';
        if (resultDiv) resultDiv.style.display = 'flex';

    } catch (error) {
        alert(`Error: ${error.message}`);
        if (placeholder) {
            placeholder.innerHTML = `
                <div class="placeholder-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                    </svg>
                </div>
                <div class="placeholder-text">Your rewritten script will appear here</div>
                <div class="placeholder-hint">Add context and click Generate</div>
            `;
        }
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'GENERATE';
        }
    }
}

// Close rewrite modal
function closeRewriteModal() {
    const rewriteModal = document.getElementById('rewriteModal');
    if (rewriteModal) rewriteModal.classList.remove('active');
    currentRewriteReel = null;
}

// Generate rewrite using AI
async function generateRewrite() {
    if (!currentRewriteReel) return;

    const btn = document.getElementById('wizardNextBtn');
    const resultDiv = document.getElementById('rewriteResult');
    const outputDiv = document.getElementById('rewriteOutput');
    const placeholder = document.getElementById('resultPlaceholder');
    const context = buildContextFromWizard();
    const provider = document.getElementById('rewriteProvider')?.value;
    const model = document.getElementById('rewriteModel')?.value;

    if (!model) {
        alert('Please select a model');
        return;
    }

    if (btn) {
        btn.disabled = true;
        btn.textContent = 'GENERATING...';
    }

    if (placeholder) {
        placeholder.innerHTML = `
            <div class="placeholder-icon" style="opacity: 0.6;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M12 2v4m0 12v4m-8-10H0m24 0h-4m-2.343-5.657l-2.828 2.828m-5.658 5.658l-2.828 2.828m0-11.314l2.828 2.828m5.658 5.658l2.828 2.828"/>
                </svg>
            </div>
            <div class="placeholder-text">Generating your script...</div>
            <div class="placeholder-hint">This may take a few seconds</div>
        `;
    }

    try {
        const response = await fetch('/api/rewrite', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                scrape_id: currentRewriteReel.scrapeId,
                shortcode: currentRewriteReel.shortcode,
                context: context,
                provider: provider,
                model: model
            })
        });

        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        if (outputDiv) outputDiv.textContent = data.result;
        if (placeholder) placeholder.style.display = 'none';
        if (resultDiv) resultDiv.style.display = 'flex';

    } catch (error) {
        alert(`Error: ${error.message}`);
        if (placeholder) {
            placeholder.innerHTML = `
                <div class="placeholder-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                    </svg>
                </div>
                <div class="placeholder-text">Your rewritten script will appear here</div>
                <div class="placeholder-hint">Complete the wizard and click Generate</div>
            `;
        }
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'GENERATE';
        }
    }
}

// Copy rewrite result
async function copyRewriteResult(event) {
    const output = document.getElementById('rewriteOutput')?.textContent || '';
    const success = await copyToClipboard(output);

    if (success) {
        const btn = event?.target || document.querySelector('.copy-rewrite-btn');
        if (btn) {
            const originalText = btn.textContent;
            btn.textContent = 'COPIED!';
            btn.style.color = 'var(--color-accent-primary)';
            setTimeout(() => {
                btn.textContent = originalText;
                btn.style.color = '';
            }, 2000);
        }
    } else {
        alert('Failed to copy. Try selecting and copying manually.');
    }
}

// Subscribe to view changes for starred jobs
Store.subscribe(() => {
    const state = Store.getState();
    if (state.ui.activeView === 'starred-jobs') {
        loadStarredJobs();
    }
});

// Initialize color swatch click handlers when DOM is ready
setTimeout(() => {
    document.querySelectorAll('#addCollectionColors .color-swatch').forEach(swatch => {
        swatch.addEventListener('click', () => {
            selectCollectionColor(swatch.dataset.color);
        });
    });

    // Load starred jobs count
    initStarredJobsCount();

    // Initialize rewrite modal as draggable and resizable
    if (typeof ModalUtils !== 'undefined') {
        ModalUtils.makeDraggableResizable('#rewriteModal', {
            persistKey: 'rewriteModalBounds',
            minWidth: 500,
            minHeight: 400,
            dragHandle: '.modal-header'
        });
    }
}, 100);

// Export for debugging
window.ReelRecon = { Store, Router, API };

// Expose accordion functions globally for onclick handlers
window.toggleReelAccordion = toggleReelAccordion;
window.copyToClipboard = copyToClipboard;
window.copyReelForAI = copyReelForAI;
window.copyTranscriptFromReel = copyTranscriptFromReel;
window.copyUrlFromReel = copyUrlFromReel;
window.toggleReelSection = toggleReelSection;
window.toggleReelMetadata = toggleReelMetadata;
window.copyReelMetadata = copyReelMetadata;
window.abortJob = abortJob;

// Expose new functions globally
window.toggleJobStar = toggleJobStar;
window.toggleAssetStar = toggleAssetStar;
window.filterLibraryByJob = filterLibraryByJob;
window.renameAsset = renameAsset;
window.startInlineEdit = startInlineEdit;
window.openAddCollectionModal = openAddCollectionModal;
window.closeAddCollectionModal = closeAddCollectionModal;
window.showNewCollectionForm = showNewCollectionForm;
window.cancelNewCollectionForm = cancelNewCollectionForm;
window.createNewCollection = createNewCollection;
window.confirmAddToCollection = confirmAddToCollection;
window.selectCollectionColor = selectCollectionColor;

// Expose rewrite functions globally
window.openRewriteModal = openRewriteModal;
window.closeRewriteModal = closeRewriteModal;
window.generateRewrite = generateRewrite;
window.generateQuickRewrite = generateQuickRewrite;
window.copyRewriteResult = copyRewriteResult;
window.updateRewriteModel = updateRewriteModel;
window.updateQuickModel = updateQuickModel;
window.setWizardMode = setWizardMode;
window.wizardNext = wizardNext;
window.wizardBack = wizardBack;
window.wizardSkip = wizardSkip;
window.resetWizard = resetWizard;
window.editWizardContext = editWizardContext;

// Expose spin button functions globally
window.insertSpinText = insertSpinText;
window.toggleSpinEditMode = toggleSpinEditMode;
window.addNewSpinButton = addNewSpinButton;
window.handleSpinInput = handleSpinInput;
window.cancelSpinInput = cancelSpinInput;
window.deleteSpinButton = deleteSpinButton;
