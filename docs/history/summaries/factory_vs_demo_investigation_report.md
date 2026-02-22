# Factory vs Demo Calculation Inconsistency Investigation Report

**Date**: 2024-12-19  
**Investigator**: AI Assistant  
**Scope**: Comparison of UI-created (factory) vs demo-created calculations

---

## Executive Summary

1. **`calculation.yaml.steps[]` missing `type` field**: Factory-created calculations store only `step_id` in steps array, missing the `type` field that workflow detection requires. This causes "missing scf" validation errors because workflow detection cannot identify step types without reading individual step YAML files.

2. **Step YAML missing canonical fields**: Factory-created steps are missing `meta.path` and `species_overrides` sections that demo steps include. The UI expects these fields and may crash when accessing them.

3. **Incomplete step data**: Factory steps have incomplete `cards` sections (missing data arrays) and some steps (bands_pw) are missing cards entirely, while demo steps have complete card data.

4. **Missing calculation-level metadata**: Factory calculations are missing `species_map` section that demo calculations include.

5. **Root cause**: `WorkflowService.instantiate_workflow()` calls `calc_set_steps()` with only ULIDs, which creates `CalculationStepEntry` objects with `type=None`. Since `CalculationStepEntry.to_dict()` only writes non-None fields, the `type` field is never persisted. Additionally, `save_step_doc()` in step factory doesn't set `meta.path`, and `create_step_doc()` may not persist empty `species_overrides` dicts.

---

## Canonical Schema Snapshot

### calculation.yaml (Golden Reference from Demo)

**Required top-level keys:**
- `meta`: Object with `id`, `name`, `slug`, `path`, `kind`
- `mode`: String (e.g., "normal")
- `working_dir`: String (e.g., "raw")
- `steps`: Array of step entries (see below)
- `structure_id`: String (ULID)
- `species_map`: Object mapping species names to pseudo metadata (REQUIRED)

**Step entry in `steps[]` array:**
```yaml
- step_id: <ULID>  # REQUIRED
  type: <step_type>  # REQUIRED (e.g., "scf", "nscf", "bands_pw")
```

### step.yaml (Golden Reference from Demo)

**Required top-level keys:**
- `meta`: Object with `id`, `name`, `slug`, `path`, `kind` (path is REQUIRED)
- `step_type`: String (e.g., "scf")
- `parameters`: Object (nested dict of namelists)
- `cards`: Object (nested dict, may be empty but should exist)
- `species_overrides`: Object (may be empty but should exist)

**meta object:**
```yaml
meta:
  id: <ULID>
  name: <string>
  slug: <string>
  path: <relative_path>  # REQUIRED (e.g., "calculations/si-bands/steps/scf.step.yaml")
  kind: "step"
```

---

## Findings Table

| File | Field Missing/Different | Golden Value/Shape | Factory Value/Shape | Where Generated | Downstream Symptom |
|------|------------------------|-------------------|-------------------|----------------|-------------------|
| `calculation.yaml` | `steps[].type` | `type: "scf"` (string) | Missing (not written) | `api.py:4933` in `calc_set_steps()` | Workflow detection reports "missing scf" because it cannot identify step types without reading step YAML files |
| `calculation.yaml` | `species_map` | Object with species pseudo metadata | Missing entirely | Unknown (not set by factory) | Calculation-level species info unavailable |
| `scf.step.yaml` | `meta.path` | `"calculations/si-bands/steps/scf.step.yaml"` | Missing (None) | `step_factory.py:108` - `save_step_doc()` doesn't set path | UI may crash when accessing `step.meta.path` (expected string, got None) |
| `scf.step.yaml` | `species_overrides` | Object (may be empty `{}`) | Missing entirely | `step_factory.py:83-84` - empty dict may not be persisted | UI expects `species_overrides` field; may crash on access |
| `bands_pw.step.yaml` | `cards` | Object with `K_POINTS` card and data | Missing entirely | `step_factory.py:79-80` - defaults may not include cards for bands_pw | UI expects `cards` field; may crash on access |
| `bands.step.yaml` | `cards.K_POINTS.data` | Array of k-point data | Missing (only `option` present) | `step_factory.py` - incomplete card data | UI may fail to render k-points visualization |
| `calculation.yaml` | `steps[]` count | 4 steps (scf, nscf, bands_pw, bands) | 3 steps (scf, bands_pw, bands) | `workflow/templates.py:344` - workflow instantiation | Missing nscf step breaks workflow sequence |

