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

