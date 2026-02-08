"""Tests for analysis primitive bundles."""

import json

import numpy as np

from quantumvitas.core.analysis.base import SourceFileStat
from quantumvitas.core.analysis.bundles import (
    CanonicalPrimitiveBundle,
    DerivedPrimitiveBundle,
    ProvenanceMeta,
    RenderMeta,
    TransformRecord,
)
from quantumvitas.core.analysis.primitives import GeometryFrame, GeometryFrames, Marker, Series1D


def _make_render_meta() -> RenderMeta:
    return RenderMeta(
        axis_labels={"x": "Energy", "y": "DOS"},
        units={"x": "eV", "y": "states/eV"},
        series_labels=["total"],
        reference_energy=5.2,
        markers=[Marker(position=0.0, label="EF", axis="x")],
    )


def _make_provenance_meta() -> ProvenanceMeta:
    return ProvenanceMeta(
        schema_version="1.0",
        object_type="dos",
        run_ulid="01RUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP1"],
        gen_steps=["dos"],
        engine_name="qe",
        source_files=[SourceFileStat(path="raw/si.dos.dat", size_bytes=123, mtime=1.0)],
        parser_name="qe_dos",
        parser_version="1.0",
        warnings=[],
    )


def _make_series() -> Series1D:
    return Series1D(
        x=np.array([0.0, 1.0, 2.0]),
        y=np.array([10.0, 11.0, 12.0]),
        x_label="Energy",
        y_label="DOS",
        x_unit="eV",
        y_unit="states/eV",
        name="total",
    )


def _make_geometry() -> GeometryFrames:
    frame = GeometryFrame(
        positions=np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]]),
        species=["Si", "Si"],
        cell=np.eye(3),
        pbc=(True, True, True),
    )
    return GeometryFrames(
        frames=[frame],
        iteration=np.array([0]),
    )


def test_canonical_bundle_construction() -> None:
    bundle = CanonicalPrimitiveBundle(
        object_type="dos",
        render_meta=_make_render_meta(),
        provenance_meta=_make_provenance_meta(),
        series=[_make_series()],
        geometry_frames=_make_geometry(),
        arrays={"values": np.array([1.0, 2.0, 3.0])},
    )

    assert bundle.bundle_kind == "canonical"
    assert bundle.object_type == "dos"
    assert len(bundle.series) == 1


def test_canonical_bundle_roundtrip_to_dict_from_dict() -> None:
    original = CanonicalPrimitiveBundle(
        object_type="dos",
        render_meta=_make_render_meta(),
        provenance_meta=_make_provenance_meta(),
        series=[_make_series()],
        geometry_frames=_make_geometry(),
        arrays={"values": np.array([1.0, 2.0, 3.0])},
    )

    payload = original.to_dict()
    restored = CanonicalPrimitiveBundle.from_dict(payload)

    assert json.dumps(payload, sort_keys=True) == json.dumps(
        restored.to_dict(),
        sort_keys=True,
    )


def test_derived_bundle_roundtrip_to_dict_from_dict() -> None:
    original = DerivedPrimitiveBundle(
        object_type="dos",
        render_meta=_make_render_meta(),
        provenance_meta=_make_provenance_meta(),
        series=[_make_series()],
        arrays={"values": np.array([1.0, 2.0, 3.0])},
        transform_chain=[TransformRecord(transform_name="fermi_shift", parameters={})],
    )

    payload = original.to_dict()
    restored = DerivedPrimitiveBundle.from_dict(payload)

    assert json.dumps(payload, sort_keys=True) == json.dumps(
        restored.to_dict(),
        sort_keys=True,
    )


def test_canonical_serialization_excludes_created_at() -> None:
    bundle = CanonicalPrimitiveBundle(
        object_type="dos",
        render_meta=_make_render_meta(),
        provenance_meta=_make_provenance_meta(),
    )
    serialized = json.dumps(bundle.to_dict(), sort_keys=True)
    assert "created_at" not in serialized


def test_bundle_kind_literals() -> None:
    canonical = CanonicalPrimitiveBundle(
        object_type="dos",
        render_meta=_make_render_meta(),
        provenance_meta=_make_provenance_meta(),
    )
    derived = DerivedPrimitiveBundle(
        object_type="dos",
        render_meta=_make_render_meta(),
        provenance_meta=_make_provenance_meta(),
    )

    assert canonical.bundle_kind == "canonical"
    assert derived.bundle_kind == "derived"

