"""Radial Distribution Function (RDF) transform for trajectory bundles."""
from __future__ import annotations

from typing import Tuple

import numpy as np

from qmatsuite.core.analysis.bundles import DerivedPrimitiveBundle
from qmatsuite.core.analysis.primitives import Series1D
from qmatsuite.core.analysis.transforms.base import (
    PrimitiveBundle,
    PrimitiveTransform,
    clone_bundle_for_transform,
)


def _minimum_image_distances(
    positions: np.ndarray,
    cell: np.ndarray,
) -> np.ndarray:
    """Compute pairwise distances with minimum image convention."""
    n_atoms = len(positions)
    inv_cell = np.linalg.inv(cell)

    distances = []
    for i in range(n_atoms):
        for j in range(i + 1, n_atoms):
            d = positions[j] - positions[i]
            # Fractional coordinates
            s = d @ inv_cell
            s -= np.round(s)
            d_mic = s @ cell
            distances.append(np.linalg.norm(d_mic))
    return np.array(distances, dtype=float)


class RDF(PrimitiveTransform):
    """Compute radial distribution function from trajectory frames.

    g(r) is computed by histogramming pairwise distances across frames,
    normalized by ideal gas shell volume and average density.
    """

    name = "rdf"
    version = "1.0"

    def __init__(
        self,
        r_max: float = 6.0,
        n_bins: int = 100,
        species_pair: Tuple[str, str] | None = None,
    ):
        self.r_max = r_max
        self.n_bins = n_bins
        self.species_pair = species_pair

    def validate(self, bundle: PrimitiveBundle) -> list[str]:
        if bundle.geometry_frames is None:
            return ["Bundle has no geometry_frames; RDF cannot be computed."]
        warnings = []
        for frame in bundle.geometry_frames.frames:
            if frame.cell is None:
                warnings.append("RDF requires periodic cell; non-PBC frames skipped.")
                break
        return warnings

    def apply(self, bundle: PrimitiveBundle) -> DerivedPrimitiveBundle:
        result = clone_bundle_for_transform(bundle)

        if bundle.geometry_frames is None:
            result.transform_chain.append(self.to_record(self._params()))
            return result

        gf = bundle.geometry_frames
        dr = self.r_max / self.n_bins
        bin_edges = np.linspace(0.0, self.r_max, self.n_bins + 1)
        bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
        histogram = np.zeros(self.n_bins, dtype=float)
        n_frames_used = 0

        for frame in gf.frames:
            if frame.cell is None:
                continue

            pos = frame.positions
            species = frame.species

            # Filter by species pair if requested
            if self.species_pair is not None:
                sp_a, sp_b = self.species_pair
                idx_a = [i for i, s in enumerate(species) if s == sp_a]
                idx_b = [i for i, s in enumerate(species) if s == sp_b]
                if not idx_a or not idx_b:
                    continue

            distances = _minimum_image_distances(pos, frame.cell)
            mask = distances < self.r_max
            counts, _ = np.histogram(distances[mask], bins=bin_edges)
            histogram += counts
            n_frames_used += 1

        if n_frames_used > 0 and gf.frames[0].cell is not None:
            n_atoms = len(gf.frames[0].species)
            volume = abs(np.linalg.det(gf.frames[0].cell))
            density = n_atoms / volume
            n_pairs = n_atoms * (n_atoms - 1) / 2

            # Normalize
            for k in range(self.n_bins):
                r_inner = bin_edges[k]
                r_outer = bin_edges[k + 1]
                shell_vol = (4.0 / 3.0) * np.pi * (r_outer**3 - r_inner**3)
                ideal = density * shell_vol * n_pairs / n_atoms
                if ideal > 0:
                    histogram[k] /= (n_frames_used * ideal)

        rdf_series = Series1D(
            x=bin_centers,
            y=histogram,
            x_label="r",
            y_label="g(r)",
            x_unit="A",
            y_unit="",
            name="RDF",
        )

        result.series = [rdf_series]
        result.arrays["rdf_r"] = bin_centers
        result.arrays["rdf_gr"] = histogram
        result.transform_chain.append(self.to_record(self._params()))
        return result

    def _params(self) -> dict:
        return {
            "r_max": self.r_max,
            "n_bins": self.n_bins,
            "species_pair": list(self.species_pair) if self.species_pair else None,
        }
