"""GPAW DOS analysis provider."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np

from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.dos import DOS
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.parsers.registry import register_parser


def _parse_dos_json(path: Path) -> dict:
    """Parse GPAW dos.json.

    Format:
        {
            "energies_eV": [...],
            "dos": [...],
            "fermi_eV": <float>,
            "n_points": <int>,
        }
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "energies_eV": np.array(data["energies_eV"], dtype=float),
        "dos": np.array(data["dos"], dtype=float),
        "fermi_eV": data.get("fermi_eV"),
        "n_points": data.get("n_points", len(data["energies_eV"])),
    }


@register_parser("gpaw", "dos")
class GPAWDOSProvider:
    """Parse GPAW DOS outputs into a canonical DOS object."""

    engine = "gpaw"
    object_type = "dos"

    def can_parse(self, raw_dir: Path) -> bool:
        return (raw_dir / "dos.json").exists()

    def parse(self, evidence: EvidenceBundle) -> DOS:
        """Parse GPAW dos.json and return engine-agnostic DOS."""
        raw_dir = evidence.primary_raw_dir
        warnings: list[str] = []

        dos_file = raw_dir / "dos.json"
        if not dos_file.exists():
            raise FileNotFoundError(f"No dos.json found in {raw_dir}")

        parsed = _parse_dos_json(dos_file)
        source_files = [SourceFileStat.from_path(dos_file, evidence.calc_dir)]

        fermi_energy = parsed.get("fermi_eV")
        if fermi_energy is None:
            warnings.append("No Fermi energy found in GPAW dos.json.")

        meta = AnalysisObjectMeta.create(
            object_type="dos",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="gpaw_dos",
            parser_version="1.0",
            warnings=warnings,
        )

        return DOS(
            meta=meta,
            energies=parsed["energies_eV"],
            total_dos=parsed["dos"],
            fermi_energy=fermi_energy,
            spin_polarized=False,
        )
