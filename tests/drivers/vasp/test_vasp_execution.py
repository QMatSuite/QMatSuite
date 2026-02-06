"""Tests for VASP execution framework (vasp_runner.py).

Tests that require real VASP binary or POTCAR library are conditional:
they skip in CI and when resources are unavailable.

Non-conditional tests use synthetic data and mock objects.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from quantumvitas.drivers.vasp.engine.vasp_runner import (
    RunResult,
    find_vasp_binary,
    run_vasp_case,
    verify_reference,
    DEFAULT_TOLERANCES,
    _extract_species_from_poscar,
)


# ──────────────────────────────────────────────────────────────────────────
# Non-conditional tests (always run)
# ──────────────────────────────────────────────────────────────────────────


class TestRunResult:
    """Test RunResult dataclass."""

    def test_defaults(self):
        r = RunResult(success=False)
        assert r.success is False
        assert r.digest is None
        assert r.return_code == -1
        assert r.elapsed_s == 0.0
        assert r.error is None

    def test_populated(self):
        r = RunResult(
            success=True,
            return_code=0,
            elapsed_s=3.14,
            stdout="ok",
        )
        assert r.success is True
        assert r.return_code == 0
        assert r.elapsed_s == 3.14
        assert r.stdout == "ok"


class TestFindVaspBinary:
    """Test binary resolution."""

    def test_return_type(self):
        result = find_vasp_binary("vasp_std")
        assert result is None or isinstance(result, Path)

    def test_nonexistent_variant(self):
        result = find_vasp_binary("vasp_doesnotexist")
        assert result is None

    def test_env_override(self, tmp_path, monkeypatch):
        fake_bin = tmp_path / "vasp_std"
        fake_bin.write_text("#!/bin/sh\nexit 0\n")
        fake_bin.chmod(0o755)
        monkeypatch.setenv("QMATS_VASP_STD_BIN", str(fake_bin))
        result = find_vasp_binary("vasp_std")
        assert result == fake_bin


class TestExtractSpecies:
    """Test POSCAR species extraction."""

    def test_standard_poscar(self, tmp_path):
        poscar = tmp_path / "POSCAR"
        poscar.write_text(
            "Si diamond\n"
            "1.0\n"
            "5.43 0.00 0.00\n"
            "0.00 5.43 0.00\n"
            "0.00 0.00 5.43\n"
            "Si\n"
            "2\n"
            "Direct\n"
            "0.0 0.0 0.0\n"
            "0.25 0.25 0.25\n"
        )
        species = _extract_species_from_poscar(poscar)
        assert species == ["Si"]

    def test_multi_species(self, tmp_path):
        poscar = tmp_path / "POSCAR"
        poscar.write_text(
            "NaCl\n"
            "1.0\n"
            "5.64 0.00 0.00\n"
            "0.00 5.64 0.00\n"
            "0.00 0.00 5.64\n"
            "Na Cl\n"
            "4 4\n"
            "Direct\n"
        )
        species = _extract_species_from_poscar(poscar)
        assert species == ["Na", "Cl"]

    def test_missing_file(self, tmp_path):
        species = _extract_species_from_poscar(tmp_path / "POSCAR")
        assert species == []


class TestVerifyReference:
    """Test reference verification utility."""

    def test_all_pass(self):
        class FakeDigest:
            final_energy_eV = -10.85
            n_atoms = 2
            converged_electronic = True

        ref = {
            "final_energy_eV": -10.85,
            "n_atoms": 2,
            "converged_electronic": True,
        }
        result = verify_reference(FakeDigest(), ref)
        assert result["passed"] is True
        assert result["n_failed"] == 0
        assert result["n_passed"] == 3

    def test_energy_within_tolerance(self):
        class FakeDigest:
            final_energy_eV = -10.855

        ref = {"final_energy_eV": -10.85}
        result = verify_reference(FakeDigest(), ref)
        assert result["passed"] is True  # 0.005 < 0.01 default tol

    def test_energy_outside_tolerance(self):
        class FakeDigest:
            final_energy_eV = -10.90

        ref = {"final_energy_eV": -10.85}
        result = verify_reference(FakeDigest(), ref)
        assert result["passed"] is False  # 0.05 > 0.01

    def test_custom_tolerance(self):
        class FakeDigest:
            final_energy_eV = -10.90

        ref = {"final_energy_eV": -10.85}
        result = verify_reference(FakeDigest(), ref, tolerances={"final_energy_eV": 0.1})
        assert result["passed"] is True  # 0.05 < 0.1

    def test_missing_field(self):
        class FakeDigest:
            pass

        ref = {"final_energy_eV": -10.85}
        result = verify_reference(FakeDigest(), ref)
        assert result["passed"] is False
        assert result["checks"][0]["reason"] == "missing from digest"

    def test_bool_field(self):
        class FakeDigest:
            converged_electronic = False

        ref = {"converged_electronic": True}
        result = verify_reference(FakeDigest(), ref)
        assert result["passed"] is False

    def test_default_tolerances_exist(self):
        assert "final_energy_eV" in DEFAULT_TOLERANCES
        assert "energy_per_atom_eV" in DEFAULT_TOLERANCES
        assert "volume_A3" in DEFAULT_TOLERANCES


class TestRunVaspCaseMock:
    """Test run_vasp_case with missing inputs (no real execution)."""

    def test_missing_incar(self, tmp_path):
        case_dir = tmp_path / "case"
        case_dir.mkdir()
        (case_dir / "POSCAR").write_text("dummy")
        (case_dir / "KPOINTS").write_text("dummy")
        # No INCAR
        result = run_vasp_case(case_dir, tmp_path / "work")
        assert result.success is False
        assert "Missing INCAR" in result.error

    def test_missing_binary(self, tmp_path, monkeypatch):
        """Missing VASP binary → graceful failure."""
        case_dir = tmp_path / "case"
        case_dir.mkdir()
        for f in ["INCAR", "POSCAR", "KPOINTS"]:
            (case_dir / f).write_text("dummy")
        # Clear all env vars
        monkeypatch.delenv("QMATS_VASP_STD_BIN", raising=False)
        monkeypatch.delenv("QMATS_VASP_GAM_BIN", raising=False)
        # Use a variant that definitely does not exist
        result = run_vasp_case(
            case_dir, tmp_path / "work",
            vasp_binary="vasp_absolutely_nonexistent_variant",
        )
        assert result.success is False
        assert "not found" in result.error


class TestRefValuesYaml:
    """Test that ref_values.yaml for si_scf case is well-formed."""

    def test_ref_values_loadable(self, si_scf_case_dir):
        ref_path = si_scf_case_dir / "ref_values.yaml"
        assert ref_path.is_file(), "ref_values.yaml missing from si_scf"
        ref = yaml.safe_load(ref_path.read_text())
        assert isinstance(ref, dict)
        assert "converged_electronic" in ref
        assert "n_atoms" in ref


# ──────────────────────────────────────────────────────────────────────────
# Conditional tests (require real VASP + POTCAR)
# ──────────────────────────────────────────────────────────────────────────


class TestRealVASPExecution:
    """Tests that run real VASP. Skip if binary/POTCAR unavailable."""

    def test_si_scf_runs(self, vasp_binary, potcar_library, si_scf_case_dir, tmp_path):
        """Run Si SCF with real VASP and verify convergence."""
        result = run_vasp_case(
            si_scf_case_dir,
            tmp_path / "si_scf_work",
            timeout=300,
        )
        assert result.success, f"VASP failed: {result.error}"
        assert result.digest is not None
        assert result.digest.final_energy_eV is not None
        assert result.digest.converged_electronic is True

    def test_si_scf_reference_check(self, vasp_binary, potcar_library, si_scf_case_dir, tmp_path):
        """Run Si SCF and check against ref_values.yaml."""
        ref_path = si_scf_case_dir / "ref_values.yaml"
        ref = yaml.safe_load(ref_path.read_text())

        result = run_vasp_case(
            si_scf_case_dir,
            tmp_path / "si_scf_ref",
            timeout=300,
        )
        assert result.success, f"VASP failed: {result.error}"
        assert result.digest is not None

        report = verify_reference(result.digest, ref)
        for check in report["checks"]:
            if not check["passed"]:
                print(f"  FAIL: {check['field']}: {check['reason']}")
        assert report["passed"], (
            f"{report['n_failed']} reference checks failed"
        )

    def test_digest_fields_populated(self, vasp_binary, potcar_library, si_scf_case_dir, tmp_path):
        """Verify digest has key fields populated after real run."""
        result = run_vasp_case(
            si_scf_case_dir,
            tmp_path / "si_scf_fields",
            timeout=300,
        )
        assert result.success, f"VASP failed: {result.error}"
        d = result.digest
        assert d is not None
        assert d.n_atoms == 2
        assert d.final_lattice is not None
        assert d.final_frac_coords is not None
        assert d.volume_A3 is not None
        assert d.n_ionic_steps >= 1
        assert d.n_electronic_steps >= 1
