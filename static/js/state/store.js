/**
 * Simple reactive state store for ReelRecon Workspace
 */

export const Store = {
    state: {
        // Data
        assets: [],
        collections: [],
        activeJobs: [],
        recentJobs: [],

        // Filters
        filters: {
            type: null,
            collection: null,
            search: '',
            dateRange: null
        },

        // UI State
        ui: {
            activeView: 'library',
            modal: null,
            sidebarCollapsed: false,
            selectedAsset: null,
            loading: false
        }
    },

    listeners: [],

    init() {
        console.log('[Store] Initialized');
    },

    getState() {
        return this.state;
    },

    subscribe(listener) {
        this.listeners.push(listener);
        return () => {
            this.listeners = this.listeners.filter(l => l !== listener);
        };
    },

    dispatch(action) {
        console.log('[Store] Dispatch:', action.type);

        switch (action.type) {
            case 'SET_ASSETS':
                this.state.assets = action.payload;
                break;
            case 'SET_COLLECTIONS':
                this.state.collections = action.payload;
                break;
            case 'SET_ACTIVE_JOBS':
                this.state.activeJobs = action.payload;
                break;
            case 'SET_VIEW':
                this.state.ui.activeView = action.payload;
                break;
            case 'SET_MODAL':
                this.state.ui.modal = action.payload;
                break;
            case 'SET_FILTER':
                this.state.filters = { ...this.state.filters, ...action.payload };
                break;
            case 'SET_LOADING':
                this.state.ui.loading = action.payload;
                break;
            case 'SELECT_ASSET':
                this.state.ui.selectedAsset = action.payload;
                break;
            default:
                console.warn('[Store] Unknown action:', action.type);
        }

        this.notify();
    },

    notify() {
        this.listeners.forEach(listener => listener(this.state));
    }
};
