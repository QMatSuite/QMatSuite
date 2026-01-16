# Pseudopotential Resolution Regression Forensics

**Date**: 2025-01-XX  
**Purpose**: Diagnose why tests fail to auto-find internal pseudopotentials (`resources/pseudo`) after execution pipeline refactor.

**Status**: Investigation only (no fixes implemented)

---

## Reproduction & Observed Failures

### Test Failures

**1. Integration test: `test_run_full_calculation` (Si bands)**
```
FAILED tests/integration/test_si_bands_calculation.py::TestSiBandsCalculation::test_run_full_calculation
AssertionError: assert <StepStatus.FAILED: 'failed'> == <StepStatus.SUCCESS: 'success'>
ERROR: scf failed (returncode=1)
```

**2. Integration test: `test_run_full_calculation` (Si DOS)**
```
FAILED tests/integration/test_si_dos_calculation.py::TestSiDOSCalculation::test_run_full_calculation
AssertionError: assert <StepStatus.FAILED: 'failed'> == <StepStatus.SUCCESS: 'success'>
ERROR: scf failed (returncode=1)
```

**3. CLI test: `test_cli_run_calculation` (Si DOS)**
```
FAILED tests/cli/test_si_dos_calculation_cli.py::test_cli_run_calculation
AssertionError: assert 1 == 0
ValueError: Pseudopotential not configured for element(s): Si. This is a configuration error, not a missing file.
```

### Error Details (CLI test)

From CLI test error log:
```
ERROR quantumvitas.core.pseudo:pseudo.py:274 [PSEUDO_CONFIG_ERROR] Pseudopotential not configured for element(s): Si
  Resolution source: QE input ATOMIC_SPECIES (legacy/standalone)
  qe_input_file=/Users/hh7465/QMatSuite/.tmp/test_outputs/cli_si_dos_project/calculations/si_dos/raw/.temp_input_for_pseudo_resolution.in
  project_pseudo_dir=/Users/hh7465/QMatSuite/.tmp/test_outputs/cli_si_dos_project/pseudo
  system_pseudo_dir=/Users/hh7465/QMatSuite/resources/pseudo
  required_pps=[]
  required_elements=['Si']
  missing_placeholders=['Si']
  element_to_pseudo={}
  project_pseudo_dir.exists()=True
  calculation_path=/Users/hh7465/QMatSuite/.tmp/test_outputs/cli_si_dos_project/calculations/si_dos/calculation.yaml
  structure_path=/Users/hh7465/QMatSuite/.tmp/test_outputs/cli_si_dos_project/structures/test_structure.json
  species_map_keys=[]
  element_pseudopot_values={}
  species_map_provided=No
  species_map_keys_provided=[]
```

**Key observations**:
- `system_pseudo_dir` is correctly resolved: `/Users/hh7465/QMatSuite/resources/pseudo`
- `required_elements=['Si']` (element detected)
- `missing_placeholders=['Si']` (pseudopotential filename missing)
- `element_to_pseudo={}` (no filename found)
- `species_map_provided=No` (calculation.yaml has no species_map)
- `required_pps=[]` (no pseudopotential filenames to resolve)

**Failing step**: `scf` (first step in all three tests)

---

## Expected Historical Behavior (internal resources/pseudo)

### Historical Resolution Path

**Before execution pipeline refactor** (Path S - parse existing .in):
1. Tests used `existing_input_file` pointing to original `.in` files in `raw/` directory
2. Original `.in` files contained real pseudopotential filenames in ATOMIC_SPECIES:
   ```
   ATOMIC_SPECIES
    Si  28.0855  Si.pbe-n-rrkjus_psl.1.0.0.UPF
   ```
3. When parsing existing `.in` files, pseudopotential filenames were extracted and used
4. `ensure_qe_pseudos` received either:
   - Real filenames from parsed ATOMIC_SPECIES, OR
   - `species_map` populated from extracted data

