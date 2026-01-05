# Changelog - 2026-01-05

## Settings Section - Complete Implementation

### Overview

Added a full-featured Settings section to the ReelRecon workspace with 4 tabbed panels for configuring API providers, customizing the Rewrite Wizard, enhancing Copy for AI output, and setting UI preferences. Matches the existing dark minimalist aesthetic with consistent card-based layouts.

---

## Tab 1: API Keys & Providers

### Features

- **Multi-provider support**: OpenAI, Anthropic, Google Gemini, Ollama (local)
- **Masked API key inputs**: Keys display as dots when populated
- **Connection status indicators**: Green/gray dots showing configured status
- **Test connection button**: Validates API keys before saving
- **Model selection dropdowns**: Default model per provider
- **Ollama integration**: Auto-detects local Ollama and lists available models
- **Compact grid layout**: 5-column grid (name, input, status, model, action)

### Technical Details

```
Provider Grid Columns: 80px | 180px | 16px | 140px | 55px
Status: Uses /api/ollama/models for model refresh
Keys: Backend stores keys, returns only `has_*_key` boolean flags
```

---

## Tab 2: Rewrite Wizard Configuration

### Features

#### System Prompt Customization
- **Two-column layout**: Custom prompt (left) + Default prompt reference (right)
- **Mode toggle**: Append (safe) or Override (with warning)
- **Revert to default**: One-click reset to built-in system prompt

#### Template Variables
Dynamic placeholders that substitute real reel data at rewrite time:

| Variable | Description |
|----------|-------------|
| `{{VIEWS}}` | Reel view count |
| `{{LIKES}}` | Like count |
| `{{COMMENTS}}` | Comment count |
| `{{SHARES}}` | Share count |
| `{{CREATOR}}` | Creator username |
| `{{PLATFORM}}` | Instagram/TikTok |
| `{{TRANSCRIPT}}` | Full transcript |
| `{{CAPTION}}` | Original caption |
| `{{DURATION}}` | Video duration |
| `{{NICHE}}` | User's niche setting |
| `{{VOICE}}` | User's voice style |
| `{{ANGLE}}` | User's angle |
| `{{CTA}}` | User's CTA preference |

- Click-to-copy functionality
- Substituted at `/api/rewrite` endpoint before LLM call

#### Quick Context Templates
- **Custom modal editor**: Replaces browser prompts with draggable modal
- **Quick insert buttons**: Insert field labels (NICHE:, VOICE:, etc.) with one click
- **Edit/Delete inline**: Manage templates directly from list
- **Two-column layout**: Default Wizard Values (left) + Templates list (right)

#### Default Wizard Values
Pre-fill wizard fields with saved defaults:
- Niche
- Voice style
- Content angle
- Call-to-action
- Time limit

---

## Tab 3: Copy for AI Enhancement

### Features

- **Toggle enable/disable**: Control custom prompt prepend
- **Custom prompt textarea**: Define prompt to prepend before reel metadata
- **Live preview**: Shows exactly what will be copied
- **Two-column layout**: Prompt editor (left) + Preview output (right)

### How It Works

When "Copy for AI" is clicked on a reel:
1. If enabled, custom prompt is prepended
2. Standard reel metadata follows (creator, platform, stats, caption, transcript)
3. Clipboard contains full context for external AI tools

---

## Tab 4: UI Preferences

### Features

- **Library View**: Default display mode (List, Grid-2, Grid-3)
- **Jobs View**: Default display mode (List, Grid-2, Grid-3)
- **Detail Panel**: Default width in pixels
- **Output Directory**: Custom output path override

### Layout

Two-row grid layout:
- Row 1: Library View | Jobs View
- Row 2: Detail Panel | Output Directory

Equal-height cards using flexbox stretching.

---

## Toast Notification System

### New Addition

Created a toast notification system for user feedback on save operations and other actions.

### Features

- **4 toast types**: success (green), error (red), warning (amber), info (blue)
- **Auto-dismiss**: 3 second default duration
- **Slide animation**: Slides in from right, slides out on dismiss
- **Stacking**: Multiple toasts stack vertically
- **Icon indicators**: Checkmark, X, warning triangle, info circle

### Usage

```javascript
showToast('Settings saved!', 'success');
showToast('API key invalid', 'error');
showToast('Changes pending', 'warning');
showToast('Testing connection...', 'info');
```

---

## Template Editor Modal

### Features

Custom modal for creating/editing Quick Context Templates:

- **Draggable/resizable**: Uses ModalUtils system
- **Name input**: Template identifier
- **Content textarea**: Multi-line template content
- **Quick insert buttons**: NICHE, VOICE, ANGLE, CTA, CONTEXT field labels
- **Save/Cancel actions**: Validates before saving

Replaces browser `prompt()` dialogs for better UX.

---

## Files Modified

| File | Changes |
|------|---------|
| `templates/workspace.html` | Full settings HTML structure (4 tabs, all forms, template editor modal) |
| `static/css/workspace.css` | ~600 lines of `.settings-*` classes, toast CSS, responsive layouts |
| `static/js/workspace.js` | Settings functions, toast system, template editor, variable substitution |
| `app.py` | Extended DEFAULT_CONFIG, updated GET/POST `/api/settings` |

### workspace.html Additions

