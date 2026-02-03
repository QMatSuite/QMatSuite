# Kernel Cleanup Worklog

**Governing Documents**:
- [KERNEL_DEPENDENCY_SPEC.md](./KERNEL_DEPENDENCY_SPEC.md) v3.1
- [KERNEL_REVIEW_REPORT.md](./KERNEL_REVIEW_REPORT.md) v3.1
- [KERNEL_EXCEPTIONS.md](./KERNEL_EXCEPTIONS.md) v3.1
- [IMPLEMENTATION_PLAN_KERNEL.md](./IMPLEMENTATION_PLAN_KERNEL.md) v1.0

**Test Commands**:
```bash
# Full suite
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile

# Quick gate tests only
python -m pytest tests/gates/ -v --tb=short
```

---

## PR Checklist

- [x] **PR-K0** — Gate Tests (3 new gate test files)
- [x] **PR-K1** — Fix Kernel→API Reverse Imports (zero allowlist for G-K0)
- [ ] **PR-K2** — YAML Write Centralization (Law K3)
- [ ] **PR-K3** — YAML Read Centralization + Resources Meta-Only (Law K7)
- [ ] **PR-K4** — Engine Input Contract — EngineInput Port (Law K6)
- [ ] **PR-K5** — Create `public.py` Stubs (Law K2)
- [ ] **PR-K6** — Deep Import Migration (Law K2, phased)

---

## Completed Work

### PR-K0: Gate Tests
- `tests/gates/test_kernel_no_api_import.py` (G-K0) — AST scan kernel for `from quantumvitas.api`
- `tests/gates/test_kernel_no_frontend_import.py` (G-K1) — AST scan kernel for CLI/daemon imports
- `tests/gates/test_engine_no_ssot_import.py` (G-K6) — Scan engine/ for SSOT imports and yaml.safe_load

### PR-K1: Fix Kernel→API Reverse Imports
- Replaced 8 `get_step_type_gen` → `gen_from()` call sites
- Moved facade function `materialize_project_from_qe_input_folder` from `calculation/folder_import.py` to `api/folder_import.py`
- G-K0 allowlist reduced to 0
