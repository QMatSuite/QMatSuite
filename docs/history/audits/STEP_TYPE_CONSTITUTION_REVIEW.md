# Step Type Constitution Review

**Date**: 2026-01-30
**Status**: REVIEW DOCUMENT - Pre-Implementation Audit
**Updated**: Corrected Wannier90 engine ownership

---

## 1. The Laws (Immutable Contract)

### Law 1: Naming Convention (Underscore Rule)

```
GEN step names MUST NOT contain underscore '_'.
Engine prefix MUST NOT contain underscore '_'.
SPEC step name := "{engine_prefix}_{gen_step}"

Corollary: Strings with '_' are SPEC; strings without '_' are GEN.
```

### Law 2: Mapping Definition (No Explicit Tables)

```
For any engine:
  (engine, gen_step) → 0 or 1 spec_step (supported or not)
  (engine, spec_step) → exactly 1 gen_step

This is satisfied by naming definition alone. NO mapping dicts allowed.
```

### Law 3: SSOT Architecture

```
ONE central GenStepRegistry declares all valid gen steps.
Each engine recipe declares:
  - PREFIX: str (required, no '_', SINGLE SOURCE OF TRUTH for engine prefix)
  - SUPPORTED_GEN_STEPS: set[str] (required, ⊆ GenStepRegistry)
```

### Law 4: Canonical Functions (Pure Definition)

```python
def spec_from(prefix: str, gen: str) -> str:
    """Create SPEC from prefix + gen. Pure string concat."""
    return f"{prefix}_{gen}"

def gen_from(spec: str) -> str:
    """Extract GEN from SPEC. Pure string split."""
    if "_" not in spec:
        return spec  # Already gen
    return spec.split("_", 1)[1]

def prefix_from(spec: str) -> str:
    """Extract prefix from SPEC."""
    if "_" not in spec:
        raise ValueError(f"'{spec}' is not a SPEC (no underscore)")
    return spec.split("_", 1)[0]
```

---

## 2. Wannier90 Chain: Correct Engine Ownership

### CRITICAL: W90 vs QE Engine Separation

The Wannier90 workflow involves THREE executables from TWO engines:

| Executable | Engine | Description |
|------------|--------|-------------|
| `wannier90.x -pp` | **w90** | Wannier90 preprocessing (generates .nnkp) |
| `pw2wannier90.x` | **qe** | QE interface (computes overlaps: .amn, .mmn, .eig) |
| `wannier90.x` | **w90** | Wannier90 MLWF construction |

**WRONG (current code in registry.py:321-350)**:
- `w90_preproc` has `engine="qe"` ← INCORRECT! Uses `wannier90.x -pp`
- `w90_run` has `engine="qe"` ← INCORRECT! Uses `wannier90.x`

**CORRECT**:
- `wannierprep` (was `w90_preproc`) → engine="w90", executable="wannier90.x"
- `pw2wannier` (was `pw2wannier90`) → engine="qe", executable="pw2wannier90.x"
- `wannier` (was `w90_run`) → engine="w90", executable="wannier90.x"

### Wannier90 Chain Mapping (Before → After)

| Current GEN | Current SPEC | After GEN | After SPEC | Engine |
|-------------|--------------|-----------|------------|--------|
| `w90_preproc` | `w90_preproc` | `wannierprep` | `w90_wannierprep` | w90 |
| `pw2wannier90` | `qe_pw2wannier90` | `pw2wannier` | `qe_pw2wannier` | qe |
| `w90_run` | `w90_run` | `wannier` | `w90_wannier` | w90 |

### Workflow Chain

```
SCF (qe_scf) → NSCF (qe_nscf) → w90_wannierprep → qe_pw2wannier → w90_wannier
     ↓              ↓                  ↓               ↓              ↓
  QE engine     QE engine         W90 engine      QE engine      W90 engine
```

---

## 3. SSOT Locations (Proposed)

### Central GenStepRegistry

**Module**: `src/quantumvitas/workflow/gen_steps.py` (NEW)

