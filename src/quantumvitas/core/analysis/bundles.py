"""
Primitive bundle data models for analysis visualization.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from quantumvitas.core.analysis.base import SourceFileStat
from quantumvitas.core.analysis.primitives import (
    GeometryFrame,
    GeometryFrames,
    Marker,
    Series1D,
)


def _serialize_array_like(value: Any) -> Any:
    """Convert numpy-backed content to JSON-serializable content."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {k: _serialize_array_like(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_array_like(v) for v in value]
    if isinstance(value, tuple):
        return [_serialize_array_like(v) for v in value]
    return value


def _series_from_dict(data: Dict[str, Any]) -> Series1D:
    return Series1D(
        x=np.array(data["x"]),
        y=np.array(data["y"]),
        x_label=data["x_label"],
        y_label=data["y_label"],
        x_unit=data["x_unit"],
        y_unit=data["y_unit"],
        name=data.get("name"),
    )


def _geometry_frames_to_dict(geometry_frames: GeometryFrames) -> Dict[str, Any]:
    return {
        "frames": [
            {
                "positions": frame.positions.tolist(),
                "species": frame.species,
                "cell": frame.cell.tolist() if frame.cell is not None else None,
                "pbc": list(frame.pbc),
                "forces": frame.forces.tolist() if frame.forces is not None else None,
                "velocities": frame.velocities.tolist() if frame.velocities is not None else None,
            }
            for frame in geometry_frames.frames
        ],
        "time": geometry_frames.time.tolist() if geometry_frames.time is not None else None,
        "iteration": (
            geometry_frames.iteration.tolist()
            if geometry_frames.iteration is not None
            else None
        ),
        "image_indices": (
            geometry_frames.image_indices.tolist()
            if geometry_frames.image_indices is not None
            else None
        ),
    }


def _geometry_frames_from_dict(data: Dict[str, Any]) -> GeometryFrames:
    frames = [
        GeometryFrame(
            positions=np.array(frame_data["positions"]),
            species=frame_data["species"],
            cell=np.array(frame_data["cell"]) if frame_data.get("cell") is not None else None,
            pbc=tuple(frame_data["pbc"]),
            forces=(
                np.array(frame_data["forces"])
                if frame_data.get("forces") is not None
                else None
            ),
            velocities=(
                np.array(frame_data["velocities"])
                if frame_data.get("velocities") is not None
                else None
            ),
        )
        for frame_data in data.get("frames", [])
    ]
    return GeometryFrames(
        frames=frames,
        time=np.array(data["time"]) if data.get("time") is not None else None,
        iteration=(
            np.array(data["iteration"])
            if data.get("iteration") is not None
            else None
        ),
        image_indices=(
            np.array(data["image_indices"])
            if data.get("image_indices") is not None
            else None
        ),
    )


@dataclass
class RenderMeta:
    axis_labels: Dict[str, str]
    units: Dict[str, str]
    series_labels: Optional[List[str]] = None
    reference_energy: Optional[float] = None
    reference_position: Optional[float] = None
    markers: List[Marker] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "axis_labels": dict(self.axis_labels),
            "units": dict(self.units),
            "series_labels": self.series_labels,
            "reference_energy": self.reference_energy,
            "reference_position": self.reference_position,
            "markers": [
                {"position": marker.position, "label": marker.label, "axis": marker.axis}
                for marker in self.markers
            ],
            "extra": _serialize_array_like(self.extra),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RenderMeta":
        return cls(
            axis_labels=data.get("axis_labels", {}),
            units=data.get("units", {}),
            series_labels=data.get("series_labels"),
            reference_energy=data.get("reference_energy"),
            reference_position=data.get("reference_position"),
            markers=[Marker(**marker_data) for marker_data in data.get("markers", [])],
            extra=data.get("extra", {}),
        )


@dataclass
class ProvenanceMeta:
    schema_version: str
    object_type: str
    run_ulid: Optional[str] = None
    calc_ulid: Optional[str] = None
    step_ulids: List[str] = field(default_factory=list)
    gen_steps: List[str] = field(default_factory=list)
    engine_name: str = ""
    source_files: List[SourceFileStat] = field(default_factory=list)
    parser_name: str = ""
    parser_version: str = ""
    warnings: List[str] = field(default_factory=list)
    manifest_snapshot: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "object_type": self.object_type,
            "run_ulid": self.run_ulid,
            "calc_ulid": self.calc_ulid,
            "step_ulids": list(self.step_ulids),
            "gen_steps": list(self.gen_steps),
            "engine_name": self.engine_name,
            "source_files": [source_file.to_dict() for source_file in self.source_files],
            "parser_name": self.parser_name,
            "parser_version": self.parser_version,
            "warnings": list(self.warnings),
            "manifest_snapshot": self.manifest_snapshot,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProvenanceMeta":
        return cls(
            schema_version=data["schema_version"],
            object_type=data["object_type"],
            run_ulid=data.get("run_ulid"),
            calc_ulid=data.get("calc_ulid"),
            step_ulids=data.get("step_ulids", []),
            gen_steps=data.get("gen_steps", []),
            engine_name=data.get("engine_name", ""),
            source_files=[
                SourceFileStat.from_dict(source_file_data)
                for source_file_data in data.get("source_files", [])
            ],
            parser_name=data.get("parser_name", ""),
            parser_version=data.get("parser_version", ""),
            warnings=data.get("warnings", []),
            manifest_snapshot=data.get("manifest_snapshot"),
        )


