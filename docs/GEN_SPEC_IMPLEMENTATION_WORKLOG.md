# GEN/SPEC Constitution Implementation Worklog

**Started**: 2026-02-01
**Completed**: 2026-02-01
**Status**: COMPLETE

---

## Critical Instructions (DO NOT FORGET)

### How to Run Tests
- **MUST use `.venv`**: `source .venv/bin/activate`
- **For full test suite MUST use parallel**: `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
- **For specific tests**: `python -m pytest <path> -v --tb=short`

### Phase 4 is REQUIRED
- Phase 4 (Centralize Execution Choke Point) is **NOT optional/future**
- Must implement `step_type_unpack.py` and migrate all execution files

### Key Reference Files
1. **LAW (MUST OBEY)**: `docs/spec/step_type_gen_spec_constitution.md`
2. **Review**: `docs/GEN_SPEC_CONSTITUTION_REVIEW.md`
3. **Implementation Plan**: `docs/GEN_SPEC_IMPLEMENTATION_PLAN.md`

---

## Progress Log

### Phase 1: Eliminate Manual Join/Split (P0 - Critical)

| Task | File | Status | Notes |
|------|------|--------|-------|
| 1.1 | calculation/verification.py:102 | DONE | Used gen_from() |
| 1.2 | calculation/runner.py:80 | DONE | Used gen_from() + prefix_from() |
| 1.3 | engines/pyscf/chain.py:27 | DONE | Used prefix_from() + is_spec() |
| 1.4 | daemon/compat.py:737 | DONE | Used gen_from() |
| 1.5 | api/_mapping/dto_mapping.py:383 | DONE | Used prefix_from() + is_spec() |
| 1.6 | api/service.py:6966 | DONE | Used prefix_from() + is_spec() |
| 1.7 | execution/reference_resolver.py:63 | DONE | Used gen_from() + prefix_from() |
| 1.8 | execution/vasp_staging.py:58 | DONE | Used gen_from() + prefix_from() |
| 1.9 | drivers/vasp/staging.py:58 | DONE | Used gen_from() + prefix_from() |

### Phase 2: Add Gate Test

| Task | File | Status | Notes |
|------|------|--------|-------|
| 2.1 | tests/gates/test_no_manual_join_split.py | DONE | Gate passes |

### Phase 3: Fix Tool Scripts

| Task | File | Status | Notes |
|------|------|--------|-------|
| 3.1 | tools/generate_wannier90_demo.py comments | DONE | w90_preproc → w90_wannierprep |
| 3.2 | tools/generate_wannier90_demo.py mapping | DONE | Use spec_from() instead of hardcoded dict |

### Phase 4: Centralize Execution Choke Point (REQUIRED)

| Task | File | Status | Notes |
|------|------|--------|-------|
| 4.1 | Create execution/step_type_unpack.py | DONE | UnpackedStepType dataclass + unpack functions |
| 4.2 | Migrate calculation/runner.py | DONE | Uses unpack_step_type() |
| 4.3 | Migrate execution/reference_resolver.py | DONE | Uses unpack_step_type() |
| 4.4 | Migrate execution/vasp_staging.py | DONE | Uses unpack_step_type() |
| 4.5 | Migrate drivers/vasp/staging.py | DONE | Uses unpack_step_type() |

### Test Runs

| Time | Scope | Result | Notes |
|------|-------|--------|-------|
| 2026-02-01 | gates/ | 126 passed | All gate tests pass including new manual join/split gate |
| 2026-02-01 | tests/ (full) | 3019 passed | Full test suite passes with parallel execution |

---

## Test Fixes Required

Track any tests that need modification due to gen/spec issues:

| Test File | Issue | Status |
|-----------|-------|--------|
| - | - | - |

---
