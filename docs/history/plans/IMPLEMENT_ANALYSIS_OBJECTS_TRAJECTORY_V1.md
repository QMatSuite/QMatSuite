# Implementation Plan: Analysis Objects Framework + Trajectory v1

**Date**: 2026-01-19  
**Status**: Ready for Implementation  
**Spec Reference**: `docs/specs/ANALYSIS_OBJECTS_FRAMEWORK.md`

---

## Overview

This document provides step-by-step implementation instructions for the Analysis Objects Framework with Trajectory as the first instance. It is designed to be followed by Cursor auto with minimal interpretation.

**Key Deliverables**:
1. Core analysis object abstractions
2. Centralized artifact scanning API
3. Provenance tracking (`.runtime/provenance.json`)
4. Analysis cache (`.analysis/`)
5. Trajectory implementation (QE parser first)
6. Settings for cache policy
7. Comprehensive tests

---

## Phase 1: Core Abstractions

### 1.1 Create Core Analysis Module Structure

**Create directory structure**:
```
src/qmatsuite/core/analysis/
├── __init__.py
├── base.py           # AnalysisObjectMeta, SourceFileStat
├── primitives.py     # Series1D, GeometryFrame, etc.
├── cache.py          # CacheManager, staleness checks
└── policy.py         # MaterializationPolicy
```

**Task 1.1.1**: Create `src/qmatsuite/core/analysis/__init__.py`

```python
"""
Analysis Objects Framework.

Provides engine-agnostic canonical analysis objects (Trajectory, DOS, Bands, etc.)
parsed from raw engine outputs.
"""

from qmatsuite.core.analysis.base import (
    AnalysisObjectMeta,
    SourceFileStat,
)
from qmatsuite.core.analysis.primitives import (
    Series1D,
    GeometryFrame,
    GeometryFrames,
    Marker,
)
from qmatsuite.core.analysis.policy import (
    MaterializationPolicy,
    CacheConfig,
)
from qmatsuite.core.analysis.cache import (
    CacheManager,
    is_cache_stale,
)

__all__ = [
    "AnalysisObjectMeta",
    "SourceFileStat",
    "Series1D",
    "GeometryFrame",
    "GeometryFrames",
    "Marker",
    "MaterializationPolicy",
    "CacheConfig",
    "CacheManager",
    "is_cache_stale",
]
```

**Task 1.1.2**: Create `src/qmatsuite/core/analysis/base.py`

```python
"""
Base classes for analysis objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SourceFileStat:
    """
    Stat of a source file for stale detection.
    
    Uses (size_bytes, mtime) only. No sha256 in v1.
    Paths are calc-relative (e.g., "raw/scf.out").
    """
    path: str                              # Calc-relative path
    size_bytes: int
    mtime: float                           # Unix timestamp
    
    @classmethod
    def from_path(cls, file_path: Path, calc_dir: Path) -> "SourceFileStat":
        """Create SourceFileStat from a file path."""
        stat = file_path.stat()
        # Make path calc-relative
        try:
            relative = file_path.relative_to(calc_dir)
        except ValueError:
            relative = file_path
        return cls(
            path=str(relative),
            size_bytes=stat.st_size,
            mtime=stat.st_mtime,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "size_bytes": self.size_bytes,
            "mtime": self.mtime,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SourceFileStat":
        return cls(
            path=data["path"],
            size_bytes=data["size_bytes"],
            mtime=data["mtime"],
        )


@dataclass
class AnalysisObjectMeta:
    """
    Unified metadata for all analysis objects.
    
    This is the SINGLE SOURCE OF TRUTH for analysis object metadata.
    Trajectory, DOS, Bands all use this same structure.
    """
    # Identity
    schema_version: str                    # e.g., "1.0"
    object_type: str                       # "trajectory" | "dos" | "bands" | "scf"
    
    # Timing
    created_at: str                        # ISO 8601
    
    # Source tracking (for stale detection)
    source_files: List[SourceFileStat] = field(default_factory=list)
    
    # Provenance (for UI explanation only, NOT for stale detection)
    run_id: Optional[str] = None
    calc_ulid: Optional[str] = None
    step_ulid: Optional[str] = None
    
    # Parser info
    parser_name: str = ""
    parser_version: str = ""
    
    @classmethod
    def create(
        cls,
        object_type: str,
        source_files: List[SourceFileStat],
        *,
        run_id: Optional[str] = None,
        calc_ulid: Optional[str] = None,
        step_ulid: Optional[str] = None,
        parser_name: str = "",
        parser_version: str = "1.0",
    ) -> "AnalysisObjectMeta":
        """Factory method to create metadata."""
        return cls(
            schema_version="1.0",
            object_type=object_type,
            created_at=datetime.now(timezone.utc).isoformat(),
            source_files=source_files,
            run_id=run_id,
            calc_ulid=calc_ulid,
            step_ulid=step_ulid,
            parser_name=parser_name,
            parser_version=parser_version,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "object_type": self.object_type,
            "created_at": self.created_at,
            "source_files": [sf.to_dict() for sf in self.source_files],
            "run_id": self.run_id,
            "calc_ulid": self.calc_ulid,
            "step_ulid": self.step_ulid,
            "parser_name": self.parser_name,
            "parser_version": self.parser_version,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalysisObjectMeta":
        return cls(
            schema_version=data.get("schema_version", "1.0"),
            object_type=data["object_type"],
            created_at=data["created_at"],
            source_files=[SourceFileStat.from_dict(sf) for sf in data.get("source_files", [])],
            run_id=data.get("run_id"),
            calc_ulid=data.get("calc_ulid"),
            step_ulid=data.get("step_ulid"),
            parser_name=data.get("parser_name", ""),
            parser_version=data.get("parser_version", ""),
        )
```

**Task 1.1.3**: Create `src/qmatsuite/core/analysis/primitives.py`

```python
"""
Visual primitives for analysis objects.

DATA ONLY - no style fields. Styling is the viz layer's responsibility.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class Series1D:
    """1D data series for line plots. DATA ONLY."""
    x: np.ndarray
    y: np.ndarray
    x_label: str
    y_label: str
    x_unit: str
    y_unit: str
    name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": self.x.tolist(),
            "y": self.y.tolist(),
            "x_label": self.x_label,
            "y_label": self.y_label,
            "x_unit": self.x_unit,
            "y_unit": self.y_unit,
            "name": self.name,
        }


@dataclass
class GeometryFrame:
    """
    Single frame of atomic geometry. DATA ONLY.
    
    Positions are UNWRAPPED Cartesian in Å.
    """
    positions: np.ndarray              # (N, 3) UNWRAPPED Å
    species: List[str]                 # N element symbols
    cell: Optional[np.ndarray]         # (3, 3) or None
    pbc: Tuple[bool, bool, bool]       # Periodic boundary conditions
    
    # Per-atom data properties
    forces: Optional[np.ndarray] = None        # (N, 3) eV/Å
    velocities: Optional[np.ndarray] = None    # (N, 3) Å/fs
    
    def __post_init__(self):
        """Validate cell/pbc consistency."""
        if any(self.pbc) and self.cell is None:
            raise ValueError("PBC requires cell to be provided")
        if self.cell is not None and self.cell.shape != (3, 3):
            raise ValueError(f"Cell must be (3, 3), got {self.cell.shape}")


@dataclass
class GeometryFrames:
    """Sequence of geometry frames for animation."""
    frames: List[GeometryFrame]
    time: Optional[np.ndarray] = None          # Frame timestamps in fs
    iteration: Optional[np.ndarray] = None     # Frame iteration numbers
    image_indices: Optional[np.ndarray] = None # For NEB


@dataclass
class Marker:
    """Annotation marker for plots. Position only, NO style."""
    position: float
    label: str
    axis: str = "x"  # "x" or "y"
```

