"""
QE output file parsers.

This module provides parsers for Quantum ESPRESSO output files:
- SCF/NSCF output (.out) files
- DOS data (.dat) files
- Band structure data (.dat.gnu) files
- Bands.x output files (for high-symmetry points)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# =============================================================================
# SCF Output Parser
# =============================================================================

@dataclass
class SCFIteration:
    """
    Single SCF iteration data.
    
    Units:
        total_energy: Rydberg (Ry)
        scf_accuracy: Rydberg (Ry)
        cpu_time: seconds
        wall_time: seconds
    """
    iteration: int
    total_energy: float  # Ry
    scf_accuracy: float  # Ry
    cpu_time: Optional[float] = None  # seconds
    wall_time: Optional[float] = None  # seconds


@dataclass
class SCFResult:
    """
    Parsed SCF calculation result.
    
    Units:
        total_energy: Rydberg (Ry)
        fermi_energy, homo, lumo, band_gap: electronvolt (eV)
        ecutwfc, ecutrho: Rydberg (Ry)
        total_cpu_time, total_wall_time: seconds
    
    Note: QE reports energies in Ry in the main output but Fermi/HOMO/LUMO in eV.
    This dataclass preserves those native units.
    """
    converged: bool
    iterations: List[SCFIteration]
    total_energy: Optional[float] = None  # Final total energy in Ry
    fermi_energy: Optional[float] = None  # Fermi/HOMO level in eV
    total_magnetization: Optional[float] = None  # Bohr magnetons
    absolute_magnetization: Optional[float] = None  # Bohr magnetons
    n_electrons: Optional[float] = None
    n_kpoints: Optional[int] = None
    n_bands: Optional[int] = None
    ecutwfc: Optional[float] = None  # kinetic-energy cutoff in Ry
    ecutrho: Optional[float] = None  # charge density cutoff in Ry
    
    # Band gap info (for insulators/semiconductors) - all in eV
    homo: Optional[float] = None  # Highest occupied level in eV
    lumo: Optional[float] = None  # Lowest unoccupied level in eV
    band_gap: Optional[float] = None  # In eV
    
    # Timing in seconds
    total_cpu_time: Optional[float] = None
    total_wall_time: Optional[float] = None
    
    # Raw metadata
    calculation_type: Optional[str] = None
    prefix: Optional[str] = None
    
    # Unit tracking for explicit documentation
    energy_unit: str = "Ry"  # For total_energy, iterations
    fermi_unit: str = "eV"  # For fermi_energy, homo, lumo, band_gap
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "converged": self.converged,
            "iterations": [
                {
                    "iteration": it.iteration,
                    "total_energy_ry": it.total_energy,
                    "scf_accuracy_ry": it.scf_accuracy,
                    "cpu_time_s": it.cpu_time,
                    "wall_time_s": it.wall_time,
                }
                for it in self.iterations
            ],
            "total_energy_ry": self.total_energy,
            "fermi_energy_ev": self.fermi_energy,
            "homo_ev": self.homo,
            "lumo_ev": self.lumo,
            "band_gap_ev": self.band_gap,
            "n_electrons": self.n_electrons,
            "n_kpoints": self.n_kpoints,
            "n_bands": self.n_bands,
            "ecutwfc_ry": self.ecutwfc,
            "ecutrho_ry": self.ecutrho,
            "calculation_type": self.calculation_type,
            "total_cpu_time_s": self.total_cpu_time,
            "total_wall_time_s": self.total_wall_time,
            "total_magnetization": self.total_magnetization,
            "absolute_magnetization": self.absolute_magnetization,
            "units": {
                "energy": "Ry",
                "fermi": "eV",
                "time": "s",
            },
        }


def parse_scf_output_text(text: str) -> SCFResult:
    """
    Parse QE pw.x output text content.
    
    This parser handles:
    - Standard SCF calculations
    - NSCF calculations (may have no iterations)
    - Relax/VC-relax (extracts final SCF block)
    - Interrupted calculations (partial data)
    
    Args:
        text: Output text content (string, not a path)
        
    Returns:
        SCFResult with parsed data
    """
    iterations: List[SCFIteration] = []
    converged = False
    total_energy = None
    fermi_energy = None
    homo = None
    lumo = None
    n_electrons = None
    n_kpoints = None
    n_bands = None
    ecutwfc = None
    ecutrho = None
    calculation_type = None
    total_cpu = None
    total_wall = None
    total_magnetization = None
    absolute_magnetization = None

    # Patterns
    iter_pattern = re.compile(r"iteration\s+#\s*(\d+)\s+ecut=\s*[\d.]+\s*Ry\s+beta=\s*[\d.]+")
    energy_pattern = re.compile(r"total energy\s*=\s*([-\d.]+)\s*Ry")
    final_energy_pattern = re.compile(r"!\s+total energy\s*=\s*([-\d.]+)\s*Ry")
    accuracy_pattern = re.compile(r"estimated scf accuracy\s*<\s*([-\d.Ee+]+)\s*Ry")
    fermi_pattern = re.compile(r"(?:Fermi energy|the Fermi energy) is\s+([-\d.]+)\s*ev", re.IGNORECASE)
    homo_lumo_pattern = re.compile(r"highest occupied, lowest unoccupied level.*?:\s+([-\d.]+)\s+([-\d.]+)")
    homo_pattern = re.compile(r"highest occupied level.*?:\s+([-\d.]+)")
    electrons_pattern = re.compile(r"number of electrons\s*=\s*([-\d.]+)")
    kpoints_pattern = re.compile(r"number of k points\s*=\s*(\d+)")
    bands_pattern = re.compile(r"number of Kohn-Sham states\s*=\s*(\d+)")
    ecutwfc_pattern = re.compile(r"kinetic-energy cutoff\s*=\s*([-\d.]+)\s*Ry")
    ecutrho_pattern = re.compile(r"charge density cutoff\s*=\s*([-\d.]+)\s*Ry")
    calc_pattern = re.compile(r"calculation\s*=\s*'?(\w+)'?", re.IGNORECASE)
    time_pattern = re.compile(r"PWSCF\s*:\s*([\d.hms ]+)\s*CPU\s+([\d.hms ]+)\s*WALL")
    total_mag_pattern = re.compile(r"total magnetization\s*=\s*([-\d.]+)\s*Bohr", re.IGNORECASE)
    abs_mag_pattern = re.compile(r"absolute magnetization\s*=\s*([-\d.]+)\s*Bohr", re.IGNORECASE)
    # Detect new SCF cycle (for relax/md)
    new_scf_pattern = re.compile(r"Self-consistent Calculation|BFGS Geometry Optimization")
    
    current_iter = None
    current_energy = None
    current_accuracy = None
    in_new_scf_block = False
    
    for line in text.splitlines():
        stripped = line.strip()
        
        # Detect start of new SCF block (relax/md calculations)
        if new_scf_pattern.search(stripped):
            # Save current iteration if exists before resetting
            if current_iter is not None and current_energy is not None:
                iterations.append(SCFIteration(
                    iteration=current_iter,
                    total_energy=current_energy,
                    scf_accuracy=current_accuracy or 0.0,
                ))
            # For relax/md, we want the LAST SCF block, so clear iterations
            if in_new_scf_block:
                iterations = []
            in_new_scf_block = True
            current_iter = None
            current_energy = None
            current_accuracy = None
            continue
        
        # Check for iteration start
        iter_match = iter_pattern.search(stripped)
        if iter_match:
            # Save previous iteration if exists
            if current_iter is not None and current_energy is not None:
                iterations.append(SCFIteration(
                    iteration=current_iter,
                    total_energy=current_energy,
                    scf_accuracy=current_accuracy or 0.0,
                ))
            current_iter = int(iter_match.group(1))
            current_energy = None
            current_accuracy = None
            continue
        
        # Check for energy in iteration
        energy_match = energy_pattern.search(stripped)
        if energy_match and "!" not in stripped:
            current_energy = float(energy_match.group(1))
            continue
        
        # Check for accuracy
        accuracy_match = accuracy_pattern.search(stripped)
        if accuracy_match:
            try:
                current_accuracy = float(accuracy_match.group(1))
            except ValueError:
                current_accuracy = None
            continue
        
        # Check for final energy (with !)
        final_match = final_energy_pattern.search(stripped)
        if final_match:
            total_energy = float(final_match.group(1))
            converged = True
            continue
        
        # Check for Fermi energy
        fermi_match = fermi_pattern.search(stripped)
        if fermi_match:
            fermi_energy = float(fermi_match.group(1))
            continue
        
        # Check for HOMO/LUMO
        homo_lumo_match = homo_lumo_pattern.search(stripped)
        if homo_lumo_match:
            homo = float(homo_lumo_match.group(1))
            lumo = float(homo_lumo_match.group(2))
            continue
        
        homo_match = homo_pattern.search(stripped)
        if homo_match:
            homo = float(homo_match.group(1))
            continue
        
        # Check for electrons (only first occurrence)
        if n_electrons is None:
            electrons_match = electrons_pattern.search(stripped)
            if electrons_match:
                n_electrons = float(electrons_match.group(1))
                continue
        
        # Check for k-points (only first occurrence)
        if n_kpoints is None:
            kpoints_match = kpoints_pattern.search(stripped)
            if kpoints_match:
                n_kpoints = int(kpoints_match.group(1))
                continue
        
        # Check for bands (only first occurrence)
        if n_bands is None:
            bands_match = bands_pattern.search(stripped)
            if bands_match:
                n_bands = int(bands_match.group(1))
                continue
        
        # Check for cutoffs (only first occurrence)
        if ecutwfc is None:
            ecutwfc_match = ecutwfc_pattern.search(stripped)
            if ecutwfc_match:
                ecutwfc = float(ecutwfc_match.group(1))
                continue
        
        if ecutrho is None:
            ecutrho_match = ecutrho_pattern.search(stripped)
            if ecutrho_match:
                ecutrho = float(ecutrho_match.group(1))
                continue
        
        # Check for calculation type (only first occurrence)
        if calculation_type is None:
            calc_match = calc_pattern.search(stripped)
            if calc_match:
                calculation_type = calc_match.group(1)
                continue
        
        # Check for magnetization (use last occurrence — correct for relax/md multi-cycle)
        mag_match = total_mag_pattern.search(stripped)
        if mag_match:
            total_magnetization = float(mag_match.group(1))
            continue
        abs_mag_match = abs_mag_pattern.search(stripped)
        if abs_mag_match:
            absolute_magnetization = float(abs_mag_match.group(1))
            continue

        # Check for JOB DONE
        if "JOB DONE" in stripped:
            converged = True
            continue

        # Check for timing (use last occurrence)
        time_match = time_pattern.search(stripped)
        if time_match:
            total_cpu = _parse_time_string(time_match.group(1))
            total_wall = _parse_time_string(time_match.group(2))
            continue
    
    # Save last iteration if exists
    if current_iter is not None and current_energy is not None:
        iterations.append(SCFIteration(
            iteration=current_iter,
            total_energy=current_energy,
            scf_accuracy=current_accuracy or 0.0,
        ))
    
    # Calculate band gap if HOMO/LUMO available
    band_gap = None
    if homo is not None and lumo is not None:
        band_gap = lumo - homo
    
    # If no fermi energy but have HOMO, use HOMO as approximate Fermi
    if fermi_energy is None and homo is not None:
        fermi_energy = homo
    
    return SCFResult(
        converged=converged,
        iterations=iterations,
        total_energy=total_energy,
        fermi_energy=fermi_energy,
        homo=homo,
        lumo=lumo,
        band_gap=band_gap,
        n_electrons=n_electrons,
        n_kpoints=n_kpoints,
        n_bands=n_bands,
        ecutwfc=ecutwfc,
        ecutrho=ecutrho,
        calculation_type=calculation_type,
        total_cpu_time=total_cpu,
        total_wall_time=total_wall,
        total_magnetization=total_magnetization,
        absolute_magnetization=absolute_magnetization,
    )


def parse_scf_output_path(path: Path | str) -> SCFResult:
    """
    Parse QE pw.x output file from file path.
    
    Args:
        path: Path to output file
        
    Returns:
        SCFResult with parsed data
        
    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If path is a directory (e.g., '.')
    """
    path_obj = Path(path)
    
    if not path_obj.exists():
        raise FileNotFoundError(f"Output file not found: {path_obj}")
    
    if path_obj.is_dir():
        raise ValueError(f"Expected file path, got directory: {path_obj}. Use parse_scf_output_text() for text input.")
    
    text = path_obj.read_text()
    return parse_scf_output_text(text)


def parse_scf_output(path_or_text: Path | str) -> SCFResult:
    """
    Parse QE pw.x output file or text.
    
    This is a convenience wrapper that automatically detects whether input is a path or text.
    
    Args:
        path_or_text: Path to output file or output text content
        
    Returns:
        SCFResult with parsed data
        
    Raises:
        FileNotFoundError: If path does not exist
        ValueError: If path is a directory (e.g., '.')
    """
    if isinstance(path_or_text, Path):
        return parse_scf_output_path(path_or_text)
    elif isinstance(path_or_text, str):
        # Check if string is a file path (short string that exists and is a file)
        path_obj = Path(path_or_text)
        # B. Don't treat '.' or directories as file paths
        if path_obj.exists() and path_obj.is_file() and len(path_or_text) < 500:
            return parse_scf_output_path(path_obj)
        else:
            # Treat as text content
            return parse_scf_output_text(path_or_text)
    else:
        raise TypeError(f"Expected Path or str, got {type(path_or_text)}")


def _parse_time_string(time_str: str) -> float:
    """Parse QE time string like '1h 2m 30.5s' or '1.23s' to seconds."""
    total = 0.0
    time_str = time_str.strip()
    
    # Handle hours
    if 'h' in time_str:
        parts = time_str.split('h')
        total += float(parts[0].strip()) * 3600
        time_str = parts[1] if len(parts) > 1 else ''
    
    # Handle minutes
    if 'm' in time_str:
        parts = time_str.split('m')
        total += float(parts[0].strip()) * 60
        time_str = parts[1] if len(parts) > 1 else ''
    
    # Handle seconds
    if 's' in time_str:
        sec_str = time_str.replace('s', '').strip()
        if sec_str:
            total += float(sec_str)
    elif time_str.strip():
        # Just a number without unit, assume seconds
        try:
            total += float(time_str.strip())
        except ValueError:
            pass
    
    return total


# =============================================================================
# DOS Parser
# =============================================================================

@dataclass
class DOSData:
    """
    Parsed DOS data from QE dos.x output.
    
    Units:
        energies: electronvolt (eV)
        dos: states/eV
        idos: number of electrons (dimensionless)
        fermi_energy: electronvolt (eV)
    
    All energies from QE DOS output are already in eV.
    """
    energies: np.ndarray  # Energy values in eV
    dos: np.ndarray  # DOS values (states/eV)
    idos: Optional[np.ndarray] = None  # Integrated DOS (electrons)
    fermi_energy: Optional[float] = None  # Fermi energy in eV
    energy_unit: str = "eV"
    dos_unit: str = "states/eV"
    
    def shift_to_fermi(self) -> "DOSData":
        """Return a new DOSData with energies shifted so Fermi is at 0."""
        if self.fermi_energy is None:
            return self
        return DOSData(
            energies=self.energies - self.fermi_energy,
            dos=self.dos.copy(),
            idos=self.idos.copy() if self.idos is not None else None,
            fermi_energy=0.0,
            energy_unit=self.energy_unit,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "energies_ev": self.energies.tolist(),
            "dos_states_per_ev": self.dos.tolist(),
            "idos": self.idos.tolist() if self.idos is not None else None,
            "fermi_energy_ev": self.fermi_energy,
            "n_points": len(self.energies),
            "energy_range_ev": [float(self.energies.min()), float(self.energies.max())],
            "units": {
                "energy": "eV",
                "dos": "states/eV",
            },
        }


def parse_dos_data(path: Path | str) -> DOSData:
    """
    Parse QE DOS output file (.dat format).
    
    Format:
        #  E (eV)   dos(E)     Int dos(E) EFermi =    X.XXX eV
        -9.000  0.0000E+00  0.0000E+00
        ...
    
    Args:
        path: Path to DOS .dat file
        
    Returns:
        DOSData with parsed values
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"DOS file not found: {path}")
    
    text = path.read_text()
    lines = text.strip().splitlines()
    
    # Parse header for Fermi energy
    fermi_energy = None
    data_start = 0
    
    for i, line in enumerate(lines):
        if line.strip().startswith('#'):
            # Parse Fermi energy from header
            fermi_match = re.search(r'EFermi\s*=\s*([-\d.]+)', line, re.IGNORECASE)
            if fermi_match:
                fermi_energy = float(fermi_match.group(1))
            data_start = i + 1
        else:
            # First non-comment line
            break
    
    # Parse data
    energies = []
    dos = []
    idos = []
    
    for line in lines[data_start:]:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        parts = line.split()
        if len(parts) >= 2:
            try:
                energies.append(float(parts[0]))
                dos.append(float(parts[1]))
                if len(parts) >= 3:
                    idos.append(float(parts[2]))
            except ValueError:
                continue
    
    return DOSData(
        energies=np.array(energies),
        dos=np.array(dos),
        idos=np.array(idos) if idos else None,
        fermi_energy=fermi_energy,
    )


