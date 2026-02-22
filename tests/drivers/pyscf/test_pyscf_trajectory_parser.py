"""Tests for PySCF trajectory parser."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from qmatsuite.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.core.analysis.trajectory.model import Trajectory
from qmatsuite.drivers.pyscf.parsers.trajectory import PySCFTrajectoryParser

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_pyscf_trajectory"


def _make_evidence(raw_dir: Path) -> EvidenceBundle:
    return EvidenceBundle(
        primary_raw_dir=raw_dir,
        calc_dir=raw_dir.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["relax"],
        engine_name="pyscf",
        evidence_steps=[],
    )


def test_can_parse_true() -> None:
    assert PySCFTrajectoryParser().can_parse(FIXTURE_DIR)


def test_can_parse_false(tmp_path: Path) -> None:
    assert not PySCFTrajectoryParser().can_parse(tmp_path)


def test_parse_returns_trajectory() -> None:
    result = PySCFTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    assert isinstance(result, Trajectory)


def test_parse_frame_count() -> None:
    """4 optimization cycles in PySCF B3LYP/STO-3G H2O."""
    result = PySCFTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    assert result.n_frames == 4
    assert len(result.frames) == 4


def test_parse_positions_shape() -> None:
    """H2O: 3 atoms, 3 coordinates."""
    result = PySCFTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    for frame in result.frames:
        assert frame.positions.shape == (3, 3)


def test_parse_species() -> None:
    result = PySCFTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    for frame in result.frames:
        assert frame.species == ["O", "H", "H"]


def test_parse_energy_physics() -> None:
    """Energies should be in eV (converted from Ha), H2O B3LYP/STO-3G ~ -2050 eV."""
    result = PySCFTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    for frame in result.frames:
        assert frame.energy is not None
    assert result.frames[0].energy < 0
    assert result.frames[0].energy == pytest.approx(-2050.0, abs=2.0)
    # Energy should decrease during optimization
    assert result.frames[-1].energy <= result.frames[0].energy


def test_parse_molecular_no_cell() -> None:
    result = PySCFTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    for frame in result.frames:
        assert frame.cell is None
        assert frame.pbc == (False, False, False)


def test_to_primitives() -> None:
    result = PySCFTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    canonical = result.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "trajectory"


def test_sha_deterministic() -> None:
    result = PySCFTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    sha1 = compute_canonical_sha(result.to_primitives())
    sha2 = compute_canonical_sha(result.to_primitives())
    assert len(sha1) == 64
    assert sha1 == sha2
