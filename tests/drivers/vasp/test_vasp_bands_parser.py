"""Tests for VASP bands parser/provider using real VASP fixture output."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.band_structure import BandStructure
from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.drivers.vasp.parsers.bands import (
    VASPBandsProvider,
    _compute_k_distances,
    _read_kpoints_labels,
    _reciprocal_lattice,
    parse_eigenval,
    parse_procar,
)


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_vasp_bands"
PROCAR_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_vasp_bands_procar"


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
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["bandspw"],
        engine_name="vasp",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    assert isinstance(band_structure, BandStructure)
    assert band_structure.meta.object_type == "bands"
    assert band_structure.meta.engine_name == "vasp"
    assert len(band_structure.k_distances) == 200
    assert band_structure.eigenvalues.shape == (200, 16)


def test_k_distance_monotonic() -> None:
    provider = VASPBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="vasp",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    diffs = np.diff(band_structure.k_distances)
    assert np.all(diffs >= -1e-10)


def test_kpoints_labels_from_real_kpoints() -> None:
    labels = _read_kpoints_labels(FIXTURE_DIR)
    assert [point.label for point in labels] == ["G", "X", "W", "K", "G", "L"]
    distances = [point.k_distance for point in labels]
    assert distances == sorted(distances)


def test_to_primitives_valid() -> None:
    provider = VASPBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="vasp",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
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
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="vasp",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    assert band_structure.fermi_energy == pytest.approx(-2.36540459, rel=1e-9, abs=1e-9)


# ---- Reciprocal Cartesian k-distance regression tests ----


def test_reciprocal_lattice_cubic() -> None:
    """For a cubic cell, B = 2*pi/a * I."""
    a = 5.4309
    lattice = np.diag([a, a, a])
    recip = _reciprocal_lattice(lattice)
    expected = np.diag([2.0 * np.pi / a] * 3)
    np.testing.assert_allclose(recip, expected, atol=1e-12)


def test_k_distances_cubic_vs_fractional() -> None:
    """For cubic cells, Cartesian k-dist = (2*pi/a) * fractional dist."""
    a = 5.4309
    lattice = np.array([[a, 0, 0], [0, a, 0], [0, 0, a]])
    kpoints = np.array([
        [0.0, 0.0, 0.0],
        [0.5, 0.0, 0.0],
        [0.5, 0.5, 0.0],
    ])
    dist_cart = _compute_k_distances(kpoints, lattice)
    dist_frac = _compute_k_distances(kpoints, None)
    scale = 2.0 * np.pi / a
    np.testing.assert_allclose(dist_cart, dist_frac * scale, atol=1e-12)


def test_k_distances_noncubic_differs_from_fractional() -> None:
    """For a non-cubic FCC conventional cell, reciprocal Cartesian distances
    must differ from fractional Euclidean distances.

    FCC conventional lattice (a=3.5 Angstrom Al-like):
        a1 = [a, 0, 0]
        a2 = [0, a, 0]
        a3 = [0, 0, a]
    This is actually cubic (trivially), so use a hexagonal cell instead.

    Hexagonal BN-like lattice (a=2.504, c=6.661):
        a1 = [a, 0, 0]
        a2 = [-a/2, a*sqrt(3)/2, 0]
        a3 = [0, 0, c]
    """
    a, c = 2.504, 6.661
    lattice = np.array([
        [a, 0.0, 0.0],
        [-a / 2, a * np.sqrt(3) / 2, 0.0],
        [0.0, 0.0, c],
    ])

    # K-path: Gamma -> M -> K -> Gamma
    kpoints = np.array([
        [0.0, 0.0, 0.0],       # Gamma
        [0.5, 0.0, 0.0],       # M
        [1.0 / 3, 1.0 / 3, 0.0],  # K
        [0.0, 0.0, 0.0],       # Gamma
    ])

    dist_cart = _compute_k_distances(kpoints, lattice)
    dist_frac = _compute_k_distances(kpoints, None)

    # Both must be monotonically non-decreasing
    assert np.all(np.diff(dist_cart) >= -1e-10)
    assert np.all(np.diff(dist_frac) >= -1e-10)

    # They must NOT be proportional (ratio varies per segment)
    # because the reciprocal metric is anisotropic for hex
    ratios = []
    for i in range(1, len(dist_cart)):
        if dist_frac[i] > 1e-12:
            ratios.append(dist_cart[i] / dist_frac[i])
    assert len(ratios) >= 2
    # If they were simply proportional, all ratios would be equal
    assert max(ratios) - min(ratios) > 0.01, (
        f"Ratios should vary for non-cubic cell but are nearly constant: {ratios}"
    )

    # Verify analytically: Gamma->M distance in reciprocal Cartesian
    # B = 2*pi * inv(A)^T
    recip = _reciprocal_lattice(lattice)
    # Gamma = [0,0,0], M = [0.5, 0, 0] in fractional
    delta_frac = np.array([0.5, 0.0, 0.0])
    delta_cart = recip.T @ delta_frac
    expected_GM = np.linalg.norm(delta_cart)
    assert dist_cart[1] == pytest.approx(expected_GM, rel=1e-10)


def test_k_distances_with_poscar_in_fixture() -> None:
    """The Si fixture has POSCAR; k-distances should use reciprocal Cartesian."""
    provider = VASPBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="vasp",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)

    # Si cubic a=5.4309: reciprocal Cartesian scale = 2*pi/a
    a = 5.4309
    scale = 2.0 * np.pi / a

    # First segment: Gamma (0,0,0) -> X (0.5,0,0.5)
    # Fractional distance = sqrt(0.25+0.25) = sqrt(0.5)
    # Cartesian distance = scale * sqrt(0.5)
    expected_GX = scale * np.sqrt(0.5)
    # k_distances[39] is the last point of the first 40-point segment (G->X)
    assert band_structure.k_distances[39] == pytest.approx(expected_GX, rel=1e-4)

    # Monotonicity still holds
    diffs = np.diff(band_structure.k_distances)
    assert np.all(diffs >= -1e-10)


# ---- PROCAR fatband tests (real VASP output) ----

_procar_available = (PROCAR_FIXTURE_DIR / "PROCAR").exists()


@pytest.mark.skipif(not _procar_available, reason="PROCAR fixture not found")
def test_parse_procar_header() -> None:
    """Verify PROCAR header dimensions: 15 kpts, 8 bands, 2 atoms."""
    result = parse_procar(PROCAR_FIXTURE_DIR / "PROCAR")
    assert result["n_kpoints"] == 15
    assert result["n_bands"] == 8
    assert result["n_atoms"] == 2


@pytest.mark.skipif(not _procar_available, reason="PROCAR fixture not found")
def test_parse_procar_projections_shape() -> None:
    """Verify projections array shape: (15, 8, 2, 9)."""
    result = parse_procar(PROCAR_FIXTURE_DIR / "PROCAR")
    assert result["projections"].shape == (15, 8, 2, 9)


@pytest.mark.skipif(not _procar_available, reason="PROCAR fixture not found")
def test_parse_procar_orbital_labels() -> None:
    """Verify orbital labels from PROCAR header."""
    result = parse_procar(PROCAR_FIXTURE_DIR / "PROCAR")
    assert result["orbital_labels"] == ["s", "py", "pz", "px", "dxy", "dyz", "dz2", "dxz", "x2-y2"]


@pytest.mark.skipif(not _procar_available, reason="PROCAR fixture not found")
def test_parse_procar_weights_physical() -> None:
    """Verify projection weights are non-negative and reasonable."""
    result = parse_procar(PROCAR_FIXTURE_DIR / "PROCAR")
    proj = result["projections"]
    # All weights non-negative
    assert np.all(proj >= 0.0)
    # Per-band total across atoms should be < 1.0 per orbital
    # (some charge is in the interstitial)
    per_band_total = proj.sum(axis=2)  # sum over atoms -> (k, b, orb)
    assert np.all(per_band_total <= 1.5)  # generous bound


@pytest.mark.skipif(not _procar_available, reason="PROCAR fixture not found")
def test_procar_integrated_in_parse() -> None:
    """Verify provider.parse() picks up PROCAR projections."""
    provider = VASPBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=PROCAR_FIXTURE_DIR,
        calc_dir=PROCAR_FIXTURE_DIR.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["bandspw"],
        engine_name="vasp",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    assert band_structure.projections is not None
    assert band_structure.projections.shape == (15, 8, 2, 9)
    assert band_structure.projection_labels is not None
    assert band_structure.projection_labels["atoms"] == ["Si_1", "Si_2"]


@pytest.mark.skipif(not _procar_available, reason="PROCAR fixture not found")
def test_procar_in_primitives() -> None:
    """Verify canonical bundle arrays contain projections."""
    provider = VASPBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=PROCAR_FIXTURE_DIR,
        calc_dir=PROCAR_FIXTURE_DIR.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["bandspw"],
        engine_name="vasp",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    canonical = band_structure.to_primitives()
    assert "projections" in canonical.arrays
    assert "projection_labels" in canonical.arrays
    assert canonical.arrays["projection_labels"]["atoms"] == ["Si_1", "Si_2"]


@pytest.mark.skipif(not _procar_available, reason="PROCAR fixture not found")
def test_procar_display_hints() -> None:
    """Verify render_meta.extra has fatband display hints."""
    provider = VASPBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=PROCAR_FIXTURE_DIR,
        calc_dir=PROCAR_FIXTURE_DIR.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["bandspw"],
        engine_name="vasp",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    canonical = band_structure.to_primitives()
    extra = canonical.render_meta.extra
    assert extra["has_projections"] is True
    assert extra["projection_shape"] == [15, 8, 2, 9]
    assert extra["fatband_display_hint"] == "width"
    assert extra["fatband_width_eV"] == 0.5


@pytest.mark.skipif(not _procar_available, reason="PROCAR fixture not found")
def test_procar_sha_deterministic() -> None:
    """Verify SHA is stable across two calls with PROCAR data."""
    provider = VASPBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=PROCAR_FIXTURE_DIR,
        calc_dir=PROCAR_FIXTURE_DIR.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["bandspw"],
        engine_name="vasp",
        evidence_steps=[],
    )
    bs1 = provider.parse(evidence)
    bs2 = provider.parse(evidence)
    sha1 = compute_canonical_sha(bs1.to_primitives())
    sha2 = compute_canonical_sha(bs2.to_primitives())
    assert len(sha1) == 64
    assert sha1 == sha2


def test_no_procar_yields_none_projections() -> None:
    """Existing fixture (no PROCAR) → projections is None."""
    provider = VASPBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["bandspw"],
        engine_name="vasp",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    assert band_structure.projections is None
    assert band_structure.projection_labels is None
