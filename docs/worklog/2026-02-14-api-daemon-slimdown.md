# API & Daemon Slimdown — Execution Worklog

**Date**: 2026-02-14
**Driven by**: `docs/history/reviews/api_daemon_architecture_review.md`

## Starting Metrics

| Metric | Before |
|--------|--------|
| API methods total (QVService, all depths) | 117 |
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

**Status**: TODO

---

## Milestone 4: QE Metadata Browser → API

**Status**: TODO

---

## Milestone 5: Create `svc.pseudo` Sub-Object

**Status**: TODO

---

## Milestone 6: Daemon Cleanup

**Status**: TODO
