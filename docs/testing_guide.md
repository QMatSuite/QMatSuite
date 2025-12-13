## Testing Overview (for Contributors)

QMatSuite uses a pytest-based test suite with 412 tests organized by subsystem. Detailed documentation is available in [`docs/tests_overview.md`](tests_overview.md). This section provides a quick "map" to help you know which tests to run when you make changes.

### Test Organization by Subsystem

| Area / Subsystem | Key Test Locations | Notes |
|------------------|-------------------|-------|
| **Core models & DAG** | `tests/unit/test_models.py`, `tests/unit/test_project_and_cli.py`, `tests/unit/test_calculation_dag_constitution.py` | Project/calculation/step schemas, ULID validation, DAG structure |
| **CLI commands** | `tests/cli/` | `qv init`, `qv run`, `qv configure`, `qv analyze`, error handling |
| **Daemon / RPC** | `tests/daemon/` | JSON-RPC endpoints for GUI, job management, step operations |
| **QE calculations** | `tests/integration/test_si_*.py`, `tests/cli/test_si_*_workflow_*.py` | Full calculation execution (requires QE installation) |
| **Analysis & plotting** | `tests/unit/test_analysis_*.py` | SCF/DOS/bands output parsing, plotting, artifacts |
| **Structure I/O** | `tests/unit/test_structure_*.py`, `tests/examples/test_structure_io_examples.py` | Structure import/export, format conversion, roundtrip |
| **Resource resolution** | `tests/unit/test_resolution.py` | Selector resolution (ULID, slug, path, name) |
| **Legacy migration** | `tests/unit/test_legacy_migration.py` | Legacy project format detection and migration |
| **QE engine** | `tests/integration/test_qe_engine.py`, `tests/integration/test_qe_executable_*.py` | QE input generation, executable detection (requires QE) |
| **API service** | `tests/unit/test_api_service*.py` | `QVService` API methods for project/calculation/step operations |

### What to Run When You Change Things

- **Core project/calculation/step models** (`quantumvitas.core.models`, `quantumvitas.project.model`)
  - `pytest tests/unit/test_models.py tests/unit/test_project_and_cli.py tests/unit/test_calculation_dag_constitution.py`

- **CLI behavior** (`quantumvitas.cli.main`)
  - `pytest tests/cli/` (some tests require QE installation)

- **Daemon / RPC / backend** (`quantumvitas.daemon.server`, `quantumvitas.api.QVService`)
  - `pytest tests/daemon/ tests/unit/test_daemon.py tests/unit/test_qvservice_gui.py`

- **QE calculations** (calculation execution, QE integration)
  - `pytest tests/integration/test_si_*.py` (requires QE installation)
  - `pytest tests/cli/test_si_*_workflow_*.py` (requires QE installation)

- **Analysis / parsing / plotting** (`quantumvitas.analysis.*`)
  - `pytest tests/unit/test_analysis_*.py`

- **Structure I/O** (`quantumvitas.io.structure_io`)
  - `pytest tests/unit/test_structure_*.py tests/examples/test_structure_io_examples.py`

- **Resource resolution** (`quantumvitas.core.resolution`)
  - `pytest tests/unit/test_resolution.py`

- **Legacy migration** (`quantumvitas.legacy.migrate`)
  - `pytest tests/unit/test_legacy_migration.py`

### QE-backed Integration Tests

**QE-backed integration tests** are test modules that actually run Quantum ESPRESSO executables (pw.x, bands.x, dos.x, etc.) via the `qv` CLI. These tests are slower than unit tests because they execute full QE calculations, but they provide end-to-end validation of the entire system.

#### QE-backed vs Pure Unit Tests

**Pure unit tests** (fast, no QE required):
- Test individual functions and modules in isolation
- Use mocked data or precomputed test files
- Parse outputs, generate plots, validate models
- Located primarily in `tests/unit/`
- Run in CI without QE installation

**QE-backed integration tests** (slower, require QE):
- Execute complete calculations via `qv run calculation ...` or `CalculationRunner.run()`
- Spawn QE executables (pw.x, bands.x, dos.x, ph.x, etc.)
- Require QE installation and pseudopotentials
- Located in `tests/cli/` (CLI execution) or `tests/integration/` (CalculationRunner/engine execution)
- Marked with `@pytest.mark.qe_core` or `@pytest.mark.qe_cli`

#### The "One QE-running Test Per File" Convention

Each QE-backed test module must have exactly **one** QE-running test function that:
- Runs the full calculation (`qv run calculation ...`)
- Performs all post-processing checks (`qv analyze ...`)
- Verifies outputs and plots

All other tests in the same module must be pure unit tests (no QE execution). This convention ensures:
- Each calculation is tested once end-to-end
- Tests are predictable and not dependent on execution order
- Fast unit tests can run without QE installation

For the complete list of QE-backed test modules, see [Tests Overview](tests_overview.md#qe-backed-integration-tests).

#### Running QE-backed Tests

**Run all QE-backed tests:**
```bash
# Run all CLI tests (includes QE-backed integration tests)
pytest tests/cli/

# Run all QE integration tests via markers
pytest -m qe_core
pytest -m qe_cli
```

**Run specific QE-backed calculation test:**
```bash
# CLI-based calculations
pytest tests/cli/test_si_dos_calculation_comprehensive.py
pytest tests/cli/test_si_bands_manual_workflow_cli.py
pytest tests/cli/test_si_bands_auto_workflow_cli.py

# CalculationRunner-based calculations
pytest tests/integration/test_si_dos_calculation.py
pytest tests/integration/test_si_bands_calculation.py

# Step execution tests
pytest tests/integration/test_pw_quick_tests_ci.py
pytest tests/integration/test_pw_step_specs.py
pytest tests/integration/test_pw_scf_ibrav_step_specs.py
pytest tests/integration/test_ph_quick_tests.py
```

**Note:** QE-backed tests require:
- Quantum ESPRESSO installation (pw.x, bands.x, dos.x, etc.)
- QE_HOME environment variable or QE in PATH
- Pseudopotential files (typically in `pseudo/` directory)

#### Adding New QE-backed Tests

When adding a new QE-backed calculation test:
1. Create a new test module (or reuse an existing one if it's the same calculation)
2. Put all QE-running logic into a **single** integration test function (e.g., `test_run_calculation_and_analyze`)
3. Any other checks should either be:
   - Folded into that single function, OR
   - Split into pure unit tests (no `qv run calculation` calls)

This ensures compliance with the "one QE-running test per file" convention.

### Running Tests Without QE Installation

For environments without Quantum ESPRESSO installed, you can run only unit tests that don't require QE:

```bash
# Run all unit tests (no QE required)
pytest tests/unit

# Skip QE-dependent tests using markers
pytest -m "not qe_core and not qe_cli"

# Run only quick tests (excludes extended-tests/)
pytest -m quick
```

**Note:** Tests in `tests/integration/` and some tests in `tests/cli/` require QE installation. These are marked with `@pytest.mark.qe_core` or `@pytest.mark.qe_cli` and will be skipped if QE is not available.