@dataclass
class TransformRecord:
    transform_name: str
    parameters: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transform_name": self.transform_name,
            "parameters": _serialize_array_like(self.parameters),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransformRecord":
        return cls(
            transform_name=data["transform_name"],
            parameters=data.get("parameters", {}),
        )


@dataclass
class CanonicalPrimitiveBundle:
    bundle_kind: str = "canonical"
    object_type: str = ""
    render_meta: RenderMeta = field(
        default_factory=lambda: RenderMeta(axis_labels={}, units={})
    )
    provenance_meta: ProvenanceMeta = field(
        default_factory=lambda: ProvenanceMeta(schema_version="1.0", object_type="")
    )
    series: List[Series1D] = field(default_factory=list)
    geometry_frames: Optional[GeometryFrames] = None
    arrays: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.bundle_kind != "canonical":
            raise ValueError("CanonicalPrimitiveBundle.bundle_kind must be 'canonical'")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bundle_kind": "canonical",
            "object_type": self.object_type,
            "render_meta": self.render_meta.to_dict(),
            "provenance_meta": self.provenance_meta.to_dict(),
            "series": [series.to_dict() for series in self.series],
            "geometry_frames": (
                _geometry_frames_to_dict(self.geometry_frames)
                if self.geometry_frames is not None
                else None
            ),
            "arrays": _serialize_array_like(self.arrays),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalPrimitiveBundle":
        return cls(
            bundle_kind="canonical",
            object_type=data.get("object_type", ""),
            render_meta=RenderMeta.from_dict(data.get("render_meta", {})),
            provenance_meta=ProvenanceMeta.from_dict(data.get("provenance_meta", {})),
            series=[_series_from_dict(series_data) for series_data in data.get("series", [])],
            geometry_frames=(
                _geometry_frames_from_dict(data["geometry_frames"])
                if data.get("geometry_frames") is not None
                else None
            ),
            arrays=data.get("arrays", {}),
        )


@dataclass
class DerivedPrimitiveBundle:
    bundle_kind: str = "derived"
    object_type: str = ""
    render_meta: RenderMeta = field(
        default_factory=lambda: RenderMeta(axis_labels={}, units={})
    )
    provenance_meta: ProvenanceMeta = field(
        default_factory=lambda: ProvenanceMeta(schema_version="1.0", object_type="")
    )
    series: List[Series1D] = field(default_factory=list)
    geometry_frames: Optional[GeometryFrames] = None
    arrays: Dict[str, Any] = field(default_factory=dict)
    transform_chain: List[TransformRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.bundle_kind != "derived":
            raise ValueError("DerivedPrimitiveBundle.bundle_kind must be 'derived'")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bundle_kind": "derived",
            "object_type": self.object_type,
            "render_meta": self.render_meta.to_dict(),
            "provenance_meta": self.provenance_meta.to_dict(),
            "series": [series.to_dict() for series in self.series],
            "geometry_frames": (
                _geometry_frames_to_dict(self.geometry_frames)
                if self.geometry_frames is not None
                else None
            ),
            "arrays": _serialize_array_like(self.arrays),
            "transform_chain": [
                transform_record.to_dict() for transform_record in self.transform_chain
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DerivedPrimitiveBundle":
        return cls(
            bundle_kind="derived",
            object_type=data.get("object_type", ""),
            render_meta=RenderMeta.from_dict(data.get("render_meta", {})),
            provenance_meta=ProvenanceMeta.from_dict(data.get("provenance_meta", {})),
            series=[_series_from_dict(series_data) for series_data in data.get("series", [])],
            geometry_frames=(
                _geometry_frames_from_dict(data["geometry_frames"])
                if data.get("geometry_frames") is not None
                else None
            ),
            arrays=data.get("arrays", {}),
            transform_chain=[
                TransformRecord.from_dict(transform_record_data)
                for transform_record_data in data.get("transform_chain", [])
            ],
        )

