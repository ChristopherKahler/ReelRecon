/**
 * API client for ReelRecon backend
 */

const BASE_URL = '';

async function request(endpoint, options = {}) {
    const url = `${BASE_URL}${endpoint}`;
    const config = {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        ...options
    };

    if (options.body && typeof options.body === 'object') {
        config.body = JSON.stringify(options.body);
    }

    const response = await fetch(url, config);

    if (!response.ok) {
        const error = await response.json().catch(() => ({ error: 'Request failed' }));
        throw new Error(error.error || `HTTP ${response.status}`);
    }

    return response.json();
}

export const API = {
    // Assets
    getAssets(filters = {}) {
        const params = new URLSearchParams();
        if (filters.type) params.set('type', filters.type);
        if (filters.collection) params.set('collection_id', filters.collection);
        if (filters.starred) params.set('starred', '1');
        const query = params.toString();
        return request(`/api/assets${query ? '?' + query : ''}`);
    },

    getAsset(id) {
        return request(`/api/assets/${id}`);
    },

    searchAssets(query) {
        return request(`/api/assets/search?q=${encodeURIComponent(query)}`);
    },

    // Collections
    getCollections() {
        return request('/api/collections');
    },

    createCollection(data) {
        return request('/api/collections', { method: 'POST', body: data });
    },

    // Jobs (unified)
    getActiveJobs() {
        return request('/api/jobs/active');
    },

    getRecentJobs() {
        return request('/api/jobs/recent');
    },

    // Scraping
    startScrape(data) {
        return request('/api/scrape', { method: 'POST', body: data });
    },

    getScrapeStatus(id) {
        return request(`/api/scrape/${id}/status`);
    },

    abortScrape(id) {
        return request(`/api/scrape/${id}/abort`, { method: 'POST' });
    },

    // Skeleton Ripper
    getProviders() {
        return request('/api/skeleton-ripper/providers');
    },

    startAnalysis(data) {
        return request('/api/skeleton-ripper/start', { method: 'POST', body: data });
    },

    getAnalysisStatus(id) {
        return request(`/api/skeleton-ripper/status/${id}`);
    },

    // Settings
    getSettings() {
        return request('/api/settings');
    },

    updateSettings(data) {
        return request('/api/settings', { method: 'POST', body: data });
    },

    // Stats
    getDashboardStats() {
        return request('/api/stats/dashboard');
    }
};
