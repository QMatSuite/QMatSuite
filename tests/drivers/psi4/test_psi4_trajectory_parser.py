"""Tests for Psi4 trajectory parser."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.core.analysis.trajectory.model import Trajectory
from quantumvitas.drivers.psi4.parsers.trajectory import Psi4TrajectoryParser

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_psi4_trajectory"


def _make_evidence(raw_dir: Path) -> EvidenceBundle:
    return EvidenceBundle(
        primary_raw_dir=raw_dir,
        calc_dir=raw_dir.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["relax"],
        engine_name="psi4",
        evidence_steps=[],
    )


def test_can_parse_true() -> None:
    assert Psi4TrajectoryParser().can_parse(FIXTURE_DIR)


def test_can_parse_false(tmp_path: Path) -> None:
    assert not Psi4TrajectoryParser().can_parse(tmp_path)


def test_parse_returns_trajectory() -> None:
    result = Psi4TrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    assert isinstance(result, Trajectory)


def test_parse_frame_count() -> None:
    """3 optimization steps in Psi4 B3LYP/cc-pVDZ H2O."""
    result = Psi4TrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    assert result.n_frames == 3
    assert len(result.frames) == 3


def test_parse_positions_shape() -> None:
    """H2O: 3 atoms, 3 coordinates."""
    result = Psi4TrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    for frame in result.frames:
        assert frame.positions.shape == (3, 3)


def test_parse_species() -> None:
    result = Psi4TrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    for frame in result.frames:
        assert frame.species == ["O", "H", "H"]


def test_parse_energy_physics() -> None:
    """Energies should be in eV (converted from Ha), H2O B3LYP/cc-pVDZ ~ -2080 eV."""
    result = Psi4TrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    for frame in result.frames:
        assert frame.energy is not None
    assert result.frames[0].energy < 0
    assert result.frames[0].energy == pytest.approx(-2080.0, abs=2.0)
    # Energy should decrease during optimization
    assert result.frames[-1].energy <= result.frames[0].energy


def test_parse_molecular_no_cell() -> None:
    result = Psi4TrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    for frame in result.frames:
        assert frame.cell is None
        assert frame.pbc == (False, False, False)


def test_to_primitives() -> None:
    result = Psi4TrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    canonical = result.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "trajectory"


def test_sha_deterministic() -> None:
    result = Psi4TrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    sha1 = compute_canonical_sha(result.to_primitives())
    sha2 = compute_canonical_sha(result.to_primitives())
    assert len(sha1) == 64
    assert sha1 == sha2
