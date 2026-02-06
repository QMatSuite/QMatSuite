"""LAMMPS output parser: extract thermo, convergence, timing from log.lammps.

Parses LAMMPS calculation outputs into a canonical LAMMPSDigest dataclass.
Primary source: log.lammps.

Registers with the parser registry as ("lammps", "scf_digest").
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from quantumvitas.parsers.registry import register_parser

logger = logging.getLogger(__name__)


@dataclass
class LAMMPSDigest:
    """Canonical digest of a LAMMPS calculation output.

    Attributes:
        success: True if LAMMPS completed without errors.
        final_energy: TotEng from last thermo line (units-dependent).
        final_temp: Temperature from last thermo line.
        final_pressure: Pressure from last thermo line.
        final_e_pair: Pair energy from last thermo line.
        n_atoms: Number of atoms in the system.
        n_steps: Total steps executed (from Loop time line).
        wall_time_s: Total wall time in seconds.
        units: Unit system (lj, real, metal, etc.).
        converged_minimize: True if minimization converged.
        minimize_criterion: Stopping criterion string.
        minimize_energy_initial: Initial energy for minimization.
        minimize_energy_final: Final energy for minimization.
        minimize_iterations: Number of minimizer iterations.
        minimize_force_evaluations: Number of force evaluations.
        error_message: Error message if calculation failed.
    """

    success: bool = False
    final_energy: Optional[float] = None
    final_temp: Optional[float] = None
    final_pressure: Optional[float] = None
    final_e_pair: Optional[float] = None
    n_atoms: Optional[int] = None
    n_steps: Optional[int] = None
    wall_time_s: Optional[float] = None
    units: Optional[str] = None
    converged_minimize: Optional[bool] = None
    minimize_criterion: Optional[str] = None
    minimize_energy_initial: Optional[float] = None
    minimize_energy_final: Optional[float] = None
    minimize_iterations: Optional[int] = None
    minimize_force_evaluations: Optional[int] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to plain dict (JSON-serialisable)."""
        return asdict(self)


@register_parser("lammps", "scf_digest")
class LAMMPSOutputParser:
    """Parse LAMMPS outputs into a LAMMPSDigest.

    Looks for log.lammps in the directory.
    """

    engine = "lammps"
    object_type = "scf_digest"

    def can_parse(self, raw_dir: Path) -> bool:
        """Check if the directory contains parseable LAMMPS output."""
        return (raw_dir / "log.lammps").is_file()

    def parse(self, raw_dir: Path, **kwargs: Any) -> LAMMPSDigest:
        """Parse LAMMPS output into a LAMMPSDigest.

        Args:
            raw_dir: Directory containing log.lammps.

        Returns:
            LAMMPSDigest with populated fields.
        """
        log_path = raw_dir / "log.lammps"
        if not log_path.is_file():
            return LAMMPSDigest(error_message="No log.lammps found")

        try:
            text = log_path.read_text(errors="replace")
        except OSError as e:
            return LAMMPSDigest(error_message=f"Failed to read log: {e}")

        return parse_lammps_log_text(text)


def parse_lammps_output(raw_dir: Path) -> LAMMPSDigest:
    """Convenience function to parse LAMMPS output directory."""
    parser = LAMMPSOutputParser()
    return parser.parse(raw_dir)


def parse_lammps_log_text(text: str) -> LAMMPSDigest:
    """Parse LAMMPS log text directly into a LAMMPSDigest."""
    digest = LAMMPSDigest()

    # --- Error detection ---
    if "ERROR" in text:
        error_match = re.search(r"ERROR[:\s]+(.*?)(?:\n|$)", text)
        if error_match:
            digest.error_message = error_match.group(1).strip()[:500]

    if "lost atoms" in text.lower():
        digest.error_message = digest.error_message or "Lost atoms detected"

    # --- Units detection (from echoed command) ---
    units_match = re.search(r"^units\s+(\S+)", text, re.MULTILINE)
    if units_match:
        digest.units = units_match.group(1)

    # --- Thermo block parsing ---
    # Find all thermo header + data blocks (last one wins)
    _parse_thermo_blocks(text, digest)

    # --- Loop time line ---
    # Pattern: Loop time of X on N procs for M steps with K atoms
    loop_matches = re.findall(
        r"Loop time of ([\d.e+-]+) on \d+ procs for (\d+) steps with (\d+) atoms",
        text,
    )
    if loop_matches:
        last_loop = loop_matches[-1]
        try:
            loop_time = float(last_loop[0])
            # Only use loop time for wall_time if we don't have Total wall time
            if digest.wall_time_s is None:
                digest.wall_time_s = loop_time
            digest.n_steps = int(last_loop[1])
            digest.n_atoms = int(last_loop[2])
        except ValueError:
            pass

    # --- Total wall time ---
    # Pattern: Total wall time: H:MM:SS
    wall_match = re.search(
        r"Total wall time:\s*(\d+):(\d+):(\d+)", text
    )
    if wall_match:
        hours, mins, secs = map(int, wall_match.groups())
        digest.wall_time_s = hours * 3600 + mins * 60 + secs

    # --- Minimization stats ---
    _parse_minimize_stats(text, digest)

    # --- Success determination ---
    # Success if we have at least one Loop time line and no ERROR
    has_loop = bool(loop_matches)
    has_error = digest.error_message is not None
    digest.success = has_loop and not has_error

    return digest


