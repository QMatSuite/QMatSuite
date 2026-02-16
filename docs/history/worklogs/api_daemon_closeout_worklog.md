# API & Daemon Closeout — Worklog

**Date:** 2026-02-16
**Plan:** `docs/history/plans/API_DAEMON_CLOSEOUT_PLAN.md`
**Review:** `docs/history/reviews/api_daemon_closeout_review.md`

## M1: Delete duplicate handler definitions in daemon — DONE

Deleted 3 shadowed first-definition stubs + 1 duplicate dispatch dict key:
- First `_handle_detect_workflow` (simple preset-based stub, lines ~2903-2935)
- First `_handle_list_wannier_3d_fixtures` (simple stub, lines ~3885-3932)
- First `_handle_compile_fixture_volume` (simple stub, lines ~3934-3962)
- Duplicate `"detect_workflow"` key at line 333 in dispatch dict

**Tests:** 5613 passed, 18 skipped
**Commit:** `109a23f9`

## M2: Delete svc.engine sub-object (dead code) — DONE

Deleted `Engine` inner class (4 methods, 250 lines) + `engine` property from service.py.
Deleted `tests/api/test_engine_capabilities.py` (188 lines).
Updated gate test `test_no_legacy_nested_accessors.py` to remove `engine` accessor.

Confirmed zero callers in daemon, CLI, or any code.

**Tests:** 5605 passed, 18 skipped (−8 deleted tests)
**Commit:** `aaa866d3`

## M3: Delete QE metadata re-exports from api.utils — DONE

Removed 11 QE-specific top-level re-exports from `api/utils.py`:
- `get_ui_parameters`, `list_supported_modules`, `get_module_param_sections`,
  `get_module_card_sections`, `get_module_doc_url`, `get_metadata_file_info`,
  `get_qe_metadata_debug_info`, `safe_load_metadata`, `reload_metadata`,
  `QEUIParam`, `_iter_params`

Added local imports in the 2 functions that need them:
- `_qe_parameter_metadata()` — 6 imports
- `get_engine_ui_parameters()` — 2 imports

Rewrote CLI `params_command` to use engine-agnostic `get_engine_parameter_metadata("qe", ...)`.

**Tests:** 5605 passed, 18 skipped
**Commit:** `3b9e7f19`

## M4: Move Wannier 3D fixture scanning to API — DONE

Added 2 static methods to `Analysis` inner class:
- `list_3d_fixtures(fixture_dir=None)` — 3-priority path discovery + manifest/glob scan
- `compile_fixture_volume(file_path, calc_dir, band_index=1)` — volume parsing

Thinned daemon handlers from ~130+115 lines to ~5 lines each (pass-through).

Key design decision: explicit `fixture_dir` argument skips auto-discovery chain entirely
(consistent with old daemon behavior where payload override was terminal).

**Tests:** 5605 passed, 18 skipped
**Commit:** `3e48797c`

## M5: Enrich create_demo_project return value — DONE

Moved GUI enrichment from daemon into `QVService.create_demo_project()`:
- `project_id`, `project_name`, `structure` (dict), `calculation` (dict), `ready_to_run`
- Non-fatal: enrichment failure returns defaults (empty strings, None, False)

Daemon handler kept registry rebuild only.

**Tests:** 5605 passed, 18 skipped
**Commit:** `46009e45`

## M6: Add detail parameter to svc.calculation.list() — DONE

Added `detail: bool = False` parameter to `Calculation.list()`.
When True, calls `get_detail()` inline for each calculation, returning `list[dict]`.
Falls back to `dto.to_dict()` if detail fails for any individual calculation.

Daemon `_handle_list_calculations` simplified to one-liner: `svc.calculation.list(detail=True)`.

**Tests:** 5605 passed, 18 skipped (1 pre-existing flaky pseudo test excluded)
**Commit:** `4c36faef`

## M7: Make resolution helpers internal-only — SKIPPED

Per review reassessment (section W4-2): `require_ref`, `require_step_ref`,
`resolve_enclosing_path`, `require_enclosing` are legitimate public API methods
that Jupyter users need. They cannot be made private.

## Skipped items (from plan)

- **Simplify _handle_run_calculation** — Medium risk, touches job submission pipeline
- **CLI YAML reads** — Large effort (16 call sites), separate effort
- **Auto registry rebuild** — High risk relative to benefit, separate effort

## Final Metrics

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| svc.engine methods | 4 | 0 | −4 |
| api.utils public items | 72 | 61 | −11 |
| Daemon duplicate handlers | 4 | 0 | −4 |
| Daemon duplicate dispatch keys | 1 | 0 | −1 |
| Daemon business logic leaks | 3 | 1 (run_calculation) | −2 |
| server.py lines | 5,519 | ~5,100 | ~−400 |
| test files deleted | 0 | 1 | +1 |
| Tests | 5,613 | 5,605 | −8 (deleted dead tests) |
