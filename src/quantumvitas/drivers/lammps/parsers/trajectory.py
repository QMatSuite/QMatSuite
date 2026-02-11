"""LAMMPS trajectory parser (dump file + log.lammps)."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Optional

import numpy as np

from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.core.analysis.trajectory.model import Frame, Trajectory
from quantumvitas.parsers.registry import register_parser

logger = logging.getLogger(__name__)


def _parse_lammps_dump(path: Path) -> list[dict]:
    """Parse LAMMPS custom dump file.

    Reads ITEM: ATOMS header to discover column names, then parses
    positions, velocities, forces adaptively.
    """
    frames: list[dict] = []
    lines = path.read_text(errors="replace").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line == "ITEM: TIMESTEP":
            i += 1
            timestep = int(lines[i].strip())
            i += 1
        elif line == "ITEM: NUMBER OF ATOMS":
            i += 1
            n_atoms = int(lines[i].strip())
            i += 1
        elif line.startswith("ITEM: BOX BOUNDS"):
            bounds = []
            i += 1
            for _ in range(3):
                parts = lines[i].split()
                bounds.append([float(parts[0]), float(parts[1])])
                i += 1
            cell = np.diag([b[1] - b[0] for b in bounds])
        elif line.startswith("ITEM: ATOMS"):
            col_names = line.replace("ITEM: ATOMS", "").split()
            i += 1
            atom_data = []
            for _ in range(n_atoms):
                if i >= len(lines):
                    break
                atom_data.append(lines[i].split())
                i += 1

            if len(atom_data) != n_atoms:
                continue

            # Build column index
            col_idx = {name: j for j, name in enumerate(col_names)}

            # Positions: prefer xu,yu,zu (unwrapped) else x,y,z
            pos_cols = None
            if all(c in col_idx for c in ("xu", "yu", "zu")):
                pos_cols = [col_idx["xu"], col_idx["yu"], col_idx["zu"]]
            elif all(c in col_idx for c in ("x", "y", "z")):
                pos_cols = [col_idx["x"], col_idx["y"], col_idx["z"]]

            positions = None
            if pos_cols is not None:
                positions = np.array(
                    [[float(row[c]) for c in pos_cols] for row in atom_data],
                    dtype=float,
                )

            # Velocities
            velocities = None
            if all(c in col_idx for c in ("vx", "vy", "vz")):
                vel_cols = [col_idx["vx"], col_idx["vy"], col_idx["vz"]]
                velocities = np.array(
                    [[float(row[c]) for c in vel_cols] for row in atom_data],
                    dtype=float,
                )

            # Forces
            forces = None
            if all(c in col_idx for c in ("fx", "fy", "fz")):
                frc_cols = [col_idx["fx"], col_idx["fy"], col_idx["fz"]]
                forces = np.array(
                    [[float(row[c]) for c in frc_cols] for row in atom_data],
                    dtype=float,
                )

            # Types → species (just "1", "2", etc. unless we have a data file)
            type_col = col_idx.get("type")
            if type_col is not None:
                species = [atom_data[j][type_col] for j in range(n_atoms)]
            else:
                species = ["X"] * n_atoms

            frames.append({
                "timestep": timestep,
                "positions": positions,
                "velocities": velocities,
                "forces": forces,
                "species": species,
                "cell": cell,
            })
        else:
            i += 1

    return frames


def _parse_lammps_thermo(path: Path) -> list[dict]:
    """Parse thermo output from log.lammps.

    Returns list of dicts with keys matching thermo_style columns.
    """
    rows: list[dict] = []
    lines = path.read_text(errors="replace").splitlines()
    header: list[str] = []
    in_thermo = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Step") and "Temp" in stripped:
            header = stripped.split()
            in_thermo = True
            continue
        if in_thermo:
            if stripped.startswith("Loop time") or not stripped:
                in_thermo = False
                continue
            parts = stripped.split()
            if len(parts) == len(header):
                try:
                    row = {h: float(v) for h, v in zip(header, parts)}
                    rows.append(row)
                except ValueError:
                    in_thermo = False
    return rows


@register_parser("lammps", "trajectory")
class LAMMPSTrajectoryParser:
    """LAMMPS trajectory parser."""

    engine = "lammps"
    object_type = "trajectory"

    def can_parse(self, raw_dir: Path) -> bool:
        return bool(list(raw_dir.glob("*.lammpstrj")) or list(raw_dir.glob("dump.*")))

    def parse(self, evidence: EvidenceBundle) -> Trajectory:
        raw_dir = evidence.primary_raw_dir
        dump_files = sorted(raw_dir.glob("*.lammpstrj")) or sorted(raw_dir.glob("dump.*"))
        if not dump_files:
            raise FileNotFoundError(f"No LAMMPS dump file found in {raw_dir}")

        source_files: list[SourceFileStat] = []
        dump_path = dump_files[0]
        source_files.append(SourceFileStat.from_path(dump_path, evidence.calc_dir))

        dump_frames = _parse_lammps_dump(dump_path)
        if not dump_frames:
            raise ValueError(f"No frames in {dump_path}")

        # Thermo data (optional)
        thermo: list[dict] = []
        log_files = sorted(raw_dir.glob("log.lammps"))
        if log_files:
            source_files.append(SourceFileStat.from_path(log_files[0], evidence.calc_dir))
            thermo = _parse_lammps_thermo(log_files[0])

        # Build thermo lookup by timestep
        thermo_by_step: dict[int, dict] = {}
        for row in thermo:
            step = int(row.get("Step", -1))
            if step >= 0:
                thermo_by_step[step] = row

        frames: list[Frame] = []
        for idx, df in enumerate(dump_frames):
            ts = df["timestep"]
            th = thermo_by_step.get(ts, {})

            energy = th.get("PotEng") or th.get("TotEng")
            temperature = th.get("Temp")
            pressure = th.get("Press")
            kinetic_energy = th.get("KinEng")

            cell = df["cell"]
            pbc = (True, True, True) if cell is not None else (False, False, False)

            frames.append(Frame(
                frame_index=idx,
                positions=df["positions"],
                species=df["species"],
                cell=cell,
                pbc=pbc,
                iteration=ts,
                energy=energy,
                forces=df["forces"],
                velocities=df["velocities"],
                temperature=temperature,
                pressure=pressure,
                kinetic_energy=kinetic_energy,
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
            parser_name="lammps_trajectory",
            parser_version="1.0",
        )

        return Trajectory(meta=meta, frames=frames, trajectory_type=traj_type)
