"""CP2K output parser."""

from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from dataclasses import dataclass

import numpy as np
from pymatgen.core import Structure, Lattice

if TYPE_CHECKING:
    from pymatgen.core import Structure as PMGStructure

logger = logging.getLogger(__name__)


@dataclass
class CP2KTrajectory:
    """
    Trajectory parsed from CP2K output.

    Attributes:
        frames: List of structure snapshots
        energies: List of energies (Hartree) per frame
        iterations: List of iteration numbers
        times: List of simulation times (fs) - for MD only
        temperatures: List of temperatures (K) - for MD only
        cells: List of cell matrices - from .cell file if available
        source_file: Path to source XYZ file
        has_cell_evolution: Whether cell varies over trajectory
    """
    frames: List[Structure]
    energies: List[float]
    iterations: List[int]
    times: Optional[List[float]] = None
    temperatures: Optional[List[float]] = None
    cells: Optional[List[np.ndarray]] = None
    source_file: Optional[Path] = None
    has_cell_evolution: bool = False


def parse_cp2k_output(output_path: Path) -> Dict[str, Any]:
    """
    Parse CP2K output log file.

    Args:
        output_path: Path to output.log

    Returns:
        Dictionary with parsed data:
        - total_energy: Final total energy (Hartree)
        - forces: Forces array (if available)
        - scf_converged: Whether SCF converged
        - n_scf_iterations: Number of SCF iterations
    """
    content = output_path.read_text()

    result = {
        "total_energy": None,
        "forces": None,
        "scf_converged": False,
        "n_scf_iterations": 0,
    }

    # Extract total energy
    # Pattern: "ENERGY| Total FORCE_EVAL ( QS ) energy:"
    energy_pattern = re.compile(
        r"ENERGY\|\s+Total FORCE_EVAL.*?energy:\s+([-\d.]+)"
    )
    matches = energy_pattern.findall(content)
    if matches:
        result["total_energy"] = float(matches[-1])  # Last match (final energy)

    # Check SCF convergence
    if "SCF run converged" in content or "*** SCF run converged" in content:
        result["scf_converged"] = True

    # Extract SCF iteration count
    scf_iter_pattern = re.compile(r"SCF run converged in\s+(\d+)\s+iterations")
    match = scf_iter_pattern.search(content)
    if match:
        result["n_scf_iterations"] = int(match.group(1))

    # Extract forces (if printed)
    # Pattern: "ATOMIC FORCES in [a.u.]"
    forces_section = _extract_forces_section(content)
    if forces_section:
        result["forces"] = forces_section

    return result


def _extract_forces_section(content: str) -> Optional[List[List[float]]]:
    """Extract forces from output log."""
    # Look for "ATOMIC FORCES in [a.u.]" section
    pattern = re.compile(
        r"ATOMIC FORCES in.*?\n.*?\n(.*?)(?=\n\n|\n[A-Z])", re.DOTALL
    )
    match = pattern.search(content)
    if not match:
        return None

    forces_text = match.group(1)
    forces = []
    for line in forces_text.split("\n"):
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 4:
            try:
                fx, fy, fz = float(parts[-3]), float(parts[-2]), float(parts[-1])
                forces.append([fx, fy, fz])
            except (ValueError, IndexError):
                continue

    return forces if forces else None


def parse_cp2k_cell(cell_path: Path) -> List[Dict[str, Any]]:
    """
    Parse CP2K .cell file.

    Format:
    #  Step   Time [fs]       Ax   Ay   Az   Bx   By   Bz   Cx   Cy   Cz   Volume
         1    0.5000        10.0  0.0  0.0  0.0 10.0  0.0  0.0  0.0 10.0  1000.0

    Returns:
        List of dicts with step, time, cell vectors (A, B, C), volume.
    """
    data = []
    with open(cell_path) as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 11:
                try:
                    data.append({
                        "step": int(parts[0]),
                        "time_fs": float(parts[1]),
                        "A": [float(parts[2]), float(parts[3]), float(parts[4])],
                        "B": [float(parts[5]), float(parts[6]), float(parts[7])],
                        "C": [float(parts[8]), float(parts[9]), float(parts[10])],
                        "volume": float(parts[11]) if len(parts) > 11 else None,
                    })
                except (ValueError, IndexError):
                    continue
    return data


