# GEN/SPEC Convergence: Mechanical Implementation Plan

**Date**: 2026-01-29 (Post-Rollback, Strict Convergence)
**Reference**: `docs/GEN_SPEC_SEMANTICS_REVIEW.md`
**Executor**: Cursor Auto (very dumb, follows instructions literally)

---

## Critical Rules for Executor

1. **NO FALLBACKS**: Never write `data.get("new") or data.get("old")` or `pop("x") or pop("y")`. If old key exists, raise `KeyError` or `ValueError`.
2. **NO ALIASES**: One field name per concept. Delete all alternatives.
3. **NO SCOPE CREEP**: Only change what is listed. Do not "improve" surrounding code.
4. **NO LOGIC CHANGES**: Rename fields only. Do not change algorithms, mappings, or execution logic.
5. **VALIDATE AFTER EACH PHASE**: Run full test suite before proceeding.
6. **YAML IS SPEC-ONLY**: Both `calculation.yaml` AND `step.yaml` store `step_type_spec`. Never persist `step_type_gen` to YAML.
7. **SINGLE SOURCE OF TRUTH**: All SPEC↔GEN conversions MUST use `registry.normalize_step_type_to_public()`. No hardcoded mapping dicts.

---

## Explicit Decisions

### Decision 1: Hard Error on Old Keys (NO FALLBACKS)

**WRONG** (fallback/compat shim):
```python
step["step_type_spec"] = step.pop("type", None) or step.pop("step_type", None)
```

**RIGHT** (hard error):
```python
# In loaders/shapers that read data:
if "type" in data or "step_type" in data:
    raise ValueError(f"Legacy field found. Run migration script first: {list(data.keys())}")
step_type_spec = data["step_type_spec"]  # KeyError if missing
```

**RIGHT** (in migration scripts ONLY):
```python
# Migration scripts are allowed to read old keys and write new keys
# But they are ONE-TIME scripts, not runtime code
old_value = data.pop("type", None) or data.pop("step_type", None)
data["step_type_spec"] = old_value
```

### Decision 2: Golden Patch Script Uses Registry SSOT

The patch script MUST NOT contain hardcoded `SPEC_TO_GEN` mapping. Instead:
```python
# Import and use the registry SSOT
import sys
sys.path.insert(0, "src")
from quantumvitas.workflow.registry import normalize_step_type_to_public

step_type_gen = normalize_step_type_to_public(step_type_spec)
```

### Decision 3: Surgical Identity Field Renames

**TARGETED for rename** (resource identity ULIDs):
| Old Pattern | New Pattern | Context |
|-------------|-------------|---------|
| `meta["id"]` or `meta.id` | `meta["ulid"]` or `meta.ulid` | Resource metadata block |
| `step_id` | `step_ulid` | Step identity field |
| `calc_id` | `calc_ulid` | Calculation identity field |
| `structure_id` | `structure_ulid` | Structure identity field |
| `project_id` | `project_ulid` | Project identity field |
| `job_id` | `job_ulid` | Job identity field |
| `run_id` | `run_ulid` | Run identity field |
| `event_id` | `event_ulid` | Event identity field |
| `parent_calculation_id` | `parent_calculation_ulid` | Parent reference |

**NOT TARGETED** (allowed to remain):
| Pattern | Reason |
|---------|--------|
| JSON-RPC `"id"` in request/response | Protocol-level, not resource identity |
| `request_id` | Request tracking, not resource |
| `correlation_id` | Tracing, not resource |
| `spec.id` → DELETE | This is step-type semantic, not identity (becomes `spec.step_type_gen`) |
| Function parameters named `id` | Local variable naming |
| `Job.id` (internal class attr) | Rename to `Job.ulid` only if exposed in serialization |

### Decision 4: YAML SPEC-Only Enforcement

**Rule**: `step_type_gen` MUST NEVER appear in any `.yaml` file.

**Workflow**:
1. Demo generator / materializers MAY accept GEN input (e.g., user says "scf")
2. They MUST convert to SPEC before writing YAML (e.g., write "qe_scf")
3. YAML loaders MUST read `step_type_spec` only
4. RPC shapers compute `step_type_gen` at response time via registry SSOT

**Gate pattern**:
```bash
# Must return 0 matches
rg "step_type_gen:" --glob "*.yaml" --glob "*.yml"
```

### Decision 5: Canonical QERecipe Location

**Canonical file**: `src/quantumvitas/drivers/qe/recipe.py`
**Canonical import**: `from quantumvitas.drivers.qe.recipe import QERecipe`

**Re-export only** (in `execution/recipes.py`):
```python
from quantumvitas.drivers.qe.recipe import QERecipe  # Re-export
```

**Gate pattern**:
```bash
# Must return exactly 1 match (the canonical definition)
rg "^class QERecipe" src/quantumvitas/
# Expected: src/quantumvitas/drivers/qe/recipe.py
```

### Decision 6: EXECUTABLE_MAP is OUT OF SCOPE

**DO NOT TOUCH**:
- `EXECUTABLE_MAP` dict in any file
- `spec.executable` field or logic
- Any execution routing logic
- Any engine selection logic

This migration renames field names only. It does not change how executables are resolved or how engines are selected.

### Decision 7: calc.yaml `type` Field Contains GEN → Must Convert to SPEC

**CURRENT STATE** (verified from `core/models.py:82`):
```python
type: Optional[str] = None  # ... stores PUBLIC type
```
The `type` field currently holds **GEN** values (e.g., "scf", "bands", "relax").

**TARGET STATE** (per Law 4):
calculation.yaml must store `step_type_spec` with **SPEC** values (e.g., "qe_scf").

**MIGRATION REQUIREMENT**:
When migrating calc.yaml files, the migration script MUST:
1. Read the old GEN value from `type` field
2. Convert GEN → SPEC using registry SSOT (or fallback: prepend engine prefix)
3. Write the SPEC value to `step_type_spec`

**GUI IMPACT**:
- Currently: GUI may render `type` directly (which is GEN, human-readable)
- After migration: calc.yaml has SPEC (ugly for display: "qe_scf")
- Solution: GUI MUST use `step_type_gen` from RPC response, NOT read calc.yaml directly
- RPC shapers provide BOTH `step_type_spec` and `step_type_gen`
- GUI displays `step_type_gen` for human-readable labels

