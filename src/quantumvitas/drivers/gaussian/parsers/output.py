"""Gaussian output parser: extract energy, convergence, geometry from log files.

Parses Gaussian calculation outputs into a canonical GaussianDigest dataclass.
Primary source: *.log (Gaussian output file).

Registers with the parser registry as ("gaussian", "scf_digest").
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from quantumvitas.parsers.registry import register_parser

logger = logging.getLogger(__name__)


# Conversion factor: 1 Hartree = 27.211386245988 eV
HARTREE_TO_EV = 27.211386245988

# Atomic number to symbol mapping (for Standard orientation parsing)
_ATOMIC_SYMBOLS = {
    1: "H", 2: "He", 3: "Li", 4: "Be", 5: "B", 6: "C", 7: "N", 8: "O",
    9: "F", 10: "Ne", 11: "Na", 12: "Mg", 13: "Al", 14: "Si", 15: "P",
    16: "S", 17: "Cl", 18: "Ar", 19: "K", 20: "Ca", 26: "Fe", 29: "Cu",
    30: "Zn", 35: "Br", 53: "I",
}


@dataclass
class GaussianDigest:
    """Canonical digest of a Gaussian calculation output.

    Attributes:
        success: True if Gaussian terminated normally.
        final_energy_Ha: Final SCF/DFT/MP2 energy in Hartree.
        final_energy_eV: Final energy converted to eV.
        scf_method: Method string from SCF Done (e.g., "RHF", "RB3LYP").
        n_atoms: Number of atoms in the system.
        n_scf_cycles: Number of SCF iterations in final calculation.
        converged_scf: True if SCF converged.
        converged_geometry: True if geometry optimization converged.
        n_opt_steps: Number of optimization steps.
        mp2_energy_Ha: MP2 total energy if applicable.
        e2_correlation_Ha: E2 correlation energy for MP2.
        tddft_states: List of TDDFT excited state dicts.
        frequencies_cm: Vibrational frequencies in cm^-1.
        zpe_Ha: Zero-point energy in Hartree.
        imaginary_freq_count: Number of imaginary frequencies.
        final_species: List of element symbols in final geometry.
        final_cart_coords: Final Cartesian coordinates (Angstrom).
        charge: Molecular charge.
        multiplicity: Spin multiplicity.
        dipole_debye: Dipole moment total in Debye.
        wall_time_s: Elapsed time in seconds (if extractable).
        error_message: Error message if calculation failed.
        n_link1_jobs: Number of Link1 jobs (1 = single job, 2+ = Link1 chain).
    """

    success: bool = False
    final_energy_Ha: Optional[float] = None
    final_energy_eV: Optional[float] = None
    scf_method: Optional[str] = None
    n_atoms: int = 0
    n_scf_cycles: Optional[int] = None
    converged_scf: bool = False
    converged_geometry: Optional[bool] = None
    n_opt_steps: Optional[int] = None
    mp2_energy_Ha: Optional[float] = None
    e2_correlation_Ha: Optional[float] = None
    tddft_states: Optional[List[Dict[str, Any]]] = None
    frequencies_cm: Optional[List[float]] = None
    zpe_Ha: Optional[float] = None
    imaginary_freq_count: Optional[int] = None
    final_species: Optional[List[str]] = None
    final_cart_coords: Optional[List[List[float]]] = None
    charge: Optional[int] = None
    multiplicity: Optional[int] = None
    dipole_debye: Optional[float] = None
    wall_time_s: Optional[float] = None
    error_message: Optional[str] = None
    n_link1_jobs: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to plain dict (JSON-serialisable)."""
        return asdict(self)


