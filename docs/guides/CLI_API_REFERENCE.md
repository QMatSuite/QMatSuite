# CLI & API Quick Reference

This page lists every `qms` CLI command plus the Python APIs that are meant to
be used directly by end users or automation scripts. Each entry keeps the
description short and includes a minimal example you can run or adapt.

## CLI commands

| Command | What it does | Quick example |
| --- | --- | --- |
| `qms init project [--path PATH] [--name NAME] [--template TEMPLATE]` | Create a project skeleton. Passing `--path` selects destination; `--name` controls metadata. Use `--template project1` to copy from predefined template with example structures and calculations. | `qms init project --template project1` |
| `qms init calculation <name> --structure STRUCT [--project PATH] [--parent wfA] [--template TEMPLATE]` | Scaffold a calculation folder with `calculation.yaml`, `steps/`, and metadata. Use `--template si-dos` to copy from template (also copies related structures). When using `--template`, `--structure` is optional. | `qms init calculation my-dos --template si-dos` |
| `qms init step <type> [--structure STRUCT] [--calculation ID] [--project PATH] [--template TEMPLATE] [overrides…]` | Generate a step `.yaml` in the enclosing calculation. Step type is required (scf, nscf, relax, dos, etc.). Structure is optional if inside a calculation. Use `--template scf` to copy from template. | `qms init step nscf --template nscf` or `qms init step scf` (inside calculation) |
| `qms import-structure <file> [--name NAME] [--project PATH] [--output-format json]` | Parse a structure with pymatgen, auto-generate name/slug if omitted, and register it. Supports .cif, POSCAR, QE .in, and .json (including QMS format). | `qms import-structure si.cif --project ~/projects/si_demo --name "Si prim cell"` |
| `qms list [--project PATH] [--verbose]` | Print the project tree down to each calculation step (IDs shown only with `--verbose`). | `qms list --project ~/projects/si_demo -v` |
| `qms detect-qe` | Print the QE installation detected via the engine registry. | `qms detect-qe` |
| `qms show-command <input.in>` | Parse a QE input and print example `qms init step` / `qms configure step` commands. Auto-detects module type (pw.x, bands.x, dos.x, etc.). | `qms show-command ci_test_data/pw_single_tests/scf.in` |
| `qms get-command <input.in>` | Alias for `qms show-command`. | `qms get-command inputs/si_scf.in` |
| `qms analyze band [file] [--calculation WF] [--plot]` | Analyze band structure. Auto-detects files from calculation context. | `qms analyze band --calculation si-bands --plot` |
| `qms analyze dos <file> [--scf FILE] [--plot]` | Analyze DOS data with optional Fermi energy extraction. | `qms analyze dos si.dos.dat --scf nscf.out --plot` |
| `qms analyze energy <file> [--plot]` | Analyze SCF output for energies and convergence. | `qms analyze energy si.scf.out --plot` |
| `qms analyze scf <file> [--plot]` | Alias for `analyze energy`. | `qms analyze scf si.scf.out --plot` |
| `qms analyze structure <selector> [options]` | 3D ball-and-stick visualization of crystal structure. | `qms analyze structure si --supercell "2 2 2" --output si.png` |
| `qms analyze output [DEPRECATED]` | **Deprecated.** Use `qms analyze band/dos/energy` instead. | — |
| `qms params <module> [--section SECTION]` | Inspect parameters scraped from the QE docs (`qe_module_parameters.json`). | `qms params pw --section SYSTEM` |

### Configure Commands (Recommended)

| Command | What it does | Quick example |
| --- | --- | --- |
| `qms configure step <step-id|path> [--calculation ID] [--name NAME] [--remove] [overrides…]` | Edit step parameters. Use `--name` to rename. Use `--remove` to delete parameters. Step auto-detected from pwd if inside calculation. | `qms configure step nscf --name="NSCF high k" --SYSTEM.ecutwfc=70` |
| `qms configure calculation [<calculation-id|path>] [--name NAME] [--structure STRUCT] [--reorder STEP1,STEP2,...]` | Modify calculation settings. Use `--name` to rename. Use `--structure` to change structure (updates all steps). Use `--reorder` to change step order. | `qms configure calculation --name="Si DOS v2" --reorder scf,nscf,dos` |
| `qms configure structure <identifier> [--project PATH] [--name NAME]` | Rename a structure using `--name`. For complex modifications, re-import. | `qms configure structure si --name "Silicon bulk"` |