**Task 1.1.4**: Create `src/qmatsuite/core/analysis/policy.py`

```python
"""
Materialization policy for analysis objects.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class MaterializationPolicy(Enum):
    """Policy for analysis cache."""
    ENABLED = "enabled"    # Default: cache to .analysis/
    DISABLED = "disabled"  # Never cache
    
    @classmethod
    def from_settings(cls) -> "MaterializationPolicy":
        """
        Get policy from user settings.
        
        TODO: Wire to actual settings when Settings/Advanced is implemented.
        """
        # Default to ENABLED
        return cls.ENABLED


@dataclass
class CacheConfig:
    """Configuration for analysis caching."""
    policy: MaterializationPolicy = MaterializationPolicy.ENABLED
    format: str = "json"  # "json" or "hdf5"
    
    @classmethod
    def default(cls) -> "CacheConfig":
        return cls(policy=MaterializationPolicy.from_settings())
```

**Task 1.1.5**: Create `src/qmatsuite/core/analysis/cache.py`

```python
"""
Cache management for analysis objects.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from qmatsuite.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from qmatsuite.core.analysis.policy import CacheConfig, MaterializationPolicy

logger = logging.getLogger(__name__)

# Cache directory name (hidden)
ANALYSIS_CACHE_DIR = ".analysis"


def get_cache_dir(calc_dir: Path) -> Path:
    """Get the analysis cache directory for a calculation."""
    return calc_dir / ANALYSIS_CACHE_DIR


def get_cache_path(calc_dir: Path, object_type: str) -> Path:
    """
    Get cache file path for an object type.
    
    Convention: .analysis/<object_type>.json
    """
    return get_cache_dir(calc_dir) / f"{object_type}.json"


def is_cache_stale(
    meta: AnalysisObjectMeta,
    calc_dir: Path,
) -> Tuple[bool, str]:
    """
    Check if cached analysis object is stale.
    
    Hard stale criterion: source file stat mismatch.
    Provenance is NOT used for staleness (UI explanation only).
    
    Returns:
        (is_stale, reason)
    """
    for source in meta.source_files:
        source_path = calc_dir / source.path
        
        # File missing → stale
        if not source_path.exists():
            return (True, f"Source file missing: {source.path}")
        
        stat = source_path.stat()
        
        # Size mismatch → stale
        if stat.st_size != source.size_bytes:
            return (True, f"Size changed: {source.path} ({source.size_bytes} → {stat.st_size})")
        
        # Mtime mismatch → stale (with tolerance for float comparison)
        if abs(stat.st_mtime - source.mtime) > 0.01:
            return (True, f"Modified: {source.path}")
    
    return (False, "")


class CacheManager:
    """
    Manages analysis object caching.
    """
    
    def __init__(self, calc_dir: Path, config: Optional[CacheConfig] = None):
        self.calc_dir = calc_dir
        self.config = config or CacheConfig.default()
    
    def cache_enabled(self) -> bool:
        """Check if caching is enabled."""
        return self.config.policy == MaterializationPolicy.ENABLED
    
    def get_cached(self, object_type: str) -> Optional[Dict[str, Any]]:
        """
        Load cached object if exists and not stale.
        
        Returns:
            Object dict if cache hit, None if miss or stale
        """
        if not self.cache_enabled():
            return None
        
        cache_path = get_cache_path(self.calc_dir, object_type)
        if not cache_path.exists():
            logger.debug(f"Cache miss: {cache_path} does not exist")
            return None
        
        try:
            data = json.loads(cache_path.read_text())
            meta = AnalysisObjectMeta.from_dict(data.get("meta", {}))
            
            is_stale, reason = is_cache_stale(meta, self.calc_dir)
            if is_stale:
                logger.debug(f"Cache stale: {reason}")
                return None
            
            logger.debug(f"Cache hit: {cache_path}")
            return data
        except Exception as e:
            logger.warning(f"Failed to load cache {cache_path}: {e}")
            return None
    
    def save_cache(self, object_type: str, data: Dict[str, Any]) -> Path:
        """
        Save object to cache.
        
        Returns:
            Path to cache file
        """
        if not self.cache_enabled():
            raise RuntimeError("Cannot save cache when caching is disabled")
        
        cache_dir = get_cache_dir(self.calc_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        cache_path = get_cache_path(self.calc_dir, object_type)
        cache_path.write_text(json.dumps(data, indent=2, default=str))
        
        logger.debug(f"Saved cache: {cache_path}")
        return cache_path
    
    def invalidate(self, object_type: str) -> bool:
        """
        Invalidate (delete) cache for an object type.
        
        Returns:
            True if cache was deleted, False if it didn't exist
        """
        cache_path = get_cache_path(self.calc_dir, object_type)
        if cache_path.exists():
            cache_path.unlink()
            logger.debug(f"Invalidated cache: {cache_path}")
            return True
        return False
    
    def invalidate_all(self) -> int:
        """
        Invalidate all cached objects.
        
        Returns:
            Number of caches deleted
        """
        cache_dir = get_cache_dir(self.calc_dir)
        if not cache_dir.exists():
            return 0
        
        count = 0
        for cache_file in cache_dir.glob("*.json"):
            cache_file.unlink()
            count += 1
        
        logger.debug(f"Invalidated {count} caches")
        return count
```

---

## Phase 2: Centralized Artifact Scanning

### 2.1 Create Artifact Scanning Module

**Task 2.1.1**: Create `src/qmatsuite/core/artifact_scanning.py`

