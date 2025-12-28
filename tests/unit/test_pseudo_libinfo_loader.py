"""
Unit tests for pseudo libinfo bundle loader.

Tests verify that load_pseudo_libinfo_bundle() works correctly and
validates checksums without network access.
"""

from pathlib import Path

import pytest

from quantumvitas.core.pseudo_libinfo import load_pseudo_libinfo_bundle


def test_load_pseudo_libinfo_bundle() -> None:
    """
    Test that load_pseudo_libinfo_bundle() works and validates checksums.
    
    Assertions:
    1. bundle.tag == contents of CURRENT
    2. bundle.index["schema_version"] exists
    3. Computed manifest sha matches (implicitly by loader not raising)
    """
    # Find repo root
    repo_root = Path(__file__).parent.parent.parent
    
    # Load bundle
    bundle = load_pseudo_libinfo_bundle(repo_root=repo_root)
    
    # Verify bundle structure
    assert bundle.tag is not None
    assert bundle.root_dir.exists()
    assert isinstance(bundle.index, dict)
    assert isinstance(bundle.manifest, dict)
    assert isinstance(bundle.sha256sums, dict)
    
    # Verify tag matches CURRENT file
    current_file = repo_root / "resources" / "pseudo_libinfo" / "CURRENT"
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
    repo_root = Path(__file__).parent.parent.parent
    
    bundle1 = load_pseudo_libinfo_bundle(repo_root=repo_root)
    bundle2 = load_pseudo_libinfo_bundle(repo_root=repo_root)
    
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

