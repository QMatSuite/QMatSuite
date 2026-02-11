"""CP2K trajectory parser (geo_opt / MD)."""
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

# CP2K forces are in Ha/Bohr → convert to eV/Å
HA_TO_EV = 27.211386245988
BOHR_TO_ANG = 0.529177249
HA_BOHR_TO_EV_ANG = HA_TO_EV / BOHR_TO_ANG  # ~51.422 eV/Å


def _parse_cp2k_xyz_frames(path: Path) -> list[dict]:
    """Parse CP2K extended XYZ file (*-pos-*.xyz or *-frc-*.xyz).

    Comment line format: ` i =        N, E =       -17.2211528628`
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
        step = None
        m_e = re.search(r"E\s*=\s*([-\d.Ee+]+)", comment)
        if m_e:
            energy = float(m_e.group(1))
        m_i = re.search(r"i\s*=\s*(\d+)", comment)
        if m_i:
            step = int(m_i.group(1))
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
                "coords": np.array(coords, dtype=float),
                "energy": energy,
                "step": step,
            })

    return frames


def _parse_cp2k_cell_file(path: Path) -> list[np.ndarray]:
    """Parse CP2K cell file (*-1.cell).

    Header: # Step  Time  Ax Ay Az  Bx By Bz  Cx Cy Cz  Volume
    """
    cells = []
    for line in path.read_text(errors="replace").splitlines():
        if line.strip().startswith("#") or not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 11:
            cell = np.array([
                [float(parts[2]), float(parts[3]), float(parts[4])],
                [float(parts[5]), float(parts[6]), float(parts[7])],
                [float(parts[8]), float(parts[9]), float(parts[10])],
            ], dtype=float)
            cells.append(cell)
    return cells


def _parse_cp2k_energies_from_output(path: Path) -> list[float]:
    """Extract energies from CP2K .out (ENERGY| line)."""
    energies = []
    pattern = re.compile(r"ENERGY\|\s+Total FORCE_EVAL.*energy\s+\[hartree\]\s+([-\d.Ee+]+)")
    for line in path.read_text(errors="replace").splitlines():
        m = pattern.search(line)
        if m:
            energies.append(float(m.group(1)) * HA_TO_EV)
    return energies


@register_parser("cp2k", "trajectory")
class CP2KTrajectoryParser:
    """CP2K trajectory parser."""

    engine = "cp2k"
    object_type = "trajectory"

    def can_parse(self, raw_dir: Path) -> bool:
        return bool(list(raw_dir.glob("*-pos-*.xyz")))

    def parse(self, evidence: EvidenceBundle) -> Trajectory:
        raw_dir = evidence.primary_raw_dir
        pos_files = sorted(raw_dir.glob("*-pos-*.xyz"))
        if not pos_files:
            raise FileNotFoundError(f"No CP2K position file found in {raw_dir}")

        source_files: list[SourceFileStat] = []
        pos_path = pos_files[0]
        source_files.append(SourceFileStat.from_path(pos_path, evidence.calc_dir))

        pos_frames = _parse_cp2k_xyz_frames(pos_path)
        if not pos_frames:
            raise ValueError(f"No frames in {pos_path}")

        # Forces (optional)
        frc_frames: list[dict] = []
        frc_files = sorted(raw_dir.glob("*-frc-*.xyz"))
        if frc_files:
            source_files.append(SourceFileStat.from_path(frc_files[0], evidence.calc_dir))
            frc_frames = _parse_cp2k_xyz_frames(frc_files[0])

        # Cell (optional)
        cells: list[np.ndarray] = []
        cell_files = sorted(raw_dir.glob("*-*.cell"))
        if cell_files:
            source_files.append(SourceFileStat.from_path(cell_files[0], evidence.calc_dir))
            cells = _parse_cp2k_cell_file(cell_files[0])

        # Energy from .out if not in XYZ comment
        energies_from_out: list[float] = []
        out_files = sorted(raw_dir.glob("*.out"))
        if out_files:
            source_files.append(SourceFileStat.from_path(out_files[0], evidence.calc_dir))
            energies_from_out = _parse_cp2k_energies_from_output(out_files[0])

        frames: list[Frame] = []
        for idx, pf in enumerate(pos_frames):
            # Energy: prefer XYZ comment (Ha), convert to eV
            energy = None
            if pf["energy"] is not None:
                energy = pf["energy"] * HA_TO_EV
            elif idx < len(energies_from_out):
                energy = energies_from_out[idx]

            # Forces: Ha/Bohr → eV/Å
            forces = None
            if idx < len(frc_frames):
                forces = frc_frames[idx]["coords"] * HA_BOHR_TO_EV_ANG

            # Cell
            cell = cells[idx] if idx < len(cells) else (cells[0] if cells else None)
            pbc = (True, True, True) if cell is not None else (False, False, False)

            frames.append(Frame(
                frame_index=idx,
                positions=pf["coords"],
                species=pf["species"],
                cell=cell,
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
            parser_name="cp2k_trajectory",
            parser_version="1.0",
        )

        return Trajectory(meta=meta, frames=frames, trajectory_type=traj_type)