**Evidence**: Original test data files contain real pseudopotential filenames:
- `tests/data/4_Si_DOS/si.2_nscf.in`: `Si.pbe-n-rrkjus_psl.1.0.0.UPF`
- `tests/data/7_Si_bandStructure/`: Similar structure

### Internal Pseudo Directory

**Location**: `resources/pseudo/` (repo root)

**Evidence**:
- `get_system_pseudo_dir()` returns `repo_root / "resources" / "pseudo"` (pseudo.py:480-490)
- Files exist: `resources/pseudo/Si.*.UPF` (verified via `ls`)
- `ensure_qe_pseudos` checks `system_pseudo_dir` as second priority (after `project_pseudo_dir`) (pseudo.py:390-398)

**Historical usage**: Tests implicitly relied on:
1. Pseudopotentials copied to `project/pseudo` by `create_calculation_project` (tests/utils/calculation_projects.py:62)
2. OR auto-resolution from `system_pseudo_dir` when filenames were known

---

## Pseudo Resolution Contract (where it should come from)

### Q1: Is there an engine-level default pseudo library path (resources/pseudo)?

**Answer**: **YES**

**Where defined**:
- `get_system_pseudo_dir()` in `src/quantumvitas/core/pseudo.py:480-490`
- Returns `repo_root / "resources" / "pseudo"` if quantumvitas root is found

**Used in**:
- `ensure_qe_pseudos()`: `system_pseudo_dir` parameter (defaults to `get_system_pseudo_dir()` if None) (pseudo.py:312-318)
- `materialize_step_spec()`: Passes `get_system_pseudo_dir()` to `ensure_qe_pseudos` (structure_steps.py:1169)

**Production vs tests**: Used in both production code and tests. Tests rely on it for implicit resolution.

### Q2: Does QE input generation require a filename for each ATOMIC_SPECIES, or can it resolve by element name within pseudo_dir?

**Answer**: **Requires explicit filename** (no auto-resolve by element name)

**Evidence**:
- `qe_input_from_structure()` creates ATOMIC_SPECIES with placeholders: `__MISSING_PSEUDO__{element}` (structure_io.py:199)
- `apply_species_overrides_to_qe_input()` only updates existing ATOMIC_SPECIES rows; does NOT auto-resolve by element name (input_runner.py:682-723)
- `ensure_qe_pseudos()` requires explicit filenames in `required_pps` list; searches for those filenames, does NOT search by element (pseudo.py:378-444)

**Placeholder detection**:
- `is_missing_pseudo_placeholder()` checks for `__MISSING_PSEUDO__{element}` pattern (pseudo.py:37-47)
- If placeholder found, `ensure_qe_pseudos` raises `ValueError` (configuration error) before file resolution (pseudo.py:214-300)

**Conclusion**: System requires explicit pseudopotential filenames. No element→filename auto-resolution exists.

### Q3: At what stage is pseudo_dir injected into QE CONTROL?

**Answer**: **During materialization (before write)**

**Evidence**:
- `materialize_step_spec()` calls `set_pseudo_dir_in_input()` after generating QE input (structure_steps.py:1188)
- `pseudo_dir` is set to `project_pseudo_dir` (relative to `output_dir`) (structure_steps.py:1145, 1188)
- This happens during `.in` file generation, not during runtime

**What changed with SSOT refactor**:
- **Before**: `prepare_input_step()` (called during run) could parse existing `.in` and extract pseudopotentials
- **After**: `materialize_step_spec()` (called before run) generates `.in` from spec, and spec lacks pseudopotential filenames

**Key change**: Generation path no longer has access to original `.in` files' ATOMIC_SPECIES with real filenames.

---

## Current Runtime Call Chain (integration + CLI)

### Integration Test Call Chain

**File**: `tests/integration/test_si_bands_calculation.py:51-59`

