# Step Type Migration Plan

**Date**: 2026-01-30
**Status**: IMPLEMENTATION PLAN - For Cursor Auto Execution
**Updated**: Corrected Wannier90 engine ownership, comprehensive audit

---

## Overview

This plan migrates the codebase from explicit mapping tables to the pure naming-based spec↔gen conversion defined in `STEP_TYPE_CONSTITUTION_REVIEW.md`.

**Invariant**: At every step, the test suite must pass (except for explicitly listed expected failures).

**CRITICAL CORRECTION**: W90 steps (`wannierprep`, `wannier`) use W90 engine, NOT QE engine. Only `pw2wannier` uses QE engine.

---

## Wannier90 Chain: Correct Mapping

### Current System (TODAY)

| GEN (current) | SPEC (current) | Engine (WRONG) | Executable |
|---------------|----------------|----------------|------------|
| `w90_preproc` | `w90_preproc` | `qe` ← WRONG | `wannier90.x -pp` |
| `pw2wannier90` | `qe_pw2wannier90` | `qe` ✓ | `pw2wannier90.x` |
| `w90_run` | `w90_run` | `qe` ← WRONG | `wannier90.x` |

### Target System (AFTER MIGRATION)

| GEN (target) | SPEC (target) | Engine (CORRECT) | Executable |
|--------------|---------------|------------------|------------|
| `wannierprep` | `w90_wannierprep` | `w90` ✓ | `wannier90.x -pp` |
| `pw2wannier` | `qe_pw2wannier` | `qe` ✓ | `pw2wannier90.x` |
| `wannier` | `w90_wannier` | `w90` ✓ | `wannier90.x` |

---

## Phase 1: Create New SSOT Modules (Non-Breaking)

### Step 1.1: Create GenStepRegistry

**Goal**: Establish single source of truth for all valid GEN step names.

**Files to create**: `src/quantumvitas/workflow/gen_steps.py`

**Content**:
```python
"""
GenStepRegistry: Single source of truth for all valid GEN step names.

GEN steps are engine-agnostic, underscore-free identifiers.
SPEC steps are created by: {engine_prefix}_{gen_step}
"""

from typing import FrozenSet


class GenStepRegistry:
    """Central registry of all valid GEN step names."""

    # All valid GEN steps (NO underscores allowed by constitution)
    # NOTE: This is a MIGRATION state - some names still have underscores
    # and will be renamed in Phase 2
    GEN_STEPS: FrozenSet[str] = frozenset({
        # SCF-family (PBC and molecular)
        "scf",
        "hf",
        "nscf",
        # Optimization
        "relax",
        # Electronic structure (QE post-processing)
        "bands",
        "bands_pw",     # MIGRATION: will become "bandspw"
        "dos",
        "projwfc",
        "pp",
        # Wannier (MIGRATION: these will be renamed)
        "w90_preproc",  # MIGRATION: will become "wannierprep"
        "pw2wannier90", # MIGRATION: will become "pw2wannier"
        "w90_run",      # MIGRATION: will become "wannier"
        # Phonon
        "ph",
        "q2r",
        "matdyn",
        "dynmat",
        # Dynamics
        "md",
        "vc-md",
        # Post-HF (molecular)
        "mp2",
        "td",
        # Escape hatch
        "custom",
    })

    @classmethod
    def is_valid(cls, gen: str) -> bool:
        """Check if gen step is in registry."""
        return gen.lower() in {g.lower() for g in cls.GEN_STEPS}

    @classmethod
    def validate(cls, gen: str) -> None:
        """Validate gen step, raise if invalid."""
        if not cls.is_valid(gen):
            raise ValueError(f"GEN step '{gen}' not in registry")

    @classmethod
    def get_all(cls) -> FrozenSet[str]:
        """Get all registered GEN steps."""
        return cls.GEN_STEPS
```

**Commands to run**:
```bash
# Create the file (manually or via editor)
# Then verify import works:
.venv/bin/python -c "from quantumvitas.workflow.gen_steps import GenStepRegistry; print(GenStepRegistry.is_valid('scf'))"
```

**Expected outcome**: Prints `True`

**If it fails**: Check for syntax errors in the new file, verify `__init__.py` exports if needed.

