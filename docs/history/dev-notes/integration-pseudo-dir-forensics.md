# Integration Pseudo Directory Forensics

**Date**: 2025-01-XX  
**Purpose**: Diagnose why integration tests use `/home/anonymous/...` pseudo_dir and why project/pseudo is empty.

**Status**: Forensics only (no fixes implemented)

---

## Reproduction Evidence

### Failing Test

**Test**: `tests/integration/test_si_bands_calculation.py::TestSiBandsCalculation::test_run_full_calculation`

**Error**:
```
from readpp : error # 1
file /home/anonymous/quantumEspresso_2019/SSSP_precision_pseudos/Si.pbe-n-rrkjus_psl.1.0.0.UPF not found
```

### Generated .in File Snippet

**File**: `.tmp/runs/calculation_si_bands/calculations/si_bands/raw/si.0_scf.in`

```fortran
&CONTROL
    prefix = 'si'
    outdir = './outdir'
    pseudo_dir = '/home/anonymous/quantumEspresso_2019/SSSP_precision_pseudos'
/
&SYSTEM
    ...
/
ATOMIC_SPECIES
 Si  28.0855  Si.pbe-n-rrkjus_psl.1.0.0.UPF
```

**Key observation**: The generated .in file contains the external path `/home/anonymous/...` instead of project pseudo directory.

### Project Pseudo Directory Status

**Location**: `.tmp/runs/calculation_si_bands/pseudo`

**Contents**: Contains entire internal pseudo library (23 files, 22MB total)
- This is from the `shutil.copytree` in test fixture (before revert)
- After revert, this directory would be empty if copytree is removed

**Expected**: Should contain only `Si.pbe-n-rrkjus_psl.1.0.0.UPF` (1 file, ~1.5MB)

---

## Root Cause Analysis

### Q1: Where does `/home/anonymous/.../SSSP_precision_pseudos` come from?

**Answer**: **From the original test data .in files**

**Evidence**:

1. **Source in test data**:
   - `tests/data/7_Si_bandStructure/si.0_scf.in` contains:
     ```
     pseudo_dir = '/home/anonymous/quantumEspresso_2019/SSSP_precision_pseudos'
     ```
   - `tests/data/4_Si_DOS/si.1_scf.in` contains the same path

2. **Test fixture extracts parameters**:
   - `tests/utils/calculation_projects.py:141-150`:
     ```python
     input_file = raw_dir / step["input"]
     qe_input = QEInputParser.parse_file(input_file)
     parameters, cards = _build_step_spec_from_qe_input_data(
         qe_input, step_id, apply_defaults=False
     )
     ```
   - `_build_step_spec_from_qe_input_data()` extracts ALL parameters from the .in file, including `pseudo_dir`

3. **Parameters written to step.yaml**:
   - `tests/utils/calculation_projects.py:162-163`:
     ```python
     if parameters:
         step_spec["parameters"] = parameters
     ```
   - The extracted `CONTROL.pseudo_dir` parameter is written to `step.yaml`

4. **Parameters applied during materialization**:
   - `src/qmatsuite/calculation/structure_steps.py:514-522`:
     ```python
     spec_overrides = parameter_dict_to_overrides(spec.parameters)
     combined_overrides: list[ParameterOverride] = list(spec_overrides)
     qe_input = generate_qe_input_from_structure(
         structure=structure,
         step_type=spec.step_type,
         parameter_overrides=combined_overrides,
     )
     ```
   - The `pseudo_dir` parameter from `spec.parameters` is applied as an override, setting it in the generated QE input

5. **set_pseudo_dir_in_input() called but too late**:
   - `src/qmatsuite/calculation/structure_steps.py:1192`:
     ```python
     set_pseudo_dir_in_input(qe_input, project_pseudo_dir, output_dir)
     ```
   - However, `set_pseudo_dir_in_input()` only updates `pseudo_dir` if it already exists in a namelist (line 154-156 in `input_runner.py`)
   - Since the parameter was already set from `spec.parameters`, it exists and gets updated
   - **BUT**: The update happens AFTER the QE input is written to file (line 1192 is after line 1194 where file is written)

**Wait, let me check the order again...**

Actually, looking at `structure_steps.py:1191-1194`:
```python
set_pseudo_dir_in_input(qe_input, project_pseudo_dir, output_dir)

filename = input_name or spec_obj.input_name or f"{resolved_spec_path.stem}.pw.in"
generated_input = output_dir / filename
QEInputGenerator.write_file(qe_input, generated_input)
```

