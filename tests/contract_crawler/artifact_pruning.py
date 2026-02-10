"""
Artifact pruning utilities for engine-dependent RPC methods.

Ensures only small, essential artifacts are stored in fixtures.
"""

import shutil
from pathlib import Path
from typing import List, Set

# Directories/files to always exclude
EXCLUDE_PATTERNS: Set[str] = {
    "outdir",
    ".save",
    "save",
    "wfc",
    "wfc1",
    "wfc2",
    "wavefunction",
    "tmp",
    "tmpdir",
    "__pycache__",
    ".pytest_cache",
}

# File extensions to exclude (large binaries)
EXCLUDE_EXTENSIONS: Set[str] = {
    ".wfc",
    ".save",
    ".dat",
    ".bin",
    ".h5",
    ".hdf5",
}

# Maximum file size (1MB)
MAX_FILE_SIZE = 1024 * 1024

# Maximum total fixture size (10MB)
MAX_TOTAL_SIZE = 10 * 1024 * 1024


def should_exclude_path(path: Path) -> bool:
    """Check if a path should be excluded."""
    # Check directory name
    if any(pattern in path.name.lower() for pattern in EXCLUDE_PATTERNS):
        return True
    
    # Check extension
    if path.suffix.lower() in EXCLUDE_EXTENSIONS:
        return True
    
    # Check file size
    if path.is_file() and path.stat().st_size > MAX_FILE_SIZE:
        return True
    
    return False


def prune_directory(source_dir: Path, dest_dir: Path, keep_patterns: List[str] = None) -> int:
    """
    Copy directory while pruning large/unnecessary files.
    
    Args:
        source_dir: Source directory to prune
        dest_dir: Destination directory
        keep_patterns: List of patterns to keep (e.g., ["*.out", "*.xml"])
    
    Returns:
        Total size of copied files in bytes
    """
    keep_patterns = keep_patterns or []
    total_size = 0
    
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    for item in source_dir.iterdir():
        if should_exclude_path(item):
            continue
        
        # Check if we should keep this file
        if keep_patterns:
            should_keep = any(item.match(pattern) for pattern in keep_patterns)
            if not should_keep and item.is_file():
                continue
        
        dest_item = dest_dir / item.name
        
        if item.is_dir():
            # Recursively prune subdirectory
            sub_size = prune_directory(item, dest_item, keep_patterns)
            total_size += sub_size
        elif item.is_file():
            # Copy file
            shutil.copy2(item, dest_item)
            total_size += item.stat().st_size
    
    return total_size


def get_directory_size(path: Path) -> int:
    """Get total size of directory in bytes."""
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


def validate_fixture_size(fixture_dir: Path, max_size: int = MAX_TOTAL_SIZE) -> tuple[bool, int, str]:
    """
    Validate that fixture directory doesn't exceed size limit.
    
    Returns:
        (is_valid, actual_size, error_message)
    """
    if not fixture_dir.exists():
        return True, 0, ""
    
    actual_size = get_directory_size(fixture_dir)
    
    if actual_size > max_size:
        return False, actual_size, f"Fixture directory {fixture_dir} exceeds {max_size} bytes (actual: {actual_size})"
    
    return True, actual_size, ""


def copy_minimal_artifacts(
    source_dir: Path,
    dest_dir: Path,
    artifact_patterns: List[str],
) -> Path:
    """
    Copy only minimal artifacts matching patterns.
    
    Args:
        source_dir: Source directory (e.g., calculation raw/)
        dest_dir: Destination directory in fixtures
        artifact_patterns: Patterns to keep (e.g., ["*.out", "*.xml", "*.in"])
    
    Returns:
        Path to destination directory
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    total_size = 0
    for pattern in artifact_patterns:
        for artifact in source_dir.glob(pattern):
            if artifact.is_file() and not should_exclude_path(artifact):
                dest_file = dest_dir / artifact.name
                shutil.copy2(artifact, dest_file)
                total_size += artifact.stat().st_size
    
    # Validate size
    is_valid, actual_size, error = validate_fixture_size(dest_dir)
    if not is_valid:
        raise ValueError(f"Artifacts too large: {error}")
    
    return dest_dir