@register_parser("gaussian", "scf_digest")
class GaussianOutputParser:
    """Parse Gaussian outputs into a GaussianDigest.

    Looks for *.log files in the directory.
    """

    engine = "gaussian"
    object_type = "scf_digest"

    def can_parse(self, raw_dir: Path) -> bool:
        """Check if the directory contains parseable Gaussian output."""
        for f in raw_dir.glob("*.log"):
            try:
                text = f.read_text(errors="replace")[:2048]
                if "Entering Gaussian System" in text or "Entering Link 1" in text:
                    return True
            except OSError:
                pass
        return False

    def parse(self, raw_dir: Path, **kwargs: Any) -> GaussianDigest:
        """Parse Gaussian output into a GaussianDigest.

        Args:
            raw_dir: Directory containing Gaussian output file(s).

        Returns:
            GaussianDigest with populated fields.
        """
        out_file = self._find_output_file(raw_dir)
        if out_file is None:
            return GaussianDigest(error_message="No Gaussian output file found")

        try:
            text = out_file.read_text(errors="replace")
        except OSError as e:
            return GaussianDigest(error_message=f"Failed to read output: {e}")

        return self._parse_output_text(text)

    def _find_output_file(self, raw_dir: Path) -> Optional[Path]:
        """Find the main Gaussian output file in the directory."""
        for name in ["output.log", "gaussian.log", "calc.log"]:
            candidate = raw_dir / name
            if candidate.is_file():
                return candidate

        log_files = list(raw_dir.glob("*.log"))
        if log_files:
            return log_files[0]
        return None

    def _parse_output_text(self, text: str) -> GaussianDigest:
        """Parse Gaussian output text into a GaussianDigest."""
        digest = GaussianDigest()

        # Count Link1 jobs (number of "Normal termination" lines)
        normal_count = len(re.findall(r"Normal termination of Gaussian", text))
        digest.n_link1_jobs = max(normal_count, 1)

        # Check for normal termination (last job must succeed)
        digest.success = text.rstrip().endswith(
            "Normal termination of Gaussian"
        ) or "Normal termination of Gaussian" in text.split("\n")[-5:]

        # More robust: check last 500 chars for normal termination
        tail = text[-500:]
        if "Normal termination of Gaussian" in tail:
            digest.success = True
        elif "Error termination" in tail:
            digest.success = False
            error_match = re.search(r"Error termination.*", tail)
            if error_match:
                digest.error_message = error_match.group(0).strip()[:500]

        # Extract charge and multiplicity from "Charge = N Multiplicity = M"
        charge_mult = re.search(
            r"Charge\s*=\s*([-\d]+)\s+Multiplicity\s*=\s*(\d+)", text
        )
        if charge_mult:
            digest.charge = int(charge_mult.group(1))
            digest.multiplicity = int(charge_mult.group(2))

        # Extract SCF energy (last occurrence)
        scf_pattern = re.compile(
            r"SCF Done:\s+E\((\w+)\)\s*=\s*([-\d.]+)\s+A\.U\.\s+after\s+(\d+)\s+cycles"
        )
        scf_matches = list(scf_pattern.finditer(text))
        if scf_matches:
            last_scf = scf_matches[-1]
            digest.scf_method = last_scf.group(1)
            digest.final_energy_Ha = float(last_scf.group(2))
            digest.final_energy_eV = digest.final_energy_Ha * HARTREE_TO_EV
            digest.n_scf_cycles = int(last_scf.group(3))
            digest.converged_scf = True

        # Extract MP2 energy (overrides final_energy if present)
        mp2_pattern = re.compile(
            r"E2\s*=\s*([-\dD.+]+)\s+EUMP2\s*=\s*([-\dD.+]+)"
        )
        mp2_match = mp2_pattern.search(text)
        if mp2_match:
            e2_str = mp2_match.group(1).replace("D", "E")
            mp2_str = mp2_match.group(2).replace("D", "E")
            digest.e2_correlation_Ha = float(e2_str)
            digest.mp2_energy_Ha = float(mp2_str)
            digest.final_energy_Ha = digest.mp2_energy_Ha
            digest.final_energy_eV = digest.final_energy_Ha * HARTREE_TO_EV

        # Check optimization convergence
        if "Optimization completed" in text or "Stationary point found" in text:
            digest.converged_geometry = True
        elif "Opt" in text and "SCF Done" in text:
            # Optimization was attempted but may not have converged
            if "Optimization stopped" in text or "Number of steps exceeded" in text:
                digest.converged_geometry = False
            elif scf_matches and len(scf_matches) > 1:
                digest.converged_geometry = None  # unknown

        # Count optimization steps
        if digest.converged_geometry is not None:
            digest.n_opt_steps = len(scf_matches) if scf_matches else 0

        # Extract TDDFT excited states
        td_pattern = re.compile(
            r"Excited State\s+(\d+):\s+(\S+)\s+([\d.]+)\s+eV\s+([\d.]+)\s+nm\s+"
            r"f=([\d.]+)\s+<S\*\*2>=([\d.]+)"
        )
        td_matches = list(td_pattern.finditer(text))
        if td_matches:
            digest.tddft_states = []
            for m in td_matches:
                digest.tddft_states.append({
                    "state": int(m.group(1)),
                    "symmetry": m.group(2),
                    "energy_eV": float(m.group(3)),
                    "wavelength_nm": float(m.group(4)),
                    "oscillator_strength": float(m.group(5)),
                })

        # Extract frequencies
        freq_pattern = re.compile(r"Frequencies\s+--\s+([\d.\s-]+)")
        freq_matches = freq_pattern.findall(text)
        if freq_matches:
            frequencies: List[float] = []
            for match in freq_matches:
                for val in match.split():
                    try:
                        frequencies.append(float(val))
                    except ValueError:
                        continue
            if frequencies:
                digest.frequencies_cm = frequencies
                digest.imaginary_freq_count = sum(
                    1 for f in frequencies if f < 0
                )

        # Extract ZPE
        zpe_match = re.search(
            r"Zero-point correction=\s+([\d.]+)", text
        )
        if zpe_match:
            digest.zpe_Ha = float(zpe_match.group(1))

        # Extract dipole moment total
        dipole_pattern = re.compile(
            r"X=\s*([-\d.]+)\s+Y=\s*([-\d.]+)\s+Z=\s*([-\d.]+)\s+Tot=\s*([-\d.]+)"
        )
        dipole_match = dipole_pattern.search(text)
        if dipole_match:
            digest.dipole_debye = float(dipole_match.group(4))

        # Extract final geometry from Standard orientation
        geom = self._extract_final_geometry(text)
        if geom:
            digest.final_species = geom["species"]
            digest.final_cart_coords = geom["cart_coords"]
            digest.n_atoms = len(geom["species"])

        # Extract elapsed time from "Elapsed time:" line
        elapsed_pattern = re.compile(
            r"Elapsed time:\s+(\d+)\s+days?\s+(\d+)\s+hours?\s+(\d+)\s+minutes?\s+([\d.]+)\s+seconds?"
        )
        elapsed_match = elapsed_pattern.search(text)
        if elapsed_match:
            days = int(elapsed_match.group(1))
            hours = int(elapsed_match.group(2))
            mins = int(elapsed_match.group(3))
            secs = float(elapsed_match.group(4))
            digest.wall_time_s = days * 86400 + hours * 3600 + mins * 60 + secs

        return digest

    def _extract_final_geometry(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract final Cartesian coordinates from Standard orientation block.

        Returns dict with 'species' and 'cart_coords' keys, or None.
        """
        pattern = re.compile(
            r"Standard orientation:.*?-{5,}\n.*?-{5,}\n(.*?)-{5,}",
            re.DOTALL,
        )
        matches = pattern.findall(text)
        if not matches:
            return None

        coord_text = matches[-1]
        species: List[str] = []
        cart_coords: List[List[float]] = []

        for line in coord_text.strip().split("\n"):
            parts = line.split()
            if len(parts) >= 6:
                try:
                    atomic_num = int(parts[1])
                    x, y, z = float(parts[3]), float(parts[4]), float(parts[5])
                    sym = _ATOMIC_SYMBOLS.get(atomic_num, f"X{atomic_num}")
                    species.append(sym)
                    cart_coords.append([x, y, z])
                except ValueError:
                    continue

        if species:
            return {"species": species, "cart_coords": cart_coords}
        return None


def parse_gaussian_output(raw_dir: Path) -> GaussianDigest:
    """Convenience function to parse Gaussian output.

    Args:
        raw_dir: Directory containing Gaussian output file.

    Returns:
        GaussianDigest with parsed results.
    """
    parser = GaussianOutputParser()
    return parser.parse(raw_dir)


def parse_gaussian_output_text(text: str) -> GaussianDigest:
    """Parse Gaussian output text directly.

    Args:
        text: Gaussian output text content.

    Returns:
        GaussianDigest with parsed results.
    """
    parser = GaussianOutputParser()
    return parser._parse_output_text(text)
