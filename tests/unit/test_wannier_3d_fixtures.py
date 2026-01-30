"""
Unit tests for Wannier90 3D fixtures discovery.
"""

import pytest
from pathlib import Path
from quantumvitas.daemon.server import QVDaemon
import io
import sys


def test_list_wannier_3d_fixtures():
    """Test that fixtures discovery works and returns expected fixtures."""
    daemon = QVDaemon(
        stdin=io.StringIO(),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    
    # Call handler
    result = daemon._handle_list_wannier_3d_fixtures({})
    
    # Assert fixtures found
    assert "fixtures" in result
    fixtures = result["fixtures"]
    assert len(fixtures) > 0, f"Expected at least 1 fixture, got {len(fixtures)}"
    
    # Assert structure
    for fixture in fixtures:
        assert "ulid" in fixture, f"Fixture missing 'ulid': {fixture}"
        assert "label" in fixture, f"Fixture missing 'label': {fixture}"
        assert "kind" in fixture, f"Fixture missing 'kind': {fixture}"
        assert "path" in fixture, f"Fixture missing 'path': {fixture}"
        assert fixture["kind"] in ("xsf", "bxsf"), f"Invalid kind: {fixture['kind']}"
        
        # Verify file exists
        assert Path(fixture["path"]).exists(), f"Fixture file does not exist: {fixture['path']}"
    
    # Assert expected fixtures present (by label matching)
    labels = [f["label"] for f in fixtures]
    
    # Check for example01/gaas_00001.xsf
    gaas_found = any("example01" in label and "gaas_00001" in label and label.endswith(".xsf") for label in labels)
    assert gaas_found, f"Expected example01/gaas_00001.xsf not found. Labels: {labels}"
    
    # Check for example02/lead.bxsf
    lead_found = any("example02" in label and "lead" in label and label.endswith(".bxsf") for label in labels)
    assert lead_found, f"Expected example02/lead.bxsf not found. Labels: {labels}"
    
    # Count by kind
    xsf_count = sum(1 for f in fixtures if f["kind"] == "xsf")
    bxsf_count = sum(1 for f in fixtures if f["kind"] == "bxsf")
    
    # Should have at least 4 XSF files (example01 has 4, example05 has 4)
    assert xsf_count >= 4, f"Expected at least 4 XSF files, got {xsf_count}"
    
    # Should have at least 2 BXSF files (example02 and example04)
    assert bxsf_count >= 2, f"Expected at least 2 BXSF files, got {bxsf_count}"


def test_list_wannier_3d_fixtures_with_env_var(monkeypatch, tmp_path):
    """Test that environment variable override works."""
    # Create a temporary fixtures directory
    test_fixtures_dir = tmp_path / "test_fixtures"
    test_fixtures_dir.mkdir()
    
    # Create a test fixture file
    test_file = test_fixtures_dir / "test.xsf"
    test_file.write_text("# Test XSF file\n")
    
    # Set environment variable
    monkeypatch.setenv("QMATSUITE_WANNIER_3D_FIXTURES", str(test_fixtures_dir))
    
    daemon = QVDaemon(
        stdin=io.StringIO(),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    
    result = daemon._handle_list_wannier_3d_fixtures({})
    
    assert "fixtures" in result
    # Should find the test file
    assert len(result["fixtures"]) >= 1
    assert any("test.xsf" in f["label"] for f in result["fixtures"])


def test_list_wannier_3d_fixtures_not_found(monkeypatch):
    """Test that missing fixtures directory raises error when all paths fail."""
    # Set environment variable to non-existent path
    monkeypatch.setenv("QMATSUITE_WANNIER_3D_FIXTURES", "/nonexistent/path/to/fixtures")
    
    # Also override the DEV fallback to non-existent
    # We need to patch the handler to skip repo derivation and DEV fallback
    # Since we can't easily mock Path(__file__), we'll use payload override
    daemon = QVDaemon(
        stdin=io.StringIO(),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    
    # Use payload to force a non-existent path (this overrides all priority checks)
    with pytest.raises(FileNotFoundError) as exc_info:
        daemon._handle_list_wannier_3d_fixtures({"fixture_dir": "/nonexistent/path/to/fixtures"})
    
    assert "not found" in str(exc_info.value).lower()
    assert "attempted paths" in str(exc_info.value).lower()

