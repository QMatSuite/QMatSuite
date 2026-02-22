"""Tests for ORCA trajectory parser."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from qmatsuite.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.core.analysis.trajectory.model import Trajectory
from qmatsuite.drivers.orca.parsers.trajectory import ORCATrajectoryParser

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_orca_trajectory"


def _make_evidence(raw_dir: Path, gen_steps: list[str] | None = None) -> EvidenceBundle:
    return EvidenceBundle(
        primary_raw_dir=raw_dir,
        calc_dir=raw_dir.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=gen_steps or ["relax"],
        engine_name="orca",
        evidence_steps=[],
    )


def test_can_parse_true() -> None:
    assert ORCATrajectoryParser().can_parse(FIXTURE_DIR)


def test_can_parse_false(tmp_path: Path) -> None:
    assert not ORCATrajectoryParser().can_parse(tmp_path)


def test_parse_returns_trajectory() -> None:
    result = ORCATrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    assert isinstance(result, Trajectory)


def test_parse_frame_count() -> None:
    result = ORCATrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    assert result.n_frames == 5  # 5 opt steps in water_opt_trj.xyz


def test_parse_positions_shape() -> None:
    result = ORCATrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    for frame in result.frames:
        assert frame.positions.shape == (3, 3)  # H2O: 3 atoms


def test_parse_energy_physics() -> None:
    result = ORCATrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    for frame in result.frames:
        assert frame.energy is not None
    # ORCA energy in eV (from Ha), H2O ~ -2077 eV
    assert result.frames[0].energy < 0
    assert result.frames[0].energy == pytest.approx(-2077.0, abs=2.0)


def test_parse_molecular_no_cell() -> None:
    result = ORCATrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    for frame in result.frames:
        assert frame.cell is None
        assert frame.pbc == (False, False, False)


def test_to_primitives() -> None:
    result = ORCATrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    canonical = result.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "trajectory"


def test_sha_deterministic() -> None:
    result = ORCATrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    sha1 = compute_canonical_sha(result.to_primitives())
    sha2 = compute_canonical_sha(result.to_primitives())
    assert len(sha1) == 64
    assert sha1 == sha2