```python
"""
Centralized artifact scanning API.

Used by:
- Provenance tracking (after run)
- Analysis staleness checks
- Future: staging compatibility

Respects engine-specific and project ignore patterns.
"""
from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class FileStat:
    """Stat of a scanned file."""
    relative_path: str
    size_bytes: int
    mtime: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "size_bytes": self.size_bytes,
            "mtime": self.mtime,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileStat":
        return cls(
            relative_path=data["relative_path"],
            size_bytes=data["size_bytes"],
            mtime=data["mtime"],
        )


# Built-in ignore patterns per engine
ENGINE_IGNORE_PATTERNS: Dict[str, List[str]] = {
    "qe": [
        "outdir/",
        "*.save/",
        "*.wfc*",
        "*.mix*",
        "*.update",
        "*.bak",
        "pwscf.wfc*",
    ],
    "vasp": [
        "WAVECAR",
        "CHGCAR",
        "CHG",
        "PROCAR",
        "DOSCAR",  # Large, regenerated
    ],
    "lammps": [
        "*.restart*",
    ],
    "orca": [
        "*.gbw",
        "*.tmp",
    ],
    "pyscf": [],
}


def get_engine_ignore_patterns(engine: str) -> List[str]:
    """Get built-in ignore patterns for an engine."""
    return ENGINE_IGNORE_PATTERNS.get(engine.lower(), [])


def should_ignore(path: str, ignore_patterns: List[str]) -> bool:
    """
    Check if a path should be ignored.
    
    Patterns support:
    - "dir/" matches directories
    - "*.ext" matches file extensions
    - Standard fnmatch patterns
    """
    for pattern in ignore_patterns:
        # Directory pattern (ends with /)
        if pattern.endswith("/"):
            dir_name = pattern.rstrip("/")
            # Check if path contains this directory
            if f"/{dir_name}/" in f"/{path}/" or path.startswith(f"{dir_name}/"):
                return True
        # Standard fnmatch
        elif fnmatch.fnmatch(path, pattern):
            return True
        # Also check basename
        elif fnmatch.fnmatch(Path(path).name, pattern):
            return True
    return False


def scan_directory(
    directory: Path,
    ignore_patterns: Optional[List[str]] = None,
    base_dir: Optional[Path] = None,
) -> Dict[str, FileStat]:
    """
    Scan directory for files, respecting ignore patterns.
    
    Args:
        directory: Directory to scan
        ignore_patterns: Glob patterns to ignore
        base_dir: Base directory for relative paths (default: directory)
    
    Returns:
        Dict mapping relative paths to FileStat
    """
    if not directory.exists():
        return {}
    
    ignore_patterns = ignore_patterns or []
    base_dir = base_dir or directory
    
    result: Dict[str, FileStat] = {}
    
    for file_path in directory.rglob("*"):
        if not file_path.is_file():
            continue
        
        try:
            relative = str(file_path.relative_to(base_dir))
        except ValueError:
            relative = str(file_path)
        
        if should_ignore(relative, ignore_patterns):
            continue
        
        try:
            stat = file_path.stat()
            result[relative] = FileStat(
                relative_path=relative,
                size_bytes=stat.st_size,
                mtime=stat.st_mtime,
            )
        except (OSError, IOError) as e:
            logger.warning(f"Failed to stat {file_path}: {e}")
    
    return result


def scan_raw_directory(
    calc_dir: Path,
    engine: str,
    additional_ignore: Optional[List[str]] = None,
) -> Dict[str, FileStat]:
    """
    Scan calculation raw directory with engine-specific ignore patterns.
    
    Paths in result are calc-relative (e.g., "raw/scf.out").
    
    Args:
        calc_dir: Calculation directory
        engine: Engine name for default ignore patterns
        additional_ignore: Additional patterns from project config
    
    Returns:
        Dict mapping calc-relative paths to FileStat
    """
    raw_dir = calc_dir / "raw"
    if not raw_dir.exists():
        return {}
    
    # Combine engine defaults and additional patterns
    patterns = get_engine_ignore_patterns(engine)
    if additional_ignore:
        patterns = patterns + additional_ignore
    
    # Scan with calc_dir as base so paths are "raw/..."
    return scan_directory(raw_dir, patterns, base_dir=calc_dir)


def diff_scans(
    old_scan: Dict[str, FileStat],
    new_scan: Dict[str, FileStat],
) -> Dict[str, str]:
    """
    Diff two scans to find changed/new/deleted files.
    
    Returns:
        Dict mapping path to change type: "added", "modified", "deleted"
    """
    changes: Dict[str, str] = {}
    
    # Check for added/modified
    for path, new_stat in new_scan.items():
        old_stat = old_scan.get(path)
        if old_stat is None:
            changes[path] = "added"
        elif old_stat.size_bytes != new_stat.size_bytes or abs(old_stat.mtime - new_stat.mtime) > 0.01:
            changes[path] = "modified"
    
    # Check for deleted
    for path in old_scan:
        if path not in new_scan:
            changes[path] = "deleted"
    
    return changes
```

---

## Phase 3: Provenance Tracking

### 3.1 Create Provenance Module

**Task 3.1.1**: Create `src/qmatsuite/core/provenance.py`

```python
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
    scan_raw_directory,
    diff_scans,
)

logger = logging.getLogger(__name__)

RUNTIME_DIR = ".runtime"
PROVENANCE_FILE = "provenance.json"
PROVENANCE_SCHEMA_VERSION = 1


@dataclass
class ProvenanceEntry:
    """Provenance entry for a single file."""
    run_id: str
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
        return cls(
            schema_version=data.get("schema_version", PROVENANCE_SCHEMA_VERSION),
            updated_at=data.get("updated_at", ""),
            files=files,
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
        return ProvenanceMap.from_dict(data)
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
    run_id: str,
    step_ulid: str,
    engine: str,
    additional_ignore: Optional[List[str]] = None,
) -> Dict[str, str]:
    """
    Update provenance after a step completes.
    
    This should be called AFTER any staging is complete.
    
    Args:
        calc_dir: Calculation directory
        run_id: Current run ULID
        step_ulid: Step that just completed
        engine: Engine name (for ignore patterns)
        additional_ignore: Additional ignore patterns from config
    
    Returns:
        Dict of changed files: path -> change_type
    """
    # Load current provenance
    provenance = load_provenance(calc_dir)
    
    # Scan current state
    current_scan = scan_raw_directory(calc_dir, engine, additional_ignore)
    
    # Find changed files
    old_scan = provenance._last_scan or {}
    changes = diff_scans(old_scan, current_scan)
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Update provenance for changed/new files
    for path, change_type in changes.items():
        if change_type in ("added", "modified"):
            stat = current_scan[path]
            provenance.files[path] = ProvenanceEntry(
                run_id=run_id,
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
```

### 3.2 Hook Provenance into Runner

**Task 3.2.1**: Modify `src/qmatsuite/calculation/runner.py`

Add import at top:
```python
from qmatsuite.core.provenance import update_provenance_after_step
```

In `_execute_with_jobgraph()`, after manifest update (around line 610), add provenance update:

```python
# AFTER: update_manifest_step(...)

# Update provenance (after staging is complete)
try:
    from qmatsuite.core.provenance import update_provenance_after_step
    engine_name = job.engine or "qe"
    update_provenance_after_step(
        calc_dir=calculation.dir,
        run_id=run_id,
        step_ulid=step_ulid,
        engine=engine_name,
    )
except Exception as e:
    logger.warning(f"Failed to update provenance: {e}")
```

---

## Phase 4: Trajectory Implementation

### 4.1 Create Trajectory Module

**Create directory**:
```
src/qmatsuite/core/analysis/trajectory/
├── __init__.py
├── model.py          # Frame, Trajectory
├── io.py             # Serialization
└── utils.py          # Wrapping, observables
```

**Task 4.1.1**: Create `src/qmatsuite/core/analysis/trajectory/__init__.py`

```python
"""
Trajectory analysis object.

The first fully-specified analysis object in the framework.
Supports MD, relax, and NEB trajectories.
"""

from qmatsuite.core.analysis.trajectory.model import (
    Frame,
    Trajectory,
)
from qmatsuite.core.analysis.trajectory.io import (
    save_trajectory,
    load_trajectory,
)
from qmatsuite.core.analysis.trajectory.utils import (
    wrap_positions,
)

__all__ = [
    "Frame",
    "Trajectory",
    "save_trajectory",
    "load_trajectory",
    "wrap_positions",
]
```

**Task 4.1.2**: Create `src/qmatsuite/core/analysis/trajectory/model.py`

