"""
Integration test for QMCPACK diamond C workflow.

Full pipeline: QE SCF -> pw2qmcpack -> QMCPACK VMC.
QE and pw2qmcpack phases use subprocess (setup, not under test).
QMCPACK VMC phase uses the full QMatSuite API (project/calc/step).

Requires: pw.x, pw2qmcpack.x, qmcpack binaries.
"""

import json
import math
import os
import shutil
import subprocess
import textwrap

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


# ─── helpers ────────────────────────────────────────────────────────

# Repo root (resolved at import time before conftest may change CWD)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_pw_bin() -> Path | None:
    """Try to find pw.x."""
    try:
        from qmatsuite.core.engines.qe_resolver import resolve_qe_bin_dir
        pw = resolve_qe_bin_dir() / "pw.x"
        if pw.is_file():
            return pw
    except (ImportError, FileNotFoundError):
        pass
    # Also check repo-local .qmatsuite
    for qe_dir in sorted((_REPO_ROOT / ".qmatsuite" / "engines" / "qe").glob("*/bin"), reverse=True):
        pw = qe_dir / "pw.x"
        if pw.is_file():
            return pw
    from shutil import which
    p = which("pw.x")
    return Path(p) if p else None


def _resolve_pw2qmcpack_bin() -> Path | None:
    try:
        from qmatsuite.core.engines.qmcpack_resolver import resolve_pw2qmcpack_bin
        return resolve_pw2qmcpack_bin()
    except FileNotFoundError:
        pass
    # Check repo-local .qmatsuite
    for qe_dir in sorted((_REPO_ROOT / ".qmatsuite" / "engines" / "qe").glob("*/bin"), reverse=True):
        p2q = qe_dir / "pw2qmcpack.x"
        if p2q.is_file():
            return p2q
    return None


def _resolve_qmcpack_bin() -> Path | None:
    try:
        from qmatsuite.core.engines.qmcpack_resolver import resolve_qmcpack_bin
        return resolve_qmcpack_bin()
    except FileNotFoundError:
        pass
    # Check repo-local .qmatsuite
    for qmc_dir in sorted((_REPO_ROOT / ".qmatsuite" / "engines" / "qmcpack").glob("*/bin"), reverse=True):
        qmc = qmc_dir / "qmcpack"
        if qmc.is_file():
            return qmc
    return None


def _find_qmcpack_test_data() -> Path | None:
    """Find QMCPACK test data directory (diamondC_1x1x1_pp or staged data)."""
    # Prefer staged test data (independent of engine installation)
    staged = _REPO_ROOT / "tests" / "data" / "qmcpack_diamond"
    if staged.is_dir():
        return staged
    candidates = [
        Path.home() / ".qmatsuite" / "engines" / "qmcpack",
        _REPO_ROOT / ".qmatsuite" / "engines" / "qmcpack",
    ]
    for root in candidates:
        if not root.is_dir():
            continue
        for version_dir in sorted(root.iterdir(), reverse=True):
            test_dir = version_dir / "tests" / "solids" / "diamondC_1x1x1_pp"
            if test_dir.is_dir():
                return test_dir
    return None


# ─── QE SCF input ──────────────────────────────────────────────────

SCF_INPUT = textwrap.dedent("""\
    &CONTROL
       calculation     = 'scf'
       disk_io         = 'low'
       outdir          = 'pwscf_output'
       prefix          = 'pwscf'
       pseudo_dir      = './'
       restart_mode    = 'from_scratch'
       tprnfor         = .false.
       tstress         = .false.
       verbosity       = 'high'
       wf_collect      = .true.
    /

    &SYSTEM
       celldm(1)       = 1.0
       degauss         = 0.0001
       ecutrho         = 800
       ecutwfc         = 200
       ibrav           = 0
       input_dft       = 'lda'
       nat             = 2
       nosym           = .true.
       ntyp            = 1
       occupations     = 'smearing'
       smearing        = 'fermi-dirac'
       tot_charge      = 0
    /

    &ELECTRONS
       conv_thr        = 1e-08
       electron_maxstep = 1000
       mixing_beta     = 0.7
    /

    ATOMIC_SPECIES
       C  12.011 C.BFD.upf

    ATOMIC_POSITIONS alat
       C        0.00000000       0.00000000       0.00000000
       C        1.68658058       1.68658058       1.68658058

    K_POINTS automatic
       1 1 1  0 0 0

    CELL_PARAMETERS cubic
             3.37316115       3.37316115       0.00000000
             0.00000000       3.37316115       3.37316115
             3.37316115       0.00000000       3.37316115
""")

PW2QMCPACK_INPUT = textwrap.dedent("""\
    &inputpp
       write_psir = .false.
       prefix = 'pwscf'
       outdir = 'pwscf_output'
    /
""")


# ─── fixture ───────────────────────────────────────────────────────

