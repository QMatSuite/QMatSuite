# Engine Recipes + JobGraph Implementation: Independent Audit Report

**Date**: 2026-01-13  
**Auditor**: Independent Reviewer (not implementer)  
**Baseline Tests**: ✅ PASSED
- `pytest tests/unit/test_step_type_mapping.py -q` → 10 passed
- `pytest tests/unit/execution/test_executor.py -q` → 16 passed

**Reference Plan**: `docs/plans/engine_recipes_jobgraph_plan.md`

---

## Executive Summary

**Overall Status**: ⚠️ **CONDITIONAL PASS** with **3 HIGH-SEVERITY RISKS**

The implementation largely follows the Constitution, but contains **critical technical debt** that violates SSOT principles and introduces prefix inference patterns. The unified pipeline is correctly implemented, and JobGraph is properly runtime-only. However, normalization functions and prefix inference in key codepaths create ambiguity and potential future regressions.

### Top 3 Risks

1. **BLOCKER**: `normalize_step_type_to_public()` used in persisted data paths (`structure_steps.py:105-106`, `hash_utils.py:187-188`) violates Constitution §B (Persisted Truth = SPEC). This creates ambiguity about whether in-memory models use SPEC or GEN, and risks affecting execution dispatch.

2. **HIGH**: Prefix inference in `runner.py:854-859` violates Constitution §C (Explicit Dispatch Mapping). Engine family is inferred from step type string prefix (`startswith("pyscf_")`, `startswith("orca_")`) instead of using registry mapping.

3. **HIGH**: Legacy code paths (`run_step_legacy()`, legacy execution loop in `runner.py:378-800`) remain reachable and could be accidentally invoked, creating maintenance burden and potential divergence.

---

## Constitution Checklist (A–F)

### A) Engine Family + Members

**Status**: ✅ **PASS**

**Evidence**:
- Registry enforces uniqueness: `tests/unit/test_step_type_mapping.py:48-73` tests that no two step types within an engine share the same `public_type`.
- All step types in `src/quantumvitas/workflow/registry.py:181-558` use SPEC keys (engine-prefixed).
- Engine field is non-empty for all specs: `tests/unit/test_step_type_mapping.py:32-38`.

**Compliance**: ✅ No violations detected.

---

### B) Persisted Truth = SPEC

**Status**: ❌ **FAIL** (BLOCKER)

**Evidence of Violations**:

1. **Step YAML Write Path** ✅ CORRECT:
   - `src/quantumvitas/workflow/step_factory.py:73` correctly writes `machine_step_type` (SPEC) to `step.yaml`.
   - No GEN types written to persisted YAML.

2. **Step YAML Read Path** ❌ VIOLATION:
   - `src/quantumvitas/calculation/structure_steps.py:105-106`:
     ```python
     from quantumvitas.workflow.registry import normalize_step_type_to_public
     step_type = normalize_step_type_to_public(str(step_type))
     ```
     This normalizes SPEC → GEN when loading step specs into `StructureStepSpec`. The in-memory model uses GEN, but YAML contains SPEC. This creates ambiguity.

3. **SHA Computation Path** ❌ VIOLATION:
   - `src/quantumvitas/calculation/hash_utils.py:187-188`:
     ```python
     from quantumvitas.workflow.registry import normalize_step_type_to_public
     step_data["step_type"] = normalize_step_type_to_public(step_data["step_type"])
     ```
     SHA computation normalizes SPEC → GEN before hashing. This means hashes are computed on GEN types, not SPEC types. This could cause hash mismatches if the same step is loaded with different normalization paths.

**Impact**:
- In-memory `StructureStepSpec` uses GEN types, but YAML contains SPEC types. This creates a disconnect between persisted truth and in-memory model.
- SHA computation uses GEN types, which means fingerprints may not match if normalization is inconsistent.
- The normalization function `normalize_step_type_to_public()` in `registry.py:711-731` is marked as "legacy" but is still actively used in production paths.

**Compliance**: ❌ **FAIL** - Normalization violates SSOT principle. In-memory models should use SPEC types to match persisted YAML.

---

### C) Explicit Dispatch Mapping (No Prefix Inference)

**Status**: ❌ **FAIL** (HIGH)

**Evidence of Violations**:

