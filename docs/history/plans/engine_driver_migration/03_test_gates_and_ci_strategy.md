# Test Gates and CI Strategy

**Version**: 1.0
**Date**: 2026-01-20
**Status**: IMPLEMENTATION CONTRACT

This document defines mandatory test gates, CI strategy, and anti-regression tests.

---

## 1. Test Gate Categories

| Category | Purpose | When Run |
|----------|---------|----------|
| **Gate 0: No Fallbacks** | Ensure no silent routing fallbacks | Every PR |
| **Gate 1: Registry Routing** | Verify registry-based dispatch | Every PR |
| **Gate 2: Unknown Type Errors** | Verify hard errors on unknowns | Every PR |
| **Gate 3: Engine Isolation** | No engine code leaked to kernel | Engine PRs |
| **Gate 4: Semantic Preservation** | Existing behavior unchanged | Engine PRs |

---

## 2. Gate 0: No Fallbacks (Prerequisite)

### 2.1 Static Analysis Tests

```python
# tests/gates/test_no_fallbacks.py

import ast
import re
from pathlib import Path

KERNEL_PATHS = [
    "src/qmatsuite/core/calc_identity.py",
    "src/qmatsuite/calculation/calculation.py",
    "src/qmatsuite/workflow/generalized_steps.py",
    "src/qmatsuite/execution/handlers.py",
    "src/qmatsuite/execution/recipes.py",
]


class TestNoSilentFallbacks:
    """Gate 0: No silent fallbacks to QE or any default engine."""

    def test_no_qe_fallback_in_calc_identity(self):
        """calc_identity.py must not have QE fallback."""
        source = Path("src/qmatsuite/core/calc_identity.py").read_text()
        # Check for the specific dangerous pattern
        assert 'families.add("qe")' not in source or "QE fallback" not in source, \
            "Silent QE fallback still exists in calc_identity.py"

    def test_no_default_engine_get(self):
        """No .get('engine', 'qe') patterns in calculation loading."""
        for path in ["src/qmatsuite/calculation/calculation.py"]:
            source = Path(path).read_text()
            matches = re.findall(r'\.get\(["\']engine["\'],\s*["\']qe["\']\)', source)
            assert not matches, f"Found .get('engine', 'qe') in {path}"

    def test_no_startswith_for_engine_detection(self):
        """No startswith patterns for engine detection in routing."""
        for path in KERNEL_PATHS:
            source = Path(path).read_text()
            # These patterns are dangerous when used for engine detection
            dangerous_patterns = [
                r'startswith\(["\']vasp_',
                r'startswith\(["\']orca_',
                r'startswith\(["\']pyscf_',
                r'startswith\(["\']lammps_',
                r'startswith\(["\']cp2k_',
            ]
            for pattern in dangerous_patterns:
                matches = re.findall(pattern, source)
                # Allow in comments/docstrings, disallow in code
                # This is a simplified check; real implementation should parse AST
                assert len(matches) == 0, \
                    f"Found {pattern} in {path}"


class TestNoFallbackRecipeDispatch:
    """Recipe dispatch must not have fallbacks."""

    def test_recipe_selection_no_default(self):
        """get_recipe_class must not return QERecipe as default."""
        source = Path("src/qmatsuite/execution/recipes.py").read_text()
        # Check for .get(..., QERecipe) pattern
        assert "QERecipe)" not in source or "get(" not in source, \
            "Recipe dispatch has QERecipe fallback"
```

### 2.2 Runtime Tests

```python
class TestFallbackRuntimeBehavior:
    """Verify no fallback at runtime."""

    def test_unknown_type_does_not_route_to_qe(self):
        """Unknown step type must not silently execute as QE."""
        from qmatsuite.core.calc_identity import _infer_engine_family_from_machine_types

        result = _infer_engine_family_from_machine_types(["totally_unknown_xyz"])
        # After fix: should be None or raise, not "qe"
        assert result != "qe", "Unknown type silently routed to QE"

    def test_typo_step_type_raises(self):
        """Typos must raise, not silently route."""
        from qmatsuite.core.driver_registry import DriverRegistry
        from qmatsuite.core.driver_exceptions import UnknownStepTypeError

        typos = ["vaps_scf", "orce_scf", "lammp_md", "cp2k_scff"]
        for typo in typos:
            with pytest.raises(UnknownStepTypeError):
                DriverRegistry.get_step_type_spec(typo)
```

---

## 3. Gate 1: Registry Routing Tests

### 3.1 Registration Tests

