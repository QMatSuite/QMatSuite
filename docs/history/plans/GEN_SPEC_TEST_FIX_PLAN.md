# GEN/SPEC Test Fix Implementation Plan

## Overview

255 test failures remain after the GEN/SPEC convergence cleanup. This plan categorizes them into mechanical fixes (for agent implementation) and complex fixes (requiring human review).

## Non-Negotiable Rules Reminder

1. **Class/dataclass fields** must use canonical names: `step_type_spec`, `step_type_gen`, `*_ulid`
2. **Function parameters** can use simpler names (e.g., `step_id`, `step_type`)
3. **YAML files** must use `step_type_spec:` (not bare `step_type:`)
4. **No backwards compatibility shims** - direct renames only

---

## CATEGORY 1: MockStep Classes Missing Canonical Attributes [EASY - AGENT]

**Pattern:** Test mock classes have `step_type` attribute but code expects `step_type_spec` and `step_type_gen`.

**Files to fix:**

### 1.1 tests/unit/orca/test_input_compiler.py
```python
# FIND:
@dataclass
class MockStep:
    step_type: str
    ...

# REPLACE WITH:
@dataclass
class MockStep:
    step_type_spec: str  # SPEC type (e.g., "orca_scf")
    step_type_gen: str = ""  # GEN type (e.g., "scf") - derived from spec
    ...
```
Then update all MockStep instantiations to pass `step_type_spec=` and optionally `step_type_gen=`.

### 1.2 tests/unit/orca/test_chain_detection.py
Same pattern - update MockStep dataclass.

### 1.3 tests/unit/execution/test_recipes.py
```python
# Line ~38-42: Update MockStep
@dataclass
class MockStep:
    ulid: str
    step_type_spec: str  # was step_type
    step_type_gen: str = ""
    ...
```

### 1.4 tests/unit/test_vasp_recipe.py
Update MockStep to have `step_type_spec` instead of `step_type`.

### 1.5 tests/unit/test_vasp_staging.py
Update MockStep to have `step_type_spec` instead of `step_type`.

### 1.6 tests/unit/test_reference_resolver.py
Update mock class to have `step_type_spec` and `step_type_gen`.

### 1.7 tests/unit/orca/test_orca_engine.py
Update MockStep to have `step_type_spec`.

---

## CATEGORY 2: Function Calls With Old Parameter Names [EASY - AGENT]

**Pattern:** Tests call functions with old parameter names like `step_id=` instead of `step_ulid=`.

**Files to fix:**

### 2.1 tests/unit/test_history_digests.py
```python
# FIND all occurrences of:
compute_step_digest(
    step_id="...",
    step_type="...",
    ...
)

# REPLACE WITH:
compute_step_digest(
    step_ulid="...",
    step_type_spec="...",  # Use SPEC type like "qe_scf"
    ...
)
```

### 2.2 tests/unit/test_analysis_objects_base.py
Update `AnalysisObjectMeta.create()` calls to use `run_ulid=`, `calc_ulid=`, `step_ulid=`.

---

## CATEGORY 3: YAML Fixtures With Old Field Names [EASY - AGENT]

**Pattern:** Test fixtures write YAML with `step_type:` instead of `step_type_spec:`.

**Files to fix:**

### 3.1 tests/unit/test_workflow.py
Find all inline YAML strings with `step_type:` and replace with `step_type_spec:`.

Example:
```python
# FIND:
steps:
  - step_type_gen: scf
    file: steps/scf.step.yaml

# REPLACE WITH (note: use step_type_spec in calculation.yaml step entries):
steps:
  - step_type_spec: qe_scf
    file: steps/scf.step.yaml
```

### 3.2 tests/unit/test_preset_integration.py
Same pattern - update YAML fixtures.

### 3.3 tests/unit/test_structure_steps.py
Update YAML fixtures.

### 3.4 tests/unit/test_yamldoc.py
Update YAML fixtures.

### 3.5 tests/unit/test_calc_identity.py
Update step YAML fixtures to use `step_type_spec:`.

### 3.6 tests/unit/test_structure_roundtrip.py
Update fixtures.

---

## CATEGORY 4: Assertion Checks for Old Attribute Names [EASY - AGENT]