```python
"""
Trajectory data model.

Frame: Single snapshot
Trajectory: Collection of frames with metadata
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple

import numpy as np

from qmatsuite.core.analysis.base import AnalysisObjectMeta
from qmatsuite.core.analysis.primitives import (
    GeometryFrame,
    GeometryFrames,
    Series1D,
)


@dataclass
class Frame:
    """
    A single trajectory frame.
    
    Positions are UNWRAPPED Cartesian coordinates in Å.
    Cell can be None for molecular systems without a box.
    """
    # Required
    frame_index: int
    positions: np.ndarray              # (N, 3) UNWRAPPED Cartesian Å
    species: List[str]                 # N element symbols
    cell: Optional[np.ndarray]         # (3, 3) or None
    pbc: Tuple[bool, bool, bool]       # Periodic boundary conditions
    
    # Time/iteration axis
    time: Optional[float] = None       # fs (for MD)
    iteration: Optional[int] = None    # (for relax/NEB)
    
    # Observables
    energy: Optional[float] = None             # eV (potential energy)
    forces: Optional[np.ndarray] = None        # (N, 3) eV/Å
    temperature: Optional[float] = None        # K
    pressure: Optional[float] = None           # GPa
    stress: Optional[np.ndarray] = None        # (3, 3) GPa, positive=tensile
    kinetic_energy: Optional[float] = None     # eV
    velocities: Optional[np.ndarray] = None    # (N, 3) Å/fs
    momenta: Optional[np.ndarray] = None       # (N, 3) amu·Å/fs
    
    # NEB
    image_index: Optional[int] = None
    
    # Atom identity
    atom_ids: Optional[List[str]] = None
    
    def __post_init__(self):
        """Validate frame data."""
        # Validate cell/pbc
        if any(self.pbc) and self.cell is None:
            raise ValueError("PBC requires cell to be provided")
        if self.cell is not None and self.cell.shape != (3, 3):
            raise ValueError(f"Cell must be (3, 3), got {self.cell.shape}")
        
        # Validate positions shape
        if self.positions.shape[1] != 3:
            raise ValueError(f"Positions must be (N, 3), got {self.positions.shape}")
        
        # Validate species count
        if len(self.species) != len(self.positions):
            raise ValueError(f"Species count ({len(self.species)}) != atoms ({len(self.positions)})")
    
    @property
    def n_atoms(self) -> int:
        return len(self.species)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result = {
            "frame_index": self.frame_index,
            "positions": self.positions.tolist(),
            "species": self.species,
            "cell": self.cell.tolist() if self.cell is not None else None,
            "pbc": list(self.pbc),
            "time": self.time,
            "iteration": self.iteration,
            "energy": self.energy,
            "temperature": self.temperature,
            "pressure": self.pressure,
            "kinetic_energy": self.kinetic_energy,
            "image_index": self.image_index,
            "atom_ids": self.atom_ids,
        }
        # Optional arrays
        if self.forces is not None:
            result["forces"] = self.forces.tolist()
        if self.stress is not None:
            result["stress"] = self.stress.tolist()
        if self.velocities is not None:
            result["velocities"] = self.velocities.tolist()
        if self.momenta is not None:
            result["momenta"] = self.momenta.tolist()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Frame":
        """Create from dict."""
        return cls(
            frame_index=data["frame_index"],
            positions=np.array(data["positions"]),
            species=data["species"],
            cell=np.array(data["cell"]) if data.get("cell") is not None else None,
            pbc=tuple(data["pbc"]),
            time=data.get("time"),
            iteration=data.get("iteration"),
            energy=data.get("energy"),
            forces=np.array(data["forces"]) if data.get("forces") else None,
            temperature=data.get("temperature"),
            pressure=data.get("pressure"),
            stress=np.array(data["stress"]) if data.get("stress") else None,
            kinetic_energy=data.get("kinetic_energy"),
            velocities=np.array(data["velocities"]) if data.get("velocities") else None,
            momenta=np.array(data["momenta"]) if data.get("momenta") else None,
            image_index=data.get("image_index"),
            atom_ids=data.get("atom_ids"),
        )


@dataclass
class Trajectory:
    """
    Canonical trajectory representation.
    
    Supports MD, relax (optimization), and NEB trajectories.
    """
    meta: AnalysisObjectMeta
    frames: List[Frame]
    trajectory_type: str              # "md" | "relax" | "neb"
    n_images: Optional[int] = None    # For NEB
    
    @property
    def n_frames(self) -> int:
        return len(self.frames)
    
    @property
    def n_atoms(self) -> int:
        return self.frames[0].n_atoms if self.frames else 0
    
    def __len__(self) -> int:
        return self.n_frames
    
    def __getitem__(self, index: int) -> Frame:
        return self.frames[index]
    
    def __iter__(self) -> Iterator[Frame]:
        return iter(self.frames)
    
    def get_observable_series(self, name: str) -> Optional[Series1D]:
        """Extract time series of an observable."""
        if not self.frames:
            return None
        
        # Determine x-axis based on trajectory type
        if self.trajectory_type == "md":
            x = np.array([f.time for f in self.frames if f.time is not None])
            x_label = "Time"
            x_unit = "fs"
        else:
            x = np.array([f.iteration or f.frame_index for f in self.frames])
            x_label = "Iteration"
            x_unit = ""
        
        if len(x) != len(self.frames):
            # Fall back to frame index
            x = np.arange(len(self.frames))
            x_label = "Frame"
            x_unit = ""
        
        if name == "energy":
            values = [f.energy for f in self.frames]
            if all(v is not None for v in values):
                return Series1D(
                    x=x,
                    y=np.array(values),
                    x_label=x_label,
                    y_label="Energy",
                    x_unit=x_unit,
                    y_unit="eV",
                    name="Total Energy",
                )
        elif name == "temperature":
            values = [f.temperature for f in self.frames]
            if all(v is not None for v in values):
                return Series1D(
                    x=x,
                    y=np.array(values),
                    x_label=x_label,
                    y_label="Temperature",
                    x_unit=x_unit,
                    y_unit="K",
                    name="Temperature",
                )
        elif name == "pressure":
            values = [f.pressure for f in self.frames]
            if all(v is not None for v in values):
                return Series1D(
                    x=x,
                    y=np.array(values),
                    x_label=x_label,
                    y_label="Pressure",
                    x_unit=x_unit,
                    y_unit="GPa",
                    name="Pressure",
                )
        elif name == "max_force":
            values = []
            for f in self.frames:
                if f.forces is not None:
                    values.append(np.max(np.linalg.norm(f.forces, axis=1)))
                else:
                    return None
            return Series1D(
                x=x,
                y=np.array(values),
                x_label=x_label,
                y_label="Max Force",
                x_unit=x_unit,
                y_unit="eV/Å",
                name="Max Force",
            )
        
        return None
    
    def get_available_observables(self) -> List[str]:
        """Get list of available observables."""
        if not self.frames:
            return []
        
        observables = []
        sample = self.frames[0]
        
        if sample.energy is not None:
            observables.append("energy")
        if sample.temperature is not None:
            observables.append("temperature")
        if sample.pressure is not None:
            observables.append("pressure")
        if sample.forces is not None:
            observables.append("max_force")
        if sample.kinetic_energy is not None:
            observables.append("kinetic_energy")
        
        return observables
    
    def to_visual_primitives(self) -> Dict[str, Any]:
        """Convert to visualization primitives (data only, no style)."""
        primitives: Dict[str, Any] = {}
        
        # Geometry frames
        primitives["geometry"] = GeometryFrames(
            frames=[
                GeometryFrame(
                    positions=f.positions,
                    species=f.species,
                    cell=f.cell,
                    pbc=f.pbc,
                    forces=f.forces,
                    velocities=f.velocities,
                )
                for f in self.frames
            ],
            time=np.array([f.time for f in self.frames]) if self.frames and self.frames[0].time else None,
            iteration=np.array([f.iteration or f.frame_index for f in self.frames]),
            image_indices=np.array([f.image_index for f in self.frames]) if self.frames and self.frames[0].image_index is not None else None,
        )
        
        # Observable series
        for obs in self.get_available_observables():
            series = self.get_observable_series(obs)
            if series:
                primitives[f"series_{obs}"] = series
        
        return primitives
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "meta": self.meta.to_dict(),
            "frames": [f.to_dict() for f in self.frames],
            "trajectory_type": self.trajectory_type,
            "n_images": self.n_images,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Trajectory":
        """Create from dict."""
        return cls(
            meta=AnalysisObjectMeta.from_dict(data["meta"]),
            frames=[Frame.from_dict(f) for f in data["frames"]],
            trajectory_type=data["trajectory_type"],
            n_images=data.get("n_images"),
        )
```

