# Test Suite Overview

## 1. Overall Structure

### Test Organization

Tests are organized into several directories:

- **`tests/unit/`** (32 files) - Fast unit tests that don't require QE execution
- **`tests/cli/`** (6 files) - CLI command integration tests
- **`tests/daemon/`** (5 files) - Daemon RPC endpoint tests (GUI backend)
- **`tests/integration/`** (11 files) - Integration tests that run Quantum ESPRESSO
- **`tests/examples/`** (2 files) - Example usage tests
- **`tests/core/`** (8 files) - Core test utilities and helpers
- **`tests/utils/`** (3 files) - Shared test utilities
- **`tests/data/`** - Test data files (QE inputs, outputs, project examples)

### Test Markers

Tests are automatically marked based on location:
- `@pytest.mark.quick` - All tests in `tests/` (run in CI)
- `@pytest.mark.unit` - Tests in `tests/unit/`
- `@pytest.mark.qe_core` - Tests in `tests/integration/` (run QE via engine)
- `@pytest.mark.qe_cli` - Tests in `tests/cli/` (run QE via CLI)
- `@pytest.mark.extended` - Tests in `extended-tests/`

### Subsystems Covered

1. **Project & Workflow Models** - DAG + ULID architecture, schema validation
2. **CLI Commands** - All `qv` CLI commands (init, run, configure, analyze, etc.)
3. **Daemon RPC** - JSON-RPC endpoints used by GUI
4. **QE Engine Integration** - Quantum ESPRESSO execution, input generation, output parsing
5. **Analysis** - Band structure, DOS, SCF convergence parsing and plotting
6. **Structure I/O** - Structure import/export, format conversion
7. **Resource Resolution** - Selector resolution (ULID, slug, path)
8. **Legacy Migration** - Legacy project format detection and migration
9. **Step Defaults** - QE parameter defaults application
10. **Workflow Execution** - Multi-step workflow runs, job management

## 2. Summary Table

| Test File | Main Area / Module | Key Responsibilities | Key Dependencies |
|-----------|-------------------|---------------------|------------------|
| `tests/unit/test_models.py` | Project/workflow DAG & schema | Load/save project/workflow models, ULID validation, legacy format detection | `tmp_path`, in-memory YAML data |
| `tests/unit/test_project_and_cli.py` | Project model + CLI integration | Project operations, workflow creation, step creation, CLI roundtrips | `tmp_path`, `sample_project` fixture |
| `tests/unit/test_api_service.py` | QVService API | Project init, structure import, workflow init, step creation | `tmp_path`, minimal project fixtures |
| `tests/unit/test_api_service_steps.py` | QVService step operations | Step creation, step detail retrieval, step updates | `tmp_path`, project fixtures |
| `tests/unit/test_resolution.py` | Resource selector resolution | ULID/slug/path selector resolution, resource lookup | `tmp_path`, project fixtures |
| `tests/unit/test_legacy_migration.py` | Legacy project migration | Legacy format detection, migration script validation | `tmp_path`, manually created legacy projects |
| `tests/unit/test_workflow_dag_constitution.py` | Workflow DAG structure | DAG invariants, step ordering, structure inheritance | `tmp_path`, project fixtures |
| `tests/unit/test_id_based_references.py` | ID-only reference model | ULID-based references, no legacy fields | `tmp_path`, project fixtures |
| `tests/unit/test_structure_io.py` | Structure I/O | Structure import/export, format conversion | `tmp_path`, test structure files |
| `tests/unit/test_structure_roundtrip.py` | Structure roundtrip | Structure → QE input → structure conversion | `tmp_path`, `ci_test_data_dir` |
| `tests/unit/test_qe_input.py` | QE input parsing | QE input file parsing, namelist/card extraction | `tmp_path`, sample QE input files |
| `tests/unit/test_qe_geometry_roundtrip.py` | QE geometry conversion | Geometry conversion between formats (ibrav, cell_parameters) | `tmp_path`, `ci_test_data_dir` |
| `tests/unit/test_qe_executable_detection.py` | QE installation detection | QE executable detection, QE_HOME resolution | `monkeypatch`, environment variables |
| `tests/unit/test_qe_modules.py` | QE module parameters | QE module parameter loading, validation | `project_root_path` |
| `tests/unit/test_step_defaults.py` | Step parameter defaults | QE parameter defaults application | `tmp_path`, step fixtures |
| `tests/unit/test_parameter_overrides.py` | CLI parameter overrides | Parameter override parsing, application | `tmp_path` |
| `tests/unit/test_workflow_importers.py` | Workflow import | Import workflows from QE input files | `tmp_path`, QE input files |
| `tests/unit/test_workflow_inputs.py` | Workflow input generation | Input file generation from step specs | `tmp_path`, workflow fixtures |
| `tests/unit/test_structure_steps.py` | Structure step operations | Step creation with structure inheritance | `tmp_path`, project fixtures |
| `tests/unit/test_analysis_parsers.py` | Analysis output parsing | SCF/DOS/bands output parsing | `tests/data/analysis_*` directories |
| `tests/unit/test_analysis_plotting.py` | Analysis plotting | Band structure/DOS plotting | `tests/data/analysis_*`, matplotlib |
| `tests/unit/test_analysis_artifacts.py` | Analysis artifacts | Artifact generation, file management | `tmp_path`, analysis data |
| `tests/unit/test_structure_viz.py` | Structure visualization | 3D structure visualization data | `tmp_path`, structure fixtures |
| `tests/unit/test_pseudopotential_resolution.py` | Pseudopotential resolution | PP file lookup, path resolution | `tmp_path`, pseudo directory fixtures |
| `tests/unit/test_context.py` | Path context detection | Workflow/structure context from CWD | `tmp_path`, project fixtures |
| `tests/unit/test_daemon.py` | Daemon core | Daemon initialization, RPC request handling | `tmp_path`, `QVDaemon` |
| `tests/unit/test_qvservice_gui.py` | QVService GUI paths | GUI-specific API methods | `tmp_path`, project fixtures |
| `tests/unit/test_project_snapshot.py` | Project snapshots | Snapshot creation, restoration | `tmp_path`, project fixtures |
| `tests/unit/test_snapshot_id_regeneration.py` | Snapshot ID handling | ULID regeneration in snapshots | `tmp_path`, project fixtures |
| `tests/unit/test_resource_rename_safety.py` | Resource renaming | Safe resource renaming, path updates | `tmp_path`, project fixtures |
| `tests/unit/test_demo_snapshot_restore.py` | Demo project snapshots | Demo project snapshot/restore | `tmp_path`, demo project fixtures |
| `tests/unit/test_ci_smoke.py` | CI smoke tests | Basic smoke tests for CI | `tmp_path` |
| `tests/cli/test_graphene_workflow_setup.py` | CLI workflow setup | Complete workflow setup via CLI | `ci_test_data_dir`, `tmp_path`, `CliRunner` |
| `tests/cli/test_si_dos_workflow_cli.py` | CLI DOS workflow | DOS workflow execution via CLI | `ci_test_data_dir`, QE installation |
| `tests/cli/test_si_dos_workflow_comprehensive.py` | CLI DOS workflow comprehensive | Full DOS workflow with analysis | `project_root_path`, QE installation |
| `tests/cli/test_si_bands_workflow_comprehensive.py` | CLI bands workflow comprehensive | Full bands workflow with manual/auto k-path | `project_root_path`, QE installation |
| `tests/cli/test_template_workflow.py` | CLI workflow templates | Template-based workflow creation | `tmp_path`, `CliRunner` |
| `tests/cli/test_cli_show_command_integration.py` | CLI show command | `qv show` command integration | `tests/data/project_examples`, `CliRunner` |
| `tests/daemon/test_gui_workflow_detail.py` | Daemon workflow detail | `get_workflow_detail`, `change_workflow_structure` | `tmp_path`, `QVDaemon`, `QVService` |
| `tests/daemon/test_gui_job_and_step_flows.py` | Daemon job/step flows | Job submission, step detail, DAG invariants | `tmp_path`, `QVDaemon`, `QVService` |
| `tests/daemon/test_si_bands_workflow_daemon.py` | Daemon bands workflow | Full bands workflow via daemon RPC | `project_root_path`, QE installation, `QVDaemon` |
| `tests/integration/test_si_bands_workflow.py` | Integration bands workflow | SCF→NSCF→Bands workflow execution | `ci_test_data_dir`, QE installation, `create_workflow_project` |
| `tests/integration/test_si_dos_workflow.py` | Integration DOS workflow | SCF→NSCF→DOS workflow execution | `ci_test_data_dir`, QE installation, `create_workflow_project` |
| `tests/integration/test_qe_engine.py` | QE engine integration | QE engine input generation, execution | `tmp_path`, QE installation |
| `tests/integration/test_qe_executable_integration.py` | QE executable integration | QE executable detection, execution | QE installation, environment |
| `tests/integration/test_pw_step_specs.py` | PW step specifications | Various PW step types, input generation | `ci_test_data_dir`, QE installation |
| `tests/integration/test_pw_scf_ibrav_step_specs.py` | PW SCF ibrav specs | SCF with different ibrav values | `ci_test_data_dir/pw_scf_ibrav`, QE installation |
| `tests/integration/test_pw_quick_tests_ci.py` | PW quick CI tests | Quick PW tests for CI | `ci_test_data_dir`, QE installation |
| `tests/integration/test_ph_quick_tests.py` | PH quick tests | Phonon calculation tests | `ci_test_data_dir/ph_*`, QE installation |
| `tests/integration/test_ci_validation.py` | CI validation | CI validation workflows | `ci_test_data_dir`, QE installation |
| `tests/examples/test_cli_usage_examples.py` | CLI usage examples | Example CLI command sequences | `tmp_path`, `CliRunner` |
| `tests/examples/test_structure_io_examples.py` | Structure I/O examples | Example structure import/export | `tmp_path`, structure files |

