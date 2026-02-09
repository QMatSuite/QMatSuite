"""Tests for CP2K bands parser/provider using real CP2K fixture output."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.band_structure import BandStructure
from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.drivers.cp2k.parsers.bands import CP2KBandsProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_cp2k_bands"


def test_can_parse_true_when_bs_exists() -> None:
    provider = CP2KBandsProvider()
    assert provider.can_parse(FIXTURE_DIR)


def test_can_parse_false_when_no_bs(tmp_path: Path) -> None:
    provider = CP2KBandsProvider()
    assert not provider.can_parse(tmp_path)


def test_parse_returns_band_structure() -> None:
    provider = CP2KBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["bandspw"],
        engine_name="cp2k",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    assert isinstance(band_structure, BandStructure)
    assert band_structure.meta.object_type == "bands"
    assert band_structure.meta.engine_name == "cp2k"


def test_eigenvalues_shape() -> None:
    provider = CP2KBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="cp2k",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    assert band_structure.eigenvalues.shape == (80, 4)


def test_k_distances_length() -> None:
    provider = CP2KBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="cp2k",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    assert len(band_structure.k_distances) == 80


def test_k_distances_monotonic() -> None:
    provider = CP2KBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="cp2k",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    diffs = np.diff(band_structure.k_distances)
    assert np.all(diffs >= -1e-10)


def test_high_symmetry_points() -> None:
    provider = CP2KBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="cp2k",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    assert len(band_structure.high_symmetry_points) == 6


def test_high_symmetry_labels() -> None:
    provider = CP2KBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="cp2k",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    labels = [point.label for point in band_structure.high_symmetry_points]
    assert labels == ["Γ", "X", "W", "L", "Γ", "K"]


def test_energies_in_eV_range() -> None:
    provider = CP2KBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="cp2k",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    assert band_structure.eigenvalues.min() > -10.0
    assert band_structure.eigenvalues.max() < 10.0


def test_to_primitives_valid() -> None:
    provider = CP2KBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="cp2k",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    canonical = band_structure.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "bands"
    assert canonical.render_meta.axis_labels["x"] == "k-path"
    assert canonical.provenance_meta.engine_name == "cp2k"
    assert "k_distances" in canonical.arrays
    assert "eigenvalues" in canonical.arrays

    sha_one = compute_canonical_sha(canonical)
    sha_two = compute_canonical_sha(band_structure.to_primitives())
    assert len(sha_one) == 64
    assert sha_one == sha_two

