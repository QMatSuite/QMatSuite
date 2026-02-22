# QE Migration: Test Gates and CI Strategy

> This document defines the test requirements, gates, and CI strategy for the QE migration.

---

## Test Categories

### 1. Unit Tests (Fast, No External Dependencies)
**Location**: `tests/unit/`
**Runtime**: < 2 minutes total
**Requirement**: MUST PASS for every PR

#### QE-Specific Unit Tests
| Test File | Description | PR Gate |
|-----------|-------------|---------|
| `test_qe_driver.py` | Driver registration, properties | PR 1+ |
| `test_qe_step_types.py` | Step type spec validation | PR 2+ |
| `test_qe_recipe.py` | Recipe materialization | PR 3+ |
| `test_qe_handler.py` | Handler logic (mocked engine) | PR 4+ |
| `test_qe_io_model.py` | QEModule, QEInput, etc. | PR 6+ |
| `test_qe_parser.py` | QE input parsing | PR 6+ |
| `test_qe_generator.py` | QE input generation | PR 6+ |
| `test_qe_ir_mapping.py` | IR↔QE param conversion | PR 7+ |

#### Kernel Unit Tests (Must Not Regress)
| Test File | Description | Critical For |
|-----------|-------------|--------------|
| `test_driver_registry.py` | Registry operations | All PRs |
| `test_step.py` | Step creation, validation | PR 10 |
| `test_calculation.py` | Calculation operations | PR 10 |
| `test_job_graph.py` | JobGraph creation | PR 3-4 |
| `test_executor.py` | Job execution | PR 4+ |

### 2. Integration Tests (Require QE Installation)
**Location**: `tests/integration/qe/`
**Runtime**: ~10 minutes total
**Requirement**: MUST PASS before merge, can run on dedicated CI job

#### QE Integration Tests
| Test File | Description | PR Gate |
|-----------|-------------|---------|
| `test_qe_scf_e2e.py` | Full SCF calculation | PR 4+ |
| `test_qe_relax_e2e.py` | Relax + artifact generation | PR 4+ |
| `test_qe_bands_e2e.py` | SCF→NSCF→bands workflow | PR 4+ |
| `test_qe_dos_e2e.py` | SCF→NSCF→dos workflow | PR 4+ |
| `test_qe_phonon_e2e.py` | Phonon workflow | PR 4+ |
| `test_qe_w90_e2e.py` | Wannier90 integration | PR 4+ |

### 3. Backward Compatibility Tests
**Location**: `tests/compat/`
**Requirement**: MUST PASS - ensures existing code works

#### Import Compatibility
```python
# test_qe_import_compat.py

def test_io_imports():
    """Old import paths must still work."""
    from qmatsuite.io import QEModule, QEInput
    from qmatsuite.io import QEInputParser, QEInputGenerator
    assert QEModule is not None
    assert QEInput is not None

def test_core_engines_imports():
    """Legacy engine imports must work."""
    from qmatsuite.core.engines import QuantumEspressoEngine
    assert QuantumEspressoEngine is not None

def test_execution_imports():
    """Legacy execution imports must work."""
    from qmatsuite.execution.recipes import QERecipe
    from qmatsuite.execution.handlers import qe_step_handler
    assert QERecipe is not None
    assert qe_step_handler is not None

def test_ir_imports():
    """IR backend imports must work."""
    from qmatsuite.ir.backends.qe.mapping import ir_to_qe_param
    assert ir_to_qe_param is not None
```

#### Calculation Compatibility
```python
# test_qe_calculation_compat.py

def test_legacy_calculation_yaml_loads():
    """calculation.yaml with engine_family: qe must load."""
    # Load a legacy calculation.yaml
    # Verify it executes correctly
    pass

def test_legacy_step_yaml_loads():
    """step.yaml with step_type: qe_scf must load."""
    # Load a legacy step.yaml
    # Verify step executes
    pass
```

---

## Test Gates Per PR

