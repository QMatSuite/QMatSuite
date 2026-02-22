"""Engine-agnostic DOS analysis model."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from qmatsuite.core.analysis.base import AnalysisObjectMeta
from qmatsuite.core.analysis.bundles import (
    CanonicalPrimitiveBundle,
    ProvenanceMeta,
    RenderMeta,
)
from qmatsuite.core.analysis.primitives import Series1D


@dataclass
class DOS:
    """Engine-agnostic DOS analysis object."""

    meta: AnalysisObjectMeta
    energies: np.ndarray  # shape (nedos,), eV
    total_dos: np.ndarray  # shape (nedos,) or (2, nedos) for spin
    fermi_energy: Optional[float] = None
    integrated_dos: Optional[np.ndarray] = None  # shape (nedos,)
    pdos: Optional[np.ndarray] = None  # shape (n_atoms, nedos, n_orbitals)
    atom_labels: Optional[List[str]] = None
    orbital_labels: Optional[List[str]] = None
    spin_polarized: bool = False

    def __post_init__(self) -> None:
        if self.energies.ndim != 1:
            raise ValueError("energies must be a 1D array")
        nedos = self.energies.shape[0]

        if self.total_dos.ndim == 1:
            if self.total_dos.shape[0] != nedos:
                raise ValueError("total_dos must have shape (nedos,) or (2, nedos)")
            self.spin_polarized = False
        elif self.total_dos.ndim == 2:
            if self.total_dos.shape != (2, nedos):
                raise ValueError("total_dos must have shape (nedos,) or (2, nedos)")
            self.spin_polarized = True
        else:
            raise ValueError("total_dos must be 1D or 2D")

        if self.integrated_dos is not None:
            if self.integrated_dos.shape != (nedos,):
                raise ValueError("integrated_dos must have shape (nedos,)")

        if self.pdos is not None:
            if self.pdos.ndim != 3:
                raise ValueError("pdos must have shape (n_atoms, nedos, n_orbitals)")
            if self.pdos.shape[1] != nedos:
                raise ValueError("pdos second dimension must match nedos")

    def to_primitives(self) -> CanonicalPrimitiveBundle:
        """Convert to canonical primitive bundle."""
        series: List[Series1D] = []
        energies = np.array(self.energies, copy=True)

        if self.spin_polarized:
            series.append(
                Series1D(
                    x=energies,
                    y=np.array(self.total_dos[0], copy=True),
                    x_label="Energy",
                    y_label="DOS",
                    x_unit="eV",
                    y_unit="states/eV",
                    name="DOS up",
                )
            )
            series.append(
                Series1D(
                    x=energies,
                    y=-np.array(self.total_dos[1], copy=True),
                    x_label="Energy",
                    y_label="DOS",
                    x_unit="eV",
                    y_unit="states/eV",
                    name="DOS down",
                )
            )
        else:
            series.append(
                Series1D(
                    x=energies,
                    y=np.array(self.total_dos, copy=True),
                    x_label="Energy",
                    y_label="DOS",
                    x_unit="eV",
                    y_unit="states/eV",
                    name="Total DOS",
                )
            )

        # Emit PDOS as individual Series1D entries per (atom, orbital)
        if self.pdos is not None:
            atom_labels = self.atom_labels or [
                f"atom_{i}" for i in range(self.pdos.shape[0])
            ]
            orbital_labels = self.orbital_labels or [
                f"orb_{j}" for j in range(self.pdos.shape[2])
            ]
            for i, atom_lbl in enumerate(atom_labels):
                for j, orb_lbl in enumerate(orbital_labels):
                    pdos_y = self.pdos[i, :, j]
                    if self.spin_polarized:
                        # For spin-polarized PDOS, assume pdos is per-spin-channel
                        # and emit as-is (spin labeling handled by total DOS context)
                        series.append(
                            Series1D(
                                x=np.array(energies, copy=True),
                                y=np.array(pdos_y, copy=True),
                                x_label="Energy",
                                y_label="DOS",
                                x_unit="eV",
                                y_unit="states/eV",
                                name=f"{atom_lbl} {orb_lbl}",
                            )
                        )
                    else:
                        series.append(
                            Series1D(
                                x=np.array(energies, copy=True),
                                y=np.array(pdos_y, copy=True),
                                x_label="Energy",
                                y_label="DOS",
                                x_unit="eV",
                                y_unit="states/eV",
                                name=f"{atom_lbl} {orb_lbl}",
                            )
                        )

        arrays: Dict[str, Any] = {
            "energies": np.array(self.energies, copy=True),
            "total_dos": np.array(self.total_dos, copy=True),
        }

        if self.spin_polarized:
            arrays["total_dos_up"] = np.array(self.total_dos[0], copy=True)
            arrays["total_dos_down"] = np.array(self.total_dos[1], copy=True)

        if self.integrated_dos is not None:
            arrays["integrated_dos"] = np.array(self.integrated_dos, copy=True)

        if self.pdos is not None:
            arrays["pdos"] = np.array(self.pdos, copy=True)
            if self.atom_labels is not None:
                arrays["atom_labels"] = list(self.atom_labels)
            if self.orbital_labels is not None:
                arrays["orbital_labels"] = list(self.orbital_labels)

        render_meta = RenderMeta(
            axis_labels={"x": "Energy", "y": "DOS"},
            units={"x": "eV", "y": "states/eV"},
            series_labels=[s.name for s in series],
            reference_energy=self.fermi_energy,
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
            arrays=arrays,
        )

