"""Siesta output digest parser.

Parses common Siesta outputs into a minimal canonical digest and registers
as ``("siesta", "scf_digest")``.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from qmatsuite.parsers.registry import register_parser


@dataclass
class SiestaDigest:
    """Canonical digest for common Siesta workflows (SCF/relax/MD)."""

    final_energy_eV: float | None = None
    energy_per_atom_eV: float | None = None
    n_atoms: int = 0
    converged_electronic: bool = False
    converged_ionic: bool = False
    n_ionic_steps: int = 0
    n_electronic_steps: int = 0
    final_lattice: list[list[float]] | None = None
    final_frac_coords: list[list[float]] | None = None
    volume_A3: float | None = None
    max_force_eV_A: float | None = None
    total_magnetization: float | None = None
    elapsed_time_s: float | None = None
    pressure_kBar: float | None = None
    normal_exit: bool = False
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@register_parser("siesta", "scf_digest")
class SiestaOutputParser:
    """Parse Siesta raw directories into :class:`SiestaDigest`."""

    engine = "siesta"
    object_type = "scf_digest"

    def can_parse(self, raw_dir: Path) -> bool:
        out = self._find_out_file(raw_dir)
        if out is None:
            return False
        text = out.read_text(errors="replace")
        lower = text.lower()
        return ("welcome to siesta" in lower) or ("siesta:" in lower)

    def parse(self, raw_dir: Path, **kwargs: Any) -> SiestaDigest:
        out_file = self._find_out_file(raw_dir)
        if out_file is None:
            return SiestaDigest(error_message="No Siesta .out file found")

        try:
            out_text = out_file.read_text(errors="replace")
        except OSError as exc:
            return SiestaDigest(error_message=f"Failed to read output: {exc}")

        digest = _parse_out_text(out_text)

        digest.normal_exit = digest.normal_exit or (raw_dir / "0_NORMAL_EXIT").exists()

        # Optional structure info.
        struct_file = _find_first(raw_dir, "*.STRUCT_OUT")
        if struct_file is not None:
            _fill_structure_from_struct_out(digest, struct_file)

        # Optional forces.
        fa_file = _find_first(raw_dir, "*.FA")
        if fa_file is not None:
            _fill_max_force_from_fa(digest, fa_file)

        # Optional ionic trajectory / pressure from MDE.
        mde_file = _find_first(raw_dir, "*.MDE")
        if mde_file is not None:
            _fill_ionic_from_mde(digest, mde_file)

        if digest.n_atoms > 0 and digest.final_energy_eV is not None:
            digest.energy_per_atom_eV = digest.final_energy_eV / float(digest.n_atoms)

        return digest

    def _find_out_file(self, raw_dir: Path) -> Path | None:
        preferred = sorted(raw_dir.glob("*.out"))
        if preferred:
            return preferred[0]
        return None


def _find_first(raw_dir: Path, pattern: str) -> Path | None:
    matches = sorted(raw_dir.glob(pattern))
    return matches[0] if matches else None


def _parse_out_text(text: str) -> SiestaDigest:
    d = SiestaDigest()

    e_matches = re.findall(r"siesta:\s+E_KS\(eV\)\s*=\s*([\-0-9.Ee+]+)", text)
    if e_matches:
        d.final_energy_eV = float(e_matches[-1])

    m = re.search(r"Number of atoms, orbitals, and projectors:\s*(\d+)", text)
    if not m:
        m = re.search(r"NumberOfAtoms\s+(\d+)", text)
    if m:
        d.n_atoms = int(m.group(1))

    d.converged_electronic = "SCF Convergence" in text
    d.n_electronic_steps = len(re.findall(r"^\s*scf:\s+\d+", text, flags=re.MULTILINE))

    wall = re.search(r"timer:\s+Elapsed wall time \(sec\)\s*=\s*([\-0-9.Ee+]+)", text)
    if wall:
        d.elapsed_time_s = float(wall.group(1))

    d.normal_exit = "Job completed" in text

    mag = re.search(r"Total spin moment:\s*([\-0-9.Ee+]+)", text)
    if mag:
        d.total_magnetization = float(mag.group(1))

    return d


def _fill_structure_from_struct_out(d: SiestaDigest, path: Path) -> None:
    try:
        lines = [ln.strip() for ln in path.read_text(errors="replace").splitlines() if ln.strip()]
        if len(lines) < 4:
            return

        lattice: list[list[float]] = []
        for i in range(3):
            toks = lines[i].split()
            if len(toks) < 3:
                return
            lattice.append([float(toks[0]), float(toks[1]), float(toks[2])])

        nat = int(lines[3].split()[0])
        fracs: list[list[float]] = []
        for row in lines[4 : 4 + nat]:
            toks = row.split()
            if len(toks) < 5:
                continue
            fracs.append([float(toks[2]), float(toks[3]), float(toks[4])])

        d.final_lattice = lattice
        d.final_frac_coords = fracs

        vol = abs(
            lattice[0][0] * (lattice[1][1] * lattice[2][2] - lattice[1][2] * lattice[2][1])
            - lattice[0][1] * (lattice[1][0] * lattice[2][2] - lattice[1][2] * lattice[2][0])
            + lattice[0][2] * (lattice[1][0] * lattice[2][1] - lattice[1][1] * lattice[2][0])
        )
        d.volume_A3 = vol
    except Exception:
        return


def _fill_max_force_from_fa(d: SiestaDigest, path: Path) -> None:
    try:
        lines = [ln.strip() for ln in path.read_text(errors="replace").splitlines() if ln.strip()]
        if len(lines) < 2:
            return
        max_norm = 0.0
        for row in lines[1:]:
            toks = row.split()
            if len(toks) < 4:
                continue
            fx, fy, fz = float(toks[1]), float(toks[2]), float(toks[3])
            norm = (fx * fx + fy * fy + fz * fz) ** 0.5
            if norm > max_norm:
                max_norm = norm
        d.max_force_eV_A = max_norm
    except Exception:
        return


def _fill_ionic_from_mde(d: SiestaDigest, path: Path) -> None:
    try:
        rows = []
        for raw in path.read_text(errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            toks = line.split()
            if len(toks) >= 6:
                rows.append(toks)
        if not rows:
            return

        d.n_ionic_steps = len(rows)
        d.converged_ionic = d.normal_exit and (d.n_ionic_steps > 0)

        # Column 6 is P(kBar) in standard .MDE format.
        try:
            d.pressure_kBar = float(rows[-1][5])
        except ValueError:
            pass
    except Exception:
        return


__all__ = ["SiestaDigest", "SiestaOutputParser"]
