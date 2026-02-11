"""Wannier90 field3d analysis provider (MLWF density from XSF files)."""
from __future__ import annotations

from pathlib import Path
from typing import List

from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.core.analysis.field3d import Field3D
from quantumvitas.io.parser.cube_parser import parse_xsf_field3d
from quantumvitas.parsers.registry import register_parser


@register_parser("w90", "field3d")
class W90Field3DProvider:
    """Wannier90 field3d analysis provider.

    Parses MLWF density XSF files produced by wannier90.x.
    W90 naming convention: <seedname>_NNNNN.xsf (one per WF).
    """

    engine = "w90"
    object_type = "field3d"

    def can_parse(self, raw_dir: Path) -> bool:
        return any(raw_dir.glob("*_[0-9][0-9][0-9][0-9][0-9].xsf"))

    def parse(self, evidence: EvidenceBundle) -> Field3D:
        raw_dir = evidence.primary_raw_dir

        # Discover all WF XSF files
        xsf_files = sorted(raw_dir.glob("*_[0-9][0-9][0-9][0-9][0-9].xsf"))
        if not xsf_files:
            raise FileNotFoundError(f"No W90 XSF files found in {raw_dir}")

        discovered: List[str] = [f.name for f in xsf_files]

        # Parse the first WF as primary
        primary_path = xsf_files[0]
        parsed = parse_xsf_field3d(primary_path)

        source_files = [SourceFileStat.from_path(primary_path, evidence.calc_dir)]

        warnings: list[str] = []
        if len(discovered) > 1:
            warnings.append(
                f"Found {len(discovered)} MLWF XSF files. "
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
            parser_name="w90_field3d",
            parser_version="1.0",
            warnings=warnings,
        )

        return Field3D(
            meta=meta,
            grid_shape=parsed["grid_shape"],
            grid_data=parsed["grid_data"],
            lattice=parsed["lattice"],
            field_kind="mlwf_density",
            discovered_files=discovered,
        )
