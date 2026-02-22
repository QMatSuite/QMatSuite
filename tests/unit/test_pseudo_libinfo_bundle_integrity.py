"""
Unit tests for pseudo libinfo bundle integrity pinning.

These tests ensure that bundle integrity checks are enforced and will
fail deterministically if bundle files are manually edited without
updating checksums.
"""

import json
import shutil
from pathlib import Path

import pytest

from qmatsuite.core.pseudo_libinfo import load_pseudo_libinfo_bundle
from qmatsuite.core.resources import get_resources_dir


def test_pseudo_libinfo_bundle_loads_successfully() -> None:
    """
    Test that load_pseudo_libinfo_bundle() loads successfully with default behavior.
    
    Assertions:
    - Bundle is loaded
    - schema_version exists
    - Index has expected fields
    """
    bundle = load_pseudo_libinfo_bundle()
    
    assert bundle is not None
    assert bundle.tag is not None
    assert bundle.root_dir.exists()
    assert isinstance(bundle.index, dict)
    assert isinstance(bundle.manifest, dict)
    
    # Verify schema_version exists
    assert "schema_version" in bundle.index
    assert bundle.index["schema_version"] is not None
    
    # Verify expected top-level fields
    assert "files" in bundle.index
    assert "occurrences" in bundle.index
    assert "source_manifest" in bundle.index


def test_pseudo_libinfo_sha256sums_verification_enforced(tmp_path: Path) -> None:
    """
    Test that SHA256SUMS verification is actually enforced.
    
    Strategy:
    1. Copy CURRENT bundle files into tmp dir under same folder structure
    2. Modify ONE BYTE in PSEUDO_FILE_INDEX.json (append a space)
    3. Keep SHA256SUMS.txt unchanged
    4. Call load_pseudo_libinfo_bundle(repo_root=tmp_root)
    5. Assert it raises with clear error about checksum mismatch
    """
    # Find repo root
    # Copy bundle structure to tmp
    src_bundle_root = get_resources_dir() / "pseudo_libinfo"
    tmp_bundle_root = tmp_path / "resources" / "pseudo_libinfo"
    
    # Read CURRENT to get tag
    current_file = src_bundle_root / "CURRENT"
    if not current_file.exists():
        pytest.skip("CURRENT file not found - bundle not installed")
    
    tag = current_file.read_text(encoding="utf-8").strip()
    src_bundle_dir = src_bundle_root / tag
    
    if not src_bundle_dir.exists():
        pytest.skip(f"Bundle directory not found: {src_bundle_dir}")
    
    # Copy entire bundle structure
    tmp_bundle_root.mkdir(parents=True, exist_ok=True)
    tmp_bundle_dir = tmp_bundle_root / tag
    shutil.copytree(src_bundle_dir, tmp_bundle_dir)
    
    # Copy CURRENT file
    shutil.copy2(current_file, tmp_bundle_root / "CURRENT")
    
    # Modify PSEUDO_FILE_INDEX.json by appending a space
    index_file = tmp_bundle_dir / "PSEUDO_FILE_INDEX.json"
    original_content = index_file.read_text(encoding="utf-8")
    modified_content = original_content + " "  # Append one space
    index_file.write_text(modified_content, encoding="utf-8")
    
    # SHA256SUMS.txt is unchanged (still has old checksum)
    
    # Attempt to load - should raise RuntimeError about checksum mismatch
    with pytest.raises(RuntimeError, match="SHA256 mismatch"):
        load_pseudo_libinfo_bundle(repo_root=tmp_path)


def test_manifest_sha_matches_index_declaration() -> None:
    """
    Test that manifest SHA256 matches the declared value in index.
    
    This test must fail if the manifest is edited (even whitespace changes)
    without updating the declared sha in the index.
    """
    bundle = load_pseudo_libinfo_bundle()
    
    # Get declared manifest SHA from index
    source_manifest = bundle.index.get("source_manifest", {})
    declared_sha256 = source_manifest.get("sha256")
    
    assert declared_sha256 is not None, "Index must declare source_manifest.sha256"
    
    # Compute actual manifest SHA256
    manifest_file = bundle.root_dir / "MANIFEST_PSEUDO_SEED.json"
    assert manifest_file.exists()
    
    # Use the internal _compute_sha256 logic (read raw bytes)
    import hashlib
    sha256_hash = hashlib.sha256()
    with open(manifest_file, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    computed_sha256 = sha256_hash.hexdigest()
    
    # Assert they match
    assert computed_sha256 == declared_sha256, (
        f"Manifest SHA256 mismatch:\n"
        f"  Declared in index: {declared_sha256}\n"
        f"  Computed from file: {computed_sha256}\n"
        f"If this fails, the manifest was edited without updating the index declaration."
    )
