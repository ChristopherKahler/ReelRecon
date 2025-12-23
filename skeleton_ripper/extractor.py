"""
Batched content skeleton extractor with smart retry logic.

Extracts content structure (hook/value/CTA) from video transcripts using LLM.
Batches 3-5 transcripts per call for efficiency.
"""

import json
import traceback
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

from .llm_client import LLMClient
from .prompts import get_extraction_prompt, validate_skeleton
from utils.logger import get_logger

logger = get_logger()


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class ExtractionResult:
    """Result from extracting a single video's skeleton."""
    video_id: str
    success: bool
    skeleton: Optional[dict] = None
    error: Optional[str] = None
    from_cache: bool = False


@dataclass
class BatchExtractionResult:
    """Result from a batch extraction attempt."""
    successful: list[dict] = field(default_factory=list)
    failed_video_ids: list[str] = field(default_factory=list)
    total_attempts: int = 0


# =============================================================================
# BATCHED EXTRACTOR
# =============================================================================

class BatchedExtractor:
    """
    Extracts content skeletons from video transcripts in batches.

    Uses batching to reduce API calls while maintaining reliability
    through smart retry logic.

    Usage:
        extractor = BatchedExtractor(llm_client)
        results = extractor.extract_all(transcripts)
    """

    DEFAULT_BATCH_SIZE = 4  # 3-5 transcripts per batch
    MAX_RETRIES = 2

    def __init__(
        self,
        llm_client: LLMClient,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_retries: int = MAX_RETRIES
    ):
        """
        Initialize the batched extractor.

        Args:
            llm_client: Configured LLM client
            batch_size: Number of transcripts per batch (3-5 recommended)
            max_retries: Max retry attempts on batch failure
        """
        self.llm_client = llm_client
        self.batch_size = min(max(batch_size, 1), 5)  # Clamp to 1-5
        self.max_retries = max_retries

        logger.info("EXTRACT", f"BatchedExtractor initialized: batch_size={self.batch_size}")

    def extract_all(
        self,
        transcripts: list[dict],
        on_progress: Optional[callable] = None
    ) -> BatchExtractionResult:
        """
        Extract skeletons from all transcripts.

        Args:
            transcripts: List of dicts with 'video_id', 'transcript', 'views', etc.
            on_progress: Optional callback(extracted_count, total_count, batch_idx, total_batches)

        Returns:
            BatchExtractionResult with successful extractions and failures
        """
        result = BatchExtractionResult()
        total = len(transcripts)

        # Split into batches
        batches = self._create_batches(transcripts)
        total_batches = len(batches)
        logger.info("EXTRACT", f"Processing {total} transcripts in {total_batches} batches")

        for batch_idx, batch in enumerate(batches):
            logger.debug("EXTRACT", f"Processing batch {batch_idx + 1}/{total_batches}")

            batch_result = self._extract_batch_with_retry(batch)

            result.successful.extend(batch_result.successful)
            result.failed_video_ids.extend(batch_result.failed_video_ids)
            result.total_attempts += batch_result.total_attempts

            # Progress callback with batch info
            if on_progress:
                on_progress(len(result.successful), total, batch_idx + 1, total_batches)

        logger.info(
            "EXTRACT",
            f"Extraction complete: {len(result.successful)} successful, "
            f"{len(result.failed_video_ids)} failed"
        )

        return result

    def _create_batches(self, transcripts: list[dict]) -> list[list[dict]]:
        """Split transcripts into batches."""
        batches = []
        for i in range(0, len(transcripts), self.batch_size):
            batches.append(transcripts[i:i + self.batch_size])
        return batches

    def _extract_batch_with_retry(
        self,
        batch: list[dict],
        attempt: int = 0
    ) -> BatchExtractionResult:
        """
        Extract a batch of transcripts with smart retry on failure.

        On parse failure:
        1. Split batch in half
        2. Retry each half
        3. If single transcript fails, mark as failed and skip

        Args:
            batch: List of transcript dicts
            attempt: Current attempt number

        Returns:
            BatchExtractionResult for this batch
        """
        result = BatchExtractionResult()
        result.total_attempts = 1

        if not batch:
            return result

        try:
            # Build and send prompt
            prompt = get_extraction_prompt(batch)
            response = self.llm_client.complete(prompt, temperature=0)

            # Parse JSON response
            parsed = self._parse_response(response)

            if parsed is None:
                raise json.JSONDecodeError("Failed to parse response", response, 0)

            # Validate and collect results
            for skeleton in parsed:
                is_valid, error = validate_skeleton(skeleton)

                if is_valid:
                    # Enrich skeleton with metadata
                    video_id = skeleton.get('video_id')
                    original = self._find_original(batch, video_id)

                    if original:
                        skeleton['creator_username'] = original.get('username', 'unknown')
                        skeleton['platform'] = original.get('platform', 'unknown')
                        skeleton['views'] = original.get('views', 0)
                        skeleton['likes'] = original.get('likes', 0)
                        skeleton['url'] = original.get('url', '')
                        skeleton['video_url'] = original.get('video_url', '')
                        skeleton['transcript'] = original.get('transcript', '')
                        skeleton['extracted_at'] = datetime.utcnow().isoformat()
                        skeleton['extraction_model'] = f"{self.llm_client.provider}/{self.llm_client.model}"

                    result.successful.append(skeleton)
                else:
                    logger.warning("EXTRACT", f"Invalid skeleton for {skeleton.get('video_id')}: {error}")
                    result.failed_video_ids.append(skeleton.get('video_id', 'unknown'))

            return result

        except json.JSONDecodeError as e:
            logger.warning("EXTRACT", f"Batch parse failed (attempt {attempt + 1}): {e}")
            return self._handle_parse_failure(batch, attempt)

        except Exception as e:
            logger.error("EXTRACT", f"Batch extraction error: {e}")
            logger.debug("EXTRACT", f"Stack trace:\n{traceback.format_exc()}")
            # Mark all as failed
            result.failed_video_ids = [t.get('video_id', 'unknown') for t in batch]
            return result

    def _handle_parse_failure(
        self,
        batch: list[dict],
        attempt: int
    ) -> BatchExtractionResult:
        """
        Handle parse failure by splitting batch and retrying.

        Args:
            batch: Failed batch
            attempt: Current attempt number

        Returns:
            Combined results from retry attempts
        """
        result = BatchExtractionResult()

        if attempt >= self.max_retries:
            # Max retries reached - mark all as failed
            result.failed_video_ids = [t.get('video_id', 'unknown') for t in batch]
            logger.warning("EXTRACT", f"Max retries reached, {len(batch)} transcripts failed")
            return result

        if len(batch) > 1:
            # Split batch and retry each half
            mid = len(batch) // 2
            first_half = batch[:mid]
            second_half = batch[mid:]

            logger.info("EXTRACT", f"Splitting batch: {len(first_half)} + {len(second_half)}")

            # Retry first half
            first_result = self._extract_batch_with_retry(first_half, attempt + 1)
            result.successful.extend(first_result.successful)
            result.failed_video_ids.extend(first_result.failed_video_ids)
            result.total_attempts += first_result.total_attempts

            # Retry second half
            second_result = self._extract_batch_with_retry(second_half, attempt + 1)
            result.successful.extend(second_result.successful)
            result.failed_video_ids.extend(second_result.failed_video_ids)
            result.total_attempts += second_result.total_attempts

        else:
            # Single transcript failed - mark as failed
            video_id = batch[0].get('video_id', 'unknown')
            result.failed_video_ids.append(video_id)
            logger.warning("EXTRACT", f"Single transcript extraction failed: {video_id}")

        return result

    def _parse_response(self, response: str) -> Optional[list[dict]]:
        """
        Parse LLM response into list of skeleton dicts.

        Handles common response formatting issues.

        Args:
            response: Raw LLM response text

        Returns:
            List of skeleton dicts, or None if parse fails
        """
        import re

        # Clean response
        text = response.strip()

        # Remove markdown code blocks if present
        if '```' in text:
            # Extract content between ``` markers
            match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
            if match:
                text = match.group(1).strip()
            else:
                # Remove leading ``` and everything before it
                text = re.sub(r'^.*?```(?:json)?\s*', '', text, flags=re.DOTALL)
                text = re.sub(r'\s*```.*$', '', text, flags=re.DOTALL)

        # Try to find JSON array or object in the text
        text = text.strip()

        # If doesn't start with [ or {, try to find them
        if not text.startswith('[') and not text.startswith('{'):
            # Find first [ or {
            array_start = text.find('[')
            obj_start = text.find('{')

            if array_start >= 0 and (obj_start < 0 or array_start < obj_start):
                text = text[array_start:]
            elif obj_start >= 0:
                text = text[obj_start:]

        # Try to parse
        try:
            parsed = json.loads(text)

            # Ensure it's a list
            if isinstance(parsed, dict):
                # Single skeleton returned as object - wrap in list
                parsed = [parsed]

            if isinstance(parsed, list):
                return parsed

        except json.JSONDecodeError as e:
            # Log the actual error for debugging
            logger.debug("EXTRACT", f"JSON parse failed: {e}. First 200 chars: {text[:200]}")

        return None

    def _find_original(self, batch: list[dict], video_id: str) -> Optional[dict]:
        """Find original transcript dict by video_id."""
        for t in batch:
            if t.get('video_id') == video_id:
                return t
        return None


# =============================================================================
# SINGLE VIDEO EXTRACTION (for testing/debugging)
# =============================================================================

def extract_single(
    llm_client: LLMClient,
    transcript: dict
) -> ExtractionResult:
    """
    Extract skeleton from a single transcript.

    Useful for testing or processing individual videos.

    Args:
        llm_client: Configured LLM client
        transcript: Dict with 'video_id', 'transcript', etc.

    Returns:
        ExtractionResult
    """
    extractor = BatchedExtractor(llm_client, batch_size=1)
    result = extractor.extract_all([transcript])

    if result.successful:
        return ExtractionResult(
            video_id=transcript.get('video_id', 'unknown'),
            success=True,
            skeleton=result.successful[0]
        )
    else:
        return ExtractionResult(
            video_id=transcript.get('video_id', 'unknown'),
            success=False,
            error="Extraction failed"
        )