### Rename Commands (Deprecated)

> **Warning:** The `qms rename` commands are deprecated. Use `qms configure --name` instead.

| Command | What it does | Quick example |
| --- | --- | --- |
| `qms rename structure <selector> [--name NAME] [--slug SLUG] [--path PATH]` | **Deprecated.** Use `qms configure structure <selector> --name <new_name>` instead. | `qms configure structure si --name "Si DOS"` |
| `qms rename calculation <selector> [--name NAME] [--slug SLUG] [--path PATH]` | **Deprecated.** Use `qms configure calculation <selector> --name <new_name>` instead. | `qms configure calculation si_dos --name "Si DOS calculation"` |
| `qms rename step <calculation> <step-id> [--project PATH] [--id NEW_ID]` | **Deprecated.** Use `qms configure step <step-id> --calculation <calculation> --name <new_name>` instead. | `qms configure step nscf --name nscf_relax` |
| `qms rename project [--project PATH] [--name NAME]` | **Deprecated.** Use project-level configuration. | — |

### Delete Commands

| Command | What it does | Quick example |
| --- | --- | --- |
| `qms delete structure <selector> [--project PATH] [--force] [--cascade]` | Move a structure (and optionally referencing calculations) into the project's `trash/` folder. Selector = id/name/slug/path. | `qms delete structure si` |
| `qms delete calculation [<selector>] [--project PATH] [--force] [--cascade]` | Move a calculation directory into `trash/`, optionally cascading dependent calculations. Auto-detects from pwd if not specified. | `qms delete calculation --cascade` |
| `qms delete step <step-id> [--calculation ID] [--project PATH]` | Remove a step entry from a calculation and move its `.step.yaml` to trash. Calculation auto-detected from pwd if inside one. | `qms delete step nscf` |
| `qms delete project [<selector>] [--project PATH]` | Move a project directory into the parent `trash/` folder. Selector = name/slug/path. | `qms delete project si_demo` |
| `qms delete trash [--project PATH] [--path PATH] [--parent]` | Clean a trash directory (project-level by default, or explicit path). | `qms delete trash --project ~/projects/si_demo` |

### Run Commands

| Command | What it does | Quick example |
| --- | --- | --- |
| `qms run step <input.in|step.yaml> [--project PATH] [--workdir PATH] [overrides…]` | Run a QE input file **or** a `.step.yaml` in project mode, applying overrides to parameters/cards/species. | `qms run step calculations/si_dos/steps/scf.step.yaml --project . --CARD.K_POINTS.data=[[6,6,6,0,0,0]]` |
| `qms run step --standalone --input <file> [--workdir PATH]` | Run a QE input file in standalone mode (no project context). See `docs/STANDALONE_QE.md` for details. | `qms run step --standalone --input pw.in --workdir ./run` |
| `qms run structure <structure-id|file> [--project PATH] [--type scf] [overrides…]` | Load a stored structure, materialize a QE input, apply overrides, and run it. | `qms run structure si --project ~/projects/si_demo --type scf --k_points=4,4,4,0,0,0` |
| `qms run calculation [<calculation-id|path>] [--project PATH] [--strict] [--verbose]` | Execute a calculation. Auto-detects enclosing calculation from pwd if not specified. | `qms run calculation --strict` |
| `qms run [target] [--project PATH] [--workdir PATH] [--strict]` | Auto-detect the target type (QE input, step YAML, calculation id, structure id) and dispatch to the appropriate subcommand. If no target, runs enclosing calculation. | `qms run --strict` |

> **Selectors:** Resources can be identified by:
> - **id** (ULID): Exact match, case-sensitive (e.g., `01JXYZ...`)
> - **name/slug**: Case-insensitive match (e.g., `si_dos`, `"Si DOS"`)
> - **path**: Relative or absolute filesystem path (e.g., `calculations/si-dos`)
>
> **Auto-detection:** Many commands auto-detect resources from the current directory:
> - **Project**: Walks up from pwd to find `project.qms.yml`
> - **Calculation**: Detects if pwd is inside a calculation directory
> - **Step**: If inside a calculation, step id can be used directly

