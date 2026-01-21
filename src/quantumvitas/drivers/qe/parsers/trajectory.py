"""
QE trajectory parser.

Parses QE MD and relax outputs to canonical Trajectory.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.trajectory.model import Frame, Trajectory
from quantumvitas.parsers.registry import register_parser

logger = logging.getLogger(__name__)

# Ry to eV conversion
RY_TO_EV = 13.605693122994


@register_parser("qe", "trajectory")
class QETrajectoryParser:
    """
    Parse QE MD/relax output to canonical Trajectory.
    """
    
    engine = "qe"
    object_type = "trajectory"
    
    def can_parse(self, raw_dir: Path) -> bool:
        """Check if this raw directory contains parseable QE trajectory."""
        # Look for relax.out, vc-relax.out, or md.out
        for pattern in ["relax.out", "vc-relax.out", "md.out", "*.relax.out"]:
            if list(raw_dir.glob(pattern)):
                return True
        return False
    
    def parse(
        self,
        raw_dir: Path,
        calc_dir: Path,
        *,
        run_id: Optional[str] = None,
        step_ulid: Optional[str] = None,
        calc_ulid: Optional[str] = None,
    ) -> Trajectory:
        """
        Parse QE output to canonical Trajectory.
        
        Handles:
        - relax/vc-relax: geometry optimization
        - md: molecular dynamics (future)
        """
        # Find output file
        output_file = self._find_output_file(raw_dir)
        if output_file is None:
            raise FileNotFoundError(f"No QE trajectory output found in {raw_dir}")
        
        # Detect trajectory type
        traj_type = self._detect_trajectory_type(output_file)
        
        # Parse frames
        frames = self._parse_output(output_file, traj_type)
        
        if not frames:
            raise ValueError(f"No frames found in {output_file}")
        
        # Build source files stat
        source_files = [
            SourceFileStat.from_path(output_file, calc_dir)
        ]
        
        # Build metadata
        meta = AnalysisObjectMeta.create(
            object_type="trajectory",
            source_files=source_files,
            run_id=run_id,
            calc_ulid=calc_ulid,
            step_ulid=step_ulid,
            parser_name="qe_trajectory",
            parser_version="1.0",
        )
        
        return Trajectory(
            meta=meta,
            frames=frames,
            trajectory_type=traj_type,
        )
    
    def _find_output_file(self, raw_dir: Path) -> Optional[Path]:
        """Find the trajectory output file."""
        # Priority order
        patterns = [
            "vc-relax.out",
            "relax.out",
            "md.out",
            "*.vc-relax.out",
            "*.relax.out",
        ]
        
        for pattern in patterns:
            matches = list(raw_dir.glob(pattern))
            if matches:
                return matches[0]
        
        return None
    
    def _detect_trajectory_type(self, output_file: Path) -> str:
        """Detect trajectory type from output file."""
        name = output_file.name.lower()
        if "md" in name:
            return "md"
        elif "vc-relax" in name or "vcrelax" in name:
            return "relax"
        elif "relax" in name:
            return "relax"
        
        # Check file content
        text = output_file.read_text(errors="replace")[:5000]
        if "molecular dynamics" in text.lower():
            return "md"
        if "bfgs" in text.lower() or "geometry optimization" in text.lower():
            return "relax"
        
        return "relax"  # Default
    
    def _parse_output(self, output_file: Path, traj_type: str) -> List[Frame]:
        """Parse QE output file for trajectory frames."""
        text = output_file.read_text(errors="replace")
        
        frames: List[Frame] = []
        
        # Parse based on type
        if traj_type == "relax":
            frames = self._parse_relax_output(text)
        else:
            frames = self._parse_md_output(text)
        
        return frames
    
    def _parse_relax_output(self, text: str) -> List[Frame]:
        """Parse relax/vc-relax output."""
        frames: List[Frame] = []
        
        # Patterns
        bfgs_start = re.compile(r"BFGS Geometry Optimization")
        new_coords = re.compile(r"ATOMIC_POSITIONS\s*\(([^)]+)\)")
        cell_params = re.compile(r"CELL_PARAMETERS\s*\(([^)]+)\)")
        total_energy = re.compile(r"!\s*total energy\s*=\s*([-\d.]+)\s*Ry")
        total_force = re.compile(r"Total force\s*=\s*([-\d.]+)")
        
        # Split by BFGS steps
        lines = text.split("\n")
        current_positions = []
        current_species = []
        current_cell = None
        current_energy = None
        current_forces = []
        iteration = 0
        in_positions = False
        in_cell = False
        pos_unit = "angstrom"
        cell_unit = "angstrom"
        alat = 1.0  # Lattice parameter
        
        # First pass: get initial structure and alat
        for line in lines:
            if "lattice parameter" in line.lower() and "a.u." in line:
                match = re.search(r"=\s*([\d.]+)", line)
                if match:
                    alat = float(match.group(1)) * 0.529177  # Bohr to Å
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Energy
            energy_match = total_energy.search(line)
            if energy_match:
                current_energy = float(energy_match.group(1)) * RY_TO_EV
            
            # Detect ATOMIC_POSITIONS block
            pos_match = new_coords.search(line)
            if pos_match:
                pos_unit = pos_match.group(1).lower()
                in_positions = True
                current_positions = []
                current_species = []
                continue
            
            # Detect CELL_PARAMETERS block
            cell_match = cell_params.search(line)
            if cell_match:
                cell_unit = cell_match.group(1).lower()
                in_cell = True
                current_cell = []
                continue
            
            # Parse positions
            if in_positions:
                if stripped == "" or stripped.startswith("End") or stripped.startswith("CELL"):
                    in_positions = False
                else:
                    parts = stripped.split()
                    if len(parts) >= 4:
                        try:
                            species = parts[0]
                            x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                            current_species.append(species)
                            current_positions.append([x, y, z])
                        except ValueError:
                            in_positions = False
            
            # Parse cell
            if in_cell:
                parts = stripped.split()
                if len(parts) >= 3:
                    try:
                        current_cell.append([float(parts[0]), float(parts[1]), float(parts[2])])
                        if len(current_cell) == 3:
                            in_cell = False
                    except ValueError:
                        in_cell = False
            
            # End of BFGS step - create frame
            if "number of scf cycles" in line.lower() or "bfgs converged" in line.lower():
                if current_positions:
                    # Convert positions to Å
                    positions = np.array(current_positions)
                    if "crystal" in pos_unit:
                        # Fractional coordinates - need cell
                        if current_cell:
                            cell = np.array(current_cell)
                            # Scale cell if needed
                            if "alat" in cell_unit:
                                cell = cell * alat
                            elif "bohr" in cell_unit:
                                cell = cell * 0.529177
                            positions = positions @ cell
                    elif "bohr" in pos_unit:
                        positions = positions * 0.529177
                    elif "alat" in pos_unit:
                        positions = positions * alat
                    
                    # Cell
                    cell = None
                    pbc = (False, False, False)
                    if current_cell:
                        cell = np.array(current_cell)
                        if "alat" in cell_unit:
                            cell = cell * alat
                        elif "bohr" in cell_unit:
                            cell = cell * 0.529177
                        pbc = (True, True, True)
                    
                    frame = Frame(
                        frame_index=len(frames),
                        positions=positions,
                        species=current_species.copy(),
                        cell=cell,
                        pbc=pbc,
                        iteration=len(frames),
                        energy=current_energy,
                    )
                    frames.append(frame)
        
        # Add final frame if we have coordinates but haven't saved them
        if current_positions and (not frames or frames[-1].iteration != len(frames)):
            positions = np.array(current_positions)
            cell = np.array(current_cell) if current_cell else None
            pbc = (True, True, True) if cell is not None else (False, False, False)
            
            frame = Frame(
                frame_index=len(frames),
                positions=positions,
                species=current_species.copy(),
                cell=cell,
                pbc=pbc,
                iteration=len(frames),
                energy=current_energy,
            )
            frames.append(frame)
        
        return frames
    
    def _parse_md_output(self, text: str) -> List[Frame]:
        """Parse MD output (placeholder - to be implemented)."""
        # Similar structure to relax but with time steps
        logger.warning("QE MD parsing not yet fully implemented")
        return []

