"""
ReelRecon - Persistent Scrape State Manager
File-based state persistence to survive server restarts
"""

import os
import json
import time
import threading
from datetime import datetime
from pathlib import Path
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict, field


class ScrapePhase(Enum):
    """Phases of a scrape operation for progress tracking"""
    INITIALIZING = "initializing"
    AUTHENTICATING = "authenticating"
    FETCHING_PROFILE = "fetching_profile"
    DISCOVERING_CONTENT = "discovering_content"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    PROCESSING = "processing"
    FINALIZING = "finalizing"
    COMPLETE = "complete"
    ERROR = "error"
    ABORTED = "aborted"


class ScrapeState(Enum):
    """Overall state of a scrape job"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"
    PARTIAL = "partial"  # Completed with some errors
    ABORTED = "aborted"


@dataclass
class ScrapeProgress:
    """Detailed progress tracking for a scrape"""
    phase: ScrapePhase = ScrapePhase.INITIALIZING
    phase_progress: int = 0  # 0-100 within current phase
    overall_progress: int = 0  # 0-100 overall
    current_item: int = 0
    total_items: int = 0
    message: str = ""
    started_at: str = ""
    updated_at: str = ""
    errors: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ScrapeJob:
    """Complete scrape job record"""
    id: str
    username: str
    platform: str
    state: ScrapeState = ScrapeState.QUEUED
    progress: ScrapeProgress = field(default_factory=ScrapeProgress)
    config: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str = ""
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['state'] = self.state.value
        data['progress']['phase'] = self.progress.phase.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScrapeJob':
        """Create from dictionary"""
        progress_data = data.get('progress', {})
        progress = ScrapeProgress(
            phase=ScrapePhase(progress_data.get('phase', 'initializing')),
            phase_progress=progress_data.get('phase_progress', 0),
            overall_progress=progress_data.get('overall_progress', 0),
            current_item=progress_data.get('current_item', 0),
            total_items=progress_data.get('total_items', 0),
            message=progress_data.get('message', ''),
            started_at=progress_data.get('started_at', ''),
            updated_at=progress_data.get('updated_at', ''),
            errors=progress_data.get('errors', [])
        )

        return cls(
            id=data['id'],
            username=data['username'],
            platform=data['platform'],
            state=ScrapeState(data.get('state', 'queued')),
            progress=progress,
            config=data.get('config', {}),
            result=data.get('result'),
            error_code=data.get('error_code'),
            error_message=data.get('error_message'),
            created_at=data.get('created_at', ''),
            completed_at=data.get('completed_at')
        )


class ScrapeStateManager:
    """
    Persistent state manager for scrape jobs.
    Survives server restarts by persisting to disk.
    """

    def __init__(self, state_dir: Optional[Path] = None):
        self.state_dir = state_dir or Path(__file__).parent.parent / "state"
        self.state_dir.mkdir(exist_ok=True)

        self.state_file = self.state_dir / "active_scrapes.json"
        self.archive_file = self.state_dir / "scrape_archive.json"

        self._lock = threading.RLock()
        self._jobs: Dict[str, ScrapeJob] = {}
        self._memory_cache: Dict[str, Dict] = {}  # Fast lookup for active scrapes

        # Load existing state on startup
        self._load_state()

        # Clean up stale jobs (running jobs that crashed)
        self._recover_crashed_jobs()

    def _load_state(self):
        """Load persisted state from disk"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for job_data in data.get('jobs', []):
                    try:
                        job = ScrapeJob.from_dict(job_data)
                        self._jobs[job.id] = job
                    except Exception as e:
                        print(f"[StateManager] Failed to load job: {e}")
            except Exception as e:
                print(f"[StateManager] Failed to load state file: {e}")

    def _save_state(self):
        """Persist current state to disk (atomic write)"""
        temp_file = self.state_file.with_suffix('.tmp')
        try:
            data = {
                'updated_at': datetime.now().isoformat(),
                'jobs': [job.to_dict() for job in self._jobs.values()]
            }

            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Atomic rename
            temp_file.replace(self.state_file)
        except Exception as e:
            print(f"[StateManager] Failed to save state: {e}")
            if temp_file.exists():
                temp_file.unlink()

    def _recover_crashed_jobs(self):
        """Mark jobs that were running when server crashed as error state"""
        for job_id, job in self._jobs.items():
            if job.state == ScrapeState.RUNNING:
                job.state = ScrapeState.ERROR
                job.error_code = "SRV-CRASH"
                job.error_message = "Server restarted while scrape was in progress. Please retry."
                job.progress.phase = ScrapePhase.ERROR
                job.progress.message = "Server restarted unexpectedly"
                job.progress.updated_at = datetime.now().isoformat()

        self._save_state()

    def create_job(self, scrape_id: str, username: str, platform: str,
                   config: Optional[Dict] = None) -> ScrapeJob:
        """Create a new scrape job"""
        with self._lock:
            now = datetime.now().isoformat()
            job = ScrapeJob(
                id=scrape_id,
                username=username,
                platform=platform,
                state=ScrapeState.QUEUED,
                config=config or {},
                created_at=now,
                progress=ScrapeProgress(
                    phase=ScrapePhase.INITIALIZING,
                    message=f"Initializing {platform.title()} scrape...",
                    started_at=now,
                    updated_at=now
                )
            )

            self._jobs[scrape_id] = job
            self._save_state()
            return job

    def get_job(self, scrape_id: str) -> Optional[ScrapeJob]:
        """Get a scrape job by ID"""
        with self._lock:
            return self._jobs.get(scrape_id)

    def update_progress(self, scrape_id: str, phase: ScrapePhase, progress_pct: int,
                        message: str, current_item: int = 0, total_items: int = 0):
        """Update job progress"""
        with self._lock:
            job = self._jobs.get(scrape_id)
            if not job:
                return

            # Calculate overall progress based on phase
            phase_weights = {
                ScrapePhase.INITIALIZING: 0,
                ScrapePhase.AUTHENTICATING: 5,
                ScrapePhase.FETCHING_PROFILE: 10,
                ScrapePhase.DISCOVERING_CONTENT: 25,
                ScrapePhase.DOWNLOADING: 50,
                ScrapePhase.TRANSCRIBING: 80,
                ScrapePhase.PROCESSING: 90,
                ScrapePhase.FINALIZING: 95,
                ScrapePhase.COMPLETE: 100,
            }

            base_progress = phase_weights.get(phase, 0)
            next_phase = list(phase_weights.keys())[list(phase_weights.values()).index(base_progress) + 1] if base_progress < 100 else phase
            next_progress = phase_weights.get(next_phase, 100)
            phase_range = next_progress - base_progress

            overall = base_progress + int((progress_pct / 100) * phase_range)

            job.progress.phase = phase
            job.progress.phase_progress = progress_pct
            job.progress.overall_progress = min(overall, 100)
            job.progress.current_item = current_item
            job.progress.total_items = total_items
            job.progress.message = message
            job.progress.updated_at = datetime.now().isoformat()

            if job.state == ScrapeState.QUEUED:
                job.state = ScrapeState.RUNNING

            self._save_state()

    def add_error(self, scrape_id: str, error_code: str, error_message: str,
                  is_fatal: bool = False):
        """Add an error to the job"""
        with self._lock:
            job = self._jobs.get(scrape_id)
            if not job:
                return

            job.progress.errors.append({
                "code": error_code,
                "message": error_message,
                "timestamp": datetime.now().isoformat(),
                "fatal": is_fatal
            })

            if is_fatal:
                job.state = ScrapeState.ERROR
                job.error_code = error_code
                job.error_message = error_message
                job.progress.phase = ScrapePhase.ERROR
                job.progress.message = f"Error [{error_code}]: {error_message}"
                job.completed_at = datetime.now().isoformat()

            self._save_state()

    def complete_job(self, scrape_id: str, result: Dict[str, Any],
                     had_errors: bool = False):
        """Mark job as complete"""
        with self._lock:
            job = self._jobs.get(scrape_id)
            if not job:
                return

            job.state = ScrapeState.PARTIAL if had_errors else ScrapeState.COMPLETE
            job.result = result
            job.progress.phase = ScrapePhase.COMPLETE
            job.progress.overall_progress = 100
            job.progress.message = "Scrape complete"
            job.progress.updated_at = datetime.now().isoformat()
            job.completed_at = datetime.now().isoformat()

            self._save_state()

    def fail_job(self, scrape_id: str, error_code: str, error_message: str):
        """Mark job as failed"""
        with self._lock:
            job = self._jobs.get(scrape_id)
            if not job:
                return

            job.state = ScrapeState.ERROR
            job.error_code = error_code
            job.error_message = error_message
            job.progress.phase = ScrapePhase.ERROR
            job.progress.message = f"Error [{error_code}]: {error_message}"
            job.progress.updated_at = datetime.now().isoformat()
            job.completed_at = datetime.now().isoformat()

            self._save_state()

    def abort_job(self, scrape_id: str, reason: str = "User cancelled"):
        """Abort a running job"""
        with self._lock:
            job = self._jobs.get(scrape_id)
            if not job:
                return

            job.state = ScrapeState.ABORTED
            job.progress.phase = ScrapePhase.ABORTED
            job.progress.message = reason
            job.progress.updated_at = datetime.now().isoformat()
            job.completed_at = datetime.now().isoformat()

            self._save_state()

    def get_job_status(self, scrape_id: str) -> Optional[Dict[str, Any]]:
        """Get job status for API response"""
        with self._lock:
            job = self._jobs.get(scrape_id)
            if not job:
                return None

            return {
                'status': job.state.value,
                'progress': job.progress.message,
                'progress_pct': job.progress.overall_progress,
                'phase': job.progress.phase.value,
                'current_item': job.progress.current_item,
                'total_items': job.progress.total_items,
                'errors': job.progress.errors,
                'result': job.result,
                'error_code': job.error_code,
                'error_message': job.error_message
            }

    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove completed/failed jobs older than max_age_hours"""
        with self._lock:
            cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
            to_remove = []

            for job_id, job in self._jobs.items():
                if job.state in (ScrapeState.COMPLETE, ScrapeState.ERROR,
                                 ScrapeState.PARTIAL, ScrapeState.ABORTED):
                    if job.completed_at:
                        try:
                            completed_ts = datetime.fromisoformat(job.completed_at).timestamp()
                            if completed_ts < cutoff:
                                to_remove.append(job_id)
                        except:
                            pass

            for job_id in to_remove:
                del self._jobs[job_id]

            if to_remove:
                self._save_state()

    def get_active_jobs(self) -> List[Dict[str, Any]]:
        """Get all active (running/queued) jobs"""
        with self._lock:
            return [
                job.to_dict() for job in self._jobs.values()
                if job.state in (ScrapeState.QUEUED, ScrapeState.RUNNING)
            ]

    def get_recent_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get most recent jobs"""
        with self._lock:
            jobs = sorted(
                self._jobs.values(),
                key=lambda j: j.created_at,
                reverse=True
            )
            return [j.to_dict() for j in jobs[:limit]]
