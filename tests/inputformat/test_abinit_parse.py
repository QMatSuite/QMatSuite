"""Tests for ABINIT input parser and write-parse roundtrip.

ABINIT uses flat key-value format with structure embedded as natom/ntypat/
typat/znucl/rprim/xred variables. The parser separates structure variables
from calculation parameters.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quantumvitas.drivers.abinit.inputspec import (
    _parse_abinit_text,
    _write_abinit_text,
    get_abinit_input_spec,
)


SAMPLES_DIR = Path(__file__).parent / "samples" / "abinit"


# ──────────────────────────────────────────────────────────────────────────
# Parser unit tests
# ──────────────────────────────────────────────────────────────────────────


class TestABINITParser:
    """Unit tests for _parse_abinit_text."""

    def test_parse_basic_keyval(self):
        text = "ecut  30\nngkpt  4 4 4\n"
        result = _parse_abinit_text(text)
        assert result["params"]["ecut"] == 30
        assert result["params"]["ngkpt"] == [4, 4, 4]

    def test_parse_comments_stripped(self):
        text = "# comment\necut  30 ! inline comment\n"
        result = _parse_abinit_text(text)
        assert result["params"]["ecut"] == 30
        assert len(result["params"]) == 1

    def test_parse_fortran_d_exponent(self):
        text = "toldfe  1.0d-8\n"
        result = _parse_abinit_text(text)
        assert abs(result["params"]["toldfe"] - 1e-8) < 1e-20

    def test_parse_structure_vars(self):
        text = (
            "natom  2\n"
            "ntypat 1\n"
            "typat  1 1\n"
            "znucl  14\n"
            "acell  1.0 1.0 1.0  Angstrom\n"
            "rprim\n"
            "  5.43 0.0 0.0\n"
            "  0.0 5.43 0.0\n"
            "  0.0 0.0 5.43\n"
            "\n"
            "xred\n"
            "  0.0 0.0 0.0\n"
            "  0.25 0.25 0.25\n"
        )
        result = _parse_abinit_text(text)
        struct = result["structure"]

        # Lattice
        assert len(struct["lattice"]) == 3
        assert abs(struct["lattice"][0][0] - 5.43) < 1e-10

        # Species
        assert struct["species"] == ["Si", "Si"]

        # Fractional coordinates
        assert len(struct["frac_coords"]) == 2
        assert abs(struct["frac_coords"][1][0] - 0.25) < 1e-10

    def test_parse_multi_value(self):
        text = "shiftk  0.0 0.0 0.0\n"
        result = _parse_abinit_text(text)
        assert result["params"]["shiftk"] == [0.0, 0.0, 0.0]

    def test_parse_empty_input(self):
        result = _parse_abinit_text("")
        assert result["params"] == {}
        assert result["structure"] == {}

    def test_parse_pseudos(self):
        text = 'pp_dirpath "./"\npseudos "Si.psp8"\n'
        result = _parse_abinit_text(text)
        assert result["params"]["pp_dirpath"] == "./"
        assert result["params"]["pseudos"] == "Si.psp8"

    def test_curated_sample_parse(self):
        """Parse the curated si_scf.abi sample."""
        text = (SAMPLES_DIR / "si_scf.abi").read_text()
        result = _parse_abinit_text(text)

        # Structure
        struct = result["structure"]
        assert struct["species"] == ["Si", "Si"]
        assert len(struct["frac_coords"]) == 2
        assert abs(struct["frac_coords"][1][0] - 0.25) < 1e-10
        assert abs(struct["lattice"][0][0] - 5.4309) < 1e-6

        # Params
        assert result["params"]["ecut"] == 30
        assert result["params"]["ngkpt"] == [4, 4, 4]
        assert result["params"]["nstep"] == 50
        assert abs(result["params"]["toldfe"] - 1e-8) < 1e-20

        # znucl mapping preserved
        assert result["params"]["znucl"]["Si"] == 14


# ──────────────────────────────────────────────────────────────────────────
# Roundtrip tests
# ──────────────────────────────────────────────────────────────────────────


class TestABINITRoundtrip:
    """Primary semantic loop: dict -> write -> parse -> dict."""

    SI_PARAMS = {
        "ecut": 30,
        "ngkpt": [4, 4, 4],
        "nshiftk": 1,
        "shiftk": [0.0, 0.0, 0.0],
        "toldfe": 1e-8,
        "nstep": 50,
        "znucl": {"Si": 14},
        "pseudos": ["Si.psp8"],
        "pp_dirpath": "./",
    }

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
    }

    def test_dict_write_parse_roundtrip(self):
        """Write from params+structure -> parse -> verify."""
        fragment = {"params": self.SI_PARAMS, "structure": self.SI_STRUCTURE}
        text = _write_abinit_text(fragment)
        result = _parse_abinit_text(text)

        # Structure
        struct = result["structure"]
        assert struct["species"] == ["Si", "Si"]
        for i in range(2):
            for j in range(3):
                assert abs(
                    struct["frac_coords"][i][j] - self.SI_STRUCTURE["frac_coords"][i][j]
                ) < 1e-8
        for i in range(3):
            for j in range(3):
                assert abs(
                    struct["lattice"][i][j] - self.SI_STRUCTURE["lattice"][i][j]
                ) < 1e-6

        # Key params
        assert result["params"]["ecut"] == 30
        assert result["params"]["ngkpt"] == [4, 4, 4]
        assert result["params"]["nstep"] == 50
        assert abs(result["params"]["toldfe"] - 1e-8) < 1e-20
        assert result["params"]["znucl"]["Si"] == 14

    def test_curated_sample_roundtrip(self):
        """Parse curated sample -> write -> parse -> compare."""
        original_text = (SAMPLES_DIR / "si_scf.abi").read_text()
        parsed1 = _parse_abinit_text(original_text)

        # Write from parsed result
        text = _write_abinit_text(parsed1)
        parsed2 = _parse_abinit_text(text)

        # Compare structure
        struct1 = parsed1["structure"]
        struct2 = parsed2["structure"]
        assert struct2["species"] == struct1["species"]
        for i in range(len(struct1["frac_coords"])):
            for j in range(3):
                assert abs(
                    struct2["frac_coords"][i][j] - struct1["frac_coords"][i][j]
                ) < 1e-8
        for i in range(3):
            for j in range(3):
                assert abs(
                    struct2["lattice"][i][j] - struct1["lattice"][i][j]
                ) < 1e-6

        # Compare key params
        assert parsed2["params"]["ecut"] == parsed1["params"]["ecut"]
        assert parsed2["params"]["nstep"] == parsed1["params"]["nstep"]


class TestABINITOrchestrator:
    """Test ABINIT through the parse_engine_inputs orchestrator."""

    def test_orchestrator_roundtrip(self, tmp_path):
        """Write via orchestrator -> parse via orchestrator -> compare."""
        from quantumvitas.inputformat import write_engine_inputs, parse_engine_inputs

        spec = get_abinit_input_spec()

        params = {
            "ecut": 30,
            "ngkpt": [4, 4, 4],
            "nstep": 50,
            "toldfe": 1e-8,
            "znucl": {"Si": 14},
        }
        structure = {
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
        }

        write_engine_inputs(spec, tmp_path, params=params, structure=structure)
        result = parse_engine_inputs(spec, tmp_path)

        assert result.params["ecut"] == 30
        assert result.params["nstep"] == 50
        assert result.structure is not None
        assert result.structure["species"] == ["Si", "Si"]
        assert abs(result.structure["frac_coords"][1][0] - 0.25) < 1e-8
