## Testing Overview (for Contributors)

QMatSuite uses a pytest-based test suite with 412 tests organized by subsystem. Detailed documentation is available in [`docs/tests_overview.md`](tests_overview.md). This section provides a quick "map" to help you know which tests to run when you make changes.

### Test Organization by Subsystem

| Area / Subsystem | Key Test Locations | Notes |
|------------------|-------------------|-------|
| **Core models & DAG** | `tests/unit/test_models.py`, `tests/unit/test_project_and_cli.py`, `tests/unit/test_workflow_dag_constitution.py` | Project/workflow/step schemas, ULID validation, DAG structure |
| **CLI commands** | `tests/cli/` | `qv init`, `qv run`, `qv configure`, `qv analyze`, error handling |
| **Daemon / RPC** | `tests/daemon/` | JSON-RPC endpoints for GUI, job management, step operations |
| **QE workflows** | `tests/integration/test_si_*.py`, `tests/cli/test_si_*_workflow_*.py` | Full workflow execution (requires QE installation) |
| **Analysis & plotting** | `tests/unit/test_analysis_*.py` | SCF/DOS/bands output parsing, plotting, artifacts |
| **Structure I/O** | `tests/unit/test_structure_*.py`, `tests/examples/test_structure_io_examples.py` | Structure import/export, format conversion, roundtrip |
| **Resource resolution** | `tests/unit/test_resolution.py` | Selector resolution (ULID, slug, path, name) |
| **Legacy migration** | `tests/unit/test_legacy_migration.py` | Legacy project format detection and migration |
| **QE engine** | `tests/integration/test_qe_engine.py`, `tests/integration/test_qe_executable_*.py` | QE input generation, executable detection (requires QE) |
| **API service** | `tests/unit/test_api_service*.py` | `QVService` API methods for project/workflow/step operations |

### What to Run When You Change Things

- **Core project/workflow/step models** (`quantumvitas.core.models`, `quantumvitas.project.model`)
  - `pytest tests/unit/test_models.py tests/unit/test_project_and_cli.py tests/unit/test_workflow_dag_constitution.py`

- **CLI behavior** (`quantumvitas.cli.main`)
  - `pytest tests/cli/` (some tests require QE installation)

- **Daemon / RPC / backend** (`quantumvitas.daemon.server`, `quantumvitas.api.QVService`)
  - `pytest tests/daemon/ tests/unit/test_daemon.py tests/unit/test_qvservice_gui.py`

- **QE workflows** (workflow execution, QE integration)
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
