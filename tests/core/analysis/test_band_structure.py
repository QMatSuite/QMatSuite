"""Tests for BandStructure analysis object."""

import json

import numpy as np

from qmatsuite.core.analysis.band_structure import BandStructure, HighSymPoint
from qmatsuite.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from qmatsuite.core.analysis.bundles import CanonicalPrimitiveBundle


def _make_meta() -> AnalysisObjectMeta:
    return AnalysisObjectMeta.create(
        object_type="bands",
        source_files=[
            SourceFileStat(path="raw/si.bands.dat.gnu", size_bytes=123, mtime=1.0),
            SourceFileStat(path="raw/si.bands.pp.out", size_bytes=456, mtime=2.0),
        ],
        run_ulid="01RUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP1"],
        gen_steps=["bandspw"],
        engine_name="qe",
        parser_name="qe_bands",
        parser_version="1.0",
    )


def _make_band_structure() -> BandStructure:
    return BandStructure(
        meta=_make_meta(),
        k_distances=np.array([0.0, 0.5, 1.0]),
        eigenvalues=np.array(
            [
                [-5.0, 1.0],
                [-4.0, 2.0],
                [-3.0, 3.0],
            ]
        ),
        high_symmetry_points=[
            HighSymPoint(k_distance=0.0, label="G"),
            HighSymPoint(k_distance=1.0, label="X"),
        ],
        fermi_energy=0.8,
    )


def test_band_structure_construction() -> None:
    band_structure = _make_band_structure()

    assert band_structure.n_kpoints == 3
    assert band_structure.n_bands == 2
    assert band_structure.fermi_energy == 0.8


def test_to_primitives_returns_canonical_bundle() -> None:
    band_structure = _make_band_structure()
    bundle = band_structure.to_primitives()

    assert isinstance(bundle, CanonicalPrimitiveBundle)
    assert bundle.bundle_kind == "canonical"
    assert bundle.object_type == "bands"
    assert len(bundle.series) == 2


def test_to_primitives_is_deterministic() -> None:
    band_structure = _make_band_structure()

    first = json.dumps(band_structure.to_primitives().to_dict(), sort_keys=True)
    second = json.dumps(band_structure.to_primitives().to_dict(), sort_keys=True)
    assert first == second


def test_reference_energy_set_from_fermi() -> None:
    band_structure = _make_band_structure()
    bundle = band_structure.to_primitives()

    assert bundle.render_meta.reference_energy == 0.8


def test_markers_match_high_symmetry_points() -> None:
    band_structure = _make_band_structure()
    bundle = band_structure.to_primitives()

    markers = bundle.render_meta.markers
    assert len(markers) == 2
    assert markers[0].position == 0.0
    assert markers[0].label == "G"
    assert markers[1].position == 1.0
    assert markers[1].label == "X"


def test_serialized_bundle_excludes_created_at() -> None:
    band_structure = _make_band_structure()
    serialized = json.dumps(band_structure.to_primitives().to_dict(), sort_keys=True)

    assert "created_at" not in serialized


def test_provenance_meta_populated_from_analysis_meta() -> None:
    band_structure = _make_band_structure()
    provenance_meta = band_structure.to_primitives().provenance_meta

    assert provenance_meta.object_type == "bands"
    assert provenance_meta.run_ulid == "01RUN"
    assert provenance_meta.calc_ulid == "01CALC"
    assert provenance_meta.step_ulids == ["01STEP1"]
    assert provenance_meta.gen_steps == ["bandspw"]
    assert provenance_meta.engine_name == "qe"
    assert provenance_meta.parser_name == "qe_bands"
    assert provenance_meta.parser_version == "1.0"
    assert len(provenance_meta.source_files) == 2


def test_render_meta_has_no_provenance_fields() -> None:
    band_structure = _make_band_structure()
    render_payload = band_structure.to_primitives().render_meta.to_dict()

    assert "run_ulid" not in render_payload
    assert "calc_ulid" not in render_payload
    assert "step_ulids" not in render_payload
    assert "engine_name" not in render_payload
    assert "parser_name" not in render_payload
    assert "source_files" not in render_payload


def test_spin_polarized_to_primitives_contains_spin_series() -> None:
    """3D eigenvalues serialize as explicit spin-resolved series."""
    spin_bands = BandStructure(
        meta=_make_meta(),
        k_distances=np.array([0.0, 0.5, 1.0]),
        eigenvalues=np.array(
            [
                [[-5.0, 0.2], [-4.5, 0.5], [-4.0, 0.8]],  # spin 0
                [[-4.8, 0.3], [-4.2, 0.6], [-3.9, 1.0]],  # spin 1
            ]
        ),
        high_symmetry_points=[HighSymPoint(k_distance=0.0, label="G")],
        fermi_energy=0.2,
    )

    assert spin_bands.spin_polarized is True

    bundle = spin_bands.to_primitives()
    names = [series.name for series in bundle.series if series.name is not None]
    assert any(name.startswith("spin_0_band_") for name in names)
    assert any(name.startswith("spin_1_band_") for name in names)


def test_spin_polarized_to_primitives_is_deterministic() -> None:
    """3D spin-resolved canonical output remains deterministic."""
    spin_bands = BandStructure(
        meta=_make_meta(),
        k_distances=np.array([0.0, 0.4, 0.8]),
        eigenvalues=np.array(
            [
                [[-2.0, 0.1], [-1.5, 0.3], [-1.1, 0.6]],
                [[-1.9, 0.2], [-1.4, 0.4], [-1.0, 0.7]],
            ]
        ),
        high_symmetry_points=[HighSymPoint(k_distance=0.0, label="G")],
        fermi_energy=0.1,
    )

    first = json.dumps(spin_bands.to_primitives().to_dict(), sort_keys=True)
    second = json.dumps(spin_bands.to_primitives().to_dict(), sort_keys=True)
    assert first == second
