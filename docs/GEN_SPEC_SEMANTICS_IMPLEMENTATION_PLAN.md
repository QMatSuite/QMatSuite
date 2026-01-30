# !! OBSOLETE - DO NOT IMPLEMENT !!

---

> **STATUS: ROLLED BACK**
>
> This implementation plan is **OBSOLETE**. The repository was rolled back due to
> semantic explosion from GEN/SPEC/id/public conflicts.
>
> **See instead**: `docs/GEN_SPEC_CONVERGENCE_IMPLEMENTATION_PLAN.md`
>
> **Archive note**: `docs/ARCHIVED_GEN_SPEC_PLAN_OBSOLETE.md`

---

# GEN/SPEC Step Type Semantics Implementation Plan (OBSOLETE)

**For**: Cursor Auto (Mechanical Execution)
**Reference**: `docs/GEN_SPEC_SEMANTICS_REVIEW.md`
**Date**: 2026-01-29
**Status**: **ROLLED BACK - DO NOT IMPLEMENT**

---

## Prerequisites

```bash
# Activate virtual environment
source .venv/bin/activate

# Verify tests pass before starting
python -m pytest tests/gates/test_daemon_kernel_ban.py -v
```

---

## Phase 1: Update Kernel Registry SSOT + Add API Facade

**Goal**: Fix registry `public_type` values for Law F compliance, then expose via thin API facade.

### Architecture Principle (Law J)

The SSOT for SPEC→GEN mapping is `StepTypeSpec.public_type` in the kernel registry.
- **NO** hardcoded mapping table in API (would drift)
- **NO** inference/fallback like `split("_")` (creates hidden second source)
- API exposes a thin facade that delegates to kernel registry

### Step 1.1: Fix Registry `public_type` Values (Law F)

**File**: `src/quantumvitas/workflow/registry.py`

**Change 1** (line ~204-214): Update `qe_bands_pw` public_type

**Find**:
```python
    "qe_bands_pw": StepTypeSpec(
        id="bands_pw",
        machine_type="qe_bands_pw",
        public_type="bands_pw",
```

**Replace with**:
```python
    "qe_bands_pw": StepTypeSpec(
        id="bands_pw",
        machine_type="qe_bands_pw",
        public_type="bands",  # Law F: GEN="bands" (eigenvalues, not plottable)
```

**Change 2** (line ~252-262): Update `qe_bands` public_type

**Find**:
```python
    "qe_bands": StepTypeSpec(
        id="bands",
        machine_type="qe_bands",
        public_type="bands",
```

**Replace with**:
```python
    "qe_bands": StepTypeSpec(
        id="bands",
        machine_type="qe_bands",
        public_type="bandpp",  # Law F: GEN="bandpp" (post-processing, plottable)
```

### Step 1.2: Add Thin API Facade (Law I/J Compliant)

**File**: `src/quantumvitas/api/__init__.py`

**Add export** (at top of file with other exports):
```python
from quantumvitas.workflow.registry import normalize_step_type_to_public as get_step_type_gen
```

**Alternative** (if explicit wrapper preferred):
```python
# In __init__.py
def get_step_type_gen(spec_type: str) -> str:
    """
    Map SPEC step_type to GEN step_type_gen.

    Thin facade over kernel registry SSOT (Law J).
    MUST NOT contain any mapping logic - delegates to registry.
    """
    from quantumvitas.workflow.registry import normalize_step_type_to_public
    return normalize_step_type_to_public(spec_type)
```

**Validation**:
```bash
python -c "from quantumvitas.api import get_step_type_gen; print(get_step_type_gen('qe_bands')); print(get_step_type_gen('qe_bands_pw'))"
# Expected output:
# bandpp
# bands
```

---

## Phase 2: Update Daemon Compat to Add `step_type_gen`

**Goal**: All step-bearing RPC responses include `step_type_gen` field.

### Step 2.1: Add helper function to compat.py

**File**: `src/quantumvitas/daemon/compat.py`

**Location**: After line 214 (after `_map_step_type_to_v0`)

**Add**:
```python
def _add_step_type_gen(step: Dict[str, Any], type_field: str = "step_type") -> None:
    """
    Add step_type_gen field to step dict.

    Uses API function to map SPEC→GEN without kernel import.

    Args:
        step: Step dict to modify (in place)
        type_field: Field name containing SPEC type ("step_type" or "type")
    """
    from quantumvitas.api.step_type_mapping import get_step_type_gen

    spec_type = step.get(type_field, "")
    if spec_type:
        step["step_type_gen"] = get_step_type_gen(spec_type)
```