**Example**:
```
Before migration:
  calc.yaml: { type: "scf" }  ← GEN value
  GUI renders: "scf" (human-readable)

After migration:
  calc.yaml: { step_type_spec: "qe_scf" }  ← SPEC value
  RPC response: { step_type_spec: "qe_scf", step_type_gen: "scf" }
  GUI displays: step_type_gen = "scf" (still human-readable)
```

**Auto guidance**:
- In Phase 6: from_dict() must NOT read `step_type_spec` and assume it's GEN
- In Phase 9: GUI MUST use `step_type_gen` for display, never `step_type_spec`
- In Phase 12: User migration script MUST convert GEN→SPEC values

---

## Test Suite Command (Run After Each Phase)

```bash
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

Abbreviated as `RUN_TESTS` in phase validations.

---

## Phase 0: Pre-Flight Checks

**Goal**: Verify starting state is clean.

### Validation

```bash
# Ensure tests pass before starting
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile

# Verify current state
git status  # Should be clean or only docs changes
```

---

## Phase 1: Delete Duplicate QERecipe

**Goal**: Single QERecipe definition in canonical location.

### Step 1.1: Verify Canonical Location

```bash
rg "^class QERecipe" src/quantumvitas/
```

**Expected output**:
```
src/quantumvitas/drivers/qe/recipe.py:class QERecipe(BaseRecipe):
src/quantumvitas/execution/recipes.py:class QERecipe(BaseRecipe):  # DUPLICATE - DELETE THIS
```

### Step 1.2: Delete Duplicate from execution/recipes.py

**File**: `src/quantumvitas/execution/recipes.py`
**Action**: DELETE the entire `class QERecipe` block (approximately lines 157-234).

**Keep intact**:
- All imports at top of file
- `TopologyError`, `verify_qc_topology`, `Recipe` protocol, `BaseRecipe` class
- The re-export line: `from quantumvitas.drivers.qe.recipe import QERecipe`

### Step 1.3: Verify Re-export Exists

After deletion, confirm this line exists in `execution/recipes.py`:
```python
from quantumvitas.drivers.qe.recipe import QERecipe
```

If it doesn't exist, ADD it near other re-exports.

### Validation

```bash
# Gate: Exactly 1 class definition
rg "^class QERecipe" src/quantumvitas/
# EXPECTED: Only src/quantumvitas/drivers/qe/recipe.py

# Module still importable via both paths
python -c "from quantumvitas.execution.recipes import QERecipe; print(QERecipe.__module__)"
# EXPECTED: quantumvitas.drivers.qe.recipe

python -c "from quantumvitas.drivers.qe.recipe import QERecipe; print('OK')"
# EXPECTED: OK

# RUN_TESTS
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

---

## Phase 2: Add API Facade for SPEC→GEN

**Goal**: Daemon-safe function for SPEC→GEN conversion (delegates to registry SSOT).

### Step 2.1: Add Facade Function

**File**: `src/quantumvitas/api/__init__.py`
**Action**: ADD this function (find suitable location near other exports):

```python
def get_step_type_gen(step_type_spec: str) -> str:
    """Convert SPEC to GEN via registry SSOT.

    Args:
        step_type_spec: Engine-prefixed type (e.g., "qe_scf")

    Returns:
        Engine-agnostic type (e.g., "scf")

    Raises:
        KeyError: If step_type_spec is not in registry
    """
    from quantumvitas.workflow.registry import normalize_step_type_to_public
    return normalize_step_type_to_public(step_type_spec)
```

### Step 2.2: Add to __all__ (if exists)

If file has `__all__`, add `"get_step_type_gen"` to it.

### Validation

```bash
python -c "from quantumvitas.api import get_step_type_gen; print(get_step_type_gen('qe_scf'))"
# EXPECTED: scf

# Gate: Function exists
rg "def get_step_type_gen" src/quantumvitas/api/
# EXPECTED: 1 match

# RUN_TESTS
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

---

## Phase 3: Rename StepTypeSpec Dataclass Fields

**Goal**: Canonical field names in registry dataclass.

### Step 3.1: Update Dataclass Definition

**File**: `src/quantumvitas/workflow/registry.py`
**Location**: StepTypeSpec dataclass (around lines 42-56)

**BEFORE**:
```python
@dataclass(frozen=True)
class StepTypeSpec:
    id: str
    machine_type: str
    public_type: str
    # ... other fields
```

**AFTER**:
```python
@dataclass(frozen=True)
class StepTypeSpec:
    step_type_spec: str   # SPEC: Engine-prefixed (e.g., "qe_scf")
    step_type_gen: str    # GEN: Engine-agnostic (e.g., "scf")
    # ... other fields (keep unchanged)
```

**Note**: DELETE the `id` field entirely. It was redundant with `public_type`.

### Step 3.2: Update All StepTypeSpec Instantiations

**File**: `src/quantumvitas/workflow/registry.py`
**Location**: `_STEP_TYPES` dict (approximately lines 166-626)

**BEFORE** (each entry):
```python
"qe_scf": StepTypeSpec(
    id="scf",
    machine_type="qe_scf",
    public_type="scf",
    # ... other fields
),
```

**AFTER** (each entry):
```python
"qe_scf": StepTypeSpec(
    step_type_spec="qe_scf",
    step_type_gen="scf",
    # ... other fields (keep unchanged)
),
```

Apply to ALL ~66 entries.

### Step 3.3: Update Registry Internal Methods

**File**: `src/quantumvitas/workflow/registry.py`

Find and rename these internal references:
- `spec.machine_type` → `spec.step_type_spec`
- `spec.public_type` → `spec.step_type_gen`
- `spec.id` → `spec.step_type_gen` (or DELETE if unused after id removal)
- `self._machine_to_spec` → `self._spec_to_obj` (optional clarity rename)
- `self._public_to_machine` → `self._gen_to_spec` (optional clarity rename)

### Step 3.4: Update normalize_step_type_to_public

**Location**: Around lines 890-913

Update internal field access to use new names. Function signature stays the same.

### Validation

```bash
python -c "
from quantumvitas.workflow.registry import get_registry
spec = get_registry().get('qe_scf')
print(f'SPEC={spec.step_type_spec}, GEN={spec.step_type_gen}')
"
# EXPECTED: SPEC=qe_scf, GEN=scf