1. **Registry Mapping** ✅ CORRECT:
   - `src/quantumvitas/workflow/registry.py:734-798` provides `resolve_engine_for_step()` which uses explicit registry lookup.
   - Tests enforce completeness: `tests/unit/test_step_type_mapping.py` (10 tests, all passing).

2. **Runner Engine Family Inference** ❌ VIOLATION:
   - `src/quantumvitas/calculation/runner.py:854-859`:
     ```python
     if step_type_str.startswith("pyscf_"):
         engine_family = "pyscf"
     elif step_type_str.startswith("orca_"):
         engine_family = "orca"
     else:
         engine_family = "qe"
     ```
     This infers engine family from string prefix instead of using registry mapping. While this is used only for recipe selection (not execution dispatch), it violates the spirit of Constitution §C.

3. **Other Prefix Inference** ⚠️ ACCEPTABLE:
   - `src/quantumvitas/core/models.py:86` and `src/quantumvitas/core/calc_identity.py:97` use prefix inference for backward compatibility recovery (inferring engine_family from legacy data). This is acceptable as it's only for migration/recovery, not execution dispatch.

**Impact**:
- Recipe selection uses prefix inference, which could break if step type naming changes. Should use registry to determine engine family from step types.

**Compliance**: ❌ **FAIL** - Prefix inference in recipe selection violates explicit mapping requirement.

---

### D) Workflow Semantics (Run Calc / Run Step Unification)

**Status**: ✅ **PASS**

**Evidence**:

1. **Unified Pipeline** ✅ CORRECT:
   - `src/quantumvitas/api.py:1319-1453` (`run_step()`) calls `runner.run()` with `target_step_id` parameter.
   - `src/quantumvitas/api.py:1146-1176` (`run_calculation()`) calls `runner.run()` without `target_step_id` (selection=ALL).
   - Both use the same `CalculationRunner.run()` method.

2. **Selection Mode** ✅ CORRECT:
   - `src/quantumvitas/calculation/runner.py:873` sets `selection = SelectionMode.TARGET if target_step_id else SelectionMode.ALL`.
   - `src/quantumvitas/execution/executor.py:99-104` correctly handles both modes.

3. **Target Step Always Runs** ✅ CORRECT:
   - `src/quantumvitas/execution/executor.py:173-175` enforces that target job is never skipped:
     ```python
     if is_target_job:
         return False  # Never skip target
     ```

4. **Legacy Code** ⚠️ PRESENT BUT UNREACHABLE:
   - `src/quantumvitas/api.py:1456-1465` contains `run_step_legacy()` marked as "LEGACY" and kept for reference. This is acceptable as it's not called by production code.

**Compliance**: ✅ **PASS** - One pipeline correctly implemented with selection mode.

---

### E) Locks + Persisted Run Truth (JobGraph Runtime-Only)

**Status**: ✅ **PASS**

**Evidence**:

1. **JobGraph Not Persisted** ✅ CORRECT:
   - No YAML/JSON write operations found in `src/quantumvitas/execution/` (grep for `save.*jobgraph|write.*jobgraph|dump.*jobgraph|persist.*jobgraph` returned no matches).
   - JobGraph is materialized each run: `src/quantumvitas/execution/recipes.py:40-57` defines `materialize()` method that creates JobGraph from steps.

2. **Manifest is Only Persisted Truth** ✅ CORRECT:
   - `src/quantumvitas/calculation/runner.py:936-951` updates manifest entries after job execution.
   - Manifest entries use SPEC types: `src/quantumvitas/calculation/runner.py:942` sets `kind=step_type_str` (which is SPEC from step.yaml).

3. **Job Fingerprint Not Persisted** ✅ CORRECT:
   - `src/quantumvitas/execution/job_graph.py:compute_job_fingerprint()` is used only for runtime skip logic, not persisted.

4. **Locks** ✅ CORRECT:
   - Two locks maintained: `calc_run_lock` (outer, long-held) and `calc_edit_lock` (inner, short-held). No new locks added.

**Compliance**: ✅ **PASS** - JobGraph is runtime-only, manifest is the only persisted run truth.

---

### F) Naming Rules (GEN for Filenames, SPEC in YAML Content)

**Status**: ✅ **PASS**

**Evidence**:

