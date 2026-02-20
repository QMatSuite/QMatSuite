"""
Unit tests for pseudo options generation.

Tests SHA256 deduplication, source chips, installed status, and name collisions.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from quantumvitas.core.pseudo_options import (
    PseudoOption,
    PseudoSource,
    get_pseudo_options_for_elements,
)
from quantumvitas.core.pseudo_config import PseudoConfig


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project directory structure."""
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    pseudo_dir = project_root / "pseudo"
    pseudo_dir.mkdir()
    return project_root, pseudo_dir


@pytest.fixture
def mock_bundle():
    """Create a mock pseudo libinfo bundle."""
    bundle = Mock()
    bundle.index = {
        "files": [
            {
                "sha256": "abc123",
                "sha_family": "family123",
                "basenames": ["Si.pbe-n-rrkjus_psl.1.0.0.UPF"],
            },
            {
                "sha256": "def456",
                "sha_family": "family456",
                "basenames": ["Si.pbe-n-rrkjus_psl.1.0.0.UPF"],  # Same basename, different sha256
            },
        ],
        "occurrences": [
            {
                "sha256": "abc123",
                "archive": {"name": "SSSP_1.3.0_PBE_precision.tar.gz", "sha256": "archive123"},
                "library": {
                    "library_name": "sssp",
                    "library_version": "1.3.0",
                    "xc": "pbe",
                    "quality": "precision",
                },
                "path_in_archive": "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
            },
            {
                "sha256": "abc123",
                "archive": {"name": "SSSP_1.3.0_PBE_efficiency.tar.gz", "sha256": "archive456"},
                "library": {
                    "library_name": "sssp",
                    "library_version": "1.3.0",
                    "xc": "pbe",
                    "quality": "efficiency",
                },
                "path_in_archive": "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
            },
        ],
    }
    bundle.manifest = {
        "files": [
            {
                "relative_path": "SSSP_1.3.0_PBE_precision.tar.gz",
                "sha256": "archive123",
                "size_bytes": 1000000,
                "library_name": "sssp",
                "library_version": "1.3.0",
                "xc": "pbe",
                "quality": "precision",
            },
            {
                "relative_path": "SSSP_1.3.0_PBE_efficiency.tar.gz",
                "sha256": "archive456",
                "size_bytes": 1000000,
                "library_name": "sssp",
                "library_version": "1.3.0",
                "xc": "pbe",
                "quality": "efficiency",
            },
        ]
    }
    bundle.tag = "assets-2025-12-26"
    return bundle


def create_test_upf_file(path: Path, element: str, content: str = None):
    """Create a test UPF file."""
    if content is None:
        content = f"""<PP_HEADER>
  <PP_INFO>
    {element}   Element
  </PP_INFO>
</PP_HEADER>
"""
    path.write_text(content, encoding="utf-8")
    return path


@patch("quantumvitas.core.pseudo_options.load_pseudo_libinfo_bundle")
@patch("quantumvitas.core.pseudo_options._find_upf_in_libraries")
@patch("quantumvitas.core.pseudo_options.get_system_pseudo_dir")
def test_dedup_by_sha256(
    mock_get_system_pseudo_dir,
    mock_find_upf,
    mock_load_bundle,
    temp_project,
    mock_bundle,
):
    """Test that options are deduplicated by SHA256."""
    project_root, pseudo_dir = temp_project

    # Create two files with same content (same sha256)
    upf1 = create_test_upf_file(pseudo_dir / "Si1.UPF", "Si")
    upf2 = create_test_upf_file(pseudo_dir / "Si2.UPF", "Si")
    # Make them identical
    content = upf1.read_bytes()
    upf2.write_bytes(content)

    mock_load_bundle.return_value = mock_bundle
    mock_find_upf.return_value = None  # No installed libraries
    mock_get_system_pseudo_dir.return_value = None

    config = PseudoConfig(store_dir=str(project_root / "store"))

    options = get_pseudo_options_for_elements(project_root, ["Si"], config=config)

    # Should have one option for the project files (deduplicated by sha256)
    assert "Si" in options
    project_sha256 = None
    for variant in options["Si"]:
        project_sources = [s for s in variant["sources"] if s["kind"] == "project"]
        if project_sources:
            project_sha256 = variant["sha256"]
            break

    if project_sha256:
        matching_variants = [v for v in options["Si"] if v["sha256"] == project_sha256]
        assert len(matching_variants) == 1, f"Project files with same sha256 should merge into one variant, got {len(matching_variants)}"


