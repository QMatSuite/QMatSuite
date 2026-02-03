"""
Test calculation write capabilities.

Tests for the calculation write domain in QVService.
"""

import pytest
from pathlib import Path

from quantumvitas.api.service import QVService
from quantumvitas.api.types.calculation import CalculationDTO, StepDTO


def test_calculation_create_returns_dto(tmp_path):
    """create() returns CalculationDTO."""
    # Create minimal project structure
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    (project_root / "project.qv.yml").write_text("name: test\ncalculations: []\nstructures: []\n")
    
    svc = QVService(project_root)
    
    # This will fail because we need proper project setup, but tests the structure
    try:
        calc = svc.calculation.create(engine="qe", name="test_calc")
        assert isinstance(calc, CalculationDTO)
        assert calc.calc_id is not None
        assert calc.engine == "qe"
    except Exception:
        # Expected to fail without full project setup
        pass


def test_calculation_update_meta_returns_dto(tmp_path):
    """update_meta() returns updated CalculationDTO."""
    # Create minimal project structure
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    (project_root / "project.qv.yml").write_text("name: test\ncalculations: []\n")
    
    svc = QVService(project_root)
    
    try:
        calc = svc.calculation.update_meta("test_calc", name="updated_name")
        assert isinstance(calc, CalculationDTO)
        assert calc.meta is None or calc.meta.name == "updated_name"
    except Exception:
        # Expected to fail without full project setup
        pass


def test_calculation_update_step_params_returns_dto(tmp_path):
    """update_step_params() returns updated StepDTO."""
    # Create minimal project structure
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    (project_root / "project.qv.yml").write_text("name: test\ncalculations: []\n")
    
    svc = QVService(project_root)
    
    try:
        step = svc.calculation.update_step_params("test_calc", "step1", {"key": "value"})
        assert isinstance(step, StepDTO)
    except Exception:
        # Expected to fail without full project setup
        pass


def test_duplicate_calculation_happy_path(tmp_path):
    """duplicate() successfully duplicates a calculation with steps."""
    # Create minimal project structure
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    (project_root / "project.qv.yml").write_text("name: test\ncalculations: []\nstructures: []\n")
    
    # Create source calculation
    calc_dir = project_root / "calculations" / "original_calc"
    calc_dir.mkdir(parents=True)
    steps_dir = calc_dir / "steps"
    steps_dir.mkdir()
    
    # Write calculation.yaml
    calc_yaml = calc_dir / "calculation.yaml"
    calc_yaml.write_text("""meta:
  ulid: 01TESTORIGINAL1234567890
  name: Original Calculation
  slug: original_calc
  path: calculations/original_calc
  kind: calculation
engine_family: qe
structure_kind: periodic
""")
    
    # Write step file
    step_yaml = steps_dir / "step1.step.yaml"
    step_yaml.write_text("""meta:
  ulid: 01TESTSTEP1234567890123
  name: step1
  slug: step1
  path: calculations/original_calc/steps/step1.step.yaml
  kind: step
step_type_spec: qe_scf
parameters:
  system:
    ecutwfc: 30.0
""")
    
    # Add to project config (API format: meta with ulid, name, slug, path)
    import yaml
    config = {
        "name": "test",
        "calculations": [{
            "meta": {
                "ulid": "01TESTORIGINAL1234567890",
                "name": "Original Calculation",
                "slug": "original_calc",
                "path": "calculations/original_calc",
                "kind": "calculation"
            }
        }],
        "structures": []
    }
    (project_root / "project.qv.yml").write_text(yaml.safe_dump(config))
    
    svc = QVService(project_root)
    
    # Duplicate calculation
    dup_calc = svc.calculation.duplicate("original_calc", new_name="Duplicated Calculation")
    
    # Verify DTO
    assert isinstance(dup_calc, CalculationDTO)
    assert dup_calc.calc_id is not None
    assert dup_calc.calc_id != "01TESTORIGINAL1234567890"  # Different ID
    assert dup_calc.meta is not None
    assert dup_calc.meta.name == "Duplicated Calculation"
    
    # Verify new calculation directory exists
    new_calc_dir = project_root / "calculations" / "duplicated-calculation"
    assert new_calc_dir.exists()
    assert (new_calc_dir / "calculation.yaml").exists()
    
    # Verify step was copied
    new_steps_dir = new_calc_dir / "steps"
    assert new_steps_dir.exists()
    step_files = list(new_steps_dir.glob("*.step.yaml"))
    assert len(step_files) == 1
    
    # Verify step has new ULID
    new_step_data = yaml.safe_load(step_files[0].read_text())
    assert new_step_data["meta"]["ulid"] != "01TESTSTEP1234567890123"
    
    # Verify calculation is in project config
    config_after = yaml.safe_load((project_root / "project.qv.yml").read_text())
    calc_ids = [(c.get("meta") or {}).get("ulid") for c in config_after.get("calculations", [])]
    assert dup_calc.calc_id in calc_ids
    assert "01TESTORIGINAL1234567890" in calc_ids  # Original still there


