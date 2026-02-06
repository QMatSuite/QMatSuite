"""Tests for the VASP curated example corpus.

Validates all 12 cases parse correctly, roundtrip successfully,
and have valid case.yaml metadata.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from quantumvitas.drivers.vasp.io.incar import parse_incar_text
from quantumvitas.drivers.vasp.io.poscar import write_poscar_text, parse_poscar_text
from quantumvitas.drivers.vasp.io.kpoints import write_kpoints_text, parse_kpoints_text


CORPUS_DIR = Path(__file__).parent.parent.parent / "inputformat" / "samples" / "vasp"

EXPECTED_CASES = [
    "si_scf", "si_relax", "si_vc_relax", "si_bands", "si_dos",
    "fe_magnetic", "tio2_hubbard", "graphene_vdw", "al_md",
    "mgo_slab", "si_hybrid", "gaas_soc",
]

CASE_YAML_REQUIRED_FIELDS = {"case_id", "title", "engine", "species", "description"}


def _get_case_dirs() -> list[Path]:
    """Return all case directories that contain INCAR + POSCAR + KPOINTS."""
    dirs = []
    for d in sorted(CORPUS_DIR.iterdir()):
        if d.is_dir() and (d / "INCAR").exists():
            dirs.append(d)
    return dirs


# ──────────────────────────────────────────────────────────────────────────
# Case structure validation
# ──────────────────────────────────────────────────────────────────────────


class TestCorpusStructure:
    """Validate corpus directory structure."""

    def test_expected_cases_exist(self):
        """All 12 expected case directories exist."""
        existing = {d.name for d in _get_case_dirs()}
        for case in EXPECTED_CASES:
            assert case in existing, f"Missing case directory: {case}"

    def test_all_cases_have_required_files(self):
        """Each case has INCAR, POSCAR, KPOINTS."""
        for case_dir in _get_case_dirs():
            for fname in ("INCAR", "POSCAR", "KPOINTS"):
                assert (case_dir / fname).exists(), (
                    f"{case_dir.name}/{fname} missing"
                )

    def test_case_yaml_valid(self):
        """Each case.yaml has required fields."""
        for case_dir in _get_case_dirs():
            yaml_path = case_dir / "case.yaml"
            if not yaml_path.exists():
                continue
            with open(yaml_path) as fh:
                data = yaml.safe_load(fh)
            missing = CASE_YAML_REQUIRED_FIELDS - set(data.keys())
            assert not missing, (
                f"{case_dir.name}/case.yaml missing fields: {missing}"
            )
            assert data["engine"] == "vasp"

    def test_case_yaml_present_for_all(self):
        """Each case directory has a case.yaml."""
        for case_dir in _get_case_dirs():
            assert (case_dir / "case.yaml").exists(), (
                f"{case_dir.name} missing case.yaml"
            )


# ──────────────────────────────────────────────────────────────────────────
# Parse validation
# ──────────────────────────────────────────────────────────────────────────


class TestCorpusParse:
    """Parse all cases without errors."""

    @pytest.mark.parametrize("case_name", EXPECTED_CASES)
    def test_incar_parse(self, case_name):
        """INCAR parses to non-empty dict."""
        text = (CORPUS_DIR / case_name / "INCAR").read_text()
        result = parse_incar_text(text)
        assert isinstance(result, dict)
        assert len(result) > 0, f"{case_name} INCAR parsed to empty dict"
        assert "SYSTEM" in result or "ENCUT" in result

    @pytest.mark.parametrize("case_name", EXPECTED_CASES)
    def test_poscar_parse(self, case_name):
        """POSCAR parses to valid structure dict."""
        text = (CORPUS_DIR / case_name / "POSCAR").read_text()
        result = parse_poscar_text(text)
        assert "lattice" in result
        assert "species" in result
        assert "frac_coords" in result
        assert len(result["species"]) > 0
        assert len(result["frac_coords"]) == len(result["species"])

    @pytest.mark.parametrize("case_name", EXPECTED_CASES)
    def test_kpoints_parse(self, case_name):
        """KPOINTS parses to valid kpoints dict."""
        text = (CORPUS_DIR / case_name / "KPOINTS").read_text()
        result = parse_kpoints_text(text)
        assert "mode" in result


# ──────────────────────────────────────────────────────────────────────────
# Roundtrip validation
# ──────────────────────────────────────────────────────────────────────────


class TestCorpusRoundtrip:
    """Parse -> write -> parse roundtrip for all cases."""

    @pytest.mark.parametrize("case_name", EXPECTED_CASES)
    def test_poscar_roundtrip(self, case_name):
        """POSCAR parse -> write -> parse preserves structure."""
        text = (CORPUS_DIR / case_name / "POSCAR").read_text()
        parsed = parse_poscar_text(text)
        written = write_poscar_text(parsed)
        reparsed = parse_poscar_text(written)

        assert parsed["species"] == reparsed["species"]
        for i in range(len(parsed["frac_coords"])):
            for j in range(3):
                assert abs(
                    parsed["frac_coords"][i][j] - reparsed["frac_coords"][i][j]
                ) < 1e-10, f"{case_name} coord mismatch at [{i}][{j}]"

    @pytest.mark.parametrize("case_name", EXPECTED_CASES)
    def test_kpoints_roundtrip(self, case_name):
        """KPOINTS parse -> write -> parse preserves k-points."""
        text = (CORPUS_DIR / case_name / "KPOINTS").read_text()
        parsed = parse_kpoints_text(text)
        written = write_kpoints_text(parsed)
        reparsed = parse_kpoints_text(written)

        assert parsed["mode"] == reparsed["mode"]
        if parsed["mode"] == "automatic":
            assert parsed["mesh"] == reparsed["mesh"]


# ──────────────────────────────────────────────────────────────────────────
# Full 3-file orchestrator roundtrip
# ──────────────────────────────────────────────────────────────────────────


class TestCorpusOrchestrator:
    """Full 3-file roundtrip via inputformat orchestrator."""

    @pytest.mark.parametrize("case_name", EXPECTED_CASES)
    def test_orchestrator_roundtrip(self, case_name, tmp_path):
        """Copy case -> parse -> write -> parse -> semantic equality."""
        from quantumvitas.inputformat import write_engine_inputs, parse_engine_inputs
        from quantumvitas.drivers.vasp.inputspec import get_vasp_input_spec

        spec = get_vasp_input_spec()
        case_dir = CORPUS_DIR / case_name

        # Copy to workdir
        workdir = tmp_path / case_name
        workdir.mkdir()
        for fname in ("INCAR", "POSCAR", "KPOINTS"):
            shutil.copy(case_dir / fname, workdir / fname)

        # Parse
        result1 = parse_engine_inputs(spec, workdir)
        assert result1.structure is not None

        # Write to new dir
        out_dir = tmp_path / f"{case_name}_rewrite"
        write_engine_inputs(
            spec, out_dir,
            params=result1.params,
            structure=result1.structure,
        )

        # Re-parse
        result2 = parse_engine_inputs(spec, out_dir)
        assert result2.structure is not None

        # Compare params (excluding kpoints)
        for key in result1.params:
            if key == "kpoints":
                continue
            assert result2.params[key] == result1.params[key], (
                f"{case_name} param {key}: {result2.params[key]} != {result1.params[key]}"
            )

        # Compare structure species
        assert result2.structure["species"] == result1.structure["species"]