# =============================================================================
# Band Structure Parser
# =============================================================================

@dataclass
class HighSymmetryPoint:
    """High-symmetry k-point information."""
    label: str  # e.g., "Γ", "X", "L", "K"
    k_distance: float  # x-coordinate in band plot
    k_coords: Optional[Tuple[float, float, float]] = None  # k-point coordinates


@dataclass
class BandStructureData:
    """
    Parsed band structure data from QE bands.x output.
    
    Units:
        k_distances: 2π/a (inverse Bohr, dimensionless in crystal coords)
        energies: electronvolt (eV)
        fermi_energy: electronvolt (eV)
    
    The bands.dat.gnu format outputs energies in eV.
    k_distances are cumulative path distances in reciprocal space.
    """
    k_distances: np.ndarray  # x-axis values (cumulative k-distance in 2π/a)
    energies: np.ndarray  # Shape: (n_bands, n_kpoints), energies in eV
    high_symmetry_points: List[HighSymmetryPoint]  # For tick marks/labels
    fermi_energy: Optional[float] = None  # Fermi energy in eV
    n_bands: int = 0
    n_kpoints: int = 0
    energy_unit: str = "eV"
    
    def __post_init__(self):
        """Set band and k-point counts."""
        if self.energies.size > 0:
            self.n_bands = self.energies.shape[0]
            self.n_kpoints = self.energies.shape[1]
    
    def shift_to_fermi(self) -> "BandStructureData":
        """Return new BandStructureData with energies shifted so Fermi is at 0."""
        if self.fermi_energy is None:
            return self
        return BandStructureData(
            k_distances=self.k_distances.copy(),
            energies=self.energies - self.fermi_energy,
            high_symmetry_points=self.high_symmetry_points.copy(),
            fermi_energy=0.0,
            energy_unit=self.energy_unit,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "k_distances": self.k_distances.tolist(),
            "energies_ev": self.energies.tolist(),
            "high_symmetry_points": [
                {
                    "label": pt.label,
                    "k_distance": pt.k_distance,
                    "k_coords": list(pt.k_coords) if pt.k_coords is not None else None,
                }
                for pt in self.high_symmetry_points
            ],
            "fermi_energy_ev": self.fermi_energy,
            "n_bands": self.n_bands,
            "n_kpoints": self.n_kpoints,
            "units": {
                "energy": "eV",
                "k_distance": "2π/a",
            },
        }


