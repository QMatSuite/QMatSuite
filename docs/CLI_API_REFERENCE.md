# CLI & API Quick Reference

This page lists every `qv` CLI command plus the Python APIs that are meant to
be used directly by end users or automation scripts. Each entry keeps the
description short and includes a minimal example you can run or adapt.

## CLI commands

| Command | What it does | Quick example |
| --- | --- | --- |
| `qv init project [--path PATH] [--name NAME] [--template TEMPLATE]` | Create an empty project skeleton (defaults to `./projectN` in the current directory). Passing `--path` selects the destination; `--name` controls metadata/slug; `--template` is reserved for future bundles. | `qv init project --path ~/projects --name Si Demo` |
| `qv init workflow <id> --structure STRUCT [--project PATH] [--step scf --parent wfA --parent wfB]` | Scaffold a workflow folder (`workflows/<slug>/`) with `workflow.yaml`, `steps/`, and metadata. Optional `--parent` flags record upstream workflow dependencies. | `qv init workflow si_dos --structure si --project ~/projects/si_demo --step scf --step nscf --parent si_scf` |
| `qv init step <structure-id> [--workflow ID] [--name NAME] [--type scf] [overrides…]` | Generate a step `.yaml`, optionally appending it to a workflow (defaults to end). | `qv init step si --workflow si_dos --project ~/projects/si_demo --name nscf --type nscf --SYSTEM.ecutwfc=60` |
| `qv import-structure <file> [--name NAME] [--project PATH] [--output-format json]` | Parse a structure with pymatgen, auto-generate name/slug if omitted, and register it. | `qv import-structure si.cif --project ~/projects/si_demo --name "Si prim cell"` |
| `qv list [--project PATH] [--verbose]` | Print the project tree down to each workflow step (IDs shown only with `--verbose`). | `qv list --project ~/projects/si_demo -v` |
| `qv rename structure <selector> [--name NAME] [--slug SLUG] [--path PATH]` | Update a structure’s metadata and/or move its file (selector = name/slug/path). | `qv rename structure si --project ~/projects/si_demo --name "Si DOS" --path structures/si_dos.json` |
| `qv rename workflow <selector> [--name NAME] [--slug SLUG] [--path PATH]` | Update a workflow’s metadata and/or move its directory (selectors are name/slug/path). | `qv rename workflow si_dos --project ~/projects/si_demo --name "Si DOS workflow"` |
| `qv rename step <workflow> <step-id> [--project PATH] [--id NEW_ID] [--path NEW_PATH]` | Change a step id and/or relocate the `.step.yaml` file. | `qv rename step si_dos nscf --project ~/projects/si_demo --id nscf_relax` |
| `qv rename project [--project PATH] [--name NAME] [--slug SLUG] [--path PATH]` | Update project metadata or move the entire project directory. | `qv rename project --project ~/projects/si_demo --name "Si tutorial"` |
| `qv detect-qe` | Print the QE installation detected via the engine registry. | `qv detect-qe` |
| `qv configure step <step.yaml> [--remove] [overrides…]` | Edit (or remove via `--remove`) parameters inside an existing step spec. Placeholders for `project/workflow/structure` currently print “not yet implemented”. | `qv configure step workflows/si_dos/steps/nscf.step.yaml --SYSTEM.ecutwfc=70` |
| `qv delete structure <selector> [--project PATH] [--force] [--cascade]` | Move a structure (and optionally referencing workflows) into the project’s `trash/` folder (selector = name/slug/path). | `qv delete structure si --project ~/projects/si_demo` |
| `qv delete workflow <selector> [--project PATH] [--force] [--cascade]` | Move a workflow directory into `trash/`, optionally cascading dependent workflows (selector = name/slug/path). | `qv delete workflow si_dos --project ~/projects/si_demo --cascade` |
| `qv delete step <workflow> <step-id> [--project PATH]` | Remove a step entry from a workflow and move its `.step.yaml` to trash. | `qv delete step si_dos nscf --project ~/projects/si_demo` |
| `qv delete project [--project PATH]` | Move an entire project directory into the parent `trash/` folder (auto-confirms if you’re inside it). | `qv delete project --project ~/projects/si_demo` |
| `qv delete trash [--project PATH] [--path PATH] [--parent]` | Clean a trash directory (project-level by default, or explicit path). | `qv delete trash --project ~/projects/si_demo` |
| `qv run step <input.in|step.yaml> [--project PATH] [--workdir PATH] [overrides…]` | Run a standalone QE input file **or** a `.step.yaml`, applying overrides to parameters/cards/species. | `qv run step workflows/si_dos/steps/scf.step.yaml --project . --CARD.K_POINTS.data=[[6,6,6,0,0,0]]` |
| `qv run structure <structure-id|file> [--project PATH] [--type scf] [overrides…]` | Load a stored structure, materialize a QE input, apply overrides, and run it. | `qv run structure si --project ~/projects/si_demo --type scf --k_points=4,4,4,0,0,0` |
| `qv run workflow <workflow-id|path> [--project PATH] [--strict] [--verbose]` | Execute an entire workflow defined in `project.qv.yml` or an explicit YAML file (optionally forcing strict mode). | `qv run workflow si_dos --project ~/projects/si_demo --strict` |
| `qv run [target] [--project PATH] [--workdir PATH] [--strict]` | Auto-detect the target type (QE input, step YAML, workflow id, structure id) and dispatch to the appropriate subcommand. | `qv run workflows/si_dos/steps/scf.step.yaml --workdir temp/scf_run` |
| `qv analyze <energy|band|dos> <output-file>` | Invoke the lightweight analysis hooks on a QE output. | `qv analyze energy temp/test_outputs/si_scf.out` |
| `qv params <module> [--section SECTION]` | Inspect parameters scraped from the QE docs (`qe_module_parameters.json`). | `qv params pw --section SYSTEM` |
| `qv show-command <input.in>` | Parse a QE input and print example `qv init step` / `qv configure step` commands. | `qv show-command ci_test_data/pw_single_tests/scf.in` |
| `qv get-command <input.in>` | Alias for `qv show-command`. | `qv get-command inputs/si_scf.in` |

