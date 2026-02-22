# MCP Stage 6: Error Recovery — Worklog

## Plan

Upgrade `run_calculation` error returns from basic failure messages to structured diagnostics with knowledge-backed suggested_fixes. Deterministic rules, not LLM reasoning.

### Tasks
1. Review existing error infrastructure (ErrorDTO, exc_mapping, output parsers, run_calculation error path)
2. Review knowledge base error_recovery entries for actionable content
3. Design error enrichment layer (pattern classification → knowledge query → suggested_fixes)
4. Implement `error_enrichment.py`
5. Modify `run_calculation.py` to use enrichment on failure
6. Add tag filtering to KnowledgeStore if needed
7. Write `test_stage6.py` (~7-8 tests)
8. Run all tests, fix issues
9. Update this worklog

## Infrastructure Review

### Error DTO & Run Result
- `RunResultDTO` (core/run/dto.py): dataclass with `calc_ulid`, `run_ulid`, `status`, `steps` (list of StepResultDTO), `exit_code`, `error` (ErrorDTO), `io_dir`
- `StepResultDTO`: `step_ulid`, `step_type_gen`, `step_type_spec`, `status`, `message`
- `ErrorDTO`: `error_type`, `message`, `details` dict
- `exc_mapping.py`: maps Python exceptions → ErrorDTO (KeyError → "validation_error", etc.)

### QE Output Parser
- `QEOutputParser` at `drivers/qe/parsers/output.py`
- `QESCFDigest` dataclass: `converged`, `total_energy_ry`, `n_iterations`, `wall_time_s`, etc.
- Key: `converged=True` only when `! total energy =` line is found
- `can_parse(workdir)` checks for .out files

### Existing run_calculation error path
- Before Stage 6: returned basic `make_error("execution_failed", ...)` or `make_response(payload, status="error")` with no diagnostics

### Knowledge base error_recovery entries
- 5 entries tagged `error_recovery` in builtin_entries.py:
  1. SCF oscillation → reduce mixing_beta/AMIX
  2. SCF not converging → increase electron_maxstep/NELM
  3. SCF diverging → check structure, reduce mixing
  4. Charge sloshing in metals → Kerker/diag mixing
  5. Forces not converging → tighten thresholds

## Error Pattern → Fix Mapping

| Error Type | Detection Signal | Severity | Suggested Fixes |
|------------|-----------------|----------|-----------------|
| `SCF_NOT_CONVERGED` | digest.converged=False, n_iterations>0 | recoverable | reduce mixing_beta, increase electron_maxstep |
| `IONIC_NOT_CONVERGED` | converged=False in relax/vc-relax workflow | recoverable | tighten conv_thr |
| `ENGINE_CRASH` | No digest + non-zero exit_code (or digest with 0 iterations) | fatal | (none — input/install error) |
| `OUT_OF_MEMORY` | OOM keywords in step messages | recoverable | reduce parallelism |
| `UNKNOWN_FAILURE` | Catch-all (no digest, exit_code=None) | error | (none) |

## Key Discovery: QE "JOB DONE" vs SCF Convergence

QE prints `JOB DONE` even when SCF does not converge — it just means the program finished normally. The real convergence indicator is the `! total energy = ...` line in the output. When SCF doesn't converge:
- `status = "completed"` (QE exited normally)
- `total_energy_ry = None` (no `!` final energy line found)
- `n_iterations > 0` (QE ran some SCF iterations)

This required a **post-completion convergence check** in `run_calculation.py`: after "completed" status, parse the digest and if `total_energy_ry is None` with `n_iterations > 0`, override `converged` to `False` and trigger error enrichment.

## Knowledge Base Changes

No schema changes. The existing FTS5 `tags` column naturally supports searching for `"error_recovery SCF convergence mixing"` which matches the tagged entries. The `_query_knowledge_for_error()` function queries with error-type-specific keywords and returns up to 300 chars of the top match's content.

## Test Results

### Stage 6 tests: 9 passed
- `TestEnrichmentClassification` (7 unit tests with mock DTOs):
  - `test_scf_not_converged`: converged=False, n_iterations>0 → SCF_NOT_CONVERGED
  - `test_engine_crash`: no digest, exit_code=139 → ENGINE_CRASH (fatal)
  - `test_unknown_failure`: no digest, exit_code=None → UNKNOWN_FAILURE
  - `test_suggested_fixes_from_knowledge`: fixes include knowledge-backed reasoning
  - `test_suggested_fix_format`: each fix has action/parameter/confidence/reason
  - `test_context_hint_includes_calc_ulid`: calc_ulid in context_hint for copy-paste
  - `test_error_severity_classification`: recoverable vs fatal classification

- `TestRealQEFailureRecovery` (2 real QE tests, skip if no QE):
  - `test_scf_failure_and_recovery`: bad params → SCF_NOT_CONVERGED → fix → success
  - `test_error_return_has_diagnostics`: verify complete error return structure

### All MCP tests: 86 passed
### Full suite: 5746 passed, 4 skipped, 0 failed

## Files Created

| File | Purpose |
|------|---------|
| `src/qmatsuite/mcp/error_enrichment.py` | Error classification + knowledge-backed suggested_fixes |
| `tests/mcp/test_stage6.py` | 9 tests (7 unit + 2 real QE) |

## Files Modified

| File | Change |
|------|--------|
| `src/qmatsuite/mcp/tools/run_calculation.py` | Rewritten: added `_try_parse_digest()`, post-completion convergence check, error enrichment on both failure and completed-but-not-converged paths |

## MCP Tool Count

- Stage 0: 1 tool (ping)
- Stage 1: 4 tools (list_engines, list_workflows, get_presets, search_parameters)
- Stage 2: 5 tools (create_calculation, set_parameters, apply_preset, inspect_calculation, preview_compilation)
- Stage 3: 4 tools (run_calculation, get_status, get_results_summary, quick_run)
- Stage 4: 1 tool (search_knowledge)
- Stage 5: 0 tools (integration testing only)
- Stage 6: 0 tools (error enrichment layer, no new tools)
- **Total: 15 tools, 86 MCP tests**
