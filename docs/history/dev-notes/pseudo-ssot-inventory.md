# Pseudopotential SSOT Forensics Inventory

**Date:** 2025-01-XX  
**Purpose:** Map the single source of truth (SSOT) for pseudopotential mappings (element → UPF filename) across core/tests/demo.

## Executive Summary

**Current SSOT Verdict:** The codebase has a **hybrid/migrating state**:
- **Intended SSOT:** `calculation.yaml` → `species_map` (calculation-level)
- **Actual Runtime SSOT:** `calculation.species_map` (if present) takes precedence, falls back to `step.species_overrides` (for backwards compatibility)
- **Import SSOT:** Both paths exist:
  - New import code writes to `calculation.yaml` → `species_map`
  - Legacy import code writes to `step.yaml` → `species_overrides`
- **Test/Demo SSOT:** Most test projects use `step.yaml` → `species_overrides` (legacy format)

**Key Conflict:** Import code writes `species_overrides` to step.yaml, but runtime prefers `species_map` from calculation.yaml. This creates a migration gap where imported projects have step-level pseudo info but no calc-level info.

---

## 1. Definitions (Terms Used in Code)

### Core Terms

- **`species_map`**: Calculation-level mapping `Dict[str, Dict[str, Any]]` where key is element symbol (e.g., "Si") and value contains `{pseudopot: str, mass: float?, pseudo_sha256: str?, ...}`. Stored in `calculation.yaml`.
  - **Location:** `src/quantumvitas/core/models.py:238-243`
  - **Documentation:** "This is the authoritative source of truth for pseudo mapping. Step-level species_overrides are deprecated (used only for backwards compat on load)."

- **`species_overrides`**: Step-level mapping with same structure as `species_map`, stored in `step.yaml`.
  - **Location:** `src/quantumvitas/calculation/structure_steps.py:51`
  - **Status:** Legacy field, marked for deprecation but still used in many projects.

- **`ATOMIC_SPECIES`**: QE input card containing element, mass, pseudopotential filename. Format: `Si  28.0855  Si.pbe-n-rrkjus_psl.1.0.0.UPF`

- **`pseudo_dir`**: Directory path where QE looks for pseudopotential files. Runtime-managed (set to `project_root/pseudo`).

- **`ensure_qe_pseudos()`**: Canonical function for pseudopotential resolution. Handles copying pseudos to `project_pseudo_dir` and returns resolution result.
  - **Location:** `src/quantumvitas/core/pseudo.py:67-107`

---

## 2. Data Models & Storage Locations

### 2.1 calculation.yaml

**Schema Location:** `src/quantumvitas/core/models.py:208-243`

**Fields:**
- `species_map: Optional[Dict[str, Dict[str, Any]]]` (lines 238-243)
  - Contains: `{element: {pseudopot: str, mass: float?, pseudo_sha256: str?, pseudo_sha_family: str?, pseudo_basename: str?}}`
  - **Documentation states:** "This is the authoritative source of truth for pseudo mapping."

**Example Files:**
- `tests/data/project_examples/project1/calculations/si-dos/calculation.yaml` (lines 1-19)
  - **Does NOT contain `species_map`** (only has structure_id, mode, steps, structure_kind, engine_family)
- `tests/data/project_examples/project2_bands/calculations/si-bands/calculation.yaml` (lines 1-20)
  - **Does NOT contain `species_map`** (same structure as above)
- `resources/calculation_templates/si-dos/calculation.yaml` (lines 1-20)
  - **Does NOT contain `species_map`** (legacy format with `structure: si` selector)

**Verdict:** Most example/test calculation.yaml files do NOT contain `species_map`. Only newer projects created via import APIs have it.

### 2.2 step.yaml

**Schema Location:** `src/quantumvitas/calculation/structure_steps.py:34-51`

**Fields:**
- `species_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)` (line 51)
  - Contains: `{element: {pseudopot: str, mass: float?}}`
  - **Documentation states:** "Legacy field - for backwards compatibility only" (from `docs/SCHEMA.md:91-104`)

