# API & Daemon Closeout Review

**Date:** 2026-02-16
**Scope:** Post-slimdown, post-compat-removal comprehensive audit
**Baseline:** `api_daemon_architecture_review.md` (2026-02-14)
**Codebase state:** 5,631 tests collected, all green

---

## A1. Updated Metrics

| Metric | Original (2026-02-14) | Current | Delta |
|--------|----------------------|---------|-------|
| **Total API methods (all depths)** | 117 | 125 | +8 |
| **Depth-0 methods on QVService** | 23 | 18 | -5 |
| **Depth-1 sub-objects** | 8 | 9 | +1 (`pseudo`) |
| **Depth-1 methods (total)** | 94 | 107 | +13 |
| **api.utils public functions** | ~65 | 72 | +7 |
| **api.utils total lines** | 2,262 | 2,685 | +423 |
| **RPC endpoint count** | 120 (118 unique) | 122 entries (120 unique, 2 dup keys) | ~same |
| **Daemon internal helpers** | ~35 | ~24 | -11 |
| **compat.py** | 1,011 lines | **DELETED** | -1,011 |
| **server.py lines** | 6,409 | 5,519 | -890 |
| **service.py lines** | 8,610 | 8,988 | +378 |
| **cli/main.py lines** | 5,374 | 5,374 | 0 |
| **Total (4 key files)** | 24,373 | 22,566 | -1,807 |
| **DTO types** | 18 | 9 (exported) | -9 |
| **Tests** | not tracked | 5,631 | — |

### Method count detail

**Depth-0 on QVService (18):**
- 9 properties (sub-object accessors): `analysis`, `structure`, `online_search`, `calculation`, `run`, `project`, `engine`, `history`, `pseudo`
- 9 static methods: `init_project`, `get_settings`, `get_workflow_service`, `run_single_step`, `get_default_step_params`, `resolve_step_type_spec`, `generate_kpath`, `create_demo_project`, `list_demo_projects`

**Depth-1 breakdown:**

| Sub-object | Methods | Change from original |
|------------|---------|---------------------|
| `svc.analysis` | 11 | -1 (analyze_scf removed from direct) |
| `svc.structure` | 12 | +1 (`import_online` added) |
| `svc.online_search` | 5 | +1 (`get_candidate_detail` added) |
| `svc.calculation` | 35 | ~same |
| `svc.run` | 5 | ~same |
| `svc.project` | 12 | -1 |
| `svc.engine` | 4 | same |
| `svc.history` | 9 | same |
| `svc.pseudo` | 14 | **NEW** (moved from depth-0) |
| **Total depth-1** | **107** | — |

### Commentary on metric deltas

The total API method count went UP (+8) rather than down, for two reasons:
1. **svc.pseudo created** (+14 methods at depth-1, -13 statics at depth-0): net +1 but better organized
2. **Capability gaps closed** (+2): `svc.structure.import_online()`, `svc.online_search.get_candidate_detail()`
3. **api.utils grew** (+7 functions, +423 lines): engine metadata browsing was moved FROM daemon TO api.utils, increasing its size

The compat.py deletion (-1,011 lines) and daemon cleanup (-890 lines) more than offset the growth. Total across key files: **-1,807 lines**.

---

## A2. Wave 4 Items — Current State Assessment

### W4-1: api.utils QE re-exports (9 functions + 2 extras)

**Current state:** Still present at `api/utils.py:618-634`.

```python
from quantumvitas.drivers.qe.data.qe_metadata import (
    get_ui_parameters, list_supported_modules, get_module_param_sections,
    get_module_card_sections, get_module_doc_url, get_metadata_file_info,
    get_qe_metadata_debug_info, safe_load_metadata, reload_metadata,
    QEUIParam, _iter_params,
)
```

**Callers:**
- **CLI** (`main.py:50-53`): imports `get_module_doc_url`, `get_module_param_sections`, `list_supported_modules` — used in QE-specific `show` command for parameter documentation links
- **Daemon**: zero direct imports of these re-exports (engine handlers use `get_engine_parameter_metadata` and `get_engine_ui_parameters` instead)
- **Tests**: not checked yet, likely some

