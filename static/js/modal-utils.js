/**
 * Modal Utilities - Reusable drag and resize functionality for modals
 *
 * Usage:
 *   ModalUtils.makeDraggableResizable('#myModal', {
 *       persistKey: 'myModalBounds',
 *       minWidth: 400,
 *       minHeight: 300,
 *       dragHandle: '.modal-header'
 *   });
 */

const ModalUtils = (function() {
    'use strict';

    // Track initialized modals
    const initializedModals = new Map();

    // Default configuration
    const defaults = {
        minWidth: 400,
        minHeight: 300,
        maxWidth: null,  // null = viewport width
        maxHeight: null, // null = viewport height
        dragHandle: '.modal-header',
        contentSelector: '.modal-content',
        persistKey: null,  // If set, saves/loads bounds from server
        onResize: null,    // Callback after resize
        onMove: null,      // Callback after move
        onBoundsChange: null  // Callback after any bounds change
    };

    /**
     * Initialize draggable and resizable functionality for a modal
     */
    function makeDraggableResizable(modalSelector, options = {}) {
        const modal = document.querySelector(modalSelector);
        if (!modal) {
            console.warn(`ModalUtils: Modal not found: ${modalSelector}`);
            return null;
        }

        const config = { ...defaults, ...options };
        const content = modal.querySelector(config.contentSelector);

        if (!content) {
            console.warn(`ModalUtils: Content not found: ${config.contentSelector}`);
            return null;
        }

        // Check if already initialized
        if (initializedModals.has(modalSelector)) {
            return initializedModals.get(modalSelector);
        }

        // Create instance
        const instance = {
            modal,
            content,
            config,
            bounds: null,
            isDragging: false,
            isResizing: false,
            resizeDirection: null
        };

        // Setup
        setupModalStyles(instance);
        addResizeHandles(instance);
        setupDragHandlers(instance);
        setupResizeHandlers(instance);

        // Load saved bounds if persistence is enabled
        if (config.persistKey) {
            loadBounds(instance);
        }

        // Store instance
        initializedModals.set(modalSelector, instance);

        return {
            reset: () => resetBounds(instance),
            getBounds: () => ({ ...instance.bounds }),
            setBounds: (bounds) => applyBounds(instance, bounds),
            destroy: () => destroy(modalSelector)
        };
    }

    /**
     * Setup initial modal styles for positioning
     */
    function setupModalStyles(instance) {
        const { content } = instance;

        // Ensure content can be positioned absolutely
        content.style.position = 'absolute';
        content.style.margin = '0';

        // Add draggable class for cursor styling
        content.classList.add('modal-draggable-resizable');
    }

    /**
     * Add resize handles to modal
     */
    function addResizeHandles(instance) {
        const { content } = instance;

        // Create resize handles container
        const handlesContainer = document.createElement('div');
        handlesContainer.className = 'modal-resize-handles';

        // 8 resize handles: n, ne, e, se, s, sw, w, nw
        const directions = ['n', 'ne', 'e', 'se', 's', 'sw', 'w', 'nw'];

        directions.forEach(dir => {
            const handle = document.createElement('div');
            handle.className = `modal-resize-handle modal-resize-${dir}`;
            handle.dataset.direction = dir;
            handlesContainer.appendChild(handle);
        });

        content.appendChild(handlesContainer);
    }

    /**
     * Setup drag handlers
     */
    function setupDragHandlers(instance) {
        const { modal, content, config } = instance;
        const dragHandle = content.querySelector(config.dragHandle);

        if (!dragHandle) {
            console.warn(`ModalUtils: Drag handle not found: ${config.dragHandle}`);
            return;
        }

        // Add drag cursor class
        dragHandle.classList.add('modal-drag-handle');

        let startX, startY, startLeft, startTop;

        dragHandle.addEventListener('mousedown', (e) => {
            // Don't drag if clicking on buttons or close
            if (e.target.closest('button') || e.target.closest('.modal-close')) {
                return;
            }

            e.preventDefault();
            instance.isDragging = true;

            const rect = content.getBoundingClientRect();
            startX = e.clientX;
            startY = e.clientY;
            startLeft = rect.left;
            startTop = rect.top;

            content.classList.add('modal-dragging');
            document.body.style.userSelect = 'none';
        });

        document.addEventListener('mousemove', (e) => {
            if (!instance.isDragging) return;

            const deltaX = e.clientX - startX;
            const deltaY = e.clientY - startY;

            let newLeft = startLeft + deltaX;
            let newTop = startTop + deltaY;

            // Constrain to viewport
            const rect = content.getBoundingClientRect();
            const maxLeft = window.innerWidth - rect.width;
            const maxTop = window.innerHeight - rect.height;

            newLeft = Math.max(0, Math.min(newLeft, maxLeft));
            newTop = Math.max(0, Math.min(newTop, maxTop));

            content.style.left = `${newLeft}px`;
            content.style.top = `${newTop}px`;
            content.style.transform = 'none';
        });

        document.addEventListener('mouseup', () => {
            if (instance.isDragging) {
                instance.isDragging = false;
                content.classList.remove('modal-dragging');
                document.body.style.userSelect = '';

                saveBoundsDebounced(instance);

                if (config.onMove) config.onMove(getBoundsFromElement(content));
                if (config.onBoundsChange) config.onBoundsChange(getBoundsFromElement(content));
            }
        });
    }

    /**
     * Setup resize handlers
     */
    function setupResizeHandlers(instance) {
        const { content, config } = instance;
        const handles = content.querySelectorAll('.modal-resize-handle');

        let startX, startY, startWidth, startHeight, startLeft, startTop;

        handles.forEach(handle => {
            handle.addEventListener('mousedown', (e) => {
                e.preventDefault();
                e.stopPropagation();

                instance.isResizing = true;
                instance.resizeDirection = handle.dataset.direction;

                const rect = content.getBoundingClientRect();
                startX = e.clientX;
                startY = e.clientY;
                startWidth = rect.width;
                startHeight = rect.height;
                startLeft = rect.left;
                startTop = rect.top;

                content.classList.add('modal-resizing');
                document.body.style.userSelect = 'none';
            });
        });

        document.addEventListener('mousemove', (e) => {
            if (!instance.isResizing) return;

            const dir = instance.resizeDirection;
            const deltaX = e.clientX - startX;
            const deltaY = e.clientY - startY;

            let newWidth = startWidth;
            let newHeight = startHeight;
            let newLeft = startLeft;
            let newTop = startTop;

            // Calculate new dimensions based on direction
            if (dir.includes('e')) {
                newWidth = startWidth + deltaX;
            }
            if (dir.includes('w')) {
                newWidth = startWidth - deltaX;
                newLeft = startLeft + deltaX;
            }
            if (dir.includes('s')) {
                newHeight = startHeight + deltaY;
            }
            if (dir.includes('n')) {
                newHeight = startHeight - deltaY;
                newTop = startTop + deltaY;
            }

            // Apply constraints
            const minW = config.minWidth;
            const minH = config.minHeight;
            const maxW = config.maxWidth || window.innerWidth - 40;
            const maxH = config.maxHeight || window.innerHeight - 40;

            // Enforce minimums and adjust position if needed
            if (newWidth < minW) {
                if (dir.includes('w')) {
                    newLeft = startLeft + startWidth - minW;
                }
                newWidth = minW;
            }
            if (newHeight < minH) {
                if (dir.includes('n')) {
                    newTop = startTop + startHeight - minH;
                }
                newHeight = minH;
            }

            // Enforce maximums
            newWidth = Math.min(newWidth, maxW);
            newHeight = Math.min(newHeight, maxH);

            // Constrain to viewport
            newLeft = Math.max(0, newLeft);
            newTop = Math.max(0, newTop);

            // Apply
            content.style.width = `${newWidth}px`;
            content.style.height = `${newHeight}px`;
            content.style.left = `${newLeft}px`;
            content.style.top = `${newTop}px`;
            content.style.transform = 'none';
            content.style.maxWidth = 'none';
        });

        document.addEventListener('mouseup', () => {
            if (instance.isResizing) {
                instance.isResizing = false;
                instance.resizeDirection = null;
                content.classList.remove('modal-resizing');
                document.body.style.userSelect = '';

                saveBoundsDebounced(instance);

                if (config.onResize) config.onResize(getBoundsFromElement(content));
                if (config.onBoundsChange) config.onBoundsChange(getBoundsFromElement(content));
            }
        });
    }

    /**
     * Get bounds from element
     */
    function getBoundsFromElement(element) {
        const rect = element.getBoundingClientRect();
        return {
            x: rect.left,
            y: rect.top,
            width: rect.width,
            height: rect.height
        };
    }

    /**
     * Apply bounds to element
     */
    function applyBounds(instance, bounds) {
        const { content } = instance;

        if (!bounds) return;

        // Validate bounds are within viewport
        const vw = window.innerWidth;
        const vh = window.innerHeight;

        let { x, y, width, height } = bounds;

        // Ensure minimum sizes
        width = Math.max(width, instance.config.minWidth);
        height = Math.max(height, instance.config.minHeight);

        // Ensure within viewport
        x = Math.max(0, Math.min(x, vw - width));
        y = Math.max(0, Math.min(y, vh - height));

        content.style.position = 'absolute';
        content.style.left = `${x}px`;
        content.style.top = `${y}px`;
        content.style.width = `${width}px`;
        content.style.height = `${height}px`;
        content.style.transform = 'none';
        content.style.maxWidth = 'none';

        instance.bounds = { x, y, width, height };
    }

    /**
     * Reset bounds to default (centered)
     */
    function resetBounds(instance) {
        const { content, config } = instance;

        content.style.position = '';
        content.style.left = '';
        content.style.top = '';
        content.style.width = '';
        content.style.height = '';
        content.style.transform = '';
        content.style.maxWidth = '';

        instance.bounds = null;

        if (config.persistKey) {
            saveBounds(instance, null);
        }
    }

    /**
     * Debounced save
     */
    let saveTimeout = null;
    function saveBoundsDebounced(instance) {
        if (!instance.config.persistKey) return;

        clearTimeout(saveTimeout);
        saveTimeout = setTimeout(() => {
            const bounds = getBoundsFromElement(instance.content);
            instance.bounds = bounds;
            saveBounds(instance, bounds);
        }, 300);
    }

    /**
     * Save bounds to server
     */
    async function saveBounds(instance, bounds) {
        const { config } = instance;
        if (!config.persistKey) return;

        try {
            await fetch('/api/modal-bounds', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    key: config.persistKey,
                    bounds: bounds
                })
            });
        } catch (error) {
            console.warn('ModalUtils: Failed to save bounds:', error);
        }
    }

    /**
     * Load bounds from server
     */
    async function loadBounds(instance) {
        const { config } = instance;
        if (!config.persistKey) return;

        try {
            const response = await fetch(`/api/modal-bounds/${config.persistKey}`);
            if (response.ok) {
                const data = await response.json();
                if (data.bounds) {
                    applyBounds(instance, data.bounds);
                }
            }
        } catch (error) {
            console.warn('ModalUtils: Failed to load bounds:', error);
        }
    }

    /**
     * Destroy instance
     */
    function destroy(modalSelector) {
        const instance = initializedModals.get(modalSelector);
        if (!instance) return;

        const { content } = instance;

        // Remove resize handles
        const handles = content.querySelector('.modal-resize-handles');
        if (handles) handles.remove();

        // Remove classes
        content.classList.remove('modal-draggable-resizable', 'modal-dragging', 'modal-resizing');

        const dragHandle = content.querySelector(instance.config.dragHandle);
        if (dragHandle) dragHandle.classList.remove('modal-drag-handle');

        // Reset styles
        content.style.position = '';
        content.style.left = '';
        content.style.top = '';
        content.style.width = '';
        content.style.height = '';
        content.style.transform = '';
        content.style.maxWidth = '';

        initializedModals.delete(modalSelector);
    }

    // Public API
    return {
        makeDraggableResizable,
        destroy,
        getInitializedModals: () => new Map(initializedModals)
    };
})();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ModalUtils;
}