### Step 2.2: Update `_shape_step_detail()`

**File**: `src/quantumvitas/daemon/compat.py`
**Line**: ~905-926

**Find**:
```python
def _shape_step_detail(response: Dict[str, Any]) -> Dict[str, Any]:
```

**Replace entire function with**:
```python
def _shape_step_detail(response: Dict[str, Any]) -> Dict[str, Any]:
    """Shape step detail response for v0 compat.

    v0 response only has: id, name, slug, path, absolute_path, step_type,
    structure, parent_calculation_id, parameters, cards, species_overrides,
    prefix_outdir_injection

    NEW (Law D): Also adds step_type_gen for GUI display/gating.
    """
    response = copy.deepcopy(response)

    # Remove HEAD-only keys
    response.pop("meta", None)
    response.pop("status", None)
    response.pop("step_id", None)
    response.pop("calc_id", None)

    # Map step_type to v0 format (qe_ prefix) if needed
    if "step_type" in response:
        response["step_type"] = _map_step_type_to_v0(response["step_type"])

    # Add step_type_gen (Law D: RPC must provide both SPEC and GEN)
    _add_step_type_gen(response, "step_type")

    return response
```

### Step 2.3: Update `_shape_list_calculations()`

**File**: `src/quantumvitas/daemon/compat.py`
**Line**: ~523-533 (inside the function, where steps are processed)

**Find** (around line 530):
```python
        for step in calc.get("steps", []):
            step_type = step.get("type", "")
            # Derive name from type if missing
            if _should_derive_step_name(step.get("name", "")):
                step["name"] = _derive_step_name_from_type(step_type)
            if "type" in step:
                step["type"] = _map_step_type_to_v0(step["type"])
```

**Replace with**:
```python
        for step in calc.get("steps", []):
            step_type = step.get("type", "")
            # Derive name from type if missing
            if _should_derive_step_name(step.get("name", "")):
                step["name"] = _derive_step_name_from_type(step_type)
            if "type" in step:
                step["type"] = _map_step_type_to_v0(step["type"])
            # Add step_type_gen (Law D)
            _add_step_type_gen(step, "type")
```

### Step 2.4: Update `_shape_calculation_detail()`

**File**: `src/quantumvitas/daemon/compat.py`
**Line**: ~693-740

**Find** (around line 717-720, inside the for loop processing steps):
```python
        if "type" in step:
            step["type"] = _map_step_type_to_v0(step["type"])
```

**Add after that block**:
```python
        # Add step_type_gen (Law D)
        _add_step_type_gen(step, "type")
```

### Step 2.5: Update `_shape_add_step_to_calculation()`

**File**: `src/quantumvitas/daemon/compat.py`
**Line**: ~308-384

**Find** the steps processing loop and add `_add_step_type_gen` call for each step.

### Step 2.6: Update `_shape_update_step_params()`

**File**: `src/quantumvitas/daemon/compat.py`
**Line**: ~386-410

**The function calls `_shape_step_detail`, which now adds `step_type_gen`, so no change needed here.**

**Validation**:
```bash
python -m pytest tests/gates/test_daemon_kernel_ban.py -v
# Must pass - no kernel imports in compat.py
```

---

## Phase 3: Update GUI Types and Components

**Goal**: GUI uses `step_type_gen` for display and gating.

### Step 3.1: Update TypeScript types

**File**: `gui/src/types/qv.ts`

**Find** (around line 194, `StepInfo` interface):
```typescript
export interface StepInfo {
  id: string;
  type: string;
  step_file: string;
}
```

**Replace with**:
```typescript
export interface StepInfo {
  id: string;
  type: string;
  step_type_gen?: string;  // GEN format for display (Law D)
  step_file: string;
}
```

**Find** (around line 417, `StepDetail` interface):
```typescript
export interface StepDetail {
  id: string;
  name: string;
  slug: string;
  path: string;
  absolute_path: string;
  step_type: string;
```

**Add field after `step_type`**:
```typescript
  step_type_gen?: string;  // GEN format for display (Law D)
```

