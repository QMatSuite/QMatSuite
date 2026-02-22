"""Tests for ORCA input parser and write-parse roundtrip.

ORCA is a keyword-block format with Cartesian geometry. The writer
converts frac_coords → Cartesian; the parser returns Cartesian coordinates.
Roundtrip tests compare Cartesian coordinates with tolerance.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qmatsuite.drivers.orca.inputspec import (
    _parse_orca_text,
    _write_orca_text,
    get_orca_input_spec,
)


SAMPLES_DIR = Path(__file__).parent / "samples" / "orca"


# ──────────────────────────────────────────────────────────────────────────
# Parser unit tests
# ──────────────────────────────────────────────────────────────────────────


class TestORCAParser:
    """Unit tests for _parse_orca_text."""

    def test_parse_keyword_line(self):
        text = "! B3LYP def2-SVP Opt\n\n* xyz 0 1\n  H  0.0 0.0 0.0\n*\n"
        result = _parse_orca_text(text)
        assert result["params"]["method"] == "B3LYP"
        assert result["params"]["basis"] == "def2-SVP"
        assert result["params"]["keywords"] == ["Opt"]

    def test_parse_geometry_block(self):
        text = "! HF STO-3G\n\n* xyz 0 1\n  O  0.0 0.0 0.117\n  H  0.0 0.757 -0.469\n  H  0.0 -0.757 -0.469\n*\n"
        result = _parse_orca_text(text)
        assert result["params"]["charge"] == 0
        assert result["params"]["multiplicity"] == 1
        assert result["structure"]["species"] == ["O", "H", "H"]
        assert len(result["structure"]["cart_coords"]) == 3
        assert abs(result["structure"]["cart_coords"][0][2] - 0.117) < 1e-8

    def test_parse_pal_block(self):
        text = "! HF STO-3G\n%pal nprocs 4 end\n\n* xyz 0 1\n  H  0.0 0.0 0.0\n*\n"
        result = _parse_orca_text(text)
        assert result["params"]["nprocs"] == 4

    def test_parse_maxcore(self):
        text = "! HF STO-3G\n%maxcore 4000\n\n* xyz 0 1\n  H  0.0 0.0 0.0\n*\n"
        result = _parse_orca_text(text)
        assert result["params"]["maxcore"] == 4000

    def test_parse_extra_block(self):
        text = "! HF STO-3G\n%scf\n  MaxIter 200\n  ConvForced true\nend\n\n* xyz 0 1\n  H  0.0 0.0 0.0\n*\n"
        result = _parse_orca_text(text)
        assert "blocks" in result["params"]
        assert "scf" in result["params"]["blocks"]
        assert result["params"]["blocks"]["scf"]["MaxIter"] == 200

    def test_parse_empty_input(self):
        result = _parse_orca_text("")
        assert result["params"] == {}
        assert result["structure"] == {}

    def test_curated_sample_parse(self):
        """Parse the curated water_sp sample."""
        text = (SAMPLES_DIR / "water_sp" / "input.inp").read_text()
        result = _parse_orca_text(text)

        assert result["params"]["method"] == "B3LYP"
        assert result["params"]["basis"] == "DEF2-TZVP"
        assert "RIJCOSX" in result["params"]["keywords"]
        assert "D3BJ" in result["params"]["keywords"]
        assert "TIGHTSCF" in result["params"]["keywords"]
        assert result["params"]["maxcore"] == 2000
        assert result["params"]["nprocs"] == 4
        assert result["params"]["charge"] == 0
        assert result["params"]["multiplicity"] == 1

        assert len(result["structure"]["species"]) == 3
        assert result["structure"]["species"].count("O") == 1
        assert result["structure"]["species"].count("H") == 2
        assert len(result["structure"]["cart_coords"]) == 3


# ──────────────────────────────────────────────────────────────────────────
# Roundtrip tests
# ──────────────────────────────────────────────────────────────────────────


class TestORCARoundtrip:
    """Primary semantic loop: dict -> write -> parse -> dict.

    ORCA uses Cartesian coordinates. The writer converts fractional→Cartesian.
    The parser returns Cartesian. Roundtrip comparison is on Cartesian coords.
    """

    WATER_PARAMS = {
        "method": "B3LYP",
        "basis": "def2-SVP",
        "keywords": ["Opt"],
        "charge": 0,
        "multiplicity": 1,
        "maxcore": 4000,
        "nprocs": 4,
    }

    WATER_STRUCTURE = {
        "lattice": [
            [10.0, 0.0, 0.0],
            [0.0, 10.0, 0.0],
            [0.0, 0.0, 10.0],
        ],
        "species": ["O", "H", "H"],
        "frac_coords": [
            [0.0, 0.0, 0.0117],
            [0.0, 0.0757, -0.0469],
            [0.0, -0.0757, -0.0469],
        ],
    }

    def test_dict_write_parse_roundtrip(self):
        """Write from params+structure -> parse -> verify params and Cartesian coords."""
        fragment = {"params": self.WATER_PARAMS, "structure": self.WATER_STRUCTURE}
        text = _write_orca_text(fragment)
        result = _parse_orca_text(text)

        # Verify params
        assert result["params"]["method"] == "B3LYP"
        assert result["params"]["basis"] == "def2-SVP"
        assert result["params"]["keywords"] == ["Opt"]
        assert result["params"]["charge"] == 0
        assert result["params"]["multiplicity"] == 1
        assert result["params"]["maxcore"] == 4000
        assert result["params"]["nprocs"] == 4

        # Verify species
        assert result["structure"]["species"] == ["O", "H", "H"]

        # Verify Cartesian coordinates (derived from fractional * lattice)
        expected_cart = [
            [0.0, 0.0, 0.117],
            [0.0, 0.757, -0.469],
            [0.0, -0.757, -0.469],
        ]
        for i in range(3):
            for j in range(3):
                assert abs(
                    result["structure"]["cart_coords"][i][j] - expected_cart[i][j]
                ) < 1e-4

    def test_curated_sample_roundtrip(self):
        """Parse curated sample -> write -> parse -> compare Cartesian coords."""
        original_text = (SAMPLES_DIR / "water_sp" / "input.inp").read_text()
        parsed1 = _parse_orca_text(original_text)

        # Write from parsed result (using cart_coords as frac_coords without lattice)
        fragment = {
            "params": parsed1["params"],
            "structure": {
                "species": parsed1["structure"]["species"],
                "frac_coords": parsed1["structure"]["cart_coords"],
                "lattice": [],  # no lattice = coords are used as-is
            },
        }
        text = _write_orca_text(fragment)
        parsed2 = _parse_orca_text(text)

        # Compare params
        assert parsed2["params"]["method"] == parsed1["params"]["method"]
        assert parsed2["params"]["basis"] == parsed1["params"]["basis"]
        assert parsed2["params"]["charge"] == parsed1["params"]["charge"]
        assert parsed2["params"]["multiplicity"] == parsed1["params"]["multiplicity"]

        # Compare Cartesian coordinates
        assert parsed2["structure"]["species"] == parsed1["structure"]["species"]
        for i in range(len(parsed1["structure"]["cart_coords"])):
            for j in range(3):
                assert abs(
                    parsed2["structure"]["cart_coords"][i][j]
                    - parsed1["structure"]["cart_coords"][i][j]
                ) < 1e-6


class TestORCAOrchestrator:
    """Test ORCA through the parse_engine_inputs orchestrator."""

    def test_orchestrator_roundtrip(self, tmp_path):
        """Write via orchestrator -> parse via orchestrator -> compare."""
        from qmatsuite.inputformat import write_engine_inputs, parse_engine_inputs

        spec = get_orca_input_spec()

        params = {
            "method": "B3LYP",
            "basis": "def2-SVP",
            "charge": 0,
            "multiplicity": 1,
        }
        structure = {
            "species": ["O", "H", "H"],
            "frac_coords": [
                [0.0, 0.0, 0.0],
                [0.0, 0.757, -0.469],
                [0.0, -0.757, -0.469],
            ],
            "lattice": [],
        }

        write_engine_inputs(spec, tmp_path, params=params, structure=structure)
        result = parse_engine_inputs(spec, tmp_path)

        assert result.params["method"] == "B3LYP"
        assert result.params["basis"] == "def2-SVP"
        assert result.structure is not None
        assert result.structure["species"] == ["O", "H", "H"]


# ──────────────────────────────────────────────────────────────────────────
# Enhanced parser tests (Stage 4)
# ──────────────────────────────────────────────────────────────────────────


class TestORCAEnhancedParser:
    """Tests for enhanced parser features: multi-line blocks, booleans, CPCM, etc."""

    def test_parse_multiline_pal_block(self):
        """Multi-line %pal block should extract nprocs."""
        text = """! B3LYP def2-SVP
