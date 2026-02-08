"""Engine-agnostic band structure analysis model."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from quantumvitas.core.analysis.base import AnalysisObjectMeta
from quantumvitas.core.analysis.bundles import (
    CanonicalPrimitiveBundle,
    ProvenanceMeta,
    RenderMeta,
)
from quantumvitas.core.analysis.primitives import Marker, Series1D


@dataclass(frozen=True)
class HighSymPoint:
    """High-symmetry point marker on the k-path."""

    k_distance: float
    label: str


@dataclass
class BandStructure:
    """Engine-agnostic band structure analysis object."""

    meta: AnalysisObjectMeta
    k_distances: np.ndarray
    eigenvalues: np.ndarray
    high_symmetry_points: List[HighSymPoint] = field(default_factory=list)
    fermi_energy: Optional[float] = None
    spin_polarized: bool = False

    def __post_init__(self) -> None:
        if self.k_distances.ndim != 1:
            raise ValueError("k_distances must be a 1D array")
        if self.eigenvalues.ndim not in {2, 3}:
            raise ValueError("eigenvalues must be 2D or 3D")

        if self.eigenvalues.ndim == 2:
            if self.eigenvalues.shape[0] != self.k_distances.shape[0]:
                raise ValueError("2D eigenvalues must have shape (n_kpoints, n_bands)")
        else:
            if self.eigenvalues.shape[1] != self.k_distances.shape[0]:
                raise ValueError("3D eigenvalues must have shape (n_spin, n_kpoints, n_bands)")
            self.spin_polarized = True

    @property
    def n_kpoints(self) -> int:
        if self.eigenvalues.ndim == 2:
            return int(self.eigenvalues.shape[0])
        return int(self.eigenvalues.shape[1])

    @property
    def n_bands(self) -> int:
        if self.eigenvalues.ndim == 2:
            return int(self.eigenvalues.shape[1])
        return int(self.eigenvalues.shape[2])

    def to_primitives(self) -> CanonicalPrimitiveBundle:
        """Convert to canonical primitive bundle."""
        series: List[Series1D] = []
        k_axis = np.array(self.k_distances, copy=True)

        if self.eigenvalues.ndim == 2:
            for band_index in range(self.n_bands):
                series.append(
                    Series1D(
                        x=np.array(k_axis, copy=True),
                        y=np.array(self.eigenvalues[:, band_index], copy=True),
                        x_label="k-path",
                        y_label="Energy",
                        x_unit="1/A",
                        y_unit="eV",
                        name=f"band_{band_index}",
                    )
                )
        else:
            n_spin = self.eigenvalues.shape[0]
            for spin_index in range(n_spin):
                for band_index in range(self.n_bands):
                    series.append(
                        Series1D(
                            x=np.array(k_axis, copy=True),
                            y=np.array(self.eigenvalues[spin_index, :, band_index], copy=True),
                            x_label="k-path",
                            y_label="Energy",
                            x_unit="1/A",
                            y_unit="eV",
                            name=f"spin_{spin_index}_band_{band_index}",
                        )
                    )

        render_meta = RenderMeta(
            axis_labels={"x": "k-path", "y": "Energy"},
            units={"x": "1/A", "y": "eV"},
            series_labels=[series_item.name for series_item in series],
            reference_energy=self.fermi_energy,
            markers=[
                Marker(
                    position=point.k_distance,
                    label=point.label,
                    axis="x",
                )
                for point in self.high_symmetry_points
            ],
        )

        provenance_meta = ProvenanceMeta(
            schema_version=self.meta.schema_version,
            object_type=self.meta.object_type,
            run_ulid=self.meta.run_ulid,
            calc_ulid=self.meta.calc_ulid,
            step_ulids=list(self.meta.step_ulids),
            gen_steps=list(self.meta.gen_steps),
            engine_name=self.meta.engine_name,
            source_files=list(self.meta.source_files),
            parser_name=self.meta.parser_name,
            parser_version=self.meta.parser_version,
            warnings=list(self.meta.warnings),
            manifest_snapshot=self.meta.manifest_snapshot,
        )

        return CanonicalPrimitiveBundle(
            object_type=self.meta.object_type,
            render_meta=render_meta,
            provenance_meta=provenance_meta,
            series=series,
            arrays={
                "k_distances": np.array(self.k_distances, copy=True),
                "eigenvalues": np.array(self.eigenvalues, copy=True),
            },
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "meta": self.meta.to_dict(),
            "k_distances": self.k_distances.tolist(),
            "eigenvalues": self.eigenvalues.tolist(),
            "high_symmetry_points": [
                {"k_distance": point.k_distance, "label": point.label}
                for point in self.high_symmetry_points
            ],
            "fermi_energy": self.fermi_energy,
            "spin_polarized": self.spin_polarized,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BandStructure":
        return cls(
            meta=AnalysisObjectMeta.from_dict(data["meta"]),
            k_distances=np.array(data["k_distances"]),
            eigenvalues=np.array(data["eigenvalues"]),
            high_symmetry_points=[
                HighSymPoint(
                    k_distance=point_data["k_distance"],
                    label=point_data["label"],
                )
                for point_data in data.get("high_symmetry_points", [])
            ],
            fermi_energy=data.get("fermi_energy"),
            spin_polarized=bool(data.get("spin_polarized", False)),
        )

