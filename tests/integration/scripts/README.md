# CI Test Scripts

## copy_ci_test_files.py

Copies selected CI quick test files from QE test-suite to `tests/integration/ci_test_data/`.

### Usage

```bash
python3 tests/integration/scripts/copy_ci_test_files.py
```

### Options

- `--test-suite-dir PATH`: Path to QE test-suite (auto-detected if not provided)
- `--output-dir PATH`: Output directory (default: `tests/integration/ci_test_data/`)

### What it does

1. Reads selected tests from `extended-tests/pw_test_stats.json`
2. Copies input files (`.in`) from test-suite
3. Copies benchmark files (if available)
4. Copies related files (if any)
5. Creates `manifest.json` with metadata

### When to run

- After updating selected tests in `pw_test_stats.json`
- When adding new CI quick tests
- To ensure test files are up to date

### Output

Files are copied to `tests/integration/ci_test_data/` with structure:
```
ci_test_data/
├── manifest.json
├── pw_atom/
│   └── atom.in
├── pw_metal/
│   ├── metal.in
│   └── metal-gaussian.in
└── ...
```