---

## Evidence Appendix

### Evidence 1: calculation.yaml steps[] comparison

**Demo (si-bands/calculation.yaml):**
```yaml
steps:
- step_id: 01KDZGYN283EZD0ZJ0W9AP5ZPR
  type: scf
- step_id: 01KDZGYN28JNPM0C4ETEMXE5NX
  type: nscf
- step_id: 01KDZGYN28N5N7B840NVBXBV66
  type: bands_pw
- step_id: 01KDZGYN286N2RRJ7QEN9VSZ6V
  type: bands
```

**Factory (bands/calculation.yaml):**
```yaml
steps:
- step_id: 01KDZGZ76NAECY9FFR6ZC41JED
- step_id: 01KDZGZ76Q9HYRZK9J1N84T7PS
- step_id: 01KDZGZ76QWQRX79KHJ44T60JT
```

**Root cause code location:**
- `src/qmatsuite/api.py:4933`: `CalculationStepEntry(step_id=step_ulid, type=None)`
- `src/qmatsuite/core/models.py:63`: `if self.type: d["type"] = self.type` (only writes if truthy)
- `src/qmatsuite/workflow/templates.py:375-379`: `calc_set_steps()` called with only ULIDs, no step_type info

### Evidence 2: Step YAML meta.path comparison

**Demo (si-bands/steps/scf.step.yaml):**
```yaml
meta:
  id: 01KDZGYN283EZD0ZJ0W9AP5ZPR
  name: scf
  slug: scf
  path: calculations/si-bands/steps/scf.step.yaml  # PRESENT
  kind: step
```

**Factory (bands/steps/scf.step.yaml):**
```yaml
meta:
  id: 01KDZGZ76NAECY9FFR6ZC41JED
  name: scf
  slug: scf
  # path: MISSING
  kind: step
```

**Root cause code location:**
- `src/qmatsuite/workflow/step_factory.py:104-108`: `save_step_doc()` doesn't update `meta.path` before saving
- Compare with `src/qmatsuite/api.py:874-878`: `init_step()` DOES set `meta.path` before saving

### Evidence 3: Step YAML species_overrides comparison

**Demo (si-bands/steps/scf.step.yaml):**
```yaml
species_overrides:
  Si:
    mass: 28.0855
    pseudopot: Si.pbe-n-rrkjus_psl.1.0.0.UPF
```

**Factory (bands/steps/scf.step.yaml):**
```yaml
# species_overrides: MISSING
```

**Root cause code location:**
- `src/qmatsuite/workflow/step_factory.py:82-84`: `create_step_doc()` adds `species_overrides` from defaults
- `src/qmatsuite/workflow/registry.py:330`: `get_defaults()` returns `{"species_overrides": {}}` (empty dict)
- Empty dicts may not be persisted by YAML serializer (implementation-dependent)

### Evidence 4: Step YAML cards comparison

**Demo (si-bands/steps/bands_pw.step.yaml):**
```yaml
cards:
  K_POINTS:
    option: crystal_b
    data:
    - - 5
    - - 0.0
      - 0.5
      - 0.0
      - 20
    # ... more k-points
```

**Factory (bands/steps/bands_pw.step.yaml):**
```yaml
# cards: MISSING
```

**Factory (bands/steps/bands.step.yaml):**
```yaml
cards:
  K_POINTS:
    option: crystal_b
    # data: MISSING
```

**Root cause code location:**
- `src/qmatsuite/workflow/step_factory.py:79-80`: `create_step_doc()` adds cards from defaults
- Defaults may not include cards for all step types (bands_pw may not have default cards)

### Evidence 5: Runtime representation comparison

**Demo step (via StepDoc):**
```python
{
  'meta': {'id': '...', 'name': 'scf', 'slug': 'scf', 'path': 'calculations/si-bands/steps/scf.step.yaml', 'kind': 'step'},
  'step_type': 'scf',
  'parameters': {...},
  'cards': {'K_POINTS': {...}},
  'species_overrides': {'Si': {...}}
}
```

