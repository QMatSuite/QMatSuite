"""ABINIT convergence analysis provider."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

import numpy as np

from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.convergence import Convergence
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.parsers.registry import register_parser

# Ha -> eV
_HA_TO_EV = 27.211386245988

# SCF step:  ETOT  3  -8.7699525525712    -1.374E-04 ...
_ETOT_RE = re.compile(
    r"^\s*ETOT\s+(\d+)\s+([-+]?\d+\.\d+(?:[eE][-+]?\d+)?)\s+([-+]?\d+\.\d+(?:[eE][-+]?\d+)?)"
)

# Ionic iteration:
#  --- Iteration: ( 1/10) Internal Cycle: (1/1)
_IONIC_RE = re.compile(
    r"^---\s+Iteration:\s+\(\s*(\d+)/\s*\d+\)"
)

# Total energy (ionic summary):
#  Total energy (etotal) [Ha]= -8.76995255257120E+00
_TOTAL_ENERGY_RE = re.compile(
    r"^\s*Total energy \(etotal\) \[Ha\]=\s*([-+]?\d+\.\d+[eE][-+]?\d+)"
)

# SCF convergence:
#  At SCF step    3, forces are converged :
_SCF_CONVERGED_RE = re.compile(
    r"^\s*At SCF step\s+\d+,\s+forces are converged"
)

# Ionic convergence:
#  At Broyd/MD step   4, gradients are converged :
_IONIC_CONVERGED_RE = re.compile(
    r"^\s*At Broyd/MD step\s+\d+,\s+gradients are converged"
)


def parse_abinit_convergence(output_path: Path) -> dict:
    """Parse ABINIT .abo output for convergence data.

    Returns dict with:
    - scf_steps, scf_energies, scf_des: cumulative SCF data (eV)
    - ionic_steps, ionic_energies: ionic data (eV)
    - algorithm, converged
    """
    text = output_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    scf_steps: List[int] = []
    scf_energies: List[float] = []
    scf_des: List[float] = []
    ionic_steps: List[int] = []
    ionic_energies: List[float] = []
    converged = False
    cumulative_scf = 0

    for line in lines:
        # ETOT line (SCF step)
        etot_m = _ETOT_RE.match(line)
        if etot_m:
            cumulative_scf += 1
            energy_ha = float(etot_m.group(2))
            de_ha = float(etot_m.group(3))
            scf_steps.append(cumulative_scf)
            scf_energies.append(energy_ha * _HA_TO_EV)
            scf_des.append(de_ha * _HA_TO_EV)
            continue

        # Ionic iteration marker
        ionic_m = _IONIC_RE.match(line)
        if ionic_m:
            continue

        # Total energy (ionic step summary)
        te_m = _TOTAL_ENERGY_RE.match(line)
        if te_m:
            ionic_steps.append(len(ionic_steps) + 1)
            ionic_energies.append(float(te_m.group(1)) * _HA_TO_EV)
            continue

        # Ionic convergence
        if _IONIC_CONVERGED_RE.match(line):
            converged = True
            continue

    return {
        "scf_steps": scf_steps,
        "scf_energies": scf_energies,
        "scf_des": scf_des,
        "ionic_steps": ionic_steps,
        "ionic_energies": ionic_energies,
        "algorithm": "Broyden",
        "converged": converged,
    }


@register_parser("abinit", "convergence")
class ABINITConvergenceProvider:
    """ABINIT convergence analysis provider."""

    engine = "abinit"
    object_type = "convergence"

    def can_parse(self, raw_dir: Path) -> bool:
        return any(p.suffix == ".abo" for p in raw_dir.iterdir() if p.is_file())

    def parse(self, evidence: EvidenceBundle) -> Convergence:
        """Parse ABINIT .abo output and return Convergence object."""
        abo_files = list(evidence.primary_raw_dir.glob("*.abo"))
        if not abo_files:
            raise FileNotFoundError(
                f"No .abo file found in {evidence.primary_raw_dir}"
            )
        output_path = abo_files[0]

        parsed = parse_abinit_convergence(output_path)

        source_files = [SourceFileStat.from_path(output_path, evidence.calc_dir)]

        warnings: list[str] = []
        if not parsed["scf_energies"]:
            warnings.append("No SCF steps found in output.")

        meta = AnalysisObjectMeta.create(
            object_type="convergence",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="abinit_convergence",
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
