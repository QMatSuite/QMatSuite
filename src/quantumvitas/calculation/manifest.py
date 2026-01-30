"""
Manifest system for incremental run tracking.

Minimal manifest schema tracking step completion state and input identity (three SHAs).
Stored at calculations/<calc_id>/.run_tmp_info/manifest.json
"""

from __future__ import annotations

import json
import logging
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MANIFEST_SCHEMA_VERSION = 1
MANIFEST_DIR_NAME = ".run_tmp_info"
MANIFEST_FILE_NAME = "manifest.json"


@dataclass
class ManifestStepEntry:
    """
    Single step entry in manifest.
    
    Minimal fields only - no output hashes, paths, or artifacts.
    """
    kind: str  # Step type (e.g., "scf", "nscf")
    step_ulid: str  # ULID for traceability (updated on reconcile but not used for skip logic)
    pseudo_set_sha: str  # SHA256 of pseudo set (computed fresh each run)
    structure_sha: str  # SHA256 of structure JSON (meta stripped) - init structure SHA
    step_sha: str  # SHA256 of step YAML (meta stripped)
    effective_structure_sha: Optional[str] = None  # NEW: SHA256 of effective structure at execution time (for relax-aware skip logic)
    run_ulid: Optional[str] = None  # Last attempted run ULID
    done: bool = False  # Whether step is completed
    started_at: Optional[str] = None  # ISO8601 timestamp
    done_at: Optional[str] = None  # ISO8601 timestamp when done==true
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ManifestStepEntry":
        """Create from dictionary."""
        return cls(
            kind=data["kind"],
            step_ulid=data["step_ulid"],
            pseudo_set_sha=data["pseudo_set_sha"],
            structure_sha=data["structure_sha"],
            step_sha=data["step_sha"],
            effective_structure_sha=data.get("effective_structure_sha"),  # Optional, backward compatible
            run_ulid=data.get("run_ulid"),
            done=data.get("done", False),
            started_at=data.get("started_at"),
            done_at=data.get("done_at"),
        )


@dataclass
class Manifest:
    """
    Manifest for a calculation.
    
    Tracks step completion state and input identity (three SHAs).
    """
    schema_version: int = MANIFEST_SCHEMA_VERSION
    steps: List[ManifestStepEntry] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "schema_version": self.schema_version,
            "steps": [step.to_dict() for step in self.steps],
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Manifest":
        """Create from dictionary."""
        steps = [ManifestStepEntry.from_dict(step_data) for step_data in data.get("steps", [])]
        return cls(
            schema_version=data.get("schema_version", MANIFEST_SCHEMA_VERSION),
            steps=steps,
        )


def get_manifest_dir(calc_dir: Path) -> Path:
    """Get manifest directory path."""
    return calc_dir / MANIFEST_DIR_NAME


def get_manifest_path(calc_dir: Path) -> Path:
    """Get manifest file path."""
    return get_manifest_dir(calc_dir) / MANIFEST_FILE_NAME


def load_manifest(calc_dir: Path) -> Optional[Manifest]:
    """
    Load manifest from calculation directory.
    
    Args:
        calc_dir: Calculation directory
        
    Returns:
        Manifest instance if exists, None otherwise
    """
    manifest_path = get_manifest_path(calc_dir)
    
    if not manifest_path.exists():
        return None
    
    try:
        data = json.loads(manifest_path.read_text())
        return Manifest.from_dict(data)
    except Exception as e:
        logger.warning(f"Failed to load manifest from {manifest_path}: {e}")
        return None


def save_manifest_atomic(calc_dir: Path, manifest: Manifest) -> None:
    """
    Save manifest atomically (temp file + rename).
    
    Args:
        calc_dir: Calculation directory
        manifest: Manifest instance to save
    """
    manifest_dir = get_manifest_dir(calc_dir)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    
    manifest_path = get_manifest_path(calc_dir)
    
    # Write to temp file first
    temp_fd, temp_path = tempfile.mkstemp(
        prefix="manifest_",
        suffix=".json.tmp",
        dir=manifest_dir,
    )
    
    try:
        with open(temp_fd, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)
            f.flush()
            import os
            os.fsync(f.fileno())
        
        # Atomic rename
        Path(temp_path).rename(manifest_path)
    except Exception as e:
        # Clean up temp file on error
        try:
            Path(temp_path).unlink()
        except Exception:
            pass
        raise RuntimeError(f"Failed to save manifest to {manifest_path}: {e}") from e


