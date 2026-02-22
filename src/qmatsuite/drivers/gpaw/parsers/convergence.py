"""GPAW convergence analysis provider.

Parses SCF iteration output from GPAW Python log files.
Registers with the parser registry as ("gpaw", "convergence").
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

import numpy as np

from qmatsuite.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from qmatsuite.core.analysis.convergence.model import Convergence
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.parsers.registry import register_parser

# GPAW SCF iteration line patterns:
# iter:   1  12:34:56  -15.1234567  0.123  log10-change= -1.23
# or: iter:   1  -15.1234567  0.123
_GPAW_ITER_RE = re.compile(
    r"iter:\s+(\d+)\s+(?:\d+:\d+:\d+\s+)?([-\d.]+)\s+([-\d.Ee+]+)"
)

# Converged marker
_GPAW_CONVERGED_RE = re.compile(
    r"Converged after \d+ iterations"
)

# Final energy
_GPAW_ENERGY_RE = re.compile(
    r"Free energy:\s+([-\d.]+)"
)


def parse_gpaw_convergence(text: str) -> dict:
    """Parse GPAW log text into convergence data.

    Returns dict with standard convergence fields.
    """
    scf_steps: List[int] = []
    scf_energies: List[float] = []
    scf_des: List[float] = []
    ionic_steps: List[int] = []
    ionic_energies: List[float] = []
    converged = False
    prev_energy: Optional[float] = None

    for m in _GPAW_ITER_RE.finditer(text):
        step = int(m.group(1))
        energy = float(m.group(2))
        scf_steps.append(step)
        scf_energies.append(energy)
        if prev_energy is not None:
            scf_des.append(energy - prev_energy)
        else:
            scf_des.append(0.0)
        prev_energy = energy

    if _GPAW_CONVERGED_RE.search(text):
        converged = True

    # Collect final energy as single ionic step
    energy_matches = _GPAW_ENERGY_RE.findall(text)
    if energy_matches:
        ionic_steps = [1]
        ionic_energies = [float(energy_matches[-1])]
    elif scf_energies:
        ionic_steps = [1]
        ionic_energies = [scf_energies[-1]]

    return {
        "scf_steps": scf_steps,
        "scf_energies": scf_energies,
        "scf_des": scf_des,
        "ionic_steps": ionic_steps,
        "ionic_energies": ionic_energies,
        "algorithm": "GPAW-SCF",
        "converged": converged,
    }


@register_parser("gpaw", "convergence")
class GPAWConvergenceProvider:
    """GPAW convergence analysis provider."""

    engine = "gpaw"
    object_type = "convergence"

    def can_parse(self, raw_dir: Path) -> bool:
        for f in raw_dir.glob("*.txt"):
            try:
                text = f.read_text(errors="replace")[:2048]
                if "gpaw" in text.lower() or "iter:" in text:
                    return True
            except OSError:
                pass
        return False

    def parse(self, evidence: EvidenceBundle) -> Convergence:
        """Parse GPAW log and return Convergence object."""
        log_file = self._find_output_file(evidence.primary_raw_dir)
        if log_file is None:
            raise FileNotFoundError(
                f"No GPAW log file found in {evidence.primary_raw_dir}"
            )

        text = log_file.read_text(encoding="utf-8", errors="replace")
        parsed = parse_gpaw_convergence(text)

        source_files = [SourceFileStat.from_path(log_file, evidence.calc_dir)]

        warnings: list[str] = []
        if not parsed["scf_energies"]:
            warnings.append("No SCF steps found in GPAW log.")

        meta = AnalysisObjectMeta.create(
            object_type="convergence",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="gpaw_convergence",
            parser_version="1.0",
            warnings=warnings,
        )

        return Convergence(
            meta=meta,
            scf_step=np.array(parsed["scf_steps"], dtype=int),
            scf_energy=np.array(parsed["scf_energies"], dtype=float),
            scf_de=np.array(parsed["scf_des"], dtype=float),
            ionic_step=np.array(parsed["ionic_steps"], dtype=int),
            ionic_energy=np.array(parsed["ionic_energies"], dtype=float),
            converged=parsed["converged"],
            n_ionic_steps=len(parsed["ionic_steps"]),
            algorithm=parsed["algorithm"],
        )

    def _find_output_file(self, raw_dir: Path) -> Optional[Path]:
        """Find the main GPAW log file."""
        for name in ["gpaw.txt", "output.txt", "log.txt"]:
            candidate = raw_dir / name
            if candidate.is_file():
                return candidate
        txt_files = list(raw_dir.glob("*.txt"))
        return txt_files[0] if txt_files else None
