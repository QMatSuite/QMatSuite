"""Gaussian trajectory parser (geometry opt from .log)."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List

import numpy as np

from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.core.analysis.trajectory.model import Frame, Trajectory
from quantumvitas.parsers.registry import register_parser

logger = logging.getLogger(__name__)

HA_TO_EV = 27.211386245988

# Atomic number → symbol
_Z_TO_SYMBOL = {
    1: "H", 2: "He", 3: "Li", 4: "Be", 5: "B", 6: "C", 7: "N", 8: "O",
    9: "F", 10: "Ne", 11: "Na", 12: "Mg", 13: "Al", 14: "Si", 15: "P",
    16: "S", 17: "Cl", 18: "Ar", 19: "K", 20: "Ca", 22: "Ti", 26: "Fe",
    29: "Cu", 30: "Zn", 35: "Br", 53: "I",
}


def _parse_gaussian_opt_log(path: Path) -> list[dict]:
    """Parse Gaussian log for optimization trajectory.

    Extracts:
    - Standard orientation geometry blocks
    - SCF Done energies
    Pairs each geometry with its preceding energy.
    """
    text = path.read_text(errors="replace")

    # Extract all SCF energies
    scf_re = re.compile(r"SCF Done:\s+E\(\w+\)\s*=\s*([-\d.]+)")
    energies = [float(m.group(1)) * HA_TO_EV for m in scf_re.finditer(text)]

    # Extract all Standard orientation blocks
    geom_re = re.compile(
        r"Standard orientation:.*?-{5,}\n.*?-{5,}\n(.*?)-{5,}",
        re.DOTALL,
    )
    geom_blocks = geom_re.findall(text)

    frames: list[dict] = []
    for i, block in enumerate(geom_blocks):
        species = []
        coords = []
        for line in block.strip().splitlines():
            parts = line.split()
            if len(parts) >= 6:
                try:
                    z = int(parts[1])
                    x, y, z_coord = float(parts[3]), float(parts[4]), float(parts[5])
                    species.append(_Z_TO_SYMBOL.get(z, f"Z{z}"))
                    coords.append([x, y, z_coord])
                except (ValueError, IndexError):
                    continue

        if coords:
            energy = energies[i] if i < len(energies) else (
                energies[-1] if energies else None
            )
            frames.append({
                "species": species,
                "positions": np.array(coords, dtype=float),
                "energy": energy,
            })

    return frames


@register_parser("gaussian", "trajectory")
class GaussianTrajectoryParser:
    """Gaussian trajectory parser."""

    engine = "gaussian"
    object_type = "trajectory"

    def can_parse(self, raw_dir: Path) -> bool:
        for pattern in ["*.log", "*.out"]:
            for f in raw_dir.glob(pattern):
                # Quick check: does it contain Standard orientation?
                header = f.read_text(errors="replace")[:5000]
                if "Gaussian" in header:
                    return True
        return False

    def parse(self, evidence: EvidenceBundle) -> Trajectory:
        raw_dir = evidence.primary_raw_dir

        log_files = sorted(raw_dir.glob("*.log")) + sorted(raw_dir.glob("*.out"))
        log_file = None
        for f in log_files:
            header = f.read_text(errors="replace")[:5000]
            if "Gaussian" in header:
                log_file = f
                break

        if log_file is None:
            raise FileNotFoundError(f"No Gaussian log found in {raw_dir}")

        source_files = [SourceFileStat.from_path(log_file, evidence.calc_dir)]

        parsed = _parse_gaussian_opt_log(log_file)
        if not parsed:
            raise ValueError(f"No geometry frames in {log_file}")

        frames: list[Frame] = []
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

        traj_type = "relax"

        meta = AnalysisObjectMeta.create(
            object_type="trajectory",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="gaussian_trajectory",
            parser_version="1.0",
        )

        return Trajectory(meta=meta, frames=frames, trajectory_type=traj_type)