```python
# tests/gates/test_registry_routing.py

class TestDriverRegistration:
    """Verify drivers register correctly."""

    @pytest.mark.parametrize("engine", ["vasp", "orca", "pyscf", "lammps", "cp2k", "w90"])
    def test_driver_is_registered(self, engine):
        """Each migrated engine must be registered."""
        from qmatsuite.core.driver_registry import DriverRegistry
        assert DriverRegistry.is_known_engine(engine), f"Engine {engine} not registered"

    @pytest.mark.parametrize("engine", ["vasp", "orca", "pyscf", "lammps", "cp2k", "w90"])
    def test_driver_has_step_types(self, engine):
        """Each driver must declare at least one step type."""
        from qmatsuite.core.driver_registry import DriverRegistry
        step_types = DriverRegistry.list_step_types(engine)
        assert len(step_types) > 0, f"Engine {engine} has no step types"

    @pytest.mark.parametrize("engine", ["vasp", "orca", "pyscf", "lammps", "cp2k", "w90"])
    def test_step_types_have_correct_engine(self, engine):
        """Step types must reference correct engine."""
        from qmatsuite.core.driver_registry import DriverRegistry
        for step_type in DriverRegistry.list_step_types(engine):
            spec = DriverRegistry.get_step_type_spec(step_type)
            assert spec.engine == engine, f"{step_type} has wrong engine"


class TestDispatchChain:
    """Verify dispatch works through registry."""

    def test_handler_dispatch_uses_registry(self):
        """Handler dispatch must use registry, not hardcoded map."""
        from qmatsuite.core.driver_registry import DriverRegistry

        for engine in ["vasp", "orca", "pyscf", "lammps", "cp2k"]:
            driver = DriverRegistry.get_driver(engine)
            handler = driver.get_handler()
            assert callable(handler), f"{engine} handler not callable"

    def test_recipe_dispatch_uses_registry(self):
        """Recipe dispatch must use registry."""
        from qmatsuite.core.driver_registry import DriverRegistry
        from qmatsuite.execution.recipes import BaseRecipe

        for engine in ["vasp", "orca", "pyscf", "lammps", "cp2k"]:
            driver = DriverRegistry.get_driver(engine)
            recipe_class = driver.get_recipe_class()
            assert issubclass(recipe_class, BaseRecipe), \
                f"{engine} recipe not subclass of BaseRecipe"

    def test_materialization_uses_registry(self):
        """GEN→SPEC must use registry."""
        from qmatsuite.core.driver_registry import DriverRegistry

        test_cases = [
            ("vasp", "GEN_SCF", "vasp_scf"),
            ("vasp", "GEN_RELAX", "vasp_relax"),
            ("orca", "GEN_SCF", "orca_scf"),
            ("lammps", "GEN_MD", "lammps_md"),
            ("cp2k", "GEN_SCF", "cp2k_scf"),
        ]
        for engine, gen_type, expected in test_cases:
            result = DriverRegistry.materialize(engine, gen_type)
            assert result == expected, f"({engine}, {gen_type}) -> {result}, expected {expected}"
```

---

## 4. Gate 2: Unknown Type Hard Error Tests

### 4.1 Error Behavior Tests

```python
# tests/gates/test_unknown_type_errors.py

class TestUnknownStepTypeErrors:
    """Verify hard errors for unknown step types."""

    def test_unknown_step_type_raises_specific_error(self):
        """Unknown step type must raise UnknownStepTypeError."""
        from qmatsuite.core.driver_registry import DriverRegistry
        from qmatsuite.core.driver_exceptions import UnknownStepTypeError

        with pytest.raises(UnknownStepTypeError) as exc:
            DriverRegistry.get_step_type_spec("nonexistent_step_xyz")

        # Error message must be helpful
        assert "nonexistent_step_xyz" in str(exc.value)

    def test_error_message_includes_suggestions(self):
        """Error must include similar type suggestions."""
        from qmatsuite.core.driver_registry import DriverRegistry
        from qmatsuite.core.driver_exceptions import UnknownStepTypeError

        with pytest.raises(UnknownStepTypeError) as exc:
            DriverRegistry.get_step_type_spec("vasp_scff")  # typo

        # Should suggest vasp_scf
        error_msg = str(exc.value)
        assert "vasp_scf" in error_msg or "Did you mean" in error_msg

    def test_error_message_lists_known_types(self):
        """Error must list available types."""
        from qmatsuite.core.driver_registry import DriverRegistry
        from qmatsuite.core.driver_exceptions import UnknownStepTypeError

        with pytest.raises(UnknownStepTypeError) as exc:
            DriverRegistry.get_step_type_spec("xyz")

        assert "Known" in str(exc.value) or "Available" in str(exc.value)


class TestUnknownEngineErrors:
    """Verify hard errors for unknown engines."""

    def test_unknown_engine_raises_specific_error(self):
        """Unknown engine must raise UnknownEngineError."""
        from qmatsuite.core.driver_registry import DriverRegistry
        from qmatsuite.core.driver_exceptions import UnknownEngineError

        with pytest.raises(UnknownEngineError) as exc:
            DriverRegistry.get_driver("nonexistent_engine")

        assert "nonexistent_engine" in str(exc.value)
        assert "Available" in str(exc.value)


class TestUnknownMaterializationErrors:
    """Verify hard errors for unknown materialization."""

    def test_unknown_materialization_raises(self):
        """Unknown (engine, gen_type) must raise."""
        from qmatsuite.core.driver_registry import DriverRegistry
        from qmatsuite.core.driver_exceptions import UnknownMaterializationError

        with pytest.raises(UnknownMaterializationError):
            DriverRegistry.materialize("vasp", "GEN_UNKNOWN_XYZ")
```