## 3. Per-file Details

### `tests/unit/test_models.py`

**Module / feature:**
- Core data models: `WorkflowModel`, `WorkflowStepEntry`, `ProjectModel`, `StructureEntry`, `WorkflowEntry`, `StructureModel`
- DAG + ULID model validation
- Legacy format detection

**Related production code:**
- `quantumvitas.core.models`
- `quantumvitas.core.resources.ResourceMeta`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary directories for test projects
  - In-memory YAML data structures
- No external data files (all data created in tests)

**Contained tests:**

- `TestWorkflowStepEntry` - Tests step entry serialization/deserialization
  - `test_to_dict_minimal` - Minimal entry only has `step_id` (ULID)
  - `test_to_dict_full` - Full entry has all fields, no legacy `step_file`
  - `test_from_dict_valid_dag_entry` - Parse DAG format entry
  - `test_from_dict_legacy_format_raises_error` - Legacy format raises `LegacyProjectError`

- `TestWorkflowModel` - Tests workflow model loading/saving
  - `test_from_dict_minimal` - Parse minimal workflow
  - `test_from_dict_with_steps` - Parse workflow with steps (DAG + ULID)
  - `test_from_dict_legacy_structure_raises_error` - Legacy `structure` field raises error
  - `test_from_dict_legacy_step_file_raises_error` - Legacy `step_file` raises error
  - `test_save_workflow_preserves_ulids` - Saving preserves ULIDs

- `TestProjectModel` - Tests project model operations
  - `test_load_project_minimal` - Load minimal project
  - `test_load_project_with_resources` - Load project with structures/workflows
  - `test_save_project_preserves_ulids` - Saving preserves ULIDs

- `TestStructureEntry` - Tests structure entry serialization
  - `test_to_dict_only_structure_id` - Only `structure_id` in dict (no duplicated meta)

- `TestLegacyDetection` - Tests legacy format detection
  - Various tests checking that legacy fields (`structure`, `step_file`, non-ULID `id`) raise `LegacyProjectError`

### `tests/unit/test_project_and_cli.py`

