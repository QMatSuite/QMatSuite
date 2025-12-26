"""
Integration tests for SSSP pseudopotential download functionality.

These tests verify that SSSP libraries can be downloaded from GitHub release.
They require network access and may take time to complete.

Run with:
    pytest tests/integration/test_pseudo_download.py -v
    
To skip network tests in CI, use:
    pytest -m "not network"
"""

import json
import tempfile
from pathlib import Path
from typing import Generator

import pytest


# Mark all tests in this module as requiring network
pytestmark = pytest.mark.network


@pytest.fixture
def temp_store_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for pseudo store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestSSSPManifest:
    """Test manifest fetching and parsing."""
    
    def test_fetch_manifest(self):
        """Test that manifest can be fetched from GitHub release."""
        from quantumvitas.core.pseudo_config import fetch_manifest
        
        manifest = fetch_manifest()
        
        # Should have entries
        assert len(manifest) > 0
        
        # Check structure of entries
        for entry in manifest[:5]:  # Check first 5 entries
            assert hasattr(entry, "relative_path")
            assert hasattr(entry, "size_bytes")
            assert hasattr(entry, "sha256")
            assert hasattr(entry, "category")
            assert hasattr(entry, "library_name")
            assert hasattr(entry, "library_version")
            assert hasattr(entry, "xc")
            assert hasattr(entry, "quality")
    
    def test_select_sssp_entries(self):
        """Test selecting SSSP entries from manifest."""
        from quantumvitas.core.pseudo_config import fetch_manifest, select_sssp_entries
        
        manifest = fetch_manifest()
        sssp_entries = select_sssp_entries(manifest, version="1.3.0", xc="pbe")
        
        # Should have efficiency and precision
        assert ("1.3.0", "efficiency") in sssp_entries
        assert ("1.3.0", "precision") in sssp_entries
        
        # Each should have exactly 2 entries (tar.gz + json)
        for key, entries in sssp_entries.items():
            assert len(entries) == 2, f"Expected 2 entries for {key}, got {len(entries)}"
            has_tar = any(e.relative_path.endswith(".tar.gz") for e in entries)
            has_json = any(e.relative_path.endswith(".json") for e in entries)
            assert has_tar, f"Missing tar.gz for {key}"
            assert has_json, f"Missing json for {key}"