**Example Files:**
- `tests/data/project_examples/project1/calculations/si-dos/steps/scf.step.yaml` (lines 29-32)
  - **Contains `species_overrides`:** `{Si: {mass: 28.0855, pseudopot: Si.pbe-n-rrkjus_psl.1.0.0.UPF}}`
- `tests/data/project_examples/project2_bands/calculations/si-bands/steps/scf.step.yaml` (lines 31-34)
  - **Contains `species_overrides`:** `{Si: {mass: 28.0855, pseudopot: Si.pbe-n-rrkjus_psl.1.0.0.UPF}}`
- `resources/calculation_templates/si-dos/steps/scf.step.yaml` (lines 31-34)
  - **Contains `species_overrides`:** `{Si: {mass: 28.0855, pseudopot: Si.pbe-n-rrkjus_psl.1.0.0.UPF}}`

**Verdict:** All example step.yaml files contain `species_overrides`. This is the de facto storage location in test/demo projects.

### 2.3 Raw .in Files

**Location:** `calculations/<calc>/raw/*.in`

**Content:** Contains `ATOMIC_SPECIES` card with element, mass, pseudopotential filename.

**Example:** `tests/data/7_Si_bandStructure/si.0_scf.in` (if exists) would contain:
```
ATOMIC_SPECIES
Si  28.0855  Si.pbe-n-rrkjus_psl.1.0.0.UPF
```

**Verdict:** Raw .in files are used for:
1. Import source (parsed to extract pseudo info)
2. Compat executor playback (direct execution without YAML)

### 2.4 Other Storage Locations

- **`project/pseudo/`**: Runtime directory where pseudopotentials are staged. Not a source of truth for mapping (only file storage).
- **`resources/pseudo/`**: Internal pseudo library (source for copying, not SSOT for mapping).

---

## 3. Runtime Consumption (Who Reads What When Running)

### 3.1 Primary Runtime Path: `materialize_step_spec()`

**Location:** `src/quantumvitas/calculation/structure_steps.py:648-1187`

**Flow:**
1. **Load calculation context** (lines 1070-1102):
   - Loads `calculation.yaml` via `load_calculation()`
   - Extracts `calc_model.species_map` (line 1090)
   - Stores in `calculation_species_map` variable

2. **Generate QE input** (line 1112):
   ```python
   qe_input, _ = generate_qe_input_from_spec(structure, spec_obj, species_map=calculation_species_map)
   ```
   - Passes `calculation_species_map` (calc-level) to input generation

3. **Resolve pseudopotentials** (lines 1163-1171):
   ```python
   pseudo_result = ensure_qe_pseudos(
       qe_input_file=temp_input,
       project_pseudo_dir=project_pseudo_dir,
       system_pseudo_dir=get_system_pseudo_dir(),
       species_map=calculation_species_map,  # PRIMARY SOURCE
   )
   ```
   - Passes `calculation_species_map` as PRIMARY source to `ensure_qe_pseudos`

**Verdict:** Runtime prefers `calculation.species_map` if available.

### 3.2 Input Generation: `generate_qe_input_from_spec()`

**Location:** `src/quantumvitas/calculation/structure_steps.py:487-578`

**Precedence Logic** (lines 573-576):
```python
# Apply species overrides: calc-level species_map takes precedence, fall back to step-level
# This supports backwards compatibility with old projects that have step-level species_overrides
effective_species_overrides = species_map if species_map else spec.species_overrides
apply_species_overrides_to_qe_input(qe_input, effective_species_overrides)
```

**Verdict:** 
- **Primary:** `species_map` (calculation-level)
- **Fallback:** `spec.species_overrides` (step-level, backwards compatibility)

### 3.3 Pseudopotential Resolution: `ensure_qe_pseudos()`

**Location:** `src/quantumvitas/core/pseudo.py:67-392`

**Precedence Logic** (lines 173-212):
```python
if species_map and required_elements:
    # PRIMARY PATH: Use calculation-level species_map as source of truth
    for element in required_elements:
        entry = species_map.get(element)
        # ... extract pseudo_filename from species_map
        element_to_pseudo[element] = pseudo_filename
else:
    # FALLBACK PATH: Parse from QE input ATOMIC_SPECIES (legacy/standalone)
    if atomic_species and atomic_species.data:
        # ... parse from QE input
```