---

### Step 1.2: Create step_type_convert Module

**Goal**: Provide pure functions for SPEC↔GEN conversion.

**Files to create**: `src/quantumvitas/workflow/step_type_convert.py`

**Content**:
```python
"""
Pure functions for SPEC↔GEN conversion.

Constitution:
- SPEC = {prefix}_{gen}
- GEN = no underscores (after migration)
- String with '_' is SPEC
- String without '_' is GEN
"""

from typing import FrozenSet

# Known engine prefixes (no underscores allowed)
ENGINE_PREFIXES: FrozenSet[str] = frozenset({
    "qe", "pyscf", "orca", "vasp", "lammps", "cp2k", "w90"
})


def spec_from(prefix: str, gen: str) -> str:
    """
    Create SPEC from prefix + gen.

    Args:
        prefix: Engine prefix (e.g., "qe", "vasp", "w90")
        gen: GEN step name (e.g., "scf", "wannierprep")

    Returns:
        SPEC step type (e.g., "qe_scf", "w90_wannierprep")
    """
    if not prefix:
        raise ValueError("prefix cannot be empty")
    if not gen:
        raise ValueError("gen cannot be empty")
    return f"{prefix}_{gen}"


def gen_from(spec: str) -> str:
    """
    Extract GEN from SPEC.

    If input has no underscore, returns as-is (already GEN).

    Args:
        spec: SPEC step type (e.g., "qe_scf") or GEN (e.g., "scf")

    Returns:
        GEN step name (e.g., "scf")
    """
    if not spec:
        return spec
    if "_" not in spec:
        return spec  # Already GEN
    # Split on first underscore only
    parts = spec.split("_", 1)
    return parts[1]


def prefix_from(spec: str) -> str:
    """
    Extract engine prefix from SPEC.

    Args:
        spec: SPEC step type (e.g., "qe_scf")

    Returns:
        Engine prefix (e.g., "qe")

    Raises:
        ValueError: If spec has no underscore
    """
    if "_" not in spec:
        raise ValueError(f"'{spec}' is not a SPEC (no underscore)")
    return spec.split("_", 1)[0]


def is_spec(s: str) -> bool:
    """Check if string is SPEC format (has underscore)."""
    return bool(s) and "_" in s


def is_gen(s: str) -> bool:
    """Check if string is GEN format (no underscore)."""
    return bool(s) and "_" not in s


def normalize_to_gen(step_type: str) -> str:
    """
    Normalize any step type to GEN format.

    Handles both SPEC (qe_scf) and GEN (scf) inputs.
    This is the canonical replacement for normalize_step_type_to_gen().

    Args:
        step_type: Any step type string

    Returns:
        GEN step name
    """
    return gen_from(step_type)
```

**Commands to run**:
```bash
.venv/bin/python -c "
from quantumvitas.workflow.step_type_convert import spec_from, gen_from, is_spec, is_gen
print(spec_from('qe', 'scf'))       # qe_scf
print(spec_from('w90', 'wannier'))  # w90_wannier
print(gen_from('qe_scf'))           # scf
print(gen_from('w90_wannier'))      # wannier
print(gen_from('scf'))              # scf
print(is_spec('qe_scf'))            # True
print(is_gen('scf'))                # True
"
```

**Expected outcome**: All prints match comments.

---

### Step 1.3: Add Gate Tests (Initial Version)

**Goal**: Create gate tests that will enforce the constitution.

**Files to create**: `tests/gates/test_step_type_constitution.py`

