# Dimension / Variant / Key Ownership / Oracle Specification

**Version**: 1.0  
**Date**: 2025-01-17  
**Status**: Final Developer-Facing Spec  
**Purpose**: Define the precise semantics of dimension, variant, key ownership, compile order, and oracle to lock reversibility invariants and prevent future drift.

---

## 1. Terms and Definitions

### 1.1 Dimension

**Definition**: A string identifier representing a physical concept or parameter group that presets target.

**Format**: Lowercase string (e.g., `"magnetism"`, `"precision"`, `"occupations_scheme"`, `"qc_precision"`).

**Location**: Dimension names are defined in:
- `src/qmatsuite/presets/dimensions.py` (dimension constants)
- `src/qmatsuite/presets/variants_registry.py:ParamSpaceVariant.dimension` (variant binding)

**SSOT**: Dimension names MUST match between:
- `ParamSpaceVariant.dimension`
- `Engine.supported_presets` list entries
- `ENUM_TO_PROFILE` / `PROFILE_TO_ENUM` keys

**Evidence**:
- Dimension constants: `src/qmatsuite/presets/dimensions.py:DIMENSION_*` (lines 21-24)
- Variant binding: `src/qmatsuite/presets/variants_registry.py:OCCUPATIONS_SCHEME_VARIANT` (line 45)

### 1.2 Variant

**Definition**: A `ParamSpaceVariant` instance that binds a `ParamSpace` to specific gen/public step types.

**NOT** profiles (HIGH/MED/LOW). Variants determine *where* a dimension applies; profiles determine *what values* to apply.

**Data Structure**:
```python
@dataclass(frozen=True)
class ParamSpaceVariant:
    name: str                           # e.g., "PRECISION_PW_DEFAULT"
    dimension: str                      # e.g., "precision"
    space: ParamSpace                   # The ParamSpace definition
    applies_to_step_types: frozenset[str]  # Gen step types, e.g., {"scf", "relax"}
```

**Location**: `src/qmatsuite/presets/space_variant.py` (lines 16-51)

**Mutual Exclusivity**: For a given `(gen_step, dimension)` pair, at most ONE variant may apply. This is enforced at import time by `_build_indexes()`.

**Evidence**:
- Variant definition: `src/qmatsuite/presets/space_variant.py:ParamSpaceVariant` (lines 16-51)
- Overlap enforcement: `src/qmatsuite/presets/variants_registry.py:_build_indexes()` (lines 129-166)
- Error on overlap: Lines 152-158 raise `ValueError` if overlap detected

### 1.3 Profile

**Definition**: A named set of cells within a `ParamSpace`, representing one preset option (e.g., `"LOW"`, `"MED"`, `"HIGH"` for precision).

**Data Structure**: `ParamSpace.profiles: dict[str, dict[ParamKey, Cell]]`

**Cell Types**:
- `Cell.VALUE(v)`: Key must have this value
- `Cell.NOT_APPLICABLE()`: Key must be ABSENT
- `Cell.WILDCARD()`: Key is ignored during matching

**Evidence**:
- Profile storage: `src/qmatsuite/presets/paramspace.py:ParamSpace.profiles` (line 306)
- Cell types: `src/qmatsuite/presets/paramspace.py:Cell` (lines 33-56)

### 1.4 ParamKey

**Definition**: Definition of a parameter key within a `ParamSpace`, specifying:
- `section`: YAML section name (e.g., `"SYSTEM"`, `"ELECTRONS"`)
- `key`: Parameter name (e.g., `"ecutwfc"`, `"conv_thr"`)
- `parser`: Function to parse raw YAML value
- `canonicalizer`: Function to normalize value for comparison
- `tolerance`: Numeric tolerance for matching (optional)
- `aliases`: Synonym mappings (optional)
- `default`: Default value if key absent (optional)

**Evidence**:
- ParamKey: `src/qmatsuite/presets/paramspace.py:ParamKey` (lines 59-121)

### 1.5 Owned Key

**Definition**: A key `(section, key)` tuple that belongs to exactly one ParamSpace.

**Ownership MUST be unique**: No two ParamSpaces may claim the same key.

**Enforcement**:
- Registration: `register_paramspace()` raises `RuntimeError` on duplicate
- Access control: `check_key_access()` raises `KeyAccessError` on unauthorized access
- Context: `ParamSpaceContext` sets the current ParamSpace during operations

