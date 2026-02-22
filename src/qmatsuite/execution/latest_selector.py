"""mtime-based latest artifact selection."""

from pathlib import Path
from typing import Optional


def find_latest_by_mtime(workdir: Path, pattern: str) -> Optional[Path]:
    """
    Find latest file matching pattern by modification time.

    Args:
        workdir: Directory to search (Runtime SSOT: raw/<step_ulid>/)
        pattern: Glob pattern (e.g., "cp2k_calc-*.restart", "*.wfn")

    Returns:
        Path to file with most recent mtime, or None if no matches.

    Note:
        This is a GENERAL mechanism, not CP2K-specific.
        Can be used by any engine that accumulates artifacts.
    """
    candidates = list(workdir.glob(pattern))
    if not candidates:
        return None

    # Select by mtime (most recent)
    return max(candidates, key=lambda p: p.stat().st_mtime)