```python
class GenStepRegistry:
    """Single source of truth for all valid GEN step names."""

    # All valid GEN steps (NO underscores allowed)
    GEN_STEPS: frozenset[str] = frozenset({
        # SCF-family
        "scf", "hf", "nscf",
        # Optimization
        "relax",
        # Electronic structure
        "bands", "bandspw", "dos", "projwfc", "pp",
        # Wannier (RENAMED: no underscores)
        "wannierprep",    # was: w90_preproc (W90 engine)
        "pw2wannier",     # was: pw2wannier90 (QE engine)
        "wannier",        # was: w90_run (W90 engine)
        # Phonon
        "ph", "q2r", "matdyn", "dynmat",
        # Dynamics
        "md", "vcmd",     # vc-md → vcmd (no hyphen either for consistency)
        # Post-HF
        "mp2", "td",
        # Escape hatch
        "custom",
    })

    @classmethod
    def is_valid(cls, gen: str) -> bool:
        return gen in cls.GEN_STEPS

    @classmethod
    def validate(cls, gen: str) -> None:
        if "_" in gen:
            raise ValueError(f"GEN step '{gen}' contains underscore (FORBIDDEN)")
        if gen not in cls.GEN_STEPS:
            raise ValueError(f"GEN step '{gen}' not in registry")
```

### Engine Recipe Declarations

**QE Recipe** (`src/quantumvitas/drivers/qe/recipe.py`):
```python
class QERecipe:
    PREFIX: str = "qe"  # REQUIRED, no underscore
    SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({
        "scf", "nscf", "relax", "bands", "bandspw", "dos",
        "projwfc", "pp", "ph", "q2r", "matdyn", "dynmat",
        "md", "vcmd", "pw2wannier", "custom",  # Note: pw2wannier is QE
    })
```

**W90 Recipe** (`src/quantumvitas/drivers/w90/recipe.py`):
```python
class W90Recipe:
    PREFIX: str = "w90"  # REQUIRED, no underscore
    SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({
        "wannierprep",  # wannier90.x -pp
        "wannier",      # wannier90.x
    })
```

### Canonical Conversion Module

**Module**: `src/quantumvitas/workflow/step_type_convert.py` (NEW)

```python
"""Pure functions for SPEC↔GEN conversion. No mapping tables."""

from .gen_steps import GenStepRegistry

ENGINE_PREFIXES: frozenset[str] = frozenset({
    "qe", "pyscf", "orca", "vasp", "lammps", "cp2k", "w90"
})

def spec_from(prefix: str, gen: str) -> str:
    """Create SPEC from prefix + gen."""
    if "_" in prefix:
        raise ValueError(f"Engine prefix '{prefix}' contains underscore")
    if "_" in gen:
        raise ValueError(f"GEN step '{gen}' contains underscore")
    GenStepRegistry.validate(gen)
    return f"{prefix}_{gen}"

def gen_from(spec: str) -> str:
    """Extract GEN from SPEC."""
    if "_" not in spec:
        return spec  # Already gen
    parts = spec.split("_", 1)
    return parts[1]

def is_spec(s: str) -> bool:
    """Check if string is SPEC format."""
    return "_" in s

def is_gen(s: str) -> bool:
    """Check if string is GEN format."""
    return "_" not in s

def prefix_from(spec: str) -> str:
    """Extract engine prefix from SPEC."""
    if "_" not in spec:
        raise ValueError(f"'{spec}' is not a SPEC")
    return spec.split("_", 1)[0]
```

---

## 4. Repo Audit: Wannier90-Specific Code Locations

### 4.1 Core Registry Files

| File | Line(s) | Current | Action |
|------|---------|---------|--------|
| `workflow/registry.py` | 321-330 | `w90_preproc` with `engine="qe"` | Change to `engine="w90"`, spec=`w90_wannierprep`, gen=`wannierprep` |
| `workflow/registry.py` | 331-340 | `qe_pw2wannier90` | Change gen to `pw2wannier`, spec to `qe_pw2wannier` |
| `workflow/registry.py` | 341-350 | `w90_run` with `engine="qe"` | Change to `engine="w90"`, spec=`w90_wannier`, gen=`wannier` |

### 4.2 Driver Files

| File | Line(s) | Issue | Action |
|------|---------|-------|--------|
| `drivers/w90/driver.py` | 61 | `step_type_spec="w90_run"` | Change to `w90_wannier` |
| `drivers/w90/driver.py` | 6-8 | Wrong comment about w90_preproc | Fix comment: wannierprep IS W90, not QE |
| `drivers/w90/driver.py` | 86 | `"GEN_WANNIER": "w90_run"` | DELETE (mapping dict) |
| `drivers/qe/driver.py` | 50 | `"GEN_WANNIER_CONVERT": "qe_pw2wannier90"` | DELETE (mapping dict) |
| `drivers/qe/step_types.py` | 110-114 | `qe_pw2wannier90` | Change spec to `qe_pw2wannier` |
| `drivers/qe/step_types.py` | 121-128 | `w90_preproc` with `engine="qe"` | **REMOVE** - belongs in w90 driver |

### 4.3 Engine Execution Code

