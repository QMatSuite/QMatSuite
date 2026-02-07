# M3: Companion Allowlist Routing

## Scope

Rewrite `materialize_public_step_key()` and `materialize_workflow()` to use the companion allowlist (COMPANION_ENGINES from M0) instead of StepTypeRegistry first-match. Add a helper method to DriverRegistry. Write 2 gate tests.

## Prerequisites

M0 (ENGINE_ROLE + COMPANION_ENGINES on all drivers), M1 (demos fixed), and M2 (no silent QE fallbacks) must be complete.

## Exact File List

### Modify

1. `src/quantumvitas/workflow/generalized_steps.py` — Rewrite `materialize_public_step_key`, update `materialize_workflow`
2. `src/quantumvitas/core/driver_registry.py` — Add `resolve_companion_step()` classmethod

### Create

3. `tests/gates/test_companion_routing.py`
4. `tests/workflow/test_companion_materialize.py`

## Do NOT Touch

- `src/quantumvitas/drivers/` (already done in M0)
- `src/quantumvitas/daemon/server.py` (that's M4)
- GUI files
- `src/quantumvitas/core/driver_protocol.py` (already done in M0)
- `src/quantumvitas/workflow/registry.py` (StepTypeRegistry stays as-is; we stop USING it for cross-engine resolution)

## Exact Instructions

### Step 1: Add `resolve_companion_step()` to DriverRegistry

In `src/quantumvitas/core/driver_registry.py`, add a new classmethod after `materialize_step_type()` (after line ~328):

```python
@classmethod
def resolve_companion_step(cls, engine_family: str, gen_step: str) -> str | None:
    """Resolve a gen step through companion engines.

    Tries the base engine first, then iterates COMPANION_ENGINES.

    Args:
        engine_family: Base engine family (e.g., 'qe')
        gen_step: Generalized step name (e.g., 'wannierprep')

    Returns:
        Engine-specific step type (e.g., 'w90_wannierprep'), or None if
        not supported by base engine or any companion.
    """
    instance = cls.get_instance()

    if engine_family not in instance._drivers:
        from quantumvitas.core.driver_exceptions import UnknownEngineError
        raise UnknownEngineError(engine_family, list(instance._drivers.keys()))

    gen_lower = gen_step.lower()
    if gen_lower.startswith("gen_"):
        gen_lower = gen_lower[4:]

    # 1. Try base engine
    mat_map = instance._materialization_maps.get(engine_family, {})
    if gen_lower in mat_map:
        return mat_map[gen_lower]

    # 2. Try each companion engine
    driver = instance._drivers[engine_family]
    companions = getattr(driver, 'COMPANION_ENGINES', frozenset())
    for companion in sorted(companions):  # sorted for determinism
        comp_map = instance._materialization_maps.get(companion, {})
        if gen_lower in comp_map:
            return comp_map[gen_lower]

    return None
```

### Step 2: Rewrite `materialize_public_step_key()` in generalized_steps.py

Replace the entire function body (lines 161-207) with:

```python
def materialize_public_step_key(
    public_step_key: str,
    engine_family: str,
) -> Optional[str]:
    """
    Materialize a PUBLIC step key to MACHINE step type.

    Uses companion allowlist routing:
    1. Try base engine's materialization map
    2. Try each companion engine's materialization map
    3. Return None if no match (caller decides if it's a zero-mapping or error)

    SSOT: Uses DriverRegistry.resolve_companion_step() for all mappings.
    The StepTypeRegistry is NOT used for cross-engine first-match resolution.

    Args:
        public_step_key: PUBLIC step key (e.g., "scf", "wannierprep", "vmc")
        engine_family: Engine family identifier (e.g., "qe", "vasp")

    Returns:
        MACHINE step type (e.g., "qe_scf", "w90_wannierprep"), or None if unsupported
    """
    # Normalize to lowercase gen step name
    gen_lower = public_step_key.lower()
    if gen_lower.startswith("gen_"):
        gen_lower = gen_lower[4:]

    return DriverRegistry.resolve_companion_step(engine_family, gen_lower)
```

**Key change**: The old code called `registry.get(public_step_key)` from `StepTypeRegistry` as a first-match lookup. This is DELETED. All resolution now goes through `DriverRegistry.resolve_companion_step()`, which respects the companion allowlist.

### Step 3: Update `materialize_workflow()` (NO CHANGES NEEDED)

`materialize_workflow()` already delegates to `materialize_public_step_key()`. It handles zero-mappings via `_is_zero_mapping()`. No changes needed here — the rewrite of `materialize_public_step_key` is sufficient.

Verify that `materialize_workflow()` still works by checking that its signature is:
```python
def materialize_workflow(generalized_steps: list[str], engine_family: str) -> list[str]:
```

If `engine_family` is None, `materialize_workflow` will fail at `DriverRegistry.resolve_companion_step()` which raises `UnknownEngineError`. This is correct — workflows require DECIDED state.

### Step 4: Remove unused StepTypeRegistry import

In `generalized_steps.py`, remove or guard the import:
```python
# DELETE this import (was used by old materialize_public_step_key):
# from quantumvitas.workflow.registry import get_registry
```

Only remove if no other function in the file uses it. If `dematerialize_step` or other functions still use `StepTypeRegistry`, keep the import but remove it from `materialize_public_step_key` specifically.

### Step 5: Write gate test — test_companion_routing.py

Create `tests/gates/test_companion_routing.py`:

```python
"""
Gate: Law EF3 — Companion Allowlist Routing.

materialize_public_step_key must use companion allowlist, not StepTypeRegistry first-match.
"""
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
GENERALIZED_STEPS_PATH = REPO_ROOT / "src" / "quantumvitas" / "workflow" / "generalized_steps.py"


def test_no_step_type_registry_in_materialize():
    """materialize_public_step_key must not use StepTypeRegistry for resolution."""
    text = GENERALIZED_STEPS_PATH.read_text(encoding="utf-8")

    # Find the materialize_public_step_key function body
    # Look for usage of registry.get() or get_registry() inside this function
    in_func = False
    violations = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if "def materialize_public_step_key" in line:
            in_func = True
            continue
        if in_func and line.strip() and not line[0].isspace() and not line.strip().startswith("#"):
            # Hit next top-level def/class — stop
            break
        if in_func:
            if "get_registry" in line or "registry.get(" in line:
                violations.append(f"  generalized_steps.py:{lineno}  {line.strip()}")

    assert not violations, (
        "EF3 violation — materialize_public_step_key still uses StepTypeRegistry:\n"
        + "\n".join(violations)
    )


def test_companion_routing_for_qe():
    """QE companion steps resolve through DriverRegistry, not first-match."""
    from quantumvitas.core.driver_registry import DriverRegistry
    import quantumvitas.drivers

    # w90 is a companion of QE
    result = DriverRegistry.resolve_companion_step("qe", "wannierprep")
    assert result == "w90_wannierprep", f"Expected 'w90_wannierprep', got '{result}'"

    result = DriverRegistry.resolve_companion_step("qe", "wannier")
    assert result == "w90_wannier", f"Expected 'w90_wannier', got '{result}'"

    # qmcpack is a companion of QE
    result = DriverRegistry.resolve_companion_step("qe", "vmc")
    assert result == "qmcpack_vmc", f"Expected 'qmcpack_vmc', got '{result}'"

    # yambo is a companion of QE
    result = DriverRegistry.resolve_companion_step("qe", "setup")
    assert result == "yambo_setup", f"Expected 'yambo_setup', got '{result}'"


def test_no_companion_routing_for_vasp():
    """VASP has no companions. Companion steps should return None."""
    from quantumvitas.core.driver_registry import DriverRegistry
    import quantumvitas.drivers

    result = DriverRegistry.resolve_companion_step("vasp", "wannierprep")
    assert result is None, f"Expected None for VASP+wannierprep, got '{result}'"

    result = DriverRegistry.resolve_companion_step("vasp", "vmc")
    assert result is None, f"Expected None for VASP+vmc, got '{result}'"


def test_base_steps_still_resolve():
    """Base engine steps still resolve normally through companion routing."""
    from quantumvitas.core.driver_registry import DriverRegistry
    import quantumvitas.drivers

    assert DriverRegistry.resolve_companion_step("qe", "scf") == "qe_scf"
    assert DriverRegistry.resolve_companion_step("vasp", "scf") == "vasp_scf"
    assert DriverRegistry.resolve_companion_step("orca", "scf") == "orca_scf"
```

### Step 6: Write integration test — test_companion_materialize.py

Create `tests/workflow/test_companion_materialize.py`:

```python
"""
Integration tests for companion allowlist materialization.

Verifies that materialize_public_step_key and materialize_workflow
use the companion allowlist correctly.
"""
import pytest

from quantumvitas.workflow.generalized_steps import (
    materialize_public_step_key,
    materialize_workflow,
    get_supported_generalized_steps,
)


class TestMaterializePublicStepKey:
    """Test materialize_public_step_key with companion routing."""

    def test_base_step_qe(self):
        assert materialize_public_step_key("scf", "qe") == "qe_scf"

    def test_base_step_vasp(self):
        assert materialize_public_step_key("scf", "vasp") == "vasp_scf"

    def test_companion_step_w90_via_qe(self):
        """W90 steps resolve through QE's companion allowlist."""
        assert materialize_public_step_key("wannierprep", "qe") == "w90_wannierprep"
        assert materialize_public_step_key("wannier", "qe") == "w90_wannier"

    def test_companion_step_qmcpack_via_qe(self):
        """QMCPACK steps resolve through QE's companion allowlist."""
        assert materialize_public_step_key("vmc", "qe") == "qmcpack_vmc"
        assert materialize_public_step_key("dmc", "qe") == "qmcpack_dmc"

    def test_companion_step_yambo_via_qe(self):
        """Yambo steps resolve through QE's companion allowlist."""
        result = materialize_public_step_key("setup", "qe")
        assert result == "yambo_setup"

    def test_companion_step_not_on_vasp(self):
        """VASP has no companions — postproc steps return None."""
        assert materialize_public_step_key("wannierprep", "vasp") is None
        assert materialize_public_step_key("vmc", "vasp") is None

    def test_unsupported_step(self):
        """Unknown gen step returns None."""
        assert materialize_public_step_key("nonexistent_step", "qe") is None

    def test_case_insensitive(self):
        """Gen step names are case-insensitive."""
        assert materialize_public_step_key("SCF", "qe") == "qe_scf"
        assert materialize_public_step_key("Scf", "vasp") == "vasp_scf"


class TestMaterializeWorkflow:
    """Test materialize_workflow with companion routing."""

    def test_qe_basic_workflow(self):
        result = materialize_workflow(["scf", "nscf", "dos"], "qe")
        assert result == ["qe_scf", "qe_nscf", "qe_dos"]

    def test_qe_with_companion_steps(self):
        """QE workflow with W90 companion steps."""
        result = materialize_workflow(["scf", "nscf", "wannierprep", "wannier"], "qe")
        assert result == ["qe_scf", "qe_nscf", "w90_wannierprep", "w90_wannier"]

    def test_vasp_basic_workflow(self):
        result = materialize_workflow(["scf", "nscf", "relax"], "vasp")
        assert result == ["vasp_scf", "vasp_nscf", "vasp_relax"]

    def test_unsupported_step_raises(self):
        """Unsupported step (not in base or companions, not zero-mapped) raises."""
        with pytest.raises(ValueError, match="not supported"):
            materialize_workflow(["scf", "nonexistent"], "qe")
```

## Invariants to Preserve

- `materialize_public_step_key()` signature stays the same: `(public_step_key: str, engine_family: str) -> Optional[str]`
- `materialize_workflow()` signature stays the same: `(generalized_steps: list[str], engine_family: str) -> list[str]`
- Zero-mapping logic (`_is_zero_mapping`) is NOT changed
- `dematerialize_step()` and `dematerialize_to_generalized_step()` are NOT changed
- `get_supported_generalized_steps()` and `get_engine_families_for_step()` are NOT changed
- StepTypeRegistry still exists and works — it just isn't used for cross-engine first-match in `materialize_public_step_key`
- No driver code is modified
- DriverRegistry is NOT modified except for the new `resolve_companion_step()` classmethod

## Verifiers

```bash
# 1. Gate test passes
source .venv/bin/activate && python -m pytest tests/gates/test_companion_routing.py -v

# 2. Integration tests pass
python -m pytest tests/workflow/test_companion_materialize.py -v

# 3. Verify StepTypeRegistry is not used in materialize_public_step_key
grep -n "get_registry\|registry.get" src/quantumvitas/workflow/generalized_steps.py
# Expected: Only appears in functions OTHER than materialize_public_step_key (if at all)

# 4. Full test suite
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

## Do NOT Do

- Do NOT modify any driver files (M0 already added ENGINE_ROLE + COMPANION_ENGINES)
- Do NOT modify `materialize_workflow()` unless absolutely necessary
- Do NOT delete StepTypeRegistry or `src/quantumvitas/workflow/registry.py`
- Do NOT import driver modules directly in generalized_steps.py (use DriverRegistry only)
- Do NOT add new class attributes to drivers
- Do NOT modify daemon/server.py (that's M4)
- Do NOT add engine_family inference logic
- Do NOT create mapping dicts outside DriverRegistry

## Expected Failure Modes

1. **Breaking existing QE workflows**: The most common path (`materialize_public_step_key("scf", "qe")`) must still return `"qe_scf"`. If `resolve_companion_step` tries companions BEFORE the base engine, base steps may break.
2. **Forgetting to remove StepTypeRegistry usage**: If the old `registry.get(public_step_key)` call remains, cross-engine first-match is still active and the gate test will fail.
3. **Importing driver modules in generalized_steps.py**: Use `DriverRegistry.resolve_companion_step()`, NOT `from quantumvitas.drivers.qe.driver import ...`.
4. **Non-deterministic companion ordering**: Use `sorted(companions)` when iterating to ensure deterministic results across test runs.
5. **Breaking `dematerialize_step`**: This function uses `StepTypeRegistry` for reverse lookup. Do NOT change it — it still needs `StepTypeRegistry` for spec→gen resolution.
