"""Tests for primitive transforms."""

import json

import numpy as np

from qmatsuite.core.analysis.base import SourceFileStat
from qmatsuite.core.analysis.bundles import (
    CanonicalPrimitiveBundle,
    DerivedPrimitiveBundle,
    ProvenanceMeta,
    RenderMeta,
)
from qmatsuite.core.analysis.primitives import Series1D
from qmatsuite.core.analysis.transforms.energy_crop import EnergyCrop
from qmatsuite.core.analysis.transforms.fermi_shift import FermiShift


def _make_bundle() -> CanonicalPrimitiveBundle:
    return CanonicalPrimitiveBundle(
        object_type="bands",
        render_meta=RenderMeta(
            axis_labels={"x": "k-path", "y": "Energy"},
            units={"x": "1/A", "y": "eV"},
            reference_energy=5.0,
        ),
        provenance_meta=ProvenanceMeta(
            schema_version="1.0",
            object_type="bands",
            run_ulid="01RUN",
            calc_ulid="01CALC",
            step_ulids=["01STEP1"],
            gen_steps=["bandspw"],
            engine_name="qe",
            source_files=[
                SourceFileStat(
                    path="raw/si.bands.dat.gnu",
                    size_bytes=123,
                    mtime=1.0,
                )
            ],
            parser_name="qe_bands",
            parser_version="1.0",
        ),
        series=[
            Series1D(
                x=np.array([0.0, 1.0, 2.0, 3.0]),
                y=np.array([4.5, 5.0, 5.5, 6.0]),
                x_label="k-path",
                y_label="Energy",
                x_unit="1/A",
                y_unit="eV",
                name="band_0",
            )
        ],
        arrays={"eigenvalues": np.array([[4.5, 5.0, 5.5, 6.0]])},
    )


def test_fermi_shift_shifts_energy_and_sets_reference_to_zero() -> None:
    bundle = _make_bundle()
    shifted = FermiShift().apply(bundle)

    assert isinstance(shifted, DerivedPrimitiveBundle)
    np.testing.assert_allclose(shifted.series[0].y, np.array([-0.5, 0.0, 0.5, 1.0]))
    np.testing.assert_allclose(
        shifted.arrays["eigenvalues"],
        np.array([[-0.5, 0.0, 0.5, 1.0]]),
    )
    assert shifted.render_meta.reference_energy == 0.0


def test_energy_crop_trims_series_to_window() -> None:
    bundle = CanonicalPrimitiveBundle(
        object_type="dos",
        render_meta=RenderMeta(
            axis_labels={"x": "Energy", "y": "DOS"},
            units={"x": "eV", "y": "states/eV"},
            reference_energy=0.0,
        ),
        provenance_meta=ProvenanceMeta(schema_version="1.0", object_type="dos"),
        series=[
            Series1D(
                x=np.array([-2.0, -1.0, 0.0, 1.0, 2.0]),
                y=np.array([1.0, 2.0, 3.0, 4.0, 5.0]),
                x_label="Energy",
                y_label="DOS",
                x_unit="eV",
                y_unit="states/eV",
                name="total",
            )
        ],
    )

    cropped = EnergyCrop(emin=-1.0, emax=1.0).apply(bundle)
    assert isinstance(cropped, DerivedPrimitiveBundle)
    np.testing.assert_allclose(cropped.series[0].x, np.array([-1.0, 0.0, 1.0]))
    np.testing.assert_allclose(cropped.series[0].y, np.array([2.0, 3.0, 4.0]))


def test_transform_returns_derived_and_appends_transform_record() -> None:
    bundle = _make_bundle()
    shifted = FermiShift().apply(bundle)

    assert shifted.bundle_kind == "derived"
    assert len(shifted.transform_chain) == 1
    assert shifted.transform_chain[0].transform_name == "fermi_shift"


def test_transform_is_pure_and_does_not_mutate_input_bundle() -> None:
    bundle = _make_bundle()
    before = json.dumps(bundle.to_dict(), sort_keys=True)

    shifted = FermiShift().apply(bundle)
    after = json.dumps(bundle.to_dict(), sort_keys=True)

    assert before == after
    assert shifted is not bundle


def test_transform_composition_records_chain_order() -> None:
    bundle = _make_bundle()

    shifted = FermiShift().apply(bundle)
    cropped = EnergyCrop(emin=-0.25, emax=0.75).apply(shifted)

    assert cropped.bundle_kind == "derived"
    assert len(cropped.transform_chain) == 2
    assert cropped.transform_chain[0].transform_name == "fermi_shift"
    assert cropped.transform_chain[1].transform_name == "energy_crop"
    np.testing.assert_allclose(cropped.series[0].y, np.array([0.0, 0.5]))

