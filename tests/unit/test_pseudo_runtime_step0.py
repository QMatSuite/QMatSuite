"""
Unit tests for Step0 pseudo runtime preparation (constitution-compliant).

Tests verify that prepare_project_pseudos_for_run() correctly handles:
- Noop (same sha256)
- Overwrite (same sha_family, different sha256)
- Rename existing (different sha_family, same basename)
- Analyzer is read-only (no filesystem mutations)
- Calc refresh updates records correctly
"""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from quantumvitas.core.pseudo_libinfo import (
    compute_sha256_bytes,
    compute_sha_family_file,
)


def compute_sha256_file(path: Path) -> str:
    """Compute SHA256 hash of a file."""
    data = path.read_bytes()
    return compute_sha256_bytes(data)
from quantumvitas.core.pseudo_runtime import (
    analyze_project_pseudo_effects,
    prepare_project_pseudos_for_run,
    refresh_calc_pseudo_records_after_step0,
    species_map_to_selections,
    update_project_calcs_filename_by_sha_family,
    PseudoSelection,
)


def create_dummy_pseudo_file(path: Path, content: str = "DUMMY UPF CONTENT\n") -> tuple[str, str]:
    """Create a dummy UPF file and return (sha256, sha_family)."""
    path.write_text(content, encoding="utf-8")
    sha256 = compute_sha256_file(path)
    sha_family = compute_sha_family_file(path)
    return sha256, sha_family


