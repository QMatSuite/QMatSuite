"""ORCA field3d analysis provider (cube from %plots block)."""
from __future__ import annotations

from pathlib import Path
from typing import List

from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.core.analysis.field3d import Field3D
from quantumvitas.io.parser.cube_parser import parse_cube_file
from quantumvitas.parsers.registry import register_parser

_FIELD_KIND_PATTERNS = {
    "density": "charge_density",
    "eldens": "charge_density",
    "spin": "spin_density",
    "mo": "orbital_density",
    "potential": "potential",
}


def _detect_field_kind(name: str) -> str:
    lower = name.lower()
    for pattern, kind in _FIELD_KIND_PATTERNS.items():
        if pattern in lower:
            return kind
    return "charge_density"


@register_parser("orca", "field3d")
class ORCAField3DProvider:
    """ORCA field3d analysis provider."""

    engine = "orca"
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
        field_kind = _detect_field_kind(primary_path.name)

        source_files = [SourceFileStat.from_path(primary_path, evidence.calc_dir)]
        warnings: list[str] = []
        if len(discovered) > 1:
            warnings.append(
                f"Found {len(discovered)} cube files. Parsed primary: {discovered[0]}."
            )

        meta = AnalysisObjectMeta.create(
            object_type="field3d",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="orca_field3d",
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