| File | Line(s) | Issue | Action |
|------|---------|-------|--------|
| `drivers/qe/engine/qe_engine.py` | 62-64 | Executable map for `w90_preproc`, `pw2wannier90`, `w90_run` | Rename keys to `wannierprep`, `pw2wannier`, `wannier` |
| `drivers/qe/engine/qe_engine.py` | 379-401 | Conditional checks for `w90_preproc`, `w90_run`, `pw2wannier90` | Rename to new GEN names |
| `drivers/qe/engine/qe_engine.py` | 431-442 | `no_stdin_steps` set | Update set members |
| `drivers/qe/engine/qe_calculation.py` | 304-310 | Step type conditionals | Rename GEN names |
| `drivers/qe/engine/qe_calculation.py` | 399-452 | `w90_preproc`, `w90_run`, `pw2wannier90` handling | Rename GEN names |
| `drivers/qe/engine/qe_calculation.py` | 528-576 | Success/failure checks | Rename GEN names |
| `drivers/qe/engine/qe_calculation.py` | 589-607 | Post-execution handling | Rename GEN names |

### 4.4 Calculation/Structure Code

| File | Line(s) | Issue | Action |
|------|---------|-------|--------|
| `calculation/structure_steps.py` | 270 | `"pw2wannier90"` in POST_PROCESSING_STEP_TYPES | Rename to `pw2wannier` |
| `calculation/structure_steps.py` | 283 | STEP_TYPE_NAMELIST_MAP entry | Rename key to `pw2wannier` |
| `calculation/structure_steps.py` | 302 | STEP_TYPE_MODULE_MAP entry | Rename key to `pw2wannier` |
| `calculation/structure_steps.py` | 784 | `WANNIER90_STEP_TYPES = {"w90_preproc", "w90_run", "pw2wannier90"}` | Rename to `{"wannierprep", "wannier", "pw2wannier"}` |
| `calculation/structure_steps.py` | 842 | `if step_type_gen == "w90_preproc" or ...` | Rename conditionals |
| `calculation/structure_steps.py` | 1004 | `elif step_type_gen == "pw2wannier90":` | Rename to `pw2wannier` |
| `calculation/naming.py` | 45, 63-75, 97-98 | `pw2wannier90` special cases | Rename to `pw2wannier` |
| `calculation/step_done.py` | 18 | WANNIER90_STEP_TYPES | Rename members |
| `calculation/verification.py` | 97 | wannier90_step_types | Rename members |
| `calculation/step_artifacts.py` | 50, 60, 78, 119-121 | Function names and dict keys | Rename |
| `calculation/input_runner.py` | 228, 239, 430-442 | WANNIER90_STEP_TYPES and conditionals | Rename |

### 4.5 CLI/Frontend Code

| File | Line(s) | Issue | Action |
|------|---------|-------|--------|
| `cli/main.py` | 956-957 | `"qe_pw2wannier90"`, `"w90_preproc"`, `"w90_run"` | Rename to new SPEC names |
| `cli/main.py` | 964 | `"pw2wannier90"` | Rename to `pw2wannier` |
| `frontends/cli/app.py` | 882-883 | SPEC names in choices | Rename |
| `frontends/cli/app.py` | 890 | GEN names in choices | Rename |

### 4.6 Other Code

| File | Line(s) | Issue | Action |
|------|---------|-------|--------|
| `workflow/templates.py` | 119 | `step_sequence` with `pw2wannier90`, `w90_run` | Rename |
| `workflow/generalized_steps.py` | 42 | `WANNIER_CONVERT = "WANNIER_CONVERT"` | Update comment |
| `core/driver_protocol.py` | 67 | `_allowed_special_ids` with w90 names | Rename or REMOVE |
| `core/pseudo.py` | 143 | Comment about pw2wannier90 | Update comment |
| `drivers/w90/artifact_resolver.py` | 25, 52, 74 | References to w90_preproc | Update comments/code |
| `drivers/w90/handler.py` | 43, 94 | References to w90_preproc | Update comments/code |

### 4.7 Test Files

| File | Issue | Action |
|------|-------|--------|
| `tests/integration/test_wannier90_project_execution.py` | Method names `run_w90_preproc`, `run_pw2wannier90` | Rename methods |
| `tests/unit/test_wannier90_integration.py` | Assertions using old names | Update assertions |
| `tests/fixtures/golden_*/daemon/list_workflow_templates.json` | Contains `pw2wannier90`, `w90_run` | Regenerate fixtures |

### 4.8 Demo Projects and Resources

