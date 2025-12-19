/**
 * IG Reel Scraper - Tactical UI JavaScript
 */

// State
let currentScrapeId = null;
let currentResults = null;
let historyData = [];
let currentRewriteReel = null;  // For rewrite modal

// DOM Elements
const scrapeForm = document.getElementById('scrapeForm');
const executeBtn = document.getElementById('executeBtn');
const progressSection = document.getElementById('progressSection');
const progressText = document.getElementById('progressText');
const progressFill = document.getElementById('progressFill');
const resultsContent = document.getElementById('resultsContent');
const historyList = document.getElementById('historyList');
const reelModal = document.getElementById('reelModal');
const modalBody = document.getElementById('modalBody');
const whisperModelGroup = document.getElementById('whisperModelGroup');
const transcribeCheckbox = document.getElementById('transcribe');

// Clock Update
function updateClock() {
    const now = new Date();
    const time = now.toTimeString().split(' ')[0];
    document.getElementById('clock').textContent = time;
}
setInterval(updateClock, 1000);
updateClock();

// Toggle Transcription Options visibility
transcribeCheckbox?.addEventListener('change', function() {
    const transcribeOptionsGroup = document.getElementById('transcribeOptionsGroup');
    const whisperModelGroup = document.getElementById('whisperModelGroup');

    if (this.checked) {
        transcribeOptionsGroup.style.display = 'block';
        updateTranscribeOptions();
    } else {
        transcribeOptionsGroup.style.display = 'none';
        whisperModelGroup.style.display = 'none';
    }
});

// Update transcription options based on provider
function updateTranscribeOptions() {
    const provider = document.getElementById('transcribeProvider').value;
    const whisperModelGroup = document.getElementById('whisperModelGroup');
    const hint = document.getElementById('transcribeProviderHint');

    if (provider === 'local') {
        whisperModelGroup.style.display = 'block';
        hint.textContent = 'Uses local Whisper model (free, requires download)';
    } else {
        whisperModelGroup.style.display = 'none';
        hint.textContent = 'Uses OpenAI API ($0.006/min, requires API key)';
        hint.style.color = cachedSettings?.has_openai_key ? 'var(--color-accent-primary)' : 'var(--color-warning)';
    }
}

// Model sizes and estimated times
const whisperModelInfo = {
    'tiny.en': { size: '39 MB', time: '30 sec - 1 min' },
    'base.en': { size: '74 MB', time: '1-2 minutes' },
    'small.en': { size: '244 MB', time: '1-3 minutes' },
    'medium.en': { size: '769 MB', time: '3-5 minutes' },
    'large': { size: '1.5 GB', time: '5-10 minutes' }
};

// Pending scrape data (used when waiting for download confirmation)
let pendingScrape = null;

// Download modal functions
function showDownloadModal(modelName) {
    const info = whisperModelInfo[modelName] || { size: 'Unknown', time: 'Unknown' };

    document.getElementById('downloadModelName').textContent = modelName;
    document.getElementById('downloadModelSize').textContent = `~${info.size}`;
    document.getElementById('downloadEstTime').textContent = info.time;

    document.getElementById('downloadModal').classList.add('active');
}

function closeDownloadModal(cancelled = true) {
    document.getElementById('downloadModal').classList.remove('active');
    if (cancelled) {
        pendingScrape = null;
        resetForm();
    }
}

function confirmDownload() {
    // Capture scrape data before closing modal
    const scrapeData = pendingScrape;
    closeDownloadModal(false);  // Don't clear pendingScrape
    pendingScrape = null;

    if (scrapeData) {
        // Show progress indicator with download message
        progressSection.style.display = 'block';
        progressText.textContent = 'Downloading Whisper model (this may take several minutes)...';
        progressFill.style.width = '5%';
        executeBtn.disabled = true;
        executeBtn.querySelector('.btn-text').textContent = 'DOWNLOADING MODEL...';

        executeScrape(scrapeData);
    }
}

// Form Submit
scrapeForm.addEventListener('submit', async function(e) {
    e.preventDefault();

    const username = document.getElementById('username').value.trim();
    if (!username) return;

    const transcribe = document.getElementById('transcribe').checked;
    const transcribeProvider = document.getElementById('transcribeProvider')?.value || 'local';
    const whisperModel = document.getElementById('whisperModel').value;

    // Build scrape data
    const scrapeData = {
        username: username,
        max_reels: parseInt(document.getElementById('maxReels').value) || 100,
        top_n: parseInt(document.getElementById('topN').value) || 10,
        download: document.getElementById('downloadVideos').checked,
        transcribe: transcribe,
        transcribe_provider: transcribeProvider,
        whisper_model: whisperModel
    };

    // If using local transcription, check if model is installed
    if (transcribe && transcribeProvider === 'local') {
        executeBtn.disabled = true;
        executeBtn.querySelector('.btn-text').textContent = 'CHECKING...';

        try {
            const checkResponse = await fetch(`/api/whisper/check/${whisperModel}`);
            const checkData = await checkResponse.json();

            if (!checkData.installed) {
                // Show download modal
                pendingScrape = scrapeData;
                showDownloadModal(whisperModel);
                return;
            }
        } catch (error) {
            console.warn('Could not check model status:', error);
            // Continue anyway - model will download during scrape
        }
    }

    // Check OpenAI key if using OpenAI transcription
    if (transcribe && transcribeProvider === 'openai') {
        if (!cachedSettings?.has_openai_key) {
            alert('OpenAI API key is required for OpenAI transcription. Please configure it in Settings.');
            resetForm();
            return;
        }
    }

    // Execute scrape
    executeScrape(scrapeData);
});

