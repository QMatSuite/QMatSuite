"""Tests for VASP INCAR parser and full 3-file write-parse roundtrip.

Enforces the primary semantic loop:
    YAML(params+structure+kpoints) -> write -> parse -> YAML (semantic equality)

No text fidelity, no comments/whitespace preservation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quantumvitas.drivers.vasp.io.incar import parse_incar_text
from quantumvitas.drivers.vasp.inputspec import _write_incar_text


SAMPLES_DIR = Path(__file__).parent / "samples" / "vasp"


# ──────────────────────────────────────────────────────────────────────────
# INCAR parser unit tests
# ──────────────────────────────────────────────────────────────────────────


class TestINCARParser:
    """Unit tests for parse_incar_text."""

    def test_basic_key_value(self):
        text = "ENCUT = 300\nISMEAR = 0\n"
        result = parse_incar_text(text)
        assert result["ENCUT"] == 300
        assert result["ISMEAR"] == 0

    def test_system_tag(self):
        text = "SYSTEM = Si bulk SCF\n"
        result = parse_incar_text(text)
        assert result["SYSTEM"] == "Si bulk SCF"

    def test_boolean_true_false(self):
        text = "LCHARG = .TRUE.\nLWAVE = .FALSE.\n"
        result = parse_incar_text(text)
        assert result["LCHARG"] is True
        assert result["LWAVE"] is False

    def test_boolean_case_insensitive(self):
        text = "LCHARG = .true.\nLWAVE = .False.\n"
        result = parse_incar_text(text)
        assert result["LCHARG"] is True
        assert result["LWAVE"] is False

    def test_integer_values(self):
        text = "NSW = 0\nNELM = 60\nIBRION = -1\n"
        result = parse_incar_text(text)
        assert result["NSW"] == 0
        assert result["NELM"] == 60
        assert result["IBRION"] == -1

    def test_float_values(self):
        text = "SIGMA = 0.05\nEDIFF = 1e-6\n"
        result = parse_incar_text(text)
        assert abs(result["SIGMA"] - 0.05) < 1e-12
        assert abs(result["EDIFF"] - 1e-6) < 1e-18

    def test_fortran_d_exponent(self):
        text = "EDIFF = 1.0d-6\n"
        result = parse_incar_text(text)
        assert abs(result["EDIFF"] - 1e-6) < 1e-18

    def test_comments_stripped(self):
        text = "ENCUT = 300 ! cutoff energy\n# this is a comment\nISMEAR = 0\n"
        result = parse_incar_text(text)
        assert result["ENCUT"] == 300
        assert result["ISMEAR"] == 0
        assert len(result) == 2

    def test_semicolon_multi_tag(self):
        text = "ISMEAR = 0 ; SIGMA = 0.1\n"
        result = parse_incar_text(text)
        assert result["ISMEAR"] == 0
        assert abs(result["SIGMA"] - 0.1) < 1e-12

    def test_multi_value_list(self):
        text = "MAGMOM = 3.0 3.0 -3.0 -3.0\n"
        result = parse_incar_text(text)
        assert result["MAGMOM"] == [3.0, 3.0, -3.0, -3.0]

    def test_star_expansion(self):
        text = "MAGMOM = 2*3.0 2*-3.0\n"
        result = parse_incar_text(text)
        assert result["MAGMOM"] == [3.0, 3.0, -3.0, -3.0]

    def test_empty_input(self):
        assert parse_incar_text("") == {}
        assert parse_incar_text("   \n  \n") == {}

    def test_string_value(self):
        text = "PREC = Accurate\n"
        result = parse_incar_text(text)
        assert result["PREC"] == "Accurate"

    def test_keys_uppercase(self):
        text = "encut = 300\nismear = 0\n"
        result = parse_incar_text(text)
        assert "ENCUT" in result
        assert "ISMEAR" in result

    def test_curated_sample_parse(self):
        """Parse the curated si_scf_INCAR sample."""
        text = (SAMPLES_DIR / "si_scf_INCAR").read_text()
        result = parse_incar_text(text)

        assert result["SYSTEM"] == "Si diamond SCF"
        assert result["ENCUT"] == 240
        assert result["IBRION"] == -1
        assert result["ISMEAR"] == 0
        assert result["LCHARG"] is True
        assert result["LWAVE"] is False
        assert result["NSW"] == 0
        assert result["PREC"] == "Accurate"
        assert abs(result["SIGMA"] - 0.05) < 1e-12


# ──────────────────────────────────────────────────────────────────────────
# INCAR writer-parser roundtrip
# ──────────────────────────────────────────────────────────────────────────


class TestINCAR_WriterParserRoundtrip:
    """Primary semantic loop: dict -> write -> parse -> dict."""

    def test_basic_roundtrip(self):
        params = {"ENCUT": 300, "ISMEAR": 0, "NSW": 100}
        text = _write_incar_text(params)
        recovered = parse_incar_text(text)
        for key in params:
            assert recovered[key] == params[key], f"Mismatch on {key}"

    def test_boolean_roundtrip(self):
        params = {"LCHARG": True, "LWAVE": False}
        text = _write_incar_text(params)
        recovered = parse_incar_text(text)
        assert recovered["LCHARG"] is True
        assert recovered["LWAVE"] is False

    def test_string_roundtrip(self):
        params = {"SYSTEM": "Si bulk SCF", "PREC": "Accurate"}
        text = _write_incar_text(params)
        recovered = parse_incar_text(text)
        assert recovered["SYSTEM"] == "Si bulk SCF"
        assert recovered["PREC"] == "Accurate"

    def test_float_roundtrip(self):
        params = {"SIGMA": 0.05, "EDIFF": 1e-6}
        text = _write_incar_text(params)
        recovered = parse_incar_text(text)
        assert abs(recovered["SIGMA"] - 0.05) < 1e-12
        assert abs(recovered["EDIFF"] - 1e-6) < 1e-18

    def test_curated_sample_roundtrip(self):
        """Parse curated INCAR -> write -> parse -> compare."""
        original_text = (SAMPLES_DIR / "si_scf_INCAR").read_text()
        parsed = parse_incar_text(original_text)
        written = _write_incar_text(parsed)
        reparsed = parse_incar_text(written)
        for key in parsed:
            assert reparsed[key] == parsed[key], f"Roundtrip mismatch on {key}"


# ──────────────────────────────────────────────────────────────────────────
# Full 3-file VASP roundtrip via orchestrator
# ──────────────────────────────────────────────────────────────────────────


class TestVASPFullRoundtrip:
    """End-to-end: SSOT dicts -> write_engine_inputs -> parse_engine_inputs."""

    SI_STRUCTURE = {
        "lattice": [
            [5.4309, 0.0, 0.0],
            [0.0, 5.4309, 0.0],
            [0.0, 0.0, 5.4309],
        ],
        "species": ["Si", "Si"],
        "frac_coords": [
            [0.0, 0.0, 0.0],
            [0.25, 0.25, 0.25],
        ],
        "comment": "Si diamond",
    }

    VASP_PARAMS = {
        "SYSTEM": "Si diamond SCF",
        "ENCUT": 240,
        "ISMEAR": 0,
        "SIGMA": 0.05,
        "NSW": 0,
        "IBRION": -1,
        "LCHARG": True,
        "LWAVE": False,
        "kpoints": {
            "mode": "automatic",
            "mesh": [4, 4, 4],
            "shift": [0, 0, 0],
            "centering": "Gamma",
        },
    }

    def _get_vasp_spec(self):
        from quantumvitas.drivers.vasp.inputspec import get_vasp_input_spec
        return get_vasp_input_spec()

    def test_full_write_parse_roundtrip(self, tmp_path):
        """Write VASP files -> parse -> verify params and structure."""
        from quantumvitas.inputformat import write_engine_inputs, parse_engine_inputs

        spec = self._get_vasp_spec()

        # Write
        write_engine_inputs(
            spec, tmp_path,
            params=self.VASP_PARAMS,
            structure=self.SI_STRUCTURE,
        )

        # Parse
        result = parse_engine_inputs(spec, tmp_path)

        # Verify params
        assert result.params["ENCUT"] == 240
        assert result.params["ISMEAR"] == 0
        assert abs(result.params["SIGMA"] - 0.05) < 1e-12
        assert result.params["NSW"] == 0
        assert result.params["LCHARG"] is True
        assert result.params["LWAVE"] is False

        # Verify kpoints
        assert "kpoints" in result.params
        kpts = result.params["kpoints"]
        assert kpts["mode"] == "automatic"
        assert kpts["mesh"] == [4, 4, 4]
        assert kpts["centering"] == "Gamma"

        # Verify structure
        assert result.structure is not None
        assert result.structure["species"] == ["Si", "Si"]
        for i in range(3):
            for j in range(3):
                assert abs(
                    result.structure["lattice"][i][j]
                    - self.SI_STRUCTURE["lattice"][i][j]
                ) < 1e-10
        for i in range(2):
            for j in range(3):
                assert abs(
                    result.structure["frac_coords"][i][j]
                    - self.SI_STRUCTURE["frac_coords"][i][j]
                ) < 1e-10

    def test_curated_sample_full_roundtrip(self, tmp_path):
        """Copy curated samples -> parse -> write -> parse -> compare."""
        from quantumvitas.inputformat import write_engine_inputs, parse_engine_inputs
        import shutil

        spec = self._get_vasp_spec()

        # Copy curated samples to workdir with canonical filenames
        shutil.copy(SAMPLES_DIR / "si_scf_INCAR", tmp_path / "INCAR")
        shutil.copy(SAMPLES_DIR / "si_scf_POSCAR", tmp_path / "POSCAR")
        shutil.copy(SAMPLES_DIR / "si_scf_KPOINTS", tmp_path / "KPOINTS")

        # First parse
        result1 = parse_engine_inputs(spec, tmp_path)

        # Write to new dir
        out_dir = tmp_path / "rewritten"
        write_engine_inputs(
            spec, out_dir,
            params=result1.params,
            structure=result1.structure,
        )

        # Second parse
        result2 = parse_engine_inputs(spec, out_dir)

        # Compare params (excluding kpoints, compared separately)
        for key in result1.params:
            if key == "kpoints":
                continue
            assert result2.params[key] == result1.params[key], (
                f"Param {key}: {result2.params[key]} != {result1.params[key]}"
            )

        # Compare kpoints
        assert result2.params["kpoints"]["mode"] == result1.params["kpoints"]["mode"]
        assert result2.params["kpoints"]["mesh"] == result1.params["kpoints"]["mesh"]

        # Compare structure
        assert result2.structure is not None
        assert result1.structure is not None
        assert result2.structure["species"] == result1.structure["species"]
        for i in range(len(result1.structure["frac_coords"])):
            for j in range(3):
                assert abs(
                    result2.structure["frac_coords"][i][j]
                    - result1.structure["frac_coords"][i][j]
                ) < 1e-10
