/**
 * Simple hash-based router for ReelRecon Workspace
 */

import { Store } from '../state/store.js';

const routes = {
    '': 'library',
    'library': 'library',
    'favorites': 'favorites',
    'jobs': 'jobs',
    'starred-jobs': 'starred-jobs',
    'settings': 'settings'
};

export const Router = {
    init() {
        // Listen for hash changes
        window.addEventListener('hashchange', () => this.handleRoute());

        // Handle initial route
        this.handleRoute();

        console.log('[Router] Initialized');
    },

    handleRoute() {
        const hash = window.location.hash.slice(1) || '';
        const [path, queryString] = hash.split('?');
        const view = routes[path] || 'library';

        console.log('[Router] Navigating to:', view);

        // Update store
        Store.dispatch({ type: 'SET_VIEW', payload: view });

        // Handle query params (e.g., ?start=analysis)
        if (queryString) {
            const params = new URLSearchParams(queryString);
            if (params.get('start') === 'scrape') {
                Store.dispatch({ type: 'SET_MODAL', payload: 'new-scrape' });
            } else if (params.get('start') === 'analysis') {
                Store.dispatch({ type: 'SET_MODAL', payload: 'new-analysis' });
            }
        }

        // Update UI
        this.updateView(view);
    },

    navigate(path) {
        window.location.hash = path;
    },

    updateView(view) {
        // Hide all views
        document.querySelectorAll('[data-view]').forEach(el => {
            el.style.display = 'none';
        });

        // Show active view
        const activeView = document.querySelector(`[data-view="${view}"]`);
        if (activeView) {
            activeView.style.display = 'block';
        }

        // Update nav active state
        document.querySelectorAll('[data-nav]').forEach(el => {
            el.classList.remove('active');
            if (el.dataset.nav === view) {
                el.classList.add('active');
            }
        });
    }
};
