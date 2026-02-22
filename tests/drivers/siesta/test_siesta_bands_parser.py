"""Tests for Siesta bands parser/provider using real Siesta fixture output."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from qmatsuite.core.analysis.band_structure import BandStructure
from qmatsuite.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.drivers.siesta.parsers.bands import SiestaBandsProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_siesta_bands"


def test_can_parse_true_when_eig_exists() -> None:
    provider = SiestaBandsProvider()
    assert provider.can_parse(FIXTURE_DIR)


def test_can_parse_false_when_no_eig(tmp_path: Path) -> None:
    provider = SiestaBandsProvider()
    assert not provider.can_parse(tmp_path)


def test_parse_returns_band_structure() -> None:
    provider = SiestaBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["bandspw"],
        engine_name="siesta",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    assert isinstance(band_structure, BandStructure)
    assert band_structure.meta.object_type == "bands"
    assert band_structure.meta.engine_name == "siesta"


def test_eigenvalues_shape() -> None:
    provider = SiestaBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="siesta",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    assert band_structure.eigenvalues.shape == (32, 26)


def test_k_distances_monotonic() -> None:
    provider = SiestaBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="siesta",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    diffs = np.diff(band_structure.k_distances)
    assert np.all(diffs >= -1e-10)


def test_fermi_energy_present() -> None:
    provider = SiestaBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="siesta",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    assert band_structure.fermi_energy == pytest.approx(-4.487, abs=0.01)


def test_high_symmetry_points() -> None:
    provider = SiestaBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="siesta",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    assert len(band_structure.high_symmetry_points) == 5


def test_to_primitives_valid() -> None:
    provider = SiestaBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="siesta",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    canonical = band_structure.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "bands"
    assert canonical.render_meta.axis_labels["x"] == "k-path"
    assert canonical.provenance_meta.engine_name == "siesta"
    assert "k_distances" in canonical.arrays
    assert "eigenvalues" in canonical.arrays

    sha_one = compute_canonical_sha(canonical)
    sha_two = compute_canonical_sha(band_structure.to_primitives())
    assert len(sha_one) == 64
    assert sha_one == sha_two

