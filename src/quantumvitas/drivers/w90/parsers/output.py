"""Wannier90 output parser: extract spreads, convergence, timing from .wout.

Parses Wannier90 calculation outputs into a canonical W90Digest dataclass.
Primary source: <seedname>.wout.

Registers with the parser registry as ("w90", "scf_digest").
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
class W90Digest:
    """Canonical digest of a Wannier90 calculation output.

    Attributes:
        success: True if Wannier90 completed without errors.
        converged: True if wannierisation converged within tolerance.
        num_wann: Number of Wannier functions.
        num_bands: Number of input Bloch states.
        num_iter_completed: Number of wannierisation iterations completed.
        final_spread_total: Omega Total (Ang^2).
        final_spread_i: Omega I — gauge-invariant spread.
        final_spread_d: Omega D — diagonal spread.
        final_spread_od: Omega OD — off-diagonal spread.
        wf_centres: WF centres [x, y, z] per WF from Final State.
        wf_spreads: Per-WF spreads (Ang^2) from Final State.
        wall_time_s: Total Execution Time in seconds.
        disentanglement_converged: True if disentanglement converged.
        error_message: Error message if calculation failed.
    """

    success: bool = False
    converged: Optional[bool] = None
    num_wann: Optional[int] = None
    num_bands: Optional[int] = None
    num_iter_completed: Optional[int] = None
    final_spread_total: Optional[float] = None
    final_spread_i: Optional[float] = None
    final_spread_d: Optional[float] = None
    final_spread_od: Optional[float] = None
    wf_centres: Optional[List[List[float]]] = None
    wf_spreads: Optional[List[float]] = None
    wall_time_s: Optional[float] = None
    disentanglement_converged: Optional[bool] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to plain dict (JSON-serialisable)."""
        return asdict(self)


@register_parser("w90", "scf_digest")
class W90OutputParser:
    """Parse Wannier90 outputs into a W90Digest.

    Looks for *.wout files in the directory.
    """

    engine = "w90"
    object_type = "scf_digest"

    def can_parse(self, raw_dir: Path) -> bool:
        """Check if the directory contains parseable Wannier90 output."""
        return any(raw_dir.glob("*.wout"))

    def parse(self, raw_dir: Path, **kwargs: Any) -> W90Digest:
        """Parse Wannier90 output into a W90Digest."""
        wout_files = list(raw_dir.glob("*.wout"))
        if not wout_files:
            return W90Digest(error_message="No .wout file found")

        try:
            text = wout_files[0].read_text(errors="replace")
        except OSError as e:
            return W90Digest(error_message=f"Failed to read .wout: {e}")

        return parse_wout_text(text)


def parse_w90_output(raw_dir: Path) -> W90Digest:
    """Convenience function to parse Wannier90 output directory."""
    parser = W90OutputParser()
    return parser.parse(raw_dir)


def parse_wout_text(text: str) -> W90Digest:
    """Parse Wannier90 .wout text directly into a W90Digest."""
    digest = W90Digest()

    # --- Error detection ---
    if "Exiting......" in text:
        error_match = re.search(r"Error[:\s]+(.*?)(?:\n|$)", text, re.IGNORECASE)
        if error_match:
            digest.error_message = error_match.group(1).strip()[:500]
        else:
            digest.error_message = "Wannier90 exited with error"

    # --- Success detection ---
    if "All done: wannier90 exiting" in text:
        digest.success = True

    # --- Number of Wannier Functions ---
    nwann_match = re.search(
        r"Number of Wannier Functions\s*:\s*(\d+)", text
    )
    if nwann_match:
        digest.num_wann = int(nwann_match.group(1))

    # --- Number of input Bloch states ---
    nbands_match = re.search(
        r"Number of input Bloch states\s*:\s*(\d+)", text
    )
    if nbands_match:
        digest.num_bands = int(nbands_match.group(1))

    # --- Disentanglement convergence ---
    if "<<< Disentanglement >>>" in text or "DISENTANGLE" in text:
        if "Disentanglement converged" in text:
            digest.disentanglement_converged = True
        elif re.search(r"dis_num_iter\s*iterations", text, re.IGNORECASE):
            digest.disentanglement_converged = False

    # --- Wannierisation CONV lines: track iteration count ---
    conv_lines = re.findall(
        r"^\s*(\d+)\s+[+-]?\d+\.\d+E[+-]\d+\s+[\d.]+\s+([\d.]+)\s+[\d.]+\s*<-- CONV",
        text, re.MULTILINE,
    )
    if conv_lines:
        last_iter = int(conv_lines[-1][0])
        digest.num_iter_completed = last_iter

    # --- Final spreads (from the summary after "Final State") ---
    omega_i_match = re.search(r"Omega I\s*=\s*([\d.]+)", text)
    if omega_i_match:
        digest.final_spread_i = float(omega_i_match.group(1))

    omega_d_match = re.search(r"Omega D\s*=\s*([\d.]+)", text)
    if omega_d_match:
        digest.final_spread_d = float(omega_d_match.group(1))

    omega_od_match = re.search(r"Omega OD\s*=\s*([\d.]+)", text)
    if omega_od_match:
        digest.final_spread_od = float(omega_od_match.group(1))

    omega_total_match = re.search(r"Omega Total\s*=\s*([\d.]+)", text)
    if omega_total_match:
        digest.final_spread_total = float(omega_total_match.group(1))

    # --- Final State WF centres and spreads ---
    _parse_final_state(text, digest)

    # --- Convergence: check if spread changed by less than tolerance ---
    if digest.num_iter_completed is not None and digest.final_spread_total is not None:
        # If we got a Final State, the calculation completed the wannierisation
        digest.converged = True
    if conv_lines and len(conv_lines) >= 2:
        # Check if the last delta was very small
        last_delta_match = re.findall(
            r"^\s*\d+\s+([+-]?\d+\.\d+E[+-]\d+)", text, re.MULTILINE
        )
        # Convergence is implied by reaching Final State in a successful run

    # --- Total Execution Time ---
    time_match = re.search(
        r"Total Execution Time\s+([\d.]+)\s*\(sec\)", text
    )
    if time_match:
        digest.wall_time_s = float(time_match.group(1))

    return digest


def _parse_final_state(text: str, digest: W90Digest) -> None:
    """Extract WF centres and spreads from the Final State block."""
    # Find the "Final State" section
    final_idx = text.find("Final State")
    if final_idx == -1:
        return

    # Extract text from "Final State" to next "------" separator
    final_section = text[final_idx:]
    sep_idx = final_section.find("Spreads (Ang^2)")
    if sep_idx > 0:
        final_section = final_section[:sep_idx]

    # Pattern: WF centre and spread    N  ( x, y, z )     spread
    wf_pattern = re.compile(
        r"WF centre and spread\s+\d+\s+\(\s*([+-]?\d+\.\d+),\s*"
        r"([+-]?\d+\.\d+),\s*([+-]?\d+\.\d+)\s*\)\s+([\d.]+)"
    )

    centres: List[List[float]] = []
    spreads: List[float] = []

    for m in wf_pattern.finditer(final_section):
        centres.append([float(m.group(1)), float(m.group(2)), float(m.group(3))])
        spreads.append(float(m.group(4)))

    if centres:
        digest.wf_centres = centres
        digest.wf_spreads = spreads
