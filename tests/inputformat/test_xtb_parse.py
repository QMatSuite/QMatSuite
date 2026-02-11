"""Tests for xTB input parser/writer and semantic roundtrip."""

from __future__ import annotations

from pathlib import Path

import pytest

from quantumvitas.drivers.xtb.io.xtb_input import (
    parse_xcontrol_text,
    parse_xyz_text,
    write_xcontrol_text,
    write_xyz_text,
)
from quantumvitas.drivers.xtb.inputspec import get_xtb_input_spec
from quantumvitas.inputformat import parse_engine_inputs, write_engine_inputs


SAMPLES_DIR = Path(__file__).parent / "samples" / "xtb"


def _read_xyz(path: Path) -> dict:
    return parse_xyz_text(path.read_text(encoding="utf-8"))


class TestXTBXYZParserWriter:
    def test_parse_xyz_text(self):
        text = """3\nwater\nO 0.0 0.0 0.1\nH 0.0 0.7 -0.4\nH 0.0 -0.7 -0.4\n"""
        parsed = parse_xyz_text(text)
        assert parsed["comment"] == "water"
        assert parsed["species"] == ["O", "H", "H"]
        assert len(parsed["cart_coords"]) == 3

    def test_write_xyz_text(self):
        structure = {
            "comment": "water",
            "species": ["O", "H", "H"],
            "cart_coords": [
                [0.0, 0.0, 0.1],
                [0.0, 0.7, -0.4],
                [0.0, -0.7, -0.4],
            ],
        }
        text = write_xyz_text(structure)
        parsed = parse_xyz_text(text)
        assert parsed["species"] == structure["species"]

    def test_frac_coords_conversion(self):
        structure = {
            "comment": "frac",
            "species": ["H"],
            "frac_coords": [[0.5, 0.0, 0.0]],
            "lattice": [[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 2.0]],
        }
        parsed = parse_xyz_text(write_xyz_text(structure))
        assert abs(parsed["cart_coords"][0][0] - 1.0) < 1e-8


class TestXTBXControlParserWriter:
    def test_write_parse_xcontrol(self):
        params = {
            "xcontrol": {
                "md": {"temp": 300, "time": 0.02, "step": 1.0, "dump": 5.0},
                "opt": {"optlevel": "tight", "maxcycle": 200},
            }
        }
        text = write_xcontrol_text(params)
        parsed = parse_xcontrol_text(text)
        assert "xcontrol" in parsed
        assert parsed["xcontrol"]["md"]["temp"] == 300
        assert parsed["xcontrol"]["opt"]["optlevel"] == "tight"

    def test_parse_empty_xcontrol(self):
        assert parse_xcontrol_text("") == {}


class TestXTBWriterAgainstCuratedInputs:
    @pytest.mark.parametrize(
        "case_dir",
        [
            "water_sp",
            "water_opt",
            "water_freq",
            "ethanol_opt_tight",
            "water_solvation_alpb",
            "o2_triplet_sp",
            "caffeine_grad",
        ],
    )
    def test_yaml_to_inputs_matches_curated_semantics(self, tmp_path, case_dir):
        curated = _read_xyz(SAMPLES_DIR / case_dir / "input.xyz")
        structure = {
            "comment": curated.get("comment", ""),
            "species": curated["species"],
            "cart_coords": curated["cart_coords"],
        }
        spec = get_xtb_input_spec()
        written = write_engine_inputs(spec, tmp_path, structure=structure)
        assert (tmp_path / "input.xyz") in written

        out = _read_xyz(tmp_path / "input.xyz")
        assert out["species"] == curated["species"]
        for a, b in zip(out["cart_coords"], curated["cart_coords"]):
            for x, y in zip(a, b):
                assert abs(x - y) < 1e-8

    def test_xcontrol_writer_matches_curated_md(self, tmp_path):
        spec = get_xtb_input_spec()
        md_params = {
            "xcontrol": {
                "md": {
                    "temp": 300,
                    "time": 0.02,
                    "step": 1.0,
                    "dump": 5.0,
                }
            }
        }
        write_engine_inputs(spec, tmp_path, params=md_params, structure=_read_xyz(SAMPLES_DIR / "water_md" / "input.xyz"))
        assert (tmp_path / "xcontrol.inp").exists()
        generated = parse_xcontrol_text((tmp_path / "xcontrol.inp").read_text(encoding="utf-8"))
        expected = parse_xcontrol_text((SAMPLES_DIR / "water_md" / "xcontrol.inp").read_text(encoding="utf-8"))
        assert generated == expected


class TestXTBOrchestratorRoundtrip:
    def test_parse_write_parse_roundtrip(self, tmp_path):
        spec = get_xtb_input_spec()
        params = {"xcontrol": {"md": {"temp": 300, "time": 0.02}}}
        structure = _read_xyz(SAMPLES_DIR / "water_sp" / "input.xyz")

        write_engine_inputs(spec, tmp_path, params=params, structure=structure)
        parsed1 = parse_engine_inputs(spec, tmp_path)

        out_dir = tmp_path / "rewrite"
        write_engine_inputs(spec, out_dir, params=parsed1.params, structure=parsed1.structure)
        parsed2 = parse_engine_inputs(spec, out_dir)

        assert parsed2.structure is not None
        assert parsed2.structure["species"] == parsed1.structure["species"]
        assert parsed2.params == parsed1.params


_NORMALIZED_DIR = Path(__file__).resolve().parents[2] / ".tmp" / "engine_research" / "xtb" / "normalized"


@pytest.mark.skipif(not _NORMALIZED_DIR.is_dir(), reason="No normalized xTB corpus in .tmp")
class TestXTBNormalizedCorpus:
    def test_parse_available_normalized_xyz_cases(self, tmp_path):
        spec = get_xtb_input_spec()
        xyz_files = sorted(
            p for p in _NORMALIZED_DIR.glob("*/**/*.xyz")
            if "_parse_tmp" not in p.parts
        )
        # Corpus may not include xyz for every normalized case.
        assert xyz_files, "Expected at least one normalized xyz case"

        for xyz_path in xyz_files:
            case_name = xyz_path.parent.name
            workdir = tmp_path / case_name
            workdir.mkdir(parents=True, exist_ok=True)
            (workdir / "input.xyz").write_text(xyz_path.read_text(encoding="utf-8"), encoding="utf-8")
            result = parse_engine_inputs(spec, workdir)
            assert result.structure is not None
            assert len(result.structure.get("species", [])) > 0
