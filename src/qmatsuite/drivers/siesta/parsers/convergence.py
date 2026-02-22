"""Siesta convergence analysis provider."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

import numpy as np

from qmatsuite.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from qmatsuite.core.analysis.convergence import Convergence
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.parsers.registry import register_parser

# Siesta outputs energy directly in eV — no conversion needed.

# SCF line:
#   scf:    1     -229.166849     -229.989583     -229.989583  1.582136 -4.732410  0.352940
_SCF_RE = re.compile(
    r"^\s*scf:\s+(\d+)\s+([-+]?\d+\.\d+)\s+([-+]?\d+\.\d+)"
)

# Ionic step:
#   Begin CG opt. move =      0
_IONIC_RE = re.compile(
    r"^\s*Begin\s+(?:CG|Broyden|FIRE|MD)\s+.*move\s*=\s*(\d+)"
)

# Final energy:
#   siesta: E_KS(eV) =             -229.9967
_FINAL_ENERGY_RE = re.compile(
    r"^siesta:\s+E_KS\(eV\)\s+=\s+([-+]?\d+\.\d+)"
)

# Convergence:
#   SCF cycle converged after 6 iterations
_CONVERGED_RE = re.compile(
    r"^SCF cycle converged after\s+(\d+)\s+iterations"
)


def parse_siesta_convergence(output_path: Path) -> dict:
    """Parse Siesta .out for convergence data.

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
    algorithm = ""
    converged = False
    cumulative_scf = 0
    prev_energy: float | None = None

    for line in lines:
        # Algorithm detection from ionic line
        if not algorithm:
            ionic_m = _IONIC_RE.match(line)
            if ionic_m:
                if "CG" in line:
                    algorithm = "CG"
                elif "Broyden" in line:
                    algorithm = "Broyden"
                elif "FIRE" in line:
                    algorithm = "FIRE"
                elif "MD" in line:
                    algorithm = "MD"

        # SCF line
        scf_m = _SCF_RE.match(line)
        if scf_m:
            cumulative_scf += 1
            # E_KS is column 3 (3rd number)
            energy_ev = float(scf_m.group(3))
            scf_steps.append(cumulative_scf)
            scf_energies.append(energy_ev)
            de = energy_ev - prev_energy if prev_energy is not None else energy_ev
            scf_des.append(de)
            prev_energy = energy_ev
            continue

        # SCF convergence marker
        conv_m = _CONVERGED_RE.match(line)
        if conv_m:
            converged = True
            continue

        # Final energy (ionic step summary)
        fe_m = _FINAL_ENERGY_RE.match(line)
        if fe_m:
            ionic_steps.append(len(ionic_steps) + 1)
            ionic_energies.append(float(fe_m.group(1)))
            continue

    return {
        "scf_steps": scf_steps,
        "scf_energies": scf_energies,
        "scf_des": scf_des,
        "ionic_steps": ionic_steps,
        "ionic_energies": ionic_energies,
        "algorithm": algorithm,
        "converged": converged,
    }


@register_parser("siesta", "convergence")
class SiestaConvergenceProvider:
    """Siesta convergence analysis provider."""

    engine = "siesta"
    object_type = "convergence"

    def can_parse(self, raw_dir: Path) -> bool:
        return any(p.suffix == ".out" for p in raw_dir.iterdir() if p.is_file())

    def parse(self, evidence: EvidenceBundle) -> Convergence:
        """Parse Siesta output and return Convergence object."""
        out_files = list(evidence.primary_raw_dir.glob("*.out"))
        if not out_files:
            raise FileNotFoundError(
                f"No .out file found in {evidence.primary_raw_dir}"
            )
        output_path = out_files[0]

        parsed = parse_siesta_convergence(output_path)

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
            parser_name="siesta_convergence",
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
