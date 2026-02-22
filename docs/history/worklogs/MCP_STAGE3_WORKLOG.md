# MCP Stage 3: Execution Tools — Worklog

## Summary

Stage 3 adds 4 execution tools to the MCP server, completing the Phase 1 chain:
**discover -> configure -> run -> get results**.

## Tools Implemented

| Tool | File | Purpose |
|------|------|---------|
| `run_calculation` | `src/qmatsuite/mcp/tools/run_calculation.py` | Synchronous engine execution |
| `get_status` | `src/qmatsuite/mcp/tools/get_status.py` | Query historical run state |
| `get_results_summary` | `src/qmatsuite/mcp/tools/get_results_summary.py` | Compact results (energy, convergence) |
| `quick_run` | `src/qmatsuite/mcp/tools/quick_run.py` | Create + configure + run in one shot |

## Key Design Decisions

1. **Synchronous execution**: `svc.run.run_calculation()` blocks until engine finishes. No polling needed.
2. **Dual strategy for results**: Try provenance digest first (Strategy A), fall back to direct QE parser (Strategy B).
3. **Energy units**: Returns both Ry and eV (conversion factor: 13.605693123).
4. **quick_run limitation**: Cannot auto-set species_map (engine-specific config). User must set it beforehand for QE.

## Files Created (5)

- `src/qmatsuite/mcp/tools/run_calculation.py`
- `src/qmatsuite/mcp/tools/get_status.py`
- `src/qmatsuite/mcp/tools/get_results_summary.py`
- `src/qmatsuite/mcp/tools/quick_run.py`
- `tests/mcp/test_stage3.py`

## Files Modified (1)

- `src/qmatsuite/mcp/server.py` — 4 new tool module imports

## Test Results

- **Stage 3 tests**: 9 passed (4 contract + 5 real QE)
- **All MCP tests**: 44 passed (stages 0-3)
- **Full suite**: 5704 passed, 0 failed, 4 skipped

## Backend API Mappings

| MCP Tool | QMSService Method |
|----------|-----------------|
| run_calculation | `svc.run.run_calculation(calc_ulid)` |
| get_status | `svc.calculation.get_detail()` + `svc.history.get_latest_run_for_step()` |
| get_results_summary | `svc.analysis.get_step_digest()` or `QEOutputParser().parse()` |
| quick_run | `init_calculation` + `add_step` + `apply_presets` + `update_step_params` + `run_calculation` |

## MCP Tool Count

- Stage 0: 1 tool (ping)
- Stage 1: 4 tools (list_engines, list_workflows, get_presets, search_parameters)
- Stage 2: 5 tools (create_calculation, set_parameters, apply_preset, inspect_calculation, preview_compilation)
- Stage 3: 4 tools (run_calculation, get_status, get_results_summary, quick_run)
- **Total: 14 tools**
