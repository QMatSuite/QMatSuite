"""Tests for post-run analysis orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

import qmatsuite.core.analysis.orchestrator as orchestrator_mod
from qmatsuite.core.analysis.band_structure import BandStructure, HighSymPoint
from qmatsuite.core.analysis.base import AnalysisObjectMeta
from qmatsuite.core.analysis.bundles import CanonicalPrimitiveBundle
from qmatsuite.core.analysis.capability import (
    AnalysisCapability,
    AnalysisResult,
    MissingReason,
    ResultState,
)
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.core.analysis.orchestrator import run_post_run_analysis
from qmatsuite.drivers.qe.driver import QEDriver
from qmatsuite.drivers.qe.parsers.bands import QEBandsProvider  # noqa: F401


REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass
class MockDriver:
    """Simple driver stub with declared capabilities."""

    ANALYSIS_CAPABILITIES: list[AnalysisCapability]


class SuccessfulBandsProvider:
    """Provider that always returns a small valid BandStructure."""

    def can_parse(self, raw_dir: Path) -> bool:
        return True

    def parse(self, evidence: EvidenceBundle) -> BandStructure:
        meta = AnalysisObjectMeta.create(
            object_type="bands",
            source_files=[],
            step_ulids=evidence.step_ulids,
            gen_steps=evidence.gen_steps,
            engine_name=evidence.engine_name,
            parser_name="mock_bands",
            parser_version="1.0",
        )
        return BandStructure(
            meta=meta,
            k_distances=np.array([0.0, 1.0]),
            eigenvalues=np.array([[0.0, 0.5], [1.0, 1.5]]),
            high_symmetry_points=[HighSymPoint(k_distance=0.0, label="G")],
            fermi_energy=0.25,
            spin_polarized=False,
        )


class FailingProvider:
    """Provider that fails in parse()."""

    def can_parse(self, raw_dir: Path) -> bool:
        return True

    def parse(self, evidence: EvidenceBundle) -> BandStructure:
        raise RuntimeError("synthetic parse failure")


class NeverParseProvider:
    """Provider that refuses to parse raw evidence."""

    def can_parse(self, raw_dir: Path) -> bool:
        return False


def test_orchestrator_matches_capabilities_and_skips_non_matching(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    driver = MockDriver(
        ANALYSIS_CAPABILITIES=[
            AnalysisCapability(object_type="bands", gen_step_sequence=["bandspw"], evidence_files=[]),
            AnalysisCapability(object_type="trajectory", gen_step_sequence=["relax"], evidence_files=[]),
        ]
    )

    def _get_parser(engine: str, object_type: str):
        if (engine, object_type) == ("qe", "bands"):
            return SuccessfulBandsProvider
        if (engine, object_type) == ("qe", "trajectory"):
            return SuccessfulBandsProvider
        return None

    monkeypatch.setattr(orchestrator_mod, "get_parser", _get_parser)

    ordered_gen_steps = [
        ("01STEP1", "scf", tmp_path / "scf"),
        ("01STEP2", "bandspw", tmp_path / "bandspw"),
    ]

    results = run_post_run_analysis(
        engine="qe",
        driver=driver,
        ordered_gen_steps=ordered_gen_steps,
        run_ulid="01RUN",
        calc_ulid="01CALC",
        calc_dir=tmp_path,
    )

    ok_results = [r for r in results if r.state == ResultState.OK]
    assert len(ok_results) == 1
    assert ok_results[0].object_type == "bands"
    assert isinstance(ok_results[0].canonical, CanonicalPrimitiveBundle)


def test_orchestrator_skips_capability_when_provider_cannot_parse(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    driver = MockDriver(
        ANALYSIS_CAPABILITIES=[
            AnalysisCapability(object_type="bands", gen_step_sequence=["bandspw"], evidence_files=[]),
        ]
    )

    monkeypatch.setattr(
        orchestrator_mod,
        "get_parser",
        lambda engine, object_type: NeverParseProvider if (engine, object_type) == ("qe", "bands") else None,
    )

    results = run_post_run_analysis(
        engine="qe",
        driver=driver,
        ordered_gen_steps=[("01STEP", "bandspw", tmp_path / "raw")],
        calc_dir=tmp_path,
    )

    ok_results = [r for r in results if r.state == ResultState.OK]
    assert ok_results == []
    # Should have a MISSING_EVIDENCE result
    missing = [r for r in results if r.state == ResultState.MISSING_EVIDENCE]
    assert len(missing) == 1
    assert missing[0].reason == MissingReason.NO_EVIDENCE


def test_orchestrator_continues_after_one_capability_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    driver = MockDriver(
        ANALYSIS_CAPABILITIES=[
            AnalysisCapability(object_type="dos", gen_step_sequence=["scf"], evidence_files=[]),
            AnalysisCapability(object_type="bands", gen_step_sequence=["bandspw"], evidence_files=[]),
        ]
    )

    def _get_parser(engine: str, object_type: str):
        if (engine, object_type) == ("qe", "dos"):
            return FailingProvider
        if (engine, object_type) == ("qe", "bands"):
            return SuccessfulBandsProvider
        return None

    monkeypatch.setattr(orchestrator_mod, "get_parser", _get_parser)

    ordered_gen_steps = [
        ("01STEP1", "scf", tmp_path / "scf"),
        ("01STEP2", "bandspw", tmp_path / "bands"),
    ]

    with pytest.warns(UserWarning, match="failed"):
        results = run_post_run_analysis(
            engine="qe",
            driver=driver,
            ordered_gen_steps=ordered_gen_steps,
            calc_dir=tmp_path,
        )

    ok_results = [r for r in results if r.state == ResultState.OK]
    assert len(ok_results) == 1
    assert ok_results[0].object_type == "bands"

    error_results = [r for r in results if r.state == ResultState.PARSER_ERROR]
    assert len(error_results) == 1
    assert error_results[0].object_type == "dos"
    assert "synthetic parse failure" in error_results[0].error


def test_orchestrator_integration_qe_bands_real_fixture() -> None:
    raw_dir = REPO_ROOT / "tests" / "data" / "analysis_bands"

    results = run_post_run_analysis(
        engine="qe",
        driver=QEDriver(),
        ordered_gen_steps=[("01STEP1", "bandspw", raw_dir)],
        run_ulid="01RUN",
        calc_ulid="01CALC",
        calc_dir=raw_dir.parent,
    )

    ok_results = [r for r in results if r.state == ResultState.OK]
    bands_results = [r for r in ok_results if r.object_type == "bands"]
    assert len(bands_results) >= 1

    bands_row = bands_results[0]
    assert bands_row.canonical.bundle_kind == "canonical"
    assert bands_row.analysis_object.meta.object_type == "bands"


# ─────────────────────────────────────────────────────────────────────────
# Multi-match orchestrator tests (spec v2.2)
# ─────────────────────────────────────────────────────────────────────────


def test_orchestrator_multi_match_scf_scf_scf(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """3 SCF steps → 3 convergence OK results."""
    driver = MockDriver(
        ANALYSIS_CAPABILITIES=[
            AnalysisCapability(object_type="convergence", gen_step_sequence=["scf"]),
        ]
    )

    monkeypatch.setattr(orchestrator_mod, "get_parser", lambda e, o: SuccessfulBandsProvider)

    ordered = [
        ("S1", "scf", tmp_path / "s1"),
        ("S2", "scf", tmp_path / "s2"),
        ("S3", "scf", tmp_path / "s3"),
    ]
    results = run_post_run_analysis(engine="qe", driver=driver, ordered_gen_steps=ordered, calc_dir=tmp_path)
    ok = [r for r in results if r.state == ResultState.OK]
    assert len(ok) == 3
    assert [r.step_ulids for r in ok] == [["S1"], ["S2"], ["S3"]]


def test_orchestrator_missing_provider_returns_missing_evidence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """AC5: missing provider → MISSING_EVIDENCE(NO_PROVIDER), no crash."""
    driver = MockDriver(
        ANALYSIS_CAPABILITIES=[
            AnalysisCapability(object_type="unknown_thing", gen_step_sequence=["scf"]),
        ]
    )

    monkeypatch.setattr(orchestrator_mod, "get_parser", lambda e, o: None)

    with pytest.warns(UserWarning, match="No analysis provider"):
        results = run_post_run_analysis(
            engine="qe",
            driver=driver,
            ordered_gen_steps=[("S1", "scf", tmp_path)],
            calc_dir=tmp_path,
        )

    assert len(results) == 1
    assert results[0].state == ResultState.MISSING_EVIDENCE
    assert results[0].reason == MissingReason.NO_PROVIDER


def test_orchestrator_parser_error_returns_parser_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """AC11: parse() exception → PARSER_ERROR with error string."""
    driver = MockDriver(
        ANALYSIS_CAPABILITIES=[
            AnalysisCapability(object_type="bands", gen_step_sequence=["bandspw"]),
        ]
    )

    monkeypatch.setattr(orchestrator_mod, "get_parser", lambda e, o: FailingProvider)

    with pytest.warns(UserWarning, match="failed"):
        results = run_post_run_analysis(
            engine="qe",
            driver=driver,
            ordered_gen_steps=[("S1", "bandspw", tmp_path)],
            calc_dir=tmp_path,
        )

    assert len(results) == 1
    assert results[0].state == ResultState.PARSER_ERROR
    assert "synthetic parse failure" in results[0].error


def test_orchestrator_result_states_exhaustive(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Every matched instance gets exactly one of OK/MISSING_EVIDENCE/PARSER_ERROR."""
    driver = MockDriver(
        ANALYSIS_CAPABILITIES=[
            AnalysisCapability(object_type="ok_type", gen_step_sequence=["scf"]),
            AnalysisCapability(object_type="no_prov", gen_step_sequence=["relax"]),
            AnalysisCapability(object_type="fail_type", gen_step_sequence=["md"]),
        ]
    )

    def _get_parser(engine, object_type):
        if object_type == "ok_type":
            return SuccessfulBandsProvider
        if object_type == "fail_type":
            return FailingProvider
        return None

    monkeypatch.setattr(orchestrator_mod, "get_parser", _get_parser)

    ordered = [
        ("S1", "scf", tmp_path / "s1"),
        ("S2", "relax", tmp_path / "s2"),
        ("S3", "md", tmp_path / "s3"),
    ]

    with pytest.warns(UserWarning):
        results = run_post_run_analysis(engine="qe", driver=driver, ordered_gen_steps=ordered, calc_dir=tmp_path)

    assert len(results) == 3
    states = {r.object_type: r.state for r in results}
    assert states["ok_type"] == ResultState.OK
    assert states["no_prov"] == ResultState.MISSING_EVIDENCE
    assert states["fail_type"] == ResultState.PARSER_ERROR
