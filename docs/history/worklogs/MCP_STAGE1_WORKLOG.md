# MCP Stage 1: Discovery Tools — Worklog

## Plan Summary (from Plan Mode)

### Objective
Add 4 read-only discovery tools to the MCP server so an agent can explore QMatSuite's engines, workflows, presets, and parameter tags.

### Code Review Findings

**Engine Registry**
- `DriverRegistry` at `core/driver_registry.py` — singleton, side-effect registration via `import quantumvitas.drivers`
- `get_all_engines()` returns 15 families, `get_driver(family)` returns driver with `display_name`, `SUPPORTED_GEN_STEPS`, `get_capabilities()`

**Workflow Templates**
- `WorkflowService` at `workflow/templates.py` — 8 templates (scf, relax, dos, bands, pdos, wannier, scf_mp2, scf_td)
- Templates use gen steps. `materialize_workflow()` in `workflow/generalized_steps.py` converts to spec steps
- Companion engines (w90) handled via `resolve_companion_step()`

**Presets**
- `variants_registry.py` — 5 dimensions: magnetism, occupations_scheme, precision, convergence, qc_precision
- `list_dimensions_for_gen_step(gen_step)` returns applicable dimensions per gen step
- `PROFILE_TO_ENUM` maps profile names to enum values per dimension
- Presets declared per gen step (not per engine) — QE-focused but dimension check is engine-agnostic

**Parameter Tag Files — 3 JSON Patterns**
| Pattern | Engines | Top-level key |
|---------|---------|---------------|
| `"tags": {...}` | VASP, ABINIT, CP2K, W90, xTB, Yambo, QMCPACK | tags |
| `"keywords": {...}` | ORCA, Gaussian | keywords |
| `"commands": {...}` | LAMMPS | commands |

QE special: module-structured JSON at `data/qe_module_parameters.json` (schema v3), `_iter_params(module)` yields params.
4 engines have NO tag files: Siesta, GPAW, Psi4, PySCF.

### Implementation Approach
- Upgrade `envelope.py` with `status` field and `make_error()`
- 4 tool files: `list_engines.py`, `list_workflows.py`, `get_presets.py`, `search_parameters.py`
- `search_index.py`: stdlib-only BM25 scorer with lazy singleton
- Wire into `server.py`, add 14 tests in `test_stage1.py`

---

## Implementation Log

### 1. envelope.py upgrade
- Added `status` parameter (default `"success"`) to `make_response()`
- Added `make_error(error_type, message, context_hint, suggestions)` returning `{"status": "error", ...}`
- Backward compatible: existing `ping` tool unchanged
- Updated `test_stage0.py`: envelope shape test expects `status` key, ping test asserts `status == "success"`

### 2. list_engines.py
- `_SYNTAX_FAMILIES` dict: hardcoded mapping of 15 engines → syntax family labels from the inputformat design doc's 8 families
- `_count_parameters()`: dynamic loader using `__import__` for all 3 JSON patterns + QE's module iteration
- Returns sorted list of engine dicts: engine, display_name, supported_gen_steps, capabilities, parameter_count, syntax_family, installed
- `installed` always `True` for now (binary detection deferred)

### 3. list_workflows.py
- Validates engine via `DriverRegistry.get_all_engines()`
- Unknown engine → `make_error("unknown_engine", ..., suggestions=[known])`
- Uses `materialize_workflow()` which handles companion engines and zero-mappings
- Catches `ValueError` from materialize to skip unsupported workflows
- Returns materialized spec_steps alongside gen_steps

### 4. get_presets.py
- Validates engine AND workflow (two-stage error reporting)
- Collects union of dimensions across all gen steps in `template.step_sequence`
- `_DIMENSION_META`: hardcoded descriptions + option labels (not stored in ParamSpace)
- Options enumerated from `PROFILE_TO_ENUM[dimension]`

### 5. search_index.py (BM25)
- `TagDoc` class: engine, tag_name, type, default, category, description, pre-tokenized
- `BM25Index`: standard Okapi BM25 (k1=1.5, b=0.75), supports engine/category filtering
- `_load_all_tag_docs()`: loads from all 11 engines with metadata
- `get_search_index()`: lazy singleton (first-call builds index)
- ~60 lines of BM25 code, stdlib only (math, re)

### 6. search_parameters.py
- Thin wrapper: clamps max_results to [1,20], calls index, formats results
- Truncates description to 200 chars for brevity
- Includes relevance_score (rounded to 3 decimal places)

### 7. server.py
- Added 4 side-effect imports for new tool modules

### 8. Test writing
- 14 tests in `test_stage1.py`, all calling `.fn()` directly on `@mcp.tool` decorated functions

**Design decision during testing**: Initial `test_get_presets_lammps_no_presets` test assumed LAMMPS + relax would have no presets. But preset dimensions are declared per gen step (not per engine), so `relax` has dimensions even for LAMMPS. Replaced with `test_get_presets_dimension_has_options` which tests option structure quality.

---

## Files Created (7 new)

| File | Lines | Purpose |
|------|-------|---------|
| `src/quantumvitas/mcp/tools/list_engines.py` | ~95 | list_engines tool |
| `src/quantumvitas/mcp/tools/list_workflows.py` | ~55 | list_workflows tool |
| `src/quantumvitas/mcp/tools/get_presets.py` | ~115 | get_presets tool |
| `src/quantumvitas/mcp/tools/search_parameters.py` | ~50 | search_parameters tool |
| `src/quantumvitas/mcp/search_index.py` | ~195 | BM25 index + tag loading |
| `tests/mcp/conftest.py` | ~5 | Skip MCP tests when fastmcp not installed |
| `tests/mcp/test_stage1.py` | ~150 | 14 Stage 1 tests |

## Files Modified (3 existing)

| File | Change |
|------|--------|
| `src/quantumvitas/mcp/envelope.py` | Added `status` field + `make_error()` |
| `src/quantumvitas/mcp/server.py` | 4 new tool module imports |
| `tests/mcp/test_stage0.py` | Updated envelope shape + ping status assertions |

## Test Results

```
tests/mcp/test_stage0.py  — 6 passed (all green, no regressions)
tests/mcp/test_stage1.py  — 14 passed
Full suite               — 5680 passed, 4 skipped, 0 failed
```

### CI Fix: fastmcp dependency skip

CI installs `pip install -e '.[dev]'` which does NOT include the `[mcp]` optional extra.
All MCP tests failed with `ModuleNotFoundError: No module named 'fastmcp'`.

**Fix**: Added `tests/mcp/conftest.py` with `pytest.importorskip("fastmcp")`.
This skips the entire `tests/mcp/` directory when `fastmcp` is not installed,
matching the pattern used for other optional dependencies (`requires_orca`, `requires_pyscf`).

## Issues / Notes for Stage 2

1. **Presets are gen-step-scoped, not engine-scoped**: `get_presets()` returns preset dimensions for any engine+workflow whose gen steps have variants, even when those presets are only meaningful for QE (pw.x). A future enhancement could annotate dimensions with applicable engines.

2. **`installed` field is always `True`**: Real binary detection is deferred. The `installed_only` parameter is a no-op.

3. **QE metadata path**: QE parameters JSON is at `data/qe_module_parameters.json` (under `src/quantumvitas/data/`), not under `drivers/qe/data/`. The `qe_metadata.py` module handles this via `importlib.resources`.

4. **Search index size**: ~1000 documents from 11 engines. Performance is not a concern at this scale, but if engines grow significantly, consider caching the serialized index.

5. **No modification tools yet**: All 4 tools are read-only discovery. Stage 2-3 will add configuration and execution tools.
