"""ABINIT trajectory parser (_HIST.nc + .abo fallback)."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Optional

import numpy as np

from qmatsuite.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.core.analysis.trajectory.model import Frame, Trajectory
from qmatsuite.parsers.registry import register_parser

logger = logging.getLogger(__name__)

HA_TO_EV = 27.211386245988
BOHR_TO_ANG = 0.529177249
HA_BOHR_TO_EV_ANG = HA_TO_EV / BOHR_TO_ANG

# Atomic number to symbol (small table for common elements)
_Z_TO_SYMBOL = {
    1: "H", 2: "He", 3: "Li", 4: "Be", 5: "B", 6: "C", 7: "N", 8: "O",
    9: "F", 10: "Ne", 11: "Na", 12: "Mg", 13: "Al", 14: "Si", 15: "P",
    16: "S", 17: "Cl", 18: "Ar", 19: "K", 20: "Ca", 22: "Ti", 24: "Cr",
    25: "Mn", 26: "Fe", 27: "Co", 28: "Ni", 29: "Cu", 30: "Zn",
    31: "Ga", 32: "Ge", 33: "As", 34: "Se", 35: "Br", 47: "Ag",
    56: "Ba", 79: "Au",
}


def _parse_hist_nc(path: Path) -> dict:
    """Parse ABINIT _HIST.nc file using scipy.io.netcdf (stdlib-compatible)."""
    try:
        from scipy.io import netcdf_file
    except ImportError:
        raise ImportError("scipy required for ABINIT _HIST.nc parsing")

    with netcdf_file(str(path), "r", mmap=False) as ds:
        # typat and znucl for species mapping
        typat = np.array(ds.variables["typat"][:], dtype=int)
        znucl = np.array(ds.variables["znucl"][:], dtype=float)

        species = []
        for t in typat:
            z = int(round(znucl[t - 1]))
            species.append(_Z_TO_SYMBOL.get(z, f"Z{z}"))

        # xcart (Bohr) → Angstrom
        xcart = np.array(ds.variables["xcart"][:], dtype=float) * BOHR_TO_ANG

        # rprimd (Bohr) → Angstrom
        rprimd = np.array(ds.variables["rprimd"][:], dtype=float) * BOHR_TO_ANG

        # etotal (Ha) → eV
        etotal = np.array(ds.variables["etotal"][:], dtype=float) * HA_TO_EV

        # fcart (Ha/Bohr) → eV/Å (optional)
        fcart = None
        if "fcart" in ds.variables:
            fcart = np.array(ds.variables["fcart"][:], dtype=float) * HA_BOHR_TO_EV_ANG

        # strten (optional, Ha/Bohr^3)
        strten = None
        if "strten" in ds.variables:
            strten = np.array(ds.variables["strten"][:], dtype=float)

    n_steps = xcart.shape[0]
    return {
        "species": species,
        "xcart": xcart,
        "rprimd": rprimd,
        "etotal": etotal,
        "fcart": fcart,
        "strten": strten,
        "n_steps": n_steps,
    }


def _parse_abo_text(path: Path) -> dict:
    """Fallback: parse .abo text for trajectory (limited data)."""
    text = path.read_text(errors="replace")
    energies: list[float] = []
    for m in re.finditer(r"Total energy\s*\(etotal\)\s*\[Ha\]\s*=\s*([-\d.Ee+]+)", text):
        energies.append(float(m.group(1)) * HA_TO_EV)
    return {"energies": energies}


@register_parser("abinit", "trajectory")
class ABINITTrajectoryParser:
    """ABINIT trajectory parser."""

    engine = "abinit"
    object_type = "trajectory"

    def can_parse(self, raw_dir: Path) -> bool:
        return bool(list(raw_dir.glob("*_HIST.nc")) or list(raw_dir.glob("*_HIST")))

    def parse(self, evidence: EvidenceBundle) -> Trajectory:
        raw_dir = evidence.primary_raw_dir
        hist_files = sorted(raw_dir.glob("*_HIST.nc"))
        if not hist_files:
            raise FileNotFoundError(f"No ABINIT _HIST.nc found in {raw_dir}")

        source_files: list[SourceFileStat] = []
        hist_path = hist_files[0]
        source_files.append(SourceFileStat.from_path(hist_path, evidence.calc_dir))

        parsed = _parse_hist_nc(hist_path)

        frames: list[Frame] = []
        for idx in range(parsed["n_steps"]):
            forces = parsed["fcart"][idx] if parsed["fcart"] is not None else None
            frames.append(Frame(
                frame_index=idx,
                positions=parsed["xcart"][idx],
                species=list(parsed["species"]),
                cell=parsed["rprimd"][idx],
                pbc=(True, True, True),
                iteration=idx,
                energy=parsed["etotal"][idx],
                forces=forces,
            ))

        if not frames:
            raise ValueError(f"No frames in {hist_path}")

        traj_type = "md" if any("md" in gs for gs in evidence.gen_steps) else "relax"

        meta = AnalysisObjectMeta.create(
            object_type="trajectory",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="abinit_trajectory",
            parser_version="1.0",
        )

        return Trajectory(meta=meta, frames=frames, trajectory_type=traj_type)
