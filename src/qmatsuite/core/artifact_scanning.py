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
            relative = file_path.relative_to(base_dir).as_posix()
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


def scan_raw_directory_for_provenance(
    calc_dir: Path,
    additional_ignore: Optional[List[str]] = None,
) -> Dict[str, FileStat]:
    """
    Scan calculation raw directory for provenance tracking.
    
    Unlike scan_raw_directory(), this does NOT apply engine-specific
    ignore patterns. Provenance tracks ALL final artifacts for UI explanation.
    
    Args:
        calc_dir: Calculation directory
        additional_ignore: User-configured patterns only (e.g., "*.tmp")
    
    Returns:
        Dict mapping calc-relative paths to FileStat
    """
    raw_dir = calc_dir / "raw"
    if not raw_dir.exists():
        return {}
    
    # Only user-configured patterns, NO engine defaults
    patterns = additional_ignore or []
    
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

