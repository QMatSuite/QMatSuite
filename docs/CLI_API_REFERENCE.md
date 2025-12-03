# CLI & API Quick Reference

This page lists every `qv` CLI command plus the Python APIs that are meant to
be used directly by end users or automation scripts. Each entry keeps the
description short and includes a minimal example you can run or adapt.

## CLI commands

| Command | What it does | Quick example |
| --- | --- | --- |
| `qv init project [--path PATH] [--name NAME] [--template TEMPLATE]` | Create a project skeleton. Passing `--path` selects destination; `--name` controls metadata. Use `--template project1` to copy from predefined template with example structures and workflows. | `qv init project --template project1` |
| `qv init workflow <name> --structure STRUCT [--project PATH] [--parent wfA] [--template TEMPLATE]` | Scaffold a workflow folder with `workflow.yaml`, `steps/`, and metadata. Use `--template si-dos` to copy from template (also copies related structures). When using `--template`, `--structure` is optional. | `qv init workflow my-dos --template si-dos` |
| `qv init step <type> [--structure STRUCT] [--workflow ID] [--project PATH] [--template TEMPLATE] [overrides…]` | Generate a step `.yaml` in the enclosing workflow. Step type is required (scf, nscf, relax, dos, etc.). Structure is optional if inside a workflow. Use `--template scf` to copy from template. | `qv init step nscf --template nscf` or `qv init step scf` (inside workflow) |
| `qv import-structure <file> [--name NAME] [--project PATH] [--output-format json]` | Parse a structure with pymatgen, auto-generate name/slug if omitted, and register it. Supports .cif, POSCAR, QE .in, and .json (including QV format). | `qv import-structure si.cif --project ~/projects/si_demo --name "Si prim cell"` |
| `qv list [--project PATH] [--verbose]` | Print the project tree down to each workflow step (IDs shown only with `--verbose`). | `qv list --project ~/projects/si_demo -v` |
| `qv detect-qe` | Print the QE installation detected via the engine registry. | `qv detect-qe` |
| `qv show-command <input.in>` | Parse a QE input and print example `qv init step` / `qv configure step` commands. Auto-detects module type (pw.x, bands.x, dos.x, etc.). | `qv show-command ci_test_data/pw_single_tests/scf.in` |
| `qv get-command <input.in>` | Alias for `qv show-command`. | `qv get-command inputs/si_scf.in` |
| `qv analyze <energy|band|dos> <output-file>` | Invoke the lightweight analysis hooks on a QE output. | `qv analyze energy temp/test_outputs/si_scf.out` |
| `qv params <module> [--section SECTION]` | Inspect parameters scraped from the QE docs (`qe_module_parameters.json`). | `qv params pw --section SYSTEM` |

### Configure Commands (Recommended)

| Command | What it does | Quick example |
| --- | --- | --- |
| `qv configure step <step-id|path> [--workflow ID] [--name NAME] [--remove] [overrides…]` | Edit step parameters. Use `--name` to rename. Use `--remove` to delete parameters. Step auto-detected from pwd if inside workflow. | `qv configure step nscf --name="NSCF high k" --SYSTEM.ecutwfc=70` |
| `qv configure workflow [<workflow-id|path>] [--name NAME] [--structure STRUCT] [--reorder STEP1,STEP2,...]` | Modify workflow settings. Use `--name` to rename. Use `--structure` to change structure (updates all steps). Use `--reorder` to change step order. | `qv configure workflow --name="Si DOS v2" --reorder scf,nscf,dos` |
| `qv configure structure <identifier> [--project PATH] [--name NAME]` | Rename a structure using `--name`. For complex modifications, re-import. | `qv configure structure si --name "Silicon bulk"` |

### Rename Commands (Deprecated)

> **Warning:** The `qv rename` commands are deprecated. Use `qv configure --name` instead.

| Command | What it does | Quick example |
| --- | --- | --- |
| `qv rename structure <selector> [--name NAME] [--slug SLUG] [--path PATH]` | **Deprecated.** Use `qv configure structure <selector> --name <new_name>` instead. | `qv configure structure si --name "Si DOS"` |
| `qv rename workflow <selector> [--name NAME] [--slug SLUG] [--path PATH]` | **Deprecated.** Use `qv configure workflow <selector> --name <new_name>` instead. | `qv configure workflow si_dos --name "Si DOS workflow"` |
| `qv rename step <workflow> <step-id> [--project PATH] [--id NEW_ID]` | **Deprecated.** Use `qv configure step <step-id> --workflow <workflow> --name <new_name>` instead. | `qv configure step nscf --name nscf_relax` |
| `qv rename project [--project PATH] [--name NAME]` | **Deprecated.** Use project-level configuration. | — |

