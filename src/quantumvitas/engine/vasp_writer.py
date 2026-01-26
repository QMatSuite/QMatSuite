"""VASP input file writers: POSCAR, INCAR, KPOINTS, POTCAR."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List, Optional
from pymatgen.core import Structure

from quantumvitas.io.structure_io import write_structure
from quantumvitas.core.engines.vasp_resolver import get_potcar_dir


def write_poscar(structure: Structure, path: Path) -> None:
    """
    Write POSCAR file from pymatgen Structure.
    
    Args:
        structure: pymatgen Structure
        path: Path to POSCAR file
    """
    write_structure(structure, path, format="poscar")


def write_incar(params: Dict[str, Any], path: Path) -> None:
    """
    Write INCAR file from parameters dictionary.
    
    Args:
        params: Dictionary of INCAR parameters (e.g., {"ENCUT": 300, "ISMEAR": 0})
        path: Path to INCAR file
    """
    lines = []
    
    # System name (optional)
    if "SYSTEM" in params:
        lines.append(f"SYSTEM = {params['SYSTEM']}")
        lines.append("")
    
    # Write parameters (sorted for reproducibility)
    for key, value in sorted(params.items()):
        if key == "SYSTEM":
            continue  # Already handled
        
        # Format value
        if isinstance(value, bool):
            value_str = ".TRUE." if value else ".FALSE."
        elif isinstance(value, (int, float)):
            value_str = str(value)
        elif isinstance(value, str):
            value_str = value
        else:
            value_str = str(value)
        
        lines.append(f"{key} = {value_str}")
    
    path.write_text("\n".join(lines) + "\n")


def write_kpoints(
    kpoints_data: Dict[str, Any],
    path: Path,
) -> None:
    """
    Write KPOINTS file.
    
    Supports two modes:
    1. Automatic mesh: {"mode": "automatic", "mesh": [4, 4, 4], "shift": [0, 0, 0]}
    2. Line mode: {"mode": "line", "path": [[k1, k2], [k2, k3], ...], "npoints": 40}
    
    Args:
        kpoints_data: Dictionary with k-points configuration
        path: Path to KPOINTS file
    """
    mode = kpoints_data.get("mode", "automatic")
    
    if mode == "automatic":
        mesh = kpoints_data.get("mesh", [4, 4, 4])
        shift = kpoints_data.get("shift", [0, 0, 0])
        
        lines = [
            "Automatic",
            "0",
            "Gamma",
            f"{mesh[0]} {mesh[1]} {mesh[2]}",
            f"{shift[0]} {shift[1]} {shift[2]}",
        ]
    elif mode == "line":
        path_list = kpoints_data.get("path", [])
        npoints = kpoints_data.get("npoints", 40)
        
        lines = [
            "k-points along high symmetry path",
            str(npoints),
            "Line-mode",
            "Reciprocal",
        ]
        
        for k1, k2 in path_list:
            lines.append(f"{k1[0]:.6f} {k1[1]:.6f} {k1[2]:.6f}   ! {kpoints_data.get('labels', {}).get(str(k1), '')}")
            lines.append(f"{k2[0]:.6f} {k2[1]:.6f} {k2[2]:.6f}   ! {kpoints_data.get('labels', {}).get(str(k2), '')}")
            lines.append("")
    else:
        raise ValueError(f"Unknown KPOINTS mode: {mode}")
    
    path.write_text("\n".join(lines) + "\n")


def write_potcar(
    structure: Structure,
    species_map: Dict[str, Dict[str, Any]],
    path: Path,
    potcar_type: str = "PBE",
) -> None:
    """
    Assemble POTCAR file from POTCAR fragments.
    
    Concatenates POTCAR files for each element in the order they appear in POSCAR.
    
    Args:
        structure: pymatgen Structure
        species_map: Dictionary mapping element symbols to species config
                     (e.g., {"Si": {"pseudo": "Si"}})
        path: Path to POTCAR file
        potcar_type: POTCAR type ("PBE" or "LDA")
    """
    potcar_dir = get_potcar_dir(potcar_type)
    
    # Get unique species in POSCAR order
    species_order = []
    seen = set()
    for site in structure:
        symbol = site.specie.symbol
        if symbol not in seen:
            species_order.append(symbol)
            seen.add(symbol)
    
    # Assemble POTCAR
    potcar_parts = []
    for symbol in species_order:
        # Get pseudo name from species_map
        pseudo_name = symbol  # Default to element symbol
        if symbol in species_map:
            species_config = species_map[symbol]
            pseudo_name = species_config.get("pseudo", symbol)
        
        # Find POTCAR file
        potcar_file = potcar_dir / pseudo_name / "POTCAR"
        if not potcar_file.exists():
            raise FileNotFoundError(
                f"POTCAR not found for {symbol} (pseudo: {pseudo_name}) "
                f"at {potcar_file}"
            )
        
        potcar_parts.append(potcar_file.read_bytes())
    
    # Concatenate and write
    path.write_bytes(b"".join(potcar_parts))






