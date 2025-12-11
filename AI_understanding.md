# AI Understanding of QuantumVITAS (Python v2)

> **Purpose**: This document captures architectural knowledge, conventions, and lessons learned
> to help future AI assistants quickly understand the QuantumVITAS Python codebase.

---

## 1. Project Overview

QuantumVITAS is a workflow engine and GUI layer for **Quantum ESPRESSO (QE)** ab-initio simulations.
The Python v2 rewrite (in `v2-python` branch) replaces the original Java GUI with a modern
Python implementation featuring:

- **Typer CLI** (`qv` command) for all operations
- **Workflow engine** for multi-step QE calculations
- **Project model** for organizing structures, workflows, and steps
- **Automatic QE detection** across platforms

### Key Directories

```
src/quantumvitas/
├── api.py               # QVService - stable interface for CLI and GUI
├── cli/                 # Typer CLI implementation (main.py is ~2600 lines)
├── core/
│   ├── engines/         # QE engine, installation detection, pseudopotentials
│   ├── resources.py     # ResourceMeta model (ULID, slug, name, path)
│   ├── models.py        # Dataclass models with load/save (WorkflowModel, etc.)
│   ├── resolution.py    # Centralized selector→resource resolution
│   ├── context.py       # PWD context helper for CLI (max_depth=20)
│   ├── project_utils.py # Extracted helpers for project/config manipulation
│   └── templates.py     # Template copying utilities
├── io/                  # QE input/output parsing and generation
│   ├── parser/          # QEInputParser
│   ├── generator/       # QEInputGenerator
│   ├── model.py         # QEInput, QENamelist, QECard, etc.
│   └── structure_io.py  # pymatgen-based structure I/O
├── project/             # Project model (project.qv.yml)
├── workflow/            # Workflow execution, steps, verification
├── analysis/            # Post-processing (energy, bands, DOS)
├── engine/              # High-level engine registry
└── data/                # QE parameter metadata JSON
```

---

## 2. Core Concepts

### 2.1 Resource Model

All resources (projects, workflows, structures, steps) share a common metadata model:

```python
@dataclass
class ResourceMeta:
    id: str       # ULID (Universally Unique Lexicographically Sortable Identifier)
    name: str     # Human-readable name
    slug: str     # URL-safe identifier (auto-generated from name)
    path: Path    # Filesystem path (relative to project root)
    kind: str     # "project" | "workflow" | "structure" | "step"
```

**Key principles**:
- `id` is a ULID, never changes, never input by user
- `name` is human-readable, can be renamed
- `slug` is auto-generated from `name` via `slugify()`
- CLI commands accept `name`, `slug`, or `path` - never raw `id`

### 2.2 Project Structure

A QuantumVITAS project is a directory containing:

```
project/
├── project.qv.yml       # Project metadata and registry
├── structures/          # Structure JSON files (pymatgen format)
├── workflows/
│   └── <workflow-slug>/
│       ├── workflow.yaml    # Workflow definition with structure reference
│       ├── steps/           # Step YAML specifications
│       ├── raw/             # Working directory for QE execution
│       └── reference/       # Reference outputs for verification
├── pseudo/              # Pseudopotential files
└── trash/               # Soft-deleted resources
```

### 2.3 Workflow and Step YAML Structure

**workflow.yaml** (ID-only cross-references):
```yaml
meta:
  id: 01JXYZ123ABC456DEF789GHI  # ULID
  name: si-dos
  slug: si-dos
  path: workflows/si-dos
  kind: workflow
mode: normal
structure_id: 01SABC123...        # Structure reference (ULID only)
structure_name: Si               # Optional display name (cosmetic)
working_dir: raw
steps:
- step_id: 01TXYZ789...          # Step reference (ULID only)
  step_file: steps/scf.step.yaml
- step_id: 01TUVW456...
  step_file: steps/nscf.step.yaml
```

**step.yaml** (StructureStepSpec, ID-only cross-references):
```yaml
meta:
  id: 01KB8FEQWVYJAB16NMRVZ7JYEG  # ULID
  name: scf
  slug: scf
  path: scf.step.yaml
  kind: step
# DAG + ID-only model: NO structure_id or parent_workflow_id in step YAML
# Structure is inherited from workflow.structure_id
# Parent workflow is implicit from file location (workflows/<slug>/steps/<step>.step.yaml)
step_type: scf
parameters:
  CONTROL:
    calculation: scf
  SYSTEM:
    ecutwfc: 50
cards:
  K_POINTS:
    option: automatic
    data: [[8, 8, 8, 0, 0, 0]]
species_overrides:
  Si:
    mass: 28.0855
    pseudopot: Si.pbe-n-rrkjus_psl.1.0.0.UPF
```

### 2.4 QE Input Model

QE inputs are represented as structured objects:

```python
QEInput
├── namelists: List[QENamelist]   # &CONTROL, &SYSTEM, &ELECTRONS, etc.
├── cards: List[QECard]           # ATOMIC_SPECIES, ATOMIC_POSITIONS, K_POINTS, etc.
└── module: QEModule              # PW, PH, DOS, BANDS, etc.
```

**Roundtrip parsing**: `QEInputParser.parse_file()` → modify → `QEInputGenerator.write_file()`

### 2.5 Workflow Execution

```
WorkflowRunner.run(workflow)
    └── for each step:
        └── engine.run_step(step, working_dir)
            └── subprocess: pw.x < input.in > output.out
        └── evaluate_step_result() → SUCCESS/FAILED
```

**Modes**:
- `StepMode.LENIENT`: Pass if "JOB DONE" found in output
- `StepMode.STRICT`: Compare energy/Fermi level against reference

---

## 3. QE Installation Detection

### 3.1 Internal Registry (Important!)

The QE home path is stored in an **internal Python registry**, NOT `os.environ["QE_HOME"]`.
This prevents test pollution and external process interference.

```python
from quantumvitas.core.engines import get_qe_home, set_qe_home, reset_qe_home

# Get (triggers auto-detection on first call)
qe_home = get_qe_home()

# Set programmatically
set_qe_home(Path("/path/to/qe"))

# Reset to re-run detection
reset_qe_home()
```

### 3.2 Detection Order

1. **`QE_HOME` environment variable** - Read ONCE at startup
2. **System PATH** - `which pw.x` → infer `../..` as QE home
3. **Shell config files** - Parse `~/.zshrc`, `~/.zprofile`, `~/.zshenv`, `~/.bashrc`, `~/.bash_profile`, `~/.profile`
4. **Home directory scan** - Search `$HOME/**/q-e-qe*`

### 3.3 Caveat: Test Isolation

Tests that create fake QE installations must restore the registry:

```python
@pytest.fixture(autouse=True)
def preserve_qe_home():
    original = get_qe_home()
    yield
    if original:
        set_qe_home(original)
    else:
        reset_qe_home()
```

---

## 4. CLI Architecture

### 4.1 Command Structure (Current State)

The CLI uses Typer with sub-apps. All commands support `--project PATH` for explicit project specification:

```
qv
├── init
│   ├── project [--path PATH] [--name NAME] [--snapshot SNAPSHOT]
│   ├── workflow <name> [--structure STRUCT] [--parent WF] [--template TEMPLATE]
│   └── step <type> [--structure STRUCT] [--workflow WF] [overrides...]
├── import-structure <file> [--name NAME]
├── list [--verbose]
├── configure (PREFERRED for renaming)
│   ├── step <step-id|path> [--name NAME] [--workflow WF] [--remove] [overrides...]
│   ├── workflow [<selector>] [--name NAME] [--structure STRUCT] [--reorder s1,s2,...]
│   └── structure <selector> [--name NAME]
├── rename (DEPRECATED - use configure --name instead)
│   ├── project [--name NAME] [--slug SLUG] [--path PATH]
│   ├── workflow <selector> [--name NAME]
│   ├── step <workflow> <step-id> [--id NEW_ID]
│   └── structure <selector> [--name NAME]
├── delete
│   ├── project [<selector>]
│   ├── workflow [<selector>] [--force] [--cascade]
│   ├── step <step-id> [--workflow WF]
│   ├── structure <selector> [--force] [--cascade]
│   └── trash [--parent]
├── run
│   ├── step <input.in|step.yaml> [--workdir PATH] [overrides...]
│   ├── workflow [<selector>] [--strict] [--verbose]
│   ├── structure <selector> [--type TYPE] [overrides...]
│   └── (auto-dispatch if target given without subcommand)
├── detect-qe [--path PATH]
├── show-command <input.in>  # Auto-detects module type (pw.x, bands.x, etc.)
├── get-command <input.in>   # alias for show-command
├── analyze
│   ├── band [<file>] [--workflow WF] [--symmetry FILE] [--scf FILE] [--plot]
│   ├── dos <file> [--scf FILE] [--plot] [--energy-range MIN,MAX]
│   ├── energy <file> [--plot]  # SCF convergence analysis
│   ├── scf <file> [--plot]     # alias for energy
│   ├── structure <selector> [--supercell "a b c"] [--repeat-boundary]
│   └── output [DEPRECATED] <kind> <file>  # Use band/dos/energy instead
└── params <module> [--section SECTION]
```

### 4.2 Resource Resolution

Resources can be identified by:
- **name/slug**: Case-insensitive match (e.g., `si_dos`, `"Si DOS"`)
- **path**: Relative or absolute filesystem path

**Auto-detection from current directory**:
- `find_project_root()`: Walks up to find `project.qv.yml`
- `find_enclosing_workflow()`: Detects if pwd is inside a workflow (uses directory path matching)
- `PathContext` (`core/context.py`): Scans upward to find project/workflow/step context
- Used by `qv run workflow`, `qv init step`, `qv analyze band`, etc.

**Important**: For workflow auto-detection, prefer `find_enclosing_workflow()` over `PathContext.workflow_selector` because it uses directory paths (more reliable after renames). See section 26.4 for details.

Key utility: `resolve_resource()` in `core/project_utils.py`

### 4.3 Parameter Overrides

CLI supports QE parameter overrides with special syntax:

| Syntax | Effect |
|--------|--------|
| `--ecutwfc=60` | Set namelist parameter (auto-detects section) |
| `--SYSTEM.ecutwfc=60` | Explicit section prefix |
| `--CARD.K_POINTS.data=[[6,6,6,0,0,0]]` | Replace card data |
| `--k_points=automatic:6,6,6,0,0,0` | Card shorthand |
| `--SPECIES.Si.pseudopot=Si.UPF` | Atomic species field |
| `--tprnfor` | Boolean true |
| `--tprnfor=false` | Boolean false |

### 4.4 API Architecture

**Architecture Goal**: CLI should be thin wrappers around `QVService` methods.

```
INTENDED ARCHITECTURE:
    CLI (main.py) → api.py (QVService) → core/* modules
                                       → workflow/*
                                       → analysis/*

CURRENT STATE (Partial):
    - analyze commands: ✅ Uses QVService (fixed 2025-12-05)
    - init/configure/delete: ⚠️ Mixed (some use QVService, some bypass)
    - run commands: ⚠️ Bypasses QVService
```

**`api.py` (`QVService`)** provides a clean service layer:
- All methods receive `project_root` explicitly (never use `os.getcwd()`)
- Uses selectors (name/slug/path) for resources
- Raises `QVServiceError` for all errors
- Provides consistent interface for CLI, GUI, and scripts

**`cli/main.py`** should be a thin wrapper:
- Parse CLI arguments with Typer
- Call `QVService` methods
- Convert `QVServiceError` to `typer.BadParameter`
- Format output for terminal

**For new implementations**: Always add functionality to `QVService` first, then call from CLI.

**Files**:
- **`core/project_utils.py`**: Low-level config helpers that raise `ValueError`, `ResourceNotFoundError`
- **`api.py`**: Service layer (`QVService`) that should be the single entry point
- **`cli/main.py`**: Thin CLI wrapper (currently too thick)

---

## 5. Recent Implementations (2025-11-30)

### 5.1 Configure Workflow Command

`qv configure workflow` now supports:

```bash
# Change structure for workflow and all its steps
qv configure workflow --structure new_structure

# Reorder steps in workflow
qv configure workflow --reorder scf,nscf,dos

# Both at once
qv configure workflow si_dos --structure si --reorder scf,nscf
```

When `--structure` is used, the command:
1. Validates the new structure exists
2. Updates `workflow.yaml` 
3. Iterates through all step YAML files and updates their `structure` field

### 5.2 Parent Workflow ID in Steps

Steps now have an optional `parent_workflow_id` field linking them to their parent workflow:

```python
@dataclass
class StructureStepSpec:
    meta: ResourceMeta
    structure: str
    step_type: str = "scf"
    parameters: Dict[str, Dict[str, Any]]
    cards: Dict[str, Dict[str, Any]]
    species_overrides: Dict[str, Dict[str, Any]]
    parent_workflow_id: Optional[str] = None  # NEW
```

This enables:
- Tracking step provenance
- Structure consistency validation when running steps

### 5.3 Init Step: Type Required, Structure Optional

`qv init step` syntax changed to make step type required (validated against known types):

```bash
# Known step types:
# scf, nscf, relax, vc-relax, md, vc-md, dos, bands, bands_pw,
# ph, q2r, matdyn, dynmat, pp, projwfc, custom

# With explicit structure
qv init step scf --structure si

# Inside workflow directory (structure inherited)
cd project/workflows/si-dos
qv init step nscf
# Output: "Using structure 'si' from parent workflow"

# Outside workflow without structure = ERROR
qv init step scf  # Error: Structure required
```

### 5.5 Structure Validation on Step Run

When running a step that has `parent_workflow_id`:

```python
def _validate_step_structure_consistency(spec, spec_path, project_root):
    # Loads parent workflow, checks structure field
    # Shows warning if step.structure != workflow.structure
```

