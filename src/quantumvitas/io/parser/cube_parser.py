"""Shared parsers for Gaussian cube (.cube) and XSF (.xsf) volumetric files.

These parsers are engine-agnostic (stdlib + numpy only, no kernel imports).
Used by QE, CP2K, ABINIT, Siesta, Gaussian, ORCA, GPAW, Psi4, PySCF, W90.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

BOHR_TO_ANGSTROM = 0.529177249


def parse_cube_file(path: Path) -> dict:
    """Parse a Gaussian cube file.

    Returns dict with:
    - comment: str (2-line comment header)
    - lattice: ndarray (3, 3) in Angstrom (converted from Bohr)
    - species: list[str] (element symbols)
    - positions_cart: ndarray (N, 3) in Angstrom (converted from Bohr)
    - grid_shape: tuple (N1, N2, N3)
    - grid_data: ndarray (N1*N2*N3,) float64
    - grid_vectors: ndarray (3, 3) in Angstrom (step vectors per grid point)
    - origin: ndarray (3,) in Angstrom
    - data_order: "c_z_fastest"
    - n_mo: int (0 for density cube, >0 for MO cube)
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    if len(lines) < 7:
        raise ValueError(f"Cube file too short: {path}")

    # Lines 0-1: comment
    comment = lines[0].strip() + "\n" + lines[1].strip()

    # Line 2: N_atoms origin_x origin_y origin_z [nval]
    parts2 = lines[2].split()
    n_atoms_signed = int(parts2[0])
    n_mo = 0
    if n_atoms_signed < 0:
        n_atoms = abs(n_atoms_signed)
        n_mo = 1  # MO cube, will read extra line
    else:
        n_atoms = n_atoms_signed

    origin = np.array([float(parts2[1]), float(parts2[2]), float(parts2[3])],
                      dtype=np.float64) * BOHR_TO_ANGSTROM

    # Lines 3-5: grid dimensions + step vectors
    grid_shape_list = []
    grid_vectors = np.zeros((3, 3), dtype=np.float64)
    for i in range(3):
        parts = lines[3 + i].split()
        n_pts = int(parts[0])
        grid_shape_list.append(n_pts)
        grid_vectors[i] = [float(parts[1]), float(parts[2]), float(parts[3])]
    grid_vectors *= BOHR_TO_ANGSTROM
    grid_shape = tuple(grid_shape_list)

    # Reconstruct lattice from grid_vectors * grid_counts
    lattice = np.array([
        grid_vectors[0] * grid_shape[0],
        grid_vectors[1] * grid_shape[1],
        grid_vectors[2] * grid_shape[2],
    ], dtype=np.float64)

    # Lines 6 to 6+N_atoms-1: atomic positions
    # Format: atomic_number charge x y z (all in Bohr)
    _Z_TO_SYMBOL = {
        1: "H", 2: "He", 3: "Li", 4: "Be", 5: "B", 6: "C", 7: "N", 8: "O",
        9: "F", 10: "Ne", 11: "Na", 12: "Mg", 13: "Al", 14: "Si", 15: "P",
        16: "S", 17: "Cl", 18: "Ar", 19: "K", 20: "Ca", 21: "Sc", 22: "Ti",
        23: "V", 24: "Cr", 25: "Mn", 26: "Fe", 27: "Co", 28: "Ni", 29: "Cu",
        30: "Zn", 31: "Ga", 32: "Ge", 33: "As", 34: "Se", 35: "Br", 36: "Kr",
        37: "Rb", 38: "Sr", 39: "Y", 40: "Zr", 41: "Nb", 42: "Mo", 43: "Tc",
        44: "Ru", 45: "Rh", 46: "Pd", 47: "Ag", 48: "Cd", 49: "In", 50: "Sn",
        51: "Sb", 52: "Te", 53: "I", 54: "Xe", 55: "Cs", 56: "Ba",
        57: "La", 58: "Ce", 59: "Pr", 60: "Nd", 72: "Hf", 73: "Ta",
        74: "W", 75: "Re", 76: "Os", 77: "Ir", 78: "Pt", 79: "Au", 80: "Hg",
        81: "Tl", 82: "Pb", 83: "Bi",
    }

    species = []
    positions_cart = np.zeros((n_atoms, 3), dtype=np.float64)
    for i in range(n_atoms):
        parts = lines[6 + i].split()
        z = int(parts[0])
        species.append(_Z_TO_SYMBOL.get(z, f"X{z}"))
        positions_cart[i] = [float(parts[2]), float(parts[3]), float(parts[4])]
    positions_cart *= BOHR_TO_ANGSTROM

    # Data starts after atoms (and optional MO info line)
    data_start = 6 + n_atoms
    if n_mo > 0:
        # MO cube: extra line with number of MOs and their indices
        mo_parts = lines[data_start].split()
        n_mo = int(mo_parts[0])
        data_start += 1

    # Read grid data
    n1, n2, n3 = grid_shape
    n_total = n1 * n2 * n3 * max(1, n_mo) if n_mo > 0 else n1 * n2 * n3

    values = []
    for line_idx in range(data_start, len(lines)):
        line = lines[line_idx].strip()
        if not line:
            continue
        for token in line.split():
            try:
                values.append(float(token))
            except ValueError:
                break
        if len(values) >= n_total:
            break

    if len(values) < n1 * n2 * n3:
        raise ValueError(
            f"Expected at least {n1 * n2 * n3} grid values, got {len(values)} in {path}"
        )

    # For MO cubes, only keep first MO's data
    grid_data = np.array(values[:n1 * n2 * n3], dtype=np.float64)

    return {
        "comment": comment,
        "lattice": lattice,
        "species": species,
        "positions_cart": positions_cart,
        "grid_shape": (n1, n2, n3),
        "grid_data": grid_data,
        "grid_vectors": grid_vectors,
        "origin": origin,
        "data_order": "c_z_fastest",
        "n_mo": n_mo,
    }


