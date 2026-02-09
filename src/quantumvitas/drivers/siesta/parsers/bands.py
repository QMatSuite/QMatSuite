"""Siesta bands analysis provider."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Sequence

import numpy as np

from quantumvitas.core.analysis.band_structure import BandStructure, HighSymPoint
from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.parsers.registry import register_parser


def _parse_siesta_eig(eig_path: Path) -> dict:
    """Parse Siesta .EIG file into eigenvalues dict.

    Format:
        Line 0: Fermi energy (eV)
        Line 1: n_bands n_spin n_kpoints
        Lines 2+: k-point index followed by eigenvalues (may span multiple lines)
    """
    lines = eig_path.read_text(encoding="utf-8", errors="replace").strip().split("\n")
    fermi_energy = float(lines[0].strip())

    header = lines[1].strip().split()
    n_bands = int(header[0])
    n_spin = int(header[1])
    n_kpoints = int(header[2])

    eigenvalues: dict[int, list[float]] = {}
    current_kpt: Optional[int] = None
    current_eigs: list[float] = []

    for line in lines[2:]:
        tokens = line.split()
        if not tokens:
            continue
        try:
            kpt_idx = int(tokens[0])
            if current_kpt is not None:
                eigenvalues[current_kpt] = current_eigs
            current_kpt = kpt_idx
            current_eigs = [float(t) for t in tokens[1:]]
        except ValueError:
            current_eigs.extend(float(t) for t in tokens)

    if current_kpt is not None:
        eigenvalues[current_kpt] = current_eigs

    return {
        "fermi_energy_eV": fermi_energy,
        "n_bands": n_bands,
        "n_spin": n_spin,
        "n_kpoints": n_kpoints,
        "eigenvalues": eigenvalues,
    }


def _extract_bandlines_from_out(out_path: Path) -> Optional[list[dict]]:
    """Extract BandLines k-path from Siesta .out file.

    Returns list of dicts with 'label' and 'kfrac' (fractional k-coords).
    """
    text = out_path.read_text(encoding="utf-8", errors="replace")

    # Look for BandLinesScale and BandLines block echoed in the output
    bandlines: list[dict] = []

    # Pattern: "redata: BandLines" or "%block BandLines" echoed
    # Siesta echoes the input in the output. Look for BandLines content.
    # Format in .out:
    #   block BandLinesScale pi/a  (or ReciprocalLatticeVectors)
    #   block BandLines
    #     1  0.500 0.500 0.500  L
    #    20  0.000 0.000 0.000  \Gamma
    #   endblock BandLines

    # Find BandLinesScale
    scale_match = re.search(r"BandLinesScale\s+(\S+)", text, re.IGNORECASE)
    scale = scale_match.group(1).lower() if scale_match else "reciprocallatticevectors"

    # Find BandLines block content
    block_match = re.search(
        r"block\s+BandLines\s*\n(.*?)(?:endblock|end\s+block)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not block_match:
        return None

    for line in block_match.group(1).strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) >= 5:
            try:
                npts = int(parts[0])
                kx, ky, kz = float(parts[1]), float(parts[2]), float(parts[3])
                label = parts[4] if len(parts) > 4 else ""
                # Clean up label: \Gamma -> Γ
                label = label.replace("\\Gamma", "Γ").replace("Gamma", "Γ")
                bandlines.append({
                    "npoints": npts,
                    "kfrac": [kx, ky, kz],
                    "label": label,
                })
            except (ValueError, IndexError):
                continue

    return bandlines if bandlines else None


@register_parser("siesta", "bands")
class SiestaBandsProvider:
    """Parse Siesta band structure outputs into a canonical BandStructure."""

    engine = "siesta"
    object_type = "bands"

    def can_parse(self, raw_dir: Path) -> bool:
        return bool(list(raw_dir.glob("*.EIG")))

    def parse(self, evidence: EvidenceBundle) -> BandStructure:
        """Parse Siesta .EIG file and return engine-agnostic BandStructure."""
        raw_dir = evidence.primary_raw_dir

        eig_files = sorted(raw_dir.glob("*.EIG"))
        if not eig_files:
            raise FileNotFoundError(f"No Siesta .EIG file found in {raw_dir}")
        eig_file = eig_files[0]

        warnings: list[str] = []
        parsed = _parse_siesta_eig(eig_file)

        fermi_energy = parsed["fermi_energy_eV"]
        n_kpoints = parsed["n_kpoints"]
        n_bands = parsed["n_bands"]
        n_spin = parsed["n_spin"]

        # Build eigenvalue array (n_kpoints, n_bands) — already in eV
        eigenvalues = np.zeros((n_kpoints, n_bands), dtype=float)
        for kpt_idx in sorted(parsed["eigenvalues"].keys()):
            eigs = parsed["eigenvalues"][kpt_idx]
            # Handle spin: for n_spin=1, all bands in one block
            # For n_spin=2, first n_bands are spin-up, next n_bands spin-down
            if n_spin == 1:
                eigenvalues[kpt_idx - 1, :] = eigs[:n_bands]
            else:
                # Use only first spin channel for now
                eigenvalues[kpt_idx - 1, :] = eigs[:n_bands]

        source_files = [SourceFileStat.from_path(eig_file, evidence.calc_dir)]

        # Try to get high-symmetry points and k-distances from .out
        high_sym_points: list[HighSymPoint] = []
        k_distances = np.arange(n_kpoints, dtype=float)  # fallback: index-based

        out_files = sorted(raw_dir.glob("*.out"))
        if out_files:
            out_file = out_files[0]
            source_files.append(SourceFileStat.from_path(out_file, evidence.calc_dir))

            bandlines = _extract_bandlines_from_out(out_file)
            if bandlines:
                # Compute cumulative k-distances from BandLines segment lengths
                total_pts = sum(bl["npoints"] for bl in bandlines)
                if total_pts > 0:
                    # Build k_distances as proportional distances along the path
                    segment_distances: list[float] = []
                    for i in range(1, len(bandlines)):
                        k1 = np.array(bandlines[i - 1]["kfrac"])
                        k2 = np.array(bandlines[i]["kfrac"])
                        segment_distances.append(float(np.linalg.norm(k2 - k1)))

                    # Build cumulative k_distances
                    k_dist_list: list[float] = [0.0]
                    cumulative = 0.0
                    seg_idx = 0
                    points_in_seg = 0
                    for kpt in range(1, n_kpoints):
                        if seg_idx < len(segment_distances):
                            npts_seg = bandlines[seg_idx + 1]["npoints"] if (seg_idx + 1) < len(bandlines) else 1
                            if npts_seg > 0:
                                cumulative += segment_distances[seg_idx] / max(npts_seg, 1)
                        k_dist_list.append(cumulative)
                        points_in_seg += 1
                        # Check if we've completed this segment
                        if seg_idx + 1 < len(bandlines):
                            npts_this = bandlines[seg_idx + 1]["npoints"]
                            if points_in_seg >= npts_this and seg_idx + 2 < len(bandlines):
                                seg_idx += 1
                                points_in_seg = 0

                    if len(k_dist_list) == n_kpoints:
                        k_distances = np.array(k_dist_list, dtype=float)

                    # Add high-symmetry point markers
                    cumulative_kpt = 0
                    cum_dist = 0.0
                    for i, bl in enumerate(bandlines):
                        if i == 0:
                            high_sym_points.append(HighSymPoint(
                                k_distance=k_distances[0] if n_kpoints > 0 else 0.0,
                                label=bl["label"],
                            ))
                        else:
                            cumulative_kpt += bl["npoints"]
                            idx = min(cumulative_kpt - 1, n_kpoints - 1)
                            high_sym_points.append(HighSymPoint(
                                k_distance=float(k_distances[idx]),
                                label=bl["label"],
                            ))
            else:
                warnings.append("No BandLines block found in .out; using index-based k-distances.")
        else:
            warnings.append("No .out file found; using index-based k-distances.")

        meta = AnalysisObjectMeta.create(
            object_type="bands",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="siesta_bands",
            parser_version="1.0",
            warnings=warnings,
        )

        return BandStructure(
            meta=meta,
            k_distances=k_distances,
            eigenvalues=eigenvalues,
            high_symmetry_points=high_sym_points,
            fermi_energy=fermi_energy,
            spin_polarized=False,
        )
