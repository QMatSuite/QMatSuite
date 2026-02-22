"""QMCPACK convergence analysis provider.

Parses per-block energy statistics from QMCPACK scalar.dat files.
Registers with the parser registry as ("qmcpack", "convergence").
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

# QMCPACK scalar.dat format:
# Column 0: block index
# Column 1: LocalEnergy
# First line is header: #  index  LocalEnergy  ...
_SCALAR_HEADER_RE = re.compile(r"#\s+index\s+LocalEnergy", re.IGNORECASE)


def parse_qmcpack_convergence(text: str) -> dict:
    """Parse QMCPACK scalar.dat text into convergence data.

    In QMC, "SCF steps" map to block indices and "SCF energies" to
    per-block average local energies (already in Hartree, converted to eV).

    Returns dict with standard convergence fields.
    """
    HARTREE_TO_EV = 27.211386245988
    scf_steps: List[int] = []
    scf_energies: List[float] = []
    scf_des: List[float] = []
    prev_energy: Optional[float] = None

    lines = text.splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            try:
                block_idx = int(parts[0])
                energy_ha = float(parts[1])
                energy_ev = energy_ha * HARTREE_TO_EV
                scf_steps.append(block_idx)
                scf_energies.append(energy_ev)
                if prev_energy is not None:
                    scf_des.append(energy_ev - prev_energy)
                else:
                    scf_des.append(0.0)
                prev_energy = energy_ev
            except (ValueError, IndexError):
                continue

    # QMC doesn't have "ionic" steps in the same sense;
    # we report a single ionic step with the mean energy
    ionic_steps: List[int] = []
    ionic_energies: List[float] = []
    if scf_energies:
        ionic_steps = [1]
        ionic_energies = [float(np.mean(scf_energies))]

    # QMC is always "converged" if we have data (statistical method)
    converged = len(scf_energies) > 0

    return {
        "scf_steps": scf_steps,
        "scf_energies": scf_energies,
        "scf_des": scf_des,
        "ionic_steps": ionic_steps,
        "ionic_energies": ionic_energies,
        "algorithm": "QMC",
        "converged": converged,
    }


@register_parser("qmcpack", "convergence")
class QMCPACKConvergenceProvider:
    """QMCPACK convergence analysis provider.

    Parses scalar.dat files containing per-block energy statistics.
    """

    engine = "qmcpack"
    object_type = "convergence"

    def can_parse(self, raw_dir: Path) -> bool:
        return bool(list(raw_dir.glob("*.scalar.dat")))

    def parse(self, evidence: EvidenceBundle) -> Convergence:
        """Parse QMCPACK scalar.dat and return Convergence object."""
        scalar_file = self._find_scalar_file(evidence.primary_raw_dir)
        if scalar_file is None:
            raise FileNotFoundError(
                f"No scalar.dat file found in {evidence.primary_raw_dir}"
            )

        text = scalar_file.read_text(encoding="utf-8", errors="replace")
        parsed = parse_qmcpack_convergence(text)

        source_files = [SourceFileStat.from_path(scalar_file, evidence.calc_dir)]

        warnings: list[str] = []
        if not parsed["scf_energies"]:
            warnings.append("No energy blocks found in scalar.dat.")

        meta = AnalysisObjectMeta.create(
            object_type="convergence",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="qmcpack_convergence",
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

    def _find_scalar_file(self, raw_dir: Path) -> Optional[Path]:
        """Find the scalar.dat file."""
        scalar_files = list(raw_dir.glob("*.scalar.dat"))
        return scalar_files[0] if scalar_files else None
