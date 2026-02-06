"""Tests for ORCA input parser and write-parse roundtrip.

ORCA is a keyword-block format with Cartesian geometry. The writer
converts frac_coords → Cartesian; the parser returns Cartesian coordinates.
Roundtrip tests compare Cartesian coordinates with tolerance.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quantumvitas.drivers.orca.inputspec import (
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
        """Parse the curated benzene_opt.inp sample."""
        text = (SAMPLES_DIR / "benzene_opt.inp").read_text()
        result = _parse_orca_text(text)

        assert result["params"]["method"] == "B3LYP"
        assert result["params"]["basis"] == "def2-SVP"
        assert result["params"]["keywords"] == ["Opt"]
        assert result["params"]["maxcore"] == 4000
        assert result["params"]["nprocs"] == 4
        assert result["params"]["charge"] == 0
        assert result["params"]["multiplicity"] == 1

        assert len(result["structure"]["species"]) == 12
        assert result["structure"]["species"].count("C") == 6
        assert result["structure"]["species"].count("H") == 6
        assert len(result["structure"]["cart_coords"]) == 12


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
        original_text = (SAMPLES_DIR / "benzene_opt.inp").read_text()
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
        from quantumvitas.inputformat import write_engine_inputs, parse_engine_inputs

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