```
test_run_full_calculation()
  ↓ Project.open(si_bands_project)
  ↓ project.get_calculation("si_bands")
  ↓ CalculationRunner.run(calculation)
  ↓ CalculationRunner._execute_with_jobgraph()
  ↓ JobExecutor.execute_jobs()
  ↓ QEJobHandler.execute()
  ↓ Step.run()
  ↓ (NEW PATH: direct engine call, no prepare_input_step)
  ↓ engine.backend.run_step()
```

**Materialization path** (happens before Step.run):
```
CalculationRunner._execute_with_jobgraph()
  ↓ (implicit materialization via JobGraph)
  ↓ materialize_step_spec()
  ↓ generate_qe_input_from_spec(structure, spec, species_map=calculation_species_map)
  ↓ generate_qe_input_from_structure() → creates ATOMIC_SPECIES with placeholders
  ↓ apply_species_overrides_to_qe_input(qe_input, effective_species_overrides)
    (effective_species_overrides is None/empty → no-op)
  ↓ ensure_qe_pseudos(temp_input, project_pseudo_dir, system_pseudo_dir, species_map=calculation_species_map)
    (calculation_species_map is empty → falls back to parsing QE input)
    (QE input has placeholders → raises ValueError)
```

**Files**:
- `tests/integration/test_si_bands_calculation.py:51-59`
- `src/quantumvitas/calculation/runner.py:483-653`
- `src/quantumvitas/calculation/structure_steps.py:648-1193`
- `src/quantumvitas/core/pseudo.py:67-477`

### CLI Test Call Chain

**File**: `tests/cli/test_si_dos_calculation_cli.py:34-40`

```
test_cli_run_calculation()
  ↓ CliRunner.invoke(cli_app, ["run", "calculation", "si_dos", ...])
  ↓ run_calculation_command()
  ↓ QVService.run_calculation()
  ↓ CalculationRunner.run(calculation)
  ↓ (same materialization path as integration test)
```

**Materialization path**: Same as integration test (above).

---

## Where the Regression Happens (exact function/branch)

### Root Cause: Type D - Previously parsing .in imported ATOMIC_SPECIES filenames

**Hypothesis**: **CONFIRMED**

**Evidence**:

1. **Test fixture does NOT extract species_overrides**:
   - `create_calculation_project()` calls `_build_step_spec_from_qe_input_data()` (calculation_projects.py:148)
   - `_build_step_spec_from_qe_input_data()` only extracts `parameters` and `cards` (importers.py:49-92)
   - It does NOT extract `species_overrides` (that extraction happens in `build_step_spec_from_qe_input()`, not `_build_step_spec_from_qe_input_data()`)
   - Result: `step.yaml` has no `species_overrides` field

2. **calculation.yaml has no species_map**:
   - `create_calculation_project()` creates `calculation.yaml` with no `species_map` field (calculation_projects.py:178-193)
   - Result: `calculation_species_map` is `None` when `materialize_step_spec()` loads it (structure_steps.py:1090)

3. **QE input generation creates placeholders**:
   - `generate_qe_input_from_structure()` creates ATOMIC_SPECIES with `__MISSING_PSEUDO__Si` (structure_io.py:199)
   - `apply_species_overrides_to_qe_input()` with empty overrides does nothing (input_runner.py:689-690)
   - Result: Generated QE input has placeholders

4. **ensure_qe_pseudos fails on placeholders**:
   - `ensure_qe_pseudos()` receives `species_map=None` (empty calculation_species_map)
   - Falls back to parsing QE input (pseudo.py:193-212)
   - Finds placeholders `__MISSING_PSEUDO__Si` (pseudo.py:204-207)
   - Raises `ValueError` before file resolution (pseudo.py:214-300)

**Exact function where regression occurs**:
- **Primary**: `tests/utils/calculation_projects.py:148` - `_build_step_spec_from_qe_input_data()` does not extract species_overrides
- **Secondary**: `src/quantumvitas/calculation/structure_steps.py:1112` - `generate_qe_input_from_spec()` receives empty `species_map`
- **Tertiary**: `src/quantumvitas/core/pseudo.py:214-300` - `ensure_qe_pseudos()` raises ValueError on placeholders

