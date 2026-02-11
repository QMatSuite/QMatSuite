"""Tests for ABINIT trajectory parser (_HIST.nc)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.core.analysis.trajectory.model import Trajectory
from quantumvitas.drivers.abinit.parsers.trajectory import ABINITTrajectoryParser

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_abinit_trajectory"


def _make_evidence(raw_dir: Path, gen_steps: list[str] | None = None) -> EvidenceBundle:
    return EvidenceBundle(
        primary_raw_dir=raw_dir,
        calc_dir=raw_dir.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=gen_steps or ["relax"],
        engine_name="abinit",
        evidence_steps=[],
    )


def test_can_parse_true() -> None:
    assert ABINITTrajectoryParser().can_parse(FIXTURE_DIR)


def test_can_parse_false(tmp_path: Path) -> None:
    assert not ABINITTrajectoryParser().can_parse(tmp_path)


def test_parse_returns_trajectory() -> None:
    result = ABINITTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    assert isinstance(result, Trajectory)


def test_parse_frame_count() -> None:
    result = ABINITTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    assert result.n_frames >= 2  # At least 2 relax steps


def test_parse_positions_shape() -> None:
    result = ABINITTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    for frame in result.frames:
        assert frame.positions.shape[1] == 3
        assert frame.positions.shape[0] == 2  # 2-atom Si


def test_parse_energy_physics() -> None:
    result = ABINITTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    for frame in result.frames:
        assert frame.energy is not None
    # ABINIT energy in eV (converted from Ha), negative for Si
    assert result.frames[0].energy < 0


def test_parse_cell_present() -> None:
    result = ABINITTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    for frame in result.frames:
        assert frame.cell is not None
        assert frame.cell.shape == (3, 3)


def test_to_primitives() -> None:
    result = ABINITTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    canonical = result.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "trajectory"


def test_sha_deterministic() -> None:
    result = ABINITTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    sha1 = compute_canonical_sha(result.to_primitives())
    sha2 = compute_canonical_sha(result.to_primitives())
    assert len(sha1) == 64
    assert sha1 == sha2
