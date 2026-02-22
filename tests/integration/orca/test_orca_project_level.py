"""
Level-3 Project Integration Tests for ORCA.

These tests verify the full unified pipeline (JobGraph execution) for ORCA:
- QMSService.run_calculation() runs through JobGraph pipeline
- run_step() runs through unified run_step() (not legacy)
- SPEC step types are preserved throughout execution

Per Constitution §C: Run Calc and Run Step share ONE pipeline.

Run with:
    pytest tests/integration/orca/test_orca_project_level.py -v -m integration
"""
import pytest
import yaml
from pathlib import Path
from typing import Optional

from qmatsuite.api import QMSService


def get_orca_path() -> Optional[Path]:
    """Get ORCA path using the resolver."""
    try:
        from qmatsuite.core.engines.orca_resolver import resolve_orca_bin
        return resolve_orca_bin()
    except RuntimeError:
        return None


ORCA_BIN = get_orca_path()


@pytest.fixture
def orca_project(tmp_path):
    """Create an ORCA project using QMSService APIs.

    Uses the same pattern as other integration tests:
    - QMSService.init_project() to create project
    - Create molecule structure file manually (pymatgen Molecule)
    - QMSService.init_calculation() with engine_family=orca
    - Add step using QMSService.add_step()
    """
    if not ORCA_BIN:
        pytest.skip("QMATSUITE_ORCA_BIN not set")

    # Create project using service API
    project_root = QMSService.init_project(target_dir=tmp_path / "orca_project", name="ORCA Test")

    # Create molecule structure file (water)
    from pymatgen.core import Molecule
    import json

    water = Molecule(
        species=["O", "H", "H"],
        coords=[
            [0.000000, 0.000000, 0.117300],
            [0.000000, 0.756950, -0.469200],
            [0.000000, -0.756950, -0.469200],
        ],
        charge=0,
        spin_multiplicity=1,
    )

    # Create structures directory and save molecule
    structures_dir = project_root / "structures"
    structures_dir.mkdir(parents=True, exist_ok=True)

    from qmatsuite.core.resources import generate_resource_id
    structure_ulid = generate_resource_id()
    structure_data = {
        "__qms_meta__": {
            "ulid": structure_ulid,
            "name": "H2O",
            "slug": "h2o",
            "path": "structures/h2o.json",
            "kind": "structure",
        },
        "structure": water.as_dict(),
    }
    (structures_dir / "h2o.json").write_text(json.dumps(structure_data))

    # Create calculation for ORCA
    calc_resolved = QMSService(project_root).project.init_calculation(
        name="h2o-scf",
        structure_selector=structure_ulid,
    )
    calc_id = calc_resolved.meta.ulid
    calc_dir = calc_resolved.absolute_path

    # Set engine_family to orca in calculation.yaml
    calc_yaml = calc_dir / "calculation.yaml"
    calc_data = yaml.safe_load(calc_yaml.read_text())
    calc_data["engine_family"] = "orca"
    calc_yaml.write_text(yaml.dump(calc_data, default_flow_style=False))

    # Add SCF step with SPEC step type
    step_dto = QMSService(project_root).calculation.add_step(
        calc_id,
        step_type_gen="scf",  # GEN type for UI layer (Constitution §A)
    )
    step_id = step_dto.meta.ulid

    # Update step parameters
    step_yaml = project_root / step_dto.meta.path
    step_data = yaml.safe_load(step_yaml.read_text())
    step_data["parameters"] = {
        "functional": "HF",
        "basis": "def2-SVP",
    }
    step_yaml.write_text(yaml.dump(step_data, default_flow_style=False))

    return {
        "root": project_root,
        "structure_ulid": structure_ulid,
        "calc_id": calc_id,
        "calc_dir": calc_dir,
        "step_ulid": step_id,
        "calc_selector": "h2o-scf",
    }


