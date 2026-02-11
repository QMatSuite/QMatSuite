"""QE field3d analysis provider (cube/XSF from pp.x post-processing)."""
from __future__ import annotations

from pathlib import Path
from typing import List

from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.core.analysis.field3d import Field3D
from quantumvitas.io.parser.cube_parser import parse_cube_file, parse_xsf_field3d
from quantumvitas.parsers.registry import register_parser

_FIELD_KIND_PATTERNS = {
    "charge density": "charge_density",
    "total charge": "charge_density",
    "spin polarization": "spin_density",
    "elf": "elf",
    "electron localization": "elf",
    "stm": "stm",
    "local dos": "ldos",
    "potential": "potential",
    "wavefunction": "orbital_density",
    "psi": "orbital_density",
}


def _detect_field_kind(comment: str) -> str:
    lower = comment.lower()
    for pattern, kind in _FIELD_KIND_PATTERNS.items():
        if pattern in lower:
            return kind
    return "charge_density"


@register_parser("qe", "field3d")
class QEField3DProvider:
    """QE field3d analysis provider."""

    engine = "qe"
    object_type = "field3d"

    def can_parse(self, raw_dir: Path) -> bool:
        return (any(raw_dir.glob("*.cube"))
                or any(f for f in raw_dir.glob("*.xsf")
                       if "DATAGRID" in f.read_text(errors="replace")[:500]))

    def parse(self, evidence: EvidenceBundle) -> Field3D:
        raw_dir = evidence.primary_raw_dir

        cube_files = sorted(raw_dir.glob("*.cube"))
        xsf_files = sorted(raw_dir.glob("*.xsf"))

        # Prefer cube over XSF
        if cube_files:
            primary_path = cube_files[0]
            parsed = parse_cube_file(primary_path)
            field_kind = _detect_field_kind(parsed.get("comment", ""))
        elif xsf_files:
            primary_path = xsf_files[0]
            parsed = parse_xsf_field3d(primary_path)
            field_kind = "charge_density"
        else:
            raise FileNotFoundError(f"No cube/xsf files found in {raw_dir}")

        all_files = cube_files + xsf_files
        discovered: List[str] = [f.name for f in all_files]

        source_files = [SourceFileStat.from_path(primary_path, evidence.calc_dir)]

        warnings: list[str] = []
        if len(discovered) > 1:
            warnings.append(
                f"Found {len(discovered)} volumetric files. "
                f"Parsed primary: {primary_path.name}."
            )

        meta = AnalysisObjectMeta.create(
            object_type="field3d",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="qe_field3d",
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
