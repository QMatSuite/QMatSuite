# DOC 1 — Review Report (Constitution Compliance Audit)

**Generated**: 2026-01-31
**Constitution Reference**: `docs/spec/step_type_gen_spec_constitution.md` v1.0 (IMMUTABLE LAW)
**Scope**: Full repository audit of `src/qmatsuite/**/*.py`

---

## NON-NEGOTIABLE LAWS (From Constitution)

These are immutable. Any violation is blocking.

1. **Only two step type namespaces exist**: `step_type_gen` and `step_type_spec`. Any third namespace (`GEN_*`, `GeneralizedStep`, `public_type`/`machine_type`, etc.) is **ILLEGAL**.

2. **`step_type_spec` is purely derived**: `f"{engine_prefix}_{step_type_gen}"`. No overrides, no mapping tables, no special cases.

3. **Underscore disambiguation**: `step_type_gen` and `engine_prefix` must contain NO underscores. If a string contains `_`, it's SPEC; otherwise GEN.

4. **Repo-wide ban on bare `step_type`**: No function parameters, dataclass fields, TypedDict keys, dict keys, or DTO keys named `step_type`. Must be explicitly `step_type_gen` or `step_type_spec`.

---

## Layering Rule (Prevents Preset/Kpoints Regressions)

| Layer | Uses | Examples |
|-------|------|----------|
| **UI / Preset / ParamSpace / Workflow Templates** | `step_type_gen` ONLY | `"scf"`, `"bandpw"`, `"wannierprep"`, `"md"` |
| **step.yaml / Runner / Dispatch / Execution** | `step_type_spec` ONLY | `"qe_scf"`, `"qe_bandpw"`, `"w90_wannierprep"`, `"qe_md"` |

**Conversions only at boundaries**, using pure derivation:
- GEN → SPEC: `spec_from(prefix, gen)` = `f"{prefix}_{gen}"`
- SPEC → GEN: `gen_from(spec)` = split on first underscore

**⚠️ WARNING**: If you convert workflow/preset/paramspace code to SPEC strings, you WILL break precision/kpoints/preset detection. The preset layer reasons in GEN only.

---

## Locked GEN/SPEC Semantics

### Relaxation Workflow

| GEN | SPEC | Description |
|-----|------|-------------|
| `relax` | `qe_relax`, `vasp_relax`, etc. | Structural optimization. VC vs non-VC is a **parameter** (e.g., `calculation='vc-relax'` in QE, `ISIF=3` in VASP), NOT a separate GEN step. |

### Molecular Dynamics Workflow

| GEN | SPEC | Description |
|-----|------|-------------|
| `md` | `qe_md`, `vasp_md`, `lammps_md`, etc. | Molecular dynamics. VC vs non-VC is a **parameter** (e.g., `calculation='vc-md'` in QE), NOT a separate GEN step. |

**There is NO `vcmd`, `vc_md`, `vc-md`, or `GEN_VC_MD`**. Use `step_type_gen="md"` and store VC-ness in step parameters.

### Bands Workflow

| GEN | SPEC | Description | Engine Support |
|-----|------|-------------|----------------|
| `bandpw` | `qe_bandpw`, `vasp_bandpw` | Eigenvalue computation on k-path | QE, VASP |
| `bands` | `qe_bands` | Post-processing/parse (bands.x) | QE only (0-mapping for VASP) |

### Wannier Workflow

| Order | GEN | SPEC | Executable |
|-------|-----|------|------------|
| 1 | `wannierprep` | `w90_wannierprep` | wannier90.x -pp |
| 2 | `pw2wannier` | `qe_pw2wannier` | pw2wannier90.x |
| 3 | `wannier` | `w90_wannier` | wannier90.x |

**Banned values**: `w90_preproc`, `w90_run` are FORBIDDEN as step type values.
**Note**: `pw2wannier90` may appear only as an executable name, never as a step type.

---

## Section 1: Violation Inventory (Concrete Counts)

### 1.1 Bare `step_type` Violations (§9)

**Command**:
```bash
rg "step_type[^_]" src/ --type py -c | awk -F: '{sum += $2} END {print sum}'
```

**Result**: **1146 occurrences**

**Breakdown**:
- Function parameters (`def .*step_type[^_].*:`): **72**
- Dataclass/typed fields (`step_type:\s*str`): **114**

**Top violating files** (by occurrence count):

| File | Count |
|------|-------|
| `src/qmatsuite/api/service.py` | 84 |
| `src/qmatsuite/_vault/_legacy_service.py` | 83 |
| `src/qmatsuite/_vault/_legacy_facade.py` | 71 |
| `src/qmatsuite/workflow/registry.py` | 48 |
| `src/qmatsuite/presets/integration.py` | 46 |
| `src/qmatsuite/presets/receivers.py` | 37 |
| `src/qmatsuite/calculation/calculation.py` | 35 |
| `src/qmatsuite/presets/variants_registry.py` | 34 |
| `src/qmatsuite/drivers/qe/engine/qe_calculation.py` | 33 |
| `src/qmatsuite/presets/detector.py` | 29 |

### 1.2 Third Namespace Violations (§10.3)

**Command**:
```bash
rg "GEN_[A-Z]" src/ --type py -l
```

