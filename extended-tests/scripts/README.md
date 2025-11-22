# Extended Test Scripts

These scripts run comprehensive tests based on the QE official test-suite.
They are **NOT run automatically in CI** and require:
- QE installation
- QE test-suite directory
- Extended execution time

## Scripts

### Module Test Runners
- `run_pw_tests_official_style.py` - PW module tests
- `run_ph_tests.py` - PH module tests
- `run_pp_tests.py` - PP module tests
- `run_cp_tests.py` - CP module tests
- `run_hp_tests.py` - HP module tests
- `run_tddfpt_tests.py` - TDDFPT module tests
- `run_kcw_tests.py` - KCW module tests
- `run_epw_tests.py` - EPW module tests
- `run_zg_tests.py` - ZG module tests
- `run_all_currents_tests.py` - all_currents module tests
- `run_xsd_pw_tests.py` - XSD validation tests

### Utility Scripts
- `run_first_10_pw_categories.py` - Run first 10 PW categories
- `run_multiple_pw_tests.py` - Run multiple PW test categories
- `run_tests.py` - Unified test runner (legacy)

## Usage

All scripts support similar options:
```bash
--qe-path PATH      # Path to QE bin directory
--test-dir PATH     # Path to QE test-suite (auto-detected if not provided)
--category NAME     # Run specific category
--timeout SECONDS   # Timeout per test
```

Example:
```bash
python3 extended-tests/scripts/run_pw_tests_official_style.py --category pw_atom
python3 extended-tests/scripts/run_ph_tests.py --all
```

## Note

These scripts are for **developer use only**. They are not part of the quick test suite
and are not run automatically in CI.

