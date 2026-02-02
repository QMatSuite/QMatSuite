# GEN/SPEC Constitution Code Review

**Date**: 2026-02-01
**Reviewer**: Claude Code
**Constitution Version**: 1.0
**Scope**: Full codebase review against `docs/spec/step_type_gen_spec_constitution.md`

---

## Executive Summary

The codebase has made significant progress toward constitution compliance. The core infrastructure (GenStepRegistry, DriverRegistry, step_type_convert.py) is well-designed and follows the constitution. However, **scattered manual join/split operations** throughout execution layer code create inconsistency and violate the "No Manual Join/Split" rule (§3.1).

**Critical Finding**: There are **12+ manual `.split("_", 1)` calls** in src/ that should use canonical `gen_from()` / `prefix_from()` functions.

---

## 1. SSOT Infrastructure Assessment

### 1.1 GenStepRegistry (§12.1) - **PASS**

**File**: `src/quantumvitas/workflow/gen_steps.py`

- Properly defines `GEN_STEPS` as a frozenset
- Contains all required gen steps: scf, hf, nscf, relax, bands, bandspw, dos, projwfc, pp, wannierprep, pw2wannier, wannier, ph, q2r, matdyn, dynmat, md, minimize, mp2, td, custom
- No underscores in any gen step name
- Provides `is_valid()`, `validate()`, `get_all()` methods

### 1.2 Engine Recipe Declarations (§12.2) - **PASS**

All drivers properly declare PREFIX and SUPPORTED_GEN_STEPS:

| Engine | PREFIX | SUPPORTED_GEN_STEPS Location |
|--------|--------|------------------------------|
| qe | `"qe"` | `src/quantumvitas/drivers/qe/driver.py:9-13` |
| vasp | `"vasp"` | `src/quantumvitas/drivers/vasp/driver.py:22-25` |
| w90 | `"w90"` | `src/quantumvitas/drivers/w90/driver.py:31-34` |
| orca | `"orca"` | `src/quantumvitas/drivers/orca/driver.py:20-23` |
| pyscf | `"pyscf"` | `src/quantumvitas/drivers/pyscf/driver.py:22-25` |
| lammps | `"lammps"` | `src/quantumvitas/drivers/lammps/driver.py:28-32` |
| cp2k | `"cp2k"` | `src/quantumvitas/drivers/cp2k/driver.py:24-27` |

No underscores in any PREFIX value.

### 1.3 Conversion Functions (§3) - **PASS**

**File**: `src/quantumvitas/workflow/step_type_convert.py`

Canonical functions properly implemented:
- `spec_from(prefix, gen)` - join operation
- `gen_from(spec)` - split to get gen
- `prefix_from(spec)` - split to get prefix
- `is_spec(s)`, `is_gen(s)` - predicates

### 1.4 DriverRegistry Materialization (§12.3) - **PASS**

**File**: `src/quantumvitas/core/driver_registry.py:181-204`

`_build_materialization_map()` uses pure derivation:
```python
spec_type = spec_from(prefix, gen_step)  # Pure derivation
mat_map[gen_step] = spec_type
```

No hardcoded override tables.

---

## 2. Violations Found

### 2.1 Manual Join/Split Violations (§3.1) - **CRITICAL**

**Constitution Quote**: "The entire repository is ONLY allowed to perform step type conversions via the canonical functions... FORBIDDEN everywhere else: `spec.split("_", 1)` or any manual underscore parsing"

**Violations in src/ (12 instances)**:

| File:Line | Code | Should Use |
|-----------|------|------------|
| `calculation/verification.py:102` | `step_type_gen = step_type_str.split("_", 1)[1]` | `gen_from()` |
| `calculation/runner.py:80` | `parts = step_type_spec.split("_", 1)` | `gen_from()`, `prefix_from()` |
| `engines/pyscf/chain.py:27` | `engine_prefix = step_type_spec.split("_", 1)[0]` | `prefix_from()` |
| `daemon/compat.py:737` | `step.get("step_type_spec", "").split("_", 1)[-1]` | `gen_from()` |
| `api/_mapping/dto_mapping.py:383` | `engine = step_type_spec.split("_")[0]` | `prefix_from()` |
| `api/service.py:6966` | `engine_family = machine_step_type.split("_", 1)[0]` | `prefix_from()` |
| `execution/reference_resolver.py:63` | `parts = step_type_str.split("_", 1)` | `gen_from()`, `prefix_from()` |
| `execution/vasp_staging.py:58` | `parts = step_type_str.split("_", 1)` | `gen_from()`, `prefix_from()` |
| `drivers/vasp/staging.py:58` | `parts = step_type_str.split("_", 1)` | `gen_from()`, `prefix_from()` |

**Note**: `step_type_convert.py:54,73` are ALLOWED (canonical implementation).

### 2.2 Bare `step_type` Fields (§11) - **MINOR**

**Constitution Quote**: "The repository MUST NOT have any DTO/dataclass fields or function parameters named `step_type` (bare)."

**Potential Violations**:

| File:Line | Issue |
|-----------|-------|
| `engine/vasp_engine.py:243` | `step_type = step.step_type_spec` (local variable, acceptable) |
| `engine/qe_engine.py:49-50` | `step_type = getattr(step, "step_type_spec", None)` (local variable, acceptable) |
| `engine/pyscf_engine.py:363,369,372` | `target_step_type` (local variable, acceptable) |

