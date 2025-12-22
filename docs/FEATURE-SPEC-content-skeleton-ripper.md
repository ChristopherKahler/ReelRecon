# Feature Specification: Content Skeleton Ripper

> **Branch:** `develop`
> **Priority:** High
> **Status:** Ready for Implementation
> **Created:** 2025-12-22
> **Last Updated:** 2025-12-22

---

## Executive Summary

The Content Skeleton Ripper is a new feature for ReelRecon v2 that automates the extraction and synthesis of content patterns from top-performing Instagram/TikTok videos. Users input up to 5 creator usernames, the system scrapes their top N videos, extracts transcripts, analyzes content structure (hook/value/CTA), and synthesizes actionable content templates.

**Business Context:** This feature directly supports the content modeling workflow where creators analyze successful accounts to build their own content strategy. Currently this is a manual process using external ChatGPT prompts—we're bringing it in-app with cost optimization.

---

## User Story

As a content creator using ReelRecon, I want to analyze the content patterns of up to 5 successful creators so that I can build data-driven content templates for my own strategy.

**Workflow:**
1. Enter 1-5 Instagram/TikTok usernames
2. Configure videos per creator (default: 3, max: 5)
3. **Select LLM provider and model** for extraction/synthesis
4. System scrapes, sorts by engagement, downloads top N per creator
5. System transcribes videos (validates real speech exists)
6. System extracts content skeleton from each transcript (batched)
7. System synthesizes patterns across all skeletons
8. User receives structured Content Skeleton Report

---

## Architecture Decision: Staged Pipeline

### Why Staged vs Monolithic

| Approach | Token Cost (15 videos) | Latency | Quality |
|----------|------------------------|---------|---------|
| Full prompt × 15 calls | ~45,000 tokens | Slow | Overkill for extraction |
| One massive call | ~15,000 tokens | Fast | Context limits, less structured |
| **Staged pipeline (batched)** | ~12,000 tokens | Optimal | Best of both |

**Decision:** Staged pipeline with batched extraction (3-5 per call) + full synthesis prompt.

### Pipeline Stages

```
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 0: CACHE CHECK                                           │
│  - Check transcript cache for each video                        │
│  - Skip download/transcription for cached transcripts           │
│  - Always re-scrape profile for fresh engagement stats          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 1: EXTRACTION (BATCHED)                                  │
│  - Batch 3-5 transcripts per LLM call                           │
│  - Prompt (~400 tokens) + batch response                        │
│  - Output: Array of structured JSON skeletons                   │
│  - Smart retry: Remove failing transcript, retry batch          │
│  - Validates: Skip if no real transcript                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 2: AGGREGATION                                           │
│  - Collect all extraction results                               │
│  - No LLM call (pure data transformation)                       │
│  - Group by creator, calculate averages                         │
│  - Prepare synthesis input                                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 3: SYNTHESIS                                             │
│  - Single LLM call with full context prompt                     │
│  - Full content strategy prompt (~2,800 tokens)                 │
│  - Pattern recognition across all skeletons                     │
│  - Output: Templates + recommendations                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 4: OUTPUT                                                │
│  - No LLM (templated rendering)                                 │
│  - Generate markdown report                                     │
│  - Save to output directory                                     │
│  - Display in UI                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## LLM Provider Configuration

### Provider Selection at Job Start

Users select the LLM provider and model when starting a skeleton ripper job. Only providers with valid API keys configured in global settings are shown.

**Supported Providers:**

| Provider | Models | Notes |
|----------|--------|-------|
| **Local (Ollama)** | llama3, llama3.1, mistral, mixtral, phi3, etc. | Free, requires local setup |
| **OpenAI** | gpt-4o-mini (recommended), gpt-4o, gpt-4-turbo | Best balance of cost/quality |
| **Anthropic** | claude-3-haiku, claude-3-sonnet, claude-3-opus | High quality, higher cost |
| **Google** | gemini-1.5-flash, gemini-1.5-pro | Good alternative |

**UI Dropdown:**
```
┌─────────────────────────────────────────┐
│ LLM Provider                            │
│ ┌─────────────────────────────────────┐ │
│ │ ▼ OpenAI                            │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ Model                                   │
│ ┌─────────────────────────────────────┐ │
│ │ ▼ gpt-4o-mini (Recommended)         │ │
│ │   gpt-4o                            │ │
│ │   gpt-4-turbo                       │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

