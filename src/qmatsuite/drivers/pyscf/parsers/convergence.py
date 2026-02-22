"""PySCF convergence analysis provider.

Parses SCF iteration output from PySCF log/output files.
Registers with the parser registry as ("pyscf", "convergence").
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

# PySCF SCF iteration:
# cycle= 1 E= -75.9701234568  delta_E= -75.97  |g|= 0.543  |ddm|= 1.23
_PYSCF_CYCLE_RE = re.compile(
    r"cycle=\s*(\d+)\s+E=\s*([-\d.Ee+]+)\s+delta_E=\s*([-\d.Ee+]+)"
)

# PySCF convergence marker
_PYSCF_CONVERGED_RE = re.compile(
    r"converged SCF energy\s*=\s*([-\d.Ee+]+)"
)

# Extra energy: PySCF "Extra cycle" final
_PYSCF_EXTRA_RE = re.compile(
    r"Extra cycle\s+E=\s*([-\d.Ee+]+)"
)


def parse_pyscf_convergence(text: str) -> dict:
    """Parse PySCF output text into convergence data.

    Returns dict with standard convergence fields.
    """
    scf_steps: List[int] = []
    scf_energies: List[float] = []
    scf_des: List[float] = []
    ionic_steps: List[int] = []
    ionic_energies: List[float] = []
    converged = False

    for m in _PYSCF_CYCLE_RE.finditer(text):
        step = int(m.group(1))
        energy_ha = float(m.group(2))
        de_ha = float(m.group(3))
        energy_ev = energy_ha * HARTREE_TO_EV
        de_ev = de_ha * HARTREE_TO_EV
        scf_steps.append(step)
        scf_energies.append(energy_ev)
        scf_des.append(de_ev)

    conv_m = _PYSCF_CONVERGED_RE.search(text)
    if conv_m:
        converged = True
        final_ha = float(conv_m.group(1))
        ionic_steps = [1]
        ionic_energies = [final_ha * HARTREE_TO_EV]
    elif scf_energies:
        ionic_steps = [1]
        ionic_energies = [scf_energies[-1]]

    return {
        "scf_steps": scf_steps,
        "scf_energies": scf_energies,
        "scf_des": scf_des,
        "ionic_steps": ionic_steps,
        "ionic_energies": ionic_energies,
        "algorithm": "PySCF-SCF",
        "converged": converged,
    }


@register_parser("pyscf", "convergence")
class PySCFConvergenceProvider:
    """PySCF convergence analysis provider."""

    engine = "pyscf"
    object_type = "convergence"

    def can_parse(self, raw_dir: Path) -> bool:
        for pattern in ("*.out", "*.log"):
            for f in raw_dir.glob(pattern):
                try:
                    text = f.read_text(errors="replace")[:2048]
                    if "pyscf" in text.lower() or "cycle=" in text:
                        return True
                except OSError:
                    pass
        return False

    def parse(self, evidence: EvidenceBundle) -> Convergence:
        """Parse PySCF output and return Convergence object."""
        out_file = self._find_output_file(evidence.primary_raw_dir)
        if out_file is None:
            raise FileNotFoundError(
                f"No PySCF output file found in {evidence.primary_raw_dir}"
            )

        text = out_file.read_text(encoding="utf-8", errors="replace")
        parsed = parse_pyscf_convergence(text)

        source_files = [SourceFileStat.from_path(out_file, evidence.calc_dir)]

        warnings: list[str] = []
        if not parsed["scf_energies"]:
            warnings.append("No SCF steps found in PySCF output.")

        meta = AnalysisObjectMeta.create(
            object_type="convergence",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="pyscf_convergence",
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
        """Find the main PySCF output file."""
        for name in ["pyscf.out", "pyscf.log", "output.out", "log.out"]:
            candidate = raw_dir / name
            if candidate.is_file():
                return candidate
        for pattern in ("*.out", "*.log"):
            files = list(raw_dir.glob(pattern))
            if files:
                return files[0]
        return None
