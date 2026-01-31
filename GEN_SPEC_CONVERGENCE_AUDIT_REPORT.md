# GEN/SPEC Step Type Convergence Audit Report

**Date**: 2025-01-27  
**Auditor**: Independent Review  
**Scope**: Repository-wide audit of step type identity fields, legacy remnants, and constitution compliance

---

## 1. Executive Summary

### Compliance Status: **PARTIALLY COMPLIANT** ⚠️

The repository has made significant progress toward GEN/SPEC convergence, but **critical violations and high-risk legacy remnants remain**. The codebase is not fully compliant with the constitution.

### Top 5 Remaining Risks

1. **`get_materialization_map()` methods still exist in drivers** - These are "second truth" mappings that duplicate SSOT logic. While `DriverRegistry._build_materialization_map()` uses `PREFIX + SUPPORTED_GEN_STEPS`, the protocol still requires drivers to implement `get_materialization_map()`, creating a dual-path system.

2. **`GeneralizedStep` enum and `GEN_*` namespace still active** - The `generalized_steps.py` module maintains a `GeneralizedStep` enum and normalizes to `GEN_*` format internally, creating a third namespace alongside `step_type_gen` and `step_type_spec`.

3. **`normalize_step_type_to_gen()` fallback uses prefix stripping** - The function in `registry.py:851-882` falls back to hardcoded `ENGINE_PREFIXES` tuple stripping when registry lookup fails, violating the "no fallback heuristics" rule.

4. **Multiple `ENGINE_PREFIXES` definitions scattered** - Found in `structure_steps.py:242`, `registry.py:876`, `step_type_convert.py:14`, creating potential drift if one is updated but others aren't.

5. **Legacy `step_type` key still accepted in some contexts** - While `StructureStepSpec.from_dict()` raises hard errors, some test fixtures and tools still read `step_type` as fallback (e.g., `test_w90_parameter_rendering.py:39`).

### Old World Entry Points

- **`src/quantumvitas/workflow/generalized_steps.py`** - Entire module is a legacy entry point. Contains `GeneralizedStep` enum, `materialize_step()` that normalizes to `GEN_*` format, and delegates to `DriverRegistry.materialize_step_type()` which uses `get_materialization_map()`.

- **`src/quantumvitas/workflow/registry.py`** - Contains `normalize_step_type_to_gen()` with fallback prefix stripping, and maintains `STEP_TYPE_ALIASES` dict for legacy compatibility.

- **`src/quantumvitas/core/driver_registry.py`** - While it builds from `PREFIX + SUPPORTED_GEN_STEPS`, it still calls `driver.get_materialization_map()` as fallback, and applies special-case overrides in `_apply_special_case_overrides()`.

---

## 2. Hard Violations (Must-Fix)

### 2.1 Non-Canonical Fields in Serialized DTOs

#### Violation: `step_type` key in API responses (v0 compatibility)

**Location**: `src/quantumvitas/daemon/server.py:1459, 4139`

```python
# Line 1459
step_type = (payload.get("step_type_gen") or payload.get("step_type", "")).strip().lower()

# Line 4139
step_type = payload.get("step_type_spec") or payload.get("step_type_gen") or payload.get("step_type")
```

**Issue**: Daemon server accepts legacy `step_type` key for v0 compatibility. This violates Constitution §1 which states only `step_type_gen` and `step_type_spec` are allowed.

**Impact**: External clients can send non-canonical keys, creating drift risk.

---

#### Violation: Test fixtures read `step_type` as fallback

**Location**: `tests/unit/test_w90_parameter_rendering.py:39, 75`

```python
# Line 39
step_type = step.get("step_type_spec") or step.get("step_type")

# Line 75
step_type = step.get("step_type_spec") or step.get("step_type")
```

**Issue**: Tests accept legacy `step_type` key, normalizing drift into test expectations.

**Impact**: Tests may pass with non-canonical data, masking violations.

---

#### Violation: Tools read `step_type` from demo files

**Location**: `tools/import_tutorial_datasets.py:303, 574, 1349, 1403, 1672`

```python
# Line 303
step_types.append(step.get("step_type", "unknown"))
```

**Issue**: Import tools read legacy `step_type` key from demo project files.

**Impact**: Legacy data persists in imported projects.

---

### 2.2 Non-Canonical Fields in Persisted YAML

