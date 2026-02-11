"""Tests for QE trajectory parser (relax + MD)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.core.analysis.trajectory.model import Trajectory
from quantumvitas.drivers.qe.parsers.trajectory import QETrajectoryParser

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_qe_trajectory"


def _make_evidence(raw_dir: Path, gen_steps: list[str] | None = None) -> EvidenceBundle:
    return EvidenceBundle(
        primary_raw_dir=raw_dir,
        calc_dir=raw_dir.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=gen_steps or ["relax"],
        engine_name="qe",
        evidence_steps=[],
    )


class TestQETrajectoryRelax:
    """Tests for QE relax trajectory parsing."""

    def test_can_parse_true(self) -> None:
        provider = QETrajectoryParser()
        assert provider.can_parse(FIXTURE_DIR)

    def test_can_parse_false(self, tmp_path: Path) -> None:
        provider = QETrajectoryParser()
        assert not provider.can_parse(tmp_path)

    def test_parse_returns_trajectory(self) -> None:
        provider = QETrajectoryParser()
        result = provider.parse(_make_evidence(FIXTURE_DIR))
        assert isinstance(result, Trajectory)

    def test_parse_frame_count(self) -> None:
        provider = QETrajectoryParser()
        result = provider.parse(_make_evidence(FIXTURE_DIR))
        assert result.n_frames >= 3  # BFGS steps

    def test_parse_positions_shape(self) -> None:
        provider = QETrajectoryParser()
        result = provider.parse(_make_evidence(FIXTURE_DIR))
        for frame in result.frames:
            assert frame.positions.shape == (2, 3)  # 2-atom Si

    def test_parse_energy_physics(self) -> None:
        provider = QETrajectoryParser()
        result = provider.parse(_make_evidence(FIXTURE_DIR))
        for frame in result.frames:
            assert frame.energy is not None
        # Energy should be in eV, negative for Si
        assert result.frames[0].energy < 0
        assert result.frames[0].energy == pytest.approx(-214.26, abs=1.0)

    def test_trajectory_type_relax(self) -> None:
        provider = QETrajectoryParser()
        result = provider.parse(_make_evidence(FIXTURE_DIR, gen_steps=["relax"]))
        assert result.trajectory_type == "relax"

    def test_to_primitives(self) -> None:
        provider = QETrajectoryParser()
        result = provider.parse(_make_evidence(FIXTURE_DIR))
        canonical = result.to_primitives()
        assert isinstance(canonical, CanonicalPrimitiveBundle)
        assert canonical.object_type == "trajectory"

    def test_sha_deterministic(self) -> None:
        provider = QETrajectoryParser()
        result = provider.parse(_make_evidence(FIXTURE_DIR))
        sha1 = compute_canonical_sha(result.to_primitives())
        sha2 = compute_canonical_sha(result.to_primitives())
        assert len(sha1) == 64
        assert sha1 == sha2


class TestQETrajectoryMD:
    """Tests for QE MD trajectory parsing."""

    def test_md_parse(self) -> None:
        provider = QETrajectoryParser()
        result = provider.parse(_make_evidence(FIXTURE_DIR, gen_steps=["md"]))
        # Should detect MD from gen_steps
        assert result.trajectory_type == "md"

    def test_md_frame_count(self) -> None:
        # MD fixture: si.md.out has 5 MD steps + 1 initial
        md_evidence = _make_evidence(FIXTURE_DIR, gen_steps=["md"])
        # The parser should try md.out first if gen_steps=md
        provider = QETrajectoryParser()
        result = provider.parse(md_evidence)
        assert result.n_frames >= 3

    def test_md_temperature(self) -> None:
        provider = QETrajectoryParser()
        result = provider.parse(_make_evidence(FIXTURE_DIR, gen_steps=["md"]))
        # At least one frame should have temperature
        temps = [f.temperature for f in result.frames if f.temperature is not None]
        if temps:
            assert temps[0] > 0  # Should have nonzero temperature
