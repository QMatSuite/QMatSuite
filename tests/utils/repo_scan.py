"""
Pure-Python repository scanner for guard tests.

This module provides a replacement for ripgrep (rg) in CI environments
where external binaries may not be available. It scans production code
files for patterns while excluding test files and build artifacts.

Why not use rg? CI portability: not all CI runners have ripgrep installed.
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple, Union


def find_repo_root(start_path: Optional[Path] = None) -> Path:
    """
    Find repository root by looking for .git directory or setup.py/pyproject.toml.
    
    Args:
        start_path: Starting path (defaults to this file's parent)
        
    Returns:
        Path to repository root
    """
    if start_path is None:
        start_path = Path(__file__).resolve()
    
    current = start_path if start_path.is_dir() else start_path.parent
    
    while current != current.parent:
        # Check for common repo root markers
        if (current / ".git").exists():
            return current
        if (current / "pyproject.toml").exists():
            return current
        if (current / "setup.py").exists():
            return current
        current = current.parent
    
    # Fallback: assume we're in tests/utils, go up to repo root
    return current


def collect_production_files(
    repo_root: Path,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
) -> List[Path]:
    """
    Collect production code files to scan.
    
    Args:
        repo_root: Repository root path
        include_patterns: Glob patterns to include (default: ["src/**/*.py"])
        exclude_patterns: Path substrings to exclude (default: common build/test dirs)
        
    Returns:
        List of file paths to scan, sorted for deterministic ordering
    """
    if include_patterns is None:
        include_patterns = ["src/**/*.py"]
    
    if exclude_patterns is None:
        exclude_patterns = [
            "test",
            ".venv",
            "venv",
            "node_modules",
            "dist",
            "build",
            ".git",
            ".history",
            "raw",
            "outdir",
            "__pycache__",
            ".pytest_cache",
        ]
    
    files = []
    for pattern in include_patterns:
        for file_path in repo_root.glob(pattern):
            # Skip if any exclude pattern matches
            if any(exclude in str(file_path) for exclude in exclude_patterns):
                continue
            if file_path.is_file():
                files.append(file_path)
    
    # Sort for deterministic ordering
    return sorted(files)


def scan_for_pattern(
    pattern: Union[str, re.Pattern],
    repo_root: Optional[Path] = None,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    return_lines: bool = False,
) -> Union[List[Path], List[Tuple[Path, int, str]]]:
    """
    Scan production code files for a pattern.
    
    Args:
        pattern: String pattern (substring search) or compiled regex
        repo_root: Repository root (auto-detected if None)
        include_patterns: File patterns to include
        exclude_patterns: Path substrings to exclude
        return_lines: If True, return (path, line_no, line_text) tuples
        
    Returns:
        If return_lines=False: List of matching file paths
        If return_lines=True: List of (path, line_no, line_text) tuples
    """
    if repo_root is None:
        repo_root = find_repo_root()
    
    files = collect_production_files(repo_root, include_patterns, exclude_patterns)
    
    # Compile pattern if it's a string (treat as regex)
    if isinstance(pattern, str):
        try:
            regex = re.compile(pattern)
        except re.error:
            # If regex fails, treat as literal substring
            regex = None
            pattern_str = pattern
    else:
        regex = pattern
        pattern_str = None
    
    matches = []
    
    for file_path in files:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            # Skip files that can't be read
            continue
        
        if return_lines:
            # Return line-by-line matches
            for line_no, line in enumerate(content.splitlines(), start=1):
                if regex:
                    if regex.search(line):
                        matches.append((file_path, line_no, line))
                else:
                    if pattern_str in line:
                        matches.append((file_path, line_no, line))
        else:
            # Just check if file contains pattern
            if regex:
                if regex.search(content):
                    matches.append(file_path)
            else:
                if pattern_str in content:
                    matches.append(file_path)
    
    return matches


def scan_for_pattern_list_files(
    pattern: Union[str, re.Pattern],
    repo_root: Optional[Path] = None,
) -> str:
    """
    Scan for pattern and return newline-separated file list (like rg -l).
    
    Args:
        pattern: Pattern to search for
        repo_root: Repository root (auto-detected if None)
        
    Returns:
        Newline-separated string of matching file paths (relative to repo_root)
    """
    if repo_root is None:
        repo_root = find_repo_root()
    
    matches = scan_for_pattern(pattern, repo_root, return_lines=False)
    
    # Return relative paths, newline-separated
    return "\n".join(str(m.relative_to(repo_root)) for m in matches)