**Verdict**: These are local variables, not field/parameter names. **No critical violations** of §11.

### 2.3 Legacy Aliases (§7) - **MINOR**

**Files with outdated comments** (not code violations):

| File:Line | Issue |
|-----------|-------|
| `tools/generate_wannier90_demo.py:9` | Comment says "w90_preproc step" |
| `tools/generate_wannier90_demo.py:11` | Comment says "w90_run step" |
| `tools/generate_wannier90_demo.py:190` | Comment says "w90_preproc and w90_run" |

**Verdict**: Comments only; actual code uses correct names (`w90_wannierprep`, `w90_wannier`). Should be updated for clarity.

### 2.4 Third Namespaces (§13 Gate: Forbid Third Namespaces) - **PASS**

No `GEN_SCF`, `GEN_NSCF`, `GeneralizedStep` enums found in src/.

Legacy audit documents contain historical references but these are documentation, not runtime code.

### 2.5 Non-Derived Mapping Tables (§12.3) - **MINOR**

**File**: `tools/generate_wannier90_demo.py:186-191`

```python
gen_to_spec = {
    "scf": "qe_scf",
    "nscf": "qe_nscf",
    "pw2wannier90": "qe_pw2wannier90",
}
```

**Issue**: Hardcoded mapping table in tool script.
**Verdict**: Tool script, not runtime code. Low priority but should use DriverRegistry.

### 2.6 Execution Choke Point (§4.3) - **PARTIAL COMPLIANCE**

**Constitution Quote**: "Runner/dispatch performs exactly ONE spec→(prefix, gen) 'unpack' at a SINGLE choke point"

**Current State**: Multiple files perform spec→gen conversion:
- `calculation/runner.py:80`
- `execution/reference_resolver.py:63`
- `execution/vasp_staging.py:58`
- `drivers/vasp/staging.py:58`

**Verdict**: Conversion is not centralized at a single choke point. These should all flow through a single dispatcher.

### 2.7 Engine Recipe GEN-Keyed Maps (§4.2) - **PASS**

**File**: `drivers/qe/engine/qe_engine.py:30-47`

`EXECUTABLE_MAP` is correctly keyed by GEN:
```python
EXECUTABLE_MAP = {
    "scf": "pw.x",
    "nscf": "pw.x",
    "relax": "pw.x",
    ...
}
```

---

## 3. Gate Test Coverage

### Existing Gates (Good Coverage)

| Gate | File | Status |
|------|------|--------|
| No bare step_type | `test_no_bare_step_type.py` | EXISTS |
| Underscore ban | `test_underscore_ban.py` | EXISTS |
| Declared-only (C1) | `test_step_type_declared_sets.py` | EXISTS |
| Cross-assignment (C2) | `test_step_type_cross_assignment.py` | EXISTS |
| No third namespace | `test_no_third_namespace.py` | EXISTS |
| Constitution compliance | `test_step_type_constitution.py` | EXISTS |
| Parameter mismatch (C3) | `test_step_type_param_mismatch.py` | EXISTS |
| Banned aliases | `test_banned_legacy_aliases.py` | EXISTS |
| No non-derived mappings | `test_no_nonderived_mappings.py` | EXISTS |
| Supported subset | `test_supported_subset.py` | EXISTS |

### Missing Gate

| Gate | Constitution Section | Status |
|------|---------------------|--------|
| No Manual Join/Split | §3.1, §13 | **MISSING** |

---

## 4. Compliance Summary

| Category | Constitution Section | Status | Severity |
|----------|---------------------|--------|----------|
| GenStepRegistry SSOT | §12.1 | PASS | - |
| Engine Recipe Declarations | §12.2 | PASS | - |
| Conversion Functions | §3 | PASS | - |
| DriverRegistry Pure Derivation | §12.3 | PASS | - |
| No Manual Join/Split | §3.1 | **FAIL** | HIGH |
| No Bare step_type | §11 | PASS | - |
| No Legacy Aliases | §7 | PASS | - |
| No Third Namespaces | §13 | PASS | - |
| Single Execution Choke Point | §4.3 | PARTIAL | MEDIUM |
| GEN-Keyed Engine Maps | §4.2 | PASS | - |
| Gate Coverage | §13 | PARTIAL | MEDIUM |

---

## 5. Risk Assessment

### High Risk
- **Manual split operations**: 12+ locations bypass canonical functions, creating drift risk

### Medium Risk
- **No centralized execution choke point**: Spec→gen conversions spread across multiple files
- **Missing gate for manual join/split**: Violations can reappear

### Low Risk
- **Outdated comments in tools/**: Documentation drift, no runtime impact
- **Hardcoded map in tool script**: Not in runtime path

---

## 6. Recommendations

### Immediate (P0)
1. Replace all `.split("_", 1)` calls with `gen_from()` / `prefix_from()`
2. Add gate test for manual join/split detection

### Short-term (P1)
1. Centralize spec→gen conversion to single choke point in execution layer
2. Update outdated comments in tools/

### Long-term (P2)
1. Refactor tools to use DriverRegistry instead of hardcoded maps
2. Document execution choke point pattern for future contributors

---

**End of Review**