**Why it worked before**:
- **Old path (Path S)**: `prepare_input_step()` parsed existing `.in` files which had real filenames
- **New path (Path P)**: `materialize_step_spec()` generates `.in` from spec, and spec lacks filenames

### Other Hypotheses (Ruled Out)

**Type A: pseudo_dir injection moved/removed** - **NO**
- `pseudo_dir` is still injected during materialization (structure_steps.py:1188)
- `system_pseudo_dir` is correctly passed to `ensure_qe_pseudos` (structure_steps.py:1169)

**Type B: mapping element→filename no longer happens** - **N/A**
- System never had element→filename auto-resolution
- Always required explicit filenames

**Type C: project_root / resource root resolution changed** - **NO**
- `get_system_pseudo_dir()` still correctly resolves `resources/pseudo` (pseudo.py:480-490)
- `_find_quantumvitas_root()` still works (verified in error logs)

---

## Hypotheses & Evidence

### Hypothesis 1: Test fixture does not extract species_overrides (CONFIRMED)

**Evidence**:
- `create_calculation_project()` uses `_build_step_spec_from_qe_input_data()` which only extracts `parameters` and `cards` (calculation_projects.py:148, importers.py:49-92)
- `build_step_spec_from_qe_input()` (different function) extracts `species_overrides`, but it's not called by the test fixture (importers.py:198-223)
- Original `.in` files have real filenames: `Si.pbe-n-rrkjus_psl.1.0.0.UPF` (verified in test data)

**Conclusion**: Test fixture creates step.yaml without species_overrides, even though original .in files contain pseudopotential filenames.

### Hypothesis 2: calculation.yaml lacks species_map (CONFIRMED)

**Evidence**:
- `create_calculation_project()` creates `calculation.yaml` with no `species_map` field (calculation_projects.py:178-193)
- `materialize_step_spec()` loads `calculation_species_map` from calculation.yaml, gets `None` (structure_steps.py:1090)
- Error log shows `species_map_provided=No` and `species_map_keys=[]`

**Conclusion**: calculation.yaml has no species_map, so materialization cannot use it.

### Hypothesis 3: Generated QE input has placeholders (CONFIRMED)

**Evidence**:
- `generate_qe_input_from_structure()` creates ATOMIC_SPECIES with `make_missing_pseudo_placeholder(el.symbol)` (structure_io.py:199)
- `apply_species_overrides_to_qe_input()` with empty overrides returns early (input_runner.py:689-690)
- Error log shows `missing_placeholders=['Si']` and `element_to_pseudo={}`

**Conclusion**: Generated QE input contains placeholders because no species_overrides were applied.

### Hypothesis 4: ensure_qe_pseudos fails before file resolution (CONFIRMED)

**Evidence**:
- `ensure_qe_pseudos()` checks for placeholders before file resolution (pseudo.py:214-300)
- If placeholders found, raises `ValueError` (configuration error) immediately (pseudo.py:293-300)
- File resolution code (pseudo.py:378-444) is never reached when placeholders exist

**Conclusion**: System correctly identifies configuration error (missing filenames) before attempting file resolution.

---

## Minimal Fix Options (no code)

### Option 1: Extract species_overrides in test fixture (RECOMMENDED)

**Location**: `tests/utils/calculation_projects.py:148`

**Change**: After calling `_build_step_spec_from_qe_input_data()`, also extract `species_overrides` from ATOMIC_SPECIES card (similar to `build_step_spec_from_qe_input()` lines 198-223).

**Rationale**:
- Original `.in` files contain real pseudopotential filenames
- Test fixture should preserve this information in step.yaml
- Minimal change, only affects test fixtures
- Does not change production behavior

**Implementation hint**:
```python
# After line 150 in calculation_projects.py:
species_overrides = {}
atomic_species_card = qe_input.get_card(QECardType.ATOMIC_SPECIES)
if atomic_species_card and atomic_species_card.data:
    # Extract species_overrides (same logic as importers.py:198-223)
    # Then add to step_spec["species_overrides"] = species_overrides
```