class TestSSSPDownloadFunction:
    """Test the download_sssp_library function.
    
    These tests download to a temporary directory and verify:
    - Tar file is downloaded and valid
    - File size > 0
    - Tar can be opened
    - No mutation of real store/seed dirs
    """
    
    def test_download_efficiency_tar_to_temp(self, temp_store_dir: Path):
        """Test downloading SSSP efficiency from GitHub release with SHA256 verification.
        
        This test:
        - Fetches manifest from GitHub release
        - Downloads SSSP_1.3.0_PBE_efficiency.tar.gz and .json
        - Verifies SHA256 checksums against manifest
        - Extracts tar and verifies UPF files
        - Verifies cutoffs.json loads correctly
        
        If download fails, test FAILS (no skip).
        """
        import tarfile
        
        from quantumvitas.core.pseudo_config import (
            download_sssp_library,
            fetch_manifest,
            select_sssp_entries,
        )
        
        # Download to temp store dir (not real store)
        result = download_sssp_library(
            store_dir=temp_store_dir,
            flavor="efficiency",
            version="1.3.0",
            force=True,
            allow_download=True,
        )
        
        # Check result structure
        assert "success" in result
        assert "version" in result
        assert "flavor" in result
        assert "files_downloaded" in result
        assert "files_installed" in result
        assert "messages" in result
        assert "errors" in result
        
        # If download failed, test FAILS (no skip)
        if not result["success"]:
            pytest.fail(f"Download failed: {result['errors']}")
        
        # Verify files were installed
        assert result["files_installed"] > 0, "No UPF files installed"
        
        library_path = temp_store_dir / "sssp" / "1.3.0" / "efficiency" / "library"
        assert library_path.exists(), f"Library path not created: {library_path}"
        
        # Check UPF files exist
        upf_files = list(library_path.glob("*.UPF"))
        assert len(upf_files) > 0, "No UPF files found"
        
        # Verify at least one UPF file has content
        first_upf = upf_files[0]
        assert first_upf.stat().st_size > 0, f"UPF file is empty: {first_upf}"
        
        # Check cutoffs.json exists and is valid
        cutoffs_path = temp_store_dir / "sssp" / "1.3.0" / "efficiency" / "cutoffs.json"
        assert cutoffs_path.exists(), "cutoffs.json not created"
        assert cutoffs_path.stat().st_size > 0, "cutoffs.json is empty"
        
        # Verify cutoffs.json is valid JSON
        cutoffs_data = json.loads(cutoffs_path.read_text())
        assert isinstance(cutoffs_data, dict)
        assert len(cutoffs_data) > 0
        
        # Check manifest.json exists and has correct source info
        manifest_path = temp_store_dir / "sssp" / "1.3.0" / "efficiency" / "manifest.json"
        assert manifest_path.exists(), "manifest.json not created"
        
        manifest_data = json.loads(manifest_path.read_text())
        assert manifest_data["library"] == "sssp"
        assert manifest_data["version"] == "1.3.0"
        assert manifest_data["flavor"] == "efficiency"
        assert manifest_data["source"] == "github_release"
        assert "source_release" in manifest_data
        assert "manifest_sha256" in manifest_data
        
        # Verify downloaded files list includes expected files
        assert len(result["files_downloaded"]) >= 2, "Expected at least 2 files (tar.gz + json)"
        assert any("SSSP_1.3.0_PBE_efficiency.tar.gz" in f for f in result["files_downloaded"])
        assert any("SSSP_1.3.0_PBE_efficiency.json" in f for f in result["files_downloaded"])
    
    def test_download_verifies_sha256(self, temp_store_dir: Path):
        """Test that download verifies SHA256 checksums from manifest."""
        from quantumvitas.core.pseudo_config import (
            fetch_manifest,
            select_sssp_entries,
            download_github_release_asset,
            compute_sha256,
        )
        import tempfile
        
        # Fetch manifest and get efficiency entry
        manifest = fetch_manifest()
        sssp_entries = select_sssp_entries(manifest, version="1.3.0", xc="pbe")
        efficiency_entries = sssp_entries[("1.3.0", "efficiency")]
        archive_entry = next(e for e in efficiency_entries if e.relative_path.endswith(".tar.gz"))
        
        # Download with verification
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_temp = temp_path / Path(archive_entry.relative_path).name
            
            # This should succeed and verify SHA256
            download_github_release_asset(
                asset_name=Path(archive_entry.relative_path).name,
                output_path=archive_temp,
                expected_size=archive_entry.size_bytes,
                expected_sha256=archive_entry.sha256,
            )
            
            # Verify file exists and has correct size
            assert archive_temp.exists()
            assert archive_temp.stat().st_size == archive_entry.size_bytes
            
            # Verify SHA256 matches
            actual_sha256 = compute_sha256(archive_temp)
            assert actual_sha256.lower() == archive_entry.sha256.lower(), \
                f"SHA256 mismatch: expected {archive_entry.sha256}, got {actual_sha256}"
    
    def test_download_already_installed_skips(self, temp_store_dir: Path):
        """Test that re-downloading already installed library skips gracefully."""
        from quantumvitas.core.pseudo_config import download_sssp_library, get_sssp_library_path
        
        # Create a fake "installed" library in temp dir
        library_path = get_sssp_library_path(temp_store_dir, "1.3.0", "efficiency")
        (library_path / "library").mkdir(parents=True)
        (library_path / "library" / "Si.UPF").write_text("fake UPF content")
        
        # Verify fake file exists
        assert (library_path / "library" / "Si.UPF").exists()
        assert (library_path / "library" / "Si.UPF").stat().st_size > 0
        
        # Try to download - should skip (library already exists)
        result = download_sssp_library(
            store_dir=temp_store_dir,
            flavor="efficiency",
            version="1.3.0",
            force=True,
            allow_download=True,
        )
        
        # Should succeed but warn about already installed
        assert result["success"]
        assert any("already installed" in w.lower() for w in result.get("warnings", []))
    
    def test_download_not_allowed_fails(self, temp_store_dir: Path):
        """Test that download fails when not allowed and force is False."""
        from quantumvitas.core.pseudo_config import download_sssp_library
        
        result = download_sssp_library(
            store_dir=temp_store_dir,
            flavor="efficiency",
            version="1.3.0",
            force=False,
            allow_download=False,
        )
        
        assert not result["success"]
        assert any("not allowed" in e.lower() for e in result["errors"])
    
    def test_download_invalid_flavor_fails(self, temp_store_dir: Path):
        """Test that invalid flavor fails gracefully."""
        from quantumvitas.core.pseudo_config import download_sssp_library
        
        result = download_sssp_library(
            store_dir=temp_store_dir,
            flavor="invalid_flavor",
            version="1.3.0",
            force=True,
            allow_download=True,
        )
        
        assert not result["success"]
        assert any("invalid" in e.lower() or "not found" in e.lower() for e in result["errors"])


