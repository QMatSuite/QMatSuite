"""PySCF trajectory parser (geometry optimization output)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

import numpy as np

from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.core.analysis.trajectory.model import Frame, Trajectory
from quantumvitas.parsers.registry import register_parser

HA_TO_EV = 27.211386245988

# "Geometry optimization cycle 1"
_RE_OPT_CYCLE = re.compile(r"Geometry optimization cycle\s+(\d+)")

# Cartesian coordinates block atom line:
#   "   O   0.000000   0.000000   0.117370    0.000000  0.000000  0.000000"
_RE_CART_ATOM = re.compile(
    r"^\s+([A-Z][a-z]?)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)"
    r"\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*$"
)

# "converged SCF energy = -75.3125485173168"
_RE_CONVERGED_SCF = re.compile(r"converged SCF energy\s*=\s*([-\d.]+)")

# "N * All criteria matched"
_RE_ALL_CONVERGED = re.compile(r"\d+\s+\*\s+All criteria matched")


def parse_pyscf_opt(text: str) -> list[dict]:
    """Parse PySCF Berny optimizer output for per-step geometry + energy.

    Each optimization cycle has:
    1. "Geometry optimization cycle N" + Cartesian coordinates block
    2. SCF iterations → "converged SCF energy = ..."
    3. Gradient → convergence criteria check

    Returns list of {species, positions, energy (eV)}.
    """
    lines = text.splitlines()

    # Split into optimization cycles
    cycle_starts: list[int] = []
    for i, line in enumerate(lines):
        if _RE_OPT_CYCLE.search(line):
            cycle_starts.append(i)

    if not cycle_starts:
        return []

    frames = []
    for ci, start in enumerate(cycle_starts):
        end = cycle_starts[ci + 1] if ci + 1 < len(cycle_starts) else len(lines)
        block = lines[start:end]

        # Extract geometry from "Cartesian coordinates (Angstrom)" block
        species: list[str] = []
        positions: list[list[float]] = []
        in_cart = False
        for bline in block:
            if "Cartesian coordinates (Angstrom)" in bline:
                in_cart = True
                continue
            if in_cart and "Atom" in bline and "New coordinates" in bline:
                continue  # header line
            if in_cart:
                m = _RE_CART_ATOM.match(bline)
                if m:
                    species.append(m.group(1))
                    positions.append([
                        float(m.group(2)),
                        float(m.group(3)),
                        float(m.group(4)),
                    ])
                elif species:
                    # End of atom lines
                    in_cart = False

        # Extract converged SCF energy for this cycle
        energy_ha = None
        for bline in block:
            m = _RE_CONVERGED_SCF.search(bline)
            if m:
                energy_ha = float(m.group(1))

        if species and energy_ha is not None:
            frames.append({
                "species": species,
                "positions": np.array(positions, dtype=float),
                "energy": energy_ha * HA_TO_EV,
            })

    return frames


@register_parser("pyscf", "trajectory")
class PySCFTrajectoryParser:
    """PySCF trajectory parser."""

    engine = "pyscf"
    object_type = "trajectory"

    def can_parse(self, raw_dir: Path) -> bool:
        for p in raw_dir.iterdir():
            if p.is_file() and p.suffix == ".out":
                head = p.read_text(errors="replace")[:2000]
                if "pyscf" in head.lower() and "Geometry optimization" in p.read_text(errors="replace"):
                    return True
        return False

    def parse(self, evidence: EvidenceBundle) -> Trajectory:
        raw_dir = evidence.primary_raw_dir

        out_files = sorted(raw_dir.glob("*.out"))
        if not out_files:
            raise FileNotFoundError(f"No .out file in {raw_dir}")

        src_path = out_files[0]
        text = src_path.read_text(encoding="utf-8", errors="replace")
        parsed = parse_pyscf_opt(text)
        if not parsed:
            raise ValueError(f"No optimization steps found in {src_path}")

        frames: List[Frame] = []
        for idx, pf in enumerate(parsed):
            frames.append(Frame(
                frame_index=idx,
                positions=pf["positions"],
                species=pf["species"],
                cell=None,
                pbc=(False, False, False),
                iteration=idx,
                energy=pf["energy"],
            ))

        source_files = [SourceFileStat.from_path(src_path, evidence.calc_dir)]

        meta = AnalysisObjectMeta.create(
            object_type="trajectory",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="pyscf_trajectory",
            parser_version="1.0",
        )

        return Trajectory(meta=meta, frames=frames, trajectory_type="relax")