**Evidence**:
- Ownership registry: `src/qmatsuite/presets/paramspace.py:_KEY_OWNERSHIP` (line 164)
- Registration: `src/qmatsuite/presets/paramspace.py:register_paramspace()` (lines 168-205)
- Access check: `src/qmatsuite/presets/paramspace.py:check_key_access()` (lines 207-254)

### 1.6 Oracle

**Definition**: Read-only helper that provides semantic prerequisite queries based on current YAML state.

**Contract**:
- MUST be read-only
- MUST only return small discrete values (bool, small enum)
- MUST NOT return preset IDs or parameter values
- MUST only read IR YAML truth (current in-memory state)
- MUST NOT access preset intention or detect results

**Usage**: Oracle allows dependent dimensions (e.g., precision) to check prerequisites (e.g., occupations) without violating key ownership.

**Current Methods**:
- `degauss_applicability() -> bool`: Returns `True` if `occupations == "smearing"`

**Evidence**:
- Oracle class: `src/qmatsuite/presets/oracle.py:Oracle` (lines 18-60)
- Usage in precision: `src/qmatsuite/presets/paramspace.py:precision_apply_invariants()` (lines 962-979)

### 1.7 Gen/Public Step Type vs Spec/Machine Step Type

**Gen/Public Step Type**:
- Format: Generalized string (e.g., `"scf"`, `"nscf"`, `"bands"`)
- Used by: Presets, ParamSpace `applies_to_step_types`, UI display
- Storage: NOT persisted; derived from `spec/machine` type

**Spec/Machine Step Type**:
- Format: Engine-prefixed string (e.g., `"qe_scf"`, `"pyscf_scf"`)
- Used by: `step.yaml` storage, runner execution, materialization
- Storage: Persisted in `step.yaml:step_type`

**Mapping**: `StepTypeRegistry` provides bidirectional mapping.

**Evidence**:
- Registry: `src/qmatsuite/workflow/registry.py:StepTypeRegistry`
- Mapping: `src/qmatsuite/workflow/registry.py:normalize_step_type_to_public()`
- Variant lookup: `src/qmatsuite/presets/variants_registry.py:get_variant()` (lines 304-327)

---

## 2. Invariants (MUST / MUST NOT / SHOULD)

### 2.1 Exact-Match Reversibility Rule

**MUST**: Preset detection uses full-pattern matching. A profile is detected ONLY if ALL owned keys match exactly (after canonicalization).

**MUST**: Any deviation from profile values → CUSTOM. No partial matching.

**MUST**: Apply→Detect roundtrip MUST be idempotent: if preset P is applied and then detected, detection MUST return P (or equivalent profile).

**Evidence**:
- Match logic: `src/qmatsuite/presets/paramspace.py:match_profile()` (lines 461-534)
- Roundtrip tests: `tests/unit/test_paramspace_contract.py`

### 2.2 Key Ownership + Enforcement Rule

**MUST**: Each key `(section, key)` belongs to exactly ONE ParamSpace.

**MUST**: Registration of duplicate ownership raises `RuntimeError` immediately.

**MUST**: Unauthorized key access raises `KeyAccessError`.

**MUST NOT**: ParamSpace A read/write keys owned by ParamSpace B except via Oracle.

**Evidence**:
- Ownership check: `src/qmatsuite/presets/paramspace.py:check_key_access()` (lines 207-254)
- Tests: `tests/unit/test_key_access_enforcement.py`

### 2.3 Compile Order / Oracle Contract

**MUST**: Dimensions are compiled in two phases:
- **Phase 1 (Prerequisite)**: `occupations_scheme`, `magnetism`
- **Phase 2 (Dependent)**: `precision`, `convergence`

**MUST**: Phase 1 patches are applied to YAML before Phase 2 compilation, so Oracle reads latest state.

**MUST**: Oracle is created with updated YAML state, not stale state.

**MUST NOT**: Oracle make decisions about presets or values; it only answers "is X applicable?".

**Evidence**:
- Phase ordering: `src/qmatsuite/presets/integration.py:apply_presets_to_step()` (lines 517-591)
- Oracle creation: `src/qmatsuite/presets/integration.py` (line 722)
- Tests: `tests/unit/test_paramspace_invariants.py`

### 2.4 Step Applicability Declaration Contract

**MUST**: Step applicability is declared inside `ParamSpaceVariant.applies_to_step_types` using gen/public step types.

