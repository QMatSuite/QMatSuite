# Migration Gates and Test Contract

**Version**: 1.0
**Status**: SPECIFICATION

---

## 1. Overview

This document specifies the gates (required conditions) and tests that must pass before and during engine driver migration. Migration proceeds one engine per PR with explicit rollback capability.

---

## 2. Pre-Migration Gate (Gate Zero)

Before ANY engine migration begins, these conditions MUST be met:

### 2.1 Required Changes

| ID | Requirement | Verification |
|----|-------------|--------------|
| G0-1 | Remove all `startswith` on step_type in routing code | `grep -r "startswith.*step" --include="*.py" src/` returns 0 hits |
| G0-2 | Remove all `.get(..., default)` in routing lookups | Code review + grep |
| G0-3 | Add `UnknownStepTypeError` exception class | Exception exists in codebase |
| G0-4 | All routing paths raise on unknown type | Test coverage |
| G0-5 | Driver protocol defined | `engine_driver_protocol.py` exists |
| G0-6 | Registry infrastructure exists | `driver_registry.py` exists |

### 2.2 Gate Zero Tests

```python
# tests/test_gate_zero.py

class TestGateZeroNoFallbacks:
    """Gate Zero: Verify no silent fallbacks exist."""

    def test_unknown_step_type_raises(self):
        """Unknown step type must raise, not return default."""
        with pytest.raises(UnknownStepTypeError):
            determine_engine_family("nonexistent_step_type_xyz")

    def test_unknown_engine_raises(self):
        """Unknown engine must raise, not return default."""
        with pytest.raises(UnknownEngineError):
            get_driver("nonexistent_engine_xyz")

    def test_typo_step_type_raises(self):
        """Typos must raise, not silently route elsewhere."""
        # Common typos that might match prefix patterns
        typos = ["vaps_scf", "vasp_scff", "pw_scff", "orca_scff"]
        for typo in typos:
            with pytest.raises(UnknownStepTypeError):
                determine_engine_family(typo)

    def test_no_prefix_inference(self):
        """New prefix must not infer to existing engine."""
        # vasp_* exists, but vasp_newtype should fail
        with pytest.raises(UnknownStepTypeError):
            determine_engine_family("vasp_newtype_not_registered")


class TestGateZeroCodeScan:
    """Gate Zero: Static analysis of prohibited patterns."""

    def test_no_startswith_on_step_type(self):
        """No startswith pattern matching on step types."""
        # This would be implemented as a custom linter or grep check
        prohibited_patterns = [
            r'\.startswith\(["\']vasp',
            r'\.startswith\(["\']qe',
            r'\.startswith\(["\']orca',
            r'\.startswith\(["\']pyscf',
            r'\.startswith\(["\']lammps',
            r'\.startswith\(["\']cp2k',
            r'\.startswith\(["\']pw_',
        ]
        # Implementation: scan src/ for these patterns
        violations = scan_for_patterns(prohibited_patterns)
        assert not violations, f"Found prohibited patterns: {violations}"

    def test_no_silent_get_defaults(self):
        """No .get() with engine/step defaults in routing."""
        # Scan for patterns like: .get(step_type, "qe")
        # Implementation detail
        pass
```

### 2.3 Gate Zero CI Job

```yaml
# .github/workflows/gate_zero.yml
name: Gate Zero Verification

on: [push, pull_request]

jobs:
  gate-zero:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Check no startswith patterns
        run: |
          if grep -rn "startswith.*step\|startswith.*vasp\|startswith.*qe\|startswith.*orca" \
             --include="*.py" src/quantumvitas/core/ src/quantumvitas/execution/; then
            echo "FAIL: Found prohibited startswith patterns"
            exit 1
          fi

      - name: Check no silent fallbacks
        run: |
          # Custom script to detect .get(x, default) in routing code
          python scripts/check_no_fallbacks.py

      - name: Run Gate Zero tests
        run: pytest tests/test_gate_zero.py -v
```

---

## 3. Per-Engine Migration Gate

For each engine migration PR, these gates must pass:

### 3.1 Pre-Merge Requirements

| ID | Requirement | Verification |
|----|-------------|--------------|
| E-1 | Driver bundle created | `drivers/<engine>/` exists |
| E-2 | Driver implements MUST interface | Type check passes |
| E-3 | Driver registered | Registration test passes |
| E-4 | All engine's step types registered | Introspection test |
| E-5 | Existing tests pass | CI green |
| E-6 | No kernel files modified | PR diff check |
| E-7 | Rollback tested | Rollback test passes |

### 3.2 Per-Engine Tests

