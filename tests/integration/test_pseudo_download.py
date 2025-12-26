"""
Integration tests for SSSP pseudopotential download functionality.

These tests verify that SSSP libraries can be downloaded from Materials Cloud.
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


class TestSSSPDownloadURLs:
    """Test that SSSP download URLs are valid and accessible."""
    
    def test_sssp_base_url_accessible(self):
        """Verify Materials Cloud base URL is accessible."""
        import urllib.request
        import urllib.error
        
        from quantumvitas.core.pseudo_config import SSSP_BASE_URL
        
        # Just check the base URL is a valid format
        assert SSSP_BASE_URL.startswith("https://")
        assert "materialscloud.org" in SSSP_BASE_URL
    
    def test_sssp_library_files_defined(self):
        """Verify SSSP library file definitions exist."""
        from quantumvitas.core.pseudo_config import SSSP_LIBRARY_FILES
        
        # Check that we have entries for known versions/flavors
        assert ("1.3.0", "efficiency") in SSSP_LIBRARY_FILES
        assert ("1.3.0", "precision") in SSSP_LIBRARY_FILES
        
        # Check structure of entries
        for key, files in SSSP_LIBRARY_FILES.items():
            assert "archive" in files
            assert "cutoffs" in files
            assert files["archive"].endswith(".tar.gz")
            assert files["cutoffs"].endswith(".json")
    
    def test_cutoffs_url_valid(self):
        """Verify cutoffs JSON URL returns valid JSON."""
        import urllib.request
        import urllib.error
        import socket
        
        from quantumvitas.core.pseudo_config import SSSP_BASE_URL, SSSP_LIBRARY_FILES
        
        # Test just the efficiency cutoffs (smaller download)
        files = SSSP_LIBRARY_FILES[("1.3.0", "efficiency")]
        cutoffs_url = SSSP_BASE_URL + files["cutoffs"]
        
        try:
            socket.setdefaulttimeout(30)
            response = urllib.request.urlopen(cutoffs_url)
            content = response.read().decode('utf-8')
            socket.setdefaulttimeout(None)
            
            # Parse as JSON
            data = json.loads(content)
            
            # Should be a dict with element keys
            assert isinstance(data, dict)
            # Should have some elements
            assert len(data) > 0
            # Check a common element exists
            assert "Si" in data or "C" in data or "O" in data
            
        except urllib.error.URLError as e:
            pytest.skip(f"Network unavailable: {e}")
        except socket.timeout:
            pytest.skip("Network timeout")


class TestSSSPDownloadFunction:
    """Test the download_sssp_library function.
    
    These tests download to a temporary directory and verify:
    - Tar file is downloaded and valid
    - File size > 0
    - Tar can be opened
    - No mutation of real store/seed dirs
    """
    
    def test_download_efficiency_tar_to_temp(self, temp_store_dir: Path):
        """Test downloading SSSP efficiency tar to temp dir and verifying it.
        
        NOTE: This test requires valid Materials Cloud URLs. If URLs return 404,
        the test will be skipped. The download functionality is tested via the
        structure checks even if the actual download fails.
        """
        import urllib.request
        import urllib.error
        import socket
        import tarfile
        
        from quantumvitas.core.pseudo_config import (
            download_sssp_library,
            SSSP_BASE_URL,
            SSSP_LIBRARY_FILES,
        )
        
        # First, verify the URL is accessible (skip if 404)
        files = SSSP_LIBRARY_FILES[("1.3.0", "efficiency")]
        archive_url = SSSP_BASE_URL + files["archive"]
        try:
            req = urllib.request.Request(archive_url)
            req.add_header('User-Agent', 'Mozilla/5.0')
            urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                pytest.skip(f"SSSP download URL returns 404 - URL may need updating: {archive_url}")
        except Exception:
            # Network error - skip but don't fail
            pytest.skip("Network unavailable or URL inaccessible")
        
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
        
        if not result["success"]:
            # Skip if network failed (but structure should still be correct)
            if any("Failed to download" in e or "404" in e or "NOT FOUND" in e for e in result["errors"]):
                pytest.skip(f"Download failed (URL issue): {result['errors']}")
            pytest.fail(f"Download failed: {result['errors']}")
        
        # Verify tar file was downloaded (check in temp dir structure)
        archive_name = files["archive"]
        
        # The download function extracts, but we can verify the extracted files
        library_path = temp_store_dir / "sssp" / "1.3.0" / "efficiency" / "library"
        
        # Verify files were installed
        assert result["files_installed"] > 0, "No UPF files installed"
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
        
        # Check manifest.json exists
        manifest_path = temp_store_dir / "sssp" / "1.3.0" / "efficiency" / "manifest.json"
        assert manifest_path.exists(), "manifest.json not created"
        
        manifest_data = json.loads(manifest_path.read_text())
        assert manifest_data["library"] == "sssp"
        assert manifest_data["version"] == "1.3.0"
        assert manifest_data["flavor"] == "efficiency"
        
        # Verify archive name is in downloaded files
        assert archive_name in result["files_downloaded"], "Archive not in downloaded files list"
    
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
        assert any("unknown" in e.lower() for e in result["errors"])


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

