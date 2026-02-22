"""
Siesta FDF input writer — utility script for engine exploration.

Generates Siesta FDF input files from structured parameters.
This is a temporary exploration tool. It will be adapted into
src/qmatsuite/drivers/siesta/writer.py during the integration phase.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def write_fdf(
    output_path: Path,
    system_name: str,
    system_label: str,
    species: list[dict[str, Any]],
    lattice_constant: float,
    lattice_vectors: list[list[float]],
    atoms: list[dict[str, Any]],
    coord_format: str = "Ang",
    params: dict[str, Any] | None = None,
) -> str:
    """Write a Siesta FDF input file.

    Args:
        output_path: Path to write the FDF file
        system_name: Human-readable system name
        system_label: Short label for file naming (Siesta uses this for all output files)
        species: List of dicts with keys: index, atomic_number, label
        lattice_constant: Lattice constant in Angstrom
        lattice_vectors: 3x3 lattice vectors (scaled by lattice_constant)
        atoms: List of dicts with keys: x, y, z, species_index
        coord_format: Coordinate format (Ang, Bohr, ScaledCartesian, Fractional)
        params: Additional FDF parameters as key-value dict

    Returns:
        The FDF file content as a string
    """
    if params is None:
        params = {}

    lines = []

    # System identification
    lines.append(f"SystemName        {system_name}")
    lines.append(f"SystemLabel       {system_label}")
    lines.append("")

    # Species
    lines.append(f"NumberOfAtoms     {len(atoms)}")
    lines.append(f"NumberOfSpecies   {len(species)}")
    lines.append("")
    lines.append("%block ChemicalSpeciesLabel")
    for sp in species:
        lines.append(f" {sp['index']}  {sp['atomic_number']}  {sp['label']}")
    lines.append("%endblock ChemicalSpeciesLabel")
    lines.append("")

    # Basis set
    basis_size = params.pop("PAO.BasisSize", "DZP")
    energy_shift = params.pop("PAO.EnergyShift", "100 meV")
    lines.append(f"PAO.BasisSize     {basis_size}")
    lines.append(f"PAO.EnergyShift   {energy_shift}")
    lines.append("")

    # Lattice
    lines.append(f"LatticeConstant   {lattice_constant} Ang")
    lines.append("%block LatticeVectors")
    for v in lattice_vectors:
        lines.append(f"  {v[0]:.6f}  {v[1]:.6f}  {v[2]:.6f}")
    lines.append("%endblock LatticeVectors")
    lines.append("")

    # Atomic coordinates
    lines.append(f"AtomicCoordinatesFormat  {coord_format}")
    lines.append("%block AtomicCoordinatesAndAtomicSpecies")
    for atom in atoms:
        lines.append(
            f"  {atom['x']:.6f}  {atom['y']:.6f}  {atom['z']:.6f}  {atom['species_index']}"
        )
    lines.append("%endblock AtomicCoordinatesAndAtomicSpecies")
    lines.append("")

    # K-points (if provided)
    kgrid = params.pop("kgrid", None)
    if kgrid:
        lines.append("%block kgrid_Monkhorst_Pack")
        for row in kgrid:
            if len(row) == 4:
                lines.append(f"  {row[0]}  {row[1]}  {row[2]}  {row[3]}")
            else:
                lines.append(f"  {row[0]}  {row[1]}  {row[2]}  0.0")
        lines.append("%endblock kgrid_Monkhorst_Pack")
        lines.append("")

    # SCF parameters
    mesh_cutoff = params.pop("MeshCutoff", "200.0 Ry")
    max_scf = params.pop("MaxSCFIterations", 100)
    mixing_weight = params.pop("DM.MixingWeight", 0.3)
    dm_tolerance = params.pop("DM.Tolerance", "1.d-4")
    solution_method = params.pop("SolutionMethod", "diagon")
    xc_functional = params.pop("XC.functional", "GGA")
    xc_authors = params.pop("XC.authors", "PBE")

    lines.append(f"MeshCutoff        {mesh_cutoff}")
    lines.append(f"MaxSCFIterations  {max_scf}")
    lines.append(f"DM.MixingWeight   {mixing_weight}")
    lines.append(f"DM.Tolerance      {dm_tolerance}")
    lines.append(f"SolutionMethod    {solution_method}")
    lines.append(f"XC.functional     {xc_functional}")
    lines.append(f"XC.authors        {xc_authors}")
    lines.append("")

    # Output controls
    write_forces = params.pop("WriteForces", True)
    write_coor_xmol = params.pop("WriteCoorXmol", True)
    if write_forces:
        lines.append("WriteForces       T")
    if write_coor_xmol:
        lines.append("WriteCoorXmol     T")

    # Relaxation parameters (if any)
    md_type = params.pop("MD.TypeOfRun", None)
    if md_type:
        lines.append("")
        lines.append(f"MD.TypeOfRun      {md_type}")
        md_steps = params.pop("MD.NumCGsteps", None) or params.pop("MD.Steps", None)
        if md_steps:
            if md_type == "CG":
                lines.append(f"MD.NumCGsteps     {md_steps}")
            else:
                lines.append(f"MD.Steps          {md_steps}")
        force_tol = params.pop("MD.MaxForceTol", None)
        if force_tol:
            lines.append(f"MD.MaxForceTol    {force_tol}")
        variable_cell = params.pop("MD.VariableCell", None)
        if variable_cell:
            lines.append(f"MD.VariableCell   {'T' if variable_cell else 'F'}")
        stress_tol = params.pop("MD.MaxStressTol", None)
        if stress_tol:
            lines.append(f"MD.MaxStressTol   {stress_tol}")
        # MD-specific output
        if md_type in ("Verlet", "Nose", "NoseParrinelloRahman", "Anneal"):
            lines.append("WriteMDXmol       T")
            lines.append("WriteMDhistory    T")
        elif md_type == "CG":
            lines.append("WriteMDXmol       T")
            lines.append("WriteMDhistory    T")

    # DM restart
    use_dm = params.pop("DM.UseSaveDM", None)
    if use_dm is not None:
        lines.append(f"DM.UseSaveDM      {'T' if use_dm else 'F'}")

    # PDOS block
    pdos = params.pop("ProjectedDensityOfStates", None)
    if pdos:
        lines.append("")
        lines.append("%block ProjectedDensityOfStates")
        lines.append(f"  {pdos['emin']}  {pdos['emax']}  {pdos['sigma']}  {pdos['npoints']}  eV")
        lines.append("%endblock ProjectedDensityOfStates")

    # Band lines
    band_lines = params.pop("BandLines", None)
    if band_lines:
        lines.append("")
        scale = params.pop("BandLinesScale", "pi/a")
        lines.append(f"BandLinesScale    {scale}")
        lines.append("%block BandLines")
        for bl in band_lines:
            lines.append(f"{bl['npoints']:3d}  {bl['kx']:.3f}  {bl['ky']:.3f}  {bl['kz']:.3f}  {bl['label']}")
        lines.append("%endblock BandLines")

    # Any remaining params
    if params:
        lines.append("")
        for key, value in params.items():
            if isinstance(value, bool):
                lines.append(f"{key}  {'T' if value else 'F'}")
            else:
                lines.append(f"{key}  {value}")

    lines.append("")
    content = "\n".join(lines)

    output_path.write_text(content)
    return content


# ─────────────────────────────────────────────────────────────────────
# Self-test: generate and verify input files
# ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import tempfile

    # Test 1: Water molecule SCF
    print("Test 1: H2O SCF input")
    with tempfile.NamedTemporaryFile(suffix=".fdf", mode="w", delete=False) as f:
        content = write_fdf(
            output_path=Path(f.name),
            system_name="Water molecule",
            system_label="h2o",
            species=[
                {"index": 1, "atomic_number": 8, "label": "O"},
                {"index": 2, "atomic_number": 1, "label": "H"},
            ],
            lattice_constant=10.0,
            lattice_vectors=[
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ],
            atoms=[
                {"x": 0.0, "y": 0.0, "z": 0.0, "species_index": 1},
                {"x": 0.757, "y": 0.586, "z": 0.0, "species_index": 2},
                {"x": -0.757, "y": 0.586, "z": 0.0, "species_index": 2},
            ],
            params={
                "PAO.BasisSize": "SZ",
                "MeshCutoff": "100.0 Ry",
            },
        )
        assert "SystemLabel       h2o" in content
        assert "NumberOfAtoms     3" in content
        assert "PAO.BasisSize     SZ" in content
        print(f"  Written to {f.name}")
        print("  PASS")

    # Test 2: Silicon bulk with k-points, bands, and relaxation
    print("\nTest 2: Si relax input")
    with tempfile.NamedTemporaryFile(suffix=".fdf", mode="w", delete=False) as f:
        content = write_fdf(
            output_path=Path(f.name),
            system_name="Silicon bulk relaxation",
            system_label="si_relax",
            species=[
                {"index": 1, "atomic_number": 14, "label": "Si"},
            ],
            lattice_constant=5.50,
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
            params={
                "kgrid": [
                    [4, 0, 0, 0.5],
                    [0, 4, 0, 0.5],
                    [0, 0, 4, 0.5],
                ],
                "MD.TypeOfRun": "CG",
                "MD.NumCGsteps": 30,
                "MD.MaxForceTol": "0.02 eV/Ang",
                "MD.VariableCell": True,
                "MD.MaxStressTol": "0.5 GPa",
            },
        )
        assert "MD.TypeOfRun      CG" in content
        assert "MD.NumCGsteps     30" in content
        assert "MD.VariableCell   T" in content
        assert "kgrid_Monkhorst_Pack" in content
        print(f"  Written to {f.name}")
        print("  PASS")

    print("\nAll input writer tests passed.")