This is a warning only (doesn't block execution) to maintain compatibility with standalone steps.

### 5.6 Post-Processing Step Types (DOS, Bands, etc.)

Post-processing steps (dos.x, bands.x, projwfc.x, etc.) now generate correct input format:

```python
# Post-processing step types that don't need structure-based input
POST_PROCESSING_STEP_TYPES = {
    "dos", "bands", "projwfc", "pp", "q2r", "matdyn", "dynmat",
    "sumpdos", "band_interpolation", "ppacf", "pprism",
}
```

When generating input from a step spec with these types:
- Only the appropriate namelist is created (e.g., `&DOS ... /`)
- No structure cards (ATOMIC_SPECIES, ATOMIC_POSITIONS, etc.)
- Parameters are mapped to the correct namelist (DOS → &DOS)

Example DOS input generation:
```python
spec = StructureStepSpec(step_type="dos", parameters={"DOS": {"prefix": "si"}})
qe_input, _ = generate_qe_input_from_spec(struct, spec)
# Generates: &DOS prefix = 'si' /
```

### 5.7 Reduced Input File Output

Previously, `run_input_step()` created multiple debug copies:
- `pw.in`, `pw_original.in`, `pw_modified.in`, `pw_work.in`

Now:
- When running from step spec: Only the final input file is created
- When running from `.in` file: Original is preserved as `<name>_original.in` only if modified

Control via `keep_original` parameter:
```python
run_input_step(..., keep_original=False)  # For step specs
run_input_step(..., keep_original=True)   # Default for raw .in files
```

### 5.7 Configure Structure Command

Basic implementation for renaming structures:

```bash
qv configure structure si --name "Silicon bulk"
```

### 5.8 Step Parameter Defaults vs Import Semantics

QuantumVITAS distinguishes two distinct scenarios for step creation, each with different default parameter behavior:

#### Scenario A: "Create Step from Scratch" (Uses QV Defaults)

**Sources:**
- `qv init step <type>` (without `--no-defaults`)
- GUI "Add Step" (type = scf / nscf / bands / dos / ...)
- `reset_step_params` (reset to QV defaults)

**Behavior:**
- Step spec parameters and cards include QV's in-code default parameters
- Defaults are defined in `workflow/step_defaults.py` per step type
- Common defaults include:
  - `CONTROL.outdir = "./outdir"`
  - `CONTROL.restart_mode = "from_scratch"`
  - `ELECTRONS.conv_thr = 1.0e-08`
  - Step-type-specific defaults (e.g., `K_POINTS` for scf/nscf)
- Generated QE input includes these defaults
- User-provided parameters override defaults (merged behavior)

**Example:**
```bash
qv init step scf --structure si
# Creates step with defaults: outdir, restart_mode, conv_thr, etc.
```

#### Scenario B: "Import Existing QE Input" (Preserves Original)

**Sources:**
- `qv init step <type> --no-defaults` (with parameters extracted from QE input)
- `show-command` → `qv init step` workflow (suggests `--no-defaults`)
- Future GUI "Import QE Input" flow

**Behavior:**
- Step spec parameters reflect only what was in the original input file
- No QV defaults are injected (no `outdir`, `restart_mode`, `conv_thr` unless present in original)
- Round-trip preservation: original QE input → step spec → generated QE input should match
- Run-time tweaks like `set_outdir_to_temp()` are allowed at execution time but not persisted back to the spec

**Example:**
```bash
qv show-command si_scf.in
# Suggests: qv init step scf --no-defaults --CONTROL.calculation=scf ...
# This preserves original parameters without injecting defaults
```

**Implementation Details:**
- `init_step_command` in `cli/main.py` accepts `--no-defaults` flag
- When `--no-defaults` is set, `apply_defaults=False` in parameter merging
- `build_step_spec_from_qe_input()` in `workflow/importers.py` accepts `apply_defaults` parameter (defaults to `False` for import scenarios)
- `reset_step_params()` always uses `apply_defaults=True` (Scenario A)

**GUI Wiring:**
- **GUI "Add Step"** (`WorkflowDetailPanel.handleAddStep`):
  - Calls RPC `add_step_to_workflow` → `QVService.add_step_to_workflow` → `init_step`
  - Uses `apply_defaults=True` (Scenario A: from-scratch with QV defaults)
  - Steps created this way include `outdir`, `restart_mode`, `conv_thr`, etc.
  
- **GUI "Import QE Input"** (`WorkflowDetailPanel.handleImportStep`):
  - Calls RPC `import_step_from_qe_input` → `QVService.import_step_from_qe_input`
  - Uses `apply_defaults=False` (Scenario B: preserve original parameters)
  - Steps imported this way only contain parameters from the original QE input file
  
- **GUI "Reset Step Parameters"** (`StepDetailPanel.handleResetParams`):
  - Calls RPC `reset_step_params` → `QVService.reset_step_params`
  - Uses `apply_defaults=True` (Scenario A: reset to QV defaults)
  - Always resets to in-code defaults, not to "original QE input file"

**Decision Tree:**
```
Create Step
├─ From scratch (GUI "Add Step", CLI `qv init step` without --no-defaults)
│  └─ apply_defaults=True → QV defaults included
│
└─ Import existing QE input (GUI "Import QE Input", CLI `qv init step --no-defaults`)
   └─ apply_defaults=False → Original parameters preserved

Reset Step Parameters
└─ Always apply_defaults=True → Reset to QV defaults
```

**Historical Context:**
- Older behavior tended to always inject defaults, which broke round-trip import scenarios
- Tests have been updated to reflect the clarified semantics:
  - `test_init_step_scf_uses_defaults`: Verifies Scenario A (defaults present)
  - `test_import_step_from_qe_input_does_not_inject_defaults`: Verifies Scenario B (no defaults)
  - E2E tests in `gui/tests/e2e/step_defaults.spec.ts` verify GUI wiring

Updates:
- Entry in `project.qv.yml`
- Renames the structure file
- Updates metadata inside the JSON file

---

## 6. Testing

### 6.1 Test Categories

| Marker | Description | Requires QE |
|--------|-------------|-------------|
| `unit` | Parser, model tests | No |
| `qe_core` | Engine integration tests | Yes |
| `qe_cli` | CLI integration tests | Yes |

### 6.2 Test Status (as of 2025-11-30)

```
tests/unit/          78 tests PASS
tests/cli/            7 tests PASS (requires QE installed)
─────────────────────────────────
Total:               85 tests PASS
```

**Note**: CLI tests require QE to be installed. QE is auto-detected via:
1. `QE_HOME` env var (if set)
2. System PATH (`which pw.x`)
3. Shell config files (`~/.zshrc`, `~/.zprofile`, `~/.zshenv`, `~/.bashrc`, `~/.bash_profile`, `~/.profile`)
4. Home directory scan (`~/src/q-e-qe*`, etc.)

### 6.3 CI Test Data

Small bundled test cases in `tests/data/`:
- `pw_single_tests/` - Single-point SCF tests
- `pw_scf/` - Basic SCF tests
- `4_Si_DOS/` - Si DOS workflow
- `7_Si_bandStructure/` - Si bands workflow

**Analysis test data** in `tests/data/analysis_*/`:
- `analysis_scf/` - SCF output files
- `analysis_dos/` - DOS data files  
- `analysis_bands/` - Band structure files with symmetry

### 6.4 Running Tests

```bash
# Activate virtual environment
source .venv/bin/activate

# Run unit tests only (no QE needed)
python -m pytest tests/unit/ -v

# Run all tests (requires QE)
python -m pytest tests/ -v

# Run specific categories
python -m pytest -m unit          # No QE needed
python -m pytest -m qe_core       # Needs QE
python -m pytest tests/cli/       # CLI tests (needs QE)
```

### 6.5 Common Test Issues

1. **Mock function signatures**: When mocking `run_input_step`, include all parameters:
   ```python
   def fake_run_input_step(
       *, engine, input_file, working_dir, project_root,
       step_type=None, parameter_overrides=None,
       keep_original=True,  # Don't forget new parameters!
   ):
   ```

2. **Slugification mismatch**: CLI creates dirs with `slugify(name)`, tests must match

3. **QE_HOME pollution**: Use `reset_qe_home()` fixture

---

## 7. Key Files Reference

| File | Purpose | Lines |
|------|---------|-------|
| `cli/main.py` | All CLI commands | ~2600 |
| `core/project_utils.py` | Resource resolution, config helpers | ~920 |
| `core/engines/qe_installation.py` | QE detection logic | ~470 |
| `core/engines/qe.py` | QE engine implementation | ~550 |
| `core/engines/qe_workflow.py` | Step/workflow execution | ~320 |
| `workflow/structure_steps.py` | StructureStepSpec model, post-processing input generation | ~450 |
| `core/templates.py` | Template copying utilities | ~350 |
| `workflow/input_runner.py` | Input preparation and execution | ~540 |
| `io/parser/qe_parser.py` | QE input parsing | ~420 |
| `io/model.py` | QE data structures | ~230 |
| `workflow/runner.py` | Workflow orchestration | ~95 |
| `project/model.py` | Project/Workflow models | ~260 |

---

## 8. Conventions

### 8.1 Error Handling

- **CLI layer**: Use `typer.BadParameter`, `typer.Exit(1)`
- **Core layer**: Raise `ValueError`, `FileNotFoundError`, `ResourceNotFoundError`

### 8.2 Path Handling

- Always use `Path` objects, not strings
- Use `.expanduser()` for `~` expansion
- Use `.resolve()` for symlink resolution (wrap in try/except for broken links)
- Store paths relative to project root in YAML files

### 8.3 YAML Files

- `project.qv.yml` - Project metadata
- `workflow.yaml` - Workflow definition (includes `structure_id` ULID reference)
- `*.step.yaml` - Step specifications (DAG model: NO `parent_workflow_id` or `structure_id` - these are inherited from workflow)

### 8.4 Structure Storage

Structures are stored as pymatgen JSON with embedded metadata:

```json
{
  "@module": "pymatgen.core.structure",
  "@class": "Structure",
  "lattice": {...},
  "sites": [...],
  "_meta": {
    "id": "01JXYZ...",
    "name": "Si bulk",
    "slug": "si-bulk",
    "kind": "structure"
  }
}
```

---

## 9. Lessons Learned / Caveats

### 9.1 Environment Variables

❌ **Don't** store state in `os.environ` - it's mutable by external processes.
✅ **Do** use internal registries with explicit APIs.

### 9.2 CLI ID vs Name

❌ **Don't** expose ULID to users in CLI commands
✅ **Do** use name/slug/path for user-facing identifiers

### 9.3 Structure Consistency

Workflows reference a single structure in `workflow.yaml`. Steps also have a `structure` field.
When changing a workflow's structure, use `qv configure workflow --structure` which updates all steps.

### 9.4 QE Input Quirks

- QE uses Fortran-style booleans: `.true.`, `.false.`, `t`, `f`
- Card options are case-sensitive: `ATOMIC_POSITIONS angstrom`
- Some namelists are optional (e.g., `&IONS` only for relaxation)
- K_POINTS can be `automatic`, `gamma`, `crystal`, `tpiba`, etc.

### 9.5 Workflow Verification

The verification logic checks:
1. "JOB DONE" in output (basic success)
2. Energy comparison against reference (strict mode)
3. Fermi energy comparison (for NSCF/DOS/bands)

Tolerances:
- Total energy: 1e-5 Ry
- Fermi energy: 1e-2 eV (note: units are eV for Fermi energy)

### 9.6 New Feature Implementation Pattern

When adding new functionality, follow this pattern:

1. **Add to `QVService` first** (`api.py`):
   ```python
   @staticmethod
   def new_feature(project_root: Path, selector: str, **kwargs) -> Result:
       """Implement the core logic here."""
       # 1. Resolve resources
       resource = resolve_workflow(project_root, selector)
       # 2. Load models
       model = load_workflow(resource.absolute_path, project_root)
       # 3. Perform operation
       # 4. Save models
       save_workflow(model, resource.absolute_path)
       return result
   ```

2. **Add CLI wrapper** (`cli/main.py`):
   ```python
   @app.command("new-feature")
   def new_feature_command(...):
       try:
           result = QVService.new_feature(project_root, selector, **kwargs)
           typer.echo(f"Success: {result}")
       except QVServiceError as e:
           raise typer.BadParameter(str(e))
   ```

3. **Never**:
   - Import `core/project_utils.py` directly in CLI
   - Use `Path.cwd()` in `QVService` methods
   - Duplicate logic between CLI and `QVService`

---

## 10. Quick Start for AI Assistants

### Reading Order

1. `core/resources.py` - ResourceMeta pattern
2. `core/models.py` - Dataclass models with load/save (WorkflowModel, ProjectModel)
3. `core/resolution.py` - Centralized selector→resource resolution
4. `core/context.py` - PWD context helper for CLI
5. `api.py` - QVService stable interface
6. `workflow/structure_steps.py` - StructureStepSpec (step YAML model)
7. `io/model.py` - QE input structure
8. `cli/main.py` - CLI commands (large file, use semantic search)

### Common Tasks

| Task | Key Files |
|------|-----------|
| Add CLI command | `cli/main.py` |
| Add configure option | `cli/main.py` (look for `@configure_app.command`) |
| Modify resource resolution | `core/resolution.py` |
| Add service layer method | `api.py` (`QVService` class) |
| Modify PWD context detection | `core/context.py` |
| Add/modify resource models | `core/models.py` |
| Modify QE detection | `core/engines/qe_installation.py` |
| Add QE module support | `io/parser/qe_parser.py`, `core/engines/qe.py` |
| Change step spec format | `workflow/structure_steps.py` |
| Change workflow execution | `workflow/runner.py`, `core/engines/qe_workflow.py` |
| Modify verification | `workflow/verification.py` |
| Add template support | `core/templates.py` |

### Development Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e '.[dev]'

# Run tests
python -m pytest tests/unit/ -v
```

---

## 11. GUI Implementation (Electron + React)

The GUI is implemented as an Electron desktop application with React/TypeScript frontend:

### 11.1 Architecture

```
┌─────────────────────────────────────────────┐
│              React Frontend                  │
│  ┌─────────────┐ ┌──────────────────────┐  │
│  │   Sidebar   │ │    Main Panel        │  │
│  │  + Actions  │ │  (view-based)        │  │
│  └─────────────┘ └──────────────────────┘  │
│               │                             │
│        window.qv.request()                  │
└───────────────┼─────────────────────────────┘
                │ IPC (contextBridge)
┌───────────────┼─────────────────────────────┐
│          Electron Main Process              │
│         spawn() JSON-RPC daemon             │
└───────────────┼─────────────────────────────┘
                │ stdio (JSON lines)
┌───────────────┼─────────────────────────────┐
│           Python Daemon                     │
│    QVDaemon → QVService → core modules      │
└─────────────────────────────────────────────┘
```

### 11.2 Key Features

#### Core Features (2025-12-07)
| Feature | Implementation |
|---------|---------------|
| Resizable daemon logs panel | DebugPanel with drag handle |
| Resizable list panels | ResizablePane component |
| Drag-and-drop step reordering | Native HTML5 DnD in WorkflowDetailPanel |
| Add step to workflow | add_step_to_workflow in QVService + daemon handler |
| Supercell visualization | Controls in StructureViewer3D, params to get_structure_vis |
| Boundary atom repetition | repeat_boundary param in structure visualization |
| Context-aware element legend | Filter legend to only present elements |
| Summary auto-refresh | refreshSummary() called after CRUD operations |

#### UI/UX Enhancements (2025-01-XX)
| Feature | Implementation |
|---------|---------------|
| Theme switching (dark/light) | CSS variables with `[data-theme="light"]` selector, Settings panel toggle |
| Reveal in Finder/Explorer | `shell.showItemInFolder()` IPC handler, `window.qv.revealPath()` API |
| Automatic analysis selection | `detectAnalysisType()` based on workflow's last step type |
| Automatic analysis loading | Settings toggle, auto-loads when workflow selected (if enabled) |
| Band structure ylim control | Energy range inputs update YAxis domain dynamically |

### 11.3 Daemon Methods for GUI

Key methods exposed via JSON-RPC:

```python
# Project operations
"get_project_summary" → QVService.get_project_summary
"list_structures" → QVService.list_structures_data
"list_workflows" → QVService.list_workflows_data

# CRUD operations
"create_project" → QVService.init_project
"import_structure" → QVService.import_structure
"create_workflow" → QVService.init_workflow
"add_step_to_workflow" → QVService.add_step_to_workflow (NEW)
"reorder_workflow_steps" → QVService.reorder_workflow_steps
"delete_structure" → QVService.delete_structure
"delete_workflow" → QVService.delete_workflow

# Visualization data (pure data, no matplotlib)
"get_structure_vis" → QVService.get_structure_visualization_data
"get_scf_convergence" → QVService.get_scf_convergence_data
"get_dos_data" → QVService.get_dos_data
"get_band_structure_data" → QVService.get_band_structure_data

# Job management
"run_workflow" → JobManager.submit(QVService.run_workflow)
"run_step" → JobManager.submit(QVService.run_step)
"list_jobs" → JobManager.list_jobs
"cancel_job" → JobManager.cancel_job
```

### 11.4 GUI Components

```
gui/src/components/
├── layout/
│   ├── AppShell.tsx              # Main layout with sidebar + content + footer
│   ├── Sidebar.tsx               # Navigation tabs, project path input
│   ├── StatusBar.tsx             # Bottom bar with project/QE/job status
│   ├── ResizablePane.tsx         # Horizontal draggable resize (width)
│   └── VerticalResizablePane.tsx # Vertical draggable resize (height)
├── panels/
│   ├── DebugPanel.tsx           # Resizable daemon logs
│   ├── StructureViewer3D.tsx    # 3D view with supercell controls, camera state preservation
│   ├── WorkflowListPanel.tsx    # With drag-and-drop reorder + add step
│   ├── AnalysisPanel.tsx        # Recharts-based SCF/DOS/bands plots
│   │                             # - Auto-detects analysis type from workflow
│   │                             # - Energy range controls for band plots
│   │                             # - Automatic loading when enabled
│   ├── SettingsPanel.tsx        # QE detection + theme + auto-analysis settings
│   └── JobsPanel.tsx            # Job list with logs viewer
└── dialogs/
    └── ...
```

### 11.5 Log File Persistence

Logs are persisted to `.qv-daemon.log` in the project directory:

```typescript
// Electron main process
appendToLogFile(message)  // Appends timestamped log
readLogFile(projectPath)  // Reads tail of log file

// Preload API
window.qv.setProject(path)  // Set current project for logging
window.qv.readLogs(path)    // Read logs from project
```

When a project is loaded, `setProject` is called automatically to enable log persistence.

## 12. Future Considerations

1. **Other engines**: LAMMPS, Wannier90 support is planned
2. **Online databases**: Integration with Materials Project, AFLOW
3. **Parallel execution**: MPI support exists but is basic
4. **Real-time log streaming**: WebSocket or SSE for job logs

---

## 13. Refactoring History

### 2025-11-30 Session 2

Implemented from `temporary_ai_prompts` (lines 372-379):

| Item | Implementation |
|------|---------------|
| **Post-processing step support** | DOS/bands/projwfc steps now generate correct input format (just &DOS, &BANDS, etc. namelists) instead of pw.x format |
| **`--snapshot` for `qv init project`** | Create project from snapshot YAML file (e.g., `qv init project --snapshot demo.yml`) |
| **`--template` for `qv init workflow`** | Copy workflow template with steps from resources/workflow_templates/ (e.g., `qv init workflow my-dos --template si-dos`) |
| **`qv init step`** | Creates step with in-code default parameters based on step type (no template option) |
| **`qv import-structure` accepts .json** | Can now import QV-format JSON files with embedded metadata |
| **`qv show-command` simplified** | No longer includes `--structure <structure-id>` placeholder; shows helpful explanation instead |
| **Structure inheritance in `qv init step`** | When using `--workflow`, inherits structure from that workflow (not just from enclosing directory) |
| **ULID consistency in templates** | When copying templates, workflow ULIDs in project.qv.yml match step parent_workflow_id |
| **QE registry isolation** | Added autouse fixture to reset QE home registry between tests |

**New file**: `src/quantumvitas/core/templates.py` - Template management utilities

**New test file**: `tests/cli/test_template_workflow.py` - Tests for template copying and ULID consistency

**Resources Layout** (new organization):

```
resources/
├── demo_projects/          # Complete project snapshots (.yml)
│   └── si_bands_demo.yml  # Demo project snapshot (used by GUI "Create Demo Project")
├── workflow_templates/     # Reusable workflow recipes (public API)
│   ├── si-bands/          # Si band structure workflow
│   └── si-dos/            # Si DOS workflow
└── structure_library/      # Reusable structures (pymatgen JSON, public API)
    └── si.json            # Si bulk structure
```

**Key design principles**:
- **Public API** (GUI, high-level features): Uses `resources/` directories
  - Demo projects: `resources/demo_projects/*.yml` (project snapshots)
  - Workflow templates: `resources/workflow_templates/` (for GUI listing and `list_workflow_templates()`)
  - Structure library: `resources/structure_library/` (for `import_structure_from_template()`)
- **Step defaults**: Step parameters use in-code defaults (no template files)
  - Default parameters defined in `workflow/step_defaults.py`
  - `qv init step` creates steps with default parameters based on step type
  - `reset_step_params` resets to in-code defaults

**Key implementation details**:
- When creating workflow from template, CLI generates the workflow ULID first and passes it to `copy_workflow_template` so steps get the correct `parent_workflow_id`
- When copying project template, old workflow ULIDs from project.qv.yml are mapped to new ULIDs for consistency
- Demo project creation (`create_demo_project`) uses snapshots from `resources/demo_projects/` instead of templates
- Demo snapshots are generated from test projects using `scripts/generate_demo_snapshots.py`
- If test example projects change, rerun `python scripts/generate_demo_snapshots.py` to regenerate the demo snapshot files

### 2025-11-30 Session 1

Implemented from `temporary_ai_prompts` (lines 344-365):

| Item | Implementation |
|------|---------------|
| `qv configure workflow --reorder` | Reorders steps in workflow.yaml |
| `qv configure workflow --structure` | Changes structure, updates all step YAMLs |
| DAG model: step.yaml | Step YAML contains only step-local config (no `parent_workflow_id` or `structure_id`) |
| Structure optional in `qv init step` | Inherits from parent workflow if inside one |
| Structure validation on run step | Warning if step structure differs from workflow |
| Reduced input file output | Only one file when running from step spec |
| `qv configure structure` | Basic renaming support |

All tests passing (80/80).

### 2025-12-01 Resource Resolution Refactoring

Implemented the unified resource resolution architecture from `temporary_ai_prompts`:

**New modules created**:

| Module | Purpose |
|--------|---------|
| `core/resolution.py` | Centralized selector→resource resolution |
| `core/context.py` | PWD context helper for CLI |
| `api.py` | `QVService` - stable service layer |

**Architecture summary**:

1. **Resolution Layer** (`core/resolution.py`):
   - `resolve_structure(project_root, selector)` - Resolve structure by ULID/slug/name/path
   - `resolve_workflow(project_root, selector)` - Resolve workflow by ULID/slug/name/path
   - `resolve_step(project_root, workflow_selector, step_selector)` - Resolve step within workflow
   - Resolution order: path → ULID → slug → name (case-insensitive)
   - Never uses `Path.cwd()`

2. **Context Layer** (`core/context.py`):
   - `find_path_context_from_pwd()` - Scans upward to find project/workflow context
   - Returns `PathContext` with `project_root` and `nodes` (project→workflow→step chain)
   - **Only place that uses `Path.cwd()`** for resource discovery
   - Used by CLI for auto-detection

3. **Models Layer** (`core/models.py`):
   - Dataclass models for all resources: `WorkflowModel`, `ProjectModel`, `StructureModel`
   - `load_*` / `save_*` functions for YAML/JSON I/O
   - All models have complete meta: `id`, `name`, `slug`, `path`, `kind`
   - Business logic works with objects, not raw dicts

4. **API Layer** (`api.py`):
   - `QVService` class with methods for all CRUD operations
   - Always receives `project_root` explicitly
   - Never looks at cwd
   - Uses models layer for YAML I/O
   - Shared by CLI and future GUI

**Selector resolution rules**:
```
A selector is any of:
- ULID: exact match on resource id (26 chars, uppercase)
- slug: exact match (e.g., "si-dos")
- name: exact match (case-insensitive, NOT normalized to slug)
- path-like string: contains "/" or ends with .yaml/.yml/.json

Resolution order:
1. Path → normalize → load YAML → return resource
2. ULID → search all entries for matching id
3. slug → exact slug match within parent scope
4. name → case-insensitive exact name match
```

**Key classes**:
```python
@dataclass
class ResolvedResource:
    meta: ResourceMeta      # ULID, name, slug, path, kind
    entry: dict             # Raw entry from project.qv.yml
    absolute_path: Path     # Resolved absolute filesystem path

@dataclass
class PathContext:
    project_root: Path
    nodes: List[ContextNode]  # [project, workflow?, step?]
    
    # Convenience properties:
    workflow_selector: Optional[str]
    workflow_directory: Optional[Path]
    is_inside_workflow() -> bool

@dataclass
class WorkflowModel:
    meta: ResourceMeta      # Complete metadata
    structure: Optional[str]  # Structure selector
    steps: List[WorkflowStepEntry]
    mode: str = "normal"
    working_dir: str = "raw"
```

**Model I/O functions**:
```python
# Workflow
model = load_workflow(path, project_root)
save_workflow(model, path)

# Project  
model = load_project(path)
save_project(model, path)

# Structure
model = load_structure_model(path, project_root)
save_structure_model(model, path)
```

**Test coverage**:
- `tests/unit/test_resolution.py` - 20 tests for resolution
- `tests/unit/test_context.py` - 11 tests for PWD context
- `tests/unit/test_api_service.py` - 19 tests for QVService
- `tests/unit/test_models.py` - 20 tests for models

All 155 tests passing.

**Design principle**: Resource = dataclass, YAML = persistence, Selector = user-facing handle, Resolution = centralized lookup, CLI = thin wrapper, API = stable interface.

---

## 13. Analysis Layer

The analysis layer provides parsers and plotting functions for QE outputs, designed for:
- CLI integration (`qv analyze`)
- Future GUI integration (JSON-serializable data)

### 13.1 Dataclasses

| Class | File | Purpose |
|-------|------|---------|
| `SCFResult` | `analysis/parsers.py` | SCF/NSCF calculation result with iterations |
| `SCFIteration` | `analysis/parsers.py` | Single SCF iteration (energy, accuracy) |
| `DOSData` | `analysis/parsers.py` | DOS data (energies, dos, idos) |
| `BandStructureData` | `analysis/parsers.py` | Band structure with high-symmetry points |
| `HighSymmetryPoint` | `analysis/parsers.py` | K-path label and position |
| `KPathResult` | `analysis/kpath.py` | Auto-generated k-path metadata |
| `KPathSegment` | `analysis/kpath.py` | Single k-path segment |

### 13.2 Units Convention

**IMPORTANT**: Different QE outputs use different units. The analysis layer preserves native units:

| Quantity | Unit | Source |
|----------|------|--------|
| Total energy, SCF accuracy | Rydberg (Ry) | pw.x output |
| Fermi energy, HOMO, LUMO, band gap | eV | pw.x output |
| Band energies | eV | bands.x output |
| DOS energies | eV | dos.x output |
| DOS values | states/eV | dos.x output |
| k-distances | 2π/a | bands.dat.gnu |
| ecutwfc, ecutrho | Ry | pw.x input |

**Metrics dictionary keys** (from `extract_energy_metrics_from_text()`):
```python
{
    "total_energy_ry": 123.456,    # Rydberg
    "fermi_energy_ev": 5.76,       # eV (NOT fermi_energy_ry!)
}
```

**All `to_dict()` methods include a `"units"` key** for explicit documentation:

```python
result = parse_scf_output(path)
data = result.to_dict()
# data["units"] = {"energy": "Ry", "fermi": "eV", "time": "s"}
```

### 13.3 Pattern: Parse → Structured Data → Plot

```python
from quantumvitas.analysis import (
    parse_scf_output, parse_dos_data, parse_bands_gnu,
    plot_dos, plot_bands, save_figure,
)

# Parse
scf = parse_scf_output("si.scf.out")      # -> SCFResult
dos = parse_dos_data("si.dos.dat")        # -> DOSData
bands = parse_bands_gnu("si.bands.dat.gnu", 
    symmetry_file="si.bands.pp.out",      # Optional: high-sym labels
    fermi_energy=5.76)                    # Optional: from SCF

# Use
print(f"Total energy: {scf.total_energy} Ry")
print(f"Converged: {scf.converged}, iterations: {len(scf.iterations)}")

# Plot
fig, ax = plot_bands(bands, shift_fermi=True, energy_range=(-5, 10))
save_figure(fig, "bands.png")

# Serialize
import json
json.dumps(dos.to_dict())  # Ready for GUI
```

### 13.4 Auto K-Path Generation

When running `qv init step bands --auto-kpath`, the CLI:

1. Loads the step's structure (pymatgen `Structure`)
2. Calls `generate_kpath(structure, points_per_segment=N)`
3. Uses `pymatgen.symmetry.bandstructure.HighSymmKpath` internally
4. Stores result in **step YAML** (not sidecar file):

```yaml
# bands.step.yaml
meta:
  id: 01KB8...
  name: bands
  ...
step_type: bands
structure: si
cards:
  K_POINTS:
    option: crystal_b
    data:
      - [0.0, 0.0, 0.0, 20]  # Gamma, 20 pts
      - [0.5, 0.5, 0.5, 20]  # L, 20 pts
      - ...
kpath_metadata:  # Stored here, not in .kpath.json
  segments:
    - start_label: Γ
      end_label: L
      start_coords: [0.0, 0.0, 0.0]
      end_coords: [0.5, 0.5, 0.5]
      n_points: 20
  labels: [Γ, L, W, X, ...]
  lattice_type: cubic
  spacegroup_symbol: Fd-3m
  spacegroup_number: 227
```

**Precedence rules**:
- If `--auto-kpath` used but no structure: error
- If manual `K_POINTS` also provided: manual takes precedence
- The `kpath_metadata` is optional; `qv analyze band` can work without it

### 13.5 CLI Integration

```bash
# Basic analysis
qv analyze scf si.scf.out
qv analyze dos si.dos.dat
qv analyze band si.bands.dat.gnu

# With options
qv analyze band si.bands.dat.gnu \
  --symmetry si.bands.pp.out \    # High-sym labels
  --scf si.scf.out \              # Extract Fermi from SCF
  --plot \                        # Generate plot
  --output results/ \             # Output directory
  --format svg                    # Plot format

# Energy range
qv analyze dos si.dos.dat --plot --energy-range -5,5
```

### 13.6 Parsing Robustness

**SCF Parser** handles:
- Standard SCF calculations
- NSCF calculations (may have no iterations)
- Relax/VC-relax (extracts final SCF block only)
- Interrupted calculations (partial data)
- Missing Fermi energy (uses HOMO if available)

**Bands Parser** handles:
- With and without symmetry file
- Auto-identification of high-symmetry points (Γ, X, L, K, etc.)
- Custom Fermi energy override

### 13.7 Test Data Location

Test data for analysis is in `tests/data/`:

```
tests/data/
├── analysis_scf/
│   └── si.0_scf.out       # SCF output
├── analysis_dos/
│   └── si.dos.dat         # DOS data
├── analysis_bands/
│   ├── si.bands.dat.gnu   # Band energies
│   └── si.3_bands.pp.out  # High-symmetry points
└── ci_test_data/          # Moved from tests/integration/
    ├── 4_Si_DOS/
    ├── 7_Si_bandStructure/
    └── ...
```

**Tests**: `tests/unit/test_analysis_parsers.py`, `tests/unit/test_analysis_plotting.py`

### 13.8 Plotting Tests

Generated plots go to `temp/matplotlib_tests/`:

```bash
pytest tests/unit/test_analysis_plotting.py -v
# Creates: temp/matplotlib_tests/*.png, *.svg, *.pdf
```

Tests verify:
- File created
- File size > 0
- Expected number of curves (for bands)

---

## 14. Refactoring History - 2025-12-03

### 14.1 Bug Fixes

#### Fermi Energy Unit Mismatch (Critical Fix)

**Problem**: `extract_energy_metrics_from_text()` returned `result.fermi_energy` (in eV) with key `"fermi_energy_ry"`, causing unit mismatches in verification and analysis.

**Fix**: Changed key from `"fermi_energy_ry"` to `"fermi_energy_ev"` and updated all consumers:

| File | Change |
|------|--------|
| `analysis/energy.py` | Key `"fermi_energy_ry"` → `"fermi_energy_ev"` |
| `workflow/verification.py` | Uses `metrics.get("fermi_energy_ev")` |
| `analysis/dos.py` | Uses `step.metrics.get("fermi_energy_ev")` |
| `analysis/bands.py` | Uses `step.metrics.get("fermi_energy_ev")` |

**Important**: `SCFResult.fermi_energy` is always in eV (documented in `analysis/parsers.py`).

#### K-Points Crystal_B Format

**Clarification**: The `to_qe_kpoints_crystal_b()` method in `analysis/kpath.py` correctly sets the last k-point weight to 0 for `crystal_b` format. This is per QE documentation - weight 0 means "end of path segment, don't generate interpolation points after this."

### 14.2 CLI Improvements

#### `qv show-command` Module Detection

**Problem**: `show-command` always assumed `pw.x` module, giving wrong suggestions for `bands.x`, `dos.x`, etc.

**Fix**: Now detects module type from input file content:

```python
module = qe_input.module or qe_input.detect_module()
calculation = module.value if module != QEModule.UNKNOWN else "scf"
```

Example output for `si.bands.pp.in`:
```
Step type: bands
Suggested: qv init step bands --workflow <workflow>
```

#### `qv configure --name` (Preferred) and `qv rename` (Deprecated)

**New approach**: Renaming resources via `qv configure <type> <selector> --name <new_name>`:

```bash
# Preferred syntax
qv configure structure si --name "Silicon bulk"
qv configure workflow si-dos --name "Si DOS v2"
qv configure step scf --workflow si-dos --name "SCF high-precision"

# Deprecated (shows warning, still works)
qv rename structure si --name "Silicon bulk"
```

**Implementation**:
- Added `--name` option to `configure_structure_command`, `configure_workflow_command`, `configure_step_command`
- `qv rename *` commands now emit deprecation warning via `typer.secho(..., fg=typer.colors.YELLOW)`

### 14.3 Resource Metadata Updates

#### Workflow YAML Structure

**workflow.yaml** now includes full `meta` section:

```yaml
# New format (preferred)
meta:
  id: 01JXYZ123ABC456DEF789GHI
  name: si-dos
  slug: si-dos
  path: workflows/si-dos
  kind: workflow
mode: normal
structure: si
working_dir: raw
steps:
  - id: scf
    type: scf
    step_file: steps/scf.step.yaml
```

Previously was:
```yaml
# Old format (still supported for reading)
id: si-dos
mode: normal
workflow:
  working_dir: raw
  structure: si
steps: ...
```

#### Templates Updated

Templates in `/templates/workflow/` updated to use new format with `meta` section.

### 14.4 Pseudopotential Handling

**New logic in `ensure_pseudopotentials()`**:

1. Check `project_root/pseudo/` first
2. If not found, check `quantumvitas_root/pseudo/`
3. If not found, download to `quantumvitas_root/pseudo/`
4. **Always copy** found/downloaded pseudopotentials to `project_root/pseudo/`

This makes projects self-contained for portability.

```python
# Priority order:
# 1. project_root/pseudo/Si.pbe-n-rrkjus_psl.1.0.0.UPF
# 2. quantumvitas_root/pseudo/Si.pbe-n-rrkjus_psl.1.0.0.UPF (then copy to project)
# 3. Download to quantumvitas_root/pseudo/ and copy to project
```

### 14.5 Input File Handling

**Simplified naming**:
- Input files written to `working_dir/<stem>.in` (no more `_run.in` suffix)
- Original preserved as `<stem>_original.in` only if:
  - `keep_original=True` AND
  - Input was actually modified

### 14.6 Architecture Notes

#### API Layer Separation (Technical Debt)

**Finding**: The CLI (`main.py`) bypasses `QVService` and directly imports from `core/project_utils.py`.

**Current state**:
```
CLI (main.py) → core/project_utils.py (DIRECT)
             ↘ core/resources.py (DIRECT)
```

**Intended architecture**:
```
CLI (main.py) → api.py (QVService) → core/* modules
```

**Impact**: Logic is duplicated between CLI and `QVService`. Future refactoring should make CLI a thin wrapper around `QVService`.

#### Post-Processing Step Inputs (Verified)

`bands.x` and other post-processing steps correctly omit `&control` namelist. Implementation in `workflow/structure_steps.py:_generate_postprocessing_input()`:

```python
# POST_PROCESSING_STEP_TYPES = {"dos", "bands", "projwfc", ...}
# These only get their specific namelist (&DOS, &BANDS, etc.)
# No CONTROL, no ATOMIC_SPECIES, no CELL_PARAMETERS
```

### 14.7 Documentation Updates

| File | Updates |
|------|---------|
| `docs/CLI_API_REFERENCE.md` | Reorganized commands, added deprecation notes, updated unit conventions |
| `AI_understanding.md` | This section |

### 14.8 Band Structure K-Point Labeling

**Problem**: High-symmetry k-points from `bands.x` output are in Cartesian coordinates (2π/a), which don't directly correspond to standard labels like Γ, X, L, K, etc.

**Solution**: Convert Cartesian k-points to crystal (fractional) coordinates using reciprocal lattice vectors from `pw.x` output:

```python
# Parse reciprocal lattice from pw.x output (scf/nscf/bands)
#     reciprocal axes: (cart. coord. in units 2 pi/alat)
#               b(1) = ( -0.707107 -0.707107  0.707107 )
#               ...

# Convert k_cart → k_cryst
# k_cart = k_cryst[0]*b1 + k_cryst[1]*b2 + k_cryst[2]*b3
# k_cryst = B^(-T) @ k_cart

# Then identify label from crystal coordinates (structure-independent)
```

**New functions in `analysis/parsers.py`**:
- `_parse_reciprocal_lattice_vectors(output_file)` - Extract b1, b2, b3 from pw.x output
- `_cartesian_to_crystal(k_cart, B)` - Convert Cartesian to crystal coords
- `_identify_high_symmetry_point_crystal(k_cryst)` - Label from crystal coords

**CLI usage**:
```bash
# Pass SCF/NSCF output to provide reciprocal lattice vectors
qv analyze band si.bands.dat.gnu --symmetry si.bands.out --scf si.nscf.out --plot
```

### 14.9 Files Modified in Session 2

| File | Purpose |
|------|---------|
| `src/quantumvitas/analysis/parsers.py` | K-point coordinate conversion and crystal labeling |
| `src/quantumvitas/analysis/bands.py` | Pass pw_output_file for k-point conversion |
| `src/quantumvitas/cli/main.py` | Pass scf_file to parse_bands_gnu for k-point conversion |
| `tests/integration/test_si_bands_workflow_comprehensive.py` | Copy only Si pseudopotentials, fix file patterns |
| `AI_understanding.md` | API architecture guidelines, new feature pattern |

### 14.10 Auto-Detection in `qv analyze band`

**New feature**: The `qv analyze band` command can now auto-locate files from workflow context.

**Usage patterns**:
```bash
# Explicit workflow selector
qv analyze band --workflow si-bands --plot

# Auto-detect from pwd (if inside workflow)
cd project/workflows/si-bands/raw
qv analyze band --plot

# Auto-detect from pwd (searches current directory)
qv analyze band --plot

# Explicit files (still supported)
qv analyze band si.bands.dat.gnu --symmetry si.bands.out --scf si.nscf.out --plot
```

**New module**: `workflow/naming.py` provides centralized file naming conventions:
- `WorkflowFileNaming` class - input/output extensions for step types
- `BandAnalysisFiles` dataclass - container for band analysis files
- `find_band_analysis_files()` - auto-locate files in a directory

**Implementation uses**:
- `core/context.py:find_path_context_from_pwd()` - detect enclosing workflow
- `core/project_utils.py:find_workflow_entry()` - resolve workflow selector
- `workflow/naming.py` - centralized file patterns

### 14.11 3D Structure Visualization (`qv analyze structure`)

**New command**: `qv analyze structure <selector> [options]`

Creates 3D ball-and-stick visualization of crystal structures using matplotlib.

**Features**:
- Atoms as colored spheres (CPK-like element colors)
- Bonds as lines (detected via covalent radii)
- Supercell expansion (`--supercell "2 2 2"`)
- Boundary repetition (`--repeat-boundary`)
- Unit cell wireframe overlay
- Multiple output formats (png, svg, pdf)

**Architecture**:
- **Core module**: `analysis/structure_viz.py`
  - `visualize_structure()` - Main entry point
  - `plot_structure_3d()` - Creates matplotlib 3D plot
  - `detect_bonds()` - Bond detection via covalent radii
    - Uses coordinate-based deduplication to handle periodic images correctly
    - `include_periodic_images=False` by default to show only internal bonds
    - With `include_periodic_images=True` (for boundary repetition), shows bonds to periodic images
  - `generate_boundary_atoms()` - Periodic image generation
  - `StructurePlotOptions` - Configuration dataclass
  - `COVALENT_RADII` - Built-in covalent radii table (Cordero et al., Dalton Trans. 2008)
  - `get_element_radius()` - Uses built-in table, falls back to pymatgen's `atomic_radius`
  
- **Service layer**: `api.py:QVService.visualize_structure()`
  - Resolves structure from selector
  - Calls core visualization function
  - Returns metadata dict

- **CLI**: `cli/main.py:analyze_structure_command()`
  - Parses arguments
  - Supports both project structures and direct file paths
  - Prints success message with stats

**Usage examples**:
```bash
qv analyze structure si
qv analyze structure si --supercell "2 2 2" --repeat-boundary
qv analyze structure /path/to/structure.cif --output vis.png
```

### 14.12 Files Modified in Session 1

| File | Purpose |
|------|---------|
| `src/quantumvitas/analysis/energy.py` | Fix `fermi_energy_ev` key |
| `src/quantumvitas/analysis/dos.py` | Use `fermi_energy_ev` key |
| `src/quantumvitas/analysis/bands.py` | Use `fermi_energy_ev` key, prefer NSCF for Fermi |
| `src/quantumvitas/workflow/verification.py` | Use `fermi_energy_ev` key |
| `src/quantumvitas/core/engines/qe_pseudopotentials.py` | Pseudopotential priority and copying |
| `src/quantumvitas/workflow/input_runner.py` | Simplified input file naming |
| `src/quantumvitas/workflow/workflow.py` | Better input file extensions (.bands.in, .dos.in) |
| `src/quantumvitas/cli/main.py` | Module detection, configure --name, rename deprecation, workflow meta |
| `templates/workflow/si-dos/workflow.yaml` | Updated to new meta format |
| `docs/CLI_API_REFERENCE.md` | Comprehensive update |

### 14.13 Files Modified in Session 2 (Bond Detection Fix)

| File | Purpose |
|------|---------|
| `src/quantumvitas/analysis/structure_viz.py` | Fixed bond detection for supercells |
| | - Added `COVALENT_RADII` table (Cordero et al.) |
| | - Fixed `get_element_radius()` to use built-in table + fallback |
| | - Added `_is_coord_in_cell()` helper |
| | - Modified `detect_bonds()` to use coordinate-based deduplication |
| | - Added `include_periodic_images` parameter |
| `tests/unit/test_structure_viz.py` | New comprehensive unit tests for structure viz |

---

## 15. Refactoring History - 2025-12-05

### 15.1 CLI Analyze Commands - API Layer Refactoring

**Problem**: The `analyze_output_command` implemented analysis logic directly in the CLI layer (~200 lines), bypassing the `QVService` API layer. This was the technical debt mentioned in the documentation.

**Root Cause of Test Failure**: The documented API showed `qv analyze band <file>` but the implementation only had `qv analyze output band <file>`. Tests were calling the documented API.

**Solution**: Full refactoring to follow the intended architecture:

1. **Added QVService methods** (`api.py`):
   - `QVService.analyze_band()` - Band structure analysis
   - `QVService.analyze_dos()` - DOS analysis
   - `QVService.analyze_scf()` - SCF convergence analysis
   - `QVService._detect_workflow_results_dir()` - Helper for auto-detecting output directory

2. **Updated CLI commands** (`cli/main.py`):
   - `qv analyze band` - Thin wrapper calling `QVService.analyze_band()`
   - `qv analyze dos` - Thin wrapper calling `QVService.analyze_dos()`
   - `qv analyze energy` - Thin wrapper calling `QVService.analyze_scf()`
   - `qv analyze scf` - Alias for `analyze energy`

3. **Deprecated `qv analyze output`**:
   - Marked with `deprecated=True` in Typer
   - Shows warning when used
   - Kept for backward compatibility but will be removed later

### 15.2 Architecture Pattern for New Commands

When implementing new CLI commands, follow this pattern:

```python
# 1. Add service method in api.py
class QVService:
    @staticmethod
    def new_feature(
        project_root: Optional[Path],  # Always explicit, never use cwd
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Service method with all business logic.
        
        - Resolves resources using resolution.resolve_*()
        - Calls core modules for actual work
        - Returns structured result dict
        - Raises QVServiceError on failures
        """
        from quantumvitas.analysis.some_module import do_work
        
        # Resolve resources
        if project_root:
            resource = resolve_workflow(project_root, selector)
        
        # Do actual work
        result = do_work(...)
        
        # Return structured result
        return {
            "data": result.to_dict(),
            "output_path": str(output_path),
            ...
        }

# 2. Add thin CLI wrapper in cli/main.py
@some_app.command("feature")
def feature_command(
    arg: str = typer.Argument(..., help="..."),
    project: Optional[Path] = typer.Option(None, "--project"),
    ...
) -> None:
    """CLI docstring."""
    from quantumvitas.api import QVService, QVServiceError
    from quantumvitas.core.context import find_path_context_from_pwd, ContextNotFoundError
    
    # Auto-detect project root if not provided
    project_root: Optional[Path] = None
    if project:
        project_root = Path(project).resolve()
    else:
        try:
            ctx = find_path_context_from_pwd()
            project_root = ctx.project_root
        except ContextNotFoundError:
            pass
    
    # Call service
    try:
        result = QVService.new_feature(project_root=project_root, ...)
        typer.echo(json.dumps(result, indent=2))
    except QVServiceError as e:
        raise typer.BadParameter(str(e))
```

### 15.3 Key Principles

1. **CLI is thin**: Only argument parsing, context detection, and calling QVService
2. **QVService receives explicit project_root**: Never looks at cwd internally
3. **Context detection in CLI**: Use `find_path_context_from_pwd()` for auto-detection
4. **Errors**: QVService raises `QVServiceError`, CLI converts to `typer.BadParameter`
5. **Results**: QVService returns dict, CLI formats for terminal output

### 15.4 Files Modified

| File | Changes |
|------|---------|
| `src/quantumvitas/api.py` | Added `analyze_scf()`, `analyze_dos()`, `analyze_band()`, `_detect_workflow_results_dir()` |
| `src/quantumvitas/cli/main.py` | Refactored analyze commands to use QVService, deprecated `analyze output` |

### 15.5 Test Results

All 263 tests pass, including the previously failing:
- `test_si_bands_workflow_comprehensive.py::TestSiBandsWorkflowManualKpath::test_analyze_bands`
- `test_si_bands_workflow_comprehensive.py::TestSiBandsWorkflowAutoKpath::test_analyze_bands`

---

## 16. GUI-Ready Backend Architecture (2025-12-05)

### 16.1 Overview

QuantumVITAS now includes a stdio JSON-RPC daemon for GUI integration. The architecture follows the established pattern of using `QVService` as the single API surface.

**Key components**:
```
Electron GUI (future)
       ↓ JSON-RPC (stdin/stdout)
   QVDaemon
       ↓ method calls
   QVService (api.py)
       ↓ 
   core/*, workflow/*, analysis/*
```

**Location**: `src/quantumvitas/daemon/`
- `server.py` - `QVDaemon` class implementing JSON-RPC protocol
- `jobs.py` - `JobManager` for background QE execution

### 16.2 JSON-RPC Protocol

**Request format** (one JSON object per line):
```json
{"id": "req1", "type": "command_name", "payload": {...}}
```

**Response format** (one JSON object per line):
```json
{"id": "req1", "ok": true, "data": {...}}
{"id": "req1", "ok": false, "error": {"code": "...", "message": "..."}}
```

**Error codes**:
- `parse_error` - Invalid JSON
- `invalid_request` - Missing required fields
- `unknown_command` - Unknown command type
- `service_error` - `QVServiceError` from API layer
- `not_found` - `FileNotFoundError`
- `invalid_argument` - `ValueError`
- `handler_error` - Unexpected exception

### 16.3 Available Commands

**System**:
- `ping` → `{pong: true, version: "..."}`
- `shutdown` → Gracefully stops daemon

**Resource listing**:
- `get_project_summary` → Project name, ID, resource counts
- `list_structures` → List of structure metadata
- `list_workflows` → List of workflow metadata with steps

**Pure data (no matplotlib)**:
- `get_structure_vis` → Atoms, bonds, lattice for 3D rendering
- `get_scf_convergence` → Iteration data for SCF plots
- `get_dos_data` → Energy and DOS arrays
- `get_band_structure_data` → Band energies and k-distances

**Job management**:
- `run_workflow` → Submit workflow execution, returns `{job_id}`
- `run_step` → Submit single step, returns `{job_id}`
- `get_job_status` → Check job status, result, or error
- `list_jobs` → List all jobs (filterable by status/type)
- `cancel_job` → Cancel a pending job

### 16.4 GUI-Ready QVService Methods

New methods in `QVService` return pure JSON-serializable data (no matplotlib objects):

```python
# Project/resource summary
QVService.get_project_summary(project_root) -> dict
QVService.list_structures_data(project_root) -> list[dict]
QVService.list_workflows_data(project_root) -> list[dict]

# Pure visualization data
QVService.get_structure_vis_data(project_root, selector, supercell, repeat_boundary) -> dict
# Returns: atoms (coords, element, color, radius), bonds, lattice matrix

QVService.get_scf_convergence_data(project_root, workflow, step) -> dict
# Returns: iterations, energies, converged status

QVService.get_dos_data(project_root, workflow, step) -> dict
# Returns: energies[], dos[], fermi_energy

QVService.get_band_structure_data(project_root, workflow, step) -> dict
# Returns: k_distances[], energies[bands][kpoints], high_symmetry_points
```

### 16.5 Layering Rules

**Architecture principle**: Strict layering to maintain clean separation of concerns.

**Allowed paths**:
```
GUI (React/Electron) → Electron main → Daemon RPC → QVService → core/workflow/analysis
```

**Forbidden paths**:
- ❌ GUI → core/workflow/analysis (direct Python imports)
- ❌ Daemon handlers → core/workflow/analysis (bypassing QVService)
- ❌ GUI → daemon internals (must use typed RPC protocol)

**Exceptions** (documented):
- `find_project_root` handler uses `quantumvitas.core.context` directly (utility function, not business logic)
- `list_workflow_templates` handler uses `quantumvitas.core.templates` directly (read-only listing, no state mutation)

**Enforcement**:
- GUI TypeScript code must only use `window.qv.*` RPC calls (typed in `gui/src/types/qv.ts`)
- Daemon handlers should delegate to `QVService` methods whenever possible
- New handlers should follow the pattern: parse payload → call `QVService.method()` → return result

### 16.6 JobManager and Background Execution

**Design principles**:
- All QE-invoking operations go through `JobManager`
- `ThreadPoolExecutor(max_workers=1)` ensures sequential QE execution
- Daemon main loop remains responsive and non-blocking
- Job results/status live in memory; project/workflow data lives on disk

```python
from quantumvitas.daemon.jobs import JobManager, JobStatus

manager = JobManager(max_workers=1)

# Submit job
job_id = manager.submit(
    job_type="run_workflow",
    func=QVService.run_workflow,
    params={"workflow": "si-dos"},
    project_root=project_root,
    workflow_selector="si-dos",
)

# Check status
status = manager.get_job_status(job_id)
# {"id": "...", "status": "completed", "result": {...}}

# List jobs
manager.list_jobs(status=JobStatus.RUNNING)
```

**Job lifecycle**:
```
PENDING → RUNNING → COMPLETED
                  → FAILED (with error message)
                  → CANCELLED (if cancelled while pending)
```

### 16.6 Example Daemon Session

```python
# Start daemon (typically from Electron via spawn)
# In Python:
from quantumvitas.daemon import QVDaemon
daemon = QVDaemon()
daemon.run()

# Or from command line:
# python -m quantumvitas.daemon.server
```

**Example JSON conversation**:
```
→ {"id": "1", "type": "ping", "payload": {}}
← {"id": "1", "ok": true, "data": {"pong": true, "version": "2.0.0"}}

→ {"id": "2", "type": "get_project_summary", "payload": {"project_root": "/path/to/project"}}
← {"id": "2", "ok": true, "data": {"name": "my-project", "n_workflows": 3, ...}}

→ {"id": "3", "type": "run_workflow", "payload": {"project_root": "/path", "workflow": "si-dos"}}
← {"id": "3", "ok": true, "data": {"job_id": "abc-123", "status": "pending"}}

→ {"id": "4", "type": "get_job_status", "payload": {"job_id": "abc-123"}}
← {"id": "4", "ok": true, "data": {"status": "running", ...}}
```

### 16.7 Architectural Invariants

The daemon implementation follows these rules:

1. **CLI convenience ≠ service logic**: CLI uses `core/context.py` (cwd-based), daemon/service never look at cwd
2. **All resolution via `core/resolution.py`**: Selector rules (path → ULID → slug → name) apply
3. **Analysis is read-only**: Uses existing `analysis/*` dataclasses with `.to_dict()`
4. **Pure JSON-RPC over stdio**: One request/response per line
5. **Daemon never crashes**: All exceptions become `{ok: false, error: {...}}`
6. **Long QE runs = background jobs**: Sequential (max_workers=1)
7. **No CLI invocation from daemon**: Only call `QVService` methods

### 16.8 Files Added

| File | Purpose |
|------|---------|
| `src/quantumvitas/daemon/__init__.py` | Package exports |
| `src/quantumvitas/daemon/server.py` | `QVDaemon` class with JSON-RPC handlers |
| `src/quantumvitas/daemon/jobs.py` | `JobManager`, `Job`, `JobStatus` |
| `tests/unit/test_daemon.py` | Unit tests for daemon and job manager |
| `tests/unit/test_qvservice_gui.py` | Unit tests for GUI-ready QVService methods |
| `tests/daemon/test_si_bands_workflow_daemon.py` | Integration tests using daemon/JobManager |
| `docs/DAEMON_API_REFERENCE.md` | Complete daemon API documentation |

### 16.9 Self-Audit Results (2025-12-05)

A thorough audit was performed on the daemon implementation:

#### 1. No CLI/Subprocess Calls ✅

- No `subprocess` imports in daemon code
- No `typer` imports in daemon code
- No imports from `quantumvitas.cli`
- No dependency on `core/context.py`
- All operations go through `QVService`

#### 2. JSON-RPC Streaming Correctness ✅

- `stdout.write(response.to_json() + "\n")` ensures one JSON per line
- `stdout.flush()` called after every response
- All logging goes to `stderr` via `self.log()` method
- No accidental `print()` statements that would pollute stdout

#### 3. Resolution Correctness ✅

- Daemon passes explicit `project_root` from payload
- No duplicate resolution logic - all goes through `QVService`
- `QVService` methods call `core/resolution.resolve_*()` internally
- No cwd-based lookups in daemon or service layer

#### 4. JobManager Correctness ✅

**Cancellation semantics documented**:
- Only `PENDING` jobs can be cancelled
- `RUNNING` jobs cannot be interrupted (Python limitation)
- Documentation clarified in `cancel_job()` docstring

**Status transitions verified**:
- `PENDING` → `RUNNING` → `COMPLETED` / `FAILED`
- `PENDING` → `CANCELLED` (only via `cancel_job()`)
- Failed jobs capture error message and traceback

**Memory usage**:
- Job results are stored as dicts, not raw QE output logs
- `cleanup_completed()` method available to prune old jobs

#### 5. JSON Schema Validation ✅

All GUI methods return pure JSON-serializable types:

| Issue Found | Fix Applied |
|-------------|-------------|
| `pt.k_coords` in band data might be numpy array | Changed to `[float(x) for x in pt.k_coords]` |
| `pt.k_distance` might be numpy scalar | Added explicit `float()` conversion |

Verified conversions throughout:
- `numpy.ndarray` → `.tolist()`
- `pathlib.Path` → `str()`
- `dataclasses` → `.to_dict()`
- All floats explicitly cast via `float()`

#### 6. No cwd-Dependence ✅

Searched for `Path.cwd()`, `os.getcwd()`, `core.context` in:
- `api.py` - No cwd usage in GUI methods ✅
- `daemon/server.py` - No cwd usage ✅
- `daemon/jobs.py` - No cwd usage ✅

Only `cli/main.py` uses cwd (via `core/context.py`), which is correct.

### 16.10 Test Organization

Tests are organized by component and purpose:

```
tests/
├── unit/                    # Pure Python tests, NO QE required
├── daemon/                  # Daemon/JobManager integration (requires QE)
├── cli/                     # CLI integration tests (requires QE)
├── integration/             # QE engine integration tests (requires QE)
├── examples/                # Documentation example tests
├── core/                    # Test infrastructure (base classes, runners)
├── data/                    # Test input files and reference data
└── utils/                   # Test helper utilities
```

### 16.11 Test Categories and What They Test

#### **Unit Tests (`tests/unit/`)** — No QE Required

Run with: `pytest tests/unit/ -v`

| File | Purpose |
|------|---------|
| `test_daemon.py` | Daemon JSON-RPC protocol, JobManager thread safety |
| `test_qvservice_gui.py` | QVService GUI methods, JSON-serializable outputs |
| `test_analysis_parsers.py` | SCF convergence, DOS, band structure parsing |
| `test_analysis_plotting.py` | Band structure/DOS plot generation |
| `test_api_service.py` | QVService core methods (create, list, run) |
| `test_context.py` | cwd-based auto-detection in CLI context |
| `test_models.py` | Core models (Workflow, Step, Structure) |
| `test_parameter_overrides.py` | Parameter merging and override logic |
| `test_project_and_cli.py` | Project model and CLI arg parsing |
| `test_qe_executable_detection.py` | QE installation detection (PATH, env vars, shell configs) |
| `test_qe_geometry_roundtrip.py` | Geometry: QV → QE input → parse back → verify |
| `test_qe_input.py` | QE input file generation |
| `test_qe_modules.py` | Module parameter mappings (pw.x, dos.x, etc.) |
| `test_resolution.py` | Selector resolution (path → ULID → slug → name) |
| `test_structure_io.py` | Structure file I/O (CIF, XSF, XYZ) |
| `test_structure_roundtrip.py` | Structure serialization roundtrip |
| `test_structure_steps.py` | Structure step generation |
| `test_structure_viz.py` | Structure visualization data extraction |
| `test_workflow_importers.py` | Workflow import from QE input files |
| `test_workflow_inputs.py` | Workflow input generation |

#### **Daemon Tests (`tests/daemon/`)** — Requires QE

Run with: `pytest tests/daemon/ -v -s`

| File | Purpose |
|------|---------|
| `test_si_bands_workflow_daemon.py` | Full Si band structure via daemon + JobManager |

**What it tests:**
- Project/workflow/step creation via `QVService` (not CLI)
- Job submission via `JobManager.submit()`
- Polling job status until completion
- Band structure data retrieval via `QVService.get_band_structure_data()`
- Band analysis and PNG plot generation via `QVService.analyze_band()`

#### **CLI Tests (`tests/cli/`)** — Requires QE

Run with: `pytest tests/cli/ -v -s`

| File | Purpose |
|------|---------|
| `test_si_bands_workflow_comprehensive.py` | Full Si band structure via CLI commands |
| `test_si_dos_workflow_cli.py` | Full Si DOS calculation via CLI |
| `test_cli_show_command_integration.py` | `qv show` command variants |
| `test_template_workflow.py` | Template copying and ULID consistency |

**What `test_si_bands_workflow_comprehensive.py` tests:**
- `qv project create`, `qv structure import`, `qv workflow create`
- `qv step init`, `qv step configure`, `qv run`
- Both manual k-path and auto k-path modes
- `qv analyze band` with PNG output

#### **Integration Tests (`tests/integration/`)** — Requires QE

Run with: `pytest tests/integration/ -v`

| File | Purpose |
|------|---------|
| `test_si_bands_workflow.py` | Simple Si bands workflow (programmatic) |
| `test_si_dos_workflow.py` | Simple Si DOS workflow (programmatic) |
| `test_qe_engine.py` | QuantumEspressoEngine direct invocation |
| `test_qe_executable_integration.py` | QE executable discovery integration |
| `test_pw_step_specs.py` | pw.x step parameter verification |
| `test_pw_scf_ibrav_step_specs.py` | pw.x ibrav lattice type tests |
| `test_pw_quick_tests_ci.py` | Quick pw.x tests for CI |
| `test_ph_quick_tests.py` | Quick ph.x phonon tests |
| `test_ci_validation.py` | CI environment validation |

#### **Example Tests (`tests/examples/`)** — Documentation Verification

| File | Purpose |
|------|---------|
| `test_cli_usage_examples.py` | Verifies CLI examples from docs work |
| `test_structure_io_examples.py` | Structure I/O documentation examples |

### 16.12 Test Infrastructure (`tests/core/`)

Shared test infrastructure:

| File | Purpose |
|------|---------|
| `base.py` | Base test classes with common fixtures |
| `runner.py` | Generic test runner infrastructure |
| `qe_step_runner.py` | QE-specific step execution for tests |
| `qe_step_verification.py` | Output verification utilities |
| `qe_test_utils.py` | QE test helper functions |
| `test_data.py` | Test data loading utilities |
| `thresholds.py` | Numerical comparison thresholds |

### 16.13 Test Data (`tests/data/`)

Reference data for tests:

| Directory | Contents |
|-----------|----------|
| `4_Si_DOS/` | Silicon DOS workflow inputs and reference outputs |
| `7_Si_bandStructure/` | Silicon band structure workflow reference |
| `analysis_bands/` | Band structure parsing test data |
| `analysis_dos/` | DOS parsing test data |
| `analysis_scf/` | SCF convergence parsing test data |
| `workflow_bands/` | Band workflow test inputs |
| `pw_scf_ibrav/` | SCF inputs for all ibrav values |
| `pw_single_tests/` | Single pw.x test cases |
| `ph_1d/`, `ph_2d/` | Phonon calculation test cases |

### 16.14 Running Tests

```bash
# All unit tests (fast, no QE needed)
pytest tests/unit/ -v

# Daemon tests (needs QE)
pytest tests/daemon/ -v -s

# CLI tests (needs QE)
pytest tests/cli/ -v -s

# Quick smoke test
pytest tests/unit/test_ci_smoke.py -v

# Full test suite (needs QE)
pytest tests/ -v
```

## 17. GUI Layer Architecture (Electron + React)

### 17.1 Overview

The GUI layer provides a desktop application interface using:
- **Electron** - Desktop application framework
- **React + TypeScript** - UI framework
- **electron-vite** - Build tooling
- **react-three-fiber** - 3D structure visualization
- **recharts** - 2D analysis charts

Architecture diagram:
```
┌─────────────────────────────────────────────────────────────┐
│                     Electron Main Process                    │
│                                                              │
│  ┌──────────────────┐    ┌───────────────────────────────┐ │
│  │   BrowserWindow  │    │      Python Daemon            │ │
│  │                  │    │                               │ │
│  │  ┌────────────┐  │    │  stdin ← JSON requests       │ │
│  │  │   React    │  │    │  stdout → JSON responses     │ │
│  │  │   App      │  │    │  stderr → logs               │ │
│  │  └────────────┘  │    │                               │ │
│  └────────┬─────────┘    └───────────────┬───────────────┘ │
│           │                              │                  │
│           │ IPC                          │ spawn/stdio      │
│           ▼                              ▼                  │
│  ┌────────────────────────────────────────────────────────┐│
│  │                   ipcMain.handle                       ││
│  │                   Request Map (id → resolve/reject)    ││
│  └────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### 17.2 Directory Structure

```
gui/
├── electron/
│   ├── main.ts           # Daemon spawning, IPC, file dialogs
│   └── preload.ts        # Context bridge API
├── src/
│   ├── main.tsx          # React entry point
│   ├── App.tsx           # Root component with view routing
│   ├── index.css         # Global styles (design tokens)
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppShell.tsx         # Main layout wrapper
│   │   │   └── Sidebar.tsx          # Navigation, view tabs
│   │   ├── panels/
│   │   │   ├── ResultPanel.tsx      # JSON result display
│   │   │   ├── DebugPanel.tsx       # Daemon logs + ping tool
│   │   │   ├── ProjectSummaryPanel.tsx  # Welcome + project view
│   │   │   ├── StructureListPanel.tsx   # Structure list + detail
│   │   │   ├── WorkflowListPanel.tsx    # Workflow list + detail
│   │   │   ├── StructureViewer3D.tsx    # 3D ball-and-stick viewer
│   │   │   ├── AnalysisPanel.tsx        # SCF/DOS/Bands charts
│   │   │   └── DaemonErrorBanner.tsx    # Startup error display
│   │   └── dialogs/
│   │       ├── Modal.tsx            # Base modal component
│   │       ├── CreateProjectDialog.tsx
│   │       ├── ImportStructureDialog.tsx
│   │       └── CreateWorkflowDialog.tsx
│   ├── hooks/
│   │   └── useQVClient.ts   # Type-safe daemon communication
│   └── types/
│       └── qv.ts            # QVCommandMap + all RPC types
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts
```

### 17.3 Type-Safe RPC API

The GUI uses a centralized `QVCommandMap` for end-to-end type safety:

```typescript
// In src/types/qv.ts
export interface QVCommandMap {
  // System
  ping: { payload: {}; result: { pong: boolean; version: string } };
  shutdown: { payload: {}; result: { shutdown: boolean } };
  
  // Project/Resource listing
  get_project_summary: { payload: { project_root: string }; result: ProjectSummary };
  list_structures: { payload: { project_root: string }; result: { structures: StructureInfo[]; count: number } };
  list_workflows: { payload: { project_root: string }; result: { workflows: WorkflowInfo[]; count: number } };
  
  // Project creation
  create_project: { payload: { target_dir: string; name?: string; template?: string }; result: { project_root: string; name: string; id: string } };
  import_structure: { payload: { project_root: string; source_file: string; name?: string }; result: { structure_id: string; name: string; slug: string; formula: string; n_atoms: number } };
  
  // Workflow creation
  list_workflow_templates: { payload: {}; result: { templates: WorkflowTemplateInfo[]; count: number } };
  create_workflow: { payload: { project_root: string; name: string; structure?: string; template?: string }; result: { workflow_id: string; name: string; slug: string; n_steps: number } };
  
  // Visualization data
  get_structure_vis: { payload: { project_root: string; selector: string; supercell?: [number, number, number]; repeat_boundary?: boolean }; result: StructureVisData };
  get_scf_convergence: { payload: { project_root: string; workflow: string; step: string }; result: ScfConvergenceData };
  get_dos_data: { payload: { project_root: string; workflow: string; step?: string }; result: DosData };
  get_band_structure_data: { payload: { project_root: string; workflow: string; step?: string }; result: BandStructureData };
  
  // Job management
  run_workflow: { payload: { project_root: string; workflow: string; strict?: boolean; verbose?: boolean }; result: JobSubmitResult };
  run_step: { payload: { project_root: string; workflow: string; step: string; verbose?: boolean }; result: JobSubmitResult };
  get_job_status: { payload: { job_id: string }; result: JobInfo };
  list_jobs: { payload: { status?: JobStatus; job_type?: string }; result: { jobs: JobInfo[]; count: number } };
  cancel_job: { payload: { job_id: string }; result: { job_id: string; cancelled: boolean } };
}

// In hooks/useQVClient.ts
const qv = useQVClient();
const response = await qv.call('get_project_summary', { project_root: '/path' });
// response.data is typed as ProjectSummary
```

### 17.4 Daemon Spawning (Robust)

Python interpreter detection order:
1. `QV_DAEMON_PYTHON` env var (if set)
2. `.venv/bin/python` or `.venv/Scripts/python.exe` (Windows)
3. `venv/bin/python` or `venv/Scripts/python.exe`
4. Fallback to `python` on PATH

Daemon module override: `QV_DAEMON_MODULE` env var (default: `quantumvitas.daemon.server`)

Error handling:
- Startup errors stored in `DaemonStatus`
- Rendered as `DaemonErrorBanner` in UI
- Status pushed to renderer via IPC

Shutdown:
- Sends `shutdown` command
- Waits 2 seconds for graceful exit
- Force kills with SIGTERM if needed
- No race condition (properly awaited)

### 17.5 UI Components

**Structured Panels:**

| Panel | Purpose |
|-------|---------|
| `ProjectSummaryPanel` | Welcome card with CTAs, project overview |
| `StructureListPanel` | Clickable list of structures with lattice info |
| `StructureDetailPanel` | Full structure details (lattice params, path) |
| `StructureViewer3D` | 3D ball-and-stick viewer (react-three-fiber) |
| `WorkflowListPanel` | Workflow list with steps, structure, mode |
| `WorkflowDetailPanel` | Workflow details with step list, run button |
| `AnalysisPanel` | Container with SCF/DOS/Bands chart selection |
| `ScfConvergenceChart` | Energy vs iteration, accuracy vs iteration |
| `DosChart` | DOS and iDOS vs energy |
| `BandsChart` | Band structure along k-path |
| `DaemonErrorBanner` | Displays daemon startup errors |
| `DebugView` | Ping button, status info, logs |
| `DebugPanel` | Compact daemon log footer |
| `ResultPanel` | Raw JSON viewer (for debug view) |

**Dialogs:**

| Dialog | Purpose |
|--------|---------|
| `Modal` | Base modal/dialog component |
| `CreateProjectDialog` | Create new QV project (target dir, name) |
| `ImportStructureDialog` | Import CIF/XSF/etc. structure file |
| `CreateWorkflowDialog` | Create workflow from template |

**View Routing:**

The `Sidebar` has view tabs: Summary, Structures, Workflows, Analysis, Debug.

**Auto-fetch behavior:**
- Switching to Structures view auto-fetches structures list
- Switching to Workflows view auto-fetches workflows list
- Switching to Analysis view auto-fetches workflows for selection

**Empty states:**
- No project loaded → Welcome card with "Browse & Load" and "Create Project" CTAs
- Project load failed → Error card with message and recovery actions
- Views disabled until project is loaded (except Summary and Debug)

### 17.6 Preload API

```typescript
window.qv = {
  // Daemon communication
  request: <T>(type, payload) => Promise<QVResponse<T>>,
  onLog: (callback) => unsubscribe,
  isConnected: () => Promise<boolean>,
  getDaemonStatus: () => Promise<DaemonStatus>,
  onDaemonStatus: (callback) => unsubscribe,
  onMainMessage: (callback) => unsubscribe,
  
  // Native dialogs
  openDirectory: () => Promise<string | null>,   // Folder picker
  openFile: (options?) => Promise<string | null>, // File picker with filters
  
  // File system integration
  revealPath: (targetPath: string) => Promise<boolean>, // Reveal in Finder/Explorer
}
```

**File dialog filters example:**
```typescript
const path = await window.qv.openFile({
  title: 'Select Structure File',
  filters: [
    { name: 'Structure Files', extensions: ['cif', 'json', 'in', 'xsf'] },
    { name: 'All Files', extensions: ['*'] },
  ],
});
```

### 17.7 Design System

CSS custom properties in `src/index.css` with theme support:

**Dark Theme** (default):
- `--color-primary`, `--color-success`, `--color-error`
- `--bg-primary`, `--bg-sidebar`, `--bg-card`
- `--text-primary`, `--text-secondary`, `--text-muted`

**Light Theme** (`[data-theme="light"]`):
- VS Code-inspired light color scheme
- Adjusted primary colors for light backgrounds
- Theme toggle in Settings → Appearance

Theme is controlled via `data-theme` attribute on document root and persisted in localStorage.
- `--text-primary`, `--text-secondary`, `--text-muted`
- `--font-sans` (IBM Plex Sans), `--font-mono` (IBM Plex Mono)
- JSON syntax highlighting: `--json-key`, `--json-string`, etc.

Theme: Midnight blue dark theme for professional scientific software appearance.

### 17.8 Running the GUI

```bash
cd gui
npm install       # First time only
npm run dev       # Development mode (hot reload)
npm run build     # Production build
```

Development mode opens DevTools automatically.

### 17.9 Extending the GUI

**Adding a new daemon command:**
1. Add Python handler in `daemon/server.py` (calls `QVService`)
2. Add entry to `QVCommandMap` in `src/types/qv.ts` with payload + result types
3. Optionally add convenience method to `useQVClient.ts`
4. Call via `qv.call('new_command', payload)` - fully typed!

**Adding a new panel:**
1. Create component in `src/components/panels/`
2. Add CSS file with same name
3. Export from `panels/index.ts`
4. Add to view routing in `App.tsx`

**Adding a dialog:**
1. Create component in `src/components/dialogs/` using `Modal` as base
2. Add form state, validation, and submit handler
3. Export from `dialogs/index.ts`
4. Add dialog state in `App.tsx` (`showMyDialog`, `setShowMyDialog`)
5. Render outside `AppShell` for proper z-index

**Adding 3D visualization:**
- Use `react-three-fiber` for WebGL rendering
- Get pure data from daemon (no matplotlib)
- See `StructureViewer3D.tsx` for atom/bond rendering pattern

**Adding 2D charts:**
- Use `recharts` for plotting
- Get data arrays from daemon
- See `AnalysisPanel.tsx` for LineChart/AreaChart examples

### 17.10 Key Dependencies

```json
{
  "react": "^18.2.0",
  "react-dom": "^18.2.0",
  "@react-three/fiber": "^8.16.3",
  "@react-three/drei": "^9.105.4",
  "three": "^0.164.1",
  "recharts": "^2.12.6"
}
```

### 17.11 Enhanced Job System (2025-12-06)

The daemon job system was enhanced to support full GUI job management with live log streaming.

**Job Model Enhancements** (`daemon/jobs.py`):

New fields added to `Job` dataclass:
- `target_name: str | None` - Human-readable name (e.g., "si-dos")
- `project_root: str | None` - Project path for display/filtering
- `output_file: str | None` - QE output file path for log reading
- `last_log_line: str | None` - Last line from output (quick status)

New methods:
- `to_summary_dict()` - Lighter dict for list views
- `get_job_logs(job_id, tail_lines, offset)` - Read QE output with tail/offset
- `count_by_status()` - Get counts for sidebar badge

**New Daemon RPCs**:

| Command | Purpose | Response |
|---------|---------|----------|
| `get_job_logs` | Read QE output file | `{logs: string[], total_lines, has_more, output_file}` |
| `job_counts` | Job counts by status | `{counts: {status: count}, running: n, pending: n}` |

**Updated RPCs**:

| Command | Change |
|---------|--------|
| `list_jobs` | Now returns `JobSummary[]` (lighter), supports `project_root` filter |
| `run_workflow` | Returns `target_name` in response |
| `run_step` | Returns `target_name` in response |

**GUI Components Added**:

| Component | Purpose |
|-----------|---------|
| `JobsPanel` | Main jobs view with list + detail |
| `JobListItem` | Compact job row with status badge |
| `JobDetailPanel` | Full job info, logs, cancel button |
| `StatusBadge` | Colored status indicator |

**React Hooks Added** (`hooks/useJobs.ts`):

```typescript
// Job list with polling
const { jobs, counts, isLoading, refresh, isPolling } = useJobs({
  pollInterval: 3000,    // Poll every 3s
  projectRoot?: string,  // Filter by project
  status?: JobStatus,    // Filter by status
});

// Single job detail with logs
const { job, logs, cancelJob, refresh } = useJobDetail({
  jobId: 'abc-123',
  pollInterval: 2000,    // Poll while running
});
```

**Sidebar Updates**:

- New "Jobs" tab in view navigation
- Running jobs badge with count + pulse animation
- `jobCounts` prop for live status

**Workflow Run Button Integration**:

When clicking "Run Workflow":
1. Calls `job.submit_run_workflow` RPC
2. Shows toast notification with job ID
3. Updates job counts immediately
4. "View Jobs" button links to Jobs view

**TypeScript Types Added** (`types/qv.ts`):

```typescript
interface JobSummary {
  id: string;
  job_type: string;
  status: JobStatus;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  target_name: string | null;
  project_root: string | null;
  error: string | null;
  last_log_line: string | null;
}

interface JobLogs {
  job_id: string;
  logs: string[];
  total_lines: number;
  has_more: boolean;
  output_file: string | null;
}

interface JobCounts {
  counts: Record<string, number>;
  running: number;
  pending: number;
}
```

### 17.12 Known Limitations

- No SSL/TLS (daemon is local only via stdio)
- Single daemon instance per Electron app
- Request timeout: 60 seconds (configurable in main.ts)
- Daemon must be restarted if Python code changes
- Running jobs cannot be cancelled (ThreadPoolExecutor limitation)
- 3D viewer performance depends on structure size (works well up to ~1000 atoms)
- Job logs are polled, not streamed (2s interval while job is active)

### 17.13 GUI-CLI Parity Roadmap (2025-12-06)

The goal is to enable non-expert users to perform all core QV operations entirely from the GUI.

**Completed Features:**

| CLI Command | GUI Feature | Component |
|-------------|------------|-----------|
| `qv init project` | Create Project dialog | `CreateProjectDialog` |
| `qv import-structure` | Import Structure dialog | `ImportStructureDialog` |
| `qv init workflow` | Create Workflow dialog | `CreateWorkflowDialog` |
| `qv list structures` | Structures view | `StructureListPanel` |
| `qv list workflows` | Workflows view | `WorkflowListPanel` |
| `qv run workflow` | Run Workflow button | `WorkflowDetailPanel` |
| `qv analyze scf` | SCF Convergence chart | `AnalysisPanel` |
| `qv analyze dos` | DOS chart | `AnalysisPanel` |
| `qv analyze bands` | Band Structure chart | `AnalysisPanel` |
| `qv detect-qe` | Settings panel | `SettingsPanel` |
| `qv rename structure` | Rename dialog | `RenameDialog` |
| `qv rename workflow` | Rename dialog | `RenameDialog` |
| `qv delete structure` | Delete confirmation | `DeleteConfirmDialog` |
| `qv delete workflow` | Delete confirmation | `DeleteConfirmDialog` |
| `qv run step` | Run Step button | `StepDetailPanel` |
| `qv show-command step` | Step detail view | `StepDetailPanel` |

**Settings & Environment Panel** (`SettingsPanel`):

Shows QE detection status, Python/daemon version, and provides:
- Re-detect QE button (triggers auto-detection)
- Default project root setting (persisted in localStorage)

**New RPCs for Environment**:

| Command | Purpose |
|---------|---------|
| `get_environment_info` | Returns QE home, version, Python version, platform |
| `detect_qe_installation` | Re-triggers QE detection, returns updated info |
| `get_default_project_root` | Returns stored default project path |
| `set_default_project_root` | Updates default project path |

**New RPCs for Resource Management**:

| Command | Purpose |
|---------|---------|
| `rename_structure` | Rename a structure |
| `rename_workflow` | Rename a workflow |
| `can_delete_structure` | Check if structure can be deleted (dependency check) |
| `can_delete_workflow` | Check if workflow can be deleted |
| `delete_structure` | Delete structure (with force option) |
| `delete_workflow` | Delete workflow |

**New Dialog Components**:

| Dialog | Purpose |
|--------|---------|
| `RenameDialog` | Generic rename dialog with validation |
| `DeleteConfirmDialog` | Confirm delete with dependency warnings |

**Sidebar Updates**:
- New "Settings" view tab (⚙️)

**Step Detail Panel** (`StepDetailPanel`):

Shows detailed step information with:
- Step metadata (type, ID, structure, path)
- QE parameters organized by namelist (expandable sections)
- QE cards (expandable JSON view)
- Species overrides display
- "Run Step" button for individual step execution
- **Parameter Editing (NEW)**: Editable form for common QE parameters:
  - `ecutwfc`, `ecutrho`, `conv_thr`, `occupations`, `smearing`, `degauss`
  - Type-specific parameter sets (scf, nscf, relax, bands, dos)
  - Apply and Reset buttons with validation

### 17.14 Parameter Editing System (2025-12-06)

**New RPCs for Step Parameter Editing**:

| Command | Purpose |
|---------|---------|
| `update_step_params` | Update specific parameters in a step |
| `reset_step_params` | Reset step to template defaults |

**Backend Implementation** (`QVService`):
- `update_step_params()`: Merges new parameters into existing spec
- Type validation for numeric parameters
- Only touches specified fields, doesn't clobber unknown options
- Returns updated step detail for immediate UI refresh

**UI Implementation** (`StepDetailPanel`):
- "Common Parameters" section with editable form fields
- Edit/Cancel/Apply/Reset workflow
- Parameter descriptions and units displayed
- Disabled state when not editing

### 17.15 Workflow Configuration (2025-12-06)

**Reorder Steps**:
- In `WorkflowDetailPanel`: ↑/↓ buttons for each step
- RPC: `reorder_workflow_steps` - takes new step order array
- Updates `workflow.yaml` step list

**Change Structure**:
- Structure dropdown in workflow detail view
- RPC: `change_workflow_structure` - updates workflow and all steps
- Returns list of updated steps and any warnings

### 17.16 Jobs ↔ Analysis Integration (2025-12-06)

**View Analysis Button**:
- Appears in `JobDetailPanel` for completed workflow jobs
- Clicking switches to Analysis view with workflow pre-selected
- Handler: `handleViewAnalysisFromJob(workflowSlug)`

### 17.17 Pre-flight Checks (2025-12-06)

**Before Running Workflows/Steps**:
- RPC: `preflight_check` validates environment before job submission
- Checks performed:
  - QE installation present and executable
  - Project path exists and is writable
  - Structure file exists
  - Pseudopotential directory has files
  - Working directory accessible

**Error Handling**:
- If checks fail, job is NOT submitted
- User-friendly error messages via toast notification
- Warnings logged to console

### 17.18 Demo Project & Recent Projects (2025-12-06)

**Demo Project Creation**:
- **Single Entry Point**: "Browse Demo Gallery" button in welcome screen is the only entry point for demo projects
- Demo projects are stored as snapshots in `resources/demo_projects/*.yml`
- Default demo is `si_bands_demo` (Silicon band structure workflow)
- Available demos: `si_bands_demo`, `si_dos_demo`
- Demo snapshots are generated from test projects using `scripts/generate_demo_snapshots.py`
- If test example projects change, rerun `python scripts/generate_demo_snapshots.py` to regenerate snapshots

**Demo Gallery (Home Sub-View)**:
- Demo Gallery is implemented as `DemoGalleryPanel` component, rendered inline in the Home view
- Uses `HomeMode` state in `ProjectSummaryPanel`: `'welcome' | 'demo-gallery'`
- When `homeMode === 'demo-gallery'` and no project is loaded, `ProjectSummaryPanel` renders `DemoGalleryPanel`
- RPC: `list_demo_projects` returns available demo projects with enriched metadata
- RPC: `create_demo_project` accepts optional `demo_id` parameter (defaults to "si_bands_demo")
- Gallery shows demo cards with:
  - Title and subtitle (from snapshot `meta` section)
  - Description
  - Tags as badges (from `meta.tags`)
  - Difficulty badge (from `meta.difficulty`)
  - "Create Project" button
- Each card has a "Create Project" button that opens file picker for workspace folder
- On success: project is created, loaded, and view switches back to welcome (with project loaded)
- On error: error shown inline on card, gallery stays open for retry

**Demo Snapshot Metadata**:
- Snapshots can include a `meta` section with:
  - `id`: Demo identifier (e.g., "si_bands_demo")
  - `title`: Display title (e.g., "Silicon band structure")
  - `subtitle`: Short description (e.g., "SCF → NSCF → Bands")
  - `tags`: List of tags (e.g., ["bands", "Si", "PW", "tutorial"])
  - `recommended_analysis`: Default analysis type (e.g., "bands", "dos")
  - `difficulty`: Difficulty level (e.g., "beginner", "intermediate", "advanced")
- Backend (`QVService.list_demo_projects()`) reads metadata from snapshot files with fallback to defaults
- If metadata is missing, sensible defaults are used for backward compatibility
- When a demo project is created with `recommended_analysis`, the Analysis view pre-selects that analysis type

**Project Creation Validation**:
- Both `create_project` and `create_demo_project` check if target directory is inside an existing project
- Uses `detect_enclosing_project()` helper from `core/context.py`
- Raises `ValueError` with clear message: "Cannot create a new project inside an existing QuantumVITAS project. The selected folder is inside a project at: <path>. Please choose a parent folder above your current project directory."
- GUI shows error and keeps dialog/gallery open (doesn't close on validation error)
- User can correct the folder choice without losing context

**Workspace/Project Context Display**:
- When a project is loaded, Home view shows a subtle context line:
  - "Workspace: /path/to/parent · Current project: project-name"
- Workspace is derived as the parent directory of `project_root`
- Displayed in small text below the panel header for clarity
- Creates Si project with ready-to-run workflow
- RPC: `create_demo_project` - creates project, imports Si structure, adds workflow

**Recent Projects**:
- Stored in localStorage (`qv-recent-projects`)
- Max 5 recent projects tracked
- Click to open, × to remove
- Displays project name and parent directory

**ProjectSummaryPanel Updates**:
- `recentProjects` prop with list of paths
- `onCreateDemoProject` handler
- `onOpenRecentProject(path)` handler
- `onRemoveRecentProject(path)` handler

### 17.19 Known Limitations

- No SSL/TLS (daemon is local only via stdio)
- Single daemon instance per Electron app
- Request timeout: 60 seconds (configurable in main.ts)
- Daemon must be restarted if Python code changes
- Running jobs cannot be cancelled (ThreadPoolExecutor limitation)
- 3D viewer performance depends on structure size (works well up to ~1000 atoms)
- Job logs are polled, not streamed (2s interval while job is active)

### 17.20 End-to-End User Flow (2025-12-06)

The GUI now supports the complete user workflow without CLI:

1. **Start App** → Welcome screen with options
2. **Create Demo Project** → One-click Si project with workflow
3. **Or Create/Open Project** → Manual project setup
4. **Import Structure** → CIF/XSF file import dialog
5. **Create Workflow** → Template-based workflow creation
6. **Configure Workflow** → Change structure, reorder steps
7. **Edit Parameters** → Adjust ecutwfc, smearing, etc.
8. **Pre-flight Check** → Automatic validation before run
9. **Run Workflow** → Submit job to daemon
10. **Monitor Jobs** → Live status and log streaming
11. **View Analysis** → One-click from completed job to SCF/DOS/Bands charts

### 17.21 Design System & Polish (2025-12-06)

**Design Tokens** (`gui/src/index.css`):

A comprehensive design system was established with CSS custom properties:

| Category | Variables |
|----------|-----------|
| Typography | `--font-sans`, `--font-mono`, `--text-xs` → `--text-3xl` |
| Colors | `--color-primary`, `--color-success`, `--color-error`, `--color-warning` |
| Backgrounds | `--bg-app`, `--bg-primary`, `--bg-secondary`, `--bg-card`, `--bg-hover` |
| Text | `--text-primary`, `--text-secondary`, `--text-tertiary`, `--text-muted` |
| Borders | `--border-subtle`, `--border-color`, `--border-hover`, `--border-focus` |
| Spacing | `--space-1` → `--space-16` (4px → 64px) |
| Radius | `--radius-sm` → `--radius-2xl`, `--radius-full` |
| Shadows | `--shadow-xs` → `--shadow-xl`, `--shadow-glow` |
| Transitions | `--transition-fast`, `--transition-normal`, `--transition-slow` |
| Z-Index | `--z-dropdown` → `--z-toast` |

**Status Bar** (`StatusBar.tsx`):

Bottom status bar showing:
- Daemon connection status (green/red indicator)
- Active project name and path
- Running/pending job counts with pulse animation
- QE detection status (clickable to open Settings)

**Error Boundary** (`ErrorBoundary.tsx`):

React error boundary wrapping main content:
- Catches render errors and displays friendly fallback
- "Try Again" button to reset state
- "Reload App" fallback option
- Expandable error details for debugging

**Standard Button Classes**:

Global CSS classes for consistent button styling:
- `.btn`, `.btn-primary`, `.btn-secondary`, `.btn-ghost`, `.btn-danger`
- Size variants: `.btn-sm`, `.btn-lg`, `.btn-icon`

**Tooltips**:

CSS-only tooltips using `data-tooltip` attributes:
- Position variants: `data-tooltip-position="bottom|left|right"`
- Native title attributes on all navigation buttons

**Accessibility Improvements**:

- Visible focus outlines (`:focus-visible`)
- Proper color contrast in dark theme
- ARIA-compatible button structures
- Semantic HTML throughout

**Layout Conventions**:

Standard panel structure:
```
.panel-header  (title + actions, bg-secondary)
.panel-content (scrollable body, bg-card)
```

Split view layouts:
- Structures: list (380px) + 3D viewer (flex)
- Workflows: list (420px) + detail (flex) + step detail
- Jobs: list (340px) + detail (flex)

---

## 18. Refactoring History - 2025-12-07

### Backend Fixes

| Fix | Details |
|-----|---------|
| `run_step` engine error | Changed `engine.backend` to pass `QuantumEspressoEngine` directly to `run_input_step` |
| Workflow resolution | Updated `Project.get_workflow_ref` to search by `slug` in addition to `id` and `name` |
| si-dos workflow display | Added missing `type` field to all steps in `templates/workflow/si-dos/workflow.yaml` |
| Boundary atoms | Fixed `generate_boundary_atoms` usage to correctly iterate over `BoundaryAtom` objects |

### GUI Improvements

| Feature | Implementation |
|---------|---------------|
| Summary panel refresh | Fixed `handleCreateProjectSuccess` to load project directly instead of via setTimeout (avoiding stale closures) |
| 3D viewer camera state | Added `structureId` tracking to `CameraController` - camera only resets on structure change, not supercell/boundary changes |
| Workflow/step separator | Created `VerticalResizablePane` component for draggable height separation |
| Log persistence | Logs saved to `.qv-daemon.log` in project directory with `setProject`/`readLogs` IPC methods |

### New Components

```
gui/src/components/layout/
├── VerticalResizablePane.tsx  # Draggable height resize
└── VerticalResizablePane.css
```

### Modified Files

**Backend**:
- `src/quantumvitas/api.py` - Fixed `run_step`, boundary atoms
- `src/quantumvitas/project/model.py` - Added slug search to `get_workflow_ref`
- `templates/workflow/si-dos/workflow.yaml` - Added step types

**Frontend**:
- `gui/src/App.tsx` - Project loading, resizable panes, camera state
- `gui/src/components/panels/StructureViewer3D.tsx` - `structureId` prop
- `gui/electron/main.ts` - Log persistence IPC handlers
- `gui/electron/preload.ts` - `setProject`/`readLogs` methods
- `gui/src/types/qv.ts` - New method types

---

## 19. GUI Enhancements - 2025-01-XX

### New Features

| Feature | Implementation | Files |
|---------|---------------|-------|
| Theme switching | CSS variables with `[data-theme="light"]` selector, Settings panel toggle, localStorage persistence | `gui/src/index.css`, `gui/src/components/panels/SettingsPanel.tsx`, `gui/src/App.tsx` |
| Reveal in Finder/Explorer | `shell.showItemInFolder()` IPC handler, `window.qv.revealPath()` API | `gui/electron/main.ts`, `gui/electron/preload.ts` |
| Automatic analysis selection | `detectAnalysisType()` function checks workflow's last step type (dos → DOS, bands → Bands, else → SCF) | `gui/src/components/panels/AnalysisPanel.tsx` |
| Automatic analysis loading | Settings toggle in Settings → Analysis, auto-loads when workflow selected if enabled (default: true) | `gui/src/components/panels/SettingsPanel.tsx`, `gui/src/components/panels/AnalysisPanel.tsx`, `gui/src/App.tsx` |
| Band structure ylim control | Energy range inputs update YAxis `domain` prop dynamically | `gui/src/components/panels/AnalysisPanel.tsx` (BandsChart component) |

### Implementation Details

**Theme System:**
- Dark theme is default (defined in `:root`)
- Light theme uses `[data-theme="light"]` selector with VS Code-inspired colors
- Theme applied via `document.documentElement.setAttribute('data-theme', theme)`
- Persisted in localStorage as `qv-app-settings`

**Reveal Path:**
- Uses Electron's `shell.showItemInFolder()` (cross-platform)
- Works on macOS (Finder), Windows (Explorer), Linux (file manager)
- Accessible via `window.qv.revealPath(path)` in renderer

**Analysis Auto-Selection:**
- Checks last step's `type` field
- Maps: `dos` → DOS, `bands`/`bands_pw` → Bands, otherwise → SCF
- Also checks if workflow has any DOS/bands steps as fallback

**Settings Panel:**
- New sections: Appearance (theme toggle), Analysis (auto-analysis toggle)
- Settings persisted in localStorage
- Type-safe with `AppSettings` interface

### Modified Files

- `gui/src/index.css` - Added light theme CSS variables
- `gui/src/components/panels/SettingsPanel.tsx` - Added theme and auto-analysis settings
- `gui/src/components/panels/AnalysisPanel.tsx` - Added auto-selection and auto-loading
- `gui/src/App.tsx` - Added settings state management and theme application
- `gui/electron/main.ts` - Added `qv-reveal-path` IPC handler
- `gui/electron/preload.ts` - Added `revealPath` method

---

## 20. Refactoring History - 2025-12-07 Session 2

### Bug Fixes

| Fix | Details |
|-----|---------|
| Log clearing on show/hide | Changed `DebugPanel` to use CSS hiding (`height: 0`) instead of returning `null` when hidden - preserves log state |
| "Workflow not found" error | Fixed `preflight_check` in `api.py` - was catching ALL exceptions and reporting "Workflow not found" even for unrelated errors |
| bands_pw editable params | Added `bands_pw` to `EDITABLE_PARAMS` in `StepDetailPanel.tsx` with ecutwfc, ecutrho, nbnd, conv_thr |

### UX Improvements

| Feature | Implementation |
|---------|---------------|
| Search up for project root | When loading/browsing, uses `find_path_context_from_pwd()` from `core/context.py` to search up for project.qv.yml |
| Remove "Load Project" button | Removed button, press Enter in path input to load, browse button directly loads |
| Project subfolder support | If user opens a subfolder, GUI searches up and loads parent project |

### Key Architectural Note

**Project Root Finding**: The GUI now reuses the existing `find_path_context_from_pwd()` function from `core/context.py` rather than implementing duplicate logic. This function:
- Searches up to 20 directories for `project.qv.yml`
- Returns a `PathContext` with `project_root` and context nodes
- Raises `ContextNotFoundError` if no project found

**Daemon Handler**:
```python
def _handle_find_project_root(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    from quantumvitas.core.context import find_path_context_from_pwd, ContextNotFoundError
    
    start_dir = Path(payload.get("start_dir", "")).resolve()
    try:
        ctx = find_path_context_from_pwd(start_dir)
        return {"found": True, "project_root": str(ctx.project_root)}
    except ContextNotFoundError:
        return {"found": False, "project_root": None}
```

### Modified Files

**Backend**:
- `src/quantumvitas/api.py` - Fixed preflight_check exception handling
- `src/quantumvitas/daemon/server.py` - Uses `find_path_context_from_pwd` for project root finding

**Frontend**:
- `gui/src/App.tsx` - Updated `handleBrowseAndLoad` and `handleLoadProject` to search up
- `gui/src/components/layout/Sidebar.tsx` - Removed Load Project button, added Enter key handler
- `gui/src/components/panels/DebugPanel.tsx` - CSS hiding instead of unmounting
- `gui/src/components/panels/DebugPanel.css` - Added `.debug-panel--hidden` class
- `gui/src/components/panels/StepDetailPanel.tsx` - Added `bands_pw` editable params
- `gui/src/types/qv.ts` - Added `find_project_root` RPC type

---

## 21. Refactoring History - 2025-12-07 Session 3

### Project Creation/Opening UX Improvements

| Feature | Implementation |
|---------|---------------|
| Unified CreateProjectDialog | Parent directory + project name approach, creates `<parent>/<slug>` |
| Default projects directory | Setting in SettingsPanel, persisted in localStorage |
| Collapsible sidebar | Toggle button at bottom-right, shows only icons when collapsed |
| Settings panel scrollability | Added `overflow-y: auto` and `height: 100%` to panel CSS |

### Bug Fixes

| Fix | Details |
|-----|---------|
| Demo workflow step display | Fixed step resolution order in `core/resolution.py` - now checks `meta.name`/`meta.slug` before `step_type` |
| CreateProjectDialog CSS missing | Created `gui/src/components/dialogs/CreateProjectDialog.css` |
| Sidebar syntax error | Fixed missing `>` on opening `<div>` tag in `Sidebar.tsx` |

### Reveal in Finder Feature

Added "Reveal in Finder" buttons to all resource panels:

| Panel | Implementation |
|-------|---------------|
| `StepDetailPanel` | File Location section with path and Reveal button |
| `WorkflowDetailPanel` | Updated existing File Location section |
| `StructureDetailPanel` | Updated existing File Location section |
| `ProjectSummaryPanel` | Project path with Reveal button |

### Step Resolution Order (Important!)

The step resolution in `core/resolution.py` now follows this order:

1. **Path** - if selector looks like a path
2. **ULID** - if selector is a 26-char uppercase alphanumeric string
3. **meta.name/meta.slug** - exact match in step YAML's `meta` section
4. **id field** - top-level `id` field in step YAML (legacy)
5. **step_type** - match on `step_type` field (backwards compatibility)
6. **filename stem** - match on step file name without `.step.yaml`

This fixes the bug where clicking "bands" step returned "bands-pp" because "bands" matched `step_type` of `bands-pp.step.yaml` before checking `meta.name`.

### Modified Files

**Backend**:
- `src/quantumvitas/core/resolution.py` - Fixed step resolution order
- `src/quantumvitas/api.py` - Added `absolute_path` to step detail responses

**Frontend**:
- `gui/src/components/dialogs/CreateProjectDialog.tsx` - Parent dir + name approach
- `gui/src/components/dialogs/CreateProjectDialog.css` - New file
- `gui/src/components/panels/SettingsPanel.tsx` - Default projects directory setting
- `gui/src/components/panels/SettingsPanel.css` - Path input styles
- `gui/src/components/layout/Sidebar.tsx` - Collapsible sidebar, syntax fix
- `gui/src/components/layout/Sidebar.css` - Collapsed state styles
- `gui/src/components/layout/StatusBar.tsx` - Full project path display
- `gui/src/components/layout/StatusBar.css` - Path display styles
- `gui/src/components/panels/StepDetailPanel.tsx` - File location with Reveal button
- `gui/src/components/panels/StepDetailPanel.css` - File location styles
- `gui/src/components/panels/WorkflowListPanel.tsx` - Reveal in Finder for workflow
- `gui/src/components/panels/WorkflowListPanel.css` - File location styles
- `gui/src/components/panels/StructureListPanel.tsx` - Reveal in Finder for structure
- `gui/src/components/panels/StructureListPanel.css` - File location styles
- `gui/src/components/panels/ProjectSummaryPanel.tsx` - Reveal in Finder for project
- `gui/src/components/panels/ProjectSummaryPanel.css` - Reveal button styles
- `gui/src/types/qv.ts` - Added `absolute_path` to `StepDetail` interface

---

## 22. GUI E2E Testing (Playwright + Electron)

### 22.1 Overview

The GUI uses **Playwright** for end-to-end (E2E) testing of the Electron application. All tests use a **unified Electron fixture** that automatically chooses the appropriate launch strategy based on platform:

- **Linux**: Uses Playwright's native `_electron.launch()` API (works out of the box)
- **macOS**: Uses CDP (Chrome DevTools Protocol) workaround (required due to Playwright bug)
- **Windows**: Uses Linux path (can be extended if needed)

**Key benefit**: The same test specs run on all platforms - the fixture handles platform differences transparently.

### 22.2 The macOS Compatibility Issue

Playwright's `_electron.launch()` automatically injects `--remote-debugging-port=0` for Chromium debugging. On macOS, Electron rejects this flag with "bad option: --remote-debugging-port=0", causing tests to fail.

**Root cause**: Playwright's automatic flag injection doesn't work with Electron on macOS, even with the latest Playwright version.

**Solution**: Manual Electron spawn + CDP connection workaround, hidden behind the unified fixture.

### 22.3 Unified Test Fixture

**Location**: `gui/tests/e2e/fixtures/electronTest.ts`

The unified fixture automatically detects the platform and chooses the appropriate launch method:

```typescript
import { electronTest as test, expect } from './fixtures/electronTest';

test('my test', async ({ appPage }) => {
  await expect(appPage.getByTestId('qv-welcome-title')).toBeVisible();
});
```

**How it works**:
- On Linux/Windows: Uses `launchApp()` from `helpers/electron.ts` (Playwright's `_electron.launch()`)
- On macOS: Uses `launchElectronViaCDP()` from `helpers/electron_cdp.ts` (CDP workaround)

The fixture provides a single `appPage: Page` fixture that works identically on all platforms.

### 22.4 Test Architecture

#### Linux/Windows Launch (Native Playwright)

**Location**: `gui/tests/e2e/helpers/electron.ts`

Uses Playwright's built-in `_electron.launch()` API:

```typescript
import { _electron as electron, ElectronApplication, Page } from '@playwright/test';

const launchArgs = [mainPath];  // dist-electron/main.js
// On Linux CI, disable sandbox (no root access for SUID sandbox setup)
if (os.platform() === 'linux') {
  launchArgs.unshift('--no-sandbox');
}

const app = await electron.launch({
  executablePath: electronExecutablePath,  // Platform-specific binary path
  args: launchArgs,
  cwd: guiDir,
});
```

**Linux CI Note**: The `--no-sandbox` flag is required on Linux CI environments (like GitHub Actions) because we don't have root access to configure the SUID sandbox helper (`chrome-sandbox`). This is safe in CI environments where the test process is already isolated.

#### macOS Launch (CDP Workaround)

**Location**: `gui/tests/e2e/helpers/electron_cdp.ts`

Manually spawns Electron with remote debugging enabled, then connects via CDP:

```typescript
// 1. Spawn Electron with environment variable
const electronProcess = spawn(electronExecutablePath, [mainPath], {
  env: {
    ELECTRON_REMOTE_DEBUG_PORT: '9222',  // Enables remote debugging
    // ... other env vars
  },
});

// 2. Extract WebSocket URL from Electron's stderr output
// Electron prints: "DevTools listening on ws://127.0.0.1:9222/devtools/browser/..."
const wsUrl = extractFromStderr(electronProcess);

// 3. Connect via CDP
const browser = await chromium.connectOverCDP(wsUrl);
```

**Test files** (all use the unified fixture):
- `tests/e2e/welcome.spec.ts` - Welcome screen tests
- `tests/e2e/demo_workflow.spec.ts` - Demo project creation and workflow step verification
- `tests/e2e/demo_workflow_run.spec.ts` - Full workflow execution with status tracking and analysis verification (combined test)

### 22.6 Duplicate Test ID Detection

The `electronTest` fixture automatically checks for duplicate `data-testid` values at the end of each test. This prevents test selector ambiguity and ensures reliable E2E tests.

**Implementation**:
- Helper function: `gui/tests/e2e/helpers/testid.ts` - `assertNoDuplicateTestIds()`
- Integrated into `electronTest` fixture teardown (runs after each test)
- Fails the test immediately if duplicates are detected

**Test ID Naming Convention**:
- **Always use namespaced IDs** to avoid collisions across different views/components:
  - `qv-welcome-btn-open-project` (Welcome screen)
  - `qv-sidebar-btn-open-project` (Sidebar)
  - `qv-demo-card-si-bands-demo` (Demo Gallery)
  - `qv-step-row-{stepId}` (Workflow steps - includes step ID for uniqueness)
- **Never reuse the same test ID** for different UI elements, even in different views
- **For list items**, include a unique identifier (e.g., item ID, index, or slug) in the test ID

**Example violations that will fail tests**:
```typescript
// ❌ BAD - same ID in different components
<button data-testid="qv-btn-open-project">  // In Welcome
<button data-testid="qv-btn-open-project">  // In Sidebar

// ✅ GOOD - namespaced IDs
<button data-testid="qv-welcome-btn-open-project">  // In Welcome
<button data-testid="qv-sidebar-btn-open-project">  // In Sidebar
```

**When adding new components**:
- Use a clear namespace prefix (e.g., `qv-{component}-{element}`)
- For repeated elements (lists), include unique identifiers
- Run E2E tests to verify no duplicates are introduced

### 22.4 Remote Debugging Setup

The Electron main process (`gui/electron/main.ts`) enables remote debugging when `ELECTRON_REMOTE_DEBUG_PORT` is set:

```typescript
// Enable remote debugging for E2E tests if requested via environment variable
if (process.env.ELECTRON_REMOTE_DEBUG_PORT) {
  const port = parseInt(process.env.ELECTRON_REMOTE_DEBUG_PORT, 10);
  if (!isNaN(port)) {
    // This must be called before app.whenReady()
    app.commandLine.appendSwitch('remote-debugging-port', port.toString());
  }
}
```

This allows the CDP helper to connect to Electron's debugging endpoint.

### 22.5 Platform-Specific Binary Paths

Both helpers compute Electron binary paths explicitly:

```typescript
function getElectronExecutablePath(): string {
  const electronDistDir = path.join(repoRoot, 'gui', 'node_modules', 'electron', 'dist');
  
  if (os.platform() === 'darwin') {
    // macOS: Electron.app/Contents/MacOS/Electron
    return path.join(electronDistDir, 'Electron.app', 'Contents', 'MacOS', 'Electron');
  } else if (os.platform() === 'win32') {
    // Windows: electron.exe
    return path.join(electronDistDir, 'electron.exe');
  } else {
    // Linux: electron
    return path.join(electronDistDir, 'electron');
  }
}
```

**Key point**: Always use the direct binary path, never a wrapper script or `require('electron')`.

### 22.6 Automatic Console Error Detection

**Location**: `gui/tests/e2e/fixtures/electronTest.ts`

The unified Electron fixture automatically monitors and fails tests on unexpected console errors:

**What is monitored**:
- Console errors (`console.error()` calls)
- Page errors (uncaught exceptions)
- Network request failures

**What is allowed** (benign messages):
- React warnings (dev mode)
- React DevTools messages
- Webpack dev server messages (if in dev mode)

**Implementation**:
```typescript
// Collect errors during test execution
const consoleErrors: string[] = [];
const pageErrors: string[] = [];
const networkFailures: string[] = [];

page.on('console', (msg) => {
  if (msg.type() === 'error' && !isBenignConsoleMessage(msg.text())) {
    consoleErrors.push(`[Console Error] ${msg.text()}`);
  }
});

page.on('pageerror', (error) => {
  pageErrors.push(`[Page Error] ${error.message}`);
});

// Auto-assert after test completes
if (consoleErrors.length > 0 || pageErrors.length > 0 || networkFailures.length > 0) {
  throw new Error(`Test failed due to unexpected errors:\n...`);
}
```

**Benefits**:
- Tests automatically catch runtime errors that might not cause visible UI failures
- No need to manually check for errors in each test
- Clear error messages with full console output

**Allowlist maintenance**:
- Keep `BENIGN_CONSOLE_PATTERNS` minimal and documented
- Only add patterns for messages we can't avoid and don't indicate bugs
- Review allowlist periodically to ensure it's still appropriate

### 22.7 Running E2E Tests

**Same command on all platforms** - the fixture handles platform differences:

```bash
cd gui
npm run build:e2e  # Build Electron app first
npm run test:e2e   # Runs all E2E tests (unified fixture)
```

Or run specific tests:
```bash
npx playwright test tests/e2e/welcome.spec.ts --project=electron
```

The fixture automatically:
- Uses `_electron.launch()` on Linux/Windows
- Uses CDP workaround on macOS

### 22.7 CI Configuration

The GitHub Actions workflow (`.github/workflows/tests.yml`) runs E2E tests **on every push** to the `v2-python` branch, **after QE compilation** is complete. The tests run on both Linux and macOS:

```yaml
# E2E tests run as part of the tests-with-qe job, after:
# 1. QE source download and compilation
# 2. QE installation verification
# 3. Python dependencies installation
# 4. Python pytest tests

- name: Run GUI E2E tests
  run: |
    export QE_HOME=$HOME/src/q-e-qe-7.5
    export PATH="$QE_HOME/bin:$PATH"
    # Unified E2E tests - fixture automatically chooses launch strategy:
    # Linux: uses Playwright's _electron.launch()
    # macOS: uses CDP workaround
    if [ "${{ matrix.os }}" == "ubuntu-latest" ]; then
      xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" \
        npx playwright test \
          tests/e2e/welcome.spec.ts \
          tests/e2e/demo_workflow.spec.ts \
          tests/e2e/demo_workflow_run.spec.ts \
          --project=electron
    else
      npx playwright test \
        tests/e2e/welcome.spec.ts \
        tests/e2e/demo_workflow.spec.ts \
        tests/e2e/demo_workflow_run.spec.ts \
        --project=electron
    fi
```

**Key points**:
- E2E tests **always run on push** (no conditional skipping)
- Tests run **after QE compilation** (QE must be available for `demo_workflow_run.spec.ts`)
- Both Linux and macOS run the exact same test files
- Linux uses `xvfb-run` for headless display; macOS runs directly
- Tests have access to QE binaries via `QE_HOME` and `PATH` environment variables

### 22.8 Test Data Attributes

All UI components use `data-testid` attributes for reliable test selection:

| Component | Test IDs |
|-----------|----------|
| Welcome screen | `qv-welcome-title`, `qv-btn-open-project`, `qv-btn-create-new-project`, `qv-btn-create-demo-project` |
| Navigation | `qv-nav-{home,structures,workflows,jobs,analysis,settings,debug}` |
| Project summary | `qv-home-project`, `qv-project-path`, `qv-btn-project-reveal` |
| Workflows | `qv-workflows-view`, `qv-workflow-row`, `qv-workflow-detail`, `qv-btn-run-workflow` |
| Steps | `qv-steps-list`, `qv-step-row`, `qv-step-detail`, `qv-step-id`, `qv-step-file-path` |
| Jobs | `qv-jobs-view`, `qv-job-row`, `qv-job-status`, `qv-job-detail` |
| Analysis | `qv-analysis-view`, `qv-analysis-bands-chart`, `qv-analysis-fermi`, `qv-analysis-kpath` |
| Dialogs | `qv-create-project-dialog`, `qv-input-parent-dir`, `qv-input-project-name`, `qv-btn-confirm-create` |

### 22.9 Helper Functions

**`gui/tests/e2e/fixtures/electronTest.ts`** (Unified fixture):
- `electronTest` - Playwright test fixture that provides `appPage: Page`
- Automatically chooses launch strategy based on platform
- Re-exports `expect`, `navigateToView`, `waitForDaemonConnection`

**`gui/tests/e2e/helpers/electron.ts`** (Linux/Windows):
- `launchApp(options?)` - Launches Electron via `_electron.launch()`
- `closeApp(app)` - Closes Electron app
- `navigateToView(page, view)` - Navigates to a view tab
- `waitForDaemonConnection(page, timeout?)` - Waits for daemon connection

**`gui/tests/e2e/helpers/electron_cdp.ts`** (macOS):
- `launchElectronViaCDP(options?)` - Spawns Electron and connects via CDP
- Returns `{ browser, page, electronProcess, close }`
- Automatically extracts WebSocket URL from Electron output
- Handles process cleanup

**`gui/tests/e2e/helpers/paths.ts`**:
- `getRepoRoot()` - Finds repository root
- `getGuiDir()` - Gets GUI directory
- `ensureE2EProjectsRoot()` - Ensures `temp/e2e_projects/` exists
- `createUniqueProjectDir(prefix)` - Creates unique test project directory in `temp/e2e_projects/`
- `cleanupProjectDir(dirPath)` - Cleans up test projects

### 22.10 Test Performance

- **Welcome test**: ~3.1 seconds
- **Demo workflow tests**: ~5.2 seconds each (2 tests)
- **Full workflow run test**: ~30 seconds (includes QE execution, status tracking, and analysis verification)

**Total E2E test suite**: ~44 seconds (all 4 tests)

All tests properly clean up Electron processes after completion. Tests run serially (one Electron instance at a time) to ensure proper isolation.

### 22.11 Known Limitations

1. **macOS requires CDP workaround**: Native `_electron.launch()` doesn't work on macOS due to Playwright bug
2. **QE required for workflow tests**: `demo_workflow_run.spec.ts` requires QE to be installed (tests fail if QE is not available)
3. **Test isolation**: Each test creates a unique project directory in `temp/e2e_projects/`
4. **Serial execution**: Tests run serially (not in parallel) to ensure only one Electron instance exists at a time
5. **Test project cleanup**: `temp/e2e_projects/` is cleared before each test but left after tests for inspection

### 22.12 Files Structure

```
gui/tests/e2e/
├── fixtures/
│   └── electronTest.ts       # Unified Electron fixture (auto-detects platform)
├── helpers/
│   ├── electron.ts           # Linux/Windows: Native Playwright API
│   ├── electron_cdp.ts       # macOS: CDP workaround
│   ├── paths.ts              # Path utilities (creates projects in temp/e2e_projects/)
│   └── index.ts              # Exports
├── welcome.spec.ts           # Welcome screen tests (unified - works on all platforms)
├── demo_workflow.spec.ts     # Demo workflow tests (unified - works on all platforms)
└── demo_workflow_run.spec.ts # Full workflow run test (unified - combines status tracking and analysis verification)
```

**Note**: All test files use the unified `electronTest` fixture. There are no platform-specific test files anymore.

### 22.13 Test Project Location

All E2E-generated projects are created in `temp/e2e_projects/` (relative to repo root). The `paths.ts` helper ensures this directory exists and creates unique subdirectories for each test run.

**Test lifecycle**:
- Before each test: `temp/e2e_projects/` is cleared (via `clearE2EProjectsRoot()`)
- During test: Unique project directories are created (e.g., `temp/e2e_projects/e2e-run-<timestamp>/`)
- After test: Projects are left in place for inspection (no cleanup)

### 22.14 Future Improvements

- **Test coverage**: Add more E2E tests for edge cases and error handling
- **Windows support**: Verify and extend Windows support if needed
- **Playwright fix**: When Playwright fixes macOS compatibility, the fixture can be simplified to always use `_electron.launch()`

---

## 23. Project Snapshot Format

The project snapshot format allows exporting a complete QuantumVITAS project into a single YAML file and recreating it elsewhere. This is useful for:
- **Project templates**: Create reusable project definitions
- **Version control**: Track project structure without binary files
- **Sharing**: Distribute demo projects or workflows
- **Demo projects**: Pre-configured projects with reference analysis data

**Important**: Snapshots are **templates**, not bit-for-bit backups. When materializing a snapshot, all ULIDs are regenerated to create a fresh ID universe.

### 23.1 Snapshot Schema

A snapshot is a YAML file with the following structure:

```yaml
version: 1
project:
  meta:
    id: "<original_project_ulid>"
    name: "Si demo"
    slug: "si-demo"
    kind: "project"
    path: "."
  settings:
    # Project-level settings from project.qv.yml
structures:
  - meta:
      id: "<structure_ulid>"
      name: "Si bulk"
      slug: "si-bulk"
      kind: "structure"
      path: "structures/si.json"
    data:  # Full pymatgen structure JSON
      @module: "pymatgen.core.structure"
      @class: "Structure"
      lattice: { ... }
      sites: [ ... ]
workflows:
  - meta:
      id: "<workflow_ulid>"
      name: "Si bands+dos"
      slug: "si-bands-dos"
      kind: "workflow"
      path: "workflows/si-bands-dos/workflow.yaml"
    mode: "normal"
    structure: "si-bulk"   # Structure reference (slug/name)
    working_dir: "raw"
    steps:
      - meta:
          id: "<step_ulid>"
          name: "scf"
          slug: "scf"
          kind: "step"
          path: "workflows/si-bands-dos/steps/scf.step.yaml"
        step_type: "scf"
        parameters: { ... }
        cards: { ... }
        # Note: structure_id and parent_workflow_id are NOT in step YAML
        # Structure is inherited from workflow.structure_id
        # Parent workflow is implicit from file location
        species_overrides:
          Si:
            mass: 28.08
            pseudopot: "Si.pbe-n-rrkjus_psl.1.0.0.UPF"
pseudo:
  directory: "pseudo"
  files:
    - "Si.pbe-n-rrkjus_psl.1.0.0.UPF"
    - "O.pbe-n-rrkjus_psl.1.0.0.UPF"
```

**Key points**:
- **Version**: Currently `1` (for future schema evolution)
- **Project**: Project metadata and settings
- **Structures**: Full structure data (pymatgen JSON) with metadata
- **Workflows**: Complete workflow definitions with all steps
- **Pseudo**: Pseudopotential filenames only (content NOT embedded)

### 23.3 Snapshot Semantics (Option B: Template with Fresh IDs)

**Export behavior** (`export_project_to_snapshot`):
- Preserves all `id` and `*_id` fields as recorded in the original project
- Exports complete resource graph with all cross-references (`structure_id` in workflows, `step_id` in workflow steps)
- Note: Step YAML files do NOT contain `parent_workflow_id` or `structure_id` in the DAG model - these are only in snapshot's internal data structures for graph reconstruction
- Snapshot contains the full graph structure with original ULIDs

**Materialize behavior** (`materialize_project_from_snapshot`):
- **Always regenerates new ULIDs** for all resources (project, workflows, structures, steps)
- Builds an internal mapping (`old_id → new_id`) during materialization
- Rewrites all `*_id` cross-references using the mapping to maintain graph structure
- Snapshot IDs are used **only as a template graph** - they do not survive materialization
- Names, slugs, and logical relationships (which workflow uses which structure/steps) are preserved

**Key implications**:
- ✅ Multiple projects from the same snapshot are independent and have distinct ULIDs
- ✅ Graph structure is preserved (same counts, same relationships)
- ✅ No ID collisions between projects created from the same snapshot
- ❌ Snapshot is **not a bit-for-bit backup** - IDs change on materialization
- ❌ Original project ULIDs are **not preserved** in materialized projects

**Demo/Reference Features**:
- Demo recognition relies on `origin.kind == "demo"` and `origin.demo_id` (stored in project settings)
- Reference analysis lookup uses `origin.reference_artifacts` or `snapshot.meta.reference_artifacts`
- **These features do NOT depend on preserving snapshot ULIDs** - they use stable demo identifiers

### 23.4 Pseudopotential Files

**Pseudopotential file contents are NOT embedded** in snapshots:

- **Export**: Snapshot lists pseudopotential filenames from `pseudo/` directory
- **Import**: `pseudo/` directory is created, but files are NOT created
- **Rationale**: Pseudopotentials are large binary files; snapshot format focuses on project structure/metadata
- **Usage**: Users must provide pseudopotential files separately after importing a snapshot

### 23.5 CLI Commands

#### Export Project to Snapshot

```bash
qv save-project snapshot.yml
qv save-project my-project-snapshot.yml --overwrite
```

- Exports current project (auto-detected from CWD) to a YAML file
- Use `--project` to specify project root explicitly
- Use `--overwrite` to replace existing snapshot file

#### Create Project from Snapshot

```bash
qv init project --snapshot snapshot.yml --path /path/to/parent --name "My New Project"
```

- `--snapshot`: Path to snapshot YAML file
- `--path`: Parent directory where new project will be created (defaults to CWD)
- `--name`: Optional name for the new project (defaults to snapshot's project name)

**Note**: When using `--snapshot`, the `--path` argument is treated as the **parent directory** (not the project directory itself), similar to the demo project creation flow.

### 23.5 API Methods

The snapshot functionality is exposed via `QVService`:

```python
# Export project to snapshot dict
snapshot_dict = QVService.export_project_snapshot(project_root)

# Save snapshot to YAML file
output_path = QVService.save_project_snapshot(
    project_root=project_root,
    output_path=Path("snapshot.yml"),
    overwrite=False,
)

# Create project from snapshot
new_project_root = QVService.create_project_from_snapshot(
    parent_dir=Path("/path/to/parent"),
    snapshot_path=Path("snapshot.yml"),
    project_name="New Project",
)
```

### 23.6 Implementation Details

**Core module**: `src/quantumvitas/project/snapshot.py`

- `ProjectSnapshot`: Dataclass representing snapshot structure
- `export_project_to_snapshot()`: Reads project directory, packages into snapshot
- `materialize_project_from_snapshot()`: Creates new project from snapshot with ULID remapping

**Key implementation notes**:
- Uses existing model loaders (`load_project`, `load_workflow`, `load_structure_model`)
- Handles both `__qv_meta__` wrapper and direct structure dict formats
- Rewrites `parent_workflow_id` references during materialization
- Creates directory structure but not pseudopotential files

### 23.7 Roundtrip Guarantees

After `export → import` roundtrip, the following are guaranteed:

✅ **Preserved**:
- Project name, slug, settings
- Structure data (composition, sites, lattice parameters)
- Workflow structure (mode, working_dir, structure reference)
- Step specifications (step_type, parameters, cards, species_overrides)
- Logical relationships (workflow→structure, workflow→steps, step→workflow)

❌ **Changed**:
- All ULIDs (project, workflows, structures, steps)
- Filesystem paths (relative to new project root)

⚠️ **Not included**:
- Pseudopotential file contents (only filenames)
- QE output files (raw/, reference/ directories are empty)
- Trash directory contents

### 23.8 Unit Tests

Comprehensive unit tests in `tests/unit/test_project_snapshot.py`:

- **Export tests**: Verify snapshot structure and content
- **Import tests**: Verify project recreation and ULID regeneration
- **Roundtrip tests**: Verify complete export→import cycle
- **CLI tests**: Test `save-project` and `init project --snapshot` commands
- **Edge cases**: Pseudo files, overwrite protection, etc.

All tests use temporary directories and clean up after themselves.

---

## 24. Analysis Pipeline - JSON Artifacts System (2025-12-XX)

### 24.1 Overview

The analysis pipeline provides a clean separation between:
1. **Analysis** (backend) - Parsing QE outputs and writing JSON artifacts
2. **Plotting** (frontend) - Reading JSON via RPC and rendering charts

This design ensures:
- Parsed data persists across sessions
- No redundant re-parsing of QE outputs
- Clean error states when outputs are missing
- Automatic and manual analysis modes

### 24.2 JSON Artifact Locations

Analysis JSON files are stored in a dedicated directory per workflow:

```
<project_root>/
└── workflows/
    └── <workflow-slug>/
        ├── workflow.yaml
        ├── raw/                    # QE output files
        │   ├── scf.out
        │   ├── bands.dat.gnu
        │   └── ...
        └── analysis/               # JSON artifacts
            ├── scf.json
            ├── dos.json
            └── bands.json
```

### 24.3 JSON Schema (from Dataclasses)

**SCF (`scf.json`)**:
```json
{
  "converged": true,
  "total_energy": -10.5,
  "fermi_energy": 5.123,
  "calculation_type": "scf",
  "n_electrons": 8,
  "n_kpoints": 10,
  "ecutwfc": 50.0,
  "iterations": [
    {"iteration": 1, "total_energy": -10.4, "scf_accuracy": 1e-4},
    {"iteration": 2, "total_energy": -10.5, "scf_accuracy": 1e-8}
  ]
}
```

**DOS (`dos.json`)**:
```json
{
  "energies": [-10.0, -9.9, ...],
  "dos": [0.0, 0.01, ...],
  "idos": [0.0, 0.005, ...],
  "fermi_energy": 5.123
}
```

**Bands (`bands.json`)**:
```json
{
  "k_distances": [0.0, 0.1, ...],
  "energies": [[-5.0, -4.9, ...], [1.0, 1.1, ...]],
  "n_bands": 8,
  "n_kpoints": 100,
  "fermi_energy": 5.123,
  "high_symmetry_points": [
    {"label": "Γ", "k_distance": 0.0, "k_coords": [0, 0, 0]},
    {"label": "X", "k_distance": 1.5, "k_coords": [0.5, 0, 0.5]}
  ]
}
```

### 24.4 Backend: AnalysisArtifacts Helper

**Module**: `src/quantumvitas/analysis/artifacts.py`

```python
from quantumvitas.analysis.artifacts import AnalysisArtifacts

# Get expected path for an artifact
path = AnalysisArtifacts.get_artifact_path(project_root, workflow_slug, "bands")

# Write analysis data to JSON
AnalysisArtifacts.write_artifact(project_root, workflow_slug, "bands", band_data)

# Read analysis data from JSON (returns None if missing)
band_data = AnalysisArtifacts.read_artifact(project_root, workflow_slug, "bands", BandStructureData)

# Clear all artifacts for a workflow (called on re-run)
AnalysisArtifacts.clear_artifacts(project_root, workflow_slug)
```

### 24.5 Backend API: ensure_workflow_analysis

**Method**: `QVService.ensure_workflow_analysis()`

```python
from quantumvitas.api import QVService, AnalysisStatus

status = QVService.ensure_workflow_analysis(
    project_root=project_root,
    workflow_selector="si-bands",
    analysis_type="bands",  # "scf" | "dos" | "bands"
    force=False,            # True to re-parse even if JSON exists
    step_selector="scf",    # Required for SCF analysis
)

# AnalysisStatus contains:
# - ok: bool (success/failure)
# - message: str (human-readable)
# - artifact_path: Path | None (JSON file location)
# - data_available: bool (whether JSON has valid data)
# - error_code: str | None ("file_not_found", "analysis_error", etc.)
```

**Behavior**:
1. If JSON artifact exists and `force=False`: Return success immediately
2. If JSON missing or `force=True`: Parse QE outputs, write JSON, return status
3. If QE outputs missing: Return error with clear message

### 24.6 RPC Handler

**Daemon**: `src/quantumvitas/daemon/server.py`

```python
# RPC command: "ensure_workflow_analysis"
# Payload:
{
  "project_root": "/path/to/project",
  "workflow_selector": "si-bands",
  "analysis_type": "bands",
  "force": false,
  "step_selector": null  # Only needed for SCF
}

# Response:
{
  "ok": true,
  "message": "Bands analysis artifact created",
  "artifact_path": "/path/to/project/workflows/si-bands/analysis/bands.json",
  "data_available": true,
  "error_code": null
}
```

### 24.7 GUI TypeScript Types

**File**: `gui/src/types/qv.ts`

```typescript
interface AnalysisStatus {
  ok: boolean;
  message: string;
  artifact_path: string | null;
  data_available: boolean;
  error_code: string | null;
}

// In QVCommandMap:
ensure_workflow_analysis: {
  payload: {
    project_root: string;
    workflow_selector: string;
    analysis_type: 'scf' | 'dos' | 'bands';
    force?: boolean;
    step_selector?: string;
  };
  result: AnalysisStatus;
};
```

### 24.8 get_*_data Artifact Integration

The existing analysis RPC methods now:
1. **First** try to load from JSON artifact
2. **If missing**, parse raw QE output and save JSON on-the-fly
3. **Return** data in the same format as before

This ensures backward compatibility while gaining caching benefits.

### 24.9 Cache Invalidation

**When workflow is run** (`QVService.run_workflow`):
- `AnalysisArtifacts.clear_artifacts()` is called at the start
- Deletes all JSON files in `<workflow>/analysis/`
- Ensures old analysis data doesn't persist after re-run

**Manual invalidation**:
- Call `ensure_workflow_analysis(force=True)` to re-parse
- "Run Analysis" button in GUI does this

### 24.10 GUI Automatic Analysis Behavior

**Setting**: `automaticAnalysis` (boolean, default: `true`)
- Stored in `AppSettings` (localStorage)
- Toggled in Settings → Analysis section

**AnalysisPanel States**:
| State | Condition | Display |
|-------|-----------|---------|
| `idle` | No workflow selected | "Select a workflow" placeholder |
| `analyzing` | RPC in progress | Loading spinner + "Analyzing {type}..." |
| `ready` | Data loaded | Chart renders |
| `error` | Analysis failed | Error message + "Retry" button |

**Flow when entering Analysis view**:
1. If `automaticAnalysis === true` and workflow selected:
   - Call `ensure_workflow_analysis(force=false)`
   - Show "Analyzing..." state
   - On success, call `get_*_data` and render chart
2. If `automaticAnalysis === false`:
   - Show "No analysis data yet" placeholder
   - User must click "Run Analysis" button

**"Run Analysis" button**:
- Calls `ensure_workflow_analysis(force=true)` (re-parse)
- Then calls `get_*_data` to refresh chart

### 24.11 Unit Tests

**File**: `tests/unit/test_analysis_artifacts.py`

Tests cover:
- `AnalysisArtifacts.get_artifact_path()` - correct path convention
- `write_artifact()` / `read_artifact()` - roundtrip serialization
- `clear_artifacts()` - deletion behavior
- `ensure_workflow_analysis()` for scf/dos/bands
- `force=False` behavior (no re-parse if JSON exists)
- `force=True` behavior (always re-parse)
- Integration with `get_*_data` (artifact-first loading)
- Cache invalidation on `run_workflow`

### 24.12 E2E Tests

**File**: `gui/tests/e2e/demo_workflow_run.spec.ts`

Test case: "automatic analysis loads charts without manual click"

1. Enable `autoAnalysis` in Settings
2. Create demo project (si_bands_demo)
3. Run workflow and wait for completion
4. Navigate to Analysis view
5. Assert: "Analyzing..." loading state appears
6. Assert: Bands chart renders automatically
7. Assert: Fermi energy is displayed (non-empty)
8. Assert: K-path labels (Γ, X, L, etc.) are visible

### 24.13 Reference Analysis for Demo Projects

Demo projects include pre-computed reference analysis data so users can:
1. See expected bands/DOS/SCF results without running QE
2. Compare their computed results with reference data

**Reference JSON Locations**:

```
resources/demo_projects/
├── si_bands_demo.yml              # Demo snapshot
├── si_bands_demo.bands.json       # Reference bands data
├── si_bands_demo.scf.json         # Reference SCF data
├── si_dos_demo.yml
├── si_dos_demo.dos.json           # Reference DOS data
└── si_dos_demo.scf.json
```

**Snapshot Meta Schema Extension**:

Demo snapshots now include a `reference_artifacts` field:

```yaml
meta:
  id: si_bands_demo
  title: Silicon band structure
  reference_artifacts:
    bands: si_bands_demo.bands.json
    scf: si_bands_demo.scf.json
```

**Project Origin Tracking**:

When `create_demo_project` materializes a project, it stores origin info in `project.qv.yml`:

```yaml
project:
  settings:
    origin:
      kind: demo
      demo_id: si_bands_demo
      reference_artifacts:
        bands: si_bands_demo.bands.json
        scf: si_bands_demo.scf.json
```

**API: `get_reference_analysis`**:

```python
from quantumvitas.api import QVService

result = QVService.get_reference_analysis(
    project_root=project_root,
    workflow_selector="si-bands",
    analysis_type="bands",  # or "dos", "scf"
)

# Returns: Dict with reference data (same format as get_*_data)
# or None if not a demo project or no reference for this type
```

**RPC Handler**: `get_reference_analysis` in daemon/server.py

**GUI Behavior**:

1. When loading analysis, `AnalysisPanel` fetches both current data and reference data
2. If reference data exists:
   - Bands: Reference curves shown as dashed gray lines behind current (solid) bands
   - Toggle in header to show/hide reference (not yet user-controllable)
3. If only reference data exists (workflow not run):
   - Shows reference chart with notice: "Showing reference results from the demo. Run the workflow to generate your own data."

**Unit Tests**: `tests/unit/test_analysis_artifacts.py::TestGetReferenceAnalysis`

---

## 25. GUI Polish Phase (2025-12-XX)

### 25.1 Sidebar Refactoring

**Before**: The sidebar had an editable text input for project path that was confusing - users could type paths but hitting Enter didn't always work as expected.

**After**: 
- **Read-only project path display**: Shows current project path (or "No project loaded") as non-editable text
- **Reveal button**: Opens the project folder in system file manager (Finder/Explorer)
- **Always-visible action buttons**: Three compact buttons are always available regardless of current view:
  - "Open Project…" (`data-testid="qv-btn-open-project"`)
  - "Create New…" (`data-testid="qv-btn-create-new-project"`)
  - "Demo Gallery…" (`data-testid="qv-btn-demo-gallery"`)

These buttons work from any view, not just Home. They're styled as compact text buttons in expanded mode, and icon-only buttons when sidebar is collapsed.

**Files Changed**:
- `gui/src/components/layout/Sidebar.tsx` - Complete refactor
- `gui/src/components/layout/Sidebar.css` - New styles for path display, action buttons
- `gui/src/App.tsx` - Updated to pass new props, removed old handlers

### 25.2 Analysis UX: SCF vs DOS/Bands

**Key distinction**:
- **SCF analysis** is **step-based** - you analyze SCF convergence for a specific SCF step
- **DOS/Bands analysis** is **workflow-level** - combines data from multiple steps

**Changes**:
- SCF tab shows a step selector dropdown that **only lists SCF-type steps** (scf, relax, vc-relax, nscf)
- First SCF step is auto-selected when entering SCF view
- DOS/Bands tabs **do not show a step selector** - analysis is workflow-level
- State machine fixes prevent UI from "locking" onto wrong analysis type

**Code Location**: `gui/src/components/panels/AnalysisPanel.tsx`

### 25.3 Demo Project Naming

**Problem**: If user creates the same demo twice in the same workspace, the second would silently overwrite.

**Solution**: When materializing a project from snapshot, if the target directory exists, automatically append a numeric suffix:

```
si-bands-demo/      # First creation
si-bands-demo-2/    # Second creation
si-bands-demo-3/    # Third creation
```

All suffixed projects still get `origin.kind: demo` and `origin.demo_id` metadata, so reference analysis still works.

**Code Location**: `src/quantumvitas/project/snapshot.py::materialize_project_from_snapshot()`

### 25.4 Graceful Handling of Deleted Resources

**Problem**: If user deletes project folder or files while app is running, RPC calls would crash with unhelpful errors.

**Solution**: Enhanced error handling in daemon:

1. **Project path validation**: The `_require_path()` helper now specifically detects missing project roots and project.qv.yml files
2. **Specific error codes**: Returns `project_missing` error code (with `kind: "project_missing"`) for GUI to handle
3. **Clear error messages**: "Project folder not found: /path" or "Project configuration not found: project.qv.yml"

**GUI Behavior** (recommended implementation):
- On `project_missing` error, show a banner: "Project folder is missing. Close this project or restore the folder."
- Offer a "Close project" button that returns to no-project Home state

**Code Location**: `src/quantumvitas/daemon/server.py::_require_path()` and error handling in `handle_line()`

### 25.5 Home Mode State Management

The Home view now has two modes managed at the App level:
- `welcome` - Shows welcome card with action buttons (or project dashboard if loaded)
- `demo-gallery` - Shows the demo gallery inline

**HomeMode** is lifted from `ProjectSummaryPanel` to `App.tsx` so the sidebar can trigger demo gallery mode:

```tsx
// App.tsx
const [homeMode, setHomeMode] = useState<HomeMode>('welcome');

const handleOpenDemoGallery = useCallback(() => {
  setHomeMode('demo-gallery');
  setCurrentView('home');
}, []);
```

### 25.6 E2E Test Compatibility

The sidebar changes maintain backward compatibility with existing E2E tests:
- Same `data-testid` values (`qv-btn-open-project`, `qv-btn-create-new-project`, `qv-btn-demo-gallery`)
- Buttons now exist in both sidebar and welcome screen
- Demo Gallery flow unchanged: click button → gallery view → create demo

---

## 26. CLI Workflow Detection and Rename Fixes (2025-12-XX)

### 26.1 Overview

This section documents critical fixes to CLI workflow detection and rename operations that ensure commands work correctly when run from inside workflow directories, especially after renames.

### 26.2 Fix: `qv init step` Workflow Auto-Detection

**Problem**: The `qv init step scf` command from inside a workflow directory was not reliably detecting the enclosing workflow and inheriting its structure.

**Root Causes**:
1. Used `_detect_enclosing_workflow()` instead of `PathContext` from `core/context.py`
2. Structure was read from `workflow_data.get("workflow", {}).get("structure")` instead of top-level `workflow_data.get("structure")` (new format)
3. No clear error message when run from project root without `--workflow`

**Solution** (`src/quantumvitas/cli/main.py`, lines ~867-930):

1. **Use PathContext for workflow detection**:
   ```python
   # Try to detect enclosing workflow from cwd using PathContext
   try:
       ctx = find_path_context_from_pwd()
       if ctx.is_inside_workflow():
           workflow_selector = ctx.workflow_selector
           if workflow_selector:
               config = load_project_config(project_root)
               workflow_entry = find_workflow_entry(config, workflow_selector, project_root)
   except ContextNotFoundError:
       pass
   ```

2. **Fix structure reading**:
   ```python
   # Structure is at top level in workflow.yaml (new format), or under workflow key (legacy)
   workflow_structure = workflow_data.get("structure") or workflow_data.get("workflow", {}).get("structure")
   ```

3. **Clear error at project root**:
   ```python
   if not workflow_entry and project_root:
       try:
           ctx = find_path_context_from_pwd()
           if ctx.project_root == Path.cwd().resolve() and not ctx.is_inside_workflow():
               raise typer.BadParameter(
                   "You are at project root. Please specify --workflow <workflow> or run from inside a workflow directory."
               )
       except ContextNotFoundError:
           pass
   ```

**Behavior**:
- ✅ From inside workflow directory: Auto-detects workflow and inherits structure
- ✅ From project root without `--workflow`: Fails with clear error message
- ✅ Step gets correct `parent_workflow_id` and structure from workflow

**Test**: `tests/cli/test_graphene_workflow_setup.py` - Verifies the exact sequence from manual instructions.

---

## 27. ID-Only Cross-Resource References (2025-12-XX)

### 27.1 Overview

This section documents the refactoring to use **ID-only cross-references** between resources, eliminating duplication and out-of-sync problems (e.g., workflow renamed but step still stores stale workflow slug/name).

### 27.2 Current Cross-Resource References (Before Refactor)

**Workflow → Structure**:
- **File**: `workflow.yaml` (via `WorkflowModel`)
- **Field**: `structure: Optional[str]` (selector: name/slug/path)
- **Current**: Selector-based (e.g., `structure: "si"` or `structure: "C"`)
- **Location**: `src/quantumvitas/core/models.py` line 75

**Step → Workflow**:
- **File**: `*.step.yaml` (via `StructureStepSpec`)
- **Field**: `parent_workflow_id: Optional[str]`
- **Current**: ✅ Already ID-based (ULID)
- **Location**: `src/quantumvitas/workflow/structure_steps.py` line 47

**Step → Structure**:
- **File**: `*.step.yaml` (via `StructureStepSpec`)
- **Field**: `structure: str`
- **Current**: Selector-based (e.g., `structure: "si"`)
- **Location**: `src/quantumvitas/workflow/structure_steps.py` line 41

**Snapshots**:
- **File**: `resources/demo_projects/*.yml` and `ProjectSnapshot`
- **Fields**: Workflows have `structure: <selector>`, steps have `structure: <selector>` and `parent_workflow_id: <id>`
- **Current**: Mixed (workflow ID-based, structure selector-based)
- **Location**: `src/quantumvitas/project/snapshot.py` line 378

### 27.3 New Reference Contract

**Rule**: Every resource file keeps its own `meta` block (id, name, slug, path, kind). Any reference to another resource must store **only its ULID (id)**, not name/slug/path.

**Users still select resources by name/slug/path** in CLI/GUI. All resolution of references is internal: `selector → id → resource`.

**Workflow YAML**:
```yaml
meta:
  id: 01JXYZ123ABC456DEF789GHI
  name: si-dos
  slug: si-dos
  path: workflows/si-dos
  kind: workflow
structure_id: 01JABC123DEF456GHI789JKL  # Canonical reference (ULID)
structure_name: "Si"                    # Optional, cosmetic for UI only
mode: normal
working_dir: raw
```

**Step YAML**:
```yaml
meta:
  id: 01KB8FEQWVYJAB16NMRVZ7JYEG
  name: scf
  slug: scf
  path: scf.step.yaml
  kind: step
parent_workflow_id: 01JXYZ123ABC456DEF789GHI  # Canonical link to workflow (ULID)
structure_id: 01JABC123DEF456GHI789JKL          # Canonical link to structure (ULID)
step_type: scf
parameters: {...}
```

**Backwards Compatibility**:
- Loaders accept older fields (`structure`, `parent_workflow_slug`, etc.) as fallback
- Resolve them immediately to the proper resource and fill in `*_id` fields in memory
- When saving, write only `*_id` fields (and optional `*_name` for display)

### 27.4 Implementation Details

**Workflow → Structure**:
- `WorkflowModel` has `structure_id: Optional[str]` and `structure_name: Optional[str] = None`
- On load: If `structure_id` present, use it. Else, if `structure` (selector) present, resolve via `resolve_structure()` and fill `structure_id`
- On save: Write only `structure_id` (and optional `structure_name` for UI)

**Step → Structure**:
- `StructureStepSpec` has `structure_id: Optional[str]` and `structure: str` (legacy)
- On load: If `structure_id` present, use it. Else, resolve `structure` selector and fill `structure_id`
- On save: Write only `structure_id` (keep `structure` for backwards compat if needed)

**Step → Workflow**:
- Already uses `parent_workflow_id: Optional[str]` ✅
- No changes needed

**Resolution Flow**:
1. User provides selector (name/slug/path) via CLI/GUI
2. `QVService` resolves selector → resource via `resolve_structure()` / `resolve_workflow()`
3. Extract `resource.meta.id` and store in `*_id` field
4. When loading, use `*_id` to resolve back to resource via registry lookup

### 27.5 Concrete Examples

**New Workflow YAML Format**:
```yaml
meta:
  id: 01JXYZ123ABC456DEF789GHI
  name: si-dos
  slug: si-dos
  path: workflows/si-dos
  kind: workflow
structure_id: 01JABC123DEF456GHI789JKL  # Canonical reference (ULID)
structure_name: "Si"                    # Optional, cosmetic for UI only
structure: si                            # Legacy selector (backwards compat, not authoritative)
mode: normal
working_dir: raw
steps: [...]
```

**New Step YAML Format**:
```yaml
meta:
  id: 01KB8FEQWVYJAB16NMRVZ7JYEG
  name: scf
  slug: scf
  path: scf.step.yaml
  kind: step
parent_workflow_id: 01JXYZ123ABC456DEF789GHI  # Canonical link to workflow (ULID)
structure_id: 01JABC123DEF456GHI789JKL          # Canonical link to structure (ULID)
structure: si                                 # Legacy selector (backwards compat)
step_type: scf
parameters: {...}
```

**Legacy Format (Still Supported)**:
```yaml
# workflow.yaml (legacy)
meta:
  id: 01JXYZ123ABC456DEF789GHI
  name: si-dos
  slug: si-dos
  path: workflows/si-dos
  kind: workflow
structure: si  # Selector only (no structure_id)
mode: normal
working_dir: raw
```

When loading a legacy workflow with `load_workflow(path, project_root)`, the structure selector is automatically resolved to `structure_id` if the structure exists in the project.

### 27.6 How CLI/GUI Still Use Selectors

**User-facing operations** (CLI/GUI) continue to use selectors (name/slug/path):
- `qv init workflow --structure si` (uses selector)
- `qv init step --structure C` (uses selector)
- GUI workflow creation: user selects structure by name

**Internal resolution flow**:
1. User provides selector → `QVService` receives selector
2. `QVService` resolves selector → `resolve_structure(project_root, selector)` → `ResolvedResource`
3. Extract `resource.meta.id` → store in `structure_id` field
4. When loading, use `structure_id` to resolve back to resource via registry lookup

**Example: Creating a workflow**:
```python
# User: qv init workflow --structure si
structure_selector = "si"  # From CLI

# QVService resolves selector to structure
resolved = resolve_structure(project_root, structure_selector)
structure_id = resolved.meta.id  # e.g., "01JABC123DEF456GHI789JKL"

# Create workflow with structure_id
workflow_model = WorkflowModel(
    meta=workflow_meta,
    structure_id=structure_id,      # Canonical reference
    structure_name=resolved.meta.name,  # Display name
    structure=structure_selector,    # Legacy field for backwards compat
)
```

### 27.7 Rename Behavior

**Before (selector-based)**:
- Rename structure "Si" → "Silicon"
- All workflows with `structure: "si"` break (selector no longer matches)
- Must manually update all workflow.yaml files

**After (ID-based)**:
- Rename structure "Si" → "Silicon"
- Structure's `meta.id` remains unchanged (ULID is immutable)
- All workflows with `structure_id: "01JABC..."` still work
- Only `structure_name` field needs update (cosmetic, optional)
- No need to touch workflow.yaml or step.yaml files

**Example**:
```python
# Structure renamed from "Si" to "Silicon"
# Old workflow.yaml:
structure_id: 01JABC123DEF456GHI789JKL  # Still valid!
structure_name: "Si"  # Outdated, but not critical

# After reloading workflow (auto-updates structure_name):
structure_id: 01JABC123DEF456GHI789JKL  # Still valid!
structure_name: "Silicon"  # Updated from registry
```

### 27.8 Benefits

- **No duplication**: Structure name/slug/path only stored in structure's own meta and project registry
- **Rename-safe**: Renaming a structure only updates its own meta and registry; all references via `structure_id` remain valid
- **Single source of truth**: Project registry (`project.qv.yml`) is authoritative for resource metadata
- **Backwards compatible**: Legacy YAML files with selector-based references still load correctly
- **Resolution is explicit**: When loading, structure selector is resolved to `structure_id` if `project_root` is provided

### 27.9 Implementation Files

**Core Models**:
- `src/quantumvitas/core/models.py`: `WorkflowModel` with `structure_id`/`structure_name` fields
- `src/quantumvitas/workflow/structure_steps.py`: `StructureStepSpec` with `structure_id` field

**Resolution**:
- `src/quantumvitas/core/resolution.py`: `resolve_structure()` converts selector → `ResolvedResource` with `meta.id`
- `src/quantumvitas/core/models.py`: `load_workflow()` auto-resolves legacy `structure` selector to `structure_id`

**Service Layer**:
- `src/quantumvitas/api.py`: `QVService.init_workflow()`, `QVService.init_step()`, etc. resolve selectors to IDs

**Snapshots**:
- `src/quantumvitas/project/snapshot.py`: Exports `structure_id`, materializes with ID mapping

**Tests**:
- `tests/unit/test_id_based_references.py`: Comprehensive tests for ID-based references and backwards compatibility

---

## 28. Resource Identity and Cross-References (2025-12-XX)

### 28.1 Hard Invariants

**Every resource file is self-describing:**
- `project.qv.yml` (project)
- `workflows/<slug>/workflow.yaml` (workflow)
- `workflows/<slug>/steps/*.step.yaml` (step)
- `structures/*.json` (structure)

Each has a `meta` block with:
```yaml
meta:
  id: <ULID>          # Single source of truth for id
  name: <str>         # Only appears here for this resource
  slug: <str>         # Only appears here for this resource
  path: <relative>    # Path from project root
  kind: project|workflow|structure|step
```

**Cross-resource references store ONLY the id, never name/slug/path:**

**workflow.yaml:**
```yaml
meta: {... kind: workflow}
structure_id: 01S...           # Structure reference (ULID only)
steps:
  - step_id: 01T...            # Step reference (ULID only)
  - step_id: 01U...
```

***.step.yaml:**
```yaml
meta: {... kind: step}
parent_workflow_id: 01H...     # Workflow reference (ULID only)
structure_id: 01S...           # Structure reference (ULID only)
```

**project.qv.yml:**
```yaml
meta: {... kind: project}
structures:
  - id: 01S...                 # Only ID, no name/slug/path
workflows:
  - id: 01H...                 # Only ID, no name/slug/path
```

**No other resource's name/slug/path is allowed anywhere.** Names/slugs/paths of a resource appear only in that resource's own file.

### 28.2 Registry (project.qv.yml)

The registry stores only:
- The project's own meta (with name/slug/path, because it's "self")
- Top-level id lists / id mappings (project → structure ids, workflow ids, etc.)
- Project-level settings (origin, analysis options, etc.)

It must **not** contain copies of workflow/structure/step name/slug/path.

**Allowed:**
```yaml
workflows:
  - id: 01H...
structures:
  - id: 01S...
workflow_structure:
  01H...: 01S...
```

**Not allowed:**
```yaml
workflows:
  - id: 01H...
    name: graphene bands      # ❌ Not allowed anymore
    slug: graphene-bands      # ❌
    path: workflows/...       # ❌
```

### 28.3 ResourceIndex as the Canonical Selector Resolver

### 28.1 Overview

The `ResourceIndex` is the authoritative source for selector → ID resolution. It is built by scanning resource files (workflow.yaml, *.step.yaml, *.json) and reading their meta blocks, not from project.qv.yml entries.

### 28.2 ResourceIndex Structure

```python
@dataclass
class ResourceIndex:
    by_id: Dict[str, ResourceMeta]      # id -> full meta
    by_slug: Dict[str, str]              # slug -> id
    by_path: Dict[Path, str]            # absolute path -> id
    by_name: Dict[str, List[str]]        # lower(name) -> [id,...]
```

### 28.3 Building the Index

`build_resource_index(project_root: Path) -> ResourceIndex`:
- Scans `workflows/**/workflow.yaml` → reads meta, indexes by id/slug/path/name
- Scans `workflows/**/steps/*.step.yaml` → reads meta, indexes by id/slug/path/name
- Scans `structures/*.json` → reads `__qv_meta__` or `meta`, indexes by id/slug/path/name

**Key principle**: Resource files are self-describing. Their meta blocks are the source of truth for name/slug/path. project.qv.yml only stores IDs for relationships.

### 28.4 Resolution Flow

**New flow (preferred)**:
1. Build `ResourceIndex` from filesystem
2. Use `index.resolve_id(selector, project_root)` to get ID
3. Use ID + registry to find relationships
4. Use ID + index to get display name/slug/path when needed

**Legacy flow (backwards compat)**:
- Falls back to reading from project.qv.yml entries if ResourceIndex doesn't find the resource
- This ensures old projects still work

### 28.5 Usage in Resolution Functions

`resolve_structure()` and `resolve_workflow()` now:
- Accept optional `index: ResourceIndex` parameter
- Build index if not provided
- Try ResourceIndex resolution first
- Fall back to config-based resolution for backwards compatibility

**Example**:
```python
# Preferred: use ResourceIndex
index = build_resource_index(project_root)
resolved = resolve_structure(project_root, "si", index=index)

# Backwards compat: auto-builds index
resolved = resolve_structure(project_root, "si")
```

### 28.6 Benefits

- **Single source of truth**: Resource files' meta blocks are authoritative
- **No duplication**: project.qv.yml doesn't duplicate name/slug/path
- **Rename-safe**: Renaming a resource only updates its own file, index rebuilds automatically
- **Backwards compatible**: Falls back to config-based resolution for old projects

---

### 26.3 Fix: Workflow Rename Bug

**Problem**: `qv configure workflow --name "graph"` failed with `FileNotFoundError` after renaming because the code tried to read/write `workflow.yaml` at the old location after the directory was moved.

**Root Cause**: `apply_workflow_rename()` can move the workflow directory if the slug changes (e.g., "graphene bands" → "graph" changes slug from "graphene-bands" to "graph"), but the CLI code captured `workflow_dir` and `workflow_yaml` paths before the rename.

**Solution** (`src/quantumvitas/cli/main.py`, lines ~2179-2197):

```python
# Handle name change (rename)
if name:
    # Store old path to detect if directory was moved
    old_workflow_dir = workflow_dir
    old_workflow_yaml = workflow_yaml
    
    apply_workflow_rename(...)
    save_project_config(project_root, config)
    
    # Re-resolve workflow directory in case it was moved
    workflow_dir = workflow_directory(project_root, workflow_entry)
    workflow_yaml = workflow_dir / "workflow.yaml"
    
    # Re-read workflow.yaml if directory was moved
    if workflow_dir != old_workflow_dir:
        if not workflow_yaml.exists():
            raise typer.BadParameter(f"workflow.yaml not found at {workflow_yaml} after rename")
        workflow_data = yaml.safe_load(workflow_yaml.read_text()) or {}
    
    # Update meta in workflow.yaml
    if "meta" in workflow_data:
        workflow_data["meta"]["name"] = name
        new_slug = (workflow_entry.get("meta") or {}).get("slug") or slugify(name)
        workflow_data["meta"]["slug"] = new_slug
```

**Behavior**:
- ✅ Rename works whether slug changes or stays the same
- ✅ `workflow.yaml` is updated at the correct location (new directory if moved)
- ✅ Project config and workflow.yaml stay in sync

### 26.4 Fix: `qv analyze band` Workflow Detection

**Problem**: `qv analyze band` from inside a workflow directory failed with "Workflow not found: graphene-bands" because `PathContext` extracted the selector from `workflow.yaml`, which might be stale after a rename.

**Root Cause**: `PathContext.workflow_selector` reads from `workflow.yaml` meta, but after a rename, the selector might not match what's in `project.qv.yml` (the source of truth for `resolve_workflow`).

**Solution** (`src/quantumvitas/cli/main.py`, lines ~3002-3024):

```python
# Only auto-detect workflow if no input file provided
if input_file is None and ctx.is_inside_workflow():
    # Use find_enclosing_workflow to get the actual entry from project config
    # This is more reliable than using the selector from workflow.yaml
    # (which might be stale after a rename)
    config = load_project_config(project_root)
    wf_entry = find_enclosing_workflow(project_root, config)
    if wf_entry:
        # Use the slug or name from the entry (which is authoritative)
        workflow_selector = (wf_entry.get("meta") or {}).get("slug") or wf_entry.get("name")
        if workflow_selector:
            typer.echo(f"Detected workflow: {workflow_selector}")
```

**Why This Works**:
- `find_enclosing_workflow()` matches the current directory path against entries in `project.qv.yml`
- Uses directory path, not selector from `workflow.yaml`, so it works after renames
- Selector comes from the authoritative entry in `project.qv.yml`

**Behavior**:
- ✅ Works from inside workflow directory, even after rename
- ✅ Uses authoritative selector from project config, not stale workflow.yaml

### 26.5 Key Principles

1. **Use `find_enclosing_workflow()` for auto-detection**: More reliable than selectors from `workflow.yaml` because it uses directory paths
2. **Re-resolve paths after rename operations**: Always re-resolve workflow directory and re-read files after `apply_workflow_rename()`
3. **Read structure from top-level first**: Check `workflow_data.get("structure")` before legacy `workflow_data.get("workflow", {}).get("structure")`
4. **Clear error messages**: When at project root without `--workflow`, provide explicit guidance

### 26.6 Files Modified

| File | Changes |
|------|---------|
| `src/quantumvitas/cli/main.py` | Fixed `init_step_command` to use `PathContext`, fixed structure reading, added clear error at project root |
| `src/quantumvitas/cli/main.py` | Fixed `configure_workflow_command` to re-resolve paths after rename |
| `src/quantumvitas/cli/main.py` | Fixed `analyze_band_command` to use `find_enclosing_workflow` instead of `PathContext.workflow_selector` |
| `tests/cli/test_graphene_workflow_setup.py` | New test verifying exact CLI sequence from manual instructions |

### 26.7 Test Coverage

- ✅ `test_graphene_workflow_setup.py::test_graphene_workflow_setup` - Full sequence including rename
- ✅ `test_graphene_workflow_setup.py::test_init_step_fails_at_project_root_without_workflow` - Error handling
- ✅ All existing CLI tests pass (20 tests)

---

*Last updated: 2025-12-XX*
*Based on commit history through v2-python branch*
