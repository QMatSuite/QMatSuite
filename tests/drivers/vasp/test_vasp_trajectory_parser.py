"""Tests for VASP trajectory parser/provider."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import numpy as np
import pytest

from qmatsuite.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.core.analysis.trajectory.model import Trajectory
from qmatsuite.drivers.vasp.parsers.trajectory import VASPTrajectoryProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_vasp_trajectory"


def _make_evidence(raw_dir: Path, gen_steps: list[str] | None = None) -> EvidenceBundle:
    return EvidenceBundle(
        primary_raw_dir=raw_dir,
        calc_dir=raw_dir.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=gen_steps or ["relax"],
        engine_name="vasp",
        evidence_steps=[],
    )


def test_can_parse_true_when_vasprun_exists() -> None:
    provider = VASPTrajectoryProvider()
    assert provider.can_parse(FIXTURE_DIR)


def test_can_parse_false_when_nothing(tmp_path: Path) -> None:
    provider = VASPTrajectoryProvider()
    assert not provider.can_parse(tmp_path)


def test_parse_vasprun_frame_count() -> None:
    """Verify 3 frames parsed from vasprun.xml fixture."""
    provider = VASPTrajectoryProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert isinstance(result, Trajectory)
    assert result.n_frames == 3


def test_parse_vasprun_positions_shape() -> None:
    """Verify positions shape is (2, 3) for 2-atom Si cell."""
    provider = VASPTrajectoryProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    for frame in result.frames:
        assert frame.positions.shape == (2, 3)


def test_parse_vasprun_energy_per_frame() -> None:
    """Verify energy extracted for each frame."""
    provider = VASPTrajectoryProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    for frame in result.frames:
        assert frame.energy is not None
    assert result.frames[0].energy == pytest.approx(-10.58622100, abs=1e-4)


def test_parse_vasprun_forces_present() -> None:
    """Verify forces present in each frame."""
    provider = VASPTrajectoryProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    for frame in result.frames:
        assert frame.forces is not None
        assert frame.forces.shape == (2, 3)


def test_parse_trajectory_type_relax() -> None:
    """Verify trajectory type defaults to relax."""
    provider = VASPTrajectoryProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR, gen_steps=["relax"]))
    assert result.trajectory_type == "relax"


def test_parse_trajectory_type_md() -> None:
    """Verify trajectory type set to md from gen_steps."""
    provider = VASPTrajectoryProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR, gen_steps=["md"]))
    assert result.trajectory_type == "md"


def test_to_primitives_valid() -> None:
    """Verify to_primitives() produces valid CanonicalPrimitiveBundle."""
    provider = VASPTrajectoryProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    canonical = result.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "trajectory"
    assert canonical.provenance_meta.engine_name == "vasp"
    assert canonical.geometry_frames is not None
    assert len(canonical.geometry_frames.frames) == 3


def test_sha_deterministic() -> None:
    """Verify canonical SHA is deterministic."""
    provider = VASPTrajectoryProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    sha1 = compute_canonical_sha(result.to_primitives())
    sha2 = compute_canonical_sha(result.to_primitives())
    assert len(sha1) == 64
    assert sha1 == sha2


def test_parse_uses_iterparse() -> None:
    """Verify parse_vasprun_trajectory uses iterparse, not ET.parse()."""
    import inspect
    from qmatsuite.drivers.vasp.parsers.trajectory import parse_vasprun_trajectory
    source = inspect.getsource(parse_vasprun_trajectory)
    assert "iterparse" in source, "parse_vasprun_trajectory must use iterparse"
    assert "ET.parse(" not in source, "parse_vasprun_trajectory must not use ET.parse()"


def test_size_warn_threshold_exists() -> None:
    """Verify _SIZE_WARN_THRESHOLD constant is defined and reasonable."""
    from qmatsuite.drivers.vasp.parsers.trajectory import _SIZE_WARN_THRESHOLD
    assert _SIZE_WARN_THRESHOLD == 100 * 1024 * 1024  # 100 MB


def test_fallback_xdatcar_oszicar() -> None:
    """Verify fallback path using XDATCAR+OSZICAR (no vasprun.xml)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Copy XDATCAR and OSZICAR but NOT vasprun.xml
        shutil.copy(FIXTURE_DIR / "XDATCAR", tmp_path / "XDATCAR")
        shutil.copy(FIXTURE_DIR / "OSZICAR", tmp_path / "OSZICAR")

        provider = VASPTrajectoryProvider()
        assert provider.can_parse(tmp_path)
        result = provider.parse(_make_evidence(tmp_path))
        assert isinstance(result, Trajectory)
        assert result.n_frames == 3
        # Energies from OSZICAR
        assert result.frames[0].energy is not None
        assert result.frames[0].energy == pytest.approx(-10.58622100, abs=1e-3)
        # Forces not available in XDATCAR
        assert result.frames[0].forces is None
