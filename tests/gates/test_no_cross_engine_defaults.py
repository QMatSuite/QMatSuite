"""
Gate test: Step defaults must be engine-specific (spec-keyed), no cross-engine leakage.

QE namelist keys (CONTROL, SYSTEM, ELECTRONS) must ONLY appear in QE step defaults,
never in VASP, ORCA, LAMMPS, or other engines' step defaults.
"""

from __future__ import annotations

import pytest

# QE-specific namelist section keys that must never leak into non-QE steps
QE_NAMELIST_KEYS = {"CONTROL", "SYSTEM", "ELECTRONS", "IONS", "CELL", "DOS"}


def _create_step(step_type_gen: str, engine_family: str) -> dict:
    """Create a step via create_step_doc and return its data dict."""
    from qmatsuite.workflow.step_factory import create_step_doc
    step_doc = create_step_doc(step_type_gen, name="test", engine_family=engine_family)
    return step_doc.to_dict()


class TestNoCrossEngineDefaults:
    """QE namelist keys must not appear in non-QE step defaults."""

    def test_vasp_scf_no_qe_namelists(self):
        data = _create_step("scf", "vasp")
        params = data.get("parameters", {})
        leaked = set(params.keys()) & QE_NAMELIST_KEYS
        assert not leaked, f"VASP SCF step has QE namelist keys: {leaked}"

    def test_orca_scf_no_qe_namelists(self):
        data = _create_step("scf", "orca")
        params = data.get("parameters", {})
        leaked = set(params.keys()) & QE_NAMELIST_KEYS
        assert not leaked, f"ORCA SCF step has QE namelist keys: {leaked}"

    def test_lammps_scf_no_qe_namelists(self):
        """LAMMPS doesn't have scf, but md does — ensure no QE keys."""
        data = _create_step("md", "lammps")
        params = data.get("parameters", {})
        leaked = set(params.keys()) & QE_NAMELIST_KEYS
        assert not leaked, f"LAMMPS MD step has QE namelist keys: {leaked}"

    def test_qe_scf_has_qe_namelists(self):
        """QE SCF step MUST have CONTROL/SYSTEM/ELECTRONS defaults."""
        data = _create_step("scf", "qe")
        params = data.get("parameters", {})
        assert "CONTROL" in params, "QE SCF step missing CONTROL defaults"
        assert "SYSTEM" in params, "QE SCF step missing SYSTEM defaults"
        assert "ELECTRONS" in params, "QE SCF step missing ELECTRONS defaults"

    def test_companion_w90_no_qe_namelists(self):
        """Wannier90 step must NOT inherit QE namelist defaults."""
        from qmatsuite.calculation.step_defaults import get_default_step_params
        defaults = get_default_step_params("w90_wannierprep")
        params = defaults.get("parameters", {})
        leaked = set(params.keys()) & QE_NAMELIST_KEYS
        assert not leaked, f"w90 defaults have QE namelist keys: {leaked}"

    def test_companion_qmcpack_no_qe_namelists(self):
        """QMCPACK step must NOT inherit QE namelist defaults."""
        from qmatsuite.calculation.step_defaults import get_default_step_params
        defaults = get_default_step_params("qmcpack_vmc")
        params = defaults.get("parameters", {})
        leaked = set(params.keys()) & QE_NAMELIST_KEYS
        assert not leaked, f"QMCPACK defaults have QE namelist keys: {leaked}"
