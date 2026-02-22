"""
Unit tests for pseudo libinfo bundle loader.

Tests verify that load_pseudo_libinfo_bundle() works correctly and
validates checksums without network access.
"""

from pathlib import Path

import pytest

from qmatsuite.core.pseudo_libinfo import load_pseudo_libinfo_bundle
from qmatsuite.core.resources import get_resources_dir


def test_load_pseudo_libinfo_bundle() -> None:
    """
    Test that load_pseudo_libinfo_bundle() works and validates checksums.
    
    Assertions:
    1. bundle.tag == contents of CURRENT
    2. bundle.index["schema_version"] exists
    3. Computed manifest sha matches (implicitly by loader not raising)
    """
    bundle = load_pseudo_libinfo_bundle()
    
    # Verify bundle structure
    assert bundle.tag is not None
    assert bundle.root_dir.exists()
    assert isinstance(bundle.index, dict)
    assert isinstance(bundle.manifest, dict)
    assert isinstance(bundle.sha256sums, dict)
    
    # Verify tag matches CURRENT file
    current_file = get_resources_dir() / "pseudo_libinfo" / "CURRENT"
    if current_file.exists():
        current_tag = current_file.read_text(encoding="utf-8").strip()
        assert bundle.tag == current_tag, f"Bundle tag {bundle.tag} should match CURRENT {current_tag}"
    
    # Verify index has schema_version
    assert "schema_version" in bundle.index, "PSEUDO_FILE_INDEX.json should have schema_version"
    
    # Verify required files exist
    assert (bundle.root_dir / "PSEUDO_FILE_INDEX.json").exists()
    assert (bundle.root_dir / "MANIFEST_PSEUDO_SEED.json").exists()
    assert (bundle.root_dir / "SHA256SUMS.txt").exists()
    
    # Verify sha256sums dict has expected keys
    assert "PSEUDO_FILE_INDEX.json" in bundle.sha256sums
    assert "MANIFEST_PSEUDO_SEED.json" in bundle.sha256sums
    
    # Verify manifest sha256 matches index declaration (implicitly verified by loader)
    source_manifest = bundle.index.get("source_manifest", {})
    assert source_manifest.get("sha256") is not None
    assert source_manifest.get("path") == "MANIFEST_PSEUDO_SEED.json"


def test_load_pseudo_libinfo_bundle_caching() -> None:
    """Test that load_pseudo_libinfo_bundle() is cached (returns same object)."""
    bundle1 = load_pseudo_libinfo_bundle()
    bundle2 = load_pseudo_libinfo_bundle()
    
    # Should return same object due to lru_cache
    assert bundle1 is bundle2


def test_load_pseudo_libinfo_bundle_auto_detect_repo_root() -> None:
    """Test that load_pseudo_libinfo_bundle() can auto-detect repo root."""
    # Call without repo_root argument
    bundle = load_pseudo_libinfo_bundle()
    
    assert bundle.tag is not None
    assert bundle.root_dir.exists()
    assert isinstance(bundle.index, dict)
    assert isinstance(bundle.manifest, dict)


def test_load_pseudo_libinfo_bundle_missing_bundle_raises() -> None:
    """Test that missing bundle raises RuntimeError."""
    fake_root = Path("/nonexistent/path")
    
    with pytest.raises(RuntimeError, match="Pseudo libinfo root not found"):
        load_pseudo_libinfo_bundle(repo_root=fake_root)


def test_load_pseudo_libinfo_bundle_validates_sha_family() -> None:
    """Test that bundle loader validates sha_family presence in index entries."""
    bundle = load_pseudo_libinfo_bundle()
    
    # Verify all files have sha_family
    files = bundle.index.get("files", [])
    assert len(files) > 0, "Bundle should have at least one file entry"
    
    for file_entry in files:
        assert "sha_family" in file_entry, f"File entry missing sha_family: {file_entry.get('basename', 'unknown')}"
        assert isinstance(file_entry["sha_family"], str), "sha_family must be a string"
        assert len(file_entry["sha_family"]) > 0, "sha_family must be non-empty"
        
        # Verify no legacy sha_token fields
        assert "sha_token" not in file_entry, "File entry must not contain legacy sha_token"
        assert "pseudo_sha_token" not in file_entry, "File entry must not contain legacy pseudo_sha_token"


def test_load_pseudo_libinfo_bundle_validates_sha_family() -> None:
    """Test that bundle loader validates sha_family presence in index entries."""
    bundle = load_pseudo_libinfo_bundle()
    
    # Verify all files have sha_family
    files = bundle.index.get("files", [])
    assert len(files) > 0, "Bundle should have at least one file entry"
    
    for file_entry in files:
        assert "sha_family" in file_entry, f"File entry missing sha_family: {file_entry.get('basename', 'unknown')}"
        assert isinstance(file_entry["sha_family"], str), "sha_family must be a string"
        assert len(file_entry["sha_family"]) > 0, "sha_family must be non-empty"
        
        # Verify no legacy sha_token fields
        assert "sha_token" not in file_entry, "File entry must not contain legacy sha_token"
        assert "pseudo_sha_token" not in file_entry, "File entry must not contain legacy pseudo_sha_token"
