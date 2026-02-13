# Testing Policy and Execution Guide

**Date**: 2026-01-18  
**Status**: ACTIVE

---

## Overview

This document describes the test execution policy for QMatSuite, including how engine-dependent integration tests are handled in CI and local development.

---

## Test Categories

### Unit Tests
- **Location**: `tests/unit/`
- **Markers**: `@pytest.mark.unit` (optional)
- **Requirements**: None (pure Python)
- **CI**: Always runs
- **Local**: Always runs

### Integration Tests
- **Location**: `tests/integration/`
- **Markers**: `@pytest.mark.integration`
- **Requirements**: Varies by test
- **CI**: Runs (with exclusions)
- **Local**: Runs (with skip logic)

### Engine-Dependent Real Integration Tests

These tests actually execute quantum chemistry engines and require external binaries:

| Engine | Test File | Marker | CI Policy | Local Policy |
|--------|-----------|--------|-----------|--------------|
| QE | `test_qe_relax_real.py` | `@pytest.mark.requires_qe` | **MUST RUN** (fails if QE missing) | Runs if QE available, fails if missing |
| ORCA | `test_orca_relax_real.py` | `@pytest.mark.requires_orca` | **EXCLUDED** | Skips if ORCA missing |
| PySCF | `test_pyscf_relax_real.py` | `@pytest.mark.requires_pyscf` | **EXCLUDED** | Skips if PySCF/berny missing |

---

## CI Execution Policy

### Command
```bash
pytest tests/ -m "not requires_orca and not requires_pyscf"
```

### Behavior
- **QE tests** (`requires_qe`): Included and **MUST PASS**. If QE is not available, tests will **FAIL** with clear error messages.
- **ORCA tests** (`requires_orca`): Excluded via marker filter
- **PySCF tests** (`requires_pyscf`): Excluded via marker filter
- **All other tests**: Run normally

### Rationale
- QE is the primary engine and is built/installed in CI
- ORCA and PySCF require external binaries that are not available in CI
- Excluding ORCA/PySCF prevents false failures when binaries are missing

---

## Local Development Execution Policy

### Recommended Command
```bash
# Run all tests (ORCA/PySCF will skip if dependencies missing)
pytest tests/ -v
```

### Behavior
- **QE tests**: Run if QE available, **FAIL** if QE missing (same as CI)
- **ORCA tests**: Run if ORCA binary available, **SKIP** with clear message if missing
- **PySCF tests**: Run if PySCF and berny optimizer available, **SKIP** with clear message if missing
- **All other tests**: Run normally

### Skip Detection

When running locally, watch for skip messages:

```
SKIPPED [1] tests/integration/test_orca_relax_real.py: ORCA not available: ...
SKIPPED [1] tests/integration/test_pyscf_relax_real.py: berny optimizer not installed...
```

**If you have ORCA/PySCF installed but see skips**, check:
1. ORCA: Is `orca` binary in PATH? Run `which orca`
2. PySCF: Is `pyscf` installed? Run `python -c "import pyscf"`
3. berny: Is `berny` optimizer installed? Run `python -c "import berny"`

**ORCA/PySCF tests should NOT be silently skipped if dependencies are installed.**

---

## Test Markers

Markers are defined in `pytest.ini`:

```ini
markers =
    requires_qe: Tests that require a QE installation (legacy marker used by extended-tests)
    requires_orca: Tests that require ORCA binary (will skip if not available)
    requires_pyscf: Tests that require PySCF with berny optimizer (will skip if not available)
```

---

## Running Specific Test Categories

### Run only unit tests
```bash
pytest tests/unit/ -v
```

### Run only QE integration tests
```bash
pytest tests/ -m "requires_qe" -v
```

### Run only ORCA tests (if available)
```bash
pytest tests/ -m "requires_orca" -v
```

### Run only PySCF tests (if available)
```bash
pytest tests/ -m "requires_pyscf" -v
```

### Run all except engine-dependent tests
```bash
pytest tests/ -m "not requires_qe and not requires_orca and not requires_pyscf" -v
```

---

## CI Configuration

The CI configuration (`.github/workflows/tests.yml`) runs:

```bash
pytest tests/ -m "not requires_orca and not requires_pyscf"
```

This ensures:
- QE tests always run (and fail if QE is missing)
- ORCA/PySCF tests are excluded (to avoid false failures)

---

## Troubleshooting

### QE tests failing in CI
- Check that QE is being built and staged correctly
- Verify `ENGINE_ID` and `QMATSUITE_ENGINE_DIR` are set
- Check that `pw.x` exists at the expected path

### ORCA/PySCF tests skipped locally when they should run
- Verify the binary/package is installed: `which orca` or `python -c "import pyscf; import berny"`
- Check that the skip logic in test fixtures is working correctly
- Review skip messages for specific error details

### Tests passing locally but failing in CI
- Ensure CI excludes ORCA/PySCF tests (check marker filter)
- Verify QE is available in CI (check build steps)
- Check for environment-specific issues (paths, permissions)

---

## Policy Summary

| Test Type | CI | Local |
|-----------|----|----|
| Unit tests | ✅ Run | ✅ Run |
| QE real integration | ✅ Run (fail if missing) | ✅ Run (fail if missing) |
| ORCA real integration | ❌ Excluded | ⚠️ Skip if missing |
| PySCF real integration | ❌ Excluded | ⚠️ Skip if missing |
| Other integration | ✅ Run | ✅ Run |

**Key Principle**: QE is required and must be available. ORCA/PySCF are optional and gracefully skip when unavailable.

