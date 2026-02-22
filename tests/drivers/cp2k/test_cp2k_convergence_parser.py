"""Tests for CP2K convergence parser/provider."""
from __future__ import annotations

from pathlib import Path

import pytest

from qmatsuite.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from qmatsuite.core.analysis.convergence import Convergence
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.drivers.cp2k.parsers.convergence import CP2KConvergenceProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_cp2k_trajectory"


def _make_evidence(raw_dir: Path) -> EvidenceBundle:
    return EvidenceBundle(
        primary_raw_dir=raw_dir,
        calc_dir=raw_dir.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["relax"],
        engine_name="cp2k",
        evidence_steps=[],
    )


def test_can_parse_true_when_output_exists() -> None:
    provider = CP2KConvergenceProvider()
    assert provider.can_parse(FIXTURE_DIR)


def test_can_parse_false_when_no_output(tmp_path: Path) -> None:
    provider = CP2KConvergenceProvider()
    assert not provider.can_parse(tmp_path)


def test_parse_returns_convergence() -> None:
    provider = CP2KConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert isinstance(result, Convergence)
    assert result.meta.object_type == "convergence"
    assert result.meta.engine_name == "cp2k"


def test_parse_scf_count() -> None:
    """Verify correct number of SCF steps parsed."""
    provider = CP2KConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert len(result.scf_step) > 0
    # 46 total SCF lines across 6 ENERGY| blocks
    assert len(result.scf_energy) == 46
    assert len(result.scf_de) == 46


def test_parse_ionic_count() -> None:
    """Verify correct number of ionic steps parsed (6 ENERGY| lines)."""
    provider = CP2KConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert len(result.ionic_step) == 6
    assert len(result.ionic_energy) == 6
    assert result.n_ionic_steps == 6


def test_parse_algorithm_detected() -> None:
    """Verify algorithm detection from SCF table rows."""
    provider = CP2KConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert result.algorithm == "P_Mix"


def test_parse_converged_flag() -> None:
    """Verify converged=False due to MAXIMUM NUMBER OF OPTIMIZATION STEPS REACHED."""
    provider = CP2KConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    # No GEOMETRY OPTIMIZATION COMPLETED marker in fixture
    assert result.converged is False


def test_to_primitives_valid() -> None:
    """Verify to_primitives() produces valid CanonicalPrimitiveBundle."""
    provider = CP2KConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    canonical = result.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "convergence"
    assert canonical.provenance_meta.engine_name == "cp2k"
    assert "scf_energy" in canonical.arrays
    assert "ionic_energy" in canonical.arrays
    assert canonical.render_meta.extra["converged"] is False
    assert canonical.render_meta.extra["algorithm"] == "P_Mix"


def test_sha_deterministic() -> None:
    """Verify canonical SHA is deterministic."""
    provider = CP2KConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    sha1 = compute_canonical_sha(result.to_primitives())
    sha2 = compute_canonical_sha(result.to_primitives())
    assert len(sha1) == 64
    assert sha1 == sha2