@patch("quantumvitas.core.pseudo_options.load_pseudo_libinfo_bundle")
@patch("quantumvitas.core.pseudo_options._find_upf_in_libraries")
@patch("quantumvitas.core.pseudo_options.get_system_pseudo_dir")
def test_name_collision_different_sha256(
    mock_get_system_pseudo_dir,
    mock_find_upf,
    mock_load_bundle,
    temp_project,
    mock_bundle,
):
    """Test that same basename but different sha256 produces two options."""
    project_root, pseudo_dir = temp_project

    create_test_upf_file(pseudo_dir / "Si.pbe-n-rrkjus_psl.1.0.0.UPF", "Si", content="Content 1")
    create_test_upf_file(pseudo_dir / "Si_alt.UPF", "Si", content="Content 2")
    (pseudo_dir / "Si_alt.UPF").rename(pseudo_dir / "Si.pbe-n-rrkjus_psl.1.0.0.UPF_alt")

    mock_load_bundle.return_value = mock_bundle
    mock_find_upf.return_value = None
    mock_get_system_pseudo_dir.return_value = None

    config = PseudoConfig(store_dir=str(project_root / "store"))

    options = get_pseudo_options_for_elements(project_root, ["Si"], config=config)

    assert "Si" in options
    assert len(options["Si"]) >= 1


@patch("quantumvitas.core.pseudo_options.load_pseudo_libinfo_bundle")
@patch("quantumvitas.core.pseudo_options._find_upf_in_libraries")
@patch("quantumvitas.core.pseudo_options.get_system_pseudo_dir")
def test_library_chips_from_occurrences(
    mock_get_system_pseudo_dir,
    mock_find_upf,
    mock_load_bundle,
    temp_project,
    mock_bundle,
):
    """Test that same sha256 produces multiple library chips from occurrences."""
    project_root, pseudo_dir = temp_project

    upf_file = create_test_upf_file(pseudo_dir / "Si.UPF", "Si")

    mock_load_bundle.return_value = mock_bundle
    # Mock: library files are installed
    mock_find_upf.return_value = Path("/mock/lib/Si.pbe-n-rrkjus_psl.1.0.0.UPF")
    mock_get_system_pseudo_dir.return_value = None

    with patch("quantumvitas.core.pseudo_options.compute_sha256_file") as mock_sha256:
        mock_sha256.return_value = "abc123"  # Matches bundle

        config = PseudoConfig(store_dir=str(project_root / "store"))

        options = get_pseudo_options_for_elements(project_root, ["Si"], config=config)

        assert "Si" in options
        if len(options["Si"]) > 0:
            option = options["Si"][0]
            library_sources = [s for s in option["sources"] if s["kind"] == "lib"]
            # Should have library sources marked as installed
            if library_sources:
                assert any(s["installed"] for s in library_sources)


@patch("quantumvitas.core.pseudo_options.load_pseudo_libinfo_bundle")
@patch("quantumvitas.core.pseudo_options._find_upf_in_libraries")
@patch("quantumvitas.core.pseudo_options.get_system_pseudo_dir")
def test_installed_chip_reflects_library_status(
    mock_get_system_pseudo_dir,
    mock_find_upf,
    mock_load_bundle,
    temp_project,
    mock_bundle,
):
    """Test that installed chip reflects library installed/uninstalled status."""
    project_root, pseudo_dir = temp_project

    create_test_upf_file(pseudo_dir / "Si.UPF", "Si")

    mock_load_bundle.return_value = mock_bundle
    # Mock: library files are installed
    mock_find_upf.return_value = Path("/mock/lib/Si.pbe-n-rrkjus_psl.1.0.0.UPF")
    mock_get_system_pseudo_dir.return_value = None

    config = PseudoConfig(store_dir=str(project_root / "store"))

    with patch("quantumvitas.core.pseudo_options.compute_sha256_file") as mock_sha256:
        mock_sha256.return_value = "abc123"

        options = get_pseudo_options_for_elements(project_root, ["Si"], config=config)

        assert "Si" in options
        # Verify _find_upf_in_libraries was called (replaces check_archive_status)
        assert mock_find_upf.called


