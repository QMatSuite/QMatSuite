"""Tests for MACE script generation and mock execution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qmatsuite.drivers.mace.io.mace_script import (
    write_mace_script_text,
    write_structure_json_text,
)
from qmatsuite.drivers.mace.writer import write_mace_script


class TestMACEScriptGeneration:
    def test_scf_script_text(self):
        script = write_mace_script_text("scf", {"model": "medium", "device": "cpu"})
        assert "mace_mp" in script
        assert "get_potential_energy" in script
        assert "get_forces" in script
        assert "results.json" in script

    def test_relax_script_text(self):
        script = write_mace_script_text("relax", {
            "model": "medium",
            "optimizer": "BFGS",
            "fmax": 0.01,
        })
        assert "BFGS" in script
        assert "opt.run" in script
        assert "trajectory.jsonl" in script
        assert "final_structure.json" in script

    def test_md_script_text(self):
        script = write_mace_script_text("md", {
            "model": "medium",
            "md_ensemble": "NVT",
            "md_temperature": 300.0,
        })
        assert "Langevin" in script
        assert "trajectory.jsonl" in script
        assert "MaxwellBoltzmannDistribution" in script

    def test_md_nve_script(self):
        script = write_mace_script_text("md", {
            "model": "medium",
            "md_ensemble": "NVE",
        })
        assert "VelocityVerlet" in script

    def test_md_npt_script(self):
        script = write_mace_script_text("md", {
            "model": "medium",
            "md_ensemble": "NPT",
        })
        assert "NPT" in script

    def test_custom_model_script(self):
        script = write_mace_script_text("scf", {
            "model_type": "custom",
            "model_paths": "/path/to/model.model",
            "device": "cuda",
        })
        assert "MACECalculator" in script
        assert "model_paths" in script
        assert "mace_mp" not in script

    def test_dispersion_flag(self):
        script = write_mace_script_text("scf", {
            "model": "medium",
            "dispersion": True,
        })
        assert "dispersion=True" in script

    def test_cell_relax_script(self):
        script = write_mace_script_text("relax", {
            "model": "medium",
            "relax_cell": True,
            "cell_filter": "FrechetCellFilter",
        })
        assert "FrechetCellFilter" in script

    def test_unknown_gen_type_raises(self):
        with pytest.raises(ValueError, match="Unknown gen_type"):
            write_mace_script_text("unknown_type", {})


class TestMACEStructureJson:
    def test_write_structure_with_positions(self):
        structure = {
            "species": ["Si", "Si"],
            "positions": [[0.0, 0.0, 0.0], [1.37, 1.37, 1.37]],
            "lattice": [[-2.75, 0.0, 2.75], [0.0, 2.75, 2.75], [-2.75, 2.75, 0.0]],
        }
        text = write_structure_json_text(structure)
        data = json.loads(text)
        assert data["symbols"] == ["Si", "Si"]
        assert len(data["positions"]) == 2
        assert data["pbc"] == [True, True, True]

    def test_write_structure_with_frac_coords(self):
        structure = {
            "species": ["Si", "Si"],
            "lattice": [[5.0, 0.0, 0.0], [0.0, 5.0, 0.0], [0.0, 0.0, 5.0]],
            "frac_coords": [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
        }
        text = write_structure_json_text(structure)
        data = json.loads(text)
        assert data["symbols"] == ["Si", "Si"]
        assert len(data["positions"]) == 2
        # [0.5, 0.5, 0.5] in cubic 5A cell -> [2.5, 2.5, 2.5]
        assert abs(data["positions"][1][0] - 2.5) < 0.01

    def test_write_empty_structure(self):
        text = write_structure_json_text(None)
        assert text.strip() == "{}"


class TestMACEWriterWrapper:
    def test_write_script_to_file(self, tmp_path: Path):
        output = tmp_path / "scf.py"
        result = write_mace_script(
            gen_type="scf",
            params={"model": "medium"},
            output_path=output,
        )
        assert result == output
        assert output.exists()
        content = output.read_text()
        assert "mace_mp" in content
        assert "get_potential_energy" in content
