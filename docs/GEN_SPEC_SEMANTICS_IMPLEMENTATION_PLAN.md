# DOC 2 — Implementation Plan (No-Drift, Verifiable Steps)

**Generated**: 2026-01-31
**Constitution Reference**: `docs/spec/step_type_gen_spec_constitution.md` v1.0 (IMMUTABLE LAW)
**Review Reference**: `docs/GEN_SPEC_SEMANTICS_REVIEW.md` (DOC 1)

---

## NON-NEGOTIABLE LAWS (From Constitution)

1. **Only two step type namespaces exist**: `step_type_gen` and `step_type_spec`. Any third namespace is **ILLEGAL**.

2. **`step_type_spec` is purely derived**: `f"{engine_prefix}_{step_type_gen}"`. No overrides, no mapping tables, no special cases.

3. **Underscore disambiguation**: `step_type_gen` and `engine_prefix` must contain NO underscores.

4. **Repo-wide ban on bare `step_type`**: Must be explicitly `step_type_gen` or `step_type_spec`.

---

## Layering Rule (CRITICAL — Prevents Preset/Kpoints Regressions)

| Layer | Uses | Examples |
|-------|------|----------|
| **UI / Preset / ParamSpace / Workflow Templates** | `step_type_gen` ONLY | `"scf"`, `"bandpw"`, `"md"` |
| **step.yaml / Runner / Dispatch / Execution** | `step_type_spec` ONLY | `"qe_scf"`, `"qe_bandpw"`, `"qe_md"` |

**⚠️ WARNING**: If you convert workflow/preset/paramspace code to SPEC strings, you WILL break precision/kpoints/preset detection. The preset layer reasons in GEN only.

---

## Locked GEN/SPEC Semantics

### Relax and MD: VC is a Parameter, NOT a GEN Step

| GEN | SPEC | Notes |
|-----|------|-------|
| `relax` | `{prefix}_relax` | VC vs non-VC stored in step parameters |
| `md` | `{prefix}_md` | VC vs non-VC stored in step parameters |

**There is NO `vcmd`, `vc_md`, `vc-md`, or `GEN_VC_MD`**.
**There is NO `vcrelax`, `vc_relax`, or `GEN_VC_RELAX`**.

Migration: Use `step_type_gen="md"` or `step_type_gen="relax"` and store VC-ness in `parameters.calculation` (QE) or `parameters.ISIF` (VASP).

### Bands

| GEN | SPEC | Description |
|-----|------|-------------|
| `bandpw` | `{prefix}_bandpw` | Eigenvalue computation on k-path |
| `bands` | `qe_bands` | Post-processing (QE only) |

### Wannier

| GEN | SPEC | Executable |
|-----|------|------------|
| `wannierprep` | `w90_wannierprep` | wannier90.x -pp |
| `pw2wannier` | `qe_pw2wannier` | pw2wannier90.x |
| `wannier` | `w90_wannier` | wannier90.x |

**Banned**: `w90_preproc`, `w90_run` as step type values.

---

## Phase 0: Baseline Measurements

```bash
# Run all before starting. Log results.
echo "=== BASELINE $(date) ===" > /tmp/gen_spec_progress.log

# 0.1 Bare step_type
rg "step_type[^_]" src/ --type py -c 2>/dev/null | awk -F: '{sum += $2} END {print "bare_step_type:", sum}'
# Expected: 1146

# 0.2 GEN_* files
rg "GEN_[A-Z]" src/ --type py -l 2>/dev/null | wc -l
# Expected: 13

# 0.3 GeneralizedStep
rg "GeneralizedStep" src/ --type py -l 2>/dev/null | wc -l
# Expected: 1

# 0.4 _apply_special_case_overrides
rg "_apply_special_case_overrides" src/ --type py -l 2>/dev/null | wc -l
# Expected: 1

# 0.5 Underscore gen violations (vc_md, vc_relax, bands_post, bands_pw)
rg "vc_md|vc_relax|bands_post|bands_pw" src/ --type py -c 2>/dev/null | awk -F: '{sum += $2} END {print sum}'
# Expected: 27

# 0.6 Legacy aliases as step type values
rg '"w90_preproc"|"w90_run"' src/ tests/ --type py -c 2>/dev/null | awk -F: '{sum += $2} END {print sum}'
# Expected: 0 (in src), check tests separately
```

