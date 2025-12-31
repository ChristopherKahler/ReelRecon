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
}

async function loadInitialData() {
    try {
        // Load collections for sidebar
        const collectionsResponse = await API.getCollections();
        const collections = collectionsResponse.collections || collectionsResponse || [];
        Store.dispatch({ type: 'SET_COLLECTIONS', payload: collections });
        console.log('[Workspace] Loaded', collections.length, 'collections');

        // Load initial assets
        const assetsResponse = await API.getAssets();
        const assets = assetsResponse.assets || assetsResponse || [];
        Store.dispatch({ type: 'SET_ASSETS', payload: assets });
        console.log('[Workspace] Loaded', assets.length, 'assets');

        // Update UI with loaded data
        updateAssetCount(assets.length);
    } catch (error) {
        console.warn('[Workspace] Failed to load initial data:', error.message);
        // Non-fatal - UI still works
    }
}

function updateAssetCount(count) {
    const countEl = document.querySelector('.collection-count');
    if (countEl) {
        countEl.textContent = count;
    }
}

// Export for debugging
window.ReelRecon = { Store, Router, API };
