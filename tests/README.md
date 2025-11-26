# Quick Tests

Quick tests for QuantumVITAS. These tests are **automatically run in CI** and should be fast and focused.

## Structure

```
tests/
├── unit/          # Pure Python tests (no QE binaries)
├── integration/   # QE integration driven via shared engine helpers
├── cli/           # QE integration executed through the Typer CLI
├── core/          # Shared fixtures/utilities (jobconfig parsing, runners, etc.)
└── conftest.py    # Pytest configuration and automatic markers
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
pytest -m unit              # Parser / IO / project-loading tests
pytest -m qe_core           # QE integration via the engine helpers
pytest -m qe_cli            # QE integration executed through the CLI
```

### Run with coverage
```bash
pytest tests/ --cov=src/quantumvitas --cov-report=html
```

## Test Categories

### Unit Tests (`tests/unit/`, `-m unit`)
- Fast, isolated, no QE binaries.
- Examples: parser round-trips, jobconfig ordering, CLI scaffolding.

### QE Core Integration (`tests/integration/`, `-m qe_core`)
- Run real QE binaries via the shared `run_and_verify_step` helpers or the new `WorkflowRunner`.
- Reference outputs live under `workflows/<id>/reference/` and strict mode compares against them automatically.

### QE CLI Integration (`tests/cli/`, `-m qe_cli`)
- Exercise the Typer CLI end-to-end (`qv run-workflow …`).
- Use the same workflow layout (raw + reference) so debugging artifacts land in `temp/test_outputs/`.

## Markers

Tests are automatically marked based on location:
- `@pytest.mark.quick` - All tests under `tests/`
- `@pytest.mark.unit` - Files in `tests/unit/`
- `@pytest.mark.qe_core` - Files in `tests/integration/`
- `@pytest.mark.qe_cli` - Files in `tests/cli/`
- `@pytest.mark.requires_qe` - Legacy marker for tests that need QE (still present in extended-tests)

## CI Integration

Quick tests run automatically in GitHub Actions on:
- Push to main/develop
- Pull requests
- Daily schedule

See `.github/workflows/tests.yml` for configuration.

## Extended Tests

For comprehensive tests based on QE official test-suite, see `../extended-tests/`.
Extended tests are **NOT run automatically in CI** and are intended for developers.