**Find** (around line 325, `JobStepInfo` interface):
```typescript
export interface JobStepInfo {
  step_id?: string;
  step_type: string;
```

**Add field after `step_type`**:
```typescript
  step_type_gen?: string;  // GEN format for display (Law D)
```

### Step 3.2: Update CalculationAnalysisPanel.tsx

**File**: `gui/src/components/panels/CalculationAnalysisPanel.tsx`

**Find** (line ~94):
```typescript
const typeLower = selectedStep.type.toLowerCase();
```

**Replace with**:
```typescript
// Use step_type_gen for display/gating (Law C), fall back to type
const stepTypeGen = selectedStep.step_type_gen || selectedStep.type || '';
```

**Find** (lines ~98-104):
```typescript
// Fast path for scf/dos (always support plot if step type matches)
if (typeLower === 'scf' || typeLower === 'dos') {
  setSupportsPlot(true);
  return;
}

// For bands: only 'bands' step (post-processing) supports plot, not 'bands_pw'
if (typeLower === 'bands') {
```

**Replace with**:
```typescript
// Fast path for scf/dos (always support plot if step type matches)
// Law C: GUI uses GEN for gating
if (stepTypeGen === 'scf' || stepTypeGen === 'dos') {
  setSupportsPlot(true);
  return;
}

// For bands: only 'bandpp' step (post-processing) supports plot
// Law F: Plot gates on bandpp (not bands)
if (stepTypeGen === 'bandpp') {
```

**Find** (lines ~156-192, loadPlotData):
```typescript
const stepTypeLower = stepType.toLowerCase();

if (stepTypeLower === 'scf') {
```

**Replace with**:
```typescript
// Use step_type_gen for routing (Law C)
const stepTypeGen = stepType;  // Already GEN from caller

if (stepTypeGen === 'scf') {
```

**Find** (line ~175):
```typescript
} else if (stepTypeLower === 'dos') {
```

**Replace with**:
```typescript
} else if (stepTypeGen === 'dos') {
```

**Find** (line ~192):
```typescript
} else if (stepTypeLower === 'bands') {
```

**Replace with**:
```typescript
} else if (stepTypeGen === 'bandpp') {
```

**Find** where `loadPlotData` is called (should pass `step_type_gen`):
```typescript
loadPlotData(stepId, stepType)
```

**Ensure** the caller passes `step.step_type_gen || step.type`.

### Step 3.3: Update StepDetailPanel.tsx

**File**: `gui/src/components/panels/StepDetailPanel.tsx`

**Find** (line ~1263):
```typescript
{stepDetail?.step_type?.toUpperCase() || 'STEP'}
```

**Replace with**:
```typescript
{(stepDetail?.step_type_gen || stepDetail?.step_type)?.toUpperCase() || 'STEP'}
```

**Find** (lines ~1289-1293):
```typescript
{stepDetail.step_type.toUpperCase()}
```

**Replace with**:
```typescript
{(stepDetail.step_type_gen || stepDetail.step_type).toUpperCase()}
```

### Step 3.4: Update JobsPanel.tsx

**File**: `gui/src/components/panels/JobsPanel.tsx`

**Find** (lines ~94-96):
```typescript
<div key={idx} className="job-step-stepper__label" title={step.step_type}>
  {step.step_type}
</div>
```

**Replace with**:
```typescript
<div key={idx} className="job-step-stepper__label" title={step.step_type_gen || step.step_type}>
  {step.step_type_gen || step.step_type}
</div>
```

**Validation**:
```bash
cd gui && npm run type-check
```

---

## Phase 4: Patch Golden Fixtures and Update Contract Tests

**Goal**: Golden fixtures expect `step_type_gen`, enforcement tests check it.

### Step 4.1: Apply Minimal Patches to Golden Fixtures

**DO NOT** use `--update-golden` which replaces entire fixtures. Instead, apply the mechanical patch script (see "Golden Fixture Patch Strategy" section below).

```bash
# Run the patch script (requires Phase 1 registry update first)
python tools/patch_golden_step_type_gen.py

# Verify patches are minimal (only adds step_type_gen)
git diff tests/fixtures/golden_0873ebf/daemon/
```

**Expected diff pattern**:
```diff
   "step_type": "qe_scf",
+  "step_type_gen": "scf",
```

No other fields should change.

### Step 4.2: Update test_gui_field_enforcement.py