%pal
  nprocs 8
end

* xyz 0 1
  H  0.0 0.0 0.0
*
"""
        result = _parse_orca_text(text)
        assert result["params"]["nprocs"] == 8
        assert "blocks" in result["params"]
        assert result["params"]["blocks"]["pal"]["nprocs"] == 8

    def test_parse_boolean_values_true(self):
        """Boolean 'true' should parse to Python True."""
        text = """! B3LYP def2-SVP
%geom
  Calc_Hess true
end

* xyz 0 1
  H  0.0 0.0 0.0
*
"""
        result = _parse_orca_text(text)
        assert result["params"]["blocks"]["geom"]["Calc_Hess"] is True

    def test_parse_boolean_values_false(self):
        """Boolean 'false' should parse to Python False."""
        text = """! B3LYP def2-SVP
%tddft
  NRoots 10
  TDA false
end

* xyz 0 1
  H  0.0 0.0 0.0
*
"""
        result = _parse_orca_text(text)
        assert result["params"]["blocks"]["tddft"]["TDA"] is False
        assert result["params"]["blocks"]["tddft"]["NRoots"] == 10

    def test_parse_cpcm_solvation(self):
        """CPCM(solvent) on keyword line should be extracted."""
        text = """! B3LYP def2-SVP CPCM(Water)