**Documentation** (lines 82-84):
> "1. Determines required pseudopotential filenames:
>    - PRIMARY SOURCE: If species_map is provided, use it as source of truth (calculation-level authority)
>    - FALLBACK: Extract from QE input ATOMIC_SPECIES (for standalone/legacy cases)"

**Verdict:**
- **Primary:** `species_map` parameter (calculation-level)
- **Fallback:** Parse from QE input `ATOMIC_SPECIES` card

**Note:** `ensure_qe_pseudos` does NOT read `step.species_overrides` directly. It only uses:
1. `species_map` parameter (passed from calculation.yaml)
2. QE input file parsing (fallback)

### 3.4 Calculation Runner: Step0 Pseudo Preparation

**Location:** `src/quantumvitas/calculation/runner.py:180-228`

**Flow** (lines 183-195):
```python
if calculation.species_map:
    selections = species_map_to_selections(
        calculation.project.root,
        calculation.species_map,  # Uses calc-level species_map
    )
    report = prepare_project_pseudos_for_run(
        calculation.project.root,
        selections,
    )
```

**Verdict:** Runner uses `calculation.species_map` exclusively (no fallback to step-level).

### 3.5 Compat Executor (Legacy Playback)

**Location:** `src/quantumvitas/calculation/compat_executor.py:80-91`

**Flow:**
- Parses `ATOMIC_SPECIES` from raw `.in` file (line 86)
- Stages pseudos based on parsed filenames (lines 87-91)
- Does NOT use YAML species_map or species_overrides

**Verdict:** Compat executor bypasses YAML entirely, uses raw .in files as SSOT.

---

## 4. Import Consumption (Who Writes What When Importing .in)

### 4.1 Step Import: `build_step_spec_from_qe_input()`

**Location:** `src/quantumvitas/calculation/importers.py:95-266`

**Flow** (lines 198-223):
```python
# Extract species_overrides from ATOMIC_SPECIES card (if present)
species_overrides = {}
atomic_species_card = qe_input.get_card(QECardType.ATOMIC_SPECIES)
if atomic_species_card and atomic_species_card.data:
    for row in atomic_species_card.data:
        # ... extract element, mass, pseudo_filename
        species_overrides[element_symbol] = override
```

**Writes to:** `step.yaml` → `species_overrides` field

**Verdict:** Step import writes to **step-level** `species_overrides`, NOT calculation-level `species_map`.

### 4.2 Calculation Import: `build_calculation_from_qe_inputs()`

**Location:** `src/quantumvitas/calculation/importers.py:267-436`

**Flow** (lines 393-420):
```python
# Build calc-level species_map from all input files
calc_species_map: Dict[str, Dict[str, Any]] = {}
for input_path in files:
    qe_input = QEInputParser.parse_file(input_path)
    file_species_map = extract_species_map_from_qe_input(qe_input)
    if file_species_map:
        calc_species_map = merge_species_maps(
            calc_species_map,
            file_species_map,
            source_file=input_path.name,
        )

# Add species_map to calculation metadata if we have any mappings
if calc_species_map:
    calculation_meta["species_map"] = calc_species_map
```

**Writes to:** `calculation.yaml` → `species_map` field

**Verdict:** Calculation import writes to **calculation-level** `species_map`.

**Note:** This function ALSO calls `build_step_spec_from_qe_input()` for each step, which writes `species_overrides` to step.yaml. So imported calculations have BOTH:
- `calculation.yaml` → `species_map` (from this function)
- `step.yaml` → `species_overrides` (from step import)

### 4.3 Folder Import: `materialize_project_from_qe_input_folder()`

**Location:** `src/quantumvitas/calculation/folder_import.py:155-461`

