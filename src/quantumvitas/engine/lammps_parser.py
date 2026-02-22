"""LAMMPS output parsing (log, dump, restart)."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def parse_lammps_log(log_path: Path) -> pd.DataFrame:
    """
    Parse LAMMPS log file for thermo output.
    
    Returns:
        DataFrame with columns matching thermo_style
        Standard columns: step, temp, pe, ke, etotal, press, vol
    
    Strategy:
    1. Find thermo header line (starts with "Step")
    2. Read numeric rows until non-numeric
    3. Handle multiple thermo blocks (minimize + run)
    """
    content = log_path.read_text()
    lines = content.splitlines()
    
    # Find all thermo blocks
    thermo_blocks = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for thermo header
        # Accept "Step" followed by energy/force/pressure columns
        # Common patterns: "Step PE", "Step PotEng", "Step Temp PE", etc.
        if line.startswith("Step") and (
            "Temp" in line or "PE" in line or "PotEng" in line or 
            "Fnorm" in line or "Fmax" in line or "Press" in line
        ):
            # Parse header
            header = line.split()
            
            # Read data rows until blank or non-numeric
            data_rows = []
            i += 1
            while i < len(lines):
                data_line = lines[i].strip()
                if not data_line or data_line.startswith("Loop"):
                    break
                
                # Try to parse as numeric
                parts = data_line.split()
                try:
                    # Check if first column is numeric (step number)
                    float(parts[0])
                    data_rows.append(parts)
                except (ValueError, IndexError):
                    break
                i += 1
            
            if data_rows:
                # Create DataFrame for this block
                df = pd.DataFrame(data_rows, columns=header)
                # Convert numeric columns
                for col in df.columns:
                    try:
                        df[col] = pd.to_numeric(df[col])
                    except (ValueError, TypeError):
                        pass
                thermo_blocks.append(df)
        
        i += 1
    
    if not thermo_blocks:
        # Return empty DataFrame with standard columns
        return pd.DataFrame(columns=["Step", "Temp", "PE", "KE", "TotEng", "Press", "Volume"])
    
    # Concatenate all blocks
    result = pd.concat(thermo_blocks, ignore_index=True)
    
    # Normalize column names (LAMMPS uses various names)
    column_mapping = {
        "Step": "step",
        "Temp": "temperature",
        "PE": "potential_energy",
        "KE": "kinetic_energy",
        "TotEng": "total_energy",
        "Press": "pressure",
        "Volume": "volume",
        "fmax": "force_max",
        "fnorm": "force_norm",
    }
    
    result = result.rename(columns={k: v for k, v in column_mapping.items() if k in result.columns})
    
    return result


def parse_lammps_dump(
    dump_path: Path,
    max_frames: Optional[int] = None,
) -> List[Dict]:
    """
    Parse LAMMPS dump file (custom format).
    
    Expected columns (per constitution): id type x y z vx vy vz fx fy fz
    
    Returns:
        List of frame dictionaries with:
        - frame_index: int
        - timestep: int (from dump)
        - n_atoms: int
        - box_bounds: dict with xlo, xhi, ylo, yhi, zlo, zhi, xy, xz, yz (optional)
        - atoms: List[Dict] with id, type, x, y, z, vx, vy, vz, fx, fy, fz
    
    Notes:
    - Handles both wrapped and unwrapped coordinates
    - Streaming parser for large files (if max_frames set)
    - Sorts atoms by id (per constitution requirement)
    """
    content = dump_path.read_text()
    lines = content.splitlines()
    
    frames = []
    i = 0
    frame_count = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for ITEM: TIMESTEP
        if line.startswith("ITEM: TIMESTEP"):
            i += 1
            if i >= len(lines):
                break
            timestep = int(lines[i].strip())
            
            # Look for ITEM: NUMBER OF ATOMS
            i += 1
            if i >= len(lines) or not lines[i].strip().startswith("ITEM: NUMBER OF ATOMS"):
                continue
            i += 1
            if i >= len(lines):
                break
            n_atoms = int(lines[i].strip())
            
            # Look for ITEM: BOX BOUNDS
            i += 1
            if i >= len(lines) or not lines[i].strip().startswith("ITEM: BOX BOUNDS"):
                continue
            
            box_info = lines[i].strip()
            i += 1
            
            # Parse box bounds
            box_bounds = {}
            if "xy xz yz" in box_info:
                # Triclinic
                xlo, xhi = map(float, lines[i].split())
                i += 1
                ylo, yhi = map(float, lines[i].split())
                i += 1
                zlo, zhi = map(float, lines[i].split())
                i += 1
                xy, xz, yz = map(float, lines[i].split())
                box_bounds = {
                    "xlo": xlo, "xhi": xhi,
                    "ylo": ylo, "yhi": yhi,
                    "zlo": zlo, "zhi": zhi,
                    "xy": xy, "xz": xz, "yz": yz,
                }
            else:
                # Orthogonal
                xlo, xhi = map(float, lines[i].split())
                i += 1
                ylo, yhi = map(float, lines[i].split())
                i += 1
                zlo, zhi = map(float, lines[i].split())
                i += 1
                box_bounds = {
                    "xlo": xlo, "xhi": xhi,
                    "ylo": ylo, "yhi": yhi,
                    "zlo": zlo, "zhi": zhi,
                }
            
            # Look for ITEM: ATOMS
            if i >= len(lines) or not lines[i].strip().startswith("ITEM: ATOMS"):
                continue
            
            atom_header = lines[i].strip()
            i += 1
            
            # Parse atom header to get column order
            # Format: "ITEM: ATOMS id type x y z vx vy vz fx fy fz"
            atom_columns = atom_header.split()[2:]  # Skip "ITEM: ATOMS"
            
            # Read atoms
            atoms = []
            atoms_read = 0
            while i < len(lines) and atoms_read < n_atoms:
                line = lines[i].strip()
                if not line:
                    i += 1
                    continue
                
                parts = line.split()
                if len(parts) < len(atom_columns):
                    break
                
                atom_data = dict(zip(atom_columns, parts))
                # Convert numeric fields
                for key in ["id", "type", "x", "y", "z", "vx", "vy", "vz", "fx", "fy", "fz"]:
                    if key in atom_data:
                        try:
                            atom_data[key] = float(atom_data[key])
                        except (ValueError, TypeError):
                            pass
                
                atoms.append(atom_data)
                atoms_read += 1
                i += 1
            
            # Sort atoms by id (per constitution)
            atoms.sort(key=lambda a: int(a.get("id", 0)))
            
            frames.append({
                "frame_index": frame_count,
                "timestep": timestep,
                "n_atoms": n_atoms,
                "box_bounds": box_bounds,
                "atoms": atoms,
            })
            
            frame_count += 1
            
            if max_frames and frame_count >= max_frames:
                break
        
        i += 1
    
    return frames


def build_trajectory_from_parsed(
    frames: List[Dict],
    thermo_df: Optional[pd.DataFrame] = None,
    units: str = "metal",
) -> Dict:
    """
    Build canonical trajectory object from parsed frames and thermo.
    
    Args:
        frames: List of parsed frame dictionaries
        thermo_df: Optional thermo DataFrame
        units: LAMMPS unit system (metal, real, lj)
    
    Returns:
        Dictionary with trajectory data compatible with canonical Frame model
    """
    from quantumvitas.core.analysis.trajectory.model import Frame
    
    trajectory_frames = []
    
    for frame_data in frames:
        atoms = frame_data["atoms"]
        box_bounds = frame_data["box_bounds"]
        
        # Extract positions
        positions = np.array([
            [a.get("x", 0.0), a.get("y", 0.0), a.get("z", 0.0)]
            for a in atoms
        ])
        
        # Extract velocities (if available)
        velocities = None
        if all("vx" in a for a in atoms):
            velocities = np.array([
                [a.get("vx", 0.0), a.get("vy", 0.0), a.get("vz", 0.0)]
                for a in atoms
            ])
            # Convert units: metal (Å/ps) -> canonical (Å/fs)
            if units == "metal":
                velocities /= 1000.0
        
        # Extract forces (if available)
        forces = None
        if all("fx" in a for a in atoms):
            forces = np.array([
                [a.get("fx", 0.0), a.get("fy", 0.0), a.get("fz", 0.0)]
                for a in atoms
            ])
            # Convert units: real (kcal/mol/Å) -> canonical (eV/Å)
            if units == "real":
                forces *= 0.0433634  # kcal/mol to eV
        
        # Build cell matrix from box bounds
        xlo, xhi = box_bounds["xlo"], box_bounds["xhi"]
        ylo, yhi = box_bounds["ylo"], box_bounds["yhi"]
        zlo, zhi = box_bounds["zlo"], box_bounds["zhi"]
        
        if "xy" in box_bounds:
            # Triclinic
            xy, xz, yz = box_bounds["xy"], box_bounds["xz"], box_bounds["yz"]
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
        
        # Get species from atom types (requires type->element mapping)
        # For now, use placeholder - this should come from structure or data file
        species = [f"Type{a.get('type', 1)}" for a in atoms]
        
        # Get time from timestep
        timestep = frame_data["timestep"]
        # Convert time: metal (ps) -> canonical (fs)
        time = None
        if units == "metal":
            time = timestep * 1000.0  # ps to fs
        elif units == "real":
            time = timestep  # already in fs
        else:
            # lj: don't convert
            time = timestep
        
        # Get thermo data if available
        energy = None
        temperature = None
        pressure = None
        if thermo_df is not None and len(thermo_df) > frame_data["frame_index"]:
            thermo_row = thermo_df.iloc[frame_data["frame_index"]]
            energy = thermo_row.get("potential_energy")
            temperature = thermo_row.get("temperature")
            pressure = thermo_row.get("pressure")
        
        # Create Frame object
        frame = Frame(
            frame_index=frame_data["frame_index"],
            positions=positions,
            species=species,
            cell=cell,
            pbc=(True, True, True),  # Default for periodic
            time=time,
            iteration=timestep,
            velocities=velocities,
            forces=forces,
            energy=energy,
            temperature=temperature,
            pressure=pressure,
        )
        
        trajectory_frames.append(frame)
    
    return {
        "frames": trajectory_frames,
        "meta": {
            "unit_system": units,
            "n_frames": len(trajectory_frames),
        },
    }