So `set_pseudo_dir_in_input()` is called BEFORE writing. But the generated .in file still has the old path. This means `set_pseudo_dir_in_input()` is not working correctly, OR the old path is being set after this call.

Let me check if `set_pseudo_dir_in_input()` actually updates the parameter...

Looking at `input_runner.py:152-156`:
```python
found_pseudo = False
for namelist in qe_input.namelists:
    if "pseudo_dir" in namelist.parameters:
        namelist.parameters["pseudo_dir"] = pseudo_dir_str
        found_pseudo = True
```

So it should update it. But the generated file has the old path. This suggests either:
1. The update is not happening (bug in `set_pseudo_dir_in_input`)
2. The old path is being set after `set_pseudo_dir_in_input` is called
3. The generated file I'm looking at is not the one actually used

Let me check if there's a different code path...

Actually, wait - the integration test might be using the original .in file directly instead of the generated one. Let me check the Step.input_file path.

**Conclusion for Q1**: The `/home/anonymous/...` path comes from:
1. Original test data .in files contain this path
2. Test fixture extracts it into step.yaml parameters
3. During materialization, it's applied to generated QE input
4. `set_pseudo_dir_in_input()` should override it, but the generated file still shows the old path (needs investigation)

### Q2: Why is `<project_root>/pseudo` empty in integration runs?

**Answer**: **Staging happens, but only if `ensure_qe_pseudos()` is called with correct inputs**

**Evidence**:

1. **Test fixture creates empty pseudo directory** (after revert):
   - `tests/utils/calculation_projects.py:61-62` (after revert):
     ```python
     project_pseudo_dir = project_root / "pseudo"
     project_pseudo_dir.mkdir(parents=True, exist_ok=True)
     ```
   - Directory is created but empty (no `copytree`)

2. **Staging should happen in `materialize_step_spec()`**:
   - `src/qmatsuite/calculation/structure_steps.py:1166-1171`:
     ```python
     pseudo_result = ensure_qe_pseudos(
         qe_input_file=temp_input,
         project_pseudo_dir=project_pseudo_dir,
         system_pseudo_dir=get_system_pseudo_dir(),
         species_map=calculation_species_map,
     )
     ```

3. **But `calculation_species_map` is None in test fixtures**:
   - `tests/utils/calculation_projects.py:178-193` creates `calculation.yaml` with NO `species_map` field
   - `materialize_step_spec()` loads `calculation_species_map` from calculation.yaml (line 1090)
   - Result: `calculation_species_map = None`

4. **ensure_qe_pseudos() falls back to parsing QE input**:
   - `src/qmatsuite/core/pseudo.py:193-212`:
     ```python
     else:
         # FALLBACK PATH: Parse from QE input ATOMIC_SPECIES (legacy/standalone)
         if atomic_species_card and atomic_species_card.data:
             for line in atomic_species_card.data:
                 # Extract pseudo filename from ATOMIC_SPECIES
     ```
   - But the temp QE input might have placeholders if species_overrides weren't extracted correctly

5. **species_overrides might not be in step.yaml**:
   - Before the "Import ATOMIC_SPECIES" fix, step.yaml didn't have species_overrides
   - After the fix, step.yaml should have species_overrides
   - But if the fix was reverted, step.yaml might not have it

**Conclusion for Q2**: Staging doesn't happen because:
1. `calculation_species_map` is None (calculation.yaml has no species_map)
2. `spec.species_overrides` might not be passed to `ensure_qe_pseudos()` (needs verification)
3. `ensure_qe_pseudos()` falls back to parsing QE input, but temp input might have placeholders
4. If placeholders are found, `ensure_qe_pseudos()` raises ValueError before file resolution (line 214-300)

**However**, after the "Import ATOMIC_SPECIES" fix (commit cdb94f8), step.yaml should have species_overrides. So the issue might be that `materialize_step_spec()` is not passing `spec.species_overrides` to `ensure_qe_pseudos()` when `calculation_species_map` is None.

---

## Integration vs CLI Path Comparison

### CLI Test Path

**Command**: `qms run calculation si_dos --project <path>`

**Call chain** (inferred):
```
CLI command → QMSService.run_calculation() → CalculationRunner.run() → ...
```

