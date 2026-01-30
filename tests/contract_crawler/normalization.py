"""Response normalization utilities for golden comparison.

This module is shared between:
- worktree_runner.py (runs in 0873ebf worktree)
- golden_comparison.py (runs on HEAD)
"""

from typing import Any


# Non-deterministic fields to normalize (expanded for v0 compat testing)
NORMALIZE_FIELDS = {
    # ULIDs - truly non-deterministic
    "id", "structure_ulid", "calc_id", "step_id", "run_id", "job_id",
    "calculation_id", "entry_id", "calculation_ulid", "target_ulid",
    "target_name", "step", "calculation", "parent_calculation_id",
    # ULID-derived fields (suffix = last 6 chars of ULID)
    "suffix",
    # Arrays of IDs
    "structure_ulids",
    # Timestamps - truly non-deterministic
    "created_at", "updated_at", "started_at", "completed_at", "timestamp",
    "cached_at", "generated_at",
    # Paths containing temp directories - non-deterministic due to temp path
    "project_root", "log_path", "io_dir", "path", "absolute_path",
    "output_file", "resolved_path", "metadata_path_abs",
    # QE detection paths - vary by environment
    "qe_home", "qe_bin_dir", "pw_path", "current_bin_dir",
    # Engine discovery fields - engine_id varies
    "engine_id",
    # Environment info - vary by system
    "python_version", "python_executable", "qv_version",
    # Session IDs - UUIDs
    "session_id",
}

# Nested fields to normalize (dot notation)
NORMALIZE_NESTED = {
    "meta.id", "meta.created_at", "meta.updated_at", "meta.path",
    "prefix_outdir_injection.effective_prefix",
}


import re

# ULID pattern: 26 uppercase alphanumeric chars
ULID_PATTERN = re.compile(r'^[0-9A-Z]{26}$')

# Temp path patterns
TEMP_PATH_PATTERNS = [
    r'/var/folders/',
    r'/private/var/folders/',
    r'/tmp/',
    r'/private/tmp/',
    r'pytest-',
    r'qv_recipe_',
    r'qv_golden_',
]

# Patterns for paths that should be normalized within message strings
# These match absolute paths that vary by environment
PATH_IN_STRING_PATTERNS = [
    # QE executable paths (e.g., "pw.x found at /path/to/pw.x")
    re.compile(r'(/[^\s]+/(?:pw|ph|dos|bands|projwfc|pp)\.x(?:\.exe)?)'),
    # QE engine paths (e.g., ".qmatsuite/engines/qe/...")
    re.compile(r'(/[^\s]+/\.qmatsuite/engines/[^\s]+)'),
    # Project paths (e.g., "Project exists: /path/to/project")
    re.compile(r'((?:Project exists|Project path)[:\s]+)(/[^\s]+)'),
    # Generic absolute paths after "at " or ": "
    re.compile(r'(at |: )(/(?:Users|home|var|private|tmp)[^\s]+)'),
    # Paths in parentheses (e.g., "QE q-e-qe-7.5 (/Users/...)")
    re.compile(r'(\()(/(?:Users|home|var|private|tmp)[^\s\)]+)(\))'),
    # Created dir messages (e.g., "Created store dir: /path/to/dir")
    re.compile(r'(Created (?:store|seed) dir: )(/[^\s]+)'),
]


def _is_ulid_like(value: str) -> bool:
    """Check if value looks like a ULID."""
    return bool(ULID_PATTERN.match(value))


def _is_temp_path(value: str) -> bool:
    """Check if value is a temp path."""
    return any(pattern in value for pattern in TEMP_PATH_PATTERNS)


def _normalize_paths_in_string(value: str) -> str:
    """Normalize absolute paths embedded in message strings."""
    result = value
    for pattern in PATH_IN_STRING_PATTERNS:
        # Replace paths with normalized placeholder, preserving prefix/suffix
        if pattern.groups == 1:
            # Pattern captures just the path
            result = pattern.sub('<NORMALIZED_PATH>', result)
        elif pattern.groups == 2:
            # Pattern captures prefix + path
            result = pattern.sub(r'\1<NORMALIZED_PATH>', result)
        elif pattern.groups == 3:
            # Pattern captures prefix + path + suffix (e.g., parentheses)
            result = pattern.sub(r'\1<NORMALIZED_PATH>\3', result)
    return result


def normalize_value(key: str, value: Any, parent_key: str = "") -> Any:
    """
    Normalize non-deterministic fields for comparison.

    Uses both key-based and value-based heuristics:
    - If key in NORMALIZE_FIELDS or full_key in NORMALIZE_NESTED, replace with placeholder
    - If value looks like a ULID, normalize it
    - If value is a temp path, normalize it
    """
    full_key = f"{parent_key}.{key}" if parent_key else key

    # Check if this field should be normalized (key-based)
    if key in NORMALIZE_FIELDS or full_key in NORMALIZE_NESTED:
        # Determine placeholder by field name
        if "timestamp" in key.lower() or key in ("created_at", "updated_at", "started_at", "completed_at", "cached_at", "generated_at"):
            return "<NORMALIZED_TIMESTAMP>"
        elif "path" in key.lower() or key in ("project_root", "log_path", "io_dir", "absolute_path", "output_file", "resolved_path", "metadata_path_abs", "qe_home", "qe_bin_dir", "pw_path", "python_executable", "current_bin_dir"):
            return "<NORMALIZED_PATH>"
        else:
            # Default: ID-like fields
            return "<NORMALIZED_ID>"

    # Value-based heuristics for strings
    if isinstance(value, str):
        # Check for ULID-like values
        if _is_ulid_like(value):
            return "<NORMALIZED_ID>"
        # Check for temp paths
        if _is_temp_path(value):
            return "<NORMALIZED_PATH>"
        # Normalize paths embedded in message and label strings (when they contain paths)
        if key in ("message", "label") or "message" in key.lower():
            normalized = _normalize_paths_in_string(value)
            if normalized != value:
                return normalized

    # Recursively normalize dicts and lists
    if isinstance(value, dict):
        return {k: normalize_value(k, v, full_key) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize_value(key, item, parent_key) for item in value]

    return value


def normalize_response(response_data: dict) -> dict:
    """Normalize response for golden comparison."""
    return {k: normalize_value(k, v) for k, v in response_data.items()}
