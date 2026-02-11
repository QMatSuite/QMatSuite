"""Tests for QE NEB trajectory parser."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.core.analysis.trajectory import Trajectory
from quantumvitas.drivers.qe.parsers.neb_trajectory import QENEBTrajectoryProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_qe_neb_trajectory"


def _make_evidence(raw_dir: Path) -> EvidenceBundle:
    return EvidenceBundle(
        primary_raw_dir=raw_dir,
        calc_dir=raw_dir.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["neb"],
        engine_name="qe",
        evidence_steps=[],
    )


def test_can_parse_true_when_axsf_exists() -> None:
    provider = QENEBTrajectoryProvider()
    assert provider.can_parse(FIXTURE_DIR)


def test_can_parse_false_when_no_axsf(tmp_path: Path) -> None:
    provider = QENEBTrajectoryProvider()
    assert not provider.can_parse(tmp_path)


def test_parse_returns_trajectory() -> None:
    provider = QENEBTrajectoryProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert isinstance(result, Trajectory)
    assert result.meta.object_type == "neb_trajectory"
    assert result.meta.engine_name == "qe"


def test_n_images_12() -> None:
    """Verify 12 NEB images parsed from AXSF."""
    provider = QENEBTrajectoryProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert result.n_images == 12
    assert len(result.frames) == 12


def test_trajectory_type_neb() -> None:
    provider = QENEBTrajectoryProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert result.trajectory_type == "neb"


def test_image_index_populated() -> None:
    """Verify each frame has image_index."""
    provider = QENEBTrajectoryProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    for i, frame in enumerate(result.frames):
        assert frame.image_index == i + 1


def test_energy_barrier_shape() -> None:
    """Energy goes up then down for NH3 inversion NEB."""
    provider = QENEBTrajectoryProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    energies = [f.energy for f in result.frames]
    assert all(e is not None for e in energies)
    # First and last should be equal (symmetric path)
    assert energies[0] == pytest.approx(energies[-1], abs=1e-6)
    # Middle images should have higher energy (barrier)
    mid = len(energies) // 2
    assert energies[mid] > energies[0]


def test_4_atoms_per_image() -> None:
    """NH3 has 4 atoms (N + 3H)."""
    provider = QENEBTrajectoryProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    for frame in result.frames:
        assert frame.n_atoms == 4
        assert "N" in frame.species
        assert frame.species.count("H") == 3


def test_to_primitives_valid() -> None:
    """Verify to_primitives() produces valid CanonicalPrimitiveBundle."""
    provider = QENEBTrajectoryProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    canonical = result.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "neb_trajectory"
    assert canonical.geometry_frames is not None
    assert canonical.geometry_frames.image_indices is not None
    assert len(canonical.geometry_frames.frames) == 12


def test_sha_deterministic() -> None:
    """Verify canonical SHA is deterministic."""
    provider = QENEBTrajectoryProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    sha1 = compute_canonical_sha(result.to_primitives())
    sha2 = compute_canonical_sha(result.to_primitives())
    assert len(sha1) == 64
    assert sha1 == sha2
