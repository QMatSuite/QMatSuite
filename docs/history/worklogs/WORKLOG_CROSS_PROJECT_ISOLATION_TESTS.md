# Cross-Project Isolation Tests — Worklog

**Date:** 2026-02-26
**Scope:** Regression tests proving project-scoped isolation of structures, calculations, and ULIDs.
**Trigger:** v1.2.2 blind test raised the question of whether nested/sibling projects could leak resources.

## Summary

21 new tests across 2 files — all passing on first run (after fixing file extension).

| File | Tests | Status |
|------|-------|--------|
| `tests/integration/test_cross_project_isolation.py` | 15 | All pass |
| `tests/mcp/test_cross_project_isolation_mcp.py` | 6 | All pass |

## Findings

### 1. Isolation is confirmed by design

`ResourceIndex` scans only `structures/`, `calculations/`, and `steps/` under the given `project_root`. Two projects — even when nested (inner inside outer's directory tree) with identical names, slugs, and structure names — produce completely independent resource sets.

### 2. Nesting guard works as documented

`detect_enclosing_project()` walks **upward** only. Creating inner-first, outer-second succeeds because the outer directory has no parent `project.qms.yml`. The outer project's marker does not block the pre-existing inner project.

### 3. ULID global uniqueness holds

All 4 ULIDs (2 structures + 2 calculations) across both projects are distinct, as expected from ULID generation.

### 4. Cross-project ULID lookup fails cleanly

Attempting `svc_outer.structure.get(inner_ulid)` raises `NotFoundError` — no silent fallback, no cross-boundary resolution.

### 5. MCP layer respects project root override

Switching `_project_root_override` between calls to `list_structures.fn()`, `create_calculation.fn()`, `inspect_calculation.fn()`, and `get_results_summary.fn()` produces correctly scoped results. Cross-project calc ULIDs return `{"status": "error"}`.

### 6. Mutation isolation confirmed

Creating a new calculation in the outer project does not change the inner project's structure or calculation counts.

## Issue Encountered

**File extension:** pymatgen's `Structure.from_file()` does not recognize `.poscar` — it requires `.vasp` (or bare `POSCAR` filename). Fixed by using `.vasp` extension for temp POSCAR files.

## Test Topology

```
tmp_path/
├── workspace/                         ← outer project root ("My Project")
│   ├── project.qms.yml
│   ├── structures/
│   │   └── silicon/                   ← Al FCC (formula "Al1")
│   ├── calculations/
│   │   └── si-scf/                    ← qe calc bound to Al structure
│   └── subdir/
│       └── my-project/                ← inner project root ("My Project")
│           ├── project.qms.yml
│           ├── structures/
│           │   └── silicon/           ← Si diamond (formula "Si2")
│           └── calculations/
│               └── si-scf/            ← qe calc bound to Si structure
├── si.vasp                            ← Si POSCAR source
└── al.vasp                            ← Al POSCAR source
```

## Full Suite

```
6625 passed, 5 skipped in 376s
```

No regressions introduced.
