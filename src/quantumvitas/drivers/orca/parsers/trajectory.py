"""ORCA trajectory parser (opt .xyz + .out)."""
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


def _parse_orca_trj_xyz(path: Path) -> list[dict]:
    """Parse ORCA trajectory XYZ (*_trj.xyz).

    Comment line: `Coordinates from ORCA-job water_opt E -76.321097057767`
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
        i += 1
        if i >= len(lines):
            break
        comment = lines[i]
        energy = None
        m = re.search(r"E\s+([-\d.Ee+]+)", comment)
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


@register_parser("orca", "trajectory")
class ORCATrajectoryParser:
    """ORCA trajectory parser."""

    engine = "orca"
    object_type = "trajectory"

    def can_parse(self, raw_dir: Path) -> bool:
        return bool(list(raw_dir.glob("*_trj.xyz")) or list(raw_dir.glob("*_opt.xyz")))

    def parse(self, evidence: EvidenceBundle) -> Trajectory:
        raw_dir = evidence.primary_raw_dir

        # Find trajectory XYZ
        trj_files = sorted(raw_dir.glob("*_trj.xyz"))
        if not trj_files:
            trj_files = sorted(raw_dir.glob("*_opt.xyz"))
        if not trj_files:
            raise FileNotFoundError(f"No ORCA trajectory XYZ found in {raw_dir}")

        source_files: list[SourceFileStat] = []
        trj_path = trj_files[0]
        source_files.append(SourceFileStat.from_path(trj_path, evidence.calc_dir))

        parsed = _parse_orca_trj_xyz(trj_path)
        if not parsed:
            raise ValueError(f"No frames in {trj_path}")

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
            parser_name="orca_trajectory",
            parser_version="1.0",
        )

        return Trajectory(meta=meta, frames=frames, trajectory_type=traj_type)