def create_dummy_pseudo_file_different_family(path: Path, content: str = "DIFFERENT UPF CONTENT\n") -> tuple[str, str]:
    """Create a dummy UPF file with different family and return (sha256, sha_family)."""
    path.write_text(content, encoding="utf-8")
    sha256 = compute_sha256_file(path)
    sha_family = compute_sha_family_file(path)
    return sha256, sha_family


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project with project.qv.yml and pseudo directory."""
    import yaml
    
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    
    # Create project.qv.yml
    project_config = {
        "project": {
            "name": "Test Project",
            "id": "test-project-id",
        }
    }
    (project_root / "project.qv.yml").write_text(yaml.safe_dump(project_config))
    
    # Create pseudo directory
    pseudo_dir = project_root / "pseudo"
    pseudo_dir.mkdir()
    
    return project_root


@pytest.fixture
def temp_calculation(temp_project: Path) -> Path:
    """Create a temporary calculation directory with calculation.yaml."""
    import yaml
    
    calc_dir = temp_project / "calculations" / "test-calc"
    calc_dir.mkdir(parents=True)
    
    calc_yaml = {
        "meta": {
            "id": "test-calc-id",
            "name": "Test Calculation",
            "slug": "test-calc",
            "path": "calculations/test-calc",
            "kind": "calculation",
        },
        "structure_id": "test-structure-id",
        "species_map": {
            "Si": {
                "pseudopot": "Si.upf",
                "pseudo_sha256": "",
                "pseudo_sha_family": "",
            }
        },
        "steps": [],
    }
    (calc_dir / "calculation.yaml").write_text(yaml.safe_dump(calc_yaml))
    
    return calc_dir


def test_step0_noop_project_source(temp_project: Path) -> None:
    """
    Test noop: selection resolves to project/pseudo with matching sha256.
    
    Step0 should do nothing (no file change, no rename), but still refresh calc records.
    """
    # Create existing file in project/pseudo
    project_pseudo = temp_project / "pseudo" / "Si.upf"
    existing_sha256, existing_sha_family = create_dummy_pseudo_file(project_pseudo, "Si UPF content\n")
    
    # Create selection with project source (sha256 matches project file)
    selections = [
        PseudoSelection(
            element="Si",
            requested_basename="Si.upf",
            requested_sha256=existing_sha256,
            requested_sha_family=existing_sha_family,
            source_kind="project",  # Project selection
            source_path=None,  # Project selection doesn't need source_path
        )
    ]
    
    # Run Step0
    report = prepare_project_pseudos_for_run(temp_project, selections)
    
    # Verify noop action
    noop_actions = [a for a in report.actions if a.action == "noop"]
    assert len(noop_actions) > 0, "Should have noop action"
    assert noop_actions[0].element == "Si"
    assert "existing project pseudo" in noop_actions[0].detail.lower()
    
    # Verify file unchanged
    assert project_pseudo.exists()
    assert compute_sha256_file(project_pseudo) == existing_sha256


def test_step0_noop_same_sha256(temp_project: Path, tmp_path: Path) -> None:
    """
    Test noop: project already has Si.upf with same sha256 as selected internal/lib.
    
    Step0 should do nothing (no file change, no rename).
    """
    # Create existing file in project/pseudo
    project_pseudo = temp_project / "pseudo" / "Si.upf"
    existing_sha256, existing_sha_family = create_dummy_pseudo_file(project_pseudo, "Si UPF content\n")
    
    # Create source file (internal) with same content
    internal_pseudo = tmp_path / "internal" / "Si.upf"
    internal_pseudo.parent.mkdir()
    source_sha256, source_sha_family = create_dummy_pseudo_file(internal_pseudo, "Si UPF content\n")
    
    assert existing_sha256 == source_sha256, "Files should have same sha256"
    assert existing_sha_family == source_sha_family, "Files should have same sha_family"
    
    # Create selection
    selections = [
        PseudoSelection(
            element="Si",
            requested_basename="Si.upf",
            requested_sha256=source_sha256,
            requested_sha_family=source_sha_family,
            source_kind="internal",
            source_path=internal_pseudo,
        )
    ]
    
    # Run Step0
    report = prepare_project_pseudos_for_run(temp_project, selections)
    
    # Verify noop action
    noop_actions = [a for a in report.actions if a.action == "noop"]
    assert len(noop_actions) > 0, "Should have noop action"
    assert noop_actions[0].element == "Si"
    
    # Verify file unchanged
    assert project_pseudo.exists()
    assert compute_sha256_file(project_pseudo) == existing_sha256


def test_step0_overwrite_same_family_different_sha256(temp_project: Path, tmp_path: Path) -> None:
    """
    Test overwrite: project has Si.upf with same sha_family but different sha256.
    
    Step0 should overwrite with canonical (internal/lib) version.
    """
    # Create existing file in project/pseudo (different bytes, same family)
    project_pseudo = temp_project / "pseudo" / "Si.upf"
    # Use content that produces same family but different bytes
    existing_content = "Si UPF content\n"
    existing_sha256, existing_sha_family = create_dummy_pseudo_file(project_pseudo, existing_content)
    
    # Create canonical source (same family, different bytes due to whitespace)
    internal_pseudo = tmp_path / "internal" / "Si.upf"
    internal_pseudo.parent.mkdir()
    canonical_content = "Si    UPF    content\n"  # More spaces, same family (whitespace stripped)
    source_sha256, source_sha_family = create_dummy_pseudo_file(internal_pseudo, canonical_content)
    
    assert existing_sha_family == source_sha_family, "Files should have same sha_family"
    assert existing_sha256 != source_sha256, "Files should have different sha256"
    
    # Create selection
    selections = [
        PseudoSelection(
            element="Si",
            requested_basename="Si.upf",
            requested_sha256=source_sha256,
            requested_sha_family=source_sha_family,
            source_kind="internal",
            source_path=internal_pseudo,
        )
    ]
    
    # Run Step0
    report = prepare_project_pseudos_for_run(temp_project, selections)
    
    # Verify overwrite action
    overwrite_actions = [a for a in report.actions if a.action == "overwrite"]
    assert len(overwrite_actions) > 0, "Should have overwrite action"
    assert overwrite_actions[0].element == "Si"
    
    # Verify file content changed to canonical
    assert project_pseudo.exists()
    assert compute_sha256_file(project_pseudo) == source_sha256
    assert compute_sha_family_file(project_pseudo) == source_sha_family


def test_step0_rename_different_family_same_basename(temp_project: Path, tmp_path: Path, temp_calculation: Path) -> None:
    """
    Test rename: project has Si.upf family A, user selects Si.upf family B.
    
    Step0 should:
    1. Rename existing file to disambiguated filename (__fam-<sha_family[:10]>)
    2. Copy new canonical to Si.upf
    3. Update calcs referencing family A by sha_family
    """
    # Create existing file in project/pseudo (family A)
    project_pseudo = temp_project / "pseudo" / "Si.upf"
    existing_sha256, existing_sha_family = create_dummy_pseudo_file(project_pseudo, "Si UPF content A\n")
    
    # Update calc to reference this file
    calc_yaml_path = temp_calculation / "calculation.yaml"
    calc_yaml_dict = yaml.safe_load(calc_yaml_path.read_text())
    calc_yaml_dict["species_map"]["Si"] = {
        "pseudopot": "Si.upf",
        "pseudo_sha256": existing_sha256,
        "pseudo_sha_family": existing_sha_family,
    }
    calc_yaml_path.write_text(yaml.safe_dump(calc_yaml_dict))
    
    # Create canonical source (family B, different content)
    internal_pseudo = tmp_path / "internal" / "Si.upf"
    internal_pseudo.parent.mkdir()
    source_sha256, source_sha_family = create_dummy_pseudo_file_different_family(internal_pseudo, "Si UPF content B\n")
    
    assert existing_sha_family != source_sha_family, "Files should have different sha_family"
    
    # Create selection
    selections = [
        PseudoSelection(
            element="Si",
            requested_basename="Si.upf",
            requested_sha256=source_sha256,
            requested_sha_family=source_sha_family,
            source_kind="internal",
            source_path=internal_pseudo,
        )
    ]
    
    # Run Step0
    report = prepare_project_pseudos_for_run(temp_project, selections)
    
    # Verify rename action
    rename_actions = [a for a in report.actions if a.action == "rename_existing"]
    assert len(rename_actions) > 0, "Should have rename action"
    assert rename_actions[0].element == "Si"
    assert rename_actions[0].renamed_from is not None
    assert rename_actions[0].renamed_to is not None
    
    # Verify renamed filename contains __fam- prefix
    assert "__fam-" in rename_actions[0].renamed_to.name, "Renamed file should have __fam- prefix"
    
    # Verify existing file renamed
    renamed_path = temp_project / "pseudo" / rename_actions[0].renamed_to.name
    assert renamed_path.exists(), f"Renamed file should exist at {renamed_path}"
    assert compute_sha256_file(renamed_path) == existing_sha256
    assert compute_sha_family_file(renamed_path) == existing_sha_family
    
    # Verify new canonical copied
    assert project_pseudo.exists()
    assert compute_sha256_file(project_pseudo) == source_sha256
    assert compute_sha_family_file(project_pseudo) == source_sha_family
    
    # Verify calc record was updated by Step0 (Step0 calls update_project_calcs_filename_by_sha_family internally)
    calc_data_after = yaml.safe_load(calc_yaml_path.read_text())
    assert calc_data_after["species_map"]["Si"]["pseudopot"] == renamed_path.name
    assert calc_data_after["species_map"]["Si"]["pseudo_sha_family"] == existing_sha_family  # Unchanged


def test_analyzer_read_only(temp_project: Path, tmp_path: Path) -> None:
    """
    Test that analyzer never mutates filesystem (monkeypatch should never be called).
    """
    # Create existing file
    project_pseudo = temp_project / "pseudo" / "Si.upf"
    existing_sha256, existing_sha_family = create_dummy_pseudo_file(project_pseudo)
    
    # Create source file
    internal_pseudo = tmp_path / "internal" / "Si.upf"
    internal_pseudo.parent.mkdir()
    source_sha256, source_sha_family = create_dummy_pseudo_file_different_family(internal_pseudo)
    
    selections = [
        PseudoSelection(
            element="Si",
            requested_basename="Si.upf",
            requested_sha256=source_sha256,
            requested_sha_family=source_sha_family,
            source_kind="internal",
            source_path=internal_pseudo,
        )
    ]
    
    # Monkeypatch filesystem operations to raise if called
    with patch('pathlib.Path.mkdir', side_effect=RuntimeError("BUG: mkdir called in analyzer")):
        with patch('shutil.copy2', side_effect=RuntimeError("BUG: copy2 called in analyzer")):
            with patch('pathlib.Path.rename', side_effect=RuntimeError("BUG: rename called in analyzer")):
                # Analyzer should not raise
                report = analyze_project_pseudo_effects(temp_project, selections)
                
                # Should have warnings/actions but no mutations
                assert isinstance(report.actions, list)
                assert isinstance(report.warnings, list)
                assert isinstance(report.errors, list)


def test_calc_refresh_after_step0(temp_project: Path, temp_calculation: Path) -> None:
    """
    Test that refresh_calc_pseudo_records_after_step0 updates calc with actual file info.
    """
    # Create project file (after Step0)
    project_pseudo = temp_project / "pseudo" / "Si.upf"
    actual_sha256, actual_sha_family = create_dummy_pseudo_file(project_pseudo, "Si UPF content\n")
    
    # Load initial calc
    calc_yaml = temp_calculation / "calculation.yaml"
    with open(calc_yaml) as f:
        calc_data = yaml.safe_load(f)
    
    # Update species_map
    calc_data["species_map"]["Si"] = {
        "pseudopot": "Si.upf",
        "pseudo_sha256": "old_sha256",
        "pseudo_sha_family": "old_sha_family",
        "pseudo_basename": "Si.upf",
    }
    
    with open(calc_yaml, "w") as f:
        yaml.safe_dump(calc_data, f)
    
    # Run refresh (pass species_map, not selections)
    species_map = calc_data["species_map"]
    refresh_calc_pseudo_records_after_step0(temp_project, temp_calculation, species_map)
    
    # Verify calc record updated
    with open(calc_yaml) as f:
        updated_calc = yaml.safe_load(f)
    
    si_entry = updated_calc["species_map"]["Si"]
    assert si_entry["pseudo_sha256"] == actual_sha256, "sha256 should be updated"
    assert si_entry["pseudo_sha_family"] == actual_sha_family, "sha_family should be updated"
    assert si_entry["pseudopot"] == "Si.upf", "filename should be preserved"


def test_species_map_to_selections(temp_project: Path) -> None:
    """Test conversion of species_map to PseudoSelection list."""
    # Create existing file in project
    project_pseudo = temp_project / "pseudo" / "Si.upf"
    existing_sha256, existing_sha_family = create_dummy_pseudo_file(project_pseudo)
    
    species_map = {
        "Si": {
            "pseudopot": "Si.upf",
            "pseudo_sha256": existing_sha256,
            "pseudo_sha_family": existing_sha_family,
        }
    }
    
    selections = species_map_to_selections(temp_project, species_map)
    
    assert len(selections) == 1
    assert selections[0].element == "Si"
    assert selections[0].requested_basename == "Si.upf"
    assert selections[0].requested_sha256 == existing_sha256
    assert selections[0].requested_sha_family == existing_sha_family
    assert selections[0].source_kind == "project"


def test_refresh_calc_pseudo_records_missing_file(temp_project: Path) -> None:
    """
    Test refresh_calc_pseudo_records_after_step0() behavior when file is missing.
    
    Expected: Log warning and keep stored triplet unchanged (no mutation).
    """
    from quantumvitas.core.pseudo_runtime import refresh_calc_pseudo_records_after_step0
    from quantumvitas.core.models import CalculationModel, save_calculation, load_calculation, ResourceMeta
    import logging
    
    # Create calculation with pseudo_basename but file doesn't exist
    calc_dir = temp_project / "calculations" / "test_calc"
    calc_dir.mkdir(parents=True)
    calc_yaml = calc_dir / "calculation.yaml"
    
    # Create calc with stored triplet
    stored_sha256 = "abc123" * 8  # Fake sha256
    stored_sha_family = "def456" * 8  # Fake sha_family
    
    # Use correct CalculationModel constructor with ResourceMeta
    calc_model = CalculationModel(
        meta=ResourceMeta(
            id="test-calc-id",
            name="Test Calc",
            slug="test-calc",
            path="calculations/test_calc",
            kind="calculation",
        ),
        species_map={
            "Si": {
                "pseudopot": "Si.upf",
                "pseudo_basename": "Si.upf",
                "pseudo_sha256": stored_sha256,
                "pseudo_sha_family": stored_sha_family,
            }
        }
    )
    save_calculation(calc_model, calc_yaml)
    
    # Ensure file does NOT exist
    project_pseudo = temp_project / "pseudo"
    project_pseudo.mkdir(exist_ok=True)
    missing_file = project_pseudo / "Si.upf"
    if missing_file.exists():
        missing_file.unlink()
    
    # Capture log warnings
    import io
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.WARNING)
    logger = logging.getLogger("quantumvitas.core.pseudo_runtime")
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    
    try:
        # Call refresh
        species_map = calc_model.species_map or {}
        refresh_calc_pseudo_records_after_step0(
            temp_project,
            calc_dir,
            species_map,
        )
        
        # Verify warning was logged
        log_output = log_capture.getvalue()
        assert "not found" in log_output.lower() or "missing" in log_output.lower(), \
            f"Expected warning about missing file, got: {log_output}"
        
        # Verify stored triplet unchanged (reload and check)
        reloaded = load_calculation(calc_yaml, project_root=temp_project)
        si_entry = reloaded.species_map.get("Si")
        assert si_entry is not None, "Si entry should exist"
        assert isinstance(si_entry, dict), "Si entry should be dict"
        
        # Stored values should be unchanged
        assert si_entry.get("pseudo_sha256") == stored_sha256, \
            "pseudo_sha256 should remain unchanged when file missing"
        assert si_entry.get("pseudo_sha_family") == stored_sha_family, \
            "pseudo_sha_family should remain unchanged when file missing"
        assert si_entry.get("pseudo_basename") == "Si.upf", \
            "pseudo_basename should remain unchanged when file missing"
    finally:
        logger.removeHandler(handler)

