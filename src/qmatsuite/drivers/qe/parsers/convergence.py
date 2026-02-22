"""QE convergence analysis provider."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Sequence

import numpy as np

from qmatsuite.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from qmatsuite.core.analysis.convergence import Convergence
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.parsers.registry import register_parser

# Ry -> eV
_RY_TO_EV = 13.605693122994

# SCF iteration line:
#   iteration #  1     ecut=    20.00 Ry     beta= 0.70
_SCF_ITER_RE = re.compile(r"^\s+iteration\s+#\s*(\d+)")

# Total energy in SCF block:
#   total energy              =     -15.74359441 Ry
_TOTAL_ENERGY_RE = re.compile(
    r"^\s+total energy\s+=\s+([-+]?\d+\.\d+)\s+Ry"
)

# Estimated scf accuracy:
#   estimated scf accuracy    <       0.05640246 Ry
# or estimated scf accuracy    <          8.6E-09 Ry
_SCF_ACCURACY_RE = re.compile(
    r"^\s+estimated scf accuracy\s+<\s+([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)\s+Ry"
)

# Final total energy (ionic summary):
#  !    total energy              =     -15.74697012 Ry
_FINAL_ENERGY_RE = re.compile(
    r"^\s*!\s+total energy\s+=\s+([-+]?\d+\.\d+)\s+Ry"
)

# Total force:
#      Total force =     0.039171     Total SCF correction =     0.000064
_TOTAL_FORCE_RE = re.compile(
    r"^\s+Total force\s+=\s+([-+]?\d+\.\d+)"
)

# Convergence marker:
#   convergence has been achieved in   5 iterations
_CONVERGED_RE = re.compile(
    r"^\s+convergence has been achieved"
)

# Algorithm:
#   Davidson diagonalization with overlap
_ALGORITHM_RE = re.compile(
    r"^\s+(Davidson|CG|Lanczos|PPCG)\s+diagonalization"
)


def _select_output_file(raw_dir: Path, gen_steps: Sequence[str]) -> Path:
    """Select the most relevant QE output file for convergence parsing."""
    out_files = sorted(p for p in raw_dir.glob("*.out") if p.is_file())
    if not out_files:
        raise FileNotFoundError(f"No .out file found in {raw_dir}")

    normalized_steps = [str(step or "").strip().lower() for step in gen_steps if str(step or "").strip()]

    # 1) Prefer exact <gen_step>.out (e.g., scf.out, relax.out).
    by_name = {p.name.lower(): p for p in out_files}
    for step in normalized_steps:
        exact = by_name.get(f"{step}.out")
        if exact is not None:
            return exact

    # 2) Prefer names that clearly include the gen step token (e.g., si.relax.out).
    for step in normalized_steps:
        token_matches: list[Path] = []
        for candidate in out_files:
            stem = candidate.stem.lower()
            if (
                stem == step
                or f".{step}." in candidate.name.lower()
                or stem.endswith(f".{step}")
                or stem.startswith(f"{step}.")
                or stem.endswith(f"_{step}")
                or stem.startswith(f"{step}_")
                or f"-{step}-" in stem
                or stem.endswith(f"-{step}")
                or stem.startswith(f"{step}-")
            ):
                token_matches.append(candidate)
        if token_matches:
            # Stable choice: shortest name first, then lexical order.
            return sorted(token_matches, key=lambda p: (len(p.name), p.name.lower()))[0]

    # 3) Fallback: prefer non-empty output files; if multiple, choose largest.
    non_empty = [p for p in out_files if p.stat().st_size > 0]
    if non_empty:
        return max(non_empty, key=lambda p: (p.stat().st_size, p.name.lower()))

    # 4) Last resort.
    return out_files[0]


def parse_qe_convergence(output_path: Path) -> dict:
    """Parse QE pw.x output for convergence data.

    Returns dict with:
    - scf_steps, scf_energies, scf_des: cumulative SCF data (eV)
    - ionic_steps, ionic_energies, ionic_max_forces: ionic data (eV, eV/A)
    - algorithm, converged
    """
    text = output_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    scf_steps: List[int] = []
    scf_energies: List[float] = []
    scf_des: List[float] = []
    ionic_steps: List[int] = []
    ionic_energies: List[float] = []
    ionic_max_forces: List[float] = []
    algorithm = ""
    converged = False
    cumulative_scf = 0
    prev_energy: float | None = None
    ionic_index = 0

    for line in lines:
        # Algorithm detection
        if not algorithm:
            alg_m = _ALGORITHM_RE.match(line)
            if alg_m:
                algorithm = alg_m.group(1)

        # SCF iteration
        scf_m = _SCF_ITER_RE.match(line)
        if scf_m:
            cumulative_scf += 1
            continue

        # Total energy in SCF block
        te_m = _TOTAL_ENERGY_RE.match(line)
        if te_m:
            energy_ry = float(te_m.group(1))
            energy_ev = energy_ry * _RY_TO_EV
            scf_steps.append(cumulative_scf)
            scf_energies.append(energy_ev)
            de = energy_ev - prev_energy if prev_energy is not None else energy_ev
            scf_des.append(de)
            prev_energy = energy_ev
            continue

        # Convergence achieved marker
        if _CONVERGED_RE.match(line):
            converged = True
            continue

        # Final energy (ionic step summary)
        fe_m = _FINAL_ENERGY_RE.match(line)
        if fe_m:
            ionic_index += 1
            ionic_steps.append(ionic_index)
            ionic_energies.append(float(fe_m.group(1)) * _RY_TO_EV)
            continue

        # Total force
        tf_m = _TOTAL_FORCE_RE.match(line)
        if tf_m:
            # QE Total force is in Ry/Bohr, convert to eV/A
            # force_ry_bohr * 13.605693 / 0.529177 = eV/A
            force_val = float(tf_m.group(1)) * _RY_TO_EV / 0.529177249
            ionic_max_forces.append(force_val)
            continue

    return {
        "scf_steps": scf_steps,
        "scf_energies": scf_energies,
        "scf_des": scf_des,
        "ionic_steps": ionic_steps,
        "ionic_energies": ionic_energies,
        "ionic_max_forces": ionic_max_forces,
        "algorithm": algorithm,
        "converged": converged,
    }


@register_parser("qe", "convergence")
class QEConvergenceProvider:
    """QE convergence analysis provider.

    One-Provider, Multiple-Trigger Pattern:
    AnalysisCapability entries for scf/relax/md all route to this provider
    because QE writes the same pw.x output format regardless of calc type.
    """

    engine = "qe"
    object_type = "convergence"

    def can_parse(self, raw_dir: Path) -> bool:
        for p in raw_dir.iterdir():
            if p.suffix == ".out" and p.is_file():
                return True
        return False

    def parse(self, evidence: EvidenceBundle) -> Convergence:
        """Parse QE output and return Convergence object."""
        output_path = _select_output_file(
            evidence.primary_raw_dir,
            evidence.gen_steps,
        )

        parsed = parse_qe_convergence(output_path)

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
            parser_name="qe_convergence",
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
            ionic_max_force=(
                np.array(parsed["ionic_max_forces"], dtype=float)
                if parsed["ionic_max_forces"]
                else None
            ),
            converged=parsed["converged"],
            n_ionic_steps=len(parsed["ionic_steps"]),
            algorithm=parsed["algorithm"],
        )
