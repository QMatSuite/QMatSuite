# Testing Guide

## Test Structure

QuantumVITAS uses a two-tier testing structure:

### 1. Quick Tests (`tests/`)
- **Purpose**: Fast, focused tests for core functionality
- **CI**: Run automatically on every push/PR
- **Duration**: < 5 minutes
- **Location**: `tests/`

### 2. GUI E2E Tests (`gui/tests/e2e/`)
- **Purpose**: End-to-end testing of the Electron GUI application
- **CI**: Run automatically on every push/PR (after QE compilation)
- **Duration**: ~44 seconds (all tests)
- **Location**: `gui/tests/e2e/`
- **Requires**: QE installation (for workflow run tests)

### 3. Extended Tests (`extended-tests/`)
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

### GUI E2E Tests

```bash
cd gui
# Build Electron app first
npm run build:e2e

# Run all E2E tests
npm run test:e2e

# Run specific test file
npx playwright test tests/e2e/welcome.spec.ts --project=electron

# Run in headed mode (see browser)
npx playwright test --headed --project=electron
```

**Note**: E2E tests use a unified fixture that automatically chooses the launch strategy:
- **Linux/Windows**: Uses Playwright's native `_electron.launch()`
- **macOS**: Uses CDP (Chrome DevTools Protocol) workaround

See `AI_understanding.md` section 22 for detailed E2E testing documentation.

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

**Quick tests** run automatically:
- ✅ On push to `v2-python` branch
- ✅ On pull requests targeting `v2-python`
- ✅ Daily schedule

**GUI E2E tests** run automatically:
- ✅ On push to `v2-python` branch (always, no conditional skipping)
- ✅ On pull requests targeting `v2-python`
- ✅ After QE compilation completes (QE required for workflow tests)
- ✅ On both Linux and macOS

**Extended tests**:
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
├── gui/tests/e2e/          # GUI E2E tests (CI)
│   ├── fixtures/           # Unified Electron fixture
│   ├── helpers/            # Launch helpers (electron.ts, electron_cdp.ts)
│   ├── welcome.spec.ts     # Welcome screen tests
│   ├── demo_workflow.spec.ts # Demo project tests
│   └── demo_workflow_run.spec.ts # Full workflow execution test
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

## Workflow Reference Outputs

Core/CLI integration tests exercise real QE workflows. Reference `.out` files for
strict verification live alongside each workflow under
`workflows/<workflow_id>/reference/`. The runner automatically compares QE
results against those references when you invoke:

- `pytest -m qe_core` (engine-level workflows)
- `pytest -m qe_cli` (Typer CLI workflows)
- `qv run-workflow <wf> --strict`

When regenerating reference data, run the workflow once locally, copy the
resulting `.out` files into `reference/`, and commit them alongside the workflow
YAML. Quick tests never auto-generate references—they simply read whatever is in
`workflows/<id>/reference/`.

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