**Assessment:**
- 3 of 11 re-exports are used by CLI for QE-specific display functionality
- The remaining 8 (`get_ui_parameters`, `get_module_card_sections`, `get_metadata_file_info`, `get_qe_metadata_debug_info`, `safe_load_metadata`, `reload_metadata`, `QEUIParam`, `_iter_params`) have no external callers in daemon or CLI
- The 3 CLI-used functions could be replaced by calling `get_engine_parameter_metadata(engine_family="qe", ...)` instead
- **Effort: S** | **Risk: Low** | **Reduces utils count: -11 items**

### W4-2: Resolution helpers — make internal or remove

**Current state:** These are methods ON the sub-objects, not standalone functions:
- `svc.structure.require_ref()` — on Structure inner class
- `svc.calculation.require_ref()` — on Calculation inner class
- `svc.calculation.require_step_ref()` — on Calculation inner class
- `svc.calculation.resolve_enclosing_path()` — on Calculation inner class
- `svc.calculation.require_enclosing()` — on Calculation inner class

**Callers:**
- **Daemon** (`server.py`): wraps `require_ref` and `require_step_ref` in its own `_require_calculation_ref`, `_require_structure_ref`, `_require_step_ref` helpers — legitimate use
- **CLI** (`main.py`): ~40 direct calls to `svc.calculation.require_ref()`, `svc.structure.require_ref()`, `svc.calculation.require_step_ref()`, `svc.calculation.resolve_enclosing_path()` scattered across many commands

**Assessment:** These are heavily used by both daemon and CLI. They ARE public API — resolving a selector to a concrete reference is a core API capability that Jupyter users also need. **Cannot be made private.** The original review was wrong to flag these as internal plumbing.

**Recommendation:** Keep as-is. No action needed. **Remove from Wave 4 list.**

### W4-3: svc.engine sub-object — remove if unused

**Current state:** 4 methods: `list()`, `get_info()`, `list_step_types()`, `validate_installation()`.

**Callers:**
- **Daemon**: ZERO calls to `svc.engine.*`. Engine RPC handlers call `api.utils` functions directly (`list_engine_families`, `get_step_palette`, `get_engine_ui_parameters`, `get_engine_parameter_metadata`)
- **CLI**: ZERO calls to `svc.engine.*`
- **Tests**: ZERO calls to `svc.engine.*`
- **Internal (service.py)**: The methods are defined but never called by other API methods

**Assessment:** `svc.engine` is confirmed dead code. The engine capabilities exist in `api.utils` (where daemon calls them) but the sub-object wrapper is never used by anyone.

Two options:
1. **Delete svc.engine entirely** — it's dead code, the capabilities live in api.utils
2. **Wire daemon engine handlers to use svc.engine** instead of api.utils — proper layering but more work

**Recommendation:** Delete svc.engine. The `api.utils` functions serve the same purpose and are already wired. If we later want to consolidate, we can recreate it.
- **Effort: S** | **Risk: Low** | **Reduces method count: -4**

### W4-4: Auto registry rebuild

**Current state:** `_rebuild_registry_after_write` is called in 3 places in daemon:
1. After `save_relax_final_structure` (line 2765)
2. After `create_demo_project` (line 3597)
3. In one handler that needs fresh index (line 4803)

Plus `svc.project.build_resource_index()` is called directly in:
1. `__init__` cache initialization (line 130)
2. Cache rebuild (line 152)
3. `_rebuild_registry_after_write` implementation (line 4865)

**Assessment:** The rebuild pattern has already been largely cleaned up (only 3 explicit rebuild calls remain in handlers, down from "scattered" in the original review). The remaining calls are after mutations that create filesystem-level changes that the API can't easily auto-detect (demo project creation changes multiple files, relax structure save creates a new structure).

**Recommendation:** Low priority. The current pattern is manageable. Making `build_resource_index()` private would break the 3 daemon call sites without clear benefit. **Skip for now.**
- **Effort: M** | **Risk: Med** | **Benefit: Low**

### W4-5: api.utils general cleanup

**Current state:** 72 public functions, 2,685 lines.

**Functions by category:**

