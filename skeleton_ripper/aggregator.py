"""
Aggregator for Content Skeleton Ripper.

Stage 2 of the pipeline: Pure data transformation (no LLM calls).
Groups extracted skeletons by creator and prepares data for synthesis.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional
from statistics import mean, median

from utils.logger import get_logger

logger = get_logger()


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class CreatorStats:
    """Aggregated statistics for a single creator."""
    username: str
    platform: str
    video_count: int
    total_views: int
    total_likes: int
    avg_views: float
    avg_likes: float

    # Content patterns
    avg_hook_word_count: float
    avg_total_word_count: float
    avg_duration_seconds: float

    # Technique distributions
    hook_techniques: dict[str, int] = field(default_factory=dict)
    value_structures: dict[str, int] = field(default_factory=dict)
    cta_types: dict[str, int] = field(default_factory=dict)


@dataclass
class AggregatedData:
    """Fully aggregated data ready for synthesis."""
    skeletons: list[dict]
    creator_stats: list[CreatorStats]
    total_videos: int
    total_views: int
    valid_skeletons: int

    # Cross-creator patterns
    overall_hook_techniques: dict[str, int] = field(default_factory=dict)
    overall_value_structures: dict[str, int] = field(default_factory=dict)
    overall_cta_types: dict[str, int] = field(default_factory=dict)

    # Averages
    avg_hook_word_count: float = 0.0
    avg_total_word_count: float = 0.0
    avg_duration_seconds: float = 0.0


# =============================================================================
# AGGREGATOR
# =============================================================================

class SkeletonAggregator:
    """
    Aggregates extracted skeletons for synthesis.

    Groups data by creator, calculates statistics, and identifies patterns.

    Usage:
        aggregator = SkeletonAggregator()
        aggregated = aggregator.aggregate(skeletons)
    """

    def aggregate(self, skeletons: list[dict]) -> AggregatedData:
        """
        Aggregate skeleton data for synthesis.

        Args:
            skeletons: List of extracted skeleton dicts

        Returns:
            AggregatedData ready for synthesis stage
        """
        if not skeletons:
            logger.warning("No skeletons to aggregate")
            return AggregatedData(
                skeletons=[],
                creator_stats=[],
                total_videos=0,
                total_views=0,
                valid_skeletons=0
            )

        # Group by creator
        by_creator = self._group_by_creator(skeletons)

        # Calculate per-creator stats
        creator_stats = [
            self._calculate_creator_stats(username, creator_skeletons)
            for username, creator_skeletons in by_creator.items()
        ]

        # Calculate overall patterns
        overall_hook_techniques = self._count_values(skeletons, 'hook_technique')
        overall_value_structures = self._count_values(skeletons, 'value_structure')
        overall_cta_types = self._count_values(skeletons, 'cta_type')

        # Calculate overall averages
        avg_hook_word_count = self._safe_mean([s.get('hook_word_count', 0) for s in skeletons])
        avg_total_word_count = self._safe_mean([s.get('total_word_count', 0) for s in skeletons])
        avg_duration_seconds = self._safe_mean([s.get('estimated_duration_seconds', 0) for s in skeletons])

        total_views = sum(s.get('views', 0) for s in skeletons)

        result = AggregatedData(
            skeletons=skeletons,
            creator_stats=creator_stats,
            total_videos=len(skeletons),
            total_views=total_views,
            valid_skeletons=len(skeletons),
            overall_hook_techniques=overall_hook_techniques,
            overall_value_structures=overall_value_structures,
            overall_cta_types=overall_cta_types,
            avg_hook_word_count=avg_hook_word_count,
            avg_total_word_count=avg_total_word_count,
            avg_duration_seconds=avg_duration_seconds
        )

        logger.info(
            f"Aggregated {len(skeletons)} skeletons from {len(creator_stats)} creators"
        )

        return result

    def _group_by_creator(self, skeletons: list[dict]) -> dict[str, list[dict]]:
        """Group skeletons by creator username."""
        grouped = defaultdict(list)
        for skeleton in skeletons:
            username = skeleton.get('creator_username', 'unknown')
            grouped[username].append(skeleton)
        return dict(grouped)

    def _calculate_creator_stats(
        self,
        username: str,
        skeletons: list[dict]
    ) -> CreatorStats:
        """Calculate aggregated stats for a single creator."""
        platform = skeletons[0].get('platform', 'unknown') if skeletons else 'unknown'

        total_views = sum(s.get('views', 0) for s in skeletons)
        total_likes = sum(s.get('likes', 0) for s in skeletons)
        count = len(skeletons)

        return CreatorStats(
            username=username,
            platform=platform,
            video_count=count,
            total_views=total_views,
            total_likes=total_likes,
            avg_views=total_views / count if count > 0 else 0,
            avg_likes=total_likes / count if count > 0 else 0,
            avg_hook_word_count=self._safe_mean([s.get('hook_word_count', 0) for s in skeletons]),
            avg_total_word_count=self._safe_mean([s.get('total_word_count', 0) for s in skeletons]),
            avg_duration_seconds=self._safe_mean([s.get('estimated_duration_seconds', 0) for s in skeletons]),
            hook_techniques=self._count_values(skeletons, 'hook_technique'),
            value_structures=self._count_values(skeletons, 'value_structure'),
            cta_types=self._count_values(skeletons, 'cta_type')
        )

    def _count_values(self, skeletons: list[dict], field: str) -> dict[str, int]:
        """Count occurrences of each value for a field."""
        counts = defaultdict(int)
        for skeleton in skeletons:
            value = skeleton.get(field, 'unknown')
            counts[value] += 1
        return dict(counts)

    def _safe_mean(self, values: list) -> float:
        """Calculate mean, returning 0 for empty lists."""
        filtered = [v for v in values if v and v > 0]
        return mean(filtered) if filtered else 0.0


# =============================================================================
# HELPERS
# =============================================================================

def get_top_pattern(counts: dict[str, int]) -> Optional[str]:
    """Get the most common pattern from a counts dict."""
    if not counts:
        return None
    return max(counts, key=counts.get)


def get_pattern_distribution(counts: dict[str, int]) -> list[tuple[str, int, float]]:
    """
    Get pattern distribution with percentages.

    Returns:
        List of (pattern_name, count, percentage) tuples, sorted by count desc
    """
    total = sum(counts.values())
    if total == 0:
        return []

    distribution = [
        (pattern, count, count / total * 100)
        for pattern, count in counts.items()
    ]

    return sorted(distribution, key=lambda x: x[1], reverse=True)


def format_aggregation_summary(data: AggregatedData) -> str:
    """
    Format aggregated data as a human-readable summary.

    Args:
        data: Aggregated skeleton data

    Returns:
        Formatted summary string
    """
    lines = [
        f"# Aggregation Summary",
        f"",
        f"**Total Videos:** {data.total_videos}",
        f"**Total Views:** {data.total_views:,}",
        f"**Creators:** {len(data.creator_stats)}",
        f"",
        f"## Averages",
        f"- Hook word count: {data.avg_hook_word_count:.1f}",
        f"- Total word count: {data.avg_total_word_count:.1f}",
        f"- Duration: {data.avg_duration_seconds:.1f}s",
        f"",
        f"## Hook Techniques",
    ]

    for pattern, count, pct in get_pattern_distribution(data.overall_hook_techniques):
        lines.append(f"- {pattern}: {count} ({pct:.0f}%)")

    lines.append("")
    lines.append("## Value Structures")

    for pattern, count, pct in get_pattern_distribution(data.overall_value_structures):
        lines.append(f"- {pattern}: {count} ({pct:.0f}%)")

    lines.append("")
    lines.append("## CTA Types")

    for pattern, count, pct in get_pattern_distribution(data.overall_cta_types):
        lines.append(f"- {pattern}: {count} ({pct:.0f}%)")

    return "\n".join(lines)
