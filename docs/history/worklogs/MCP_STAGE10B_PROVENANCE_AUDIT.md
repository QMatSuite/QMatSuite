# MCP Stage 10B: Provenance Audit for load_demo_as_calculation

**Status**: Investigation complete — awaiting review

## Question

Does `load_demo_as_calculation()` record provenance for the demo-loaded calculation?

---

## 1. Current State

### Evidence: `load_demo_as_calculation()` records NO provenance

The method (service.py:8605-8880) makes three SSOT-writing calls, none of which pass an `OperationContext`:

| Call | Line | opctx? | Notes |
|------|------|--------|-------|
| `save_yaml_doc(step_doc, step_file, skip_journal=True)` | 8836 | **NO** | Step YAML files — `skip_journal=True`, no opctx arg |
| `save_calculation(calc_model, ...)` | 8851 | **NO** | Calls `save_yaml_doc()` internally at models.py:520 without opctx |
| `save_project(project_model, ...)` | 8865 | **NO** | Calls `save_yaml_doc()` internally at models.py:955 without opctx |

**Why this means no provenance**: `save_yaml_doc()` (yaml_io.py:141-270) only records provenance when `opctx is not None` (line 243). Since all three calls pass no opctx, the provenance timeline has zero record of this operation.

### The `save_yaml_doc()` gate

```python
# yaml_io.py:243
if opctx is not None:
    # ... record_operation_event() ...
```

The `opctx` parameter is currently **optional** (line 144: `Optional["OperationContext"]`). The docstring notes this is "optional for migration" and "will become required once all callers are updated" — indicating Law P2 enforcement is deferred.

---

## 2. Comparison with create_demo_project()

### `create_demo_project()` also records NO event-based provenance

The method (service.py:8420-8505) calls `materialize_project_from_snapshot()` (snapshot.py:522-870), which makes the same pattern of opctx-less writes:

| Call | File:Line | opctx? |
|------|-----------|--------|
| `save_yaml_doc(step_doc, step_file, skip_journal=True)` | snapshot.py:831 | **NO** |
| `save_calculation(calculation_model, ...)` | snapshot.py:844 | **NO** |
| `save_project(project_model, ...)` | snapshot.py:859 | **NO** |

### However, `create_demo_project()` DOES set `demo_source` metadata (S11)

After `materialize_project_from_snapshot()` returns, `create_demo_project()` injects a `demo_source` dict into the project's `settings` via `save_project_config()` (service.py:8464-8495):

```yaml
settings:
  demo_source:
    demo_id: "vasp_si_scf"
    generator_digest: "abc123..."
    engine: "vasp"
    materialized_at: "2026-02-18T12:00:00+00:00"
```

This `demo_source` field is:
- **Defined** in DEMO_STORE_SPEC.md S11.2
- **Written** by `create_demo_project()` at materialization time
- **Read** by `get_reference_analysis()` (service.py:1310-1317) to locate ref packs
- **Constraint C1**: No SQLite/CAS/provenance dependency — pure filesystem field

### Key distinction

| Aspect | `create_demo_project()` | `load_demo_as_calculation()` |
|--------|------------------------|------------------------------|
| Event-based provenance (opctx) | NO | NO |
| `demo_source` metadata (S11) | YES — written to `project.qms.yml:settings` | NO |
| Scope | Creates new project | Loads into existing project |

---

## 3. Gap Analysis

### Gap 1: No `demo_source` equivalent for per-calculation demo tracking

`create_demo_project()` writes `demo_source` at the **project level** because the entire project is a demo. But `load_demo_as_calculation()` operates within an existing project — potentially a non-demo project. There is no per-calculation `demo_source` field.

**Impact**: After loading a demo into a project, there is no metadata recording which calculation came from which demo. The `get_reference_analysis()` method only checks project-level `settings.demo_source`, so ref pack lookup won't work for demo-loaded calculations in non-demo projects.

### Gap 2: No opctx for provenance timeline (systemic, not demo-specific)

This is a **systemic gap** — not unique to `load_demo_as_calculation()`. The following high-level functions also skip opctx:

- `save_calculation()` (models.py:520)
- `save_project()` (models.py:955)
- `materialize_project_from_snapshot()` (snapshot.py:831/844/859)