**File**: `tests/contract_crawler/test_gui_field_enforcement.py`

**Find** (line ~38):
```python
    "get_step_detail": {
        "top_level": ["id", "name", "step_type"],
    },
```

**Replace with**:
```python
    "get_step_detail": {
        "top_level": ["id", "name", "step_type", "step_type_gen"],
    },
```

**Find** (line ~35):
```python
    "get_calculation_detail": {
        "top_level": ["id", "steps"],
        "array_items": {"steps": ["id", "type", "name"]},
    },
```

**Replace with**:
```python
    "get_calculation_detail": {
        "top_level": ["id", "steps"],
        "array_items": {"steps": ["id", "type", "name", "step_type_gen"]},
    },
```

**Validation**:
```bash
python -m pytest tests/contract_crawler/test_gui_field_enforcement.py -v
```

---

## Phase 5: Fix Demo Generators to Emit SPEC

**Goal**: All demo generators output SPEC step_type in step.yaml.

### Step 5.1: Update snapshot.py to normalize to SPEC

**File**: `src/quantumvitas/project/snapshot.py`

**Find** (around line 791-793):
```python
        for step_data in calculation_data.get("steps", []):
            step_meta = step_data.get("meta", {})
            step_name = step_meta.get("name", step_data.get("step_type", "step"))
```

**Find** (around line 805-810, where step_spec_dict is built):

**Add normalization before creating StructureStepSpec**:
```python
            # Normalize step_type to SPEC format (Law B)
            raw_step_type = step_data.get("step_type", "scf")
            from quantumvitas.workflow.registry import get_registry
            registry = get_registry()
            spec = registry.get(raw_step_type)
            if spec:
                step_spec_dict["step_type"] = spec.machine_type
            else:
                # Fallback: if already SPEC format, keep it
                step_spec_dict["step_type"] = raw_step_type
```

### Step 5.2: Regenerate all demos

**Commands**:
```bash
# Purge old demos
bash tools/purge_demos.sh

# Regenerate each demo set
python tools/import_tutorial_datasets.py --clean
python tools/regenerate_si_bands_demo.py
python tools/generate_demo_snapshots.py
python tools/generate_wannier90_demos.py
python tools/generate_orca_demos.py
python tools/generate_pyscf_demo.py

# Verify demos
python tools/verify_demos.py
```

### Step 5.3: Add SPEC format verification to verify_demos.py

**File**: `tools/verify_demos.py`

**Add function**:
```python
def verify_spec_format(demo_file: Path) -> list[str]:
    """Verify all step_type values are in SPEC format."""
    errors = []
    with open(demo_file) as f:
        data = yaml.safe_load(f)

    # Check calculations -> steps -> step_type
    for calc in data.get("calculations", []):
        for step in calc.get("steps", []):
            step_type = step.get("step_type", "")
            # SPEC format: {engine}_{type}
            if step_type and "_" not in step_type:
                errors.append(
                    f"step_type '{step_type}' is not SPEC format "
                    f"(should be like 'qe_{step_type}')"
                )
    return errors
```

**Call this function in the main verification loop.**

### Step 5.4: Create verification script

**File**: `tools/verify_demo_spec_format.sh` (NEW)

**Content**:
```bash
#!/bin/bash
# Verify all demo step.yaml files contain SPEC format step_type

echo "Checking for non-SPEC step_type values in demo projects..."

# SPEC format requires underscore (engine_type)
# This grep finds step_type values WITHOUT underscore
violations=$(grep -r "step_type:" resources/demo_projects/*.yml | \
  grep -v "step_type: qe_" | \
  grep -v "step_type: vasp_" | \
  grep -v "step_type: orca_" | \
  grep -v "step_type: pyscf_" | \
  grep -v "step_type: lammps_" | \
  grep -v "step_type: cp2k_" | \
  grep -v "step_type: w90_")

if [ -z "$violations" ]; then
    echo "✓ All step_type values are in SPEC format"
    exit 0
else
    echo "✗ Found non-SPEC step_type values:"
    echo "$violations"
    exit 1
fi
```

**Make executable**:
```bash
chmod +x tools/verify_demo_spec_format.sh
```

**Validation**:
```bash
bash tools/verify_demo_spec_format.sh
# Should exit 0 with no violations
```

---

## Phase 6: Update E2E Tests

**Goal**: E2E tests assert GEN in UI, SPEC in YAML files.

