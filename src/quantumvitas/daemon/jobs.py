"""
Job Manager for background QE execution.

Provides:
- JobManager with ThreadPoolExecutor(max_workers=1) for sequential execution
- Job tracking with status, results, and errors
- Non-blocking submission and status polling

All QE-invoking operations go through this manager to prevent blocking the daemon.
"""

from __future__ import annotations

import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, List, Optional


class JobStatus(str, Enum):
    """Job execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """
    Represents a background job.
    
    Jobs are created when long-running operations (like workflow execution)
    are submitted. They track status, start/end times, results, and errors.
    """
    id: str
    job_type: str  # e.g., "run_workflow", "run_step"
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_traceback: Optional[str] = None
    
    # Job parameters (for reference)
    params: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to JSON-serializable dict."""
        return {
            "id": self.id,
            "job_type": self.job_type,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
            "params": self.params,
        }


class JobManager:
    """
    Manages background job execution.
    
    Uses ThreadPoolExecutor with max_workers=1 to ensure sequential execution
    of QE jobs (only one QE calculation runs at a time).
    
    The daemon main loop remains responsive while jobs execute in the background.
    Job results/status live in memory; project/workflow data lives on disk.
    """
    
    def __init__(self, max_workers: int = 1):
        """
        Initialize the job manager.
        
        Args:
            max_workers: Maximum concurrent jobs (default 1 for sequential execution)
        """
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="qv-job")
        self._jobs: Dict[str, Job] = {}
        self._futures: Dict[str, Future] = {}
        self._lock = Lock()
    
    def submit(
        self,
        job_type: str,
        func: Callable[..., Dict[str, Any]],
        params: Dict[str, Any],
        **kwargs,
    ) -> str:
        """
        Submit a job for background execution.
        
        Args:
            job_type: Type of job (e.g., "run_workflow")
            func: Function to execute (should return Dict[str, Any])
            params: Parameters to store with job (for reference)
            **kwargs: Arguments to pass to func
            
        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())
        
        job = Job(
            id=job_id,
            job_type=job_type,
            params=params,
        )
        
        with self._lock:
            self._jobs[job_id] = job
        
        # Wrapper function to handle execution and status updates
        def execute_job():
            with self._lock:
                job.status = JobStatus.RUNNING
                job.started_at = datetime.now(timezone.utc)
            
            try:
                result = func(**kwargs)
                
                with self._lock:
                    job.status = JobStatus.COMPLETED
                    job.completed_at = datetime.now(timezone.utc)
                    job.result = result
                    
            except Exception as e:
                with self._lock:
                    job.status = JobStatus.FAILED
                    job.completed_at = datetime.now(timezone.utc)
                    job.error = str(e)
                    job.error_traceback = traceback.format_exc()
        
        # Submit to executor
        future = self._executor.submit(execute_job)
        
        with self._lock:
            self._futures[job_id] = future
        
        return job_id
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        with self._lock:
            return self._jobs.get(job_id)
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job status as a dict.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job status dict, or None if job not found
        """
        job = self.get_job(job_id)
        if job is None:
            return None
        return job.to_dict()
    
    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        job_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List jobs, optionally filtered by status or type.
        
        Args:
            status: Filter by status
            job_type: Filter by job type
            
        Returns:
            List of job dicts
        """
        with self._lock:
            jobs = list(self._jobs.values())
        
        if status is not None:
            jobs = [j for j in jobs if j.status == status]
        if job_type is not None:
            jobs = [j for j in jobs if j.job_type == job_type]
        
        # Sort by created_at (newest first)
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        
        return [j.to_dict() for j in jobs]
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Attempt to cancel a job.
        
        IMPORTANT: Python's ThreadPoolExecutor cannot truly kill a running thread.
        This method can only cancel jobs that have not yet started (PENDING status).
        
        Behavior by status:
        - PENDING: Can be cancelled if the executor hasn't picked it up yet
        - RUNNING: Cannot be cancelled - the QE process will run to completion
        - COMPLETED/FAILED/CANCELLED: Already terminal, returns False
        
        For GUI: If you need to "cancel" a running QE job, you must:
        1. Kill the subprocess externally (not supported by this JobManager)
        2. Or wait for it to complete
        
        Args:
            job_id: Job ID
            
        Returns:
            True if job was successfully cancelled (was PENDING), False otherwise
        """
        with self._lock:
            job = self._jobs.get(job_id)
            future = self._futures.get(job_id)
            
            if job is None:
                return False
            
            # Only PENDING jobs can be cancelled
            if job.status == JobStatus.PENDING:
                if future and future.cancel():
                    job.status = JobStatus.CANCELLED
                    job.completed_at = datetime.now(timezone.utc)
                    return True
            
            # RUNNING, COMPLETED, FAILED, CANCELLED - cannot cancel
            return False
    
    def cleanup_completed(self, keep_last: int = 100) -> int:
        """
        Remove completed/failed/cancelled jobs from memory.
        
        Keeps the most recent `keep_last` jobs of each terminal status.
        
        Args:
            keep_last: Number of recent completed jobs to keep
            
        Returns:
            Number of jobs removed
        """
        with self._lock:
            terminal_statuses = {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
            
            # Separate active and terminal jobs
            active_jobs = {
                jid: job for jid, job in self._jobs.items()
                if job.status not in terminal_statuses
            }
            terminal_jobs = [
                (jid, job) for jid, job in self._jobs.items()
                if job.status in terminal_statuses
            ]
            
            # Sort terminal jobs by completion time and keep recent ones
            terminal_jobs.sort(key=lambda x: x[1].completed_at or x[1].created_at, reverse=True)
            kept_terminal = dict(terminal_jobs[:keep_last])
            
            removed_count = len(self._jobs) - len(active_jobs) - len(kept_terminal)
            
            # Rebuild jobs dict
            self._jobs = {**active_jobs, **kept_terminal}
            
            # Clean up futures for removed jobs
            self._futures = {
                jid: f for jid, f in self._futures.items()
                if jid in self._jobs
            }
            
            return removed_count
    
    def shutdown(self, wait: bool = True):
        """
        Shutdown the executor.
        
        Args:
            wait: If True, wait for running jobs to complete
        """
        self._executor.shutdown(wait=wait)

