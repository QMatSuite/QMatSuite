"""MACE test fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = TESTS_DIR / "data" / "analysis_mace_trajectory"


@pytest.fixture
def mace_results_dir(tmp_path: Path) -> Path:
    """Create a temp directory with synthetic MACE results."""
    results = {
        "calc_type": "scf",
        "success": True,
        "total_energy_eV": -10.5432,
        "energy_per_atom_eV": -5.2716,
        "forces_eV_per_ang": [
            [0.01, -0.02, 0.003],
            [-0.01, 0.02, -0.003],
        ],
        "max_force_eV_per_ang": 0.023,
        "stress_eV_per_ang3": [0.001, 0.001, 0.001, 0.0, 0.0, 0.0],
        "n_atoms": 2,
        "model_name": "medium",
        "converged": True,
        "wall_time_s": 0.45,
        "final_species": ["Si", "Si"],
        "final_positions": [
            [0.0, 0.0, 0.0],
            [1.3773, 1.3773, 1.3773],
        ],
        "final_cell": [
            [-2.7546, 0.0, 2.7546],
            [0.0, 2.7546, 2.7546],
            [-2.7546, 2.7546, 0.0],
        ],
    }
    (tmp_path / "results.json").write_text(json.dumps(results, indent=2))
    return tmp_path


@pytest.fixture
def mace_relax_dir(tmp_path: Path) -> Path:
    """Create a temp directory with synthetic MACE relax results."""
    results = {
        "calc_type": "relax",
        "success": True,
        "total_energy_eV": -10.5432,
        "energy_per_atom_eV": -5.2716,
        "forces_eV_per_ang": [[0.001, -0.002, 0.0003], [-0.001, 0.002, -0.0003]],
        "max_force_eV_per_ang": 0.0023,
        "converged": True,
        "n_opt_steps": 12,
        "n_atoms": 2,
        "model_name": "medium",
        "wall_time_s": 1.23,
        "final_species": ["Si", "Si"],
        "final_positions": [[0.0, 0.0, 0.0], [1.3773, 1.3773, 1.3773]],
        "final_cell": [[-2.7546, 0.0, 2.7546], [0.0, 2.7546, 2.7546], [-2.7546, 2.7546, 0.0]],
    }
    (tmp_path / "results.json").write_text(json.dumps(results, indent=2))

    # Write trajectory
    frames = [
        {"frame_index": 0, "energy_eV": -10.2, "forces_eV_per_ang": [[0.5, -0.3, 0.1], [-0.5, 0.3, -0.1]], "positions": [[0.0, 0.0, 0.0], [1.4, 1.35, 1.38]], "species": ["Si", "Si"], "cell": [[-2.7546, 0.0, 2.7546], [0.0, 2.7546, 2.7546], [-2.7546, 2.7546, 0.0]]},
        {"frame_index": 1, "energy_eV": -10.35, "forces_eV_per_ang": [[0.2, -0.15, 0.05], [-0.2, 0.15, -0.05]], "positions": [[0.0, 0.0, 0.0], [1.39, 1.37, 1.378]], "species": ["Si", "Si"], "cell": [[-2.7546, 0.0, 2.7546], [0.0, 2.7546, 2.7546], [-2.7546, 2.7546, 0.0]]},
        {"frame_index": 2, "energy_eV": -10.5432, "forces_eV_per_ang": [[0.001, -0.002, 0.0003], [-0.001, 0.002, -0.0003]], "positions": [[0.0, 0.0, 0.0], [1.3773, 1.3773, 1.3773]], "species": ["Si", "Si"], "cell": [[-2.7546, 0.0, 2.7546], [0.0, 2.7546, 2.7546], [-2.7546, 2.7546, 0.0]]},
    ]
    lines = [json.dumps(f) for f in frames]
    (tmp_path / "trajectory.jsonl").write_text("\n".join(lines) + "\n")
    return tmp_path


@pytest.fixture
def mace_md_dir(tmp_path: Path) -> Path:
    """Create a temp directory with synthetic MACE MD results."""
    results = {
        "calc_type": "md",
        "success": True,
        "total_energy_eV": -14.123,
        "energy_per_atom_eV": -4.708,
        "n_md_steps": 100,
        "md_ensemble": "NVT",
        "md_temperature_K": 300.0,
        "md_timestep_fs": 1.0,
        "n_atoms": 3,
        "model_name": "medium",
        "wall_time_s": 3.45,
        "final_species": ["O", "H", "H"],
        "final_positions": [[5.0, 5.0, 5.0], [5.0, 5.96, 5.0], [5.0, 4.67, 5.76]],
        "final_cell": [[10.0, 0.0, 0.0], [0.0, 10.0, 0.0], [0.0, 0.0, 10.0]],
    }
    (tmp_path / "results.json").write_text(json.dumps(results, indent=2))

    frames = [
        {"frame_index": 0, "time_fs": 0.0, "energy_eV": -14.1, "kinetic_energy_eV": 0.038, "temperature_K": 300.0, "forces_eV_per_ang": [[0.1, -0.2, 0.05], [-0.05, 0.1, -0.03], [-0.05, 0.1, -0.02]], "positions": [[5.0, 5.0, 5.0], [5.0, 5.97, 5.0], [5.0, 4.67, 5.76]], "species": ["O", "H", "H"], "cell": [[10.0, 0.0, 0.0], [0.0, 10.0, 0.0], [0.0, 0.0, 10.0]]},
        {"frame_index": 1, "time_fs": 10.0, "energy_eV": -14.12, "kinetic_energy_eV": 0.04, "temperature_K": 310.5, "forces_eV_per_ang": [[0.08, -0.18, 0.04], [-0.04, 0.09, -0.02], [-0.04, 0.09, -0.02]], "positions": [[5.01, 5.0, 5.0], [5.0, 5.96, 5.01], [5.0, 4.68, 5.75]], "species": ["O", "H", "H"], "cell": [[10.0, 0.0, 0.0], [0.0, 10.0, 0.0], [0.0, 0.0, 10.0]]},
    ]
    lines = [json.dumps(f) for f in frames]
    (tmp_path / "trajectory.jsonl").write_text("\n".join(lines) + "\n")
    return tmp_path