// Execute scrape with given data
async function executeScrape(scrapeData) {
    // Disable form
    executeBtn.disabled = true;
    executeBtn.querySelector('.btn-text').textContent = 'EXECUTING...';
    progressSection.style.display = 'block';
    progressText.textContent = 'Initializing...';
    progressFill.style.width = '10%';

    try {
        const response = await fetch('/api/scrape', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(scrapeData)
        });

        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        currentScrapeId = data.scrape_id;
        pollScrapeStatus();

    } catch (error) {
        showError(error.message);
        resetForm();
    }
}

// Poll for scrape status
async function pollScrapeStatus() {
    if (!currentScrapeId) return;

    try {
        const response = await fetch(`/api/scrape/${currentScrapeId}/status`);

        // Handle server restart or lost scrape
        if (response.status === 404) {
            throw new Error('Scrape job lost (server may have restarted). Please try again.');
        }

        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }

        const data = await response.json();

        const progress = data.progress || '';
        progressText.textContent = progress || 'Processing...';

        // Update progress bar based on status
        if (progress.includes('Found')) {
            progressFill.style.width = '30%';
        } else if (progress.includes('Downloading')) {
            progressFill.style.width = '50%';
        } else if (progress.includes('Transcribing') || progress.includes('Loading Whisper')) {
            progressFill.style.width = '70%';
        } else if (progress.includes('Cleaning')) {
            progressFill.style.width = '90%';
        }

        if (data.status === 'complete') {
            progressFill.style.width = '100%';
            currentResults = data.result;
            renderResults(data.result);
            resetForm();
            refreshHistory();
            // Switch to list view to show new results
            if (currentView === 'gallery') {
                switchView('list');
            }
        } else if (data.status === 'error') {
            throw new Error(data.result?.error || 'Scrape failed');
        } else {
            // Continue polling
            setTimeout(pollScrapeStatus, 1000);
        }

    } catch (error) {
        showError(error.message);
        resetForm();
    }
}