def parse_bands_gnu(
    bands_file: Path | str,
    symmetry_file: Optional[Path | str] = None,
    fermi_energy: Optional[float] = None,
    pw_output_file: Optional[Path | str] = None,
    structure_file: Optional[Path | str] = None,
) -> BandStructureData:
    """
    Parse QE bands.dat.gnu file and optionally bands.x output for symmetry points.
    
    The bands.dat.gnu file format:
        k_distance  energy
        ...
        (blank line between bands)
    
    Args:
        bands_file: Path to bands.dat.gnu file
        symmetry_file: Optional path to bands.x output (for high-symmetry points)
        fermi_energy: Optional Fermi energy in eV
        pw_output_file: Optional path to pw.x output (scf/nscf/bands) for reciprocal lattice vectors.
                        Used to convert k-points from Cartesian to crystal coordinates.
        structure_file: Optional path to structure file for pymatgen k-point labeling.
        
    Returns:
        BandStructureData with parsed values
    """
    bands_path = Path(bands_file)
    if not bands_path.exists():
        raise FileNotFoundError(f"Band file not found: {bands_path}")
    
    # Parse bands.dat.gnu
    text = bands_path.read_text()
    
    # Split by blank lines to separate bands
    band_blocks = re.split(r'\n\s*\n', text.strip())
    
    bands_data: List[List[Tuple[float, float]]] = []
    
    for block in band_blocks:
        block = block.strip()
        if not block:
            continue
        
        band_points: List[Tuple[float, float]] = []
        for line in block.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    k_dist = float(parts[0])
                    energy = float(parts[1])
                    band_points.append((k_dist, energy))
                except ValueError:
                    continue
        
        if band_points:
            bands_data.append(band_points)
    
    if not bands_data:
        raise ValueError(f"No band data found in {bands_path}")
    
    # Convert to arrays
    n_bands = len(bands_data)
    n_kpoints = len(bands_data[0])
    
    # Verify all bands have same number of k-points
    for i, band in enumerate(bands_data):
        if len(band) != n_kpoints:
            raise ValueError(
                f"Band {i} has {len(band)} k-points, expected {n_kpoints}"
            )
    
    k_distances = np.array([pt[0] for pt in bands_data[0]])
    energies = np.array([[pt[1] for pt in band] for band in bands_data])
    
    # Parse reciprocal lattice vectors from pw.x output if provided
    reciprocal_lattice = None
    if pw_output_file:
        pw_path = Path(pw_output_file)
        if pw_path.exists():
            reciprocal_lattice = _parse_reciprocal_lattice_vectors(pw_path)
    
    # Parse high-symmetry points if symmetry file provided
    import logging
    logger = logging.getLogger(__name__)
    
    high_sym_points: List[HighSymmetryPoint] = []
    if symmetry_file:
        sym_path = Path(symmetry_file)
        logger.debug(f"[PARSE_BANDS] Attempting to parse high-symmetry points from: {sym_path}")
        if sym_path.exists():
            try:
                struct_path = Path(structure_file) if structure_file else None
                high_sym_points = _parse_bands_symmetry_output(
                    sym_path,
                    reciprocal_lattice=reciprocal_lattice,
                    structure_file=struct_path,
                )
                logger.debug(f"[PARSE_BANDS] Parsed {len(high_sym_points)} high-symmetry points from {sym_path.name}")
            except Exception as e:
                logger.debug(f"[PARSE_BANDS] Failed to parse high-symmetry points from {sym_path}: {e}", exc_info=True)
                # Continue without high-symmetry points - plot will still render
                high_sym_points = []
        else:
            logger.debug(f"[PARSE_BANDS] Symmetry file not found: {sym_path}")
    
    return BandStructureData(
        k_distances=k_distances,
        energies=energies,
        high_symmetry_points=high_sym_points,
        fermi_energy=fermi_energy,
    )


