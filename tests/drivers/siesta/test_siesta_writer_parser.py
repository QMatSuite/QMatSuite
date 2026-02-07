"""Regression tests for Siesta legacy writer/parser helpers."""

from __future__ import annotations

from pathlib import Path

from quantumvitas.drivers.siesta.io.fdf import parse_fdf_text
from quantumvitas.drivers.siesta.parser import parse_main_output
from quantumvitas.drivers.siesta.writer import write_fdf


def test_write_fdf_preserves_scaledcartesian_lattice_constant(tmp_path: Path) -> None:
    out = tmp_path / "si_scf.fdf"
    write_fdf(
        output_path=out,
        system_name="Silicon bulk",
        system_label="si_scf",
        species=[{"index": 1, "atomic_number": 14, "label": "Si"}],
        lattice_constant=5.43,
        lattice_vectors=[
            [0.5, 0.5, 0.0],
            [0.0, 0.5, 0.5],
            [0.5, 0.0, 0.5],
        ],
        atoms=[
            {"x": 0.0, "y": 0.0, "z": 0.0, "species_index": 1},
            {"x": 0.25, "y": 0.25, "z": 0.25, "species_index": 1},
        ],
        coord_format="ScaledCartesian",
        params={"MeshCutoff": "200 Ry"},
    )

    text = out.read_text(encoding="utf-8")
    assert "LatticeConstant   5.43 Ang" in text
    assert "AtomicCoordinatesFormat  ScaledCartesian" in text

    parsed = parse_fdf_text(text)
    assert parsed["params"]["AtomicCoordinatesFormat"] == "ScaledCartesian"
    assert parsed["structure"]["frac_coords"][1] == [0.25, 0.25, 0.25]

    lattice = parsed["structure"]["lattice"]
    assert lattice[0] == [2.715, 2.715, 0.0]
    assert lattice[1] == [0.0, 2.715, 2.715]
    assert lattice[2] == [2.715, 0.0, 2.715]


def test_parse_main_output_uses_last_reported_eks(tmp_path: Path) -> None:
    out = tmp_path / "run.out"
    out.write_text(
        "\n".join(
            [
                "reinit: System Label: si_relax",
                "initatomlists: Number of atoms, orbitals, and projectors:  2 26 52",
                "SCF Convergence by DM+H criterion",
                "siesta: E_KS(eV) =               98.6148",
                "siesta: E_KS(eV) =             -229.7864",
                "Job completed",
            ]
        ),
        encoding="utf-8",
    )

    parsed = parse_main_output(out)
    assert parsed["total_energy_eV"] == -229.7864
    assert parsed["normal_exit"] is True
    assert parsed["scf_converged"] is True
