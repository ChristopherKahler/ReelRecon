/**
 * Save/Collect Modal - Universal component for saving assets to library
 * Part of P0 Asset Management System
 */

const SaveCollectModal = {
    // Current state
    state: {
        assetType: null,      // 'skeleton', 'scrape', 'transcript'
        assetData: null,      // Full data to save
        contentPath: null,    // Path to content files
        title: '',
        preview: '',
        selectedCollection: null,
        selectedColor: '#10B981',
        onSave: null,         // Callback when saved
        onDiscard: null       // Callback when discarded
    },

    /**
     * Open the modal with asset data
     * @param {Object} options Configuration object
     * @param {string} options.type - Asset type ('skeleton', 'scrape', 'transcript')
     * @param {string} options.title - Default title
     * @param {string} options.preview - Preview text/HTML
     * @param {string} options.contentPath - Path to content files
     * @param {Object} options.metadata - Additional metadata to save
     * @param {Function} options.onSave - Callback after successful save
     * @param {Function} options.onDiscard - Callback after discard
     */
    open(options) {
        this.state = {
            assetType: options.type || 'skeleton',
            assetData: options.metadata || {},
            contentPath: options.contentPath || null,
            title: options.title || '',
            preview: options.preview || '',
            selectedCollection: null,
            selectedColor: '#10B981',
            onSave: options.onSave || null,
            onDiscard: options.onDiscard || null
        };

        // Populate UI
        document.getElementById('saveCollectTitle').value = this.state.title;
        document.getElementById('saveToLibrary').checked = true;

        // Set preview
        const previewEl = document.getElementById('saveCollectPreview');
        if (this.state.preview) {
            previewEl.innerHTML = `
                <div class="save-collect-preview-title">${this._escapeHtml(this.state.title)}</div>
                <div class="save-collect-preview-content">${this.state.preview}</div>
            `;
        } else {
            previewEl.innerHTML = `
                <div class="save-collect-preview-placeholder">
                    <span class="preview-icon">&#128196;</span>
                    <span class="preview-text">Preview content will appear here</span>
                </div>
            `;
        }

        // Load collections
        this.loadCollections();

        // Reset new collection form
        this.cancelCreateCollection();

        // Show modal
        document.getElementById('saveCollectModal').classList.add('active');
    },

    /**
     * Close the modal
     */
    close() {
        document.getElementById('saveCollectModal').classList.remove('active');
        this.state = {
            assetType: null,
            assetData: null,
            contentPath: null,
            title: '',
            preview: '',
            selectedCollection: null,
            selectedColor: '#10B981',
            onSave: null,
            onDiscard: null
        };
    },

    /**
     * Load collections from API
     */
    async loadCollections() {
        try {
            const response = await fetch('/api/collections');
            const collections = await response.json();

            const select = document.getElementById('saveCollectDropdown');
            select.innerHTML = '<option value="">-- Select Collection --</option>';

            collections.forEach(c => {
                const option = document.createElement('option');
                option.value = c.id;
                option.textContent = c.name;
                option.style.borderLeft = `3px solid ${c.color}`;
                select.appendChild(option);
            });
        } catch (error) {
            console.error('Failed to load collections:', error);
        }
    },

    /**
     * Handle collection dropdown change
     */
    onCollectionChange() {
        const select = document.getElementById('saveCollectDropdown');
        this.state.selectedCollection = select.value || null;

        // Auto-check "Save to Library" when collection is selected
        if (this.state.selectedCollection) {
            document.getElementById('saveToLibrary').checked = true;
        }
    },

    /**
     * Show create collection form
     */
    showCreateCollection() {
        document.getElementById('newCollectionForm').style.display = 'block';
        document.getElementById('newCollectionName').focus();
    },

    /**
     * Cancel create collection form
     */
    cancelCreateCollection() {
        document.getElementById('newCollectionForm').style.display = 'none';
        document.getElementById('newCollectionName').value = '';
        this.selectColor('#10B981');
    },

    /**
     * Create a new collection
     */
    async createCollection() {
        const name = document.getElementById('newCollectionName').value.trim();
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
                    color: this.state.selectedColor
                })
            });

            if (!response.ok) {
                throw new Error('Failed to create collection');
            }

            const collection = await response.json();

            // Reload collections and select the new one
            await this.loadCollections();
            document.getElementById('saveCollectDropdown').value = collection.id;
            this.state.selectedCollection = collection.id;

            // Hide form
            this.cancelCreateCollection();

        } catch (error) {
            console.error('Failed to create collection:', error);
            alert('Failed to create collection');
        }
    },

    /**
     * Select a color swatch
     */
    selectColor(color) {
        this.state.selectedColor = color;

        // Update UI
        document.querySelectorAll('.color-swatch').forEach(swatch => {
            if (swatch.dataset.color === color) {
                swatch.classList.add('active');
            } else {
                swatch.classList.remove('active');
            }
        });
    },

    /**
     * Save the asset
     */
    async save() {
        const saveToLibrary = document.getElementById('saveToLibrary').checked;
        const title = document.getElementById('saveCollectTitle').value.trim();

        if (!saveToLibrary && !this.state.selectedCollection) {
            alert('Please select "Save to Library" or choose a collection');
            return;
        }

        if (!title) {
            alert('Please enter a title');
            return;
        }

        try {
            let assetId = null;

            // Create asset if saving to library
            if (saveToLibrary) {
                const response = await fetch('/api/assets', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        type: this.state.assetType,
                        title: title,
                        content_path: this.state.contentPath,
                        preview: this._stripHtml(this.state.preview).substring(0, 500),
                        metadata: this.state.assetData
                    })
                });

                if (!response.ok) {
                    throw new Error('Failed to create asset');
                }

                const asset = await response.json();
                assetId = asset.id;
            }

            // Add to collection if selected
            if (assetId && this.state.selectedCollection) {
                await fetch(`/api/assets/${assetId}/collections`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        collection_id: this.state.selectedCollection
                    })
                });
            }

            // Close modal and call callback
            this.close();

            if (this.state.onSave) {
                this.state.onSave({ assetId, title });
            }

        } catch (error) {
            console.error('Failed to save asset:', error);
            alert('Failed to save. Please try again.');
        }
    },

    /**
     * Discard the asset
     */
    discard() {
        if (confirm('Are you sure you want to discard this content?')) {
            const onDiscard = this.state.onDiscard;
            this.close();

            if (onDiscard) {
                onDiscard();
            }
        }
    },

    /**
     * Escape HTML entities
     */
    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * Strip HTML tags
     */
    _stripHtml(html) {
        const div = document.createElement('div');
        div.innerHTML = html;
        return div.textContent || div.innerText || '';
    }
};

// Initialize color swatch click handlers
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.color-swatch').forEach(swatch => {
        swatch.addEventListener('click', () => {
            SaveCollectModal.selectColor(swatch.dataset.color);
        });
    });
});