### PR 1: Foundation
```bash
# REQUIRED
pytest tests/unit/ -v
pytest tests/unit/drivers/test_qe_driver.py -v

# EXPECTED: All pass, no new failures
```

### PR 2: Step Types
```bash
# REQUIRED
pytest tests/unit/ -v
pytest tests/unit/drivers/test_qe_step_types.py -v
pytest tests/unit/workflow/test_registry.py -v

# EXPECTED: All pass
```

### PR 3: Recipe
```bash
# REQUIRED
pytest tests/unit/ -v
pytest tests/unit/execution/test_recipes.py -v

# EXPECTED: All pass
```

### PR 4: Handler
```bash
# REQUIRED
pytest tests/unit/ -v
pytest tests/unit/execution/test_handlers.py -v

# INTEGRATION (if QE available)
pytest tests/integration/qe/ -v

# EXPECTED: All pass
```

### PR 5: Engine Files
```bash
# REQUIRED
pytest tests/unit/ -v
pytest tests/unit/core/engines/ -v

# INTEGRATION
pytest tests/integration/qe/ -v

# EXPECTED: All pass
```

### PR 6: I/O Layer
```bash
# REQUIRED
pytest tests/unit/ -v
pytest tests/unit/io/ -v

# COMPAT
pytest tests/compat/test_qe_import_compat.py -v

# EXPECTED: All pass
```

### PR 7: IR Backend
```bash
# REQUIRED
pytest tests/unit/ -v
pytest tests/unit/ir/ -v

# EXPECTED: All pass
```

### PR 8: Parsers/Data
```bash
# REQUIRED
pytest tests/unit/ -v
pytest tests/unit/parsers/ -v

# EXPECTED: All pass
```

### PR 9: Driver Registration
```bash
# REQUIRED
pytest tests/unit/ -v
pytest tests/unit/drivers/ -v

# INTEGRATION (CRITICAL)
pytest tests/integration/qe/ -v

# EXPECTED: All pass
```

### PR 10: Kernel Cleanup (CRITICAL)
```bash
# REQUIRED - FULL SUITE
pytest tests/ -v

# COMPAT (ALL)
pytest tests/compat/ -v

# MAY HAVE EXPECTED FAILURES
# Some legacy tests without explicit engine may fail
# These should be updated as part of the PR

# EXPECTED: All updated tests pass
```

### PR 11: Final Cleanup
```bash
# REQUIRED - FULL SUITE
pytest tests/ -v

# VERIFY NO DEAD IMPORTS
python -c "import qmatsuite; print('OK')"

# EXPECTED: All pass
```

---

## CI Configuration

### GitHub Actions Workflow

```yaml
# .github/workflows/qe-migration-tests.yml

name: QE Migration Tests

on:
  pull_request:
    paths:
      - 'src/qmatsuite/drivers/qe/**'
      - 'src/qmatsuite/drivers/qe_shim/**'
      - 'src/qmatsuite/core/engines/qe*.py'
      - 'src/qmatsuite/execution/**'
      - 'src/qmatsuite/io/**'
      - 'src/qmatsuite/ir/backends/qe/**'
      - 'src/qmatsuite/parsers/qe/**'

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      - name: Run unit tests
        run: |
          pytest tests/unit/ -v --tb=short

  compat-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      - name: Run compatibility tests
        run: |
          pytest tests/compat/ -v --tb=short

  integration-tests:
    runs-on: ubuntu-latest
    # Only run if QE is available
    if: ${{ vars.QE_AVAILABLE == 'true' }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      - name: Setup QE
        run: |
          # Download and setup QE for testing
          # Or use cached QE installation
          echo "QE setup would go here"
      - name: Run integration tests
        run: |
          pytest tests/integration/qe/ -v --tb=short
```

---

## Test Data and Fixtures

### QE Test Fixtures