def _parse_reciprocal_lattice_vectors(output_file: Path) -> Optional[np.ndarray]:
    """
    Parse reciprocal lattice vectors from pw.x output file.
    
    Looks for:
        reciprocal axes: (cart. coord. in units 2 pi/alat)
                   b(1) = ( -0.707107 -0.707107  0.707107 )
                   b(2) = (  0.707107  0.707107  0.707107 )
                   b(3) = ( -0.707107  0.707107 -0.707107 )
    
    Returns:
        3x3 numpy array where rows are b1, b2, b3 vectors, or None if not found
    """
    text = output_file.read_text()
    
    # Look for reciprocal axes section
    pattern = re.compile(
        r'reciprocal axes:.*?'
        r'b\(1\)\s*=\s*\(\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*\).*?'
        r'b\(2\)\s*=\s*\(\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*\).*?'
        r'b\(3\)\s*=\s*\(\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*\)',
        re.DOTALL
    )
    
    match = pattern.search(text)
    if not match:
        return None
    
    b1 = [float(match.group(1)), float(match.group(2)), float(match.group(3))]
    b2 = [float(match.group(4)), float(match.group(5)), float(match.group(6))]
    b3 = [float(match.group(7)), float(match.group(8)), float(match.group(9))]
    
    return np.array([b1, b2, b3])


