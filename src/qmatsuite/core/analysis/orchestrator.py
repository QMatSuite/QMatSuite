"""Post-run analysis orchestration (kernel layer, pure compute)."""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, List, Optional, Tuple

from qmatsuite.core.analysis.capability import (
    AnalysisResult,
    MissingReason,
    ResultState,
    canonical_match_key,
    enumerate_all_matches,
)
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.parsers.registry import get_parser


OrderedGenStep = Tuple[str, str, Path]


def run_post_run_analysis(
    engine: str,
    driver: Any,
    ordered_gen_steps: List[OrderedGenStep],
    *,
    run_ulid: Optional[str] = None,
    calc_ulid: Optional[str] = None,
    calc_dir: Optional[Path] = None,
) -> List[AnalysisResult]:
    """
    Execute post-run analysis capability matching and canonical bundle production.

    Uses multi-match semantics (spec v2.2 §5.4): ALL capability instances
    are enumerated and processed independently.  Each instance receives a
    typed result state (OK / MISSING_EVIDENCE / PARSER_ERROR).

    This function is kernel-only orchestration:
    - matches declared engine capabilities against run GEN-step sequence
    - dispatches to registered providers
    - parses raw evidence to AnalysisObject
    - converts to canonical bundle via to_primitives()

    It does not write to CAS or SQLite.
    """
    results: List[AnalysisResult] = []
    capabilities = getattr(driver, "ANALYSIS_CAPABILITIES", []) or []

    matches = enumerate_all_matches(capabilities, ordered_gen_steps)

    for match in matches:
        provider_cls = get_parser(engine, match.object_type)
        if provider_cls is None:
            warnings.warn(
                f"No analysis provider registered for ({engine}, {match.object_type}).",
                stacklevel=2,
            )
            results.append(
                AnalysisResult(
                    object_type=match.object_type,
                    step_ulids=match.step_ulids,
                    gen_steps=match.gen_steps,
                    evidence_dirs=match.evidence_dirs,
                    state=ResultState.MISSING_EVIDENCE,
                    reason=MissingReason.NO_PROVIDER,
                    effective_sequence=match.effective_sequence,
                    match_key=canonical_match_key(
                        engine, match.object_type,
                        match.effective_sequence, match.step_ulids,
                    ),
                )
            )
            continue

        provider = provider_cls()
        primary_raw_dir = match.evidence_dirs[0]
        if hasattr(provider, "can_parse") and not provider.can_parse(primary_raw_dir):
            results.append(
                AnalysisResult(
                    object_type=match.object_type,
                    step_ulids=match.step_ulids,
                    gen_steps=match.gen_steps,
                    evidence_dirs=match.evidence_dirs,
                    state=ResultState.MISSING_EVIDENCE,
                    reason=MissingReason.NO_EVIDENCE,
                    effective_sequence=match.effective_sequence,
                    match_key=canonical_match_key(
                        engine, match.object_type,
                        match.effective_sequence, match.step_ulids,
                    ),
                )
            )
            continue

        evidence_steps: List[Tuple[str, str, Path]] = []
        if len(match.step_ulids) > 1:
            evidence_steps = list(
                zip(
                    match.step_ulids,
                    match.gen_steps,
                    match.evidence_dirs,
                )
            )

        evidence = EvidenceBundle(
            primary_raw_dir=primary_raw_dir,
            calc_dir=calc_dir if calc_dir is not None else primary_raw_dir.parent,
            run_ulid=run_ulid,
            calc_ulid=calc_ulid,
            step_ulids=match.step_ulids,
            gen_steps=match.gen_steps,
            engine_name=engine,
            evidence_steps=evidence_steps,
        )

        try:
            obj = provider.parse(evidence)
            canonical = obj.to_primitives()
        except Exception as exc:
            warnings.warn(
                f"Analysis capability '{match.object_type}' failed: {exc}",
                stacklevel=2,
            )
            results.append(
                AnalysisResult(
                    object_type=match.object_type,
                    step_ulids=match.step_ulids,
                    gen_steps=match.gen_steps,
                    evidence_dirs=match.evidence_dirs,
                    state=ResultState.PARSER_ERROR,
                    error=str(exc),
                    effective_sequence=match.effective_sequence,
                    match_key=canonical_match_key(
                        engine, match.object_type,
                        match.effective_sequence, match.step_ulids,
                    ),
                )
            )
            continue

        results.append(
            AnalysisResult(
                object_type=match.object_type,
                step_ulids=match.step_ulids,
                gen_steps=match.gen_steps,
                evidence_dirs=match.evidence_dirs,
                state=ResultState.OK,
                canonical=canonical,
                analysis_object=obj,
                effective_sequence=match.effective_sequence,
                match_key=canonical_match_key(
                    engine, match.object_type,
                    match.effective_sequence, match.step_ulids,
                ),
            )
        )

    return results
