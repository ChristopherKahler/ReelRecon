"""
Pattern synthesizer for Content Skeleton Ripper.

Stage 3 of the pipeline: Uses full content strategy prompt to analyze
patterns across all extracted skeletons and generate actionable templates.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .llm_client import LLMClient
from .prompts import get_synthesis_prompts
from .aggregator import AggregatedData, format_aggregation_summary
from utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class SynthesisResult:
    """Result from pattern synthesis."""
    success: bool
    analysis: str = ""  # Raw markdown analysis from LLM
    templates: list[dict] = field(default_factory=list)  # Parsed templates if extractable
    quick_wins: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: Optional[str] = None

    # Metadata
    model_used: str = ""
    tokens_used: int = 0  # If available
    synthesized_at: str = ""


# =============================================================================
# SYNTHESIZER
# =============================================================================

class PatternSynthesizer:
    """
    Synthesizes content patterns from aggregated skeleton data.

    Uses the full content strategy assistant prompt to:
    - Identify hook/value/CTA patterns across creators
    - Generate actionable template frameworks
    - Provide quick wins and warnings

    Usage:
        synthesizer = PatternSynthesizer(llm_client)
        result = synthesizer.synthesize(aggregated_data)
    """

    def __init__(self, llm_client: LLMClient, timeout: int = 180):
        """
        Initialize pattern synthesizer.

        Args:
            llm_client: Configured LLM client
            timeout: Request timeout (synthesis can take longer)
        """
        self.llm_client = llm_client
        self.timeout = timeout

        logger.info(f"PatternSynthesizer initialized with {llm_client.provider}/{llm_client.model}")

    def synthesize(
        self,
        data: AggregatedData,
        retry_on_failure: bool = True
    ) -> SynthesisResult:
        """
        Synthesize patterns from aggregated skeleton data.

        Args:
            data: Aggregated skeleton data from Stage 2
            retry_on_failure: Whether to retry once on failure

        Returns:
            SynthesisResult with analysis and templates
        """
        if not data.skeletons:
            logger.warning("No skeletons to synthesize")
            return SynthesisResult(
                success=False,
                error="No skeleton data to synthesize"
            )

        logger.info(f"Synthesizing patterns from {len(data.skeletons)} skeletons")

        try:
            # Get prompts
            system_prompt, user_prompt = get_synthesis_prompts(data.skeletons)

            # Call LLM
            response = self.llm_client.chat(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.7  # Allow some creativity in synthesis
            )

            # Parse response
            result = self._parse_synthesis_response(response)
            result.model_used = f"{self.llm_client.provider}/{self.llm_client.model}"
            result.synthesized_at = datetime.utcnow().isoformat()

            logger.info("Synthesis complete")
            return result

        except Exception as e:
            logger.error(f"Synthesis failed: {e}")

            if retry_on_failure:
                logger.info("Retrying synthesis...")
                try:
                    # Retry with increased timeout
                    original_timeout = self.llm_client.timeout
                    self.llm_client.timeout = self.timeout + 60

                    system_prompt, user_prompt = get_synthesis_prompts(data.skeletons)
                    response = self.llm_client.chat(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        temperature=0.7
                    )

                    self.llm_client.timeout = original_timeout

                    result = self._parse_synthesis_response(response)
                    result.model_used = f"{self.llm_client.provider}/{self.llm_client.model}"
                    result.synthesized_at = datetime.utcnow().isoformat()

                    logger.info("Synthesis succeeded on retry")
                    return result

                except Exception as retry_error:
                    logger.error(f"Synthesis retry failed: {retry_error}")

            return SynthesisResult(
                success=False,
                error=str(e)
            )

    def _parse_synthesis_response(self, response: str) -> SynthesisResult:
        """
        Parse the synthesis response.

        The response is expected to be markdown with structured sections.
        We store the raw markdown and attempt to extract structured data.

        Args:
            response: Raw LLM response

        Returns:
            Parsed SynthesisResult
        """
        result = SynthesisResult(
            success=True,
            analysis=response.strip()
        )

        # Try to extract structured sections
        result.templates = self._extract_templates(response)
        result.quick_wins = self._extract_section_items(response, "Quick Wins")
        result.warnings = self._extract_section_items(response, "Warnings")

        return result

    def _extract_templates(self, text: str) -> list[dict]:
        """
        Extract template frameworks from response.

        Looks for patterns like:
        ## Template 1: Name
        **Hook:** ...
        **Visual:** ...
        **Value:** ...
        **CTA:** ...

        Args:
            text: Response text

        Returns:
            List of template dicts
        """
        templates = []
        lines = text.split('\n')

        current_template = None
        for line in lines:
            line = line.strip()

            # Check for template header
            if line.startswith('## Template') or line.startswith('### Template'):
                if current_template:
                    templates.append(current_template)

                # Extract template name
                name = line.split(':', 1)[-1].strip() if ':' in line else line
                current_template = {'name': name, 'components': {}}

            elif current_template and line.startswith('**') and ':**' in line:
                # Extract component
                parts = line.split(':**', 1)
                key = parts[0].replace('**', '').strip().lower()
                value = parts[1].strip() if len(parts) > 1 else ''
                current_template['components'][key] = value

        # Don't forget the last template
        if current_template:
            templates.append(current_template)

        return templates

    def _extract_section_items(self, text: str, section_name: str) -> list[str]:
        """
        Extract bullet items from a named section.

        Args:
            text: Response text
            section_name: Section header to find (e.g., "Quick Wins")

        Returns:
            List of bullet items
        """
        items = []
        lines = text.split('\n')

        in_section = False
        for line in lines:
            stripped = line.strip()

            # Check for section header
            if section_name.lower() in stripped.lower() and stripped.startswith('#'):
                in_section = True
                continue

            # Check for next section
            if in_section and stripped.startswith('#'):
                break

            # Extract bullet items
            if in_section and (stripped.startswith('-') or stripped.startswith('*')):
                item = stripped[1:].strip()
                if item:
                    items.append(item)

        return items


# =============================================================================
# REPORT GENERATION
# =============================================================================

def generate_report(
    data: AggregatedData,
    synthesis: SynthesisResult,
    job_config: Optional[dict] = None
) -> str:
    """
    Generate the final markdown report.

    Args:
        data: Aggregated skeleton data
        synthesis: Synthesis result
        job_config: Optional job configuration

    Returns:
        Complete markdown report
    """
    lines = [
        "# Content Skeleton Analysis Report",
        "",
        f"*Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*",
        "",
    ]

    # Job info
    if job_config:
        lines.extend([
            "## Analysis Configuration",
            f"- **Creators analyzed:** {', '.join(job_config.get('usernames', []))}",
            f"- **Platform:** {job_config.get('platform', 'N/A')}",
            f"- **Videos per creator:** {job_config.get('videos_per_creator', 'N/A')}",
            f"- **LLM:** {synthesis.model_used}",
            "",
        ])

    # Summary stats
    lines.extend([
        "## Summary",
        f"- **Total videos analyzed:** {data.total_videos}",
        f"- **Total views:** {data.total_views:,}",
        f"- **Average hook length:** {data.avg_hook_word_count:.1f} words",
        f"- **Average video length:** {data.avg_duration_seconds:.0f} seconds",
        "",
    ])

    # Main analysis
    lines.extend([
        "---",
        "",
        synthesis.analysis,
        "",
    ])

    # Extracted skeletons reference
    lines.extend([
        "---",
        "",
        "## Raw Skeletons Data",
        "",
        "See `skeletons.json` for full extracted skeleton data.",
        "",
    ])

    return "\n".join(lines)
