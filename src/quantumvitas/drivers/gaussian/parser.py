"""Gaussian output parser.

Parses Gaussian .log files for calculation results.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class GaussianEnergy:
    """Energy result from Gaussian calculation."""
    method: str  # e.g., "RHF", "RB3LYP", "RMP2-FC"
    energy_hartree: float
    scf_cycles: int | None = None


@dataclass
class GaussianOptResult:
    """Geometry optimization result."""
    converged: bool
    n_steps: int
    final_energy_hartree: float
    final_coords: list[dict[str, Any]]  # [{element, x, y, z}, ...]


@dataclass
class GaussianFreqResult:
    """Frequency calculation result."""
    frequencies_cm: list[float]  # in cm^-1
    zpe_hartree: float  # Zero-point energy in Hartree
    thermal_correction_hartree: float
    enthalpy_correction_hartree: float
    gibbs_correction_hartree: float
    imaginary_count: int


@dataclass
class GaussianMP2Result:
    """MP2 calculation result."""
    hf_energy_hartree: float
    mp2_energy_hartree: float
    e2_correlation_hartree: float


@dataclass
class GaussianTDDFTState:
    """Single excited state from TDDFT."""
    state_number: int
    symmetry: str
    energy_eV: float
    wavelength_nm: float
    oscillator_strength: float
    spin_squared: float


def parse_scf_energy(text: str) -> GaussianEnergy | None:
    """Parse final SCF energy from Gaussian log.

    Pattern: SCF Done:  E(RHF) =  -74.9631155184     A.U. after    7 cycles
    """
    pattern = r"SCF Done:\s+E\((\w+)\)\s*=\s*([-\d.]+)\s+A\.U\.\s+after\s+(\d+)\s+cycles"
    matches = list(re.finditer(pattern, text))

    if not matches:
        return None

    # Return the last SCF energy (final value for optimizations)
    m = matches[-1]
    return GaussianEnergy(
        method=m.group(1),
        energy_hartree=float(m.group(2)),
        scf_cycles=int(m.group(3)),
    )


def parse_mp2_energy(text: str) -> GaussianMP2Result | None:
    r"""Parse MP2 energy from Gaussian log.

    Patterns:
    - E2 =    -0.1218324231D+00 EUMP2 =    -0.77194688921108D+02
    - Archive line: HF=-77.0728565\MP2=-77.1946889
    """
    # First get HF energy
    hf = parse_scf_energy(text)
    if not hf:
        return None

    # Parse E2 correlation and MP2 total
    pattern = r"E2\s*=\s*([-\dD.+]+)\s+EUMP2\s*=\s*([-\dD.+]+)"
    m = re.search(pattern, text)

    if not m:
        return None

    # Convert Fortran D notation to E
    e2_str = m.group(1).replace("D", "E")
    mp2_str = m.group(2).replace("D", "E")

    return GaussianMP2Result(
        hf_energy_hartree=hf.energy_hartree,
        mp2_energy_hartree=float(mp2_str),
        e2_correlation_hartree=float(e2_str),
    )


def parse_optimization(text: str) -> GaussianOptResult | None:
    """Parse geometry optimization result.

    Patterns:
    - "Optimization completed."
    - "Stationary point found."
    - Final coordinates from Standard orientation block
    """
    converged = "Optimization completed" in text or "Stationary point found" in text

    # Count optimization steps (number of SCF Done lines)
    scf_matches = re.findall(r"SCF Done:", text)
    n_steps = len(scf_matches)

    # Get final energy
    energy = parse_scf_energy(text)
    if not energy:
        return None

    # Parse final coordinates from last Standard orientation block
    coords = _parse_final_geometry(text)

    return GaussianOptResult(
        converged=converged,
        n_steps=n_steps,
        final_energy_hartree=energy.energy_hartree,
        final_coords=coords,
    )


def _parse_final_geometry(text: str) -> list[dict[str, Any]]:
    """Extract final geometry from Standard orientation block.

    Format:
                         Standard orientation:
    ---------------------------------------------------------------------
    Center     Atomic      Atomic             Coordinates (Angstroms)
    Number     Number       Type             X           Y           Z
    ---------------------------------------------------------------------
         1          8           0        0.000000    0.000000    0.117499
         ...
    ---------------------------------------------------------------------
    """
    # Element number to symbol mapping
    ATOMIC_SYMBOLS = {
        1: "H", 6: "C", 7: "N", 8: "O", 9: "F",
        15: "P", 16: "S", 17: "Cl", 35: "Br", 53: "I",
    }

    # Find all Standard orientation blocks
    pattern = r"Standard orientation:.*?-{5,}\n(.*?)-{5,}"
    matches = list(re.finditer(pattern, text, re.DOTALL))

    if not matches:
        return []

    # Parse last block
    last_block = matches[-1].group(1)
    lines = last_block.strip().split("\n")

    coords = []
    for line in lines:
        parts = line.split()
        if len(parts) >= 6:
            try:
                atomic_num = int(parts[1])
                x, y, z = float(parts[3]), float(parts[4]), float(parts[5])
                element = ATOMIC_SYMBOLS.get(atomic_num, f"X{atomic_num}")
                coords.append({"element": element, "x": x, "y": y, "z": z})
            except ValueError:
                continue

    return coords


def parse_frequencies(text: str) -> GaussianFreqResult | None:
    """Parse frequency calculation results.

    Patterns:
    - Frequencies --   2169.8207              4141.9658              4393.0665
    - Zero-point correction=                           0.024387 (Hartree/Particle)
    - Thermal correction to Energy=                    0.027220
    - Thermal correction to Enthalpy=                  0.028164
    - Thermal correction to Gibbs Free Energy=         0.006650
    """
    # Parse frequencies
    freq_pattern = r"Frequencies\s+--\s+([\d.\s-]+)"
    freq_matches = re.findall(freq_pattern, text)

    frequencies = []
    for match in freq_matches:
        for val in match.split():
            try:
                frequencies.append(float(val))
            except ValueError:
                continue

    if not frequencies:
        return None

    # Count imaginary frequencies (negative values)
    imaginary_count = sum(1 for f in frequencies if f < 0)

    # Parse thermochemistry
    zpe_match = re.search(r"Zero-point correction=\s+([\d.]+)", text)
    thermal_match = re.search(r"Thermal correction to Energy=\s+([\d.]+)", text)
    enthalpy_match = re.search(r"Thermal correction to Enthalpy=\s+([\d.]+)", text)
    gibbs_match = re.search(r"Thermal correction to Gibbs Free Energy=\s+([\d.]+)", text)

    return GaussianFreqResult(
        frequencies_cm=frequencies,
        zpe_hartree=float(zpe_match.group(1)) if zpe_match else 0.0,
        thermal_correction_hartree=float(thermal_match.group(1)) if thermal_match else 0.0,
        enthalpy_correction_hartree=float(enthalpy_match.group(1)) if enthalpy_match else 0.0,
        gibbs_correction_hartree=float(gibbs_match.group(1)) if gibbs_match else 0.0,
        imaginary_count=imaginary_count,
    )


def parse_tddft_states(text: str) -> list[GaussianTDDFTState]:
    """Parse TDDFT excited states.

    Pattern:
    Excited State   1:      Singlet-A2     4.0615 eV  305.26 nm  f=0.0000  <S**2>=0.000
    """
    pattern = (
        r"Excited State\s+(\d+):\s+(\S+)\s+([\d.]+)\s+eV\s+([\d.]+)\s+nm\s+"
        r"f=([\d.]+)\s+<S\*\*2>=([\d.]+)"
    )

    states = []
    for m in re.finditer(pattern, text):
        states.append(GaussianTDDFTState(
            state_number=int(m.group(1)),
            symmetry=m.group(2),
            energy_eV=float(m.group(3)),
            wavelength_nm=float(m.group(4)),
            oscillator_strength=float(m.group(5)),
            spin_squared=float(m.group(6)),
        ))

    return states


def parse_termination_status(text: str) -> tuple[bool, str]:
    """Check if calculation terminated normally.

    Returns:
        (success, message)
    """
    if "Normal termination of Gaussian" in text:
        return True, "Normal termination"

    if "Error termination" in text:
        # Extract error message
        m = re.search(r"Error termination.*", text)
        return False, m.group(0) if m else "Error termination"

    return False, "Unknown termination status"


def parse_dipole_moment(text: str) -> dict[str, float] | None:
    """Parse dipole moment.

    Pattern:
    Dipole moment (field-independent basis, Debye):
       X=              0.0000    Y=              0.0000    Z=             -1.7255  Tot=              1.7255
    """
    pattern = r"X=\s*([-\d.]+)\s+Y=\s*([-\d.]+)\s+Z=\s*([-\d.]+)\s+Tot=\s*([-\d.]+)"
    m = re.search(pattern, text)

    if not m:
        return None

    return {
        "x": float(m.group(1)),
        "y": float(m.group(2)),
        "z": float(m.group(3)),
        "total": float(m.group(4)),
    }


def parse_mulliken_charges(text: str) -> list[dict[str, Any]]:
    """Parse Mulliken atomic charges.

    Pattern:
    Mulliken charges:
                  1
        1  O   -0.365181
        2  H    0.182590
    """
    # Find Mulliken charges block
    pattern = r"Mulliken charges:\s*\n\s+1\s*\n(.*?)(?:Sum of Mulliken|$)"
    m = re.search(pattern, text, re.DOTALL)

    if not m:
        return []

    charges = []
    for line in m.group(1).strip().split("\n"):
        parts = line.split()
        if len(parts) >= 3:
            try:
                idx = int(parts[0])
                element = parts[1]
                charge = float(parts[2])
                charges.append({"index": idx, "element": element, "charge": charge})
            except ValueError:
                continue

    return charges


def parse_archive_line(text: str) -> dict[str, str]:
    r"""Parse the compact archive line at the end of the log.

    Example:
    1\1\GINC-<HOST>\SP\RHF\STO-3G\H2O1\HH7465\04-Feb-2026\0\\#p HF
    /STO-3G\\Water single point energy\\0,1\O,0,0.,0.,0.117499\H,0,0.,0.75
    695,-0.469996\H,0,0.,-0.75695,-0.469996\\Version=EM64M-G09RevD.01\Stat
    e=1-A1\HF=-74.9631155\RMSD=2.136e-10\Dipole=0.,0.,-0.6788622\...
    """
    # Find archive line (starts with 1\1\)
    pattern = r"1\\1\\.*?\\\\@"
    m = re.search(pattern, text, re.DOTALL)

    if not m:
        return {}

    # Clean up line breaks and spaces
    archive = re.sub(r"\s+", "", m.group(0))

    # Parse key=value pairs
    result = {}
    for pair in re.findall(r"(\w+)=([\w.+-]+)", archive):
        result[pair[0]] = pair[1]

    return result


def parse_log_file(path: Path) -> dict[str, Any]:
    """Parse a complete Gaussian log file.

    Returns a dict with all parsed information, keyed by calculation type.
    """
    text = path.read_text()
    result: dict[str, Any] = {}

    # Always parse these
    success, msg = parse_termination_status(text)
    result["normal_termination"] = success
    result["termination_message"] = msg

    # Basic energy
    scf = parse_scf_energy(text)
    if scf:
        result["scf_energy"] = {
            "method": scf.method,
            "energy_hartree": scf.energy_hartree,
            "scf_cycles": scf.scf_cycles,
        }

    # MP2 energy
    mp2 = parse_mp2_energy(text)
    if mp2:
        result["mp2"] = {
            "hf_energy_hartree": mp2.hf_energy_hartree,
            "mp2_energy_hartree": mp2.mp2_energy_hartree,
            "e2_correlation_hartree": mp2.e2_correlation_hartree,
        }

    # Optimization
    if "Optimization completed" in text or "Stationary point found" in text or "Opt" in text:
        opt = parse_optimization(text)
        if opt:
            result["optimization"] = {
                "converged": opt.converged,
                "n_steps": opt.n_steps,
                "final_energy_hartree": opt.final_energy_hartree,
                "final_coords": opt.final_coords,
            }

    # Frequencies
    if "Frequencies" in text:
        freq = parse_frequencies(text)
        if freq:
            result["frequencies"] = {
                "frequencies_cm": freq.frequencies_cm,
                "zpe_hartree": freq.zpe_hartree,
                "thermal_correction_hartree": freq.thermal_correction_hartree,
                "enthalpy_correction_hartree": freq.enthalpy_correction_hartree,
                "gibbs_correction_hartree": freq.gibbs_correction_hartree,
                "imaginary_count": freq.imaginary_count,
            }

    # TDDFT
    states = parse_tddft_states(text)
    if states:
        result["tddft"] = [
            {
                "state": s.state_number,
                "symmetry": s.symmetry,
                "energy_eV": s.energy_eV,
                "wavelength_nm": s.wavelength_nm,
                "oscillator_strength": s.oscillator_strength,
            }
            for s in states
        ]

    # Properties
    dipole = parse_dipole_moment(text)
    if dipole:
        result["dipole_debye"] = dipole

    charges = parse_mulliken_charges(text)
    if charges:
        result["mulliken_charges"] = charges

    # Archive line
    archive = parse_archive_line(text)
    if archive:
        result["archive"] = archive

    return result
