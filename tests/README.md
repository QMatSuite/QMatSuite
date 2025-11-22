# Quick Tests

Quick tests for QuantumVITAS. These tests are **automatically run in CI** and should be fast and focused.

## Structure

```
tests/
├── unit/              # Unit tests (fast, isolated, no external dependencies)
├── integration/       # Integration tests (may require QE installation)
├── core/              # Test framework core (shared with extended-tests)
└── conftest.py        # Pytest configuration
```

## Important

**All tests that depend on QE test-suite have been moved to `extended-tests/`.**

Quick tests in `tests/` should:
- ✅ Be fast (< 1 minute each)
- ✅ Have no external dependencies (or minimal)
- ✅ Test core functionality
- ❌ NOT depend on QE test-suite
- ❌ NOT require full QE installation (unless marked)

## Running Tests

### Run all quick tests
```bash
pytest tests/ -m quick
```

### Run specific test type
```bash
pytest tests/unit/          # Unit tests only
pytest tests/integration/   # Integration tests only
```

### Run with coverage
```bash
pytest tests/ --cov=src/quantumvitas --cov-report=html
```

## Test Categories

### Unit Tests (`tests/unit/`)
- Fast, isolated tests
- Test individual components
- No external dependencies
- Examples:
  - `test_qe_input.py` - QE input parsing
  - `test_qe_modules.py` - Module detection
  - `test_qe_executable_detection.py` - Executable detection

### Integration Tests (`tests/integration/`)
- Test component interactions
- May require QE installation (marked with `@pytest.mark.requires_qe`)
- Should NOT require QE test-suite
- Examples:
  - `test_qe_engine.py` - Engine integration
  - `test_qe_executable_integration.py` - Executable integration

## Markers

Tests are automatically marked based on location:
- `@pytest.mark.quick` - Quick tests (tests/)
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.requires_qe` - Requires QE installation (but not test-suite)

## CI Integration

Quick tests run automatically in GitHub Actions on:
- Push to main/develop
- Pull requests
- Daily schedule

See `.github/workflows/tests.yml` for configuration.

## Extended Tests

For comprehensive tests based on QE official test-suite, see `../extended-tests/`.
Extended tests are **NOT run automatically in CI** and are intended for developers.