| Category | Count | Notes |
|----------|-------|-------|
| Resource/slug/name handling | 7 | Core utilities, all used by CLI |
| Structure I/O | 4 | Used by CLI and daemon |
| Calculation templates | 3 | Used by CLI and daemon |
| QE input handling | 7 | QE-specific, used by CLI |
| Calculation model/YAML | 4 | Used by CLI and daemon |
| ULID validation | 2 | Used everywhere |
| Engine registry/metadata | 7 | Used by daemon (engine RPCs) |
| QE metadata re-exports | 11 | **Mostly dead** (see W4-1) |
| Pseudo management | 6 | Used by daemon |
| QE engine config | 2 | Used by daemon |
| Visualization | 3 | Used by daemon and CLI |
| Online search | 4 | Used by daemon |
| Presets | 5 | Used by daemon |
| Blob/journal | 4 | Used by daemon |
| Path context | 2 | Used by CLI |
| Calc I/O/directory | 4 | Used by CLI |
| Analysis/plotting | 7 | Used by CLI |
| Project snapshot | 4 | Used by CLI |
| Settings | 1 | Used by daemon |

**Dead code candidates** (functions not imported by daemon, CLI, or service.py):
- Needs deeper analysis per-function with test cross-reference. Based on import scanning:
  - All 11 QE re-exports have limited usage (see W4-1)
  - `get_qe_home` — used by CLI only (1 site)
  - `create_default_registry` — used by CLI only (2 sites)

**Recommendation:** Remove the 11 QE re-exports (W4-1). Leave the rest for now — they serve legitimate roles as CLI utilities and Jupyter-facing functions.
- **Effort: M** | **Risk: Low** | **Reduces utils count: -11**

---

## A3. New Issue Scan

### A3.1 Duplicate method definitions in server.py

**CRITICAL:** Two methods are defined TWICE in the QVDaemon class:

1. `_handle_detect_workflow` — defined at line 2903 AND line 5303. The second definition silently shadows the first. The dict registers the key twice (lines 333 and 389), so the LAST dict entry wins (line 389, pointing to the shadowed method at line 5303). The first definition (line 2903) is dead code.

2. `_handle_list_wannier_3d_fixtures` — defined at line 3885 AND line 4017. The second (longer, more robust) version shadows the first.

3. `_handle_compile_fixture_volume` — likely also duplicated (second definition at line 4146+ area).

**Impact:** The duplicate `detect_workflow` entry in the dispatch dict means the key appears twice — the second one wins. The old handler (line 2903, simple preset-based detection) is dead. The new one (line 5303, workflow service based) is the active one.

**Recommendation:** Delete the shadowed (dead) first definitions of all three.
- **Effort: S** | **Risk: Low**

### A3.2 Engine RPC handlers bypass svc.engine

The 5 engine RPC handlers (`_handle_list_engine_families`, `_handle_list_step_palette`, `_handle_list_engine_ui_parameters`, `_handle_list_engine_parameter_metadata`, `_handle_set_engine_family`) call `api.utils` functions directly instead of going through `svc.engine`. This is an architectural smell but since we're recommending deleting `svc.engine` (W4-3), it's moot.

### A3.3 Daemon _handle_run_calculation contains significant business logic

Lines 4268-4372 (~105 lines): The `_handle_run_calculation` handler:
- Loads calculation.yaml directly via `load_calculation()`
- Iterates steps, builds initial_steps list with dict surgery (`to_dict()`, selective key removal)
- Generates ULID for job_id
- Computes `io_dir` using `compute_io_dir_from_calculation_model()`
- Creates a `run_calculation_wrapper` closure
- Calls `job_manager.submit_with_id()` with 13+ keyword arguments

This is the **single largest remaining business logic leak** in the daemon. A Jupyter user who wants to run a calculation and get initial step status cannot replicate this logic.

**Recommendation:** Move the step initialization and io_dir computation into `svc.run.run_calculation()` or a new `svc.run.prepare_run()` method that returns the enriched job info. The daemon handler should just call the API and pass the result to job_manager.
- **Effort: M** | **Risk: Med**

### A3.4 Daemon _handle_create_demo_project enriches response

Lines 3576-3647: After calling `QVService.create_demo_project()`, the handler:
- Rebuilds registry
- Enriches response with GUI-specific fields: structures list, calculations list with expanded detail
- Adds `project_root` field

This is moderate business logic (response enrichment for GUI). A Jupyter user calling `QVService.create_demo_project()` gets a less detailed response.

**Recommendation:** Move the enrichment into the API method itself (the create_demo_project static method should return all the data the GUI needs).
- **Effort: S** | **Risk: Low**

### A3.5 Daemon _handle_detect_workflow_for_calculation has complex selector resolution

Lines 5330-5470+: This handler contains ~140 lines of:
- Dual selector resolution (calculation_ulid vs calculation)
- Logging and error handling boilerplate
- Dict construction for the response

The core logic (calling workflow service) is small, but the wrapper is disproportionately large.