**Pros**:
- Preserves information from original .in files
- Aligns with import workflow (`build_step_spec_from_qe_input` already does this)
- Tests will work without explicit pseudopotential configuration

**Cons**:
- Only fixes test fixtures, not general case
- If original .in files lack pseudopotentials, tests will still fail

### Option 2: Auto-resolve from system_pseudo_dir when species_overrides empty (NOT RECOMMENDED)

**Location**: `src/quantumvitas/calculation/structure_steps.py:575-576` or `src/quantumvitas/io/structure_io.py:199`

**Change**: When `effective_species_overrides` is empty, scan `system_pseudo_dir` for matching element files (e.g., `Si.*.UPF`) and use first match.

**Rationale**:
- Provides fallback for tests that don't configure pseudopotentials
- Uses internal pseudo library as implicit default

**Pros**:
- Works for tests without explicit configuration
- Uses existing `system_pseudo_dir` infrastructure

**Cons**:
- **Violates contract**: System requires explicit filenames, not element→filename mapping
- **Ambiguous**: Multiple `Si.*.UPF` files may exist; which one to choose?
- **Production risk**: Could silently use wrong pseudopotential in production
- **Breaks explicit configuration**: If user wants to use a specific pseudo, auto-resolution might override it

**Verdict**: **NOT RECOMMENDED** - violates explicit configuration contract.

### Option 3: Populate calculation.yaml species_map from first step's .in file (ALTERNATIVE)

**Location**: `tests/utils/calculation_projects.py:178-193`

**Change**: After creating step files, extract species_overrides from first step's parsed QE input and populate `calculation.yaml` `species_map`.

**Rationale**:
- Calculation-level species_map is the canonical source (per materialize_step_spec contract)
- Tests can rely on it being populated from original .in files

**Pros**:
- Uses calculation-level species_map (canonical)
- Aligns with production workflow (calculation.yaml is SSOT for species)

**Cons**:
- Requires parsing first step's .in file twice (once for step.yaml, once for calculation.yaml)
- More complex than Option 1

**Verdict**: **ALTERNATIVE** - works but more complex than Option 1.

### Option 4: Modify test fixtures to explicitly set --SPECIES.Si.pseudopot (NOT RECOMMENDED)

**Location**: Test fixtures or test setup

**Change**: Add explicit pseudopotential configuration in test setup.

**Rationale**:
- Makes tests explicit about pseudopotential requirements
- No code changes to production

**Pros**:
- Explicit configuration (clear intent)
- No production code changes

**Cons**:
- **Brittle**: Requires knowing exact filenames in resources/pseudo
- **Maintenance burden**: Tests break if filenames change
- **Doesn't fix root cause**: Tests should work with internal pseudo library without explicit config

**Verdict**: **NOT RECOMMENDED** - brittle and doesn't address root cause.

---

## Recommended Fix

**Option 1: Extract species_overrides in test fixture** (RECOMMENDED)

**Justification**:
1. **Root cause**: Test fixture does not extract pseudopotential filenames from original .in files
2. **Minimal change**: Only affects test fixture, not production code
3. **Preserves information**: Original .in files have real filenames; fixture should preserve them
4. **Aligns with import workflow**: `build_step_spec_from_qe_input()` already does this extraction
5. **No contract violation**: Uses explicit filenames from original files, not element→filename mapping

**Implementation location**: `tests/utils/calculation_projects.py:148` (after `_build_step_spec_from_qe_input_data()` call)

**Expected outcome**:
- `step.yaml` files will contain `species_overrides` with real pseudopotential filenames
- `generate_qe_input_from_spec()` will apply these overrides, replacing placeholders
- `ensure_qe_pseudos()` will receive real filenames (either from species_map or from QE input)
- Tests will pass without explicit pseudopotential configuration

---

## Appendix: Evidence Snippets

### Snippet 1: Test fixture does not extract species_overrides

