"""
Transcript caching for Content Skeleton Ripper.

Caches validated transcripts to avoid re-downloading and re-transcribing
videos that have already been processed.

Cache Strategy:
- Cache transcripts (content doesn't change)
- DON'T cache engagement stats (views/likes change)
- DON'T cache video rankings (top videos change over time)
"""

import os
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional
from utils.logger import get_logger

logger = get_logger(__name__)


class TranscriptCache:
    """
    Manages caching of video transcripts.

    Cache location: {base_dir}/cache/transcripts/
    Cache key format: {platform}_{username}_{video_id}.txt

    Usage:
        cache = TranscriptCache()

        # Check cache
        transcript = cache.get('instagram', 'creator1', 'abc123')
        if transcript:
            print("Cache hit!")
        else:
            # Download and transcribe...
            cache.set('instagram', 'creator1', 'abc123', transcript_text)
    """

    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize transcript cache.

        Args:
            base_dir: Base directory for cache. Defaults to ReelRecon root.
        """
        if base_dir is None:
            # Default to ReelRecon directory
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.cache_dir = Path(base_dir) / 'cache' / 'transcripts'
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Transcript cache initialized at: {self.cache_dir}")

    def _get_cache_path(self, platform: str, username: str, video_id: str) -> Path:
        """
        Get the cache file path for a video.

        Args:
            platform: 'instagram' or 'tiktok'
            username: Creator username
            video_id: Video identifier

        Returns:
            Path to cache file
        """
        # Sanitize inputs for filename safety
        safe_platform = platform.lower().replace('/', '_').replace('\\', '_')
        safe_username = username.lower().replace('/', '_').replace('\\', '_')
        safe_video_id = video_id.replace('/', '_').replace('\\', '_')

        filename = f"{safe_platform}_{safe_username}_{safe_video_id}.txt"
        return self.cache_dir / filename

    def get(self, platform: str, username: str, video_id: str) -> Optional[str]:
        """
        Get transcript from cache if it exists.

        Args:
            platform: 'instagram' or 'tiktok'
            username: Creator username
            video_id: Video identifier

        Returns:
            Transcript text if cached, None otherwise
        """
        cache_path = self._get_cache_path(platform, username, video_id)

        if cache_path.exists():
            try:
                transcript = cache_path.read_text(encoding='utf-8')
                if transcript.strip():  # Don't return empty transcripts
                    logger.debug(f"Cache HIT: {platform}/{username}/{video_id}")
                    return transcript
            except Exception as e:
                logger.warning(f"Cache read error for {video_id}: {e}")

        logger.debug(f"Cache MISS: {platform}/{username}/{video_id}")
        return None

    def set(
        self,
        platform: str,
        username: str,
        video_id: str,
        transcript: str,
        validate: bool = True
    ) -> bool:
        """
        Save transcript to cache.

        Args:
            platform: 'instagram' or 'tiktok'
            username: Creator username
            video_id: Video identifier
            transcript: Transcript text to cache
            validate: If True, only cache if transcript is valid

        Returns:
            True if cached successfully, False otherwise
        """
        # Validate before caching
        if validate and not self._is_valid_transcript(transcript):
            logger.debug(f"Not caching invalid transcript: {video_id}")
            return False

        cache_path = self._get_cache_path(platform, username, video_id)

        try:
            cache_path.write_text(transcript, encoding='utf-8')
            logger.debug(f"Cached transcript: {platform}/{username}/{video_id}")
            return True
        except Exception as e:
            logger.warning(f"Cache write error for {video_id}: {e}")
            return False

    def exists(self, platform: str, username: str, video_id: str) -> bool:
        """
        Check if a transcript is cached.

        Args:
            platform: 'instagram' or 'tiktok'
            username: Creator username
            video_id: Video identifier

        Returns:
            True if cached, False otherwise
        """
        cache_path = self._get_cache_path(platform, username, video_id)
        return cache_path.exists() and cache_path.stat().st_size > 0

    def delete(self, platform: str, username: str, video_id: str) -> bool:
        """
        Delete a cached transcript.

        Args:
            platform: 'instagram' or 'tiktok'
            username: Creator username
            video_id: Video identifier

        Returns:
            True if deleted, False if not found
        """
        cache_path = self._get_cache_path(platform, username, video_id)

        if cache_path.exists():
            cache_path.unlink()
            logger.debug(f"Deleted cached transcript: {video_id}")
            return True
        return False

    def _is_valid_transcript(self, transcript: str) -> bool:
        """
        Check if transcript is valid and worth caching.

        Args:
            transcript: Transcript text

        Returns:
            True if valid, False otherwise
        """
        if not transcript:
            return False

        # Minimum word count
        word_count = len(transcript.split())
        if word_count < 10:
            return False

        # Check for common garbage patterns
        garbage_patterns = [
            'music',  # Just "[Music]" captions
            '♪',
            'subscribe',  # Auto-generated subscribe reminders only
            '[applause]',
            '[laughter]',
        ]

        transcript_lower = transcript.lower()

        # If transcript is mostly garbage patterns, reject it
        for pattern in garbage_patterns:
            if transcript_lower.count(pattern) > word_count // 2:
                return False

        return True

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats
        """
        if not self.cache_dir.exists():
            return {'total_files': 0, 'total_size_mb': 0}

        files = list(self.cache_dir.glob('*.txt'))
        total_size = sum(f.stat().st_size for f in files)

        return {
            'total_files': len(files),
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'cache_dir': str(self.cache_dir)
        }

    def clear_all(self) -> int:
        """
        Clear all cached transcripts.

        Returns:
            Number of files deleted
        """
        files = list(self.cache_dir.glob('*.txt'))
        for f in files:
            f.unlink()

        logger.info(f"Cleared {len(files)} cached transcripts")
        return len(files)

    def clear_for_username(self, platform: str, username: str) -> int:
        """
        Clear cached transcripts for a specific creator.

        Args:
            platform: 'instagram' or 'tiktok'
            username: Creator username

        Returns:
            Number of files deleted
        """
        pattern = f"{platform.lower()}_{username.lower()}_*.txt"
        files = list(self.cache_dir.glob(pattern))

        for f in files:
            f.unlink()

        logger.info(f"Cleared {len(files)} cached transcripts for {username}")
        return len(files)


# =============================================================================
# VALIDATION HELPERS
# =============================================================================

MIN_TRANSCRIPT_WORDS = 10
MIN_VALID_RATIO = 0.6  # 60% of videos must have valid transcripts


def is_valid_transcript(transcript: str) -> bool:
    """
    Check if a transcript is valid for extraction.

    Args:
        transcript: Transcript text

    Returns:
        True if valid, False otherwise
    """
    if not transcript or not transcript.strip():
        return False

    word_count = len(transcript.split())
    return word_count >= MIN_TRANSCRIPT_WORDS


def check_transcript_validity(transcripts: list[dict]) -> tuple[int, int, bool]:
    """
    Check validity of a batch of transcripts.

    Args:
        transcripts: List of dicts with 'transcript' key

    Returns:
        Tuple of (valid_count, total_count, meets_threshold)
    """
    total = len(transcripts)
    valid = sum(1 for t in transcripts if is_valid_transcript(t.get('transcript', '')))

    ratio = valid / total if total > 0 else 0
    meets_threshold = ratio >= MIN_VALID_RATIO

    return valid, total, meets_threshold
