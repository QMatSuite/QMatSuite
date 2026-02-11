"""QE NEB trajectory parser — AXSF + .path format."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import numpy as np

from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.core.analysis.trajectory import Trajectory
from quantumvitas.core.analysis.trajectory.model import Frame
from quantumvitas.parsers.registry import register_parser

# Ry -> eV
_RY_TO_EV = 13.605693122994


def parse_axsf(text: str) -> dict:
    """Parse AXSF (animated XSF) file.

    Returns dict with:
    - n_images: int
    - cell: (3, 3) array in Angstrom
    - frames: list of {species: [str], positions: (N,3), forces: (N,3) or None}
    """
    lines = text.strip().splitlines()
    n_images = 0
    cell = None
    frames: list[dict] = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("ANIMSTEPS"):
            n_images = int(line.split()[1])
            i += 1
            continue

        if line == "PRIMVEC":
            rows = []
            for j in range(3):
                vals = lines[i + 1 + j].split()
                rows.append([float(v) for v in vals])
            cell = np.array(rows)
            i += 4
            continue

        if line.startswith("PRIMCOORD"):
            i += 1
            parts = lines[i].strip().split()
            n_atoms = int(parts[0])
            i += 1

            species = []
            positions = []
            forces = []
            for _ in range(n_atoms):
                tokens = lines[i].strip().split()
                species.append(tokens[0])
                positions.append([float(tokens[1]), float(tokens[2]), float(tokens[3])])
                if len(tokens) >= 7:
                    forces.append([float(tokens[4]), float(tokens[5]), float(tokens[6])])
                i += 1

            frame = {
                "species": species,
                "positions": np.array(positions),
                "forces": np.array(forces) if forces else None,
            }
            frames.append(frame)
            continue

        i += 1

    return {
        "n_images": n_images,
        "cell": cell,
        "frames": frames,
    }


def parse_path_file(text: str) -> dict:
    """Parse QE NEB .path file for per-image energies.

    Returns dict with:
    - n_images: int
    - energies: list[float] (Ry)
    """
    lines = text.strip().splitlines()
    energies: list[float] = []
    n_images = 0

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("NUMBER OF IMAGES"):
            i += 1
            n_images = int(lines[i].strip())
            i += 1
            continue

        if line.startswith("Image:"):
            i += 1
            energy_ry = float(lines[i].strip())
            energies.append(energy_ry)
            i += 1
            # Skip atom lines until next Image or end
            while i < len(lines) and not lines[i].strip().startswith("Image:") and lines[i].strip():
                i += 1
            continue

        i += 1

    return {
        "n_images": n_images,
        "energies": energies,
    }


@register_parser("qe", "neb_trajectory")
class QENEBTrajectoryProvider:
    """QE NEB trajectory parser.

    Parses AXSF for per-image geometries and .path for per-image energies.
    """

    engine = "qe"
    object_type = "neb_trajectory"

    def can_parse(self, raw_dir: Path) -> bool:
        return any(p.suffix == ".axsf" for p in raw_dir.iterdir() if p.is_file())

    def parse(self, evidence: EvidenceBundle) -> Trajectory:
        """Parse NEB AXSF + .path and return Trajectory."""
        raw_dir = evidence.primary_raw_dir

        axsf_files = list(raw_dir.glob("*.axsf"))
        if not axsf_files:
            raise FileNotFoundError(f"No .axsf file found in {raw_dir}")
        axsf_path = axsf_files[0]

        axsf_data = parse_axsf(axsf_path.read_text(encoding="utf-8"))

        # Parse .path file for energies
        path_files = list(raw_dir.glob("*.path"))
        energies_ev: Optional[List[float]] = None
        if path_files:
            path_data = parse_path_file(path_files[0].read_text(encoding="utf-8"))
            energies_ev = [e * _RY_TO_EV for e in path_data["energies"]]

        cell = axsf_data["cell"]
        n_images = len(axsf_data["frames"])
        has_pbc = cell is not None

        frames: List[Frame] = []
        for idx, fdata in enumerate(axsf_data["frames"]):
            energy = None
            if energies_ev is not None and idx < len(energies_ev):
                energy = energies_ev[idx]

            frames.append(Frame(
                frame_index=idx,
                positions=fdata["positions"],
                species=fdata["species"],
                cell=cell,
                pbc=(has_pbc, has_pbc, has_pbc),
                forces=fdata["forces"],
                energy=energy,
                image_index=idx + 1,
                iteration=idx + 1,
            ))

        source_files = [SourceFileStat.from_path(axsf_path, evidence.calc_dir)]
        if path_files:
            source_files.append(SourceFileStat.from_path(path_files[0], evidence.calc_dir))

        meta = AnalysisObjectMeta.create(
            object_type="neb_trajectory",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="qe_neb_trajectory",
            parser_version="1.0",
        )

        return Trajectory(
            meta=meta,
            frames=frames,
            trajectory_type="neb",
            n_images=n_images,
        )