---

## Phase 1: Implement Gates (BLOCKING — Must Complete First)

**What changes**: Create 10 gate test files in `tests/gates/`

**Why**: §11 mandates gates. Gates must exist BEFORE batch-fixing to prevent silent regressions.

### Step 1.1-1.8: Core Gates

Create these files:
- `tests/gates/test_no_bare_step_type.py` (§9)
- `tests/gates/test_underscore_ban.py` (§4)
- `tests/gates/test_no_third_namespace.py` (§10.3) — scans for `GEN_[A-Z]`, `GeneralizedStep`
- `tests/gates/test_no_nonderived_mappings.py` (§10.3) — scans for `_apply_special_case_overrides`
- `tests/gates/test_declared_only.py` (§10.1-10.2)
- `tests/gates/test_no_cross_assignment.py` (Gate C2)
- `tests/gates/test_banned_legacy_aliases.py` (§6)
- `tests/gates/test_supported_subset.py` (§10.2)

### Step 1.9: Gate B5 — No SPEC in Preset/ParamSpace Layer

**What changes**: New file `tests/gates/test_no_spec_in_preset_layer.py`

**Satisfies**: §8 (Layering Rule)

**Scans**: `src/quantumvitas/presets/`, `src/quantumvitas/workflow/templates.py` for SPEC strings (strings containing `_` that look like step types: `qe_`, `vasp_`, `w90_`, etc.)

**Verification**:
```bash
.venv/bin/python -m pytest tests/gates/test_no_spec_in_preset_layer.py -v --tb=no
# Expected: FAIL initially if preset code uses SPEC strings
```

### Step 1.10: Gate B6 — Single SSOT for Mappings

**What changes**: New file `tests/gates/test_single_ssot_mapping.py`

**Satisfies**: §10.3 (No duplicate mapping tables)

**Scans**: Tests and tools for copied mapping dicts. All mapping lookups must call `DriverRegistry` or `GenStepRegistry`.

**Verification**:
```bash
.venv/bin/python -m pytest tests/gates/test_single_ssot_mapping.py -v --tb=no
# Expected: PASS if no duplicate mappings exist
```

### Phase 1 Verification

```bash
ls tests/gates/test_*.py | wc -l
# Expected: 10

.venv/bin/python -m pytest tests/gates/ -v --tb=no -q 2>&1 | tail -30
# Expected: 10 test files exist, some FAIL (that's expected before fixes)
```

---

## Phase 2: Delete Third Namespace (Hard Delete, No Deprecation)

**HARD CONSTRAINT**: No "temporary compatibility layer". No "deprecate then remove". Delete NOW.

### Zero-Tolerance Deletion Checklist

After Phase 2, ALL of these must be 0:

| Target | Command | Expected |
|--------|---------|----------|
| `GEN_*` tokens | `rg "GEN_[A-Z]" src/ tests/ tools/ --type py -c 2>/dev/null \| wc -l` | 0 |
| `GeneralizedStep` | `rg "GeneralizedStep" src/ tests/ tools/ --type py -l 2>/dev/null \| wc -l` | 0 |
| `_apply_special_case_overrides` | `rg "_apply_special_case_overrides" src/ --type py -l 2>/dev/null \| wc -l` | 0 |

### Step 2.1: Update GenStepRegistry.GEN_STEPS

**What changes**: `src/quantumvitas/workflow/gen_steps.py`

Ensure these GEN names exist (pure derivation compatible):
- `scf`, `nscf`, `relax`, `md`, `bandpw`, `bands`, `dos`, `ph`, `wannierprep`, `pw2wannier`, `wannier`, etc.

**Remove** any: `vc-md`, `vcmd`, `vc_md` (use `md` + parameter instead)

**Verification**:
```bash
python -c "from quantumvitas.workflow.gen_steps import GenStepRegistry; s=GenStepRegistry.GEN_STEPS; print('md' in s, 'bandpw' in s, 'vcmd' not in s, 'vc-md' not in s)"
# Expected: True True True True
```

### Step 2.2: Delete _apply_special_case_overrides

**What changes**: `src/quantumvitas/core/driver_registry.py`

