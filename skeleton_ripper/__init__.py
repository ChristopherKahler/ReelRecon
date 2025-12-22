"""
Content Skeleton Ripper - Multi-creator content pattern analysis.

Usage:
    from skeleton_ripper import SkeletonRipperPipeline, create_job_config

    config = create_job_config(
        usernames=['creator1', 'creator2'],
        videos_per_creator=3,
        llm_provider='openai',
        llm_model='gpt-4o-mini'
    )

    pipeline = SkeletonRipperPipeline()
    result = pipeline.run(config)

    print(result.report_path)
"""

from .pipeline import (
    SkeletonRipperPipeline,
    JobConfig,
    JobProgress,
    JobResult,
    JobStatus,
    create_job_config,
    run_skeleton_ripper,
)
from .extractor import BatchedExtractor
from .synthesizer import PatternSynthesizer
from .aggregator import SkeletonAggregator
from .cache import TranscriptCache
from .llm_client import LLMClient, get_available_providers

__all__ = [
    # Main pipeline
    'SkeletonRipperPipeline',
    'JobConfig',
    'JobProgress',
    'JobResult',
    'JobStatus',
    'create_job_config',
    'run_skeleton_ripper',

    # Components
    'BatchedExtractor',
    'PatternSynthesizer',
    'SkeletonAggregator',
    'TranscriptCache',
    'LLMClient',

    # Utilities
    'get_available_providers',
]