**Content**:
```python
"""
Gate tests for Step Type Constitution.

These tests enforce the naming invariants from STEP_TYPE_CONSTITUTION_REVIEW.md.

NOTE: Some tests are marked with @pytest.mark.skip during migration phase.
They will be unskipped as renames are completed.
"""

import pytest
from quantumvitas.workflow.gen_steps import GenStepRegistry
from quantumvitas.workflow.step_type_convert import (
    spec_from, gen_from, prefix_from, is_spec, is_gen, ENGINE_PREFIXES
)


class TestGenStepRegistry:
    """Gate tests for GenStepRegistry."""

    def test_registry_not_empty(self):
        """Registry must have steps defined."""
        assert len(GenStepRegistry.GEN_STEPS) > 0

    def test_common_gen_steps_present(self):
        """Common GEN steps must be in registry."""
        required = {"scf", "nscf", "relax", "dos", "bands", "md"}
        for gen in required:
            assert GenStepRegistry.is_valid(gen), f"'{gen}' missing from registry"


class TestStepTypeConvert:
    """Gate tests for spec↔gen conversion functions."""

    def test_spec_from_creates_correct_format(self):
        """spec_from creates {prefix}_{gen}."""
        assert spec_from("qe", "scf") == "qe_scf"
        assert spec_from("vasp", "relax") == "vasp_relax"
        assert spec_from("w90", "wannier") == "w90_wannier"

    def test_gen_from_extracts_gen(self):
        """gen_from extracts gen from spec."""
        assert gen_from("qe_scf") == "scf"
        assert gen_from("vasp_relax") == "relax"
        assert gen_from("pyscf_mp2") == "mp2"
        assert gen_from("w90_wannier") == "wannier"

    def test_gen_from_passthrough_for_gen(self):
        """gen_from returns gen as-is."""
        assert gen_from("scf") == "scf"
        assert gen_from("relax") == "relax"

    def test_prefix_from_extracts_prefix(self):
        """prefix_from extracts engine prefix."""
        assert prefix_from("qe_scf") == "qe"
        assert prefix_from("vasp_relax") == "vasp"
        assert prefix_from("w90_wannier") == "w90"

    def test_prefix_from_raises_for_gen(self):
        """prefix_from raises for non-SPEC input."""
        with pytest.raises(ValueError):
            prefix_from("scf")

    def test_is_spec_detects_underscore(self):
        """is_spec returns True for strings with underscore."""
        assert is_spec("qe_scf") is True
        assert is_spec("scf") is False

    def test_is_gen_detects_no_underscore(self):
        """is_gen returns True for strings without underscore."""
        assert is_gen("scf") is True
        assert is_gen("qe_scf") is False

    def test_roundtrip_conversion(self):
        """spec_from and gen_from are inverses."""
        for prefix in ["qe", "vasp", "pyscf", "w90"]:
            for gen in ["scf", "relax", "dos"]:
                spec = spec_from(prefix, gen)
                assert gen_from(spec) == gen
                assert prefix_from(spec) == prefix


class TestEnginePrefixes:
    """Gate tests for engine prefixes."""

    def test_no_underscore_in_prefixes(self):
        """No engine prefix should contain underscore."""
        for prefix in ENGINE_PREFIXES:
            assert "_" not in prefix, f"Prefix '{prefix}' contains underscore"

    def test_known_engines_present(self):
        """Known engines must be in prefix list."""
        required = {"qe", "vasp", "pyscf", "orca", "lammps", "cp2k", "w90"}
        for prefix in required:
            assert prefix in ENGINE_PREFIXES, f"'{prefix}' missing from ENGINE_PREFIXES"


# =============================================================================
# MIGRATION GATES - Skipped during migration, unskipped when renames complete
# =============================================================================

class TestNoUnderscoreInGenSteps:
    """Gate: No underscore in GEN steps (Constitution Law 1)."""

    @pytest.mark.skip(reason="MIGRATION: Unskip after Phase 2 renames complete")
    def test_no_underscore_in_gen_registry(self):
        """All GEN steps must not contain underscore."""
        for gen in GenStepRegistry.GEN_STEPS:
            assert "_" not in gen, f"GEN '{gen}' contains underscore (FORBIDDEN)"
```

**Commands to run**:
```bash
.venv/bin/python -m pytest tests/gates/test_step_type_constitution.py -v
```

**Expected outcome**: All tests pass except the skipped one.

---

### Step 1.4: Run Full Test Suite

**Goal**: Verify Phase 1 changes are non-breaking.

