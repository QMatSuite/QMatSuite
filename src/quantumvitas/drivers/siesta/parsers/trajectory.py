"""Siesta trajectory parser (.ANI + .MDE)."""
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


def _parse_ani_file(path: Path) -> list[dict]:
    """Parse Siesta .ANI file (multi-frame XYZ)."""
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
        # Comment line (usually blank in ANI)
        i += 1
        if i >= len(lines):
            break
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
            })
    return frames


def _parse_mde_file(path: Path) -> list[dict]:
    """Parse Siesta .MDE file for per-step scalars.

    Format: Step  T(K)  E_KS(eV)  E_tot(eV)  Vol(A^3)  P(kBar)
    """
    rows: list[dict] = []
    for line in path.read_text(errors="replace").splitlines():
        if line.strip().startswith("#") or not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 6:
            rows.append({
                "step": int(parts[0]),
                "temperature": float(parts[1]),
                "energy_ks": float(parts[2]),
                "energy_total": float(parts[3]),
                "volume": float(parts[4]),
                "pressure_kbar": float(parts[5]),
            })
    return rows


def _parse_siesta_cell_from_output(path: Path) -> Optional[np.ndarray]:
    """Extract cell from Siesta .out (outcell section)."""
    text = path.read_text(errors="replace")
    # Look for outcell block
    m = re.search(
        r"outcell:\s+Unit cell vectors.*?\n"
        r"\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*\n"
        r"\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*\n"
        r"\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)",
        text,
    )
    if m:
        return np.array([
            [float(m.group(1)), float(m.group(2)), float(m.group(3))],
            [float(m.group(4)), float(m.group(5)), float(m.group(6))],
            [float(m.group(7)), float(m.group(8)), float(m.group(9))],
        ], dtype=float)
    return None


@register_parser("siesta", "trajectory")
class SiestaTrajectoryParser:
    """Siesta trajectory parser."""

    engine = "siesta"
    object_type = "trajectory"

    def can_parse(self, raw_dir: Path) -> bool:
        return bool(list(raw_dir.glob("*.ANI")))

    def parse(self, evidence: EvidenceBundle) -> Trajectory:
        raw_dir = evidence.primary_raw_dir
        ani_files = sorted(raw_dir.glob("*.ANI"))
        if not ani_files:
            raise FileNotFoundError(f"No Siesta .ANI file found in {raw_dir}")

        source_files: list[SourceFileStat] = []
        ani_path = ani_files[0]
        source_files.append(SourceFileStat.from_path(ani_path, evidence.calc_dir))

        ani_frames = _parse_ani_file(ani_path)
        if not ani_frames:
            raise ValueError(f"No frames in {ani_path}")

        # MDE scalars (optional)
        mde_rows: list[dict] = []
        mde_files = sorted(raw_dir.glob("*.MDE"))
        if mde_files:
            source_files.append(SourceFileStat.from_path(mde_files[0], evidence.calc_dir))
            mde_rows = _parse_mde_file(mde_files[0])

        # Cell from .out (optional)
        cell: Optional[np.ndarray] = None
        out_files = sorted(raw_dir.glob("*.out"))
        if out_files:
            source_files.append(SourceFileStat.from_path(out_files[0], evidence.calc_dir))
            cell = _parse_siesta_cell_from_output(out_files[0])

        frames: list[Frame] = []
        for idx, af in enumerate(ani_frames):
            # Merge with MDE
            mde = mde_rows[idx] if idx < len(mde_rows) else {}
            energy = mde.get("energy_ks")
            temperature = mde.get("temperature")
            pressure_kbar = mde.get("pressure_kbar")
            pressure_gpa = pressure_kbar / 10.0 if pressure_kbar is not None else None

            pbc = (True, True, True) if cell is not None else (False, False, False)

            frames.append(Frame(
                frame_index=idx,
                positions=af["positions"],
                species=af["species"],
                cell=np.array(cell, copy=True) if cell is not None else None,
                pbc=pbc,
                iteration=idx,
                energy=energy,
                temperature=temperature,
                pressure=pressure_gpa,
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
            parser_name="siesta_trajectory",
            parser_version="1.0",
        )

        return Trajectory(meta=meta, frames=frames, trajectory_type=traj_type)
