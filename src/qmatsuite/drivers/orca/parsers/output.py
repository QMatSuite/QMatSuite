"""ORCA output parser: extract energy, convergence, geometry from ORCA output files.

Parses ORCA calculation outputs into a canonical ORCADigest dataclass.
Primary source: *.out (ORCA output file).

Registers with the parser registry as ("orca", "scf_digest").
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from qmatsuite.parsers.registry import register_parser

logger = logging.getLogger(__name__)


@dataclass
class ORCADigest:
    """Canonical digest of an ORCA calculation output.

    Attributes:
        success: True if ORCA terminated normally.
        final_energy_Ha: Final single-point energy in Hartree.
        final_energy_eV: Final energy converted to eV.
        n_atoms: Number of atoms in the system.
        n_scf_cycles: Number of SCF iterations in final calculation.
        converged_scf: True if SCF converged.
        converged_geometry: True if geometry optimization converged (HURRAY).
        n_opt_cycles: Number of geometry optimization cycles.
        final_species: List of element symbols in final geometry.
        final_cart_coords: Final Cartesian coordinates (Angstrom).
        wall_time_s: Total wall time in seconds.
        error_message: Error message if calculation failed.
        charge: Molecular charge.
        multiplicity: Spin multiplicity.
    """

    success: bool = False
    final_energy_Ha: Optional[float] = None
    final_energy_eV: Optional[float] = None
    n_atoms: int = 0
    n_scf_cycles: Optional[int] = None
    converged_scf: bool = False
    converged_geometry: Optional[bool] = None
    n_opt_cycles: Optional[int] = None
    final_species: Optional[List[str]] = None
    final_cart_coords: Optional[List[List[float]]] = None
    wall_time_s: Optional[float] = None
    error_message: Optional[str] = None
    charge: Optional[int] = None
    multiplicity: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to plain dict (JSON-serialisable)."""
        return asdict(self)


# Conversion factor: 1 Hartree = 27.211386245988 eV
HARTREE_TO_EV = 27.211386245988


