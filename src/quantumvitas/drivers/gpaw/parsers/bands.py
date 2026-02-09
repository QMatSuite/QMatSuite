"""GPAW bands analysis provider."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np

from quantumvitas.core.analysis.band_structure import BandStructure, HighSymPoint
from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.parsers.registry import register_parser


def _decode_ndarray(obj: dict) -> np.ndarray:
    """Decode ASE __ndarray__ serialization format.

    Format: {"__ndarray__": [[shape...], dtype, [flat_data...]]}
    """
    shape, dtype, data = obj["__ndarray__"]
    return np.array(data, dtype=dtype).reshape(shape)


def _parse_bandstructure_json(path: Path) -> dict:
    """Parse GPAW/ASE bandstructure.json.

    Format:
        {
            "path": {
                "kpts": {"__ndarray__": [[n_kpoints, 3], "float64", [...]]},
                "special_points": {"G": {"__ndarray__": ...}, "X": ...},
                "labelseq": "GXWKGLUWLK",
                "cell": {...},
            },
            "energies": {"__ndarray__": [[n_spin, n_kpoints, n_bands], "float64", [...]]},
            "reference": <fermi_energy_eV>,
        }

    Returns dict with k_points_frac, eigenvalues_eV, fermi_eV,
    special_points, labelseq.
    """
    data = json.loads(path.read_text(encoding="utf-8"))

    # Energies: shape (n_spin, n_kpoints, n_bands)
    energies = _decode_ndarray(data["energies"])

    # k-points: shape (n_kpoints, 3)
    k_points = _decode_ndarray(data["path"]["kpts"])

    # Fermi energy (reference)
    fermi_eV = data.get("reference")

    # Special points dict: name -> frac coords
    special_points = {}
    for name, val in data["path"].get("special_points", {}).items():
        if isinstance(val, dict) and "__ndarray__" in val:
            special_points[name] = _decode_ndarray(val).tolist()
        elif isinstance(val, list):
            special_points[name] = val

    labelseq = data["path"].get("labelseq", "")

    # Cell for computing k-distances (reciprocal lattice)
    cell = None
    cell_data = data["path"].get("cell")
    if cell_data and isinstance(cell_data, dict):
        array_data = cell_data.get("array")
        if array_data and isinstance(array_data, dict) and "__ndarray__" in array_data:
            cell = _decode_ndarray(array_data)

    return {
        "k_points_frac": k_points,
        "eigenvalues_eV": energies,
        "fermi_eV": fermi_eV,
        "special_points": special_points,
        "labelseq": labelseq,
        "cell": cell,
    }


def _compute_k_distances(k_points_frac: np.ndarray, cell: Optional[np.ndarray]) -> np.ndarray:
    """Compute cumulative k-distances from fractional k-points.

    If cell is available, uses reciprocal lattice for proper distances.
    Otherwise falls back to Euclidean distance in fractional space.
    """
    n_kpoints = len(k_points_frac)
    if n_kpoints == 0:
        return np.array([], dtype=float)

    if cell is not None:
        # Compute reciprocal lattice vectors: b = 2*pi * inv(a)^T
        recip = 2.0 * np.pi * np.linalg.inv(cell).T
    else:
        recip = None

    distances = [0.0]
    for i in range(1, n_kpoints):
        dk_frac = k_points_frac[i] - k_points_frac[i - 1]
        if recip is not None:
            dk_cart = dk_frac @ recip
        else:
            dk_cart = dk_frac
        distances.append(distances[-1] + float(np.linalg.norm(dk_cart)))

    return np.array(distances, dtype=float)


def _find_high_sym_points(
    k_points_frac: np.ndarray,
    k_distances: np.ndarray,
    special_points: dict,
    labelseq: str,
) -> list[HighSymPoint]:
    """Identify high-symmetry points along the k-path.

    Uses labelseq to determine expected sequence and matches k-points
    to special point coordinates.
    """
    if not labelseq or not special_points:
        return []

    # Parse labelseq into individual labels
    # labelseq is like "GXWKGLUWLK" — each char is a label
    # But multi-char labels don't exist in standard FCC/BCC paths
    labels = list(labelseq)

    # Match labels to k-point positions by finding nearest k-point
    # to each special point in sequence
    result: list[HighSymPoint] = []
    search_start = 0

    for label in labels:
        if label not in special_points:
            continue
        sp_frac = np.array(special_points[label])

        # Find closest k-point from search_start onwards
        best_idx = search_start
        best_dist = float("inf")
        for ki in range(search_start, len(k_points_frac)):
            dist = float(np.linalg.norm(k_points_frac[ki] - sp_frac))
            if dist < best_dist:
                best_dist = dist
                best_idx = ki

        if best_dist < 0.01:  # tolerance
            # Map "G" to the display label "Γ"
            display = "Γ" if label == "G" else label
            result.append(HighSymPoint(
                label=display,
                k_distance=float(k_distances[best_idx]),
            ))
            search_start = best_idx + 1

    return result


@register_parser("gpaw", "bands")
class GPAWBandsProvider:
    """Parse GPAW band structure outputs into a canonical BandStructure."""

    engine = "gpaw"
    object_type = "bands"

    def can_parse(self, raw_dir: Path) -> bool:
        return (raw_dir / "bandstructure.json").exists()

    def parse(self, evidence: EvidenceBundle) -> BandStructure:
        """Parse GPAW bandstructure.json and return engine-agnostic BandStructure."""
        raw_dir = evidence.primary_raw_dir
        warnings: list[str] = []

        bs_file = raw_dir / "bandstructure.json"
        if not bs_file.exists():
            raise FileNotFoundError(f"No bandstructure.json found in {raw_dir}")

        parsed = _parse_bandstructure_json(bs_file)
        source_files = [SourceFileStat.from_path(bs_file, evidence.calc_dir)]

        # Eigenvalues: take first spin channel, shape (n_kpoints, n_bands)
        energies = parsed["eigenvalues_eV"]
        if energies.ndim == 3:
            eigenvalues = energies[0]  # first spin channel
            spin_polarized = energies.shape[0] > 1
        else:
            eigenvalues = energies
            spin_polarized = False

        # Compute k-distances
        k_distances = _compute_k_distances(
            parsed["k_points_frac"],
            parsed.get("cell"),
        )

        # Find high-symmetry points
        high_sym_points = _find_high_sym_points(
            parsed["k_points_frac"],
            k_distances,
            parsed["special_points"],
            parsed["labelseq"],
        )

        fermi_energy = parsed.get("fermi_eV")
        if fermi_energy is None:
            warnings.append("No Fermi energy (reference) found in bandstructure.json.")

        meta = AnalysisObjectMeta.create(
            object_type="bands",
            source_files=source_files,
            run_ulid=evidence.run_ulid,
            calc_ulid=evidence.calc_ulid,
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="gpaw_bands",
            parser_version="1.0",
            warnings=warnings,
        )

        return BandStructure(
            meta=meta,
            k_distances=k_distances,
            eigenvalues=eigenvalues,
            high_symmetry_points=high_sym_points,
            fermi_energy=fermi_energy,
            spin_polarized=spin_polarized,
        )