**Materialization**:
- Uses same `_build_step_from_spec()` → `materialize_step_spec()` path
- `materialize_step_spec()` calls `ensure_qe_pseudos()` with `calculation_species_map`
- If `calculation_species_map` is None, falls back to parsing QE input

**Why CLI works**:
- CLI test might have different setup (needs verification)
- OR CLI path uses a different code branch

### Integration Test Path

**Call chain**:
```
test_run_full_calculation() 
  → Project.open(si_bands_project)
  → project.get_calculation("si_bands")
  → CalculationRunner.run(calculation)
  → Calculation.from_yaml(..., materialize_steps=True)
  → _build_step() → _build_step_from_spec()
  → materialize_step_spec()
```

**Materialization**:
- Same path as CLI: `_build_step_from_spec()` → `materialize_step_spec()`
- `materialize_step_spec()` calls `ensure_qe_pseudos()` with `calculation_species_map=None`
- Falls back to parsing QE input

**Why integration fails**:
- `calculation_species_map` is None (calculation.yaml has no species_map)
- `spec.species_overrides` might not be passed to `ensure_qe_pseudos()` (needs verification)
- Temp QE input might have placeholders, causing `ensure_qe_pseudos()` to raise ValueError

**Key difference**: Both paths use the same materialization code, so the difference must be in:
1. Whether `spec.species_overrides` is populated in step.yaml
2. Whether `spec.species_overrides` is passed to `ensure_qe_pseudos()`
3. Whether the temp QE input has placeholders or real filenames

---

## Evidence Snippets

### Snippet 1: Original test data contains external pseudo_dir

**File**: `tests/data/7_Si_bandStructure/si.0_scf.in:6`
```
pseudo_dir = '/home/anonymous/quantumEspresso_2019/SSSP_precision_pseudos'
```

### Snippet 2: Test fixture extracts ALL parameters (including pseudo_dir)

**File**: `tests/utils/calculation_projects.py:141-150`
```python
input_file = raw_dir / step["input"]
qe_input = QEInputParser.parse_file(input_file)
parameters, cards = _build_step_spec_from_qe_input_data(
    qe_input, step_id, apply_defaults=False
)
# parameters now contains CONTROL.pseudo_dir = '/home/anonymous/...'
```

### Snippet 3: Parameters written to step.yaml

**File**: `tests/utils/calculation_projects.py:162-163`
```python
if parameters:
    step_spec["parameters"] = parameters
# step.yaml now contains parameters.CONTROL.pseudo_dir
```

### Snippet 4: Parameters applied during materialization

**File**: `src/qmatsuite/calculation/structure_steps.py:514-522`
```python
spec_overrides = parameter_dict_to_overrides(spec.parameters)
combined_overrides: list[ParameterOverride] = list(spec_overrides)
qe_input = generate_qe_input_from_structure(
    structure=structure,
    step_type=spec.step_type,
    parameter_overrides=combined_overrides,  # Includes pseudo_dir override
)
```

### Snippet 5: set_pseudo_dir_in_input() should override

**File**: `src/qmatsuite/calculation/structure_steps.py:1192`
```python
set_pseudo_dir_in_input(qe_input, project_pseudo_dir, output_dir)
```

**File**: `src/qmatsuite/calculation/input_runner.py:152-156`
```python
for namelist in qe_input.namelists:
    if "pseudo_dir" in namelist.parameters:
        namelist.parameters["pseudo_dir"] = pseudo_dir_str  # Should update
        found_pseudo = True
```

### Snippet 6: ensure_qe_pseudos() called with None species_map

**File**: `src/qmatsuite/calculation/structure_steps.py:1166-1171`
```python
pseudo_result = ensure_qe_pseudos(
    qe_input_file=temp_input,
    project_pseudo_dir=project_pseudo_dir,
    system_pseudo_dir=get_system_pseudo_dir(),
    species_map=calculation_species_map,  # This is None in test fixtures
)
```

### Snippet 7: calculation.yaml has no species_map

**File**: `tests/utils/calculation_projects.py:178-193`
```python
calculation_config = {
    "meta": {...},
    "mode": "strict",
    "calculation": {"working_dir": "raw"},
    "structure_id": structure_id,
    "steps": step_entries,
    # NOTE: No "species_map" field
}
```

---

## Minimal Fix Hypotheses (NOT IMPLEMENTED)

### Hypothesis 1: Filter pseudo_dir from extracted parameters (RECOMMENDED)

**Location**: `tests/utils/calculation_projects.py:149` (after `_build_step_spec_from_qe_input_data`)

