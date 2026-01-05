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
    // Assets - merge from database AND history
    async getAssets(filters = {}) {
        // Build query params
        const params = new URLSearchParams();
        if (filters.type) params.set('type', filters.type);
        if (filters.collection) params.set('collection_id', filters.collection);
        if (filters.starred) params.set('starred', 'true');
        if (filters.job_id) params.set('job_id', filters.job_id);
        const query = params.toString();

        // Fetch from both sources in parallel
        const [dbAssets, history] = await Promise.all([
            request(`/api/assets${query ? '?' + query : ''}`).catch(() => []),
            request('/api/history').catch(() => [])
        ]);

        // Transform history items to asset format
        const historyAssets = (history || []).map(item => {
            const topReels = item.top_reels || item.top_videos || [];
            const transcriptCount = topReels.filter(r => r.transcript).length;
            const videoCount = topReels.filter(r => r.local_video).length;

            // Calculate aggregate stats for card display
            const totalViews = topReels.reduce((sum, r) => sum + (r.views || r.play_count || 0), 0);
            const totalLikes = topReels.reduce((sum, r) => sum + (r.likes || r.like_count || 0), 0);
            const totalComments = topReels.reduce((sum, r) => sum + (r.comments || r.comment_count || 0), 0);

            return {
                id: item.id,
                type: 'scrape_report',
                title: `@${item.username || 'unknown'} - ${(item.platform || 'instagram').charAt(0).toUpperCase() + (item.platform || 'instagram').slice(1)}`,
                username: item.username,
                platform: item.platform || 'instagram',
                created_at: item.timestamp,
                status: item.status || 'complete',
                reel_count: topReels.length,
                starred: item.starred || false,
                collections: item.collections || [],
                thumbnail: topReels[0]?.thumbnail_url || null,
                preview: `${topReels.length} reels scraped`,
                // Pre-computed metadata for card badges and stats
                transcript_count: transcriptCount,
                video_count: videoCount,
                total_views: totalViews,
                total_likes: totalLikes,
                total_comments: totalComments
            };
        });

        // Merge: DB assets + history assets (avoid duplicates by ID)
        const dbAssetIds = new Set((dbAssets || []).map(a => a.id));
        const mergedAssets = [
            ...(dbAssets || []),
            ...historyAssets.filter(a => !dbAssetIds.has(a.id))
        ];

        // Apply filters to merged results
        let assets = mergedAssets;
        if (filters.starred) {
            assets = assets.filter(a => a.starred);
        }
        if (filters.type) {
            assets = assets.filter(a => a.type === filters.type);
        }
        if (filters.job_id) {
            assets = assets.filter(a => {
                // For scrape_report from history, the asset ID IS the job ID
                if (a.id === filters.job_id) return true;
                // For DB assets, check metadata
                const meta = a.metadata || {};
                return meta.job_id === filters.job_id || meta.source_report_id === filters.job_id;
            });
        }

        // Sort by created_at descending
        assets.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));

        return { success: true, assets };
    },

    async getAsset(id) {
        // Try database first, then history
        try {
            const dbAsset = await request(`/api/assets/${id}`);
            if (dbAsset && !dbAsset.error) {
                // For skeleton_report and scrape_report, also fetch content
                if (dbAsset.type === 'skeleton_report' || dbAsset.type === 'scrape_report') {
                    try {
                        const content = await request(`/api/assets/${id}/content`);
                        if (content && !content.error) {
                            // Merge content into asset
                            if (dbAsset.type === 'skeleton_report') {
                                dbAsset.skeletons = content.skeletons || [];
                                dbAsset.markdown = content.markdown || '';
                            } else if (dbAsset.type === 'scrape_report') {
                                dbAsset.top_reels = content.top_reels || [];
                                dbAsset.username = content.username || dbAsset.metadata?.username;
                            }
                        }
                    } catch (e) {
                        console.warn('[API] Failed to fetch asset content:', e);
                    }
                }
                return dbAsset;
            }
        } catch (e) {
            // DB asset not found, try history
        }

        // Fall back to history
        const item = await request(`/api/history/${id}`);
        if (!item || item.error) {
            throw new Error(item?.error || 'Asset not found');
        }
        return {
            id: item.id,
            type: 'scrape_report',
            title: `@${item.username || 'unknown'} - ${(item.platform || 'instagram').charAt(0).toUpperCase() + (item.platform || 'instagram').slice(1)}`,
            username: item.username,
            platform: item.platform || 'instagram',
            created_at: item.timestamp,
            status: item.status || 'complete',
            reel_count: (item.top_reels || item.top_videos || []).length,
            starred: item.starred || false,
            collections: item.collections || [],
            top_reels: item.top_reels || item.top_videos || [],
            content: item  // Include full data for detail view
        };
    },

    async deleteAsset(id) {
        // Try database first, then history
        try {
            return await request(`/api/assets/${id}`, { method: 'DELETE' });
        } catch (e) {
            return request(`/api/history/${id}`, { method: 'DELETE' });
        }
    },

    async toggleStar(id) {
        // Try database first, then history
        try {
            return await request(`/api/assets/${id}/star`, { method: 'POST' });
        } catch (e) {
            return request(`/api/history/${id}/star`, { method: 'POST' });
        }
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

    removeFromCollection(assetId, collectionId) {
        return request(`/api/assets/${assetId}/collections/${collectionId}`, { method: 'DELETE' });
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

    startBatchScrape(data) {
        return request('/api/scrape/batch', { method: 'POST', body: data });
    },

    startDirectScrape(data) {
        return request('/api/scrape/direct', { method: 'POST', body: data });
    },

    getScrapeStatus(id) {
        return request(`/api/scrape/${id}/status`);
    },

    getBatchStatus(batchId) {
        return request(`/api/scrape/batch/${batchId}/status`);
    },

    abortScrape(id) {
        return request(`/api/scrape/${id}/abort`, { method: 'POST' });
    },

    abortBatch(batchId) {
        return request(`/api/scrape/batch/${batchId}/abort`, { method: 'POST' });
    },

    abortAnalysis(id) {
        return request(`/api/skeleton-ripper/${id}/abort`, { method: 'POST' });
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
