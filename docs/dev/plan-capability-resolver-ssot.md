# Plan: Capability Resolver SSOT Hardening

**Status**: Ready for implementation  
**Created**: 2026-01-17

## Executive Summary

Harden the preset capability system to be fully self-consistent with a single public API that all callers must use, eliminating duplicate logic and hidden fallbacks.

---

## 1. Review Findings

### 1.1 Current Capability Computation Entrypoints

| Function | Location | Purpose |
|----------|----------|---------|
| `list_presets_for_engine(engine_name, gen_step)` | `presets/catalog.py:211` | Returns intersection of engine.supported_presets and ParamSpace applicability |
| `list_dimensions_for_gen_step(gen_step)` | `presets/variants_registry.py:178` | Returns dimensions with variants for a gen step (ParamSpace only) |
| `list_accepting_presets_for_engine(engine_name)` | `workflow/registry.py:580` | Returns dict of gen_step → available presets for an engine |

### 1.2 Engine.supported_presets SSOT

**Location**: `engine/base.py:28` (abstract property)

**Implementations**:
- `QeEngine`: `["precision", "magnetism", "occupations_scheme", "convergence"]`
- `PySCFEngine`: `["qc_precision"]`
- `ORCAEngine`: `["qc_precision"]`

✅ This is correctly implemented as SSOT for engine capability declaration.

### 1.3 Critical Gap: apply_presets_to_step Lacks Engine Capability Validation

**Location**: `presets/integration.py:328`

**Issue**: `apply_presets_to_step()` does NOT validate against `engine.supported_presets`:
- Only checks if ParamSpace variant exists for step_type
- Does not determine which engine the step belongs to
- Does not verify the engine supports the requested preset

**Risk**: A preset could be "applied" to an engine that doesn't support it, leading to:
- Invalid parameters in step.yaml
- Runtime failures during execution
- Silent corruption of preset state

### 1.4 Daemon/CLI Usage Patterns

**Daemon** (`daemon/server.py`):
- `_handle_apply_presets_to_step()` calls `apply_presets_to_step()` directly
- No capability validation before apply
- Does not determine engine from step context

**CLI** (`cli/main.py`):
- Does not use `list_presets_for_engine()` for showing available presets
- Preset application is delegated to daemon

### 1.5 Detection Pipeline

**Location**: `presets/integration.py:106` (`detect_presets_from_calculation`)

**Issue**: Detection does not filter by engine.supported_presets:
- Returns all matched dimensions, even if engine doesn't declare support
- Could lead to UI showing presets that shouldn't be available

### 1.6 Evidence Commands

```bash
# Show all capability functions
rg "supported_presets|list_presets_for_engine|list_dimensions_for_gen_step" src/quantumvitas --type py -n

# Show apply_presets_to_step usage
rg "apply_presets_to_step" src/quantumvitas --type py -C 3

# Show engine validation in apply
rg "engine.*supported|supported.*engine" src/quantumvitas/presets/integration.py
# (Expected: no matches - this is the gap)
```

---

## 2. Target Architecture

### 2.1 Single Public Capability API

All callers must use this unified interface (in `presets/capability.py`):

```python
# Primary API
def list_presets_for_engine(engine_name: str, gen_step: str) -> List[str]:
    """List available presets for engine + gen_step combination."""

def list_profiles_for_preset(engine_name: str, preset_id: str, gen_step: str) -> List[str]:
    """List available profiles for a preset on engine + gen_step."""

def validate_preset_capability(engine_name: str, gen_step: str, preset_id: str) -> bool:
    """Check if preset is available for engine + gen_step."""

# Guard function for apply
def require_preset_capability(engine_name: str, gen_step: str, preset_id: str) -> None:
    """Raise CapabilityError if preset is not available."""
```

### 2.2 Contract Invariants

