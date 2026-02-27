"""Error enrichment layer for MCP run failures.

Takes a failed run's data (RunResultDTO, QE digest) and produces enriched
error returns with structured diagnostics and knowledge-backed suggested_fixes.

This is a deterministic rules layer — no LLM reasoning.  The agent decides
whether and how to apply the fixes.
"""

from __future__ import annotations

from typing import Any


def enrich_run_error(
    calc_ulid: str,
    result_dto: Any,
    digest: dict | None,
    engine: str,
    workflow: str,
) -> dict:
    """Classify the failure, query knowledge, return an enriched error dict.

    Returns a dict compatible with ``make_error()`` output, with added
    ``diagnostics`` and ``suggested_fixes`` fields.

    Parameters
    ----------
    calc_ulid : str
        Calculation ULID.
    result_dto : RunResultDTO
        The DTO returned by ``svc.run.run_calculation()``.
    digest : dict | None
        Parsed output digest (e.g., from QEOutputParser).
    engine : str
        Engine family (e.g., ``"qe"``).
    workflow : str
        Workflow template id (e.g., ``"scf"``).
    """
    error_type, severity, diagnostics = _classify_error(result_dto, digest, workflow)
    fixes = _build_suggested_fixes(error_type, engine, workflow, diagnostics)

    from qmatsuite.mcp.envelope import make_error

    step_messages = []
    for s in result_dto.steps:
        if s.message:
            step_messages.append(f"step {s.step_type_gen or 'unknown'}: {s.message}")

    message = _build_message(error_type, diagnostics, step_messages)

    hint = (
        f"Use set_parameters(calc_ulid='{calc_ulid}', params=...) to apply a fix, "
        f"then run_calculation(calc_ulid='{calc_ulid}') to retry."
    )

    return make_error(
        error_type=error_type,
        message=message,
        context_hint=hint,
        severity=severity,
        diagnostics=[diagnostics] if diagnostics else None,
        suggested_fixes=fixes or None,
    )


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

def _classify_error(
    result_dto: Any,
    digest: dict | None,
    workflow: str,
) -> tuple[str, str, dict]:
    """Map digest signals + step messages to an error type.

    Returns (error_type, severity, diagnostics_dict).
    """
    diagnostics: dict[str, Any] = {}

    # Extract step-level info
    exit_code = result_dto.exit_code
    step_messages = [s.message for s in result_dto.steps if s.message]

    if digest:
        converged = digest.get("converged", False)
        n_iterations = digest.get("n_iterations", 0)
        total_energy_ry = digest.get("total_energy_ry")

        diagnostics["converged"] = converged
        diagnostics["n_iterations"] = n_iterations
        if total_energy_ry is not None:
            diagnostics["last_energy_ry"] = total_energy_ry

        # SCF not converged: ran but didn't converge
        if not converged and n_iterations > 0:
            if workflow in ("relax", "minimize"):
                diagnostics["workflow"] = workflow
                return "IONIC_NOT_CONVERGED", "recoverable", diagnostics
            return "SCF_NOT_CONVERGED", "recoverable", diagnostics

        # Engine produced output but with zero iterations — likely input error
        if not converged and n_iterations == 0:
            diagnostics["exit_code"] = exit_code
            return "ENGINE_CRASH", "fatal", diagnostics

    # No digest available — check for crash indicators
    if exit_code is not None and exit_code != 0:
        diagnostics["exit_code"] = exit_code
        # Check for OOM in step messages
        for msg in step_messages:
            if msg and any(kw in msg.lower() for kw in ("out of memory", "oom", "killed", "signal 9")):
                return "OUT_OF_MEMORY", "recoverable", diagnostics
        return "ENGINE_CRASH", "fatal", diagnostics

    # Catch-all
    diagnostics["step_messages"] = step_messages
    return "UNKNOWN_FAILURE", "error", diagnostics


# ---------------------------------------------------------------------------
# Suggested fix generation
# ---------------------------------------------------------------------------

