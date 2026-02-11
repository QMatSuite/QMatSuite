"""CP2K convergence analysis provider."""
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

# SCF step line:
#      1 P_Mix/Diag. 0.40E+00    0.1     0.56604687       -17.0560640154 -1.71E+01
# or   7 DIIS/Diag.  0.14E-03    0.1     0.00001769       -17.2207326092 -1.25E-02
_SCF_RE = re.compile(
    r"^\s+(\d+)\s+(\S+/\S+)\.\s+\S+\s+\S+\s+\S+\s+([-+]?\d+\.\d+(?:[eE][-+]?\d+)?)\s+([-+]?\d+\.\d+(?:[eE][-+]?\d+)?)"
)

# SCF converged:
#   *** SCF run converged in    11 steps ***
_SCF_CONVERGED_RE = re.compile(
    r"^\s+\*\*\*\s+SCF run converged in\s+(\d+)\s+steps"
)

# Ionic step:
#   OPTIMIZATION STEP:      1
_OPT_STEP_RE = re.compile(
    r"^\s*OPTIMIZATION STEP:\s+(\d+)"
)

# Total energy:
#   Total energy:                                               -17.22073261586157
_TOTAL_ENERGY_RE = re.compile(
    r"^\s+Total energy:\s+([-+]?\d+\.\d+)"
)

# ENERGY line (more reliable):
#   ENERGY| Total FORCE_EVAL ( QS ) energy [hartree]            -17.220732615861586
_ENERGY_EVAL_RE = re.compile(
    r"^\s*ENERGY\|\s+Total FORCE_EVAL.*energy \[hartree\]\s+([-+]?\d+\.\d+)"
)

# Max convergence reached:
#   *** MAXIMUM NUMBER OF OPTIMIZATION STEPS REACHED ***
_MAX_STEPS_RE = re.compile(
    r"MAXIMUM NUMBER OF OPTIMIZATION STEPS REACHED"
)

# Geometry converged:
#   *** GEOMETRY OPTIMIZATION COMPLETED ***
_GEO_CONVERGED_RE = re.compile(
    r"GEOMETRY OPTIMIZATION COMPLETED"
)


def parse_cp2k_convergence(output_path: Path) -> dict:
    """Parse CP2K .out for convergence data.

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

    for line in lines:
        # SCF step
        scf_m = _SCF_RE.match(line)
        if scf_m:
            if not algorithm:
                algorithm = scf_m.group(2).split("/")[0]
            cumulative_scf += 1
            energy_ha = float(scf_m.group(3))
            de_ha = float(scf_m.group(4))
            scf_steps.append(cumulative_scf)
            scf_energies.append(energy_ha * _HA_TO_EV)
            scf_des.append(de_ha * _HA_TO_EV)
            continue

        # ENERGY| line (ionic energy)
        en_m = _ENERGY_EVAL_RE.match(line)
        if en_m:
            ionic_steps.append(len(ionic_steps) + 1)
            ionic_energies.append(float(en_m.group(1)) * _HA_TO_EV)
            continue

        # Geometry converged
        if _GEO_CONVERGED_RE.search(line):
            converged = True
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


@register_parser("cp2k", "convergence")
class CP2KConvergenceProvider:
    """CP2K convergence analysis provider."""

    engine = "cp2k"
    object_type = "convergence"

    def can_parse(self, raw_dir: Path) -> bool:
        return any(p.suffix == ".out" for p in raw_dir.iterdir() if p.is_file())

    def parse(self, evidence: EvidenceBundle) -> Convergence:
        """Parse CP2K output and return Convergence object."""
        out_files = list(evidence.primary_raw_dir.glob("*.out"))
        if not out_files:
            raise FileNotFoundError(
                f"No .out file found in {evidence.primary_raw_dir}"
            )
        output_path = out_files[0]

        parsed = parse_cp2k_convergence(output_path)

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
            parser_name="cp2k_convergence",
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