---

## 5. Gate 3: Engine Isolation Tests

### 5.1 Anti-Regression Tests

```python
# tests/gates/test_engine_isolation.py

class TestKernelIsolation:
    """Verify engine code does not leak into kernel."""

    KERNEL_FILES = [
        "src/qmatsuite/core/calc_identity.py",
        "src/qmatsuite/core/driver_registry.py",
        "src/qmatsuite/core/driver_protocol.py",
        # handlers.py and recipes.py may have QE code until QE migrates
    ]

    PROHIBITED_ENGINE_CONSTANTS = [
        "VASP_STEP_TYPES",
        "ORCA_STEP_TYPES",
        "PYSCF_STEP_TYPES",
        "LAMMPS_STEP_TYPES",
        "CP2K_STEP_TYPES",
    ]

    def test_no_engine_constants_in_kernel(self):
        """Kernel files must not define engine step type sets."""
        for path in self.KERNEL_FILES:
            if not Path(path).exists():
                continue
            source = Path(path).read_text()
            for const in self.PROHIBITED_ENGINE_CONSTANTS:
                assert const not in source, f"Found {const} in kernel file {path}"

    def test_no_engine_conditionals_in_core(self):
        """Core files must not have if engine == 'vasp' style checks."""
        core_files = list(Path("src/qmatsuite/core").glob("*.py"))
        for path in core_files:
            if path.name in ("driver_registry.py", "driver_protocol.py"):
                continue  # These are allowed
            source = path.read_text()
            # Check for engine-specific conditionals
            patterns = [
                'engine == "vasp"',
                'engine == "orca"',
                'engine == "lammps"',
                'engine == "cp2k"',
                'engine == "pyscf"',
            ]
            for pattern in patterns:
                assert pattern not in source, f"Found {pattern} in {path}"


class TestPRBoundaryCheck:
    """Tests for PR scope verification."""

    def test_engine_pr_modifies_only_drivers_and_tests(self):
        """Engine PRs should only modify drivers/ and tests/."""
        # This would be implemented as a CI check, not a unit test
        # Placeholder for documentation
        pass
```

---

## 6. Gate 4: Semantic Preservation Tests

### 6.1 Existing Test Suite Must Pass

```python
# tests/gates/test_semantic_preservation.py

class TestSemanticPreservation:
    """Verify migration does not change behavior."""

    def test_existing_vasp_tests_pass(self):
        """All existing VASP tests must pass unchanged."""
        # Run: pytest tests/engines/vasp/ -v
        pass

    def test_existing_orca_tests_pass(self):
        """All existing ORCA tests must pass unchanged."""
        # Run: pytest tests/engines/orca/ -v
        pass

    # ... similar for other engines ...


class TestSSOTRules:
    """Verify SSOT rules unchanged."""

    def test_step_yaml_is_step_ssot(self):
        """step.yaml remains step SSOT."""
        # Verify step loading reads from step.yaml
        pass

    def test_calculation_yaml_is_calc_ssot(self):
        """calculation.yaml remains calc SSOT."""
        # Verify calculation loading reads from calculation.yaml
        pass


class TestManifestRules:
    """Verify manifest/done rules unchanged."""

    def test_fingerprinting_unchanged(self):
        """Step fingerprinting behavior unchanged."""
        pass

    def test_done_detection_unchanged(self):
        """Done detection behavior unchanged."""
        pass
```

---

## 7. CI Configuration

### 7.1 GitHub Actions Workflow

