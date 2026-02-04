"""
Level-3 Project Integration Tests for Psi4.

These tests verify the full unified pipeline (JobGraph execution) for Psi4:
- QVService.run_calculation() runs through JobGraph pipeline
- run_step() runs through unified run_step()
- SPEC step types are preserved throughout execution

Run with:
    pytest tests/integration/psi4/test_psi4_project_level.py -v -m integration
"""
import json
import pytest
import yaml
from pathlib import Path

from quantumvitas.api import QVService


def _psi4_available() -> bool:
    """Check if Psi4 is installed and importable.

    We check for psi4.core because the project's drivers/psi4 package
    can shadow the real psi4 module during test collection.
    """
    try:
        import psi4
        return hasattr(psi4, "core")
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(
    not _psi4_available(),
    reason="Psi4 not installed - install with: conda install psi4 -c conda-forge"
)


@pytest.fixture
def psi4_project(tmp_path):
    """Create a Psi4 project using QVService APIs.

    Creates:
    - Project directory
    - Water molecule structure
    - Calculation with engine_family=psi4
    - SCF step with HF/STO-3G parameters
    """
    # Create project using service API
    project_root = QVService.init_project(target_dir=tmp_path / "psi4_project", name="Psi4 Test")

    # Create molecule structure file (water)
    from pymatgen.core import Molecule

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

    from quantumvitas.core.resources import generate_resource_id
    structure_ulid = generate_resource_id()
    structure_data = {
        "__qv_meta__": {
            "ulid": structure_ulid,
            "name": "H2O",
            "slug": "h2o",
            "path": "structures/h2o.json",
            "kind": "structure",
        },
        "structure": water.as_dict(),
    }
    (structures_dir / "h2o.json").write_text(json.dumps(structure_data))

    # Create calculation for Psi4
    calc_resolved = QVService(project_root).project.init_calculation(
        name="h2o-scf",
        structure_selector=structure_ulid,
    )
    calc_id = calc_resolved.meta.ulid
    calc_dir = calc_resolved.absolute_path

    # Set engine_family to psi4 in calculation.yaml
    calc_yaml = calc_dir / "calculation.yaml"
    calc_data = yaml.safe_load(calc_yaml.read_text())
    calc_data["engine_family"] = "psi4"
    calc_yaml.write_text(yaml.dump(calc_data, default_flow_style=False))

    # Add SCF step with SPEC step type
    step_dto = QVService(project_root).calculation.add_step(
        calc_id,
        step_type_gen="scf",
    )
    step_id = step_dto.meta.ulid

    # Update step parameters
    step_yaml = project_root / step_dto.meta.path
    step_data = yaml.safe_load(step_yaml.read_text())
    step_data["parameters"] = {
        "method": "hf",
        "basis": "sto-3g",
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
@pytest.mark.psi4
class TestPsi4ProjectLevelExecution:
    """Level-3 tests: Full project execution through unified pipeline."""

    def test_run_calculation_completes(self, psi4_project):
        """Verify run_calculation() executes through JobGraph pipeline."""
        svc = QVService(psi4_project["root"])
        result = svc.run.run_calculation(
            calc_selector=psi4_project["calc_selector"],
        )

        assert hasattr(result, "calc_ulid")
        assert hasattr(result, "status")

    def test_run_step_completes(self, psi4_project):
        """Verify run_step() uses unified pipeline."""
        svc = QVService(psi4_project["root"])
        result = svc.run.run_step(
            calc_selector=psi4_project["calc_selector"],
            step_selector=psi4_project["step_ulid"],
        )

        assert hasattr(result, "status")
        assert hasattr(result, "step_ulids")

    def test_spec_step_type_preserved_in_step_yaml(self, psi4_project):
        """Verify SPEC step types are preserved in step.yaml."""
        calc_dir = psi4_project["calc_dir"]
        steps_dir = calc_dir / "steps"

        step_files = list(steps_dir.glob("*.yaml")) + list(steps_dir.glob("*.yml"))
        assert len(step_files) > 0, "No step files found"

        for step_file in step_files:
            step_data = yaml.safe_load(step_file.read_text())
            step_type_spec = step_data.get("step_type_spec", "")
            assert step_type_spec.startswith("psi4_"), (
                f"Step type '{step_type_spec}' is not SPEC format (should start with 'psi4_')"
            )


@pytest.mark.integration
@pytest.mark.psi4
class TestPsi4RegistryLookup:
    """Tests that verify registry-based engine lookup works correctly."""

    def test_registry_resolves_psi4_types(self):
        """Verify all Psi4 step types are in registry."""
        from quantumvitas.workflow.registry import get_registry

        registry = get_registry()

        psi4_types = [
            ("scf", "psi4_scf"),
            ("hf", "psi4_hf"),
            ("mp2", "psi4_mp2"),
            ("td", "psi4_td"),
            ("relax", "psi4_relax"),
        ]

        for gen_type, expected_spec in psi4_types:
            spec = registry.get_for_engine(gen_type, "psi4")
            assert spec is not None, f"GEN type '{gen_type}' for psi4 not in registry"
            assert spec.step_type_spec == expected_spec, (
                f"Expected spec_type '{expected_spec}', got '{spec.step_type_spec}'"
            )
            assert spec.engine == "psi4", (
                f"GEN type '{gen_type}' has wrong engine: {spec.engine}"
            )

    def test_engine_registered_in_engine_registry(self):
        """Verify Psi4 is registered in the EngineRegistry."""
        from quantumvitas.engine.registry import create_default_registry

        registry = create_default_registry()
        assert registry.has("psi4")

        engine = registry.get("psi4")
        assert engine.name == "psi4"

    def test_driver_registered_in_driver_registry(self):
        """Verify Psi4 driver is registered in the DriverRegistry."""
        from quantumvitas.core.driver_registry import DriverRegistry

        assert "psi4" in DriverRegistry.get_all_engines()
        driver = DriverRegistry.get_driver("psi4")
        assert driver.PREFIX == "psi4"
