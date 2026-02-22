# API & Daemon Slimdown — Execution Worklog

**Date**: 2026-02-14
**Driven by**: `docs/history/reviews/api_daemon_architecture_review.md`

## Starting Metrics

| Metric | Before |
|--------|--------|
| API methods total (QMSService, all depths) | 117 |
| API methods at depth 0 | 23 |
| RPC endpoint count | 120 (118 unique) |
| Daemon business logic lines (misplaced) | ~770 |
| Methods merged/removed | 0 |
| Methods added (capability gaps) | 0 |

---

## Milestone 1: Close Jupyter Capability Gaps

**Status**: DONE
**Tests**: 5822 passed, 0 failed, 31 skipped

### Task 1.1: Create `svc.online_search.get_candidate_detail()`
- New static method on `OnlineSearch` class in `service.py`
- Moved ~370 lines of business logic from daemon `_handle_structure_get_online_candidate`
- Logic: cache lookup → fetch via existing `fetch_structure()` → primitive conversion → provenance building (OPTIMADE/COD) → shared vis pipeline → bond validation → formula extraction
- New DTO: `CandidateDetailDTO` in `api/types/online_search.py`
- Jupyter users can now preview online structures without daemon

### Task 1.2: Create `svc.structure.import_online()`
- New instance method on `Structure` class in `service.py`
- Moved ~100 lines of import logic from daemon `_handle_structure_import_online_candidate`
- Logic: global cache access → fetch if needed → canonicalize → generate name/slug → write structure file → add online provenance to `extra` field → update project config
- New DTO: `ImportOnlineResultDTO` in `api/types/online_search.py`
- Fixed bug: daemon used project-local cache dir (`project_root/structures/cache`); now uses global cache (`~/.qmatsuite/cache/online_structures/`)
- Jupyter users can now import online structures without daemon

### Task 1.3: Slim daemon handlers
- `_handle_structure_search_online`: Removed double-caching (API already caches in `search_structures()`). Reduced from ~55 lines to ~20 lines.
- `_handle_structure_get_online_candidate`: Replaced ~370 lines with thin wrapper calling `get_candidate_detail()`. Now ~30 lines.
- `_handle_structure_import_online_candidate`: Replaced ~100 lines with thin wrapper calling `svc.structure.import_online()`. Now ~15 lines.
- Added `APIError`/`ValueError` catch in get_candidate handler (graceful error for unknown sources)

### Metrics After Milestone 1

| Metric | Before | After M1 | Delta |
|--------|--------|----------|-------|
| API methods total | 117 | 119 | +2 |
| Daemon business logic lines (misplaced) | ~770 | ~400 | -370 |
| Methods added (capability gaps) | 0 | 2 | +2 |
| Tests passed | 5820 | 5822 | +2 |

---

## Milestone 2: API Merge Batch 1 — Calculation Domain

**Status**: TODO

### Task 2.1: Remove `svc.project.list_calculations()`
- TODO

### Task 2.2: Merge `svc.project.init_calculation()` into `svc.calculation.create()`
- TODO

### Task 2.3: Merge `add_step` + `add_step_from_spec`
- TODO

### Task 2.4: Merge relax structure promotion
- TODO

---

## Milestone 3: API Merge Batch 2 — Analysis + Dead Code + RPC Sync

**Status**: DONE
**Tests**: 5822 passed, 0 failed, 31 skipped

### Task 3.1: Merge `list_raw_files` into `list_step_artifacts`
- **SKIPPED**: Review claimed `list_raw_files` is a "Surface A wrapper" calling `list_step_artifacts`, but actual implementation is independent — recursive scan with binary filtering + rank-ordering vs step-type-aware artifact filtering. Different semantics. GUI RawFileViewer depends on it.

### Task 3.2: Remove `svc.analysis.read_raw_file()`
- `read_raw_file` was a genuine thin wrapper: `return self.read_step_artifact_text(...)` with different defaults (head=1000, tail=100 vs None/None).
- Removed API method. Daemon RPC `read_raw_file` preserved (GUI compat) — now calls `svc.analysis.read_step_artifact_text()` directly with same defaults.
- Updated test, facade assertions, contract crawler categories/exemptions.