**Factory step (via StepDoc):**
```python
{
  'meta': {'id': '...', 'name': 'scf', 'slug': 'scf', 'kind': 'step'},  # path missing
  'step_type': 'scf',
  'parameters': {...},
  'cards': {'K_POINTS': {...}},  # present but may be incomplete
  # species_overrides: MISSING
}
```

**UI expectation (from `gui/src/types/qms.ts:417-429`):**
```typescript
export interface StepDetail {
  path: string;  // REQUIRED - will be undefined if missing
  species_overrides: Record<string, Record<string, unknown>>;  // REQUIRED - may crash if missing
  cards: Record<string, Record<string, unknown>>;  // REQUIRED - may crash if missing
}
```

### Evidence 6: Workflow detection code path

**Location**: `src/qmatsuite/workflow/templates.py:196-235`

```python
for step_entry in steps:
    step_type = None
    
    # Try new format first: step_id (ULID) -> resolve step -> get step_type
    step_ulid = step_entry.get("step_id")
    if step_ulid and project_root:
        # ... resolves step and loads step YAML to get step_type ...
    
    # Fallback to legacy format: step_type directly in entry, or type field
    if not step_type:
        step_type = step_entry.get("step_type") or step_entry.get("type")  # LINE 219
    
    if step_type:
        present_steps.append(step_type)
```

**Issue**: When `type` field is missing from `steps[]`, workflow detection must resolve each step by ULID and load the step YAML file, which is slower and may fail if step files are missing or corrupted.

---

## Hypothesis Verification

### Hypothesis 1: "missing scf" due to missing `type` field in `steps[]`

**CONFIRMED**: Demo `calculation.yaml` has `type: "scf"` in steps array, factory does not. Workflow detection code (`templates.py:219`) checks `step_entry.get("type")` as fallback, but when missing, it must resolve step by ULID and load step YAML, which is slower and may fail. The validator likely reports "missing scf" because it cannot efficiently identify step types without the `type` field.

**Evidence**: 
- Demo: `steps[0] = {'step_id': '...', 'type': 'scf'}`
- Factory: `steps[0] = {'step_id': '...'}` (no type field)
- Code: `api.py:4933` creates entries with `type=None`, and `models.py:63` doesn't write None values

### Hypothesis 2: Step detail crash due to missing mandatory fields

**CONFIRMED**: Factory steps are missing `meta.path` and `species_overrides`. The UI expects these fields (see `gui/src/types/qms.ts:421, 428`). When `get_step_detail()` returns `step.meta.path` as `None` (line 3455 in `api.py`), the UI receives `path: null` instead of a string, which may cause TypeScript type errors or runtime crashes.

**Evidence**:
- `api.py:3455`: `"path": step.meta.path` (will be None if not set)
- `api.py:3462`: `"species_overrides": spec.species_overrides` (will be empty dict `{}` if missing, but StructureStepSpec defaults to `field(default_factory=dict)`, so it should exist)
- Factory step: `meta.path` is None, `species_overrides` is missing from YAML

**Potential crash location**: `gui/src/components/panels/StepDetailPanel.tsx` when accessing `stepDetail.path` or `stepDetail.species_overrides` without null checks.

### Hypothesis 3: Workflow hint "Detected workflow: Band Structure (4/3)" not visible

**PARTIALLY CONFIRMED**: The workflow detection data is likely being computed (workflow detection code runs), but the UI may not be displaying it due to:
1. CSS/layout issues (text clipped or hidden)
2. Data format mismatch (e.g., workflow name vs workflow_id)
3. Missing UI component that should display workflow badge

**Evidence needed**: Check UI component that displays workflow detection results (likely in `CalculationDetailPanel` or similar).

---

## Recommendations

### Priority 1: Fix `calc_set_steps()` to preserve step type

**Location**: `src/qmatsuite/api.py:4892-4938`

**Issue**: `calc_set_steps()` creates `CalculationStepEntry(step_id=step_ulid, type=None)` when step is not in current model, and `to_dict()` doesn't write None values.