**Commands to run**:
```bash
.venv/bin/python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

**Expected outcome**: All tests pass (same as before Phase 1).

**If it fails**: Revert Phase 1 files and debug.

---

## Phase 2: Rename Underscore-Containing GEN Steps

### IMPORTANT: Temporary Gate Bypass

During Phase 2, Gate G1 (no underscore in GEN) is **SKIPPED**. This is expected.

**What must still pass**:
- All other gates
- All unit tests (after updating string literals)
- All integration tests (after updating string literals)

**What is allowed to fail temporarily**:
- Gate G1 (test_no_underscore_in_gen_registry) - skipped

---

### Step 2.1: Audit All Occurrences (Pre-Rename)

**Goal**: Find every occurrence before batch rename.

**Commands to run**:
```bash
# Find all w90_preproc occurrences
rg -n "w90_preproc" src/ tests/ resources/ > /tmp/w90_preproc_audit.txt

# Find all w90_run occurrences
rg -n "w90_run" src/ tests/ resources/ > /tmp/w90_run_audit.txt

# Find all pw2wannier90 occurrences
rg -n "pw2wannier90" src/ tests/ resources/ > /tmp/pw2wannier90_audit.txt

# Find all bands_pw occurrences
rg -n "bands_pw" src/ tests/ resources/ > /tmp/bands_pw_audit.txt

# Count occurrences
echo "w90_preproc: $(wc -l < /tmp/w90_preproc_audit.txt)"
echo "w90_run: $(wc -l < /tmp/w90_run_audit.txt)"
echo "pw2wannier90: $(wc -l < /tmp/pw2wannier90_audit.txt)"
echo "bands_pw: $(wc -l < /tmp/bands_pw_audit.txt)"
```

**Expected outcome**: Lists of files with line numbers saved to /tmp.

---

### Step 2.2: Rename `w90_preproc` → `wannierprep` (GEN only)

**Goal**: Rename the GEN step name. SPEC becomes `w90_wannierprep`.

**Files to modify** (from audit, Section 4 of Constitution Review):

| File | What to change |
|------|----------------|
| `src/quantumvitas/workflow/gen_steps.py` | Change `"w90_preproc"` to `"wannierprep"` in GEN_STEPS |
| `src/quantumvitas/workflow/registry.py:321-330` | Change `step_type_gen="w90_preproc"` → `"wannierprep"`, `step_type_spec="w90_preproc"` → `"w90_wannierprep"`, `engine="qe"` → `"w90"` |
| `src/quantumvitas/drivers/qe/step_types.py:121-128` | **DELETE** this entry (W90 step, not QE) |
| `src/quantumvitas/drivers/qe/engine/qe_engine.py:62` | Change key `"w90_preproc"` → `"wannierprep"` |
| `src/quantumvitas/drivers/qe/engine/qe_engine.py:379` | Change `step_gen_type == "w90_preproc"` → `"wannierprep"` |
| `src/quantumvitas/drivers/qe/engine/qe_engine.py:442` | Change `"w90_preproc"` → `"wannierprep"` in no_stdin_steps |
| `src/quantumvitas/drivers/qe/engine/qe_calculation.py:304,399,528,589,603` | Change all `"w90_preproc"` → `"wannierprep"` |
| `src/quantumvitas/calculation/structure_steps.py:784` | Change `"w90_preproc"` → `"wannierprep"` in WANNIER90_STEP_TYPES |
| `src/quantumvitas/calculation/structure_steps.py:842` | Change `step_type_gen == "w90_preproc"` → `"wannierprep"` |
| `src/quantumvitas/calculation/step_done.py:18` | Change `"w90_preproc"` → `"wannierprep"` |
| `src/quantumvitas/calculation/verification.py:97` | Change `"w90_preproc"` → `"wannierprep"` |
| `src/quantumvitas/calculation/step_artifacts.py:50,119` | Rename function and dict key |
| `src/quantumvitas/calculation/input_runner.py:239` | Change `"w90_preproc"` → `"wannierprep"` |
| `src/quantumvitas/cli/main.py:957` | Change `"w90_preproc"` → `"w90_wannierprep"` (SPEC) |
| `src/quantumvitas/frontends/cli/app.py:883` | Change `"w90_preproc"` → `"w90_wannierprep"` (SPEC) |
| `src/quantumvitas/core/driver_protocol.py:67` | Change or remove `"w90_preproc"` |
| `src/quantumvitas/drivers/w90/driver.py:6-8` | Fix comment |
| `src/quantumvitas/drivers/w90/artifact_resolver.py:25,52,74` | Update references |
| `src/quantumvitas/drivers/w90/handler.py:43,94` | Update references |

**Demo projects to update**:
| File | What to change |
|------|----------------|
| `resources/demo_projects/diamond_wannier90_demo.yml:425` | `step_type_spec: w90_preproc` → `w90_wannierprep` |
| `resources/demo_projects/silicon_wannier90_demo.yml` | Same pattern |
| `resources/demo_projects/copper_wannier90_demo.yml` | Same pattern |

**Commands to run after changes**:
```bash
# Verify no w90_preproc remains in src/
rg "w90_preproc" src/
# Should return empty

