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
import time
import traceback
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
from scraper.core import (
    create_session,
    get_user_reels,
    download_video,
    transcribe_video_openai,
    transcribe_video,
    load_whisper_model,
    WHISPER_AVAILABLE
)

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
    videos_scraped: int = 0  # Reels fetched from API (metadata)
    videos_downloaded: int = 0  # Videos actually downloaded
    videos_transcribed: int = 0  # Videos transcribed
    transcripts_from_cache: int = 0
    valid_transcripts: int = 0
    skeletons_extracted: int = 0
    total_target: int = 0

    # Granular progress
    current_creator: str = ""
    current_creator_index: int = 0
    total_creators: int = 0
    reels_fetched: int = 0  # Reels fetched for current creator
    current_video_index: int = 0  # Which video we're on (out of videos_per_creator)
    extraction_batch: int = 0
    extraction_total_batches: int = 0

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

        logger.info("PIPELINE", f"SkeletonRipperPipeline initialized at {base_dir}")

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
            total_target=len(config.usernames) * config.videos_per_creator,
            total_creators=len(config.usernames)
        )

        result = JobResult(
            job_id=job_id,
            success=False,
            config=config,
            progress=progress
        )

        logger.info("SKELETON", f"Starting job {job_id}: {len(config.usernames)} creators, {config.videos_per_creator} videos each")

        # Stage timing metrics
        stage_times = {}

        try:
            # Initialize LLM client
            llm_client = LLMClient(
                provider=config.llm_provider,
                model=config.llm_model
            )

            # Stage 0 & 1: Scrape and transcribe
            stage_start = time.time()
            progress.status = JobStatus.SCRAPING
            progress.phase = "Scraping videos..."
            self._notify(on_progress, progress)

            transcripts = self._scrape_and_transcribe(
                config=config,
                progress=progress,
                on_progress=on_progress
            )
            stage_times['scrape_transcribe'] = time.time() - stage_start
            logger.info("SKELETON", f"Stage 1 (Scrape/Transcribe) complete: {stage_times['scrape_transcribe']:.2f}s")

            # Check validity threshold
            valid_count = sum(1 for t in transcripts if is_valid_transcript(t.get('transcript', '')))
            progress.valid_transcripts = valid_count
            self._notify(on_progress, progress)

            valid_ratio = valid_count / len(transcripts) if transcripts else 0
            if valid_ratio < config.min_valid_ratio:
                logger.warning(
                    "SKELETON",
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
            stage_start = time.time()
            progress.status = JobStatus.EXTRACTING
            progress.phase = "Extracting content skeletons..."
            self._notify(on_progress, progress)

            extractor = BatchedExtractor(llm_client)
            extraction_result = extractor.extract_all(
                valid_transcripts,
                on_progress=lambda done, total, batch, total_batches: self._update_extraction_progress(
                    progress, done, total, batch, total_batches, on_progress
                )
            )

            result.skeletons = extraction_result.successful
            progress.skeletons_extracted = len(extraction_result.successful)
            stage_times['extraction'] = time.time() - stage_start
            logger.info("SKELETON", f"Stage 2 (Extraction) complete: {stage_times['extraction']:.2f}s, {len(result.skeletons)} skeletons")

            if extraction_result.failed_video_ids:
                progress.errors.append(
                    f"Failed to extract: {', '.join(extraction_result.failed_video_ids)}"
                )

            if not result.skeletons:
                raise ValueError("No skeletons extracted successfully")

            # Stage 3: Aggregation
            stage_start = time.time()
            progress.status = JobStatus.AGGREGATING
            progress.phase = "Aggregating patterns..."
            progress.message = f"Analyzing {len(result.skeletons)} skeletons..."
            self._notify(on_progress, progress)

            aggregator = SkeletonAggregator()
            result.aggregated = aggregator.aggregate(result.skeletons)
            stage_times['aggregation'] = time.time() - stage_start
            logger.info("SKELETON", f"Stage 3 (Aggregation) complete: {stage_times['aggregation']:.2f}s")
            progress.message = "Patterns aggregated"
            self._notify(on_progress, progress)

            # Stage 4: Synthesis
            stage_start = time.time()
            progress.status = JobStatus.SYNTHESIZING
            progress.phase = "Synthesizing content strategy..."
            progress.message = "Calling LLM for synthesis..."
            self._notify(on_progress, progress)

            synthesizer = PatternSynthesizer(llm_client)
            result.synthesis = synthesizer.synthesize(result.aggregated)
            stage_times['synthesis'] = time.time() - stage_start
            logger.info("SKELETON", f"Stage 4 (Synthesis) complete: {stage_times['synthesis']:.2f}s")

            if not result.synthesis.success:
                progress.errors.append(f"Synthesis failed: {result.synthesis.error}")
                logger.error("SKELETON", f"Synthesis failed: {result.synthesis.error}")

            # Stage 5: Output
            stage_start = time.time()
            progress.phase = "Generating report..."
            progress.message = "Saving outputs..."
            self._notify(on_progress, progress)

            output_paths = self._save_outputs(job_id, config, result)
            result.report_path = output_paths.get('report')
            result.skeletons_path = output_paths.get('skeletons')
            result.synthesis_path = output_paths.get('synthesis')
            stage_times['output'] = time.time() - stage_start
            logger.info("SKELETON", f"Stage 5 (Output) complete: {stage_times['output']:.2f}s")

            # Complete - log total timing
            total_time = sum(stage_times.values())
            progress.status = JobStatus.COMPLETE
            progress.phase = "Analysis Complete"
            progress.message = f"✓ {len(result.skeletons)} skeletons extracted from {len(config.usernames)} creator(s)"
            progress.completed_at = datetime.utcnow().isoformat()
            result.success = True

            logger.info("SKELETON", f"Job {job_id} complete: {len(result.skeletons)} skeletons extracted")
            logger.info("SKELETON", f"Total time: {total_time:.2f}s | Scrape: {stage_times.get('scrape_transcribe', 0):.1f}s | Extract: {stage_times.get('extraction', 0):.1f}s | Aggregate: {stage_times.get('aggregation', 0):.1f}s | Synthesize: {stage_times.get('synthesis', 0):.1f}s | Output: {stage_times.get('output', 0):.1f}s")

        except Exception as e:
            logger.error("SKELETON", f"Pipeline failed: {e}")
            logger.debug("SKELETON", f"Stack trace:\n{traceback.format_exc()}")
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
        Scrape videos and get transcripts using iterative approach.

        Strategy:
        1. Fetch 100 most recent reels (metadata only)
        2. Sort by views (highest first)
        3. Iterate through sorted list, download/transcribe one at a time
        4. Stop when we have N valid transcripts
        5. Cache valid transcripts for future runs
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

        # Load local Whisper model if needed (once for all creators)
        whisper_model = None
        if config.transcribe_provider == 'local' and WHISPER_AVAILABLE:
            progress.message = f"Loading Whisper model ({config.whisper_model})..."
            self._notify(on_progress, progress)
            whisper_model = load_whisper_model(config.whisper_model)
            if not whisper_model:
                logger.warning("SKELETON", "Failed to load Whisper model, falling back to OpenAI")
                config.transcribe_provider = 'openai'

        # Create authenticated session
        try:
            session = create_session(cookies_path)
        except Exception as e:
            raise RuntimeError(f"Failed to create session: {e}")

        # Setup temp directory for downloads
        temp_dir = self.base_dir / 'output' / 'skeleton_temp'
        temp_dir.mkdir(parents=True, exist_ok=True)

        for idx, username in enumerate(config.usernames):
            logger.info("SKELETON", f"Processing creator {idx + 1}/{len(config.usernames)}: @{username}")
            progress.current_creator = username
            progress.current_creator_index = idx + 1
            progress.current_video_index = 0
            progress.reels_fetched = 0
            progress.phase = f"Processing @{username} ({idx + 1}/{len(config.usernames)})"
            progress.message = "Checking cache..."
            self._notify(on_progress, progress)

            # Check cache for this creator first
            cached_transcripts = self._get_cached_transcripts(
                config.platform, username, config.videos_per_creator
            )

            if cached_transcripts and len(cached_transcripts) >= config.videos_per_creator:
                # Have enough cached - use those
                logger.info("SKELETON", f"Using {len(cached_transcripts)} cached transcripts for @{username}")
                progress.message = f"Using {len(cached_transcripts)} cached transcripts"
                progress.transcripts_from_cache += len(cached_transcripts)
                transcripts.extend(cached_transcripts[:config.videos_per_creator])
                progress.videos_scraped += len(cached_transcripts[:config.videos_per_creator])
                progress.videos_transcribed += len(cached_transcripts[:config.videos_per_creator])
                progress.videos_downloaded += len(cached_transcripts[:config.videos_per_creator])
                self._notify(on_progress, progress)
                continue

            # Fetch reel metadata (100 most recent, no download)
            progress.message = f"Fetching reels from @{username}..."
            self._notify(on_progress, progress)

            try:
                reels, profile, error = get_user_reels(session, username, max_reels=100)

                if error:
                    logger.warning("SKELETON", f"Failed to fetch reels for @{username}: {error}")
                    progress.errors.append(f"@{username}: {error}")
                    continue

                if not reels:
                    logger.warning("SKELETON", f"No reels found for @{username}")
                    progress.errors.append(f"@{username}: No reels found")
                    continue

                progress.videos_scraped += len(reels)
                progress.reels_fetched = len(reels)
                progress.message = f"Found {len(reels)} reels, sorting by views..."
                self._notify(on_progress, progress)
                logger.info("SKELETON", f"Found {len(reels)} reels for @{username}, sorting by views...")

            except Exception as e:
                logger.error("SKELETON", f"Error fetching reels for @{username}: {e}")
                logger.debug("SKELETON", f"Stack trace:\n{traceback.format_exc()}")
                progress.errors.append(f"@{username}: {str(e)}")
                continue

            # Sort by views (highest first)
            reels_sorted = sorted(reels, key=lambda x: x.get('views', 0), reverse=True)

            # Iterate through sorted reels until we have enough valid transcripts
            valid_count = 0
            attempted = 0

            for reel in reels_sorted:
                if valid_count >= config.videos_per_creator:
                    break  # Have enough valid transcripts

                video_id = reel.get('shortcode', 'unknown')
                attempted += 1
                views_display = f"{reel.get('views', 0):,}"

                # Check if already cached
                cached = self.cache.get(config.platform, username, video_id)
                if cached and is_valid_transcript(cached):
                    logger.debug("SKELETON", f"Cache hit for {video_id}")
                    valid_count += 1
                    progress.current_video_index = valid_count
                    progress.message = f"Video {valid_count}/{config.videos_per_creator}: Using cached transcript ({views_display} views)"
                    transcripts.append({
                        'video_id': video_id,
                        'username': username,
                        'platform': config.platform,
                        'views': reel.get('views', 0),
                        'likes': reel.get('likes', 0),
                        'url': reel.get('url', ''),
                        'video_url': reel.get('video_url', ''),
                        'transcript': cached,
                        'from_cache': True
                    })
                    progress.transcripts_from_cache += 1
                    progress.videos_transcribed += 1
                    progress.videos_downloaded += 1
                    self._notify(on_progress, progress)
                    continue

                # Need to download and transcribe
                progress.current_video_index = valid_count + 1
                progress.message = f"Video {valid_count + 1}/{config.videos_per_creator}: Downloading... ({views_display} views, attempt #{attempted})"
                self._notify(on_progress, progress)

                # Download video
                video_path = temp_dir / f"{username}_{video_id}.mp4"
                try:
                    download_success = download_video(
                        reel_url=reel.get('url', ''),
                        output_path=str(video_path),
                        cookies_file=cookies_path,
                        video_url=reel.get('video_url')
                    )

                    if not download_success or not video_path.exists():
                        logger.warning("SKELETON", f"Download failed for {video_id}, trying next...")
                        progress.message = f"Video {valid_count + 1}/{config.videos_per_creator}: Download failed, trying next..."
                        self._notify(on_progress, progress)
                        continue

                except Exception as e:
                    logger.warning("SKELETON", f"Download error for {video_id}: {e}")
                    progress.message = f"Video {valid_count + 1}/{config.videos_per_creator}: Download error, trying next..."
                    self._notify(on_progress, progress)
                    continue

                # Downloaded successfully - update count and show transcription status
                progress.videos_downloaded += 1
                progress.message = f"Video {valid_count + 1}/{config.videos_per_creator}: Transcribing... ({views_display} views)"
                self._notify(on_progress, progress)

                # Transcribe video
                transcript_text = None
                try:
                    if config.transcribe_provider == 'openai' and openai_key:
                        transcript_text = transcribe_video_openai(
                            video_path=str(video_path),
                            api_key=openai_key
                        )
                    elif whisper_model:
                        transcript_text = transcribe_video(
                            video_path=str(video_path),
                            model=whisper_model
                        )
                    else:
                        logger.warning("SKELETON", f"No transcription method available for {video_id}")
                        continue

                except Exception as e:
                    logger.warning("SKELETON", f"Transcription error for {video_id}: {e}")
                    transcript_text = None

                # Clean up video file
                try:
                    if video_path.exists():
                        video_path.unlink()
                except OSError as cleanup_err:
                    logger.debug("SKELETON", f"Failed to cleanup temp file {video_path}: {cleanup_err}")

                # Validate transcript
                if transcript_text and is_valid_transcript(transcript_text):
                    # Cache for future use
                    self.cache.set(config.platform, username, video_id, transcript_text)

                    transcripts.append({
                        'video_id': video_id,
                        'username': username,
                        'platform': config.platform,
                        'views': reel.get('views', 0),
                        'likes': reel.get('likes', 0),
                        'url': reel.get('url', ''),
                        'video_url': reel.get('video_url', ''),
                        'transcript': transcript_text,
                        'from_cache': False
                    })
                    valid_count += 1
                    progress.videos_transcribed += 1
                    progress.current_video_index = valid_count
                    progress.message = f"Video {valid_count}/{config.videos_per_creator}: ✓ Transcribed ({views_display} views)"
                    logger.info("SKELETON", f"Valid transcript #{valid_count} for @{username}: {video_id} ({reel.get('views', 0):,} views)")
                    self._notify(on_progress, progress)
                else:
                    progress.message = f"Video {valid_count + 1}/{config.videos_per_creator}: Invalid transcript, trying next..."
                    self._notify(on_progress, progress)
                    logger.debug("SKELETON", f"Invalid/empty transcript for {video_id}, trying next...")

            if valid_count < config.videos_per_creator:
                logger.warning(
                    "SKELETON",
                    f"Only got {valid_count}/{config.videos_per_creator} valid transcripts "
                    f"for @{username} after trying {attempted} videos"
                )
                progress.errors.append(
                    f"@{username}: Only {valid_count}/{config.videos_per_creator} valid transcripts"
                )

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
                logger.warning("SKELETON", f"Failed to read cache file {cache_file}: {e}")

        return cached

    def _update_extraction_progress(
        self,
        progress: JobProgress,
        done: int,
        total: int,
        batch: int,
        total_batches: int,
        on_progress: Optional[Callable]
    ):
        """Update extraction progress count with batch info."""
        progress.skeletons_extracted = done
        progress.extraction_batch = batch
        progress.extraction_total_batches = total_batches
        progress.message = f"Extracting skeletons: batch {batch}/{total_batches} ({done}/{total} done)"
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
                logger.warning("SKELETON", f"Progress callback error: {e}")

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

        logger.info("SKELETON", f"Saved outputs to {job_dir}")
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
