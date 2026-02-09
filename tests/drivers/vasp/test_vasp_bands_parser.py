"""Tests for VASP bands parser/provider using real VASP fixture output."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.band_structure import BandStructure
from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from quantumvitas.drivers.vasp.parsers.bands import (
    VASPBandsProvider,
    _read_kpoints_labels,
    parse_eigenval,
)


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_vasp_bands"


def test_parse_eigenval_header() -> None:
    parsed = parse_eigenval(FIXTURE_DIR / "EIGENVAL")
    assert parsed["n_electrons"] == 8
    assert parsed["n_kpoints"] == 200
    assert parsed["n_bands"] == 16
    assert "Si diamond" in parsed["system_name"]


def test_parse_eigenval_shapes() -> None:
    parsed = parse_eigenval(FIXTURE_DIR / "EIGENVAL")
    assert parsed["kpoints"].shape == (200, 3)
    assert parsed["eigenvalues"].shape == (200, 16)
    assert parsed["occupations"].shape == (200, 16)
    assert parsed["weights"].shape == (200,)


def test_parse_eigenval_physics() -> None:
    parsed = parse_eigenval(FIXTURE_DIR / "EIGENVAL")
    assert np.allclose(parsed["kpoints"][0], np.array([0.0, 0.0, 0.0]))
    assert parsed["eigenvalues"][0, 0] == pytest.approx(-10.068717, rel=1e-6, abs=1e-6)
    assert np.allclose(parsed["occupations"][0, :3], np.array([1.0, 1.0, 1.0]), atol=1e-8)
    assert np.allclose(parsed["occupations"][0, 3:], np.zeros(13), atol=1e-8)
    assert float(np.min(parsed["eigenvalues"])) > -15.0
    assert float(np.max(parsed["eigenvalues"])) < 10.0


def test_can_parse_true_when_eigenval_exists() -> None:
    provider = VASPBandsProvider()
    assert provider.can_parse(FIXTURE_DIR)


def test_can_parse_false_when_no_eigenval(tmp_path: Path) -> None:
    provider = VASPBandsProvider()
    assert not provider.can_parse(tmp_path)


def test_parse_returns_band_structure() -> None:
    provider = VASPBandsProvider()
    band_structure = provider.parse(
        raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid="01TESTRUN",
        step_ulids=["01STEP"],
        gen_steps=["bandspw"],
        calc_ulid="01CALC",
    )
    assert isinstance(band_structure, BandStructure)
    assert band_structure.meta.object_type == "bands"
    assert band_structure.meta.engine_name == "vasp"
    assert len(band_structure.k_distances) == 200
    assert band_structure.eigenvalues.shape == (200, 16)


def test_k_distance_monotonic() -> None:
    provider = VASPBandsProvider()
    band_structure = provider.parse(raw_dir=FIXTURE_DIR, calc_dir=FIXTURE_DIR.parent)
    diffs = np.diff(band_structure.k_distances)
    assert np.all(diffs >= -1e-10)


def test_kpoints_labels_from_real_kpoints() -> None:
    labels = _read_kpoints_labels(FIXTURE_DIR)
    assert [point.label for point in labels] == ["G", "X", "W", "K", "G", "L"]
    distances = [point.k_distance for point in labels]
    assert distances == sorted(distances)


def test_to_primitives_valid() -> None:
    provider = VASPBandsProvider()
    band_structure = provider.parse(raw_dir=FIXTURE_DIR, calc_dir=FIXTURE_DIR.parent)
    canonical = band_structure.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "bands"
    assert canonical.render_meta.axis_labels["x"] == "k-path"
    assert canonical.provenance_meta.engine_name == "vasp"
    assert "k_distances" in canonical.arrays
    assert "eigenvalues" in canonical.arrays

    sha_one = compute_canonical_sha(canonical)
    sha_two = compute_canonical_sha(band_structure.to_primitives())
    assert len(sha_one) == 64
    assert sha_one == sha_two


def test_fermi_energy_extraction() -> None:
    provider = VASPBandsProvider()
    band_structure = provider.parse(raw_dir=FIXTURE_DIR, calc_dir=FIXTURE_DIR.parent)
    assert band_structure.fermi_energy == pytest.approx(-2.36540459, rel=1e-9, abs=1e-9)