**Pattern:** Tests assert on old attribute names like `result.run_id` instead of `result.run_ulid`.

**Files to fix:**

### 4.1 tests/api/test_run_capabilities.py
```python
# FIND:
assert result.run_id == ...
assert result.calc_id == ...
assert result.step_ids == ...

# REPLACE WITH:
assert result.run_ulid == ...
assert result.calc_ulid == ...
assert result.step_ulids == ...
```

### 4.2 tests/unit/test_qvservice_gui.py
Update assertions to use canonical field names.

### 4.3 tests/unit/test_daemon.py
Update schema assertions to expect canonical field names.

### 4.4 tests/daemon/test_daemon_payload_contracts.py
Update expected schema fields.

---

## CATEGORY 5: Workflow Detection Template Issues [MEDIUM - REQUIRES CODE FIX]

**Root Cause Analysis:**

In `src/quantumvitas/workflow/templates.py`:
- Line 230: `step_entry_type = step_entry.get("step_type") or step_entry.get("type")` - looks for bare `step_type`
- Line 251: `calculation_ulid = calc_doc.get(["meta", "id"], default=None)` - should be `["meta", "ulid"]`
- Line 264: `step_type = step_doc.get(["step_type_spec"], default=None)` - correct

**Code fixes needed first:**

### 5.0 src/quantumvitas/workflow/templates.py
```python
# Line 230 - FIND:
step_entry_type = step_entry.get("step_type") or step_entry.get("type")

# REPLACE WITH:
step_entry_type = step_entry.get("step_type_spec") or step_entry.get("step_type") or step_entry.get("type")

# Line 251 - FIND:
calculation_ulid = calc_doc.get(["meta", "id"], default=None)

# REPLACE WITH:
calculation_ulid = calc_doc.get(["meta", "ulid"], default=None) or calc_doc.get(["meta", "id"], default=None)
```

**Then update test fixtures:**

### 5.1 tests/unit/test_workflow.py
Update YAML fixtures to use `step_type_spec:` in step entries.

### 5.2 tests/unit/test_preset_integration.py
Same as above.

---

## CATEGORY 6: Job/Execution Graph Issues [MEDIUM - AGENT]

**Files:**
- tests/unit/execution/test_job_graph.py
- tests/unit/execution/test_qc_topology.py

**Pattern:** Job class may have old field names. Check `src/quantumvitas/execution/job_graph.py` for canonical field names and update tests.

---

## CATEGORY 7: Complex Integration Tests [HARDER - LEAVE FOR HUMAN]

These require deeper investigation or fixture regeneration:

- tests/contract_crawler/test_golden_contracts.py (need golden fixture regeneration)
- tests/contract_crawler/test_schema_preservation.py (schema expectations need review)
- tests/contract_crawler/test_gui_field_enforcement.py (may need golden regeneration)
- tests/cli/* (CLI output contracts need review)
- tests/daemon/test_gui_job_and_step_flows.py (complex daemon flows)

---

## CATEGORY 8: Post-Job and Manifest Tests [MEDIUM - AGENT]

**Files:**
- tests/unit/test_post_job.py
- tests/unit/test_manifest_effective_structure.py

**Pattern:** Check for old parameter names in function calls.

---

## Execution Order

1. **First:** Fix MockStep classes (Category 1) - ~7 files
2. **Second:** Fix function call parameters (Category 2) - ~2 files
3. **Third:** Fix YAML fixtures (Category 3) - ~6 files
4. **Fourth:** Fix assertions (Category 4) - ~4 files
5. **Fifth:** Fix workflow detection (Category 5) - needs investigation first
6. **Sixth:** Fix job graph (Category 6) - ~2 files
7. **Last:** Human handles Category 7

---

## Verification

After each category fix, run:
```bash
source .venv/bin/activate && python -m pytest <specific_test_file> -v --tb=short -n auto
```

Final verification:
```bash
source .venv/bin/activate && python -m pytest tests/gates/ -v --tb=short -n auto
```

Gate tests must remain 100% passing.

---

## Estimated Impact

- Category 1-4: ~150 test fixes (mechanical, agent-ready)
- Category 5-6: ~30 test fixes (needs some investigation)
- Category 7: ~75 tests (complex, human review needed)
