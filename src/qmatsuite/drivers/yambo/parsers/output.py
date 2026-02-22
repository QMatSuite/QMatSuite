"""Yambo output digest parser."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from qmatsuite.parsers.registry import register_parser


@dataclass
class QPCorrection:
    k_point: int
    band: int
    e_dft: float
    e_correction: float
    sc_at_eo: float

    @property
    def e_qp(self) -> float:
        return self.e_dft + self.e_correction


@dataclass
class QPResult:
    corrections: list[QPCorrection] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def dft_gap(self) -> float | None:
        if not self.corrections:
            return None
        vbm = max((c.e_dft for c in self.corrections if c.band <= 4), default=None)
        cbm = min((c.e_dft for c in self.corrections if c.band >= 5), default=None)
        if vbm is None or cbm is None:
            return None
        return cbm - vbm

    @property
    def qp_gap(self) -> float | None:
        if not self.corrections:
            return None
        vbm = max((c.e_qp for c in self.corrections if c.band <= 4), default=None)
        cbm = min((c.e_qp for c in self.corrections if c.band >= 5), default=None)
        if vbm is None or cbm is None:
            return None
        return cbm - vbm


@dataclass
class SpectrumPoint:
    energy: float
    im_eps: float
    re_eps: float


@dataclass
class SpectrumResult:
    points: list[SpectrumPoint] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    spectrum_type: str = ""

    @property
    def static_dielectric(self) -> float | None:
        return self.points[0].re_eps if self.points else None


@dataclass
class YamboReportInfo:
    version: str = ""
    n_bands: int = 0
    n_kpoints: int = 0
    fermi_level: float | None = None
    direct_gap: float | None = None
    indirect_gap: float | None = None
    filled_bands: int = 0
    warnings: list[str] = field(default_factory=list)
    wall_time_s: float | None = None


@dataclass
class YamboDigest:
    success: bool = False
    run_type: str | None = None
    n_qp_corrections: int = 0
    qp_gap_eV: float | None = None
    dft_gap_eV: float | None = None
    n_spectrum_points: int = 0
    static_dielectric: float | None = None
    spectrum_type: str | None = None
    n_kpoints: int = 0
    n_bands: int = 0
    filled_bands: int = 0
    direct_gap_eV: float | None = None
    indirect_gap_eV: float | None = None
    wall_time_s: float | None = None
    warnings: list[str] = field(default_factory=list)
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_qp_file(filepath: Path) -> QPResult:
    result = QPResult()
    for raw in filepath.read_text(errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            if ":" in line:
                k, v = line.lstrip("# ").split(":", 1)
                result.metadata[k.strip()] = v.strip()
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        try:
            result.corrections.append(
                QPCorrection(
                    k_point=int(parts[0]),
                    band=int(parts[1]),
                    e_dft=float(parts[2]),
                    e_correction=float(parts[3]),
                    sc_at_eo=float(parts[4]),
                )
            )
        except ValueError:
            continue
    return result


def parse_spectrum_file(filepath: Path) -> SpectrumResult:
    result = SpectrumResult()
    name = filepath.name.lower()
    if "_ip" in name:
        result.spectrum_type = "ip"
    elif "_haydock_bse" in name:
        result.spectrum_type = "haydock_bse"
    elif "_diago_bse" in name:
        result.spectrum_type = "diago_bse"
    elif "_tddft" in name:
        result.spectrum_type = "tddft"
    elif "_rpa" in name:
        result.spectrum_type = "rpa"

    for raw in filepath.read_text(errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            if ":" in line:
                k, v = line.lstrip("# ").split(":", 1)
                result.metadata[k.strip()] = v.strip()
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            result.points.append(
                SpectrumPoint(
                    energy=float(parts[0]),
                    im_eps=float(parts[1]),
                    re_eps=float(parts[2]),
                )
            )
        except ValueError:
            continue
    return result


def parse_report_file(filepath: Path) -> YamboReportInfo:
    info = YamboReportInfo()
    for raw in filepath.read_text(errors="replace").splitlines():
        line = raw.strip()
        m = re.search(r"Version\s+(\S+)\s+Revision\s+(\d+)", line)
        if m:
            info.version = m.group(1)

        if "Filled Bands" not in line:
            m = re.search(r"\bBands\s*:\s*(\d+)", line)
            if m:
                info.n_bands = int(m.group(1))

        m = re.search(r"K-points\s*:\s*(\d+)", line)
        if m:
            info.n_kpoints = int(m.group(1))

        m = re.search(r"Filled Bands\s*:\s*(\d+)", line)
        if m:
            info.filled_bands = int(m.group(1))

        m = re.search(r"Direct Gap\s*:\s*([\d.Ee+-]+)", line)
        if m:
            info.direct_gap = float(m.group(1))

        m = re.search(r"Indirect Gap\s*:\s*([\d.Ee+-]+)", line)
        if m:
            info.indirect_gap = float(m.group(1))

        if "[WARNING]" in line:
            info.warnings.append(line.replace("[WARNING]", "").strip())

        m = re.search(r"Timing\s*\[Min/Max/Average\]\s*:\s*(\d+)s", line)
        if m:
            info.wall_time_s = float(m.group(1))
    return info


def _find_output_files(raw_dir: Path, pattern: str) -> list[Path]:
    files = list(raw_dir.glob(pattern))
    if files:
        return files
    for child in raw_dir.iterdir() if raw_dir.is_dir() else []:
        if child.is_dir():
            files.extend(child.glob(pattern))
    return sorted(files)


_Q_INDEX_RE = re.compile(r"_q(\d+)_")


def _spectrum_order_key(path: Path) -> tuple[int, str]:
    m = _Q_INDEX_RE.search(path.name.lower())
    if m:
        return (int(m.group(1)), path.name.lower())
    return (10**9, path.name.lower())


@register_parser("yambo", "scf_digest")
class YamboOutputParser:
    engine = "yambo"
    object_type = "scf_digest"

    def can_parse(self, raw_dir: Path) -> bool:
        if not raw_dir.exists():
            return False
        return bool(
            _find_output_files(raw_dir, "o-*.qp")
            or _find_output_files(raw_dir, "o-*.eps_*")
            or _find_output_files(raw_dir, "r-*")
        )

    def parse(self, raw_dir: Path, **kwargs: Any) -> YamboDigest:
        if not raw_dir.exists():
            return YamboDigest(error_message="Output directory does not exist")

        digest = YamboDigest()

        qp_files = _find_output_files(raw_dir, "o-*.qp")
        eps_files = sorted(
            _find_output_files(raw_dir, "o-*.eps_*"),
            key=_spectrum_order_key,
        )
        report_files = _find_output_files(raw_dir, "r-*")

        if qp_files:
            qp = parse_qp_file(qp_files[0])
            digest.success = True
            digest.run_type = "gw"
            digest.n_qp_corrections = len(qp.corrections)
            digest.qp_gap_eV = qp.qp_gap
            digest.dft_gap_eV = qp.dft_gap

        if eps_files:
            spec = parse_spectrum_file(eps_files[0])
            digest.success = True
            digest.run_type = "optics" if digest.run_type is None else digest.run_type
            digest.n_spectrum_points = len(spec.points)
            digest.static_dielectric = spec.static_dielectric
            digest.spectrum_type = spec.spectrum_type or None

        if report_files:
            rep = parse_report_file(report_files[0])
            digest.n_kpoints = rep.n_kpoints
            digest.n_bands = rep.n_bands
            digest.filled_bands = rep.filled_bands
            digest.direct_gap_eV = rep.direct_gap
            digest.indirect_gap_eV = rep.indirect_gap
            digest.wall_time_s = rep.wall_time_s
            digest.warnings = rep.warnings
            if digest.run_type is None:
                digest.run_type = "report"
                digest.success = True

        if not digest.success:
            digest.error_message = "No Yambo output files found"

        return digest