**MUST NOT**: Use spec/machine types in `applies_to_step_types`.

**MUST**: `get_variant()` maps machine_type → public_type before lookup.

**MUST**: Variant registry builds index at import time; overlap causes immediate failure.

**Evidence**:
- Variant declaration: `src/qmatsuite/presets/variants_registry.py:VARIANTS` (lines 114-122)
- Machine→public mapping: `src/qmatsuite/presets/variants_registry.py:get_variant()` (lines 304-327)

### 2.5 Capability Contract (Engine.supported_presets)

**MUST**: `Engine.supported_presets` is SSOT for what presets an engine declares.

**MUST**: Capability resolver is the SINGLE enforcement point:
- `list_presets_for_engine()`: Returns intersection of engine support and ParamSpace applicability
- `validate_preset_capability()`: Returns bool
- `require_preset_capability()`: Raises `CapabilityError` if not available

**MUST NOT**: Any code bypass the capability resolver by directly checking `supported_presets` or `applies_to_step_types`.

**Evidence**:
- Capability resolver: `src/qmatsuite/presets/capability.py`
- Guard tests: `tests/unit/test_no_capability_bypass.py`

### 2.6 No Bypass Rules

**MUST NOT**: Reintroduce old gating logic (`StepTypeSpec.accepts_presets`, etc.).

**MUST NOT**: Use `StepType` Enum for core logic decisions.

**MUST**: Guard tests exist to prevent regression.

**Evidence**:
- Guard tests:
  - `tests/unit/test_no_deprecated_preset_fields.py`
  - `tests/unit/test_no_capability_bypass.py`
  - `tests/unit/test_no_steptype_enum.py`

---

## 3. How to Add a New Dimension / Profile

### 3.1 Checklist for Adding a New Dimension

1. **Define dimension constant** in `src/qmatsuite/presets/dimensions.py`:
   ```python
   DIMENSION_NEW = "new_dimension"
   ```

2. **Define Option enum** in `dimensions.py`:
   ```python
   class NewDimensionOption(str, Enum):
       LOW = "low"
       HIGH = "high"
   ```

3. **Build ParamSpace** in a new file or `paramspace.py`:
   - Define `ParamKey` instances for each owned key
   - Define profiles with cells for each key
   - Call `ParamSpace(name="new_dimension", keys=[...], profiles={...})`
   - ParamSpace registration happens automatically in `__post_init__` for canonical spaces

4. **Create Variant(s)** in `variants_registry.py`:
   ```python
   NEW_DIMENSION_VARIANT = ParamSpaceVariant(
       name="NEW_DIMENSION_VARIANT",
       dimension="new_dimension",
       space=get_new_dimension_paramspace(),
       applies_to_step_types=frozenset({"scf", "nscf"}),
   )
   ```

5. **Add to VARIANTS tuple** in `variants_registry.py`:
   ```python
   VARIANTS: tuple[ParamSpaceVariant, ...] = (
       # ... existing variants
       NEW_DIMENSION_VARIANT,
   )
   ```

6. **Add profile↔enum mappings** in `variants_registry.py`:
   ```python
   NEW_DIMENSION_PROFILE_TO_ENUM = {"LOW": NewDimensionOption.LOW, ...}
   NEW_DIMENSION_ENUM_TO_PROFILE = {NewDimensionOption.LOW: "LOW", ...}
   PROFILE_TO_ENUM["new_dimension"] = NEW_DIMENSION_PROFILE_TO_ENUM
   ENUM_TO_PROFILE["new_dimension"] = NEW_DIMENSION_ENUM_TO_PROFILE
   ```

7. **Add to Engine.supported_presets** for applicable engines

8. **Add tests**:
   - Roundtrip test: apply→detect returns same profile
   - Ownership test: verify no key conflicts with other ParamSpaces
   - Custom detection test: modified value → CUSTOM

### 3.2 Common Mistakes to Avoid

- **Duplicate key ownership**: Two ParamSpaces claiming the same key → immediate failure
- **Using machine_type in applies_to_step_types**: Use gen/public step types only
- **Forgetting ENUM_TO_PROFILE mapping**: Detection will always return CUSTOM
- **Not adding to VARIANTS tuple**: Dimension will never apply
- **Not updating Engine.supported_presets**: Dimension won't show in UI

---

## 4. Evidence Pointers

### Core ParamSpace