def parse_xsf_field3d(path: Path) -> dict:
    """Parse XSF DATAGRID_3D block into field3d dict.

    Supports Wannier90 and QE pp.x output formats.

    Returns dict with:
    - lattice: ndarray (3, 3) in Angstrom (from PRIMVEC)
    - species: list[str] (from PRIMCOORD, may be empty)
    - positions_cart: ndarray (N, 3) in Angstrom
    - grid_shape: tuple (nx, ny, nz)
    - grid_data: ndarray (nx*ny*nz,) float64
    - grid_vectors: ndarray (3, 3) in Angstrom (full cell vectors from DATAGRID)
    - origin: ndarray (3,) in Angstrom
    - data_order: "fortran_i_fastest"
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    # Parse PRIMVEC (lattice)
    lattice = _parse_xsf_primvec(lines)

    # Parse PRIMCOORD (atoms)
    species, positions_cart = _parse_xsf_primcoord(lines)

    # Find DATAGRID_3D block
    dg_start = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "BEGIN_DATAGRID_3D" in stripped and "BEGIN_BLOCK" not in stripped:
            dg_start = i
            break

    if dg_start is None:
        raise ValueError("No BEGIN_DATAGRID_3D found in XSF file")

    # Next line: grid dimensions (nx ny nz)
    idx = dg_start + 1
    dim_line = lines[idx].strip()
    dim_parts = dim_line.split()
    nx, ny, nz = int(dim_parts[0]), int(dim_parts[1]), int(dim_parts[2])

    # Origin line
    idx += 1
    origin_parts = lines[idx].split()
    origin = np.array([float(origin_parts[0]), float(origin_parts[1]),
                       float(origin_parts[2])], dtype=np.float64)

    # 3 grid vectors (spanning vectors, NOT step vectors)
    grid_vectors = np.zeros((3, 3), dtype=np.float64)
    for i in range(3):
        idx += 1
        parts = lines[idx].split()
        grid_vectors[i] = [float(parts[0]), float(parts[1]), float(parts[2])]

    # Data starts after grid vectors
    data_start = idx + 1

    # Find END marker
    end_idx = None
    for i in range(data_start, len(lines)):
        if "END_DATAGRID_3D" in lines[i]:
            end_idx = i
            break

    if end_idx is None:
        raise ValueError("No END_DATAGRID_3D found in XSF file")

    # Read data values
    n_total = nx * ny * nz
    values = []
    for i in range(data_start, end_idx):
        line = lines[i].strip()
        if not line:
            continue
        for token in line.split():
            try:
                values.append(float(token))
            except ValueError:
                continue
        if len(values) >= n_total:
            break

    if len(values) < n_total:
        raise ValueError(
            f"Expected {n_total} grid values, got {len(values)} in {path}"
        )

    grid_data = np.array(values[:n_total], dtype=np.float64)

    # If no PRIMVEC found, use grid_vectors as lattice
    if lattice is None:
        lattice = grid_vectors.copy()

    return {
        "lattice": lattice,
        "species": species,
        "positions_cart": positions_cart,
        "grid_shape": (nx, ny, nz),
        "grid_data": grid_data,
        "grid_vectors": grid_vectors,
        "origin": origin,
        "data_order": "fortran_i_fastest",
    }


def _parse_xsf_primvec(lines: list[str]) -> np.ndarray | None:
    """Extract PRIMVEC lattice from XSF lines."""
    for i, line in enumerate(lines):
        if "PRIMVEC" in line:
            lattice = np.zeros((3, 3), dtype=np.float64)
            for j in range(3):
                parts = lines[i + 1 + j].split()
                lattice[j] = [float(parts[0]), float(parts[1]), float(parts[2])]
            return lattice
    return None


def _parse_xsf_primcoord(lines: list[str]) -> tuple[list[str], np.ndarray]:
    """Extract PRIMCOORD atoms from XSF lines."""
    species = []
    positions = []
    for i, line in enumerate(lines):
        if "PRIMCOORD" in line:
            # Next line: n_atoms n_dummy
            count_parts = lines[i + 1].split()
            n_atoms = int(count_parts[0])
            for j in range(n_atoms):
                parts = lines[i + 2 + j].split()
                elem = parts[0]
                # Element could be atomic number or symbol
                try:
                    z = int(elem)
                    _Z = {6: "C", 14: "Si", 8: "O", 1: "H", 7: "N", 26: "Fe"}
                    elem = _Z.get(z, f"X{z}")
                except ValueError:
                    pass
                species.append(elem)
                positions.append([float(parts[1]), float(parts[2]), float(parts[3])])
            break

    if not positions:
        return [], np.zeros((0, 3), dtype=np.float64)
    return species, np.array(positions, dtype=np.float64)