# Run targeted Wannier tests
.venv/bin/python -m pytest tests/ -k "wannier" -v --tb=short

# Run full suite
.venv/bin/python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

**Expected outcome**: No `w90_preproc` in src/, all tests pass.

**If tests fail**: Check error messages, likely missed a string literal somewhere.

---

### Step 2.3: Rename `w90_run` → `wannier` (GEN only)

**Goal**: Rename the GEN step name. SPEC becomes `w90_wannier`.

**Files to modify**:

| File | What to change |
|------|----------------|
| `src/quantumvitas/workflow/gen_steps.py` | Change `"w90_run"` to `"wannier"` in GEN_STEPS |
| `src/quantumvitas/workflow/registry.py:341-350` | Change `step_type_gen="w90_run"` → `"wannier"`, `step_type_spec="w90_run"` → `"w90_wannier"`, `engine="qe"` → `"w90"` |
| `src/quantumvitas/drivers/w90/driver.py:61` | Change `step_type_spec="w90_run"` → `"w90_wannier"` |
| `src/quantumvitas/drivers/w90/driver.py:86` | **DELETE** the get_materialization_map method |
| `src/quantumvitas/drivers/qe/engine/qe_engine.py:64` | Change key `"w90_run"` → `"wannier"` |
| `src/quantumvitas/drivers/qe/engine/qe_engine.py:385` | Change `step_gen_type == "w90_run"` → `"wannier"` |
| `src/quantumvitas/drivers/qe/engine/qe_engine.py:442` | Change `"w90_run"` → `"wannier"` in no_stdin_steps |
| `src/quantumvitas/drivers/qe/engine/qe_calculation.py:304,400,546,556,559,589,603` | Change all `"w90_run"` → `"wannier"` |
| `src/quantumvitas/calculation/structure_steps.py:784` | Change `"w90_run"` → `"wannier"` in WANNIER90_STEP_TYPES |
| `src/quantumvitas/calculation/structure_steps.py:842` | Change `step_type_gen == "w90_run"` → `"wannier"` |
| `src/quantumvitas/calculation/step_done.py:18` | Change `"w90_run"` → `"wannier"` |
| `src/quantumvitas/calculation/verification.py:97` | Change `"w90_run"` → `"wannier"` |
| `src/quantumvitas/calculation/step_artifacts.py:78,121` | Rename function and dict key |
| `src/quantumvitas/calculation/input_runner.py:239` | Change `"w90_run"` → `"wannier"` |
| `src/quantumvitas/workflow/templates.py:119` | Change `"w90_run"` → `"wannier"` |
| `src/quantumvitas/cli/main.py:957` | Change `"w90_run"` → `"w90_wannier"` (SPEC) |
| `src/quantumvitas/frontends/cli/app.py:883` | Change `"w90_run"` → `"w90_wannier"` (SPEC) |
| `src/quantumvitas/core/driver_protocol.py:67` | Change or remove `"w90_run"` |

**Demo projects to update**:
| File | What to change |
|------|----------------|
| `resources/demo_projects/diamond_wannier90_demo.yml:449` | `step_type_spec: w90_run` → `w90_wannier` |
| `resources/demo_projects/silicon_wannier90_demo.yml` | Same pattern |
| `resources/demo_projects/copper_wannier90_demo.yml` | Same pattern |