```python
# tests/test_engine_migration.py

class TestDriverRegistration:
    """Verify driver is properly registered."""

    @pytest.mark.parametrize("engine", ["vasp", "qe", "orca", "pyscf", "lammps", "cp2k"])
    def test_driver_registered(self, engine):
        """Driver must be registered after import."""
        from quantumvitas import drivers  # Triggers discovery
        assert DriverRegistry.is_valid_engine(engine)

    @pytest.mark.parametrize("engine", ["vasp", "qe", "orca", "pyscf", "lammps", "cp2k"])
    def test_driver_has_step_types(self, engine):
        """Driver must register at least one step type."""
        step_types = DriverRegistry.list_step_types(engine)
        assert len(step_types) > 0, f"Engine {engine} has no step types"

    @pytest.mark.parametrize("engine", ["vasp", "qe", "orca", "pyscf", "lammps", "cp2k"])
    def test_step_types_resolve_to_driver(self, engine):
        """All step types must resolve back to the driver."""
        step_types = DriverRegistry.list_step_types(engine)
        for st in step_types:
            driver = DriverRegistry.get_driver_for_step_type(st)
            assert driver.engine_family == engine


class TestNoKernelModification:
    """Verify engine-specific code not in kernel."""

    KERNEL_PATHS = [
        "src/quantumvitas/core/",
        "src/quantumvitas/execution/handlers.py",
        "src/quantumvitas/execution/recipes.py",
        "src/quantumvitas/workflow/generalized_steps.py",
    ]

    def test_no_engine_constants_in_kernel(self):
        """No hardcoded engine step type sets in kernel."""
        for path in self.KERNEL_PATHS:
            content = read_all_py_files(path)
            # Check for patterns like: VASP_STEP_TYPES = {...}
            assert "VASP_STEP_TYPES" not in content
            assert "ORCA_STEP_TYPES" not in content
            assert "LAMMPS_STEP_TYPES" not in content

    def test_no_engine_conditionals_in_kernel(self):
        """No if engine == 'vasp' style conditionals in kernel."""
        for path in self.KERNEL_PATHS:
            content = read_all_py_files(path)
            # Simplified check - real impl would parse AST
            assert 'engine == "vasp"' not in content
            assert 'engine == "qe"' not in content
            # ... etc
```

### 3.3 Kernel Modification Check

```yaml
# CI check for PRs adding/modifying engines

- name: Check no kernel modifications
  run: |
    # Get files changed in PR
    CHANGED=$(git diff --name-only origin/main...HEAD)

    # Check for kernel file modifications
    KERNEL_FILES="src/quantumvitas/core/calc_identity.py
    src/quantumvitas/execution/handlers.py
    src/quantumvitas/execution/recipes.py
    src/quantumvitas/workflow/generalized_steps.py
    src/quantumvitas/calculation/structure_steps.py
    src/quantumvitas/calculation/step_done.py"

    for f in $KERNEL_FILES; do
      if echo "$CHANGED" | grep -q "$f"; then
        echo "FAIL: Kernel file modified: $f"
        echo "Engine additions must not modify kernel files."
        exit 1
      fi
    done
```

---

## 4. Rollback Strategy

### 4.1 Rollback Mechanism

Each migration is reversible by:
1. Deleting the driver package
2. Re-enabling legacy code path (if still present during transition)

### 4.2 Rollback Test

```python
# tests/test_rollback.py

class TestRollbackCapability:
    """Verify system works if driver is removed."""

    def test_missing_driver_raises_clearly(self):
        """Unregistered engine gives clear error."""
        # Simulate driver not loaded
        DriverRegistry._drivers.pop("test_engine", None)

        with pytest.raises(UnknownEngineError) as exc:
            get_driver("test_engine")

        assert "test_engine" in str(exc.value)
        assert "Available engines" in str(exc.value)

    def test_legacy_path_available_during_transition(self):
        """Legacy handlers available during migration phase."""
        # During transition, both paths should work
        # This test is removed after migration complete
        pass
```

### 4.3 Rollback Procedure

```markdown
## Rollback Procedure for Engine X

1. Revert the merge commit:
   git revert <commit-hash>

2. Or manually:
   - Delete drivers/x/ directory
   - Remove x from drivers/__init__.py imports (if explicit)
   - Verify: pytest tests/ -k "not x_driver"

3. Deploy and verify:
   - All other engines still work
   - x engine gives clear "not available" error
```

---

## 5. Migration Order

### 5.1 Recommended Order

| Order | Engine | Rationale |
|-------|--------|-----------|
| 1 | ORCA | Clean chain pattern, well-isolated, low risk |
| 2 | PySCF | Similar to ORCA, validates chain pattern |
| 3 | VASP | Representative per-step engine, good test coverage |
| 4 | LAMMPS | Similar to VASP, validates per-step pattern |
| 5 | CP2K | Similar to LAMMPS, recent addition |
| 6 | QE | Oldest engine, deepest integration, highest risk |
| 7 | W90 | Cross-engine dependency (QE), migrate last |

