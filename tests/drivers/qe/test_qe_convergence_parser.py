"""Tests for QE convergence parser/provider."""
from __future__ import annotations

from pathlib import Path

import pytest

from qmatsuite.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from qmatsuite.core.analysis.convergence import Convergence
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.drivers.qe.parsers.convergence import QEConvergenceProvider


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_qe_trajectory"


def _make_evidence(raw_dir: Path) -> EvidenceBundle:
    return EvidenceBundle(
        primary_raw_dir=raw_dir,
        calc_dir=raw_dir.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["relax"],
        engine_name="qe",
        evidence_steps=[],
    )


def test_can_parse_true_when_output_exists() -> None:
    provider = QEConvergenceProvider()
    assert provider.can_parse(FIXTURE_DIR)


def test_can_parse_false_when_no_output(tmp_path: Path) -> None:
    provider = QEConvergenceProvider()
    assert not provider.can_parse(tmp_path)


def test_parse_returns_convergence() -> None:
    provider = QEConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert isinstance(result, Convergence)
    assert result.meta.object_type == "convergence"
    assert result.meta.engine_name == "qe"


def test_parse_scf_count() -> None:
    """Verify correct number of SCF steps parsed."""
    provider = QEConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert len(result.scf_step) > 0
    # Fixture dir has both si.md.out and si.relax.out; gen_step=relax should select si.relax.out.
    assert len(result.scf_energy) == 10
    assert len(result.scf_de) == 10


def test_parse_ionic_count() -> None:
    """Verify correct number of ionic steps parsed."""
    provider = QEConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    # si.relax.out contains 4 ionic-step summaries.
    assert len(result.ionic_step) == 4
    assert len(result.ionic_energy) == 4
    assert result.n_ionic_steps == 4


def test_parse_algorithm_detected() -> None:
    """Verify algorithm detection from output."""
    provider = QEConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert result.algorithm == "Davidson"


def test_parse_converged_flag() -> None:
    """Verify converged flag based on convergence marker."""
    provider = QEConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    assert result.converged is True


def test_to_primitives_valid() -> None:
    """Verify to_primitives() produces valid CanonicalPrimitiveBundle."""
    provider = QEConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    canonical = result.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "convergence"
    assert canonical.provenance_meta.engine_name == "qe"
    assert "scf_energy" in canonical.arrays
    assert "ionic_energy" in canonical.arrays
    assert canonical.render_meta.extra["converged"] is True
    assert canonical.render_meta.extra["algorithm"] == "Davidson"


def test_sha_deterministic() -> None:
    """Verify canonical SHA is deterministic."""
    provider = QEConvergenceProvider()
    result = provider.parse(_make_evidence(FIXTURE_DIR))
    sha1 = compute_canonical_sha(result.to_primitives())
    sha2 = compute_canonical_sha(result.to_primitives())
    assert len(sha1) == 64
    assert sha1 == sha2


def test_parse_prefers_step_specific_output_in_shared_raw_dir(tmp_path: Path) -> None:
    """When multiple *.out files exist, parser should choose the one matching gen_step."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()

    # This file is present but unrelated for convergence parsing in scf context.
    (raw_dir / "wannierprep.out").write_text("", encoding="utf-8")

    # Minimal SCF-like output with one iteration + energy + convergence marker.
    (raw_dir / "scf.out").write_text(
        "\n".join(
            [
                " iteration #  1     ecut=    30.00 Ry     beta= 0.70",
                " total energy              =     -22.42698584 Ry",
                " convergence has been achieved in  1 iterations",
            ]
        ),
        encoding="utf-8",
    )

    evidence = EvidenceBundle(
        primary_raw_dir=raw_dir,
        calc_dir=tmp_path,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=["scf"],
        engine_name="qe",
        evidence_steps=[],
    )

    provider = QEConvergenceProvider()
    result = provider.parse(evidence)
    assert len(result.scf_energy) == 1
    assert result.meta.source_files, "Expected source file metadata to be populated"
    assert result.meta.source_files[0].path.endswith("scf.out")
