"""Tests for analysis capability matching."""

from pathlib import Path

import pytest

from qmatsuite.core.analysis.capability import (
    AnalysisCapability,
    AnalysisResult,
    CapabilityMatch,
    MissingReason,
    ResultState,
    canonical_match_key,
    enumerate_all_matches,
    find_contiguous_match,
)
from qmatsuite.core.driver_protocol import BaseEngineDriver
from qmatsuite.drivers.qe.driver import QEDriver


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


# ─────────────────────────────────────────────────────────────────────────
# enumerate_all_matches() tests — multi-match semantics (spec §5.4, §5.9)
# ─────────────────────────────────────────────────────────────────────────


def test_enumerate_all_matches_repeated_scf() -> None:
    """AC1: [scf, scf, scf] with convergence→["scf"] → 3 convergence instances."""
    caps = [AnalysisCapability(object_type="convergence", gen_step_sequence=["scf"])]
    ordered = [
        ("S1", "scf", Path("/tmp/s1")),
        ("S2", "scf", Path("/tmp/s2")),
        ("S3", "scf", Path("/tmp/s3")),
    ]
    matches = enumerate_all_matches(caps, ordered)
    assert len(matches) == 3
    assert all(m.object_type == "convergence" for m in matches)
    assert [m.step_ulids for m in matches] == [["S1"], ["S2"], ["S3"]]


def test_enumerate_all_matches_repeated_pipeline() -> None:
    """AC2: [scf, bandspw, bands, bandspw, bands] → 1 convergence + 2 bands."""
    caps = [
        AnalysisCapability(object_type="convergence", gen_step_sequence=["scf"]),
        AnalysisCapability(object_type="bands", gen_step_sequence=["bandspw", "bands"]),
    ]
    ordered = [
        ("S1", "scf", Path("/tmp/s1")),
        ("S2", "bandspw", Path("/tmp/s2")),
        ("S3", "bands", Path("/tmp/s3")),
        ("S4", "bandspw", Path("/tmp/s4")),
        ("S5", "bands", Path("/tmp/s5")),
    ]
    matches = enumerate_all_matches(caps, ordered)
    conv = [m for m in matches if m.object_type == "convergence"]
    bands = [m for m in matches if m.object_type == "bands"]
    assert len(conv) == 1
    assert conv[0].step_ulids == ["S1"]
    assert len(bands) == 2
    assert bands[0].step_ulids == ["S2", "S3"]
    assert bands[1].step_ulids == ["S4", "S5"]


def test_enumerate_all_matches_longest_wins() -> None:
    """AC3: overlapping capabilities at same start → longer wins per type."""
    caps = [
        AnalysisCapability(object_type="bands", gen_step_sequence=["bandspw"]),
        AnalysisCapability(object_type="bands", gen_step_sequence=["bandspw", "bands"]),
    ]
    ordered = [
        ("S1", "bandspw", Path("/tmp/s1")),
        ("S2", "bands", Path("/tmp/s2")),
    ]
    matches = enumerate_all_matches(caps, ordered)
    # At start_idx=0, both match, but longer (["bandspw","bands"]) wins
    bands_at_0 = [m for m in matches if m.step_ulids[0] == "S1" and m.object_type == "bands"]
    assert len(bands_at_0) == 1
    assert bands_at_0[0].step_ulids == ["S1", "S2"]


def test_enumerate_all_matches_no_cross_index_collapse() -> None:
    """Different start indices produce independent instances."""
    caps = [AnalysisCapability(object_type="convergence", gen_step_sequence=["scf"])]
    ordered = [
        ("S1", "scf", Path("/tmp/s1")),
        ("S2", "relax", Path("/tmp/s2")),
        ("S3", "scf", Path("/tmp/s3")),
    ]
    matches = enumerate_all_matches(caps, ordered)
    assert len(matches) == 2
    assert matches[0].step_ulids == ["S1"]
    assert matches[1].step_ulids == ["S3"]


def test_enumerate_all_matches_empty_inputs() -> None:
    """Edge case: empty capabilities or steps → empty result."""
    caps = [AnalysisCapability(object_type="x", gen_step_sequence=["scf"])]
    assert enumerate_all_matches([], [("S1", "scf", Path("/tmp"))]) == []
    assert enumerate_all_matches(caps, []) == []


def test_enumerate_all_matches_different_types_at_same_start() -> None:
    """Multiple object_types can match at the same start index."""
    caps = [
        AnalysisCapability(object_type="convergence", gen_step_sequence=["scf"]),
        AnalysisCapability(object_type="field3d", gen_step_sequence=["scf"]),
    ]
    ordered = [("S1", "scf", Path("/tmp/s1"))]
    matches = enumerate_all_matches(caps, ordered)
    assert len(matches) == 2
    types = {m.object_type for m in matches}
    assert types == {"convergence", "field3d"}


# ─────────────────────────────────────────────────────────────────────────
# Validation tests (spec §5.4.6)
# ─────────────────────────────────────────────────────────────────────────


