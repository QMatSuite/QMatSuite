"""Psi4 convergence analysis provider.

Parses SCF iteration output from Psi4 output files.
Registers with the parser registry as ("psi4", "convergence").
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

import numpy as np

from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.convergence.model import Convergence
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.parsers.registry import register_parser

# Conversion factor: 1 Hartree = 27.211386245988 eV
HARTREE_TO_EV = 27.211386245988

# Psi4 SCF iteration:
#   @DF-RHF iter   1:   -75.97012345678901   -7.59701e+01   5.43210e-02 DIIS
_PSI4_ITER_RE = re.compile(
    r"@[\w-]+\s+iter\s+(\d+):\s+([-\d.]+)\s+([-\d.Ee+]+)"
)

# Psi4 final energy:
#   @DF-RHF Final Energy:   -76.02345678901234
_PSI4_FINAL_RE = re.compile(
    r"@[\w-]+\s+Final Energy:\s+([-\d.]+)"
)

# Convergence marker
_PSI4_CONVERGED_RE = re.compile(
    r"Energy and wave function converged"
)


def parse_psi4_convergence(text: str) -> dict:
    """Parse Psi4 output text into convergence data.

    Returns dict with standard convergence fields.
    """
    scf_steps: List[int] = []
    scf_energies: List[float] = []
    scf_des: List[float] = []
    ionic_steps: List[int] = []
    ionic_energies: List[float] = []
    converged = False
    algorithm = ""

    for m in _PSI4_ITER_RE.finditer(text):
        step = int(m.group(1))
        energy_ha = float(m.group(2))
        de_ha = float(m.group(3))
        energy_ev = energy_ha * HARTREE_TO_EV
        de_ev = de_ha * HARTREE_TO_EV

        if not algorithm:
            # Extract method from the prefix
            prefix_m = re.search(r"@([\w-]+)\s+iter", text)
            if prefix_m:
                algorithm = prefix_m.group(1)

        scf_steps.append(step)
        scf_energies.append(energy_ev)
        scf_des.append(de_ev)

    if _PSI4_CONVERGED_RE.search(text):
        converged = True

    # Final energy as ionic step
    final_matches = _PSI4_FINAL_RE.findall(text)
    if final_matches:
        ionic_steps = [1]
        ionic_energies = [float(final_matches[-1]) * HARTREE_TO_EV]

    return {
        "scf_steps": scf_steps,
        "scf_energies": scf_energies,
        "scf_des": scf_des,
        "ionic_steps": ionic_steps,
        "ionic_energies": ionic_energies,
        "algorithm": algorithm,
        "converged": converged,
    }


@register_parser("psi4", "convergence")
class Psi4ConvergenceProvider:
    """Psi4 convergence analysis provider."""

    engine = "psi4"
    object_type = "convergence"

    def can_parse(self, raw_dir: Path) -> bool:
        for pattern in ("*.dat", "*.out"):
            for f in raw_dir.glob(pattern):
                try:
                    text = f.read_text(errors="replace")[:8192]
                    lower = text.lower()
                    if "psi4" in lower or "@df-" in text or "@rhf" in text:
                        return True
                except OSError:
                    pass
        return False

    def parse(self, evidence: EvidenceBundle) -> Convergence:
        """Parse Psi4 output and return Convergence object."""
        out_file = self._find_output_file(evidence.primary_raw_dir)
        if out_file is None:
            raise FileNotFoundError(
                f"No Psi4 output file found in {evidence.primary_raw_dir}"
            )

        text = out_file.read_text(encoding="utf-8", errors="replace")
        parsed = parse_psi4_convergence(text)

        source_files = [SourceFileStat.from_path(out_file, evidence.calc_dir)]

        warnings: list[str] = []
        if not parsed["scf_energies"]:
            warnings.append("No SCF steps found in Psi4 output.")

        meta = AnalysisObjectMeta.create(
            object_type="convergence",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="psi4_convergence",
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
        """Find the main Psi4 output file."""
        for name in ["output.dat", "psi4.out", "output.out"]:
            candidate = raw_dir / name
            if candidate.is_file():
                return candidate
        dat_files = list(raw_dir.glob("*.dat"))
        if dat_files:
            return dat_files[0]
        out_files = list(raw_dir.glob("*.out"))
        return out_files[0] if out_files else None