**Action**: Delete the entire `_apply_special_case_overrides` method and its call site.

**Verification**:
```bash
rg "_apply_special_case_overrides" src/ --type py -l
# Expected: (no output)
```

### Step 2.3: Refactor _build_materialization_map

**What changes**: `src/quantumvitas/core/driver_registry.py`

**From**:
```python
gen_type = f"GEN_{gen_step.upper().replace('-', '_')}"
mat_map[gen_type] = spec_type
```

**To**:
```python
# Pure derivation: gen (lowercase) → spec = f"{prefix}_{gen}"
mat_map[gen_step] = f"{prefix}_{gen_step}"
```

**Verification**:
```bash
rg 'GEN_\{|GEN_[A-Z]' src/quantumvitas/core/driver_registry.py
# Expected: (no output)
```

### Step 2.4: Delete GeneralizedStep enum

**What changes**: `src/quantumvitas/workflow/generalized_steps.py`

**Action**: Delete the `GeneralizedStep` class. Update all imports to use `GenStepRegistry.GEN_STEPS`.

**Verification**:
```bash
rg "GeneralizedStep" src/ tests/ tools/ --type py -l
# Expected: (no output)
```

### Step 2.5: Update all driver files

**What changes**: All 7 driver files in `src/quantumvitas/drivers/*/driver.py`

**Action**: Ensure `get_materialization_map()` returns purely derived mappings: `{gen: f"{PREFIX}_{gen}" for gen in SUPPORTED_GEN_STEPS}`. No exceptions.

**Verification**:
```bash
rg "GEN_[A-Z]" src/quantumvitas/drivers/ --type py -l
# Expected: (no output)
```

### Phase 2 Verification

```bash
# Zero-tolerance check (all must be 0)
rg "GEN_[A-Z]" src/ tests/ tools/ --type py -c 2>/dev/null | wc -l
# Expected: 0

rg "GeneralizedStep" src/ tests/ tools/ --type py -l 2>/dev/null | wc -l
# Expected: 0

rg "_apply_special_case_overrides" src/ --type py -l 2>/dev/null | wc -l
# Expected: 0

# Gates should pass
.venv/bin/python -m pytest tests/gates/test_no_third_namespace.py tests/gates/test_no_nonderived_mappings.py -v
# Expected: PASS PASS
```

---

## Phase 3: Rename Bare `step_type`

**What changes**: ~100+ files, 1146 occurrences

### Step 3.1: Classification Guide

- **Rename to `step_type_spec`**: execution/dispatch layer, step.yaml, runner
- **Rename to `step_type_gen`**: preset/paramspace/workflow/UI layer

### Step 3.2: Audit Preset/ParamSpace for Accidental SPEC

Before renaming, run Gate B5 to identify preset code that incorrectly uses SPEC strings:

```bash
.venv/bin/python -m pytest tests/gates/test_no_spec_in_preset_layer.py -v
```

Fix any failures FIRST. The preset layer must use GEN only.

### Step 3.3: Batch Processing

Process by file, verify each:
```bash
rg "step_type[^_]" src/quantumvitas/api/service.py --type py -c
# After fixing: Expected 0
```

### Phase 3 Verification

```bash
rg "step_type[^_]" src/ --type py -c 2>/dev/null | awk -F: '{sum += $2} END {print sum}'
# Expected: 0

.venv/bin/python -m pytest tests/gates/test_no_bare_step_type.py -v
# Expected: PASS
```

---

## Phase 4: Fix Underscore Violations (VC Migration)

**What changes**: Migrate `vc_md`, `vc_relax` to parameter-based approach

### Step 4.1: Required Migrations

| Invalid | Migration |
|---------|-----------|
| `vc_md`, `vcmd`, `vc-md` | Use `step_type_gen="md"` + `parameters.calculation="vc-md"` |
| `vc_relax` | Use `step_type_gen="relax"` + `parameters.calculation="vc-relax"` |
| `bands_post` | Use `step_type_gen="bands"` |
| `bands_pw` | Use `step_type_gen="bandpw"` |

### Step 4.2: Update Code

For each file using `vc_md` or `vc_relax`:
1. Change step type to `md` or `relax`
2. Add VC mode to step parameters