The codebase is in a **migration phase**: Law P2 ("OperationContext Required") is defined but not enforced. The `opctx` parameter on `save_yaml_doc()` remains optional.

### Gap 3: S5.6 compliance

DEMO_STORE_SPEC.md S5.6 says:

> **SHOULD**: When loading a demo snapshot and materializing it into a project, the system SHOULD record in its provenance store [...] that the project originated from a demo snapshot.

This is a SHOULD (recommendation), not a MUST (requirement). Neither `create_demo_project()` nor `load_demo_as_calculation()` fully complies — `create_demo_project()` partially complies via `demo_source`, while `load_demo_as_calculation()` has no compliance at all.

---

## 4. Fix Design

### Fix A: Per-calculation `demo_origin` field (Recommended — minimal, scoped)

Add a `demo_origin` dict to `calculation.yaml` metadata for demo-loaded calculations:

```yaml
# calculation.yaml
meta:
  ulid: "01ABCDEF..."
  name: "Silicon SCF"
  slug: "0-si-scf"
  ...
demo_origin:
  demo_id: "qe_si_scf"
  engine: "qe"
  materialized_at: "2026-02-18T12:00:00+00:00"
```

**Implementation**:
1. Add `demo_origin: dict | None = None` field to `CalculationModel`
2. In `load_demo_as_calculation()`, set it before `save_calculation()`:
   ```python
   calc_model.demo_origin = {
       "demo_id": demo_id,
       "engine": engine,
       "materialized_at": datetime.now(timezone.utc).isoformat(),
   }
   ```
3. Update `get_reference_analysis()` to also check `calculation.demo_origin.demo_id` (not just project-level `settings.demo_source`)

**Pros**: Minimal change, scoped to demo feature, no provenance system dependency, works for mixed projects (some calcs from demos, some user-created).

**Cons**: Not full event-based provenance — but that's a systemic issue (Gap 2) with its own migration timeline.

### Fix B: Full opctx provenance (NOT recommended now)

Pass opctx to all `save_yaml_doc()` calls in `load_demo_as_calculation()`. This would require:
1. Creating a factory `opctx_for_demo_load()` in opctx.py
2. Threading opctx through `save_calculation()` and `save_project()` (which currently don't accept it)
3. Updating `save_calculation()` and `save_project()` signatures

**Why not now**: This is a systemic migration tracked by Law P2. Fixing it in one method while the rest of the codebase (including `create_demo_project()`) doesn't pass opctx would be inconsistent and premature.

### Recommendation

**Fix A now, Fix B later** (when Law P2 enforcement lands). Fix A gives us per-calculation demo origin tracking with minimal change. Fix B is the right long-term solution but should be done systemically, not piecemeal.

---

## 5. Test Design

### Tests for Fix A

1. **`test_load_demo_has_demo_origin`**: Load a demo → `calculation.yaml` has `demo_origin` with correct `demo_id`, `engine`, `materialized_at`
2. **`test_regular_calc_no_demo_origin`**: Create a normal calculation → `calculation.yaml` has `demo_origin: null` or absent
3. **`test_demo_origin_preserved_on_reload`**: Load demo, reload project, read calculation → `demo_origin` persists
4. **`test_get_reference_analysis_via_calc_demo_origin`**: Load demo into non-demo project → `get_reference_analysis()` still finds ref pack via `calculation.demo_origin.demo_id`

### Verification of existing meta consistency (already tested)

The existing Stage 10 tests (188 passing) already verify:
- ULID consistency across project.qms.yml ↔ calculation.yaml ↔ step files
- Slug uniqueness on repeated loads
- Step parameter preservation for all 52 demos

---

## Summary

| Finding | Severity | Action |
|---------|----------|--------|
| `load_demo_as_calculation()` records no provenance events | Low (systemic — Law P2 migration) | Defer to systemic fix |
| `load_demo_as_calculation()` has no `demo_source`/`demo_origin` metadata | Medium (breaks ref pack lookup for loaded demos) | Fix A: add `demo_origin` to CalculationModel |
| `create_demo_project()` sets project-level `demo_source` but no opctx | Low (same systemic gap) | Already compliant via S11 |
| S5.6 SHOULD compliance | Low (recommendation, not requirement) | Fix A provides partial compliance |
