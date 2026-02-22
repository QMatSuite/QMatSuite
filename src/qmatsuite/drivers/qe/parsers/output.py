"""QE output parser: SCF digest from pw.x text output."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from qmatsuite.analysis.parsers import parse_scf_output
from qmatsuite.parsers.registry import register_parser


@dataclass
class QESCFDigest:
    """Canonical digest summary for QE SCF/NSCF output."""

    converged: bool = False
    total_energy_ry: Optional[float] = None
    fermi_energy_ev: Optional[float] = None
    homo_ev: Optional[float] = None
    lumo_ev: Optional[float] = None
    band_gap_ev: Optional[float] = None
    n_iterations: int = 0
    total_magnetization: Optional[float] = None
    absolute_magnetization: Optional[float] = None
    total_cpu_time_s: Optional[float] = None
    total_wall_time_s: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@register_parser("qe", "scf_digest")
class QEOutputParser:
    """Parse QE outputs into a compact SCF digest."""

    engine = "qe"
    object_type = "scf_digest"

    def can_parse(self, raw_dir: Path) -> bool:
        return self._find_output_file(raw_dir) is not None

    def parse(self, raw_dir: Path, **kwargs: Any) -> QESCFDigest:
        output_file = self._find_output_file(raw_dir)
        if output_file is None:
            return QESCFDigest()

        result = parse_scf_output(output_file)
        return QESCFDigest(
            converged=bool(getattr(result, "converged", False)),
            total_energy_ry=getattr(result, "total_energy", None),
            fermi_energy_ev=getattr(result, "fermi_energy", None),
            homo_ev=getattr(result, "homo", None),
            lumo_ev=getattr(result, "lumo", None),
            band_gap_ev=getattr(result, "band_gap", None),
            n_iterations=len(getattr(result, "iterations", []) or []),
            total_magnetization=getattr(result, "total_magnetization", None),
            absolute_magnetization=getattr(result, "absolute_magnetization", None),
            total_cpu_time_s=getattr(result, "total_cpu_time", None),
            total_wall_time_s=getattr(result, "total_wall_time", None),
        )

    def _find_output_file(self, raw_dir: Path) -> Optional[Path]:
        patterns = [
            "*.scf.out",
            "scf.out",
            "*.nscf.out",
            "nscf.out",
            "*.out",
        ]
        for pattern in patterns:
            matches = sorted(raw_dir.glob(pattern))
            if matches:
                return matches[0]
        return None

