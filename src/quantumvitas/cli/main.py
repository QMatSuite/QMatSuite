"""
Typer-based CLI for QuantumVITAS.
"""

from __future__ import annotations

import ast
import json
import shutil
from pathlib import Path
from typing import List, Optional

import yaml

import typer
from pymatgen.core import Structure as PMGStructure

from quantumvitas.analysis import bands as bands_analysis
from quantumvitas.analysis import dos as dos_analysis
from quantumvitas.analysis import energy as energy_analysis
from quantumvitas.data import load_qe_parameter_map
from quantumvitas.engine.registry import create_default_registry
from quantumvitas.project.model import Project
from quantumvitas.workflow.runner import WorkflowRunner
from quantumvitas.workflow.workflow import Workflow
from quantumvitas.workflow.input_runner import (
    ParameterOverride,
    detect_project_root,
    run_input_step,
)
from quantumvitas.workflow.structure_steps import (
    StructureStepSpec,
    generate_qe_input_from_spec,
    generate_qe_input_from_structure,
)
from quantumvitas.io import QEInputGenerator, read_structure, write_structure

app = typer.Typer(help="QuantumVITAS CLI")


def _resolve_project_root(start: Optional[Path] = None) -> Path:
    start_path = Path(start or Path.cwd()).resolve()
    current = start_path
    while current != current.parent:
        if (current / "project.qv.yml").exists():
            return current
        current = current.parent
    raise typer.BadParameter("Unable to locate project.qv.yml. Use --project or run inside a project root.")


def _ensure_empty_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _coerce_override_value(raw: str):
    value = raw.strip()
    # Strip surrounding quotes if present
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        value = value[1:-1]
    
    lower = value.lower()
    if lower in {".true.", "true", "t"}:
        return True
    if lower in {".false.", "false", "f"}:
        return False
    try:
        result = ast.literal_eval(value)
        # Convert tuples to lists for consistency
        if isinstance(result, tuple):
            return list(result)
        return result
    except (ValueError, SyntaxError):
        pass
    if "," in value and not value.startswith(("(", "[")):
        parts = [part.strip() for part in value.split(",")]
        if len(parts) > 1:
            return [_coerce_override_value(part) for part in parts]
    return value


def _parse_override_args(extra_args: List[str]) -> List[ParameterOverride]:
    """
    Convert unknown CLI arguments (e.g., --ecutwfc=40) into overrides.
    """

    overrides: dict[str, ParameterOverride] = {}
    i = 0
    while i < len(extra_args):
        token = extra_args[i]
        if not token.startswith("--"):
            i += 1
            continue
        key = token[2:]
        value: Optional[str] = None
        if "=" in key:
            key, value = key.split("=", 1)
        else:
            if i + 1 < len(extra_args) and not extra_args[i + 1].startswith("--"):
                value = extra_args[i + 1]
                i += 1
            else:
                value = "true"

        key = key.strip()
        if not key:
            i += 1
            continue

        section_hint: Optional[str] = None
        param_name = key
        if "." in key:
            section_hint, param_name = key.split(".", 1)

        normalized_param = param_name.replace("-", "_")
        normalized_section = section_hint.replace("-", "_") if section_hint else None
        overrides[normalized_param.lower()] = ParameterOverride(
            name=normalized_param,
            value=_coerce_override_value(value),
            section=normalized_section,
        )
        i += 1

    return list(overrides.values())


def _resolve_structure_input(
    project_root: Path, identifier: str
) -> tuple[PMGStructure, str]:
    """
    Load a structure either from a file path or from project metadata.
    """

    candidate = Path(identifier)
    if candidate.exists():
        structure = read_structure(candidate)
        return structure, candidate.stem

    project = Project.open(project_root)
    ref = project.get_structure(identifier)
    structure = read_structure(ref.path)
    return structure, identifier


