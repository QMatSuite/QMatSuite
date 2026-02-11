"""Gaussian field3d analysis provider (density/orbital cubes from cubegen)."""
from __future__ import annotations

from pathlib import Path
from typing import List

from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.core.analysis.field3d import Field3D
from quantumvitas.io.parser.cube_parser import parse_cube_file
from quantumvitas.parsers.registry import register_parser

_FIELD_KIND_PATTERNS = {
    "total density": "charge_density",
    "scf total density": "charge_density",
    "spin density": "spin_density",
    "alpha density": "spin_density",
    "mo ": "orbital_density",
    "electrostatic potential": "potential",
}


def _detect_field_kind(comment: str) -> str:
    """Detect field_kind from cube comment header."""
    lower = comment.lower()
    for pattern, kind in _FIELD_KIND_PATTERNS.items():
        if pattern in lower:
            return kind
    return "charge_density"


@register_parser("gaussian", "field3d")
class GaussianField3DProvider:
    """Gaussian field3d analysis provider."""

    engine = "gaussian"
    object_type = "field3d"

    def can_parse(self, raw_dir: Path) -> bool:
        return any(raw_dir.glob("*.cube"))

    def parse(self, evidence: EvidenceBundle) -> Field3D:
        raw_dir = evidence.primary_raw_dir

        cube_files = sorted(raw_dir.glob("*.cube"))
        if not cube_files:
            raise FileNotFoundError(f"No cube files found in {raw_dir}")

        discovered: List[str] = [f.name for f in cube_files]
        primary_path = cube_files[0]
        parsed = parse_cube_file(primary_path)

        field_kind = _detect_field_kind(parsed["comment"])

        source_files = [SourceFileStat.from_path(primary_path, evidence.calc_dir)]

        warnings: list[str] = []
        if len(discovered) > 1:
            warnings.append(
                f"Found {len(discovered)} cube files. "
                f"Parsed primary: {discovered[0]}."
            )

        meta = AnalysisObjectMeta.create(
            object_type="field3d",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="gaussian_field3d",
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