def update_manifest_step(
    calc_dir: Path,
    step_index: int,
    kind: str,
    step_ulid: str,
    pseudo_set_sha: str,
    structure_sha: str,
    step_sha: str,
    run_id: Optional[str] = None,
    done: bool = False,
    started_at: Optional[str] = None,
    done_at: Optional[str] = None,
    effective_structure_sha: Optional[str] = None,
) -> None:
    """
    Update a single step entry in manifest.
    
    Creates manifest if it doesn't exist.
    
    Args:
        calc_dir: Calculation directory
        step_index: Step index (0-based)
        kind: Step type
        step_ulid: Step ULID
        pseudo_set_sha: Pseudo set SHA
        structure_sha: Structure SHA
        step_sha: Step YAML SHA
        run_id: Optional run ID
        done: Whether step is done
        started_at: Optional started timestamp (ISO8601)
        done_at: Optional done timestamp (ISO8601)
        effective_structure_sha: Optional effective structure SHA (for relax-aware skip logic)
    """
    manifest = load_manifest(calc_dir) or Manifest()
    
    # Ensure manifest has enough entries
    while len(manifest.steps) <= step_index:
        # Create placeholder entry (will be filled by reconcile)
        manifest.steps.append(ManifestStepEntry(
            kind="",
            step_ulid="",
            pseudo_set_sha="",
            structure_sha="",
            step_sha="",
            done=False,
        ))
    
    # Update entry
    entry = ManifestStepEntry(
        kind=kind,
        step_ulid=step_ulid,
        pseudo_set_sha=pseudo_set_sha,
        structure_sha=structure_sha,
        step_sha=step_sha,
        effective_structure_sha=effective_structure_sha,
        run_ulid=run_id,  # Parameter is run_id, field is run_ulid
        done=done,
        started_at=started_at,
        done_at=done_at,
    )
    manifest.steps[step_index] = entry
    
    save_manifest_atomic(calc_dir, manifest)


def clear_manifest_from_step(calc_dir: Path, from_step_index: int) -> None:
    """
    Clear manifest entries from step index onward.
    
    Sets done=False for all entries from from_step_index to end.
    Used for single-step runs to invalidate subsequent steps.
    
    Args:
        calc_dir: Calculation directory
        from_step_index: First step index to clear (inclusive)
    """
    manifest = load_manifest(calc_dir)
    if not manifest:
        return
    
    # Only invalidate existing entries, don't extend manifest
    if from_step_index >= len(manifest.steps):
        # No entries to clear
        return
    
    # Clear entries (set done=False, but keep SHAs and other fields for reference)
    for i in range(from_step_index, len(manifest.steps)):
        entry = manifest.steps[i]
        entry.done = False
        entry.done_at = None
        # Keep run_id and started_at for traceability (per spec)
        # Keep SHAs as they are
    
    save_manifest_atomic(calc_dir, manifest)


def trim_manifest_to_length(calc_dir: Path, length: int) -> None:
    """
    Trim manifest to specified length (remove tail entries).
    
    Args:
        calc_dir: Calculation directory
        length: Target length (number of steps)
    """
    manifest = load_manifest(calc_dir)
    if not manifest:
        return
    
    if len(manifest.steps) <= length:
        return
    
    manifest.steps = manifest.steps[:length]
    save_manifest_atomic(calc_dir, manifest)


def should_skip_step(
    manifest_entry: ManifestStepEntry,
    current_kind: str,
    current_pseudo_set_sha: str,
    current_structure_sha: str,
    current_step_sha: str,
) -> bool:
    """
    Check if step should be skipped based on manifest entry.
    
    Step is skipped if:
    - kind matches
    - All three SHAs match
    - done == True
    
    Args:
        manifest_entry: Manifest entry for this step
        current_kind: Current step type
        current_pseudo_set_sha: Current pseudo set SHA
        current_structure_sha: Current structure SHA
        current_step_sha: Current step SHA
        
    Returns:
        True if step should be skipped, False otherwise
    """
    # Check kind match
    if manifest_entry.kind != current_kind:
        return False
    
    # Check SHA matches
    if manifest_entry.pseudo_set_sha != current_pseudo_set_sha:
        return False
    
    if manifest_entry.structure_sha != current_structure_sha:
        return False
    
    if manifest_entry.step_sha != current_step_sha:
        return False
    
    # Check done flag
    if not manifest_entry.done:
        return False
    
    return True


def now_iso8601() -> str:
    """Get current timestamp as ISO8601 string."""
    return datetime.now(timezone.utc).isoformat()