| File | Issue | Action |
|------|-------|--------|
| `resources/demo_projects/diamond_wannier90_demo.yml` | Lines 401-449: old SPEC names | Update `step_type_spec` values |
| `resources/demo_projects/silicon_wannier90_demo.yml` | Same | Update |
| `resources/demo_projects/copper_wannier90_demo.yml` | Same | Update |

---

## 5. Repo Audit: Other Mapping Tables

### 5.1 Driver `get_materialization_map()` Methods

| File | Status | Action |
|------|--------|--------|
| `src/quantumvitas/drivers/qe/driver.py:33-56` | **MUST DELETE** | Replace with `PREFIX` + `SUPPORTED_GEN_STEPS` |
| `src/quantumvitas/drivers/vasp/driver.py:144-158` | **MUST DELETE** | Replace with `PREFIX` + `SUPPORTED_GEN_STEPS` |
| `src/quantumvitas/drivers/pyscf/driver.py:137-148` | **MUST DELETE** | Replace with `PREFIX` + `SUPPORTED_GEN_STEPS` |
| `src/quantumvitas/drivers/orca/driver.py:141-151` | **MUST DELETE** | Replace with `PREFIX` + `SUPPORTED_GEN_STEPS` |
| `src/quantumvitas/drivers/cp2k/driver.py:117-128` | **MUST DELETE** | Replace with `PREFIX` + `SUPPORTED_GEN_STEPS` |
| `src/quantumvitas/drivers/lammps/driver.py:125-131` | **MUST DELETE** | Replace with `PREFIX` + `SUPPORTED_GEN_STEPS` |
| `src/quantumvitas/drivers/w90/driver.py:80-87` | **MUST DELETE** | Replace with `PREFIX` + `SUPPORTED_GEN_STEPS` |

### 5.2 StepTypeRegistry Internal Maps

| Location | Status | Action |
|----------|--------|--------|
| `registry.py:617` `_gen_to_spec` | **MUST DELETE** | Computed from naming rule |
| `registry.py:621` `_spec_to_obj` | **OK (CANONICAL)** | Keep - maps SPEC to StepTypeSpec objects |
| `registry.py:164-589` `_STEP_TYPES` | **NEEDS REFACTOR** | Reduce to SPEC→metadata only |

### 5.3 Other Mapping Tables

| Location | Status | Action |
|----------|--------|--------|
| `structure_steps.py:278-287` `STEP_TYPE_NAMELIST_MAP` | **OK (DOMAIN-SPECIFIC)** | QE namelist mapping, not spec↔gen |
| `structure_steps.py:290-306` `STEP_TYPE_MODULE_MAP` | **OK (DOMAIN-SPECIFIC)** | QE module mapping, not spec↔gen |
| `structure_steps.py:267-271` `POST_PROCESSING_STEP_TYPES` | **NEEDS REFACTOR** | Uses GEN types; rename underscore members |
| `daemon/compat.py:276` mapping | **MUST DELETE** | Legacy compat layer |
| `step_defaults.py:240` mapping | **MUST DELETE** | Duplicate of registry |

### 5.4 GeneralizedStep Enum

| Location | Status | Action |
|----------|--------|--------|
| `generalized_steps.py:24-59` `GeneralizedStep` | **NEEDS REFACTOR** | Values should match GenStepRegistry (uppercase OK) |

### 5.5 Test Files with Mapping Tables

| File | Status | Action |
|------|--------|--------|
| `tests/drivers/*/test_*_driver.py` | **MUST DELETE** | Tests for `get_materialization_map()` assertions |
| `tests/workflow/test_materialization_ssot.py` | **MUST DELETE** | Entire file tests explicit mappings |
| `tests/gates/test_registry_routing.py` | **NEEDS REFACTOR** | Update to use canonical functions |

---

## 6. The Underscore Problem: Gen Steps to Rename

### Current Violations

| Current GEN | Proposed GEN | Engine | Reason | Impact |
|-------------|--------------|--------|--------|--------|
| `w90_preproc` | `wannierprep` | w90 | Contains `_` | High - registry, tests, templates |
| `w90_run` | `wannier` | w90 | Contains `_` | High - registry, tests, templates |
| `pw2wannier90` | `pw2wannier` | qe | Long name cleanup | Medium - registry, presets |
| `bands_pw` | `bandspw` | qe | Contains `_` | Medium - registry, presets |
| `vc-md` | `vcmd` | qe | Contains `-` (optional fix) | Low |

### Resulting SPEC Names