1. **Engine not declared → not listed**: If `preset_id not in engine.supported_presets`, it must not appear in any capability query result
2. **Declared but no ParamSpace wiring → empty**: If engine declares support but no ParamSpace variant exists, return empty
3. **Apply must validate**: `apply_presets_to_step()` must call `require_preset_capability()` and fail if not available
4. **Detection filters by engine**: Detection must only attempt matching within `engine.supported_presets`
5. **ORCA optional**: Capability queries do not require ORCA binary

---

## 3. Implementation Plan

### PR0: Create capability resolver module
- [ ] Create `src/quantumvitas/presets/capability.py`
- [ ] Move `list_presets_for_engine()` from `catalog.py` (keep re-export for backwards compat)
- [ ] Add `list_profiles_for_preset()` 
- [ ] Add `validate_preset_capability()`
- [ ] Add `require_preset_capability()` with `CapabilityError` exception
- [ ] Add engine lookup helper that determines engine from step context

**Files to modify**:
- Create: `src/quantumvitas/presets/capability.py`
- Modify: `src/quantumvitas/presets/__init__.py` (add exports)

**Tests to run**:
```bash
pytest tests/unit/test_preset_capability_contract.py -v
python -c "from quantumvitas.presets.capability import list_presets_for_engine, require_preset_capability"
```

---

### PR1: Add engine context resolution to apply
- [ ] Add `_resolve_engine_for_step(step_path)` helper that reads step.yaml and determines engine
- [ ] Modify `apply_presets_to_step()` to call this helper
- [ ] Call `require_preset_capability()` before applying each dimension
- [ ] Add clear error message: "Preset '{preset_id}' is not available for engine '{engine}' on gen step '{gen_step}'"

**Files to modify**:
- `src/quantumvitas/presets/integration.py`

**Tests to run**:
```bash
pytest tests/unit/test_preset_capability_contract.py -v
pytest tests/presets/ -v
```

---

### PR2: Add detection filtering by engine
- [ ] Modify `detect_presets_from_calculation()` to accept optional `engine_filter` param
- [ ] When engine_filter is provided, only attempt detection for supported presets
- [ ] Add `_detect_engine_for_calculation()` helper
- [ ] Update daemon handlers to pass engine filter

**Files to modify**:
- `src/quantumvitas/presets/integration.py`
- `src/quantumvitas/daemon/server.py`

**Tests to run**:
```bash
pytest tests/presets/ -v
pytest tests/daemon/ -v
```

---

### PR3: Add contract enforcement tests
- [ ] Test: engine not declared → not listed
- [ ] Test: declared but missing wiring → hard error on apply
- [ ] Test: apply with unsupported preset raises CapabilityError
- [ ] Test: ORCA capability queries without binary
- [ ] Test: engine-specific supersedes IR (if applicable)

**Files to create**:
- `tests/unit/test_capability_enforcement.py`

**Tests to run**:
```bash
pytest tests/unit/test_capability_enforcement.py -v
pytest tests/unit/test_preset_capability_contract.py -v
```

---

### PR4: Add grep-based guard tests
- [ ] Test: No `StepTypeSpec` gating fields in production code
- [ ] Test: No bypass of capability resolver (direct ParamSpace apply without validation)
- [ ] Test: All apply paths call `require_preset_capability`

**Files to create**:
- `tests/unit/test_no_capability_bypass.py`

**Guard test content**:
```python
"""Guard tests to prevent reintroduction of old gating logic."""

import subprocess

def test_no_accepts_presets_field():
    """Production code must not reference StepTypeSpec.accepts_presets."""
    result = subprocess.run(
        ["rg", "accepts_presets", "src/quantumvitas", "--type", "py", "-l"],
        capture_output=True, text=True
    )
    assert result.stdout.strip() == "", f"Found accepts_presets in: {result.stdout}"

def test_no_allowed_dimensions_field():
    """Production code must not reference StepTypeSpec.allowed_dimensions."""
    result = subprocess.run(
        ["rg", "allowed_dimensions", "src/quantumvitas", "--type", "py", "-l"],
        capture_output=True, text=True
    )
    assert result.stdout.strip() == "", f"Found allowed_dimensions in: {result.stdout}"

def test_all_apply_paths_validate_capability():
    """All apply_presets_to_step calls must go through validated path."""
    # Check that integration.py calls require_preset_capability
    result = subprocess.run(
        ["rg", "require_preset_capability", "src/quantumvitas/presets/integration.py"],
        capture_output=True, text=True
    )
    assert "require_preset_capability" in result.stdout, \
        "apply_presets_to_step must call require_preset_capability"
```