**File**: `tests/utils/calculation_projects.py:140-150`
```python
# Parse the reference input file to extract QE parameters
input_file = raw_dir / step["input"]
parameters = {}
cards = {}
if input_file.exists():
    try:
        qe_input = QEInputParser.parse_file(input_file)
        # Extract parameters and cards WITHOUT applying defaults (preserve original)
        parameters, cards = _build_step_spec_from_qe_input_data(
            qe_input, step_id, apply_defaults=False
        )
    except Exception as e:
        # If parsing fails, fall back to minimal spec
        print(f"Warning: Failed to parse {input_file}: {e}")

# DAG model: Step YAML should NOT contain structure_id (inherits from calculation)
step_spec = {
    "meta": step_meta.to_dict(),
    "step_type": step_id,  # Use step id as step_type (scf, nscf, dos, etc.)
    # structure_id is NOT written to step YAML (DAG model)
}
# Add extracted parameters and cards if available
if parameters:
    step_spec["parameters"] = parameters
if cards:
    step_spec["cards"] = cards
# NOTE: species_overrides is NOT extracted here
```

### Snippet 2: _build_step_spec_from_qe_input_data only extracts parameters and cards

**File**: `src/quantumvitas/calculation/importers.py:49-92`
```python
def _build_step_spec_from_qe_input_data(
    qe_input: QEInput,
    step_type: str,
    *,
    apply_defaults: bool = False,
) -> tuple[Dict[str, Dict[str, object]], Dict[str, Dict[str, object]]]:
    """
    Build step spec parameters and cards from a QE input, optionally merging with defaults.
    
    Returns:
        Tuple of (parameters_dict, cards_dict)
    """
    # Extract parameters and cards from the input
    parameters = _extract_parameters(qe_input)
    cards = _extract_cards(qe_input)
    # NOTE: Does NOT extract species_overrides
    # ...
    return parameters, cards
```

### Snippet 3: build_step_spec_from_qe_input DOES extract species_overrides (but not called by fixture)

**File**: `src/quantumvitas/calculation/importers.py:198-223`
```python
# Extract species_overrides from ATOMIC_SPECIES card (if present)
# ATOMIC_SPECIES should not be in cards - it should be in species_overrides
species_overrides = {}
atomic_species_card = qe_input.get_card(QECardType.ATOMIC_SPECIES)
if atomic_species_card and atomic_species_card.data:
    for row in atomic_species_card.data:
        if isinstance(row, list) and len(row) >= 3:
            element_symbol = str(row[0]).strip()
            mass = row[1] if len(row) > 1 else None
            pseudo_filename = str(row[2]).strip() if len(row) > 2 else None
            
            # Build species override
            override = {}
            if mass is not None:
                override["mass"] = float(mass)
            if pseudo_filename:
                from quantumvitas.core.pseudo import is_missing_pseudo_placeholder
                if not is_missing_pseudo_placeholder(pseudo_filename):
                    override["pseudopot"] = pseudo_filename
            
            if override:
                species_overrides[element_symbol] = override
```

### Snippet 4: QE input generation creates placeholders

**File**: `src/quantumvitas/io/structure_io.py:191-200`
```python
# ATOMIC_SPECIES: element symbol, atomic mass, pseudo file name (placeholder).
# Use obvious placeholder to indicate missing configuration (not a real file)
from quantumvitas.core.pseudo import make_missing_pseudo_placeholder
species: List[Element] = unique_species
atomic_species_data: List[list] = []
for el in species:
    mass = float(el.atomic_mass)
    # Use placeholder to clearly indicate missing configuration
    pseudo_name = make_missing_pseudo_placeholder(el.symbol)  # Creates "__MISSING_PSEUDO__Si"
    atomic_species_data.append([el.symbol, mass, pseudo_name])
```

### Snippet 5: apply_species_overrides does nothing when overrides empty