**Task 4.1.3**: Create `src/qmatsuite/core/analysis/trajectory/io.py`

```python
"""
Trajectory I/O: serialization to/from cache.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from qmatsuite.core.analysis.cache import CacheManager, get_cache_path
from qmatsuite.core.analysis.trajectory.model import Trajectory


def save_trajectory(
    trajectory: Trajectory,
    calc_dir: Path,
    cache_manager: Optional[CacheManager] = None,
) -> Optional[Path]:
    """
    Save trajectory to cache.
    
    Returns:
        Path to cache file, or None if caching disabled
    """
    if cache_manager is None:
        cache_manager = CacheManager(calc_dir)
    
    if not cache_manager.cache_enabled():
        return None
    
    return cache_manager.save_cache("trajectory", trajectory.to_dict())


def load_trajectory(
    calc_dir: Path,
    cache_manager: Optional[CacheManager] = None,
) -> Optional[Trajectory]:
    """
    Load trajectory from cache if exists and not stale.
    
    Returns:
        Trajectory or None if not cached/stale
    """
    if cache_manager is None:
        cache_manager = CacheManager(calc_dir)
    
    data = cache_manager.get_cached("trajectory")
    if data is None:
        return None
    
    return Trajectory.from_dict(data)
```

**Task 4.1.4**: Create `src/qmatsuite/core/analysis/trajectory/utils.py`

```python
"""
Trajectory utilities.

Includes wrapping (called by viz, NOT by parser).
"""
from __future__ import annotations

from typing import Tuple

import numpy as np


def wrap_positions(
    positions: np.ndarray,
    cell: np.ndarray,
    pbc: Tuple[bool, bool, bool],
) -> np.ndarray:
    """
    Wrap positions into cell.
    
    Called by visualization/analysis code when needed,
    NOT by parsers during parsing.
    
    Args:
        positions: (N, 3) Cartesian positions in Å
        cell: (3, 3) cell vectors (row vectors)
        pbc: Periodic boundary conditions
    
    Returns:
        (N, 3) wrapped positions
    """
    # Convert to fractional
    inv_cell = np.linalg.inv(cell)
    frac = positions @ inv_cell
    
    # Wrap in PBC directions
    for i in range(3):
        if pbc[i]:
            frac[:, i] = frac[:, i] % 1.0
    
    # Convert back to Cartesian
    return frac @ cell


def compute_rdf(
    positions: np.ndarray,
    cell: np.ndarray,
    species: list,
    r_max: float = 10.0,
    n_bins: int = 100,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute radial distribution function.
    
    Returns:
        (r_values, g_r)
    """
    # Placeholder implementation
    r = np.linspace(0, r_max, n_bins)
    g = np.ones(n_bins)  # Placeholder
    return r, g


def compute_msd(
    trajectory: "Trajectory",
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute mean squared displacement.
    
    Returns:
        (time, msd)
    """
    # Placeholder implementation
    from qmatsuite.core.analysis.trajectory.model import Trajectory
    n_frames = len(trajectory)
    time = np.arange(n_frames)
    msd = np.zeros(n_frames)  # Placeholder
    return time, msd
```

---

## Phase 5: QE Trajectory Parser

### 5.1 Create Parser Module

**Create directory**:
```
src/qmatsuite/parsers/
├── __init__.py
├── registry.py
└── qe/
    ├── __init__.py
    └── trajectory.py
```

**Task 5.1.1**: Create `src/qmatsuite/parsers/__init__.py`

```python
"""
Engine-specific parsers for analysis objects.
"""

from qmatsuite.parsers.registry import ParserRegistry

__all__ = ["ParserRegistry"]
```

**Task 5.1.2**: Create `src/qmatsuite/parsers/registry.py`

```python
"""
Parser registry for automatic parser selection.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from qmatsuite.core.analysis.base import AnalysisObjectMeta

# Registry: (engine, object_type) -> parser class
_PARSERS: Dict[Tuple[str, str], type] = {}


def register_parser(engine: str, object_type: str):
    """Decorator to register a parser class."""
    def decorator(cls):
        _PARSERS[(engine.lower(), object_type.lower())] = cls
        return cls
    return decorator


def get_parser(engine: str, object_type: str):
    """Get parser class for engine and object type."""
    return _PARSERS.get((engine.lower(), object_type.lower()))


def find_parser_for_raw(raw_dir: Path, object_type: str):
    """
    Auto-detect parser based on raw directory contents.
    
    Returns:
        Parser class or None
    """
    for (engine, obj_type), parser_cls in _PARSERS.items():
        if obj_type == object_type.lower():
            parser = parser_cls()
            if hasattr(parser, "can_parse") and parser.can_parse(raw_dir):
                return parser_cls
    return None


class ParserRegistry:
    """Registry facade."""
    
    @staticmethod
    def register(engine: str, object_type: str):
        return register_parser(engine, object_type)
    
    @staticmethod
    def get(engine: str, object_type: str):
        return get_parser(engine, object_type)
    
    @staticmethod
    def find_for_raw(raw_dir: Path, object_type: str):
        return find_parser_for_raw(raw_dir, object_type)
```

**Task 5.1.3**: Create `src/qmatsuite/parsers/qe/__init__.py`

```python
"""QE parsers."""

# Import to register parsers
from qmatsuite.parsers.qe.trajectory import QETrajectoryParser

__all__ = ["QETrajectoryParser"]
```

**Task 5.1.4**: Create `src/qmatsuite/parsers/qe/trajectory.py`

