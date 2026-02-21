"""Siesta trajectory parser (.ANI / .MD_CAR / .MDE).

Siesta 4.x wrote per-step trajectories to ``*.ANI`` (multi-frame XYZ).
Siesta 5.x no longer writes ``.ANI``. Instead per-step geometry is written
to ``*.MD_CAR`` (POSCAR-like, always produced when running relax or md) and
per-step energies/pressures to ``*.MDE``.

Fallback: multi-frame ``*.xyz`` produced when ``WriteMDXmol T``.
"""
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

# Atomic number → element symbol (for STRUCT_OUT species extraction)
_Z_TO_SYMBOL: dict[int, str] = {
    1: "H", 2: "He", 3: "Li", 4: "Be", 5: "B", 6: "C", 7: "N", 8: "O",
    9: "F", 10: "Ne", 11: "Na", 12: "Mg", 13: "Al", 14: "Si", 15: "P",
    16: "S", 17: "Cl", 18: "Ar", 19: "K", 20: "Ca", 21: "Sc", 22: "Ti",
    23: "V", 24: "Cr", 25: "Mn", 26: "Fe", 27: "Co", 28: "Ni", 29: "Cu",
    30: "Zn", 31: "Ga", 32: "Ge", 33: "As", 34: "Se", 35: "Br", 36: "Kr",
    37: "Rb", 38: "Sr", 39: "Y", 40: "Zr", 41: "Nb", 42: "Mo", 47: "Ag",
    48: "Cd", 49: "In", 50: "Sn", 51: "Sb", 74: "W", 78: "Pt", 79: "Au",
    82: "Pb",
}


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


def _extract_species_from_struct_out(path: Path) -> list[str]:
    """Extract ordered element symbol list from Siesta STRUCT_OUT.

    STRUCT_OUT format:
        3×3 cell matrix (Angstrom)
        n_atoms
        species_idx  atomic_num  x  y  z  (fractional)
        ...
    """
    lines = path.read_text(errors="replace").splitlines()
    if len(lines) < 5:
        return []
    try:
        n_atoms = int(lines[3].strip())
    except (ValueError, IndexError):
        return []
    symbols: list[str] = []
    for i in range(4, 4 + n_atoms):
        if i >= len(lines):
            break
        parts = lines[i].split()
        if len(parts) >= 2:
            try:
                z = int(parts[1])
                symbols.append(_Z_TO_SYMBOL.get(z, f"X{z}"))
            except ValueError:
                symbols.append("X")
    return symbols


