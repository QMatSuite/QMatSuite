"""Post-run analysis orchestration (kernel layer, pure compute)."""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from quantumvitas.core.analysis.capability import find_contiguous_match
from quantumvitas.core.analysis.evidence import EvidenceBundle
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

    # Deterministic capability resolution:
    # - Evaluate one match per object_type
    # - Prefer longest contiguous sequence, then declaration order
    capabilities_by_type: Dict[str, List[Tuple[int, Any]]] = {}
    type_order: List[str] = []
    for index, capability in enumerate(capabilities):
        object_type = capability.object_type.lower()
        if object_type not in capabilities_by_type:
            capabilities_by_type[object_type] = []
            type_order.append(object_type)
        capabilities_by_type[object_type].append((index, capability))

    for object_type in type_order:
        selected_capability = None
        selected_match = None
        ranked = sorted(
            capabilities_by_type[object_type],
            key=lambda row: (-len(row[1].gen_step_sequence), row[0]),
        )
        for _, candidate in ranked:
            candidate_match = find_contiguous_match(candidate, ordered_gen_steps)
            if candidate_match is not None:
                selected_capability = candidate
                selected_match = candidate_match
                break

        if selected_capability is None or selected_match is None:
            continue

        provider_cls = get_parser(engine, selected_capability.object_type)
        if provider_cls is None:
            warnings.warn(
                f"No analysis provider registered for ({engine}, {selected_capability.object_type}).",
                stacklevel=2,
            )
            continue

        provider = provider_cls()
        primary_raw_dir = selected_match.evidence_dirs[0]
        if hasattr(provider, "can_parse") and not provider.can_parse(primary_raw_dir):
            continue

        evidence_steps: List[Tuple[str, str, Path]] = []
        if len(selected_match.step_ulids) > 1:
            evidence_steps = list(
                zip(
                    selected_match.step_ulids,
                    selected_match.gen_steps,
                    selected_match.evidence_dirs,
                )
            )

        evidence = EvidenceBundle(
            primary_raw_dir=primary_raw_dir,
            calc_dir=calc_dir if calc_dir is not None else primary_raw_dir.parent,
            run_ulid=run_ulid,
            calc_ulid=calc_ulid,
            step_ulids=selected_match.step_ulids,
            gen_steps=selected_match.gen_steps,
            engine_name=engine,
            evidence_steps=evidence_steps,
        )

        try:
            obj = provider.parse(evidence)
            canonical = obj.to_primitives()
        except Exception as exc:
            warnings.warn(
                f"Analysis capability '{selected_capability.object_type}' failed: {exc}",
                stacklevel=2,
            )
            continue

        results.append(
            {
                "object_type": selected_capability.object_type,
                "canonical": canonical,
                "analysis_object": obj,
            }
        )

    return results