**Change**: Remove `pseudo_dir` (and other runtime-managed parameters) from extracted parameters before writing to step.yaml.

**Rationale**:
- `pseudo_dir` is a runtime-managed parameter, not part of the step spec
- It should be set by `materialize_step_spec()` based on `project_root`, not from imported .in files
- Prevents external paths from leaking into step.yaml

**Implementation**:
```python
parameters, cards = _build_step_spec_from_qe_input_data(...)
# Remove runtime-managed parameters
if "CONTROL" in parameters:
    parameters["CONTROL"].pop("pseudo_dir", None)
    parameters["CONTROL"].pop("outdir", None)
    parameters["CONTROL"].pop("prefix", None)
```

**Pros**:
- Prevents external paths from being imported
- Aligns with "runtime-managed parameters" concept
- Minimal change, only affects test fixture

**Cons**:
- Only fixes test fixture, not general import path
- If users import .in files with external paths, they'll still leak through

### Hypothesis 2: Ensure spec.species_overrides is passed to ensure_qe_pseudos()

**Location**: `src/qmatsuite/calculation/structure_steps.py:1166-1171`

**Change**: When `calculation_species_map` is None, pass `spec.species_overrides` to `ensure_qe_pseudos()`.

**Rationale**:
- `ensure_qe_pseudos()` needs pseudo filenames to copy files
- If `calculation_species_map` is None, fall back to `spec.species_overrides`
- This ensures staging happens even when calculation.yaml lacks species_map

**Implementation**:
```python
effective_species_map = calculation_species_map if calculation_species_map else (
    spec_obj.species_overrides if spec_obj.species_overrides else None
)
pseudo_result = ensure_qe_pseudos(
    qe_input_file=temp_input,
    project_pseudo_dir=project_pseudo_dir,
    system_pseudo_dir=get_system_pseudo_dir(),
    species_map=effective_species_map,  # Use spec.species_overrides as fallback
)
```

**Pros**:
- Ensures staging happens when calculation.yaml lacks species_map
- Uses step-level species_overrides (already populated by test fixture after "Import ATOMIC_SPECIES" fix)
- Minimal change, only affects materialization logic

**Cons**:
- Doesn't fix the pseudo_dir path issue (separate problem)
- If step.yaml also lacks species_overrides, still won't work

### Hypothesis 3: Remove runtime-managed parameters in generate_qe_input_from_spec()

**Location**: `src/qmatsuite/calculation/structure_steps.py:571-578` (after applying overrides)

**Change**: After applying parameter overrides, remove `pseudo_dir`, `outdir`, `prefix` from QE input. These will be set by `materialize_step_spec()` later.

**Rationale**:
- Runtime-managed parameters should not come from spec
- They should always be set by materialization based on project_root
- Prevents imported paths from being used

**Implementation**:
```python
apply_card_overrides_to_qe_input(qe_input, spec.cards)
apply_species_overrides_to_qe_input(qe_input, effective_species_overrides)

# Remove runtime-managed parameters (will be set by materialize_step_spec)
runtime_keys = {"pseudo_dir", "outdir", "prefix"}
for namelist in qe_input.namelists:
    for key in list(namelist.parameters.keys()):
        if key.lower() in runtime_keys:
            del namelist.parameters[key]

return qe_input, combined_overrides
```

**Pros**:
- Prevents external paths from being used in generated QE input
- Applies to all materialization paths (not just test fixtures)
- Ensures runtime-managed parameters are always set correctly

**Cons**:
- More invasive change (affects production code)
- Might break existing projects that rely on spec-level pseudo_dir

---

## Recommended Fix Strategy

**Combination of Hypothesis 1 + Hypothesis 2**:

1. **Filter runtime-managed parameters in test fixture** (Hypothesis 1)
   - Prevents external paths from being imported into step.yaml
   - Only affects test fixtures (minimal impact)

2. **Pass spec.species_overrides to ensure_qe_pseudos()** (Hypothesis 2)
   - Ensures staging happens when calculation.yaml lacks species_map
   - Uses step-level species_overrides (already populated)

3. **Verify set_pseudo_dir_in_input() is working** (investigation needed)
   - Check if the generated .in file actually has the updated pseudo_dir
   - Or if there's a different .in file being used

**Why not Hypothesis 3**:
- Too invasive (affects production code)
- Might break existing projects
- Should be done as a separate, vetted change

---

## Test Results After Revert