**Commands to run after changes**:
```bash
# Verify no w90_run remains in src/
rg "w90_run" src/
# Should return empty

# Run targeted Wannier tests
.venv/bin/python -m pytest tests/ -k "wannier" -v --tb=short

# Run full suite
.venv/bin/python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

**Expected outcome**: No `w90_run` in src/, all tests pass.

---

### Step 2.4: Rename `pw2wannier90` → `pw2wannier` (GEN only)

**Goal**: Rename the GEN step name. SPEC becomes `qe_pw2wannier` (QE engine, unchanged).

**Files to modify**:

| File | What to change |
|------|----------------|
| `src/quantumvitas/workflow/gen_steps.py` | Change `"pw2wannier90"` to `"pw2wannier"` in GEN_STEPS |
| `src/quantumvitas/workflow/registry.py:331-340` | Change `step_type_gen="pw2wannier90"` → `"pw2wannier"`, `step_type_spec="qe_pw2wannier90"` → `"qe_pw2wannier"` |
| `src/quantumvitas/drivers/qe/step_types.py:110-114` | Change `step_type_spec="qe_pw2wannier90"` → `"qe_pw2wannier"` |
| `src/quantumvitas/drivers/qe/engine/qe_engine.py:63` | Change key `"pw2wannier90"` → `"pw2wannier"` |
| `src/quantumvitas/drivers/qe/engine/qe_engine.py:389-398` | Change `step_gen_type == "pw2wannier90"` → `"pw2wannier"` |
| `src/quantumvitas/drivers/qe/engine/qe_engine.py:442` | Change `"pw2wannier90"` → `"pw2wannier"` in no_stdin_steps |
| `src/quantumvitas/drivers/qe/engine/qe_calculation.py:309,401-452,564-576,607-608` | Change all `"pw2wannier90"` → `"pw2wannier"` |
| `src/quantumvitas/calculation/structure_steps.py:270,283,302,784,1004` | Change all `"pw2wannier90"` → `"pw2wannier"` |
| `src/quantumvitas/calculation/step_done.py:18` | Change `"pw2wannier90"` → `"pw2wannier"` |
| `src/quantumvitas/calculation/verification.py:97` | Change `"pw2wannier90"` → `"pw2wannier"` |
| `src/quantumvitas/calculation/step_artifacts.py:60,120` | Rename function and dict key |
| `src/quantumvitas/calculation/input_runner.py:239,431` | Change `"pw2wannier90"` → `"pw2wannier"` |
| `src/quantumvitas/calculation/naming.py:45,63-75,97-98` | Change all `"pw2wannier90"` → `"pw2wannier"` |
| `src/quantumvitas/workflow/templates.py:119` | Change `"pw2wannier90"` → `"pw2wannier"` |
| `src/quantumvitas/cli/main.py:956,964` | Change `"qe_pw2wannier90"` → `"qe_pw2wannier"`, `"pw2wannier90"` → `"pw2wannier"` |
| `src/quantumvitas/frontends/cli/app.py:882,890` | Change SPEC and GEN names |

**Demo projects to update**:
| File | What to change |
|------|----------------|
| `resources/demo_projects/diamond_wannier90_demo.yml:438` | `step_type_spec: qe_pw2wannier90` → `qe_pw2wannier` |
| `resources/demo_projects/silicon_wannier90_demo.yml` | Same pattern |
| `resources/demo_projects/copper_wannier90_demo.yml` | Same pattern |

**Commands to run after changes**:
```bash
# Verify no pw2wannier90 remains in src/
rg "pw2wannier90" src/
# Should return empty (or only in comments/docs)

# Run targeted tests
.venv/bin/python -m pytest tests/ -k "pw2wannier or wannier" -v --tb=short

# Run full suite
.venv/bin/python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

**Expected outcome**: No `pw2wannier90` in src/, all tests pass.

---

### Step 2.5: Rename `bands_pw` → `bandspw` (GEN only)

**Goal**: Rename the GEN step name. SPEC becomes `qe_bandspw`.

**Files to modify**:

| File | What to change |
|------|----------------|
| `src/quantumvitas/workflow/gen_steps.py` | Change `"bands_pw"` to `"bandspw"` in GEN_STEPS |
| `src/quantumvitas/workflow/registry.py:199-208` | Change `step_type_gen="bands_pw"` → `"bandspw"`, `step_type_spec="qe_bands_pw"` → `"qe_bandspw"` |
| `src/quantumvitas/drivers/qe/step_types.py:32-36` | Change `step_type_spec="qe_bands_pw"` → `"qe_bandspw"` |
| `src/quantumvitas/calculation/structure_steps.py` | Search and replace `bands_pw` → `bandspw` |
| `src/quantumvitas/history/digests.py:314` | Change conditional check |
| `src/quantumvitas/frontends/cli/app.py` | Change SPEC and GEN names |
| `src/quantumvitas/presets/precision_variants.py` | Search and replace |

