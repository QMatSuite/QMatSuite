"""Tests for ABINIT convergence parser/provider."""
from __future__ import annotations

from pathlib import Path

import pytest

from qmatsuite.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from qmatsuite.core.analysis.convergence import Convergence
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.drivers.abinit.parsers.convergence import ABINITConvergenceProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_abinit_trajectory"


def _make_evidence(raw_dir: Path) -> EvidenceBundle:
    return EvidenceBundle(
        primary_raw_dir=raw_dir,
        calc_dir=raw_dir.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["relax"],
        engine_name="abinit",
        evidence_steps=[],
    )


def test_can_parse_true_when_output_exists() -> None:
    provider = ABINITConvergenceProvider()
    assert provider.can_parse(FIXTURE_DIR)


def test_can_parse_false_when_no_output(tmp_path: Path) -> None:
    provider = ABINITConvergenceProvider()
    assert not provider.can_parse(tmp_path)


def test_parse_returns_convergence() -> None:
    provider = ABINITConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert isinstance(result, Convergence)
    assert result.meta.object_type == "convergence"
    assert result.meta.engine_name == "abinit"


def test_parse_scf_count() -> None:
    """Verify correct number of SCF steps parsed."""
    provider = ABINITConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert len(result.scf_step) > 0
    # 3 ETOT lines per ionic step x 4 ionic steps = 12 total SCF steps
    assert len(result.scf_energy) == 12
    assert len(result.scf_de) == 12


def test_parse_ionic_count() -> None:
    """Verify correct number of ionic steps parsed."""
    provider = ABINITConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert len(result.ionic_step) == 4
    assert len(result.ionic_energy) == 4
    assert result.n_ionic_steps == 4


def test_parse_algorithm_detected() -> None:
    """Verify algorithm detection from output."""
    provider = ABINITConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert result.algorithm == "Broyden"


def test_parse_converged_flag() -> None:
    """Verify converged flag based on ionic convergence marker."""
    provider = ABINITConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    # "At Broyd/MD step   4, gradients are converged"
    assert result.converged is True


def test_to_primitives_valid() -> None:
    """Verify to_primitives() produces valid CanonicalPrimitiveBundle."""
    provider = ABINITConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    canonical = result.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "convergence"
    assert canonical.provenance_meta.engine_name == "abinit"
    assert "scf_energy" in canonical.arrays
    assert "ionic_energy" in canonical.arrays
    assert canonical.render_meta.extra["converged"] is True
    assert canonical.render_meta.extra["algorithm"] == "Broyden"


def test_sha_deterministic() -> None:
    """Verify canonical SHA is deterministic."""
    provider = ABINITConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    sha1 = compute_canonical_sha(result.to_primitives())
    sha2 = compute_canonical_sha(result.to_primitives())
    assert len(sha1) == 64
    assert sha1 == sha2
