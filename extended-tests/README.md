# Extended Tests

Extended tests are comprehensive tests based on the full QE official test-suite.
These tests are **not run automatically in CI** and are intended for developers.

## Purpose

- Full validation against QE official test-suite
- Success rate analysis
- Regression testing
- Performance benchmarking

## Structure

```
extended-tests/
├── suites/              # Test suites (same structure as tests/suites)
│   └── qe_testsuite/   # QE official test-suite integration
├── utils/              # Shared utilities
└── run_all.py          # Run all extended tests
```

## Usage

### Run all extended tests
```bash
pytest extended-tests/ -m extended
```

### Run specific module
```bash
python3 extended-tests/run_all.py --suite qe-pw
```

### Analyze results
```bash
python3 extended-tests/analyze_results.py results.json
```

## Requirements

- QE installation with test-suite
- Sufficient disk space for test outputs
- Longer execution time (hours for full suite)

## CI Integration

Extended tests are **excluded** from GitHub Actions by default.
To run them manually in CI, use:
```bash
pytest extended-tests/ -m extended --ci
```