**Commands to run after changes**:
```bash
# Verify no bands_pw remains in src/
rg "bands_pw" src/
# Should return empty

# Run full suite
.venv/bin/python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

**Expected outcome**: No `bands_pw` in src/, all tests pass.

---

### Step 2.6: Update GenStepRegistry to Final State

**Goal**: Remove migration comments, verify no underscores remain.

**Files to modify**: `src/quantumvitas/workflow/gen_steps.py`

**Final content for GEN_STEPS**:
```python
GEN_STEPS: FrozenSet[str] = frozenset({
    # SCF-family
    "scf", "hf", "nscf",
    # Optimization
    "relax",
    # Electronic structure
    "bands", "bandspw", "dos", "projwfc", "pp",
    # Wannier (W90 engine: wannierprep, wannier; QE engine: pw2wannier)
    "wannierprep", "pw2wannier", "wannier",
    # Phonon
    "ph", "q2r", "matdyn", "dynmat",
    # Dynamics
    "md", "vcmd",
    # Post-HF
    "mp2", "td",
    # Escape hatch
    "custom",
})
```

---

### Step 2.7: Unskip Gate G1

**Goal**: Enable the underscore gate test.

**Files to modify**: `tests/gates/test_step_type_constitution.py`

**Change**:
```python
# Remove or comment out this line:
# @pytest.mark.skip(reason="MIGRATION: Unskip after Phase 2 renames complete")
def test_no_underscore_in_gen_registry(self):
```

**Commands to run**:
```bash
.venv/bin/python -m pytest tests/gates/test_step_type_constitution.py -v
```

**Expected outcome**: All gate tests pass, including G1.

---

### Step 2.8: Add Wannier90 Engine Ownership Gate

**Goal**: Enforce correct engine assignment for Wannier steps.

**Add to** `tests/gates/test_step_type_constitution.py`:

```python
class TestWannier90EngineOwnership:
    """Gate: Wannier90 steps must have correct engine assignment."""

    def test_wannierprep_is_w90_engine(self):
        """wannierprep uses W90 engine (wannier90.x -pp)."""
        from quantumvitas.workflow.registry import get_registry
        registry = get_registry()
        spec = registry.get("w90_wannierprep")
        assert spec is not None, "w90_wannierprep not found in registry"
        assert spec.engine == "w90", f"wannierprep has wrong engine: {spec.engine}"

    def test_wannier_is_w90_engine(self):
        """wannier uses W90 engine (wannier90.x)."""
        from quantumvitas.workflow.registry import get_registry
        registry = get_registry()
        spec = registry.get("w90_wannier")
        assert spec is not None, "w90_wannier not found in registry"
        assert spec.engine == "w90", f"wannier has wrong engine: {spec.engine}"

    def test_pw2wannier_is_qe_engine(self):
        """pw2wannier uses QE engine (pw2wannier90.x)."""
        from quantumvitas.workflow.registry import get_registry
        registry = get_registry()
        spec = registry.get("qe_pw2wannier")
        assert spec is not None, "qe_pw2wannier not found in registry"
        assert spec.engine == "qe", f"pw2wannier has wrong engine: {spec.engine}"
