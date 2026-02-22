"""
Corpus loading and validation for the demo store.

Reads corpus_index.yaml and individual case.yaml files,
validates them against the spec, and provides access to corpus data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


def _corpus_root() -> Path:
    """Find the corpus root directory."""
    # Walk up from this file to find repo root
    current = Path(__file__).resolve().parent
    while current != current.parent:
        candidate = current / "tests" / "inputformat" / "samples"
        if candidate.exists():
            return candidate
        if (current / "pyproject.toml").exists():
            return current / "tests" / "inputformat" / "samples"
        current = current.parent
    raise RuntimeError("Could not find corpus root (tests/inputformat/samples/)")


def load_corpus_index(corpus_root: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load and parse corpus_index.yaml.

    Args:
        corpus_root: Path to corpus root. If None, auto-detected.

    Returns:
        Parsed corpus index dict with 'schema_version' and 'entries' keys.
    """
    if corpus_root is None:
        corpus_root = _corpus_root()
    index_path = corpus_root / "corpus_index.yaml"
    if not index_path.exists():
        raise FileNotFoundError(f"Corpus index not found: {index_path}")
    with open(index_path, "r") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "entries" not in data:
        raise ValueError(f"Invalid corpus index format: missing 'entries' key")
    return data


def load_case_yaml(case_dir: Path) -> Dict[str, Any]:
    """
    Load and parse a case.yaml file.

    Args:
        case_dir: Path to the corpus case directory.

    Returns:
        Parsed case.yaml dict.
    """
    case_path = case_dir / "case.yaml"
    if not case_path.exists():
        raise FileNotFoundError(f"case.yaml not found: {case_path}")
    with open(case_path, "r") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid case.yaml format: {case_path}")
    return data


def get_eligible_cases(
    corpus_root: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Get all demo-eligible corpus cases from the index.

    Returns:
        List of index entries where demo_eligible is True.
    """
    index = load_corpus_index(corpus_root)
    return [e for e in index["entries"] if e.get("demo_eligible")]


def validate_case_yaml(case_data: Dict[str, Any], index_entry: Dict[str, Any]) -> List[str]:
    """
    Validate a case.yaml against its corpus_index entry (Rule CI6).

    Args:
        case_data: Parsed case.yaml dict.
        index_entry: Corresponding corpus_index entry.

    Returns:
        List of validation error messages (empty if valid).
    """
    errors = []

    # Required fields in case.yaml
    # Note: 'species' is optional for classical codes like LAMMPS (they use atom types)
    for field in ("case_id", "engine", "title", "description", "workflow_tags"):
        if field not in case_data:
            errors.append(f"Missing required field: {field}")

    # Translation metadata
    for field in ("demo_eligible", "step_type_gen", "step_type_spec"):
        if field not in case_data:
            errors.append(f"Missing translation metadata field: {field}")

    # Cross-check with index entry (Rule CI6)
    for field in ("demo_eligible", "demo_slug", "engine", "case_id"):
        case_val = case_data.get(field)
        index_val = index_entry.get(field)
        if case_val != index_val:
            errors.append(
                f"Mismatch on '{field}': case.yaml={case_val!r}, index={index_val!r}"
            )

    # If demo_eligible, must have demo_slug
    if case_data.get("demo_eligible") and not case_data.get("demo_slug"):
        errors.append("demo_eligible is true but demo_slug is missing")

    # If not demo_eligible, must have exclusion_reason
    if not case_data.get("demo_eligible") and not case_data.get("exclusion_reason"):
        errors.append("demo_eligible is false but exclusion_reason is missing")

    return errors


def resolve_corpus_dir(
    engine: str,
    dir_name: str,
    corpus_root: Optional[Path] = None,
) -> Path:
    """
    Resolve a corpus case directory from engine and dir_name.

    Args:
        engine: Engine name (e.g., "vasp").
        dir_name: Directory name within the engine dir.
        corpus_root: Corpus root path (auto-detected if None).

    Returns:
        Absolute path to the case directory.
    """
    if corpus_root is None:
        corpus_root = _corpus_root()
    case_dir = corpus_root / engine / dir_name
    if not case_dir.exists():
        raise FileNotFoundError(f"Corpus case directory not found: {case_dir}")
    return case_dir