```python
"""
QE trajectory parser.

Parses QE MD and relax outputs to canonical Trajectory.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from qmatsuite.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from qmatsuite.core.analysis.trajectory.model import Frame, Trajectory
from qmatsuite.parsers.registry import register_parser

logger = logging.getLogger(__name__)

# Ry to eV conversion
RY_TO_EV = 13.605693122994


@register_parser("qe", "trajectory")
class QETrajectoryParser:
    """
    Parse QE MD/relax output to canonical Trajectory.
    """
    
    engine = "qe"
    object_type = "trajectory"
    
    def can_parse(self, raw_dir: Path) -> bool:
        """Check if this raw directory contains parseable QE trajectory."""
        # Look for relax.out, vc-relax.out, or md.out
        for pattern in ["relax.out", "vc-relax.out", "md.out", "*.relax.out"]:
            if list(raw_dir.glob(pattern)):
                return True
        return False
    
    def parse(
        self,
        raw_dir: Path,
        calc_dir: Path,
        *,
        run_id: Optional[str] = None,
        step_ulid: Optional[str] = None,
        calc_ulid: Optional[str] = None,
    ) -> Trajectory:
        """
        Parse QE output to canonical Trajectory.
        
        Handles:
        - relax/vc-relax: geometry optimization
        - md: molecular dynamics (future)
        """
        # Find output file
        output_file = self._find_output_file(raw_dir)
        if output_file is None:
            raise FileNotFoundError(f"No QE trajectory output found in {raw_dir}")
        
        # Detect trajectory type
        traj_type = self._detect_trajectory_type(output_file)
        
        # Parse frames
        frames = self._parse_output(output_file, traj_type)
        
        if not frames:
            raise ValueError(f"No frames found in {output_file}")
        
        # Build source files stat
        source_files = [
            SourceFileStat.from_path(output_file, calc_dir)
        ]
        
        # Build metadata
        meta = AnalysisObjectMeta.create(
            object_type="trajectory",
            source_files=source_files,
            run_id=run_id,
            calc_ulid=calc_ulid,
            step_ulid=step_ulid,
            parser_name="qe_trajectory",
            parser_version="1.0",
        )
        
        return Trajectory(
            meta=meta,
            frames=frames,
            trajectory_type=traj_type,
        )
    
    def _find_output_file(self, raw_dir: Path) -> Optional[Path]:
        """Find the trajectory output file."""
        # Priority order
        patterns = [
            "vc-relax.out",
            "relax.out",
            "md.out",
            "*.vc-relax.out",
            "*.relax.out",
        ]
        
        for pattern in patterns:
            matches = list(raw_dir.glob(pattern))
            if matches:
                return matches[0]
        
        return None
    
    def _detect_trajectory_type(self, output_file: Path) -> str:
        """Detect trajectory type from output file."""
        name = output_file.name.lower()
        if "md" in name:
            return "md"
        elif "vc-relax" in name or "vcrelax" in name:
            return "relax"
        elif "relax" in name:
            return "relax"
        
        # Check file content
        text = output_file.read_text(errors="replace")[:5000]
        if "molecular dynamics" in text.lower():
            return "md"
        if "bfgs" in text.lower() or "geometry optimization" in text.lower():
            return "relax"
        
        return "relax"  # Default
    
    def _parse_output(self, output_file: Path, traj_type: str) -> List[Frame]:
        """Parse QE output file for trajectory frames."""
        text = output_file.read_text(errors="replace")
        
        frames: List[Frame] = []
        
        # Parse based on type
        if traj_type == "relax":
            frames = self._parse_relax_output(text)
        else:
            frames = self._parse_md_output(text)
        
        return frames
    
    def _parse_relax_output(self, text: str) -> List[Frame]:
        """Parse relax/vc-relax output."""
        frames: List[Frame] = []
        
        # Patterns
        bfgs_start = re.compile(r"BFGS Geometry Optimization")
        new_coords = re.compile(r"ATOMIC_POSITIONS\s*\(([^)]+)\)")
        cell_params = re.compile(r"CELL_PARAMETERS\s*\(([^)]+)\)")
        total_energy = re.compile(r"!\s*total energy\s*=\s*([-\d.]+)\s*Ry")
        total_force = re.compile(r"Total force\s*=\s*([-\d.]+)")
        
        # Split by BFGS steps
        lines = text.split("\n")
        current_positions = []
        current_species = []
        current_cell = None
        current_energy = None
        current_forces = []
        iteration = 0
        in_positions = False
        in_cell = False
        pos_unit = "angstrom"
        cell_unit = "angstrom"
        alat = 1.0  # Lattice parameter
        
        # First pass: get initial structure and alat
        for line in lines:
            if "lattice parameter" in line.lower() and "a.u." in line:
                match = re.search(r"=\s*([\d.]+)", line)
                if match:
                    alat = float(match.group(1)) * 0.529177  # Bohr to Å
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Energy
            energy_match = total_energy.search(line)
            if energy_match:
                current_energy = float(energy_match.group(1)) * RY_TO_EV
            
            # Detect ATOMIC_POSITIONS block
            pos_match = new_coords.search(line)
            if pos_match:
                pos_unit = pos_match.group(1).lower()
                in_positions = True
                current_positions = []
                current_species = []
                continue
            
            # Detect CELL_PARAMETERS block
            cell_match = cell_params.search(line)
            if cell_match:
                cell_unit = cell_match.group(1).lower()
                in_cell = True
                current_cell = []
                continue
            
            # Parse positions
            if in_positions:
                if stripped == "" or stripped.startswith("End") or stripped.startswith("CELL"):
                    in_positions = False
                else:
                    parts = stripped.split()
                    if len(parts) >= 4:
                        try:
                            species = parts[0]
                            x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                            current_species.append(species)
                            current_positions.append([x, y, z])
                        except ValueError:
                            in_positions = False
            
            # Parse cell
            if in_cell:
                parts = stripped.split()
                if len(parts) >= 3:
                    try:
                        current_cell.append([float(parts[0]), float(parts[1]), float(parts[2])])
                        if len(current_cell) == 3:
                            in_cell = False
                    except ValueError:
                        in_cell = False
            
            # End of BFGS step - create frame
            if "number of scf cycles" in line.lower() or "bfgs converged" in line.lower():
                if current_positions:
                    # Convert positions to Å
                    positions = np.array(current_positions)
                    if "crystal" in pos_unit:
                        # Fractional coordinates - need cell
                        if current_cell:
                            cell = np.array(current_cell)
                            # Scale cell if needed
                            if "alat" in cell_unit:
                                cell = cell * alat
                            elif "bohr" in cell_unit:
                                cell = cell * 0.529177
                            positions = positions @ cell
                    elif "bohr" in pos_unit:
                        positions = positions * 0.529177
                    elif "alat" in pos_unit:
                        positions = positions * alat
                    
                    # Cell
                    cell = None
                    pbc = (False, False, False)
                    if current_cell:
                        cell = np.array(current_cell)
                        if "alat" in cell_unit:
                            cell = cell * alat
                        elif "bohr" in cell_unit:
                            cell = cell * 0.529177
                        pbc = (True, True, True)
                    
                    frame = Frame(
                        frame_index=len(frames),
                        positions=positions,
                        species=current_species.copy(),
                        cell=cell,
                        pbc=pbc,
                        iteration=len(frames),
                        energy=current_energy,
                    )
                    frames.append(frame)
        
        # Add final frame if we have coordinates but haven't saved them
        if current_positions and (not frames or frames[-1].iteration != len(frames)):
            positions = np.array(current_positions)
            cell = np.array(current_cell) if current_cell else None
            pbc = (True, True, True) if cell is not None else (False, False, False)
            
            frame = Frame(
                frame_index=len(frames),
                positions=positions,
                species=current_species.copy(),
                cell=cell,
                pbc=pbc,
                iteration=len(frames),
                energy=current_energy,
            )
            frames.append(frame)
        
        return frames
    
    def _parse_md_output(self, text: str) -> List[Frame]:
        """Parse MD output (placeholder - to be implemented)."""
        # Similar structure to relax but with time steps
        logger.warning("QE MD parsing not yet fully implemented")
        return []
```

---

## Phase 6: Tests

### 6.1 Unit Tests

**Create test files**:

```
tests/unit/
├── test_analysis_objects_base.py
├── test_artifact_scanning.py
├── test_provenance.py
├── test_trajectory_model.py
└── test_trajectory_parser_qe.py
```

**Task 6.1.1**: Create `tests/unit/test_analysis_objects_base.py`

