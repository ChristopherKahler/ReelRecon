"""
Main pipeline orchestration for Content Skeleton Ripper.

Coordinates all stages:
0. Cache check
1. Scrape & transcribe (using existing ReelRecon infrastructure)
2. Batched extraction
3. Aggregation
4. Synthesis
5. Output
"""

import os
import json
import uuid
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, Callable
from enum import Enum

from .cache import TranscriptCache, is_valid_transcript
from .llm_client import LLMClient
from .extractor import BatchedExtractor
from .aggregator import SkeletonAggregator, AggregatedData
from .synthesizer import PatternSynthesizer, SynthesisResult, generate_report
from utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# JOB STATUS
# =============================================================================

class JobStatus(Enum):
    """Pipeline job status."""
    PENDING = "pending"
    SCRAPING = "scraping"
    TRANSCRIBING = "transcribing"
    EXTRACTING = "extracting"
    AGGREGATING = "aggregating"
    SYNTHESIZING = "synthesizing"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class JobProgress:
    """Progress tracking for a skeleton ripper job."""
    status: JobStatus = JobStatus.PENDING
    phase: str = ""
    message: str = ""

    # Counts
    videos_scraped: int = 0
    videos_transcribed: int = 0
    transcripts_from_cache: int = 0
    valid_transcripts: int = 0
    skeletons_extracted: int = 0
    total_target: int = 0

    # Timing
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    # Errors
    errors: list[str] = field(default_factory=list)


@dataclass
class JobConfig:
    """Configuration for a skeleton ripper job."""
    usernames: list[str]
    videos_per_creator: int = 3
    platform: str = "instagram"
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    min_valid_ratio: float = 0.6  # 60% valid transcripts required


@dataclass
class JobResult:
    """Final result of a skeleton ripper job."""
    job_id: str
    success: bool
    config: JobConfig
    progress: JobProgress

    # Data
    skeletons: list[dict] = field(default_factory=list)
    aggregated: Optional[AggregatedData] = None
    synthesis: Optional[SynthesisResult] = None

    # Output paths
    report_path: Optional[str] = None
    skeletons_path: Optional[str] = None
    synthesis_path: Optional[str] = None


# =============================================================================
# PIPELINE
# =============================================================================