### Integration Test
```
pytest -q tests/integration/test_si_bands_calculation.py::TestSiBandsCalculation::test_run_full_calculation -x
FAILED - scf failed (returncode=1) - MPI_ABORT
```

### CLI Test
```
pytest -q tests/cli/test_si_dos_calculation_cli.py::test_cli_run_calculation -x
PASSED (1 passed in 18.60s)
```

**Note**: CLI test passes, but integration test fails. This suggests the integration path has a different issue (possibly related to how the original .in files are used or how materialization differs).

---

## Final Evidence: step.yaml Contents

**File**: `.tmp/runs/calculation_si_bands/calculations/si_bands/steps/scf.step.yaml`

```yaml
parameters:
  CONTROL:
    calculation: scf
    restart_mode: from_scratch
    prefix: si
    outdir: ./outdir
    pseudo_dir: /home/anonymous/quantumEspresso_2019/SSSP_precision_pseudos  # <-- EXTERNAL PATH
  SYSTEM:
    ecutwfc: 40
    ecutrho: 320
    nbnd: 8
  ELECTRONS:
    conv_thr: 1.0e-08
cards:
  K_POINTS:
    option: automatic
    data: [[8, 8, 8, 0, 0, 0]]
species_overrides:
  Si:
    mass: 28.0855
    pseudopot: Si.pbe-n-rrkjus_psl.1.0.0.UPF  # <-- CORRECT FILENAME (Import ATOMIC_SPECIES fix is in place)
```

**Key observations**:
1. ✅ `species_overrides` exists with correct pseudo filename (Import ATOMIC_SPECIES fix is working)
2. ❌ `parameters.CONTROL.pseudo_dir` contains external path (extracted from original .in file)
3. This confirms Q1: external path comes from original .in → extracted → step.yaml → applied during materialization

## Open Questions

1. **Why does CLI test pass but integration test fail?**
   - Both use same materialization path (`_build_step_from_spec()` → `materialize_step_spec()`)
   - Difference must be in test setup or data
   - **Hypothesis**: CLI test might have different calculation.yaml or step.yaml setup

2. **Is the generated .in file actually used, or is the original .in file used?**
   - The generated file has wrong pseudo_dir, but maybe a different file is used at runtime
   - Need to check `Step.input_file` path
   - **Evidence needed**: Check which .in file is actually passed to QE engine

3. **Why does `set_pseudo_dir_in_input()` not update the pseudo_dir?**
   - Code looks correct (should update if parameter exists)
   - Need to verify the generated file actually has the updated value
   - Or check if there's a different code path that doesn't call `set_pseudo_dir_in_input()`
   - **Evidence needed**: Check generated .in file AFTER `set_pseudo_dir_in_input()` is called

4. **Is `ensure_qe_pseudos()` actually being called in integration path?**
   - Need to verify with logging or breakpoints
   - If not called, staging won't happen
   - **Evidence needed**: Add logging to confirm call and inputs

5. **Does `spec.species_overrides` get passed to `ensure_qe_pseudos()` when `calculation_species_map` is None?**
   - ✅ `spec.species_overrides` exists in step.yaml (confirmed above)
   - ❌ `materialize_step_spec()` only passes `calculation_species_map` to `ensure_qe_pseudos()` (line 1170)
   - **Root cause for Q2**: When `calculation_species_map` is None, `ensure_qe_pseudos()` falls back to parsing QE input, but temp input might have placeholders

---

## Next Steps (NOT IMPLEMENTED)

1. **Verify step.yaml contains species_overrides**:
   - Check if "Import ATOMIC_SPECIES" fix (cdb94f8) is still in place
   - If not, that's why staging doesn't work

2. **Verify set_pseudo_dir_in_input() is called and works**:
   - Add logging to see if it's called
   - Check if the generated .in file actually has updated pseudo_dir
   - Or if a different file is used

3. **Verify ensure_qe_pseudos() is called with correct inputs**:
   - Check if `spec.species_overrides` is passed when `calculation_species_map` is None
   - Check if temp QE input has placeholders or real filenames

4. **Compare CLI vs integration test setup**:
   - Check if CLI test has different calculation.yaml or step.yaml
   - Check if CLI test uses different materialization path

5. **Implement Hypothesis 1 + Hypothesis 2** (after verification):
   - Filter runtime-managed parameters in test fixture
   - Pass spec.species_overrides to ensure_qe_pseudos() when calculation_species_map is None

