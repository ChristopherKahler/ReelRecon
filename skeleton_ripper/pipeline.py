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

# Import existing scraper infrastructure
from scraper.core import run_scrape

logger = get_logger()


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

    # Transcription settings
    transcribe_provider: str = "openai"  # 'openai' or 'local'
    whisper_model: str = "small.en"  # For local transcription
    openai_api_key: Optional[str] = None  # For OpenAI transcription

    # Cookies paths (auto-detected if None)
    cookies_path: Optional[str] = None
    tiktok_cookies_path: Optional[str] = None


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

        # Default cookies paths
        self.default_cookies = self.base_dir / 'cookies.txt'
        self.default_tiktok_cookies = self.base_dir / 'tiktok_cookies.txt'

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
        Scrape videos and get transcripts using existing ReelRecon infrastructure.

        Leverages run_scrape() for each creator to:
        1. Fetch top videos by view count
        2. Download videos
        3. Transcribe using OpenAI or local Whisper
        """
        transcripts = []

        # Determine cookies path
        if config.platform == 'tiktok':
            cookies_path = config.tiktok_cookies_path or str(self.default_tiktok_cookies)
        else:
            cookies_path = config.cookies_path or str(self.default_cookies)

        # Check cookies exist
        if not os.path.exists(cookies_path):
            raise FileNotFoundError(
                f"Cookies file not found: {cookies_path}. "
                f"Please export your {config.platform} cookies."
            )

        # Get OpenAI API key for transcription
        openai_key = config.openai_api_key or os.getenv('OPENAI_API_KEY')

        for idx, username in enumerate(config.usernames):
            logger.info(f"Processing creator {idx + 1}/{len(config.usernames)}: @{username}")
            progress.phase = f"Scraping @{username}..."
            self._notify(on_progress, progress)

            # Check cache for this creator first
            cached_transcripts = self._get_cached_transcripts(
                config.platform, username, config.videos_per_creator
            )

            if cached_transcripts and len(cached_transcripts) >= config.videos_per_creator:
                # Have enough cached - use those
                logger.info(f"Using {len(cached_transcripts)} cached transcripts for @{username}")
                progress.transcripts_from_cache += len(cached_transcripts)
                transcripts.extend(cached_transcripts)
                progress.videos_scraped += len(cached_transcripts)
                progress.videos_transcribed += len(cached_transcripts)
                self._notify(on_progress, progress)
                continue

            # Need to scrape fresh - use existing ReelRecon infrastructure
            try:
                def scrape_progress(msg):
                    progress.message = msg
                    self._notify(on_progress, progress)

                scrape_result = run_scrape(
                    username=username,
                    cookies_path=cookies_path,
                    max_reels=50,  # Fetch more to ensure we get enough with transcripts
                    top_n=config.videos_per_creator,
                    download=True,
                    transcribe=True,
                    whisper_model=config.whisper_model,
                    transcribe_provider=config.transcribe_provider,
                    openai_key=openai_key,
                    output_dir=str(self.base_dir / 'output' / 'skeleton_temp'),
                    progress_callback=scrape_progress
                )

                if scrape_result.get('status') == 'error':
                    error_msg = scrape_result.get('error', 'Unknown scrape error')
                    logger.warning(f"Scrape failed for @{username}: {error_msg}")
                    progress.errors.append(f"@{username}: {error_msg}")
                    continue

                # Process results
                reels = scrape_result.get('top_reels', [])
                progress.videos_scraped += len(reels)

                for reel in reels:
                    transcript_text = reel.get('transcript', '')
                    video_id = reel.get('shortcode', 'unknown')

                    # Cache valid transcripts
                    if is_valid_transcript(transcript_text):
                        self.cache.set(config.platform, username, video_id, transcript_text)
                        progress.videos_transcribed += 1

                    transcripts.append({
                        'video_id': video_id,
                        'username': username,
                        'platform': config.platform,
                        'views': reel.get('views', 0),
                        'likes': reel.get('likes', 0),
                        'url': reel.get('url', ''),
                        'transcript': transcript_text,
                        'from_cache': False
                    })

                self._notify(on_progress, progress)

            except Exception as e:
                logger.error(f"Error scraping @{username}: {e}")
                progress.errors.append(f"@{username}: {str(e)}")

        return transcripts

    def _get_cached_transcripts(
        self,
        platform: str,
        username: str,
        count: int
    ) -> list[dict]:
        """
        Get cached transcripts for a creator.

        Returns list of transcript dicts if enough are cached.
        """
        cached = []
        cache_pattern = f"{platform.lower()}_{username.lower()}_*.txt"
        cache_files = list(self.cache.cache_dir.glob(cache_pattern))

        for cache_file in cache_files[:count]:
            try:
                transcript_text = cache_file.read_text(encoding='utf-8')
                if is_valid_transcript(transcript_text):
                    # Extract video_id from filename
                    filename = cache_file.stem
                    parts = filename.split('_')
                    video_id = parts[-1] if len(parts) >= 3 else filename

                    cached.append({
                        'video_id': video_id,
                        'username': username,
                        'platform': platform,
                        'views': 0,  # Not available from cache
                        'likes': 0,
                        'url': '',
                        'transcript': transcript_text,
                        'from_cache': True
                    })
            except Exception as e:
                logger.warning(f"Failed to read cache file {cache_file}: {e}")

        return cached

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
    llm_model: str = "gpt-4o-mini",
    transcribe_provider: str = "openai",
    whisper_model: str = "small.en",
    openai_api_key: Optional[str] = None
) -> JobConfig:
    """Create a job configuration."""
    return JobConfig(
        usernames=usernames,
        videos_per_creator=videos_per_creator,
        platform=platform,
        llm_provider=llm_provider,
        llm_model=llm_model,
        transcribe_provider=transcribe_provider,
        whisper_model=whisper_model,
        openai_api_key=openai_api_key
    )


def run_skeleton_ripper(
    usernames: list[str],
    videos_per_creator: int = 3,
    platform: str = "instagram",
    llm_provider: str = "openai",
    llm_model: str = "gpt-4o-mini",
    transcribe_provider: str = "openai",
    whisper_model: str = "small.en",
    openai_api_key: Optional[str] = None,
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
        transcribe_provider: 'openai' or 'local'
        whisper_model: Model for local transcription
        openai_api_key: OpenAI API key (optional, uses env var if not provided)
        on_progress: Optional progress callback

    Returns:
        JobResult
    """
    config = create_job_config(
        usernames=usernames,
        videos_per_creator=videos_per_creator,
        platform=platform,
        llm_provider=llm_provider,
        llm_model=llm_model,
        transcribe_provider=transcribe_provider,
        whisper_model=whisper_model,
        openai_api_key=openai_api_key
    )

    pipeline = SkeletonRipperPipeline()
    return pipeline.run(config, on_progress=on_progress)