class TestSSSPDownloadAll:
    """Test the download_all_sssp function."""
    
    def test_download_all_structure(self, temp_store_dir: Path):
        """Test download_all_sssp returns correct structure."""
        from quantumvitas.core.pseudo_config import download_all_sssp
        
        # Don't actually download - just test with allow_download=False
        result = download_all_sssp(
            store_dir=temp_store_dir,
            force=False,
            allow_download=False,
        )
        
        # Should have installed, skipped, failed lists
        assert "installed" in result
        assert "skipped" in result
        assert "failed" in result
        assert "messages" in result
        assert isinstance(result["installed"], list)
        assert isinstance(result["skipped"], list)
        assert isinstance(result["failed"], list)
        
        # Each failed entry should have version, flavor, errors
        for lib_result in result["failed"]:
            assert "version" in lib_result
            assert "flavor" in lib_result
            assert "errors" in lib_result


class TestPseudoConfigValidation:
    """Test pseudo config validation."""
    
    def test_validate_pseudo_config(self, temp_store_dir: Path):
        """Test validate_pseudo_config function."""
        from quantumvitas.core.pseudo_config import (
            PseudoConfig,
            validate_pseudo_config,
            ValidationResult,
        )
        
        config = PseudoConfig(
            store_dir=str(temp_store_dir / "store"),
            seed_dir=str(temp_store_dir / "seed"),
            allow_download=False,
        )
        
        result = validate_pseudo_config(config)
        
        # Check result is ValidationResult with expected attributes
        assert isinstance(result, ValidationResult)
        assert hasattr(result, "ok")
        assert hasattr(result, "repo_pseudo_exists")
        assert hasattr(result, "store_dir_exists")
        assert hasattr(result, "store_dir_writable")
        assert hasattr(result, "seed_dir_exists")
        assert hasattr(result, "messages")
        assert hasattr(result, "errors")
        
        # Check to_dict works
        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)
        assert "ok" in result_dict


class TestListInstalledSSP:
    """Test listing installed SSSP libraries."""
    
    def test_list_installed_empty(self, temp_store_dir: Path):
        """Test listing when no libraries installed."""
        from quantumvitas.core.pseudo_config import list_installed_sssp
        
        result = list_installed_sssp(temp_store_dir)
        
        assert isinstance(result, list)
        assert len(result) == 0
    
    def test_list_installed_with_library(self, temp_store_dir: Path):
        """Test listing with a fake installed library."""
        from quantumvitas.core.pseudo_config import (
            list_installed_sssp,
            get_sssp_library_path,
        )
        
        # Create a fake installed library
        library_path = get_sssp_library_path(temp_store_dir, "1.3.0", "efficiency")
        (library_path / "library").mkdir(parents=True)
        (library_path / "library" / "Si.UPF").write_text("fake")
        (library_path / "library" / "C.UPF").write_text("fake")
        (library_path / "manifest.json").write_text(json.dumps({
            "library": "sssp",
            "version": "1.3.0",
            "flavor": "efficiency",
        }))
        
        result = list_installed_sssp(temp_store_dir)
        
        assert len(result) == 1
        assert result[0].version == "1.3.0"
        assert result[0].flavor == "efficiency"
        assert result[0].file_count == 2
        assert result[0].installed is True


# Run a quick smoke test if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-x"])