class SkeletonRipperPipeline:
    """
    Main pipeline for Content Skeleton Ripper.

    Orchestrates the full flow from usernames to final report.

    Usage:
        pipeline = SkeletonRipperPipeline(base_dir)
        result = pipeline.run(config, on_progress=callback)
    """

    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize the pipeline.

        Args:
            base_dir: Base directory for ReelRecon. Defaults to auto-detect.
        """
        if base_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.base_dir = Path(base_dir)
        self.output_dir = self.base_dir / 'output' / 'skeleton_reports'
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.cache = TranscriptCache(base_dir)

        logger.info(f"SkeletonRipperPipeline initialized at {base_dir}")

    def run(
        self,
        config: JobConfig,
        on_progress: Optional[Callable[[JobProgress], None]] = None
    ) -> JobResult:
        """
        Run the full skeleton ripper pipeline.

        Args:
            config: Job configuration
            on_progress: Optional callback for progress updates

        Returns:
            JobResult with all data and output paths
        """
        job_id = f"sr_{uuid.uuid4().hex[:8]}"
        progress = JobProgress(
            status=JobStatus.PENDING,
            started_at=datetime.utcnow().isoformat(),
            total_target=len(config.usernames) * config.videos_per_creator
        )

        result = JobResult(
            job_id=job_id,
            success=False,
            config=config,
            progress=progress
        )

        logger.info(f"Starting job {job_id}: {len(config.usernames)} creators, {config.videos_per_creator} videos each")

        try:
            # Initialize LLM client
            llm_client = LLMClient(
                provider=config.llm_provider,
                model=config.llm_model
            )

            # Stage 0 & 1: Scrape and transcribe
            progress.status = JobStatus.SCRAPING
            progress.phase = "Scraping videos..."
            self._notify(on_progress, progress)

            transcripts = self._scrape_and_transcribe(
                config=config,
                progress=progress,
                on_progress=on_progress
            )

            # Check validity threshold
            valid_count = sum(1 for t in transcripts if is_valid_transcript(t.get('transcript', '')))
            progress.valid_transcripts = valid_count
            self._notify(on_progress, progress)

            valid_ratio = valid_count / len(transcripts) if transcripts else 0
            if valid_ratio < config.min_valid_ratio:
                logger.warning(
                    f"Only {valid_count}/{len(transcripts)} valid transcripts "
                    f"({valid_ratio:.0%} < {config.min_valid_ratio:.0%} threshold)"
                )
                progress.errors.append(
                    f"Low transcript validity: {valid_count}/{len(transcripts)} ({valid_ratio:.0%})"
                )

            if valid_count == 0:
                raise ValueError("No valid transcripts to process")

            # Filter to valid transcripts only
            valid_transcripts = [
                t for t in transcripts
                if is_valid_transcript(t.get('transcript', ''))
            ]

            # Stage 2: Extraction
            progress.status = JobStatus.EXTRACTING
            progress.phase = "Extracting content skeletons..."
            self._notify(on_progress, progress)

            extractor = BatchedExtractor(llm_client)
            extraction_result = extractor.extract_all(
                valid_transcripts,
                on_progress=lambda done, total: self._update_extraction_progress(
                    progress, done, on_progress
                )
            )

            result.skeletons = extraction_result.successful
            progress.skeletons_extracted = len(extraction_result.successful)

            if extraction_result.failed_video_ids:
                progress.errors.append(
                    f"Failed to extract: {', '.join(extraction_result.failed_video_ids)}"
                )

            if not result.skeletons:
                raise ValueError("No skeletons extracted successfully")

            # Stage 3: Aggregation
            progress.status = JobStatus.AGGREGATING
            progress.phase = "Aggregating patterns..."
            self._notify(on_progress, progress)

            aggregator = SkeletonAggregator()
            result.aggregated = aggregator.aggregate(result.skeletons)

            # Stage 4: Synthesis
            progress.status = JobStatus.SYNTHESIZING
            progress.phase = "Synthesizing content strategy..."
            self._notify(on_progress, progress)

            synthesizer = PatternSynthesizer(llm_client)
            result.synthesis = synthesizer.synthesize(result.aggregated)

            if not result.synthesis.success:
                progress.errors.append(f"Synthesis failed: {result.synthesis.error}")
                logger.error(f"Synthesis failed: {result.synthesis.error}")

            # Stage 5: Output
            progress.phase = "Generating report..."
            self._notify(on_progress, progress)

            output_paths = self._save_outputs(job_id, config, result)
            result.report_path = output_paths.get('report')
            result.skeletons_path = output_paths.get('skeletons')
            result.synthesis_path = output_paths.get('synthesis')

            # Complete
            progress.status = JobStatus.COMPLETE
            progress.phase = "Complete"
            progress.completed_at = datetime.utcnow().isoformat()
            result.success = True

            logger.info(f"Job {job_id} complete: {len(result.skeletons)} skeletons extracted")

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            progress.status = JobStatus.FAILED
            progress.phase = "Failed"
            progress.errors.append(str(e))
            progress.completed_at = datetime.utcnow().isoformat()

        self._notify(on_progress, progress)
        return result

    def _scrape_and_transcribe(
        self,
        config: JobConfig,
        progress: JobProgress,
        on_progress: Optional[Callable]
    ) -> list[dict]:
        """
        Scrape videos and get transcripts (from cache or fresh).

        This integrates with existing ReelRecon scraping infrastructure.
        """
        transcripts = []

        for username in config.usernames:
            logger.info(f"Processing creator: {username}")

            # Get top videos for this creator
            # TODO: Integrate with existing scraper modules
            videos = self._get_top_videos(
                username=username,
                platform=config.platform,
                count=config.videos_per_creator
            )

            progress.videos_scraped += len(videos)
            self._notify(on_progress, progress)

            for video in videos:
                video_id = video.get('video_id', 'unknown')

                # Check cache first
                cached = self.cache.get(config.platform, username, video_id)

                if cached:
                    progress.transcripts_from_cache += 1
                    transcript_text = cached
                    logger.debug(f"Cache hit: {video_id}")
                else:
                    # Download and transcribe
                    # TODO: Integrate with existing transcription
                    transcript_text = self._transcribe_video(video)

                    # Cache if valid
                    if is_valid_transcript(transcript_text):
                        self.cache.set(config.platform, username, video_id, transcript_text)

                progress.videos_transcribed += 1
                self._notify(on_progress, progress)

                transcripts.append({
                    'video_id': video_id,
                    'username': username,
                    'platform': config.platform,
                    'views': video.get('views', 0),
                    'likes': video.get('likes', 0),
                    'url': video.get('url', ''),
                    'transcript': transcript_text,
                    'from_cache': cached is not None
                })

        return transcripts

    def _get_top_videos(
        self,
        username: str,
        platform: str,
        count: int
    ) -> list[dict]:
        """
        Get top videos for a creator.

        TODO: Integrate with existing ReelRecon scraper modules.
        For now, this is a placeholder that should be connected to:
        - scraper/instagram.py
        - scraper/tiktok.py
        """
        logger.warning(f"_get_top_videos not yet integrated - returning empty for {username}")
        # Placeholder - needs integration with existing scraper
        return []

    def _transcribe_video(self, video: dict) -> str:
        """
        Transcribe a video.

        TODO: Integrate with existing transcription.
        For now, this is a placeholder that should be connected to
        the existing whisper transcription code.
        """
        logger.warning(f"_transcribe_video not yet integrated - returning empty")
        # Placeholder - needs integration with existing transcription
        return ""

    def _update_extraction_progress(
        self,
        progress: JobProgress,
        done: int,
        on_progress: Optional[Callable]
    ):
        """Update extraction progress count."""
        progress.skeletons_extracted = done
        self._notify(on_progress, progress)

    def _notify(
        self,
        callback: Optional[Callable[[JobProgress], None]],
        progress: JobProgress
    ):
        """Send progress notification if callback provided."""
        if callback:
            try:
                callback(progress)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

    def _save_outputs(
        self,
        job_id: str,
        config: JobConfig,
        result: JobResult
    ) -> dict[str, str]:
        """
        Save all outputs to disk.

        Returns:
            Dict with paths to saved files
        """
        # Create job output directory
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        job_dir = self.output_dir / f"{timestamp}_{job_id}"
        job_dir.mkdir(parents=True, exist_ok=True)

        paths = {}

        # Save skeletons JSON
        skeletons_path = job_dir / 'skeletons.json'
        with open(skeletons_path, 'w', encoding='utf-8') as f:
            json.dump(result.skeletons, f, indent=2, default=str)
        paths['skeletons'] = str(skeletons_path)

        # Save synthesis JSON
        if result.synthesis:
            synthesis_path = job_dir / 'synthesis.json'
            synthesis_data = {
                'success': result.synthesis.success,
                'analysis': result.synthesis.analysis,
                'templates': result.synthesis.templates,
                'quick_wins': result.synthesis.quick_wins,
                'warnings': result.synthesis.warnings,
                'model_used': result.synthesis.model_used,
                'synthesized_at': result.synthesis.synthesized_at
            }
            with open(synthesis_path, 'w', encoding='utf-8') as f:
                json.dump(synthesis_data, f, indent=2)
            paths['synthesis'] = str(synthesis_path)

        # Save markdown report
        if result.aggregated and result.synthesis:
            report_path = job_dir / 'report.md'
            report_content = generate_report(
                data=result.aggregated,
                synthesis=result.synthesis,
                job_config=asdict(config)
            )
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_content)
            paths['report'] = str(report_path)

        logger.info(f"Saved outputs to {job_dir}")
        return paths


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_job_config(
    usernames: list[str],
    videos_per_creator: int = 3,
    platform: str = "instagram",
    llm_provider: str = "openai",
    llm_model: str = "gpt-4o-mini"
) -> JobConfig:
    """Create a job configuration."""
    return JobConfig(
        usernames=usernames,
        videos_per_creator=videos_per_creator,
        platform=platform,
        llm_provider=llm_provider,
        llm_model=llm_model
    )


def run_skeleton_ripper(
    usernames: list[str],
    videos_per_creator: int = 3,
    platform: str = "instagram",
    llm_provider: str = "openai",
    llm_model: str = "gpt-4o-mini",
    on_progress: Optional[Callable] = None
) -> JobResult:
    """
    Convenience function to run the skeleton ripper.

    Args:
        usernames: List of creator usernames (1-5)
        videos_per_creator: Videos to analyze per creator (1-5)
        platform: 'instagram' or 'tiktok'
        llm_provider: LLM provider ID
        llm_model: Model ID
        on_progress: Optional progress callback

    Returns:
        JobResult
    """
    config = create_job_config(
        usernames=usernames,
        videos_per_creator=videos_per_creator,
        platform=platform,
        llm_provider=llm_provider,
        llm_model=llm_model
    )

    pipeline = SkeletonRipperPipeline()
    return pipeline.run(config, on_progress=on_progress)
