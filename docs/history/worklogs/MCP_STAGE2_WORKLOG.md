# MCP Stage 2: Configuration Tools — Worklog

## Summary

Stage 2 adds 5 configuration tools that let an agent create and configure
calculations via the MCP server — the first time the MCP layer writes to disk.

**Goal**: After Stage 2 an agent can: discover engines -> create a calculation ->
configure parameters -> apply presets -> inspect the result -> preview compilation.

## Implementation

### 0. `make_error()` upgrade (envelope.py)

Added 3 keyword-only fields for richer diagnostics while keeping backward compat:
- `severity`: `"error"` (default), `"warning"`, `"info"`
- `diagnostics`: per-parameter issues list
- `suggested_fixes`: machine-actionable fix hints

### 1. Project context module (mcp/project.py — NEW)

- `get_project_root()` — auto-detects via `find_project_root()` or returns override
- `get_service()` — returns `QVService(get_project_root())`
- `set_project_root(path)` — testable override for monkeypatching in tests
- `ProjectNotFoundError` — raised when no project found

### 2. `create_calculation` tool (mcp/tools/create_calculation.py — NEW)

- Validates engine via `DriverRegistry.get_all_engines()`
- Validates workflow via `get_workflow_service().get_template()`
- Calls `svc.project.init_calculation()` + `svc.calculation.add_step()` per workflow step
- Returns `{calc_ulid, name, engine, workflow, steps: [{step_index, step_type_gen, step_type_spec, step_ulid}]}`

### 3. `set_parameters` tool (mcp/tools/set_parameters.py — NEW)

- Resolves step ULID from zero-based index via `get_detail()`
- Calls `svc.calculation.update_step_params(calc, step, {"parameters": params})`
- Returns `{calc_ulid, step, step_ulid, params_set}`

### 4. `apply_preset` tool (mcp/tools/apply_preset.py — NEW)

- Calls `svc.calculation.apply_presets(calc_ulid, presets)`
- Returns full result including `steps_updated`, `step_results`, `dimension_states`

### 5. `inspect_calculation` tool (mcp/tools/inspect_calculation.py — NEW)

- Overview mode (step=-1): returns engine, structure, all steps summary
- Detail mode (step>=0): also returns full parameters + cards for that step
- Supports round-trip verification (set_params -> inspect -> verify)

### 6. `preview_compilation` tool (mcp/tools/preview_compilation.py — NEW)

- Stateless — no project or calculation needed
- Validates engine + workflow, then calls `compile_presets_for_step()` per gen step
- Returns compiled parameters per step

### 7. server.py — registered 5 new tool imports

### 8. Bugfix: `service.py` apply_presets broken import

Fixed pre-existing bug where `apply_presets()` tried to import
`PresetCompilationError` and `PrecisionContextError` from `quantumvitas.api`
but they were never re-exported there. Changed to import from their source modules:
- `quantumvitas.presets.compiler.PresetCompilationError`
- `quantumvitas.presets.precision_context.PrecisionContextError`
- `quantumvitas.presets.dimensions.DIMENSION_PRECISION, PrecisionOption`

## Files Created (7 new)

| File | Purpose |
|------|---------|
| `src/quantumvitas/mcp/project.py` | Project context (get_service, testable override) |
| `src/quantumvitas/mcp/tools/create_calculation.py` | create_calculation tool |
| `src/quantumvitas/mcp/tools/set_parameters.py` | set_parameters tool |
| `src/quantumvitas/mcp/tools/apply_preset.py` | apply_preset tool |
| `src/quantumvitas/mcp/tools/inspect_calculation.py` | inspect_calculation tool |
| `src/quantumvitas/mcp/tools/preview_compilation.py` | preview_compilation tool |
| `tests/mcp/test_stage2.py` | 15 Stage 2 tests |

## Files Modified (3 existing)

| File | Change |
|------|--------|
| `src/quantumvitas/mcp/envelope.py` | Added severity, diagnostics, suggested_fixes to make_error |
| `src/quantumvitas/mcp/server.py` | 5 new tool module imports |
| `src/quantumvitas/api/service.py` | Fixed broken import in apply_presets |

## Test Results

- 35 MCP tests pass (6 Stage 0 + 14 Stage 1 + 15 Stage 2)
- No regressions in Stage 0/1

## Notes for Stage 3

- `inspect_calculation` dry_run (materializing input files) deferred
- PrecisionAdvisor in preview_compilation deferred (requires structure)
- show_input_file in preview_compilation deferred (requires inputformat writer)
- run_calculation / execution tools are Stage 3
- Preset values use enum values (e.g. "collinear_lsda"), not profile names (e.g. "COL")
  — may want a normalization layer in the MCP tools for agent-friendly names