**Backend:** Provider and model passed to job config. Pipeline uses selected provider for both extraction and synthesis stages.

---

## Transcript Caching Strategy

### What Gets Cached vs Fresh

| Data | Cache? | Reason |
|------|--------|--------|
| Downloaded video files | ✅ Yes | Video content doesn't change |
| Transcripts (validated) | ✅ Yes | Speech content doesn't change |
| Video list / ranking | ❌ No | Top videos change over time |
| View/like/comment counts | ❌ No | Engagement stats change frequently |
| Profile metadata | ❌ No | Could become stale |

### Cache Implementation

**Cache Location:**
```
/mnt/c/Users/Chris/Documents/ReelRecon/
└── cache/
    └── transcripts/
        └── {platform}_{username}_{video_id}.txt
```

**Cache Key Format:** `{platform}_{username}_{video_id}_transcript.txt`

**Cache Logic:**
```python
def get_transcript(video):
    cache_path = get_cache_path(video)

    # Check cache first
    if cache_path.exists():
        logger.info(f"Cache hit: {video.video_id}")
        return cache_path.read_text()

    # Cache miss - download and transcribe
    logger.info(f"Cache miss: {video.video_id} - downloading...")
    video_file = download_video(video)
    transcript = transcribe_video(video_file)

    # Validate before caching
    if is_valid_transcript(transcript):
        cache_path.write_text(transcript)
        logger.info(f"Cached transcript: {video.video_id}")

    return transcript
```

**Benefits:**
- Repeated analysis of same creators is instant for transcription phase
- Only engagement stats refresh (always re-scraped)
- Reduces API costs for transcription (OpenAI Whisper or local)

---

## Batched Extraction Strategy

### Batch Configuration

- **Batch size:** 3-5 transcripts per LLM call
- **Benefits:** 3 API round-trips instead of 15 = faster execution
- **Token cost:** Same total tokens, just fewer HTTP requests

### Batched Extraction Prompt

```python
SKELETON_EXTRACT_BATCH_PROMPT = """Extract the content skeleton from each of these viral video transcripts.

Analyze each transcript's structure and return a JSON array. Each object should have this structure:

{
  "video_id": "the_video_id",
  "hook": "The first 1-2 sentences that grab attention (verbatim or close paraphrase)",
  "hook_technique": "curiosity|contrast|result|question|story|shock",
  "hook_word_count": 0,
  "value": "The main teaching, insight, or value delivery (2-4 sentence summary)",
  "value_structure": "steps|single_insight|framework|story|listicle|transformation",
  "value_points": ["point 1", "point 2"],
  "cta": "The call to action or closing statement (verbatim)",
  "cta_type": "follow|comment|share|link|none",
  "total_word_count": 0,
  "estimated_duration_seconds": 0
}

Return ONLY a valid JSON array (no markdown, no explanation).

---

TRANSCRIPTS TO ANALYZE:

{batch_transcripts}
"""
```

**Batch Input Format:**
```
### VIDEO: abc123 ({views:,} views)
{transcript_1}

### VIDEO: def456 ({views:,} views)
{transcript_2}

### VIDEO: ghi789 ({views:,} views)
{transcript_3}
```

### Smart Retry Logic

When a batch fails to parse (JSON error), use this recovery strategy:

```python
def extract_batch_with_retry(transcripts, max_retries=2):
    """
    Attempt batch extraction with smart retry on parse failure.
    If batch fails, identify problematic transcript and retry without it.
    """
    attempt = 0
    current_batch = transcripts.copy()
    results = []
    failed_transcripts = []

    while current_batch and attempt < max_retries:
        try:
            response = call_llm(format_batch_prompt(current_batch))
            parsed = json.loads(response)

            # Validate each result
            for skeleton in parsed:
                if is_valid_skeleton(skeleton):
                    results.append(skeleton)
                else:
                    # Individual skeleton invalid - find and remove
                    failed_id = skeleton.get('video_id')
                    failed_transcripts.append(failed_id)
                    current_batch = [t for t in current_batch if t['video_id'] != failed_id]

            # All valid - done
            if len(results) == len(transcripts):
                break

        except json.JSONDecodeError as e:
            attempt += 1
            logger.warning(f"Batch parse failed (attempt {attempt}), splitting batch...")

            # On parse failure, split batch and retry smaller groups
            if len(current_batch) > 1:
                mid = len(current_batch) // 2
                # Retry first half, then second half
                results.extend(extract_batch_with_retry(current_batch[:mid], max_retries=1))
                results.extend(extract_batch_with_retry(current_batch[mid:], max_retries=1))
                break
            else:
                # Single transcript failed - mark and skip
                failed_transcripts.append(current_batch[0]['video_id'])
                break

    return results, failed_transcripts
```

---

## Prompt Specifications

### Stage 1: Extraction Prompt (Batched)

**Purpose:** Extract structured content skeletons from 3-5 transcripts in a single call.
**Token budget:** ~400 tokens (prompt) + ~600 tokens per transcript
**Output:** JSON array

See **Batched Extraction Prompt** section above.

**Validation rules:**
- Skip videos with no transcript or transcript < 10 words
- Skip videos where transcript is clearly auto-generated garbage
- Require at least 60% of target videos to have valid skeletons to proceed to synthesis

---

### Stage 3: Synthesis Prompt

**Purpose:** Analyze patterns across all extracted skeletons and generate templates.
**Token budget:** ~2,800 tokens (system) + ~3,000 tokens (input data)
**Output:** Structured analysis + templates

**Note:** Uses the full Content Strategy Assistant v2 prompt from `content-strategy-assistant-v2.md` with modifications for batch analysis context.

```python
SKELETON_SYNTHESIS_SYSTEM_PROMPT = """You are an elite content strategist specializing in viral short-form video content. You combine deep platform understanding with content psychology to help creators build data-driven content strategies.

## Core Principles

1. **Visual-first thinking** - If we can't show something compelling on screen, the idea is weak. Always start with "what stops the scroll?"
2. **Contrast creates curiosity** - The gap between common belief (A) and surprising truth (B) is your primary tool. Bigger gap = stronger hook.
3. **Niche precision over broad appeal** - "n8n users who struggle with error handling" beats "people who want to automate things"
4. **Evidence over intuition** - Every claim needs proof potential. If we say it, we must be able to show it.
5. **Authenticity compounds** - Real results, real mistakes, real language. Polish kills relatability.

## Analysis Framework

When analyzing content skeletons, identify:

### Hook Patterns
- What techniques dominate? (curiosity, contrast, result, question, story, shock)
- What's the average word count for hooks?
- Are there specific phrase patterns that repeat?

### Value Delivery Patterns
- How is information structured? (steps, single insight, framework, story)
- What's the typical number of points covered?
- How do successful creators balance depth vs brevity?

### CTA Patterns
- What call-to-action types perform best?
- How do CTAs connect to the content?
- What creates action vs passive consumption?

### Cross-Creator Insights
- What patterns appear across multiple creators?
- What differentiates highest performers?
- What's unique vs universal?

## Hook Structure Framework

```
Context Lean-in → Interjection → Snapback