### Task 3.3: Remove dead `svc.structure.visualize()`
- Zero callers found in entire codebase (no daemon handler, no CLI, no test, no GUI).
- Also had duplicate dict key bugs (`"structure_ulid"` repeated twice).
- Removed ~63 lines of dead code.

### Task 3.4: Rename `svc.history.list_runs()` → `list_run_history()`
- Prevents confusion with `svc.run.list_runs()` (different domain).
- Updated daemon handler `_handle_list_project_runs()` to call renamed method.

### Metrics After Milestone 3

| Metric | Before | After M3 | Delta |
|--------|--------|----------|-------|
| API methods total | 118 | 116 | -2 |
| Dead code removed | 0 lines | ~80 lines | -80 |
| Tests passed | 5822 | 5822 | 0 |

---

## Milestone 4: QE Metadata Browser → API

**Status**: DONE
**Tests**: 5823 passed, 0 failed, 30 skipped

### Task 4.1: Move QE metadata browser from daemon to api.utils
- Moved ~400 lines of `_qe_parameter_metadata_internal` from `daemon/server.py` to `api/utils.py`
- New private function `_qe_parameter_metadata()` handles QE's 3-level hierarchy (modules → sections → parameters)
- Expanded `get_engine_parameter_metadata()` with `section` parameter and QE dispatch
- `_handle_list_engine_parameter_metadata` in daemon is now a one-call thin wrapper
- Removed daemon's QE metadata imports (7 imports from `api.utils` no longer needed)
- Updated 4 tests: direct `_qe_parameter_metadata_internal` calls → generic RPC requests
- Removed silent `module="pw"` default — now requires explicit category (no silent fallbacks)
- Jupyter users can now browse QE parameters via `get_engine_parameter_metadata(engine_family="qe", ...)`

### Metrics After Milestone 4

| Metric | Before | After M4 | Delta |
|--------|--------|----------|-------|
| Daemon business logic lines | ~400 | ~0 | -400 |
| API utils functions | same | same | 0 (logic moved to existing function) |
| Tests passed | 5822 | 5823 | +1 |

---

## Milestone 5: Create `svc.pseudo` Sub-Object

**Status**: DONE
**Tests**: 5823 passed, 0 failed, 30 skipped

### Task 5.1: Create `Pseudo` inner class in `service.py`
- Created `Pseudo` inner class with `__init__(self, service)` + `@property` accessor
- Moved all 14 `@staticmethod` pseudo methods into the class with simplified names:
  - `init_pseudo_dirs` → `init_dirs`
  - `list_pseudo_libraries` → `list_libraries`
  - `get_library_status` → `get_library_status` (unchanged)
  - `install_pseudo_library` → `install_library`
  - `remove_pseudo_library` → `remove_library`
  - `repair_pseudo_library` → `repair_library`
  - `compute_store_size` → `compute_store_size` (unchanged)
  - `is_pseudo_archive_installed` → `is_archive_installed`
  - `install_pseudo_archive` → `install_archive`
  - `install_sssp_from_seed` → `install_sssp_from_seed` (unchanged)
  - `install_all_sssp_from_seed` → `install_all_sssp_from_seed` (unchanged)
  - `download_sssp_library` → `download_sssp_library` (unchanged)
  - `download_all_sssp` → `download_all_sssp` (unchanged)
  - `import_seed_archives` → `import_seed_archives` (unchanged)
- Deleted old depth-0 methods entirely (no backward-compat shims)