**Flow** (lines 393-443):
```python
# Build species_map from all input files BEFORE importing steps
calc_species_map: Dict[str, Dict[str, Any]] = {}
for input_file in input_files:
    qe_input = QEInputParser.parse_file(input_file)
    file_species_map = extract_species_map_from_qe_input(qe_input)
    if file_species_map:
        calc_species_map = merge_species_maps(...)

# Import each step (which writes species_overrides to step.yaml)
for input_file in input_files:
    service.import_step_from_qe_input(...)

# Set calc-level species_map if we collected any pseudo mappings
if calc_species_map:
    calc_model.species_map = calc_species_map
    save_calculation(calc_model, calculation_yaml)
```

**Writes to:** 
- `calculation.yaml` → `species_map` (lines 437-443)
- `step.yaml` → `species_overrides` (via `import_step_from_qe_input`, line 433)

**Verdict:** Folder import writes to BOTH locations (calc-level and step-level).

### 4.4 Test Utility: `create_calculation_project()`

**Location:** `tests/utils/calculation_projects.py:29-199`

**Flow** (lines 153-197):
```python
# Extract species_overrides from ATOMIC_SPECIES card (if present)
species_overrides = {}
atomic_species_card = qe_input.get_card(QECardType.ATOMIC_SPECIES)
if atomic_species_card and atomic_species_card.data:
    for row in atomic_species_card.data:
        # ... extract and build species_overrides
        species_overrides[element_symbol] = override

# Add extracted species_overrides if available
if species_overrides:
    step_spec["species_overrides"] = species_overrides
```

**Writes to:** `step.yaml` → `species_overrides` field only

**Does NOT write:** `calculation.yaml` → `species_map`

**Verdict:** Test utility writes to **step-level only**, which is why test projects lack calc-level `species_map`.

### 4.5 Update Step from Existing Input: `update_step_from_existing_qe_input()`

**Location:** `src/quantumvitas/calculation/calculation.py:670-695`

**Flow** (lines 674-695):
```python
# Extract pseudopotentials from ATOMIC_SPECIES card
atomic_species_card = existing_qe_input.get_card(QECardType.ATOMIC_SPECIES)
if atomic_species_card and atomic_species_card.data:
    extracted_overrides = {}
    for row in atomic_species_card.data:
        # ... extract pseudo_filename
        extracted_overrides[element_symbol] = {"pseudopot": pseudo_filename}
    
    # Merge extracted overrides into step spec
    if extracted_overrides:
        if not spec_preview.species_overrides:
            spec_preview.species_overrides = {}
        spec_preview.species_overrides.update(extracted_overrides)
```

**Writes to:** `step.yaml` → `species_overrides` field (in-memory preview, written on save)

**Verdict:** Update step writes to **step-level only**.

---

## 5. Tests & Demo Projects (What They Contain and Rely On)

### 5.1 Integration Test Projects

**Location:** `tests/data/project_examples/`

**Examples Examined:**
1. `project1/calculations/si-dos/calculation.yaml`
   - **Does NOT contain `species_map`**
   - Steps contain `species_overrides` in step.yaml

2. `project2_bands/calculations/si-bands/calculation.yaml`
   - **Does NOT contain `species_map`**
   - Steps contain `species_overrides` in step.yaml

**Creation Method:** `create_calculation_project()` (test utility)
- Writes `species_overrides` to step.yaml
- Does NOT write `species_map` to calculation.yaml

**Verdict:** Integration test projects rely on **step-level `species_overrides`** as SSOT.

### 5.2 Integration Tests That Use species_map

**Location:** `tests/integration/test_incremental_run.py`

**Pattern** (lines 139-141):
```python
if not calc_model.species_map:
    calc_model.species_map = {
        "Si": {"pseudopot": "Si.UPF", ...}
    }
```

**Verdict:** Some integration tests manually set `species_map` in calculation.yaml (newer tests).

### 5.3 Calculation Templates

**Location:** `resources/calculation_templates/`

**Examples:**
- `si-dos/calculation.yaml` (legacy format, no `species_map`)
- `si-dos/steps/scf.step.yaml` (contains `species_overrides`)

**Verdict:** Templates use **step-level `species_overrides`** (legacy format).

### 5.4 Manual Test Projects

**Location:** `manual_tests/`

**Examples:**
- `project1/calculations/si-dos/calculation.yaml` (no `species_map`)
- `project2_bands/calculations/si-bands/calculation.yaml` (no `species_map`)

