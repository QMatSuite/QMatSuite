"""Engine-agnostic convergence analysis model."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

from quantumvitas.core.analysis.base import AnalysisObjectMeta
from quantumvitas.core.analysis.bundles import (
    CanonicalPrimitiveBundle,
    ProvenanceMeta,
    RenderMeta,
)
from quantumvitas.core.analysis.primitives import Series1D


@dataclass
class Convergence:
    """Engine-agnostic convergence analysis object.

    Tracks both electronic (SCF) and ionic convergence across
    any engine (QE, VASP, ABINIT, etc.).
    """

    meta: AnalysisObjectMeta

    # Electronic convergence (flat across all ionic steps)
    scf_step: np.ndarray       # int[n_total_scf], cumulative index
    scf_energy: np.ndarray     # float[n_total_scf], eV
    scf_de: np.ndarray         # float[n_total_scf], energy change per step

    # Ionic convergence
    ionic_step: np.ndarray     # int[n_ionic]
    ionic_energy: np.ndarray   # float[n_ionic], eV

    # Optional ionic observables
    ionic_max_force: Optional[np.ndarray] = None  # float[n_ionic], eV/A

    # Metadata
    converged: bool = False
    n_ionic_steps: int = 0
    algorithm: str = ""        # "CG", "DAV", "RMM", "DF", etc.

    def to_primitives(self) -> CanonicalPrimitiveBundle:
        """Convert to canonical primitive bundle."""
        series: List[Series1D] = []

        # SCF energy series
        if len(self.scf_energy) > 0:
            series.append(
                Series1D(
                    x=np.array(self.scf_step, dtype=float, copy=True),
                    y=np.array(self.scf_energy, copy=True),
                    x_label="SCF Step",
                    y_label="Energy",
                    x_unit="",
                    y_unit="eV",
                    name="SCF Energy",
                )
            )

        # SCF dE series
        if len(self.scf_de) > 0:
            series.append(
                Series1D(
                    x=np.array(self.scf_step, dtype=float, copy=True),
                    y=np.array(self.scf_de, copy=True),
                    x_label="SCF Step",
                    y_label="dE",
                    x_unit="",
                    y_unit="eV",
                    name="SCF dE",
                )
            )

        # Ionic energy series
        if len(self.ionic_energy) > 0:
            series.append(
                Series1D(
                    x=np.array(self.ionic_step, dtype=float, copy=True),
                    y=np.array(self.ionic_energy, copy=True),
                    x_label="Ionic Step",
                    y_label="Energy",
                    x_unit="",
                    y_unit="eV",
                    name="Ionic Energy",
                )
            )

        # Ionic max force series
        if self.ionic_max_force is not None and len(self.ionic_max_force) > 0:
            series.append(
                Series1D(
                    x=np.array(self.ionic_step, dtype=float, copy=True),
                    y=np.array(self.ionic_max_force, copy=True),
                    x_label="Ionic Step",
                    y_label="Max Force",
                    x_unit="",
                    y_unit="eV/A",
                    name="Ionic Max Force",
                )
            )

        render_meta = RenderMeta(
            axis_labels={"x": "Step", "y": "Energy"},
            units={"x": "", "y": "eV"},
            series_labels=[s.name for s in series if s.name],
            extra={
                "n_ionic_steps": self.n_ionic_steps,
                "converged": self.converged,
                "algorithm": self.algorithm,
            },
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

        arrays: Dict[str, Any] = {
            "scf_step": np.array(self.scf_step, copy=True),
            "scf_energy": np.array(self.scf_energy, copy=True),
            "scf_de": np.array(self.scf_de, copy=True),
            "ionic_step": np.array(self.ionic_step, copy=True),
            "ionic_energy": np.array(self.ionic_energy, copy=True),
        }
        if self.ionic_max_force is not None:
            arrays["ionic_max_force"] = np.array(self.ionic_max_force, copy=True)

        return CanonicalPrimitiveBundle(
            object_type=self.meta.object_type,
            render_meta=render_meta,
            provenance_meta=provenance_meta,
            series=series,
            arrays=arrays,
        )
