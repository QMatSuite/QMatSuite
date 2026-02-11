"""Engine-agnostic Field3D analysis object.

Wraps volumetric data (charge density, ELF, potential, orbitals, etc.)
with metadata for canonical bundle production.

Promoted from drivers/vasp/parsers/field3d.py to shared core location
since all engines that produce 3D volumetric data need this class.
"""
from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

from quantumvitas.core.analysis.base import AnalysisObjectMeta
from quantumvitas.core.analysis.bundles import (
    CanonicalPrimitiveBundle,
    ProvenanceMeta,
    RenderMeta,
)


class Field3D:
    """Engine-agnostic field3d analysis object.

    Wraps volumetric data with metadata for canonical bundle production.
    """

    meta: AnalysisObjectMeta

    def __init__(
        self,
        meta: AnalysisObjectMeta,
        grid_shape: tuple,
        grid_data: np.ndarray,
        lattice: np.ndarray,
        field_kind: str,
        discovered_files: List[str],
    ) -> None:
        self.meta = meta
        self.grid_shape = grid_shape
        self.grid_data = grid_data
        self.lattice = lattice
        self.field_kind = field_kind
        self.discovered_files = discovered_files

    def to_primitives(self) -> CanonicalPrimitiveBundle:
        """Convert to canonical primitive bundle."""
        ngx, ngy, ngz = self.grid_shape

        # Compute grid vectors (voxel step vectors)
        grid_vectors = np.array([
            self.lattice[0] / ngx,
            self.lattice[1] / ngy,
            self.lattice[2] / ngz,
        ], dtype=float)

        # Compute preview via simple downsampling
        factor = 4
        preview_shape = (
            max(1, ngx // factor),
            max(1, ngy // factor),
            max(1, ngz // factor),
        )
        grid_3d = self.grid_data.reshape((ngx, ngy, ngz), order="F")
        preview_3d = grid_3d[::factor, ::factor, ::factor]
        preview_data = preview_3d.flatten(order="F")

        # Statistics
        value_min = float(np.min(self.grid_data))
        value_max = float(np.max(self.grid_data))
        value_mean = float(np.mean(self.grid_data))

        volume_metadata: Dict[str, Any] = {
            "grid_shape": list(self.grid_shape),
            "coordinate_system": "real-space",
            "origin_cart": [0.0, 0.0, 0.0],
            "grid_vectors_cart": grid_vectors.tolist(),
            "data_order": "fortran_i_fastest",
            "data_order_format_default": "VASP_CHGCAR",
            "length_units": "A",
            "value_min": value_min,
            "value_max": value_max,
            "value_mean": value_mean,
            "preview_downsample_factor": factor,
            "preview_grid_shape": list(preview_shape),
            "grid_data_nbytes": int(self.grid_data.nbytes),
            "grid_data_dtype": str(self.grid_data.dtype),
            "grid_data_available": True,
        }

        render_meta = RenderMeta(
            axis_labels={"x": "x", "y": "y", "z": "z"},
            units={"x": "A", "y": "A", "z": "A"},
            extra={
                "volume_metadata": volume_metadata,
                "field_kind": self.field_kind,
                "discovered_files": self.discovered_files,
                "n_grid_points": int(np.prod(self.grid_shape)),
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

        # Primitive-by-reference: full grid_data is NOT embedded in the bundle
        # (a 200^3 CHGCAR = 8M floats = ~100MB JSON). The grid lives on the
        # Field3D object; the bundle carries only a preview + metadata.
        arrays: Dict[str, Any] = {
            "preview_data": preview_data.tolist(),
            "lattice": self.lattice.tolist(),
        }

        return CanonicalPrimitiveBundle(
            object_type=self.meta.object_type,
            render_meta=render_meta,
            provenance_meta=provenance_meta,
            series=[],
            arrays=arrays,
        )