Example:
"If you're building n8n workflows..." (context)
"...you're probably making the same mistake I made for 6 months" (interjection)
"Here's the one node pattern that fixes 90% of errors" (snapback)
```

## Hook Quality Gates

Every hook must pass these checks:
- [ ] Context in first 1-2 seconds (no delay)
- [ ] 6th-grade reading level (no confusion)
- [ ] Direct connection to viewer pain (no irrelevance)
- [ ] Strong contrast creating curiosity gap (no disinterest)
- [ ] Under 10 words for the core hook

## Title Formulas

Use these as starting points:
- `How I [specific result] by [unexpected method]`
- `Why [thing] [fails/works] (And What Actually [Works/Fails])`
- `The [#] [Thing] That [Specific Result]`
- `[Surprising truth] about [common topic]`
- `Stop [common action]. Do [contrarian action] instead.`

## Contrast Formula

```
Common Belief A: What most people think/do
         ↓
    [GAP = CURIOSITY]
         ↓
Contrarian Take B: The surprising truth/better way
```

The bigger the gap between A and B, the stronger the hook.

## Output Requirements

Your synthesis must include:
1. **Pattern Analysis** - What you found across the skeletons with specific examples
2. **Template Frameworks** - 3 actionable templates the user can adapt immediately
3. **Quick Wins** - Immediate improvements based on patterns observed
4. **Warnings** - Common mistakes to avoid based on what works

Be specific. Use examples from the actual skeletons. Quantify when possible."""

SKELETON_SYNTHESIS_USER_PROMPT = """Analyze these {skeleton_count} content skeletons from {creator_count} top-performing creators.

## Creators Analyzed
{creator_summary}

## All Extracted Skeletons
{skeletons_json}

---

Provide your analysis following the framework in your instructions. Be specific and actionable.
Include 3 template frameworks I can immediately use for my own content."""
```

---

## Data Structures

### Skeleton Model

```python
@dataclass
class ContentSkeleton:
    video_id: str
    creator_username: str
    platform: str  # instagram | tiktok
    views: int
    likes: int
    url: str

    # Extracted fields
    hook: str
    hook_technique: str  # curiosity|contrast|result|question|story|shock
    hook_word_count: int
    value: str
    value_structure: str  # steps|single_insight|framework|story|listicle
    value_points: list[str]
    cta: str
    cta_type: str  # follow|comment|share|link|none
    total_word_count: int
    estimated_duration_seconds: int

    # Metadata
    extracted_at: datetime
    extraction_model: str  # which LLM was used
    from_cache: bool  # was transcript from cache?

@dataclass
class SkeletonRipperJob:
    job_id: str
    status: str  # pending|scraping|transcribing|extracting|synthesizing|complete|failed

    # Input config
    usernames: list[str]
    videos_per_creator: int
    platform: str

    # LLM Configuration
    llm_provider: str  # local|openai|anthropic|google
    llm_model: str     # gpt-4o-mini, claude-3-haiku, etc.

    # Progress tracking
    total_videos_target: int
    videos_scraped: int
    videos_transcribed: int
    transcripts_from_cache: int  # NEW: track cache hits
    videos_with_valid_transcript: int
    skeletons_extracted: int

    # Results
    skeletons: list[ContentSkeleton]
    synthesis_result: dict  # The final analysis
    report_path: str  # Path to saved report

    # Timing
    started_at: datetime
    completed_at: datetime

    # Errors
    errors: list[str]
```

---

## File Structure

```
/mnt/c/Users/Chris/Documents/ReelRecon/
├── app.py                          # Add skeleton ripper routes
├── skeleton_ripper/                # NEW: Feature module
│   ├── __init__.py
│   ├── pipeline.py                 # Main pipeline orchestration
│   ├── extractor.py                # Stage 1: Batched extraction
│   ├── aggregator.py               # Stage 2: Data aggregation
│   ├── synthesizer.py              # Stage 3: Pattern synthesis
│   ├── cache.py                    # NEW: Transcript caching logic
│   ├── llm_client.py               # NEW: Multi-provider LLM client
│   └── prompts.py                  # All prompt templates
├── templates/
│   ├── skeleton_ripper.html        # NEW: UI for the feature
│   └── skeleton_report.html        # NEW: Report display template
├── static/
│   └── js/
│       └── skeleton_ripper.js      # NEW: Frontend JS
├── cache/                          # NEW: Cache directory
│   └── transcripts/                # Cached transcripts
│       └── {platform}_{username}_{video_id}.txt
└── output/
    └── skeleton_reports/           # Generated reports directory
        └── {timestamp}_{job_id}/
            ├── report.md           # Human-readable report
            ├── skeletons.json      # Raw extracted data
            └── synthesis.json      # Raw synthesis output
```

---

## API Endpoints

### Start Skeleton Ripper Job

```
POST /api/skeleton-ripper/start
```

**Request:**
```json
{
  "usernames": ["creator1", "creator2", "creator3"],
  "videos_per_creator": 3,
  "platform": "instagram",
  "llm_provider": "openai",
  "llm_model": "gpt-4o-mini",
  "min_valid_transcripts": 10
}
```

**Response:**
```json
{
  "job_id": "sr_abc123",
  "status": "pending",
  "message": "Skeleton ripper job queued"
}
```

### Get Available LLM Providers

```
GET /api/skeleton-ripper/providers
```

**Response:**
```json
{
  "providers": [
    {
      "id": "openai",
      "name": "OpenAI",
      "available": true,
      "models": [
        {"id": "gpt-4o-mini", "name": "GPT-4o Mini (Recommended)", "cost_tier": "low"},
        {"id": "gpt-4o", "name": "GPT-4o", "cost_tier": "medium"},
        {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "cost_tier": "high"}
      ]
    },
    {
      "id": "anthropic",
      "name": "Anthropic",
      "available": true,
      "models": [
        {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku", "cost_tier": "low"},
        {"id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet", "cost_tier": "medium"}
      ]
    },
    {
      "id": "google",
      "name": "Google",
      "available": false,
      "models": []
    },
    {
      "id": "local",
      "name": "Local (Ollama)",
      "available": true,
      "models": [
        {"id": "llama3", "name": "Llama 3", "cost_tier": "free"},
        {"id": "mistral", "name": "Mistral", "cost_tier": "free"}
      ]
    }
  ]
}
```

### Get Job Status

```
GET /api/skeleton-ripper/status/{job_id}
```

**Response:**
```json
{
  "job_id": "sr_abc123",
  "status": "extracting",
  "llm_provider": "openai",
  "llm_model": "gpt-4o-mini",
  "progress": {
    "phase": "extracting",
    "videos_scraped": 15,
    "videos_transcribed": 15,
    "transcripts_from_cache": 8,
    "valid_transcripts": 12,
    "skeletons_extracted": 8,
    "total_target": 15
  },
  "errors": []
}
```

### Get Completed Report

```
GET /api/skeleton-ripper/report/{job_id}
```

**Response:** Returns the generated markdown report or JSON data.

---

## UI Requirements

### Skeleton Ripper Page (`/skeleton-ripper`)

**Input Section:**
- Username input fields (1-5, add/remove buttons)
- Videos per creator slider (1-5, default 3)
- Platform toggle (Instagram / TikTok)
- **LLM Provider dropdown** (populated from `/api/skeleton-ripper/providers`)
- **Model dropdown** (updates based on selected provider)
- "Start Analysis" button

**Progress Section:**
- Phase indicator (Scraping → Transcribing → Extracting → Synthesizing)
- Progress bars for each phase
- **Cache hit indicator** (e.g., "8/15 transcripts loaded from cache")
- Real-time status updates via SSE or polling
- Error display if any videos fail

**Results Section:**
- Rendered markdown report
- Download buttons (Markdown, JSON)
- Expand/collapse for detailed skeleton data
- Copy-to-clipboard for templates

---

## Validation Rules

### Input Validation
- 1-5 usernames required
- 1-5 videos per creator
- Platform must be `instagram` or `tiktok`
- Usernames must not be empty or whitespace
- LLM provider must be configured with valid API key (or local)

### Transcript Validation
- Minimum 10 words to be considered valid
- Detect and skip auto-generated garbage (common patterns)
- Require at least 60% of target videos to have valid transcripts
- If < 60% valid, warn user but allow proceeding

### Extraction Validation
- JSON must parse successfully
- All required fields must be present
- Hook/value/CTA must not be empty strings
- Batch retry with problematic transcript removed on parse failure

---

## Error Handling

| Error | Recovery |
|-------|----------|
| Scrape fails for username | Log error, continue with remaining usernames |
| Transcript unavailable | Mark as skipped, continue with valid videos |
| **Batch extraction parse error** | Remove problematic transcript, retry batch |
| **Single extraction fails** | Mark as failed after retry, continue with others |
| Synthesis fails | Retry 1x with increased timeout |
| < 60% valid transcripts | Warn user, offer to proceed or abort |
| LLM provider unavailable | Show error, user must select different provider |

---

## Cost Estimation

**Per skeleton ripper job (15 videos, 5 creators × 3) with batching:**

| Stage | Calls | Tokens/Call | Total Tokens |
|-------|-------|-------------|--------------|
| Extraction (batched) | 3-5 | ~2,000 (prompt+response) | 8,000 |
| Synthesis | 1 | ~6,000 (prompt+response) | 6,000 |
| **Total** | 4-6 | — | **~14,000** |

**Estimated cost (GPT-4o-mini):**
- Input: ~10,000 tokens × $0.15/1M = $0.0015
- Output: ~4,000 tokens × $0.60/1M = $0.0024
- **Total: ~$0.004 per job** (less than 1 cent)

**Estimated cost (GPT-4o):**
- Input: ~10,000 tokens × $2.50/1M = $0.025
- Output: ~4,000 tokens × $10/1M = $0.04
- **Total: ~$0.065 per job** (~7 cents)

**Estimated cost (Claude 3 Haiku):**
- Input: ~10,000 tokens × $0.25/1M = $0.0025
- Output: ~4,000 tokens × $1.25/1M = $0.005
- **Total: ~$0.0075 per job** (less than 1 cent)

---

## Implementation Sequence

### Phase 1: Core Pipeline
1. Create `skeleton_ripper/` module structure
2. Implement `llm_client.py` with multi-provider support
3. Implement `cache.py` with transcript caching logic
4. Implement `prompts.py` with batched extraction and synthesis prompts
5. Implement `extractor.py` with batched Stage 1 logic + smart retry
6. Implement `aggregator.py` with Stage 2 data transformation
7. Implement `synthesizer.py` with Stage 3 logic
8. Implement `pipeline.py` orchestrating all stages

### Phase 2: Integration
9. Add Flask routes to `app.py` (including `/providers` endpoint)
10. Create `skeleton_ripper.html` UI template with provider selection
11. Add progress tracking via SSE or polling
12. Create `skeleton_report.html` for results display

### Phase 3: Polish
13. Add download functionality (MD, JSON)
14. Add cache statistics display in UI
15. Add input validation with user feedback
16. Test with real creator data across all providers

---

## Testing Checklist

- [ ] Single creator, 3 videos works end-to-end
- [ ] 5 creators, 3 videos each works
- [ ] Handles username that doesn't exist
- [ ] Handles videos with no transcript
- [ ] Handles < 60% valid transcripts (warning flow)
- [ ] **Batched extraction parses correctly**
- [ ] **Batch retry recovers from parse failures**
- [ ] **Transcript cache works (second run is faster)**
- [ ] **Cache hit count displays in UI**
- [ ] Synthesis generates valid templates
- [ ] Report saves correctly to output directory
- [ ] UI progress updates in real-time
- [ ] Download buttons work (MD, JSON)
- [ ] **LLM provider dropdown shows only configured providers**
- [ ] **Model dropdown updates when provider changes**
- [ ] Works with OpenAI provider
- [ ] Works with Anthropic provider
- [ ] Works with Google provider
- [ ] Works with Local (Ollama) provider

---

## Resolved Design Decisions

| Question | Decision | Rationale |
|----------|----------|-----------|
| Platform scope | Instagram first, add TikTok in v2.1 | Known working, reduce MVP complexity |
| Caching | Cache transcripts only, always re-scrape stats | Transcripts don't change, stats do |
| Comparison mode | Skip for MVP | Good v3 feature, not essential |
| Export formats | Markdown only for MVP | PDF is nice-to-have later |
| Presets | Skip for MVP | Manual curation work, not essential |
| LLM selection | User chooses at job start | Matches existing feature pattern |
| Batching | 3-5 transcripts per call with smart retry | Reduces latency without losing reliability |
| Full prompt | Keep full v2 prompt (~2,800 tokens) | Accept slightly higher cost for quality |

---

## Appendix A: Full Content Strategy System Prompt

The complete system prompt for Stage 3 synthesis is included inline in the Synthesis Prompt section above.

Source reference: `/docs/content-strategy-assistant-v2.md`

The full prompt includes:
- Core principles (5 behavioral guidelines)
- Hook structure framework
- Hook quality gates
- Title formulas
- Contrast formula
- Analysis frameworks
- Output requirements

---

## Appendix B: Example Output

### Sample Extracted Skeleton

```json
{
  "video_id": "abc123",
  "creator_username": "automationguy",
  "platform": "instagram",
  "views": 1240000,
  "likes": 45000,
  "url": "https://instagram.com/reel/abc123",
  "hook": "Stop wasting 4 hours on research. This workflow does it in 4 minutes.",
  "hook_technique": "contrast",
  "hook_word_count": 14,
  "value": "Using n8n's HTTP node with AI, you can scrape, filter, and summarize any public data source automatically.",
  "value_structure": "single_insight",
  "value_points": [
    "HTTP node fetches data",
    "AI node filters and summarizes",
    "Runs on schedule automatically"
  ],
  "cta": "Follow for the full tutorial dropping tomorrow.",
  "cta_type": "follow",
  "total_word_count": 87,
  "estimated_duration_seconds": 35,
  "from_cache": false
}
```

### Sample Batched Extraction Response

```json
[
  {
    "video_id": "abc123",
    "hook": "Stop wasting 4 hours on research...",
    "hook_technique": "contrast",
    ...
  },
  {
    "video_id": "def456",
    "hook": "Everyone's using ChatGPT wrong...",
    "hook_technique": "curiosity",
    ...
  },
  {
    "video_id": "ghi789",
    "hook": "I automated my entire morning routine...",
    "hook_technique": "result",
    ...
  }
]
```

### Sample Synthesis Output (Excerpt)

```markdown
## Pattern Analysis

### Hook Techniques
- **Contrast** dominated (9/15 videos) - "Stop doing X, do Y instead"
- Average hook word count: 12 words
- Specific numbers appeared in 80% of top hooks

### Value Delivery
- **Single insight** most common (7/15)
- Average 3 value points when using lists
- Transformation focus > feature focus

## Template 1: The Contrast Reversal

**Hook:** "Everyone [common action]. I [opposite action]."
**Visual:** Split screen showing both approaches
**Value:** 3 quick points showing your different approach
**CTA:** Question that triggers comments

**Example:** "Everyone manually searches for leads. I let this workflow find 50 qualified leads while I sleep."
```

---

## Development Workflow

### Git Branching Strategy

```
main (v2.0.1-alpha) ──────────────────────────────────────────────►
                          │
                          └── feature/skeleton-ripper ──────────────►
                                    │
                                    ├── Phase 1 commits (core pipeline)
                                    ├── Phase 2 commits (integration)
                                    └── Phase 3 commits (polish)
                                              │
                                              └── PR → develop → main (v2.1.0-alpha)
```

**Workflow:**
1. Create `feature/skeleton-ripper` branch from `main`
2. Develop in phases with atomic commits
3. PR to `develop` for testing
4. Merge `develop` to `main` and tag `v2.1.0-alpha` when ready

---

### Modular Commit Strategy

Each commit should be self-contained and testable:

**Phase 1: Core Pipeline**
```bash
git commit -m "feat(skeleton-ripper): add module structure and prompts"
git commit -m "feat(skeleton-ripper): implement multi-provider LLM client"
git commit -m "feat(skeleton-ripper): implement transcript caching"
git commit -m "feat(skeleton-ripper): implement batched extractor with retry"
git commit -m "feat(skeleton-ripper): implement aggregator"
git commit -m "feat(skeleton-ripper): implement synthesizer"
git commit -m "feat(skeleton-ripper): implement pipeline orchestration"
```

**Phase 2: Integration**
```bash
git commit -m "feat(skeleton-ripper): add Flask routes and API endpoints"
git commit -m "feat(skeleton-ripper): add UI template with provider selection"
git commit -m "feat(skeleton-ripper): add progress tracking via SSE"
```

**Phase 3: Polish**
```bash
git commit -m "feat(skeleton-ripper): add download and export functionality"
git commit -m "fix(skeleton-ripper): handle edge cases in batch retry"
git commit -m "test(skeleton-ripper): add end-to-end tests"
```

---

### Module Isolation

The `skeleton_ripper/` module should be completely self-contained:

```python
# skeleton_ripper/__init__.py
from .pipeline import SkeletonRipperPipeline
from .extractor import BatchedExtractor
from .synthesizer import PatternSynthesizer
from .cache import TranscriptCache
from .llm_client import LLMClient

__all__ = [
    'SkeletonRipperPipeline',
    'BatchedExtractor',
    'PatternSynthesizer',
    'TranscriptCache',
    'LLMClient'
]
```

**Key principle:** The only touchpoint with `app.py` should be route registration:

```python
# app.py - minimal integration
from skeleton_ripper import SkeletonRipperPipeline

@app.route('/api/skeleton-ripper/start', methods=['POST'])
def start_skeleton_ripper():
    pipeline = SkeletonRipperPipeline(config)
    return pipeline.start(request.json)
```

---

### Version Bumping

| Release | Version | When |
|---------|---------|------|
| Current stable | v2.0.1-alpha | Now (main) |
| Skeleton Ripper MVP | v2.1.0-alpha | After feature complete |
| TikTok support added | v2.2.0-alpha | Future |
| Production ready | v2.0.0 | Remove alpha when stable |

---

### Recommended First Steps

```bash
cd /mnt/c/Users/Chris/Documents/ReelRecon

# 1. Create feature branch
git checkout main
git pull origin main
git checkout -b feature/skeleton-ripper

# 2. Create module structure
mkdir -p skeleton_ripper
touch skeleton_ripper/__init__.py
touch skeleton_ripper/pipeline.py
touch skeleton_ripper/extractor.py
touch skeleton_ripper/aggregator.py
touch skeleton_ripper/synthesizer.py
touch skeleton_ripper/cache.py
touch skeleton_ripper/llm_client.py
touch skeleton_ripper/prompts.py

# 3. First commit
git add skeleton_ripper/
git commit -m "feat(skeleton-ripper): initialize module structure"
git push -u origin feature/skeleton-ripper
```

---

*Document prepared for handoff to development session.*
*Last updated: 2025-12-22*