def _cartesian_to_crystal(k_cart: Tuple[float, float, float], B: np.ndarray) -> Tuple[float, float, float]:
    """
    Convert k-point from Cartesian (2π/a) to crystal (fractional) coordinates.
    
    k_cart = k_cryst[0]*b1 + k_cryst[1]*b2 + k_cryst[2]*b3
    So: k_cryst = B^(-1) @ k_cart where B has b1,b2,b3 as rows
    
    Args:
        k_cart: k-point in Cartesian coordinates (units 2π/a)
        B: 3x3 matrix with reciprocal lattice vectors as rows
        
    Returns:
        k-point in crystal (fractional) coordinates
    """
    k_cart_vec = np.array(k_cart)
    # B^T has b1,b2,b3 as columns; invert to convert cart -> crystal
    B_inv = np.linalg.inv(B.T)
    k_cryst = B_inv @ k_cart_vec
    return tuple(k_cryst)


def _identify_high_symmetry_label_pymatgen(
    k_cryst: Tuple[float, float, float],
    structure_file: Optional[Path] = None,
) -> str:
    """
    Try to identify high-symmetry point label using pymatgen's HighSymmKpath.
    
    Falls back to _identify_high_symmetry_point if pymatgen is not available
    or structure is not provided.
    """
    try:
        from pymatgen.core import Structure
        from pymatgen.symmetry.bandstructure import HighSymmKpath
        
        if structure_file and structure_file.exists():
            # Load structure and get high-symmetry points
            struct = Structure.from_file(str(structure_file))
            kpath = HighSymmKpath(struct)
            
            # Check against known high-symmetry points
            kx, ky, kz = k_cryst
            tol = 0.02
            
            for label, coords in kpath.kpath['kpoints'].items():
                if (abs(kx - coords[0]) < tol and 
                    abs(ky - coords[1]) < tol and 
                    abs(kz - coords[2]) < tol):
                    # Use proper Greek letters
                    if label == "\\Gamma" or label == "GAMMA":
                        return "Γ"
                    return label
    except ImportError:
        pass
    except Exception:
        pass
    
    # Fall back to simple identification based on crystal coordinates
    return _identify_high_symmetry_point_crystal(k_cryst)