1. **YAML Content Uses SPEC** ✅ CORRECT:
   - `src/quantumvitas/workflow/step_factory.py:73` writes `machine_step_type` (SPEC) to `step.yaml`.
   - Manifest entries use SPEC: `src/quantumvitas/calculation/runner.py:942` sets `kind=step_type_str` (SPEC).

2. **Filenames Use GEN** ✅ CORRECT:
   - `src/quantumvitas/execution/recipes.py:128` uses `public_type` for input filenames: `input_file = f"{public_type}.in"`.
   - `src/quantumvitas/calculation/naming.py:82-133` uses step_type (GEN) for filenames.

3. **ORCA Subchain Basenames** ✅ CORRECT:
   - `src/quantumvitas/execution/recipes.py:227` uses `generate_subchain_basename(public_types)` which uses stable tokens from `PUBLIC_TYPE_TOKENS` registry.
   - `src/quantumvitas/workflow/registry.py:81-88` defines stable token map.
   - Tokens come from registry, not runtime sorting: `src/quantumvitas/workflow/registry.py:113-143` uses `get_token_for_public_type()` which looks up from `PUBLIC_TYPE_TOKENS`.

**Compliance**: ✅ **PASS** - Naming rules correctly implemented.

---

## Key Codepaths Evidence Map

### Run Calc Flow

1. **Entry**: `src/quantumvitas/api.py:1146` → `run_calculation()`
2. **Runner**: `src/quantumvitas/api.py:1355` → `CalculationRunner(engine_registry)`
3. **Execute**: `src/quantumvitas/api.py:1407` → `runner.run(calculation, target_step_id=None)`
4. **JobGraph Path**: `src/quantumvitas/calculation/runner.py:332` → `_execute_with_jobgraph()`
5. **Recipe**: `src/quantumvitas/calculation/runner.py:866` → `get_recipe_for_engine(engine_family)`
6. **Materialize**: `src/quantumvitas/calculation/runner.py:868` → `recipe.materialize(calculation.steps, raw_dir, step_shas)`
7. **Executor**: `src/quantumvitas/calculation/runner.py:885` → `JobExecutor(engine_handlers)`
8. **Execute**: `src/quantumvitas/calculation/runner.py:891` → `executor.execute(job_graph, calculation, selection=ALL)`
9. **Handler**: `src/quantumvitas/execution/handlers.py:37-143` → `qe_step_handler()` / `pyscf_chain_handler()` / `orca_chain_handler()`
10. **Engine**: `src/quantumvitas/execution/handlers.py:112` → `step.run(engine, ...)`

### Run Step Flow

1. **Entry**: `src/quantumvitas/api.py:1319` → `run_step()`
2. **Resolve**: `src/quantumvitas/api.py:1374` → `require_step(...)`
3. **Runner**: `src/quantumvitas/api.py:1397` → `CalculationRunner(engine_registry)`
4. **Execute**: `src/quantumvitas/api.py:1407` → `runner.run(calculation, target_step_id=step_id)`
5. **JobGraph Path**: Same as Run Calc from step 4 onwards, but with `selection=TARGET`.

**Key Difference**: Only the `target_step_id` parameter differs. Same pipeline, different selection mode.

---

## Red Flags / Technical Debt

### 1. normalize_step_type_to_public() in Production Paths (BLOCKER)

**Severity**: 🔴 **BLOCKER**

**Location**:
- `src/quantumvitas/calculation/structure_steps.py:105-106`
- `src/quantumvitas/calculation/hash_utils.py:187-188`

**Why It Violates**:
- Constitution §B requires persisted truth = SPEC. Normalization creates in-memory models with GEN types while YAML contains SPEC types.
- SHA computation uses GEN types, which could cause hash mismatches if normalization is inconsistent.
- Creates ambiguity about whether execution dispatch should use SPEC (from YAML) or GEN (from in-memory model).

**Impact**: High risk of future regressions if code paths diverge on SPEC vs GEN usage.

**Recommendation**: Remove normalization from production paths. Update `StructureStepSpec` to use SPEC types internally, matching YAML content.

---

### 2. Prefix Inference in Recipe Selection (HIGH)

**Severity**: 🟠 **HIGH**

**Location**: `src/quantumvitas/calculation/runner.py:854-859`

