"""VASP output parser: extracts energies, convergence, and metadata from OUTCAR/OSZICAR."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def parse_oszicar(oszicar_path: Path) -> Dict[str, Any]:
    """
    Parse OSZICAR to extract iteration energies.
    
    OSZICAR format:
    DAV:   N    E                  dE             d eps       ncg     rms          rms(c)
    DAV:   1    -0.307508816106E+01   -0.30751E+01   -0.12475E+03   732   0.285E+02
    
    Final line:
      1 F= -.48774144E+01 E0= -.48758836E+01  d E =-.306172E-02
    
    Args:
        oszicar_path: Path to OSZICAR file
    
    Returns:
        Dictionary with:
        - iterations: List of iteration energies
        - final_energy: Final energy (F= value)
        - final_energy_0k: Final energy at 0K (E0= value)
        - converged: Whether calculation converged
    """
    if not oszicar_path.exists():
        return {
            "iterations": [],
            "final_energy": None,
            "final_energy_0k": None,
            "converged": False,
        }
    
    content = oszicar_path.read_text()
    lines = content.strip().split("\n")
    
    iterations = []
    final_energy = None
    final_energy_0k = None
    
    # Parse iterations (DAV: lines)
    dav_pattern = re.compile(r"DAV:\s+\d+\s+(-?\d+\.\d+E[+-]\d+)")
    for line in lines:
        match = dav_pattern.search(line)
        if match:
            energy = float(match.group(1))
            iterations.append(energy)
    
    # Parse final line (F= and E0=)
    # Format: "   1 F= -.48774144E+01 E0= -.48758836E+01  d E =-.306172E-02"
    # Note: The minus sign may be separated by a space: "F= -.48774144E+01"
    # Match: F= followed by optional space, then minus, then optional space, then number
    # Note: Number may start with decimal point (e.g., .48774144E+01)
    final_pattern = re.compile(r"F=\s*-\s*(\d*\.\d+E[+-]\d+).*?E0=\s*-\s*(\d*\.\d+E[+-]\d+)")
    for line in lines:
        match = final_pattern.search(line)
        if match:
            # Add minus sign back (it's not captured in the group)
            final_energy_str = "-" + match.group(1)
            final_energy_0k_str = "-" + match.group(2)
            final_energy = float(final_energy_str)
            final_energy_0k = float(final_energy_0k_str)
            break
    
    # Convergence: if we have a final energy, the calculation completed and is considered converged
    # The final energy (F=) is the converged energy, distinct from iteration energies (DAV:)
    converged = final_energy is not None
    
    return {
        "iterations": iterations,
        "final_energy": final_energy,
        "final_energy_0k": final_energy_0k,
        "converged": converged,
    }


def parse_outcar(outcar_path: Path) -> Dict[str, Any]:
    """
    Parse OUTCAR to extract final energy, forces, and metadata.
    
    Key patterns:
    - "FREE ENERGIE OF THE ION-ELECTRON SYSTEM": TOTEN
    - "energy without entropy": Final energy
    - "energy(sigma->0)": Energy at 0K
    - "Total CPU time used": Walltime
    
    Args:
        outcar_path: Path to OUTCAR file
    
    Returns:
        Dictionary with:
        - total_energy: TOTEN (free energy)
        - energy_without_entropy: Energy without entropy
        - energy_sigma_0: Energy at sigma->0
        - walltime: Walltime in seconds
        - converged: Whether calculation converged (based on forces)
    """
    if not outcar_path.exists():
        return {
            "total_energy": None,
            "energy_without_entropy": None,
            "energy_sigma_0": None,
            "walltime": None,
            "converged": False,
        }
    
    content = outcar_path.read_text()
    
    # Find TOTEN
    toten_pattern = re.compile(r"free\s+energy\s+TOTEN\s*=\s*(-?\d+\.\d+)", re.IGNORECASE)
    toten_match = toten_pattern.search(content)
    total_energy = float(toten_match.group(1)) if toten_match else None
    
    # Find final energy without entropy (last occurrence)
    energy_pattern = re.compile(
        r"energy\s+without\s+entropy=\s*(-?\d+\.\d+)\s+energy\(sigma->0\)\s*=\s*(-?\d+\.\d+)",
        re.IGNORECASE
    )
    energy_matches = list(energy_pattern.finditer(content))
    energy_without_entropy = None
    energy_sigma_0 = None
    if energy_matches:
        last_match = energy_matches[-1]
        energy_without_entropy = float(last_match.group(1))
        energy_sigma_0 = float(last_match.group(2))
    
    # Find walltime
    walltime_pattern = re.compile(r"Elapsed\s+time\s*\(sec\):\s*(\d+\.\d+)", re.IGNORECASE)
    walltime_match = walltime_pattern.search(content)
    walltime = float(walltime_match.group(1)) if walltime_match else None
    
    # Convergence: check if forces are small (simplified check)
    # Look for "total drift" near the end
    converged = False
    # Format: "    total drift:                               -0.000000     -0.000000      0.000000"
    drift_pattern = re.compile(r"total\s+drift:\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)", re.IGNORECASE)
    drift_matches = list(drift_pattern.finditer(content))
    if drift_matches:
        last_drift = drift_matches[-1]
        max_drift = max(
            abs(float(last_drift.group(1))),
            abs(float(last_drift.group(2))),
            abs(float(last_drift.group(3))),
        )
        converged = max_drift < 0.01  # Threshold for convergence
    
    return {
        "total_energy": total_energy,
        "energy_without_entropy": energy_without_entropy,
        "energy_sigma_0": energy_sigma_0,
        "walltime": walltime,
        "converged": converged,
    }


def parse_vasp_output(workdir: Path) -> Dict[str, Any]:
    """
    Parse VASP output files (OUTCAR and OSZICAR) to extract calculation results.
    
    Priority: OSZICAR (fast, iteration energies) > OUTCAR (comprehensive, final energy)
    
    Args:
        workdir: Working directory containing OUTCAR and OSZICAR
    
    Returns:
        Dictionary with parsed results:
        - success: Whether calculation completed successfully
        - energy: Final energy (eV)
        - converged: Whether calculation converged
        - walltime: Walltime in seconds
        - iterations: Number of iterations
    """
    oszicar_path = workdir / "OSZICAR"
    outcar_path = workdir / "OUTCAR"
    
    oszicar_data = parse_oszicar(oszicar_path)
    outcar_data = parse_outcar(outcar_path)
    
    # Determine success: at least one file exists and has data
    success = (
        (oszicar_path.exists() and oszicar_data["final_energy"] is not None) or
        (outcar_path.exists() and outcar_data["total_energy"] is not None)
    )
    
    # Get energy (prefer OUTCAR TOTEN, fallback to OSZICAR final_energy)
    energy = outcar_data["total_energy"]
    if energy is None:
        energy = oszicar_data["final_energy"]
    
    # Convergence: prefer OUTCAR, fallback to OSZICAR
    converged = outcar_data["converged"]
    if not converged:
        converged = oszicar_data["converged"]
    
    # Walltime from OUTCAR
    walltime = outcar_data["walltime"]
    
    # Iterations from OSZICAR
    iterations = len(oszicar_data["iterations"])
    
    return {
        "success": success,
        "energy": energy,
        "converged": converged,
        "walltime": walltime,
        "iterations": iterations,
        "oszicar": oszicar_data,
        "outcar": outcar_data,
    }


def parse_eigenval(eigenval_path: Path) -> Dict[str, Any]:
    """
    Parse EIGENVAL to extract band structure data.
    
    EIGENVAL format:
    - Header: n_ions, n_atoms, p00, n_kpoints, n_bands
    - For each k-point: k-point coordinates, weight, then eigenvalues
    
    Args:
        eigenval_path: Path to EIGENVAL file
    
    Returns:
        Dictionary with:
        - kpoints: List of k-point coordinates (3D vectors)
        - bands: List of band eigenvalues (shape: [n_kpoints, n_bands])
        - efermi: Fermi energy (if available)
        - n_kpoints: Number of k-points
        - n_bands: Number of bands
    """
    if not eigenval_path.exists():
        return {
            "kpoints": [],
            "bands": [],
            "efermi": None,
            "n_kpoints": 0,
            "n_bands": 0,
        }
    
    content = eigenval_path.read_text()
    lines = content.strip().split("\n")
    
    # Parse header (line 5)
    # Format: "      n_ions   n_atoms   p00   n_kpoints   n_bands" (5 numbers)
    # OR: "      n_ions   n_atoms   p00" (3 numbers, then n_kpoints and n_bands on next line)
    # OR: "      n_ions   n_kpoints   n_bands" (3 numbers, simplified format)
    if len(lines) < 6:
        return {
            "kpoints": [],
            "bands": [],
            "efermi": None,
            "n_kpoints": 0,
            "n_bands": 0,
        }
    
    try:
        header_parts = lines[5].split()
        if len(header_parts) >= 5:
            # Full format: n_ions, n_atoms, p00, n_kpoints, n_bands
            n_kpoints = int(header_parts[3])
            n_bands = int(header_parts[4])
        elif len(header_parts) >= 3:
            # Simplified format: n_ions, n_kpoints, n_bands (or n_ions, n_atoms, p00)
            # Try to interpret: if second number is large (>10), it's likely n_kpoints
            if int(header_parts[1]) > 10:
                n_kpoints = int(header_parts[1])
                n_bands = int(header_parts[2])
            else:
                # Need to check next line or use defaults
                # For now, assume format: n_ions, n_atoms, p00, and n_kpoints/n_bands are elsewhere
                # Check line 6 for continuation
                if len(lines) > 6 and lines[6].strip():
                    next_parts = lines[6].split()
                    if len(next_parts) >= 2:
                        n_kpoints = int(next_parts[0])
                        n_bands = int(next_parts[1])
                    else:
                        raise ValueError("Cannot determine n_kpoints and n_bands")
                else:
                    raise ValueError("Cannot determine n_kpoints and n_bands")
        else:
            raise ValueError("Invalid header format")
    except (IndexError, ValueError) as e:
        logger.warning(f"Failed to parse EIGENVAL header: {e}")
        return {
            "kpoints": [],
            "bands": [],
            "efermi": None,
            "n_kpoints": 0,
            "n_bands": 0,
        }
    
    # Parse k-points and eigenvalues
    kpoints = []
    bands = []
    line_idx = 6  # Start after header (skip empty line if present)
    
    while line_idx < len(lines) and len(kpoints) < n_kpoints:
        # Skip empty lines
        if not lines[line_idx].strip():
            line_idx += 1
            continue
        
        # K-point line: "   0.00000000   0.00000000   0.00000000     1.00000000"
        k_line = lines[line_idx].strip()
        k_parts = k_line.split()
        if len(k_parts) >= 3:
            try:
                k_coords = [float(k_parts[0]), float(k_parts[1]), float(k_parts[2])]
                kpoints.append(k_coords)
                
                # Next n_bands lines are eigenvalues
                eigenvalues = []
                for i in range(n_bands):
                    line_idx += 1
                    if line_idx >= len(lines):
                        break
                    band_line = lines[line_idx].strip()
                    # Format: "     1     -10.12345678"
                    band_parts = band_line.split()
                    if len(band_parts) >= 2:
                        try:
                            eigenvalue = float(band_parts[1])
                            eigenvalues.append(eigenvalue)
                        except (ValueError, IndexError):
                            break
                
                if len(eigenvalues) == n_bands:
                    bands.append(eigenvalues)
                
                line_idx += 1
            except (ValueError, IndexError):
                line_idx += 1
                continue
        else:
            line_idx += 1
    
    # Try to find Fermi energy (may be in a comment or separate line)
    efermi = None
    efermi_pattern = re.compile(r"E-fermi\s*[:=]\s*(-?\d+\.\d+)", re.IGNORECASE)
    for line in lines:
        match = efermi_pattern.search(line)
        if match:
            efermi = float(match.group(1))
            break
    
    return {
        "kpoints": kpoints,
        "bands": bands,
        "efermi": efermi,
        "n_kpoints": len(kpoints),
        "n_bands": n_bands,
    }


def parse_doscar(doscar_path: Path) -> Dict[str, Any]:
    """
    Parse DOSCAR to extract density of states data.
    
    DOSCAR format:
    - Line 1: n_ions, volume, lattice_vectors
    - Line 2-6: Header info
    - Line 7+: DOS data (energy, total_dos, integrated_dos, [projected_dos...])
    
    Args:
        doscar_path: Path to DOSCAR file
    
    Returns:
        Dictionary with:
        - energies: List of energy values (eV)
        - dos: List of total DOS values
        - integrated_dos: List of integrated DOS values
        - efermi: Fermi energy
        - n_dos_points: Number of DOS points
    """
    if not doscar_path.exists():
        return {
            "energies": [],
            "dos": [],
            "integrated_dos": [],
            "efermi": None,
            "n_dos_points": 0,
        }
    
    content = doscar_path.read_text()
    lines = content.strip().split("\n")
    
    if len(lines) < 6:
        return {
            "energies": [],
            "dos": [],
            "integrated_dos": [],
            "efermi": None,
            "n_dos_points": 0,
        }
    
    # Parse header (line 5): "   n_dos_points   efermi   e_max   e_min"
    try:
        header_parts = lines[5].split()
        n_dos_points = int(header_parts[2])
        efermi = float(header_parts[3])
    except (IndexError, ValueError):
        return {
            "energies": [],
            "dos": [],
            "integrated_dos": [],
            "efermi": None,
            "n_dos_points": 0,
        }
    
    # Parse DOS data (starting from line 6)
    energies = []
    dos = []
    integrated_dos = []
    
    for i in range(6, min(6 + n_dos_points, len(lines))):
        line = lines[i].strip()
        parts = line.split()
        if len(parts) >= 3:
            try:
                energy = float(parts[0])
                total_dos = float(parts[1])
                int_dos = float(parts[2])
                
                energies.append(energy)
                dos.append(total_dos)
                integrated_dos.append(int_dos)
            except (ValueError, IndexError):
                continue
    
    return {
        "energies": energies,
        "dos": dos,
        "integrated_dos": integrated_dos,
        "efermi": efermi,
        "n_dos_points": len(energies),
    }