@register_parser("orca", "scf_digest")
class ORCAOutputParser:
    """Parse ORCA outputs into an ORCADigest.

    Looks for *.out files in the directory.
    """

    engine = "orca"
    object_type = "scf_digest"

    def can_parse(self, raw_dir: Path) -> bool:
        """Check if the directory contains parseable ORCA output."""
        # Look for any .out file that contains ORCA markers
        for f in raw_dir.glob("*.out"):
            try:
                # Read first 1KB to check for ORCA markers
                text = f.read_text(errors="replace")[:1024]
                if "O   R   C   A" in text or "ORCA" in text:
                    return True
            except OSError:
                pass
        return False

    def parse(self, raw_dir: Path, **kwargs: Any) -> ORCADigest:
        """Parse ORCA output into an ORCADigest.

        Args:
            raw_dir: Directory containing ORCA output file(s).

        Returns:
            ORCADigest with populated fields.
        """
        # Find ORCA output file
        out_file = self._find_output_file(raw_dir)
        if out_file is None:
            return ORCADigest(error_message="No ORCA output file found")

        try:
            text = out_file.read_text(errors="replace")
        except OSError as e:
            return ORCADigest(error_message=f"Failed to read output: {e}")

        return self._parse_output_text(text)

    def _find_output_file(self, raw_dir: Path) -> Optional[Path]:
        """Find the main ORCA output file in the directory."""
        # Try common names first
        for name in ["orca.out", "orca_calc.out", "output.out"]:
            candidate = raw_dir / name
            if candidate.is_file():
                return candidate

        # Fall back to any .out file
        out_files = list(raw_dir.glob("*.out"))
        if out_files:
            return out_files[0]

        return None

    def _parse_output_text(self, text: str) -> ORCADigest:
        """Parse ORCA output text into an ORCADigest."""
        digest = ORCADigest()

        # Check for normal termination
        digest.success = "****ORCA TERMINATED NORMALLY****" in text

        # Check for errors
        if "ORCA finished by error termination" in text:
            digest.success = False
            # Try to extract error message
            error_match = re.search(r"ORCA TERMINATED ABNORMALLY.*?(?=\n\n|\Z)", text, re.DOTALL)
            if error_match:
                digest.error_message = error_match.group(0).strip()[:500]

        # Extract final energy
        # Pattern: FINAL SINGLE POINT ENERGY     -76.359831578643
        energy_pattern = re.compile(
            r"FINAL SINGLE POINT ENERGY\s+([-\d.]+)"
        )
        energy_matches = energy_pattern.findall(text)
        if energy_matches:
            try:
                digest.final_energy_Ha = float(energy_matches[-1])
                digest.final_energy_eV = digest.final_energy_Ha * HARTREE_TO_EV
            except ValueError:
                pass

        # Extract SCF cycle count
        # Pattern: *                     SCF CONVERGED AFTER   N CYCLES                     *
        scf_pattern = re.compile(
            r"SCF CONVERGED AFTER\s+(\d+)\s+CYCLES"
        )
        scf_matches = scf_pattern.findall(text)
        if scf_matches:
            try:
                digest.n_scf_cycles = int(scf_matches[-1])
                digest.converged_scf = True
            except ValueError:
                pass

        # Check for SCF convergence failure
        if "SCF NOT CONVERGED" in text:
            digest.converged_scf = False

        # Check for geometry optimization convergence
        # Pattern: *                HURRAY - THE OPTIMIZATION HAS CONVERGED                 *
        if "HURRAY" in text and "OPTIMIZATION HAS CONVERGED" in text:
            digest.converged_geometry = True
        elif "GEOMETRY OPTIMIZATION" in text:
            # Optimization was attempted
            digest.converged_geometry = False

        # Extract optimization cycle count
        # Pattern: GEOMETRY OPTIMIZATION CYCLE  N
        opt_pattern = re.compile(
            r"GEOMETRY OPTIMIZATION CYCLE\s+(\d+)"
        )
        opt_matches = opt_pattern.findall(text)
        if opt_matches:
            try:
                digest.n_opt_cycles = int(opt_matches[-1])
            except ValueError:
                pass

        # Extract wall time
        # Pattern: Total run time: 0 days 0 hours 0 min 3 sec
        time_pattern = re.compile(
            r"Total run time:\s*(\d+)\s*days?\s*(\d+)\s*hours?\s*(\d+)\s*min\s*(\d+)\s*sec"
        )
        time_match = time_pattern.search(text)
        if time_match:
            days, hours, mins, secs = map(int, time_match.groups())
            digest.wall_time_s = days * 86400 + hours * 3600 + mins * 60 + secs

        # Extract charge and multiplicity
        # Pattern: Total Charge           Charge          ....     0
        #          Multiplicity           Mult            ....     1
        charge_pattern = re.compile(r"Total Charge\s+.*?(\d+)")
        mult_pattern = re.compile(r"Multiplicity\s+.*?(\d+)")
        charge_match = charge_pattern.search(text)
        mult_match = mult_pattern.search(text)
        if charge_match:
            try:
                digest.charge = int(charge_match.group(1))
            except ValueError:
                pass
        if mult_match:
            try:
                digest.multiplicity = int(mult_match.group(1))
            except ValueError:
                pass

        # Extract final geometry from optimization
        # Look for "CARTESIAN COORDINATES (ANGSTROEM)" section
        coords = self._extract_final_geometry(text)
        if coords:
            digest.final_species = coords["species"]
            digest.final_cart_coords = coords["cart_coords"]
            digest.n_atoms = len(coords["species"])

        return digest

    def _extract_final_geometry(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract final Cartesian coordinates from ORCA output.

        Returns dict with 'species' and 'cart_coords' keys, or None.
        """
        # Find all CARTESIAN COORDINATES blocks, take the last one
        pattern = re.compile(
            r"CARTESIAN COORDINATES \(ANGSTROEM\)\s*\n"
            r"-+\s*\n"
            r"((?:\s*\S+\s+[-\d.]+\s+[-\d.]+\s+[-\d.]+\s*\n)+)"
        )
        matches = pattern.findall(text)
        if not matches:
            return None

        # Parse the last geometry block
        coord_text = matches[-1]
        species = []
        cart_coords = []

        for line in coord_text.strip().split("\n"):
            parts = line.split()
            if len(parts) >= 4:
                try:
                    species.append(parts[0])
                    cart_coords.append([
                        float(parts[1]),
                        float(parts[2]),
                        float(parts[3]),
                    ])
                except ValueError:
                    continue

        if species:
            return {"species": species, "cart_coords": cart_coords}
        return None


def parse_orca_output(raw_dir: Path) -> ORCADigest:
    """Convenience function to parse ORCA output.

    Args:
        raw_dir: Directory containing ORCA output file.

    Returns:
        ORCADigest with parsed results.
    """
    parser = ORCAOutputParser()
    return parser.parse(raw_dir)


def parse_orca_output_text(text: str) -> ORCADigest:
    """Parse ORCA output text directly.

    Args:
        text: ORCA output text content.

    Returns:
        ORCADigest with parsed results.
    """
    parser = ORCAOutputParser()
    return parser._parse_output_text(text)