```

**Commands to run**:
```bash
.venv/bin/python -m pytest tests/gates/test_step_type_constitution.py::TestWannier90EngineOwnership -v
```

**Expected outcome**: All three tests pass.

---

## Phase 3: Remove Explicit Mapping Tables

### Step 3.1: Remove `get_materialization_map()` from All Drivers

**Goal**: Delete mapping dicts, add PREFIX + SUPPORTED_GEN_STEPS.

**Files to modify**:

1. `src/quantumvitas/drivers/qe/driver.py` - Remove `get_materialization_map()`, add:
   ```python
   PREFIX: str = "qe"
   SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({...})
   ```

2. `src/quantumvitas/drivers/vasp/driver.py` - Same pattern

3. `src/quantumvitas/drivers/pyscf/driver.py` - Same pattern

4. `src/quantumvitas/drivers/orca/driver.py` - Same pattern

5. `src/quantumvitas/drivers/cp2k/driver.py` - Same pattern

6. `src/quantumvitas/drivers/lammps/driver.py` - Same pattern

7. `src/quantumvitas/drivers/w90/driver.py` - Same pattern (PREFIX="w90")

**Verification after each driver**:
```bash
.venv/bin/python -m pytest tests/drivers/ -v --tb=short
.venv/bin/python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

---

### Step 3.2: Remove `_gen_to_spec` from StepTypeRegistry

**Goal**: Use canonical `spec_from()` instead.

**Files to modify**: `src/quantumvitas/workflow/registry.py`

**Changes**:
- Remove `_gen_to_spec` dict construction
- Update any code that uses it to use `spec_from()` or `gen_from()`

---

### Step 3.3: Delete Obsolete Test Files

**Files to delete**:
- `tests/workflow/test_materialization_ssot.py` (if it exists and tests explicit mappings)

**Files to update**:
- Remove tests for `get_materialization_map()` from driver tests

---

## Phase 4: Update Golden Fixtures

### Step 4.1: Identify Affected Fixtures

**Commands to run**:
```bash
rg -l "w90_preproc|w90_run|pw2wannier90|bands_pw" tests/fixtures/ resources/
```

### Step 4.2: Regenerate Fixtures

Golden fixtures should be regenerated using updated code, not hand-edited.

```bash
# If fixture regeneration scripts exist:
python tools/regenerate_fixtures.py

# Or run the tests that generate fixtures:
.venv/bin/python -m pytest tests/ -k "golden" --regenerate-fixtures
```

### Step 4.3: Verify Minimal Diff

```bash
git diff tests/fixtures/
# Should only show GEN/SPEC name changes, no structural changes
```

---

## Phase 5: Final Verification

### Step 5.1: Run All Gate Tests

```bash
.venv/bin/python -m pytest tests/gates/test_step_type_constitution.py -v
```

**Expected**: All pass.

### Step 5.2: Run Full Test Suite

```bash
.venv/bin/python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

**Expected**: All pass.

### Step 5.3: Scan for Violations

```bash
# Check for remaining old names
rg "w90_preproc|w90_run|pw2wannier90|bands_pw" src/
# Should return empty

# Check for mapping patterns
rg "GEN_SCF|GEN_NSCF|get_materialization_map" src/
# Should return empty (or only in comments about removal)
```

---

## Rollback Plan

If any step causes irreparable failures:

1. `git stash` current changes
2. Identify the breaking change from test output
3. Fix forward (preferred) or revert specific changes
4. Re-run verification

---

## Summary Checklist

- [ ] Phase 1.1: Create GenStepRegistry
- [ ] Phase 1.2: Create step_type_convert module
- [ ] Phase 1.3: Add gate tests
- [ ] Phase 1.4: Full test suite passes
- [ ] Phase 2.1: Audit all occurrences
- [ ] Phase 2.2: Rename w90_preproc → wannierprep
- [ ] Phase 2.3: Rename w90_run → wannier
- [ ] Phase 2.4: Rename pw2wannier90 → pw2wannier
- [ ] Phase 2.5: Rename bands_pw → bandspw
- [ ] Phase 2.6: Update GenStepRegistry to final state
- [ ] Phase 2.7: Unskip Gate G1
- [ ] Phase 2.8: Add Wannier90 engine ownership gate
- [ ] Phase 3.1: Remove get_materialization_map() from all drivers
- [ ] Phase 3.2: Remove _gen_to_spec from StepTypeRegistry
- [ ] Phase 3.3: Delete obsolete test files
- [ ] Phase 4.1: Identify affected fixtures
- [ ] Phase 4.2: Regenerate fixtures
- [ ] Phase 4.3: Verify minimal diff
- [ ] Phase 5.1: All gate tests pass
- [ ] Phase 5.2: Full test suite passes
- [ ] Phase 5.3: No violations found in scan
