"""
Typer-based CLI for QuantumVITAS.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

import yaml

import typer

from quantumvitas.analysis import bands as bands_analysis
from quantumvitas.analysis import dos as dos_analysis
from quantumvitas.analysis import energy as energy_analysis
from quantumvitas.data import load_qe_parameter_map
from quantumvitas.engine.registry import create_default_registry
from quantumvitas.project.model import Project
from quantumvitas.workflow.runner import WorkflowRunner
from quantumvitas.workflow.workflow import Workflow
from quantumvitas.workflow.input_runner import run_input_step, detect_project_root

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


@app.command("run-step")
def run_step_command(
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

    result, prepared = run_input_step(
        engine=engine.backend,
        input_file=input_file.resolve(),
        working_dir=workdir,
        project_root=project_root,
        step_type=None,
    )

    typer.echo(f"Step finished: {result.step_type} -> {result.output_file}")
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

