"""Tests for ABINIT bands parser/provider using real ABINIT fixture output."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.band_structure import BandStructure
from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.drivers.abinit.parsers.bands import ABINITBandsProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_abinit_bands"


def test_can_parse_true_when_eig_exists() -> None:
    provider = ABINITBandsProvider()
    assert provider.can_parse(FIXTURE_DIR)


def test_can_parse_false_when_no_eig(tmp_path: Path) -> None:
    provider = ABINITBandsProvider()
    assert not provider.can_parse(tmp_path)


def test_parse_returns_band_structure() -> None:
    provider = ABINITBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["bandspw"],
        engine_name="abinit",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    assert isinstance(band_structure, BandStructure)
    assert band_structure.meta.object_type == "bands"
    assert band_structure.meta.engine_name == "abinit"


def test_eigenvalues_shape() -> None:
    provider = ABINITBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="abinit",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    assert band_structure.eigenvalues.shape == (41, 8)


def test_eigenvalues_in_eV() -> None:
    provider = ABINITBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="abinit",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    assert band_structure.eigenvalues.max() > 5.0


def test_k_distances_monotonic() -> None:
    provider = ABINITBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="abinit",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    diffs = np.diff(band_structure.k_distances)
    assert np.all(diffs >= -1e-10)


def test_k_distances_length() -> None:
    provider = ABINITBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="abinit",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    assert len(band_structure.k_distances) == 41


def test_fermi_energy_from_abo() -> None:
    provider = ABINITBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="abinit",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    assert band_structure.fermi_energy is not None
    assert band_structure.fermi_energy == pytest.approx(5.812, abs=0.1)


def test_to_primitives_valid() -> None:
    provider = ABINITBandsProvider()
    evidence = EvidenceBundle(
        primary_raw_dir=FIXTURE_DIR,
        calc_dir=FIXTURE_DIR.parent,
        run_ulid=None,
        calc_ulid=None,
        step_ulids=[],
        gen_steps=[],
        engine_name="abinit",
        evidence_steps=[],
    )
    band_structure = provider.parse(evidence)
    canonical = band_structure.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "bands"
    assert canonical.render_meta.axis_labels["x"] == "k-path"
    assert canonical.provenance_meta.engine_name == "abinit"
    assert "k_distances" in canonical.arrays
    assert "eigenvalues" in canonical.arrays

    sha_one = compute_canonical_sha(canonical)
    sha_two = compute_canonical_sha(band_structure.to_primitives())
    assert len(sha_one) == 64
    assert sha_one == sha_two

