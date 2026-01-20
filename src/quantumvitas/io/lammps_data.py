"""LAMMPS data file I/O operations.

Converts QMatSuite structures (pymatgen) to LAMMPS data file format.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from pymatgen.core import Structure, Molecule

logger = logging.getLogger(__name__)


def write_lammps_data(
    structure: Structure | Molecule,
    path: Path,
    atom_style: str = "atomic",
    step_ulid: Optional[str] = None,
) -> None:
    """
    Write structure in LAMMPS data file format.
    
    Args:
        structure: pymatgen Structure or Molecule
        path: Output file path
        atom_style: LAMMPS atom_style (atomic, charge, full, molecular)
        step_ulid: Optional step ULID for header comment
    
    Raises:
        ValueError: If structure is not periodic (Molecule without PBC info)
        ValueError: If atom_style not supported
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Handle Molecules (non-periodic)
    is_periodic = isinstance(structure, Structure)
    if not is_periodic:
        # For molecules, create a bounding box
        coords = np.array([site.coords for site in structure])
        min_coords = coords.min(axis=0) - 5.0  # 5 Å padding
        max_coords = coords.max(axis=0) + 5.0
        box_bounds = (min_coords, max_coords)
        pbc = (False, False, False)
    else:
        # For periodic structures
        lattice = structure.lattice
        # Get box bounds from lattice
        # LAMMPS expects orthogonal or triclinic box
        # For triclinic, we need to compute lo/hi and tilt factors
        cell = lattice.matrix  # (3, 3) in Å
        
        # Check if triclinic (non-orthogonal)
        is_triclinic = not np.allclose(cell, np.diag(np.diag(cell)))
        
        if is_triclinic:
            # Triclinic box: need to compute lo/hi and tilt
            # LAMMPS uses: xlo xhi, ylo yhi, zlo zhi, xy xz yz
            # where xy, xz, yz are tilt factors
            # For now, use a simplified approach: bounding box
            coords = np.array([site.coords for site in structure])
            # Project to box-aligned coordinates
            inv_cell = np.linalg.inv(cell)
            frac_coords = coords @ inv_cell.T
            
            # Get bounds in fractional coordinates
            frac_min = frac_coords.min(axis=0)
            frac_max = frac_coords.max(axis=0)
            
            # Convert back to Cartesian for lo/hi
            lo = (cell @ frac_min).min(axis=0)
            hi = (cell @ frac_max).max(axis=0)
            
            # Tilt factors: xy = cell[0,1], xz = cell[0,2], yz = cell[1,2]
            xy = cell[0, 1]
            xz = cell[0, 2]
            yz = cell[1, 2]
            tilt = (xy, xz, yz)
        else:
            # Orthogonal box
            lo = np.array([0.0, 0.0, 0.0])
            hi = np.diag(cell)
            tilt = None
        
        box_bounds = (lo, hi)
        pbc = structure.pbc if hasattr(structure, 'pbc') else (True, True, True)
    
    # Get unique elements and assign types
    unique_elements = []
    element_to_type = {}
    type_to_element = {}
    type_to_mass = {}
    
    for site in structure:
        element = str(site.specie)
        if element not in element_to_type:
            type_id = len(unique_elements) + 1
            element_to_type[element] = type_id
            type_to_element[type_id] = element
            unique_elements.append(element)
            # Get atomic mass (in amu, LAMMPS uses g/mol which is same)
            from pymatgen.core import Element
            mass = Element(element).atomic_mass
            type_to_mass[type_id] = mass
    
    n_atoms = len(structure)
    n_types = len(unique_elements)
    
    # Write file
    lines = []
    
    # Header
    if step_ulid:
        lines.append(f"# LAMMPS data file written by QMatSuite")
        lines.append(f"# Step ULID: {step_ulid}")
    else:
        lines.append(f"# LAMMPS data file written by QMatSuite")
    lines.append("")
    
    # Atom and type counts
    lines.append(f"{n_atoms} atoms")
    lines.append(f"{n_types} atom types")
    lines.append("")
    
    # Box bounds
    lo, hi = box_bounds
    lines.append(f"{lo[0]:.8f} {hi[0]:.8f} xlo xhi")
    lines.append(f"{lo[1]:.8f} {hi[1]:.8f} ylo yhi")
    lines.append(f"{lo[2]:.8f} {hi[2]:.8f} zlo zhi")
    
    # Tilt factors (if triclinic)
    if is_periodic and tilt is not None:
        xy, xz, yz = tilt
        lines.append(f"{xy:.8f} {xz:.8f} {yz:.8f} xy xz yz")
    
    lines.append("")
    
    # Masses section
    lines.append("Masses")
    lines.append("")
    for type_id in sorted(type_to_mass.keys()):
        mass = type_to_mass[type_id]
        lines.append(f"{type_id} {mass:.6f}")
    lines.append("")
    
    # Atoms section
    lines.append(f"Atoms  # {atom_style}")
    lines.append("")
    
    # Write atoms
    for i, site in enumerate(structure, start=1):
        element = str(site.specie)
        atom_type = element_to_type[element]
        coords = site.coords
        
        # Format depends on atom_style
        if atom_style == "atomic":
            # id type x y z
            lines.append(f"{i} {atom_type} {coords[0]:.8f} {coords[1]:.8f} {coords[2]:.8f}")
        elif atom_style == "charge":
            # id type q x y z
            charge = getattr(site, 'charge', 0.0)
            lines.append(f"{i} {atom_type} {charge:.6f} {coords[0]:.8f} {coords[1]:.8f} {coords[2]:.8f}")
        elif atom_style in ("full", "molecular"):
            # id molecule-id type q x y z (and optionally bonds/angles)
            molecule_id = getattr(site, 'molecule_id', 0)
            charge = getattr(site, 'charge', 0.0) if atom_style == "full" else 0.0
            lines.append(f"{i} {molecule_id} {atom_type} {charge:.6f} {coords[0]:.8f} {coords[1]:.8f} {coords[2]:.8f}")
        else:
            raise ValueError(f"Unsupported atom_style: {atom_style}")
    
    # Write to file
    path.write_text("\n".join(lines))
    logger.debug(f"Wrote LAMMPS data file: {path} ({n_atoms} atoms, {n_types} types)")


