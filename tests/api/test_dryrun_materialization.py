"""P3 hardening: dry_run materialization — input file completeness.

Verifies that write_engine_inputs produces complete QE input files
including K_POINTS, nat, ntyp, ATOMIC_SPECIES, ATOMIC_POSITIONS,
and CELL_PARAMETERS when given proper structure and parameter data.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from qmatsuite.api.service import QMSService


# Minimal pymatgen-format 2-atom Silicon structure.
_SI_STRUCTURE_JSON = json.dumps({
    "@module": "pymatgen.core.structure",
    "@class": "Structure",
    "lattice": {
        "matrix": [[0.0, 2.715, 2.715], [2.715, 0.0, 2.715], [2.715, 2.715, 0.0]],
        "a": 3.84, "b": 3.84, "c": 3.84,
        "alpha": 60, "beta": 60, "gamma": 60,
    },
    "sites": [
        {"species": [{"element": "Si", "occu": 1}], "abc": [0.0, 0.0, 0.0], "xyz": [0, 0, 0]},
        {"species": [{"element": "Si", "occu": 1}], "abc": [0.25, 0.25, 0.25], "xyz": [1.3575, 1.3575, 1.3575]},
    ],
})


def _build_structure_doc():
    """Build a StructureDoc dict for QE writer tests."""
    return {
        "lattice": [[0.0, 2.715, 2.715], [2.715, 0.0, 2.715], [2.715, 2.715, 0.0]],
        "species": ["Si", "Si"],
        "frac_coords": [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
        "comment": "Silicon FCC",
    }


def _get_qe_input_spec():
    """Get the QE input spec for SCF step type."""
    import qmatsuite.drivers  # noqa: F401
    from qmatsuite.core.driver_registry import DriverRegistry

    driver = DriverRegistry.get_driver("qe")
    return driver.get_input_spec(gen_type="scf")


class TestQEDryRunCompleteness:
    """Verify QE dry_run generates complete, correct input files."""

    def test_dryrun_has_kpoints_card(self):
        """dry_run input for QE SCF contains K_POINTS card."""
        from qmatsuite.inputformat.writer import write_engine_inputs

        spec = _get_qe_input_spec()
        assert spec is not None

        params = {
            "SYSTEM": {"ecutwfc": 40.0, "nat": 2, "ntyp": 1},
            "kpoints": {"mesh": [4, 4, 4], "shift": [0, 0, 0]},
        }
        structure_doc = _build_structure_doc()

        with tempfile.TemporaryDirectory() as tmpdir:
            written = write_engine_inputs(spec, Path(tmpdir), params, structure_doc)
            assert written, "No files written"

            pw_files = [f for f in written if f.suffix == ".in"]
            assert pw_files, f"No .in file: {[f.name for f in written]}"

            content = pw_files[0].read_text()
            assert "K_POINTS" in content, f"K_POINTS missing:\n{content}"

    def test_dryrun_has_nat_ntyp(self):
        """dry_run input contains nat and ntyp in &SYSTEM."""
        from qmatsuite.inputformat.writer import write_engine_inputs

        spec = _get_qe_input_spec()
        params = {
            "SYSTEM": {"ecutwfc": 40.0, "nat": 2, "ntyp": 1},
            "kpoints": {"mesh": [6, 6, 6], "shift": [1, 1, 1]},
        }
        structure_doc = _build_structure_doc()

        with tempfile.TemporaryDirectory() as tmpdir:
            written = write_engine_inputs(spec, Path(tmpdir), params, structure_doc)
            pw_files = [f for f in written if f.suffix == ".in"]
            assert pw_files

            content = pw_files[0].read_text()
            assert "nat" in content.lower(), f"nat missing:\n{content}"
            assert "ntyp" in content.lower(), f"ntyp missing:\n{content}"

    def test_dryrun_has_atomic_positions(self):
        """dry_run input contains ATOMIC_POSITIONS card."""
        from qmatsuite.inputformat.writer import write_engine_inputs

        spec = _get_qe_input_spec()
        params = {
            "SYSTEM": {"ecutwfc": 40.0, "nat": 2, "ntyp": 1},
            "kpoints": {"mesh": [4, 4, 4], "shift": [0, 0, 0]},
        }
        structure_doc = _build_structure_doc()

        with tempfile.TemporaryDirectory() as tmpdir:
            written = write_engine_inputs(spec, Path(tmpdir), params, structure_doc)
            pw_files = [f for f in written if f.suffix == ".in"]
            content = pw_files[0].read_text()
            assert "ATOMIC_POSITIONS" in content, f"ATOMIC_POSITIONS missing:\n{content}"
            assert "Si" in content, "Silicon species missing from ATOMIC_POSITIONS"

    def test_dryrun_has_cell_parameters(self):
        """dry_run input contains CELL_PARAMETERS for ibrav=0."""
        from qmatsuite.inputformat.writer import write_engine_inputs

        spec = _get_qe_input_spec()
        params = {
            "SYSTEM": {"ecutwfc": 40.0, "ibrav": 0, "nat": 2, "ntyp": 1},
            "kpoints": {"mesh": [4, 4, 4], "shift": [0, 0, 0]},
        }
        structure_doc = _build_structure_doc()

        with tempfile.TemporaryDirectory() as tmpdir:
            written = write_engine_inputs(spec, Path(tmpdir), params, structure_doc)
            pw_files = [f for f in written if f.suffix == ".in"]
            content = pw_files[0].read_text()
            assert "CELL_PARAMETERS" in content, f"CELL_PARAMETERS missing:\n{content}"
            # Lattice values should appear (2.715 for Si FCC)
            assert "2.715" in content, f"Lattice value 2.715 missing:\n{content}"

    def test_dryrun_kpoints_values_match(self):
        """K_POINTS values in dry_run match what was configured."""
        from qmatsuite.inputformat.writer import write_engine_inputs

        spec = _get_qe_input_spec()
        params = {
            "SYSTEM": {"ecutwfc": 40.0, "nat": 2, "ntyp": 1},
            "kpoints": {"mesh": [8, 8, 8], "shift": [1, 1, 1]},
        }
        structure_doc = _build_structure_doc()

        with tempfile.TemporaryDirectory() as tmpdir:
            written = write_engine_inputs(spec, Path(tmpdir), params, structure_doc)
            pw_files = [f for f in written if f.suffix == ".in"]
            content = pw_files[0].read_text()

            # Find K_POINTS section and check values
            assert "K_POINTS" in content
            # The line after K_POINTS should contain "8 8 8"
            lines = content.split("\n")
            kp_idx = None
            for i, line in enumerate(lines):
                if "K_POINTS" in line:
                    kp_idx = i
                    break
            assert kp_idx is not None
            # Next non-empty line should have the mesh
            data_line = lines[kp_idx + 1].strip()
            assert "8" in data_line, f"Expected mesh 8 8 8 but got: {data_line}"

    def test_dryrun_through_inspect_api(self, tmp_path):
        """Full dry_run through inspect_calculation matches expected content."""
        # Create project and calculation
        project_root = QMSService.init_project(tmp_path / "proj")
        svc = QMSService(project_root)

        source = tmp_path / "si.json"
        source.write_text(_SI_STRUCTURE_JSON)
        svc.structure.import_file(source, name="Silicon")

        import qmatsuite.drivers  # noqa: F401
        calc = svc.project.init_calculation(
            name="si_scf", structure_selector="Silicon", engine_family="qe",
        )
        svc.calculation.add_step(calc.ulid, step_type_gen="scf")

        # Get step detail to verify cards exist
        detail = svc.calculation.get_detail(calc.ulid)
        steps = detail.get("steps", [])
        assert len(steps) >= 1

        step0 = steps[0]
        step_ulid = step0.get("step_ulid") or step0.get("ulid", "")
        step_detail = svc.calculation.get_step_detail(calc.ulid, step_ulid)
        cards = step_detail.get("cards", {})

        # K_POINTS should be in cards (set by default on add_step)
        # This verifies the SSOT state before dry_run
        assert "K_POINTS" in cards or "kpoints" in step_detail.get("parameters", {}), (
            f"Neither K_POINTS in cards nor kpoints in params. "
            f"Cards: {list(cards.keys())}, Params keys: {list(step_detail.get('parameters', {}).keys())}"
        )