**Module / feature:**
- Project model operations
- CLI command integration
- Workflow and step creation

**Related production code:**
- `quantumvitas.project.model.Project`
- `quantumvitas.cli.main`
- `quantumvitas.workflow.input_runner.PreparedInputStep`

**Key dependencies:**
- Fixtures:
  - `sample_project` - Creates a temporary project with structure and workflow
  - `tmp_path` - Temporary directories
- Data:
  - Uses `tests.core.test_data.load_test_cases` for test case data

**Contained tests:**

- Project loading/saving tests
- Workflow creation tests
- Step creation tests
- CLI roundtrip tests (create via CLI, verify via API)
- Structure import tests
- Geometry comparison tests

### `tests/unit/test_api_service.py`

**Module / feature:**
- `QVService` API methods for project, structure, workflow, and step operations

**Related production code:**
- `quantumvitas.api.QVService`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary project directories
  - `project_with_struct_source` - Project with a source structure file

**Contained tests:**

- `TestQVServiceProject` - Project operations
  - `test_init_project` - Initialize new project
  - `test_init_project_default_name` - Default name from directory
  - `test_configure_project` - Configure project settings
  - `test_init_project_prevents_nested_project` - Prevent nested projects
  - `test_create_demo_project_prevents_nested_project` - Prevent nested demo projects

- `TestQVServiceStructure` - Structure operations
  - `test_import_structure_from_json` - Import structure from JSON
  - `test_import_structure_duplicate_id_fails` - Duplicate ID detection
  - `test_list_structures` - List structures

- `TestQVServiceWorkflow` - Workflow operations
  - `test_init_workflow` - Initialize workflow
  - `test_list_workflows` - List workflows

- `TestQVServiceStep` - Step operations
  - `test_add_step_to_workflow` - Add step to workflow
  - `test_get_step_detail` - Get step detail

### `tests/unit/test_api_service_steps.py`

**Module / feature:**
- `QVService` step-specific operations

**Related production code:**
- `quantumvitas.api.QVService`

**Key dependencies:**
- Fixtures:
  - `project_with_workflow` - Project with a workflow and step

**Contained tests:**

- Step creation tests
- Step detail retrieval tests
- Step update tests
- Step deletion tests

### `tests/unit/test_resolution.py`

**Module / feature:**
- Resource selector resolution (ULID, slug, path, name)

**Related production code:**
- `quantumvitas.core.resolution`

**Key dependencies:**
- Fixtures:
  - `project_with_structures` - Project with multiple structures
  - `project_with_workflows` - Project with multiple workflows
  - `project_with_steps` - Project with workflow and steps
  - `project_with_resources` - Project with all resource types

**Contained tests:**

- `TestSelectorClassification` - Selector type classification
  - `test_is_ulid_like_valid` - ULID detection
  - `test_is_path_like_slash` - Path detection

- `TestStructureResolution` - Structure resolution
  - Tests resolving structures by ULID, slug, path, name

- `TestWorkflowResolution` - Workflow resolution
  - Tests resolving workflows by ULID, slug, path, name

- `TestStepResolution` - Step resolution
  - Tests resolving steps by ULID, slug, path

- `TestListResources` - Resource listing
  - Tests listing structures, workflows, steps

### `tests/unit/test_legacy_migration.py`

**Module / feature:**
- Legacy project migration script

**Related production code:**
- `quantumvitas.legacy.migrate.migrate_legacy_project`
- `quantumvitas.core.models.load_workflow`, `load_project`
- `quantumvitas.core.exceptions.LegacyProjectError`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary directory for legacy project
- Data:
  - Manually creates legacy project structure in test

**Contained tests:**

- `test_migrate_legacy_project_minimal` - End-to-end migration test
  - **What it tests:** Migration script converts legacy project (with `structure` selector, `step_file`, non-ULID `id`) to DAG + ULID format
  - **Dependencies:** Creates legacy project structure in `tmp_path`, then runs migration and verifies:
    - `LegacyProjectError` raised before migration
    - Migration succeeds
    - `structure_id` (ULID) present after migration
    - `step_id` (ULID) present after migration
    - Legacy fields removed (`structure`, `step_file`, `id`)
    - Project/workflow can be loaded after migration

### `tests/unit/test_workflow_dag_constitution.py`

**Module / feature:**
- Workflow DAG structure validation
- Step ordering
- Structure inheritance

**Related production code:**
- `quantumvitas.core.models.WorkflowModel`
- `quantumvitas.workflow.workflow`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary project directories
  - Project fixtures with workflows and steps

**Contained tests:**

