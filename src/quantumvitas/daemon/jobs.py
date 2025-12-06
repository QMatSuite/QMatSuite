"""
Job Manager for background QE execution.

Provides:
- JobManager with ThreadPoolExecutor(max_workers=1) for sequential execution
- Job tracking with status, results, errors, and logs
- Non-blocking submission and status polling
- Log tailing for running/completed jobs

All QE-invoking operations go through this manager to prevent blocking the daemon.
"""

from __future__ import annotations

import os
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
    
    # Job parameters (for reference and display)
    params: Dict[str, Any] = field(default_factory=dict)
    
    # Target info for display
    target_name: Optional[str] = None  # e.g., workflow name, step name
    project_root: Optional[str] = None
    
    # Output file for log reading
    output_file: Optional[str] = None
    
    # Last log line (for quick status display)
    last_log_line: Optional[str] = None
    
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
            "target_name": self.target_name,
            "project_root": self.project_root,
            "output_file": self.output_file,
            "last_log_line": self.last_log_line,
        }
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Convert job to a summary dict (less detail, for list views)."""
        return {
            "id": self.id,
            "job_type": self.job_type,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "target_name": self.target_name,
            "project_root": self.project_root,
            "error": self.error[:200] if self.error and len(self.error) > 200 else self.error,
            "last_log_line": self.last_log_line,
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
        target_name: Optional[str] = None,
        project_root_display: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Submit a job for background execution.
        
        Args:
            job_type: Type of job (e.g., "run_workflow")
            func: Function to execute (should return Dict[str, Any])
            params: Parameters to store with job (for reference)
            target_name: Human-readable target name (e.g., workflow name)
            project_root_display: Project root path (for display only)
            **kwargs: Arguments to pass to func
            
        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())
        
        job = Job(
            id=job_id,
            job_type=job_type,
            params=params,
            target_name=target_name,
            project_root=project_root_display,
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
                
                # Try to extract output file from result for log reading
                if isinstance(result, dict):
                    output_file = result.get("output_file") or result.get("last_output_file")
                    if output_file:
                        with self._lock:
                            job.output_file = str(output_file)
                        # Try to read last log line
                        self._update_last_log_line(job)
                
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
    
    def _update_last_log_line(self, job: Job) -> None:
        """Update the last_log_line field by reading the output file."""
        if not job.output_file:
            return
        
        try:
            path = Path(job.output_file)
            if path.exists():
                # Read last non-empty line
                with open(path, 'r') as f:
                    lines = f.readlines()
                    for line in reversed(lines):
                        stripped = line.strip()
                        if stripped:
                            job.last_log_line = stripped[:200]  # Limit length
                            break
        except Exception:
            pass
    
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
        
        # Update last log line for running jobs
        if job.status == JobStatus.RUNNING:
            self._update_last_log_line(job)
        
        return job.to_dict()
    
    def get_job_logs(
        self,
        job_id: str,
        tail_lines: int = 100,
        offset: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """
        Get logs for a job.
        
        Args:
            job_id: Job ID
            tail_lines: Number of lines to return (from end if offset=0)
            offset: Line offset (0 = from end, positive = from start)
            
        Returns:
            Dict with logs, total_lines, and has_more
        """
        job = self.get_job(job_id)
        if job is None:
            return None
        
        if not job.output_file:
            return {
                "job_id": job_id,
                "logs": [],
                "total_lines": 0,
                "has_more": False,
                "output_file": None,
            }
        
        path = Path(job.output_file)
        if not path.exists():
            return {
                "job_id": job_id,
                "logs": [],
                "total_lines": 0,
                "has_more": False,
                "output_file": str(job.output_file),
            }
        
        try:
            with open(path, 'r') as f:
                all_lines = f.readlines()
            
            total_lines = len(all_lines)
            
            if offset > 0:
                # Read from specific offset
                selected = all_lines[offset:offset + tail_lines]
                has_more = (offset + tail_lines) < total_lines
            else:
                # Tail from end
                if total_lines <= tail_lines:
                    selected = all_lines
                    has_more = False
                else:
                    selected = all_lines[-tail_lines:]
                    has_more = True
            
            # Strip trailing newlines
            logs = [line.rstrip('\n\r') for line in selected]
            
            return {
                "job_id": job_id,
                "logs": logs,
                "total_lines": total_lines,
                "has_more": has_more,
                "output_file": str(job.output_file),
            }
        except Exception as e:
            return {
                "job_id": job_id,
                "logs": [f"Error reading logs: {e}"],
                "total_lines": 0,
                "has_more": False,
                "output_file": str(job.output_file),
            }
    
    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        job_type: Optional[str] = None,
        project_root: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List jobs, optionally filtered by status, type, or project.
        
        Args:
            status: Filter by status
            job_type: Filter by job type
            project_root: Filter by project root
            limit: Maximum number of jobs to return
            
        Returns:
            List of job summary dicts
        """
        with self._lock:
            jobs = list(self._jobs.values())
        
        if status is not None:
            jobs = [j for j in jobs if j.status == status]
        if job_type is not None:
            jobs = [j for j in jobs if j.job_type == job_type]
        if project_root is not None:
            jobs = [j for j in jobs if j.project_root == project_root]
        
        # Sort by created_at (newest first)
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        
        # Limit results
        jobs = jobs[:limit]
        
        return [j.to_summary_dict() for j in jobs]
    
    def count_by_status(self) -> Dict[str, int]:
        """Get job counts by status."""
        with self._lock:
            counts = {}
            for status in JobStatus:
                counts[status.value] = sum(1 for j in self._jobs.values() if j.status == status)
            return counts
    
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