* xyz 0 1
  H  0.0 0.0 0.0
*
"""
        result = _parse_orca_text(text)
        assert result["params"]["solvation"] == "Water"
        assert "CPCM(Water)" in result["params"]["keywords"]

    def test_parse_cpcm_block(self):
        """CPCM parameters in %cpcm block."""
        text = """! B3LYP def2-SVP CPCM(Water)
%cpcm
  epsilon 80.4
  refrac 1.33
end

* xyz 0 1
  H  0.0 0.0 0.0
*
"""
        result = _parse_orca_text(text)
        assert result["params"]["blocks"]["cpcm"]["epsilon"] == 80.4
        assert result["params"]["blocks"]["cpcm"]["refrac"] == 1.33

    def test_parse_uks_method_extraction(self):
        """UKS should be extracted as keyword, not method. B3LYP should be method."""
        text = """! UKS B3LYP def2-SVP TIGHTSCF
* xyz 0 1
  H  0.0 0.0 0.0
*
"""
        result = _parse_orca_text(text)
        assert result["params"]["method"] == "B3LYP"
        assert result["params"]["basis"] == "def2-SVP"
        assert "UKS" in result["params"]["keywords"]
        assert "TIGHTSCF" in result["params"]["keywords"]

    def test_parse_casscf_method(self):
        """CASSCF should be recognized as method."""
        text = """! CASSCF def2-TZVP TIGHTSCF
%casscf
  nel 4
  norb 4
  nroots 4