### Delete Commands

| Command | What it does | Quick example |
| --- | --- | --- |
| `qv delete structure <selector> [--project PATH] [--force] [--cascade]` | Move a structure (and optionally referencing workflows) into the project's `trash/` folder. Selector = id/name/slug/path. | `qv delete structure si` |
| `qv delete workflow [<selector>] [--project PATH] [--force] [--cascade]` | Move a workflow directory into `trash/`, optionally cascading dependent workflows. Auto-detects from pwd if not specified. | `qv delete workflow --cascade` |
| `qv delete step <step-id> [--workflow ID] [--project PATH]` | Remove a step entry from a workflow and move its `.step.yaml` to trash. Workflow auto-detected from pwd if inside one. | `qv delete step nscf` |
| `qv delete project [<selector>] [--project PATH]` | Move a project directory into the parent `trash/` folder. Selector = name/slug/path. | `qv delete project si_demo` |
| `qv delete trash [--project PATH] [--path PATH] [--parent]` | Clean a trash directory (project-level by default, or explicit path). | `qv delete trash --project ~/projects/si_demo` |

### Run Commands

| Command | What it does | Quick example |
| --- | --- | --- |
| `qv run step <input.in|step.yaml> [--project PATH] [--workdir PATH] [overrides…]` | Run a standalone QE input file **or** a `.step.yaml`, applying overrides to parameters/cards/species. | `qv run step workflows/si_dos/steps/scf.step.yaml --project . --CARD.K_POINTS.data=[[6,6,6,0,0,0]]` |
| `qv run structure <structure-id|file> [--project PATH] [--type scf] [overrides…]` | Load a stored structure, materialize a QE input, apply overrides, and run it. | `qv run structure si --project ~/projects/si_demo --type scf --k_points=4,4,4,0,0,0` |
| `qv run workflow [<workflow-id|path>] [--project PATH] [--strict] [--verbose]` | Execute a workflow. Auto-detects enclosing workflow from pwd if not specified. | `qv run workflow --strict` |
| `qv run [target] [--project PATH] [--workdir PATH] [--strict]` | Auto-detect the target type (QE input, step YAML, workflow id, structure id) and dispatch to the appropriate subcommand. If no target, runs enclosing workflow. | `qv run --strict` |

> **Selectors:** Resources can be identified by:
> - **id** (ULID): Exact match, case-sensitive (e.g., `01JXYZ...`)
> - **name/slug**: Case-insensitive match (e.g., `si_dos`, `"Si DOS"`)
> - **path**: Relative or absolute filesystem path (e.g., `workflows/si-dos`)
>
> **Auto-detection:** Many commands auto-detect resources from the current directory:
> - **Project**: Walks up from pwd to find `project.qv.yml`
> - **Workflow**: Detects if pwd is inside a workflow directory
> - **Step**: If inside a workflow, step id can be used directly

**Overrides syntax:** Any extra `--name=value` flag is treated as a QE override.
Parameters map into namelists (`--SYSTEM.ecutwfc=60`). Cards can be updated via
`--CARD.K_POINTS.data=[[6,6,6,0,0,0]]` or the shorthand `--k_points=...`; atomic
species rows use `--SPECIES.Si.mass=28.0855` / `--SPECIES.Si.pseudopot=Si.UPF`.
Lists accept JSON (`[ ... ]`) or comma-separated values, and booleans can be
specified with `--tprnfor` / `--tprnfor=false`.

### Detecting QE installations

`qv detect-qe` no longer depends on a project checkout. It auto-detects QE using
this priority order:

| Priority | Source | Description |
|----------|--------|-------------|
| 1 | `QE_HOME` env var | Most explicit; recommended for CI/CD |
| 2 | System PATH | Uses `which pw.x` and infers `QE_HOME` |
| 3 | Shell config files | Parses `~/.zshrc`, `~/.bashrc` for exports |
| 4 | Home directory scan | Searches `$HOME` for `q-e-qe*` folders |

The command prints the resolved `qe_home`, `bin` directory, located executables,
and whether `test-suite/` was found. Use this output to verify CI images or local
developer setups.

**For CI/CD (GitHub Actions, etc.)**, always set the `QE_HOME` environment variable:

```yaml
env:
  QE_HOME: $HOME/src/q-e-qe-7.5
```

## Resource Metadata

All resources (projects, workflows, steps, structures) include a `meta` section with:

| Field | Description |
|-------|-------------|
| `id` | ULID (Universally Unique Lexicographically Sortable Identifier) |
| `name` | Human-readable display name |
| `slug` | URL-safe identifier (derived from name) |
| `path` | Relative path from project root |
| `kind` | Resource type: `project`, `workflow`, `step`, `structure` |

Example `workflow.yaml` with metadata:

