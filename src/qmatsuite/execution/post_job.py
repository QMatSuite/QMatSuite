"""
Post-job actions: generic lifecycle stage for actions after job completion.

This module provides:
- PostJobAction abstract base class
- ArchiveToSlotAction for scan variant archiving
- Snapshot/diff utilities for raw directory
"""

from __future__ import annotations

import json
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PostJobContext:
    """Context for post-job actions."""

    calc_raw_dir: Path
    variant_key: Optional[str]
    run_ulid: str


class PostJobAction(ABC):
    """Abstract base class for post-job actions."""
    
    @abstractmethod
    def execute(self, job_result: Any, context: PostJobContext) -> None:
        """
        Execute the post-job action.
        
        Args:
            job_result: Job execution result (with success flag, etc.)
            context: Post-job context
        """
        pass


def snapshot_raw_dir(raw_dir: Path, exclude: Optional[List[str]] = None) -> Dict[str, float]:
    """
    Create a snapshot of raw directory (file listing with mtimes).
    
    Args:
        raw_dir: Path to raw directory
        exclude: List of directory names to exclude (e.g., ["outdir", "scan"])
        
    Returns:
        Dict mapping relative_path (str) to mtime (float)
    """
    if exclude is None:
        exclude = []
    
    result: Dict[str, float] = {}
    
    if not raw_dir.exists():
        return result
    
    for path in raw_dir.rglob("*"):
        if not path.is_file():
            continue
        
        rel_path = path.relative_to(raw_dir)
        rel_str = str(rel_path)
        
        # Skip excluded directories (check if any part of path starts with excluded dir)
        parts = rel_str.split("/")
        if any(parts[0] == ex for ex in exclude):
            continue
        
        # Get mtime
        try:
            mtime = path.stat().st_mtime
            result[rel_str] = mtime
        except OSError:
            # File may have been deleted, skip
            continue
    
    return result


def compute_snapshot_diff(
    before: Dict[str, float],
    after: Dict[str, float],
    exclude: Optional[List[str]] = None,
) -> List[str]:
    """
    Compute diff between two snapshots (new or modified files).
    
    Args:
        before: Snapshot before job execution
        after: Snapshot after job execution
        exclude: List of directory names to exclude
        
    Returns:
        List of relative paths that are new or modified
    """
    if exclude is None:
        exclude = []
    
    changed: List[str] = []
    
    for path, mtime in after.items():
        # Skip excluded paths
        parts = path.split("/")
        if any(parts[0] == ex for ex in exclude):
            continue
        
        # Check if new or modified
        if path not in before:
            # New file
            changed.append(path)
        elif before[path] < mtime:
            # Modified file (mtime increased)
            changed.append(path)
    
    return changed


@dataclass
class ArchiveToSlotAction(PostJobAction):
    """Archive job outputs to scan variant slot."""
    
    variant_key: str
    
    def execute(self, job_result: Any, context: PostJobContext) -> None:
        """
        Archive job outputs to raw/scan/<variant_key>/.
        
        Archives on both success and failure (best-effort).
        Records entry in slots.json bookkeeping file.
        """
        dest_dir = context.calc_raw_dir / "scan" / self.variant_key
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        # Get pre-snapshot from job_result if available
        pre_snapshot = getattr(job_result, "pre_snapshot", {})
        
        # Create post-snapshot
        post_snapshot = snapshot_raw_dir(context.calc_raw_dir, exclude=["outdir", "scan"])
        
        # Compute diff
        new_modified = compute_snapshot_diff(
            before=pre_snapshot,
            after=post_snapshot,
            exclude=["outdir", "scan"],
        )
        
        # Copy files to slot (best-effort, even on failure)
        copied_files: List[str] = []
        for rel_path in new_modified:
            src = context.calc_raw_dir / rel_path
            if not src.exists():
                continue
            
            dst = dest_dir / rel_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                shutil.copy2(src, dst)
                copied_files.append(rel_path)
            except (OSError, shutil.Error) as e:
                # Best-effort: log but continue
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to copy {rel_path} to slot {self.variant_key}: {e}")
        
        # Record in slots.json (best-effort)
        slots_file = context.calc_raw_dir / "scan" / "slots.json"
        try:
            self._append_slots_entry(
                slots_file,
                variant_key=self.variant_key,
                run_ulid=context.run_ulid,
                ok=getattr(job_result, "success", False),
                archived_path=str(dest_dir.relative_to(context.calc_raw_dir)),
                copied_files=copied_files,
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to write slots.json entry: {e}")
    
    def _append_slots_entry(
        self,
        slots_file: Path,
        variant_key: str,
        run_ulid: str,
        ok: bool,
        archived_path: str,
        copied_files: List[str],
    ) -> None:
        """
        Append entry to slots.json (append-only bookkeeping).
        
        Args:
            slots_file: Path to slots.json
            variant_key: Variant key
            run_ulid: Run ULID
            ok: Whether job succeeded
            archived_path: Relative path to archived directory
            copied_files: List of files copied
        """
        entry = {
            "variant_key": variant_key,
            "run_ulid": run_ulid,
            "ok": ok,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "archived_path": archived_path,
            "copied_files": copied_files,
        }
        
        # Read existing entries
        entries: List[Dict[str, Any]] = []
        if slots_file.exists():
            try:
                content = slots_file.read_text()
                if content.strip():
                    entries = json.loads(content)
                    if not isinstance(entries, list):
                        entries = []
            except (json.JSONDecodeError, OSError):
                # If file is corrupted or unreadable, start fresh
                entries = []
        
        # Append new entry
        entries.append(entry)
        
        # Write back (append-only semantics: we read all, append, write all)
        slots_file.parent.mkdir(parents=True, exist_ok=True)
        slots_file.write_text(json.dumps(entries, indent=2) + "\n")