**Verification**:
```bash
rg "vc_md|vc_relax|bands_post|bands_pw|vcmd|vc-md" src/ --type py -c 2>/dev/null | awk -F: '{sum += $2} END {print sum}'
# Expected: 0

.venv/bin/python -m pytest tests/gates/test_underscore_ban.py -v
# Expected: PASS
```

---

## Phase 5: Update Tests and Fixtures

**IMPORTANT**: Run Gates B5/B6 BEFORE batch-fixing tests. Otherwise Auto will silently introduce regressions.

### Step 5.1: Verify B5/B6 Gates Pass

```bash
.venv/bin/python -m pytest tests/gates/test_no_spec_in_preset_layer.py tests/gates/test_single_ssot_mapping.py -v
# Expected: PASS PASS
```

### Step 5.2: Update Test Files

Replace bare `step_type` with `step_type_gen` or `step_type_spec`.

Tests that need mapping must call `DriverRegistry` or `GenStepRegistry` — NO copied mapping dicts.

**Verification**:
```bash
rg "step_type[^_]" tests/ --type py -c 2>/dev/null | awk -F: '{sum += $2} END {print sum}'
# Expected: 0 (or minimal for legitimate assertions)
```

### Step 5.3: Golden Fixtures (Deterministic, Minimal)

**CRITICAL**: No `--update-golden` wholesale regeneration.

**Procedure**:
1. Run generator from golden baseline commit
2. Apply deterministic patch LIMITED to allowlisted keys:
   - `step_type` → `step_type_spec`
   - `step_id` → `step_ulid` (if applicable)
3. Any diff outside allowlist is a BUG

**Verification**:
```bash
git diff tests/fixtures/golden_*/daemon/*.json | grep -v step_type | grep -v step_ulid | head -20
# Expected: (no output, or only whitespace)
```

---

## Phase 6: Final Compliance Check

### Step 6.1: All Gates Pass

```bash
.venv/bin/python -m pytest tests/gates/ -v --tb=short
# Expected: All 10 gates PASS
```

### Step 6.2: Zero-Tolerance Final Check

```bash
# All must be 0
rg "step_type[^_]" src/ --type py -c 2>/dev/null | awk -F: '{sum += $2} END {print sum}'
# Expected: 0

rg "GEN_[A-Z]" src/ tests/ tools/ --type py -c 2>/dev/null | wc -l
# Expected: 0

rg "GeneralizedStep" src/ tests/ tools/ --type py -l 2>/dev/null | wc -l
# Expected: 0

rg "_apply_special_case_overrides" src/ --type py -l 2>/dev/null | wc -l
# Expected: 0

rg "vc_md|vc_relax|bands_post|bands_pw|vcmd" src/ --type py -c 2>/dev/null | awk -F: '{sum += $2} END {print sum}'
# Expected: 0

rg '"w90_preproc"|"w90_run"' src/ tests/ --type py -c 2>/dev/null | awk -F: '{sum += $2} END {print sum}'
# Expected: 0
```

### Step 6.3: Full Test Suite

```bash
.venv/bin/python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
# Expected: All tests PASS
```

---

## Phase Summary

| Phase | What | Verification | Expected |
|-------|------|--------------|----------|
| 0 | Baseline | rg counts | Establish baseline |
| 1 | Create 10 gates | `ls tests/gates/ \| wc -l` | 10 files |
| 2 | Delete third namespace | Zero-tolerance checklist | All 0 |
| 3 | Rename bare step_type | Gate + rg | 0 occurrences |
| 4 | Fix underscore/VC | Gate + rg | 0 occurrences |
| 5 | Update tests | Gates B5/B6 + rg | PASS + 0 |
| 6 | Final | All gates + full suite | All PASS |

---

## Critical Success Factors

1. **Gates first**: Implement ALL 10 gates before batch-fixing
2. **No deprecation**: Hard delete, no "keep temporarily"
3. **Pure derivation only**: `get_materialization_map` returns `{gen: f"{PREFIX}_{gen}"}`
4. **Single SSOT**: All mapping lookups via `DriverRegistry` or `GenStepRegistry`
5. **VC is parameter**: No `vc_md` or `vc_relax` GEN steps
6. **No SPEC in preset layer**: Gate B5 enforces this

---

**End of Implementation Plan**
