"""
Wannier90 input file (.win) parser and generator.

This module handles reading and writing Wannier90 .win input files
and pw2wannier90 .pw2wan input files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import re


@dataclass
class Wannier90Input:
    """
    Represents a Wannier90 .win input file.
    
    Supports the minimal parameter set needed for MVP:
    - num_wann, num_bands, num_iter
    - unit_cell_cart, atoms_frac/atoms_cart
    - mp_grid, kpoints
    - projections block
    - Extra raw lines for advanced parameters
    """
    
    # Core parameters
    seedname: str = "wannier"
    num_wann: Optional[int] = None
    num_bands: Optional[int] = None
    num_iter: int = 20
    
    # Unit cell (list of 3 vectors, each a list of 3 floats)
    unit_cell_cart: List[List[float]] = field(default_factory=list)
    length_unit: str = "bohr"  # 'bohr' or 'ang'
    
    # Atoms (list of [element, x, y, z])
    atoms_frac: List[List[Any]] = field(default_factory=list)
    atoms_cart: List[List[Any]] = field(default_factory=list)
    
    # K-points
    mp_grid: List[int] = field(default_factory=lambda: [4, 4, 4])
    kpoints: List[List[float]] = field(default_factory=list)
    
    # Projections (raw block string for MVP simplicity)
    projections_block: str = ""
    
    # Plotting options
    wannier_plot: bool = False
    wannier_plot_supercell: int = 3
    
    # Band structure (optional)
    bands_plot: bool = False
    kpoint_path: List[Tuple[str, List[float]]] = field(default_factory=list)
    
    # Raw passthrough for any parameters not explicitly modeled
    extra_parameters: Dict[str, Any] = field(default_factory=dict)
    extra_lines: str = ""
    
    def to_string(self) -> str:
        """
        Render the .win file content.
        
        Returns:
            String content of the .win file
        """
        lines = []
        
        # Core parameters
        if self.num_wann is not None:
            lines.append(f"num_wann        = {self.num_wann}")
        if self.num_bands is not None:
            lines.append(f"num_bands       = {self.num_bands}")
        lines.append(f"num_iter        = {self.num_iter}")
        lines.append("")
        
        # Plotting options
        if self.wannier_plot:
            lines.append(f"wannier_plot = .true.")
            lines.append(f"wannier_plot_supercell = {self.wannier_plot_supercell}")
            lines.append("")
        
        if self.bands_plot:
            lines.append("bands_plot = .true.")
            lines.append("")
        
        # Extra parameters (key = value)
        for key, value in self.extra_parameters.items():
            if isinstance(value, bool):
                val_str = ".true." if value else ".false."
            elif isinstance(value, str):
                val_str = value
            else:
                val_str = str(value)
            lines.append(f"{key} = {val_str}")
        
        if self.extra_parameters:
            lines.append("")
        
        # Atoms block
        if self.atoms_frac:
            lines.append("begin atoms_frac")
            for atom in self.atoms_frac:
                element = atom[0]
                coords = atom[1:] if len(atom) > 1 else atom[1]
                if isinstance(coords, (list, tuple)):
                    x, y, z = coords[0], coords[1], coords[2]
                else:
                    x, y, z = atom[1], atom[2], atom[3]
                lines.append(f"{element}   {x:12.6f}  {y:12.6f}  {z:12.6f}")
            lines.append("end atoms_frac")
            lines.append("")
        elif self.atoms_cart:
            lines.append("begin atoms_cart")
            for atom in self.atoms_cart:
                element = atom[0]
                coords = atom[1:] if len(atom) > 1 else atom[1]
                if isinstance(coords, (list, tuple)):
                    x, y, z = coords[0], coords[1], coords[2]
                else:
                    x, y, z = atom[1], atom[2], atom[3]
                lines.append(f"{element}   {x:12.6f}  {y:12.6f}  {z:12.6f}")
            lines.append("end atoms_cart")
            lines.append("")
        
        # Projections block
        if self.projections_block:
            lines.append("begin projections")
            for proj_line in self.projections_block.strip().split("\n"):
                lines.append(proj_line)
            lines.append("end projections")
            lines.append("")
        
        # Unit cell
        if self.unit_cell_cart:
            if self.length_unit.lower() == "ang":
                lines.append("begin unit_cell_cart")
                lines.append("ang")
            else:
                lines.append("begin unit_cell_cart")
            for vec in self.unit_cell_cart:
                lines.append(f"{vec[0]:12.6f} {vec[1]:12.6f} {vec[2]:12.6f}")
            lines.append("end unit_cell_cart")
            lines.append("")
        
        # MP grid
        if self.mp_grid:
            lines.append(f"mp_grid : {self.mp_grid[0]} {self.mp_grid[1]} {self.mp_grid[2]}")
            lines.append("")
        
        # K-points block
        if self.kpoints:
            lines.append("begin kpoints")
            for kpt in self.kpoints:
                lines.append(f"{kpt[0]:.4f}  {kpt[1]:.4f}  {kpt[2]:.4f}")
            lines.append("end kpoints")
            lines.append("")
        
        # K-point path for band structure
        if self.kpoint_path and self.bands_plot:
            lines.append("begin kpoint_path")
            for i in range(0, len(self.kpoint_path) - 1, 2):
                start = self.kpoint_path[i]
                end = self.kpoint_path[i + 1]
                lines.append(
                    f"{start[0]} {start[1][0]:.4f} {start[1][1]:.4f} {start[1][2]:.4f}  "
                    f"{end[0]} {end[1][0]:.4f} {end[1][1]:.4f} {end[1][2]:.4f}"
                )
            lines.append("end kpoint_path")
            lines.append("")
        
        # Extra raw lines
        if self.extra_lines:
            lines.append(self.extra_lines.strip())
            lines.append("")
        
        return "\n".join(lines)
    
    def write(self, path: Path) -> None:
        """Write .win file to disk."""
        path.write_text(self.to_string())
    
    @classmethod
    def from_file(cls, path: Path) -> "Wannier90Input":
        """
        Parse a .win file into Wannier90Input.
        
        This is a minimal parser for MVP - handles common blocks and parameters.
        """
        content = path.read_text()
        return cls.from_string(content)
    
    @classmethod
    def from_string(cls, content: str) -> "Wannier90Input":
        """Parse .win content string."""
        obj = cls()
        
        lines = content.split("\n")
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip comments and empty lines
            if not line or line.startswith("!") or line.startswith("#"):
                i += 1
                continue
            
            # Check for blocks
            lower_line = line.lower()
            
            if lower_line.startswith("begin"):
                block_name = lower_line.replace("begin", "").strip()
                block_lines = []
                i += 1
                while i < len(lines) and not lines[i].strip().lower().startswith("end"):
                    block_lines.append(lines[i])
                    i += 1
                
                # Parse block content
                if block_name == "atoms_frac":
                    for bl in block_lines:
                        parts = bl.split()
                        if len(parts) >= 4:
                            element = parts[0]
                            x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                            obj.atoms_frac.append([element, x, y, z])
                
                elif block_name == "atoms_cart":
                    for bl in block_lines:
                        parts = bl.split()
                        if len(parts) >= 4:
                            element = parts[0]
                            x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                            obj.atoms_cart.append([element, x, y, z])
                
                elif block_name == "unit_cell_cart":
                    for bl in block_lines:
                        parts = bl.split()
                        if len(parts) >= 3:
                            try:
                                vec = [float(parts[0]), float(parts[1]), float(parts[2])]
                                obj.unit_cell_cart.append(vec)
                            except ValueError:
                                # Might be 'ang' or 'bohr' unit specifier
                                if parts[0].lower() in ("ang", "angstrom"):
                                    obj.length_unit = "ang"
                
                elif block_name == "projections":
                    obj.projections_block = "\n".join(bl.strip() for bl in block_lines if bl.strip())
                
                elif block_name == "kpoints":
                    for bl in block_lines:
                        parts = bl.split()
                        if len(parts) >= 3:
                            kpt = [float(parts[0]), float(parts[1]), float(parts[2])]
                            obj.kpoints.append(kpt)
                
                i += 1  # Skip 'end' line
                continue
            
            # Parse key = value or key : value
            if "=" in line or ":" in line:
                if "=" in line:
                    key, value = line.split("=", 1)
                else:
                    key, value = line.split(":", 1)
                
                key = key.strip().lower()
                value = value.strip()
                
                # Parse known parameters
                if key == "num_wann":
                    obj.num_wann = int(value)
                elif key == "num_bands":
                    obj.num_bands = int(value)
                elif key == "num_iter":
                    obj.num_iter = int(value)
                elif key == "mp_grid":
                    parts = value.split()
                    obj.mp_grid = [int(parts[0]), int(parts[1]), int(parts[2])]
                elif key == "wannier_plot":
                    obj.wannier_plot = value.lower() in (".true.", "true", "t", "1")
                elif key == "wannier_plot_supercell":
                    obj.wannier_plot_supercell = int(value)
                elif key == "bands_plot":
                    obj.bands_plot = value.lower() in (".true.", "true", "t", "1")
                else:
                    # Store as extra parameter
                    obj.extra_parameters[key] = value
            
            i += 1
        
        return obj


@dataclass
class Pw2Wannier90Input:
    """
    Represents a pw2wannier90 .pw2wan input file.
    
    This is a Fortran namelist file with the &inputpp namelist.
    """
    
    seedname: str = "wannier"
    prefix: str = "pwscf"
    outdir: str = "./"
    write_mmn: bool = True
    write_amn: bool = True
    write_unk: bool = False
    write_uHu: bool = False
    write_dmn: bool = False
    spin_component: str = "none"  # 'none', 'up', 'down'
    
    def to_string(self) -> str:
        """
        Render the .pw2wan file content.
        
        Returns:
            String content of the .pw2wan file
        """
        lines = []
        lines.append("&inputpp")
        lines.append(f"   outdir = '{self.outdir}'")
        lines.append(f"   prefix = '{self.prefix}'")
        lines.append(f"   seedname = '{self.seedname}'")
        lines.append(f"   spin_component = '{self.spin_component}'")
        lines.append(f"   write_mmn = {'.true.' if self.write_mmn else '.false.'}")
        lines.append(f"   write_amn = {'.true.' if self.write_amn else '.false.'}")
        lines.append(f"   write_unk = {'.true.' if self.write_unk else '.false.'}")
        if self.write_uHu:
            lines.append(f"   write_uHu = .true.")
        if self.write_dmn:
            lines.append(f"   write_dmn = .true.")
        lines.append("/")
        return "\n".join(lines)
    
    def write(self, path: Path) -> None:
        """Write .pw2wan file to disk."""
        path.write_text(self.to_string())
    
    @classmethod
    def from_file(cls, path: Path) -> "Pw2Wannier90Input":
        """Parse a .pw2wan file."""
        content = path.read_text()
        return cls.from_string(content)
    
    @classmethod
    def from_string(cls, content: str) -> "Pw2Wannier90Input":
        """Parse .pw2wan content string."""
        obj = cls()
        
        # Simple namelist parser
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("&") or line.startswith("/"):
                continue
            
            if "=" in line:
                key, value = line.rstrip(",").split("=", 1)
                key = key.strip().lower()
                value = value.strip().strip("'\"")
                
                if key == "seedname":
                    obj.seedname = value
                elif key == "prefix":
                    obj.prefix = value
                elif key == "outdir":
                    obj.outdir = value
                elif key == "spin_component":
                    obj.spin_component = value
                elif key == "write_mmn":
                    obj.write_mmn = value.lower() in (".true.", "true", "t")
                elif key == "write_amn":
                    obj.write_amn = value.lower() in (".true.", "true", "t")
                elif key == "write_unk":
                    obj.write_unk = value.lower() in (".true.", "true", "t")
        
        return obj


def generate_kpoints_from_mp_grid(mp_grid: List[int]) -> List[List[float]]:
    """
    Generate explicit k-point list from MP grid.
    
    Args:
        mp_grid: [n1, n2, n3] grid dimensions
        
    Returns:
        List of k-points in fractional coordinates
    """
    kpoints = []
    n1, n2, n3 = mp_grid
    
    for i in range(n1):
        for j in range(n2):
            for k in range(n3):
                kpt = [i / n1, j / n2, k / n3]
                kpoints.append(kpt)
    
    return kpoints