```yaml
meta:
  id: 01JXYZ123ABC456DEF789GHI
  name: Si DOS calculation
  slug: si-dos-calculation
  path: workflows/si-dos-calculation
  kind: workflow
mode: normal
structure: si
working_dir: raw
steps:
  - id: scf
    type: scf
    step_file: steps/scf.step.yaml
```

## Pseudopotential Handling

When running QE calculations, QuantumVITAS automatically manages pseudopotentials:

1. **Project-local first**: Checks `project/pseudo/` for required files
2. **Global cache**: Falls back to `quantumvitas_root/pseudo/`
3. **Auto-download**: Downloads missing pseudopotentials from QE servers
4. **Copy to project**: Downloaded files are copied to both locations for project portability

Set `pseudo_dir` in step YAML or use `--pseudo_dir` override to customize.

## Input File Handling

When running `.in` files via `qv run`:

- The final processed input is written to `working_dir/<stem>.in`
- If `keep_original=true` and the input was modified, the original is saved as `<stem>_original.in`
- For YAML-based steps, only the generated input file is saved

## Unit Conventions

| Quantity | Unit | Notes |
|----------|------|-------|
| Total energy | Ry | From QE output (Rydberg) |
| Fermi energy | eV | Parsed from QE output (electronvolts) |
| Band energies | eV | After processing |
| Lattice constants | Bohr (a.u.) | QE default |

In the metrics dictionary returned by analysis functions:
- `total_energy_ry`: Total energy in Rydberg
- `fermi_energy_ev`: Fermi energy in electronvolts

## Python API surface

These calls live under the `quantumvitas` package and are kept stable for user
scripts, notebooks, and automation. Import paths shown are canonical; feel free
to alias locally.

### QVService (Recommended API Layer)

The `QVService` class in `quantumvitas.api` provides the cleanest interface for
programmatic access:

```python
from quantumvitas.api import QVService

# Project operations
project_root = QVService.init_project(Path("./my_project"), name="My Project")
QVService.configure_project(project_root, new_name="Renamed Project")

# Structure operations
struct = QVService.import_structure(project_root, Path("si.cif"), name="Silicon")
QVService.configure_structure(project_root, "si", new_name="Silicon bulk")
structures = QVService.list_structures(project_root)

# Workflow operations
workflow = QVService.init_workflow(project_root, "my-workflow", structure_selector="si")
QVService.configure_workflow(project_root, "my-workflow", new_name="Renamed workflow")
workflows = QVService.list_workflows(project_root)

# Step operations
step = QVService.init_step(project_root, "my-workflow", "scf", name="SCF calculation")
QVService.configure_step(project_root, "my-workflow", "scf", parameters={"ecutwfc": 60})
steps = QVService.list_steps(project_root, "my-workflow")

# Run operations
result = QVService.run_workflow(project_root, "my-workflow", strict=True)
```

### Project & Workflow loading

| Symbol | Description | Example |
| --- | --- | --- |
| `quantumvitas.project.model.Project.open(project_root)` | Load `project.qv.yml`, structures, and workflow references. | `proj = Project.open(Path("~/projects/si_demo"))` |
| `Project.get_structure(structure_id)` | Fetch a registered structure reference (path + metadata). | `si_ref = proj.get_structure("si")` |
| `Project.get_workflow(workflow_id)` | Resolve a workflow entry from `project.qv.yml`. | `si_dos = proj.get_workflow("si_dos")` |
| `quantumvitas.workflow.workflow.Workflow.from_yaml(path, project)` | Load a workflow from an explicit YAML file (outside registry). | `wf = Workflow.from_yaml(Path("workflows/custom/workflow.yaml"), proj)` |

### Workflow execution & verification

| Symbol | Description | Example |
| --- | --- | --- |
| `quantumvitas.workflow.runner.WorkflowRunner(registry)` | Runtime coordinator that schedules steps through registered engines. | `runner = WorkflowRunner(create_default_registry())` |
| `WorkflowRunner.run(workflow)` | Execute all steps in order, returning a `WorkflowResult`. | `result = runner.run(wf); print(result.status)` |
| `quantumvitas.workflow.verification.verify_step_result(step_result, reference_file, category)` | Compare a QE run against a reference (energy, Fermi level, PH frequencies). | `ok, msg = verify_step_result(step_result, ref, "pw_scf")` |

### Structure & step specifications