def _identify_high_symmetry_point_crystal(k_cryst: Tuple[float, float, float]) -> str:
    """
    Identify high-symmetry point label from crystal coordinates.
    
    This handles common FCC/BCC/simple cubic high-symmetry points
    in crystal (fractional) coordinates.
    """
    kx, ky, kz = k_cryst
    tol = 0.02
    
    # Gamma (0, 0, 0)
    if abs(kx) < tol and abs(ky) < tol and abs(kz) < tol:
        return "Γ"
    
    # For FCC: high-symmetry points in crystal coordinates
    # L = (0.5, 0.5, 0.5)
    if abs(abs(kx) - 0.5) < tol and abs(abs(ky) - 0.5) < tol and abs(abs(kz) - 0.5) < tol:
        return "L"
    
    # X = (0.5, 0, 0.5) or permutations
    coords_sorted = sorted([abs(kx), abs(ky), abs(kz)])
    if abs(coords_sorted[0]) < tol and abs(coords_sorted[1] - 0.5) < tol and abs(coords_sorted[2] - 0.5) < tol:
        return "X"
    
    # W = (0.5, 0.25, 0.75) or permutations
    if (abs(coords_sorted[0] - 0.25) < tol and 
        abs(coords_sorted[1] - 0.5) < tol and 
        abs(coords_sorted[2] - 0.75) < tol):
        return "W"
    
    # K = (0.375, 0.375, 0.75) or similar
    if (abs(coords_sorted[0] - 0.375) < tol and 
        abs(coords_sorted[1] - 0.375) < tol and 
        abs(coords_sorted[2] - 0.75) < tol):
        return "K"
    
    # U = (0.625, 0.25, 0.625) or similar  
    if (abs(coords_sorted[0] - 0.25) < tol and
        abs(coords_sorted[1] - 0.625) < tol and 
        abs(coords_sorted[2] - 0.625) < tol):
        return "U"
    
    # Default: show crystal coordinates
    return f"({kx:.2f},{ky:.2f},{kz:.2f})"