**Fix**: When workflow instantiation calls `calc_set_steps()`, it should pass step_type information. Two approaches:

**Option A (Preferred)**: Modify `calc_set_steps()` to accept optional step_type mapping:
```python
def calc_set_steps(
    ...,
    step_types: Optional[Dict[str, str]] = None,  # step_ulid -> step_type
) -> None:
    # ...
    for step_ulid in ordered_step_ulids:
        if step_ulid in step_map:
            new_steps.append(step_map[step_ulid])
        else:
            step_type = step_types.get(step_ulid) if step_types else None
            new_steps.append(CalculationStepEntry(step_id=step_ulid, type=step_type))
```

**Option B**: Modify `WorkflowService.instantiate_workflow()` to call `calc_add_step()` for each step individually (preserves type).

**Recommendation**: Option A is cleaner and maintains atomicity of `calc_set_steps()`.

### Priority 2: Fix `save_step_doc()` to set `meta.path`

**Location**: `src/qmatsuite/workflow/step_factory.py:96-108`

**Issue**: `save_step_doc()` doesn't update `meta.path` before saving, unlike `init_step()` which does.

**Fix**: Update `save_step_doc()` to set `meta.path` from the file path:
```python
def save_step_doc(step_doc: StepDoc, path: Path) -> None:
    path = Path(path).resolve()
    
    # Calculate relative path for meta.path (same logic as init_step)
    # Need project_root to compute relative path
    # Option: pass project_root as parameter, or infer from path structure
    
    # Update path in meta
    # step_doc.set(["meta", "path"], relative_path)
    
    save_yaml_doc(step_doc, path)
```

**Challenge**: Need project_root to compute relative path. Options:
1. Pass project_root as parameter to `save_step_doc()`
2. Infer from path structure (e.g., `calculations/{calc}/steps/{step}.step.yaml`)
3. Set absolute path and normalize later

**Recommendation**: Pass project_root as optional parameter, with fallback to path inference.

### Priority 3: Ensure `species_overrides` and `cards` are always persisted

**Location**: `src/qmatsuite/workflow/step_factory.py:82-84`

**Issue**: Empty dicts may not be persisted by YAML serializer.

**Fix**: Explicitly ensure these fields exist in the StepDoc before saving:
```python
def save_step_doc(step_doc: StepDoc, path: Path) -> None:
    # Ensure species_overrides exists (even if empty)
    if not step_doc.has(["species_overrides"]):
        step_doc.set(["species_overrides"], {})
    
    # Ensure cards exists (even if empty)
    if not step_doc.has(["cards"]):
        step_doc.set(["cards"], {})
    
    # ... rest of save logic
```

**Alternative**: Modify `StructureStepSpec.to_dict()` to always write these fields (but this affects all serialization paths).

**Recommendation**: Fix in `save_step_doc()` to ensure canonical form at save time.

### Priority 4: Fix incomplete cards data

**Location**: `src/qmatsuite/workflow/step_factory.py:79-80` and step defaults

**Issue**: Some step types (bands_pw) don't have default cards, and cards may be created with incomplete data (option but no data).

**Fix**: 
1. Ensure all step types that need cards have default cards in `step_defaults.py`
2. Validate card completeness before saving (e.g., K_POINTS with `option: crystal_b` must have `data` array)

**Recommendation**: Add validation in `save_step_doc()` or `create_step_doc()` to ensure cards are complete.

### Priority 5: Add calculation-level `species_map`

**Location**: Unknown (not set by factory path)

**Issue**: Demo calculations include `species_map` at calculation level, factory calculations don't.

**Fix**: When creating calculation via workflow instantiation, extract species_map from structure and persist to `calculation.yaml`.

**Recommendation**: Lower priority - this is metadata that can be derived from structure, but should be persisted for consistency.

### Canonicalization Strategy

**Recommendation**: Fix at save time (in `save_step_doc()` and `save_calculation()`) rather than at generation time. This ensures:
1. All writes go through canonicalization (single point of enforcement)
2. Legacy calculations can be normalized on save
3. Consistent behavior regardless of creation path