**Result**: **13 files**

| File | Violation Type |
|------|---------------|
| `src/qmatsuite/workflow/generalized_steps.py` | `GeneralizedStep` enum + `GEN_*` usage |
| `src/qmatsuite/core/driver_registry.py` | `GEN_*` keys in materialization map |
| `src/qmatsuite/core/driver_protocol.py` | `GEN_*` in protocol |
| `src/qmatsuite/workflow/registry.py` | Some `GEN_*` references |
| `src/qmatsuite/workflow/gen_steps.py` | Comments only (may be compliant) |
| `src/qmatsuite/analysis/kpath.py` | `GEN_*` usage |
| `src/qmatsuite/drivers/qe/driver.py` | `GEN_*` in materialization |
| `src/qmatsuite/drivers/vasp/driver.py` | `GEN_*` in materialization |
| `src/qmatsuite/drivers/pyscf/driver.py` | `GEN_*` in materialization |
| `src/qmatsuite/drivers/orca/driver.py` | `GEN_*` in materialization |
| `src/qmatsuite/drivers/cp2k/driver.py` | `GEN_*` in materialization |
| `src/qmatsuite/drivers/lammps/driver.py` | `GEN_*` in materialization |
| `src/qmatsuite/drivers/w90/driver.py` | `GEN_*` in materialization |

**GeneralizedStep**:
```bash
rg "GeneralizedStep" src/ --type py -l
```
**Result**: **1 file** (`src/qmatsuite/workflow/generalized_steps.py`)

### 1.3 Non-Derived Mapping Violations (§10.3)

**Command**:
```bash
rg "_apply_special_case_overrides" src/ --type py -l
```

**Result**: **1 file** (`src/qmatsuite/core/driver_registry.py`)

**All overrides are illegal**. Must delete and fix GEN names to make pure derivation work.

### 1.4 Underscore in GEN Names (§4)

**Command**:
```bash
rg "vc_md|vc_relax|bands_post|bands_pw" src/ --type py -c | awk -F: '{sum += $2} END {print sum}'
```

**Result**: **27 occurrences**

**Required migrations** (NOT renames to new underscored values):

| Invalid | Migration | Rationale |
|---------|-----------|-----------|
| `vc_relax` | Use `relax` + VC parameter | VC is a mode, not a GEN step |
| `vc_md` | Use `md` + VC parameter | VC is a mode, not a GEN step |
| `bands_post` | Use `bands` | Single word |
| `bands_pw` | Use `bandpw` | Compound word, no underscore |

### 1.5 Legacy Alias Values (§6)

**Command**:
```bash
rg "w90_preproc|w90_run" src/ --type py -c
```

**Result**: **0 files in src/** (COMPLIANT)

---

## Section 2: Gate Implementation Status

| Gate | Constitution § | File | Status |
|------|---------------|------|--------|
| No bare `step_type` | §9 | `tests/gates/test_no_bare_step_type.py` | ❌ NOT IMPLEMENTED |
| Underscore ban | §4 | `tests/gates/test_underscore_ban.py` | ❌ NOT IMPLEMENTED |
| No third namespace | §10.3 | `tests/gates/test_no_third_namespace.py` | ❌ NOT IMPLEMENTED |
| No non-derived mappings | §10.3 | `tests/gates/test_no_nonderived_mappings.py` | ❌ NOT IMPLEMENTED |
| Declared-only (C1) | §10.1-10.2 | `tests/gates/test_declared_only.py` | ❌ NOT IMPLEMENTED |
| No cross-assignment (C2) | Gate C2 | `tests/gates/test_no_cross_assignment.py` | ❌ NOT IMPLEMENTED |
| Banned legacy aliases | §6 | `tests/gates/test_banned_legacy_aliases.py` | ❌ NOT IMPLEMENTED |
| Supported subset | §10.2 | `tests/gates/test_supported_subset.py` | ❌ NOT IMPLEMENTED |
| No SPEC in preset/paramspace (B5) | §8 | `tests/gates/test_no_spec_in_preset_layer.py` | ❌ NOT IMPLEMENTED |
| Single SSOT for mappings (B6) | §10.3 | `tests/gates/test_single_ssot_mapping.py` | ❌ NOT IMPLEMENTED |

---

## Section 3: Blocking Violations Summary

| Category | Constitution § | Count | Blocking |
|----------|---------------|-------|----------|
| Bare `step_type` | §9 | 1146 | YES |
| Third namespace (`GEN_*`) | §10.3 | 13 files | YES |
| Non-derived mappings | §10.3 | 1 file | YES |
| Underscore in GEN | §4 | 27 | YES |
| Missing gates | §11 | 10 gates | YES |

---

## Conclusion

The repository has **5 categories of blocking violations**. The implementation plan (DOC 2) provides the phased remediation path.

**Critical path**:
1. Implement gates FIRST (Phase 1) — including B5/B6 before test fixes
2. Delete third namespace entirely (Phase 2) — hard delete, no deprecation
3. Rename bare `step_type` (Phase 3)
4. Fix underscore violations (Phase 4) — migrate `vc_*` to parameter-based approach
5. Verify all gates pass (Phase 6)
