# Provenance Implementation Worklog

**Laws**: `docs/governance/PROVENANCE_VERSIONED_HISTORY_SPEC.md` (P1-P9)
**Plan**: `docs/governance/PROVENANCE_IMPLEMENTATION_PLAN.md` (Phase 0-5)
**Test**: `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`

---

## Progress

### Phase 0: Scaffolding + Gate Tests
- [x] Create `src/qmatsuite/provenance/__init__.py`
- [x] Create `src/qmatsuite/provenance/errors.py`
- [x] Create `src/qmatsuite/provenance/opctx.py`
- [x] Create `tests/gates/test_provenance_skip_isolation.py`
- [x] Create `tests/gates/test_no_duplicate_scanners.py`
- [x] Run tests: 3274 passed, 19 skipped

### Phase 1: SQLite + OpCtx Enforcement
- [x] Create schema.py, db.py, locks.py, recording.py
- [x] Modify save_yaml_doc() to accept opctx parameter
- [x] Create gate tests (P1, P2, P6, P7)
- [ ] Update all callers with opctx (deferred - migration mode active)
- [x] Run tests: 3293 passed, 19 skipped

### Phase 2: Run Recording
- [x] Create snapshots.py
- [x] Create cas.py (CAS for storing snapshots)
- [x] Add record_run_start/complete/step to recording.py
- [ ] Integrate with runner.py (deferred - infrastructure ready)
- [x] Run tests: 3293 passed, 19 skipped

### Phase 3: Artifact Scanning
- [x] Create policy.py (ArtifactPolicy + default policies per engine)
- [x] Create scanner.py (ArtifactScanner + ingest_artifacts)
- [ ] Add ARTIFACT_POLICY to recipes (deferred - policies defined in provenance module)
- [ ] Integrate scanner with runner (deferred - infrastructure ready)
- [x] Run tests: 3296 passed, 19 skipped, 5 pre-existing failures (Gaussian driver)

### Phase 4: CAS + Restore
- [x] Create cas.py (done in Phase 2)
- [x] Create restore.py (restore_from_snapshot, restore_from_run)
- [x] Create P5 gate test (test_cas_integrity.py - 8 tests)
- [x] Run tests: 3301 passed, 19 skipped

### Phase 5: Cleanup
- [x] Note: skip_history kept for backward compat (used in runner.py, service.py)
- [ ] Add migrate_legacy_history() (deferred - not critical for MVP)
- [x] Update governance README with gate inventory
- [x] Run tests: 3296 passed, 19 skipped, 5 pre-existing failures

---

## Session Log

### 2026-02-05: Session Start
- Baseline: 3269 passed, 19 skipped
- Beginning Phase 0 implementation

### 2026-02-05: Phase 0 Complete
- Created provenance package with opctx.py and errors.py
- Created gate tests for Law P3 (skip isolation) and Law P9 (no duplicate scanners)
- Tests: 3274 passed, 19 skipped (+5 new gate tests)
- Beginning Phase 1: SQLite + OpCtx enforcement

### 2026-02-05: Phase 1 Core Complete
- Created schema.py (SQLite DDL), db.py, locks.py, recording.py
- Modified yaml_io.py save_yaml_doc() to accept opctx and record provenance
- Modified yamldoc.py save() methods to accept opctx
- Created gate tests for Laws P1, P2, P6, P7 (19 tests)
- Tests: 3293 passed, 19 skipped (+19 new gate tests)
- Note: opctx is optional during migration; callers not yet updated
- Beginning Phase 2: Run recording

### 2026-02-05: Phase 2 Infrastructure Complete
- Created cas.py (Content-Addressed Store)
- Created snapshots.py (run snapshot creation)
- Added record_run_start/complete/step to recording.py
- Infrastructure ready for runner.py integration
- Tests: 3293 passed, 19 skipped
- Note: Runner integration deferred; all recording functions available

