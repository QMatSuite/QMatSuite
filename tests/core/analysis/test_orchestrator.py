"""Tests for post-run analysis orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

import quantumvitas.core.analysis.orchestrator as orchestrator_mod
from quantumvitas.core.analysis.band_structure import BandStructure, HighSymPoint
from quantumvitas.core.analysis.base import AnalysisObjectMeta
from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle
from quantumvitas.core.analysis.capability import AnalysisCapability
from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.core.analysis.orchestrator import run_post_run_analysis
from quantumvitas.drivers.qe.driver import QEDriver
from quantumvitas.drivers.qe.parsers.bands import QEBandsProvider  # noqa: F401


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

    assert len(results) == 1
    assert results[0]["object_type"] == "bands"
    assert isinstance(results[0]["canonical"], CanonicalPrimitiveBundle)


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

    assert results == []


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

    assert len(results) == 1
    assert results[0]["object_type"] == "bands"


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

    assert len(results) >= 1
    bands_results = [row for row in results if row["object_type"] == "bands"]
    assert len(bands_results) == 1

    bands_row = bands_results[0]
    assert bands_row["canonical"].bundle_kind == "canonical"
    assert bands_row["analysis_object"].meta.object_type == "bands"