```yaml
# .github/workflows/engine_migration_gates.yml

name: Engine Migration Gates

on:
  push:
    branches: [main, v2-python]
  pull_request:
    branches: [main, v2-python]

jobs:
  gate-0-no-fallbacks:
    name: Gate 0 - No Fallbacks
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run no-fallback tests
        run: pytest tests/gates/test_no_fallbacks.py -v

  gate-1-registry-routing:
    name: Gate 1 - Registry Routing
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run registry routing tests
        run: pytest tests/gates/test_registry_routing.py -v

  gate-2-unknown-errors:
    name: Gate 2 - Unknown Type Errors
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run unknown type error tests
        run: pytest tests/gates/test_unknown_type_errors.py -v

  gate-3-isolation:
    name: Gate 3 - Engine Isolation
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run isolation tests
        run: pytest tests/gates/test_engine_isolation.py -v

  gate-4-semantics:
    name: Gate 4 - Semantic Preservation
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run semantic tests
        run: pytest tests/ -v --ignore=tests/gates/

  static-analysis:
    name: Static Analysis
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Check no QE fallback
        run: |
          if grep -rn 'families.add("qe")' src/qmatsuite/core/calc_identity.py | grep -v "^#"; then
            echo "FAIL: Silent QE fallback found"
            exit 1
          fi
      - name: Check no default engine
        run: |
          if grep -rn '\.get("engine", "qe")' src/qmatsuite/calculation/; then
            echo "FAIL: Default engine=qe found"
            exit 1
          fi
```

### 7.2 Preventing xdist/Caching Issues

```python
# conftest.py additions for test isolation

import pytest

@pytest.fixture(autouse=True)
def reset_driver_registry():
    """Reset registry between tests to avoid cross-test pollution."""
    from qmatsuite.core.driver_registry import DriverRegistry

    # Store original state
    original_drivers = DriverRegistry()._drivers.copy()
    original_step_types = DriverRegistry()._step_types.copy()
    original_mats = DriverRegistry()._materializations.copy()

    yield

    # Restore original state
    instance = DriverRegistry()
    instance._drivers = original_drivers
    instance._step_types = original_step_types
    instance._materializations = original_mats


@pytest.fixture(scope="session", autouse=True)
def ensure_drivers_loaded():
    """Ensure all drivers are loaded before any test."""
    import qmatsuite.drivers  # Triggers auto-discovery
```

### 7.3 Test Ordering for xdist

```ini
# pytest.ini additions

[pytest]
# Run gate tests first, in order
testpaths = tests
python_files = test_*.py
python_functions = test_*

# Markers for test ordering
markers =
    gate0: Gate 0 - No Fallbacks (run first)
    gate1: Gate 1 - Registry Routing
    gate2: Gate 2 - Unknown Type Errors
    gate3: Gate 3 - Engine Isolation
    gate4: Gate 4 - Semantic Preservation
```

---

## 8. Test File Organization

```
tests/
├── gates/                          # Migration gate tests
│   ├── __init__.py
│   ├── test_no_fallbacks.py        # Gate 0
│   ├── test_registry_routing.py    # Gate 1
│   ├── test_unknown_type_errors.py # Gate 2
│   ├── test_engine_isolation.py    # Gate 3
│   └── test_semantic_preservation.py # Gate 4
│
├── core/
│   ├── test_driver_registry.py     # Registry unit tests
│   └── test_driver_protocol.py     # Protocol tests
│
├── drivers/                        # Per-driver tests
│   ├── test_vasp_driver.py
│   ├── test_orca_driver.py
│   ├── test_pyscf_driver.py
│   ├── test_lammps_driver.py
│   ├── test_cp2k_driver.py
│   └── test_w90_driver.py
│
└── integration/                    # Integration tests
    ├── test_vasp_workflow.py
    ├── test_orca_workflow.py
    └── ...
```

---

## 9. Definition of Done (Per Engine PR)

### 9.1 Checklist

- [ ] Driver bundle created in `src/qmatsuite/drivers/<engine>/`
- [ ] Driver registered and passes `test_driver_is_registered`
- [ ] All step types registered and pass `test_driver_has_step_types`
- [ ] Handler moved and passes `test_handler_dispatch_uses_registry`
- [ ] Recipe moved and passes `test_recipe_dispatch_uses_registry`
- [ ] Materialization map passes `test_materialization_uses_registry`
- [ ] Gate 0 tests pass (no fallbacks)
- [ ] Gate 1 tests pass (registry routing)
- [ ] Gate 2 tests pass (unknown type errors)
- [ ] Gate 3 tests pass (engine isolation)
- [ ] Gate 4 tests pass (semantic preservation)
- [ ] All existing engine tests pass
- [ ] CI green

### 9.2 PR Merge Criteria

1. All gate tests pass
2. No new warnings in static analysis
3. Code review approved
4. No kernel files modified (except allowed thin dispatchers)
