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

    // Load initial data
    loadInitialData();

    console.log('[Workspace] Ready.');
});

async function loadInitialData() {
    try {
        // Load collections for sidebar
        const collections = await API.getCollections();
        Store.dispatch({ type: 'SET_COLLECTIONS', payload: collections });

        // Load initial assets
        const assets = await API.getAssets();
        Store.dispatch({ type: 'SET_ASSETS', payload: assets });
    } catch (error) {
        console.error('[Workspace] Failed to load initial data:', error);
    }
}

// Export for debugging
window.ReelRecon = { Store, Router, API };