def _build_suggested_fixes(
    error_type: str,
    engine: str,
    workflow: str,
    diagnostics: dict,
) -> list[dict]:
    """Query knowledge base + apply heuristic rules to build fixes."""
    fixes: list[dict] = []

    if error_type == "SCF_NOT_CONVERGED":
        fixes.extend(_fixes_for_scf_not_converged(engine))
    elif error_type == "IONIC_NOT_CONVERGED":
        fixes.extend(_fixes_for_ionic_not_converged(engine))
    elif error_type == "OUT_OF_MEMORY":
        fixes.extend(_fixes_for_oom(engine))

    # Enrich with knowledge base reasoning
    knowledge_context = _query_knowledge_for_error(error_type, engine)
    if knowledge_context:
        for fix in fixes:
            if not fix.get("reason"):
                fix["reason"] = knowledge_context

    return fixes


def _fixes_for_scf_not_converged(engine: str) -> list[dict]:
    """Deterministic fixes for SCF non-convergence."""
    fixes = []

    if engine == "qe":
        fixes.append({
            "action": "reduce_mixing",
            "parameter": "ELECTRONS.mixing_beta",
            "to_value": 0.3,
            "confidence": "high",
            "reason": "",
        })
        fixes.append({
            "action": "increase_max_iterations",
            "parameter": "ELECTRONS.electron_maxstep",
            "to_value": 200,
            "confidence": "high",
            "reason": "",
        })
    elif engine == "vasp":
        fixes.append({
            "action": "reduce_mixing",
            "parameter": "INCAR.AMIX",
            "to_value": 0.2,
            "confidence": "high",
            "reason": "",
        })
        fixes.append({
            "action": "increase_max_iterations",
            "parameter": "INCAR.NELM",
            "to_value": 200,
            "confidence": "high",
            "reason": "",
        })
    else:
        # Generic
        fixes.append({
            "action": "reduce_mixing",
            "parameter": "mixing_beta",
            "to_value": 0.3,
            "confidence": "medium",
            "reason": "",
        })

    return fixes


def _fixes_for_ionic_not_converged(engine: str) -> list[dict]:
    """Deterministic fixes for ionic relaxation non-convergence."""
    fixes = []

    if engine == "qe":
        fixes.append({
            "action": "tighten_scf_threshold",
            "parameter": "ELECTRONS.conv_thr",
            "to_value": 1.0e-8,
            "confidence": "high",
            "reason": "",
        })
    elif engine == "vasp":
        fixes.append({
            "action": "tighten_scf_threshold",
            "parameter": "INCAR.EDIFF",
            "to_value": 1.0e-7,
            "confidence": "high",
            "reason": "",
        })

    return fixes


def _fixes_for_oom(engine: str) -> list[dict]:
    """Deterministic fixes for out-of-memory errors."""
    return [{
        "action": "reduce_parallelism",
        "parameter": "npool",
        "to_value": 1,
        "confidence": "medium",
        "reason": "Out of memory. Reducing parallelism may lower peak memory usage.",
    }]


def _query_knowledge_for_error(error_type: str, engine: str) -> str:
    """Query the knowledge base for context matching this error pattern."""
    try:
        from qmatsuite.mcp.knowledge import get_knowledge_store

        store = get_knowledge_store()
        if store.count() == 0:
            return ""

        query_map = {
            "SCF_NOT_CONVERGED": "error_recovery SCF convergence mixing",
            "IONIC_NOT_CONVERGED": "error_recovery forces convergence relax",
            "OUT_OF_MEMORY": "error_recovery memory",
        }
        query = query_map.get(error_type, "")
        if not query:
            return ""

        results = store.search(query, engine=engine, limit=1)
        if results:
            return results[0].get("content", "")[:300]
        return ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Message formatting
# ---------------------------------------------------------------------------

def _build_message(
    error_type: str,
    diagnostics: dict,
    step_messages: list[str],
) -> str:
    """Build a human-readable error message."""
    parts = []

    if error_type == "SCF_NOT_CONVERGED":
        n = diagnostics.get("n_iterations", "?")
        parts.append(f"SCF did not converge after {n} iterations.")
    elif error_type == "IONIC_NOT_CONVERGED":
        parts.append("Ionic relaxation did not converge.")
    elif error_type == "ENGINE_CRASH":
        code = diagnostics.get("exit_code", "?")
        parts.append(f"Engine crashed (exit code {code}).")
    elif error_type == "OUT_OF_MEMORY":
        parts.append("Engine ran out of memory.")
    else:
        parts.append("Calculation failed for unknown reason.")

    if step_messages:
        parts.append("Step details: " + "; ".join(step_messages[:3]))

    return " ".join(parts)
