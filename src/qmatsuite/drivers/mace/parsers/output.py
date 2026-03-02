"""MACE output digest parser.

Parses ``results.json`` produced by MACE calculation scripts into a digest object.
JSON-primary parser — no regex needed.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Union

from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.parsers.registry import register_parser


@dataclass
class MACEDigest:
    """Canonical digest for MACE outputs."""

    success: bool = False
    total_energy_eV: float | None = None
    energy_per_atom_eV: float | None = None
    forces_eV_per_ang: list[list[float]] | None = None
    max_force_eV_per_ang: float | None = None
    stress_eV_per_ang3: list[float] | None = None
    n_atoms: int = 0
    model_name: str | None = None
    calc_type: str | None = None
    converged: bool | None = None
    n_opt_steps: int | None = None
    n_md_steps: int | None = None
    wall_time_s: float | None = None
    final_species: list[str] | None = None
    final_positions: list[list[float]] | None = None
    final_cell: list[list[float]] | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@register_parser("mace", "scf_digest")
class MACEOutputParser:
    """Parse MACE raw directory into :class:`MACEDigest`."""

    engine = "mace"
    object_type = "scf_digest"

    def can_parse(self, raw_dir: Path) -> bool:
        results_path = raw_dir / "results.json"
        return results_path.is_file()

    def parse(self, evidence: Union[EvidenceBundle, Path], **kwargs: Any) -> MACEDigest:
        raw_dir = evidence.primary_raw_dir if isinstance(evidence, EvidenceBundle) else evidence
        results_path = raw_dir / "results.json"
        if not results_path.is_file():
            return MACEDigest(error_message="No results.json found")

        try:
            text = results_path.read_text(encoding="utf-8")
            data = json.loads(text)
        except (OSError, json.JSONDecodeError) as exc:
            return MACEDigest(error_message=f"Failed to parse results.json: {exc}")

        return _build_digest(data)


def _build_digest(data: dict[str, Any]) -> MACEDigest:
    """Build MACEDigest from parsed results.json data."""
    digest = MACEDigest()

    digest.success = data.get("success", False)
    digest.total_energy_eV = data.get("total_energy_eV")
    digest.energy_per_atom_eV = data.get("energy_per_atom_eV")
    digest.forces_eV_per_ang = data.get("forces_eV_per_ang")
    digest.max_force_eV_per_ang = data.get("max_force_eV_per_ang")
    digest.stress_eV_per_ang3 = data.get("stress_eV_per_ang3")
    digest.n_atoms = data.get("n_atoms", 0)
    digest.model_name = data.get("model_name")
    digest.calc_type = data.get("calc_type")
    digest.converged = data.get("converged")
    digest.n_opt_steps = data.get("n_opt_steps")
    digest.n_md_steps = data.get("n_md_steps")
    digest.wall_time_s = data.get("wall_time_s")
    digest.final_species = data.get("final_species")
    digest.final_positions = data.get("final_positions")
    digest.final_cell = data.get("final_cell")

    if not digest.success:
        digest.error_message = data.get("error_message", "Calculation did not report success")

    return digest
