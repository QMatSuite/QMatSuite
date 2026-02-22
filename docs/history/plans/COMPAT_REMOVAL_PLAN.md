# Plan: Phase Out compat.py + Delete Golden Contract Tests

## Context

`src/qmatsuite/daemon/compat.py` (~1000 lines) is a backward-compatibility shim that transforms RPC payloads and responses between the v0 GUI format (commit 0873ebf) and the current API. The GUI has since been updated to use many native field names, making most of this layer dead code. The golden contract test infrastructure (101 fixtures + comparison utilities) exists solely to verify this compat layer against the v0 baseline.

**Goal**: Hard-delete compat.py and all golden contract test infrastructure. Update GUI to speak the native API format. No deprecation, no feature flags.

---

## Milestone 1: Delete Golden Contract Infrastructure

Delete all golden fixture files, comparison utilities, and tests that exist solely for v0 baseline comparison. Rewrite test_gui_field_enforcement.py to test native (unshaped) responses.

### Files DELETED
- `tests/fixtures/golden_0873ebf/` (entire directory — 102 JSON files)
- `tests/fixtures/golden_contracts/` (entire directory — 2 scripts)
- `tests/contract_crawler/test_golden_contracts.py`
- `tests/contract_crawler/golden_comparison.py`
- `tests/contract_crawler/normalization.py`
- `tests/contract_crawler/v0_payloads.py`
- `tests/contract_crawler/test_v0_payloads.py`
- `tests/contract_crawler/test_schema_preservation.py`
- `tests/contract_crawler/test_worktree_imports.py`

### Files UPDATED
- `tests/contract_crawler/test_gui_field_enforcement.py` — Remove compat imports, test native responses
- `tests/contract_crawler/recipes/*.py` — Remove v0_payloads imports, inline payload builders
- `tests/contract_crawler/report_coverage.py` — Remove golden fixture dependency
- `tests/contract_crawler/test_gui_methods_covered.py` — Remove golden fixture dependency
- `tests/gates/test_gen_spec_convergence_gate.py` — Remove golden fixture test
- `tests/gates/test_daemon_kernel_ban.py` — Remove compat-specific test

---

## Milestone 2-5: Remove compat.py + Dispatch

Remove all payload adapters, all response shapers, delete compat.py, remove central dispatch calls in server.py, clean up remaining references. Remove `_project_root` injection from list_calculations.

### Files DELETED
- `src/qmatsuite/daemon/compat.py`

### Files UPDATED
- `src/qmatsuite/daemon/server.py` — Remove adapt/shape dispatch, remove compat import
- `tests/gates/test_daemon_kernel_ban.py` — Remove compat test method
- GUI files — Update to handle native response format (null coalescing, field renames)
- Daemon contract tests — Update assertions for native field names
