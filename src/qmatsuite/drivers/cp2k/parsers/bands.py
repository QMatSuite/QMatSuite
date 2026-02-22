"""CP2K bands analysis provider."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import numpy as np

from qmatsuite.core.analysis.band_structure import BandStructure, HighSymPoint
from qmatsuite.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.parsers.registry import register_parser

# Hartree to eV conversion
HA_TO_EV = 27.211386245988


def _parse_cp2k_bs(bs_path: Path) -> dict:
    """Parse CP2K .bs band structure file.

    Format:
        # Set 1: 2 special points, 21 k-points, 4 bands
        #  Special point 1   0.000  0.000  0.000  GAMMA
        #  Special point 2   0.500  0.000  0.500  X
        #  Point 1  Spin 1:  0.000  0.000  0.000   0.04762
        #   Band    Energy [eV]     Occupation
              1    -6.73130691     2.00000000
              ...
        # Set 2: ...

    Returns dict with sets (list of set dicts), each containing
    special_points, k_points, eigenvalues, n_bands.
    """
    text = bs_path.read_text(encoding="utf-8", errors="replace")
    lines = text.strip().split("\n")

    sets: list[dict] = []
    current_set: Optional[dict] = None
    current_point_eigs: list[float] = []
    current_point_kpt: Optional[list[float]] = None
    n_bands = 0

    for line in lines:
        stripped = line.strip()

        # Set header: # Set N: M special points, K k-points, B bands
        set_match = re.match(
            r"#\s*Set\s+\d+:\s+\d+\s+special\s+points,\s+(\d+)\s+k-points,\s+(\d+)\s+bands",
            stripped,
        )
        if set_match:
            # Save previous set
            if current_set is not None:
                if current_point_kpt is not None:
                    current_set["k_points"].append(current_point_kpt)
                    current_set["eigenvalues"].append(current_point_eigs)
                sets.append(current_set)

            n_bands = int(set_match.group(2))
            current_set = {
                "special_points": [],
                "k_points": [],
                "eigenvalues": [],
                "n_bands": n_bands,
            }
            current_point_kpt = None
            current_point_eigs = []
            continue

        if current_set is None:
            continue

        # Special point: #  Special point N  kx ky kz  LABEL
        sp_match = re.match(
            r"#\s+Special\s+point\s+\d+\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+(\S+)",
            stripped,
        )
        if sp_match:
            current_set["special_points"].append({
                "coords": [float(sp_match.group(1)), float(sp_match.group(2)), float(sp_match.group(3))],
                "label": sp_match.group(4),
            })
            continue

        # Point header: #  Point N  Spin 1:  kx ky kz  weight
        pt_match = re.match(
            r"#\s+Point\s+\d+\s+Spin\s+\d+:\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)",
            stripped,
        )
        if pt_match:
            # Save previous point
            if current_point_kpt is not None:
                current_set["k_points"].append(current_point_kpt)
                current_set["eigenvalues"].append(current_point_eigs)

            current_point_kpt = [
                float(pt_match.group(1)),
                float(pt_match.group(2)),
                float(pt_match.group(3)),
            ]
            current_point_eigs = []
            continue

        # Band header line: skip
        if stripped.startswith("#") and "Band" in stripped:
            continue

        # Band data: band_index  energy  occupation
        if current_point_kpt is not None and not stripped.startswith("#"):
            parts = stripped.split()
            if len(parts) >= 2:
                try:
                    current_point_eigs.append(float(parts[1]))
                except ValueError:
                    pass

    # Save final set
    if current_set is not None:
        if current_point_kpt is not None:
            current_set["k_points"].append(current_point_kpt)
            current_set["eigenvalues"].append(current_point_eigs)
        sets.append(current_set)

    return {"sets": sets}


def _extract_fermi_from_out(out_path: Path) -> Optional[float]:
    """Extract Fermi energy from CP2K .out file. Returns eV."""
    text = out_path.read_text(encoding="utf-8", errors="replace")
    # Pattern: "  Fermi energy:                                                 0.28352137278734"
    match = re.search(r"Fermi\s+energy:\s+([-\d.]+)", text)
    if match:
        try:
            return float(match.group(1)) * HA_TO_EV
        except ValueError:
            pass
    return None


def _compute_k_distances_from_sets(sets: list[dict]) -> tuple[np.ndarray, list[HighSymPoint]]:
    """Compute cumulative k-distances across all sets.

    Returns (k_distances, high_sym_points).
    """
    all_k_distances: list[float] = []
    high_sym_points: list[HighSymPoint] = []
    cumulative_dist = 0.0

    for si, s in enumerate(sets):
        k_points = s["k_points"]
        if not k_points:
            continue

        for ki, kpt in enumerate(k_points):
            if ki == 0 and si == 0:
                all_k_distances.append(0.0)
            elif ki == 0 and si > 0:
                # Set boundary: no distance increment (continuous path)
                all_k_distances.append(cumulative_dist)
            else:
                prev = np.array(k_points[ki - 1])
                curr = np.array(kpt)
                dist = float(np.linalg.norm(curr - prev))
                cumulative_dist += dist
                all_k_distances.append(cumulative_dist)

        # Record high-symmetry points from special_points
        sp_list = s["special_points"]
        if sp_list:
            # First special point is at the start of this set's k-points
            sp0 = sp_list[0]
            label = sp0["label"]
            if label == "GAMMA":
                label = "Γ"
            # Find the k-distance index for start of this set
            start_idx = sum(len(prev_s["k_points"]) for prev_s in sets[:si])
            if start_idx < len(all_k_distances):
                high_sym_points.append(HighSymPoint(
                    label=label,
                    k_distance=all_k_distances[start_idx],
                ))

            # Last special point is at the end of this set's k-points
            if len(sp_list) > 1:
                sp_last = sp_list[-1]
                label_last = sp_last["label"]
                if label_last == "GAMMA":
                    label_last = "Γ"
                end_idx = start_idx + len(k_points) - 1
                if end_idx < len(all_k_distances):
                    high_sym_points.append(HighSymPoint(
                        label=label_last,
                        k_distance=all_k_distances[end_idx],
                    ))

    # De-duplicate consecutive identical labels at same distance
    deduped: list[HighSymPoint] = []
    for hsp in high_sym_points:
        if deduped and abs(hsp.k_distance - deduped[-1].k_distance) < 1e-10:
            # Same point — keep the first
            continue
        deduped.append(hsp)

    return np.array(all_k_distances, dtype=float), deduped


@register_parser("cp2k", "bands")
class CP2KBandsProvider:
    """Parse CP2K band structure outputs into a canonical BandStructure."""

    engine = "cp2k"
    object_type = "bands"

    def can_parse(self, raw_dir: Path) -> bool:
        return bool(list(raw_dir.glob("*.bs")))

    def parse(self, evidence: EvidenceBundle) -> BandStructure:
        """Parse CP2K .bs file and return engine-agnostic BandStructure."""
        raw_dir = evidence.primary_raw_dir
        warnings: list[str] = []

        bs_files = sorted(raw_dir.glob("*.bs"))
        if not bs_files:
            raise FileNotFoundError(f"No CP2K .bs file found in {raw_dir}")
        bs_file = bs_files[0]

        parsed = _parse_cp2k_bs(bs_file)
        source_files = [SourceFileStat.from_path(bs_file, evidence.calc_dir)]

        # Concatenate eigenvalues from all sets into single 2D array
        sets = parsed["sets"]
        if not sets:
            raise ValueError(f"No band structure sets found in {bs_file}")

        n_bands = sets[0]["n_bands"]
        all_eigenvalues: list[list[float]] = []
        for s in sets:
            all_eigenvalues.extend(s["eigenvalues"])

        n_kpoints = len(all_eigenvalues)
        eigenvalues = np.zeros((n_kpoints, n_bands), dtype=float)
        for ki, eigs in enumerate(all_eigenvalues):
            for bi in range(min(len(eigs), n_bands)):
                eigenvalues[ki, bi] = eigs[bi]

        # Compute k-distances and high-symmetry points
        k_distances, high_sym_points = _compute_k_distances_from_sets(sets)

        # Get Fermi energy from .out file
        fermi_energy: Optional[float] = None
        out_files = sorted(raw_dir.glob("*.out"))
        if out_files:
            out_file = out_files[0]
            source_files.append(SourceFileStat.from_path(out_file, evidence.calc_dir))
            fermi_energy = _extract_fermi_from_out(out_file)

        if fermi_energy is None:
            warnings.append("No Fermi energy found in CP2K output.")

        meta = AnalysisObjectMeta.create(
            object_type="bands",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="cp2k_bands",
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