def read_lammps_data(data_path: Path) -> Structure:
    """
    Parse LAMMPS data file to pymatgen Structure.
    
    Args:
        data_path: Path to LAMMPS data file
    
    Returns:
        pymatgen Structure object
    
    Raises:
        ValueError: If file format is invalid
    """
    content = data_path.read_text()
    lines = content.splitlines()
    
    # Parse header
    n_atoms = None
    n_types = None
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith("#"):
            i += 1
            continue
        
        if "atoms" in line:
            n_atoms = int(line.split()[0])
        elif "atom types" in line:
            n_types = int(line.split()[0])
        elif "xlo xhi" in line:
            break
        i += 1
    
    if n_atoms is None or n_types is None:
        raise ValueError("Invalid LAMMPS data file: missing atom/type counts")
    
    # Parse box bounds
    xlo, xhi = None, None
    ylo, yhi = None, None
    zlo, zhi = None, None
    xy, xz, yz = 0.0, 0.0, 0.0
    is_triclinic = False
    
    while i < len(lines):
        line = lines[i].strip()
        if "xlo xhi" in line:
            parts = line.split()
            xlo, xhi = float(parts[0]), float(parts[1])
        elif "ylo yhi" in line:
            parts = line.split()
            ylo, yhi = float(parts[0]), float(parts[1])
        elif "zlo zhi" in line:
            parts = line.split()
            zlo, zhi = float(parts[0]), float(parts[1])
        elif "xy xz yz" in line:
            parts = line.split()
            xy, xz, yz = float(parts[0]), float(parts[1]), float(parts[2])
            is_triclinic = True
        elif line.startswith("Masses"):
            break
        i += 1
    
    # Build cell matrix
    if is_triclinic:
        # Triclinic: cell = [[xhi-xlo, xy, xz], [0, yhi-ylo, yz], [0, 0, zhi-zlo]]
        cell = np.array([
            [xhi - xlo, xy, xz],
            [0.0, yhi - ylo, yz],
            [0.0, 0.0, zhi - zlo],
        ])
    else:
        # Orthogonal
        cell = np.array([
            [xhi - xlo, 0.0, 0.0],
            [0.0, yhi - ylo, 0.0],
            [0.0, 0.0, zhi - zlo],
        ])
    
    # Parse masses (type -> element mapping)
    type_to_element = {}
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("Masses"):
            i += 1
            continue
        if line.startswith("Atoms"):
            break
        if line and not line.startswith("#"):
            parts = line.split()
            if len(parts) >= 2:
                type_id = int(parts[0])
                mass = float(parts[1])
                # Map mass to element (approximate)
                from pymatgen.core import Element
                # Find closest element by mass
                closest_element = min(
                    Element,
                    key=lambda e: abs(e.atomic_mass - mass)
                )
                type_to_element[type_id] = str(closest_element)
        i += 1
    
    # Parse atoms
    positions = []
    species = []
    
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("Atoms"):
            i += 1
            continue
        if not line or line.startswith("#"):
            i += 1
            continue
        
        parts = line.split()
        if len(parts) >= 4:
            atom_id = int(parts[0])
            atom_type = int(parts[1])
            x, y, z = float(parts[-3]), float(parts[-2]), float(parts[-1])
            
            element = type_to_element.get(atom_type, "X")
            species.append(element)
            positions.append([x, y, z])
        
        i += 1
    
    if len(positions) != n_atoms:
        raise ValueError(f"Mismatch: expected {n_atoms} atoms, found {len(positions)}")
    
    # Create structure
    from pymatgen.core import Lattice
    lattice = Lattice(cell)
    structure = Structure(
        lattice=lattice,
        species=species,
        coords=positions,
        coords_are_cartesian=True,
    )
    
    return structure

