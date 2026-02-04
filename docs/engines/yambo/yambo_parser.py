"""
Yambo output parser utilities.

Parses yambo text output files:
- o-*.qp         : Quasiparticle energies (GW)
- o-*.eps_*      : Dielectric function (IP, BSE, TDDFT)
- o-*.eel_*      : Energy loss function
- o-*.alpha_*    : Absorption coefficient
- r-*            : Report file (system info, parameters, warnings)

Does NOT parse binary netCDF databases (ndb.*) — those require netCDF4.
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
    e_dft: float        # Eo [eV] — DFT eigenvalue
    e_correction: float  # E-Eo [eV] — GW correction
    sc_at_eo: float      # Sc|Eo [eV] — correlation self-energy at Eo

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
        vb = [c for c in self.corrections if c.e_correction > 0]  # valence
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

    def corrections_at_k(self, k: int) -> list[QPCorrection]:
        """Get all corrections at a given k-point."""
        return [c for c in self.corrections if c.k_point == k]


def parse_qp_file(filepath: Path) -> QPResult:
    """Parse a yambo o-*.qp output file."""
    result = QPResult()
    text = filepath.read_text()

    # Parse metadata from header comments
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#") and ":" in line:
            key_val = line.lstrip("# ").split(":", 1)
            if len(key_val) == 2:
                result.metadata[key_val[0].strip()] = key_val[1].strip()

    # Parse data rows: K-point  Band  Eo  E-Eo  Sc|Eo
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
    energy: float       # eV
    im_eps: float       # Im(eps) — imaginary part of dielectric function
    re_eps: float       # Re(eps) — real part of dielectric function
    # Additional columns may exist for BSE (eps_o, eps')
    extra: dict[str, float] = field(default_factory=dict)


@dataclass
class SpectrumResult:
    """Parsed optical spectrum from o-*.eps_* or similar."""
    points: list[SpectrumPoint] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    column_headers: list[str] = field(default_factory=list)
    spectrum_type: str = ""  # "ip", "haydock_bse", "diago_bse", "tddft", etc.
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

    # Determine spectrum type from filename
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

    # Parse metadata and column headers
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
            # Column header line
            result.column_headers = [h.strip() for h in stripped.split() if h.strip()]
        if "Absorption @ Q" in stripped:
            # Extract q-direction
            m = re.search(r"Q\(\d+\):\s*([\d.E+-]+)\s+([\d.E+-]+)\s+([\d.E+-]+)", stripped)
            if m:
                result.q_direction = [float(m.group(i)) for i in (1, 2, 3)]

    # Parse data rows
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
                # Additional columns
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
    build: str = ""
    n_bands: int = 0
    n_kpoints: int = 0
    n_gvectors: int = 0
    n_electrons: float = 0.0
    n_symmetries: int = 0
    fermi_level: float = 0.0
    direct_gap: float = 0.0
    indirect_gap: float = 0.0
    direct_gap_kpt: int = 0
    indirect_gap_kpts: tuple[int, int] = (0, 0)
    filled_bands: int = 0
    cell_kind: str = ""
    atom_species: list[str] = field(default_factory=list)
    runlevels: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    timing_seconds: Optional[float] = None


def parse_report_file(filepath: Path) -> YamboReportInfo:
    """Parse a yambo r-* report file for key system information."""
    info = YamboReportInfo()
    text = filepath.read_text()

    for line in text.splitlines():
        stripped = line.strip()

        # Version
        m = re.search(r"Version (\S+) Revision (\d+)", stripped)
        if m:
            info.version = m.group(1)

        m = re.match(r"\s*(Serial|Parallel)\+(\S+)\s+Build", stripped)
        if m:
            info.build = stripped.strip()

        # Key quantities
        if "Bands" in stripped and ":" in stripped and "K-points" not in stripped:
            m = re.search(r"Bands\s*:\s*(\d+)", stripped)
            if m:
                info.n_bands = int(m.group(1))

        if "K-points" in stripped and ":" in stripped:
            m = re.search(r"K-points\s*:\s*(\d+)", stripped)
            if m:
                info.n_kpoints = int(m.group(1))

        if "G-vectors" in stripped and "RL space" in stripped:
            m = re.search(r"G-vectors\s*:\s*(\d+)", stripped)
            if m:
                info.n_gvectors = int(m.group(1))

        if "Electrons" in stripped and ":" in stripped:
            m = re.search(r"Electrons\s*:\s*([\d.]+)", stripped)
            if m:
                info.n_electrons = float(m.group(1))

        if "Symmetries" in stripped and "spatial" in stripped:
            m = re.search(r"Symmetries\s*:\s*(\d+)", stripped)
            if m:
                info.n_symmetries = int(m.group(1))

        if "Fermi Level" in stripped:
            m = re.search(r"Fermi Level\s*:\s*([\d.Ee+-]+)", stripped)
            if m:
                info.fermi_level = float(m.group(1))

        if "Direct Gap" in stripped and "localized" not in stripped:
            m = re.search(r"Direct Gap\s*:\s*([\d.Ee+-]+)", stripped)
            if m:
                info.direct_gap = float(m.group(1))

        if "Direct Gap localized" in stripped:
            m = re.search(r"localized at k\s*:\s*(\d+)", stripped)
            if m:
                info.direct_gap_kpt = int(m.group(1))

        if "Indirect Gap" in stripped and "between" not in stripped:
            m = re.search(r"Indirect Gap\s*:\s*([\d.Ee+-]+)", stripped)
            if m:
                info.indirect_gap = float(m.group(1))

        if "Indirect Gap between" in stripped:
            m = re.search(r"between kpts\s*:\s*(\d+)\s+(\d+)", stripped)
            if m:
                info.indirect_gap_kpts = (int(m.group(1)), int(m.group(2)))

        if "Filled Bands" in stripped:
            m = re.search(r"Filled Bands\s*:\s*(\d+)", stripped)
            if m:
                info.filled_bands = int(m.group(1))

        if "Cell kind" in stripped:
            m = re.search(r"Cell kind\s*:\s*(.+)", stripped)
            if m:
                info.cell_kind = m.group(1).strip()

        if "Atoms in the cell" in stripped:
            m = re.search(r"Atoms in the cell\s*:\s*(.+)", stripped)
            if m:
                info.atom_species = m.group(1).strip().split()

        # Warnings
        if "[WARNING]" in stripped:
            info.warnings.append(stripped.replace("[WARNING]", "").strip())

    return info


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    base = Path(__file__).parent / "golden_refs"

    # Test QP parser
    qp_file = base / "gw" / "o-gw_si.qp"
    if qp_file.exists():
        qp = parse_qp_file(qp_file)
        print(f"=== GW QP Results ===")
        print(f"  Corrections: {len(qp.corrections)}")
        print(f"  K=1 band 4: Eo={qp.corrections[1].e_dft:.3f} eV, "
              f"E-Eo={qp.corrections[1].e_correction:.3f} eV, "
              f"QP={qp.corrections[1].e_qp:.3f} eV")
        print(f"  DFT gap: {qp.dft_gap}")
        print(f"  QP gap: {qp.qp_gap}")
        print()

    # Test spectrum parser
    eps_file = base / "ip" / "o-ip_si.eps_q1_ip"
    if eps_file.exists():
        spec = parse_spectrum_file(eps_file)
        print(f"=== IP Optics ===")
        print(f"  Points: {len(spec.points)}")
        print(f"  Type: {spec.spectrum_type}")
        print(f"  Static dielectric: {spec.static_dielectric:.3f}")
        print()

    bse_file = base / "bse" / "o-bse_si.eps_q1_haydock_bse"
    if bse_file.exists():
        bse = parse_spectrum_file(bse_file)
        print(f"=== BSE Optics ===")
        print(f"  Points: {len(bse.points)}")
        print(f"  Type: {bse.spectrum_type}")
        print(f"  Static dielectric: {bse.static_dielectric:.3f}")
        print()

    # Test report parser
    report_file = base / "r_setup"
    if report_file.exists():
        rpt = parse_report_file(report_file)
        print(f"=== Report ===")
        print(f"  Version: {rpt.version}")
        print(f"  Bands: {rpt.n_bands}")
        print(f"  K-points: {rpt.n_kpoints}")
        print(f"  Indirect gap: {rpt.indirect_gap} eV")
        print(f"  Direct gap: {rpt.direct_gap} eV")
        print(f"  Filled bands: {rpt.filled_bands}")
        print(f"  Cell kind: {rpt.cell_kind}")
        print(f"  Atoms: {rpt.atom_species}")
