"""Post-run analysis orchestration (kernel layer, pure compute)."""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from quantumvitas.core.analysis.capability import find_contiguous_match
from quantumvitas.parsers.registry import get_parser


OrderedGenStep = Tuple[str, str, Path]


def run_post_run_analysis(
    engine: str,
    driver: Any,
    ordered_gen_steps: List[OrderedGenStep],
    *,
    run_ulid: Optional[str] = None,
    calc_ulid: Optional[str] = None,
    calc_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Execute post-run analysis capability matching and canonical bundle production.

    This function is kernel-only orchestration:
    - matches declared engine capabilities against run GEN-step sequence
    - dispatches to registered providers
    - parses raw evidence to AnalysisObject
    - converts to canonical bundle via to_primitives()

    It does not write to CAS or SQLite.
    """
    results: List[Dict[str, Any]] = []
    capabilities = getattr(driver, "ANALYSIS_CAPABILITIES", []) or []

    for capability in capabilities:
        match = find_contiguous_match(capability, ordered_gen_steps)
        if match is None:
            continue

        provider_cls = get_parser(engine, capability.object_type)
        if provider_cls is None:
            warnings.warn(
                f"No analysis provider registered for ({engine}, {capability.object_type}).",
                stacklevel=2,
            )
            continue

        provider = provider_cls()
        primary_raw_dir = match.evidence_dirs[0]
        if hasattr(provider, "can_parse") and not provider.can_parse(primary_raw_dir):
            continue

        parse_kwargs: Dict[str, Any] = {
            "run_ulid": run_ulid,
            "step_ulids": match.step_ulids,
            "gen_steps": match.gen_steps,
            "calc_ulid": calc_ulid,
        }
        if len(match.step_ulids) > 1:
            parse_kwargs["evidence_steps"] = list(
                zip(match.step_ulids, match.gen_steps, match.evidence_dirs)
            )

        try:
            obj = provider.parse(
                primary_raw_dir,
                calc_dir if calc_dir is not None else primary_raw_dir.parent,
                **parse_kwargs,
            )
            canonical = obj.to_primitives()
        except Exception as exc:
            warnings.warn(
                f"Analysis capability '{capability.object_type}' failed: {exc}",
                stacklevel=2,
            )
            continue

        results.append(
            {
                "object_type": capability.object_type,
                "canonical": canonical,
                "analysis_object": obj,
            }
        )

    return results