**Verdict:** Manual test projects use **step-level `species_overrides`**.

### 5.5 Demo Projects (if any)

**Location:** `resources/demo_projects/` (if exists)

**Note:** Not examined in detail, but likely follow same pattern as test projects.

---

## 6. Current SSOT Verdict (What Is Actually SSOT Today)

### 6.1 Intended Design (Per Code Documentation)

**Source:** `src/quantumvitas/core/models.py:238-242`
> "Calculation-level pseudopotential mapping: element -> {pseudopot, mass, pseudo_sha256, pseudo_sha_family, pseudo_basename}
> This is the authoritative source of truth for pseudo mapping.
> Step-level species_overrides are deprecated (used only for backwards compat on load)."

**Verdict:** **Intended SSOT is `calculation.yaml` → `species_map`.**

### 6.2 Actual Runtime Behavior

**Runtime Precedence** (from `generate_qe_input_from_spec`, lines 573-576):
1. **Primary:** `calculation.species_map` (if present)
2. **Fallback:** `step.species_overrides` (for backwards compatibility)

**Runtime Resolution** (from `ensure_qe_pseudos`, lines 173-212):
1. **Primary:** `species_map` parameter (from calculation.yaml)
2. **Fallback:** Parse from QE input `ATOMIC_SPECIES` card

**Verdict:** **Runtime SSOT is `calculation.species_map` when present, with fallback to `step.species_overrides`.**

### 6.3 Actual Storage in Projects

**Test/Demo Projects:**
- Most have `step.yaml` → `species_overrides`
- Most do NOT have `calculation.yaml` → `species_map`

**Imported Projects (via folder import):**
- Have BOTH `calculation.yaml` → `species_map` AND `step.yaml` → `species_overrides`

**Verdict:** **Storage SSOT is mixed:**
- Legacy projects: `step.yaml` → `species_overrides` (de facto SSOT)
- New projects: `calculation.yaml` → `species_map` (intended SSOT)

### 6.4 Final SSOT Verdict

**Current State:** **Hybrid/Migrating**
- **Intended:** `calculation.yaml` → `species_map` (calculation-level)
- **Actual in most projects:** `step.yaml` → `species_overrides` (step-level, legacy)
- **Runtime:** Prefers calc-level, falls back to step-level

**Migration Status:** Incomplete. Many projects still use step-level storage, but runtime code prefers calc-level.

---

## 7. Conflicts / Multiple Truths (Where They Diverge)

### Conflict #1: Import Writes to Step-Level, Runtime Prefers Calc-Level

**Location:**
- Import: `src/quantumvitas/calculation/importers.py:198-223` (writes `species_overrides` to step.yaml)
- Runtime: `src/quantumvitas/calculation/structure_steps.py:573-576` (prefers `species_map` from calculation.yaml)

