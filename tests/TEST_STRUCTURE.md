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
├── tests/                    # Quick tests (CI)
│   ├── unit/                # Unit tests
│   ├── integration/         # Integration tests
│   ├── core/                # Test framework
│   └── conftest.py          # Pytest config
│
├── extended-tests/          # Extended tests (developer)
│   ├── suites/             # Test suites
│   │   └── qe_testsuite/   # QE official test-suite
│   ├── utils/              # Utilities
│   ├── conftest.py         # Pytest config
│   ├── run_all.py          # Run all extended tests
│   └── analyze_results.py  # Analyze results
│
└── pytest.ini              # Pytest configuration
```

## Running Tests

### Quick Tests (CI)
```bash
# Run all quick tests
pytest tests/ -m quick

# Run specific category
pytest tests/unit/
pytest tests/integration/
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

- `@pytest.mark.quick` - Quick tests (tests/)
- `@pytest.mark.extended` - Extended tests (extended-tests/)
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.requires_qe` - Requires QE installation
- `@pytest.mark.requires_test_suite` - Requires QE test-suite

## Migration Notes

- Quick tests: Keep in `tests/`, focus on speed
- Extended tests: Moved to `extended-tests/`, comprehensive
- Old scripts: `run_*_tests.py` still work but are for extended tests
- Framework: Shared in `tests/core/` and used by both