- Settings view with tabbed navigation
- API Keys provider grid
- System prompt two-column layout
- Template variables reference panel (Jinja2-escaped)
- Template editor modal
- Copy for AI preview panel
- Preferences radio groups

### workspace.css Additions

| Section | Line Range | Description |
|---------|------------|-------------|
| Settings tabs | 8400-8450 | Tab navigation styling |
| Settings cards | 8450-8520 | Card, field, input styles |
| Provider grid | 8520-8580 | 5-column provider layout |
| Two-column layouts | 4249-4310 | Flexbox grid for side-by-side content |
| Template editor | 8580-8700 | Modal, buttons, quick insert |
| Toast notifications | 8838-8925 | Container, animations, type colors |

### workspace.js Additions

| Function | Purpose |
|----------|---------|
| `showToast()` | Display notification toast |
| `loadSettingsView()` | Initialize settings when navigating to view |
| `populateSettingsForm()` | Fill forms from cached settings |
| `updateProviderStatus()` | Update status dots for each provider |
| `setupSettingsTabSwitching()` | Tab click handlers |
| `testApiKey()` | Validate API key with test request |
| `refreshOllamaModels()` | Fetch models from `/api/ollama/models` |
| `setSystemPromptMode()` | Toggle append/override mode |
| `revertSystemPrompt()` | Reset to default prompt |
| `copyTemplateVar()` | Copy variable to clipboard |
| `openTemplateEditor()` | Show template modal |
| `closeTemplateEditor()` | Hide template modal |
| `saveTemplate()` | Save template from modal |
| `insertTemplateField()` | Quick insert field label |
| `addQuickTemplate()` | Open modal in add mode |
| `editQuickTemplate()` | Open modal in edit mode |
| `deleteQuickTemplate()` | Remove template from list |
| `updateCopyForAIPreview()` | Live preview update |
| `toggleCopyForAIPreview()` | Enable/disable preview |
| `saveApiKeysSettings()` | Save API Keys tab |
| `saveRewriteWizardSettings()` | Save Rewrite Wizard tab |
| `saveCopyForAISettings()` | Save Copy for AI tab |
| `savePreferencesSettings()` | Save Preferences tab |
| `substituteTemplateVars()` | Replace `{{VAR}}` with values (JS) |

### app.py Additions

Extended `DEFAULT_CONFIG`:
```python
'rewrite_system_prompt': '',
'rewrite_system_prompt_mode': 'append',
'rewrite_quick_templates': [],
'rewrite_defaults': {
    'niche': '', 'voice': '', 'angle': '', 'cta': '', 'timeLimit': 'Under 60 seconds'
},
'copy_for_ai_prompt_enabled': False,
'copy_for_ai_custom_prompt': ''
```

Added `substitute_template_vars()` Python function for backend variable substitution in `/api/rewrite` endpoint.

---

## CSS Design Patterns

### Consistent with Existing UI

- Uses `--color-bg-secondary` for cards
- Uses `--color-border-dim` for subtle borders
- Uses `--radius-lg` (12px) for card corners
- Monospace font for labels (`--font-mono`)
- Uppercase section titles with letter-spacing
- Emerald accent (`--color-accent-primary`) for active states
- 0.15s ease transitions for interactions

### Two-Column Layout Pattern

```css
.wizard-settings-columns {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-xl);
    align-items: stretch;
}

.wizard-settings-col {
    display: flex;
    flex-direction: column;
}

/* Cards stretch to equal heights */
.wizard-settings-col .settings-card {
    flex: 1;
}

/* Responsive collapse */
@media (max-width: 900px) {
    .wizard-settings-columns {
        grid-template-columns: 1fr;
    }
}
```

---

## Known Issues Fixed

| Issue | Resolution |
|-------|------------|
| Jinja2 interpreting `{{VIEWS}}` | Escaped with `{{ '{{VIEWS}}' }}` |
| Ollama models not loading | Changed to use `/api/ollama/models` directly |
| Button hover outline style | Added `:not(.settings-btn-primary)` to base hover |
| No save feedback | Implemented toast notification system |
| Unequal column heights | Added flex stretching and `max-height: none` |
| Duplicate function declarations | Removed duplicate `escapeHtml` |
| JS temporal dead zone | Moved `cachedSettings` to module top |

---

## Backend Schema

### Settings Storage

Settings stored in `config.json` via `load_config()`/`save_config()`.

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/settings` | GET | Retrieve all settings (keys masked) |
| `/api/settings` | POST | Update settings (partial update supported) |
| `/api/ollama/models` | GET | List available Ollama models |
| `/api/rewrite` | POST | Generate rewrite (applies variable substitution) |

---

## Testing Checklist

- [x] Tab navigation switches panels correctly
- [x] API key masking works (shows dots when populated)
- [x] Provider status dots update on load
- [x] Ollama model dropdown populates when connected
- [x] Test connection button shows results
- [x] System prompt modes toggle correctly
- [x] Template variables copy to clipboard
- [x] Quick context templates CRUD operations work
- [x] Template editor modal opens/closes
- [x] Copy for AI preview updates live
- [x] All save buttons show toast feedback
- [x] Settings persist across page refresh
- [x] Responsive layout works at narrow widths

---

*Last updated: 2026-01-05 12:32 CST*
