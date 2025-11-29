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
├── cli/                 # Typer CLI implementation (main.py is ~2200 lines)
├── core/
│   ├── engines/         # QE engine, installation detection, pseudopotentials
│   ├── resources.py     # ResourceMeta model (ULID, slug, name, path)
│   └── project_utils.py # Extracted helpers for project/config manipulation
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
    path: Path    # Filesystem path
    kind: str     # "project" | "workflow" | "structure" | "step"
```

**Key function**: `slugify(name)` converts names to slugs (`"Si DOS workflow"` → `"si-dos-workflow"`).

### 2.2 Project Structure

A QuantumVITAS project is a directory containing:

```
project/
├── project.qv.yml       # Project metadata and registry
├── structures/          # Structure JSON files (pymatgen format)
├── workflows/
│   └── <workflow-slug>/
│       ├── workflow.yaml
│       ├── steps/       # Step YAML specifications
│       ├── raw/         # Working directory for QE execution
│       └── reference/   # Reference outputs for verification
└── .trash/              # Soft-deleted resources
```

### 2.3 QE Input Model

QE inputs are represented as structured objects:

```python
QEInput
├── namelists: List[QENamelist]   # &CONTROL, &SYSTEM, &ELECTRONS, etc.
├── cards: List[QECard]           # ATOMIC_SPECIES, ATOMIC_POSITIONS, K_POINTS, etc.
└── module: QEModule              # PW, PH, DOS, BANDS, etc.
```

**Roundtrip parsing**: `QEInputParser.parse_file()` → modify → `QEInputGenerator.write_file()`

### 2.4 Workflow Execution

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

### 4.1 Command Structure

The CLI uses Typer with sub-apps:

```
qv
├── init project|workflow|step
├── import-structure
├── list
├── rename structure|workflow|step|project
├── delete structure|workflow|step|project|trash
├── configure step
├── run step|structure|workflow
├── detect-qe
├── show-command / get-command
├── analyze energy|band|dos
└── params <module>
```

### 4.2 Parameter Overrides

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

### 4.3 Separation of Concerns

The CLI (`main.py`) was refactored to extract core logic:

- **`core/project_utils.py`**: Project/config helpers that raise `ValueError`
- **`cli/main.py`**: Thin wrapper that converts to `typer.BadParameter`

This allows core functions to be used outside the CLI (notebooks, scripts).

---

## 5. Testing

### 5.1 Test Categories

| Marker | Description | Requires QE |
|--------|-------------|-------------|
| `unit` | Parser, model tests | No |
| `qe_core` | Engine integration tests | Yes |
| `qe_cli` | CLI integration tests | Yes |

### 5.2 CI Test Data

Small bundled test cases in `tests/integration/ci_test_data/`:
- `pw_scf/` - Basic SCF tests
- `4_Si_DOS/` - Si DOS workflow
- `7_Si_bandStructure/` - Si bands workflow

### 5.3 Common Test Issues

1. **Slugification mismatch**: CLI creates dirs with `slugify(name)`, tests must match:
   ```python
   workflow_dir = project_root / "workflows" / slugify(workflow_name)
   ```

2. **CliRunner `mix_stderr`**: Removed in newer Click versions:
   ```python
   # Bad: runner = CliRunner(mix_stderr=False)
   # Good: runner = CliRunner()
   ```

3. **QE_HOME pollution**: Use `reset_qe_home()` fixture (see Section 3.3)

---

## 6. Key Files Reference

| File | Purpose | Lines |
|------|---------|-------|
| `cli/main.py` | All CLI commands | ~2200 |
| `core/engines/qe_installation.py` | QE detection logic | ~470 |
| `core/engines/qe.py` | QE engine implementation | ~550 |
| `core/engines/qe_workflow.py` | Step/workflow execution | ~320 |
| `io/parser/qe_parser.py` | QE input parsing | ~420 |
| `io/model.py` | QE data structures | ~230 |
| `workflow/runner.py` | Workflow orchestration | ~95 |
| `workflow/verification.py` | Result verification | ~110 |
| `project/model.py` | Project/Workflow models | ~260 |

---

## 7. Conventions

### 7.1 Error Handling

- **CLI layer**: Use `typer.BadParameter`, `typer.Exit(1)`
- **Core layer**: Raise `ValueError`, `FileNotFoundError`, custom exceptions

### 7.2 Path Handling

- Always use `Path` objects, not strings
- Use `.expanduser()` for `~` expansion
- Use `.resolve()` for symlink resolution (wrap in try/except for broken links)

### 7.3 YAML Files

- `project.qv.yml` - Project metadata
- `workflow.yaml` - Workflow definition
- `*.step.yaml` - Step specifications

### 7.4 Structure Storage

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

## 8. Lessons Learned / Caveats

### 8.1 Environment Variables

❌ **Don't** store state in `os.environ` - it's mutable by external processes.
✅ **Do** use internal registries with explicit APIs.

### 8.2 Test Isolation

Tests that modify global state (QE_HOME, project configs) must restore it:

```python
@pytest.fixture(autouse=True)
def cleanup():
    original_state = save_state()
    yield
    restore_state(original_state)
```

### 8.3 CLI Refactoring

Large CLI files become unmaintainable. Extract logic to core modules:
- Keep CLI as thin wrapper
- Core functions raise standard exceptions
- CLI converts to Typer-friendly errors

### 8.4 QE Input Quirks

- QE uses Fortran-style booleans: `.true.`, `.false.`, `t`, `f`
- Card options are case-sensitive: `ATOMIC_POSITIONS angstrom`
- Some namelists are optional (e.g., `&IONS` only for relaxation)
- K_POINTS can be `automatic`, `gamma`, `crystal`, `tpiba`, etc.

### 8.5 Workflow Verification

The verification logic checks:
1. "JOB DONE" in output (basic success)
2. Energy comparison against reference (strict mode)
3. Fermi energy comparison (for NSCF/DOS/bands)

Tolerances:
- Total energy: 1e-5 Ry
- Fermi energy: 1e-2 Ry

---

## 9. Quick Start for AI Assistants

### Reading Order

1. `project/model.py` - Understand Project/Workflow/Structure models
2. `core/resources.py` - ResourceMeta pattern
3. `io/model.py` - QE input structure
4. `core/engines/qe_installation.py` - QE detection (especially module-level registry)
5. `cli/main.py` - CLI commands (large file, use semantic search)

### Common Tasks

| Task | Key Files |
|------|-----------|
| Add CLI command | `cli/main.py` |
| Modify QE detection | `core/engines/qe_installation.py` |
| Add QE module support | `io/parser/qe_parser.py`, `core/engines/qe.py` |
| Change workflow execution | `workflow/runner.py`, `core/engines/qe_workflow.py` |
| Modify verification | `workflow/verification.py` |

### Running Tests

```bash
# Install in editable mode
pip install -e '.[dev]'

# Run all tests
python -m pytest tests/ -v --tb=short

# Run specific categories
python -m pytest -m unit          # No QE needed
python -m pytest -m qe_core       # Needs QE
python -m pytest tests/cli/       # CLI tests only
```

---

## 10. Future Considerations

1. **GUI**: PySide6 GUI is planned but not implemented
2. **Other engines**: LAMMPS, Wannier90 support is planned
3. **Online databases**: Integration with Materials Project, AFLOW
4. **Parallel execution**: MPI support exists but is basic

---

*Last updated: 2025-11-29*
*Based on commit history through v2-python branch*

