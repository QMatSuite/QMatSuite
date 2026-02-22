"""
Runtime loader for pseudo library identification metadata bundle.

This module loads vendor metadata from qmatsuite/resources/pseudo_libinfo/<tag>/
without any network access. It verifies SHA256 checksums and cross-validates
the manifest against the index.

Also provides sha_family normalization functions for deterministic
pseudopotential file identification.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict

from qmatsuite.core.resources import get_resources_dir


@dataclass
class PseudoLibInfoBundle:
    """Container for pseudo library identification metadata."""
    
    tag: str
    root_dir: Path
    index: dict
    manifest: dict
    sha256sums: Dict[str, str]  # filename -> sha256


def _compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file (raw bytes)."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def compute_sha256_bytes(data: bytes) -> str:
    """
    Compute SHA256 hash of raw bytes.
    
    Args:
        data: Raw bytes to hash
        
    Returns:
        Hexadecimal SHA256 hash string
    """
    return hashlib.sha256(data).hexdigest()


def compute_sha_family_text(text: str) -> str:
    """
    Compute sha_family from text by removing all whitespace and hashing.
    
    Algorithm:
    1. Remove all whitespace characters (any char where ch.isspace() is True)
    2. Hash the resulting canonical string (UTF-8 bytes) with SHA256
    
    This makes sha_family stable across:
    - Any whitespace changes (spaces, tabs, CRLF/LF, etc.)
    - Multiple spaces, blank lines, etc.
    
    Args:
        text: Text content to process
        
    Returns:
        Hexadecimal SHA256 hash of whitespace-stripped text
        
    Raises:
        ValueError: If canonical string becomes empty after stripping
    """
    # Remove all whitespace characters
    canonical = ''.join(ch for ch in text if not ch.isspace())
    
    # Debug assert: ensure no whitespace remains
    assert not any(ch.isspace() for ch in canonical), "Canonical string should contain zero whitespace"
    
    # Check for empty result
    if not canonical:
        raise ValueError("sha_family computation failed: text contains only whitespace")
    
    # Hash UTF-8 encoded canonical string
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_sha_family_file(path: Path) -> str:
    """
    Compute sha_family from a file (reads as text with UTF-8, errors="replace").
    
    Args:
        path: Path to file to read
        
    Returns:
        Hexadecimal SHA256 hash of whitespace-stripped text content
        
    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If file contains only whitespace
    """
    # Read as text with UTF-8, replacing invalid bytes
    text = path.read_text(encoding="utf-8", errors="replace")
    return compute_sha_family_text(text)


@lru_cache(maxsize=1)
def load_pseudo_libinfo_bundle(repo_root: Path | None = None) -> PseudoLibInfoBundle:
    """
    Load pseudo library identification metadata bundle.
    
    This function:
    1. Locates the CURRENT pseudo libinfo bundle
    2. Verifies SHA256SUMS.txt
    3. Loads PSEUDO_FILE_INDEX.json and MANIFEST_PSEUDO_SEED.json
    4. Cross-checks that manifest sha256 matches index declaration
    
    Args:
        repo_root: Optional repository root path. If None, auto-detected.
        
    Returns:
        PseudoLibInfoBundle with loaded data
        
    Raises:
        RuntimeError: If bundle cannot be found, files are missing, or checksums don't match
    """
    if repo_root is not None:
        root = Path(repo_root)
        is_repo_root = (
            (root / "pyproject.toml").is_file()
            and (root / "src" / "qmatsuite").is_dir()
        )
        if is_repo_root:
            # Repo checkout: bundled metadata is under src/qmatsuite/resources.
            candidates = [
                root / "src" / "qmatsuite" / "resources" / "pseudo_libinfo",
                root / "pseudo_libinfo",
            ]
        else:
            # Package/test roots: allow package-local resources or direct pseudo_libinfo.
            candidates = [
                root / "resources" / "pseudo_libinfo",
                root / "src" / "qmatsuite" / "resources" / "pseudo_libinfo",
                root / "pseudo_libinfo",
            ]
        pseudo_libinfo_root = next(
            (candidate for candidate in candidates if candidate.exists()),
            candidates[0],
        )
    else:
        pseudo_libinfo_root = get_resources_dir() / "pseudo_libinfo"
    
    if not pseudo_libinfo_root.exists():
        raise RuntimeError(
            f"Pseudo libinfo root not found: {pseudo_libinfo_root}. "
            f"Run tools/build_pseudo_libinfo_bundle.py to install metadata."
        )
    
    # Read CURRENT pointer
    current_file = pseudo_libinfo_root / "CURRENT"
    if not current_file.exists():
        raise RuntimeError(
            f"CURRENT pointer not found: {current_file}. "
            f"Run tools/build_pseudo_libinfo_bundle.py to install metadata."
        )
    
    tag = current_file.read_text(encoding="utf-8").strip()
    if not tag:
        raise RuntimeError(f"CURRENT file is empty: {current_file}")
    
    bundle_dir = pseudo_libinfo_root / tag
    if not bundle_dir.exists():
        raise RuntimeError(
            f"Bundle directory not found: {bundle_dir} (tag: {tag}). "
            f"Run tools/build_pseudo_libinfo_bundle.py --tag {tag} to install metadata."
        )
    
    # Required files
    index_file = bundle_dir / "PSEUDO_FILE_INDEX.json"
    manifest_file = bundle_dir / "MANIFEST_PSEUDO_SEED.json"
    sha256sums_file = bundle_dir / "SHA256SUMS.txt"
    
    for required_file in [index_file, manifest_file, sha256sums_file]:
        if not required_file.exists():
            raise RuntimeError(
                f"Required file not found in bundle {tag}: {required_file.name}"
            )
    
    # Verify SHA256SUMS.txt
    with open(sha256sums_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    
    if len(lines) != 2:
        raise RuntimeError(
            f"SHA256SUMS.txt has {len(lines)} lines, expected 2 (tag: {tag})"
        )
    
    sha256sums: Dict[str, str] = {}
    for line in lines:
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise RuntimeError(
                f"Invalid SHA256SUMS.txt line format: {line!r} (tag: {tag})"
            )
        sha256sums[parts[1]] = parts[0]
    
    # Verify each file listed in SHA256SUMS.txt
    for filename, expected_sha256 in sha256sums.items():
        file_path = bundle_dir / filename
        if not file_path.exists():
            raise RuntimeError(
                f"File listed in SHA256SUMS.txt not found: {filename} (tag: {tag})"
            )
        computed_sha256 = _compute_sha256(file_path)
        if computed_sha256 != expected_sha256:
            raise RuntimeError(
                f"SHA256 mismatch for {filename} (tag: {tag}):\n"
                f"  Expected: {expected_sha256}\n"
                f"  Got:      {computed_sha256}"
            )
    
    # Load JSON files
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            index_data = json.load(f)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse PSEUDO_FILE_INDEX.json (tag: {tag}): {e}") from e
    
    try:
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse MANIFEST_PSEUDO_SEED.json (tag: {tag}): {e}") from e
    
    # Cross-check: manifest sha256 must match index declaration
    source_manifest = index_data.get("source_manifest", {})
    expected_manifest_sha256 = source_manifest.get("sha256")
    expected_manifest_path = source_manifest.get("path")
    
    if not expected_manifest_sha256:
        raise RuntimeError(
            f"PSEUDO_FILE_INDEX.json missing source_manifest.sha256 (tag: {tag})"
        )
    
    if expected_manifest_path != "MANIFEST_PSEUDO_SEED.json":
        raise RuntimeError(
            f"PSEUDO_FILE_INDEX.json source_manifest.path mismatch (tag: {tag}): "
            f"expected 'MANIFEST_PSEUDO_SEED.json', got {expected_manifest_path!r}"
        )
    
    computed_manifest_sha256 = _compute_sha256(manifest_file)
    if computed_manifest_sha256 != expected_manifest_sha256:
        raise RuntimeError(
            f"Manifest SHA256 mismatch (tag: {tag}):\n"
            f"  Expected (from index): {expected_manifest_sha256}\n"
            f"  Got (computed):        {computed_manifest_sha256}"
        )
    
    # Strict schema validation: check for sha_family and sha_token
    files = index_data.get("files", [])
    if not isinstance(files, list):
        raise RuntimeError(
            f"PSEUDO_FILE_INDEX.json 'files' must be a list (tag: {tag})"
        )
    
    for i, file_entry in enumerate(files):
        if not isinstance(file_entry, dict):
            raise RuntimeError(
                f"PSEUDO_FILE_INDEX.json files[{i}] must be a dict (tag: {tag})"
            )
        
        # Check for legacy sha_token field (must not exist)
        if "sha_token" in file_entry or "pseudo_sha_token" in file_entry:
            raise RuntimeError(
                f"PSEUDO_FILE_INDEX.json files[{i}] contains legacy sha_token field (tag: {tag}). "
                f"Migration to sha_family is complete - sha_token must not appear in bundle."
            )
        
        # Check for required sha_family field
        if "sha_family" not in file_entry:
            raise RuntimeError(
                f"PSEUDO_FILE_INDEX.json files[{i}] missing required 'sha_family' field (tag: {tag}). "
                f"All index entries must have sha_family (migration from sha_token is complete)."
            )
        
        # Validate sha_family is a non-empty string
        sha_family = file_entry.get("sha_family")
        if not isinstance(sha_family, str) or not sha_family:
            raise RuntimeError(
                f"PSEUDO_FILE_INDEX.json files[{i}] has invalid sha_family (tag: {tag}): "
                f"must be a non-empty string, got {type(sha_family).__name__}"
            )
    
    # Check manifest for legacy fields
    if isinstance(manifest_data, dict):
        # Check top-level keys
        if "sha_token" in manifest_data or "pseudo_sha_token" in manifest_data:
            raise RuntimeError(
                f"MANIFEST_PSEUDO_SEED.json contains legacy sha_token field (tag: {tag}). "
                f"Migration to sha_family is complete - sha_token must not appear in bundle."
            )
        
        # Check entries if manifest has a list/array structure
        entries = manifest_data.get("entries", manifest_data.get("files", []))
        if isinstance(entries, list):
            for i, entry in enumerate(entries):
                if isinstance(entry, dict):
                    if "sha_token" in entry or "pseudo_sha_token" in entry:
                        raise RuntimeError(
                            f"MANIFEST_PSEUDO_SEED.json entries[{i}] contains legacy sha_token field (tag: {tag}). "
                            f"Migration to sha_family is complete - sha_token must not appear in bundle."
                        )
    
    return PseudoLibInfoBundle(
        tag=tag,
        root_dir=bundle_dir,
        index=index_data,
        manifest=manifest_data,
        sha256sums=sha256sums,
    )