def _parse_bands_symmetry_output(
    path: Path,
    reciprocal_lattice: Optional[np.ndarray] = None,
    structure_file: Optional[Path] = None,
) -> List[HighSymmetryPoint]:
    """
    Parse bands.x output file to extract high-symmetry point positions.
    
    Looks for lines like:
        high-symmetry point:  0.5000 0.5000 0.5000   x coordinate   0.0000
        
    Note: The k-point coordinates in bands.x output are in Cartesian (2π/a) units.
    If reciprocal_lattice is provided, converts to crystal coordinates for proper labeling.
    
    Args:
        path: Path to bands.x output file
        reciprocal_lattice: Optional 3x3 array of reciprocal lattice vectors (rows are b1,b2,b3)
        structure_file: Optional path to structure file for pymatgen labeling
        
    Returns:
        List of HighSymmetryPoint objects, deduplicated by x coordinate
    """
    import logging
    logger = logging.getLogger(__name__)
    
    text = path.read_text()
    from typing import Dict
    points_dict: Dict[float, HighSymmetryPoint] = {}  # x_coord -> point (for deduplication)
    
    # More flexible regex: allows optional spacing and text between k-coords and "x coordinate"
    pattern = re.compile(
        r'high-symmetry point:\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+).*?x coordinate\s+([-\d.]+)',
        re.IGNORECASE
    )
    
    matches_found = 0
    for match in pattern.finditer(text):
        matches_found += 1
        try:
            kx, ky, kz = float(match.group(1)), float(match.group(2)), float(match.group(3))
            x_coord = float(match.group(4))
            k_cart = (kx, ky, kz)
            
            # Deduplicate by x coordinate within epsilon (1e-6)
            # If x_coord already exists, keep the first one (preserve order)
            eps = 1e-6
            existing_x = None
            for existing_x_coord in points_dict.keys():
                if abs(existing_x_coord - x_coord) < eps:
                    existing_x = existing_x_coord
                    break
            
            if existing_x is None:
                # Convert to crystal coordinates if reciprocal lattice is available
                if reciprocal_lattice is not None:
                    k_cryst = _cartesian_to_crystal(k_cart, reciprocal_lattice)
                    # Try pymatgen first, then fall back to simple identification
                    label = _identify_high_symmetry_label_pymatgen(k_cryst, structure_file)
                else:
                    # Fall back to old behavior (Cartesian-based identification)
                    label = _identify_high_symmetry_point_cartesian(kx, ky, kz)
                
                points_dict[x_coord] = HighSymmetryPoint(
                    label=label,
                    k_distance=x_coord,
                    k_coords=k_cart,  # Store original Cartesian coords
                )
        except (ValueError, IndexError) as e:
            logger.debug(f"Failed to parse high-symmetry point from line: {e}")
            continue
    
    # Return points sorted by x coordinate (preserve file order as much as possible)
    points_list = list(points_dict.values())
    points_list.sort(key=lambda p: p.k_distance)
    
    logger.debug(f"Parsed {matches_found} high-symmetry point matches from {path.name}, deduplicated to {len(points_list)} unique points")
    
    return points_list