### Step 6.1: Update demo_calculation_run.spec.ts

**File**: `gui/tests/e2e/demo_calculation_run.spec.ts`

**Find** (line ~266-273):
```typescript
// Find and click the 'bands' step chip (step_type is "qe_bands" in v0 format, not "bands_pw")
// Use the specific testid for the bands step tab (v0 format uses qe_ prefix)
const bandsStepChip = analysisPanel.locator('[data-testid="qv-analysis-step-tab-qe_bands"]');
await expect(bandsStepChip).toBeVisible({ timeout: 5000 });

// Verify it's the correct step (not bands_pw)
const stepType = await bandsStepChip.getAttribute('data-step-type');
expect(stepType?.toLowerCase()).toBe('qe_bands');
```

**Replace with**:
```typescript
// Find and click the 'bandpp' step chip (bands.x post-processing)
// Test ID uses SPEC format, but visible text uses GEN format (Law C)
const bandsStepChip = analysisPanel.locator('[data-testid="qv-analysis-step-tab-qe_bands"]');
await expect(bandsStepChip).toBeVisible({ timeout: 5000 });

// Verify the displayed text is GEN format (Law C: GUI displays GEN)
const stepText = await bandsStepChip.textContent();
expect(stepText?.toLowerCase()).toContain('bandpp');
```

### Step 6.2: Update demo_calculation.spec.ts

**File**: `gui/tests/e2e/demo_calculation.spec.ts`

**Find** (line ~180):
```typescript
// The file uses lowercase for step_type, so check case-insensitively
const stepTypePattern = new RegExp(`step_type:\\s*${trimmedStepType}`, 'i');
expect(fileContent).toMatch(stepTypePattern);
```

**Replace with**:
```typescript
// YAML file must contain SPEC format step_type (Law B)
// e.g., step_type: qe_scf (not step_type: scf)
const specPattern = /step_type:\s*(qe_|vasp_|orca_|pyscf_|lammps_|cp2k_|w90_)/;
expect(fileContent).toMatch(specPattern);
```

### Step 6.3: Update step_defaults.spec.ts

**File**: `gui/tests/e2e/step_defaults.spec.ts`

**Find** (lines ~129-132):
```typescript
// Wait for a new step row with type 'qe_scf' to appear (v0 format uses qe_ prefix)
await expect(
  page.locator('.step-type-badge').filter({ hasText: /^qe_scf$/i })
).toBeVisible({ timeout: 10000 });
```

**Replace with**:
```typescript
// Wait for a new step row with GEN type 'scf' to appear (Law C: GUI displays GEN)
await expect(
  page.locator('.step-type-badge').filter({ hasText: /^scf$/i })
).toBeVisible({ timeout: 10000 });
```

**Validation**:
```bash
cd gui && npm run test:e2e
```

---

## Phase 7: Add Regression Gate Test

**Goal**: Prevent future GEN/SPEC drift.

### Step 7.1: Create step_type_format_gate.py

**File**: `tests/gates/test_step_type_format_gate.py` (NEW)