**File**: `src/quantumvitas/calculation/input_runner.py:682-690`
```python
def apply_species_overrides_to_qe_input(
    qe_input: QEInput, overrides: Optional[Mapping[str, Mapping[str, Any]]]
) -> None:
    """
    Apply element-specific mass/pseudopotential overrides to ATOMIC_SPECIES card.
    """

    if not overrides:
        return  # Early return - placeholders remain in QE input
```

### Snippet 6: ensure_qe_pseudos raises ValueError on placeholders

**File**: `src/quantumvitas/core/pseudo.py:214-300`
```python
# Fail early with clear configuration error if placeholders or empty pseudos are found
if missing_placeholders:
    elements_str = ", ".join(sorted(set(missing_placeholders)))
    # ...
    raise ValueError(
        f"Pseudopotential not configured for element(s): {elements_str}. "
        f"This is a configuration error, not a missing file. "
        f"Please configure pseudopotentials using:\n"
        f"  - CLI: --SPECIES.{first_element}.pseudopot=<filename>\n"
        f"  - Step spec: species_overrides['{first_element}'] = {{'pseudopot': '<filename>'}}\n"
        f"  - Or import from existing QE input that has ATOMIC_SPECIES with pseudopotential filenames"
    )
```

### Snippet 7: materialize_step_spec passes empty species_map

**File**: `src/quantumvitas/calculation/structure_steps.py:1112, 1166-1170**
```python
# Pass species_map to generate_qe_input_from_spec so it populates ATOMIC_SPECIES correctly
qe_input, _ = generate_qe_input_from_spec(structure, spec_obj, species_map=calculation_species_map)
# ...
# Resolve pseudopotentials
# Pass calculation_species_map as PRIMARY source (calculation-level authority)
pseudo_result = ensure_qe_pseudos(
    qe_input_file=temp_input,
    project_pseudo_dir=project_pseudo_dir,
    system_pseudo_dir=get_system_pseudo_dir(),
    species_map=calculation_species_map,  # This is None/empty in failing tests
)
```

### Snippet 8: calculation.yaml has no species_map

**File**: `tests/utils/calculation_projects.py:178-193`
```python
calculation_config = {
    "meta": {
        "id": calculation_ulid,
        "name": calculation_id,
        "slug": calculation_id,
        "path": f"calculations/{calculation_id}",
        "kind": "calculation",
    },
    "mode": "strict",
    "calculation": {"working_dir": "raw"},
    "structure_id": structure_id,
    "steps": step_entries,
    # NOTE: No "species_map" field
}
```

### Snippet 9: Original .in files contain real pseudopotential filenames

**File**: `tests/data/4_Si_DOS/si.2_nscf.in`
```
ATOMIC_SPECIES
 Si  28.0855  Si.pbe-n-rrkjus_psl.1.0.0.UPF
```

### Snippet 10: system_pseudo_dir is correctly resolved

**File**: `src/quantumvitas/core/pseudo.py:480-490`
```python
def get_system_pseudo_dir() -> Optional[Path]:
    """
    Get the system-wide pseudopotential cache directory.
    
    Returns:
        Path to quantumvitas resources/pseudo, or None if quantumvitas root not found
    """
    qv_root = _find_quantumvitas_root()
    if qv_root:
        return qv_root / "resources" / "pseudo"
    return None
```

---

## Summary

**Root cause**: Test fixture (`create_calculation_project`) does not extract `species_overrides` from original `.in` files when creating `step.yaml`. After execution pipeline refactor, tests use Path P (generate from spec) instead of Path S (parse existing .in), so generated QE inputs have placeholders instead of real filenames.

**Why it worked before**: Path S parsed existing `.in` files which contained real pseudopotential filenames.

**Why it fails now**: Path P generates from spec, and spec lacks pseudopotential filenames.

**Minimal fix**: Extract `species_overrides` from ATOMIC_SPECIES in test fixture (Option 1).

**Files to modify**: `tests/utils/calculation_projects.py:148` (add species_overrides extraction after `_build_step_spec_from_qe_input_data()` call).