| After GEN | Engine | After SPEC |
|-----------|--------|------------|
| `wannierprep` | w90 | `w90_wannierprep` |
| `wannier` | w90 | `w90_wannier` |
| `pw2wannier` | qe | `qe_pw2wannier` |
| `bandspw` | qe | `qe_bandspw` |
| `vcmd` | qe | `qe_vcmd` |

---

## 7. Gate Specifications

### Gate G1: No Underscore in GenStepRegistry

```python
def test_no_underscore_in_gen_registry():
    """All GEN steps must not contain underscore."""
    from quantumvitas.workflow.gen_steps import GenStepRegistry
    for gen in GenStepRegistry.GEN_STEPS:
        assert "_" not in gen, f"GEN '{gen}' contains underscore"
```

### Gate G2: No Underscore in Engine Prefix

```python
def test_no_underscore_in_engine_prefix():
    """All engine prefixes must not contain underscore."""
    from quantumvitas.core.driver_registry import DriverRegistry
    import quantumvitas.drivers
    for engine in DriverRegistry.get_all_engines():
        driver = DriverRegistry.get_driver(engine)
        prefix = driver.get_recipe_class().PREFIX
        assert "_" not in prefix, f"Engine '{engine}' prefix '{prefix}' contains underscore"
        assert prefix, f"Engine '{engine}' missing PREFIX"
```

### Gate G3: supported_gen_steps ⊆ GenStepRegistry

```python
def test_supported_gen_steps_subset_of_registry():
    """Each engine's supported_gen_steps must be subset of GenStepRegistry."""
    from quantumvitas.workflow.gen_steps import GenStepRegistry
    from quantumvitas.core.driver_registry import DriverRegistry
    import quantumvitas.drivers

    for engine in DriverRegistry.get_all_engines():
        driver = DriverRegistry.get_driver(engine)
        recipe = driver.get_recipe_class()
        supported = recipe.SUPPORTED_GEN_STEPS
        invalid = supported - GenStepRegistry.GEN_STEPS
        assert not invalid, f"Engine '{engine}' has invalid GEN steps: {invalid}"
```

### Gate G4: No Explicit Mapping Dicts

```python
def test_no_explicit_mapping_dicts():
    """No mapping dicts allowed (spec↔gen)."""
    import subprocess
    result = subprocess.run(
        ["rg", "-l", r"GEN_SCF|GEN_NSCF|get_materialization_map", "src/"],
        capture_output=True, text=True
    )
    # After migration, this should return empty
    assert not result.stdout.strip(), f"Found mapping patterns: {result.stdout}"
```

### Gate G5: Wannier90 Engine Ownership

```python
def test_wannier90_engine_ownership():
    """Wannier90 steps must have correct engine assignment."""
    from quantumvitas.workflow.registry import get_registry

    registry = get_registry()

    # W90 engine steps
    wannierprep = registry.get("w90_wannierprep")
    assert wannierprep.engine == "w90", f"wannierprep has wrong engine: {wannierprep.engine}"

    wannier = registry.get("w90_wannier")
    assert wannier.engine == "w90", f"wannier has wrong engine: {wannier.engine}"

    # QE engine step
    pw2wannier = registry.get("qe_pw2wannier")
    assert pw2wannier.engine == "qe", f"pw2wannier has wrong engine: {pw2wannier.engine}"
```

---

## 8. Summary: Actions Required

### DELETE (Duplicate Truth)

1. All `get_materialization_map()` methods in drivers
2. `_gen_to_spec` in StepTypeRegistry
3. `GeneralizedStep` enum (or refactor to use GenStepRegistry)
4. All `GEN_*` string constants
5. `tests/workflow/test_materialization_ssot.py`
6. `w90_preproc` from QE step_types.py (it's a W90 step, not QE)

### REFACTOR (Update to Canonical)

1. `_STEP_TYPES` dict → only SPEC→metadata mapping
2. StepTypeRegistry → use canonical functions for gen↔spec
3. All code using `normalize_step_type_to_gen()` → use `gen_from()`
4. Rename underscore-containing GEN steps
5. Fix `w90_preproc` and `w90_run` engine assignment: `engine="w90"` not `"qe"`

### CREATE (New SSOT)

1. `src/quantumvitas/workflow/gen_steps.py` - GenStepRegistry
2. `src/quantumvitas/workflow/step_type_convert.py` - Pure functions
3. `tests/gates/test_step_type_constitution.py` - Gate tests

### KEEP (OK/Canonical)

1. `STEP_TYPE_NAMELIST_MAP` (QE-specific, domain knowledge)
2. `STEP_TYPE_MODULE_MAP` (QE-specific, domain knowledge)
3. `_spec_to_obj` mapping in StepTypeRegistry (SPEC→metadata)
