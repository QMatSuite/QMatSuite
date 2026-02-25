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
from concurrent.futures import ThreadPoolExecutor, Future

import ulid
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
    
    Jobs are created when long-running operations (like calculation execution)
    are submitted. They track status, start/end times, results, and errors.
    """
    id: str
    job_type: str  # e.g., "run_calculation", "run_step"
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
    target_name: Optional[str] = None  # e.g., calculation name, step name
    project_root: Optional[str] = None
    
    # Output file for log reading
    output_file: Optional[str] = None
    
    # Last log line (for quick status display)
    last_log_line: Optional[str] = None

    # Install/download progress (for engine install jobs)
    progress_pct: Optional[float] = None       # 0.0–100.0
    progress_bytes: Optional[int] = None       # bytes downloaded so far
    progress_total: Optional[int] = None       # total bytes (None if unknown)
    progress_stage: Optional[str] = None       # e.g., "Downloading micromamba"

    # I/O directory (the actual directory used by the runner to write QE input/output and artifacts)
    io_dir: Optional[str] = None
    
    # Step progress info (initialized at job creation, updated during execution)
    steps: Optional[List[Dict[str, Any]]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to JSON-serializable dict."""
        return {
            "ulid": self.id,
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
            "progress_pct": self.progress_pct,
            "progress_bytes": self.progress_bytes,
            "progress_total": self.progress_total,
            "progress_stage": self.progress_stage,
            "io_dir": self.io_dir,
            "steps": self.steps,
        }
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Convert job to a summary dict (less detail, for list views)."""
        result = {
            "ulid": self.id,
            "job_type": self.job_type,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "target_name": self.target_name,
            "project_root": self.project_root,
            "error": self.error[:200] if self.error and len(self.error) > 200 else self.error,
            "last_log_line": self.last_log_line,
            "progress_pct": self.progress_pct,
            "progress_bytes": self.progress_bytes,
            "progress_total": self.progress_total,
            "progress_stage": self.progress_stage,
            "steps": self.steps,  # Include steps for step progress visualization
        }
        return result


class JobManager:
    """
    Manages background job execution.
    
    Uses ThreadPoolExecutor with max_workers=1 to ensure sequential execution
    of QE jobs (only one QE calculation runs at a time).
    
    The daemon main loop remains responsive while jobs execute in the background.
    Job results/status live in memory; project/calculation data lives on disk.
    """
    
    def __init__(self, max_workers: int = 1):
        """
        Initialize the job manager.
        
        Args:
            max_workers: Maximum concurrent jobs (default 1 for sequential execution)
        """
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="qms-job")
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
        initial_steps: Optional[List[Dict[str, Any]]] = None,
        initial_io_dir: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Submit a job for background execution.
        
        Args:
            job_type: Type of job (e.g., "run_calculation")
            func: Function to execute (should return Dict[str, Any])
            params: Parameters to store with job (for reference)
            target_name: Human-readable target name (e.g., calculation name)
            project_root_display: Project root path (for display only)
            **kwargs: Arguments to pass to func
            
        Returns:
            Job ID
        """
        job_id = str(ulid.new())
        
        # Initialize steps if provided (for calculation jobs, steps are known at creation time)
        steps = initial_steps or []
        
        # Initialize io_dir if provided (so it shows immediately in UI, even before execution starts)
        io_dir = None
        if initial_io_dir:
            # Ensure absolute path
            io_dir_path = Path(initial_io_dir)
            if not io_dir_path.is_absolute() and project_root_display:
                io_dir_path = Path(project_root_display) / io_dir_path
            io_dir = str(io_dir_path.resolve())
        
        job = Job(
            id=job_id,
            job_type=job_type,
            params=params,
            target_name=target_name,
            project_root=project_root_display,
            steps=steps if steps else None,
            io_dir=io_dir,
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
                
                # Convert DTO to dict if needed
                if hasattr(result, 'to_dict'):
                    result = result.to_dict()
                elif not isinstance(result, dict):
                    # Fallback: try to convert using asdict if it's a dataclass
                    from dataclasses import asdict
                    try:
                        result = asdict(result)
                    except (TypeError, ValueError):
                        # Last resort: convert to string representation
                        result = {"error": f"Cannot serialize result type: {type(result).__name__}"}
                
                # Try to extract output file and io_dir from result
                if isinstance(result, dict):
                    output_file = result.get("output_file") or result.get("last_output_file")
                    if output_file:
                        with self._lock:
                            job.output_file = str(output_file)
                        # Try to read last log line
                        self._update_last_log_line(job)
                    
                    # Extract io_dir from result (normalize legacy keys for backward compatibility)
                    # Runner is the source of truth - it returns the actual I/O directory used
                    final_io_dir = (
                        result.get("io_dir") or 
                        result.get("working_dir") or 
                        result.get("work_dir") or 
                        result.get("raw_dir")
                    )
                    if final_io_dir:
                        # Ensure absolute path
                        io_dir_path = Path(final_io_dir)
                        if not io_dir_path.is_absolute():
                            # If relative, try to resolve relative to project_root if available
                            if job.project_root:
                                io_dir_path = Path(job.project_root) / io_dir_path
                            io_dir_path = io_dir_path.resolve()
                        final_io_dir_str = str(io_dir_path)
                        
                        # Check if planned_io_dir (from job creation) differs from final io_dir (from runner)
                        # This should be rare, but log a warning if it happens
                        if job.io_dir and job.io_dir != final_io_dir_str:
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.warning(
                                f"[WARN] job {job.id} planned io_dir != final io_dir: "
                                f"planned={job.io_dir}, final={final_io_dir_str}"
                            )
                        
                        with self._lock:
                            # Runner is source of truth - update to final value
                            job.io_dir = final_io_dir_str
                    
                    # Update steps status from result (if steps were initialized)
                    # This allows step progress to update during execution
                    if job.steps and "steps" in result:
                        result_steps = result["steps"]
                        if isinstance(result_steps, list):
                            with self._lock:
                                # Update existing steps with status from result
                                # Match by step_ulid or step_type
                                for job_step in job.steps:
                                    step_ulid = job_step.get("step_ulid")
                                    step_type = job_step.get("step_type_spec")
                                    # Find matching step in result
                                    for result_step in result_steps:
                                        result_step_ulid = result_step.get("step_ulid")
                                        result_step_type = result_step.get("step_type_spec")
                                        # Match by step_ulid (preferred) or step_type (fallback)
                                        if (step_ulid and result_step_ulid and step_ulid == result_step_ulid) or \
                                           (step_type and result_step_type and step_type == result_step_type):
                                            # Update status and timestamps
                                            job_step["status"] = result_step.get("status", job_step.get("status", "pending"))
                                            # Note: result steps may not have started_at/ended_at, preserve existing if not provided
                                            if "started_at" in result_step:
                                                job_step["started_at"] = result_step.get("started_at")
                                            if "ended_at" in result_step or "completed_at" in result_step:
                                                job_step["ended_at"] = result_step.get("ended_at") or result_step.get("completed_at")
                                            break
                
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
    
    def submit_with_id(
        self,
        job_id: str,
        job_type: str,
        func: Callable[..., Dict[str, Any]],
        params: Dict[str, Any],
        target_name: Optional[str] = None,
        project_root_display: Optional[str] = None,
        initial_steps: Optional[List[Dict[str, Any]]] = None,
        initial_io_dir: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Submit a job with a specific ID for background execution.
        
        This method is used when the job_id must equal a history run_ulid,
        ensuring job_id == run_ulid identity for the Jobs ↔ History unification.
        
        Args:
            job_id: The specific job ID to use (typically a ULID)
            job_type: Type of job (e.g., "run_calculation")
            func: Function to execute (should return Dict[str, Any])
            params: Parameters to store with job (for reference)
            target_name: Human-readable target name (e.g., calculation name)
            project_root_display: Project root path (for display only)
            initial_steps: Initial step status list
            initial_io_dir: Initial I/O directory path
            **kwargs: Arguments to pass to func
            
        Returns:
            Job ID (same as input job_id)
        """
        # Initialize steps if provided
        steps = initial_steps or []
        
        # Initialize io_dir if provided
        io_dir = None
        if initial_io_dir:
            io_dir_path = Path(initial_io_dir)
            if not io_dir_path.is_absolute() and project_root_display:
                io_dir_path = Path(project_root_display) / io_dir_path
            io_dir = str(io_dir_path.resolve())
        
        job = Job(
            id=job_id,
            job_type=job_type,
            params=params,
            target_name=target_name,
            project_root=project_root_display,
            steps=steps if steps else None,
            io_dir=io_dir,
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
                
                # Convert DTO to dict if needed
                if hasattr(result, 'to_dict'):
                    result = result.to_dict()
                elif not isinstance(result, dict):
                    # Fallback: try to convert using asdict if it's a dataclass
                    from dataclasses import asdict
                    try:
                        result = asdict(result)
                    except (TypeError, ValueError):
                        # Last resort: convert to string representation
                        result = {"error": f"Cannot serialize result type: {type(result).__name__}"}
                
                # Try to extract output file and io_dir from result
                if isinstance(result, dict):
                    output_file = result.get("output_file") or result.get("last_output_file")
                    if output_file:
                        with self._lock:
                            job.output_file = str(output_file)
                        self._update_last_log_line(job)
                    
                    # Extract io_dir from result
                    final_io_dir = (
                        result.get("io_dir") or 
                        result.get("working_dir") or 
                        result.get("work_dir") or 
                        result.get("raw_dir")
                    )
                    if final_io_dir:
                        io_dir_path = Path(final_io_dir)
                        if not io_dir_path.is_absolute():
                            if job.project_root:
                                io_dir_path = Path(job.project_root) / io_dir_path
                            io_dir_path = io_dir_path.resolve()
                        final_io_dir_str = str(io_dir_path)
                        
                        if job.io_dir and job.io_dir != final_io_dir_str:
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.warning(
                                f"[WARN] job {job.id} planned io_dir != final io_dir: "
                                f"planned={job.io_dir}, final={final_io_dir_str}"
                            )
                        
                        with self._lock:
                            job.io_dir = final_io_dir_str
                    
                    # Update steps status from result
                    if job.steps and "steps" in result:
                        result_steps = result["steps"]
                        if isinstance(result_steps, list):
                            with self._lock:
                                for job_step in job.steps:
                                    step_ulid = job_step.get("step_ulid")
                                    step_type = job_step.get("step_type_spec")
                                    for result_step in result_steps:
                                        result_step_ulid = result_step.get("step_ulid")
                                        result_step_type = result_step.get("step_type_spec")
                                        if (step_ulid and result_step_ulid and step_ulid == result_step_ulid) or \
                                           (step_type and result_step_type and step_type == result_step_type):
                                            job_step["status"] = result_step.get("status", job_step.get("status", "pending"))
                                            if "started_at" in result_step:
                                                job_step["started_at"] = result_step.get("started_at")
                                            if "ended_at" in result_step or "completed_at" in result_step:
                                                job_step["ended_at"] = result_step.get("ended_at") or result_step.get("completed_at")
                                            break
                
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
            # Normalize project_root for comparison (handle trailing slashes, relative vs absolute)
            normalized_filter = str(Path(project_root).resolve())
            jobs = [
                j for j in jobs
                if j.project_root and str(Path(j.project_root).resolve()) == normalized_filter
            ]
        
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