**Recommendation:** Low priority — the logic is mostly selector resolution + error handling which is daemon's job.
- **Effort: S** | **Risk: Low**

### A3.6 CLI direct YAML reads: 16 remain

The CLI reads YAML files directly in 16 places (same as original review). Key offenders:

1. `init_step_command()` — reads calculation.yaml to find structure and step list (2 reads)
2. `_find_calculation_structures()` — reads calculation.yaml to extract structure refs (2 reads)
3. `_calculation_step_summaries()` — reads calculation.yaml + step.yaml files (3 reads)
4. `configure_step_command()` — reads step.yaml, modifies, writes back (2 reads)
5. `configure_calculation_command()` — reads calculation.yaml directly (3 reads)
6. `run_calculation_command()` — reads calculation.yaml for pre-run validation (1 read)
7. `analyze_output_command()` — reads step.yaml and calculation.yaml (2 reads)

**Assessment:** Most of these could use `svc.calculation.get_detail()` or `svc.calculation.get_step_detail()` instead. However, the CLI also WRITES yaml (configure commands), which is a deeper issue — the API has `update_step_params` but the CLI's configure flow is more complex (interactive, with card/species overrides).

**Recommendation:** Defer to a separate CLI refactoring effort. The 16 YAML reads are a known debt but fixing them requires reworking CLI configure flows which is a larger task.
- **Effort: L** | **Risk: Med**

### A3.7 Duplicate RPC dispatch key: detect_workflow

The `_handlers` dict has `"detect_workflow"` registered TWICE (lines 333 and 389). Python dicts silently override — the second entry wins. This is a bug (the first registration is dead).

**Recommendation:** Remove the first registration at line 333 and the dead first handler definition.
- **Effort: S** | **Risk: Low**

### A3.8 Wannier 3D fixture scanning — still in daemon