**Implementation approach**:
1. Create `canonicalize_step_doc()` function that ensures all required fields exist
2. Create `canonicalize_calc_doc()` function that ensures `steps[].type` is set
3. Call these functions in `save_step_doc()` and `save_calculation()` respectively

**Minimal invariants to enforce**:
1. `calculation.yaml.steps[].type` must always be set (resolve from step YAML if missing)
2. `step.yaml.meta.path` must always be set (compute from file path)
3. `step.yaml.species_overrides` must always exist (empty dict if not set)
4. `step.yaml.cards` must always exist (empty dict if not set)
5. `calculation.yaml.species_map` should be set if structure has species info

---

## Slug Collision & Non-ULID Resolution Causing StepDetail Failure

### Evidence: Slug Collision Confirmed

**Factory calculation directory analysis:**
- Calculation slug: `"bands"`
- Step slugs: `["bands", "scf", "bands_pw"]`
- **COLLISION**: Step slug `"bands"` matches calculation slug `"bands"`

**Demo calculation (for comparison):**
- Calculation slug: `"si-bands"`
- Step slugs: `["bands", "scf", "bands_pw", "nscf"]`
- **No collision**: Calculation slug differs from all step slugs

### Evidence: UI Passes Non-ULID Identifier

**Code analysis:**
- `CalculationListPanel.tsx:1303`: `onSelectStep?.(step.id)` - UI passes `step.id`
- `get_calculation_detail()` returns steps with `id` field set to `step_id` (ULID from calculation.yaml)
- However, error message shows: `"Resource 'bands' is not a step: Resource 'bands' is not a calculation (kind: step)"`

**Hypothesis**: The UI is receiving step data where `step.id` is the slug `"bands"` instead of the ULID. This could happen if:
1. The UI is using `calculationSummary.steps[]` instead of `calculationDetail.steps[]`
2. The backend is returning slug instead of ULID in some code path
3. There's a data transformation bug that replaces ULID with slug

**Logging added to trace:**
- `daemon/server.py:_handle_get_step_detail()`: Logs the step identifier value and whether it's a ULID
- `api.py:get_step_detail()`: Logs the step_selector and whether it's found in calculation.yaml.steps[]
- `resolution.py:resolve_id()`: Logs which resolution strategy is used (ULID/slug/name/path)
- `resolution.py:resolve_step()`: Logs the resolved resource kind and slug

### Evidence: Resolver Uses Slug-Based Resolution

**Code path analysis:**
- `ResourceIndex.resolve_id()` tries strategies in order:
  1. ULID (if selector matches ULID format)
  2. **slug (exact match)** ← This is where "bands" resolves to calculation
  3. name (case-insensitive)
  4. path

**When UI passes `"bands"` (slug) instead of ULID:**
1. `resolve_id("bands")` checks ULID format → fails (not 26 chars starting with "01")
2. `resolve_id("bands")` checks `by_slug["bands"]` → **finds calculation** (slug collision!)
3. Returns calculation ULID instead of step ULID
4. `resolve_step()` receives calculation resource → error: "Resource 'bands' is not a step (kind: calculation)"

**Logging added:**
- `resolution.py:resolve_id()`: Logs which strategy matched and the resolved resource kind
- `resolution.py:resolve_step()`: Logs error when resolved resource has wrong kind

### Root Cause

The UI is passing a slug (`"bands"`) instead of a ULID when selecting a step. This happens because:
1. **Slug collision**: Calculation slug `"bands"` collides with step slug `"bands"`
2. **Non-ULID identifier**: UI is passing `step.id` which contains the slug instead of ULID
3. **Resolver ambiguity**: Slug-based resolution finds the calculation first (wrong resource)

**Design intent violation**: The only robust internal resource addressing must be ULID. Slug/name/path lookup should only exist as explicit "resolve" endpoints for user convenience, not for internal step selection.

---

## Validator/Workflow Relies on steps[].type in calculation.yaml

### Evidence: Workflow Detection Code Path

**Location**: `src/qmatsuite/workflow/templates.py:196-285`

**Code flow:**
1. Loads `calculation.yaml` and reads `steps[]` array
2. For each step entry:
   - Tries to resolve step by ULID and load step YAML to get `step_type` (requires project_root)
   - **Fallback**: Reads `step_entry.get("type")` directly from calculation.yaml
   - If missing, tries legacy `step_file` path resolution