def _parse_thermo_blocks(text: str, digest: LAMMPSDigest) -> None:
    """Extract thermo data from the last thermo block in the log.

    A thermo block starts with a header line containing column names
    (always starts with 'Step') followed by numeric data rows.
    """
    lines = text.splitlines()
    last_header_cols: List[str] = []
    last_data_row: List[str] = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Detect thermo header: starts with "Step" and has other column names
        if re.match(r"^\s*Step\s+", line):
            cols = line.split()
            # Read data rows that follow
            data_rows: List[List[str]] = []
            j = i + 1
            while j < len(lines):
                dline = lines[j].strip()
                if not dline:
                    j += 1
                    continue
                # A data row starts with an integer (step number)
                parts = dline.split()
                if parts and _is_thermo_data_row(parts):
                    data_rows.append(parts)
                    j += 1
                else:
                    break

            if data_rows:
                last_header_cols = cols
                last_data_row = data_rows[-1]
            i = j
        else:
            i += 1

    # Map column names to values from the last data row
    if last_header_cols and last_data_row:
        col_map: Dict[str, str] = {}
        for idx, col_name in enumerate(last_header_cols):
            if idx < len(last_data_row):
                col_map[col_name] = last_data_row[idx]

        # Extract known fields
        if "TotEng" in col_map:
            try:
                digest.final_energy = float(col_map["TotEng"])
            except ValueError:
                pass
        if "Temp" in col_map:
            try:
                digest.final_temp = float(col_map["Temp"])
            except ValueError:
                pass
        if "Press" in col_map:
            try:
                digest.final_pressure = float(col_map["Press"])
            except ValueError:
                pass
        if "E_pair" in col_map:
            try:
                digest.final_e_pair = float(col_map["E_pair"])
            except ValueError:
                pass


def _is_thermo_data_row(parts: List[str]) -> bool:
    """Check if a split line looks like a thermo data row.

    A thermo data row starts with an integer (step number) and the rest
    are numeric values.
    """
    if len(parts) < 2:
        return False
    try:
        int(parts[0])
    except ValueError:
        return False
    # Check that at least the second field is numeric
    try:
        float(parts[1])
        return True
    except ValueError:
        return False


def _parse_minimize_stats(text: str, digest: LAMMPSDigest) -> None:
    """Extract minimization statistics from log text."""
    if "Minimization stats:" not in text:
        return

    # Stopping criterion
    crit_match = re.search(
        r"Stopping criterion\s*=\s*(.+?)$", text, re.MULTILINE
    )
    if crit_match:
        digest.minimize_criterion = crit_match.group(1).strip()
        digest.converged_minimize = True

    # Energy initial and final
    # Pattern: Energy initial, next-to-last, final =
    #   E1  E2  E3
    energy_match = re.search(
        r"Energy initial, next-to-last, final\s*=\s*\n?\s*([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)",
        text,
    )
    if energy_match:
        try:
            digest.minimize_energy_initial = float(energy_match.group(1))
            digest.minimize_energy_final = float(energy_match.group(3))
        except ValueError:
            pass

    # Iterations, force evaluations
    iter_match = re.search(
        r"Iterations, force evaluations\s*=\s*(\d+)\s+(\d+)", text
    )
    if iter_match:
        try:
            digest.minimize_iterations = int(iter_match.group(1))
            digest.minimize_force_evaluations = int(iter_match.group(2))
        except ValueError:
            pass
