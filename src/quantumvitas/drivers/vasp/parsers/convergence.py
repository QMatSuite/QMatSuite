"""VASP convergence analysis provider (OSZICAR parser)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

import numpy as np

from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.convergence import Convergence
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.parsers.registry import register_parser

# VASP Fortran float: optional sign, optional leading digits, dot, digits, E+/-dd
_VFLOAT = r"[-+]?\d*\.\d+E[+-]\d+"

# Electronic SCF line patterns:
#   DAV:   1    -0.63070764E+01   -0.63070764E+01    0.42735337E-01    0.23073744E+01
_SCF_RE = re.compile(
    rf"^\s*(DAV|RMM|CG\s?):\s*(\d+)\s+({_VFLOAT})\s+({_VFLOAT})"
)

# Ionic summary (relaxation/SCF):  1 F= -.10586221E+02 E0= -.10585843E+02 ...
_IONIC_RE = re.compile(
    rf"^\s*(\d+)\s+F=\s*({_VFLOAT})"
)

# MD summary:  1 T=   300.00 E= -.10586221E+02 F= -.10586221E+02 E0= ...
_MD_RE = re.compile(
    rf"^\s*(\d+)\s+T=\s*([-+]?\d*\.?\d+)\s+E=\s*({_VFLOAT})"
)


def parse_oszicar(oszicar_path: Path) -> dict:
    """Parse VASP OSZICAR into convergence data.

    Returns dict with:
    - scf_steps: list of int (cumulative index)
    - scf_energies: list of float (eV)
    - scf_des: list of float (energy change)
    - ionic_steps: list of int
    - ionic_energies: list of float (eV)
    - algorithm: str
    - converged: bool (heuristic: last SCF dE is small)
    """
    text = oszicar_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    scf_steps: List[int] = []
    scf_energies: List[float] = []
    scf_des: List[float] = []
    ionic_steps: List[int] = []
    ionic_energies: List[float] = []
    algorithm = ""
    cumulative_scf = 0

    for line in lines:
        scf_match = _SCF_RE.match(line)
        if scf_match:
            if not algorithm:
                algorithm = scf_match.group(1).strip()
            cumulative_scf += 1
            scf_steps.append(cumulative_scf)
            scf_energies.append(float(scf_match.group(3)))
            scf_des.append(float(scf_match.group(4)))
            continue

        ionic_match = _IONIC_RE.match(line)
        if ionic_match:
            ionic_steps.append(int(ionic_match.group(1)))
            ionic_energies.append(float(ionic_match.group(2)))
            continue

        md_match = _MD_RE.match(line)
        if md_match:
            ionic_steps.append(int(md_match.group(1)))
            ionic_energies.append(float(md_match.group(3)))
            continue

    # Heuristic: converged if last SCF |dE| < 1e-4 eV
    converged = False
    if scf_des:
        converged = abs(scf_des[-1]) < 1e-4

    return {
        "scf_steps": scf_steps,
        "scf_energies": scf_energies,
        "scf_des": scf_des,
        "ionic_steps": ionic_steps,
        "ionic_energies": ionic_energies,
        "algorithm": algorithm,
        "converged": converged,
    }


@register_parser("vasp", "convergence")
class VASPConvergenceProvider:
    """VASP convergence analysis provider.

    Architecture: One-Provider, Three-Trigger Pattern
    ==================================================
    Three AnalysisCapability entries (scf/relax/md) all route to this single
    provider because VASP writes the same OSZICAR format regardless of calc type.
    The orchestrator picks ONE match per object_type (ranked by
    -len(gen_step_sequence), then declaration order).

    Generality for future engines:
    - Multi-step analysis: gen_step_sequence=["bandspw","bands"] matches only
      contiguous runs. EvidenceBundle.evidence_steps carries per-step dirs.
    - Artifact-driven submodes: same object_type + optional fields (e.g., PROCAR
      projections on bands). No new object_type needed.
    """

    engine = "vasp"
    object_type = "convergence"

    def can_parse(self, raw_dir: Path) -> bool:
        return (raw_dir / "OSZICAR").exists()

    def parse(self, evidence: EvidenceBundle) -> Convergence:
        """Parse OSZICAR and return Convergence object."""
        oszicar_path = evidence.primary_raw_dir / "OSZICAR"
        if not oszicar_path.exists():
            raise FileNotFoundError(f"OSZICAR not found: {oszicar_path}")

        parsed = parse_oszicar(oszicar_path)

        source_files = [SourceFileStat.from_path(oszicar_path, evidence.calc_dir)]

        warnings: list[str] = []
        if not parsed["scf_energies"]:
            warnings.append("No SCF steps found in OSZICAR.")
        if not parsed["ionic_energies"]:
            warnings.append("No ionic steps found in OSZICAR.")

        meta = AnalysisObjectMeta.create(
            object_type="convergence",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="vasp_convergence",
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