**Overrides syntax:** Any extra `--name=value` flag is treated as a QE override.
Parameters map into namelists (`--SYSTEM.ecutwfc=60`). Cards can be updated via
`--CARD.K_POINTS.data=[[6,6,6,0,0,0]]` or the shorthand `--k_points=...`; atomic
species rows use `--SPECIES.Si.mass=28.0855` / `--SPECIES.Si.pseudopot=Si.UPF`.
Lists accept JSON (`[ ... ]`) or comma-separated values, and booleans can be
specified with `--tprnfor` / `--tprnfor=false`.

### Detecting QE installations

`qms detect-qe` no longer depends on a project checkout. It auto-detects QE using
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

All resources (projects, calculations, steps, structures) include a `meta` section with:

| Field | Description |
|-------|-------------|
| `id` | ULID (Universally Unique Lexicographically Sortable Identifier) |
| `name` | Human-readable display name |
| `slug` | URL-safe identifier (derived from name) |
| `path` | Relative path from project root |
| `kind` | Resource type: `project`, `calculation`, `step`, `structure` |

Example `calculation.yaml` with metadata:

```yaml
meta:
  id: 01JXYZ123ABC456DEF789GHI
  name: Si DOS calculation
  slug: si-dos-calculation
  path: calculations/si-dos-calculation
  kind: calculation
mode: normal
structure: si
working_dir: raw
steps:
  - id: scf
    type: scf
    step_file: steps/scf.step.yaml
```

## Pseudopotential Handling

When running QE calculations, QMatSuite automatically manages pseudopotentials:

1. **Project-local first**: Checks `project/pseudo/` for required files
2. **Global cache**: Falls back to `qmatsuite_root/pseudo/`
3. **Auto-download**: Downloads missing pseudopotentials from QE servers
4. **Copy to project**: Downloaded files are copied to both locations for project portability

Set `pseudo_dir` in step YAML or use `--pseudo_dir` override to customize.

## Input File Handling

When running `.in` files via `qms run`:

- The final processed input is written to `<io_dir>/<stem>.in` (where `io_dir` is the calculation's I/O directory, default `raw/`)
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

## Analyze Commands

### `qms analyze output` - QE Output Analysis

For `qms analyze output band`, files can be auto-detected from calculation context:

```bash
# Explicit calculation selector
qms analyze output band --calculation si-bands --plot

# Auto-detect from current directory (if inside a calculation)
cd project/calculations/si-bands/raw
qms analyze output band --plot

# Auto-detect from pwd (searches for files in current directory)
qms analyze output band --plot

# Explicit files (still supported)
qms analyze output band si.bands.dat.gnu --symmetry si.bands.out --scf si.nscf.out --plot
```

Auto-detection searches for:
- `*.dat.gnu` or `*bands.dat.gnu` - Band energies
- `*.bands.out` or `*bandspp*.out` - bands.x output (high-symmetry points)
- `*nscf*.out` or `*scf*.out` - pw.x output (Fermi energy, reciprocal lattice)

### `qms analyze structure` - 3D Crystal Visualization

Visualize crystal structures as 3D ball-and-stick plots:

```bash
# Basic visualization (saves to current directory)
qms analyze structure si

# Custom output path
qms analyze structure si --output si_structure.png

# Supercell expansion (2×2×2)
qms analyze structure si --supercell "2 2 2"

# Show periodic images at cell boundaries
qms analyze structure si --supercell "2 2 2" --repeat-boundary

# Interactive display (if not headless)
qms analyze structure si --show

# Different output formats
qms analyze structure si --format svg
```

Options:
- `--supercell "a b c"` - Create a×b×c supercell (default: 1 1 1)
- `--repeat-boundary` / `--no-repeat-boundary` - Show/hide periodic images at boundaries
- `--output PATH` - Output file path (default: `<name>_structure.png`)
- `--format FMT` - Output format: png, svg, pdf
- `--show` - Display interactively (may not work in headless mode)
- `--project PATH` - Project root for structure resolution

Bond Detection:
- Bonds detected using covalent radii (Cordero et al., Dalton Trans. 2008)
- By default, only internal bonds within the cell are shown
- With `--repeat-boundary`, bonds to periodic images are included
- Supercell expansion shows all internal bonds (e.g., 2×2×2 Si has 32 bonds)

Works with:
- Project structures by selector (name/slug)
- Direct file paths (.cif, .json, POSCAR, etc.)

## Python API surface

These calls live under the `qmatsuite` package and are kept stable for user
scripts, notebooks, and automation. Import paths shown are canonical; feel free
to alias locally.

### QMSService (Recommended API Layer)

The `QMSService` class in `qmatsuite.api` provides the cleanest interface for
programmatic access:

```python
from qmatsuite.api import QMSService

# Project operations
project_root = QMSService.init_project(Path("./my_project"), name="My Project")
QMSService.configure_project(project_root, new_name="Renamed Project")

# Structure operations
struct = QMSService.import_structure(project_root, Path("si.cif"), name="Silicon")
QMSService.configure_structure(project_root, "si", new_name="Silicon bulk")
structures = QMSService.list_structures(project_root)

# Calculation operations
calculation = QMSService.init_workflow(project_root, "my-calculation", structure_selector="si")
QMSService.configure_workflow(project_root, "my-calculation", new_name="Renamed calculation")
calculations = QMSService.list_calculations(project_root)

# Step operations
step = QMSService.init_step(project_root, "my-calculation", "scf", name="SCF calculation")
QMSService.configure_step(project_root, "my-calculation", "scf", parameters={"ecutwfc": 60})
steps = QMSService.list_steps(project_root, "my-calculation")

# Run operations
result = QMSService.run_calculation(project_root, "my-calculation", strict=True)
```

### Project & Calculation loading

| Symbol | Description | Example |
| --- | --- | --- |
| `qmatsuite.project.model.Project.open(project_root)` | Load `project.qms.yml`, structures, and calculation references. | `proj = Project.open(Path("~/projects/si_demo"))` |
| `Project.get_structure(structure_id)` | Fetch a registered structure reference (path + metadata). | `si_ref = proj.get_structure("si")` |
| `Project.get_calculation(calculation_id)` | Resolve a calculation entry from `project.qms.yml`. | `si_dos = proj.get_calculation("si_dos")` |
| `qmatsuite.calculation.calculation.Calculation.from_yaml(path, project)` | Load a calculation from an explicit YAML file (outside registry). | `wf = Calculation.from_yaml(Path("calculations/custom/calculation.yaml"), proj)` |

### Calculation execution & verification

| Symbol | Description | Example |
| --- | --- | --- |
| `qmatsuite.calculation.runner.CalculationRunner(registry)` | Runtime coordinator that schedules steps through registered engines. | `runner = CalculationRunner(create_default_registry())` |
| `CalculationRunner.run(calculation)` | Execute all steps in order, returning a `CalculationResult`. | `result = runner.run(wf); print(result.status)` |
| `qmatsuite.calculation.verification.verify_step_result(step_result, reference_file, category)` | Compare a QE run against a reference (energy, Fermi level, PH frequencies). | `ok, msg = verify_step_result(step_result, ref, "pw_scf")` |

### Structure & step specifications

| Symbol | Description | Example |
| --- | --- | --- |
| `qmatsuite.calculation.structure_steps.StructureStepSpec.from_yaml(path)` | Parse a `*.step.yaml` spec (structure pointer + overrides). | `spec = StructureStepSpec.from_yaml(Path("steps/scf.step.yaml"))` |
| `generate_qe_input_from_structure(structure, step_type, parameter_overrides=None)` | Build a QE input from a `pymatgen.Structure`. | `qe_input = generate_qe_input_from_structure(structure, "scf")` |
| `generate_qe_input_from_spec(structure, spec, extra_overrides=None)` | Combine a stored spec + structure into a QE input while applying overrides. | `qe_input, applied = generate_qe_input_from_spec(structure, spec)` |
| `materialize_step_spec(structure, spec, project_root)` | Write the generated QE input to disk with correct `outdir`/`pseudo_dir`. | `input_path, overrides = materialize_step_spec(structure, spec, project_root)` |

### Importing existing QE inputs

| Symbol | Description | Example |
| --- | --- | --- |
| `qmatsuite.calculation.importers.build_step_spec_from_qe_input(input_path, output_dir)` | Convert a QE `.in` into a `StructureStepSpec` + structure JSON. | `spec_path = build_step_spec_from_qe_input(Path("si.scf.in"), Path("steps"))` |
| `qmatsuite.calculation.importers.build_calculation_from_qe_inputs(inputs, project_root, calculation_id)` | Turn a list of QE inputs into a calculation folder with `calculation.yaml`. | `build_calculation_from_qe_inputs(sorted(raw_inputs), proj_root, "si_dos")` |

### Direct step execution helpers

| Symbol | Description | Example |
| --- | --- | --- |
| `qmatsuite.calculation.input_runner.run_input_step(engine, input_file, working_dir, project_root, step_type=None, parameter_overrides=None)` | Low-level helper that prepares the QE input, runs it, and returns `StepResult` + `PreparedInputStep`. | `result, prepared = run_input_step(engine.backend, Path("pw_scf.in"), Path("temp/run"), project_root)` |
| `qmatsuite.calculation.geometry.read_geometry_from_input(path)` | Extract alat, cell matrix, and atomic positions from a QE input. | `geom_in = read_geometry_from_input(Path("pw_scf.in"))` |
| `qmatsuite.calculation.geometry.read_geometry_from_output(path)` | Same as above but from QE output. | `geom_out = read_geometry_from_output(Path("pw_scf.out"))` |
| `qmatsuite.calculation.geometry.compare_geometries(geom1, geom2, tolerance=1e-6)` | Numerical comparison helper for geometry regression tests. | `ok, diff = compare_geometries(geom_in, geom_out)` |

### Analysis functions

| Symbol | Description | Example |
| --- | --- | --- |
| `qmatsuite.analysis.energy.extract_energy_metrics_from_text(text)` | Parse SCF output for energies. Returns `{"total_energy_ry": ..., "fermi_energy_ev": ...}`. | `metrics = extract_energy_metrics_from_text(output_text)` |
| `qmatsuite.analysis.parsers.parse_scf_output(text)` | Parse full SCF output to `SCFResult` dataclass. | `result = parse_scf_output(output_text)` |
| `qmatsuite.analysis.dos.analyze_dos_file(dos_file, fermi_energy=None)` | Parse DOS data file. | `dos_data = analyze_dos_file(Path("si.dos.dat"))` |
| `qmatsuite.analysis.bands.analyze_bands_file(bands_file, fermi_energy=None)` | Parse band structure data file. | `bands = analyze_bands_file(Path("si.bands.dat"))` |

### Engine utilities

| Symbol | Description | Example |
| --- | --- | --- |
| `qmatsuite.engine.registry.create_default_registry()` | Register the QE engine (and future engines) for runners/CLI. | `registry = create_default_registry()` |
| `registry.get("qe")` → `QeEngine` | Access the QE engine wrapper to inspect installation paths. | `qe_engine = registry.get("qe")` |

### K-path generation

| Symbol | Description | Example |
| --- | --- | --- |
| `qmatsuite.analysis.kpath.generate_kpath(structure, n_points=50)` | Generate high-symmetry k-path using pymatgen. | `kpath = generate_kpath(structure, n_points=30)` |
| `KPathResult.to_qe_kpoints_crystal_b()` | Convert k-path to QE K_POINTS crystal_b format. | `qe_kpoints = kpath.to_qe_kpoints_crystal_b()` |

All higher-level APIs (CLI, calculation runner, importers) are layered on top of
these calls. If you need to automate a custom calculation, prefer these entry
points instead of reaching into internal modules.

## Architecture Note

The recommended architecture for programmatic access:

1. **CLI Layer** (`qmatsuite.cli.main`): Thin layer for command-line argument parsing and output formatting
2. **API Layer** (`qmatsuite.api.QMSService`): Clean service interface for all operations
3. **Core Layer** (`qmatsuite.core.*`): Internal implementation details

For scripts and automation, prefer `QMSService` methods over direct core imports.
