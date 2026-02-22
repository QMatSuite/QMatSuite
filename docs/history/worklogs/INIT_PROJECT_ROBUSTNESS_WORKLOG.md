# init_project Robustness Audit & Hardening — Worklog

**Date:** 2026-02-20
**Status:** COMPLETE

## Problem

During an agent demo, `rm -rf` on a calculation directory caused subsequent
MCP tool calls to fail with confusing errors or apparent hangs. This audit
hardens the project loading path so filesystem corruption never causes
hangs, crashes, or misleading errors.

## Vulnerabilities Fixed

| ID | Severity | Fix |
|----|----------|-----|
| V1 | MEDIUM | `get_service()` catches `ValueError` from `QMSService.__init__` and converts to `ProjectNotFoundError` |
| V2 | MEDIUM | `build_resource_index()` collects warnings for corrupt files (via `get_last_index_warnings()`) instead of silently swallowing |
| V3 | LOW | `load_project_config()` wraps YAML parse errors in `ProjectConfigError` |
| V4 | MEDIUM | `init_project` runs `_quick_health_check()` and returns warnings for missing dirs, orphaned refs, corrupt files |
| V5 | LOW | New `cleanup_project` MCP tool removes orphaned references from `project.qms.yml` |

## Files Modified

| File | Change |
|------|--------|
| `src/qmatsuite/mcp/project.py` | +2 lines: catch `ValueError` in `get_service()` |
| `src/qmatsuite/core/resolution.py` | +15 lines: `_last_index_warnings` + `get_last_index_warnings()` + 3 except block updates |
| `src/qmatsuite/core/project_utils.py` | +4 lines: wrap YAML errors in `load_project_config()` |
| `src/qmatsuite/mcp/tools/init_project.py` | +60 lines: `_quick_health_check()` + integration |
| `src/qmatsuite/mcp/server.py` | +1 line: register `cleanup_project` |
| `tests/mcp/test_stage11.py` | Tool count 30→31 + expected_names set |
| `tests/mcp/test_stage_p1.py` | Tool count 30→31 |
| `tests/mcp/test_stage_p2.py` | Tool count 30→31 |

## Files Created

| File | Purpose |
|------|---------|
| `src/qmatsuite/mcp/tools/cleanup_project.py` | New MCP tool (dry_run/remove orphaned refs) |
| `tests/mcp/test_project_robustness.py` | 19 robustness tests |

## Test Results

- 19/19 new robustness tests pass
- 6252 total tests pass, 0 failures, 4 skipped
- MCP tool count: 31 (was 30)
