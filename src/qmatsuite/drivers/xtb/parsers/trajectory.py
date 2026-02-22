"""xTB trajectory parser (xtbopt.log / xtb.trj)."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List

import numpy as np

from qmatsuite.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.core.analysis.trajectory.model import Frame, Trajectory
from qmatsuite.parsers.registry import register_parser

logger = logging.getLogger(__name__)

HA_TO_EV = 27.211386245988


def _parse_xtb_xyz(path: Path) -> list[dict]:
    """Parse xTB multi-frame XYZ (xtbopt.log or xtb.trj).

    Comment line format: ` energy: -5.070364560763 gnorm: 0.007345 xtb: 6.7.1 (...)`
    """
    frames: list[dict] = []
    lines = path.read_text(errors="replace").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        try:
            n_atoms = int(line)
        except ValueError:
            i += 1
            continue
        # Comment line
        i += 1
        if i >= len(lines):
            break
        comment = lines[i]
        energy = None
        m = re.search(r"energy:\s*([-\d.Ee+]+)", comment)
        if m:
            energy = float(m.group(1)) * HA_TO_EV  # Ha → eV
        i += 1

        species = []
        coords = []
        for _ in range(n_atoms):
            if i >= len(lines):
                break
            parts = lines[i].split()
            if len(parts) >= 4:
                species.append(parts[0])
                coords.append([float(parts[1]), float(parts[2]), float(parts[3])])
            i += 1

        if len(coords) == n_atoms:
            frames.append({
                "species": species,
                "positions": np.array(coords, dtype=float),
                "energy": energy,
            })

    return frames


@register_parser("xtb", "trajectory")
class XTBTrajectoryParser:
    """xTB trajectory parser."""

    engine = "xtb"
    object_type = "trajectory"

    def can_parse(self, raw_dir: Path) -> bool:
        return bool(
            list(raw_dir.glob("xtbopt.log"))
            or list(raw_dir.glob("xtb.trj"))
            or list(raw_dir.glob("xtb_md.trj"))
        )

    def parse(self, evidence: EvidenceBundle) -> Trajectory:
        raw_dir = evidence.primary_raw_dir

        # Priority: xtbopt.log (relax) > xtb.trj / xtb_md.trj (MD)
        source_files: list[SourceFileStat] = []
        traj_path = None
        for pattern in ["xtbopt.log", "xtb_md.trj", "xtb.trj"]:
            matches = sorted(raw_dir.glob(pattern))
            if matches:
                traj_path = matches[0]
                break

        if traj_path is None:
            raise FileNotFoundError(f"No xTB trajectory file found in {raw_dir}")

        source_files.append(SourceFileStat.from_path(traj_path, evidence.calc_dir))
        parsed = _parse_xtb_xyz(traj_path)
        if not parsed:
            raise ValueError(f"No frames in {traj_path}")

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

        # Detect type
        traj_type = "relax"
        if any("md" in gs for gs in evidence.gen_steps):
            traj_type = "md"
        elif "md" in traj_path.name.lower() or "trj" in traj_path.name.lower():
            traj_type = "md"

        meta = AnalysisObjectMeta.create(
            object_type="trajectory",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="xtb_trajectory",
            parser_version="1.0",
        )

        return Trajectory(meta=meta, frames=frames, trajectory_type=traj_type)
