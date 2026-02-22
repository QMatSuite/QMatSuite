"""ABINIT output parser: .abo text digest.

Parses ABINIT calculation outputs into a canonical ABINITDigest dataclass.
Primary source: .abo text file (regex on structured YAML blocks + ETOT lines).

Registers with the parser registry as ("abinit", "scf_digest").

Stdlib only — no kernel imports except qmatsuite.parsers.registry.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from qmatsuite.parsers.registry import register_parser

logger = logging.getLogger(__name__)

# ABINIT energy unit: 1 Ha = 27.211386245988 eV
_HA_TO_EV = 27.211386245988


@dataclass
class ABINITDigest:
    """Canonical digest of an ABINIT calculation output."""

    final_energy_eV: Optional[float] = None
    energy_per_atom_eV: Optional[float] = None
    n_atoms: int = 0
    converged_electronic: bool = False
    converged_ionic: bool = False
    n_ionic_steps: int = 0
    n_electronic_steps: int = 0
    n_datasets: int = 1
    final_lattice: Optional[list[list[float]]] = None
    final_frac_coords: Optional[list[list[float]]] = None
    volume_A3: Optional[float] = None
    max_force_eV_A: Optional[float] = None
    pressure_GPa: Optional[float] = None
    total_magnetization: Optional[float] = None
    fermi_energy_eV: Optional[float] = None
    elapsed_time_s: Optional[float] = None
    abinit_version: Optional[str] = None
    calculation_type: Optional[str] = None
    n_warnings: int = 0
    n_comments: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to plain dict (JSON-serialisable)."""
        return asdict(self)


@register_parser("abinit", "scf_digest")
class ABINITOutputParser:
    """Parse ABINIT outputs into an ABINITDigest.

    Looks for *.abo files in the raw directory.
    """

    engine = "abinit"
    object_type = "scf_digest"

    def can_parse(self, raw_dir: Path) -> bool:
        """Check if the directory contains parseable ABINIT output."""
        return any(raw_dir.glob("*.abo"))

    def parse(self, raw_dir: Path, **kwargs: Any) -> ABINITDigest:
        """Parse ABINIT output into an ABINITDigest."""
        abo_files = sorted(raw_dir.glob("*.abo"))
        if not abo_files:
            logger.warning("No .abo files found in %s", raw_dir)
            return ABINITDigest()

        # Use the first (or only) .abo file
        text = abo_files[0].read_text(errors="replace")
        return self._parse_abo_text(text)

    def _parse_abo_text(self, text: str) -> ABINITDigest:
        """Parse .abo file text into digest."""
        digest = ABINITDigest()

        # Version
        digest.abinit_version = _parse_version(text)

        # Calculation type
        digest.calculation_type = _detect_calc_type(text)

        # Number of datasets
        m = re.search(r"ndtset\s+(\d+)", text)
        digest.n_datasets = int(m.group(1)) if m else 1

        # SCF iterations (ETOT lines)
        etot_lines = re.findall(
            r"ETOT\s+(\d+)\s+([-\d.E+]+)", text
        )
        digest.n_electronic_steps = len(etot_lines)

        # Number of atoms
        m = re.search(r"natom\s+(\d+)", text)
        if m:
            digest.n_atoms = int(m.group(1))

        # Total energy from ResultsGS YAML block
        energy_ha = _parse_etotal(text)
        if energy_ha is not None:
            digest.final_energy_eV = energy_ha * _HA_TO_EV
            if digest.n_atoms > 0:
                digest.energy_per_atom_eV = digest.final_energy_eV / digest.n_atoms

        # Fermi energy
        m = re.search(r"fermie\s*:\s*([-\d.E+]+)", text)
        if m:
            digest.fermi_energy_eV = float(m.group(1)) * _HA_TO_EV

        # Pressure
        m = re.search(r"pressure_GPa\s*:\s*([-\d.E+]+)", text)
        if m:
            digest.pressure_GPa = float(m.group(1))

        # Forces (from ResultsGS block)
        forces = _parse_forces(text)
        if forces:
            # Convert max force from Ha/Bohr to eV/Angstrom
            # 1 Ha/Bohr = 51.42206313 eV/Angstrom
            ha_bohr_to_ev_ang = _HA_TO_EV / 0.529177249
            max_f = max(
                (sum(f ** 2 for f in atom) ** 0.5 for atom in forces),
                default=0.0,
            )
            digest.max_force_eV_A = max_f * ha_bohr_to_ev_ang

        # Convergence
        convergence = _parse_convergence(text)
        digest.converged_electronic = convergence.get("electronic", False)
        digest.converged_ionic = convergence.get("ionic", False)
        digest.n_ionic_steps = convergence.get("n_ionic", 0)

        # Final structure (from post-computation echo)
        struct = _parse_final_structure(text)
        if struct:
            digest.final_lattice = struct.get("lattice")
            digest.final_frac_coords = struct.get("frac_coords")
            digest.volume_A3 = struct.get("volume")

        # Timing
        m = re.search(
            r"\+Overall time at end \(sec\)\s*:\s*cpu=\s*[\d.]+\s+wall=\s*([\d.]+)",
            text,
        )
        if m:
            digest.elapsed_time_s = float(m.group(1))

        # Warnings and comments
        m = re.search(
            r"\.Delivered\s+(\d+)\s+WARNINGs?\s+and\s+(\d+)\s+COMMENTs?", text
        )
        if m:
            digest.n_warnings = int(m.group(1))
            digest.n_comments = int(m.group(2))

        return digest


# ── Helper functions (pure text parsing, no state) ───────────────────


def _parse_version(text: str) -> Optional[str]:
    m = re.search(r"\.Version\s+([\d.]+[^\s]*)\s+of ABINIT", text)
    return m.group(1) if m else None


