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

**workflow.yaml** (new format with meta section):
```yaml
meta:
  id: 01JXYZ123ABC456DEF789GHI  # ULID
  name: si-dos
  slug: si-dos
  path: workflows/si-dos
  kind: workflow
mode: normal
structure: si               # Structure reference (slug/name)
working_dir: raw
steps:
- id: scf
  type: scf
  step_file: steps/scf.step.yaml
- id: nscf
  type: nscf
  step_file: steps/nscf.step.yaml
```

**step.yaml** (StructureStepSpec):
```yaml
meta:
  id: 01KB8FEQWVYJAB16NMRVZ7JYEG  # ULID
  name: scf
  slug: scf
  path: scf.step.yaml
  kind: step
parent_workflow_id: 01KB8ABCD...   # Links to parent workflow (optional)
structure: si                       # Structure reference
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
3. **Shell config files** - Parse `~/.zshrc`, `~/.bashrc` for exports
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
│   ├── project [--path PATH] [--name NAME] [--template TEMPLATE]
│   ├── workflow <name> [--structure STRUCT] [--parent WF] [--template TEMPLATE]
│   └── step <type> [--structure STRUCT] [--workflow WF] [--template TEMPLATE] [overrides...]
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
├── analyze <energy|band|dos> <output-file>
└── params <module> [--section SECTION]
```

### 4.2 Resource Resolution

Resources can be identified by:
- **name/slug**: Case-insensitive match (e.g., `si_dos`, `"Si DOS"`)
- **path**: Relative or absolute filesystem path

**Auto-detection from current directory**:
- `find_project_root()`: Walks up to find `project.qv.yml`
- `find_enclosing_workflow()`: Detects if pwd is inside a workflow
- Used by `qv run workflow`, `qv init step`, `qv delete workflow`, etc.

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

### 4.4 Separation of Concerns

The CLI (`main.py`) was refactored to extract core logic:

- **`core/project_utils.py`**: Project/config helpers that raise `ValueError`, `ResourceNotFoundError`
- **`cli/main.py`**: Thin wrapper that converts to `typer.BadParameter`

This allows core functions to be used outside the CLI (notebooks, scripts).

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
3. Shell config files (`~/.zshrc`, `~/.bashrc` for PATH exports)
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
- `workflow.yaml` - Workflow definition (includes `structure` reference)
- `*.step.yaml` - Step specifications (includes `parent_workflow_id`)

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
- Fermi energy: 1e-2 Ry

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

## 11. Future Considerations

1. **GUI**: PySide6 GUI is planned but not implemented
2. **Other engines**: LAMMPS, Wannier90 support is planned
3. **Online databases**: Integration with Materials Project, AFLOW
4. **Parallel execution**: MPI support exists but is basic

---

## 12. Refactoring History

### 2025-11-30 Session 2

Implemented from `temporary_ai_prompts` (lines 372-379):

| Item | Implementation |
|------|---------------|
| **Post-processing step support** | DOS/bands/projwfc steps now generate correct input format (just &DOS, &BANDS, etc. namelists) instead of pw.x format |
| **`--template` for `qv init project`** | Copy from predefined template (e.g., `qv init project --template project1`) |
| **`--template` for `qv init workflow`** | Copy workflow template with steps, auto-copies related structures (e.g., `qv init workflow my-dos --template si-dos`) |
| **`--template` for `qv init step`** | Copy step template (e.g., `qv init step scf --template scf`) |
| **`qv import-structure` accepts .json** | Can now import QV-format JSON files with embedded metadata |
| **`qv show-command` simplified** | No longer includes `--structure <structure-id>` placeholder; shows helpful explanation instead |
| **Structure inheritance in `qv init step`** | When using `--workflow`, inherits structure from that workflow (not just from enclosing directory) |
| **ULID consistency in templates** | When copying templates, workflow ULIDs in project.qv.yml match step parent_workflow_id |
| **QE registry isolation** | Added autouse fixture to reset QE home registry between tests |

**New file**: `src/quantumvitas/core/templates.py` - Template management utilities

**New test file**: `tests/cli/test_template_workflow.py` - Tests for template copying and ULID consistency

**Templates directory**: `/templates/` at project root contains:
```
templates/
├── project/
│   └── project1/       # Complete project with workflow and structures
├── workflow/
│   └── si-dos/         # Si DOS workflow with scf, nscf, dos steps
├── step/
│   └── steps/          # Individual step templates (scf, nscf, dos)
└── structure/
    └── si.json         # Si bulk structure
```

**Key implementation details**:
- When creating workflow from template, CLI generates the workflow ULID first and passes it to `copy_workflow_template` so steps get the correct `parent_workflow_id`
- When copying project template, old workflow ULIDs from project.qv.yml are mapped to new ULIDs for consistency

### 2025-11-30 Session 1

Implemented from `temporary_ai_prompts` (lines 344-365):

| Item | Implementation |
|------|---------------|
| `qv configure workflow --reorder` | Reorders steps in workflow.yaml |
| `qv configure workflow --structure` | Changes structure, updates all step YAMLs |
| `parent_workflow_id` in step.yaml | Links step to parent workflow |
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

### 14.8 Files Modified in This Session

| File | Purpose |
|------|---------|
| `src/quantumvitas/analysis/energy.py` | Fix `fermi_energy_ev` key |
| `src/quantumvitas/analysis/dos.py` | Use `fermi_energy_ev` key |
| `src/quantumvitas/analysis/bands.py` | Use `fermi_energy_ev` key |
| `src/quantumvitas/workflow/verification.py` | Use `fermi_energy_ev` key |
| `src/quantumvitas/core/engines/qe_pseudopotentials.py` | Pseudopotential priority and copying |
| `src/quantumvitas/workflow/input_runner.py` | Simplified input file naming |
| `src/quantumvitas/cli/main.py` | Module detection, configure --name, rename deprecation, workflow meta |
| `templates/workflow/si-dos/workflow.yaml` | Updated to new meta format |
| `docs/CLI_API_REFERENCE.md` | Comprehensive update |

---

*Last updated: 2025-12-03*
*Based on commit history through v2-python branch*
