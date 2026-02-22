## Testing Overview (for Contributors)

QMatSuite uses a pytest-based test suite with 412 tests organized by subsystem. Detailed documentation is available in [`docs/tests_overview.md`](tests_overview.md). This section provides a quick "map" to help you know which tests to run when you make changes.

### Test Organization by Subsystem

| Area / Subsystem | Key Test Locations | Notes |
|------------------|-------------------|-------|
| **Core models & DAG** | `tests/unit/test_models.py`, `tests/unit/test_project_and_cli.py`, `tests/unit/test_calculation_dag_constitution.py` | Project/calculation/step schemas, ULID validation, DAG structure |
| **CLI commands** | `tests/cli/` | `qms init`, `qms run`, `qms configure`, `qms analyze`, error handling |
| **Daemon / RPC** | `tests/daemon/` | JSON-RPC endpoints for GUI, job management, step operations |
| **QE calculations** | `tests/integration/test_si_*.py`, `tests/cli/test_si_*_workflow_*.py` | Full calculation execution (requires QE installation) |
| **Analysis & plotting** | `tests/unit/test_analysis_*.py` | SCF/DOS/bands output parsing, plotting, artifacts |
| **Structure I/O** | `tests/unit/test_structure_*.py`, `tests/examples/test_structure_io_examples.py` | Structure import/export, format conversion, roundtrip |
| **Resource resolution** | `tests/unit/test_resolution.py` | Selector resolution (ULID, slug, path, name) |
| **Legacy migration** | `tests/unit/test_legacy_migration.py` | Legacy project format detection and migration |
| **QE engine** | `tests/integration/test_qe_engine.py`, `tests/integration/test_qe_executable_*.py` | QE input generation, executable detection (requires QE) |
| **API service** | `tests/unit/test_api_service*.py` | `QMSService` API methods for project/calculation/step operations |

### What to Run When You Change Things

- **Core project/calculation/step models** (`qmatsuite.core.models`, `qmatsuite.project.model`)
  - `pytest tests/unit/test_models.py tests/unit/test_project_and_cli.py tests/unit/test_calculation_dag_constitution.py`

- **CLI behavior** (`qmatsuite.cli.main`)
  - `pytest tests/cli/` (some tests require QE installation)

- **Daemon / RPC / backend** (`qmatsuite.daemon.server`, `qmatsuite.api.QMSService`)
  - `pytest tests/daemon/ tests/unit/test_daemon.py tests/unit/test_qmsservice_gui.py`

- **QE calculations** (calculation execution, QE integration)
  - `pytest tests/integration/test_si_*.py` (requires QE installation)
  - `pytest tests/cli/test_si_*_workflow_*.py` (requires QE installation)

- **Analysis / parsing / plotting** (`qmatsuite.analysis.*`)
  - `pytest tests/unit/test_analysis_*.py`

- **Structure I/O** (`qmatsuite.io.structure_io`)
  - `pytest tests/unit/test_structure_*.py tests/examples/test_structure_io_examples.py`

- **Resource resolution** (`qmatsuite.core.resolution`)
  - `pytest tests/unit/test_resolution.py`

- **Legacy migration** (`qmatsuite.legacy.migrate`)
  - `pytest tests/unit/test_legacy_migration.py`

### QE-backed Integration Tests

**QE-backed integration tests** are test modules that actually run Quantum ESPRESSO executables (pw.x, bands.x, dos.x, etc.) via the `qms` CLI. These tests are slower than unit tests because they execute full QE calculations, but they provide end-to-end validation of the entire system.

#### QE-backed vs Pure Unit Tests

**Pure unit tests** (fast, no QE required):
- Test individual functions and modules in isolation
- Use mocked data or precomputed test files
- Parse outputs, generate plots, validate models
- Located primarily in `tests/unit/`
- Run in CI without QE installation

**QE-backed integration tests** (slower, require QE):
- Execute complete calculations via `qms run calculation ...` or `CalculationRunner.run()`
- Spawn QE executables (pw.x, bands.x, dos.x, ph.x, etc.)
- Require QE installation and pseudopotentials
- Located in `tests/cli/` (CLI execution) or `tests/integration/` (CalculationRunner/engine execution)
- Marked with `@pytest.mark.qe_core` or `@pytest.mark.qe_cli`

#### The "One QE-running Test Per File" Convention

Each QE-backed test module must have exactly **one** QE-running test function that:
- Runs the full calculation (`qms run calculation ...`)
- Performs all post-processing checks (`qms analyze ...`)
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
   - Split into pure unit tests (no `qms run calculation` calls)

This ensures compliance with the "one QE-running test per file" convention.

#### Test Sandbox Pattern

Integration tests that execute QE steps must follow the **sandbox pattern** to keep template directories read-only:

1. **`raw_dir` is read-only**: Use `raw_dir` only as a template/fixture directory for materialized step specs. Never pass `raw_dir` as `working_dir` to `run_step()`.

2. **Create separate `sandbox_dir`**: Use `create_sandbox_working_dir()` from `tests.core.qe_step_runner` to create a temporary execution directory.

3. **Copy inputs to sandbox**: Copy generated inputs from `raw_dir` to `sandbox_dir` before execution.

4. **Materialize pseudos to sandbox**: Pseudopotentials must be materialized to `sandbox_dir/pseudo/` (not `raw_dir/pseudo/`). The `run_step()` function will set `ESPRESSO_PSEUDO` to `sandbox_dir/pseudo/` in standalone mode.

**Example pattern:**
```python
# Materialize step spec to raw_dir (read-only template)
generated_input, spec = materialize_step_spec(
    step_result.spec_path,
    output_dir=raw_dir,  # Template directory
    calculation_dir=working_dir,
    project_root=None,  # Standalone mode
)

# Create sandbox for execution
from tests.core.qe_step_runner import create_sandbox_working_dir
import shutil
sandbox_dir = create_sandbox_working_dir(working_dir, prefix=f"{slug}_run_")

# Copy input to sandbox
sandbox_input = sandbox_dir / generated_input.name
shutil.copy2(generated_input, sandbox_input)

# Materialize pseudos to sandbox_dir/pseudo
sandbox_pseudo_dir = sandbox_dir / "pseudo"
sandbox_pseudo_dir.mkdir(parents=True, exist_ok=True)
from qmatsuite.core.pseudo import ensure_qe_pseudos, get_system_pseudo_dir
result = ensure_qe_pseudos(
    qe_input_file=sandbox_input,
    project_pseudo_dir=sandbox_pseudo_dir,  # Materialize to sandbox
    system_pseudo_dir=get_system_pseudo_dir(),
    strict=False,
)

# Run in sandbox_dir (not raw_dir)
step_result = qe_engine.run_step(
    input_file=sandbox_input,
    working_dir=sandbox_dir,  # Execution happens here
    step_type=step_type,
    timeout=300,
)
```

**Key invariants:**
- `raw_dir` stays read-only (no `pseudo/` directory created there)
- `sandbox_dir` is the execution directory (contains `pseudo/` with materialized pseudos)
- `ESPRESSO_PSEUDO` points to `sandbox_dir/pseudo/` in standalone mode
- Pseudo materialization happens at runtime, not at materialize time

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