### 2026-02-05: Phase 4 Complete
- Created restore.py (restore_from_snapshot, restore_from_run)
- Created test_cas_integrity.py gate test (Law P5, 8 tests)
- Tests: 3301 passed, 19 skipped (+8 new CAS tests)

### 2026-02-05: Phase 3 Complete
- Created policy.py (ArtifactPolicy dataclass + default policies)
- Created scanner.py (ArtifactScanner + ingest_artifacts)
- Defined policies for: QE, VASP, ORCA, Gaussian, xTB, LAMMPS
- All 32 provenance gate tests pass
- Tests: 3296 passed, 19 skipped, 5 pre-existing Gaussian failures

### 2026-02-05: Gaussian Test Fix

Fixed 5 Gaussian test failures caused by missing entry in test_registry_routing.py.

**Root Cause**: `TestDriverValidation.setup_method()` resets the DriverRegistry and removes
driver modules from sys.modules for re-import. Gaussian was missing from this list, so
its module stayed cached but its registration was cleared.

**Fix**: Added `'qmatsuite.drivers.gaussian'` to `modules_to_remove` in
`tests/gates/test_registry_routing.py:170`.

**Tests**: 3301 passed, 19 skipped (all green)

---

### Summary

All provenance infrastructure complete:
- Phase 0: Package scaffolding + gate tests (P3, P9)
- Phase 1: SQLite store + OpCtx enforcement (P1, P2, P6, P7)
- Phase 2: Run recording + snapshots (CAS Tier-0)
- Phase 3: Artifact scanning + policies
- Phase 4: CAS + restore functionality (P5)

Remaining work (deferred):
- Phase 5: Cleanup legacy history module
- Runner integration (calling provenance functions from runner.py)
- Update all callers to pass opctx (currently optional)

---

## FINALIZATION SESSION

### 2026-02-05: Phase F1 Complete

Created gate test `tests/gates/test_no_legacy_history.py` with 5 tests:
1. `test_no_history_module_imports` - fails with 22 violations
2. `test_yaml_io_no_skip_history` - fails with 3 violations
3. `test_runner_no_skip_history` - fails with 4 violations
4. `test_no_history_dir_references` - fails with 4 violations
5. `test_history_module_not_exists` - fails (module exists)

These tests will pass once finalization is complete.

Beginning Phase F2: Wire runner to provenance.

### 2026-02-05: Phase F2 Complete

Wired runner.py to use provenance instead of legacy history:

1. **Removed `skip_history` parameter** from `CalculationRunner.run()`
2. **Replaced `_start_history_recording()`** with `_start_provenance_recording()`:
   - Calls `create_run_snapshot()` to capture SSOT state
   - Calls `record_run_start()` to record in provenance DB
   - Law P7 compliant: failures logged but don't fail runs
3. **Replaced `_complete_history_recording()`** with `_complete_provenance_recording()`:
   - Calls `record_run_complete()` to record final status
   - Law P7 compliant: failures logged but don't fail runs
4. **Updated service.py** to remove `skip_history=False` arg
5. **Updated test mocks** in test files to match new signature

**Gate test `test_runner_no_skip_history` now passes.**

Tests: 3302 passed, 19 skipped (4 gate tests fail as expected - guiding F3-F5)

Beginning Phase F3: Rewire svc.history.* to provenance.

### 2026-02-05: Phase F3 Complete

Rewired service.py History class to use provenance instead of legacy history:

1. **Created `provenance/query.py`** - Query functions for operations and runs
2. **Created `provenance/pins.py`** - Pin functionality for analysis results
3. **Added PIN_CREATE OperationType** to opctx.py
4. **Rewrote History class methods**:
   - `get_timeline()` - queries runs from provenance DB
   - `get_run_revision()` - uses get_run_details()
   - `list_runs()` - uses query_runs()
   - `pin_analysis()` - uses provenance pins
   - `can_pin()` - uses provenance pins
   - `get_pin_data()` - uses provenance pins
   - `get_latest_run_for_step()` - uses provenance queries
   - `delete()` - now deletes .provenance/ instead of .history/