// Render results
function renderResults(result) {
    if (!result || !result.top_reels || result.top_reels.length === 0) {
        resultsContent.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <circle cx="12" cy="12" r="10"/>
                        <path d="M12 8v4M12 16h.01"/>
                    </svg>
                </div>
                <div class="empty-text">NO REELS FOUND</div>
                <div class="empty-subtext">Check username or try again</div>
            </div>
        `;
        return;
    }

    const profile = result.profile || {};
    let html = `
        <div class="results-header">
            <div class="results-title">@${result.username}</div>
            <div class="results-meta">${profile.full_name || ''} • ${formatNumber(profile.followers)} followers</div>
        </div>
        <div class="results-summary">
            <span>${result.total_reels} reels analyzed</span> •
            <span>Top ${result.top_reels.length} shown</span>
        </div>
    `;

    result.top_reels.forEach((reel, index) => {
        const caption = reel.caption ? reel.caption.substring(0, 80) + '...' : 'No caption';
        html += `
            <div class="reel-item" onclick="showReelDetail('${result.id}', ${index})">
                <div>
                    <span class="reel-rank">${index + 1}</span>
                    <span class="reel-shortcode">${reel.shortcode}</span>
                </div>
                <div class="reel-stats">
                    <span class="reel-stat"><strong>${formatNumber(reel.views)}</strong> views</span>
                    <span class="reel-stat"><strong>${formatNumber(reel.likes)}</strong> likes</span>
                    <span class="reel-stat"><strong>${formatNumber(reel.comments || 0)}</strong> comments</span>
                </div>
                <div class="reel-caption">${escapeHtml(caption)}</div>
                <div class="reel-url">
                    <code>${reel.url}</code>
                    <button class="copy-btn" onclick="event.stopPropagation(); copyToClipboard('${reel.url}')">COPY</button>
                </div>
            </div>
        `;
    });

    resultsContent.innerHTML = html;
}

// Show reel detail modal
function showReelDetail(scrapeId, index) {
    // Find the scrape in history or current results
    let scrape = currentResults;
    if (currentResults?.id !== scrapeId) {
        scrape = historyData.find(h => h.id === scrapeId);
    }

    if (!scrape || !scrape.top_reels[index]) return;

    const reel = scrape.top_reels[index];

    let html = `
        <div class="modal-stat-row">
            <div class="modal-stat">
                <div class="modal-stat-value">${formatNumber(reel.views)}</div>
                <div class="modal-stat-label">VIEWS</div>
            </div>
            <div class="modal-stat">
                <div class="modal-stat-value">${formatNumber(reel.likes)}</div>
                <div class="modal-stat-label">LIKES</div>
            </div>
            <div class="modal-stat">
                <div class="modal-stat-value">${formatNumber(reel.comments || 0)}</div>
                <div class="modal-stat-label">COMMENTS</div>
            </div>
        </div>

        <div class="modal-section">
            <div class="modal-section-title">URL</div>
            <div class="reel-url">
                <code>${reel.url}</code>
                <button class="copy-btn" onclick="copyToClipboard('${reel.url}')">COPY</button>
            </div>
        </div>

        <div class="modal-section">
            <div class="modal-section-title">CAPTION / HOOK</div>
            <div class="modal-caption">${escapeHtml(reel.caption || 'No caption')}</div>
        </div>
    `;

    if (reel.transcript) {
        html += `
            <div class="modal-section">
                <div class="modal-section-title">TRANSCRIPT</div>
                <div class="modal-transcript">${escapeHtml(reel.transcript)}</div>
            </div>
        `;
    }

    html += `
        <div class="modal-actions">
            <a href="${reel.url}" target="_blank" class="modal-btn">OPEN IN IG</a>
    `;

    if (reel.local_video) {
        html += `<button class="modal-btn primary" disabled>DOWNLOADED ✓</button>`;
    } else {
        html += `<button class="modal-btn" onclick="fetchVideo('${scrapeId}', '${reel.shortcode}', this)">DOWNLOAD</button>`;
    }

    if (reel.transcript) {
        html += `<button class="modal-btn" onclick="downloadFile('/api/download/transcript/${scrapeId}/${reel.shortcode}')">DOWNLOAD TRANSCRIPT</button>`;
    }

    html += '</div>';

    // AI Actions
    html += `
        <div class="modal-section ai-section">
            <div class="modal-section-title">AI ACTIONS</div>
            <div class="modal-actions">
                <button class="modal-btn ai-btn" onclick="copyAIPrompt(event, '${scrapeId}', '${reel.shortcode}')">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                        <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                    </svg>
                    COPY AI PROMPT
                </button>
                <button class="modal-btn ai-btn primary" onclick="openRewriteModal('${scrapeId}', '${reel.shortcode}')">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                        <path d="M12 20h9"/>
                        <path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/>
                    </svg>
                    REWRITE SCRIPT
                </button>
            </div>
        </div>
    `;

    modalBody.innerHTML = html;
    reelModal.classList.add('active');
}

// Fetch/download video on-demand to output folder
async function fetchVideo(scrapeId, shortcode, btn) {
    btn.disabled = true;
    btn.textContent = 'DOWNLOADING...';

    try {
        const response = await fetch(`/api/fetch/video/${scrapeId}/${shortcode}`, {
            method: 'POST'
        });
        const data = await response.json();

        if (data.success) {
            btn.textContent = 'DOWNLOADED ✓';
            btn.classList.add('primary');
            btn.disabled = true;

            // Refresh video gallery if in gallery view
            if (currentView === 'gallery') {
                refreshVideoGallery();
            }
        } else {
            throw new Error(data.error || 'Download failed');
        }
    } catch (error) {
        btn.textContent = 'FAILED';
        setTimeout(() => {
            btn.textContent = 'DOWNLOAD';
            btn.disabled = false;
        }, 2000);
    }
}

// Download file
function downloadFile(url) {
    window.location.href = url;
}

// Close modal
function closeModal() {
    reelModal.classList.remove('active');
}

// Load history item
function loadHistoryItem(scrapeId) {
    const item = historyData.find(h => h.id === scrapeId);
    if (item) {
        currentResults = item;
        renderResults(item);
        // Always switch to list view to show loaded results
        switchView('list');
    }
}

// Delete history item
async function deleteHistoryItem(scrapeId) {
    if (!confirm('Delete this scrape from history?')) return;

    try {
        await fetch(`/api/history/${scrapeId}`, { method: 'DELETE' });
        refreshHistory();
    } catch (error) {
        console.error('Delete failed:', error);
    }
}

// Clear all history
document.getElementById('clearHistoryBtn')?.addEventListener('click', async function() {
    if (!confirm('Clear all scrape history?')) return;

    try {
        await fetch('/api/history/clear', { method: 'POST' });
        refreshHistory();
    } catch (error) {
        console.error('Clear failed:', error);
    }
});

// Clear results
document.getElementById('clearResultsBtn')?.addEventListener('click', function() {
    currentResults = null;
    resultsContent.innerHTML = `
        <div class="empty-state">
            <div class="empty-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <circle cx="11" cy="11" r="8"/>
                    <path d="M21 21l-4.35-4.35"/>
                </svg>
            </div>
            <div class="empty-text">NO INTEL GATHERED</div>
            <div class="empty-subtext">Configure target and execute scrape</div>
        </div>
    `;
});

// Refresh history from server
async function refreshHistory() {
    try {
        const response = await fetch('/api/history');
        historyData = await response.json();
        renderHistory();
    } catch (error) {
        console.error('Failed to load history:', error);
    }
}

// Render history list
function renderHistory() {
    if (!historyData || historyData.length === 0) {
        historyList.innerHTML = `
            <div class="empty-state small">
                <div class="empty-text">NO HISTORY</div>
            </div>
        `;
        return;
    }

    let html = '';
    historyData.forEach(item => {
        html += `
            <div class="history-item" data-id="${item.id}">
                <div class="history-main">
                    <span class="history-username">@${item.username}</span>
                    <span class="history-stats">${item.top_count} reels / ${item.total_reels} total</span>
                </div>
                <div class="history-meta">
                    <span class="history-time">${item.timestamp?.substring(0, 16) || ''}</span>
                    <div class="history-actions">
                        <button class="history-btn load" onclick="loadHistoryItem('${item.id}')">LOAD</button>
                        <button class="history-btn delete" onclick="deleteHistoryItem('${item.id}')">DEL</button>
                    </div>
                </div>
            </div>
        `;
    });
    historyList.innerHTML = html;
}

// Utility functions
function formatNumber(num) {
    if (!num) return '0';
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toLocaleString();
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Escape JSON for use in single-quoted HTML attributes
function escapeJsonAttr(obj) {
    const json = JSON.stringify(obj);
    // Escape single quotes and backslashes for safe embedding in single-quoted attributes
    return json.replace(/\\/g, '\\\\').replace(/'/g, '&#39;');
}

function showError(message) {
    progressSection.style.display = 'block';
    progressText.innerHTML = `<span style="cursor: pointer;" onclick="dismissError()">ERROR: ${message} <small style="opacity: 0.6;">(click to dismiss)</small></span>`;
    progressText.style.color = 'var(--color-danger)';
    progressFill.style.width = '0%';
    progressFill.style.background = 'var(--color-danger)';
}

function dismissError() {
    progressSection.style.display = 'none';
    progressText.style.color = '';
    progressText.textContent = '';
    progressFill.style.background = '';
}

function resetForm() {
    // Stop polling by clearing the scrape ID
    currentScrapeId = null;

    executeBtn.disabled = false;
    executeBtn.querySelector('.btn-text').textContent = 'EXECUTE SCRAPE';
    setTimeout(() => {
        progressSection.style.display = 'none';
        progressFill.style.width = '0%';
        progressFill.style.background = '';
        progressText.style.color = '';
    }, 2000);
}

// Initialize
refreshHistory();
loadSettings();

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeModal();
        closeSettingsModal();
        closeRewriteModal();
    }
});

// =====================
// SETTINGS FUNCTIONALITY
// =====================

const settingsModal = document.getElementById('settingsModal');
const aiProvider = document.getElementById('aiProvider');

// Open settings modal
document.getElementById('openSettingsBtn')?.addEventListener('click', function() {
    settingsModal.classList.add('active');
    refreshOllamaModels();
});

// Close settings modal
function closeSettingsModal() {
    settingsModal.classList.remove('active');
}

// Provider change handler
aiProvider?.addEventListener('change', function() {
    updateProviderSections();
});

// Cached settings for rewrite modal (stores provider availability)
let cachedSettings = null;

function updateProviderSections() {
    // All provider sections are now always visible - no hiding needed
    // This function is kept for compatibility but does nothing
}

// Models for each provider (used in rewrite modal)
const providerModels = {
    local: [], // Populated dynamically from Ollama
    openai: ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo'],
    anthropic: ['claude-3-5-haiku-20241022', 'claude-3-5-sonnet-20241022', 'claude-3-opus-20240229'],
    google: ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash-exp']
};

// Update rewrite model dropdown based on selected provider
function updateRewriteModel() {
    const provider = document.getElementById('rewriteProvider').value;
    const modelSelect = document.getElementById('rewriteModel');
    const statusDiv = document.getElementById('rewriteProviderStatus');

    modelSelect.innerHTML = '';

    if (provider === 'local') {
        // Use cached Ollama models
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
        // Use static model lists
        const models = providerModels[provider] || [];
        models.forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            option.textContent = model;
            modelSelect.appendChild(option);
        });

        // Check if API key is configured
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

// Load settings from server
async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        const settings = await response.json();

        // Cache settings for rewrite modal
        cachedSettings = settings;

        // Output directory setting
        const outputDirInput = document.getElementById('outputDirectory');
        const outputDirHint = document.getElementById('outputDirHint');
        if (outputDirInput) {
            outputDirInput.value = settings.output_directory || '';
            outputDirInput.placeholder = settings.default_output_directory || './output';
        }
        if (outputDirHint) {
            outputDirHint.textContent = settings.output_directory
                ? `Using: ${settings.output_directory}`
                : `Default: ${settings.default_output_directory || './output'}`;
        }

        if (aiProvider) aiProvider.value = settings.ai_provider || 'copy';
        document.getElementById('localModel').value = settings.local_model || '';
        document.getElementById('openaiModel').value = settings.openai_model || 'gpt-4o-mini';
        document.getElementById('anthropicModel').value = settings.anthropic_model || 'claude-3-5-haiku-20241022';
        document.getElementById('googleModel').value = settings.google_model || 'gemini-1.5-flash';

        // Update key status indicators
        if (settings.has_openai_key) {
            document.getElementById('openaiKeyStatus').textContent = 'Key configured';
            document.getElementById('openaiKeyStatus').style.color = 'var(--color-accent-primary)';
        }
        if (settings.has_anthropic_key) {
            document.getElementById('anthropicKeyStatus').textContent = 'Key configured';
            document.getElementById('anthropicKeyStatus').style.color = 'var(--color-accent-primary)';
        }
        if (settings.has_google_key) {
            document.getElementById('googleKeyStatus').textContent = 'Key configured';
            document.getElementById('googleKeyStatus').style.color = 'var(--color-accent-primary)';
        }

        updateProviderSections();

        // Also fetch Ollama models for rewrite modal
        fetchOllamaModelsForRewrite();
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

// Fetch Ollama models silently for rewrite modal
async function fetchOllamaModelsForRewrite() {
    try {
        const response = await fetch('/api/ollama/models');
        const data = await response.json();
        if (data.available && data.models.length > 0) {
            providerModels.local = data.models;
        }
    } catch (error) {
        // Silently fail - Ollama might not be running
        providerModels.local = [];
    }
}

// Save settings to server
async function saveSettings() {
    const settings = {
        ai_provider: aiProvider.value,
        local_model: document.getElementById('localModel').value,
        openai_model: document.getElementById('openaiModel').value,
        anthropic_model: document.getElementById('anthropicModel').value,
        google_model: document.getElementById('googleModel').value,
        output_directory: document.getElementById('outputDirectory').value.trim()
    };

    // Only include keys if they have values
    const openaiKey = document.getElementById('openaiKey').value;
    const anthropicKey = document.getElementById('anthropicKey').value;
    const googleKey = document.getElementById('googleKey').value;

    if (openaiKey) settings.openai_key = openaiKey;
    if (anthropicKey) settings.anthropic_key = anthropicKey;
    if (googleKey) settings.google_key = googleKey;

    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });

        if (response.ok) {
            closeSettingsModal();
            // Clear key inputs after save
            document.getElementById('openaiKey').value = '';
            document.getElementById('anthropicKey').value = '';
            document.getElementById('googleKey').value = '';
            // Reload settings to update status
            loadSettings();
            // Refresh video gallery if in gallery view
            if (currentView === 'gallery') {
                refreshVideoGallery();
            }
        }
    } catch (error) {
        console.error('Failed to save settings:', error);
    }
}

// Refresh Ollama models
async function refreshOllamaModels() {
    const localModel = document.getElementById('localModel');
    const ollamaStatus = document.getElementById('ollamaStatus');

    ollamaStatus.textContent = 'Checking Ollama...';
    ollamaStatus.style.color = '';

    try {
        const response = await fetch('/api/ollama/models');
        const data = await response.json();

        if (data.available && data.models.length > 0) {
            localModel.innerHTML = '<option value="">-- Select Model --</option>';
            data.models.forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                localModel.appendChild(option);
            });
            ollamaStatus.textContent = `${data.models.length} models available`;
            ollamaStatus.style.color = 'var(--color-accent-primary)';
        } else {
            ollamaStatus.textContent = 'Ollama not running or no models installed';
            ollamaStatus.style.color = 'var(--color-danger)';
        }
    } catch (error) {
        ollamaStatus.textContent = 'Failed to connect to Ollama';
        ollamaStatus.style.color = 'var(--color-danger)';
    }
}

// =====================
// AI PROMPT FUNCTIONALITY
// =====================

// Fallback clipboard copy method
function fallbackCopyToClipboard(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    textarea.style.top = '-9999px';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();

    try {
        document.execCommand('copy');
        return true;
    } catch (err) {
        console.error('Fallback copy failed:', err);
        return false;
    } finally {
        document.body.removeChild(textarea);
    }
}

// Copy to clipboard with fallback
async function copyToClipboard(text) {
    // Try modern clipboard API first
    if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (err) {
            console.warn('Clipboard API failed, trying fallback:', err);
        }
    }
    // Fallback to execCommand
    return fallbackCopyToClipboard(text);
}

// Copy AI prompt to clipboard
async function copyAIPrompt(event, scrapeId, shortcode) {
    const btn = event?.target?.closest('button') || document.activeElement;
    const originalHTML = btn.innerHTML;

    try {
        const response = await fetch(`/api/generate-prompt/${scrapeId}/${shortcode}`);
        const data = await response.json();

        if (data.error) {
            alert(`Error: ${data.error}`);
            return;
        }

        if (data.prompt) {
            const success = await copyToClipboard(data.prompt);
            if (success) {
                btn.innerHTML = '<span style="color: var(--color-accent-primary)">COPIED!</span>';
                setTimeout(() => {
                    btn.innerHTML = originalHTML;
                }, 2000);
            } else {
                alert('Failed to copy to clipboard. Try selecting and copying manually.');
            }
        } else {
            alert('Failed to generate prompt - no data returned');
        }
    } catch (error) {
        console.error('Failed to copy prompt:', error);
        alert(`Failed to copy prompt: ${error.message}`);
    }
}

// =====================
// REWRITE FUNCTIONALITY
// =====================

const rewriteModal = document.getElementById('rewriteModal');
const TOTAL_WIZARD_STEPS = 8;
let wizardStep = 0;
let wizardData = {};
let wizardMode = 'guided'; // 'guided' or 'quick'

// Open rewrite modal
function openRewriteModal(scrapeId, shortcode) {
    currentRewriteReel = { scrapeId, shortcode };

    // Reset wizard state
    resetWizardState();

    // Set default provider from settings
    const providerSelect = document.getElementById('rewriteProvider');
    if (cachedSettings && cachedSettings.ai_provider && cachedSettings.ai_provider !== 'copy') {
        providerSelect.value = cachedSettings.ai_provider;
    } else {
        // Default to first available configured provider
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

    // Populate model dropdown
    updateRewriteModel();

    // Initialize option button handlers
    initWizardOptionButtons();

    rewriteModal.classList.add('active');
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

    // Clear all inputs
    const inputs = ['wizardNiche', 'wizardVoice', 'wizardAngle', 'wizardProduct', 'wizardSetup', 'wizardCta'];
    inputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });

    // Reset option buttons
    document.querySelectorAll('.voice-btn, .cta-btn').forEach(btn => btn.classList.remove('selected'));
    document.querySelectorAll('.time-btn').forEach(btn => {
        btn.classList.toggle('selected', btn.dataset.time === 'Under 60 seconds');
    });

    // Reset result display
    document.getElementById('rewriteResult').style.display = 'none';
    document.getElementById('rewriteOutput').textContent = '';
    document.getElementById('resultPlaceholder').style.display = 'flex';

    updateWizardUI();
}

// Initialize option button click handlers
function initWizardOptionButtons() {
    // Voice buttons
    document.querySelectorAll('.voice-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.voice-btn').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            document.getElementById('wizardVoice').value = btn.dataset.voice;
        };
    });

    // CTA buttons
    document.querySelectorAll('.cta-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.cta-btn').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            document.getElementById('wizardCta').value = btn.dataset.cta;
        };
    });

    // Time buttons
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
    // Update progress bar
    const progress = ((wizardStep + 1) / TOTAL_WIZARD_STEPS) * 100;
    document.getElementById('wizardProgressBar').style.width = `${progress}%`;

    // Update step count
    document.getElementById('wizardStepCount').textContent = `Step ${wizardStep + 1} of ${TOTAL_WIZARD_STEPS}`;

    // Show/hide steps
    document.querySelectorAll('.wizard-step').forEach(step => {
        step.classList.toggle('active', parseInt(step.dataset.step) === wizardStep);
    });

    // Update navigation buttons
    const backBtn = document.getElementById('wizardBackBtn');
    const skipBtn = document.getElementById('wizardSkipBtn');
    const nextBtn = document.getElementById('wizardNextBtn');

    backBtn.style.display = wizardStep > 0 ? 'inline-flex' : 'none';

    // Last step changes to Generate
    if (wizardStep === TOTAL_WIZARD_STEPS - 1) {
        nextBtn.textContent = 'GENERATE';
        nextBtn.classList.add('primary');
        skipBtn.style.display = 'none';
    } else {
        nextBtn.textContent = 'NEXT';
        skipBtn.style.display = wizardStep === 0 ? 'none' : 'inline-flex'; // Can't skip provider
    }
}

// Collect current step data
function collectStepData() {
    switch(wizardStep) {
        case 1:
            wizardData.niche = document.getElementById('wizardNiche').value.trim();
            break;
        case 2:
            wizardData.voice = document.getElementById('wizardVoice').value.trim();
            break;
        case 3:
            wizardData.angle = document.getElementById('wizardAngle').value.trim();
            break;
        case 4:
            wizardData.product = document.getElementById('wizardProduct').value.trim();
            break;
        case 5:
            wizardData.setup = document.getElementById('wizardSetup').value.trim();
            break;
        case 6:
            wizardData.cta = document.getElementById('wizardCta').value.trim();
            break;
        case 7:
            // Time is already stored via button clicks
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

    // Validate provider selection on step 0
    if (wizardStep === 0) {
        const model = document.getElementById('rewriteModel').value;
        if (!model) {
            alert('Please select a model');
            return;
        }
    }

    if (wizardStep < TOTAL_WIZARD_STEPS - 1) {
        wizardStep++;
        updateWizardUI();
    } else {
        // Generate on last step
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
    // Don't collect data for skipped step
    if (wizardStep < TOTAL_WIZARD_STEPS - 1) {
        wizardStep++;
        updateWizardUI();
    }
}

// Reset wizard to start over
function resetWizard() {
    resetWizardState();
}

// Go back to wizard to edit context (keeps current data)
function editWizardContext() {
    // Go to step 1 (niche) to let them edit, keeping all current values
    wizardStep = 1;

    // Hide result, show placeholder
    document.getElementById('rewriteResult').style.display = 'none';
    document.getElementById('resultPlaceholder').style.display = 'flex';
    document.getElementById('resultPlaceholder').innerHTML = `
        <div class="placeholder-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
            </svg>
        </div>
        <div class="placeholder-text">Your rewritten script will appear here</div>
        <div class="placeholder-hint">Edit your context and click Generate</div>
    `;

    updateWizardUI();
}

// Switch between guided and quick mode
function setWizardMode(mode) {
    wizardMode = mode;

    // Update toggle buttons
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
    });

    // Show/hide modes
    document.getElementById('guidedMode').style.display = mode === 'guided' ? 'flex' : 'none';
    document.getElementById('quickMode').style.display = mode === 'quick' ? 'flex' : 'none';

    // Sync provider selection to quick mode
    if (mode === 'quick') {
        const guidedProvider = document.getElementById('rewriteProvider').value;
        document.getElementById('quickProvider').value = guidedProvider;
        updateQuickModel();
    }

    // Hide result, show placeholder
    document.getElementById('rewriteResult').style.display = 'none';
    document.getElementById('resultPlaceholder').style.display = 'flex';
}

// Update quick mode model dropdown
function updateQuickModel() {
    const provider = document.getElementById('quickProvider').value;
    const modelSelect = document.getElementById('quickModel');
    modelSelect.innerHTML = '';

    const models = providerModels[provider] || [];
    models.forEach(model => {
        const option = document.createElement('option');
        option.value = model;
        option.textContent = model;
        modelSelect.appendChild(option);
    });

    // Set default model
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
    const context = document.getElementById('quickContext').value.trim();
    const provider = document.getElementById('quickProvider').value;
    const model = document.getElementById('quickModel').value;

    if (!model) {
        alert('Please select a model');
        return;
    }

    btn.disabled = true;
    btn.textContent = 'GENERATING...';
    placeholder.innerHTML = `
        <div class="placeholder-icon" style="opacity: 0.6;">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M12 2v4m0 12v4m-8-10H0m24 0h-4m-2.343-5.657l-2.828 2.828m-5.658 5.658l-2.828 2.828m0-11.314l2.828 2.828m5.658 5.658l2.828 2.828"/>
            </svg>
        </div>
        <div class="placeholder-text">Generating your script...</div>
        <div class="placeholder-hint">This may take a few seconds</div>
    `;

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

        outputDiv.textContent = data.result;
        placeholder.style.display = 'none';
        resultDiv.style.display = 'flex';

    } catch (error) {
        alert(`Error: ${error.message}`);
        placeholder.innerHTML = `
            <div class="placeholder-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                </svg>
            </div>
            <div class="placeholder-text">Your rewritten script will appear here</div>
            <div class="placeholder-hint">Add context and click Generate</div>
        `;
    } finally {
        btn.disabled = false;
        btn.textContent = 'GENERATE';
    }
}

// Close rewrite modal
function closeRewriteModal() {
    rewriteModal.classList.remove('active');
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
    const provider = document.getElementById('rewriteProvider').value;
    const model = document.getElementById('rewriteModel').value;

    // Validate provider/model selection
    if (!model) {
        alert('Please select a model');
        return;
    }

    btn.disabled = true;
    btn.textContent = 'GENERATING...';
    placeholder.innerHTML = `
        <div class="placeholder-icon" style="opacity: 0.6;">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M12 2v4m0 12v4m-8-10H0m24 0h-4m-2.343-5.657l-2.828 2.828m-5.658 5.658l-2.828 2.828m0-11.314l2.828 2.828m5.658 5.658l2.828 2.828"/>
            </svg>
        </div>
        <div class="placeholder-text">Generating your script...</div>
        <div class="placeholder-hint">This may take a few seconds</div>
    `;

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

        outputDiv.textContent = data.result;
        placeholder.style.display = 'none';
        resultDiv.style.display = 'flex';

    } catch (error) {
        alert(`Error: ${error.message}`);
        // Reset placeholder
        placeholder.innerHTML = `
            <div class="placeholder-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                </svg>
            </div>
            <div class="placeholder-text">Your rewritten script will appear here</div>
            <div class="placeholder-hint">Complete the wizard and click Generate</div>
        `;
    } finally {
        btn.disabled = false;
        btn.textContent = 'GENERATE';
    }
}

// Copy rewrite result
async function copyRewriteResult(event) {
    const output = document.getElementById('rewriteOutput').textContent;
    const success = await copyToClipboard(output);

    if (success) {
        const btn = event?.target || document.querySelector('.copy-rewrite-btn');
        const originalText = btn.textContent;
        btn.textContent = 'COPIED!';
        btn.style.color = 'var(--color-accent-primary)';
        setTimeout(() => {
            btn.textContent = originalText;
            btn.style.color = '';
        }, 2000);
    } else {
        alert('Failed to copy. Try selecting and copying manually.');
    }
}

// =====================
// VIDEO GALLERY FUNCTIONALITY
// =====================

let currentView = 'list';
let galleryVideos = [];
let showAllVideos = false; // false = filter by current profile, true = show all

// Switch between list and gallery views
function switchView(view) {
    currentView = view;
    const listViewBtn = document.getElementById('listViewBtn');
    const galleryViewBtn = document.getElementById('galleryViewBtn');
    const resultsContent = document.getElementById('resultsContent');
    const videoGallery = document.getElementById('videoGallery');

    if (view === 'list') {
        listViewBtn.classList.add('active');
        galleryViewBtn.classList.remove('active');
        resultsContent.style.display = 'block';
        videoGallery.style.display = 'none';
    } else {
        listViewBtn.classList.remove('active');
        galleryViewBtn.classList.add('active');
        resultsContent.style.display = 'none';
        videoGallery.style.display = 'block';
        refreshVideoGallery();
    }
}

// Toggle between filtered and all videos
function toggleShowAllVideos() {
    showAllVideos = !showAllVideos;
    refreshVideoGallery();
}

// Refresh video gallery from server
async function refreshVideoGallery() {
    const videoGrid = document.getElementById('videoGrid');
    const galleryCount = document.getElementById('galleryCount');
    const seeAllBtn = document.getElementById('gallerySeeAllBtn');

    // Get current username from loaded profile
    const currentUsername = currentResults?.username || null;

    try {
        // Build URL with optional filter
        let url = '/api/videos';
        if (!showAllVideos && currentUsername) {
            url += `?username=${encodeURIComponent(currentUsername)}`;
        }

        const response = await fetch(url);
        const data = await response.json();

        galleryVideos = data.videos || [];

        // Update count label
        const countLabel = data.filtered
            ? `${galleryVideos.length} video${galleryVideos.length !== 1 ? 's' : ''} from @${data.filter_username}`
            : `${galleryVideos.length} video${galleryVideos.length !== 1 ? 's' : ''} (all profiles)`;
        galleryCount.textContent = countLabel;

        // Update See All button state
        if (seeAllBtn) {
            if (showAllVideos || !currentUsername) {
                seeAllBtn.textContent = currentUsername ? 'FILTER' : 'ALL';
                seeAllBtn.classList.toggle('active', showAllVideos);
            } else {
                seeAllBtn.textContent = 'SEE ALL';
                seeAllBtn.classList.remove('active');
            }
            // Hide button if no profile loaded
            seeAllBtn.style.display = currentUsername ? 'inline-flex' : 'none';
        }

        if (galleryVideos.length === 0) {
            videoGrid.innerHTML = `
                <div class="empty-state" style="grid-column: 1 / -1;">
                    <div class="empty-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                            <polygon points="23 7 16 12 23 17 23 7"/>
                            <rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
                        </svg>
                    </div>
                    <div class="empty-text">NO VIDEOS</div>
                    <div class="empty-subtext">Enable "Download Videos" to populate gallery</div>
                </div>
            `;
            return;
        }

        videoGrid.innerHTML = galleryVideos.map(video => createVideoCard(video)).join('');

    } catch (error) {
        console.error('Failed to load videos:', error);
        videoGrid.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <div class="empty-text">ERROR LOADING VIDEOS</div>
                <div class="empty-subtext">${error.message}</div>
            </div>
        `;
    }
}