**Why It Violates**:
- Constitution §C requires explicit dispatch mapping. Prefix inference (`startswith("pyscf_")`) is fragile and could break if naming changes.
- Should use registry to determine engine family from step types.

**Impact**: Medium risk. If step type naming changes, recipe selection could break.

**Recommendation**: Replace prefix inference with registry lookup:
```python
# Instead of:
if step_type_str.startswith("pyscf_"):
    engine_family = "pyscf"
# Use:
spec = registry.get(step_type_str)
engine_family = spec.engine if spec else "qe"
```

---

### 3. Legacy Execution Loop Still Present (HIGH)

**Severity**: 🟠 **HIGH**

**Location**: `src/quantumvitas/calculation/runner.py:378-800`

**Why It Violates**:
- Constitution requires "no backward-compat shims". Legacy loop is kept as "fallback" but could be accidentally invoked.
- Creates maintenance burden and potential divergence.

**Impact**: Medium risk. If JobGraph execution fails, falls back to legacy loop which may have different behavior.

**Recommendation**: Remove legacy loop once JobGraph execution is fully validated. If fallback is needed, make it explicit and test-protected.

---

### 4. run_step_legacy() Kept in API (MEDIUM)

**Severity**: 🟡 **MEDIUM**

**Location**: `src/quantumvitas/api.py:1456-1465`

**Why It Violates**:
- Marked as "LEGACY" but still present in public API. Could be accidentally called.

**Impact**: Low risk. Code is marked as legacy and not called by production paths.

**Recommendation**: Move to `legacy/` module or remove entirely if not needed for reference.

---

### 5. Engine Family Inference from Step Type (MEDIUM)

**Severity**: 🟡 **MEDIUM**

**Location**: `src/quantumvitas/core/models.py:35-86`, `src/quantumvitas/core/calc_identity.py:78-97`

**Why It's Acceptable**:
- Used only for backward compatibility recovery (inferring engine_family from legacy data).
- Not used for execution dispatch.

**Impact**: Low risk. Only affects migration/recovery paths.

**Recommendation**: Document that this is migration-only and should not be used for execution dispatch.

---

## Follow-ups (Actionable Items)

### Priority 1 (BLOCKER)

1. **Remove normalize_step_type_to_public() from production paths**
   - Update `StructureStepSpec` to use SPEC types internally (`structure_steps.py:105-106`).
   - Remove normalization from SHA computation (`hash_utils.py:187-188`).
   - Update tests that depend on GEN types in specs.

### Priority 2 (HIGH)

2. **Replace prefix inference with registry lookup**
   - Update `runner.py:854-859` to use registry to determine engine family.
   - Add test to ensure recipe selection uses registry, not prefix inference.

3. **Remove legacy execution loop**
   - Once JobGraph execution is fully validated, remove legacy loop (`runner.py:378-800`).
   - If fallback is needed, make it explicit and test-protected.

### Priority 3 (MEDIUM)

4. **Move or remove run_step_legacy()**
   - Move to `legacy/` module or remove if not needed for reference.

5. **Document migration-only inference**
   - Add comments to `core/models.py` and `core/calc_identity.py` clarifying that prefix inference is migration-only.

---

## Questions to Maintainer

1. **SHA Computation Normalization**: Why is `normalize_step_type_to_public()` used in SHA computation (`hash_utils.py:187-188`)? Should SHA be computed on SPEC types to match persisted YAML?

2. **StructureStepSpec Design**: Why does `StructureStepSpec` use GEN types internally when YAML contains SPEC types? Is this intentional for backward compatibility, or should it be updated to use SPEC?

3. **Legacy Loop Fallback**: What conditions would cause JobGraph execution to fail and fall back to legacy loop? Is this fallback still needed, or can it be removed?

4. **Engine Family Inference**: The prefix inference in `runner.py:854-859` is used for recipe selection. Should this use registry lookup instead, or is prefix inference acceptable for recipe selection (not execution dispatch)?

---

## Conclusion

The implementation successfully unifies Run Calc and Run Step into one pipeline, correctly implements JobGraph as runtime-only, and follows naming rules. However, **critical technical debt** in normalization and prefix inference violates Constitution principles and creates risks for future regressions.

**Recommendation**: Address Priority 1 and Priority 2 items before considering this implementation complete. The SSOT violations are blockers that must be fixed to ensure long-term maintainability.

---

**End of Report**