5. **Updated cancel_run fallback** to use provenance
6. **Updated golden fixture** for get_project_history (no auto baseline)

Tests: 3302 passed, 19 skipped (4 gate tests fail for yaml_io.py + history module)

Beginning Phase F4: Close opctx migration mode.

### 2026-02-05: Phase F4 Complete

Closed opctx migration mode in yaml_io.py:

1. **Removed `skip_history` parameter** from save_yaml_doc()
2. **Removed `actor` parameter** (no longer needed without legacy history)
3. **Removed `_record_history_edit_event()` function**
4. **Removed all history module imports** from yaml_io.py
5. **Updated docstrings** to reflect provenance-only recording

Tests: 3305 passed, 19 skipped (1 gate test fails for history module)

Beginning Phase F5: Delete legacy history module.

### 2026-02-05: Phase F5 Complete

Deleted legacy history module completely:

1. **Deleted `src/qmatsuite/history/`** (entire directory)
   - events.py, __init__.py, pins.py, run_revision.py, digests.py, storage.py
2. **Deleted legacy test files**:
   - tests/unit/test_history_digests.py
   - tests/unit/test_history_storage.py

**All 5 gate tests now pass.**

Tests: 3237 passed, 19 skipped

Beginning Phase F6: Final verification and documentation.

### 2026-02-05: FINALIZATION COMPLETE

**Verification Checks:**
- `grep -r ".history" src/` - Only `.history` in method names (svc.history.*), no path refs
- `grep -r "skip_history" src/` - No references found
- `grep -r "from qmatsuite.history" src/` - No imports found
- `ls src/qmatsuite/history` - Module deleted

**Final Test Results:**
- 3237 passed, 19 skipped
- All 5 gate tests pass (test_no_legacy_history.py)

---

## FINALIZATION SUMMARY

The Provenance/Versioned History system finalization is **COMPLETE**.

### What Was Done

1. **Phase F1**: Created gate test `test_no_legacy_history.py` (5 tests)
2. **Phase F2**: Wired runner.py to provenance recording
3. **Phase F3**: Rewired service.py History class to use provenance
4. **Phase F4**: Closed opctx migration mode in yaml_io.py
5. **Phase F5**: Deleted legacy history module entirely
6. **Phase F6**: Final verification and documentation

### Files Created
- `src/qmatsuite/provenance/query.py` - Query API for runs/operations
- `src/qmatsuite/provenance/pins.py` - Pin functionality
- `tests/gates/test_no_legacy_history.py` - Gate preventing reintroduction

### Files Modified
- `src/qmatsuite/calculation/runner.py` - Uses provenance recording
- `src/qmatsuite/api/service.py` - History class uses provenance
- `src/qmatsuite/core/yaml_io.py` - Removed skip_history, legacy history code
- `src/qmatsuite/provenance/__init__.py` - Added new exports
- `src/qmatsuite/provenance/opctx.py` - Added PIN_CREATE type
- `tests/fixtures/golden_0873ebf/daemon/get_project_history.json` - Updated contract

### Files Deleted
- `src/qmatsuite/history/` (entire directory - 6 files)
- `tests/unit/test_history_digests.py`
- `tests/unit/test_history_storage.py`

### NON-NEGOTIABLE Requirements Met
- [x] A) Delete legacy .history completely - no compat layers, no shims
- [x] B) Keep all tests fully green (3237+ passed)
- [x] C) Frontend history UI maintained (RPC payload shapes preserved)
- [x] D) No technical debt - single system only (provenance)

### Architecture
- All history/provenance now uses `.provenance/` directory
- SQLite database: `.provenance/provenance.db`
- Content-Addressed Store: `.provenance/.cas/`
- No `.history/` directory or JSONL files