#### ✅ COMPLIANT: `StructureStepSpec.to_dict()` writes only `step_type_spec`

**Location**: `src/quantumvitas/calculation/structure_steps.py:195`

```python
data: Dict[str, Any] = {
    "meta": meta_dict,
    "step_type_spec": self.step_type_spec,
}
```

**Status**: ✅ Correctly writes only `step_type_spec` to step.yaml files.

---

#### ✅ COMPLIANT: `StructureStepSpec.from_dict()` raises hard error on legacy `step_type`

**Location**: `src/quantumvitas/calculation/structure_steps.py:106-107`

```python
if "step_type" in data and "step_type_spec" not in data:
    raise ValueError("Legacy 'step_type' key found in step.yaml. Run migration script.")
```

**Status**: ✅ Correctly rejects legacy keys.

---

### 2.3 Non-Canonical Fields in RPC/API Shapes

#### Violation: Daemon accepts `step_type` for v0 compatibility

**Location**: `src/quantumvitas/daemon/server.py:1459, 1464`

```python
step_type = (payload.get("step_type_gen") or payload.get("step_type", "")).strip().lower()
if not step_type:
    raise ValueError("'step_type_gen' is required in payload (or 'step_type' for v0 compat)")
```

**Issue**: Explicitly documents v0 compatibility path, violating Constitution §1.

**Impact**: External API surface accepts non-canonical keys.

---

#### ✅ COMPLIANT: `step_to_dict()` writes both `step_type_spec` and `step_type_gen`

**Location**: `src/quantumvitas/api/_mapping/dto_mapping.py:518-519`

```python
"step_type_spec": step_dto.step_type_spec,
"step_type_gen": step_dto.step_type_gen,  # Never fallback to step_type_spec - they're semantically different
```

**Status**: ✅ Correctly writes both canonical fields.

---

## 3. High-Risk Legacy Remnants (Should-Fix)

### 3.1 `GeneralizedStep` Enum and `GEN_*` Namespace

**Location**: `src/quantumvitas/workflow/generalized_steps.py:24-59, 97-100, 127-130, 299-302, 376-378`

**Evidence**:
```python
# Line 24-59: Enum definition
class GeneralizedStep(str, Enum):
    SCF = "SCF"
    NSCF = "NSCF"
    # ... etc

# Line 97-100: Normalization to GEN_ format
gen_type_upper = generalized_step.upper()
if not gen_type_upper.startswith("GEN_"):
    gen_type_upper = f"GEN_{gen_type_upper}"

# Line 299-302: Same pattern
gen_step_upper = generalized_step.upper()
if not gen_step_upper.startswith("GEN_"):
    gen_step_upper = f"GEN_{gen_step_upper}"

# Line 376-378: Stripping GEN_ prefix
if gen_step.startswith("GEN_"):
    return gen_step[4:]
```

**Issue**: Creates a third namespace (`GEN_*`) that doesn't match the constitution's `step_type_gen` (which must NOT contain underscores). The `GEN_*` format is used internally for materialization maps but violates the naming rule.

**Impact**: 
- Confusion between `GEN_SCF` (internal materialization format) and `scf` (constitutional `step_type_gen`)
- Code must strip/add `GEN_` prefix when converting between formats
- Risk of assigning `GEN_*` values to `step_type_gen` fields

---

### 3.2 `get_materialization_map()` Protocol Requirement

**Location**: `src/quantumvitas/core/driver_protocol.py:147, 200-211`

**Evidence**:
```python
# Line 147: Protocol requires this method
def get_materialization_map(self) -> dict[str, str]:

# Line 200-211: Default implementation
def get_materialization_map(self) -> dict[str, str]:
    """Default: Build materialization map from PREFIX + SUPPORTED_GEN_STEPS.
    
    Drivers should not override this - use PREFIX + SUPPORTED_GEN_STEPS instead.
    """
    # ... builds from PREFIX + SUPPORTED_GEN_STEPS
    return registry._materialization_maps.get(family, {})
```

**Issue**: While the default implementation uses `PREFIX + SUPPORTED_GEN_STEPS`, the protocol still requires drivers to implement this method. This creates a dual-path system:
1. `DriverRegistry._build_materialization_map()` builds from `PREFIX + SUPPORTED_GEN_STEPS`
2. But also calls `driver.get_materialization_map()` as fallback

