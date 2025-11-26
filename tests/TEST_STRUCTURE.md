# Test Structure Overview

## Quick Tests vs Extended Tests

### Quick Tests (`tests/`)
- **Purpose**: Fast, focused tests that validate core functionality
- **CI**: Run automatically on every push/PR
- **Duration**: Should complete in < 5 minutes
- **Location**: `tests/`
- **Examples**:
  - Unit tests for input parsing
  - Module detection tests
  - Basic integration tests

### Extended Tests (`extended-tests/`)
- **Purpose**: Comprehensive tests based on full QE official test-suite
- **CI**: NOT run automatically (manual trigger or schedule only)
- **Duration**: Can take hours for full suite
- **Location**: `extended-tests/`
- **Examples**:
  - All QE test-suite categories
  - Success rate analysis
  - Regression testing

## Directory Structure

```
.
├── tests/                    # Quick tests (run in CI)
│   ├── unit/                # Pure Python/unit tests
│   ├── integration/         # QE integration via engine helpers
│   ├── cli/                 # QE integration triggered through the CLI
│   ├── core/                # Shared helpers
│   └── conftest.py          # Pytest config & auto-markers
│
├── extended-tests/          # Extended QE test-suite mirroring upstream
│   ├── suites/
│   │   └── qe_testsuite/
│   ├── utils/
│   ├── conftest.py
│   ├── run_all.py
│   └── analyze_results.py
│
└── pytest.ini              # Pytest configuration
```

## Running Tests

### Quick Tests (CI)
```bash
# Run all quick tests
pytest tests/ -m quick

# Run by slice
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
- On push to main/develop
- On pull requests
- Daily schedule

Extended tests run:
- On manual workflow dispatch
- On schedule (optional)
- NOT on every push/PR

See `.github/workflows/tests.yml` for details.

## Test Markers

- `@pytest.mark.quick` - Everything under `tests/`
- `@pytest.mark.extended` - Everything under `extended-tests/`
- `@pytest.mark.unit` - Pure Python/unit tests (no QE)
- `@pytest.mark.qe_core` - QE integration via engine helpers
- `@pytest.mark.qe_cli` - QE integration via the Typer CLI
- `@pytest.mark.requires_qe` - Legacy QE dependency marker
- `@pytest.mark.requires_test_suite` - Requires the official QE test-suite

## Migration Notes

- Quick tests: Keep in `tests/`, focus on speed
- Extended tests: Moved to `extended-tests/`, comprehensive
- Old scripts: `run_*_tests.py` still work but are for extended tests
- Framework: Shared in `tests/core/` and used by both