@app.command("init")
def init_project(
    destination: Path = typer.Argument(..., help="Directory to create the project in"),
    workflow_id: str = typer.Option("example", help="Initial workflow id"),
) -> None:
    """
    Scaffold a new QuantumVITAS project with a sample workflow.
    """
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)

    project_config = {
        "project": {"name": destination.name},
        "workflows": [{"id": workflow_id, "path": f"workflows/{workflow_id}"}],
        "structures": [],
        "settings": {},
    }
    (destination / "project.qv.yml").write_text(
        yaml.safe_dump(project_config, sort_keys=False)
    )

    workflow_dir = destination / "workflows" / workflow_id
    raw_dir = workflow_dir / "raw"
    steps_dir = workflow_dir / "steps"
    _ensure_empty_dir(raw_dir)
    steps_dir.mkdir(parents=True, exist_ok=True)

    sample_inputs = {
        "scf.in": "&control\n  calculation = 'scf'\n/\n",
        "nscf.in": "&control\n  calculation = 'nscf'\n/\n",
    }
    for name, content in sample_inputs.items():
        (raw_dir / name).write_text(content)

    workflow_dict = {
        "id": workflow_id,
        "mode": "normal",
        "workflow": {"working_dir": "raw"},
        "steps": [
            {"id": "scf", "input": "scf.in"},
            {"id": "nscf", "input": "nscf.in"},
        ],
    }
    (workflow_dir / "workflow.yaml").write_text(
        yaml.safe_dump(workflow_dict, sort_keys=False)
    )
    typer.secho(f"Project created at {destination}", fg=typer.colors.GREEN)


@app.command("import-structure")
def import_structure_command(
    structure_file: Path = typer.Argument(
        ..., help="Input structure file (.cif, POSCAR, QE .in, etc.)"
    ),
    structure_id: str = typer.Option(
        ..., "--id", "-i", help="Structure identifier to register in the project"
    ),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    output_format: str = typer.Option(
        "json",
        "--output-format",
        help="Canonical storage format (json, cif, poscar, etc.)",
    ),
) -> None:
    """
    Import a structure file via pymatgen and register it in project.qv.yml.
    """
    project_root = project or _resolve_project_root()
    project_root = project_root.resolve()

    struct = read_structure(structure_file)

    structures_dir = project_root / "structures"
    structures_dir.mkdir(parents=True, exist_ok=True)
    ext = output_format.lower()
    out_path = structures_dir / f"{structure_id}.{ext}"
    write_rel = out_path.relative_to(project_root)

    write_structure(struct, out_path, format=output_format)

    config_file = project_root / "project.qv.yml"
    data = yaml.safe_load(config_file.read_text()) or {}
    structures = data.get("structures", [])
    if any(s.get("id") == structure_id for s in structures):
        raise typer.BadParameter(f"Structure id '{structure_id}' already exists.")

    structures.append(
        {"id": structure_id, "file": str(write_rel), "format": output_format.lower()}
    )
    data["structures"] = structures
    config_file.write_text(yaml.safe_dump(data, sort_keys=False))

    typer.secho(
        f"Imported structure '{structure_id}' -> {write_rel}", fg=typer.colors.GREEN
    )


@app.command("detect-qe")
def detect_qe(
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    )
) -> None:
    """
    Report the QE binaries discovered in the current installation.
    """
    project_root = project or detect_project_root()
    registry = create_default_registry()
    engine = registry.get("qe")
    qe_home = getattr(engine.backend._installation, "qe_home", None)
    typer.echo(f"QE home: {qe_home}")
    for exe in ["pw.x", "ph.x", "dos.x", "bands.x"]:
        path = engine.backend.find_executable(exe)
        typer.echo(f"{exe}: {path or 'not found'}")


