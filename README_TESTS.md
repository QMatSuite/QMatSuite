# Testing Guide

## Test Structure

QuantumVITAS uses a two-tier testing structure:

### 1. Quick Tests (`tests/`)
- **Purpose**: Fast, focused tests for core functionality
- **CI**: Run automatically on every push/PR
- **Duration**: < 5 minutes
- **Location**: `tests/`

### 2. Extended Tests (`extended-tests/`)
- **Purpose**: Comprehensive tests based on full QE official test-suite
- **CI**: NOT run automatically (manual trigger or schedule only)
- **Duration**: Hours for full suite
- **Location**: `extended-tests/`

## Running Tests

### Quick Tests (CI)

```bash
# Run all quick tests
pytest tests/ -m quick

# Run with coverage
pytest tests/ --cov=src/quantumvitas --cov-report=html

# Run individual slices
pytest -m unit
pytest -m qe_core
pytest -m qe_cli
```

### Extended Tests (Developer)

```bash
# Run all extended tests
pytest extended-tests/ -m extended

# Or use the runner script
python3 extended-tests/run_all.py --all

# Run specific module
python3 extended-tests/run_all.py --suite qe-pw

# Analyze results
python3 extended-tests/analyze_results.py results.json
```

## CI Configuration

### GitHub Actions

Quick tests run automatically:
- ✅ On push to main/develop
- ✅ On pull requests
- ✅ Daily schedule

Extended tests:
- ⏸️ Manual workflow dispatch only
- ⏸️ Optional schedule
- ❌ NOT on every push/PR

See `.github/workflows/tests.yml` for details.

## Test Markers

- `@pytest.mark.quick` - Quick tests (tests/)
- `@pytest.mark.extended` - Extended tests (extended-tests/)
- `@pytest.mark.unit` - Pure Python/unit tests
- `@pytest.mark.qe_core` - QE integration via engine helpers
- `@pytest.mark.qe_cli` - QE integration via Typer CLI
- `@pytest.mark.requires_qe` - Requires QE installation
- `@pytest.mark.requires_test_suite` - Requires QE test-suite

## Directory Structure

```
.
├── tests/                    # Quick tests (CI)
│   ├── unit/               # Unit tests (no QE)
│   ├── integration/        # QE engine integration
│   ├── cli/                # CLI-driven QE workflows
│   ├── core/               # Test framework
│   └── conftest.py         # Pytest config
│
├── extended-tests/         # Extended tests (developer)
│   ├── suites/            # Test suites
│   ├── utils/             # Utilities
│   ├── conftest.py        # Pytest config
│   ├── run_all.py         # Run all extended tests
│   └── analyze_results.py # Analyze results
│
└── pytest.ini             # Pytest configuration
```

## Adding New Tests

### Quick Test
1. Add test file to `tests/unit/` or `tests/integration/`
2. Use pytest format
3. Mark with `@pytest.mark.quick` (auto-marked by location)
4. Keep tests fast (< 1 minute each)

### Extended Test
1. Add to `extended-tests/suites/`
2. Implement TestSuite interface
3. Mark with `@pytest.mark.extended`
4. Can be slow (hours acceptable)

## Success Criteria

- **Quick tests**: Must pass for CI
- **Extended tests**: Success rate analysis, not blocking