// Create video card HTML
function createVideoCard(video) {
    const viewsFormatted = formatNumber(video.views || 0);
    // Store video data for playback - use escapeJsonAttr for safe embedding in single-quoted attribute
    const videoDataAttr = escapeJsonAttr({
        url: video.url,
        username: video.username,
        views: video.views || 0,
        path: video.path,
        transcript: video.transcript || '',
        caption: video.caption || '',
        shortcode: video.shortcode || '',
        scrape_id: video.scrape_id || '',
        reel_url: video.reel_url || ''
    });

    return `
        <div class="video-card" data-path="${escapeHtml(video.path)}" data-video='${videoDataAttr}'>
            <div class="video-thumbnail">
                <video src="${video.url}" preload="metadata" muted></video>
                <div class="video-overlay">
                    <button class="video-play-btn" onclick="playVideoFromCard(this.closest('.video-card'))">
                        <svg viewBox="0 0 24 24" fill="currentColor">
                            <polygon points="5,3 19,12 5,21"/>
                        </svg>
                    </button>
                </div>
                ${video.transcript ? '<span class="video-transcript-badge" title="Has transcript">T</span>' : ''}
                <button class="video-delete-btn" onclick="event.stopPropagation(); deleteVideo('${escapeHtml(video.path)}', '${escapeHtml(video.username)}', '${escapeHtml(video.filename)}')" title="Delete Video">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6h14"/>
                        <line x1="10" y1="11" x2="10" y2="17"/>
                        <line x1="14" y1="11" x2="14" y2="17"/>
                    </svg>
                </button>
            </div>
            <div class="video-info">
                <div class="video-username">@${escapeHtml(video.username)}</div>
                <div class="video-views"><strong>${viewsFormatted}</strong> views</div>
            </div>
        </div>
    `;
}

