"""
Integration test for QMCPACK VMC workflow.

Tests the full project/calc/step API flow with QMCPACK.
Requires QMCPACK binary to be available.
"""

import json
import shutil
import pytest
from pathlib import Path

from qmatsuite.api import QMSService
from qmatsuite.calculation.calculation import Calculation
from qmatsuite.calculation.runner import CalculationRunner
from qmatsuite.engine.registry import create_default_registry
from qmatsuite.project.model import Project
from qmatsuite.core.yaml_io import save_yaml_doc
from qmatsuite.core.yamldoc import CalcDoc
from qmatsuite.core.models import load_calculation


from qmatsuite.core.engines.discovery import is_engine_available


def _find_qmcpack_asset(repo_root: Path, filename: str) -> Path | None:
    """Find a required QMCPACK test asset from known local locations."""
    candidates = [
        repo_root / "tests" / "data" / "qmcpack_diamond" / filename,
        repo_root / ".qmatsuite" / "engines" / "qmcpack" / "qmcpack-4.1.0" / "tests" / "solids" / "diamondC_1x1x1_pp" / filename,
        repo_root / ".tmp" / "engine_research" / "qmcpack" / "extracted" / "tests_solids" / "diamondC_1x1x1_pp" / filename,
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


@pytest.fixture
def diamond_vmc_project(tmp_path: Path):
    """Create a QMCPACK VMC project using Service API.

    This creates a project with a diamond C structure and a VMC step.
    Requires QMCPACK and an HDF5 wavefunction file.
    """
    if not is_engine_available("qmcpack"):
        pytest.skip("QMCPACK not installed")

    from pymatgen.core import Structure, Lattice

    # Create project
    project_root = QMSService.init_project(
        target_dir=tmp_path / "qmcpack_project",
        name="QMCPACK VMC Test"
    )
    repo_root = Path(__file__).resolve().parents[2]

    # Stage required wavefunction/pseudopotential into project root so the engine
    # can copy them into the step workdir during materialization.
    h5_src = _find_qmcpack_asset(repo_root, "pwscf.pwscf.h5")
    pseudo_src = _find_qmcpack_asset(repo_root, "C.BFD.xml")
    if h5_src is None or pseudo_src is None:
        pytest.skip("QMCPACK test assets not found (pwscf.pwscf.h5, C.BFD.xml)")
    shutil.copy2(h5_src, project_root / "pwscf.pwscf.h5")
    shutil.copy2(pseudo_src, project_root / "C.BFD.xml")

    # Create diamond C structure
    lattice = Lattice(
        [[3.37316115, 3.37316115, 0.0],
         [0.0, 3.37316115, 3.37316115],
         [3.37316115, 0.0, 3.37316115]]
    )
    structure = Structure(
        lattice,
        ["C", "C"],
        [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
    )

    # Save structure
    struct_file = tmp_path / "diamond.json"
    struct_file.write_text(json.dumps(structure.as_dict()))

    # Import structure
    struct_result = QMSService(project_root).structure.import_file(struct_file, name="Diamond C")
    structure_ulid = struct_result.meta.ulid

    # Create calculation
    calc_resolved = QMSService(project_root).project.init_calculation(
        name="qmcpack_vmc",
        structure_selector=structure_ulid,
    )
    calc_id = calc_resolved.meta.ulid
    calc_dir = calc_resolved.absolute_path
    calc_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_path, project_root=project_root)
    calc_model.engine_family = "qmcpack"
    calc_model.species_map = {}
    calc_doc = CalcDoc(calc_model.to_dict())
    save_yaml_doc(calc_doc, calc_path)

    # Add VMC step
    svc = QMSService(project_root)
    step_dto = svc.calculation.add_step(
        calc_selector=calc_id,
        step_type_gen="vmc",
    )
    step_id = step_dto.step_ulid

    # Configure VMC parameters
    svc.calculation.update_step_params(
        calc_selector=calc_id,
        step_selector=step_id,
        params={
            "parameters": {
                "qmc_project_id": "qmc",
                "cell": {
                    "lattice": [
                        [3.37316115, 3.37316115, 0.0],
                        [0.0, 3.37316115, 3.37316115],
                        [3.37316115, 0.0, 3.37316115],
                    ],
                    "bconds": "p p p",
                },
                "species": [{
                    "symbol": "C",
                    "charge": 4,
                    "valence": 4,
                    "atomic_number": 6,
                    "mass": 21894.7135906,
                    "positions": [
                        [0.0, 0.0, 0.0],
                        [1.68658058, 1.68658058, 1.68658058],
                    ],
                    "pseudo_file": "C.BFD.xml",
                }],
                "wavefunction": {
                    "href": "pwscf.pwscf.h5",
                    "num_up": 4,
                    "num_down": 4,
                    "num_orbitals": 4,
                },
                "vmc": {
                    "blocks": 10,
                    "steps": 5,
                    "timestep": 0.3,
                    "warmupsteps": 10,
                },
            },
        },
    )

    return {
        "project_root": project_root,
        "calc_dir": calc_dir,
    }


@pytest.mark.requires_qmcpack
def test_vmc_diamond_e2e(diamond_vmc_project):
    """Test VMC diamond workflow end-to-end.

    This test requires:
    1. QMCPACK binary available
    2. HDF5 wavefunction file (pwscf.pwscf.h5) available
    3. Pseudopotential file (C.BFD.xml) available

    Since these are unlikely to be present in CI, this test
    is marked with requires_qmcpack and will be skipped if
    QMCPACK is not installed.
    """
    project_root = diamond_vmc_project["project_root"]
    calc_dir = diamond_vmc_project["calc_dir"]

    project = Project.open(project_root)
    calculation = Calculation.from_yaml(calc_dir, project)

    registry = create_default_registry()
    runner = CalculationRunner(engine_registry=registry)

    result = runner.run(calculation)

    assert result.status.value == "success", (
        f"Calculation failed: {result.steps[0].message if result.steps else 'Unknown error'}"
    )

    # Verify output files exist
    working_dir = calculation.raw_dir / calculation.steps[0].meta.ulid
    scalar_files = list(working_dir.glob("*.scalar.dat"))
    assert len(scalar_files) > 0, "scalar.dat files should exist"

    # Parse and validate energy
    from qmatsuite.drivers.qmcpack.parser import parse_scalar_dat
    scalar_data = parse_scalar_dat(scalar_files[0])
    assert scalar_data.num_blocks > 0
    assert not __import__("math").isnan(scalar_data.mean_energy)
