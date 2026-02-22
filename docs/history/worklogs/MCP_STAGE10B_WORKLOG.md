# MCP Stage 10B: Provenance Audit — Worklog

**Status**: DONE
**Date**: 2026-02-18

---

## Plan (Fix A — per-calculation `demo_origin`)

### Problem

`load_demo_as_calculation()` records NO provenance events. All three SSOT writes
(step YAML, calculation.yaml, project.qms.yml) pass no `OperationContext` to
`save_yaml_doc()`. Additionally, unlike `create_demo_project()` which sets a
project-level `demo_source` in settings (S11), `load_demo_as_calculation()` has
no equivalent metadata — so `get_reference_analysis()` cannot find ref packs
for demo-loaded calculations in non-demo projects.

### Proposed Fix

Add a `demo_origin` field to `CalculationModel` for per-calculation demo tracking:

1. **`src/qmatsuite/core/models.py`** — Add `demo_origin: dict | None = None`
   to `CalculationModel`, include in `to_dict()` / `from_dict()` serialization.

2. **`src/qmatsuite/api/service.py`** — In `load_demo_as_calculation()`, set
   `calc_model.demo_origin` before `save_calculation()`:
   ```python
   calc_model.demo_origin = {
       "demo_id": demo_id,
       "engine": engine,
       "materialized_at": datetime.now(timezone.utc).isoformat(),
   }
   ```

3. **`src/qmatsuite/api/service.py`** — In `get_reference_analysis()`, also
   check `calculation.demo_origin.demo_id` (not just project-level
   `settings.demo_source`).

4. **`tests/mcp/test_stage10.py`** — Add 4 new tests:
   - `test_load_demo_has_demo_origin`
   - `test_regular_calc_no_demo_origin`
   - `test_demo_origin_preserved_on_reload`
   - `test_get_reference_analysis_via_calc_demo_origin`

### What we explicitly do NOT fix now

- Full opctx provenance (systemic Law P2 migration — not piecemeal)
- S5.6 full compliance (SHOULD, not MUST — Fix A provides partial compliance)

---

## Implementation Log

### Step 1: Add `demo_origin` to `CalculationModel` (models.py)

- Added `demo_origin: Optional[Dict[str, Any]] = None` field to `CalculationModel`
  dataclass, after `potential_map`
- Added serialization to `to_dict()`: writes `demo_origin` only when non-None
- Added deserialization to `from_dict()`: reads `data.get("demo_origin")`
- Threaded `demo_origin=demo_origin` through to the `cls()` constructor

### Step 2: Set `demo_origin` in `load_demo_as_calculation()` (service.py)

- In `load_demo_as_calculation()`, set `demo_origin` in the `CalculationModel`
  constructor (before save):
  ```python
  demo_origin={
      "demo_id": demo_id,
      "engine": engine,
      "materialized_at": datetime.now(timezone.utc).isoformat(),
  }
  ```
- Import `datetime, timezone` from stdlib at the point of use

### Step 3: Update `get_reference_analysis()` (service.py)

- Added Strategy 2 fallback: if project-level `demo_source` is absent or has
  no `demo_id`, resolve the calculation and check `calc_model.demo_origin`
- Flow: project `demo_source` → calc `demo_origin` → None
- Wrapped in try/except so resolution failures don't break the method

### Step 4: Add 4 new tests (test_stage10.py)

Added `TestDemoOrigin` class with 4 tests:

1. **`test_load_demo_has_demo_origin`** — Loads `qe_si_scf`, reads
   `calculation.yaml`, asserts `demo_origin` has correct `demo_id`, `engine`,
   and valid ISO 8601 `materialized_at`

2. **`test_regular_calc_no_demo_origin`** — Creates a manual `CalculationModel`,
   saves/reloads, asserts `demo_origin is None`

3. **`test_demo_origin_preserved_on_reload`** — Loads demo, reloads via
   `load_calculation()`, asserts `demo_origin` roundtrips correctly

4. **`test_get_reference_analysis_via_calc_demo_origin`** — Loads a demo with
   a ref pack into a non-demo project, calls `svc.analysis.get_reference_analysis()`,
   asserts ref pack is found via `demo_origin` fallback

---

## Files Modified

| File | Change |
|------|--------|
| `src/qmatsuite/core/models.py` | Added `demo_origin` field + serialization |
| `src/qmatsuite/api/service.py` | Set `demo_origin` in `load_demo_as_calculation()`, added fallback in `get_reference_analysis()` |
| `tests/mcp/test_stage10.py` | Added `TestDemoOrigin` class (4 tests) |

## Test Results

- **Stage 10 tests**: 187 passed (183 existing + 4 new)
- **Full suite**: 5984 passed, 4 skipped, 0 failed