// Play video from card element (reads data attribute)
function playVideoFromCard(card) {
    try {
        const videoData = JSON.parse(card.dataset.video);
        playVideoWithTranscript(videoData);
    } catch (e) {
        console.error('Failed to parse video data:', e);
    }
}

// Play video in modal (legacy - without transcript)
function playVideo(url, username, views, path) {
    playVideoWithTranscript({
        url, username, views, path,
        transcript: '', caption: '', shortcode: '', scrape_id: '', reel_url: ''
    });
}

// Play video with transcript panel
function playVideoWithTranscript(videoData) {
    const { url, username, views, path, transcript, caption, shortcode, scrape_id, reel_url } = videoData;
    const hasTranscript = transcript && transcript.trim();

    const modalHtml = `
        <div class="modal active" id="videoPlayerModal">
            <div class="modal-backdrop" onclick="closeVideoPlayer()"></div>
            <div class="modal-content video-player-modal ${hasTranscript ? 'with-transcript' : ''}">
                <div class="modal-header">
                    <span class="modal-title">VIDEO PLAYER</span>
                    <button class="modal-close" onclick="closeVideoPlayer()">&times;</button>
                </div>
                <div class="modal-body video-player-layout">
                    <div class="video-player-main">
                        <div class="video-player-container">
                            <video src="${url}" controls autoplay></video>
                        </div>
                        <div class="video-player-info">
                            <div class="video-player-username">@${escapeHtml(username)}</div>
                            <div class="video-player-stats">${formatNumber(views)} views</div>
                            <div class="video-player-actions">
                                ${reel_url ? `<a href="${escapeHtml(reel_url)}" target="_blank" class="modal-btn">VIEW ON IG</a>` : ''}
                                <button class="modal-btn danger" onclick="deleteVideo('${escapeHtml(path)}', '${escapeHtml(username)}', ''); closeVideoPlayer();">DELETE</button>
                            </div>
                        </div>
                    </div>
                    <div class="video-transcript-panel">
                        <div class="transcript-header">
                            <span class="transcript-title">TRANSCRIPT</span>
                            ${hasTranscript ? `
                                <div class="transcript-actions">
                                    <button class="transcript-action-btn" onclick="copyTranscript()" title="Copy to clipboard">
                                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                                        </svg>
                                    </button>
                                    ${scrape_id ? `
                                        <button class="transcript-action-btn" onclick="openRewriteFromGallery('${escapeHtml(scrape_id)}', '${escapeHtml(shortcode)}')" title="AI Rewrite">
                                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                                                <path d="M12 20h9"/>
                                                <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
                                            </svg>
                                        </button>
                                    ` : ''}
                                </div>
                            ` : ''}
                        </div>
                        <div class="transcript-content" id="transcriptContent">
                            ${hasTranscript
                                ? `<p class="transcript-text">${escapeHtml(transcript)}</p>`
                                : `<div class="transcript-empty">
                                        <div class="empty-icon">
                                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="32" height="32">
                                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                                                <polyline points="14,2 14,8 20,8"/>
                                                <line x1="16" y1="13" x2="8" y2="13"/>
                                                <line x1="16" y1="17" x2="8" y2="17"/>
                                                <polyline points="10,9 9,9 8,9"/>
                                            </svg>
                                        </div>
                                        <div class="empty-text">NO TRANSCRIPT</div>
                                        <div class="empty-subtext">Enable transcription during scrape to generate</div>
                                    </div>`
                            }
                        </div>
                        ${caption ? `
                            <div class="caption-section">
                                <div class="caption-label">CAPTION</div>
                                <p class="caption-text">${escapeHtml(caption)}</p>
                            </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        </div>
    `;

    // Store current transcript for copy function
    window.currentTranscript = transcript || '';

    // Remove existing player modal if any
    const existingModal = document.getElementById('videoPlayerModal');
    if (existingModal) existingModal.remove();

    // Add new modal
    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

// Copy transcript to clipboard
async function copyTranscript() {
    if (!window.currentTranscript) return;

    try {
        await navigator.clipboard.writeText(window.currentTranscript);
        // Show brief feedback
        const btn = document.querySelector('.transcript-action-btn');
        if (btn) {
            const originalTitle = btn.title;
            btn.title = 'Copied!';
            btn.classList.add('success');
            setTimeout(() => {
                btn.title = originalTitle;
                btn.classList.remove('success');
            }, 1500);
        }
    } catch (err) {
        console.error('Failed to copy:', err);
    }
}

// Open rewrite modal from gallery
function openRewriteFromGallery(scrapeId, shortcode) {
    closeVideoPlayer();
    openRewriteModal(scrapeId, shortcode);
}

// Close video player modal
function closeVideoPlayer() {
    const modal = document.getElementById('videoPlayerModal');
    if (modal) {
        // Stop video playback
        const video = modal.querySelector('video');
        if (video) {
            video.pause();
            video.src = '';
        }
        modal.remove();
    }
}

// Delete video from filesystem
async function deleteVideo(path, username, filename) {
    const displayName = filename || path.split('/').pop();

    if (!confirm(`Delete video "${displayName}" from @${username}?\n\nThis will permanently remove the file from your computer.`)) {
        return;
    }

    try {
        const response = await fetch('/api/videos/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: path })
        });

        const data = await response.json();

        if (data.success) {
            // Remove from gallery
            refreshVideoGallery();
        } else {
            throw new Error(data.error || 'Delete failed');
        }
    } catch (error) {
        alert(`Failed to delete video: ${error.message}`);
    }
}

// Keyboard handler for video player
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeVideoPlayer();
    }
});
