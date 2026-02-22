"""ORCA convergence analysis provider.

Parses SCF iteration energies and geometry optimization cycles from ORCA output.
Registers with the parser registry as ("orca", "convergence").
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

# SCF iteration line:
#   ITER   Energy          Delta-E        Max-DP      RMS-DP      [F,P]     Damp
#      0   -76.0241072820   0.000000000000 0.05259...
_SCF_ITER_RE = re.compile(
    r"^\s*(\d+)\s+([-\d.]+)\s+([-\d.Ee+]+)"
)

# SCF converged marker
_SCF_CONVERGED_RE = re.compile(
    r"SCF CONVERGED AFTER\s+(\d+)\s+CYCLES"
)

# Final energy
_FINAL_ENERGY_RE = re.compile(
    r"FINAL SINGLE POINT ENERGY\s+([-\d.]+)"
)

# Geometry optimization cycle
_OPT_CYCLE_RE = re.compile(
    r"GEOMETRY OPTIMIZATION CYCLE\s+(\d+)"
)

# Optimization converged
_OPT_CONVERGED_RE = re.compile(
    r"THE OPTIMIZATION HAS CONVERGED"
)


def parse_orca_convergence(text: str) -> dict:
    """Parse ORCA output text into convergence data.

    Returns dict with:
    - scf_steps: list of int (cumulative index)
    - scf_energies: list of float (eV)
    - scf_des: list of float (energy change, eV)
    - ionic_steps: list of int (opt cycle numbers)
    - ionic_energies: list of float (eV, final energy per opt cycle)
    - algorithm: str
    - converged: bool
    """
    lines = text.splitlines()

    scf_steps: List[int] = []
    scf_energies: List[float] = []
    scf_des: List[float] = []
    ionic_steps: List[int] = []
    ionic_energies: List[float] = []
    converged = False
    cumulative_scf = 0

    # Track whether we're inside an SCF block
    in_scf_block = False
    prev_energy: Optional[float] = None

    for line in lines:
        # Detect SCF block start
        if "ITER" in line and "Energy" in line and "Delta-E" in line:
            in_scf_block = True
            prev_energy = None
            continue

        # Detect end of SCF block
        if in_scf_block and line.strip() == "":
            in_scf_block = False
            continue

        # Parse SCF iteration lines
        if in_scf_block:
            m = _SCF_ITER_RE.match(line)
            if m:
                cumulative_scf += 1
                energy_ha = float(m.group(2))
                energy_ev = energy_ha * HARTREE_TO_EV
                scf_steps.append(cumulative_scf)
                scf_energies.append(energy_ev)
                if prev_energy is not None:
                    scf_des.append(energy_ev - prev_energy)
                else:
                    scf_des.append(0.0)
                prev_energy = energy_ev
                continue

        # Optimization cycle energies — use FINAL SINGLE POINT ENERGY
        energy_m = _FINAL_ENERGY_RE.search(line)
        if energy_m:
            energy_ev = float(energy_m.group(1)) * HARTREE_TO_EV
            # This is the energy at the end of the current opt cycle
            # We collect all and use them as ionic energies below

        # Opt cycle marker
        opt_m = _OPT_CYCLE_RE.search(line)
        if opt_m:
            cycle = int(opt_m.group(1))
            ionic_steps.append(cycle)

        # Convergence marker
        if _OPT_CONVERGED_RE.search(line):
            converged = True

    # SCF convergence (if no optimization)
    scf_conv_m = _SCF_CONVERGED_RE.search(text)
    if scf_conv_m and not ionic_steps:
        converged = True

    # Collect ionic energies from FINAL SINGLE POINT ENERGY lines
    all_final_energies = _FINAL_ENERGY_RE.findall(text)
    if ionic_steps and all_final_energies:
        # Each optimization cycle produces one FINAL SINGLE POINT ENERGY
        ionic_energies = [
            float(e) * HARTREE_TO_EV
            for e in all_final_energies[:len(ionic_steps)]
        ]
    elif not ionic_steps and all_final_energies:
        # Single-point: one ionic step with final energy
        ionic_steps = [1]
        ionic_energies = [float(all_final_energies[-1]) * HARTREE_TO_EV]

    # Heuristic: if no SCF dE check, use last dE
    if not converged and scf_des:
        converged = abs(scf_des[-1]) < 1e-4 * HARTREE_TO_EV

    return {
        "scf_steps": scf_steps,
        "scf_energies": scf_energies,
        "scf_des": scf_des,
        "ionic_steps": ionic_steps,
        "ionic_energies": ionic_energies,
        "algorithm": "ORCA-SCF",
        "converged": converged,
    }


@register_parser("orca", "convergence")
class ORCAConvergenceProvider:
    """ORCA convergence analysis provider.

    Routes from AnalysisCapability entries for scf and relax gen steps.
    """

    engine = "orca"
    object_type = "convergence"

    def can_parse(self, raw_dir: Path) -> bool:
        for f in raw_dir.glob("*.out"):
            try:
                text = f.read_text(errors="replace")[:1024]
                if "O   R   C   A" in text or "ORCA" in text:
                    return True
            except OSError:
                pass
        return False

    def parse(self, evidence: EvidenceBundle) -> Convergence:
        """Parse ORCA output and return Convergence object."""
        out_file = self._find_output_file(evidence.primary_raw_dir)
        if out_file is None:
            raise FileNotFoundError(
                f"No ORCA output file found in {evidence.primary_raw_dir}"
            )

        text = out_file.read_text(encoding="utf-8", errors="replace")
        parsed = parse_orca_convergence(text)

        source_files = [SourceFileStat.from_path(out_file, evidence.calc_dir)]

        warnings: list[str] = []
        if not parsed["scf_energies"]:
            warnings.append("No SCF steps found in ORCA output.")

        meta = AnalysisObjectMeta.create(
            object_type="convergence",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="orca_convergence",
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
        """Find the main ORCA output file."""
        for name in ["orca.out", "orca_calc.out", "output.out"]:
            candidate = raw_dir / name
            if candidate.is_file():
                return candidate
        out_files = list(raw_dir.glob("*.out"))
        return out_files[0] if out_files else None