def _identify_high_symmetry_point_cartesian(kx: float, ky: float, kz: float) -> str:
    """
    Identify high-symmetry point label from Cartesian coordinates (2π/a units).
    
    This is a simplified identification for common FCC/BCC/simple cubic points.
    Returns generic label if not recognized.
    
    Note: This is a fallback when reciprocal lattice vectors are not available.
    Prefer using crystal coordinates with _identify_high_symmetry_point_crystal().
    """
    tol = 0.01
    
    # Gamma (0, 0, 0)
    if abs(kx) < tol and abs(ky) < tol and abs(kz) < tol:
        return "Γ"
    
    # For FCC in Cartesian 2π/a: X ~ (-0.707, 0, 0) etc.
    # This is approximate and structure-dependent
    
    # Default: show Cartesian coordinates
    return f"({kx:.2f},{ky:.2f},{kz:.2f})"


def parse_fermi_from_scf_output(path: Path | str) -> Optional[float]:
    """
    Extract Fermi energy from SCF/NSCF output file.
    
    Args:
        path: Path to QE output file
        
    Returns:
        Fermi energy in eV, or None if not found
    """
    result = parse_scf_output(path)
    return result.fermi_energy


# =============================================================================
# Convenience functions
# =============================================================================

def find_bands_files(
    directory: Path | str,
    prefix: str = "",
) -> Dict[str, Optional[Path]]:
    """
    Find band structure related files in a directory.
    
    Args:
        directory: Directory to search
        prefix: Optional prefix filter for files
        
    Returns:
        Dict with keys: 'bands_gnu', 'bands_out', 'scf_out', 'nscf_out'
        
    File naming conventions supported:
        - bands.dat.gnu: GNU plot format bands data
        - *.bands.out or *bandspp*.out: bands.x post-processing output (contains high-sym points)
        - *scf*.out: pw.x SCF output (for Fermi energy)
        - *nscf*.out: pw.x NSCF output (preferred for Fermi energy)
    """
    directory = Path(directory)
    result: Dict[str, Optional[Path]] = {
        'bands_gnu': None,
        'bands_out': None,
        'scf_out': None,
        'nscf_out': None,
    }
    
    for file in directory.iterdir():
        if not file.is_file():
            continue
        name = file.name.lower()
        if prefix and not name.startswith(prefix.lower()):
            continue
        
        if 'bands.dat.gnu' in name or name.endswith('.dat.gnu'):
            result['bands_gnu'] = file
        # Look for bands.x output - multiple naming conventions
        elif name.endswith('.out'):
            # bands.x output patterns: 
            # - bands.out (new convention: step_type.out)
            # - *.bands.out, *bandspp*.out, *_bands.out (legacy patterns)
            if name == 'bands.out':
                result['bands_out'] = file
            elif '.bands.out' in name or 'bandspp' in name:
                result['bands_out'] = file
            # Also check for bands_pp or bands.pp patterns
            elif 'bands' in name and ('pp' in name or '_pp' in name):
                result['bands_out'] = file
            # SCF/NSCF output
            elif 'nscf' in name:
                result['nscf_out'] = file
            elif 'scf' in name:
                result['scf_out'] = file
    
    return result


def find_dos_files(
    directory: Path | str,
    prefix: str = "",
) -> Dict[str, Optional[Path]]:
    """
    Find DOS related files in a directory.
    
    Args:
        directory: Directory to search
        prefix: Optional prefix filter for files
        
    Returns:
        Dict with keys: 'dos_dat', 'dos_out', 'scf_out', 'nscf_out'
    """
    directory = Path(directory)
    result: Dict[str, Optional[Path]] = {
        'dos_dat': None,
        'dos_out': None,
        'scf_out': None,
        'nscf_out': None,
    }
    
    for file in directory.iterdir():
        name = file.name.lower()
        if prefix and not name.startswith(prefix.lower()):
            continue
        
        if name.endswith('.dos.dat') or 'dos.dat' in name:
            result['dos_dat'] = file
        elif 'dos' in name and name.endswith('.out'):
            result['dos_out'] = file
        elif 'scf' in name and name.endswith('.out'):
            if 'nscf' in name:
                result['nscf_out'] = file
            else:
                result['scf_out'] = file
    
    return result