> **Selectors:** Whenever a command asks for a structure/workflow/step, pass its
> human-readable name, slug, or filesystem path. The internal ULID identifiers
> never appear in the CLI.

**Overrides syntax:** Any extra `--name=value` flag is treated as a QE override.
Parameters map into namelists (`--SYSTEM.ecutwfc=60`). Cards can be updated via
`--CARD.K_POINTS.data=[[6,6,6,0,0,0]]` or the shorthand `--k_points=...`; atomic
species rows use `--SPECIES.Si.mass=28.0855` / `--SPECIES.Si.pseudopot=Si.UPF`.
Lists accept JSON (`[ ... ]`) or comma-separated values, and booleans can be
specified with `--tprnfor` / `--tprnfor=false`.

### Detecting QE installations

`qv detect-qe` no longer depends on a project checkout. It aggregates three data
sources:

- `QE_HOME` environment variable (highest priority)
- The QE home reported by the engine installation
- `which pw.x` (walks up two parents to guess `<qe_home>/bin/pw.x`)

The command prints the resolved `qe_home`, `bin` directory, located executables,
and whether `test-suite/` was found (assumed to live under `<qe_home>/test-suite`
when available). Use this output to verify CI images or local developer setups.

## Python API surface

These calls live under the `quantumvitas` package and are kept stable for user
scripts, notebooks, and automation. Import paths shown are canonical; feel free
to alias locally.

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

### Engine utilities

| Symbol | Description | Example |
| --- | --- | --- |
| `quantumvitas.engine.registry.create_default_registry()` | Register the QE engine (and future engines) for runners/CLI. | `registry = create_default_registry()` |
| `registry.get("qe")` → `QeEngine` | Access the QE engine wrapper to inspect installation paths. | `qe_engine = registry.get("qe")` |

All higher-level APIs (CLI, workflow runner, importers) are layered on top of
these calls. If you need to automate a custom workflow, prefer these entry
points instead of reaching into internal modules.


