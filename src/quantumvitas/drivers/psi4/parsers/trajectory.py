"""Psi4 trajectory parser (geometry optimization output.dat)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

import numpy as np

from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.core.analysis.trajectory.model import Frame, Trajectory
from quantumvitas.parsers.registry import register_parser

HA_TO_EV = 27.211386245988

# Matches: "  @DF-RKS Final Energy:   -76.42039065071262"
_RE_FINAL_ENERGY = re.compile(r"@DF-\S+\s+Final Energy:\s+([-\d.]+)")

# Matches atom line in Psi4 Geometry block (after header + dashes):
#   "         O            0.000000000000     0.000000000000     0.065677579134    15.994914619570"
_RE_ATOM_LINE = re.compile(
    r"^\s+([A-Z][a-z]?)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+[\d.]+"
)

# Marks: "  ==> Geometry <=="
_RE_GEOM_START = re.compile(r"==> Geometry <==")

# Marks: "    Geometry (in Angstrom), charge = ..."
_RE_GEOM_HEADER = re.compile(r"Geometry \(in Angstrom\)")


def parse_psi4_opt(text: str) -> list[dict]:
    """Parse Psi4 optimization output for per-step geometry + energy.

    Strategy: pair each @DF-... Final Energy with the most recent geometry block.
    """
    lines = text.splitlines()
    geometries: list[dict] = []  # list of {species, positions}
    energies: list[float] = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Detect geometry block
        if _RE_GEOM_START.search(line):
            # Scan forward for "Geometry (in Angstrom)" header
            j = i + 1
            while j < min(i + 10, len(lines)):
                if _RE_GEOM_HEADER.search(lines[j]):
                    # Skip header line, then "Center ..." header, then "----" dashes
                    k = j + 1
                    while k < len(lines) and "Center" not in lines[k]:
                        k += 1
                    k += 1  # skip "Center..." line
                    while k < len(lines) and "----" in lines[k]:
                        k += 1
                    # Now read atom lines
                    species: list[str] = []
                    positions: list[list[float]] = []
                    while k < len(lines):
                        m = _RE_ATOM_LINE.match(lines[k])
                        if not m:
                            break
                        species.append(m.group(1))
                        positions.append([
                            float(m.group(2)),
                            float(m.group(3)),
                            float(m.group(4)),
                        ])
                        k += 1
                    if species:
                        geometries.append({
                            "species": species,
                            "positions": np.array(positions, dtype=float),
                        })
                    break
                j += 1
            i += 1
            continue

        # Detect final energy
        m = _RE_FINAL_ENERGY.search(line)
        if m:
            energies.append(float(m.group(1)))

        i += 1

    # Pair geometries with energies.
    # Psi4 emits 2 geometry blocks per opt step (SCF + gradient).
    # We take every other geometry (the first of each pair) and pair with the energy.
    n_energies = len(energies)
    if len(geometries) == 2 * n_energies:
        paired_geoms = [geometries[2 * k] for k in range(n_energies)]
    elif len(geometries) == n_energies:
        paired_geoms = geometries
    else:
        # Best effort: take the last n_energies geometries
        paired_geoms = geometries[-n_energies:]

    frames = []
    for idx, (geom, energy_ha) in enumerate(zip(paired_geoms, energies)):
        frames.append({
            "species": geom["species"],
            "positions": geom["positions"],
            "energy": energy_ha * HA_TO_EV,
        })
    return frames


@register_parser("psi4", "trajectory")
class Psi4TrajectoryParser:
    """Psi4 trajectory parser."""

    engine = "psi4"
    object_type = "trajectory"

    def can_parse(self, raw_dir: Path) -> bool:
        for p in raw_dir.iterdir():
            if p.is_file() and p.suffix == ".dat":
                # Quick sniff for Psi4 content
                head = p.read_text(errors="replace")[:2000]
                if "Psi4" in head and "Final Energy" in p.read_text(errors="replace"):
                    return True
        return False

    def parse(self, evidence: EvidenceBundle) -> Trajectory:
        raw_dir = evidence.primary_raw_dir

        dat_files = sorted(raw_dir.glob("*.dat"))
        if not dat_files:
            raise FileNotFoundError(f"No .dat file in {raw_dir}")

        src_path = dat_files[0]
        text = src_path.read_text(encoding="utf-8", errors="replace")
        parsed = parse_psi4_opt(text)
        if not parsed:
            raise ValueError(f"No optimization steps found in {src_path}")

        frames: List[Frame] = []
        for idx, pf in enumerate(parsed):
            frames.append(Frame(
                frame_index=idx,
                positions=pf["positions"],
                species=pf["species"],
                cell=None,
                pbc=(False, False, False),
                iteration=idx,
                energy=pf["energy"],
            ))

        source_files = [SourceFileStat.from_path(src_path, evidence.calc_dir)]

        meta = AnalysisObjectMeta.create(
            object_type="trajectory",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="psi4_trajectory",
            parser_version="1.0",
        )

        return Trajectory(meta=meta, frames=frames, trajectory_type="relax")
