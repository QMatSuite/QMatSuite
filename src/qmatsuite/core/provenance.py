"""
Provenance tracking for calculation artifacts.

Stores current-only provenance map at .runtime/provenance.json.

Used for UI explanation only, NOT for stale detection or run logic.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from qmatsuite.core.artifact_scanning import (
    FileStat,
    scan_raw_directory_for_provenance,
    diff_scans,
)

logger = logging.getLogger(__name__)

RUNTIME_DIR = ".runtime"
PROVENANCE_FILE = "provenance.json"
PROVENANCE_SCHEMA_VERSION = 1


@dataclass
class ProvenanceEntry:
    """Provenance entry for a single file."""
    run_ulid: str
    step_ulid: str
    produced_at: str                # ISO 8601
    size_bytes: int
    mtime: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProvenanceEntry":
        return cls(**data)


@dataclass
class ProvenanceMap:
    """
    Provenance map for a calculation.
    
    Current-only: tracks which run/step last produced each file.
    """
    schema_version: int = PROVENANCE_SCHEMA_VERSION
    updated_at: str = ""
    files: Dict[str, ProvenanceEntry] = field(default_factory=dict)
    
    # Last scan state (for diffing)
    _last_scan: Dict[str, FileStat] = field(default_factory=dict, repr=False)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "updated_at": self.updated_at,
            "files": {k: v.to_dict() for k, v in self.files.items()},
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProvenanceMap":
        files = {
            k: ProvenanceEntry.from_dict(v)
            for k, v in data.get("files", {}).items()
        }
        # Restore last scan state if present (not serialized, but we reconstruct from files)
        last_scan = {}
        for path, entry in files.items():
            last_scan[path] = FileStat(
                relative_path=path,
                size_bytes=entry.size_bytes,
                mtime=entry.mtime,
            )
        return cls(
            schema_version=data.get("schema_version", PROVENANCE_SCHEMA_VERSION),
            updated_at=data.get("updated_at", ""),
            files=files,
            _last_scan=last_scan,
        )


def get_runtime_dir(calc_dir: Path) -> Path:
    """Get runtime directory for a calculation."""
    return calc_dir / RUNTIME_DIR


def get_provenance_path(calc_dir: Path) -> Path:
    """Get provenance file path."""
    return get_runtime_dir(calc_dir) / PROVENANCE_FILE


def load_provenance(calc_dir: Path) -> ProvenanceMap:
    """Load provenance map, creating empty one if not exists."""
    path = get_provenance_path(calc_dir)
    if not path.exists():
        return ProvenanceMap()
    
    try:
        data = json.loads(path.read_text())
        prov = ProvenanceMap.from_dict(data)
        # Restore last scan state if present (not serialized, but we can reconstruct)
        return prov
    except Exception as e:
        logger.warning(f"Failed to load provenance from {path}: {e}")
        return ProvenanceMap()


def save_provenance(calc_dir: Path, provenance: ProvenanceMap) -> None:
    """Save provenance map atomically."""
    runtime_dir = get_runtime_dir(calc_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    
    provenance.updated_at = datetime.now(timezone.utc).isoformat()
    
    path = get_provenance_path(calc_dir)
    
    # Atomic write via temp file
    import tempfile
    temp_fd, temp_path = tempfile.mkstemp(
        prefix="provenance_",
        suffix=".json.tmp",
        dir=runtime_dir,
    )
    try:
        import os
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(provenance.to_dict(), f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        Path(temp_path).rename(path)
    except Exception as e:
        try:
            Path(temp_path).unlink()
        except Exception:
            pass
        raise RuntimeError(f"Failed to save provenance: {e}") from e


def update_provenance_after_step(
    calc_dir: Path,
    run_ulid: str,
    step_ulid: str,
    engine: str,
    additional_ignore: Optional[List[str]] = None,
) -> Dict[str, str]:
    """
    Update provenance after a step completes.
    
    This should be called AFTER any staging is complete.
    
    Args:
        calc_dir: Calculation directory
        run_ulid: Current run ULID
        step_ulid: Step that just completed
        engine: Engine name (for ignore patterns)
        additional_ignore: Additional ignore patterns from config
    
    Returns:
        Dict of changed files: path -> change_type
    """
    # Load current provenance
    provenance = load_provenance(calc_dir)
    
    # Scan current state - NO engine ignore patterns for provenance
    current_scan = scan_raw_directory_for_provenance(calc_dir, additional_ignore)
    
    # Find changed files
    old_scan = provenance._last_scan or {}
    changes = diff_scans(old_scan, current_scan)
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Update provenance for changed/new files
    for path, change_type in changes.items():
        if change_type in ("added", "modified"):
            stat = current_scan[path]
            provenance.files[path] = ProvenanceEntry(
                run_ulid=run_ulid,
                step_ulid=step_ulid,
                produced_at=now,
                size_bytes=stat.size_bytes,
                mtime=stat.mtime,
            )
        elif change_type == "deleted":
            # Remove from provenance
            provenance.files.pop(path, None)
    
    # Store scan state for next diff
    provenance._last_scan = current_scan
    
    # Save
    save_provenance(calc_dir, provenance)
    
    logger.debug(f"Updated provenance: {len(changes)} changes")
    return changes


def get_file_provenance(calc_dir: Path, file_path: str) -> Optional[ProvenanceEntry]:
    """Get provenance for a specific file."""
    provenance = load_provenance(calc_dir)
    return provenance.files.get(file_path)