def test_capability_rejects_repeated_gen_steps() -> None:
    """AC4: AnalysisCapability(["scf","scf"]) raises ValueError."""
    with pytest.raises(ValueError, match="repeated step types"):
        AnalysisCapability(object_type="convergence", gen_step_sequence=["scf", "scf"])


# ─────────────────────────────────────────────────────────────────────────
# ResultState / AnalysisResult type tests
# ─────────────────────────────────────────────────────────────────────────


def test_result_state_values() -> None:
    assert ResultState.OK.value == "ok"
    assert ResultState.MISSING_EVIDENCE.value == "missing_evidence"
    assert ResultState.PARSER_ERROR.value == "parser_error"


def test_missing_reason_values() -> None:
    assert MissingReason.NO_PROVIDER.value == "no_provider"
    assert MissingReason.NO_EVIDENCE.value == "no_evidence"


def test_analysis_result_ok() -> None:
    r = AnalysisResult(
        object_type="bands",
        step_ulids=["S1"],
        gen_steps=["bandspw"],
        evidence_dirs=[Path("/tmp")],
        state=ResultState.OK,
        canonical="bundle_obj",
        analysis_object="ao_obj",
    )
    assert r.state == ResultState.OK
    assert r.reason is None
    assert r.error is None


def test_analysis_result_missing_evidence() -> None:
    r = AnalysisResult(
        object_type="bands",
        step_ulids=["S1"],
        gen_steps=["bandspw"],
        evidence_dirs=[Path("/tmp")],
        state=ResultState.MISSING_EVIDENCE,
        reason=MissingReason.NO_PROVIDER,
    )
    assert r.state == ResultState.MISSING_EVIDENCE
    assert r.reason == MissingReason.NO_PROVIDER
    assert r.canonical is None


def test_analysis_result_parser_error() -> None:
    r = AnalysisResult(
        object_type="bands",
        step_ulids=["S1"],
        gen_steps=["bandspw"],
        evidence_dirs=[Path("/tmp")],
        state=ResultState.PARSER_ERROR,
        error="parse failed",
    )
    assert r.state == ResultState.PARSER_ERROR
    assert r.error == "parse failed"


# ─────────────────────────────────────────────────────────────────────────
# canonical_match_key() tests
# ─────────────────────────────────────────────────────────────────────────


def test_canonical_match_key_single_step() -> None:
    mk = canonical_match_key("vasp", "convergence", ["scf"], ["01ABCDEF"])
    assert mk == "vasp:convergence:scf:01ABCDEF"


def test_canonical_match_key_multi_step() -> None:
    mk = canonical_match_key("qe", "bands", ["bandspw", "bands"], ["S1", "S2"])
    assert mk == "qe:bands:bandspw+bands:S1,S2"


def test_canonical_match_key_bijective() -> None:
    """Different inputs produce different keys."""
    mk1 = canonical_match_key("vasp", "convergence", ["scf"], ["S1"])
    mk2 = canonical_match_key("vasp", "convergence", ["relax"], ["S1"])
    mk3 = canonical_match_key("vasp", "convergence", ["scf"], ["S2"])
    assert mk1 != mk2
    assert mk1 != mk3
    assert mk2 != mk3


# ─────────────────────────────────────────────────────────────────────────
# effective_sequence propagation tests
# ─────────────────────────────────────────────────────────────────────────


def test_effective_sequence_on_capability_match() -> None:
    """enumerate_all_matches populates effective_sequence on CapabilityMatch."""
    caps = [AnalysisCapability(object_type="convergence", gen_step_sequence=["scf"])]
    ordered = [("S1", "scf", Path("/tmp/s1"))]
    matches = enumerate_all_matches(caps, ordered)
    assert len(matches) == 1
    assert matches[0].effective_sequence == ["scf"]


def test_effective_sequence_multi_step() -> None:
    caps = [AnalysisCapability(object_type="bands", gen_step_sequence=["bandspw", "bands"])]
    ordered = [
        ("S1", "bandspw", Path("/tmp/s1")),
        ("S2", "bands", Path("/tmp/s2")),
    ]
    matches = enumerate_all_matches(caps, ordered)
    assert len(matches) == 1
    assert matches[0].effective_sequence == ["bandspw", "bands"]


def test_analysis_result_has_effective_sequence_and_match_key() -> None:
    """AnalysisResult fields for effective_sequence and match_key."""
    r = AnalysisResult(
        object_type="convergence",
        step_ulids=["S1"],
        gen_steps=["scf"],
        evidence_dirs=[Path("/tmp")],
        state=ResultState.OK,
        effective_sequence=["scf"],
        match_key="vasp:convergence:scf:S1",
    )
    assert r.effective_sequence == ["scf"]
    assert r.match_key == "vasp:convergence:scf:S1"


def test_analysis_result_defaults_empty() -> None:
    """Default effective_sequence and match_key are empty."""
    r = AnalysisResult(
        object_type="x",
        step_ulids=[],
        gen_steps=[],
        evidence_dirs=[],
        state=ResultState.OK,
    )
    assert r.effective_sequence == []
    assert r.match_key == ""