**Impact**: 
- Drivers could override `get_materialization_map()` with hardcoded mappings, creating "second truth"
- Protocol requirement suggests this is still the primary interface, not `PREFIX + SUPPORTED_GEN_STEPS`

**Evidence of Usage**: Found 81 occurrences of `get_materialization_map()` across codebase, including:
- `generalized_steps.py:270, 308, 346` - Queries driver's method
- `tests/workflow/test_generalized_steps.py:107, 119` - Tests assert on method results
- `tests/drivers/*/test_*_driver.py` - Multiple driver tests check method output

---

### 3.3 `normalize_step_type_to_gen()` Fallback Prefix Stripping

**Location**: `src/quantumvitas/workflow/registry.py:851-882`

**Evidence**:
```python
def normalize_step_type_to_gen(step_type: str) -> str:
    # ... registry lookup first ...
    registry = get_registry()
    spec = registry.get(step_type)
    if spec:
        return spec.step_type_gen

    # Fallback: strip known engine prefixes (e.g., "qe_vc-relax" -> "vc-relax")
    ENGINE_PREFIXES = ("qe_", "pyscf_", "orca_", "vasp_", "lammps_", "cp2k_", "w90_")
    lower = step_type.lower()
    for prefix in ENGINE_PREFIXES:
        if lower.startswith(prefix):
            return step_type[len(prefix):]

    return step_type
```

**Issue**: Violates Constitution §4 which forbids "fallback heuristics like startswith("qe_") to infer engine". This fallback uses exactly that pattern.

**Impact**: 
- Code may work for unregistered step types, masking registration gaps
- Creates implicit mapping logic outside SSOT
- If prefix list drifts from actual engine prefixes, conversion fails silently

**Usage**: Found 197 occurrences of `normalize_step_type_to_gen` usage across codebase.

---

### 3.4 Multiple `ENGINE_PREFIXES` Definitions

**Locations**:
- `src/quantumvitas/calculation/structure_steps.py:242`
- `src/quantumvitas/workflow/registry.py:876`
- `src/quantumvitas/workflow/step_type_convert.py:14`

**Evidence**:
```python
# structure_steps.py:242
ENGINE_PREFIXES = ("qe_", "pyscf_", "orca_", "vasp_", "lammps_", "cp2k_", "w90_")

# registry.py:876
ENGINE_PREFIXES = ("qe_", "pyscf_", "orca_", "vasp_", "lammps_", "cp2k_", "w90_")

# step_type_convert.py:14
ENGINE_PREFIXES: FrozenSet[str] = frozenset({
    "qe", "pyscf", "orca", "vasp", "lammps", "cp2k", "w90"
})
```

**Issue**: 
- Three different definitions
- `step_type_convert.py` uses prefixes WITHOUT underscores (correct per constitution)
- `structure_steps.py` and `registry.py` use prefixes WITH underscores (for stripping)
- If a new engine is added, all three must be updated

**Impact**: Drift risk if one definition is updated but others aren't.

---

### 3.5 Special Case Overrides in Materialization

**Location**: `src/quantumvitas/core/driver_registry.py:209-239`

**Evidence**:
```python
def _apply_special_case_overrides(self, driver: EngineDriver, mat_map: dict[str, str]) -> None:
    """Apply special case overrides for drivers that need them.
    
    This handles cases where GEN_* types don't map 1:1 to spec_from(prefix, gen_step).
    For example: GEN_VC_RELAX -> qe_relax (not qe_vc_relax).
    """
    family = driver.engine_family
    
    # QE special cases
    if family == "qe":
        mat_map["GEN_VC_RELAX"] = "qe_relax"  # Not qe_vc_relax
        mat_map["GEN_BANDS_POST"] = "qe_bands"  # Not qe_bands_post
        mat_map["GEN_WANNIER_CONVERT"] = "qe_pw2wannier"  # Not qe_wannier_convert
        mat_map["GEN_BANDS"] = "qe_bandspw"  # Not qe_bands
        mat_map["GEN_PHONON"] = "qe_ph"  # Not qe_phonon
        mat_map["GEN_VC_MD"] = "qe_vc_md"  # Underscore not hyphen
    # ... more special cases for VASP, CP2K
```

**Issue**: Hardcoded special cases violate the "derived set" rule. Constitution §3 states spec steps should be derived as `union over engines of (prefix + "_" + gen)`, but these overrides break that rule.

