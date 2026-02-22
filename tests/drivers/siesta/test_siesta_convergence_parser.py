"""Tests for Siesta convergence parser/provider."""
from __future__ import annotations

from pathlib import Path

import pytest

from qmatsuite.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from qmatsuite.core.analysis.convergence import Convergence
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.drivers.siesta.parsers.convergence import SiestaConvergenceProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_siesta_trajectory"


def _make_evidence(raw_dir: Path) -> EvidenceBundle:
    return EvidenceBundle(
        primary_raw_dir=raw_dir,
        calc_dir=raw_dir.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["relax"],
        engine_name="siesta",
        evidence_steps=[],
    )


def test_can_parse_true_when_output_exists() -> None:
    provider = SiestaConvergenceProvider()
    assert provider.can_parse(FIXTURE_DIR)


def test_can_parse_false_when_no_output(tmp_path: Path) -> None:
    provider = SiestaConvergenceProvider()
    assert not provider.can_parse(tmp_path)


def test_parse_returns_convergence() -> None:
    provider = SiestaConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert isinstance(result, Convergence)
    assert result.meta.object_type == "convergence"
    assert result.meta.engine_name == "siesta"


def test_parse_scf_count() -> None:
    """Verify correct number of SCF steps parsed."""
    provider = SiestaConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert len(result.scf_step) > 0
    # 35 total scf: lines across 9 ionic steps
    assert len(result.scf_energy) == 35
    assert len(result.scf_de) == 35


def test_parse_ionic_count() -> None:
    """Verify correct number of ionic steps parsed (move 0 through move 8)."""
    provider = SiestaConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert len(result.ionic_step) == 9
    assert len(result.ionic_energy) == 9
    assert result.n_ionic_steps == 9


def test_parse_algorithm_detected() -> None:
    """Verify algorithm detection from CG opt. move lines."""
    provider = SiestaConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert result.algorithm == "CG"


def test_parse_converged_flag() -> None:
    """Verify converged flag based on SCF cycle convergence markers."""
    provider = SiestaConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert result.converged is True


def test_to_primitives_valid() -> None:
    """Verify to_primitives() produces valid CanonicalPrimitiveBundle."""
    provider = SiestaConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    canonical = result.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "convergence"
    assert canonical.provenance_meta.engine_name == "siesta"
    assert "scf_energy" in canonical.arrays
    assert "ionic_energy" in canonical.arrays
    assert canonical.render_meta.extra["converged"] is True
    assert canonical.render_meta.extra["algorithm"] == "CG"


def test_sha_deterministic() -> None:
    """Verify canonical SHA is deterministic."""
    provider = SiestaConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    sha1 = compute_canonical_sha(result.to_primitives())
    sha2 = compute_canonical_sha(result.to_primitives())
    assert len(sha1) == 64
    assert sha1 == sha2
