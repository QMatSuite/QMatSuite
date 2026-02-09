"""ABINIT bands analysis provider."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

import numpy as np

from quantumvitas.core.analysis.band_structure import BandStructure, HighSymPoint
from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.parsers.registry import register_parser

# Hartree to eV conversion
HA_TO_EV = 27.211386245988


def _parse_abinit_eig(eig_path: Path) -> dict:
    """Parse ABINIT _EIG file.

    Format:
        Eigenvalues (hartree) for nkpt=  41  k points:
        kpt#   1, nband=  8, wtk=  1.00000, kpt=  0.5000  0.5000  0.5000 (reduced coord)
          -0.14089   -0.04445    0.16905    0.16905    0.26473    0.33405    0.33405    0.48825
        kpt#   2, ...

    Returns dict with k_points (fractional), eigenvalues_ha, n_kpoints, n_bands.
    """
    text = eig_path.read_text(encoding="utf-8", errors="replace")
    lines = text.strip().split("\n")

    # Parse header
    header_match = re.search(r"nkpt=\s*(\d+)", lines[0])
    n_kpoints = int(header_match.group(1)) if header_match else 0

    k_points: list[list[float]] = []
    eigenvalues: list[list[float]] = []
    n_bands = 0
    current_eigs: list[float] = []
    current_kpt_coords: Optional[list[float]] = None

    for line in lines[1:]:
        kpt_match = re.match(
            r"\s*kpt#\s*\d+,\s*nband=\s*(\d+),\s*wtk=\s*[\d.]+,\s*kpt=\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)",
            line,
        )
        if kpt_match:
            # Save previous k-point data
            if current_kpt_coords is not None:
                k_points.append(current_kpt_coords)
                eigenvalues.append(current_eigs)

            n_bands = int(kpt_match.group(1))
            current_kpt_coords = [
                float(kpt_match.group(2)),
                float(kpt_match.group(3)),
                float(kpt_match.group(4)),
            ]
            current_eigs = []
        else:
            # Eigenvalue line
            stripped = line.strip()
            if stripped and current_kpt_coords is not None:
                try:
                    current_eigs.extend(float(x) for x in stripped.split())
                except ValueError:
                    pass

    # Save last k-point
    if current_kpt_coords is not None:
        k_points.append(current_kpt_coords)
        eigenvalues.append(current_eigs)

    return {
        "n_kpoints": len(k_points),
        "n_bands": n_bands,
        "k_points_frac": k_points,
        "eigenvalues_ha": eigenvalues,
    }


def _extract_fermi_from_abo(abo_path: Path) -> Optional[float]:
    """Extract Fermi energy from ABINIT .abo output file.

    Returns Fermi energy in eV.
    """
    text = abo_path.read_text(encoding="utf-8", errors="replace")

    # Look for "Fermi ... energy" lines
    patterns = [
        r"Fermi\s*\(or\s+HOMO\)\s*energy\s*\(hartree\)\s*=\s*([-\d.E+]+)",
        r"Fermi\s+energy\s*\(hartree\)\s*=\s*([-\d.E+]+)",
        r"mu\s*=\s*([-\d.E+]+)\s*Hartree",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1)) * HA_TO_EV
            except ValueError:
                continue

    return None


def _compute_k_distances(k_points_frac: list[list[float]]) -> np.ndarray:
    """Compute cumulative k-distances from fractional k-point coordinates.

    Uses Euclidean distance in fractional space (adequate for cubic systems).
    For better accuracy, would need reciprocal lattice vectors.
    """
    n_kpoints = len(k_points_frac)
    if n_kpoints == 0:
        return np.array([], dtype=float)

    distances = [0.0]
    for i in range(1, n_kpoints):
        k1 = np.array(k_points_frac[i - 1])
        k2 = np.array(k_points_frac[i])
        dist = float(np.linalg.norm(k2 - k1))
        distances.append(distances[-1] + dist)

    return np.array(distances, dtype=float)


@register_parser("abinit", "bands")
class ABINITBandsProvider:
    """Parse ABINIT band structure outputs into a canonical BandStructure."""

    engine = "abinit"
    object_type = "bands"

    def can_parse(self, raw_dir: Path) -> bool:
        return bool(
            list(raw_dir.glob("*_EIG"))
            or list(raw_dir.glob("*o_DS*_EIG"))
        )

    def parse(self, evidence: EvidenceBundle) -> BandStructure:
        """Parse ABINIT _EIG file and return engine-agnostic BandStructure."""
        raw_dir = evidence.primary_raw_dir
        warnings: list[str] = []

        # Find EIG file — prefer DS2 (bands dataset) over DS1 (SCF)
        eig_files = sorted(raw_dir.glob("*_DS2_EIG"))
        if not eig_files:
            eig_files = sorted(raw_dir.glob("*_EIG"))
        if not eig_files:
            raise FileNotFoundError(f"No ABINIT _EIG file found in {raw_dir}")
        eig_file = eig_files[0]

        parsed = _parse_abinit_eig(eig_file)
        source_files = [SourceFileStat.from_path(eig_file, evidence.calc_dir)]

        # Convert eigenvalues from Hartree to eV
        n_kpoints = parsed["n_kpoints"]
        n_bands = parsed["n_bands"]
        eigenvalues = np.zeros((n_kpoints, n_bands), dtype=float)
        for ki, eigs in enumerate(parsed["eigenvalues_ha"]):
            for bi in range(min(len(eigs), n_bands)):
                eigenvalues[ki, bi] = eigs[bi] * HA_TO_EV

        # Compute k-distances
        k_distances = _compute_k_distances(parsed["k_points_frac"])

        # Get Fermi energy from .abo file
        fermi_energy: Optional[float] = None
        abo_files = sorted(raw_dir.glob("*.abo"))
        if abo_files:
            abo_file = abo_files[0]
            source_files.append(SourceFileStat.from_path(abo_file, evidence.calc_dir))
            fermi_energy = _extract_fermi_from_abo(abo_file)

        if fermi_energy is None:
            warnings.append("No Fermi energy found in ABINIT output.")

        meta = AnalysisObjectMeta.create(
            object_type="bands",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="abinit_bands",
            parser_version="1.0",
            warnings=warnings,
        )

        return BandStructure(
            meta=meta,
            k_distances=k_distances,
            eigenvalues=eigenvalues,
            high_symmetry_points=[],
            fermi_energy=fermi_energy,
            spin_polarized=False,
        )
