# GEN/SPEC Constitution Implementation Worklog

**Started**: 2026-02-01
**Amended**: 2026-02-02 (Constitution v1.1 - DTO MUST carry BOTH, NO conversion above kernel)
**Status**: COMPLETE (v1.1 Phases A-E done)

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
| 2026-02-02 | daemon/ api/ | 203 passed | After Phase B+C (remove reexports, DTO reads) |
| 2026-02-02 | gates/ | 126 passed | All gates pass after B+C |
| 2026-02-02 | tests/ (full) | 3019 passed | Full suite passes after B+C |
| 2026-02-02 | gates/ | 126+2 skipped | After Phase D (join pattern detection added) |
| 2026-02-02 | tests/ (full) | 3019 passed | Full suite passes after all v1.1 phases |

---

## Constitution v1.1 Amendment Phases (2026-02-02)

### Phase A: Conversion Function Census

| Task | Description | Status | Notes |
|------|-------------|--------|-------|
| A.1 | Scan for all conversion helpers | DONE | All 5 canonical functions exist in SSOT |
| A.2 | Consolidate to SSOT | DONE | No duplicates in runtime code (docs/ only has examples) |
| A.3 | Add is_gen() if missing | DONE | is_gen() exists at step_type_convert.py:81 |

### Phase B: Remove API Reexports

| Task | Description | Status | Notes |
|------|-------------|--------|-------|
| B.1 | Delete reexports from api/utils.py | DONE | Removed is_step_type_spec, step_type_gen_from_spec, step_type_spec_from_gen |
| B.2 | Fix daemon/CLI/compat callsites | DONE | Updated daemon/compat.py and daemon/server.py to read from DTO |

### Phase C: Compat Uses DTO Only

| Task | Description | Status | Notes |
|------|-------------|--------|-------|
| C.1 | Audit compat.py | DONE | Found 9 conversion callsites |
| C.2 | Replace with DTO field reads | DONE | All response shapers now read step_type_gen from DTO |

### Phase D: Tighten Join/Split Gate

| Task | Description | Status | Notes |
|------|-------------|--------|-------|
| D.1 | Update gate to catch join patterns | DONE | Added scan_for_manual_join() |
| D.2 | Verify gate catches all patterns | DONE | Gate passes, detects step_type_spec = f"prefix_gen" |

### Phase E: unpack_step_type_safe Policy

| Task | Description | Status | Notes |
|------|-------------|--------|-------|
| E.1 | Find all usages | DONE | 3 usages: reference_resolver.py, vasp_staging.py, drivers/vasp/staging.py |
| E.2 | Verify rationale comments | DONE | All have "Fallback:" comments explaining boundary case |
| E.3 | Reject legacy/compat reasons | DONE | No legacy/compat usages found |

---

## Test Fixes Required

Track any tests that need modification due to gen/spec issues:

| Test File | Issue | Status |
|-----------|-------|--------|
| - | - | - |

---