| Symbol | Description | Example |
| --- | --- | --- |
| `quantumvitas.workflow.structure_steps.StructureStepSpec.from_yaml(path)` | Parse a `*.step.yaml` spec (structure pointer + overrides). | `spec = StructureStepSpec.from_yaml(Path("steps/scf.step.yaml"))` |
| `generate_qe_input_from_structure(structure, step_type, parameter_overrides=None)` | Build a QE input from a `pymatgen.Structure`. | `qe_input = generate_qe_input_from_structure(structure, "scf")` |
| `generate_qe_input_from_spec(structure, spec, extra_overrides=None)` | Combine a stored spec + structure into a QE input while applying overrides. | `qe_input, applied = generate_qe_input_from_spec(structure, spec)` |
| `materialize_step_spec(structure, spec, project_root)` | Write the generated QE input to disk with correct `outdir`/`pseudo_dir`. | `input_path, overrides = materialize_step_spec(structure, spec, project_root)` |

### Importing existing QE inputs

| Symbol | Description | Example |
| --- | --- | --- |
| `quantumvitas.workflow.importers.build_step_spec_from_qe_input(input_path, output_dir)` | Convert a QE `.in` into a `StructureStepSpec` + structure JSON. | `spec_path = build_step_spec_from_qe_input(Path("si.scf.in"), Path("steps"))` |
| `quantumvitas.workflow.importers.build_workflow_from_qe_inputs(inputs, project_root, workflow_id)` | Turn a list of QE inputs into a workflow folder with `workflow.yaml`. | `build_workflow_from_qe_inputs(sorted(raw_inputs), proj_root, "si_dos")` |

### Direct step execution helpers

| Symbol | Description | Example |
| --- | --- | --- |
| `quantumvitas.workflow.input_runner.run_input_step(engine, input_file, working_dir, project_root, step_type=None, parameter_overrides=None)` | Low-level helper that prepares the QE input, runs it, and returns `StepResult` + `PreparedInputStep`. | `result, prepared = run_input_step(engine.backend, Path("pw_scf.in"), Path("temp/run"), project_root)` |
| `quantumvitas.workflow.geometry.read_geometry_from_input(path)` | Extract alat, cell matrix, and atomic positions from a QE input. | `geom_in = read_geometry_from_input(Path("pw_scf.in"))` |
| `quantumvitas.workflow.geometry.read_geometry_from_output(path)` | Same as above but from QE output. | `geom_out = read_geometry_from_output(Path("pw_scf.out"))` |
| `quantumvitas.workflow.geometry.compare_geometries(geom1, geom2, tolerance=1e-6)` | Numerical comparison helper for geometry regression tests. | `ok, diff = compare_geometries(geom_in, geom_out)` |

### Analysis functions

| Symbol | Description | Example |
| --- | --- | --- |
| `quantumvitas.analysis.energy.extract_energy_metrics_from_text(text)` | Parse SCF output for energies. Returns `{"total_energy_ry": ..., "fermi_energy_ev": ...}`. | `metrics = extract_energy_metrics_from_text(output_text)` |
| `quantumvitas.analysis.parsers.parse_scf_output(text)` | Parse full SCF output to `SCFResult` dataclass. | `result = parse_scf_output(output_text)` |
| `quantumvitas.analysis.dos.analyze_dos_file(dos_file, fermi_energy=None)` | Parse DOS data file. | `dos_data = analyze_dos_file(Path("si.dos.dat"))` |
| `quantumvitas.analysis.bands.analyze_bands_file(bands_file, fermi_energy=None)` | Parse band structure data file. | `bands = analyze_bands_file(Path("si.bands.dat"))` |

### Engine utilities

| Symbol | Description | Example |
| --- | --- | --- |
| `quantumvitas.engine.registry.create_default_registry()` | Register the QE engine (and future engines) for runners/CLI. | `registry = create_default_registry()` |
| `registry.get("qe")` → `QeEngine` | Access the QE engine wrapper to inspect installation paths. | `qe_engine = registry.get("qe")` |

### K-path generation

| Symbol | Description | Example |
| --- | --- | --- |
| `quantumvitas.analysis.kpath.generate_kpath(structure, n_points=50)` | Generate high-symmetry k-path using pymatgen. | `kpath = generate_kpath(structure, n_points=30)` |
| `KPathResult.to_qe_kpoints_crystal_b()` | Convert k-path to QE K_POINTS crystal_b format. | `qe_kpoints = kpath.to_qe_kpoints_crystal_b()` |

All higher-level APIs (CLI, workflow runner, importers) are layered on top of
these calls. If you need to automate a custom workflow, prefer these entry
points instead of reaching into internal modules.

## Architecture Note

The recommended architecture for programmatic access:

1. **CLI Layer** (`quantumvitas.cli.main`): Thin layer for command-line argument parsing and output formatting
2. **API Layer** (`quantumvitas.api.QVService`): Clean service interface for all operations
3. **Core Layer** (`quantumvitas.core.*`): Internal implementation details

For scripts and automation, prefer `QVService` methods over direct core imports.