| Contract Point | File | Symbol/Line |
|----------------|------|-------------|
| ParamSpace definition | `src/qmatsuite/presets/paramspace.py` | `ParamSpace` (line 281-372) |
| ParamKey definition | `src/qmatsuite/presets/paramspace.py` | `ParamKey` (lines 59-121) |
| Key ownership registry | `src/qmatsuite/presets/paramspace.py` | `_KEY_OWNERSHIP` (line 164) |
| Key registration | `src/qmatsuite/presets/paramspace.py` | `register_paramspace()` (lines 168-205) |
| Key access enforcement | `src/qmatsuite/presets/paramspace.py` | `check_key_access()` (lines 207-254) |
| Match logic | `src/qmatsuite/presets/paramspace.py` | `match_profile()` (lines 461-534) |
| Compile logic | `src/qmatsuite/presets/paramspace.py` | `compile_profile_patch()` (lines 541-609) |

### Variants Registry

| Contract Point | File | Symbol/Line |
|----------------|------|-------------|
| Variant definition | `src/qmatsuite/presets/space_variant.py` | `ParamSpaceVariant` (lines 16-51) |
| All variants | `src/qmatsuite/presets/variants_registry.py` | `VARIANTS` (lines 114-122) |
| Index building | `src/qmatsuite/presets/variants_registry.py` | `_build_indexes()` (lines 129-166) |
| Overlap detection | `src/qmatsuite/presets/variants_registry.py` | Lines 152-158 |
| Variant lookup | `src/qmatsuite/presets/variants_registry.py` | `get_variant()` (lines 304-327) |

### Oracle and Compile Order

| Contract Point | File | Symbol/Line |
|----------------|------|-------------|
| Oracle class | `src/qmatsuite/presets/oracle.py` | `Oracle` (lines 18-60) |
| degauss_applicability | `src/qmatsuite/presets/oracle.py` | Line 36-58 |
| Two-phase compilation | `src/qmatsuite/presets/integration.py` | `apply_presets_to_step()` (lines 517-591) |
| Invariant enforcement | `src/qmatsuite/presets/integration.py` | Lines 727-729 |

### Capability Resolver

| Contract Point | File | Symbol/Line |
|----------------|------|-------------|
| Capability resolver | `src/qmatsuite/presets/capability.py` | All functions |
| list_presets_for_engine | `src/qmatsuite/presets/capability.py` | Lines 39-77 |
| require_preset_capability | `src/qmatsuite/presets/capability.py` | Lines 139-159 |

### Existing Tests

| Test Purpose | File |
|--------------|------|
| Key access enforcement | `tests/unit/test_key_access_enforcement.py` |
| Roundtrip (occupations/precision) | `tests/unit/test_paramspace_contract.py` |
| Roundtrip (magnetism) | `tests/unit/test_magnetism_paramspace_contract.py` |
| Invariant enforcement | `tests/unit/test_paramspace_invariants.py` |
| Precision roundtrip (integration) | `tests/integration/test_precision_roundtrip.py` |
| Capability contract | `tests/unit/test_preset_capability_contract.py` |
| Guard: no deprecated fields | `tests/unit/test_no_deprecated_preset_fields.py` |
| Guard: no capability bypass | `tests/unit/test_no_capability_bypass.py` |
| Guard: no StepType enum | `tests/unit/test_no_steptype_enum.py` |
| **Constitution-grade roundtrip invariants** | `tests/unit/test_paramspace_roundtrip_invariants.py` |
| **Constitution-grade negative invariants** | `tests/unit/test_paramspace_negative_invariants.py` |
| **Key ownership uniqueness** | `tests/unit/test_key_ownership_uniqueness.py` |
| **Capability resolver invariants** | `tests/unit/test_capability_resolver_invariants.py` |

---

## 5. Summary

The ParamSpace framework enforces:

1. **Key Ownership**: Each key has exactly one owner; violations are immediate errors
2. **Exact-Match Detection**: Any deviation → CUSTOM; no partial matching
3. **Two-Phase Compilation**: Prerequisite dimensions before dependent ones
4. **Oracle for Cross-Dimension Queries**: Read-only semantic queries without violating ownership
5. **Capability Resolver SSOT**: Single enforcement point for preset availability
6. **Guard Tests**: Prevent regression of deprecated patterns

These contracts together guarantee **reversibility** (apply→detect returns same preset) and **SSOT preservation** (only `step.yaml` is truth; presets are runtime-only).

---

**End of Specification**