**Content**:
```python
"""
Gate test: Verify GEN/SPEC step_type format invariants.

Law B: step.yaml must store SPEC only
Law F: QE bands chain has specific GEN mappings
Law J: Registry is SSOT (no separate API mapping table)
"""

import pytest
from pathlib import Path
import yaml


PROJECT_ROOT = Path(__file__).parent.parent.parent
DEMO_DIR = PROJECT_ROOT / "resources" / "demo_projects"


def test_demo_step_types_are_spec():
    """All demo YAML files must have SPEC format step_type."""
    violations = []

    for demo_file in DEMO_DIR.glob("*.yml"):
        with open(demo_file) as f:
            data = yaml.safe_load(f)

        for calc in data.get("calculations", []):
            for step in calc.get("steps", []):
                step_type = step.get("step_type", "")
                # SPEC format requires underscore
                if step_type and "_" not in step_type:
                    violations.append(
                        f"{demo_file.name}: step_type '{step_type}' is not SPEC format"
                    )

    if violations:
        pytest.fail(
            f"Demo step_type format violations (Law B):\n" +
            "\n".join(violations)
        )


def test_registry_is_ssot_for_gen_mapping():
    """
    Verify API get_step_type_gen delegates to registry SSOT (Law J).

    There must be NO hardcoded mapping table in API.
    The API function must use registry.normalize_step_type_to_public().
    """
    from quantumvitas.api import get_step_type_gen
    from quantumvitas.workflow.registry import normalize_step_type_to_public, get_registry

    registry = get_registry()

    # Test that API and registry produce identical results for ALL known types
    discrepancies = []
    for spec_type in registry._machine_to_spec.keys():
        api_result = get_step_type_gen(spec_type)
        registry_result = normalize_step_type_to_public(spec_type)
        if api_result != registry_result:
            discrepancies.append(
                f"{spec_type}: API='{api_result}', Registry='{registry_result}'"
            )

    if discrepancies:
        pytest.fail(
            f"API get_step_type_gen diverges from registry SSOT (Law J violation):\n" +
            "\n".join(discrepancies)
        )


def test_qe_bands_gen_mapping_law_f():
    """
    Verify Law F: QE bands chain GEN mappings are correct.

    qe_bands_pw → "bands" (eigenvalues, not plottable)
    qe_bands → "bandpp" (post-processing, plottable)
    """
    from quantumvitas.api import get_step_type_gen

    assert get_step_type_gen("qe_bands_pw") == "bands", \
        "Law F: qe_bands_pw must map to GEN='bands'"

    assert get_step_type_gen("qe_bands") == "bandpp", \
        "Law F: qe_bands must map to GEN='bandpp'"
```

**Validation**:
```bash
python -m pytest tests/gates/test_step_type_format_gate.py -v
```

---

## Phase 8: Final Validation

### Step 8.1: Run all gate tests

```bash
python -m pytest tests/gates/ -v -n auto --dist=loadfile
```

### Step 8.2: Run contract tests

```bash
python -m pytest tests/contract_crawler/ -v -n auto --dist=loadfile
```

### Step 8.3: Run E2E tests

```bash
cd gui && npm run test:e2e
```

### Step 8.4: Manual verification

```bash
# Start daemon and GUI
python -m quantumvitas.daemon &
cd gui && npm run dev

# Create demo project, verify:
# 1. UI shows GEN types (scf, nscf, bands, bandpp, dos)
# 2. step.yaml files contain SPEC types (qe_scf, qe_nscf, qe_bands_pw, qe_bands, qe_dos)
# 3. Plot tab appears for bandpp step (not bands step)
```

---

## Summary: Files Changed

| Phase | File | Change Type | Notes |
|-------|------|-------------|-------|
| 1 | `src/quantumvitas/workflow/registry.py` | MODIFY | Fix `public_type` for qe_bands/qe_bands_pw (SSOT) |
| 1 | `src/quantumvitas/api/__init__.py` | MODIFY | Add thin facade export |
| 2 | `src/quantumvitas/daemon/compat.py` | MODIFY | Add `step_type_gen` via API |
| 3 | `gui/src/types/qv.ts` | MODIFY | Add `step_type_gen` to interfaces |
| 3 | `gui/src/components/panels/CalculationAnalysisPanel.tsx` | MODIFY | Use `step_type_gen` for gating |
| 3 | `gui/src/components/panels/StepDetailPanel.tsx` | MODIFY | Use `step_type_gen` for display |
| 3 | `gui/src/components/panels/JobsPanel.tsx` | MODIFY | Use `step_type_gen` for labels |
| 4 | `tools/patch_golden_step_type_gen.py` | NEW | Mechanical golden patcher |
| 4 | `tests/contract_crawler/test_gui_field_enforcement.py` | MODIFY | Enforce `step_type_gen` |
| 4 | `tests/fixtures/golden_0873ebf/daemon/*.json` | PATCH | Add `step_type_gen` only |
| 5 | `src/quantumvitas/project/snapshot.py` | MODIFY | Normalize to SPEC |
| 5 | `tools/verify_demos.py` | MODIFY | Add SPEC check |
| 5 | `tools/verify_demo_spec_format.sh` | NEW | SPEC format gate |
| 5 | `resources/demo_projects/*.yml` | REGENERATE | Must be SPEC format |
| 6 | `gui/tests/e2e/demo_calculation_run.spec.ts` | MODIFY | Assert GEN in UI |
| 6 | `gui/tests/e2e/demo_calculation.spec.ts` | MODIFY | Assert SPEC in YAML |
| 6 | `gui/tests/e2e/step_defaults.spec.ts` | MODIFY | Assert GEN in UI |
| 7 | `tests/gates/test_step_type_format_gate.py` | NEW | Law B/F/J gate tests |