# Gate: No old field names in registry.py
rg "\.machine_type\b|\.public_type\b" src/quantumvitas/workflow/registry.py
# EXPECTED: 0 matches

rg "spec\.id\b" src/quantumvitas/workflow/registry.py
# EXPECTED: 0 matches

# RUN_TESTS
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

---

## Phase 4: Update All spec.* Field Access Outside Registry

**Goal**: All code using StepTypeSpec uses new field names.

### Step 4.1: Find All Usages

```bash
rg "\.machine_type\b|\.public_type\b" src/quantumvitas/ --files-with-matches
rg "spec\.id\b" src/quantumvitas/ --files-with-matches | grep -v registry.py
```

### Step 4.2: Rename Each Usage

For EACH file found:
- `spec.machine_type` → `spec.step_type_spec`
- `spec.public_type` → `spec.step_type_gen`
- `spec.id` → `spec.step_type_gen`

**DO NOT change**:
- `step_id`, `calc_id`, etc. (identity fields - Phase 8)
- Function parameters named `id`
- Unrelated `.id` access on other objects

### Validation

```bash
# Gate: No old field access patterns
rg "\.machine_type\b|\.public_type\b" src/quantumvitas/
# EXPECTED: 0 matches

rg "spec\.id\b" src/quantumvitas/
# EXPECTED: 0 matches

# RUN_TESTS
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

---

## Phase 5: Rename step.yaml Output Fields

**Goal**: step.yaml uses `step_type_spec` and `meta.ulid`.

### Step 5.1: Update step_factory.py YAML Output

**File**: `src/quantumvitas/workflow/step_factory.py`

**Line ~68** - Change meta block:
```python
# BEFORE
"meta": {
    "id": step_id,

# AFTER
"meta": {
    "ulid": step_id,
```

**Line ~73** - Change step_type field:
```python
# BEFORE
"step_type": machine_step_type,

# AFTER
"step_type_spec": machine_step_type,
```

### Step 5.2: Update Step Model/Dataclass

**File**: `src/quantumvitas/calculation/step.py`

Find the step_type field (around line 29) and rename:
```python
# BEFORE
step_type: Optional[str] = None

# AFTER
step_type_spec: Optional[str] = None
```

### Step 5.3: Update Step YAML Loader (HARD ERROR on old keys)

Find where step.yaml is loaded. Update to:
```python
# HARD ERROR if old keys exist
if "step_type" in data and "step_type_spec" not in data:
    raise ValueError("Legacy 'step_type' key found. Run migration script.")
if "meta" in data and "id" in data["meta"] and "ulid" not in data["meta"]:
    raise ValueError("Legacy 'meta.id' key found. Run migration script.")

step_type_spec = data["step_type_spec"]  # KeyError if missing
ulid = data["meta"]["ulid"]  # KeyError if missing
```

### Step 5.4: Update All .step_type Access

```bash
rg "\.step_type\b" src/quantumvitas/ --files-with-matches
```

For each file, rename `.step_type` → `.step_type_spec`

### Validation

```bash
# Gate: No old field in factory
rg '"step_type":' src/quantumvitas/workflow/step_factory.py
# EXPECTED: 0 matches

rg '"id":' src/quantumvitas/workflow/step_factory.py | grep -v "ulid"
# EXPECTED: 0 matches (or only unrelated uses)

# Gate: No .step_type field access
rg "\.step_type\b" src/quantumvitas/ | grep -v "step_type_spec\|step_type_gen"
# EXPECTED: 0 matches

# RUN_TESTS
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

---

## Phase 6: Rename calculation.yaml Fields

**Goal**: calculation.yaml steps array uses `step_type_spec` and `step_ulid`.

**CRITICAL**: calculation.yaml stores `step_type_spec` (SPEC value like "qe_scf"), NOT `step_type_gen`.

**IMPORTANT**: The current `type` field holds GEN values (see Decision 7). During this migration:
- Existing calc.yaml files have GEN values ("scf") that must be converted to SPEC ("qe_scf")
- The migration scripts (Phase 12) handle this conversion
- The new `from_dict()` reads `step_type_spec` expecting SPEC values

### Step 6.1: Update CalculationStepEntry Model

**File**: `src/quantumvitas/core/models.py`

**Line ~81**:
```python
# BEFORE
step_id: Optional[str] = None

# AFTER
step_ulid: Optional[str] = None
```

**Line ~82**:
```python
# BEFORE
type: Optional[str] = None  # stores PUBLIC type

# AFTER
step_type_spec: Optional[str] = None  # SPEC type (e.g., "qe_scf")
```

### Step 6.2: DELETE step_type Property

**Lines ~88-95** - DELETE this entire property:
```python
@property
def step_type(self) -> Optional[str]:
    return self.type
```

### Step 6.3: Update to_dict()

**Lines ~108-109**:
```python
# BEFORE
if self.type:
    d["type"] = self.type

# AFTER
if self.step_type_spec:
    d["step_type_spec"] = self.step_type_spec
```

Also update `step_id` → `step_ulid` in serialization.

### Step 6.4: Update from_dict() (HARD ERROR on old keys)

```python
# HARD ERROR if old keys exist
if "type" in data and "step_type_spec" not in data:
    raise ValueError("Legacy 'type' key in calculation.yaml. Run migration script.")
if "step_id" in data and "step_ulid" not in data:
    raise ValueError("Legacy 'step_id' key in calculation.yaml. Run migration script.")

step_type_spec = data.get("step_type_spec")
step_ulid = data.get("step_ulid")
```

### Step 6.5: Update All Consumers

```bash
rg "entry\.type\b|\.step_type\b" src/quantumvitas/ --files-with-matches
rg "\.step_id\b" src/quantumvitas/ --files-with-matches
```

For each file:
- `.type` → `.step_type_spec`
- `.step_type` → `.step_type_spec`
- `.step_id` → `.step_ulid`

### Validation

```bash
# Gate: No old fields in models
rg "self\.type\b" src/quantumvitas/core/models.py
# EXPECTED: 0 matches

rg 'd\["type"\]' src/quantumvitas/core/models.py
# EXPECTED: 0 matches

rg "\.step_id\b" src/quantumvitas/core/models.py
# EXPECTED: 0 matches

# Gate: No step_type property
rg "def step_type\b" src/quantumvitas/core/models.py
# EXPECTED: 0 matches

# RUN_TESTS
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

---

## Phase 7: Delete Daemon Second-Truth Table

**Goal**: Remove hardcoded mapping, use API facade.

### Step 7.1: Delete _map_step_type_to_v0 Function

**File**: `src/quantumvitas/daemon/compat.py`
**Lines**: ~199-214

DELETE the entire function and its `TYPE_MAP` dict.

### Step 7.2: Add API Import

At top of `daemon/compat.py`:
```python
from quantumvitas.api import get_step_type_gen
```

### Step 7.3: Replace All Calls (NO FALLBACK PATTERN)

Find all calls:
```bash
rg "_map_step_type_to_v0" src/quantumvitas/daemon/compat.py
```

**Lines ~228, 432, 530, 717, 772, 924** - Replace each:

**WRONG** (fallback):
```python
step["step_type_spec"] = step.pop("type", None) or step.pop("step_type", None)
```

**RIGHT** (expects already-migrated data):
```python
# Data should already have step_type_spec from kernel
# Just add step_type_gen for RPC response
step["step_type_gen"] = get_step_type_gen(step["step_type_spec"])
```

If the shaper receives data with old field names, that's a bug in the kernel layer, not something to paper over.

### Step 7.4: Rename Identity Fields in Shapers

Each shaper that outputs step data:
- `step["id"]` → `step["ulid"]` (if resource ULID, not JSON-RPC id)
- `step["step_id"]` → `step["step_ulid"]`
- `step["parent_calculation_id"]` → `step["parent_calculation_ulid"]`

### Validation

```bash
# Gate: No second-truth function
rg "_map_step_type_to_v0" src/quantumvitas/
# EXPECTED: 0 matches

# Gate: No hardcoded TYPE_MAP
rg "TYPE_MAP\s*=" src/quantumvitas/daemon/
# EXPECTED: 0 matches

# RUN_TESTS
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

---

## Phase 8: Rename Resource Identity Fields

**Goal**: All resource ULIDs use `*_ulid` naming.

### Step 8.1: Identify Files with Identity Fields

```bash
rg "\bstep_id\b|\bcalc_id\b|\bstructure_id\b|\bproject_id\b|\bjob_id\b|\brun_id\b|\bevent_id\b" src/quantumvitas/ --files-with-matches
```

### Step 8.2: Surgical Renames (Resource Identity Only)

For each file, rename ONLY when the field represents a resource ULID:

| Old | New | Files (from Review doc) |
|-----|-----|-------------------------|
| `step_id` | `step_ulid` | `core/models.py`, `api/types/calculation.py`, `api/types/run.py`, `history/storage.py`, `history/digests.py`, `engine/orca_engine.py` |
| `calc_id` | `calc_ulid` | `history/storage.py`, `api/types/calculation.py` |
| `structure_id` | `structure_ulid` | `engine/vasp_engine.py`, `engine/orca_engine.py`, `engine/pyscf_engine.py`, `engine/lammps_engine.py`, `engine/cp2k_engine.py`, `core/models.py` |
| `project_id` | `project_ulid` | `history/storage.py` |
| `job_id` | `job_ulid` | `execution/job_graph.py` (only if exposed in serialization) |
| `run_id` | `run_ulid` | `history/storage.py` |
| `event_id` | `event_ulid` | `history/storage.py` |
| `parent_calculation_id` | `parent_calculation_ulid` | `daemon/compat.py`, API responses |

**DO NOT rename**:
- JSON-RPC `"id"` in `daemon/server.py`
- `request_id`, `correlation_id`
- Function parameters named `id` (local scope)
- `Job.id` internal attribute (unless serialized)

### Step 8.3: Update API Type Definitions

**File**: `src/quantumvitas/api/types/calculation.py`
**File**: `src/quantumvitas/api/types/run.py`

Rename fields in dataclasses/TypedDicts.

### Validation

```bash
# Spot check - no step_id in models (should be step_ulid)
rg "\bstep_id\b" src/quantumvitas/core/models.py
# EXPECTED: 0 matches

# JSON-RPC id should still exist (allowed)
rg '"id":' src/quantumvitas/daemon/server.py
# EXPECTED: matches (this is protocol-level, allowed)

# RUN_TESTS
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

---

## Phase 9: Update GUI TypeScript

**Goal**: GUI types match new RPC contract.

**CRITICAL** (per Decision 7):
- RPC responses now include BOTH `step_type_spec` (SPEC) and `step_type_gen` (GEN)
- GUI MUST display `step_type_gen` for human-readable labels (e.g., "SCF", "Bands")
- GUI MUST NOT display `step_type_spec` directly (e.g., "qe_scf" is ugly for users)
- Any code that previously displayed `.type` (which was GEN) should now use `.step_type_gen`

### Step 9.1: Update StepInfo Interface

**File**: `gui/src/types/qv.ts`
**Location**: ~line 194

**BEFORE**:
```typescript
export interface StepInfo {
  id: string;
  type: string;
  step_file: string;
}
```

**AFTER**:
```typescript
export interface StepInfo {
  ulid: string;
  step_type_spec: string;
  step_type_gen: string;
  step_file: string;
}
```

### Step 9.2: Update StepDetail Interface

**Location**: ~line 417

**BEFORE**:
```typescript
export interface StepDetail {
  id: string;
  step_type: string;
  ...
}
```

**AFTER**:
```typescript
export interface StepDetail {
  ulid: string;
  step_type_spec: string;
  step_type_gen: string;
  ...
}
```

### Step 9.3: Update Component Field Access

```bash
rg "\.type\b" gui/src/components/ --files-with-matches
rg "\.id\b" gui/src/components/ --files-with-matches
```

For step-related access:
- `.type` → `.step_type_gen` (for display - this is the human-readable type)
- `.id` → `.ulid` (for step identity)
- `.step_type` → `.step_type_gen` (for display)

**Rule**: GUI displays `step_type_gen`. Never displays raw `step_type_spec`.

**Why**: Previously `.type` held GEN values ("scf") which were displayed directly.
Now calc.yaml holds SPEC values ("qe_scf"), but RPC responses include both fields.
GUI must use `step_type_gen` to maintain human-readable display.

**Example component update**:
```typescript
// BEFORE: displayed GEN from old .type field
<span>{step.type.toUpperCase()}</span>  // "SCF"

// AFTER: display GEN from new .step_type_gen field
<span>{step.step_type_gen.toUpperCase()}</span>  // "SCF"

// WRONG: displaying SPEC directly
<span>{step.step_type_spec}</span>  // "qe_scf" - ugly!
```

### Validation

```bash
cd gui && npm run type-check
# EXPECTED: No type errors

# RUN_TESTS (Python)
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

---

## Phase 10: Patch Golden Fixtures (Using Registry SSOT)

**Goal**: Golden fixtures have new field names. No hardcoded mapping tables.

**CRITICAL**: The patch script MUST use registry SSOT, not a hardcoded dict.

### Step 10.1: Create Patch Script

**File**: `tools/patch_golden_convergence.py`

```python
#!/usr/bin/env python3
"""
Patch golden fixtures for GEN/SPEC convergence.
Uses registry SSOT for SPEC→GEN conversion. NO hardcoded mapping.
"""
import json
import sys
from pathlib import Path

# Add src to path for registry import
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from quantumvitas.workflow.registry import normalize_step_type_to_public

GOLDEN_DIR = Path("tests/fixtures/golden_0873ebf/daemon")


def spec_to_gen(step_type_spec: str) -> str:
    """Convert SPEC to GEN using registry SSOT."""
    try:
        return normalize_step_type_to_public(step_type_spec)
    except (KeyError, ValueError):
        # Fallback for unknown types: strip engine prefix
        if "_" in step_type_spec:
            return step_type_spec.split("_", 1)[1]
        return step_type_spec


def patch_step(step: dict) -> bool:
    """Patch a step object. Returns True if modified."""
    modified = False

    # Rename step_type → step_type_spec + step_type_gen
    if "step_type" in step and "step_type_spec" not in step:
        spec_value = step.pop("step_type")
        step["step_type_spec"] = spec_value
        step["step_type_gen"] = spec_to_gen(spec_value)
        modified = True

    # Rename type → step_type_spec + step_type_gen
    if "type" in step and "step_type_spec" not in step:
        old_type = step.pop("type")
        if "_" in old_type:  # Already SPEC
            step["step_type_spec"] = old_type
            step["step_type_gen"] = spec_to_gen(old_type)
        else:  # GEN value - assume QE for golden fixtures
            step["step_type_gen"] = old_type
            step["step_type_spec"] = f"qe_{old_type}"
        modified = True

    # Rename id → ulid (only for normalized placeholders or 26-char ULIDs)
    if "id" in step:
        val = step["id"]
        if val == "<NORMALIZED_ID>" or (isinstance(val, str) and len(val) == 26 and val.isalnum()):
            step["ulid"] = step.pop("id")
            modified = True

    # Rename step_id → step_ulid
    if "step_id" in step:
        step["step_ulid"] = step.pop("step_id")
        modified = True

    return modified


def patch_recursive(data, depth=0) -> bool:
    """Recursively patch data structure."""
    modified = False

    if isinstance(data, dict):
        # Check if this looks like a step object
        if any(k in data for k in ("type", "step_type", "step_file", "parameters")):
            if patch_step(data):
                modified = True

        # Patch meta.id → meta.ulid
        if "meta" in data and isinstance(data["meta"], dict):
            meta = data["meta"]
            if "id" in meta:
                meta["ulid"] = meta.pop("id")
                modified = True

        # Rename parent_calculation_id → parent_calculation_ulid
        if "parent_calculation_id" in data:
            data["parent_calculation_ulid"] = data.pop("parent_calculation_id")
            modified = True

        # Recurse
        for value in list(data.values()):
            if isinstance(value, (dict, list)):
                if patch_recursive(value, depth + 1):
                    modified = True

    elif isinstance(data, list):
        for item in data:
            if patch_recursive(item, depth + 1):
                modified = True

    return modified


def main():
    if not GOLDEN_DIR.exists():
        print(f"Golden directory not found: {GOLDEN_DIR}")
        sys.exit(1)

    for path in sorted(GOLDEN_DIR.glob("*.json")):
        with open(path) as f:
            data = json.load(f)

        if patch_recursive(data):
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
                f.write("\n")
            print(f"Patched: {path.name}")
        else:
            print(f"No changes: {path.name}")


if __name__ == "__main__":
    main()
```

### Step 10.2: Run Patch Script

```bash
python tools/patch_golden_convergence.py
```

### Step 10.3: Review Diff

```bash
git diff tests/fixtures/golden_0873ebf/daemon/ --stat
git diff tests/fixtures/golden_0873ebf/daemon/ | head -200
```

Verify:
- Only field names changed, not values
- `step_type_spec` contains SPEC values (with underscore)
- `step_type_gen` contains GEN values (without prefix)

### Validation

```bash
# Gate: No bare "step_type" in golden
rg '"step_type":' tests/fixtures/golden_0873ebf/daemon/
# EXPECTED: 0 matches

# Gate: Both new fields present
rg '"step_type_spec":' tests/fixtures/golden_0873ebf/daemon/
# EXPECTED: Multiple matches

rg '"step_type_gen":' tests/fixtures/golden_0873ebf/daemon/
# EXPECTED: Multiple matches

# RUN_TESTS
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

---

## Phase 11: Migrate Demo Projects

**Goal**: Demo projects use `step_type_spec` with SPEC values.

**Rule**: Demo materializers may accept GEN input, but MUST write SPEC to YAML.

### Step 11.1: Create Migration Script (Uses Registry SSOT)

**File**: `tools/migrate_demo_projects.py`

```python
#!/usr/bin/env python3
"""
Migrate demo projects to step_type_spec with SPEC values.
Uses registry SSOT for GEN→SPEC conversion.
"""
import sys
from pathlib import Path

import yaml

# Add src to path for registry import
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from quantumvitas.workflow.registry import get_registry


def gen_to_spec(step_type_gen: str, engine: str = "qe") -> str:
    """Convert GEN to SPEC using registry SSOT."""
    registry = get_registry()
    spec = registry.get_for_engine(step_type_gen, engine)
    if spec:
        return spec.step_type_spec
    # Fallback: prepend engine prefix
    return f"{engine}_{step_type_gen}"


def migrate_demo(path: Path) -> bool:
    content = path.read_text()
    data = yaml.safe_load(content)
    if data is None:
        return False

    modified = False

    for calc in data.get("calculations", []):
        engine = calc.get("engine", "qe")  # Default to QE
        for step in calc.get("steps", []):
            if "step_type" in step and "step_type_spec" not in step:
                old = step.pop("step_type")
                # Convert GEN to SPEC if needed
                if "_" not in old:
                    step["step_type_spec"] = gen_to_spec(old, engine)
                else:
                    step["step_type_spec"] = old
                modified = True

            # Rename meta.id → meta.ulid
            if "meta" in step and "id" in step["meta"]:
                step["meta"]["ulid"] = step["meta"].pop("id")
                modified = True

    if modified:
        path.write_text(yaml.safe_dump(data, sort_keys=False, default_flow_style=False))
    return modified


def main():
    demo_dir = Path("resources/demo_projects")
    if not demo_dir.exists():
        print(f"Demo directory not found: {demo_dir}")
        return

    for p in sorted(demo_dir.glob("*.yml")):
        if migrate_demo(p):
            print(f"Migrated: {p}")
        else:
            print(f"No changes: {p}")


if __name__ == "__main__":
    main()
```

### Step 11.2: Run Migration

```bash
python tools/migrate_demo_projects.py
```

### Validation

```bash
# Gate: No bare step_type in demos
rg "step_type:" resources/demo_projects/ | grep -v "step_type_spec"
# EXPECTED: 0 matches

# Gate: No step_type_gen persisted to YAML
rg "step_type_gen:" resources/demo_projects/
# EXPECTED: 0 matches

# Gate: All step_type_spec have SPEC values (with underscore)
rg 'step_type_spec:\s*[a-z]+$' resources/demo_projects/
# EXPECTED: 0 matches (all should have underscore like qe_scf)

# RUN_TESTS
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

---

## Phase 12: Create User Migration Script

**Goal**: Provide script for users to migrate existing projects.

**Note**: This is documentation/tooling only. Not auto-run.

### Step 12.1: Create Script

**File**: `tools/migrate_user_project.py`

```python
#!/usr/bin/env python3
"""
Migrate user project YAML files to new field names.

IMPORTANT: calc.yaml `type` field contains GEN values ("scf").
           Must convert to SPEC values ("qe_scf") using registry SSOT.

Usage: python migrate_user_project.py /path/to/project
"""
import re
import sys
from pathlib import Path

import yaml

# Add src to path for registry import
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from quantumvitas.workflow.registry import get_registry


def gen_to_spec(step_type_gen: str, engine: str = "qe") -> str:
    """Convert GEN to SPEC using registry SSOT."""
    registry = get_registry()
    spec = registry.get_for_engine(step_type_gen, engine)
    if spec:
        return spec.step_type_spec
    # Fallback: prepend engine prefix
    print(f"  Warning: Unknown step type '{step_type_gen}', using fallback")
    return f"{engine}_{step_type_gen}"


def migrate_step_yaml(path: Path) -> bool:
    """Migrate step.yaml file.

    step.yaml step_type field already contains SPEC values.
    Only need to rename the key, not convert the value.
    """
    content = path.read_text()
    modified = False

    # step_type → step_type_spec (value stays same, it's already SPEC)
    if re.search(r'^step_type:', content, re.MULTILINE) and 'step_type_spec:' not in content:
        content = re.sub(r'^step_type:', 'step_type_spec:', content, flags=re.MULTILINE)
        modified = True

    # meta block: id → ulid
    if re.search(r'^  id:', content, re.MULTILINE):
        content = re.sub(r'^(  )id:', r'\1ulid:', content, flags=re.MULTILINE)
        modified = True

    if modified:
        path.write_text(content)
    return modified


def migrate_calc_yaml(path: Path) -> bool:
    """Migrate calculation.yaml file.

    IMPORTANT: calc.yaml `type` field contains GEN values ("scf").
    Must convert to SPEC values ("qe_scf").
    """
    content = path.read_text()
    data = yaml.safe_load(content)
    if data is None:
        return False

    modified = False

    # Determine engine from calculation metadata (default to QE)
    engine = data.get("engine", "qe")

    for step in data.get("steps", []):
        # type (GEN) → step_type_spec (SPEC) - MUST CONVERT VALUE
        if "type" in step and "step_type_spec" not in step:
            old_gen = step.pop("type")
            # Convert GEN → SPEC using registry SSOT
            if "_" not in old_gen:  # GEN value (no underscore)
                step["step_type_spec"] = gen_to_spec(old_gen, engine)
            else:  # Already SPEC (has underscore)
                step["step_type_spec"] = old_gen
            modified = True

        # step_id → step_ulid
        if "step_id" in step and "step_ulid" not in step:
            step["step_ulid"] = step.pop("step_id")
            modified = True

    # meta.id → meta.ulid
    if "meta" in data and "id" in data["meta"] and "ulid" not in data["meta"]:
        data["meta"]["ulid"] = data["meta"].pop("id")
        modified = True

    if modified:
        path.write_text(yaml.safe_dump(data, sort_keys=False))
    return modified


def main():
    if len(sys.argv) < 2:
        print("Usage: python migrate_user_project.py /path/to/project")
        sys.exit(1)

    project_dir = Path(sys.argv[1])
    if not project_dir.exists():
        print(f"Project directory not found: {project_dir}")
        sys.exit(1)

    print(f"Migrating project: {project_dir}")
    print("Note: calc.yaml 'type' (GEN) will be converted to 'step_type_spec' (SPEC)")

    # Migrate calculation.yaml files
    for p in project_dir.rglob("calculation.yaml"):
        if migrate_calc_yaml(p):
            print(f"  Migrated: {p}")

    # Migrate step.yaml files
    for p in project_dir.rglob("*.step.yaml"):
        if migrate_step_yaml(p):
            print(f"  Migrated: {p}")

    print("Done.")


if __name__ == "__main__":
    main()
```

### Validation

Script created. Manual testing only.

---

## Phase 13: Gate Tests

**Goal**: Automated enforcement of convergence invariants.

### Step 13.1: Create Gate Test File

**File**: `tests/gates/test_gen_spec_convergence_gate.py`

```python
"""
Gate tests for GEN/SPEC vocabulary convergence.
These tests enforce vocabulary invariants and must pass.
"""
import subprocess

import pytest


def rg_count(pattern: str, path: str) -> int:
    """Run ripgrep and return match count."""
    cmd = f"rg -c '{pattern}' {path} 2>/dev/null || true"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    lines = [l for l in result.stdout.strip().split("\n") if l and ":" in l]
    return sum(int(l.split(":")[-1]) for l in lines) if lines else 0


class TestBannedStepTypeVocabulary:
    """Step-type vocabulary must use only step_type_spec/step_type_gen."""

    def test_no_bare_step_type_in_step_factory(self):
        count = rg_count(r'"step_type":', "src/quantumvitas/workflow/step_factory.py")
        assert count == 0, "step_factory.py writes bare 'step_type'"

    def test_no_bare_type_field_in_models(self):
        count = rg_count(r'self\.type\b', "src/quantumvitas/core/models.py")
        assert count == 0, "models.py has self.type"

    def test_no_type_dict_key_in_models(self):
        count = rg_count(r'd\["type"\]', "src/quantumvitas/core/models.py")
        assert count == 0, "models.py writes d['type']"

    def test_no_second_truth_mapping(self):
        count = rg_count(r"_map_step_type_to_v0", "src/quantumvitas/daemon/")
        assert count == 0, "Hardcoded mapping table exists in daemon"

    def test_no_machine_type_in_registry(self):
        count = rg_count(r"\.machine_type\b", "src/quantumvitas/workflow/registry.py")
        assert count == 0, "registry.py still uses .machine_type"

    def test_no_public_type_in_registry(self):
        count = rg_count(r"\.public_type\b", "src/quantumvitas/workflow/registry.py")
        assert count == 0, "registry.py still uses .public_type"

    def test_no_spec_id_in_registry(self):
        count = rg_count(r"spec\.id\b", "src/quantumvitas/workflow/registry.py")
        assert count == 0, "registry.py still uses spec.id"


class TestCanonicalQERecipe:
    """QERecipe must have single canonical definition."""

    def test_single_qerecipe_class(self):
        result = subprocess.run(
            ["rg", "-l", "^class QERecipe", "src/quantumvitas/"],
            capture_output=True, text=True
        )
        files = [f for f in result.stdout.strip().split("\n") if f]
        assert len(files) == 1, f"QERecipe defined in multiple files: {files}"
        assert "drivers/qe/recipe.py" in files[0], f"QERecipe not in canonical location: {files}"


class TestRequiredVocabulary:
    """Required vocabulary must be present."""

    def test_step_type_spec_in_factory(self):
        count = rg_count(r'"step_type_spec":', "src/quantumvitas/workflow/step_factory.py")
        assert count > 0, "step_factory.py missing step_type_spec"

    def test_meta_ulid_in_factory(self):
        count = rg_count(r'"ulid":', "src/quantumvitas/workflow/step_factory.py")
        assert count > 0, "step_factory.py missing meta.ulid"

    def test_api_facade_exists(self):
        count = rg_count(r"def get_step_type_gen", "src/quantumvitas/api/")
        assert count > 0, "API missing get_step_type_gen facade"

    def test_registry_has_step_type_spec_field(self):
        count = rg_count(r"step_type_spec:\s*str", "src/quantumvitas/workflow/registry.py")
        assert count > 0, "StepTypeSpec missing step_type_spec field"

    def test_registry_has_step_type_gen_field(self):
        count = rg_count(r"step_type_gen:\s*str", "src/quantumvitas/workflow/registry.py")
        assert count > 0, "StepTypeSpec missing step_type_gen field"


class TestYamlSpecOnly:
    """YAML files must not contain step_type_gen."""

    def test_no_step_type_gen_in_demo_yaml(self):
        count = rg_count(r"step_type_gen:", "resources/demo_projects/")
        assert count == 0, "Demo YAML files contain step_type_gen"

    def test_no_bare_step_type_in_golden(self):
        count = rg_count(r'"step_type":', "tests/fixtures/golden_0873ebf/daemon/")
        assert count == 0, "Golden fixtures have bare step_type"


class TestIdentityFieldsRenamed:
    """Resource identity fields must use *_ulid naming."""

    def test_no_step_id_in_models(self):
        count = rg_count(r"\bstep_id\b", "src/quantumvitas/core/models.py")
        assert count == 0, "models.py still has step_id"

    def test_no_meta_id_in_factory(self):
        # Check specifically for "id": in meta context
        count = rg_count(r'"id":\s*step_id', "src/quantumvitas/workflow/step_factory.py")
        assert count == 0, "step_factory.py still writes meta.id"
```

### Validation

```bash
python -m pytest tests/gates/test_gen_spec_convergence_gate.py -v
# EXPECTED: All tests pass

# RUN_TESTS
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

---

## Phase 14: Final Validation

**Goal**: All tests pass, all gates green.

### Step 14.1: Run Full Test Suite

```bash
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

### Step 14.2: Run All Gate Patterns Manually

```bash
echo "=== Banned vocabulary gates ==="
rg '"step_type":' src/quantumvitas/workflow/step_factory.py && echo "FAIL" || echo "PASS"
rg '_map_step_type_to_v0' src/quantumvitas/ && echo "FAIL" || echo "PASS"
rg '\.machine_type\b' src/quantumvitas/workflow/registry.py && echo "FAIL" || echo "PASS"
rg '\.public_type\b' src/quantumvitas/workflow/registry.py && echo "FAIL" || echo "PASS"
rg 'spec\.id\b' src/quantumvitas/workflow/registry.py && echo "FAIL" || echo "PASS"

echo "=== QERecipe canonical location ==="
rg -l '^class QERecipe' src/quantumvitas/
# Should show ONLY: src/quantumvitas/drivers/qe/recipe.py

echo "=== YAML SPEC-only ==="
rg 'step_type_gen:' resources/demo_projects/ && echo "FAIL" || echo "PASS"
rg '"step_type":' tests/fixtures/golden_0873ebf/daemon/ && echo "FAIL" || echo "PASS"
```

### Step 14.3: TypeScript Check

```bash
cd gui && npm run type-check
```

### Step 14.4: Final Commit

```bash
git add -A
git commit -m "GEN/SPEC convergence: ONE CUT rename of all step-type and identity fields

Summary:
- Delete duplicate QERecipe from execution/recipes.py (canonical: drivers/qe/recipe.py)
- Rename StepTypeSpec fields: machine_type→step_type_spec, public_type→step_type_gen, delete id
- Rename step.yaml: step_type→step_type_spec, meta.id→meta.ulid
- Rename calculation.yaml: type→step_type_spec, step_id→step_ulid
- Delete _map_step_type_to_v0 second-truth table from daemon
- Add get_step_type_gen API facade (delegates to registry SSOT)
- Rename resource identity fields: *_id→*_ulid
- Patch golden fixtures (using registry SSOT, no hardcoded mapping)
- Migrate demo projects to step_type_spec with SPEC values
- Add gate tests enforcing vocabulary convergence

Rules enforced:
- NO fallbacks/compat shims - old keys raise errors
- YAML is SPEC-only - step_type_gen never persisted
- Single SSOT for SPEC↔GEN mapping (workflow/registry.py)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Gate Patterns Reference

### Must Return 0 Matches (Banned)

| Pattern | Target | Meaning |
|---------|--------|---------|
| `rg '"step_type":' src/quantumvitas/workflow/step_factory.py` | step_factory | No bare step_type output |
| `rg '_map_step_type_to_v0' src/quantumvitas/` | daemon | No second-truth table |
| `rg '\.machine_type\b' src/quantumvitas/workflow/registry.py` | registry | Old field gone |
| `rg '\.public_type\b' src/quantumvitas/workflow/registry.py` | registry | Old field gone |
| `rg 'spec\.id\b' src/quantumvitas/workflow/registry.py` | registry | Old field gone |
| `rg '"step_type":' tests/fixtures/golden_0873ebf/` | fixtures | Fixtures migrated |
| `rg 'step_type_gen:' resources/demo_projects/` | demos | GEN not in YAML |
| `rg '\bstep_id\b' src/quantumvitas/core/models.py` | models | Identity renamed |

### Must Return Exactly 1 Match (Canonical)

| Pattern | Target | Meaning |
|---------|--------|---------|
| `rg -l '^class QERecipe' src/quantumvitas/` | QERecipe | Single definition |

### Allowed Patterns (NOT targeted)

| Pattern | Reason |
|---------|--------|
| `"id":` in `daemon/server.py` | JSON-RPC protocol ID |
| `request_id`, `correlation_id` | Tracing, not resource identity |
| `EXECUTABLE_MAP` | Out of scope (execution logic) |
| `spec.executable` | Out of scope (execution logic) |

---

## Dependency Graph

```
Phase 0: Pre-flight
    │
    v
Phase 1: Delete duplicate QERecipe
    │
    v
Phase 2: Add API facade ─────────────────────┐
    │                                         │
    v                                         │
Phase 3: Rename StepTypeSpec fields           │
    │                                         │
    v                                         │
Phase 4: Update all spec.* access             │
    │                                         │
    ├────────────┬────────────┐               │
    v            v            v               │
Phase 5      Phase 6      Phase 8             │
(step.yaml)  (calc.yaml)  (identity)          │
    │            │            │               │
    └────────────┴────────────┘               │
                 │                            │
                 v                            │
           Phase 7: Daemon cleanup ←──────────┘
                 │
                 v
           Phase 9: GUI updates
                 │
                 v
       ┌─────────┴─────────┐
       v                   v
   Phase 10            Phase 11
   (fixtures)          (demos)
       │                   │
       └─────────┬─────────┘
                 v
           Phase 12: User migration script
                 │
                 v
           Phase 13: Gate tests
                 │
                 v
           Phase 14: Final validation
```

---

## DO NOT (Guardrails for Auto)

### Absolutely Forbidden

- **DO NOT** add fallbacks: `data.get("new") or data.get("old")`
- **DO NOT** add aliases: keeping both old and new field names
- **DO NOT** add deprecation warnings: this is ONE CUT, not gradual
- **DO NOT** regenerate golden fixtures from scratch (only patch)
- **DO NOT** rename GEN string values (e.g., "scf" stays "scf")

### Out of Scope (Do Not Touch)

- **DO NOT** modify `EXECUTABLE_MAP` or executable resolution logic
- **DO NOT** modify engine selection logic
- **DO NOT** modify recipe execution logic
- **DO NOT** modify job scheduling logic
- **DO NOT** add new features or "improvements"
- **DO NOT** refactor unrelated code
- **DO NOT** change test assertions beyond field name updates
- **DO NOT** modify JSON-RPC protocol handling (request/response `id`)

### Identity Field Scope

- **DO** rename: `step_id`, `calc_id`, `structure_id`, `project_id`, `job_id`, `run_id`, `event_id`, `parent_calculation_id`, `meta.id`
- **DO NOT** rename: JSON-RPC `"id"`, `request_id`, `correlation_id`, function parameter `id`

---

## Summary: Files Changed

| Phase | File | Action |
|-------|------|--------|
| 1 | `execution/recipes.py` | DELETE duplicate QERecipe class |
| 2 | `api/__init__.py` | ADD get_step_type_gen facade |
| 3 | `workflow/registry.py` | RENAME dataclass fields, UPDATE all instances |
| 4 | 32+ files | RENAME spec.* field access |
| 5 | `workflow/step_factory.py` | RENAME output fields |
| 5 | `calculation/step.py` | RENAME field |
| 6 | `core/models.py` | RENAME fields, DELETE property, ADD hard error |
| 7 | `daemon/compat.py` | DELETE function, UPDATE shapers |
| 8 | 15+ files | RENAME *_id → *_ulid |
| 9 | `gui/src/types/qv.ts` | RENAME interface fields |
| 9 | `gui/src/components/*.tsx` | UPDATE field access |
| 10 | `tests/fixtures/golden_*/daemon/*.json` | PATCH fields (via script) |
| 11 | `resources/demo_projects/*.yml` | MIGRATE fields (via script) |
| 12 | `tools/migrate_user_project.py` | NEW script |
| 13 | `tests/gates/test_gen_spec_convergence_gate.py` | NEW tests |