**Problem:**
- When importing a single step via `build_step_spec_from_qe_input()`, pseudo info is written to `step.yaml` → `species_overrides`
- But runtime prefers `calculation.yaml` → `species_map` (which doesn't exist yet)
- Runtime falls back to step-level, but this is not the intended design

**Consequence:** Imported single steps work via fallback, but don't follow intended SSOT pattern.

**Evidence:**
- `build_step_spec_from_qe_input()` writes to step.yaml only (line 223)
- `generate_qe_input_from_spec()` prefers calc-level (line 575)

### Conflict #2: Test Utilities Write Step-Level Only

**Location:** `tests/utils/calculation_projects.py:153-197`

**Problem:**
- Test utility `create_calculation_project()` writes `species_overrides` to step.yaml
- Does NOT write `species_map` to calculation.yaml
- This creates test projects that don't match intended design

**Consequence:** Test projects use legacy format, making it hard to test calc-level SSOT behavior.

**Evidence:**
- Lines 153-197: Extracts and writes `species_overrides` to step.yaml
- No code writes `species_map` to calculation.yaml

### Conflict #3: Folder Import Writes to Both Locations

**Location:** `src/quantumvitas/calculation/folder_import.py:393-443`

**Problem:**
- Folder import writes `species_map` to calculation.yaml (lines 437-443)
- But also calls `import_step_from_qe_input()` which writes `species_overrides` to step.yaml (line 433)
- This creates duplicate storage (both calc-level and step-level)

**Consequence:** Redundant storage. If calc-level is SSOT, step-level should not be written (or should be deprecated/ignored).

**Evidence:**
- Lines 393-411: Builds `calc_species_map` and writes to calculation.yaml
- Line 433: Calls `import_step_from_qe_input()` which writes `species_overrides` to step.yaml

### Conflict #4: Compat Executor Bypasses YAML Entirely

**Location:** `src/quantumvitas/calculation/compat_executor.py:80-91`

**Problem:**
- Compat executor parses `ATOMIC_SPECIES` from raw `.in` file
- Does NOT use YAML `species_map` or `species_overrides`
- This creates a third source of truth (raw .in files)

**Consequence:** Compat playback uses different SSOT than normal execution, making behavior inconsistent.

**Evidence:**
- Line 86: `_extract_required_pseudos_from_atomic_species(input_text)` (parses from .in)
- No code reads from YAML species_map or species_overrides

### Conflict #5: Update Step Writes Step-Level Only

**Location:** `src/quantumvitas/calculation/calculation.py:670-695`

**Problem:**
- `update_step_from_existing_qe_input()` extracts pseudo info and writes to `step.species_overrides`
- Does NOT update `calculation.species_map`
- This creates inconsistency if calculation already has `species_map`

**Consequence:** Updating a step from existing input creates step-level override, but calc-level SSOT is not updated.

**Evidence:**
- Lines 674-695: Extracts and writes to `spec_preview.species_overrides`
- No code updates `calculation.species_map`

---

## 8. Recommendations (NO CODE CHANGES)

### Recommendation #1: Migrate Test Utilities to Write Calc-Level species_map

**Current:** `create_calculation_project()` writes `species_overrides` to step.yaml only.

**Recommendation:** After creating steps, extract `species_overrides` from all steps, merge into `species_map`, and write to `calculation.yaml`. Remove `species_overrides` from step.yaml (or mark as deprecated).

**Benefit:** Test projects will match intended design, making it easier to test calc-level SSOT behavior.

**Minimal Path:**
1. After step creation, collect all `species_overrides` from steps
2. Call `migrate_species_overrides_to_calc()` (already exists in `src/quantumvitas/core/models.py:534-607`)
3. Save `species_map` to calculation.yaml
4. Optionally remove `species_overrides` from step.yaml (or leave for backwards compat)

### Recommendation #2: Make Import APIs Consistent

**Current:** 
- `build_step_spec_from_qe_input()` writes step-level only
- `build_calculation_from_qe_inputs()` writes calc-level only
- `materialize_project_from_qe_input_folder()` writes both

**Recommendation:** All import APIs should write to calc-level `species_map` only. Step-level `species_overrides` should not be written (or should be deprecated/ignored).

**Minimal Path:**
1. `build_step_spec_from_qe_input()`: Do NOT write `species_overrides` to step.yaml (or mark as deprecated)
2. `build_calculation_from_qe_inputs()`: Keep writing to calc-level (already correct)
3. `materialize_project_from_qe_input_folder()`: Write calc-level only, skip step-level (or mark as deprecated)

### Recommendation #3: Update Step Should Update Calc-Level SSOT

**Current:** `update_step_from_existing_qe_input()` writes to step-level only.

**Recommendation:** If calculation has `species_map`, update it. If not, create it from step `species_overrides`.

**Minimal Path:**
1. After extracting pseudo info, check if calculation has `species_map`
2. If yes, update `calculation.species_map` with extracted info
3. If no, create `species_map` from all step `species_overrides` (migration)

### Recommendation #4: Document Migration Path for Legacy Projects

**Current:** Many projects have step-level `species_overrides` but no calc-level `species_map`.

**Recommendation:** Document automatic migration on load:
- When loading calculation, if no `species_map` but steps have `species_overrides`, call `migrate_species_overrides_to_calc()`
- Save migrated `species_map` to calculation.yaml
- Mark step-level `species_overrides` as deprecated (but keep for backwards compat)

**Note:** Migration function already exists: `migrate_species_overrides_to_calc()` in `src/quantumvitas/core/models.py:534-607`

### Recommendation #5: Clarify Compat Executor Behavior

**Current:** Compat executor bypasses YAML and uses raw .in files as SSOT.

**Recommendation:** Document that compat executor is a special case (legacy playback mode) and does not follow normal SSOT. Consider adding a note that compat mode should eventually be deprecated in favor of YAML-based execution.

**Minimal Path:** Add documentation comment explaining compat executor is legacy mode and uses raw .in as SSOT (not YAML).

### Recommendation #6: Enforce Single SSOT in Runtime

**Current:** Runtime prefers calc-level but falls back to step-level.

**Recommendation:** Once migration is complete, remove fallback to step-level. Runtime should require `calculation.species_map` and fail if missing (with clear error message pointing to migration).

**Minimal Path:**
1. After migration period, change `generate_qe_input_from_spec()` to require `species_map` parameter
2. Remove fallback to `spec.species_overrides`
3. Add clear error if `species_map` is missing: "Calculation must have species_map. Run migration to upgrade legacy project."

---

## 9. Evidence Summary (File + Line References)

### Data Models
- `src/quantumvitas/core/models.py:238-243` - `CalculationModel.species_map` field definition
- `src/quantumvitas/calculation/structure_steps.py:51` - `StructureStepSpec.species_overrides` field definition
- `docs/SCHEMA.md:52-104` - Schema documentation (calc-level SSOT, step-level deprecated)

### Runtime Consumption
- `src/quantumvitas/calculation/structure_steps.py:1070-1112` - `materialize_step_spec()` loads calc-level `species_map`
- `src/quantumvitas/calculation/structure_steps.py:573-576` - `generate_qe_input_from_spec()` precedence (calc-level > step-level)
- `src/quantumvitas/core/pseudo.py:173-212` - `ensure_qe_pseudos()` precedence (species_map parameter > QE input parsing)
- `src/quantumvitas/calculation/runner.py:183-195` - Runner uses `calculation.species_map` exclusively

### Import Consumption
- `src/quantumvitas/calculation/importers.py:198-223` - `build_step_spec_from_qe_input()` writes step-level
- `src/quantumvitas/calculation/importers.py:393-420` - `build_calculation_from_qe_inputs()` writes calc-level
- `src/quantumvitas/calculation/folder_import.py:393-443` - `materialize_project_from_qe_input_folder()` writes both
- `tests/utils/calculation_projects.py:153-197` - Test utility writes step-level only
- `src/quantumvitas/calculation/calculation.py:670-695` - Update step writes step-level only

### Example Files
- `tests/data/project_examples/project1/calculations/si-dos/calculation.yaml` - No `species_map`
- `tests/data/project_examples/project1/calculations/si-dos/steps/scf.step.yaml:29-32` - Has `species_overrides`
- `tests/data/project_examples/project2_bands/calculations/si-bands/calculation.yaml` - No `species_map`
- `tests/data/project_examples/project2_bands/calculations/si-bands/steps/scf.step.yaml:31-34` - Has `species_overrides`

---

## 10. Conclusion

**Current SSOT State:** Hybrid/migrating
- **Intended:** `calculation.yaml` → `species_map` (calculation-level)
- **Actual in most projects:** `step.yaml` → `species_overrides` (step-level, legacy)
- **Runtime:** Prefers calc-level, falls back to step-level

**Key Conflicts:**
1. Import writes step-level, runtime prefers calc-level
2. Test utilities write step-level only
3. Folder import writes both (redundant)
4. Compat executor bypasses YAML (uses raw .in)
5. Update step writes step-level only

**Minimal Path to SSOT:**
1. Migrate test utilities to write calc-level
2. Make import APIs write calc-level only
3. Update step should update calc-level
4. Document migration path for legacy projects
5. Eventually enforce single SSOT in runtime (remove fallback)

**Migration Function Already Exists:** `migrate_species_overrides_to_calc()` in `src/quantumvitas/core/models.py:534-607` can be used to migrate legacy projects.