@app.command(
    "run-step",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def run_step_command(
    ctx: typer.Context,
    input_file: Path = typer.Argument(..., help="QE input file to execute"),
    working_dir: Optional[Path] = typer.Option(
        None, "--workdir", help="Temporary working directory"
    ),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (for pseudo/pseudo_dir handling)"
    ),
) -> None:
    """
    Run a single QE input file in isolation.
    """
    registry = create_default_registry()
    engine = registry.get("qe")

    workdir = working_dir or (Path("temp") / "cli_outputs" / input_file.stem)
    workdir = workdir.resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    if project:
        project_root = project.resolve()
    else:
        try:
            project_root = _resolve_project_root()
        except typer.BadParameter:
            project_root = detect_project_root(input_file.parent)

    overrides = _parse_override_args(ctx.args)
    if overrides:
        rendered = ", ".join(
            f"{(o.section + '.' if o.section else '')}{o.name}={o.value}"
            for o in overrides
        )
        typer.echo(f"Applying overrides: {rendered}")

    result, prepared = run_input_step(
        engine=engine.backend,
        input_file=input_file.resolve(),
        working_dir=workdir,
        project_root=project_root,
        step_type=None,
        parameter_overrides=overrides or None,
    )

    typer.echo(f"Step finished: {result.step_type} -> {result.output_file}")
    typer.echo(f"Working dir: {prepared.working_dir}")