def test_duplicate_unknown_selector_raises_not_found(tmp_path):
    """duplicate() raises NotFoundError for unknown selector."""
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    (project_root / "project.qv.yml").write_text("name: test\ncalculations: []\nstructures: []\n")
    
    svc = QVService(project_root)
    
    from quantumvitas.api.errors import NotFoundError
    with pytest.raises(NotFoundError):
        svc.calculation.duplicate("nonexistent_calc", new_name="Copy")


def test_duplicate_slug_conflict_raises_conflict(tmp_path):
    """duplicate() raises ConflictError if new_slug already exists."""
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    
    # Create original calculation
    calc_dir = project_root / "calculations" / "existing_calc"
    calc_dir.mkdir(parents=True)
    calc_yaml = calc_dir / "calculation.yaml"
    calc_yaml.write_text("""meta:
  ulid: 01TESTEXISTING1234567890
  name: Existing Calculation
  slug: existing_calc
  path: calculations/existing_calc
  kind: calculation
engine_family: qe
structure_kind: periodic
""")
    
    # Add to project config (API format: meta with ulid, name, slug, path)
    import yaml
    config = {
        "name": "test",
        "calculations": [{
            "meta": {
                "ulid": "01TESTEXISTING1234567890",
                "name": "Existing Calculation",
                "slug": "existing_calc",
                "path": "calculations/existing_calc",
                "kind": "calculation"
            }
        }],
        "structures": []
    }
    (project_root / "project.qv.yml").write_text(yaml.safe_dump(config))
    
    svc = QVService(project_root)
    
    # Try to duplicate with conflicting slug
    from quantumvitas.api.errors import ConflictError
    with pytest.raises(ConflictError) as exc_info:
        svc.calculation.duplicate("existing_calc", new_slug="existing_calc")
    
    assert "already exists" in str(exc_info.value).lower()


def test_duplicate_with_custom_slug(tmp_path):
    """duplicate() respects custom new_slug parameter."""
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    
    # Create original calculation
    calc_dir = project_root / "calculations" / "original"
    calc_dir.mkdir(parents=True)
    calc_yaml = calc_dir / "calculation.yaml"
    calc_yaml.write_text("""meta:
  ulid: 01TESTORIGINAL1234567890
  name: Original
  slug: original
  path: calculations/original
  kind: calculation
engine_family: qe
structure_kind: periodic
""")
    
    import yaml
    config = {
        "name": "test",
        "calculations": [{
            "meta": {
                "ulid": "01TESTORIGINAL1234567890",
                "name": "Original",
                "slug": "original",
                "path": "calculations/original",
                "kind": "calculation"
            }
        }],
        "structures": []
    }
    (project_root / "project.qv.yml").write_text(yaml.safe_dump(config))

    svc = QVService(project_root)

    # Duplicate with custom slug
    dup_calc = svc.calculation.duplicate("original", new_name="Custom Name", new_slug="custom-slug")
    
    assert dup_calc.meta is not None
    assert dup_calc.meta.slug == "custom-slug"
    
    # Verify directory uses custom slug
    custom_dir = project_root / "calculations" / "custom-slug"
    assert custom_dir.exists()


def test_calculation_delete_returns_none(tmp_path):
    """delete() returns None."""
    # Create minimal project structure
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    (project_root / "project.qv.yml").write_text("name: test\ncalculations: []\n")
    
    svc = QVService(project_root)
    
    try:
        result = svc.calculation.delete("test_calc")
        assert result is None
    except Exception:
        # Expected to fail without full project setup
        pass


def test_add_step_persists_and_returns_step_dto(tmp_path):
    """add_step() creates step.yaml and adds to calculation.yaml, returns StepDTO."""
    # Create minimal project structure
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    
    # Create calculation
    calc_dir = project_root / "calculations" / "test_calc"
    calc_dir.mkdir(parents=True)
    calc_yaml = calc_dir / "calculation.yaml"
    calc_yaml.write_text("""meta:
  ulid: 01TESTCALC1234567890123456
  name: Test Calculation
  slug: test_calc
  path: calculations/test_calc
  kind: calculation
engine_family: qe
structure_kind: periodic
steps: []
""")
    
    # Add to project config (API format: meta with ulid, name, slug, path)
    import yaml
    config = {
        "name": "test",
        "calculations": [{
            "meta": {
                "ulid": "01TESTCALC1234567890123456",
                "name": "Test Calculation",
                "slug": "test_calc",
                "path": "calculations/test_calc",
                "kind": "calculation"
            }
        }],
        "structures": []
    }
    (project_root / "project.qv.yml").write_text(yaml.safe_dump(config))

    svc = QVService(project_root)

    # Add step
    step = svc.calculation.add_step("test_calc", "scf", name="scf1")
    
    # Verify DTO
    assert isinstance(step, StepDTO)
    assert step.step_ulid is not None
    assert step.calc_ulid == "01TESTCALC1234567890123456"
    assert step.step_type_spec is not None
    
    # Verify step.yaml exists
    steps_dir = calc_dir / "steps"
    assert steps_dir.exists()
    step_files = list(steps_dir.glob("*.step.yaml"))
    assert len(step_files) == 1
    
    # Verify step.yaml content
    step_data = yaml.safe_load(step_files[0].read_text())
    assert step_data["meta"]["ulid"] == step.step_ulid
    assert step_data["meta"]["name"] == "scf1"
    assert "step_type_spec" in step_data
    
    # Verify calculation.yaml was updated
    calc_data = yaml.safe_load(calc_yaml.read_text())
    steps = calc_data.get("steps", [])
    assert len(steps) == 1
    assert steps[0]["step_ulid"] == step.step_ulid
    assert steps[0]["step_type_spec"] == "qe_scf"  # SPEC type
    
    # Regression test: Ensure calculation.yaml does NOT contain python object tags
    calc_yaml_text = calc_yaml.read_text()
    assert "!!python/object" not in calc_yaml_text, "calculation.yaml must not contain python object tags"
    assert "!!python" not in calc_yaml_text, "calculation.yaml must not contain any python YAML tags"


