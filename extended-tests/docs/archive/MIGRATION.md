# Test Migration Summary

## Files Moved to Extended Tests

All files that depend on QE test-suite have been moved to `extended-tests/`:

### Test Suites
- `tests/test_bidirectional_conversion.py` → `extended-tests/suites/bidirectional/`
- `tests/test_official_testsuite.py` → `extended-tests/`

### Utilities
- `tests/test_qe_roundtrip_execution.py` → `extended-tests/utils/`
- `tests/utils/qe_module_base.py` → `extended-tests/utils/` (already moved)

### Scripts
- `tests/run_*_tests.py` → `extended-tests/scripts/`
- `tests/run_tests.py` → `extended-tests/scripts/`
- `tests/run_first_10_pw_categories.py` → `extended-tests/scripts/`
- `tests/run_multiple_pw_tests.py` → `extended-tests/scripts/`

## Quick Tests Remaining

Files in `tests/` that remain (quick tests, no test-suite dependency):
- `tests/unit/` - Unit tests (no external dependencies)
- `tests/integration/` - Integration tests (may require QE, but not test-suite)
- `tests/core/` - Test framework core
- `tests/conftest.py` - Pytest configuration

## Updated Imports

All moved files have been updated to use correct import paths:
- `extended-tests/utils/qe_module_base.py` imports from `extended-tests/utils/test_qe_roundtrip_execution.py`
- Scripts in `extended-tests/scripts/` import from `extended-tests/suites/`

## Usage

### Quick Tests (CI)
```bash
pytest tests/ -m quick
```

### Extended Tests (Developer)
```bash
# Use the unified runner
python3 extended-tests/run_all.py --all

# Or use individual scripts
python3 extended-tests/scripts/run_pw_tests_official_style.py --category pw_atom
```