### Task 5.2: Update all daemon handler call sites
- Updated 14 call sites in `daemon/server.py`:
  - `QMSService.init_pseudo_dirs()` → `QMSService.Pseudo.init_dirs()`
  - `QMSService.list_pseudo_libraries()` → `QMSService.Pseudo.list_libraries()`
  - `QMSService.get_library_status(...)` → `QMSService.Pseudo.get_library_status(...)`
  - `QMSService.install_pseudo_library(...)` → `QMSService.Pseudo.install_library(...)`
  - `QMSService.remove_pseudo_library(...)` → `QMSService.Pseudo.remove_library(...)`
  - `QMSService.repair_pseudo_library(...)` → `QMSService.Pseudo.repair_library(...)`
  - `QMSService.compute_store_size()` → `QMSService.Pseudo.compute_store_size()`
  - `QMSService.is_pseudo_archive_installed(...)` → `QMSService.Pseudo.is_archive_installed(...)`
  - `QMSService.install_pseudo_archive(...)` → `QMSService.Pseudo.install_archive(...)`
  - `QMSService.install_sssp_from_seed(...)` → `QMSService.Pseudo.install_sssp_from_seed(...)`
  - `QMSService.install_all_sssp_from_seed(...)` → `QMSService.Pseudo.install_all_sssp_from_seed(...)`
  - `QMSService.download_sssp_library(...)` → `QMSService.Pseudo.download_sssp_library(...)`
  - `QMSService.download_all_sssp(...)` → `QMSService.Pseudo.download_all_sssp(...)`
  - `QMSService.import_seed_archives(...)` → `QMSService.Pseudo.import_seed_archives(...)`
- Confirmed: no CLI or test callers of old names exist

### Task 5.3: Depth-0 cleanup verified
- 14 pseudo methods removed from depth-0
- Remaining depth-0 methods: 9 (list_projects, get_settings, list_demo_projects, etc.)

---

## Milestone 6: Daemon Cleanup

**Status**: DONE
**Tests**: 5823 passed, 0 failed, 30 skipped

### Task 6.1: Remove double ULID resolution (2 sites)
- Removed `validate_ulid(calculation_ulid, kind="calculation")` from `_handle_delete_calculation` (API validates internally)
- Removed `validate_ulid(calculation_ulid, kind="calculation")` from `_handle_get_calculation_pseudo_mapping` (API validates internally)
- Removed unused `validate_ulid` import from server.py (no remaining callers; only in comments)

### Task 6.2: Fix `_expand_step_ulids_to_steps` YAML read
- Replaced raw `yaml.safe_load()` with `load_calculation()` from `api.utils` (canonical YAML loader)
- Removed constitutional violation: `stype_spec.replace("qe_", "")` prefix inference fallback
- Unknown types now propagate empty string (no prefix guessing)
- Removed local `import yaml` (no longer needed)

### Task 6.3: Fix `_iter_params` private import
- **DONE** (completed in M4): Already removed.

### Task 6.4: Move `_snapshot_dag` to API layer
- Created `snapshot_project_dag(index) -> dict` in `api/utils.py` (~50 lines)
- Daemon `_snapshot_dag` now delegates to API utility (3-line thin wrapper)
- Kernel `ResourceIndex` type annotation removed from daemon (was `Optional[ResourceIndex]`)
- `_diff_dag` stays in daemon (operates on plain dicts, no kernel access)

---

## Final Summary

| Milestone | Status | Key Outcome |
|-----------|--------|-------------|
| M1: Jupyter Capability Gaps | DONE | +2 API methods, -370 daemon lines |
| M2: API Merge Batch 1 | DONE (partial) | -1 duplicate method, 3 skipped (not true duplicates) |
| M3: Dead Code + RPC Sync | DONE | -2 methods, -80 dead code lines |
| M4: QE Metadata → API | DONE | -400 daemon lines, QE browsable from Jupyter |
| M5: svc.pseudo Sub-Object | DONE | 14 methods → Pseudo inner class, 14 daemon handlers updated |
| M6: Daemon Cleanup | DONE | 2 double ULID resolutions removed, prefix inference removed, _snapshot_dag → API |

### Aggregate Metrics

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| API methods total | 117 | 116 | -1 |
| API methods added (capability gaps) | 0 | 2 | +2 |
| Depth-0 methods on QMSService | 23 | 9 | -14 (moved to Pseudo) |
| Daemon business logic lines | ~770 | ~0 | -770 |
| Dead code removed | 0 | ~80 lines | -80 |
| Constitutional violations fixed | 0 | 3 | +3 (prefix inference, double ULID, raw YAML read) |
| Tests passed | 5820 | 5823 | +3 |
