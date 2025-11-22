# PW Test Statistics Collection

This script runs all PW tests from the QE official test-suite and collects detailed statistics for selecting quick tests for CI.

## Usage

```bash
python3 extended-tests/scripts/run_pw_all_with_stats.py \
    --qe-path /path/to/qe/bin \
    --nprocs 4 \
    --timeout 300 \
    --output extended-tests/pw_test_stats.json
```

## Options

- `--qe-path`: Path to QE bin directory (default: `$HOME/src/q-e-qe-7.5/bin`)
- `--test-dir`: Path to QE test-suite (auto-detected from `--qe-path`)
- `--nprocs`: Number of processors (default: 4)
- `--timeout`: Timeout per test in seconds (default: 300)
- `--output`: Output JSON file (default: `extended-tests/pw_test_stats.json`)
- `--max-categories`: Limit number of categories (for testing)

## Output

The script generates a JSON file with:

1. **Overall Statistics**:
   - Total categories and tests
   - Success rate
   - Total and average execution time

2. **Category Breakdown**:
   - Per-category statistics
   - Individual test results
   - Timing information

3. **Selected CI Tests**:
   - 10 shortest, most representative tests
   - Diverse categories
   - Minimal redundancy

## Test Selection Algorithm

1. Collect all passing tests with timing information
2. Sort by execution time (shortest first)
3. Select tests from different categories first (diversity)
4. Fill remaining slots with shortest tests
5. Ensure no duplicate test files

## Integration with CI

The selected tests are automatically loaded by `tests/integration/test_pw_quick_tests.py` for CI execution.

## Example Output

```
============================================================
Running PW Tests with Statistics
============================================================
QE Path: <HOME>/src/q-e-qe-7.5/bin
Test Suite: <HOME>/src/q-e-qe-7.5/test-suite
NPROCS: 4
Total Categories: 25
============================================================

============================================================
Running category: pw_atom
============================================================
  Results: 3/3 passed (100.0%) in 45.23s

...

============================================================
OVERALL SUMMARY
============================================================
Total Categories: 25
Total Tests: 150
Passed: 145 (96.7%)
Failed: 5 (3.3%)
Total Time: 2345.67s
Average Time per Test: 15.64s

============================================================
ANALYZING FOR CI QUICK TESTS
============================================================

Selected 10 representative tests for CI:
------------------------------------------------------------
 1. pw_atom            | atom-lsda.in              |  12.34s
 2. pw_scf             | si.scf.in                 |  15.67s
 ...
```