**Impact**: 
- Special cases must be maintained in code, not in engine recipe declarations
- If `SUPPORTED_GEN_STEPS` includes `"vc-relax"`, the override changes it to `"relax"` mapping
- Creates implicit knowledge that's not in SSOT

---

### 3.6 `STEP_TYPE_ALIASES` Compatibility Dict

**Location**: `src/quantumvitas/workflow/registry.py:815-820, 823-848`

**Evidence**:
```python
# Line 815-820: Alias definitions
STEP_TYPE_ALIASES = {
    "vc-relax": "relax",
    "qe_vc_relax": "qe_relax",
    "opt": "relax",
    "geomopt": "relax",
}

# Line 823-848: Normalization function
def normalize_step_type(step_type: str) -> str:
    """Normalize step type, applying compatibility aliases."""
    if step_type in STEP_TYPE_ALIASES:
        import warnings
        warnings.warn(
            f"Step type '{step_type}' is deprecated. Use 'relax' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return STEP_TYPE_ALIASES[step_type]
    return step_type
```

**Issue**: Maintains legacy alias namespace, creating drift risk if aliases are used instead of canonical names.

**Impact**: 
- External code may use aliases, creating non-canonical data
- Aliases must be maintained indefinitely for backward compatibility
- Deprecation warnings may be ignored

---

## 4. "Second Truth Map" Inventory

### 4.1 SSOT (Allowed)

#### ✅ GenStepRegistry

**Location**: `src/quantumvitas/workflow/gen_steps.py:11-62`

**Evidence**:
```python
class GenStepRegistry:
    """Central registry of all valid GEN step names."""
    
    GEN_STEPS: FrozenSet[str] = frozenset({
        "scf", "hf", "nscf", "relax", "bands", "bandspw", "dos", ...
    })
```

**Status**: ✅ SSOT for valid GEN step names. Constitution §3 explicitly allows this.

---

#### ✅ Engine Recipe `PREFIX` and `SUPPORTED_GEN_STEPS`

**Locations**: All driver files (e.g., `src/quantumvitas/drivers/qe/driver.py:9-13`)

**Evidence**:
```python
class QEDriver(BaseEngineDriver):
    PREFIX: str = "qe"
    SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({
        "scf", "nscf", "relax", "vc-relax", "bands", "bands_post", ...
    })
```

**Status**: ✅ SSOT per engine. Constitution §3 explicitly allows this.

**Note**: Found inconsistency - `QEDriver.SUPPORTED_GEN_STEPS` includes `"vc-relax"` and `"bands_post"`, but these have special-case overrides in `DriverRegistry._apply_special_case_overrides()`. This suggests the SSOT declarations don't match the actual mappings.

---

### 4.2 Derived (Allowed as Cache)

#### ✅ DriverRegistry Materialization Maps

**Location**: `src/quantumvitas/core/driver_registry.py:71, 131-134`

**Evidence**:
```python
self._materialization_maps: dict[str, dict[str, str]] = {}

# Built from PREFIX + SUPPORTED_GEN_STEPS
mat_map = self._build_materialization_map(driver)
if mat_map:
    self._materialization_maps[family] = mat_map
```

**Status**: ✅ Derived cache. Built from SSOT (`PREFIX + SUPPORTED_GEN_STEPS`), so allowed.

**Issue**: However, the build process applies special-case overrides (see 3.5), so it's not purely derived.

---

#### ✅ StepTypeRegistry `_STEP_TYPES` Dict

**Location**: `src/quantumvitas/workflow/registry.py:164-589`

**Evidence**:
```python
_STEP_TYPES: Dict[str, StepTypeSpec] = {
    "qe_scf": StepTypeSpec(
        step_type_spec="qe_scf",
        step_type_gen="scf",
        engine="qe",
        ...
    ),
    # ... many more
}
```

**Status**: ⚠️ **AMBIGUOUS**. This is a hardcoded dict, not derived from engine recipes. Constitution §3 says spec steps "may be derived as union over engines", but this dict is manually maintained.

**Issue**: If a new engine is added with `SUPPORTED_GEN_STEPS`, this dict must be manually updated. It's not automatically derived.

**Impact**: High drift risk - `StepTypeRegistry` and `DriverRegistry` can get out of sync.

---

### 4.3 Forbidden Second Truth

#### ❌ `get_materialization_map()` Methods

**Locations**: All driver implementations (protocol requirement)

