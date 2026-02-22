# M0: Driver Protocol + Gate Tests

## Scope

Add `ENGINE_ROLE` and `COMPANION_ENGINES` class attributes to all 15 engine drivers and BaseEngineDriver. Write 3 gate tests enforcing Laws EF6, EF8, EF9.

## Exact File List

### Modify

1. `src/qmatsuite/core/driver_protocol.py` — Add 2 class attributes to `BaseEngineDriver` (around line 161)
2. `src/qmatsuite/drivers/qe/driver.py`
3. `src/qmatsuite/drivers/vasp/driver.py`
4. `src/qmatsuite/drivers/abinit/driver.py`
5. `src/qmatsuite/drivers/cp2k/driver.py`
6. `src/qmatsuite/drivers/siesta/driver.py`
7. `src/qmatsuite/drivers/gpaw/driver.py`
8. `src/qmatsuite/drivers/orca/driver.py`
9. `src/qmatsuite/drivers/gaussian/driver.py`
10. `src/qmatsuite/drivers/psi4/driver.py`
11. `src/qmatsuite/drivers/pyscf/driver.py`
12. `src/qmatsuite/drivers/xtb/driver.py`
13. `src/qmatsuite/drivers/lammps/driver.py`
14. `src/qmatsuite/drivers/w90/driver.py`
15. `src/qmatsuite/drivers/qmcpack/driver.py`
16. `src/qmatsuite/drivers/yambo/driver.py`

### Create

17. `tests/gates/test_postproc_gen_uniqueness.py`
18. `tests/gates/test_companion_completeness.py`
19. `tests/gates/test_demo_integrity.py`

## Do NOT Touch

- `src/qmatsuite/api/service.py`
- `src/qmatsuite/daemon/server.py`
- `src/qmatsuite/core/driver_registry.py`
- Any GUI files
- Any workflow/ files

## Exact Instructions

### Step 1: Add defaults to BaseEngineDriver

In `src/qmatsuite/core/driver_protocol.py`, find `class BaseEngineDriver:` (line 161). Add these two class attributes immediately after the class docstring, before the first method (`get_workdir_policy`):

```python
    # ─────────────────────────────────────────────────────────────────────
    # Engine classification (per GUI_ENGINE_FAMILY_DEMO_SPEC.md v1.1)
    # ─────────────────────────────────────────────────────────────────────

    ENGINE_ROLE: str = "base"
    COMPANION_ENGINES: frozenset = frozenset()
```

### Step 2: Add attributes to each driver

In each of the 15 `drivers/<engine>/driver.py` files, find the line after `SUPPORTED_GEN_STEPS` and add `ENGINE_ROLE` + `COMPANION_ENGINES`.

**12 base engines** (qe, vasp, abinit, cp2k, siesta, gpaw, orca, gaussian, psi4, pyscf, xtb, lammps):
```python
    ENGINE_ROLE: str = "base"
    COMPANION_ENGINES: frozenset = frozenset()
```

**Exception — QE only**:
```python
    ENGINE_ROLE: str = "base"
    COMPANION_ENGINES: frozenset = frozenset({"w90", "qmcpack", "yambo"})
```

**3 postprocessing engines** (w90, qmcpack, yambo):
```python
    ENGINE_ROLE: str = "postprocessing"
    COMPANION_ENGINES: frozenset = frozenset()
```

### Step 3: Write gate test — test_postproc_gen_uniqueness.py

Create `tests/gates/test_postproc_gen_uniqueness.py`:

```python
"""
Gate: Law EF8 — Postprocessing Gen Step Global Uniqueness.

Every postprocessing engine's gen step names must be globally unique:
- No gen step name appears in >1 postprocessing engine's SUPPORTED_GEN_STEPS.
- No postprocessing gen step name appears in any base engine's SUPPORTED_GEN_STEPS.
"""
import pytest

def test_postproc_gen_steps_unique_across_postproc_engines():
    """No postprocessing gen step appears in more than one postproc engine."""
    from qmatsuite.core.driver_registry import DriverRegistry
    import qmatsuite.drivers

    postproc_engines = []
    for engine_family in DriverRegistry.get_all_engines():
        driver = DriverRegistry.get_driver(engine_family)
        if getattr(driver, 'ENGINE_ROLE', 'base') == 'postprocessing':
            postproc_engines.append((engine_family, driver.SUPPORTED_GEN_STEPS))

    seen = {}  # gen_step -> engine_family
    collisions = []
    for engine_family, gen_steps in postproc_engines:
        for g in gen_steps:
            if g in seen:
                collisions.append(f"  gen step '{g}' appears in both '{seen[g]}' and '{engine_family}'")
            else:
                seen[g] = engine_family

    assert not collisions, f"EF8 violation — postproc gen step collisions:\n" + "\n".join(collisions)


def test_postproc_gen_steps_not_in_base_engines():
    """No postprocessing gen step appears in any base engine's SUPPORTED_GEN_STEPS."""
    from qmatsuite.core.driver_registry import DriverRegistry
    import qmatsuite.drivers

    postproc_gen_steps = set()
    base_gen_steps = {}  # gen_step -> [engine_families]

    for engine_family in DriverRegistry.get_all_engines():
        driver = DriverRegistry.get_driver(engine_family)
        role = getattr(driver, 'ENGINE_ROLE', 'base')
        if role == 'postprocessing':
            postproc_gen_steps.update(driver.SUPPORTED_GEN_STEPS)
        else:
            for g in driver.SUPPORTED_GEN_STEPS:
                base_gen_steps.setdefault(g, []).append(engine_family)

    collisions = []
    for g in postproc_gen_steps:
        if g in base_gen_steps:
            collisions.append(f"  postproc gen step '{g}' also in base engines: {base_gen_steps[g]}")

    assert not collisions, f"EF8 violation — postproc/base gen step overlap:\n" + "\n".join(collisions)
```