```python
"""Tests for analysis objects base classes."""
import pytest
from pathlib import Path
from datetime import datetime, timezone

from qmatsuite.core.analysis.base import (
    AnalysisObjectMeta,
    SourceFileStat,
)


class TestSourceFileStat:
    def test_from_path(self, tmp_path):
        """Test creating SourceFileStat from file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")
        
        stat = SourceFileStat.from_path(test_file, tmp_path)
        
        assert stat.path == "test.txt"
        assert stat.size_bytes == 11
        assert stat.mtime > 0
    
    def test_to_dict_from_dict(self):
        """Test serialization round-trip."""
        original = SourceFileStat(
            path="raw/scf.out",
            size_bytes=1234,
            mtime=1234567890.123,
        )
        
        data = original.to_dict()
        restored = SourceFileStat.from_dict(data)
        
        assert restored.path == original.path
        assert restored.size_bytes == original.size_bytes
        assert restored.mtime == original.mtime


class TestAnalysisObjectMeta:
    def test_create_factory(self):
        """Test factory method."""
        source = SourceFileStat("raw/test.out", 100, 12345.0)
        meta = AnalysisObjectMeta.create(
            object_type="trajectory",
            source_files=[source],
            run_id="01JTEST",
        )
        
        assert meta.schema_version == "1.0"
        assert meta.object_type == "trajectory"
        assert len(meta.source_files) == 1
        assert meta.run_id == "01JTEST"
    
    def test_to_dict_from_dict(self):
        """Test serialization round-trip."""
        source = SourceFileStat("raw/test.out", 100, 12345.0)
        original = AnalysisObjectMeta.create(
            object_type="dos",
            source_files=[source],
            parser_name="qe_dos",
        )
        
        data = original.to_dict()
        restored = AnalysisObjectMeta.from_dict(data)
        
        assert restored.object_type == original.object_type
        assert len(restored.source_files) == 1
        assert restored.parser_name == original.parser_name
```

**Task 6.1.2**: Create `tests/unit/test_provenance.py`

```python
"""Tests for provenance tracking."""
import pytest
from pathlib import Path

from qmatsuite.core.provenance import (
    ProvenanceMap,
    ProvenanceEntry,
    load_provenance,
    save_provenance,
    update_provenance_after_step,
    get_file_provenance,
)


class TestProvenanceMap:
    def test_empty_provenance(self, tmp_path):
        """Loading non-existent provenance returns empty map."""
        calc_dir = tmp_path / "calc"
        calc_dir.mkdir()
        
        prov = load_provenance(calc_dir)
        
        assert prov.files == {}
    
    def test_save_and_load(self, tmp_path):
        """Test save and load round-trip."""
        calc_dir = tmp_path / "calc"
        calc_dir.mkdir()
        
        prov = ProvenanceMap()
        prov.files["raw/scf.out"] = ProvenanceEntry(
            run_id="01JTEST",
            step_ulid="01JSTEP",
            produced_at="2026-01-19T10:00:00Z",
            size_bytes=1234,
            mtime=12345.0,
        )
        
        save_provenance(calc_dir, prov)
        loaded = load_provenance(calc_dir)
        
        assert "raw/scf.out" in loaded.files
        assert loaded.files["raw/scf.out"].run_id == "01JTEST"


class TestUpdateProvenance:
    def test_tracks_new_files(self, tmp_path):
        """Provenance tracks newly created files."""
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(parents=True)
        
        # Create a file
        (raw_dir / "scf.out").write_text("output")
        
        # Update provenance
        changes = update_provenance_after_step(
            calc_dir=calc_dir,
            run_id="01JRUN1",
            step_ulid="01JSTEP1",
            engine="qe",
        )
        
        assert "raw/scf.out" in changes
        assert changes["raw/scf.out"] == "added"
        
        # Check provenance
        entry = get_file_provenance(calc_dir, "raw/scf.out")
        assert entry is not None
        assert entry.run_id == "01JRUN1"
    
    def test_tracks_modified_files(self, tmp_path):
        """Provenance updates when files are modified."""
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(parents=True)
        
        # Create file
        test_file = raw_dir / "scf.out"
        test_file.write_text("output1")
        
        # First update
        update_provenance_after_step(calc_dir, "01JRUN1", "01JSTEP1", "qe")
        
        # Modify file
        test_file.write_text("output2 - modified")
        
        # Second update
        changes = update_provenance_after_step(calc_dir, "01JRUN2", "01JSTEP2", "qe")
        
        assert "raw/scf.out" in changes
        assert changes["raw/scf.out"] == "modified"
        
        entry = get_file_provenance(calc_dir, "raw/scf.out")
        assert entry.run_id == "01JRUN2"
    
    def test_ignores_outdir(self, tmp_path):
        """QE outdir/ is ignored by default."""
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        outdir = raw_dir / "outdir"
        outdir.mkdir(parents=True)
        
        # Create files
        (raw_dir / "scf.out").write_text("output")
        (outdir / "pwscf.save").write_text("save data")
        
        # Update
        update_provenance_after_step(calc_dir, "01JRUN1", "01JSTEP1", "qe")
        
        # Check
        prov = load_provenance(calc_dir)
        assert "raw/scf.out" in prov.files
        # outdir should be ignored
        assert not any("outdir" in p for p in prov.files)
```

**Task 6.1.3**: Create `tests/unit/test_trajectory_model.py`

```python
"""Tests for trajectory model."""
import pytest
import numpy as np

from qmatsuite.core.analysis.trajectory.model import Frame, Trajectory
from qmatsuite.core.analysis.base import AnalysisObjectMeta, SourceFileStat


class TestFrame:
    def test_valid_frame(self):
        """Test creating a valid frame."""
        frame = Frame(
            frame_index=0,
            positions=np.array([[0, 0, 0], [1, 1, 1]]),
            species=["Si", "Si"],
            cell=np.eye(3) * 5.43,
            pbc=(True, True, True),
        )
        
        assert frame.n_atoms == 2
        assert frame.frame_index == 0
    
    def test_molecular_no_box(self):
        """Molecule without box (cell=None)."""
        frame = Frame(
            frame_index=0,
            positions=np.array([[0, 0, 0], [1.5, 0, 0]]),
            species=["H", "H"],
            cell=None,
            pbc=(False, False, False),
        )
        
        assert frame.cell is None
        assert frame.pbc == (False, False, False)
    
    def test_molecular_with_box(self):
        """Molecule with box but no PBC."""
        frame = Frame(
            frame_index=0,
            positions=np.array([[0, 0, 0], [1.5, 0, 0]]),
            species=["H", "H"],
            cell=np.eye(3) * 20.0,  # Large box for viz
            pbc=(False, False, False),
        )
        
        assert frame.cell is not None
        assert not any(frame.pbc)
    
    def test_pbc_requires_cell(self):
        """PBC requires cell."""
        with pytest.raises(ValueError, match="PBC requires cell"):
            Frame(
                frame_index=0,
                positions=np.array([[0, 0, 0]]),
                species=["H"],
                cell=None,
                pbc=(True, False, False),  # PBC without cell
            )
    
    def test_species_count_match(self):
        """Species count must match positions."""
        with pytest.raises(ValueError, match="Species count"):
            Frame(
                frame_index=0,
                positions=np.array([[0, 0, 0], [1, 1, 1]]),
                species=["Si"],  # Only 1 species for 2 atoms
                cell=None,
                pbc=(False, False, False),
            )


class TestTrajectory:
    def test_observable_series(self):
        """Test extracting observable series."""
        frames = [
            Frame(
                frame_index=i,
                positions=np.array([[0, 0, 0]]),
                species=["H"],
                cell=None,
                pbc=(False, False, False),
                iteration=i,
                energy=-10.0 + i * 0.1,
            )
            for i in range(5)
        ]
        
        meta = AnalysisObjectMeta.create("trajectory", [])
        traj = Trajectory(meta=meta, frames=frames, trajectory_type="relax")
        
        series = traj.get_observable_series("energy")
        
        assert series is not None
        assert len(series.y) == 5
        assert series.y_unit == "eV"
    
    def test_to_visual_primitives(self):
        """Test visual primitives extraction."""
        frames = [
            Frame(
                frame_index=0,
                positions=np.array([[0, 0, 0]]),
                species=["H"],
                cell=np.eye(3) * 5.0,
                pbc=(True, True, True),
                energy=-10.0,
            )
        ]
        
        meta = AnalysisObjectMeta.create("trajectory", [])
        traj = Trajectory(meta=meta, frames=frames, trajectory_type="md")
        
        primitives = traj.to_visual_primitives()
        
        assert "geometry" in primitives
        assert primitives["geometry"].frames[0].n_atoms == 1
```