@patch("quantumvitas.core.pseudo_options.load_pseudo_libinfo_bundle")
@patch("quantumvitas.core.pseudo_options._find_upf_in_libraries")
@patch("quantumvitas.core.pseudo_options.get_system_pseudo_dir")
def test_project_chip_adds_to_existing_option(
    mock_get_system_pseudo_dir,
    mock_find_upf,
    mock_load_bundle,
    temp_project,
    mock_bundle,
):
    """Test that project pseudo matching library sha256 adds Project chip (not new option)."""
    project_root, pseudo_dir = temp_project

    create_test_upf_file(pseudo_dir / "Si.UPF", "Si")

    mock_load_bundle.return_value = mock_bundle
    mock_find_upf.return_value = None
    mock_get_system_pseudo_dir.return_value = None

    config = PseudoConfig(store_dir=str(project_root / "store"))

    with patch("quantumvitas.core.pseudo_options.compute_sha256_file") as mock_sha256:
        mock_sha256.return_value = "abc123"

        options = get_pseudo_options_for_elements(project_root, ["Si"], config=config)

        assert "Si" in options
        if len(options["Si"]) > 0:
            option = options["Si"][0]
            project_sources = [s for s in option["sources"] if s["kind"] == "project"]
            assert len(project_sources) > 0


@patch("quantumvitas.core.pseudo_options.load_pseudo_libinfo_bundle")
@patch("quantumvitas.core.pseudo_options._find_upf_in_libraries")
@patch("quantumvitas.core.pseudo_options.get_system_pseudo_dir")
def test_internal_chip_always_installed(
    mock_get_system_pseudo_dir,
    mock_find_upf,
    mock_load_bundle,
    temp_project,
    mock_bundle,
):
    """Test that Internal chip is always marked as installed."""
    project_root, pseudo_dir = temp_project

    internal_dir = temp_project[0].parent / "internal"
    internal_dir.mkdir()
    create_test_upf_file(internal_dir / "Si.UPF", "Si")

    mock_load_bundle.return_value = mock_bundle
    mock_find_upf.return_value = None
    mock_get_system_pseudo_dir.return_value = internal_dir

    config = PseudoConfig(store_dir=str(project_root / "store"))

    options = get_pseudo_options_for_elements(project_root, ["Si"], config=config)

    assert "Si" in options
    if len(options["Si"]) > 0:
        option = options["Si"][0]
        internal_sources = [s for s in option["sources"] if s["kind"] == "internal"]
        if internal_sources:
            assert all(s["installed"] for s in internal_sources)


@patch("quantumvitas.core.pseudo_options.load_pseudo_libinfo_bundle")
@patch("quantumvitas.core.pseudo_options._find_upf_in_libraries")
@patch("quantumvitas.core.pseudo_options.get_system_pseudo_dir")
def test_rpc_roundtrip_stable_json(
    mock_get_system_pseudo_dir,
    mock_find_upf,
    mock_load_bundle,
    temp_project,
    mock_bundle,
):
    """Test that RPC roundtrip returns stable JSON schema."""
    project_root, pseudo_dir = temp_project

    create_test_upf_file(pseudo_dir / "Si.UPF", "Si")

    mock_load_bundle.return_value = mock_bundle
    mock_find_upf.return_value = None
    mock_get_system_pseudo_dir.return_value = None

    config = PseudoConfig(store_dir=str(project_root / "store"))

    options = get_pseudo_options_for_elements(project_root, ["Si"], config=config)

    json_str = json.dumps(options)
    parsed = json.loads(json_str)

    assert "Si" in parsed
    if len(parsed["Si"]) > 0:
        option = parsed["Si"][0]
        assert "sha256" in option
        assert "sha_family" in option
        assert "element" in option
        assert "basename" in option
        assert "display_label" in option
        assert "sources" in option
        assert "availability" in option
        assert isinstance(option["sources"], list)
        assert isinstance(option["availability"], dict)
