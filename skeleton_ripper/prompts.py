"""
Prompt templates for the Content Skeleton Ripper feature.

Contains:
- SKELETON_EXTRACT_BATCH_PROMPT: Extract content skeletons from 3-5 transcripts per call
- SKELETON_SYNTHESIS_SYSTEM_PROMPT: Full content strategy prompt for pattern synthesis
- SKELETON_SYNTHESIS_USER_PROMPT: User prompt template for synthesis stage
"""

# =============================================================================
# STAGE 1: BATCHED EXTRACTION PROMPT
# =============================================================================

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


def format_batch_transcripts(transcripts: list[dict]) -> str:
    """
    Format a batch of transcripts for the extraction prompt.

    Args:
        transcripts: List of dicts with 'video_id', 'views', 'transcript' keys

    Returns:
        Formatted string for insertion into prompt
    """
    formatted = []
    for t in transcripts:
        views_str = f"{t.get('views', 0):,}" if t.get('views') else 'N/A'
        formatted.append(
            f"### VIDEO: {t['video_id']} ({views_str} views)\n{t['transcript']}"
        )
    return "\n\n".join(formatted)


def get_extraction_prompt(transcripts: list[dict]) -> str:
    """
    Get the full extraction prompt with transcripts inserted.

    Args:
        transcripts: List of transcript dicts (3-5 recommended)

    Returns:
        Complete prompt ready for LLM
    """
    batch_text = format_batch_transcripts(transcripts)
    return SKELETON_EXTRACT_BATCH_PROMPT.format(batch_transcripts=batch_text)


# =============================================================================
# STAGE 3: SYNTHESIS PROMPTS
# =============================================================================

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


def format_creator_summary(skeletons: list[dict]) -> str:
    """
    Generate a summary of creators analyzed.

    Args:
        skeletons: List of extracted skeleton dicts

    Returns:
        Formatted creator summary string
    """
    # Group by creator
    creators = {}
    for s in skeletons:
        username = s.get('creator_username', 'unknown')
        if username not in creators:
            creators[username] = {
                'count': 0,
                'total_views': 0,
                'platform': s.get('platform', 'unknown')
            }
        creators[username]['count'] += 1
        creators[username]['total_views'] += s.get('views', 0)

    # Format summary
    lines = []
    for username, data in creators.items():
        avg_views = data['total_views'] // data['count'] if data['count'] > 0 else 0
        lines.append(
            f"- **@{username}** ({data['platform']}): "
            f"{data['count']} videos, {avg_views:,} avg views"
        )

    return "\n".join(lines)


def get_synthesis_prompts(skeletons: list[dict]) -> tuple[str, str]:
    """
    Get the system and user prompts for synthesis.

    Args:
        skeletons: List of extracted skeleton dicts

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    import json

    # Count unique creators
    creators = set(s.get('creator_username', 'unknown') for s in skeletons)

    user_prompt = SKELETON_SYNTHESIS_USER_PROMPT.format(
        skeleton_count=len(skeletons),
        creator_count=len(creators),
        creator_summary=format_creator_summary(skeletons),
        skeletons_json=json.dumps(skeletons, indent=2)
    )

    return SKELETON_SYNTHESIS_SYSTEM_PROMPT, user_prompt


# =============================================================================
# VALIDATION
# =============================================================================

REQUIRED_SKELETON_FIELDS = [
    'video_id',
    'hook',
    'hook_technique',
    'value',
    'value_structure',
    'cta',
    'cta_type'
]

VALID_HOOK_TECHNIQUES = {'curiosity', 'contrast', 'result', 'question', 'story', 'shock'}
VALID_VALUE_STRUCTURES = {'steps', 'single_insight', 'framework', 'story', 'listicle', 'transformation'}
VALID_CTA_TYPES = {'follow', 'comment', 'share', 'link', 'none'}


def validate_skeleton(skeleton: dict) -> tuple[bool, str]:
    """
    Validate an extracted skeleton has all required fields.

    Args:
        skeleton: Extracted skeleton dict

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check required fields
    for field in REQUIRED_SKELETON_FIELDS:
        if field not in skeleton:
            return False, f"Missing required field: {field}"
        if not skeleton[field]:
            return False, f"Empty required field: {field}"

    # Validate enum fields
    if skeleton.get('hook_technique') not in VALID_HOOK_TECHNIQUES:
        return False, f"Invalid hook_technique: {skeleton.get('hook_technique')}"

    if skeleton.get('value_structure') not in VALID_VALUE_STRUCTURES:
        return False, f"Invalid value_structure: {skeleton.get('value_structure')}"

    if skeleton.get('cta_type') not in VALID_CTA_TYPES:
        return False, f"Invalid cta_type: {skeleton.get('cta_type')}"

    return True, ""
