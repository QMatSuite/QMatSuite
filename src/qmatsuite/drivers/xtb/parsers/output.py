"""xTB output digest parser.

Parses ``xtb.out`` and companion artifacts into a small digest object.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from qmatsuite.parsers.registry import register_parser

HARTREE_TO_EV = 27.211386245988


@dataclass
class XTBDigest:
    """Canonical digest for xTB outputs."""

    success: bool = False
    normal_termination: bool = False
    final_energy_Ha: float | None = None
    final_energy_eV: float | None = None
    gradient_norm_Ha_per_a0: float | None = None
    homo_lumo_gap_eV: float | None = None
    converged_geometry: bool | None = None
    n_opt_cycles: int | None = None
    n_atoms: int = 0
    final_species: list[str] | None = None
    final_cart_coords: list[list[float]] | None = None
    free_energy_Ha: float | None = None
    zpe_Ha: float | None = None
    frequencies_cm: list[float] | None = None
    md_completed: bool = False
    wall_time_s: float | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@register_parser("xtb", "scf_digest")
class XTBOutputParser:
    """Parse xTB raw directory into :class:`XTBDigest`."""

    engine = "xtb"
    object_type = "scf_digest"

    def can_parse(self, raw_dir: Path) -> bool:
        out_path = self._find_output_file(raw_dir)
        if out_path is None:
            return False
        text = out_path.read_text(errors="replace")
        return "xtb" in text.lower() or "TOTAL ENERGY" in text

    def parse(self, raw_dir: Path, **kwargs: Any) -> XTBDigest:
        out_path = self._find_output_file(raw_dir)
        if out_path is None:
            return XTBDigest(error_message="No xTB output file found")

        try:
            text = out_path.read_text(errors="replace")
        except OSError as exc:
            return XTBDigest(error_message=f"Failed to read xTB output: {exc}")

        digest = parse_xtb_output_text(text)

        # Optional geometry artifact
        geom = raw_dir / "xtbopt.xyz"
        if geom.is_file():
            _fill_geometry_from_xtbopt(digest, geom)

        # Optional MD completion marker
        digest.md_completed = (raw_dir / "xtbmdok").exists()

        return digest

    def _find_output_file(self, raw_dir: Path) -> Path | None:
        preferred = ["xtb.out", "output.out", "stdout.log"]
        for name in preferred:
            p = raw_dir / name
            if p.is_file():
                return p

        out_files = sorted(raw_dir.glob("*.out"))
        if out_files:
            return out_files[0]
        return None


def _parse_wall_time_s(text: str) -> float | None:
    # xTB prints repeated wall-time lines; use the last one.
    matches = re.findall(r"\* wall-time:\s*(\d+) d,\s*(\d+) h,\s*(\d+) min,\s*([0-9.]+) sec", text)
    if not matches:
        return None
    d, h, m, s = matches[-1]
    return float(d) * 86400.0 + float(h) * 3600.0 + float(m) * 60.0 + float(s)


def _parse_frequencies(text: str) -> list[float] | None:
    # Example line: eigval : 1539.03 3642.76 3651.17
    freqs: list[float] = []
    for line in text.splitlines():
        if "eigval" not in line:
            continue
        parts = line.split(":", 1)
        if len(parts) != 2:
            continue
        for tok in parts[1].split():
            try:
                freqs.append(float(tok))
            except ValueError:
                continue
    return freqs or None


def parse_xtb_output_text(text: str) -> XTBDigest:
    digest = XTBDigest()

    m = re.search(r"TOTAL ENERGY\s+([\-0-9.]+)\s+Eh", text)
    if m:
        digest.final_energy_Ha = float(m.group(1))
        digest.final_energy_eV = digest.final_energy_Ha * HARTREE_TO_EV

    m = re.search(r"GRADIENT NORM\s+([\-0-9.]+)\s+Eh/", text)
    if m:
        digest.gradient_norm_Ha_per_a0 = float(m.group(1))

    m = re.search(r"HOMO-LUMO GAP\s+([\-0-9.]+)\s+eV", text)
    if m:
        digest.homo_lumo_gap_eV = float(m.group(1))

    m = re.search(r"GEOMETRY OPTIMIZATION CONVERGED AFTER\s+(\d+)\s+ITERATIONS", text)
    if m:
        digest.converged_geometry = True
        digest.n_opt_cycles = int(m.group(1))
    elif "FAILED TO CONVERGE" in text.upper():
        digest.converged_geometry = False

    m = re.search(r"total free energy\s+([\-0-9.]+)\s+Eh", text)
    if m:
        digest.free_energy_Ha = float(m.group(1))

    m = re.search(r"zero point energy\s+([\-0-9.]+)\s+Eh", text)
    if m:
        digest.zpe_Ha = float(m.group(1))

    digest.frequencies_cm = _parse_frequencies(text)

    digest.normal_termination = "normal termination of xtb" in text
    digest.wall_time_s = _parse_wall_time_s(text)
    digest.success = digest.normal_termination and digest.final_energy_Ha is not None

    if not digest.success and "error" in text.lower() and digest.error_message is None:
        digest.error_message = "xTB output indicates an error condition"

    return digest


def _fill_geometry_from_xtbopt(digest: XTBDigest, path: Path) -> None:
    text = path.read_text(errors="replace").strip()
    lines = text.splitlines()
    if len(lines) < 3:
        return

    try:
        n_atoms = int(lines[0].strip())
    except ValueError:
        return

    species: list[str] = []
    coords: list[list[float]] = []
    for line in lines[2 : 2 + n_atoms]:
        parts = line.split()
        if len(parts) < 4:
            continue
        try:
            species.append(parts[0])
            coords.append([float(parts[1]), float(parts[2]), float(parts[3])])
        except ValueError:
            continue

    digest.n_atoms = len(species)
    digest.final_species = species
    digest.final_cart_coords = coords