The `_handle_list_wannier_3d_fixtures` handler (lines 4017-4155, ~138 lines) contains substantial filesystem scanning logic:
- 3-priority path discovery (env var → repo derivation → dev fallback)
- manifest.json reading
- Recursive glob for *.xsf/*.bxsf
- Metadata extraction

This is business logic that belongs in the API layer.

**Recommendation:** Move to `svc.analysis.list_3d_fixtures()` or similar. Daemon handler becomes thin passthrough.
- **Effort: M** | **Risk: Low**

### A3.9 _handle_list_calculations enriches with get_detail() loop

Lines 1540-1567: The handler loops through calculation DTOs and calls `get_detail()` for each one, enriching the list response. This was added post-compat-removal to give the GUI the data it needs.

This is acceptable short-term but means:
- The `svc.calculation.list()` method returns less data than the GUI needs
- The daemon compensates by calling `get_detail()` N times

**Recommendation:** Consider making `svc.calculation.list()` accept a `detail=True` parameter that includes all fields the GUI needs, eliminating the N+1 query pattern.
- **Effort: S** | **Risk: Low**

---

## A4. Capability Gap Re-check

### Workflow 1: Load demo → run → analyze → plot

| Step | API Method | Status |
|------|-----------|--------|
| List demos | `QVService.list_demo_projects()` | OK |
| Create demo | `QVService.create_demo_project()` | OK |
| Run calculation | `svc.run.run_calculation()` | OK |
| Check run status | `svc.run.list_runs()` | OK |
| Get step digest | `svc.analysis.get_step_digest()` | OK |
| Get SCF analysis | `svc.analysis.get_analysis()` | OK |
| Plot SCF | `api.utils.plot_scf_convergence()` | OK |
| Plot bands | `api.utils.plot_bands()` | OK |
| Plot DOS | `api.utils.plot_dos()` | OK |

**Status: FULLY COVERED**

### Workflow 2: Create project → import structure → create calc → add steps → configure → run → analyze

| Step | API Method | Status |
|------|-----------|--------|
| Create project | `QVService.init_project()` | OK |
| Import local structure | `svc.structure.import_file()` | OK |
| Search online structures | `svc.online_search.search_structures()` | OK |
| Preview online candidate | `svc.online_search.get_candidate_detail()` | OK |
| Import online structure | `svc.structure.import_online()` | OK |
| Create calculation | `svc.calculation.create()` | OK |
| Set engine | `svc.calculation.set_engine_family()` | OK |
| Add steps | `svc.calculation.add_step()` | OK |
| Configure step params | `svc.calculation.update_step_params()` | OK |
| Configure pseudo | `svc.calculation.set_step_pseudo_mapping()` | OK |
| Preflight check | `svc.run.preflight()` | OK |
| Run calculation | `svc.run.run_calculation()` | OK |
| Get results | `svc.analysis.get_step_digest()` | OK |
| Get analysis | `svc.analysis.get_analysis()` | OK |
| Plot | `api.utils.plot_*()` | OK |

**Status: FULLY COVERED** — All critical gaps from the original review have been closed.

### Remaining minor gaps (not blocking either workflow):

1. **No `svc.project.delete()` method** — CLI has `delete_project_command()` but it operates directly on filesystem. Low severity since project deletion is rare.
2. **No API method for 3D fixture listing** — Wannier 3D fixtures are served by daemon-only handler. Only affects 3D volume visualization workflow.
3. **Job management detail** — `svc.run.run_calculation()` returns less information than the daemon's enriched version (no initial_steps, no io_dir). Jupyter users get a working run but less status detail.

---

## A5. Priority-Ordered Action List

| # | Action | Effort | Risk | Method Δ | Utils Δ |
|---|--------|--------|------|----------|---------|
| 1 | **Delete duplicate handlers** (detect_workflow ×2, wannier_fixtures ×1, compile_fixture ×1) + fix dispatch dict duplicate key | S | Low | 0 | 0 |
| 2 | **Delete svc.engine sub-object** (confirmed dead code) | S | Low | -4 | 0 |
| 3 | **Delete QE metadata re-exports** from api.utils (11 items); update 3 CLI call sites to use `get_engine_parameter_metadata()` | S | Low | 0 | -11 |
| 4 | **Move Wannier 3D fixture scanning** from daemon to API (`svc.analysis`) | M | Low | +1 | 0 |
| 5 | **Simplify _handle_run_calculation** — move step init + io_dir computation to API | M | Med | 0 | 0 |
| 6 | **Enrich create_demo_project return** — move GUI enrichment from daemon into API | S | Low | 0 | 0 |
| 7 | **Add detail mode to svc.calculation.list()** — eliminate N+1 get_detail loop in daemon | S | Low | 0 | 0 |
| 8 | **CLI YAML reads** — replace 16 direct YAML reads with API calls | L | Med | 0 | 0 |

### Expected final metrics after actions 1-7:

| Metric | Current | After | Delta |
|--------|---------|-------|-------|
| Total API methods | 125 | 122 | -3 |
| api.utils functions | 72 | 61 | -11 |
| Daemon duplicate handlers | 4 | 0 | -4 |
| Daemon business logic leaks | 3 significant | 0 | -3 |
| RPC duplicate keys | 1 | 0 | -1 |

---

## Appendix: File Size Summary (current)

| File | Lines |
|------|-------|
| `src/quantumvitas/api/service.py` | 8,988 |
| `src/quantumvitas/api/utils.py` | 2,685 |
| `src/quantumvitas/daemon/server.py` | 5,519 |
| `src/quantumvitas/daemon/compat.py` | **DELETED** |
| `src/quantumvitas/daemon/jobs.py` | ~707 |
| `src/quantumvitas/cli/main.py` | 5,374 |
| **Total** | **~23,273** |

## Appendix: RPC Handler Dispatch (122 entries, 120 unique)

Duplicate keys in dispatch dict:
1. `"detect_workflow"` — registered at line 333 AND line 389 (second wins)

Duplicate handler method definitions:
1. `_handle_detect_workflow` — defined at line 2903 AND line 5303
2. `_handle_list_wannier_3d_fixtures` — defined at line 3885 AND line 4017
3. `_handle_compile_fixture_volume` — defined at line 3934 AND line ~4146+

## Appendix: DTO Types (exported)

| DTO | Module |
|-----|--------|
| `BaseDTO` | `types/base.py` |
| `MetaDTO` | `types/common.py` |
| `CandidateSummary` | `types/common.py` |
| `ErrorDTO` | `types/error.py` |
| `CalculationDTO` | `types/calculation.py` |
| `CalculationRefDTO` | `types/calculation.py` |
| `StepDTO` | `types/calculation.py` |
| `StructureDTO` | `types/structure.py` |
| `RunResultDTO` | `types/run.py` |
| `AnalysisRefDTO` | `types/analysis.py` |
| `AnalysisSummaryDTO` | `types/analysis.py` |