### 6.2 Integration Tests

**Task 6.2.1**: Create `tests/integration/test_analysis_cache_staging.py`

```python
"""
Integration tests for analysis cache with staging compatibility.

Tests that provenance is updated correctly after staging operations.
"""
import pytest
from pathlib import Path
import shutil

from qmatsuite.core.provenance import (
    update_provenance_after_step,
    load_provenance,
)


class TestProvenanceStagingCompatibility:
    """Test provenance tracks staged files correctly."""
    
    def test_provenance_after_staging_chgcar(self, tmp_path):
        """
        Simulate: step1 creates CHGCAR, step2 staging copies it.
        Provenance should track final locations.
        """
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        step1_dir = raw_dir / "step1"
        step2_dir = raw_dir / "step2"
        step1_dir.mkdir(parents=True)
        step2_dir.mkdir(parents=True)
        
        # Step 1: Create CHGCAR
        (step1_dir / "OUTCAR").write_text("step1 output")
        (step1_dir / "CHGCAR").write_text("charge density")
        
        update_provenance_after_step(calc_dir, "01JRUN1", "01JSTEP1", "vasp")
        
        # Simulate staging: copy CHGCAR to step2
        shutil.copy(step1_dir / "CHGCAR", step2_dir / "CHGCAR")
        (step2_dir / "OUTCAR").write_text("step2 output")
        
        # Update provenance after step2 (which includes staging)
        update_provenance_after_step(calc_dir, "01JRUN1", "01JSTEP2", "vasp")
        
        # Check: both CHGCARs are tracked
        prov = load_provenance(calc_dir)
        
        assert "raw/step1/CHGCAR" in prov.files
        assert "raw/step2/CHGCAR" in prov.files
        
        # step2 CHGCAR should be attributed to step2
        assert prov.files["raw/step2/CHGCAR"].step_ulid == "01JSTEP2"
    
    def test_provenance_updated_after_staging_not_before(self, tmp_path):
        """
        Provenance update occurs after staging completes.
        Files that don't exist yet shouldn't appear in provenance.
        """
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(parents=True)
        
        # Initial state: no files
        prov = load_provenance(calc_dir)
        assert len(prov.files) == 0
        
        # Simulate step execution
        (raw_dir / "scf.out").write_text("output")
        
        # Update provenance
        update_provenance_after_step(calc_dir, "01JRUN1", "01JSTEP1", "qe")
        
        prov = load_provenance(calc_dir)
        assert "raw/scf.out" in prov.files
```

---

## Phase 7: Wiring and Settings

### 7.1 Settings Integration

**Task 7.1.1**: Add cache policy to settings

In `src/qmatsuite/core/settings.py` (or equivalent), add:

```python
class AnalysisSettings:
    """Analysis-related settings."""
    
    cache_enabled: bool = True  # Default: cache enabled
    
    # Future: additional analysis settings
    # cache_format: str = "json"  # or "hdf5"
```

**Task 7.1.2**: Wire to MaterializationPolicy

Update `src/qmatsuite/core/analysis/policy.py`:

```python
@classmethod
def from_settings(cls) -> "MaterializationPolicy":
    """Get policy from user settings."""
    try:
        from qmatsuite.core.settings import get_analysis_settings
        settings = get_analysis_settings()
        if not settings.cache_enabled:
            return cls.DISABLED
    except ImportError:
        pass  # Settings not yet implemented
    
    return cls.ENABLED
```

---

## Phase 8: Migration of Existing Code

### 8.1 Update Existing Analysis Module

**Task 8.1.1**: Update `src/qmatsuite/analysis/artifacts.py`

Change `get_analysis_dir()` to use hidden directory:

```python
def get_analysis_dir(calculation_dir: Path) -> Path:
    """
    Get the analysis artifacts directory for a calculation.
    
    UPDATED: Now uses hidden .analysis/ directory.
    """
    return calculation_dir / ".analysis"
```

**Task 8.1.2**: Add cache stale check

Before loading cached artifacts, add stale check using `AnalysisObjectMeta.source_files`.

---

## Acceptance Criteria

### Must Pass

1. **Core abstractions work**:
   - `AnalysisObjectMeta` serializes/deserializes correctly
   - `SourceFileStat` captures file state
   
2. **Cache works**:
   - `.analysis/` directory created on cache write
   - Cache loaded when valid
   - Cache stale when source file changes
   
3. **Provenance works**:
   - `.runtime/provenance.json` created
   - Tracks new/modified files
   - Respects engine ignore patterns
   - Works after staging

4. **Trajectory works**:
   - QE relax output parsed to Trajectory
   - Frames have unwrapped positions
   - cell=None valid for molecules
   - Observable series extractable

5. **No regressions**:
   - Existing analysis features still work
   - Tests pass

### Performance

- Provenance scan of typical raw/ < 100ms
- Ignore patterns effectively skip outdir/ (no recursive descent)

---

## Files Changed Summary

### New Files
```
src/qmatsuite/core/analysis/__init__.py
src/qmatsuite/core/analysis/base.py
src/qmatsuite/core/analysis/primitives.py
src/qmatsuite/core/analysis/policy.py
src/qmatsuite/core/analysis/cache.py
src/qmatsuite/core/analysis/trajectory/__init__.py
src/qmatsuite/core/analysis/trajectory/model.py
src/qmatsuite/core/analysis/trajectory/io.py
src/qmatsuite/core/analysis/trajectory/utils.py
src/qmatsuite/core/artifact_scanning.py
src/qmatsuite/core/provenance.py
src/qmatsuite/parsers/__init__.py
src/qmatsuite/parsers/registry.py
src/qmatsuite/parsers/qe/__init__.py
src/qmatsuite/parsers/qe/trajectory.py
tests/unit/test_analysis_objects_base.py
tests/unit/test_provenance.py
tests/unit/test_trajectory_model.py
tests/unit/test_artifact_scanning.py
tests/integration/test_analysis_cache_staging.py
```

### Modified Files
```
src/qmatsuite/calculation/runner.py  # Add provenance hook
src/qmatsuite/analysis/artifacts.py  # Change to .analysis/
```

---

## Evidence References

| Evidence | Location |
|----------|----------|
| Existing analysis artifacts | `src/qmatsuite/analysis/artifacts.py:63-75` |
| Manifest storage pattern | `src/qmatsuite/calculation/manifest.py` |
| VASP staging | `src/qmatsuite/execution/vasp_staging.py` |
| Step artifact rules | `src/qmatsuite/calculation/step_artifacts.py` |
| Runner orchestration | `src/qmatsuite/calculation/runner.py:94-630` |
| Job execution | `src/qmatsuite/execution/executor.py:76-178` |

---

**End of Implementation Plan**