end

* xyz 0 1
  H  0.0 0.0 0.0
*
"""
        result = _parse_orca_text(text)
        assert result["params"]["method"] == "CASSCF"
        assert result["params"]["basis"] == "def2-TZVP"
        assert result["params"]["blocks"]["casscf"]["nel"] == 4
        assert result["params"]["blocks"]["casscf"]["norb"] == 4

    def test_parse_array_syntax_in_block(self):
        """Array syntax like weights[0] = 1,1,1,1 should be preserved."""
        text = """! CASSCF def2-TZVP
%casscf
  nel 4
  norb 4
  nroots 4
  weights[0] = 1,1,1,1
end

* xyz 0 1
  H  0.0 0.0 0.0
*
"""
        result = _parse_orca_text(text)
        assert result["params"]["blocks"]["casscf"]["weights[0]"] == "1,1,1,1"

    def test_parse_tddft_block(self):
        """%tddft block with multiple parameters."""
        text = """! B3LYP def2-TZVP
%tddft
  NRoots 10
  MaxDim 50
  TDA false
end

* xyz 0 1
  C  0.0 0.0 0.0
*
"""
        result = _parse_orca_text(text)
        assert "tddft" in result["params"]["blocks"]
        tddft = result["params"]["blocks"]["tddft"]
        assert tddft["NRoots"] == 10
        assert tddft["MaxDim"] == 50
        assert tddft["TDA"] is False

    def test_parse_geom_block_with_hess(self):
        """%geom block with Calc_Hess and other parameters."""
        text = """! B3LYP def2-SVP OPT
%geom
  MaxIter 100
  Calc_Hess true
  Recalc_Hess 5
end

* xyz 0 1
  O  0.0 0.0 0.0
*
"""
        result = _parse_orca_text(text)
        assert "geom" in result["params"]["blocks"]
        geom = result["params"]["blocks"]["geom"]
        assert geom["MaxIter"] == 100
        assert geom["Calc_Hess"] is True
        assert geom["Recalc_Hess"] == 5

    def test_parse_comment_lines(self):
        """Lines starting with # should be ignored."""
        text = """! B3LYP def2-SVP
# This is a comment
%maxcore 4000
# Another comment

* xyz 0 1
  H  0.0 0.0 0.0
*
"""
        result = _parse_orca_text(text)
        assert result["params"]["maxcore"] == 4000

    def test_parse_multiple_keyword_lines(self):
        """Multiple ! lines should merge keywords."""
        text = """! B3LYP def2-SVP
! OPT TIGHTSCF

* xyz 0 1
  H  0.0 0.0 0.0
*
"""
        result = _parse_orca_text(text)
        assert result["params"]["method"] == "B3LYP"
        assert result["params"]["basis"] == "def2-SVP"
        # All keywords from both lines should be collected
        assert "OPT" in result["params"]["keywords"]
        assert "TIGHTSCF" in result["params"]["keywords"]


