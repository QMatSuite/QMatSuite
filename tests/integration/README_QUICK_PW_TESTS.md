# Quick PW Tests for CI

This directory contains quick integration tests for the PW module, selected from the QE official test-suite.

## Selection Criteria

Tests are selected based on:
1. **Shortest execution time** - Fast tests for CI
2. **Representative coverage** - Cover different categories and functionality
3. **Minimal redundancy** - Avoid duplicate test cases
4. **High success rate** - Reliable tests that consistently pass

## How to Update Quick Tests

1. Run the statistics collection script:
   ```bash
   python3 extended-tests/scripts/run_pw_all_with_stats.py \
       --qe-path /path/to/qe/bin \
       --nprocs 4 \
       --output extended-tests/pw_test_stats.json
   ```

2. The script will:
   - Run all PW test categories
   - Collect timing and success rate statistics
   - Automatically select 10 representative tests
   - Save results to `extended-tests/pw_test_stats.json`

3. The quick tests in `test_pw_quick_tests.py` will automatically load from the statistics file.

## Test Structure

- `test_pw_quick_tests.py` - Main test file with parametrized tests
- Tests are loaded from `extended-tests/pw_test_stats.json`
- Each test:
  - Parses the input file
  - Generates a new input file
  - Runs pw.x
  - Verifies "JOB DONE" in output

## Requirements

- QE installation (can be skipped if not available)
- QE test-suite (can be skipped if not available)
- Tests marked with `@pytest.mark.quick` for CI

## CI Integration

These tests run automatically in CI as part of quick tests:
```bash
pytest tests/integration/test_pw_quick_tests.py -m quick
```

If QE is not available in CI, tests will be skipped gracefully.