@pytest.fixture
def diamond_workflow_project(tmp_path: Path):
    """Set up the full diamond workflow: QE SCF -> pw2qmcpack -> QMCPACK VMC.

    QE and pw2qmcpack are run via subprocess (setup).
    QMCPACK VMC is configured via QMatSuite API.
    """
    pw_bin = _resolve_pw_bin()
    pw2q_bin = _resolve_pw2qmcpack_bin()
    qmcpack_bin = _resolve_qmcpack_bin()
    test_data = _find_qmcpack_test_data()

    if pw_bin is None:
        pytest.skip("pw.x not available")
    if pw2q_bin is None:
        pytest.skip("pw2qmcpack.x not available")
    if qmcpack_bin is None:
        pytest.skip("qmcpack not available")
    if test_data is None:
        pytest.skip("QMCPACK test data (diamondC_1x1x1_pp) not found")

    # Set env var so the engine's resolver can find qmcpack
    # (conftest changes CWD to tmp, breaking CWD-based resolution)
    old_env = os.environ.get("QMATS_QMCPACK_BIN")
    os.environ["QMATS_QMCPACK_BIN"] = str(qmcpack_bin)

    # ── Phase 1: QE SCF (subprocess) ──
    dft_dir = tmp_path / "dft"
    dft_dir.mkdir()

    # Copy pseudopotential
    shutil.copy2(test_data / "dft-inputs" / "C.BFD.upf", dft_dir / "C.BFD.upf")

    # Write SCF input
    (dft_dir / "scf.in").write_text(SCF_INPUT)

    # Run pw.x
    scf_result = subprocess.run(
        [str(pw_bin)],
        input=SCF_INPUT,
        cwd=dft_dir,
        capture_output=True,
        text=True,
        timeout=300,
    )
    scf_out = scf_result.stdout
    assert "JOB DONE" in scf_out, f"QE SCF failed:\n{scf_result.stderr[:500]}"

    # ── Phase 2: pw2qmcpack (subprocess) ──
    p2q_result = subprocess.run(
        [str(pw2q_bin)],
        input=PW2QMCPACK_INPUT,
        cwd=dft_dir,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert p2q_result.returncode == 0, f"pw2qmcpack failed:\n{p2q_result.stderr[:500]}"

    h5_file = dft_dir / "pwscf_output" / "pwscf.pwscf.h5"
    assert h5_file.exists(), "pw2qmcpack did not produce HDF5 file"

    # ── Phase 3: Set up QMCPACK VMC via QMatSuite API ──
    project_root = QMSService.init_project(
        target_dir=tmp_path / "qmcpack_project",
        name="QMCPACK Diamond Workflow Test",
    )

    # Create diamond C structure
    from pymatgen.core import Structure, Lattice
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
    struct_file = tmp_path / "diamond.json"
    struct_file.write_text(json.dumps(structure.as_dict()))

    struct_result = QMSService(project_root).structure.import_file(struct_file, name="Diamond C")
    structure_ulid = struct_result.meta.ulid

    # Create calculation with engine_family=qmcpack
    calc_resolved = QMSService(project_root).project.init_calculation(
        name="diamond_vmc",
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
                "qmc_project_id": "qmc_smoke",
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
                    "precision": "float",
                },
                "vmc": {
                    "walkers": 1,
                    "blocks": 50,
                    "steps": 10,
                    "substeps": 2,
                    "timestep": 0.3,
                    "warmupsteps": 20,
                },
            },
        },
    )

    # Stage supporting files into the project root so the engine can find them
    shutil.copy2(h5_file, project_root / "pwscf.pwscf.h5")
    shutil.copy2(test_data / "C.BFD.xml", project_root / "C.BFD.xml")

    yield {
        "project_root": project_root,
        "calc_dir": calc_dir,
        "dft_dir": dft_dir,
    }

    # Restore environment
    if old_env is None:
        os.environ.pop("QMATS_QMCPACK_BIN", None)
    else:
        os.environ["QMATS_QMCPACK_BIN"] = old_env


# ─── test ──────────────────────────────────────────────────────────

@pytest.mark.requires_qmcpack
def test_diamond_qe_to_qmcpack_workflow(diamond_workflow_project):
    """Test full QE SCF -> pw2qmcpack -> QMCPACK VMC workflow.

    Validates:
    1. QMCPACK VMC runs successfully via QMatSuite API
    2. scalar.dat output file is produced
    3. Mean energy is finite and in the expected range (~-10.2 Ha)
    """
    project_root = diamond_workflow_project["project_root"]
    calc_dir = diamond_workflow_project["calc_dir"]

    # Load project and calculation
    project = Project.open(project_root)
    calculation = Calculation.from_yaml(calc_dir, project)

    # Run via CalculationRunner
    registry = create_default_registry()
    runner = CalculationRunner(engine_registry=registry)
    result = runner.run(calculation)

    assert result.status.value == "success", (
        f"QMCPACK calculation failed: "
        f"{result.steps[0].message if result.steps else 'Unknown error'}"
    )

    # Verify scalar.dat output exists
    working_dir = calculation.raw_dir / calculation.steps[0].meta.ulid
    scalar_files = list(working_dir.glob("*.scalar.dat"))
    assert len(scalar_files) > 0, "No scalar.dat files produced"

    # Parse and validate energy
    from qmatsuite.drivers.qmcpack.parser import parse_scalar_dat
    scalar_data = parse_scalar_dat(scalar_files[0])

    assert scalar_data.num_blocks > 0, "No data blocks in scalar.dat"
    assert not math.isnan(scalar_data.mean_energy), "Mean energy is NaN"
    assert math.isfinite(scalar_data.mean_energy), "Mean energy is not finite"

    # Diamond C 1x1x1 without Jastrow: energy ~-10.2 Ha (stochastic, wide tolerance)
    assert -15.0 < scalar_data.mean_energy < -5.0, (
        f"Mean energy {scalar_data.mean_energy:.4f} Ha outside expected range [-15, -5]"
    )

    # Verify QMCPACK input file was generated with driver_version
    qmc_input = working_dir / "qmc_input.xml"
    assert qmc_input.exists(), "qmc_input.xml not generated"
    xml_content = qmc_input.read_text()
    assert "driver_version" in xml_content, "driver_version not in generated XML"
    assert "legacy" in xml_content, "driver_version should be 'legacy'"
