# CI Quick Test Data

This directory contains input files and reference data for CI quick tests.

## Source

These files are copied from the QE official test-suite to ensure consistency
and allow tests to run without requiring access to the full test-suite.

## Contents

- **Input files**: QE input files (`.in`) for selected quick tests
- **Benchmark files**: Reference output files for comparison (if available)
- **manifest.json**: Metadata about the copied tests

## Usage

Tests automatically use files from this directory if available, falling back
to the QE test-suite directory if not found.

## Updating

To update these files (e.g., when selected tests change):

```bash
python3 tests/integration/scripts/copy_ci_test_files.py
```

This will:
1. Read selected tests from `extended-tests/pw_test_stats.json`
2. Copy input files from QE test-suite
3. Copy benchmark files if available
4. Update `manifest.json`

## Distribution

These files are included in the repository and distributed with the software
to ensure consistent test results across different environments.