```python
# tests/conftest.py

import pytest
from pathlib import Path


@pytest.fixture
def qe_scf_input_path(tmp_path):
    """Create a minimal QE SCF input file."""
    input_content = """
&CONTROL
    calculation = 'scf'
    prefix = 'test'
    outdir = './outdir'
    pseudo_dir = './'
/
&SYSTEM
    ibrav = 0
    nat = 2
    ntyp = 1
    ecutwfc = 30.0
/
&ELECTRONS
    conv_thr = 1.0d-6
/
ATOMIC_SPECIES
  Si  28.0855  Si.pbe-n-kjpaw_psl.1.0.0.UPF

ATOMIC_POSITIONS crystal
  Si  0.0  0.0  0.0
  Si  0.25 0.25 0.25

CELL_PARAMETERS angstrom
  5.43  0.0   0.0
  0.0   5.43  0.0
  0.0   0.0   5.43

K_POINTS automatic
  4 4 4 0 0 0
"""
    input_file = tmp_path / "scf.in"
    input_file.write_text(input_content)
    return input_file


@pytest.fixture
def qe_driver():
    """Get QE driver instance."""
    from qmatsuite.drivers.qe import QEDriver
    return QEDriver()


@pytest.fixture
def mock_qe_engine(mocker):
    """Mock QE engine for unit tests."""
    mock = mocker.MagicMock()
    mock.run_step.return_value = mocker.MagicMock(
        success=True,
        output_file=Path("/tmp/test.out"),
        return_code=0,
    )
    return mock
```

---

## Known Test Gaps

### Tests to Create During Migration

| Test | Description | Priority |
|------|-------------|----------|
| `test_qe_workdir_policy.py` | Verify shared outdir behavior | HIGH |
| `test_qe_prefix_management.py` | Verify managed prefix parameter | HIGH |
| `test_qe_pseudo_resolution.py` | Verify pseudo_dir handling | HIGH |
| `test_qe_w90_handoff.py` | QE→W90 workflow handoff | MEDIUM |
| `test_qe_ir_roundtrip.py` | IR compile → parse roundtrip | MEDIUM |

### Tests That May Need Updates

| Test | Reason | Action |
|------|--------|--------|
| Tests creating Step without engine | Default removed | Add explicit `engine="qe"` |
| Tests assuming QE as default | Default removed | Add explicit engine |
| Tests with hardcoded import paths | Paths changed | Update imports |

---

## Rollback Criteria

### When to Rollback

1. **Unit test pass rate drops below 95%** - Investigate before merge
2. **Integration tests fail consistently** - Do not merge
3. **Compatibility tests fail** - Fix before merge
4. **Production calculation fails** - Rollback immediately

### Rollback Procedure

```bash
# Identify the problematic PR
git log --oneline -20

# Revert the specific PR
git revert <commit-hash>

# Or revert to known good state
git checkout <good-commit> -- src/qmatsuite/drivers/qe/

# Run full test suite to verify
pytest tests/ -v
```

---

## Success Metrics

### Per-PR Metrics
- All unit tests pass (100%)
- All compatibility tests pass (100%)
- Integration tests pass (if QE available)
- No new deprecation warnings (unless intentional)

### Final Validation Metrics
- All 54 files with QE references updated or migrated
- Zero QE-specific logic in kernel (grep verification)
- All existing calculations execute successfully
- Performance within 5% of pre-migration baseline

### Verification Commands

```bash
# Verify no QE defaults in kernel
grep -r '"qe"' src/qmatsuite/calculation/ src/qmatsuite/core/ \
  --include="*.py" | grep -v "test_" | grep -v "__pycache__"
# Expected: Empty or only in comments

# Verify driver registration
python -c "
from qmatsuite.core.driver_registry import DriverRegistry
import qmatsuite.drivers
d = DriverRegistry.get_driver('qe')
print(f'Driver: {d.__class__.__name__}')
print(f'Step types: {len(d.get_step_type_specs())}')
"
# Expected: Driver: QEDriver, Step types: 20+

# Verify backward compat imports
python -c "
from qmatsuite.io import QEModule, QEInput
from qmatsuite.core.engines import QuantumEspressoEngine
from qmatsuite.execution.recipes import QERecipe
print('All backward compat imports work')
"
# Expected: Prints success message
```