### Step 4: Write gate test — test_companion_completeness.py

Create `tests/gates/test_companion_completeness.py`:

```python
"""
Gate: Laws EF3/EF9 — Companion Completeness.

1. Every engine in a base engine's COMPANION_ENGINES must have ENGINE_ROLE="postprocessing".
2. Every postprocessing engine must appear in at least one base engine's COMPANION_ENGINES.
3. COMPANION_ENGINES must be a frozenset.
"""
import pytest

def test_companion_engines_are_postprocessing():
    """Every engine listed in COMPANION_ENGINES must have ENGINE_ROLE='postprocessing'."""
    from qmatsuite.core.driver_registry import DriverRegistry
    import qmatsuite.drivers

    violations = []
    for engine_family in DriverRegistry.get_all_engines():
        driver = DriverRegistry.get_driver(engine_family)
        companions = getattr(driver, 'COMPANION_ENGINES', frozenset())
        for c in companions:
            if not DriverRegistry.is_engine_registered(c):
                violations.append(f"  {engine_family}.COMPANION_ENGINES references unregistered engine '{c}'")
                continue
            c_driver = DriverRegistry.get_driver(c)
            c_role = getattr(c_driver, 'ENGINE_ROLE', 'base')
            if c_role != 'postprocessing':
                violations.append(f"  {engine_family}.COMPANION_ENGINES includes '{c}' which has ENGINE_ROLE='{c_role}', not 'postprocessing'")

    assert not violations, f"EF3 violation:\n" + "\n".join(violations)


def test_every_postproc_engine_has_a_host():
    """Every postprocessing engine appears in at least one base engine's COMPANION_ENGINES."""
    from qmatsuite.core.driver_registry import DriverRegistry
    import qmatsuite.drivers

    postproc_engines = set()
    hosted_engines = set()

    for engine_family in DriverRegistry.get_all_engines():
        driver = DriverRegistry.get_driver(engine_family)
        role = getattr(driver, 'ENGINE_ROLE', 'base')
        if role == 'postprocessing':
            postproc_engines.add(engine_family)
        companions = getattr(driver, 'COMPANION_ENGINES', frozenset())
        hosted_engines.update(companions)

    orphans = postproc_engines - hosted_engines
    assert not orphans, f"EF9 violation — postproc engines not hosted by any base engine: {orphans}"


def test_companion_engines_is_frozenset():
    """COMPANION_ENGINES must be a frozenset on all drivers."""
    from qmatsuite.core.driver_registry import DriverRegistry
    import qmatsuite.drivers

    violations = []
    for engine_family in DriverRegistry.get_all_engines():
        driver = DriverRegistry.get_driver(engine_family)
        companions = getattr(driver, 'COMPANION_ENGINES', None)
        if companions is None:
            violations.append(f"  {engine_family}: missing COMPANION_ENGINES")
        elif not isinstance(companions, frozenset):
            violations.append(f"  {engine_family}: COMPANION_ENGINES is {type(companions).__name__}, not frozenset")

    assert not violations, f"Type violation:\n" + "\n".join(violations)


def test_engine_role_is_valid():
    """ENGINE_ROLE must be 'base' or 'postprocessing' on all drivers."""
    from qmatsuite.core.driver_registry import DriverRegistry
    import qmatsuite.drivers

    violations = []
    for engine_family in DriverRegistry.get_all_engines():
        driver = DriverRegistry.get_driver(engine_family)
        role = getattr(driver, 'ENGINE_ROLE', None)
        if role is None:
            violations.append(f"  {engine_family}: missing ENGINE_ROLE")
        elif role not in ('base', 'postprocessing'):
            violations.append(f"  {engine_family}: ENGINE_ROLE='{role}', must be 'base' or 'postprocessing'")

    assert not violations, f"Role violation:\n" + "\n".join(violations)
```