def _detect_calc_type(text: str) -> str:
    """Detect calculation type from echoed input variables."""
    m = re.search(r"ionmov\s+(\d+)", text)
    if m:
        ionmov = int(m.group(1))
        if ionmov in (2, 3, 4, 5, 7, 10, 11, 20, 22):
            optcell_m = re.search(r"optcell\s+(\d+)", text)
            if optcell_m and int(optcell_m.group(1)) > 0:
                return "vc_relax"
            return "relax"
        if ionmov in (1, 6, 8, 9, 12, 13, 14, 23):
            return "md"

    m = re.search(r"iscf\s+(-?\d+)", text)
    if m and int(m.group(1)) < 0:
        return "nscf"

    m = re.search(r"optdriver\s+(\d+)", text)
    if m:
        od = int(m.group(1))
        return {1: "dfpt", 3: "screening", 4: "sigma", 7: "eph"}.get(od, "scf")

    return "scf"


def _parse_etotal(text: str) -> Optional[float]:
    """Extract total energy in Hartree from the output."""
    # Prefer the ResultsGS YAML block
    m = re.search(r"etotal\s*:\s*([-\d.E+]+)", text)
    if m:
        return float(m.group(1))

    # Fallback: last etotal line in echoed output
    m = re.search(
        r"-outvars: echo values of variables after computation.*?etotal\s+([-\d.E+]+)",
        text,
        re.DOTALL,
    )
    if m:
        return float(m.group(1))

    # Last resort: final ETOT line
    matches = list(re.finditer(r"ETOT\s+\d+\s+([-\d.E+]+)", text))
    if matches:
        return float(matches[-1].group(1))

    return None


def _parse_forces(text: str) -> Optional[list[list[float]]]:
    """Extract Cartesian forces from ResultsGS block (Ha/Bohr)."""
    m = re.search(
        r"cartesian_forces:.*?\n((?:\s*-\s*\[.*?\]\n)+)", text, re.DOTALL
    )
    if not m:
        return None

    forces = []
    for line in m.group(1).strip().split("\n"):
        nums = re.findall(r"[-+]?\d+\.?\d*[Ee]?[-+]?\d*", line)
        valid = [float(n) for n in nums if n and n not in ("-", "+")]
        if len(valid) >= 3:
            forces.append(valid[:3])
    return forces or None


def _parse_convergence(text: str) -> dict[str, Any]:
    """Determine convergence status."""
    result: dict[str, Any] = {"electronic": False, "ionic": False, "n_ionic": 0}

    # Electronic convergence: check for "At SCF step" with convergence
    if re.search(r"At SCF step.*,\s*etot is converged", text):
        result["electronic"] = True
    # Also check if calculation completed normally (Delivered ... WARNINGs)
    elif re.search(r"\.Delivered\s+\d+\s+WARNINGs?", text):
        result["electronic"] = True

    # Ionic convergence
    hist_matches = list(re.finditer(r"Iteration:\s+(\d+)", text))
    if hist_matches:
        result["n_ionic"] = int(hist_matches[-1].group(1))
    if re.search(r"Relaxation converged", text, re.IGNORECASE):
        result["ionic"] = True
    elif re.search(r"ionmov\s+(\d+)", text):
        # If relaxation was requested and completed, check tolerances
        if re.search(r"\.Delivered", text) and result["n_ionic"] > 0:
            result["ionic"] = True

    return result


def _parse_final_structure(text: str) -> Optional[dict[str, Any]]:
    """Parse final structure from post-computation echo."""
    m = re.search(
        r"-outvars: echo values of variables after computation(.*)", text, re.DOTALL
    )
    if not m:
        return None

    block = m.group(1)
    result: dict[str, Any] = {}

    # acell
    m = re.search(r"acell\s+([-\d.E+]+)\s+([-\d.E+]+)\s+([-\d.E+]+)", block)
    if not m:
        return None

    acell = [float(m.group(i)) for i in range(1, 4)]

    # rprim
    m = re.search(
        r"rprim\s+([-\d.E+]+)\s+([-\d.E+]+)\s+([-\d.E+]+)\s+"
        r"([-\d.E+]+)\s+([-\d.E+]+)\s+([-\d.E+]+)\s+"
        r"([-\d.E+]+)\s+([-\d.E+]+)\s+([-\d.E+]+)",
        block,
    )
    if m:
        rprim = [
            [float(m.group(i)) for i in range(1, 4)],
            [float(m.group(i)) for i in range(4, 7)],
            [float(m.group(i)) for i in range(7, 10)],
        ]
        # Scale by acell to get real-space lattice (in Bohr)
        lattice_bohr = [
            [rprim[i][j] * acell[i] for j in range(3)]
            for i in range(3)
        ]
        # Convert to Angstrom
        bohr_to_ang = 0.529177249
        result["lattice"] = [
            [v * bohr_to_ang for v in row] for row in lattice_bohr
        ]

        # Volume in Angstrom^3
        a, b, c = result["lattice"]
        vol = abs(
            a[0] * (b[1] * c[2] - b[2] * c[1])
            - a[1] * (b[0] * c[2] - b[2] * c[0])
            + a[2] * (b[0] * c[1] - b[1] * c[0])
        )
        result["volume"] = vol

    # xred
    xred_m = re.search(r"xred\s+((?:[-\d.E+]+\s+[-\d.E+]+\s+[-\d.E+]+\s*)+)", block)
    if xred_m:
        nums = re.findall(r"[-\d.E+]+", xred_m.group(1))
        frac_coords = []
        for i in range(0, len(nums), 3):
            if i + 2 < len(nums):
                frac_coords.append([float(nums[i]), float(nums[i + 1]), float(nums[i + 2])])
        result["frac_coords"] = frac_coords

    return result if result else None