def parse_cp2k_ener(ener_path: Path) -> List[Dict[str, Any]]:
    """
    Parse CP2K .ener file.

    Format:
    #   Step   Time[fs]       Kin.[a.u.]   Temp[K]     Pot.[a.u.]   Cons Qty[a.u.]   CPU[s]
          0      0.000000    0.000000000    0.00     -17.157456789   -17.157456789    1.234

    Returns:
        List of dicts with step, time, kinetic, temp, potential, conserved, cpu.
    """
    data = []
    with open(ener_path) as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 7:
                try:
                    data.append({
                        "step": int(parts[0]),
                        "time_fs": float(parts[1]),
                        "kinetic_au": float(parts[2]),
                        "temp_K": float(parts[3]),
                        "potential_au": float(parts[4]),
                        "conserved_au": float(parts[5]),
                        "cpu_s": float(parts[6]),
                    })
                except (ValueError, IndexError):
                    continue
    return data


def parse_cp2k_xyz_comment(line: str) -> Dict[str, Any]:
    """
    Parse CP2K XYZ comment line.

    Format: ' i =        5, E =      -17.12345678'

    Returns:
        {"iteration": 5, "energy": -17.12345678}
    """
    match = re.match(r"\s*i\s*=\s*(\d+),\s*E\s*=\s*([-\d.]+)", line)
    if match:
        return {
            "iteration": int(match.group(1)),
            "energy": float(match.group(2)),
        }
    return {}


def parse_cp2k_trajectory(
    xyz_path: Path,
    cell_path: Optional[Path] = None,
    ener_path: Optional[Path] = None,
    initial_structure: Optional["PMGStructure"] = None,
) -> CP2KTrajectory:
    """
    Parse CP2K trajectory from XYZ, optional .ener file, and optional .cell file.

    Args:
        xyz_path: Path to cp2k_calc-pos-N.xyz
        cell_path: Optional path to cp2k_calc-N.cell (for cell evolution)
        ener_path: Optional path to cp2k_calc-N.ener (for MD)
        initial_structure: Fallback structure for cell if no cell file

    Returns:
        CP2KTrajectory with all frames and metadata.
    """
    frames = []
    energies = []
    iterations = []

    # Parse XYZ file
    with open(xyz_path) as f:
        while True:
            # Read atom count
            line = f.readline()
            if not line:
                break
            try:
                n_atoms = int(line.strip())
            except ValueError:
                break

            # Read comment line: " i =        5, E =      -17.12345678"
            comment = f.readline()
            meta = parse_cp2k_xyz_comment(comment)
            iterations.append(meta.get("iteration", len(frames)))
            energies.append(meta.get("energy", 0.0))

            # Read coordinates
            coords = []
            species = []
            for _ in range(n_atoms):
                coord_line = f.readline()
                if not coord_line:
                    break
                parts = coord_line.split()
                if len(parts) >= 4:
                    species.append(parts[0])
                    coords.append([float(x) for x in parts[1:4]])

            if len(coords) == n_atoms:
                frames.append({"species": species, "coords": coords})

    # Parse cell file if available
    cells = None
    has_cell_evolution = False
    if cell_path and cell_path.exists():
        cell_data = parse_cp2k_cell(cell_path)
        if cell_data:
            cells = [
                np.array([d["A"], d["B"], d["C"]])
                for d in cell_data
            ]
            has_cell_evolution = True

    # Parse energy file if available (has more columns)
    times = None
    temperatures = None
    if ener_path and ener_path.exists():
        ener_data = parse_cp2k_ener(ener_path)
        times = [d["time_fs"] for d in ener_data]
        temperatures = [d["temp_K"] for d in ener_data]

    # Build structures with cell info
    structures = []
    for i, frame in enumerate(frames):
        if cells and i < len(cells):
            lattice = Lattice(cells[i])
        elif initial_structure:
            lattice = initial_structure.lattice
        else:
            raise ValueError(f"No cell information for frame {i}")

        structures.append(Structure(
            lattice,
            frame["species"],
            frame["coords"],
            coords_are_cartesian=True,
        ))

    return CP2KTrajectory(
        frames=structures,
        energies=energies,
        iterations=iterations,
        times=times,
        temperatures=temperatures,
        cells=cells,
        source_file=xyz_path,
        has_cell_evolution=has_cell_evolution,
    )


def extract_final_structure(
    xyz_path: Path,
    cell_path: Optional[Path] = None,
    initial_structure: Optional["PMGStructure"] = None,
) -> Structure:
    """
    Extract final (last) frame from CP2K trajectory XYZ file.

    Args:
        xyz_path: Path to trajectory XYZ file
        cell_path: Optional path to cell file (for cell evolution)
        initial_structure: Fallback structure for cell if no cell file

    Returns:
        Pymatgen Structure of the final frame.
    """
    trajectory = parse_cp2k_trajectory(
        xyz_path=xyz_path,
        cell_path=cell_path,
        initial_structure=initial_structure,
    )
    return trajectory.frames[-1]

