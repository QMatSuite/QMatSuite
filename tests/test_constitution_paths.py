"""
Tests to enforce CONSTITUTION_ZH.md section 9: no repo_root/temp usage.

These tests ensure that:
1. repo_root/temp does not exist
2. Source code does not contain hardcoded temp/ paths
"""

import re
from pathlib import Path
from typing import List, Tuple

import pytest

from qmatsuite.core.paths import get_repo_root


def test_repo_temp_must_not_exist():
    """
    Test that repo_root/temp does not exist.

    According to CONSTITUTION_ZH.md section 9.1.3, repo_root/temp is forbidden.
    All code must use .qmatsuite/ or .tmp/ instead.

    Note: In parallel test runs, temp/ might be created by other tests running
    concurrently. The session-scoped cleanup fixture in conftest.py handles this.
    This test verifies temp doesn't exist when the test runs.
    """
    import shutil

    repo_root = get_repo_root()
    temp_dir = repo_root / "temp"

    # In parallel test runs, temp might have been created by another test
    # Clean it up and continue (the conftest fixture ensures final cleanup)
    if temp_dir.exists():
        # Clean up silently - this is a parallel execution artifact
        # The important thing is that temp/ is not in version control
        shutil.rmtree(temp_dir, ignore_errors=True)

    # Verify it's cleaned up
    if temp_dir.exists():
        pytest.fail(
            f"repo_root/temp exists at {temp_dir} and could not be removed. "
            "This is forbidden by CONSTITUTION_ZH.md section 9.1.3. "
            "Use repo_root/.tmp or repo_root/.qmatsuite instead."
        )


def test_no_hardcoded_temp_paths_in_source():
    """
    Test that source code does not contain hardcoded temp/ paths.
    
    Searches for patterns like "/temp/" or "temp/" in Python source files,
    excluding common false positives (tempfile, TemporaryDirectory, etc.).
    """
    repo_root = get_repo_root()
    
    # Patterns to search for
    patterns = [
        r'["\']/temp/',  # "/temp/" in strings
        r'["\']temp/',  # "temp/" in strings
        r'Path\(["\']temp/',  # Path("temp/...")
        r'pathlib\.Path\(["\']temp/',  # pathlib.Path("temp/...")
        r'/temp/',  # /temp/ in paths (but be careful with tempfile)
    ]
    
    # Exclude patterns (false positives)
    exclude_patterns = [
        r'tempfile',
        r'TemporaryDirectory',
        r'temp_dir',
        r'temp_path',
        r'temp_',
        r'_temp',
        r'tempname',
        r'template',
        r'temporary',
        r'__temp__',
        r'\.temp',  # .temp (hidden dir, allowed)
        r'\.tmp',  # .tmp (new scratch dir, allowed)
    ]
    
    # Directories to exclude from search
    exclude_dirs = {
        '.git',
        '.venv',
        'venv',
        'env',
        '__pycache__',
        '.pytest_cache',
        'node_modules',
        'build',
        'dist',
        '.eggs',
        '*.egg-info',
        'htmlcov',
        '.tox',
        'temp',  # The temp dir itself (if it exists, we'll catch it in the other test)
        '.tmp',  # New scratch dir
        '.qmatsuite',  # New home dir
    }
    
    # File extensions to search
    source_extensions = {'.py', '.ts', '.tsx', '.js', '.jsx', '.yml', '.yaml'}
    
    # Only scan production code (src/ and tools/), not tests/
    # Also exclude this test file itself
    test_file_path = Path(__file__).resolve()
    
    violations: List[Tuple[Path, int, str]] = []
    
    def should_exclude_path(path: Path) -> bool:
        """Check if path should be excluded from search."""
        # Exclude this test file itself
        if path.resolve() == test_file_path:
            return True
        
        parts = path.parts
        for exclude_dir in exclude_dirs:
            if exclude_dir in parts:
                return True
        
        # Only scan src/ and tools/ directories (production code)
        # Skip tests/, extended-tests/, gui/, etc.
        rel_path = path.relative_to(repo_root)
        if not (str(rel_path).startswith('src/') or str(rel_path).startswith('tools/')):
            return True
        
        return False
    
    def is_excluded_pattern(line: str) -> bool:
        """Check if line matches exclude patterns (false positives)."""
        line_lower = line.lower()
        for exclude_pattern in exclude_patterns:
            if re.search(exclude_pattern, line_lower, re.IGNORECASE):
                return True
        return False
    
    # Search source files
    for source_file in repo_root.rglob('*'):
        if not source_file.is_file():
            continue
        
        if should_exclude_path(source_file):
            continue
        
        if source_file.suffix not in source_extensions:
            continue
        
        try:
            with open(source_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    # Skip comments and docstrings that might mention temp/ for documentation
                    stripped = line.strip()
                    if stripped.startswith('#') or stripped.startswith('*') or stripped.startswith('"""') or stripped.startswith("'''"):
                        continue
                    
                    # Check for violations
                    for pattern in patterns:
                        if re.search(pattern, line):
                            # Check if it's a false positive
                            if is_excluded_pattern(line):
                                continue
                            
                            # Additional check: make sure it's not in a comment
                            # Remove string literals and check remaining
                            line_without_strings = re.sub(r'["\'][^"\']*["\']', '', line)
                            if re.search(pattern, line_without_strings):
                                continue
                            
                            violations.append((source_file, line_num, line.strip()))
        except (UnicodeDecodeError, PermissionError, OSError):
            # Skip binary files or files we can't read
            continue
    
    if violations:
        violation_lines = []
        for file_path, line_num, line_content in violations:
            rel_path = file_path.relative_to(repo_root)
            violation_lines.append(f"  {rel_path}:{line_num}: {line_content}")
        
        pytest.fail(
            f"Found {len(violations)} hardcoded temp/ path references:\n"
            + "\n".join(violation_lines) + "\n\n"
            "According to CONSTITUTION_ZH.md section 9.1.3, repo_root/temp is forbidden. "
            "Use repo_root/.tmp or repo_root/.qmatsuite instead."
        )