**Evidence**: See 3.2 above.

**Status**: ❌ **FORBIDDEN**. While default implementation derives from SSOT, the protocol requirement creates a dual-path system. Tests assert on method output, suggesting it's treated as truth source.

---

#### ❌ `STEP_TYPE_ALIASES` Dict

**Location**: `src/quantumvitas/workflow/registry.py:815-820`

**Status**: ❌ **FORBIDDEN**. Creates a second mapping for legacy names that should not exist.

---

#### ❌ `ENGINE_PREFIXES` Tuples (for stripping)

**Locations**: `structure_steps.py:242`, `registry.py:876`

**Status**: ❌ **FORBIDDEN**. Used for fallback heuristics (prefix stripping), violating Constitution §4.

---

#### ❌ Special Case Overrides in `_apply_special_case_overrides()`

**Location**: `src/quantumvitas/core/driver_registry.py:209-239`

**Status**: ❌ **FORBIDDEN**. Hardcoded mappings that override the derived `spec_from(prefix, gen)` rule.

---

## 5. Contract/Schema Surface Review

### 5.1 Workflow/Preset Layer (Must Be Gen-Only)

#### ✅ Preset Variants Use Gen Steps

**Location**: `src/quantumvitas/presets/variants_registry.py:49-110`

**Evidence**:
```python
applies_to_step_types=frozenset({"scf"}),  # Gen step, not spec
applies_to_step_types=frozenset({"nscf"}),
applies_to_step_types=frozenset({"bandspw"}),
```

**Status**: ✅ Correctly uses gen steps.

---

#### ✅ `get_variant()` Converts Spec to Gen

**Location**: `src/quantumvitas/presets/variants_registry.py:304-324`

**Evidence**:
```python
def get_variant(dimension: str, step_type: str) -> Optional[ParamSpaceVariant]:
    # ...
    from quantumvitas.workflow.registry import get_registry
    registry = get_registry()
    spec = registry.get(step_type)  # Accepts both gen and spec
    if spec:
        step_type = spec.step_type_gen  # Convert to gen for variant lookup
```

**Status**: ✅ Correctly converts spec to gen before variant lookup.

---

#### ⚠️ Workflow Templates May Use Spec Types

**Location**: `src/quantumvitas/workflow/templates.py:488-498`

**Evidence**:
```python
from quantumvitas.workflow.generalized_steps import materialize_public_step_key

machine_steps = []
for public_step_key in workflow.step_sequence:
    machine_step = materialize_public_step_key(public_step_key, engine_family)
    if machine_step is None:
        unsupported_steps.append(public_step_key)
    else:
        machine_steps.append(machine_step)
```

**Status**: ⚠️ **POTENTIAL LEAK**. Workflow templates use `public_step_key` (gen), which is correct. But `materialize_public_step_key()` may return spec types, and these are stored in `machine_steps`. Need to verify this doesn't leak into workflow definitions.

---

### 5.2 Execution/Persistence Layer (Must Be Spec-Only)

#### ✅ Step YAML Writes Only `step_type_spec`

**Location**: `src/quantumvitas/calculation/structure_steps.py:195`

**Status**: ✅ Correctly writes only `step_type_spec` to step.yaml.

---

#### ✅ Step Factory Uses Spec Types

**Location**: `src/quantumvitas/workflow/step_factory.py:48-73`

**Evidence**:
```python
# Phase 2: Normalize step_type to spec type for step.yaml
spec = registry.get(step_type)  # Accepts both gen and spec types
if spec:
    machine_step_type = spec.step_type_spec  # Use spec type for step.yaml
else:
    machine_step_type = step_type

data: Dict[str, Any] = {
    "step_type_spec": machine_step_type,  # step_type_spec goes to step.yaml
}
```

**Status**: ✅ Correctly converts to spec type before writing to step.yaml.

---

#### ⚠️ Calculation YAML May Store Gen Types

**Location**: `src/quantumvitas/workflow/templates.py:546-547`

**Evidence**:
```python
for public_step, step_ulid in zip(public_steps, step_ulids):
    step_types[step_ulid] = public_step  # Store public type in calculation.yaml
```

**Issue**: Stores `public_step` (gen type) in `calculation.yaml` step_types dict. Constitution says calculation.yaml should use spec types for execution routing.

**Impact**: If calculation.yaml is used for execution routing, it would use gen types instead of spec types.