- DAG invariant tests (workflow has `structure_id`, steps don't have `structure_id`)
- Step ordering tests
- Structure inheritance tests

### `tests/unit/test_id_based_references.py`

**Module / feature:**
- ID-only reference model validation
- ULID-based references

**Related production code:**
- `quantumvitas.core.models`
- `quantumvitas.core.resolution`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary project directories

**Contained tests:**

- Tests that all references use ULIDs
- Tests that legacy reference formats are rejected

### `tests/unit/test_structure_io.py`

**Module / feature:**
- Structure import/export
- Format conversion (CIF, JSON, QE input)

**Related production code:**
- `quantumvitas.io.structure_io`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary directories
  - Structure files in various formats

**Contained tests:**

- Structure import tests
- Structure export tests
- Format conversion tests

### `tests/unit/test_structure_roundtrip.py`

**Module / feature:**
- Structure → QE input → structure roundtrip conversion

**Related production code:**
- `quantumvitas.io.structure_io`
- `quantumvitas.io.parser.qe_parser`
- `quantumvitas.workflow.geometry`

**Key dependencies:**
- Fixtures:
  - `ci_test_data_dir` - Test data directory
  - `sample_input_file` - Sample QE input file
  - `qe_input_files` - Multiple QE input files

**Contained tests:**

- Roundtrip conversion tests
- Geometry preservation tests

### `tests/unit/test_qe_input.py`

**Module / feature:**
- QE input file parsing
- Namelist and card extraction

**Related production code:**
- `quantumvitas.io.parser.qe_parser.QEInputParser`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary directories
  - Sample QE input files

**Contained tests:**

- QE input parsing tests
- Namelist extraction tests
- Card extraction tests

### `tests/unit/test_qe_geometry_roundtrip.py`

**Module / feature:**
- QE geometry format conversion (ibrav, cell_parameters)

**Related production code:**
- `quantumvitas.workflow.geometry`

**Key dependencies:**
- Fixtures:
  - `ci_test_data_dir` - Test data directory
  - `qe_input_files` - QE input files with various geometry formats

**Contained tests:**

- Geometry conversion tests
- Format preservation tests

### `tests/unit/test_qe_executable_detection.py`

**Module / feature:**
- QE executable detection
- QE_HOME resolution

**Related production code:**
- `quantumvitas.core.engines.qe_installation`

**Key dependencies:**
- Fixtures:
  - `monkeypatch` - Environment variable patching
  - `fake_qe_installation` - Mock QE installation

**Contained tests:**

- QE executable detection tests
- QE_HOME resolution tests
- Environment variable handling tests

### `tests/unit/test_qe_modules.py`

**Module / feature:**
- QE module parameter loading
- Module parameter validation

**Related production code:**
- `quantumvitas.data.qe_module_parameters`

**Key dependencies:**
- Fixtures:
  - `project_root_path` - Project root for data files

**Contained tests:**

- Module parameter loading tests
- Parameter validation tests

### `tests/unit/test_step_defaults.py`

**Module / feature:**
- QE parameter defaults application

**Related production code:**
- `quantumvitas.workflow.step_defaults`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary directories
  - Step fixtures

**Contained tests:**

- Default parameter application tests
- Parameter override tests

### `tests/unit/test_parameter_overrides.py`

**Module / feature:**
- CLI parameter override parsing
- Parameter override application

**Related production code:**
- `quantumvitas.cli.main._parse_override_args`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary directories

**Contained tests:**

- Override parsing tests
- Override application tests

### `tests/unit/test_workflow_importers.py`

**Module / feature:**
- Workflow import from QE input files

**Related production code:**
- `quantumvitas.workflow.importers`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary directories
  - QE input files

**Contained tests:**

- Workflow import tests
- Step import tests

### `tests/unit/test_workflow_inputs.py`

**Module / feature:**
- Workflow input file generation

**Related production code:**
- `quantumvitas.workflow.input_runner`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary directories
  - `workflow_project` - Workflow project fixture

**Contained tests:**

- Input generation tests
- Parameter application tests

### `tests/unit/test_structure_steps.py`

**Module / feature:**
- Step creation with structure inheritance

**Related production code:**
- `quantumvitas.api.QVService`
- `quantumvitas.workflow.structure_steps`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary project directories
  - Project fixtures with structures

**Contained tests:**

- Step creation with structure inheritance
- Structure resolution in steps

### `tests/unit/test_analysis_parsers.py`

**Module / feature:**
- QE output parsing (SCF, DOS, bands)

**Related production code:**
- `quantumvitas.analysis.parsers`

**Key dependencies:**
- Data files:
  - `tests/data/analysis_scf/si.0_scf.out` - SCF output file
  - `tests/data/analysis_dos/si.dos.dat` - DOS data file
  - `tests/data/analysis_bands/si.bands.dat.gnu` - Bands data file

**Contained tests:**

- `TestSCFParser` - SCF output parsing
  - `test_parse_scf_basic` - Basic SCF parsing
  - `test_scf_convergence` - Convergence detection
  - `test_scf_iterations` - Iteration extraction
  - `test_scf_total_energy` - Total energy extraction
  - `test_scf_fermi_energy` - Fermi energy extraction

- `TestDOSParser` - DOS data parsing
  - `test_parse_dos_basic` - Basic DOS parsing
  - `test_dos_data_structure` - DOS data structure validation

- `TestBandsParser` - Bands data parsing
  - `test_parse_bands_gnu_basic` - Basic bands parsing
  - `test_bands_data_structure` - Bands data structure validation

### `tests/unit/test_analysis_plotting.py`

**Module / feature:**
- Band structure and DOS plotting

**Related production code:**
- `quantumvitas.analysis.plotting`

**Key dependencies:**
- Data files:
  - `tests/data/analysis_bands/` - Bands data files
  - `tests/data/analysis_dos/` - DOS data files
- Fixtures:
  - `matplotlib_backend` - Non-interactive matplotlib backend

**Contained tests:**

- Band structure plotting tests
- DOS plotting tests
- Plot data validation tests

### `tests/unit/test_analysis_artifacts.py`

**Module / feature:**
- Analysis artifact generation
- Artifact file management

**Related production code:**
- `quantumvitas.analysis.artifacts`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary directories
  - Analysis data fixtures

**Contained tests:**

- Artifact generation tests
- File management tests

### `tests/unit/test_structure_viz.py`

**Module / feature:**
- 3D structure visualization data generation

**Related production code:**
- `quantumvitas.analysis.structure_viz`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary directories
  - Structure fixtures

**Contained tests:**

- Visualization data generation tests
- 3D coordinate calculation tests

### `tests/unit/test_pseudopotential_resolution.py`

**Module / feature:**
- Pseudopotential file lookup
- PP path resolution

**Related production code:**
- `quantumvitas.core.pseudo`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary directories
  - Pseudopotential directory fixtures

**Contained tests:**

- PP file lookup tests
- Path resolution tests

### `tests/unit/test_context.py`

**Module / feature:**
- Path context detection (workflow/structure from CWD)

**Related production code:**
- `quantumvitas.core.context`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary project directories
  - `project_context` - Project context fixture

**Contained tests:**

- Context detection tests
- Workflow/structure resolution from CWD

### `tests/unit/test_daemon.py`

**Module / feature:**
- Daemon core functionality
- RPC request handling

**Related production code:**
- `quantumvitas.daemon.server.QVDaemon`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary directories
  - `QVDaemon` instance

**Contained tests:**

- Daemon initialization tests
- RPC request handling tests
- Error handling tests

### `tests/unit/test_qvservice_gui.py`

**Module / feature:**
- GUI-specific API methods

**Related production code:**
- `quantumvitas.api.QVService`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary project directories
  - Project fixtures

**Contained tests:**

- GUI API method tests
- Data serialization tests

### `tests/unit/test_project_snapshot.py`

**Module / feature:**
- Project snapshot creation and restoration

**Related production code:**
- `quantumvitas.project.snapshot`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary directories
  - `project_dir` - Project directory fixture
  - `snapshot_dir` - Snapshot directory fixture

**Contained tests:**

- Snapshot creation tests
- Snapshot restoration tests
- Snapshot validation tests

### `tests/unit/test_snapshot_id_regeneration.py`

**Module / feature:**
- ULID regeneration in snapshots

**Related production code:**
- `quantumvitas.project.snapshot`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary directories
  - Project fixtures

**Contained tests:**

- ULID regeneration tests
- ID preservation tests

### `tests/unit/test_resource_rename_safety.py`

**Module / feature:**
- Safe resource renaming
- Path updates after rename

**Related production code:**
- `quantumvitas.api.QVService`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary project directories

**Contained tests:**

- Resource rename tests
- Path update tests

### `tests/unit/test_demo_snapshot_restore.py`

**Module / feature:**
- Demo project snapshot/restore

**Related production code:**
- `quantumvitas.api.QVService`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary directories
  - Demo project fixtures

**Contained tests:**

- Demo snapshot tests
- Demo restore tests

### `tests/unit/test_ci_smoke.py`

**Module / feature:**
- Basic smoke tests for CI

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary directories

**Contained tests:**

- Basic functionality smoke tests

### `tests/cli/test_graphene_workflow_setup.py`

**Module / feature:**
- Complete workflow setup via CLI commands

**Related production code:**
- `quantumvitas.cli.main`

**Key dependencies:**
- Data files:
  - `tests/data/13_graphene/graphene.2_scf.in` - Graphene QE input file
- Fixtures:
  - `ci_test_data_dir` - Test data directory
  - `tmp_path` - Temporary directories
  - `CliRunner` - Typer CLI test runner

**Contained tests:**

- `test_graphene_workflow_setup` - Complete workflow setup sequence
  - **What it tests:** End-to-end workflow setup: `qv init project` → `qv import-structure` → `qv init workflow` → `qv init step` → `qv configure workflow`
  - **Dependencies:** Uses `CliRunner.isolated_filesystem()` to simulate `cd` commands, requires `tests/data/13_graphene/graphene.2_scf.in`

- `test_init_step_fails_at_project_root_without_workflow` - Error handling for invalid step init
  - **What it tests:** `qv init step` at project root without `--workflow` fails with clear error message
  - **Dependencies:** Creates project via CLI, then tries to init step at project root

### `tests/cli/test_si_dos_workflow_cli.py`

**Module / feature:**
- DOS workflow execution via CLI

**Related production code:**
- `quantumvitas.cli.main`

**Key dependencies:**
- Data files:
  - `tests/data/4_Si_DOS/` - DOS workflow test data
- Fixtures:
  - `ci_test_data_dir` - Test data directory
  - QE installation (required for execution)

**Contained tests:**

- `test_cli_run_workflow` - Run DOS workflow via CLI
  - **What it tests:** Complete DOS workflow execution (SCF → NSCF → DOS) via CLI commands
  - **Dependencies:** Requires QE installation, uses `tests/data/4_Si_DOS/` test data

### `tests/cli/test_si_dos_workflow_comprehensive.py`

**Module / feature:**
- Comprehensive DOS workflow with analysis

**Related production code:**
- `quantumvitas.cli.main`
- `quantumvitas.analysis`

**Key dependencies:**
- Fixtures:
  - `project_root_path` - Project root for temp directory
  - `test_project_dir` - Temporary project directory (module scope)
  - `project_with_structure` - Project with Si structure (module scope)
  - QE installation (required)

**Contained tests:**

- `TestSiDosWorkflow` - Comprehensive DOS workflow tests
  - `test_run_workflow` - Run complete DOS workflow
  - `test_analyze_dos` - Analyze DOS and generate plot
  - **Dependencies:** Creates project in `temp/test_si_dos_workflow`, requires QE installation

### `tests/cli/test_si_bands_workflow_comprehensive.py`

**Module / feature:**
- Comprehensive bands workflow with manual and auto k-path

**Related production code:**
- `quantumvitas.cli.main`
- `quantumvitas.analysis`

**Key dependencies:**
- Fixtures:
  - `project_root_path` - Project root for temp directory
  - `test_project_dir` - Temporary project directory (module scope)
  - `project_with_structure` - Project with Si structure (module scope)
  - QE installation (required)

**Contained tests:**

- `TestSiBandsWorkflowManualKpath` - Manual k-path workflow
  - `test_run_workflow` - Run bands workflow with manual k-path
  - `test_analyze_bands` - Analyze bands and generate plot

- `TestSiBandsWorkflowAutoKpath` - Auto k-path workflow
  - `test_run_workflow` - Run bands workflow with auto-generated k-path
  - `test_analyze_bands` - Analyze bands and generate plot

- `TestCompareKpaths` - K-path comparison
  - `test_kpaths_are_different` - Verify manual and auto k-paths differ

- `TestBandsWorkflowDataModels` - Data model tests
  - `test_parse_bands_gnu_from_test_data` - Parse bands data from test files
  - `test_parse_scf_from_test_data` - Parse SCF output from test files
  - `test_generate_kpath_for_si` - Generate k-path for Si
  - `test_plot_bands_from_test_data` - Plot bands from test data

### `tests/cli/test_template_workflow.py`

**Module / feature:**
- Template-based workflow creation

**Related production code:**
- `quantumvitas.cli.main`
- `quantumvitas.core.templates`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary directories
  - `CliRunner` - Typer CLI test runner
  - `template_project` - Template project fixture

**Contained tests:**

- `test_template_project_structure` - Template project structure validation
- `test_template_workflow_ulids_consistent` - ULID consistency in templates
- `test_template_structure_copied` - Structure copying from template
- `test_template_workflow_runs` - Template workflow execution
- `test_init_workflow_from_template_with_custom_structure` - Template with custom structure

### `tests/cli/test_cli_show_command_integration.py`

**Module / feature:**
- `qv show` command integration

**Related production code:**
- `quantumvitas.cli.main`

**Key dependencies:**
- Data files:
  - `tests/data/project_examples/` - Example projects
- Fixtures:
  - `CliRunner` - Typer CLI test runner
  - `reference_project_dir` - Reference project directory (module scope)

**Contained tests:**

- `test_cli_show_command_executes_against_references` - Show command against reference projects
  - **What it tests:** `qv show` command works correctly against reference projects in `tests/data/project_examples/`
  - **Dependencies:** Uses `tests/data/project_examples/project1` and `project2_bands` as reference

### `tests/daemon/test_gui_workflow_detail.py`

**Module / feature:**
- Daemon RPC endpoints for workflow detail and structure changes

**Related production code:**
- `quantumvitas.daemon.server.QVDaemon`
- `quantumvitas.api.QVService`

**Key dependencies:**
- Fixtures:
  - `temp_project` - Temporary project with workflow and steps
  - `daemon` - `QVDaemon` instance
- Data:
  - Uses `tests/data/workflow_bands/si.0_scf.in` for structure import

**Contained tests:**

- `TestGetWorkflowDetail` - Workflow detail retrieval
  - `test_get_workflow_detail_has_steps` - Workflow detail includes steps
  - `test_multi_step_workflow_ulid_only_selectors` - Multi-step workflow with ULID selectors

- `TestChangeWorkflowStructure` - Workflow structure changes
  - `test_change_workflow_structure_via_daemon` - Change workflow structure via RPC
  - `test_change_workflow_structure_rejects_project_root_as_selector` - Reject invalid selectors

### `tests/daemon/test_gui_job_and_step_flows.py`

**Module / feature:**
- Daemon RPC endpoints for job submission, step detail, DAG invariants

**Related production code:**
- `quantumvitas.daemon.server.QVDaemon`
- `quantumvitas.daemon.jobs.JobManager`
- `quantumvitas.api.QVService`

**Key dependencies:**
- Fixtures:
  - `temp_project` - Temporary project with workflow and step
  - `daemon` - `QVDaemon` instance
- Data:
  - Uses `tests/data/workflow_bands/si.0_scf.in` for structure import

**Contained tests:**

- `TestJobSubmissionAndListing` - Job submission and listing
  - `test_submit_job_and_list_jobs` - Submit job and list jobs
  - `test_job_list_path_normalization` - Path normalization in job listing

- `TestStepDetailRetrieval` - Step detail retrieval
  - `test_get_step_detail_with_ulid` - Get step detail with ULID selector
  - `test_get_step_detail_requires_ulid_from_workflow_yaml` - ULID must come from workflow.yaml

- `TestDAGInvariants` - DAG model invariants
  - `test_workflow_has_structure_id_ulid` - Workflow has `structure_id` (ULID)
  - `test_step_yaml_no_structure_id` - Step YAML doesn't have `structure_id`

- `TestStepCreationRaceCondition` - Race condition handling
  - `test_immediate_get_step_detail_after_add_step` - Get step detail immediately after creation

- `TestStepDeletion` - Step deletion
  - `test_delete_step_via_daemon_removes_from_workflow_yaml` - Deletion removes from workflow.yaml
  - `test_delete_step_via_daemon_moves_step_file_to_trash` - Deletion moves file to trash
  - `test_delete_step_via_daemon_allows_missing_step_file` - Deletion handles missing file
  - `test_delete_step_via_daemon_invalid_ulid_raises_resource_not_found` - Invalid ULID raises error

### `tests/daemon/test_si_bands_workflow_daemon.py`

**Module / feature:**
- Full bands workflow execution via daemon RPC

**Related production code:**
- `quantumvitas.daemon.server.QVDaemon`
- `quantumvitas.api.QVService`
- `quantumvitas.daemon.jobs.JobManager`

**Key dependencies:**
- Fixtures:
  - `project_root_path` - Project root for temp directory
  - `test_project_dir` - Temporary project directory (module scope)
  - `project_with_structure` - Project with Si structure (module scope)
  - `daemon` - `QVDaemon` instance (class scope)
  - QE installation (required)

**Contained tests:**

- `TestDaemonProtocol` - Daemon protocol tests
  - `test_ping` - Ping endpoint
  - `test_unknown_command` - Unknown command handling

- `TestDaemonProjectOperations` - Project operations
  - `test_get_project_summary` - Get project summary
  - `test_list_structures` - List structures
  - `test_get_structure_vis` - Get structure visualization data

- `TestDaemonWorkflowExecution` - Workflow execution
  - `test_list_workflows` - List workflows
  - `test_run_workflow_via_job_manager` - Run workflow via job manager
  - `test_job_list` - List jobs
  - `test_get_band_structure_data` - Get band structure data
  - `test_analyze_bands_and_generate_plot` - Analyze bands and generate plot

- `TestJobManagerDirectly` - Job manager direct tests
  - `test_job_status_transitions` - Job status transitions
  - `test_job_failure_captured` - Job failure capture
  - `test_cancel_pending_job` - Cancel pending job

- `TestJSONSerializability` - JSON serialization tests
  - `test_project_summary_serializable` - Project summary serialization
  - `test_structures_list_serializable` - Structures list serialization
  - `test_structure_vis_serializable` - Structure visualization serialization

### `tests/integration/test_si_bands_workflow.py`

**Module / feature:**
- SCF → NSCF → Bands → bands.x workflow execution

**Related production code:**
- `quantumvitas.project.model.Project`
- `quantumvitas.workflow.runner.WorkflowRunner`
- `quantumvitas.engine.registry`

**Key dependencies:**
- Data files:
  - `tests/data/7_Si_bandStructure/` - Bands workflow test data
- Fixtures:
  - `ci_test_data_dir` - Test data directory
  - `si_bands_dir` - Si bands test data directory
  - `si_bands_project` - Workflow project created via `create_workflow_project`
  - QE installation (required)
  - Pseudopotentials from `pseudo/` directory

**Contained tests:**

- `TestSiBandsWorkflow` - Bands workflow execution
  - `test_run_full_workflow` - Run complete bands workflow (SCF → NSCF → Bands → bands.x)
  - **What it tests:** Full workflow execution with all steps succeeding
  - **Dependencies:** Uses `create_workflow_project` helper to scaffold project from `tests/data/7_Si_bandStructure/`, requires QE installation

### `tests/integration/test_si_dos_workflow.py`

**Module / feature:**
- SCF → NSCF → DOS workflow execution

**Related production code:**
- `quantumvitas.project.model.Project`
- `quantumvitas.workflow.runner.WorkflowRunner`
- `quantumvitas.engine.registry`

**Key dependencies:**
- Data files:
  - `tests/data/4_Si_DOS/` - DOS workflow test data
- Fixtures:
  - `ci_test_data_dir` - Test data directory
  - `si_dos_dir` - Si DOS test data directory
  - `si_dos_project` - Workflow project created via `create_workflow_project`
  - QE installation (required)
  - Pseudopotentials from `pseudo/` directory

**Contained tests:**

- `TestSiDosWorkflow` - DOS workflow execution
  - `test_run_full_workflow` - Run complete DOS workflow (SCF → NSCF → DOS)
  - **What it tests:** Full workflow execution with all steps succeeding
  - **Dependencies:** Uses `create_workflow_project` helper to scaffold project from `tests/data/4_Si_DOS/`, requires QE installation

### `tests/integration/test_qe_engine.py`

**Module / feature:**
- QE engine input generation and execution

**Related production code:**
- `quantumvitas.core.engines.qe.QuantumEspressoEngine`
- `quantumvitas.io.QEInputGenerator`

**Key dependencies:**
- Fixtures:
  - `engine` - `QuantumEspressoEngine` instance
  - `tmp_path` - Temporary directories
  - QE installation (for execution tests)

**Contained tests:**

- `TestQEEngineInputGeneration` - Input generation
  - `test_generate_input_from_data` - Generate input from structured data
  - `test_parse_input_file` - Parse input file

### `tests/integration/test_qe_executable_integration.py`

**Module / feature:**
- QE executable detection and execution

**Related production code:**
- `quantumvitas.core.engines.qe_installation`

**Key dependencies:**
- Fixtures:
  - `qe_installation` - QE installation fixture (autouse)
  - QE installation (required)

**Contained tests:**

- QE executable detection tests
- QE execution tests

### `tests/integration/test_pw_step_specs.py`

**Module / feature:**
- Various PW step types and input generation

**Related production code:**
- `quantumvitas.workflow.structure_steps`
- `quantumvitas.io.QEInputGenerator`

**Key dependencies:**
- Data files:
  - `tests/data/pw_single_tests/` - PW test input files
- Fixtures:
  - `ci_test_data_dir` - Test data directory
  - `pw_test_files` - PW test files (module scope)
  - QE installation (required)

**Contained tests:**

- Various PW step type tests (scf, nscf, relax, etc.)
- Input generation tests

### `tests/integration/test_pw_scf_ibrav_step_specs.py`

**Module / feature:**
- SCF with different ibrav values

**Related production code:**
- `quantumvitas.workflow.structure_steps`
- `quantumvitas.io.QEInputGenerator`

**Key dependencies:**
- Data files:
  - `tests/data/pw_scf_ibrav/` - SCF ibrav test files
- Fixtures:
  - `ci_test_data_dir` - Test data directory
  - `ibrav_test_files` - ibrav test files (module scope)
  - QE installation (required)

**Contained tests:**

- SCF with various ibrav values (0-14)
- Input generation tests

### `tests/integration/test_pw_quick_tests_ci.py`

**Module / feature:**
- Quick PW tests for CI

**Related production code:**
- `quantumvitas.workflow.runner.WorkflowRunner`

**Key dependencies:**
- Data files:
  - `tests/data/pw_single_tests/` - PW test files
- Fixtures:
  - `ci_test_data_dir` - Test data directory
  - `pw_test_files` - PW test files (module scope)
  - QE installation (required)

**Contained tests:**

- Quick PW calculation tests for CI

### `tests/integration/test_ph_quick_tests.py`

**Module / feature:**
- Phonon calculation tests

**Related production code:**
- `quantumvitas.workflow.runner.WorkflowRunner`

**Key dependencies:**
- Data files:
  - `tests/data/ph_1d/`, `tests/data/ph_2d/` - Phonon test files
- Fixtures:
  - `ci_test_data_dir` - Test data directory
  - `ph_test_files` - Phonon test files (module scope)
  - QE installation (required)

**Contained tests:**

- Phonon calculation tests

### `tests/integration/test_ci_validation.py`

**Module / feature:**
- CI validation workflows

**Related production code:**
- `quantumvitas.workflow.runner.WorkflowRunner`

**Key dependencies:**
- Data files:
  - `ci_test_data_dir` - Test data directory
  - QE installation (required)

**Contained tests:**

- CI validation workflow tests

### `tests/examples/test_cli_usage_examples.py`

**Module / feature:**
- Example CLI command sequences

**Related production code:**
- `quantumvitas.cli.main`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary directories
  - `CliRunner` - Typer CLI test runner

**Contained tests:**

- `TestImportStructureCommand` - Structure import examples
  - `test_import_structure_from_cif` - Import from CIF
  - `test_import_structure_with_custom_format` - Import with custom format
  - `test_import_structure_duplicate_id_fails` - Duplicate ID handling

- `TestRunStructureCommand` - Structure run examples
  - `test_run_structure_basic` - Basic structure run
  - `test_run_structure_with_parameter_overrides` - Run with parameter overrides

- `TestRunStepCommand` - Step run examples
  - `test_run_step_with_overrides` - Run step with overrides

### `tests/examples/test_structure_io_examples.py`

**Module / feature:**
- Example structure import/export

**Related production code:**
- `quantumvitas.io.structure_io`

**Key dependencies:**
- Fixtures:
  - `tmp_path` - Temporary directories
  - Structure files

**Contained tests:**

- Structure import/export examples

## 4. Fixtures & Shared Test Infrastructure

### Global Fixtures (`tests/conftest.py`)

- **`project_root_path`** (session scope)
  - Returns the project root path (`Path(__file__).parent.parent`)
  - Used by tests that need to reference project root for data files

- **`ci_test_data_dir`** (session scope)
  - Returns path to `tests/data` directory
  - Skips test if data directory doesn't exist
  - Used by tests that need test data files

- **`sample_input_file`** (function scope)
  - Returns path to a sample QE input file
  - Prefers `tests/data/pw_single_tests/scf-cg.in`, falls back to tutorial examples if available
  - Used by tests that need a sample QE input file

- **`cleanup_temp_outdir`** (autouse, function scope)
  - Automatically cleans up `temp/outdir` before and after each test
  - Prevents test pollution from output files

- **`reset_qe_registry`** (autouse, function scope)
  - Resets QE home registry before and after each test
  - Prevents test pollution where a unit test's fake QE installation persists into CLI tests

### Daemon Fixtures (`tests/daemon/conftest.py`)

- **`project_root_path`** (session scope)
  - Returns the project root path
  - Same as global fixture

### Helper Modules

- **`tests/utils/workflow_projects.py`**
  - `create_workflow_project()` - Scaffolds a temporary workflow project from test data
  - Creates project structure, workflows, steps, and copies pseudopotentials
  - Used by integration tests that need a complete project setup

- **`tests/core/test_data.py`**
  - `load_test_cases()` - Loads test case data
  - Used by tests that need structured test case data

- **`tests/core/qe_test_utils.py`**
  - QE test utilities
  - Used by QE-related tests

- **`tests/core/qe_step_runner.py`**
  - QE step runner utilities
  - Used by QE execution tests

- **`tests/core/qe_step_verification.py`**
  - QE step verification utilities
  - Used by QE verification tests

## 5. Coverage Notes & Gaps

### Well-Covered Areas

1. **Core Models** - Extensive coverage of project/workflow/step models, DAG structure, ULID validation
2. **Resource Resolution** - Comprehensive selector resolution tests (ULID, slug, path, name)
3. **Legacy Migration** - End-to-end migration test
4. **CLI Commands** - Good coverage of main CLI commands (init, run, configure, analyze)
5. **Daemon RPC** - Good coverage of GUI backend endpoints
6. **Analysis Parsing** - Good coverage of SCF/DOS/bands output parsing
7. **Structure I/O** - Good coverage of structure import/export and format conversion

### Lightly Tested Areas

1. **GUI Frontend** - No direct GUI tests (GUI tests are in `gui/tests/` with Playwright)
2. **Error Recovery** - Some error paths may not be fully covered
3. **Concurrent Operations** - Limited testing of concurrent job execution
4. **Large Projects** - Limited testing with large numbers of structures/workflows/steps
5. **Network/Remote Operations** - No tests for remote file access or network operations
6. **Performance** - No performance/load tests

### Missing Test Areas

1. **GUI E2E Tests** - GUI E2E tests are in `gui/tests/e2e/` (Playwright), not in pytest suite
2. **Migration Edge Cases** - More edge cases for legacy project migration
3. **Resource Renaming Edge Cases** - More edge cases for resource renaming (conflicts, circular references)
4. **Snapshot Edge Cases** - More edge cases for snapshot creation/restoration
5. **QE Module Parameter Validation** - More validation tests for QE module parameters
6. **Workflow Template System** - More comprehensive template system tests
7. **Analysis Plotting Edge Cases** - More edge cases for plotting (empty data, malformed data)
8. **Pseudopotential Resolution Edge Cases** - More edge cases for PP resolution (missing files, invalid formats)

### Test Data Dependencies

**Critical test data files:**
- `tests/data/13_graphene/graphene.2_scf.in` - Used by graphene workflow setup test
- `tests/data/4_Si_DOS/` - Used by DOS workflow tests
- `tests/data/7_Si_bandStructure/` - Used by bands workflow tests
- `tests/data/workflow_bands/` - Used by daemon workflow tests
- `tests/data/analysis_*` - Used by analysis parser/plotting tests
- `tests/data/pw_single_tests/` - Used by PW step tests
- `tests/data/pw_scf_ibrav/` - Used by ibrav tests
- `tests/data/ph_*` - Used by phonon tests
- `tests/data/project_examples/` - Used by CLI show command test

**Pseudopotential dependencies:**
- `pseudo/` directory - Contains pseudopotential files used by integration tests
- Tests copy pseudopotentials into project directories

### External Dependencies

**Required for integration tests:**
- Quantum ESPRESSO installation (QE executables: `pw.x`, `bands.x`, `dos.x`, `ph.x`, etc.)
- QE_HOME environment variable or QE in PATH
- Pseudopotential files (in `pseudo/` directory)

**Optional dependencies:**
- Matplotlib (for plotting tests)
- NumPy (for analysis tests)
- pymatgen (for structure operations)

### Test Execution Notes

- **Unit tests** (`tests/unit/`) - Fast, no QE required, run in CI
- **CLI tests** (`tests/cli/`) - May require QE, run via CLI commands
- **Integration tests** (`tests/integration/`) - Require QE installation, run QE calculations
- **Daemon tests** (`tests/daemon/`) - Test daemon RPC endpoints, may require QE for workflow execution
- **Example tests** (`tests/examples/`) - Example usage patterns, typically fast

Tests are automatically marked based on location and can be filtered using pytest markers:
- `pytest -m unit` - Run only unit tests
- `pytest -m qe_core` - Run only integration tests
- `pytest -m qe_cli` - Run only CLI tests