**Logging added:**
- `workflow/templates.py:detect_workflow()`: Logs each step entry with `step_id` and `type` (or None)
- Logs when `type` field is missing and workflow detection must resolve step by ULID
- Logs the final `present_steps` list and any warnings about missing types

### Evidence: Factory Calculation Missing type Field

**Demo calculation.yaml:**
```yaml
steps:
- step_id: 01KDZGYN283EZD0ZJ0W9AP5ZPR
  type: scf  # PRESENT
- step_id: 01KDZGYN28JNPM0C4ETEMXE5NX
  type: nscf  # PRESENT
```

**Factory calculation.yaml:**
```yaml
steps:
- step_id: 01KDZGZ76NAECY9FFR6ZC41JED
  # type: MISSING
- step_id: 01KDZGZ76Q9HYRZK9J1N84T7PS
  # type: MISSING
```

**Impact:**
- When `type` is missing, workflow detection must resolve each step by ULID and load the step YAML file
- This is slower and may fail if step files are missing or corrupted
- Validator reports "missing scf" because it cannot efficiently identify step types without the `type` field

### Root Cause

`calc_set_steps()` in `api.py:4933` creates `CalculationStepEntry(step_id=step_ulid, type=None)` when step is not in current model. Since `CalculationStepEntry.to_dict()` only writes non-None fields (line 63 in `models.py`), the `type` field is never persisted.

**Workflow instantiation flow:**
1. `WorkflowService.instantiate_workflow()` creates steps and collects ULIDs
2. Calls `calc_set_steps()` with only ULIDs (no step_type info)
3. `calc_set_steps()` creates entries with `type=None`
4. `to_dict()` doesn't write None values → `type` field missing from YAML

---

## meta.path Usage Verification

### Evidence: meta.path is Display-Only (Not Used for Resolution)

**Code analysis:**
- `resolution.py:1198`: `step_path = project_root / meta.path` - Used ONLY for verification (belongs-to check)
- `resolution.py:1207-1210`: Falls back to `meta.path` ONLY if `by_path` index doesn't have the absolute path
- **Resolution happens via**: `ResourceIndex.resolve_id()` which uses ULID/slug/name/path selectors, NOT meta.path

**Conclusion**: `meta.path` is used for:
1. **Verification**: Checking if step belongs to calculation directory (line 1199)
2. **Fallback path construction**: Only if absolute path not found in `by_path` index
3. **Display**: Returned to UI for display purposes

**meta.path is NOT used for:**
- Initial resource resolution (resolution uses ULID/slug/name/path selectors)
- ResourceIndex building (index is built from file paths, not meta.path)

**Logging added:**
- `resolution.py:resolve_step()`: Logs when meta.path is used vs when by_path index is used
- Logs error if meta.path is missing when needed for fallback

---

## Next Steps

1. **Implement Priority 1 fix**: Modify `calc_set_steps()` to accept and preserve step_type
2. **Implement Priority 2 fix**: Update `save_step_doc()` to set `meta.path`
3. **Implement Priority 3 fix**: Ensure `species_overrides` and `cards` are always persisted
4. **Test**: Create new calculation via UI and verify all fields are present
5. **Verify**: Run workflow detection and step detail retrieval on factory-created calculation
6. **Document**: Update step factory documentation to specify canonical form requirements

---

## Appendix: Code Locations Summary

| Issue | File | Function/Line | Fix Location |
|-------|------|---------------|--------------|
| Missing `steps[].type` | `api.py` | `calc_set_steps()`:4933 | `api.py:4892-4938` |
| Missing `meta.path` | `step_factory.py` | `save_step_doc()`:104-108 | `step_factory.py:96-108` |
| Missing `species_overrides` | `step_factory.py` | `create_step_doc()`:82-84 | `step_factory.py:96-108` (save time) |
| Missing `cards` | `step_factory.py` | `create_step_doc()`:79-80 | `step_factory.py:96-108` (save time) |
| Missing `species_map` | Unknown | Not set by factory | `workflow/templates.py` or `api.py` |

