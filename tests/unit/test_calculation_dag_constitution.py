"""
Test DAG + ID-only constitution for calculation.yaml files.

This test ensures that calculation.yaml files only persist structure_id (ULID)
and do NOT persist structure_name or structure selector fields.
"""
import json
import yaml
from pathlib import Path

import pytest

from quantumvitas.core.models import CalculationModel, ResourceMeta, save_calculation, load_calculation
from quantumvitas.core.resources import generate_resource_id
from quantumvitas.io.structure_io import STRUCTURE_META_KEY, STRUCTURE_DATA_KEY


def test_calculation_yaml_only_persists_structure_id(tmp_path):
    """Test that calculation.yaml only contains structure_id, not structure_name or structure."""
    calc_dir = tmp_path / "calculations" / "test-calculation"
    calc_dir.mkdir(parents=True)
    
    structure_id = generate_resource_id()
    structure_name = "Test Structure"
    structure_selector = "test-structure"
    
    # Create calculation model with structure_id only (DAG + ULID model)
    model = CalculationModel(
        meta=ResourceMeta(
            id=generate_resource_id(),
            name="Test Calculation",
            slug="test-calculation",
            path="calculations/test-calculation",
            kind="calculation",
        ),
        structure_id=structure_id,
        structure_name=structure_name,  # In-memory only (cosmetic)
        mode="normal",
        working_dir="raw",
        steps=[],
    )
    
    # Save calculation.yaml
    save_calculation(model, calc_dir)
    
    # Load and verify on-disk YAML
    yaml_path = calc_dir / "calculation.yaml"
    assert yaml_path.exists()
    
    on_disk = yaml.safe_load(yaml_path.read_text())
    
    # DAG + ID-only constitution: only structure_id is persisted
    assert "structure_id" in on_disk, "calculation.yaml must contain structure_id"
    assert on_disk["structure_id"] == structure_id
    
    # These fields must NOT be persisted
    assert "structure_name" not in on_disk, "calculation.yaml must NOT contain structure_name"
    assert "structure" not in on_disk, "calculation.yaml must NOT contain structure selector"
    
    # Verify we can still load the model (structure_name/structure are in-memory only)
    loaded = load_calculation(calc_dir, tmp_path)
    assert loaded.structure_id == structure_id
    # structure_name and structure may be None after loading (not persisted)
    # but that's OK - they're in-memory convenience fields


def test_calculation_roundtrip_strips_legacy_fields(tmp_path):
    """Test that loading and saving a calculation strips legacy fields."""
    calc_dir = tmp_path / "calculations" / "roundtrip"
    calc_dir.mkdir(parents=True)
    
    structure_id = generate_resource_id()
    
    # Create calculation.yaml with legacy fields (simulating old format)
    legacy_yaml = {
        "meta": {
            "id": generate_resource_id(),
            "name": "Roundtrip Test",
            "slug": "roundtrip-test",
            "path": "calculations/roundtrip",
            "kind": "calculation",
        },
        "structure_id": structure_id,
        "structure_name": "Legacy Structure Name",  # Should be stripped
        "structure": "legacy-structure",  # Should be stripped
        "mode": "normal",
        "working_dir": "raw",
        "steps": [],
    }
    
    yaml_path = calc_dir / "calculation.yaml"
    yaml_path.write_text(yaml.safe_dump(legacy_yaml))
    
    # Load calculation
    model = load_calculation(calc_dir, tmp_path)
    assert model.structure_id == structure_id
    
    # Save calculation (should strip legacy fields)
    save_calculation(model, calc_dir)
    
    # Verify legacy fields are gone
    on_disk = yaml.safe_load(yaml_path.read_text())
    assert "structure_id" in on_disk
    assert "structure_name" not in on_disk, "Legacy structure_name should be stripped"
    assert "structure" not in on_disk, "Legacy structure selector should be stripped"


def test_calculation_legacy_selector_raises_error(tmp_path):
    """Test that legacy structure selector (without structure_id) raises LegacyProjectError."""
    from quantumvitas.core.exceptions import LegacyProjectError
    
    calc_dir = tmp_path / "calculations" / "legacy"
    calc_dir.mkdir(parents=True)
    
    # Create a structure in the project
    project_root = tmp_path
    structures_dir = project_root / "structures"
    structures_dir.mkdir(parents=True)
    
    structure_id = generate_resource_id()
    structure_file = structures_dir / "test-structure.json"
    import json
    from quantumvitas.io.structure_io import STRUCTURE_META_KEY, STRUCTURE_DATA_KEY
    structure_file.write_text(json.dumps({
        STRUCTURE_META_KEY: {
            "id": structure_id,
            "name": "Test Structure",
            "slug": "test-structure",
            "path": "structures/test-structure.json",
            "kind": "structure",
        },
        STRUCTURE_DATA_KEY: {
            "@module": "pymatgen.core.structure",
            "@class": "Structure",
            "lattice": {"matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
            "sites": [],
        },
    }, indent=2))
    
    # Create project.qv.yml
    project_config = {
        "project": {"name": "Test Project"},
        "structures": [{
            "id": structure_id,
            "file": "structures/test-structure.json",
            "format": "json",
        }],
        "calculations": [],
    }
    (project_root / "project.qv.yml").write_text(yaml.safe_dump(project_config))
    
    # Create calculation.yaml with legacy structure selector (no structure_id)
    legacy_yaml = {
        "meta": {
            "id": generate_resource_id(),
            "name": "Legacy Test",
            "slug": "legacy-test",
            "path": "calculations/legacy-test",
            "kind": "calculation",
        },
        "structure": "test-structure",  # Legacy selector without structure_id
        "mode": "normal",
        "working_dir": "raw",
        "steps": [],
    }
    
    yaml_path = calc_dir / "calculation.yaml"
    yaml_path.write_text(yaml.safe_dump(legacy_yaml))
    
    # Load calculation should raise LegacyProjectError (no auto-migration)
    with pytest.raises(LegacyProjectError) as exc_info:
        load_calculation(calc_dir, project_root)
    
    assert "structure" in str(exc_info.value).lower() or "legacy" in str(exc_info.value).lower()
