"""GPAW trajectory parser (ASE .traj files)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import numpy as np

from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.core.analysis.trajectory.model import Frame, Trajectory
from quantumvitas.parsers.registry import register_parser

logger = logging.getLogger(__name__)


@register_parser("gpaw", "trajectory")
class GPAWTrajectoryParser:
    """GPAW trajectory parser via ASE .traj."""

    engine = "gpaw"
    object_type = "trajectory"

    def can_parse(self, raw_dir: Path) -> bool:
        return bool(list(raw_dir.glob("*.traj")))

    def parse(self, evidence: EvidenceBundle) -> Trajectory:
        raw_dir = evidence.primary_raw_dir
        traj_files = sorted(raw_dir.glob("*.traj"))
        if not traj_files:
            raise FileNotFoundError(f"No .traj file found in {raw_dir}")

        traj_path = traj_files[0]
        source_files = [SourceFileStat.from_path(traj_path, evidence.calc_dir)]

        try:
            from ase.io import read as ase_read
        except ImportError:
            raise ImportError("ASE required for GPAW trajectory parsing")

        images = ase_read(str(traj_path), index=":")
        if not isinstance(images, list):
            images = [images]

        if not images:
            raise ValueError(f"No frames in {traj_path}")

        frames: list[Frame] = []
        for idx, atoms in enumerate(images):
            positions = atoms.get_positions()
            species = atoms.get_chemical_symbols()
            cell = atoms.get_cell()
            cell_array = np.array(cell, dtype=float)
            pbc = tuple(atoms.get_pbc().tolist())

            energy = None
            forces = None
            try:
                energy = atoms.get_potential_energy()
            except Exception:
                pass
            try:
                forces = atoms.get_forces()
            except Exception:
                pass

            # If cell is zero (no periodic), set to None
            if np.allclose(cell_array, 0.0):
                cell_array = None
                pbc = (False, False, False)

            frames.append(Frame(
                frame_index=idx,
                positions=positions,
                species=list(species),
                cell=cell_array,
                pbc=pbc,
                iteration=idx,
                energy=energy,
                forces=forces,
            ))

        traj_type = "md" if any("md" in gs for gs in evidence.gen_steps) else "relax"

        meta = AnalysisObjectMeta.create(
            object_type="trajectory",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="gpaw_trajectory",
            parser_version="1.0",
        )

        return Trajectory(meta=meta, frames=frames, trajectory_type=traj_type)
