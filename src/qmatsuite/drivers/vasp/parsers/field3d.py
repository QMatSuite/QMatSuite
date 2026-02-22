"""VASP field3d analysis provider (CHGCAR/LOCPOT/ELFCAR/PARCHG parser)."""
from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np

from qmatsuite.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.core.analysis.field3d import Field3D
from qmatsuite.parsers.registry import register_parser

# Map filenames to field kinds
_FIELD_KIND_MAP = {
    "CHGCAR": "charge_density",
    "LOCPOT": "potential",
    "ELFCAR": "elf",
    "PARCHG": "partial_charge",
}

# Files to look for
_VOLUMETRIC_FILES = ["CHGCAR", "LOCPOT", "ELFCAR", "PARCHG"]


def parse_vasp_volumetric(path: Path) -> dict:
    """Parse a VASP volumetric file (CHGCAR, LOCPOT, ELFCAR, PARCHG).

    Returns dict with:
    - lattice: ndarray (3, 3) in Angstrom
    - species: list[str]
    - positions_frac: ndarray (N, 3) fractional coords
    - grid_shape: tuple (NGX, NGY, NGZ)
    - grid_data: ndarray (NGX*NGY*NGZ,) float64
    - scale: float (scale factor from POSCAR header)
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    if len(lines) < 10:
        raise ValueError(f"Volumetric file too short: {path}")

    # Line 0: comment
    # Line 1: scale factor
    scale = float(lines[1].strip())

    # Lines 2-4: lattice vectors
    lattice = np.array([
        [float(x) for x in lines[2].split()],
        [float(x) for x in lines[3].split()],
        [float(x) for x in lines[4].split()],
    ], dtype=float) * scale

    # Line 5: species labels
    species_labels = lines[5].split()

    # Line 6: counts
    counts = [int(x) for x in lines[6].split()]
    species: List[str] = []
    for label, count in zip(species_labels, counts):
        species.extend([label] * count)
    n_atoms = sum(counts)

    # Line 7: Direct or Cartesian
    coord_line = lines[7].strip().lower()
    if not (coord_line.startswith("d") or coord_line.startswith("c")):
        raise ValueError(f"Expected Direct/Cartesian, got: {lines[7]!r}")

    # Lines 8 to 8+n_atoms-1: atomic positions
    positions_frac = np.zeros((n_atoms, 3), dtype=float)
    for i in range(n_atoms):
        parts = lines[8 + i].split()
        positions_frac[i] = [float(parts[0]), float(parts[1]), float(parts[2])]

    # Blank line, then grid dimensions
    line_idx = 8 + n_atoms
    # Skip blank lines
    while line_idx < len(lines) and not lines[line_idx].strip():
        line_idx += 1

    if line_idx >= len(lines):
        raise ValueError(f"No grid dimensions found in {path}")

    grid_parts = lines[line_idx].split()
    if len(grid_parts) < 3:
        raise ValueError(f"Invalid grid dimension line: {lines[line_idx]!r}")

    ngx, ngy, ngz = int(grid_parts[0]), int(grid_parts[1]), int(grid_parts[2])
    n_total = ngx * ngy * ngz
    line_idx += 1

    # Read grid data values
    values: List[float] = []
    while len(values) < n_total and line_idx < len(lines):
        line = lines[line_idx].strip()
        if not line:
            line_idx += 1
            continue
        # Stop if we hit augmentation data separator (CHGCAR specific)
        # Augmentation starts with a line containing species name
        if len(values) >= n_total:
            break
        try:
            parts = line.split()
            for part in parts:
                values.append(float(part))
                if len(values) >= n_total:
                    break
        except ValueError:
            break
        line_idx += 1

    if len(values) < n_total:
        raise ValueError(
            f"Expected {n_total} grid values, got {len(values)} in {path}"
        )

    grid_data = np.array(values[:n_total], dtype=np.float64)

    return {
        "lattice": lattice,
        "species": species,
        "positions_frac": positions_frac,
        "grid_shape": (ngx, ngy, ngz),
        "grid_data": grid_data,
        "scale": scale,
    }


@register_parser("vasp", "field3d")
class VASPField3DProvider:
    """VASP field3d analysis provider."""

    engine = "vasp"
    object_type = "field3d"

    def can_parse(self, raw_dir: Path) -> bool:
        return any((raw_dir / name).exists() for name in _VOLUMETRIC_FILES)

    def parse(self, evidence: EvidenceBundle) -> Field3D:
        """Parse primary volumetric file and note discovered files."""
        raw_dir = evidence.primary_raw_dir

        # Discover which volumetric files exist
        discovered: List[str] = [
            name for name in _VOLUMETRIC_FILES
            if (raw_dir / name).exists()
        ]

        if not discovered:
            raise FileNotFoundError(
                f"No volumetric files found in {raw_dir}"
            )

        # Parse the primary file (first in priority order)
        primary_name = discovered[0]
        primary_path = raw_dir / primary_name
        parsed = parse_vasp_volumetric(primary_path)

        field_kind = _FIELD_KIND_MAP.get(primary_name, "unknown")

        source_files = [SourceFileStat.from_path(primary_path, evidence.calc_dir)]

        warnings: list[str] = []
        if len(discovered) > 1:
            warnings.append(
                f"Multiple volumetric files found: {discovered}. "
                f"Parsed primary: {primary_name}."
            )

        meta = AnalysisObjectMeta.create(
            object_type="field3d",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="vasp_field3d",
            parser_version="1.0",
            warnings=warnings,
        )

        return Field3D(
            meta=meta,
            grid_shape=parsed["grid_shape"],
            grid_data=parsed["grid_data"],
            lattice=parsed["lattice"],
            field_kind=field_kind,
            discovered_files=discovered,
        )