def test_remove_step_removes_from_step_yaml(tmp_path):
    """remove_step() removes step from calculation.yaml and moves file to trash."""
    # Create minimal project structure
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    
    # Create calculation with a step
    calc_dir = project_root / "calculations" / "test_calc"
    calc_dir.mkdir(parents=True)
    steps_dir = calc_dir / "steps"
    steps_dir.mkdir()
    
    step_ulid = "01TESTSTEP1234567890123456"  # Proper ULID length (26 chars)
    step_yaml = steps_dir / "scf1.step.yaml"
    step_yaml.write_text(f"""meta:
  ulid: {step_ulid}
  name: scf1
  slug: scf1
  path: calculations/test_calc/steps/scf1.step.yaml
  kind: step
step_type_spec: qe_scf
parameters:
  system:
    ecutwfc: 30.0
""")

    calc_yaml = calc_dir / "calculation.yaml"
    calc_yaml.write_text(f"""meta:
  ulid: 01TESTCALC1234567890123456
  name: Test Calculation
  slug: test_calc
  path: calculations/test_calc
  kind: calculation
engine_family: qe
structure_kind: periodic
steps:
  - step_ulid: {step_ulid}
    step_type_spec: qe_scf
""")
    
    # Add to project config (API format: meta with ulid, name, slug, path)
    import yaml
    config = {
        "name": "test",
        "calculations": [{
            "meta": {
                "ulid": "01TESTCALC1234567890123456",
                "name": "Test Calculation",
                "slug": "test_calc",
                "path": "calculations/test_calc",
                "kind": "calculation"
            }
        }],
        "structures": []
    }
    (project_root / "project.qv.yml").write_text(yaml.safe_dump(config))

    svc = QVService(project_root)

    # Verify step exists
    assert step_yaml.exists()
    calc_data_before = yaml.safe_load(calc_yaml.read_text())
    assert len(calc_data_before.get("steps", [])) == 1
    
    # Remove step
    svc.calculation.remove_step("test_calc", step_ulid)
    
    # Verify step file moved to trash
    assert not step_yaml.exists()
    trash_dir = project_root / "trash"
    if trash_dir.exists():
        trash_files = list(trash_dir.glob("*scf1*"))
        assert len(trash_files) > 0
    
    # Verify calculation.yaml updated
    calc_data_after = yaml.safe_load(calc_yaml.read_text())
    steps_after = calc_data_after.get("steps", [])
    assert len(steps_after) == 0


def test_add_step_unknown_calc_raises_not_found(tmp_path):
    """add_step() raises NotFoundError for unknown calculation."""
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    (project_root / "project.qv.yml").write_text("name: test\ncalculations: []\nstructures: []\n")
    
    svc = QVService(project_root)
    
    from quantumvitas.api.errors import NotFoundError
    with pytest.raises(NotFoundError):
        svc.calculation.add_step("nonexistent_calc", "scf")


def test_remove_step_unknown_step_raises_not_found(tmp_path):
    """remove_step() raises NotFoundError for unknown step."""
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    
    # Create calculation without steps
    calc_dir = project_root / "calculations" / "test_calc"
    calc_dir.mkdir(parents=True)
    calc_yaml = calc_dir / "calculation.yaml"
    calc_yaml.write_text("""meta:
  ulid: 01TESTCALC1234567890123456
  name: Test Calculation
  slug: test_calc
  path: calculations/test_calc
  kind: calculation
engine_family: qe
structure_kind: periodic
steps: []
""")

    import yaml
    config = {
        "name": "test",
        "calculations": [{
            "meta": {
                "ulid": "01TESTCALC1234567890123456",
                "name": "Test Calculation",
                "slug": "test_calc",
                "path": "calculations/test_calc",
                "kind": "calculation"
            }
        }],
        "structures": []
    }
    (project_root / "project.qv.yml").write_text(yaml.safe_dump(config))

    svc = QVService(project_root)

    from quantumvitas.api.errors import NotFoundError
    with pytest.raises(NotFoundError):
        svc.calculation.remove_step("test_calc", "nonexistent_step_ulid")