@app.command(
    "run-structure",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def run_structure_command(
    ctx: typer.Context,
    structure: str = typer.Argument(
        ..., help="Structure id (from project) or direct file path"
    ),
    working_dir: Optional[Path] = typer.Option(
        None, "--workdir", help="Working directory for generated inputs"
    ),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    input_name: Optional[str] = typer.Option(
        None,
        "--input-name",
        help="Filename for the generated QE input (defaults to <structure>.pw.in)",
    ),
    step_type: str = typer.Option(
        "scf",
        "--step-type",
        help="QE calculation type (scf, nscf, relax, etc.).",
    ),
) -> None:
    """
    Generate a QE input from a stored structure + CLI parameters, then run it.
    """
    registry = create_default_registry()
    engine = registry.get("qe")

    if project:
        project_root = project.resolve()
    else:
        project_root = _resolve_project_root()

    struct, struct_name = _resolve_structure_input(project_root, structure)

    workdir = working_dir or (Path("temp") / "cli_outputs" / struct_name)
    workdir = workdir.resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    overrides = _parse_override_args(ctx.args)
    if overrides:
        rendered = ", ".join(
            f"{(o.section + '.' if o.section else '')}{o.name}={o.value}"
            for o in overrides
        )
        typer.echo(f"Applying overrides: {rendered}")

    qe_input = generate_qe_input_from_structure(
        structure=struct,
        step_type=step_type,
        parameter_overrides=overrides,
    )

    generated_name = input_name or f"{struct_name}_{step_type}.pw.in"
    generated_input = workdir / generated_name
    QEInputGenerator.write_file(qe_input, generated_input)

    result, prepared = run_input_step(
        engine=engine.backend,
        input_file=generated_input,
        working_dir=workdir,
        project_root=project_root,
        step_type=None,
        parameter_overrides=overrides or None,
    )

    typer.echo(
        f"Structure run finished: {result.step_type} -> {result.output_file} "
        f"(input {generated_input})"
    )
    typer.echo(f"Working dir: {prepared.working_dir}")


@app.command(
    "run-stepfile",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def run_stepfile_command(
    ctx: typer.Context,
    step_file: Path = typer.Argument(
        ..., help="YAML file describing structure, parameters, and step type"
    ),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    working_dir: Optional[Path] = typer.Option(
        None, "--workdir", help="Working directory for generated inputs"
    ),
) -> None:
    """
    Generate and run a QE input based on a step YAML file.
    """

    project_root = project or _resolve_project_root()
    project_root = project_root.resolve()

    spec = StructureStepSpec.from_yaml(step_file)
    struct, struct_name = _resolve_structure_input(project_root, spec.structure)

    extra_overrides = _parse_override_args(ctx.args)
    if extra_overrides:
        rendered = ", ".join(
            f"{(o.section + '.' if o.section else '')}{o.name}={o.value}"
            for o in extra_overrides
        )
        typer.echo(f"Applying overrides: {rendered}")

    qe_input, combined_overrides = generate_qe_input_from_spec(
        structure=struct,
        spec=spec,
        extra_overrides=extra_overrides,
    )

    workdir = working_dir or (Path("temp") / "cli_outputs" / struct_name)
    workdir = workdir.resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    input_name = spec.input_name or f"{struct_name}_{spec.step_type}.pw.in"
    generated_input = workdir / input_name
    QEInputGenerator.write_file(qe_input, generated_input)

    registry = create_default_registry()
    engine = registry.get("qe")
    result, prepared = run_input_step(
        engine=engine.backend,
        input_file=generated_input,
        working_dir=workdir,
        project_root=project_root,
        step_type=None,
        parameter_overrides=combined_overrides or None,
    )

    typer.echo(
        f"Step file run finished: {result.step_type} -> {result.output_file} "
        f"(input {generated_input})"
    )
    typer.echo(f"Working dir: {prepared.working_dir}")


@app.command("run-workflow")
def run_workflow_command(
    workflow: str = typer.Argument(..., help="Workflow id or path"),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
) -> None:
    """
    Execute a workflow defined in project.qv.yml.
    """
    project_root = project or _resolve_project_root()
    proj = Project.open(project_root)

    # Accept either workflow id or direct path
    workflow_path = Path(workflow)
    if workflow_path.exists():
        wf = Workflow.from_yaml(workflow_path, proj)
    else:
        wf = proj.get_workflow(workflow)

    registry = create_default_registry()
    runner = WorkflowRunner(registry)
    result = runner.run(wf)

    typer.echo(f"Workflow {wf.id} status: {result.status}")
    for step in result.steps:
        typer.echo(f"- {step.step_id}: {step.status} ({step.message})")


@app.command("analyze")
def analyze_command(
    kind: str = typer.Argument(..., help="energy, band, or dos"),
    input_file: Path = typer.Argument(..., help="Output file to analyze"),
) -> None:
    """
    Run lightweight analysis on QE outputs (placeholder hooks).
    """
    normalized = kind.lower()
    if normalized == "energy":
        data = energy_analysis.analyze_energies(input_file)
    elif normalized == "band":
        data = bands_analysis.analyze_bands(input_file)
    elif normalized == "dos":
        data = dos_analysis.analyze_dos(input_file)
    else:
        raise typer.BadParameter("kind must be one of: energy, band, dos")
    typer.echo(json.dumps(data, indent=2))


@app.command("params")
def params_command(
    module: str = typer.Argument(..., help="QE module name, e.g. pw, ph, dos"),
    section: Optional[str] = typer.Option(
        None, "--section", help="Optional section/namelist to filter (e.g., CONTROL)."
    ),
) -> None:
    """
    Inspect module parameter metadata sourced from the QE documentation.
    """
    module_key = module.lower()
    param_map = load_qe_parameter_map()
    modules = param_map.get("modules", {})
    if module_key not in modules:
        raise typer.BadParameter(
            f"Unknown module '{module}'. Available: {', '.join(sorted(modules))}"
        )

    module_entry = modules[module_key]
    sections = module_entry.get("sections", {})

    def match_section(name: str) -> bool:
        if not section:
            return True
        normalized = section.strip().lower().lstrip("&")
        return name.lower().lstrip("&") == normalized

    filtered = {k: v for k, v in sections.items() if match_section(k)}
    if not filtered:
        raise typer.BadParameter(
            f"Section '{section}' not found for module '{module}'. "
            f"Available: {', '.join(sections)}"
        )

    typer.echo(f"Documentation: {module_entry.get('doc_url')}")
    for sec_name, params in filtered.items():
        typer.echo(f"\n{sec_name}:")
        for param in params:
            typer.echo(f"  - {param}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()

