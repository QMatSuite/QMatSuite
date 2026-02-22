"""Gaussian convergence analysis provider.

Parses SCF iteration energies and geometry optimization convergence from Gaussian log.
Registers with the parser registry as ("gaussian", "convergence").
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

# Conversion factor: 1 Hartree = 27.211386245988 eV
HARTREE_TO_EV = 27.211386245988

# SCF Done line:
# SCF Done:  E(RB3LYP) =  -76.4203805028     A.U. after   10 cycles
_SCF_DONE_RE = re.compile(
    r"SCF Done:\s+E\((\w+)\)\s*=\s*([-\d.]+)\s+A\.U\.\s+after\s+(\d+)\s+cycles"
)

# SCF iteration energy line (within SCF output):
# E= -76.3831024123     Delta-E=       -0.002130458889 ...
_SCF_ENERGY_RE = re.compile(
    r"E=\s*([-\d.]+)\s+Delta-E=\s*([-\d.Ee+]+)"
)

# Optimization convergence summary (Converged? YES/NO lines)
# Maximum Force, RMS Force, Maximum Displacement, RMS Displacement
_OPT_CONVERGED_RE = re.compile(
    r"(?:Optimization completed|Stationary point found)"
)

# MP2 energy with Fortran D notation
_MP2_RE = re.compile(
    r"EUMP2\s*=\s*([-\dD.+]+)"
)


def parse_gaussian_convergence(text: str) -> dict:
    """Parse Gaussian log text into convergence data.

    Returns dict with:
    - scf_steps: list of int (cumulative index)
    - scf_energies: list of float (eV)
    - scf_des: list of float (energy change, eV)
    - ionic_steps: list of int (opt step numbers)
    - ionic_energies: list of float (eV)
    - algorithm: str (method name)
    - converged: bool
    """
    scf_steps: List[int] = []
    scf_energies: List[float] = []
    scf_des: List[float] = []
    ionic_steps: List[int] = []
    ionic_energies: List[float] = []
    algorithm = ""
    converged = False
    cumulative_scf = 0

    # Parse SCF iteration energies
    for m in _SCF_ENERGY_RE.finditer(text):
        cumulative_scf += 1
        energy_ev = float(m.group(1)) * HARTREE_TO_EV
        de_ev = float(m.group(2)) * HARTREE_TO_EV
        scf_steps.append(cumulative_scf)
        scf_energies.append(energy_ev)
        scf_des.append(de_ev)

    # Parse SCF Done lines for optimization ionic steps
    scf_done_matches = list(_SCF_DONE_RE.finditer(text))
    for i, m in enumerate(scf_done_matches, 1):
        if not algorithm:
            algorithm = m.group(1)
        energy_ev = float(m.group(2)) * HARTREE_TO_EV
        ionic_steps.append(i)
        ionic_energies.append(energy_ev)

    # Check for MP2 energy override on last step
    mp2_m = _MP2_RE.search(text)
    if mp2_m and ionic_energies:
        mp2_str = mp2_m.group(1).replace("D", "E")
        ionic_energies[-1] = float(mp2_str) * HARTREE_TO_EV

    # Convergence check
    if _OPT_CONVERGED_RE.search(text):
        converged = True
    elif not ionic_steps:
        # Single-point: check if SCF converged
        if scf_done_matches:
            converged = True
    elif "Normal termination of Gaussian" in text:
        converged = True

    return {
        "scf_steps": scf_steps,
        "scf_energies": scf_energies,
        "scf_des": scf_des,
        "ionic_steps": ionic_steps,
        "ionic_energies": ionic_energies,
        "algorithm": algorithm,
        "converged": converged,
    }


@register_parser("gaussian", "convergence")
class GaussianConvergenceProvider:
    """Gaussian convergence analysis provider.

    Routes from AnalysisCapability entries for scf and relax gen steps.
    """

    engine = "gaussian"
    object_type = "convergence"

    def can_parse(self, raw_dir: Path) -> bool:
        for f in raw_dir.glob("*.log"):
            try:
                text = f.read_text(errors="replace")[:2048]
                if "Entering Gaussian System" in text or "Entering Link 1" in text:
                    return True
            except OSError:
                pass
        return False

    def parse(self, evidence: EvidenceBundle) -> Convergence:
        """Parse Gaussian log and return Convergence object."""
        log_file = self._find_output_file(evidence.primary_raw_dir)
        if log_file is None:
            raise FileNotFoundError(
                f"No Gaussian log file found in {evidence.primary_raw_dir}"
            )

        text = log_file.read_text(encoding="utf-8", errors="replace")
        parsed = parse_gaussian_convergence(text)

        source_files = [SourceFileStat.from_path(log_file, evidence.calc_dir)]

        warnings: list[str] = []
        if not parsed["scf_energies"]:
            warnings.append("No SCF iteration energies found in Gaussian log.")

        meta = AnalysisObjectMeta.create(
            object_type="convergence",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="gaussian_convergence",
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
        """Find the main Gaussian log file."""
        for name in ["output.log", "gaussian.log", "calc.log"]:
            candidate = raw_dir / name
            if candidate.is_file():
                return candidate
        log_files = list(raw_dir.glob("*.log"))
        return log_files[0] if log_files else None