---

## Golden Fixture Patch Strategy

### CRITICAL: Minimal Mechanical Patches Only

**DO NOT** regenerate golden fixtures with "current outputs". Golden fixtures capture specific known-good baseline behavior. Replacing them wholesale loses that baseline.

**INSTEAD**: Apply minimal, deterministic, mechanical patches that ADD the new `step_type_gen` field without changing existing fields.

### Patch Script

**File**: `tools/patch_golden_step_type_gen.py` (NEW)

**Content**:
```python
#!/usr/bin/env python3
"""
Minimal mechanical patch: Add step_type_gen field to golden fixtures.

This script:
1. Reads each golden fixture
2. For any object with "step_type" or "type" field, adds "step_type_gen"
3. Uses registry SSOT for SPEC→GEN mapping
4. Writes back with minimal diff (preserves formatting)

Run: python tools/patch_golden_step_type_gen.py
"""

import json
from pathlib import Path
from quantumvitas.api import get_step_type_gen

GOLDEN_DIR = Path("tests/fixtures/golden_0873ebf/daemon")


def add_step_type_gen(obj: dict, type_field: str = "step_type") -> bool:
    """Add step_type_gen to object if it has type_field. Returns True if modified."""
    if type_field not in obj:
        return False
    if "step_type_gen" in obj:
        return False  # Already has field

    spec_type = obj[type_field]
    if spec_type:
        obj["step_type_gen"] = get_step_type_gen(spec_type)
        return True
    return False


def patch_recursive(data, type_fields=("step_type", "type")):
    """Recursively patch all objects that have type fields."""
    modified = False

    if isinstance(data, dict):
        # Check this object
        for tf in type_fields:
            if add_step_type_gen(data, tf):
                modified = True
        # Recurse into values
        for v in data.values():
            if patch_recursive(v, type_fields):
                modified = True
    elif isinstance(data, list):
        for item in data:
            if patch_recursive(item, type_fields):
                modified = True

    return modified


def main():
    patched_files = []

    for fixture_path in GOLDEN_DIR.glob("*.json"):
        with open(fixture_path, "r") as f:
            data = json.load(f)

        if patch_recursive(data):
            with open(fixture_path, "w") as f:
                json.dump(data, f, indent=2)
            patched_files.append(fixture_path.name)

    print(f"Patched {len(patched_files)} files:")
    for name in patched_files:
        print(f"  - {name}")


if __name__ == "__main__":
    main()
```

### Patch Execution (Part of Phase 4)

```bash
# Run AFTER Phase 1 (registry updated) and Phase 2 (compat updated)
python tools/patch_golden_step_type_gen.py

# Verify no other changes
git diff --stat tests/fixtures/golden_0873ebf/daemon/

# The diff should ONLY show added "step_type_gen" fields
```

### Fixtures That Will Be Patched

All step-bearing fixtures will gain `step_type_gen` field:

1. `get_step_detail.json` - Response gains `step_type_gen`
2. `list_calculations.json` - Each step in `steps[]` gains `step_type_gen`
3. `get_calculation_detail.json` - Each step gains `step_type_gen`
4. `add_step_to_calculation.json` - Each step gains `step_type_gen`
5. `update_step_params.json` - Response gains `step_type_gen`

### Contract Test Adjustment

The `DATA_DEPENDENT_FIELDS` in `golden_comparison.py` already skips `steps` comparison, so the new field won't break existing golden comparison logic. However, `test_gui_field_enforcement.py` must be updated to enforce `step_type_gen` presence.

---

## Rollback Plan

If issues arise:

1. Revert `src/quantumvitas/workflow/registry.py` (restore old `public_type` values)
2. Revert `src/quantumvitas/api/__init__.py` (remove facade export)
3. Revert `src/quantumvitas/daemon/compat.py` changes
4. Revert GUI component changes
5. Revert E2E test changes
6. Remove `step_type_gen` fields from golden fixtures (inverse patch):
   ```bash
   # Use sed or jq to remove step_type_gen lines
   find tests/fixtures/golden_0873ebf/daemon -name "*.json" -exec \
     sed -i '' '/"step_type_gen":/d' {} \;
   ```