**Note**: Need to verify if `calculation.yaml` step_types dict is used for execution or only for display.

---

#### ✅ Execution Uses Spec Types

**Location**: `src/quantumvitas/drivers/qe/engine/qe_calculation.py:385, 484, 620, 636`

**Evidence**:
```python
step_type_spec=step_type,  # SPEC type passed to execution
```

**Status**: ✅ Execution layer correctly uses spec types.

---

## 6. Recommendations (NO CODE CHANGES)

### 6.1 Immediate Must-Fix Violations

#### Recommendation 1: Remove `step_type` Fallback from Daemon Server

**What**: Remove v0 compatibility fallback in `src/quantumvitas/daemon/server.py:1459, 4139`

**Why**: Violates Constitution §1 (only `step_type_gen` and `step_type_spec` allowed)

**Validation**: 
- Run `tests/gates/test_no_legacy_identity_fields.py` - should catch any remaining `step_type` keys
- Run `rg '"step_type":' src/quantumvitas/daemon/` - should return zero matches

---

#### Recommendation 2: Remove `step_type` Fallback from Tests

**What**: Update `tests/unit/test_w90_parameter_rendering.py:39, 75` to only read `step_type_spec`

**Why**: Tests should not accept non-canonical keys, as this normalizes drift

**Validation**: 
- Run `rg '\.get\("step_type"' tests/` - should return zero matches (except in tests that explicitly test legacy rejection)

---

### 6.2 High-Priority Legacy Cleanup

#### Recommendation 3: Eliminate `GeneralizedStep` Enum and `GEN_*` Namespace

**What**: 
1. Remove `GeneralizedStep` enum from `generalized_steps.py`
2. Update `materialize_step()` to work with `step_type_gen` format (no `GEN_` prefix)
3. Update `DriverRegistry.materialize_step_type()` to accept gen types directly (not `GEN_*`)

**Why**: Creates confusion between `GEN_SCF` (internal) and `scf` (constitutional). Constitution says `step_type_gen` must NOT contain underscores.

**Validation**:
- Run `rg 'GEN_' src/` - should return zero matches (except in comments/docs)
- Run `rg 'GeneralizedStep' src/` - should return zero matches
- All materialization should work with `step_type_gen` format directly

---

#### Recommendation 4: Remove `get_materialization_map()` Protocol Requirement

**What**:
1. Remove `get_materialization_map()` from `EngineDriver` protocol
2. Update `DriverRegistry._build_materialization_map()` to ONLY use `PREFIX + SUPPORTED_GEN_STEPS`
3. Remove all calls to `driver.get_materialization_map()`

**Why**: Creates dual-path system. SSOT should be `PREFIX + SUPPORTED_GEN_STEPS` only.

**Validation**:
- Run `rg 'get_materialization_map' src/` - should return zero matches
- Run `rg 'get_materialization_map' tests/` - update tests to assert on `PREFIX + SUPPORTED_GEN_STEPS` instead

---

#### Recommendation 5: Remove Fallback Prefix Stripping

**What**: Update `normalize_step_type_to_gen()` to ONLY use registry lookup, remove fallback

**Why**: Violates Constitution §4 (no fallback heuristics)

**Validation**:
- Run `rg 'ENGINE_PREFIXES.*startswith' src/` - should return zero matches
- All normalization should fail if step type not in registry (forces registration)

---

#### Recommendation 6: Consolidate `ENGINE_PREFIXES` Definitions

**What**: 
1. Keep only `step_type_convert.py:ENGINE_PREFIXES` (without underscores)
2. Remove `ENGINE_PREFIXES` from `structure_steps.py` and `registry.py`
3. Update all prefix-stripping code to use `step_type_convert.prefix_from()` instead

**Why**: Eliminates drift risk from multiple definitions

**Validation**:
- Run `rg 'ENGINE_PREFIXES' src/` - should return only `step_type_convert.py`
- All prefix operations should use `step_type_convert` functions

---

#### Recommendation 7: Move Special Cases to Engine Recipe Declarations

**What**: Instead of hardcoded overrides in `_apply_special_case_overrides()`, engines should declare special mappings in their recipe classes

**Why**: Special cases should be in SSOT (engine recipe), not in registry code

**Validation**:
- Run `rg '_apply_special_case_overrides' src/` - should return zero matches
- All mappings should be derivable from `PREFIX + SUPPORTED_GEN_STEPS` or explicit recipe declarations

