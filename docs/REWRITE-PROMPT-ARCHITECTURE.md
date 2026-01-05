# Rewrite Wizard Prompt Architecture

Reference document for the AI Script Rewriter prompt system.

---

## Overview

The Rewrite Wizard generates prompts sent to various LLM providers (OpenAI, Anthropic, Google, Ollama) to rewrite viral Instagram/TikTok scripts. The prompt is built in layers:

1. **Base Template** - Core instructions + original transcript
2. **User Context** - Optional wizard/quick mode inputs
3. **Final Assembly** - Combined prompt sent to API

---

## File Locations

| Component | File | Lines |
|-----------|------|-------|
| Base Prompt Template | `app.py` | 74-85 |
| Prompt Assembly | `app.py` | 2151-2156 |
| API Endpoint | `app.py` | 2119-2189 |
| Wizard Context Builder (JS) | `static/js/app.js` | ~1758-1827 |

---

## Base Prompt Template

**Location:** `app.py:74-85`

```python
UNIVERSAL_PROMPT_TEMPLATE = """Rewrite this viral Instagram reel script.

CRITICAL RULES - FOLLOW EXACTLY:
1. Output ONLY the script text - no introductions, explanations, headers, or commentary
2. Do NOT say "Here's your script", "Sure!", "Great!", or any preamble - start directly with the script
3. Keep it SHORT: 30-60 seconds spoken (75-150 words max)
4. Match the original's hook pattern and pacing but make content unique
5. Start your response with the first word of the script, nothing else

ORIGINAL ({views:,} views):
{transcript}
"""
```

### Template Variables

| Variable | Source | Description |
|----------|--------|-------------|
| `{views:,}` | `reel.get('views', 0)` | View count (comma formatted) |
| `{transcript}` | `reel.get('transcript')` or `reel.get('caption')` | Original script text |

---

## User Context (Wizard Mode)

When user fills out the wizard, context is built in JavaScript and sent to the API.

**Location:** `static/js/app.js` - `buildContextFromWizard()` function

### Wizard Steps & Fields

| Step | Field | Element ID | Description |
|------|-------|------------|-------------|
| 0 | Provider/Model | `rewriteProvider`, `rewriteModel` | AI provider selection |
| 1 | Niche | `wizardNiche` | Topic/industry |
| 2 | Voice | `wizardVoice` | Tone (buttons + custom input) |
| 3 | Angle | `wizardAngle` | Unique spin/perspective |
| 4 | Product | `wizardProduct` | Main focus/offering |
| 5 | Setup | `wizardSetup` | Key details to include |
| 6 | CTA | `wizardCta` | Call-to-action (buttons + custom) |
| 7 | Time | Time buttons | Target length |

### Context Format (sent to API)

```
NICHE: {niche}
TONE: {voice}
ANGLE: {angle}
PROMOTING: {product}
KEY DETAILS: {setup}
CTA: {cta}
LENGTH: {time}
```

---

## Final Prompt Assembly

**Location:** `app.py:2151-2156`

```python
# Build prompt
base_prompt = generate_ai_prompt(reel)
if user_context:
    full_prompt = f"{base_prompt}\nMY CONTEXT (adapt script for this):\n{user_context}\n\nRemember: Output ONLY the script, no preamble."
else:
    full_prompt = base_prompt
```

### Full Prompt Structure (with context)

```
Rewrite this viral Instagram reel script.

CRITICAL RULES - FOLLOW EXACTLY:
1. Output ONLY the script text - no introductions, explanations, headers, or commentary
2. Do NOT say "Here's your script", "Sure!", "Great!", or any preamble - start directly with the script
3. Keep it SHORT: 30-60 seconds spoken (75-150 words max)
4. Match the original's hook pattern and pacing but make content unique
5. Start your response with the first word of the script, nothing else

ORIGINAL (125,000 views):
[Original transcript here...]

MY CONTEXT (adapt script for this):
NICHE: AI automation
TONE: Passionate & Tactical
ANGLE: Free tool, no subscriptions
PROMOTING: Instagram scraper for content creators
KEY DETAILS: - Scrapes top reels, - Gets transcripts, - Analyzes patterns
CTA: Comment FIRE for the link
LENGTH: Under 60 seconds

Remember: Output ONLY the script, no preamble.
```

---

## Quick Mode

Quick mode skips the wizard and allows freeform context input.

**Location:** `static/js/app.js` - `generateQuickRewrite()` function

- Uses `#quickContext` textarea for freeform input
- Same API endpoint, same prompt assembly
- User writes their own context format

---

## API Flow

```
┌─────────────────┐
│  Wizard/Quick   │
│  (Frontend JS)  │
└────────┬────────┘
         │ POST /api/rewrite
         │ {scrape_id, shortcode, context, provider, model}
         ▼
┌─────────────────┐
│  rewrite_script │
│  (app.py)       │
├─────────────────┤
│ 1. Load history │
│ 2. Find reel    │
│ 3. Build prompt │
│ 4. Call LLM     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LLM Provider   │
│  (OpenAI, etc.) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Response       │
│  (script only)  │
└─────────────────┘
```

---

## Provider-Specific Handling

| Provider | Function | Model Default |
|----------|----------|---------------|
| Ollama | `call_ollama()` | User-selected |
| OpenAI | `call_openai()` | `gpt-4o-mini` |
| Anthropic | `call_anthropic()` | `claude-3-5-haiku-20241022` |
| Google | `call_google()` | `gemini-1.5-flash` |

All providers receive the same prompt. Response is processed through `strip_thinking_output()` to remove `<think>` tags from reasoning models.

---

## Potential Improvements

### Current Limitations
- [ ] No system prompt - everything in user message
- [ ] No few-shot examples
- [ ] No hook type analysis passed to LLM
- [ ] No engagement metrics context (likes, comments)
- [ ] Word count not enforced programmatically
- [ ] No platform-specific adaptations (IG vs TikTok)

### Enhancement Ideas
- Add system prompt for role/persona
- Include hook pattern classification from skeleton data
- Add few-shot examples of good rewrites
- Include engagement ratio context
- Add platform-specific instructions
- Temperature/creativity controls
- Multiple output variations option

---

## Testing Prompts

To test prompt changes without the full UI:

```bash
curl -X POST http://localhost:5000/api/rewrite \
  -H "Content-Type: application/json" \
  -d '{
    "scrape_id": "YOUR_SCRAPE_ID",
    "shortcode": "REEL_SHORTCODE",
    "context": "NICHE: test\nTONE: casual",
    "provider": "openai",
    "model": "gpt-4o-mini"
  }'
```

---

*Last updated: 2026-01-04*