**Tests to run**:
```bash
pytest tests/unit/test_no_capability_bypass.py -v
pytest tests/unit/test_no_deprecated_preset_fields.py -v
```

---

### PR5: Cleanup and documentation
- [ ] Remove duplicate `list_presets_for_engine` from `catalog.py` (keep only re-export)
- [ ] Update existing tests to use capability module
- [ ] Add docstrings referencing this plan
- [ ] Update spec document with capability resolver SSOT

**Files to modify**:
- `src/quantumvitas/presets/catalog.py`
- `docs/dev/spec-preset-paramspace-ir-engine-contract.md`

**Tests to run**:
```bash
pytest tests/unit/ -v --tb=short
pytest tests/presets/ -v
```

---

## 4. Acceptance Criteria

- [ ] `list_presets_for_engine()` is the single entrypoint for capability queries
- [ ] `apply_presets_to_step()` validates capability and fails with clear error if not available
- [ ] Detection filters by engine.supported_presets
- [ ] No production code references `StepTypeSpec.accepts_presets` or `allowed_dimensions`
- [ ] ORCA capability queries work without binary
- [ ] All tests pass: `pytest tests/unit/ tests/presets/ tests/daemon/ -v`

---

## 5. Risk Assessment

| Risk | Mitigation |
|------|------------|
| Breaking existing apply flows | Add capability validation incrementally; backward-compat mode first |
| ORCA binary requirement regression | Maintain `defer_binary_resolution=True` pattern |
| Detection performance impact | Engine filter is optional; only enable when needed |
| Daemon API breaking change | Capability validation returns clear error, not silent failure |

---

## 6. Implementation Log

_Auto will update this section as PRs are implemented._

```
PR0: [ ] Create capability resolver module
PR1: [ ] Add engine context resolution to apply
PR2: [ ] Add detection filtering by engine
PR3: [ ] Add contract enforcement tests
PR4: [ ] Add grep-based guard tests
PR5: [ ] Cleanup and documentation
```

---

## 7. Prompts for Cursor Auto

### PR0 Prompt

```
You are AUTO implementing PR0 from docs/dev/plan-capability-resolver-ssot.md

TASK: Create capability resolver module.

CREATE FILE: src/quantumvitas/presets/capability.py

Content must include:
- CapabilityError exception class
- list_presets_for_engine(engine_name, gen_step) - move from catalog.py
- list_profiles_for_preset(engine_name, preset_id, gen_step)
- validate_preset_capability(engine_name, gen_step, preset_id) -> bool
- require_preset_capability(engine_name, gen_step, preset_id) -> None (raises CapabilityError)

MODIFY: src/quantumvitas/presets/__init__.py
- Add exports for new functions

VERIFICATION:
python -c "from quantumvitas.presets.capability import list_presets_for_engine, require_preset_capability, CapabilityError"
pytest tests/unit/test_preset_capability_contract.py -v

TICK CHECKBOXES: PR0 in plan file section 6
COMMIT: "Presets: add capability resolver module (PR0)"
STOP IF: Import errors occur.
```

### PR1 Prompt