---

### 6.3 Architectural Improvements

#### Recommendation 8: Make `StepTypeRegistry` Derived, Not Hardcoded

**What**: Generate `_STEP_TYPES` dict automatically from `DriverRegistry` step type specs

**Why**: Eliminates drift between `StepTypeRegistry` and `DriverRegistry`

**Validation**:
- `StepTypeRegistry._types` should be built from `DriverRegistry.get_all_step_types()` at init time
- No manual `_STEP_TYPES` dict maintenance

---

#### Recommendation 9: Add Gate Test for Spec Leakage into Workflow Layer

**What**: Create `tests/gates/test_no_spec_in_workflow_layer.py` that scans:
- Preset variant `applies_to_step_types` - must be gen only
- Workflow template step sequences - must be gen only
- ParamSpace dimension declarations - must be gen only

**Why**: Prevents spec types from leaking into workflow/preset definitions

**Validation**: Gate test should fail if any spec types found in workflow layer

---

#### Recommendation 10: Add Gate Test for Gen Leakage into Execution Layer

**What**: Create `tests/gates/test_no_gen_in_execution_layer.py` that scans:
- Step YAML files - must have `step_type_spec` only
- Execution dispatch code - must use spec types
- Calculation YAML step_types dict - verify if used for execution

**Why**: Prevents gen types from leaking into execution/persistence

**Validation**: Gate test should fail if gen types found in execution layer

---

### 6.4 Migration Plan Summary

**Phase 1: Remove Violations** (Recommendations 1-2)
- Remove `step_type` fallbacks from daemon and tests
- **Estimated effort**: 2-4 hours
- **Risk**: Low (breaking v0 compatibility, but constitution requires it)

**Phase 2: Eliminate Legacy Namespaces** (Recommendations 3-4)
- Remove `GeneralizedStep` enum and `GEN_*` format
- Remove `get_materialization_map()` protocol requirement
- **Estimated effort**: 1-2 days
- **Risk**: Medium (touches many files, requires test updates)

**Phase 3: Remove Fallbacks and Consolidate** (Recommendations 5-7)
- Remove prefix-stripping fallbacks
- Consolidate `ENGINE_PREFIXES` definitions
- Move special cases to engine recipes
- **Estimated effort**: 2-3 days
- **Risk**: Medium-High (may break unregistered step types, requires engine recipe updates)

**Phase 4: Architectural Improvements** (Recommendations 8-10)
- Make `StepTypeRegistry` derived
- Add gate tests
- **Estimated effort**: 1-2 days
- **Risk**: Low (additive changes)

**Total Estimated Effort**: 5-8 days

---

## Appendix: Evidence Summary

### File Counts

- Files with `step_type[^_]` pattern: 865+ matches
- Files with `StepType|GeneralizedStep|GEN_` pattern: 352+ matches
- Files with `get_materialization_map`: 81 matches
- Files with `normalize_step_type`: 197 matches
- Files with `ENGINE_PREFIXES`: 146 matches

### Key Violation Files

1. `src/quantumvitas/workflow/generalized_steps.py` - Legacy entry point
2. `src/quantumvitas/workflow/registry.py` - Fallback prefix stripping
3. `src/quantumvitas/core/driver_registry.py` - Special case overrides
4. `src/quantumvitas/daemon/server.py` - `step_type` fallback
5. `tests/unit/test_w90_parameter_rendering.py` - `step_type` fallback

### Compliance Status by Category

| Category | Status | Notes |
|----------|--------|-------|
| Step YAML serialization | ✅ Compliant | Only `step_type_spec` written |
| Step YAML deserialization | ✅ Compliant | Hard error on legacy `step_type` |
| API/DTO serialization | ⚠️ Partial | Daemon accepts `step_type` fallback |
| Workflow layer | ✅ Compliant | Uses gen types |
| Execution layer | ✅ Compliant | Uses spec types |
| SSOT registries | ✅ Compliant | GenStepRegistry and engine recipes exist |
| Legacy namespaces | ❌ Non-compliant | `GeneralizedStep` enum, `GEN_*` format |
| Fallback heuristics | ❌ Non-compliant | Prefix stripping in `normalize_step_type_to_gen()` |
| Second truth maps | ❌ Non-compliant | `get_materialization_map()`, special case overrides |

---

**End of Report**

