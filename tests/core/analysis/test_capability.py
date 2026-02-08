"""Tests for analysis capability matching."""

from pathlib import Path

import pytest

from quantumvitas.core.analysis.capability import (
    AnalysisCapability,
    CapabilityMatch,
    find_contiguous_match,
)
from quantumvitas.core.driver_protocol import BaseEngineDriver
from quantumvitas.drivers.qe.driver import QEDriver


def _ordered_steps() -> list[tuple[str, str, Path]]:
    return [
        ("01STEP1", "scf", Path("/tmp/scf")),
        ("01STEP2", "nscf", Path("/tmp/nscf")),
        ("01STEP3", "bandspw", Path("/tmp/bandspw")),
        ("01STEP4", "bands", Path("/tmp/bands")),
    ]


def test_single_step_capability_matches() -> None:
    capability = AnalysisCapability(
        object_type="scf",
        gen_step_sequence=["scf"],
        evidence_files=["*.out"],
    )

    match = find_contiguous_match(capability, _ordered_steps())
    assert isinstance(match, CapabilityMatch)
    assert match.step_ulids == ["01STEP1"]
    assert match.gen_steps == ["scf"]


def test_multi_step_capability_matches() -> None:
    capability = AnalysisCapability(
        object_type="bands",
        gen_step_sequence=["bandspw", "bands"],
        evidence_files=["*.bands.dat.gnu"],
    )

    match = find_contiguous_match(capability, _ordered_steps())
    assert isinstance(match, CapabilityMatch)
    assert match.step_ulids == ["01STEP3", "01STEP4"]
    assert match.gen_steps == ["bandspw", "bands"]


def test_non_matching_capability_returns_none() -> None:
    capability = AnalysisCapability(
        object_type="dos",
        gen_step_sequence=["dos"],
        evidence_files=["*.dos.dat"],
    )

    match = find_contiguous_match(capability, _ordered_steps())
    assert match is None


def test_first_occurrence_wins_when_ambiguous() -> None:
    capability = AnalysisCapability(
        object_type="scf",
        gen_step_sequence=["scf"],
    )
    ordered_steps = [
        ("01STEP1", "scf", Path("/tmp/scf_1")),
        ("01STEP2", "relax", Path("/tmp/relax")),
        ("01STEP3", "scf", Path("/tmp/scf_2")),
    ]

    match = find_contiguous_match(capability, ordered_steps)
    assert isinstance(match, CapabilityMatch)
    assert match.step_ulids == ["01STEP1"]
    assert match.evidence_dirs == [Path("/tmp/scf_1")]


def test_overlapping_matches_allowed_across_capabilities() -> None:
    ordered_steps = [
        ("01STEP1", "scf", Path("/tmp/scf")),
        ("01STEP2", "nscf", Path("/tmp/nscf")),
        ("01STEP3", "bandspw", Path("/tmp/bandspw")),
        ("01STEP4", "bands", Path("/tmp/bands")),
    ]
    cap_single = AnalysisCapability(object_type="bandspw_only", gen_step_sequence=["bandspw"])
    cap_multi = AnalysisCapability(object_type="bands", gen_step_sequence=["bandspw", "bands"])

    match_single = find_contiguous_match(cap_single, ordered_steps)
    match_multi = find_contiguous_match(cap_multi, ordered_steps)

    assert isinstance(match_single, CapabilityMatch)
    assert isinstance(match_multi, CapabilityMatch)
    assert match_single.step_ulids == ["01STEP3"]
    assert match_multi.step_ulids == ["01STEP3", "01STEP4"]


def test_empty_gen_step_sequence_raises_value_error() -> None:
    with pytest.raises(ValueError, match="gen_step_sequence"):
        AnalysisCapability(object_type="bands", gen_step_sequence=[])


def test_capability_matching_is_deterministic() -> None:
    capability = AnalysisCapability(
        object_type="bands",
        gen_step_sequence=["bandspw", "bands"],
    )
    ordered_steps = _ordered_steps()

    first = find_contiguous_match(capability, ordered_steps)
    second = find_contiguous_match(capability, ordered_steps)
    assert first == second


def test_base_engine_driver_analysis_capabilities_default_empty() -> None:
    assert BaseEngineDriver().ANALYSIS_CAPABILITIES == []


def test_qe_driver_analysis_capabilities_declared() -> None:
    capabilities = QEDriver().ANALYSIS_CAPABILITIES
    assert capabilities
    assert any(cap.object_type == "bands" for cap in capabilities)
    assert all(len(cap.gen_step_sequence) >= 1 for cap in capabilities)
