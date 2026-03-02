"""MACE trajectory parser.

Parses ``trajectory.jsonl`` files produced by MACE relax/MD scripts.
Each line is a JSON object representing one trajectory frame.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Union

import numpy as np

from qmatsuite.core.analysis.base import AnalysisObjectMeta
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.core.analysis.trajectory.model import Frame, Trajectory
from qmatsuite.parsers.registry import register_parser


@register_parser("mace", "trajectory")
class MACETrajectoryParser:
    """Parse MACE trajectory.jsonl into a Trajectory object."""

    engine = "mace"
    object_type = "trajectory"

    def can_parse(self, raw_dir: Path) -> bool:
        traj_path = raw_dir / "trajectory.jsonl"
        return traj_path.is_file()

    def parse(self, evidence: Union[EvidenceBundle, Path], **kwargs: Any) -> Trajectory:
        raw_dir = evidence.primary_raw_dir if isinstance(evidence, EvidenceBundle) else evidence
        traj_path = raw_dir / "trajectory.jsonl"
        if not traj_path.is_file():
            return _empty_trajectory("relax", "No trajectory.jsonl found")

        try:
            text = traj_path.read_text(encoding="utf-8")
        except OSError as exc:
            return _empty_trajectory("relax", f"Failed to read trajectory.jsonl: {exc}")

        frames = _parse_jsonl_frames(text)
        if not frames:
            return _empty_trajectory("relax", "No frames in trajectory.jsonl")

        # Detect trajectory type from frame content
        traj_type = "md" if frames[0].time is not None else "relax"

        source_files = []
        try:
            from qmatsuite.core.analysis.base import SourceFileStat
            stat = traj_path.stat()
            source_files.append(SourceFileStat(
                path=str(traj_path),
                size_bytes=stat.st_size,
                mtime=stat.st_mtime,
            ))
        except Exception:
            pass

        meta = AnalysisObjectMeta.create(
            object_type="trajectory",
            source_files=source_files,
            engine_name="mace",
            parser_name="MACETrajectoryParser",
            parser_version="1.0",
        )

        return Trajectory(
            meta=meta,
            frames=frames,
            trajectory_type=traj_type,
        )


def _parse_jsonl_frames(text: str) -> list[Frame]:
    """Parse JSONL text into Frame objects."""
    frames: list[Frame] = []
    for line_num, line in enumerate(text.strip().splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        frame = _frame_from_dict(data, line_num)
        if frame is not None:
            frames.append(frame)

    return frames


def _frame_from_dict(data: dict[str, Any], fallback_index: int) -> Frame | None:
    """Convert a JSONL frame dict to a Frame object."""
    positions = data.get("positions")
    species = data.get("species")
    if not positions or not species:
        return None

    positions_arr = np.array(positions, dtype=float)
    cell_data = data.get("cell")
    cell = np.array(cell_data, dtype=float) if cell_data else None

    # Determine PBC from cell presence
    pbc = (True, True, True) if cell is not None else (False, False, False)

    forces_data = data.get("forces_eV_per_ang")
    forces = np.array(forces_data, dtype=float) if forces_data else None

    return Frame(
        frame_index=data.get("frame_index", fallback_index),
        positions=positions_arr,
        species=species,
        cell=cell,
        pbc=pbc,
        time=data.get("time_fs"),
        iteration=data.get("frame_index", fallback_index),
        energy=data.get("energy_eV"),
        forces=forces,
        temperature=data.get("temperature_K"),
        kinetic_energy=data.get("kinetic_energy_eV"),
    )


def _empty_trajectory(traj_type: str, error: str) -> Trajectory:
    """Return an empty Trajectory with error metadata."""
    meta = AnalysisObjectMeta.create(
        object_type="trajectory",
        source_files=[],
        engine_name="mace",
        parser_name="MACETrajectoryParser",
        warnings=[error],
    )
    return Trajectory(
        meta=meta,
        frames=[],
        trajectory_type=traj_type,
    )