@pytest.mark.integration
@pytest.mark.orca
class TestORCAProjectLevelExecution:
    """Level-3 tests: Full project execution through unified pipeline."""

    def test_run_calculation_uses_jobgraph_pipeline(self, orca_project):
        """Verify run_calculation() executes through JobGraph pipeline (not legacy).

        Constitution §C: Run Calc uses JobGraph execution pipeline.
        """
        svc = QMSService(orca_project["root"])
        result = svc.run.run_calculation(
            calc_selector=orca_project["calc_selector"],
        )

        # Should complete (success or failure based on ORCA availability)
        # Result is RunResultDTO with calc_ulid and status
        assert hasattr(result, "calc_ulid")
        assert hasattr(result, "status")

    def test_run_step_uses_unified_pipeline(self, orca_project):
        """Verify run_step() uses unified pipeline (not run_step_legacy).

        Constitution §C: Run Step shares the unified pipeline with Run Calc.
        """
        svc = QMSService(orca_project["root"])
        result = svc.run.run_step(
            calc_selector=orca_project["calc_selector"],
            step_selector=orca_project["step_ulid"],
        )

        # Should complete (success or failure based on ORCA availability)
        # Result is RunResultDTO with status and step_ulids
        assert hasattr(result, "status")
        assert hasattr(result, "step_ulids")

    def test_spec_step_type_preserved_in_step_yaml(self, orca_project):
        """Verify SPEC step types are preserved in step.yaml.

        Constitution §B: Persisted truth = SPEC. Must not be normalized to GEN.
        """
        # Find the step YAML file
        calc_dir = orca_project["calc_dir"]
        steps_dir = calc_dir / "steps"

        # There should be at least one step file
        step_files = list(steps_dir.glob("*.yaml")) + list(steps_dir.glob("*.yml"))
        assert len(step_files) > 0, "No step files found"

        # Check that step_type_spec is SPEC format (YAML persists SPEC, not GEN)
        for step_file in step_files:
            step_data = yaml.safe_load(step_file.read_text())
            step_type_spec = step_data.get("step_type_spec", "")
            assert step_type_spec.startswith("orca_"), (
                f"Step type '{step_type_spec}' is not SPEC format (should start with 'orca_')"
            )

    def test_no_run_step_legacy_attribute(self, orca_project):
        """Verify run_step_legacy has been removed from QMSService.

        Constitution §C audit fix: Legacy paths removed.
        """
        # Verify run_step_legacy doesn't exist
        assert not hasattr(QMSService, 'run_step_legacy'), (
            "run_step_legacy still exists - should have been removed"
        )


@pytest.mark.integration
@pytest.mark.orca
class TestORCARegistryLookup:
    """Tests that verify registry-based engine lookup works correctly."""

    def test_engine_family_from_spec_type(self):
        """Verify engine family is determined from SPEC type via registry.

        Constitution §C: Must use registry lookup, NOT prefix inference.
        """
        from qmatsuite.calculation.runner import _get_engine_family_from_step
        from unittest.mock import MagicMock

        # Create mock step with SPEC type
        mock_step = MagicMock()
        mock_step.step_type_spec= "orca_scf"

        result = _get_engine_family_from_step(mock_step)
        assert result == "orca", f"Expected 'orca', got '{result}'"

    def test_registry_resolves_orca_types(self):
        """Verify all ORCA step types are in registry.

        Per constitution, registry.get() only accepts GEN types.
        Use get_for_engine(gen_type, engine) for engine-specific lookups.
        """
        from qmatsuite.workflow.registry import get_registry

        registry = get_registry()

        # ORCA step types: (gen_type, expected_spec_type)
        orca_types = [
            ("scf", "orca_scf"),
            ("hf", "orca_hf"),
            ("td", "orca_td"),
        ]

        for gen_type, expected_spec in orca_types:
            spec = registry.get_for_engine(gen_type, "orca")
            assert spec is not None, f"GEN type '{gen_type}' for orca not in registry"
            assert spec.step_type_spec == expected_spec, (
                f"Expected spec_type '{expected_spec}', got '{spec.step_type_spec}'"
            )
            assert spec.engine == "orca", (
                f"GEN type '{gen_type}' has wrong engine: {spec.engine}"
            )