### Step 5: Write gate test — test_demo_integrity.py

Create `tests/gates/test_demo_integrity.py`:

```python
"""
Gate: Law EF6 — Demo Integrity.

Every demo snapshot must have:
1. engine_family explicitly set on each calculation.
2. Every step's step_type_spec prefix matches engine_family or a companion engine.
"""
import yaml
from pathlib import Path
import pytest

DEMO_DIR = Path(__file__).parent.parent.parent / "resources" / "demo_projects"


def _load_demo(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _get_prefix(step_type_spec: str) -> str:
    """Extract engine prefix from step_type_spec."""
    if "_" in step_type_spec:
        return step_type_spec.split("_", 1)[0]
    return step_type_spec


def test_all_demos_have_engine_family():
    """Every demo calculation must have explicit engine_family."""
    from qmatsuite.core.driver_registry import DriverRegistry
    import qmatsuite.drivers

    violations = []
    for yml_path in sorted(DEMO_DIR.glob("*.yml")):
        data = _load_demo(yml_path)
        for i, calc in enumerate(data.get("calculations", [])):
            ef = calc.get("engine_family")
            if ef is None:
                violations.append(f"  {yml_path.name}: calculations[{i}] missing engine_family")

    assert not violations, f"EF6 violation — demos missing engine_family:\n" + "\n".join(violations)


def test_demo_step_type_spec_matches_engine_family():
    """Every step's step_type_spec prefix must match engine_family or its companion engines."""
    from qmatsuite.core.driver_registry import DriverRegistry
    import qmatsuite.drivers

    violations = []
    for yml_path in sorted(DEMO_DIR.glob("*.yml")):
        data = _load_demo(yml_path)
        for calc in data.get("calculations", []):
            ef = calc.get("engine_family")
            if ef is None:
                continue  # Caught by other test

            # Build allowed prefixes: engine_family + companions
            allowed_prefixes = {ef}
            if DriverRegistry.is_engine_registered(ef):
                driver = DriverRegistry.get_driver(ef)
                companions = getattr(driver, 'COMPANION_ENGINES', frozenset())
                allowed_prefixes.update(companions)

            for step in calc.get("steps", []):
                spec = step.get("step_type_spec", "")
                prefix = _get_prefix(spec)
                if prefix not in allowed_prefixes:
                    step_name = step.get("meta", {}).get("name", "?")
                    violations.append(
                        f"  {yml_path.name}: step '{step_name}' has step_type_spec='{spec}' "
                        f"(prefix='{prefix}') but engine_family='{ef}' "
                        f"(allowed: {sorted(allowed_prefixes)})"
                    )

    assert not violations, f"EF6 violation — step_type_spec/engine_family mismatch:\n" + "\n".join(violations)
```

## Invariants to Preserve

- step.yaml stores ONLY step_type_spec (no gen in YAML)
- No modifications to service.py, server.py, or workflow/ files
- No silent fallbacks introduced
- ENGINE_ROLE and COMPANION_ENGINES are CLASS attributes (not instance attributes)
- COMPANION_ENGINES is frozenset, not set or list

## Verifiers

```bash
# 1. Full test suite
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile

# 2. New gate tests specifically
python -m pytest tests/gates/test_postproc_gen_uniqueness.py tests/gates/test_companion_completeness.py tests/gates/test_demo_integrity.py -v

# 3. Count driver attributes
grep -rn "ENGINE_ROLE" src/qmatsuite/drivers/*/driver.py | wc -l
# Expected: 15

grep -rn "COMPANION_ENGINES" src/qmatsuite/drivers/*/driver.py | wc -l
# Expected: 15
```

## Do NOT Do

- Do NOT modify driver_registry.py
- Do NOT modify service.py
- Do NOT modify server.py
- Do NOT fix demos (that's M1)
- Do NOT remove QE fallbacks (that's M2)
- Do NOT create new RPC handlers
- Do NOT modify GUI files
- Do NOT add ENGINE_ROLE to calculation.yaml schema
- Do NOT make COMPANION_ENGINES a mutable type (list or set)

## Expected Outputs

- 15 driver files with ENGINE_ROLE + COMPANION_ENGINES
- BaseEngineDriver with default values
- 3 new gate test files
- test_demo_integrity.py will FAIL (ORCA demos are still broken) — that's expected, mark those assertions as `pytest.mark.xfail` or skip for now. M1 will fix the demos.

**NOTE**: test_demo_integrity.py will fail until M1 fixes the demos. You have two options:
- Option A: Write the test but expect it to fail (don't mark xfail — let M1 fix it)
- Option B: Write the test with a note that 3 ORCA demos + 17 demos without engine_family will fail

Choose Option A: write the test as-is. M0 verifies by running the gate tests for postproc uniqueness and companion completeness (which should pass). The demo integrity gate is written now but will only fully pass after M1.