### 5.2 Rationale

- **ORCA/PySCF first**: Clean isolation, validates chain recipe pattern
- **VASP/LAMMPS/CP2K middle**: Per-step workdir pattern, moderate coupling
- **QE last**: Oldest code, most fallback targets, requires most cleanup
- **W90 after QE**: Depends on QE outputs, must validate cross-engine

---

## 6. Test Contract

### 6.1 Required Tests for Each Driver

| Category | Tests Required |
|----------|----------------|
| Registration | Driver registers, step types register, no duplicates |
| Dispatch | Handler retrieved, recipe retrieved, materialization works |
| Execution | Smoke test with mock engine (if binary unavailable) |
| Errors | Unknown types raise, helpful messages |

### 6.2 Test File Structure

```
tests/
├── drivers/
│   ├── test_vasp_driver.py
│   ├── test_qe_driver.py
│   ├── test_orca_driver.py
│   └── ...
├── test_driver_registry.py
├── test_gate_zero.py
└── test_dispatch.py
```

### 6.3 Example Driver Test

```python
# tests/drivers/test_vasp_driver.py

class TestVASPDriverRegistration:
    def test_vasp_driver_registered(self):
        from quantumvitas import drivers
        assert DriverRegistry.is_valid_engine("vasp")

    def test_vasp_step_types_registered(self):
        step_types = DriverRegistry.list_step_types("vasp")
        assert "vasp_scf" in step_types
        assert "vasp_relax" in step_types
        assert "vasp_md" in step_types

    def test_vasp_materialization_registered(self):
        machine = DriverRegistry.materialize("vasp", "GEN_SCF")
        assert machine == "vasp_scf"


class TestVASPDriverDispatch:
    def test_vasp_handler_callable(self):
        driver = DriverRegistry.get_driver("vasp")
        handler = driver.get_handler()
        assert callable(handler)

    def test_vasp_recipe_instantiable(self):
        driver = DriverRegistry.get_driver("vasp")
        recipe_class = driver.get_recipe_class()
        # Should be instantiable (may need mock step)
        assert issubclass(recipe_class, BaseRecipe)


class TestVASPDriverCapabilities:
    def test_vasp_declares_capabilities(self):
        driver = DriverRegistry.get_driver("vasp")
        caps = driver.get_capabilities()
        assert "scf" in caps
        assert "relax" in caps

    def test_vasp_workdir_policy(self):
        driver = DriverRegistry.get_driver("vasp")
        policy = driver.get_workdir_policy()
        assert policy == WorkdirPolicy.CLEANUP
```

---

## 7. CI Pipeline

### 7.1 Full Test Matrix

```yaml
# .github/workflows/engine_integration.yml

name: Engine Integration Tests

on: [push, pull_request]

jobs:
  gate-zero:
    name: Gate Zero (No Fallbacks)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pytest tests/test_gate_zero.py -v

  registry-tests:
    name: Registry Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pytest tests/test_driver_registry.py -v

  driver-tests:
    name: Driver Tests
    runs-on: ubuntu-latest
    strategy:
      matrix:
        engine: [vasp, qe, orca, pyscf, lammps, cp2k]
    steps:
      - uses: actions/checkout@v4
      - run: pytest tests/drivers/test_${{ matrix.engine }}_driver.py -v

  dispatch-tests:
    name: Dispatch Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pytest tests/test_dispatch.py -v

  kernel-isolation:
    name: Kernel Isolation Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python scripts/check_kernel_isolation.py
```

### 7.2 PR Labels

| Label | Meaning |
|-------|---------|
| `engine-migration` | PR migrates an engine to driver model |
| `driver-new` | PR adds a new engine driver |
| `kernel-change` | PR modifies kernel (requires extra review) |

---

## 8. Success Criteria

### 8.1 Migration Complete When

- [ ] All 7 engines have driver bundles
- [ ] All Gate Zero tests pass
- [ ] No engine-specific code in kernel
- [ ] handlers.py is thin dispatcher (< 50 lines)
- [ ] recipes.py is thin dispatcher (< 50 lines)
- [ ] Legacy hardcoded step type sets removed
- [ ] All existing integration tests pass
- [ ] Documentation updated

### 8.2 Metrics

| Metric | Before | After |
|--------|--------|-------|
| handlers.py lines | ~1400 | < 50 |
| recipes.py lines | ~900 | < 50 |
| Files to modify for new engine | 5-7 | 0 (kernel) |
| Silent fallback paths | Multiple | 0 |
| Engine-specific sets in kernel | 5+ | 0 |
