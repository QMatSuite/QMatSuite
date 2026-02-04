"""Yambo output parser.

Parses yambo text output files:
- o-*.qp         : Quasiparticle energies (GW)
- o-*.eps_*      : Dielectric function (IP, BSE, TDDFT)
- o-*.eel_*      : Energy loss function
- r-*            : Report file (system info, parameters, warnings)

Does NOT parse binary netCDF databases (ndb.*).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# QP output parser (o-*.qp)
# ---------------------------------------------------------------------------

@dataclass
class QPCorrection:
    """Single quasiparticle correction."""
    k_point: int
    band: int
    e_dft: float
    e_correction: float
    sc_at_eo: float

    @property
    def e_qp(self) -> float:
        """Quasiparticle energy = Eo + (E-Eo)."""
        return self.e_dft + self.e_correction


@dataclass
class QPResult:
    """Parsed GW quasiparticle results from o-*.qp file."""
    corrections: list[QPCorrection] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def dft_gap(self) -> Optional[float]:
        """Indirect DFT gap from QP data."""
        vb = [c for c in self.corrections if c.e_correction > 0]
        cb = [c for c in self.corrections if c.e_correction < 0 or c.e_dft > 0.5]
        if not vb or not cb:
            return None
        vbm = max(c.e_dft for c in vb)
        cbm = min(c.e_dft for c in cb if c.e_dft > vbm - 0.1)
        return cbm - vbm if cbm > vbm else None

    @property
    def qp_gap(self) -> Optional[float]:
        """Indirect QP gap from GW-corrected energies."""
        vb = [c for c in self.corrections if c.e_correction > 0]
        cb = [c for c in self.corrections if c.e_correction < 0 or c.e_dft > 0.5]
        if not vb or not cb:
            return None
        vbm = max(c.e_qp for c in vb)
        cbm = min(c.e_qp for c in cb if c.e_dft > max(c2.e_dft for c2 in vb) - 0.1)
        return cbm - vbm if cbm > vbm else None


def parse_qp_file(filepath: Path) -> QPResult:
    """Parse a yambo o-*.qp output file."""
    result = QPResult()
    text = filepath.read_text()

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#") and ":" in line:
            key_val = line.lstrip("# ").split(":", 1)
            if len(key_val) == 2:
                result.metadata[key_val[0].strip()] = key_val[1].strip()

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        parts = line.split()
        if len(parts) >= 5:
            try:
                qp = QPCorrection(
                    k_point=int(parts[0]),
                    band=int(parts[1]),
                    e_dft=float(parts[2]),
                    e_correction=float(parts[3]),
                    sc_at_eo=float(parts[4]),
                )
                result.corrections.append(qp)
            except (ValueError, IndexError):
                continue

    return result


# ---------------------------------------------------------------------------
# Spectrum output parser (o-*.eps_*, o-*.eel_*, o-*.alpha_*)
# ---------------------------------------------------------------------------

@dataclass
class SpectrumPoint:
    """Single energy point in a spectrum."""
    energy: float
    im_eps: float
    re_eps: float
    extra: dict[str, float] = field(default_factory=dict)


@dataclass
class SpectrumResult:
    """Parsed optical spectrum from o-*.eps_* or similar."""
    points: list[SpectrumPoint] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    column_headers: list[str] = field(default_factory=list)
    spectrum_type: str = ""
    q_direction: Optional[list[float]] = None

    @property
    def energies(self) -> list[float]:
        return [p.energy for p in self.points]

    @property
    def im_eps(self) -> list[float]:
        return [p.im_eps for p in self.points]

    @property
    def re_eps(self) -> list[float]:
        return [p.re_eps for p in self.points]

    @property
    def static_dielectric(self) -> Optional[float]:
        """Re(eps) at omega=0."""
        if self.points:
            return self.points[0].re_eps
        return None


def parse_spectrum_file(filepath: Path) -> SpectrumResult:
    """Parse a yambo o-*.eps_* / o-*.eel_* / o-*.alpha_* output file."""
    result = SpectrumResult()
    text = filepath.read_text()
    fname = filepath.name

    if "_ip" in fname:
        result.spectrum_type = "ip"
    elif "_haydock_bse" in fname:
        result.spectrum_type = "haydock_bse"
    elif "_diago_bse" in fname:
        result.spectrum_type = "diago_bse"
    elif "_tddft" in fname:
        result.spectrum_type = "tddft"
    elif "_rpa" in fname:
        result.spectrum_type = "rpa"

    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("#"):
            continue
        stripped = line.lstrip("# ").strip()
        if ":" in stripped:
            key_val = stripped.split(":", 1)
            if len(key_val) == 2:
                result.metadata[key_val[0].strip()] = key_val[1].strip()
        if "E[1]" in stripped or "E/ev" in stripped.lower():
            result.column_headers = [h.strip() for h in stripped.split() if h.strip()]

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        parts = line.split()
        if len(parts) >= 3:
            try:
                point = SpectrumPoint(
                    energy=float(parts[0]),
                    im_eps=float(parts[1]),
                    re_eps=float(parts[2]),
                )
                col_names = ["im_eps_o", "re_eps_o", "im_eps_prime", "re_eps_prime"]
                for i, name in enumerate(col_names):
                    if i + 3 < len(parts):
                        try:
                            point.extra[name] = float(parts[i + 3])
                        except ValueError:
                            pass
                result.points.append(point)
            except (ValueError, IndexError):
                continue

    return result


# ---------------------------------------------------------------------------
# Report file parser (r-*)
# ---------------------------------------------------------------------------

@dataclass
class YamboReportInfo:
    """Key information extracted from a yambo report file."""
    version: str = ""
    n_bands: int = 0
    n_kpoints: int = 0
    fermi_level: float = 0.0
    direct_gap: float = 0.0
    indirect_gap: float = 0.0
    filled_bands: int = 0
    cell_kind: str = ""
    atom_species: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_report_file(filepath: Path) -> YamboReportInfo:
    """Parse a yambo r-* report file for key system information."""
    info = YamboReportInfo()
    text = filepath.read_text()

    for line in text.splitlines():
        stripped = line.strip()

        m = re.search(r"Version (\S+) Revision (\d+)", stripped)
        if m:
            info.version = m.group(1)

        if "Bands" in stripped and ":" in stripped and "K-points" not in stripped:
            m = re.search(r"Bands\s*:\s*(\d+)", stripped)
            if m:
                info.n_bands = int(m.group(1))

        if "K-points" in stripped and ":" in stripped:
            m = re.search(r"K-points\s*:\s*(\d+)", stripped)
            if m:
                info.n_kpoints = int(m.group(1))

        if "Fermi Level" in stripped:
            m = re.search(r"Fermi Level\s*:\s*([\d.Ee+-]+)", stripped)
            if m:
                info.fermi_level = float(m.group(1))

        if "Direct Gap" in stripped and "localized" not in stripped:
            m = re.search(r"Direct Gap\s*:\s*([\d.Ee+-]+)", stripped)
            if m:
                info.direct_gap = float(m.group(1))

        if "Indirect Gap" in stripped and "between" not in stripped:
            m = re.search(r"Indirect Gap\s*:\s*([\d.Ee+-]+)", stripped)
            if m:
                info.indirect_gap = float(m.group(1))

        if "Filled Bands" in stripped:
            m = re.search(r"Filled Bands\s*:\s*(\d+)", stripped)
            if m:
                info.filled_bands = int(m.group(1))

        if "[WARNING]" in stripped:
            info.warnings.append(stripped.replace("[WARNING]", "").strip())

    return info
