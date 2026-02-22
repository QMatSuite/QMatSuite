# Chunk 2 Milestone: Core Kernel Module Elimination from CLI

**Commit:** `eda69e3` (Add generate_resource_id method to QMSService and corresponding tests)

**Achievement:** Eliminated all direct imports from three core kernel modules in CLI:
- `qmatsuite.core.selectors`: 0 occurrences
- `qmatsuite.core.project_utils`: 0 occurrences  
- `qmatsuite.core.resources`: 0 occurrences

**Methodology:** Micro-batch refactoring using wrapper-first approach: (1) audit CLI imports via `scripts/audit_cli_kernel_imports.py`, (2) add QMSService wrappers in `api.py` with unit tests, (3) migrate call sites to use wrappers, (4) remove direct imports, (5) verify with full pytest suite (`python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`).

**Enforcement:** Architecture gates enforced via `QMATSUITE_ENFORCE_ARCH_GATES` environment variable. Audit JSON snapshots (`/tmp/cli_kernel_deps_chunk2_final.json`) provide measurable metrics. Gate tests in `tests/gates/test_import_rules.py` verify no kernel imports in frontends.

**Status:** All tests passing (2397 passed, 2 skipped, 154 warnings). CLI now accesses core functionality exclusively through QMSService API layer.