```
You are AUTO implementing PR1 from docs/dev/plan-capability-resolver-ssot.md

TASK: Add engine context resolution and capability validation to apply.

MODIFY: src/quantumvitas/presets/integration.py

Changes:
1. Add _resolve_engine_for_step(step_path) helper that:
   - Reads step.yaml
   - Gets step_type
   - Uses workflow.registry to determine engine

2. Modify apply_presets_to_step() to:
   - Call _resolve_engine_for_step() at the start
   - For each dimension in options, call require_preset_capability()
   - If CapabilityError raised, include clear message with engine/gen_step/preset

VERIFICATION:
pytest tests/presets/ -v
pytest tests/unit/test_preset_capability_contract.py -v

TICK CHECKBOXES: PR1 in plan file section 6
COMMIT: "Presets: add capability validation to apply (PR1)"
STOP IF: Existing tests fail.
```

### PR2 Prompt

```
You are AUTO implementing PR2 from docs/dev/plan-capability-resolver-ssot.md

TASK: Add detection filtering by engine.

MODIFY: src/quantumvitas/presets/integration.py
- Add optional engine_filter param to detect_presets_from_calculation()
- When provided, only detect presets in engine.supported_presets

MODIFY: src/quantumvitas/daemon/server.py
- Update detection handlers to optionally pass engine filter

VERIFICATION:
pytest tests/presets/ -v
pytest tests/daemon/ -v --ignore=tests/daemon/test_si_bands_calculation_daemon.py

TICK CHECKBOXES: PR2 in plan file section 6
COMMIT: "Presets: add detection filtering by engine (PR2)"
STOP IF: Daemon tests fail.
```

### PR3 Prompt

```
You are AUTO implementing PR3 from docs/dev/plan-capability-resolver-ssot.md

TASK: Add contract enforcement tests.

CREATE FILE: tests/unit/test_capability_enforcement.py

Tests must include:
- test_engine_not_declared_not_listed: engine without preset in supported_presets → not in list
- test_declared_but_no_wiring_returns_empty: engine declares but no ParamSpace variant → empty
- test_apply_unsupported_preset_raises_error: apply with unsupported preset → CapabilityError
- test_orca_capability_without_binary: ORCA capability queries work without binary
- test_require_capability_clear_error_message: error message includes engine/gen_step/preset

VERIFICATION:
pytest tests/unit/test_capability_enforcement.py -v
pytest tests/unit/test_preset_capability_contract.py -v

TICK CHECKBOXES: PR3 in plan file section 6
COMMIT: "Tests: add capability enforcement tests (PR3)"
STOP IF: New tests fail.
```

### PR4 Prompt

```
You are AUTO implementing PR4 from docs/dev/plan-capability-resolver-ssot.md

TASK: Add grep-based guard tests.

CREATE FILE: tests/unit/test_no_capability_bypass.py

Tests must include:
- test_no_accepts_presets_field: rg check for accepts_presets in production code
- test_no_allowed_dimensions_field: rg check for allowed_dimensions in production code
- test_apply_calls_require_capability: integration.py must call require_preset_capability

VERIFICATION:
pytest tests/unit/test_no_capability_bypass.py -v
pytest tests/unit/test_no_deprecated_preset_fields.py -v

TICK CHECKBOXES: PR4 in plan file section 6
COMMIT: "Tests: add capability bypass guard tests (PR4)"
STOP IF: Guard tests fail unexpectedly (indicates production code issue).
```

### PR5 Prompt

```
You are AUTO implementing PR5 from docs/dev/plan-capability-resolver-ssot.md

TASK: Cleanup and documentation.

MODIFY: src/quantumvitas/presets/catalog.py
- Remove list_presets_for_engine implementation (keep re-export from capability module)

MODIFY: docs/dev/spec-preset-paramspace-ir-engine-contract.md
- Add section on capability resolver being SSOT

VERIFICATION:
pytest tests/unit/ -v --tb=short
pytest tests/presets/ -v

TICK ALL CHECKBOXES in plan file section 6
COMMIT: "Presets: cleanup capability resolver integration (PR5)"
```