def _parse_md_car_file(path: Path, species: list[str]) -> list[dict]:
    """Parse Siesta .MD_CAR trajectory (Siesta 5.x POSCAR-like format).

    Each frame:
        ---<label>---   (system name)
        scale           (float, usually 1.0)
        a1x a1y a1z     (cell vector 1, Angstrom × scale)
        a2x a2y a2z
        a3x a3y a3z
        n_atoms
        Direct          (or Cartesian)
        x1 y1 z1
        x2 y2 z2
        ...
    """
    frames: list[dict] = []
    lines = path.read_text(errors="replace").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line.startswith("---"):
            i += 1
            continue
        i += 1  # system name line consumed
        if i >= len(lines):
            break
        # Scale factor
        try:
            scale = float(lines[i].strip())
        except (ValueError, IndexError):
            i += 1
            continue
        i += 1
        # 3 cell-vector lines
        cell: list[list[float]] = []
        for _ in range(3):
            if i >= len(lines):
                break
            parts = lines[i].split()
            if len(parts) >= 3:
                cell.append([
                    float(parts[0]) * scale,
                    float(parts[1]) * scale,
                    float(parts[2]) * scale,
                ])
            i += 1
        if len(cell) != 3:
            continue
        # n_atoms
        if i >= len(lines):
            break
        try:
            n_atoms = int(lines[i].strip())
        except ValueError:
            i += 1
            continue
        i += 1
        # Coordinate type
        if i >= len(lines):
            break
        coord_type = lines[i].strip().lower()
        i += 1
        is_direct = coord_type.startswith("d")
        # Atomic positions
        positions: list[list[float]] = []
        for _ in range(n_atoms):
            if i >= len(lines):
                break
            parts = lines[i].split()
            if len(parts) >= 3:
                positions.append([float(parts[0]), float(parts[1]), float(parts[2])])
            i += 1
        if len(positions) != n_atoms:
            continue
        cell_array = np.array(cell, dtype=float)
        if is_direct:
            # fractional → Cartesian
            cart = np.dot(np.array(positions, dtype=float), cell_array)
        else:
            cart = np.array(positions, dtype=float)
        frame_species = list(species[:n_atoms]) if species else [f"X{j}" for j in range(n_atoms)]
        frames.append({
            "species": frame_species,
            "positions": cart,
            "cell": cell_array,
        })
    return frames


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
        # Priority 1: .ANI (Siesta 4.x legacy)
        if list(raw_dir.glob("*.ANI")):
            return True
        # Priority 2: .MD_CAR (Siesta 5.x — per-step POSCAR-like trajectory)
        if list(raw_dir.glob("*.MD_CAR")):
            return True
        # Priority 3: multi-frame .xyz (WriteMDXmol T)
        for f in sorted(raw_dir.glob("*.xyz")):
            try:
                n_atoms_lines = sum(
                    1 for ln in f.read_text(errors="replace").splitlines()
                    if ln.strip().isdigit()
                )
                if n_atoms_lines >= 2:
                    return True
            except Exception:
                continue
        return False

    def parse(self, evidence: EvidenceBundle) -> Trajectory:
        raw_dir = evidence.primary_raw_dir

        ani_files = sorted(raw_dir.glob("*.ANI"))
        md_car_files = sorted(raw_dir.glob("*.MD_CAR"))
        xyz_candidates = (
            []
            if (ani_files or md_car_files)
            else [
                f for f in sorted(raw_dir.glob("*.xyz"))
                if sum(
                    1 for ln in f.read_text(errors="replace").splitlines()
                    if ln.strip().isdigit()
                ) >= 2
            ]
        )

        if not ani_files and not md_car_files and not xyz_candidates:
            raise FileNotFoundError(
                f"No Siesta trajectory file (.ANI, .MD_CAR, or multi-frame .xyz) found in {raw_dir}"
            )

        source_files: list[SourceFileStat] = []

        # MDE scalars (available for all trajectory types)
        mde_rows: list[dict] = []
        mde_files = sorted(raw_dir.glob("*.MDE"))
        if mde_files:
            source_files.append(SourceFileStat.from_path(mde_files[0], evidence.calc_dir))
            mde_rows = _parse_mde_file(mde_files[0])

        if ani_files:
            # ── Siesta 4.x .ANI (multi-frame XYZ) ──────────────────────
            ani_path = ani_files[0]
            source_files.append(SourceFileStat.from_path(ani_path, evidence.calc_dir))
            raw_frames = _parse_ani_file(ani_path)
            if not raw_frames:
                raise ValueError(f"No frames in {ani_path}")

            # Cell from .out (optional, for periodic systems)
            cell: Optional[np.ndarray] = None
            out_files = sorted(raw_dir.glob("*.out"))
            if out_files:
                source_files.append(SourceFileStat.from_path(out_files[0], evidence.calc_dir))
                cell = _parse_siesta_cell_from_output(out_files[0])

            frames: list[Frame] = []
            for idx, af in enumerate(raw_frames):
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

        elif md_car_files:
            # ── Siesta 5.x .MD_CAR (per-step POSCAR-like) ───────────────
            md_car_path = md_car_files[0]
            source_files.append(SourceFileStat.from_path(md_car_path, evidence.calc_dir))

            # Get species from STRUCT_OUT (has atomic numbers for each atom)
            species: list[str] = []
            struct_out_files = sorted(raw_dir.glob("*.STRUCT_OUT"))
            if struct_out_files:
                species = _extract_species_from_struct_out(struct_out_files[0])

            raw_frames = _parse_md_car_file(md_car_path, species)
            if not raw_frames:
                raise ValueError(f"No frames in {md_car_path}")

            frames = []
            for idx, rf in enumerate(raw_frames):
                mde = mde_rows[idx] if idx < len(mde_rows) else {}
                energy = mde.get("energy_ks")
                temperature = mde.get("temperature")
                pressure_kbar = mde.get("pressure_kbar")
                pressure_gpa = pressure_kbar / 10.0 if pressure_kbar is not None else None
                cell_arr = rf.get("cell")
                pbc = (True, True, True) if cell_arr is not None else (False, False, False)
                frames.append(Frame(
                    frame_index=idx,
                    positions=rf["positions"],
                    species=rf["species"],
                    cell=cell_arr,
                    pbc=pbc,
                    iteration=idx,
                    energy=energy,
                    temperature=temperature,
                    pressure=pressure_gpa,
                ))

        else:
            # ── Multi-frame .xyz fallback (WriteMDXmol T) ────────────────
            xyz_path = xyz_candidates[0]
            source_files.append(SourceFileStat.from_path(xyz_path, evidence.calc_dir))
            raw_frames = _parse_ani_file(xyz_path)  # same XYZ format
            if not raw_frames:
                raise ValueError(f"No frames in {xyz_path}")

            cell_xyz: Optional[np.ndarray] = None
            out_files = sorted(raw_dir.glob("*.out"))
            if out_files:
                source_files.append(SourceFileStat.from_path(out_files[0], evidence.calc_dir))
                cell_xyz = _parse_siesta_cell_from_output(out_files[0])

            frames = []
            for idx, af in enumerate(raw_frames):
                mde = mde_rows[idx] if idx < len(mde_rows) else {}
                energy = mde.get("energy_ks")
                temperature = mde.get("temperature")
                pressure_kbar = mde.get("pressure_kbar")
                pressure_gpa = pressure_kbar / 10.0 if pressure_kbar is not None else None
                pbc = (True, True, True) if cell_xyz is not None else (False, False, False)
                frames.append(Frame(
                    frame_index=idx,
                    positions=af["positions"],
                    species=af["species"],
                    cell=np.array(cell_xyz, copy=True) if cell_xyz is not None else None,
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