class TestORCAEnhancedWriter:
    """Tests for enhanced writer features."""

    def test_write_multiline_pal_block(self):
        """Writer should output multi-line %pal block."""
        fragment = {
            "params": {
                "method": "B3LYP",
                "basis": "def2-SVP",
                "nprocs": 4,
                "charge": 0,
                "multiplicity": 1,
            },
            "structure": {
                "species": ["H"],
                "cart_coords": [[0.0, 0.0, 0.0]],
            },
        }
        text = _write_orca_text(fragment)
        assert "%pal" in text
        assert "nprocs 4" in text
        assert "end" in text

    def test_write_boolean_values(self):
        """Writer should output lowercase true/false for booleans."""
        fragment = {
            "params": {
                "method": "B3LYP",
                "basis": "def2-SVP",
                "charge": 0,
                "multiplicity": 1,
                "blocks": {
                    "geom": {"Calc_Hess": True, "NumHess": False},
                },
            },
            "structure": {
                "species": ["H"],
                "cart_coords": [[0.0, 0.0, 0.0]],
            },
        }
        text = _write_orca_text(fragment)
        assert "Calc_Hess true" in text
        assert "NumHess false" in text

    def test_write_cpcm_solvation(self):
        """Writer should include CPCM(solvent) on keyword line if solvation is set."""
        fragment = {
            "params": {
                "method": "B3LYP",
                "basis": "def2-SVP",
                "solvation": "Water",
                "charge": 0,
                "multiplicity": 1,
            },
            "structure": {
                "species": ["H"],
                "cart_coords": [[0.0, 0.0, 0.0]],
            },
        }
        text = _write_orca_text(fragment)
        assert "CPCM(Water)" in text

    def test_write_uses_cart_coords(self):
        """Writer should use cart_coords directly if present."""
        fragment = {
            "params": {
                "method": "B3LYP",
                "basis": "def2-SVP",
                "charge": 0,
                "multiplicity": 1,
            },
            "structure": {
                "species": ["O", "H", "H"],
                "cart_coords": [
                    [0.0, 0.0, 0.117369],
                    [0.0, 0.757918, -0.469476],
                    [0.0, -0.757918, -0.469476],
                ],
            },
        }
        text = _write_orca_text(fragment)
        result = _parse_orca_text(text)

        # Coords should roundtrip exactly
        for i, (orig, parsed) in enumerate(
            zip(fragment["structure"]["cart_coords"], result["structure"]["cart_coords"])
        ):
            for j in range(3):
                assert abs(orig[j] - parsed[j]) < 1e-6, f"Coord mismatch at atom {i}, dim {j}"


class TestORCAEnhancedRoundtrip:
    """Roundtrip tests with enhanced features."""

    def test_roundtrip_with_blocks(self):
        """Roundtrip with %geom, %scf blocks."""
        fragment = {
            "params": {
                "method": "B3LYP",
                "basis": "def2-SVP",
                "keywords": ["OPT", "TIGHTSCF"],
                "charge": 0,
                "multiplicity": 1,
                "nprocs": 4,
                "maxcore": 4000,
                "blocks": {
                    "geom": {"MaxIter": 100, "Calc_Hess": True},
                    "scf": {"MaxIter": 200},
                },
            },
            "structure": {
                "species": ["O", "H", "H"],
                "cart_coords": [
                    [0.0, 0.0, 0.117],
                    [0.0, 0.758, -0.469],
                    [0.0, -0.758, -0.469],
                ],
            },
        }
        text = _write_orca_text(fragment)
        result = _parse_orca_text(text)

        assert result["params"]["method"] == "B3LYP"
        assert result["params"]["basis"] == "def2-SVP"
        assert result["params"]["nprocs"] == 4
        assert result["params"]["maxcore"] == 4000

        # Blocks should roundtrip
        assert result["params"]["blocks"]["geom"]["MaxIter"] == 100
        assert result["params"]["blocks"]["geom"]["Calc_Hess"] is True
        assert result["params"]["blocks"]["scf"]["MaxIter"] == 200

    def test_roundtrip_with_solvation(self):
        """Roundtrip with CPCM solvation."""
        fragment = {
            "params": {
                "method": "B3LYP",
                "basis": "def2-SVP",
                "solvation": "Ethanol",
                "charge": 0,
                "multiplicity": 1,
                "blocks": {
                    "cpcm": {"epsilon": 24.3},
                },
            },
            "structure": {
                "species": ["H"],
                "cart_coords": [[0.0, 0.0, 0.0]],
            },
        }
        text = _write_orca_text(fragment)
        result = _parse_orca_text(text)

        assert result["params"]["solvation"] == "Ethanol"
        assert "CPCM(Ethanol)" in result["params"]["keywords"]
        assert result["params"]["blocks"]["cpcm"]["epsilon"] == 24.3
