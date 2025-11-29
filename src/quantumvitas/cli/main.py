"""
Typer-based CLI for QuantumVITAS.
"""

from __future__ import annotations

import ast
import shlex
import copy
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import os
from typing import Any, Dict, List, Optional, Sequence, TYPE_CHECKING

import yaml

import typer
from pymatgen.core import Structure as PMGStructure

from quantumvitas.analysis import bands as bands_analysis
from quantumvitas.analysis import dos as dos_analysis
from quantumvitas.analysis import energy as energy_analysis
from quantumvitas.core.resources import (
    ensure_relative_path,
    generate_resource_id,
    generate_unique_name_and_slug,
    meta_from_name,
    slugify,
)
from quantumvitas.data import load_qe_parameter_map
from quantumvitas.core.engines.base import EngineConfig
from quantumvitas.engine.registry import create_default_registry
from quantumvitas.project.model import Project
from quantumvitas.workflow.runner import WorkflowRunner
from quantumvitas.workflow.workflow import Workflow
from quantumvitas.workflow.types import StepMode, StepStatus
from quantumvitas.workflow.input_runner import (
    ParameterOverride,
    apply_card_overrides_to_qe_input,
    apply_species_overrides_to_qe_input,
    detect_project_root,
    run_input_step,
)
from quantumvitas.workflow.structure_steps import (
    StructureStepSpec,
    generate_qe_input_from_spec,
    generate_qe_input_from_structure,
)
from quantumvitas.io import QEInputGenerator, read_structure, write_structure
from quantumvitas.io.model import QECardType
from quantumvitas.io.parser.qe_parser import QEInputParser

if TYPE_CHECKING:
    from pymatgen.core import Structure as PMGStructure


@dataclass(slots=True)
class ParsedOverrides:
    parameters: List[ParameterOverride]
    card_overrides: Dict[str, Dict[str, Any]]
    species_overrides: Dict[str, Dict[str, Any]]

    def has_any(self) -> bool:
        return bool(self.parameters or self.card_overrides or self.species_overrides)


app = typer.Typer(help="QuantumVITAS CLI")
init_app = typer.Typer(help="Initialize QuantumVITAS resources.", no_args_is_help=True)
rename_app = typer.Typer(help="Rename existing resources.", no_args_is_help=True)
delete_app = typer.Typer(help="Move resources to trash or purge trash.", no_args_is_help=True)
configure_app = typer.Typer(help="Configure resources.", no_args_is_help=True)
run_app = typer.Typer(
    help="Run QE targets.",
    invoke_without_command=True,
    no_args_is_help=False,
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)

app.add_typer(init_app, name="init")
app.add_typer(rename_app, name="rename")
app.add_typer(delete_app, name="delete")
app.add_typer(configure_app, name="configure")
app.add_typer(run_app, name="run")


def _resolve_project_root(start: Optional[Path] = None) -> Path:
    start_path = Path(start or Path.cwd()).resolve()
    current = start_path
    while current != current.parent:
        if (current / "project.qv.yml").exists():
            return current
        current = current.parent
    raise typer.BadParameter("Unable to locate project.qv.yml. Use --project or run inside a project root.")


def _maybe_project_root(path: Optional[Path]) -> Optional[Path]:
    if path:
        return Path(path).expanduser().resolve()
    try:
        return _resolve_project_root()
    except typer.BadParameter:
        return None


def _ensure_empty_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _next_project_directory(base_dir: Path, prefix: str = "project") -> Path:
    index = 1
    while True:
        candidate = base_dir / f"{prefix}{index}"
        if not candidate.exists():
            return candidate
        index += 1


def _determine_project_directory(
    *,
    base_dir: Path,
    path_option: Optional[Path],
    name_option: Optional[str],
) -> Path:
    if path_option:
        resolved_path = Path(path_option).expanduser().resolve()
    else:
        resolved_path = None

    slug = slugify(name_option) if name_option else None
    if path_option and name_option:
        if not slug:
            raise typer.BadParameter("Name must contain at least one alphanumeric character.")
        return resolved_path / slug
    if path_option:
        return resolved_path
    if name_option:
        if not slug:
            raise typer.BadParameter("Name must contain at least one alphanumeric character.")
        return (base_dir / slug).resolve()
    return _next_project_directory(base_dir)


def _derive_step_identity(base_name: str, existing_ids: Sequence[str]) -> tuple[str, str]:
    preferred = (base_name or "step").strip() or "step"
    slug_candidate = slugify(preferred)
    display = preferred
    occupied = {value.lower() for value in existing_ids if value}
    suffix = 2
    while slug_candidate.lower() in occupied:
        display = f"{preferred}-{suffix}"
        slug_candidate = slugify(display)
        suffix += 1
    return display, slug_candidate


def _resolve_structure_reference(
    identifier: str, project_root: Optional[Path], config: Optional[dict]
) -> str:
    if project_root and config is not None:
        try:
            entry = _find_structure_entry(config, identifier, project_root)
            meta = entry.get("meta") or {}
            return meta.get("slug") or entry.get("name") or identifier
        except typer.BadParameter:
            pass

    candidate = Path(identifier)
    if candidate.exists():
        if project_root:
            try:
                return ensure_relative_path(candidate, base=project_root)
            except ValueError:
                return candidate.as_posix()
        return candidate.as_posix()
    return identifier


def _detect_enclosing_workflow(
    project_root: Path, current_dir: Path, workflows: Sequence[dict]
) -> Optional[str]:
    try:
        current_dir.relative_to(project_root)
    except ValueError:
        return None

    for entry in workflows:
        rel_path = entry.get("path") or (entry.get("meta") or {}).get("path")
        if not rel_path:
            continue
        workflow_dir = (project_root / rel_path).resolve()
        if current_dir == workflow_dir or current_dir.is_relative_to(workflow_dir):
            meta = entry.get("meta") or {}
            return meta.get("slug") or entry.get("name")
    return None


def _move_to_trash(target: Path, trash_dir: Path) -> Path:
    trash_dir = trash_dir.resolve()
    trash_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    destination = trash_dir / f"{target.name}_{timestamp}"
    idx = 1
    while destination.exists():
        destination = trash_dir / f"{target.name}_{timestamp}_{idx}"
        idx += 1
    shutil.move(str(target), str(destination))
    return destination


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


CARD_KEYWORDS = {
    "k_points",
    "cell_parameters",
    "atomic_positions",
    "atomic_species",
}

STRUCTURAL_SYSTEM_KEYS = {"ibrav", "nat", "ntyp"}
STRUCTURAL_LATTICE_KEYS = {"a", "alat", "b", "c", "cosab", "cosac", "cosbc"}


@dataclass(slots=True)
class ParsedOverrides:
    parameters: List[ParameterOverride]
    card_overrides: Dict[str, Dict[str, Any]]
    species_overrides: Dict[str, Dict[str, Any]]

    def has_any(self) -> bool:
        return bool(self.parameters or self.card_overrides or self.species_overrides)


def _parse_override_args(extra_args: List[str]) -> ParsedOverrides:
    """
    Convert unknown CLI arguments (e.g., --ecutwfc=40) into overrides.
    """

    parameter_map: dict[str, ParameterOverride] = {}
    card_overrides: Dict[str, Dict[str, Any]] = {}
    species_overrides: Dict[str, Dict[str, Any]] = {}
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

        lower_key = key.lower()
        if lower_key.startswith("card."):
            _assign_card_override(card_overrides, key[5:], value or "")
            i += 1
            continue
        if lower_key.startswith("species."):
            _assign_species_override(species_overrides, key[8:], value or "")
            i += 1
            continue

        section_hint: Optional[str] = None
        param_name = key
        if "." in key:
            section_hint, param_name = key.split(".", 1)

        normalized_param = param_name.replace("-", "_")
        normalized_section = section_hint.replace("-", "_") if section_hint else None

        if not normalized_section and normalized_param.lower() in CARD_KEYWORDS:
            _assign_card_override(card_overrides, normalized_param, value or "")
            i += 1
            continue

        parameter_map[normalized_param.lower()] = ParameterOverride(
            name=normalized_param,
            value=_coerce_override_value(value or ""),
            section=normalized_section,
        )
        i += 1

    return ParsedOverrides(
        parameters=list(parameter_map.values()),
        card_overrides=card_overrides,
        species_overrides=species_overrides,
    )


def _assign_card_override(
    card_overrides: Dict[str, Dict[str, Any]],
    path: str,
    raw_value: str,
) -> None:
    card_name, _, remainder = path.partition(".")
    card_key = card_name.strip().upper()
    if not card_key:
        raise typer.BadParameter("Card overrides must specify a card name.")
    attr = remainder.strip().lower() if remainder else None
    target = card_overrides.setdefault(card_key, {})

    if attr in {None, "", "data"}:
        payload = _coerce_override_value(raw_value)
        _merge_card_payload(target, payload)
        return

    if attr == "option":
        target["option"] = str(_coerce_cli_scalar(raw_value))
        return

    if attr and (attr.startswith("rows.") or attr.startswith("row")):
        row_key = attr.split(".", 1)[1] if attr.startswith("rows.") else attr
        if not row_key:
            raise typer.BadParameter("Row overrides must specify a row key.")
        rows = target.setdefault("rows", {})
        rows[row_key] = _parse_row_tokens(raw_value)
        return

    raise typer.BadParameter(
        f"Unsupported card attribute '{attr}'. Use '.option' or '.data'."
    )


def _merge_card_payload(target: Dict[str, Any], payload: Any) -> None:
    interpreted = None
    if isinstance(payload, str):
        interpreted = _interpret_card_compact_string(payload)
    elif isinstance(payload, list):
        interpreted = _interpret_card_compact_list(payload)
    if interpreted is not None:
        if interpreted.get("option"):
            target["option"] = interpreted["option"]
        if interpreted.get("data") is not None:
            target["data"] = interpreted["data"]
        return

    if isinstance(payload, dict):
        if "option" in payload:
            target["option"] = str(payload["option"])
        if "data" in payload:
            target["data"] = _normalize_card_data(payload["data"])
        return
    target["data"] = _normalize_card_data(payload)


def _interpret_card_compact_string(value: str) -> Optional[dict[str, Any]]:
    raw = value.strip()
    if not raw:
        return {"data": []}
    if ":" in raw:
        option, remainder = raw.split(":", 1)
        option = option.strip()
        if option and any(ch.isalpha() for ch in option):
            data_row = _parse_row_tokens(remainder)
            return {"option": option, "data": [data_row]}
    return None


def _interpret_card_compact_list(values: list[Any]) -> Optional[dict[str, Any]]:
    if not values:
        return {"data": []}
    first = values[0]
    if isinstance(first, str) and ":" in first:
        option, remainder = first.split(":", 1)
        option = option.strip()
        if option and any(ch.isalpha() for ch in option):
            row = [_coerce_cli_scalar(remainder)]
            for item in values[1:]:
                if isinstance(item, str):
                    row.append(_coerce_cli_scalar(item))
                else:
                    row.append(item)
            return {"option": option, "data": [row]}
    return None


def _assign_species_override(
    species_overrides: Dict[str, Dict[str, Any]],
    path: str,
    raw_value: str,
) -> None:
    symbol, _, field = path.partition(".")
    symbol_key = symbol.strip()
    if not symbol_key:
        raise typer.BadParameter("Species symbol cannot be empty.")
    attr = (field or "pseudopot").strip().lower()
    if attr not in {"mass", "pseudopot"}:
        raise typer.BadParameter(
            "Species overrides support attributes 'mass' or 'pseudopot'."
        )
    target = species_overrides.setdefault(symbol_key, {})
    target[attr] = _coerce_cli_scalar(raw_value)


def _normalize_card_data(value: Any) -> List[List[Any]]:
    parsed = value
    if isinstance(parsed, str):
        parsed = parsed.strip()
        if parsed.startswith("["):
            try:
                parsed = json.loads(parsed)
            except Exception:
                pass
    if isinstance(parsed, list):
        if parsed and isinstance(parsed[0], (list, tuple)):
            rows = [list(row) for row in parsed]
        else:
            rows = [list(parsed)]
    elif isinstance(parsed, tuple):
        rows = [list(parsed)]
    else:
        rows = [[parsed]]

    normalized: List[List[Any]] = []
    for row in rows:
        if isinstance(row, str):
            normalized.append(_parse_row_tokens(row))
        elif isinstance(row, (list, tuple)):
            normalized.append([_coerce_cli_scalar(str(item)) for item in row])
        else:
            normalized.append([_coerce_cli_scalar(str(row))])
    return normalized


def _parse_row_tokens(raw: str) -> List[Any]:
    value = raw.strip()
    if not value:
        return []
    if value.startswith("["):
        try:
            data = json.loads(value)
            if isinstance(data, list):
                return [_coerce_cli_scalar(str(item)) for item in data]
        except Exception:
            pass
    tokens = [token for token in value.replace(",", " ").split() if token]
    return [_coerce_cli_scalar(token) for token in tokens]


def _coerce_cli_scalar(value: str) -> Any:
    stripped = value.strip()
    try:
        if "." in stripped or "e" in stripped.lower():
            return float(stripped)
        return int(stripped)
    except ValueError:
        pass
    lower = stripped.lower()
    if lower in {"true", ".true.", "t"}:
        return True
    if lower in {"false", ".false.", "f"}:
        return False
    return stripped


def _render_override_summary(bundle: ParsedOverrides) -> str:
    parts: list[str] = []
    for override in bundle.parameters:
        prefix = f"{override.section}." if override.section else ""
        parts.append(f"{prefix}{override.name}={override.value}")
    for card_name, payload in bundle.card_overrides.items():
        entry = {"card": card_name}
        if "option" in payload:
            entry["option"] = payload["option"]
        if "data" in payload:
            entry["rows"] = len(payload["data"])
        parts.append(f"CARD.{card_name}({json.dumps(entry)})")
    for symbol, overrides in bundle.species_overrides.items():
        for field, val in overrides.items():
            parts.append(f"SPECIES.{symbol}.{field}={val}")
    return ", ".join(parts)


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



@init_app.command("project")
def init_project_command(
    name: Optional[str] = typer.Option(None, "--name", help="Project display name"),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        help="Directory where the project should be created (defaults to ./projectN).",
    ),
    template: Optional[str] = typer.Option(
        None, "--template", help="Project template (reserved for future use)."
    ),
) -> None:
    """
    Scaffold a new QuantumVITAS project skeleton (no workflows by default).
    """

    if template:
        typer.secho(
            "--template is not implemented yet; creating an empty project skeleton.",
            fg=typer.colors.YELLOW,
        )

    base_dir = Path.cwd()
    project_dir = _determine_project_directory(
        base_dir=base_dir, path_option=path, name_option=name
    )
    project_dir = project_dir.resolve()
    if project_dir.exists() and any(project_dir.iterdir()):
        raise typer.BadParameter(
            f"Destination '{project_dir}' already exists and is not empty."
        )
    project_dir.mkdir(parents=True, exist_ok=True)

    project_name = name or project_dir.name
    project_meta = meta_from_name("project", name=project_name, path=".")

    project_config = {
        "project": {
            "name": project_meta.name,
            "meta": project_meta.to_dict(),
            "structures_dir": "structures",
            "workflows_dir": "workflows",
        },
        "workflows": [],
        "structures": [],
        "settings": {},
    }

    (project_dir / "structures").mkdir(parents=True, exist_ok=True)
    (project_dir / "workflows").mkdir(parents=True, exist_ok=True)
    (project_dir / "project.qv.yml").write_text(
        yaml.safe_dump(project_config, sort_keys=False)
    )

    typer.secho(f"Project created at {project_dir}", fg=typer.colors.GREEN)


@init_app.command("workflow")
def init_workflow_command(
    workflow_id: str = typer.Argument(..., help="Workflow identifier to create"),
    structure: str = typer.Option(
        ..., "--structure", help="Structure id registered in the project"
    ),
    parent: List[str] = typer.Option(
        [],
        "--parent",
        help="Workflow ids/slugs that must finish before this workflow (metadata only).",
    ),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
) -> None:
    """
    Scaffold a workflow folder with workflow.yaml and no pre-populated steps.
    """

    project_root = (project or _resolve_project_root()).resolve()
    config = _load_project_config(project_root)
    workflows_section = config.setdefault("workflows", [])
    existing_slugs = {
        (entry.get("meta") or {}).get("slug") or slugify(entry.get("name") or "")
        for entry in workflows_section
    }

    workflow_slug = slugify(workflow_id)
    if workflow_slug in existing_slugs:
        raise typer.BadParameter(
            f"Workflow '{workflow_id}' already exists. Use qv configure workflow to modify it."
        )

    _find_structure_entry(config, structure, project_root)

    workflow_dir = (project_root / "workflows" / workflow_slug).resolve()
    if workflow_dir.exists():
        raise typer.BadParameter(
            f"Workflow directory '{workflow_dir}' already exists. Remove it or choose another name."
        )
    raw_dir = workflow_dir / "raw"
    steps_dir = workflow_dir / "steps"
    raw_dir.mkdir(parents=True, exist_ok=True)
    steps_dir.mkdir(parents=True, exist_ok=True)

    workflow_payload = {
        "id": workflow_slug,
        "mode": "normal",
        "workflow": {"working_dir": "raw", "structure": structure},
        "steps": [],
    }
    (workflow_dir / "workflow.yaml").write_text(yaml.safe_dump(workflow_payload, sort_keys=False))

    rel_path = ensure_relative_path(workflow_dir, base=project_root)
    workflow_meta = meta_from_name("workflow", name=workflow_id, path=rel_path).to_dict()
    if parent:
        workflow_meta["parents"] = parent

    workflows_section.append(
        {
            "name": workflow_id,
            "path": rel_path,
            "meta": workflow_meta,
        }
    )
    _save_project_config(project_root, config)

    typer.secho(f"Workflow '{workflow_id}' created at {workflow_dir}", fg=typer.colors.GREEN)



@init_app.command(
    "step",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def init_step_command(
    ctx: typer.Context,
    structure: str = typer.Argument(..., help="Structure id registered in the project"),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    workflow: Optional[str] = typer.Option(
        None, "--workflow", help="Workflow id/slug to attach this step to"
    ),
    step_type: str = typer.Option("scf", "--type", help="QE calculation type"),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        help="Step display name/slug (defaults to step type or next available value)",
    ),
    index: Optional[int] = typer.Option(
        None,
        "--index",
        help="Insert position when attaching to a workflow (0-indexed, defaults to append).",
    ),
) -> None:
    """Create a StructureStepSpec YAML file and optionally attach it to a workflow."""

    project_root = _maybe_project_root(project)
    bundle = _parse_override_args(ctx.args)
    if bundle.has_any():
        typer.echo(f"Applying overrides: {_render_override_summary(bundle)}")

    if project_root:
        project_root = project_root.resolve()
        config = _load_project_config(project_root)
    else:
        config = {"structures": [], "workflows": []}

    workflow_entry = None
    workflow_dir: Optional[Path] = None
    workflow_steps: list[dict] | None = None
    workflow_data = None
    existing_step_ids: list[str] = []

    if workflow:
        if not project_root:
            raise typer.BadParameter("Specify --project when attaching to a workflow.")
        workflow_entry = _find_workflow_entry(config, workflow, project_root)
    elif project_root:
        detected = _detect_enclosing_workflow(
            project_root, Path.cwd().resolve(), config.get("workflows", [])
        )
        if detected:
            workflow_entry = _find_workflow_entry(config, detected, project_root)

    if workflow_entry and project_root:
        workflow_dir = _workflow_directory(project_root, workflow_entry)
        workflow_yaml = workflow_dir / "workflow.yaml"
        if not workflow_yaml.exists():
            raise typer.BadParameter(f"workflow.yaml not found under {workflow_dir}")
        workflow_data = yaml.safe_load(workflow_yaml.read_text()) or {}
        workflow_steps = workflow_data.setdefault("steps", [])
        existing_step_ids = [step.get("id") for step in workflow_steps if step.get("id")]

    step_display_name, step_slug = _derive_step_identity(name or step_type, existing_step_ids)

    if workflow_dir is not None:
        spec_path = (workflow_dir / "steps" / f"{step_slug}.step.yaml").resolve()
    else:
        spec_path = (Path.cwd() / f"{step_slug}.step.yaml").resolve()

    if spec_path.exists():
        raise typer.BadParameter(
            f"Step spec '{spec_path}' already exists. Use qv configure step to modify it."
        )

    spec_path.parent.mkdir(parents=True, exist_ok=True)
    structure_value = _resolve_structure_reference(
        structure, project_root, config if project_root else None
    )
    spec = StructureStepSpec(
        meta=meta_from_name("step", name=step_display_name, path=""),
        structure=structure_value,
        step_type=step_type,
        parameters=_overrides_to_parameter_dict(bundle.parameters),
        cards=bundle.card_overrides or {},
        species_overrides=bundle.species_overrides or {},
    )
    _write_step_spec(spec_path, spec, project_root=project_root)

    if workflow_entry and workflow_steps is not None and workflow_data is not None:
        assert workflow_dir is not None
        rel_step_path = ensure_relative_path(spec_path, base=workflow_dir)
        insertion_index = (
            max(0, min(len(workflow_steps), index))
            if index is not None
            else len(workflow_steps)
        )
        workflow_steps.insert(
            insertion_index,
            {
                "id": step_slug,
                "step_file": rel_step_path,
            },
        )
        workflow_yaml = workflow_dir / "workflow.yaml"
        workflow_yaml.write_text(yaml.safe_dump(workflow_data, sort_keys=False))
        typer.echo(
            f"Workflow '{_entry_display_name(workflow_entry)}' updated with step id '{step_slug}'."
        )

    typer.echo(f"Step spec created at {spec_path}")


@app.command("import-structure")
def import_structure_command(
    structure_file: Path = typer.Argument(
        ..., help="Input structure file (.cif, POSCAR, QE .in, etc.)"
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        "--id",
        help="Structure display name (defaults to formula or file stem)",
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
    config = _load_project_config(project_root)
    structures_section = config.setdefault("structures", [])
    existing_slugs = _collect_slugs(structures_section)

    user_name = name.strip() if name else None
    if user_name:
        candidate_slug = slugify(user_name)
        if candidate_slug in existing_slugs:
            raise typer.BadParameter(
                f"Structure name '{user_name}' conflicts with an existing entry."
            )
        structure_name = user_name
        structure_slug = candidate_slug
    else:
        base_name = _suggest_structure_name(struct, structure_file)
        structure_name, structure_slug = generate_unique_name_and_slug(
            kind="structure",
            preferred_name=base_name,
            existing_slugs=existing_slugs,
        )

    structures_dir = project_root / "structures"
    structures_dir.mkdir(parents=True, exist_ok=True)
    ext = output_format.lower()
    out_path = (structures_dir / f"{structure_slug}.{ext}").resolve()
    write_rel = ensure_relative_path(out_path, base=project_root)

    metadata = meta_from_name("structure", name=structure_name, path=write_rel)
    write_structure(struct, out_path, format=output_format, metadata=metadata)

    structures_section.append(
        {
            "name": structure_name,
            "file": write_rel,
            "format": output_format.lower(),
            "meta": metadata.to_dict(),
        }
    )
    _save_project_config(project_root, config)

    typer.secho(
        f"Imported structure '{structure_name}' -> {write_rel}", fg=typer.colors.GREEN
    )


@app.command("detect-qe")
def detect_qe(
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Explicit QE home directory (overrides auto-detection).",
    )
) -> None:
    """
    Report QE installation details (qe_home, bin directory, test-suite, executables).
    """
    config = None
    if path:
        try:
            config = EngineConfig(name="qe", qe_home=path)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
    registry = create_default_registry(config)
    engine = registry.get("qe")
    info = _collect_qe_detection_info(engine.backend)

    typer.echo("Quantum ESPRESSO detection summary")
    typer.echo("-" * 40)
    typer.echo(f"Environment QE_HOME  : {info['env_home'] or 'not set'}")
    typer.echo(f"Engine-reported home : {info['engine_home'] or 'not detected'}")
    typer.echo(f"`pw.x` on PATH       : {info['which_home'] or 'not found'}")
    typer.echo(f"Resolved QE home     : {info['qe_home'] or 'not resolved'}")
    typer.echo(f"bin directory        : {info['bin_dir'] or 'not resolved'}")
    typer.echo(f"test-suite directory : {info['test_suite'] or 'not found'}")
    typer.echo("")
    typer.echo("Key executables:")
    for exe_name, exe_path in info["executables"].items():
        typer.echo(f"  {exe_name:<8} -> {exe_path or 'not found'}")


@run_app.command(
    "step",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def run_step_command(
    ctx: typer.Context,
    target: Path = typer.Argument(
        ..., help="QE input (.in) or step spec (.yaml) to execute"
    ),
    working_dir: Optional[Path] = typer.Option(
        None, "--workdir", help="Temporary working directory"
    ),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (for pseudo/pseudo_dir handling)"
    ),
) -> None:
    """
    Run a single QE input file or step spec in isolation.
    """
    registry = create_default_registry()
    engine = registry.get("qe")

    workdir = working_dir or (Path("temp") / "cli_outputs" / target.stem)
    workdir = workdir.resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    if project:
        project_root = project.resolve()
    else:
        try:
            project_root = _resolve_project_root()
        except typer.BadParameter:
            project_root = detect_project_root(target.parent)

    bundle = _parse_override_args(ctx.args)
    if bundle.has_any():
        typer.echo(f"Applying overrides: {_render_override_summary(bundle)}")

    if target.suffix.lower() in {".yaml", ".yml"}:
        result, prepared, generated_input = _execute_step_spec_path(
            spec_path=target,
            bundle=bundle,
            project_root=project_root,
            working_dir=workdir,
            engine_backend=engine.backend,
        )
        typer.echo(
            f"Step finished: {result.step_type} -> {result.output_file} "
            f"(input {generated_input})"
        )
        typer.echo(f"Working dir: {prepared.working_dir}")
        return

    if not target.exists():
        raise typer.BadParameter(f"Input file '{target}' not found.")

    result, prepared = run_input_step(
        engine=engine.backend,
        input_file=target.resolve(),
        working_dir=workdir,
        project_root=project_root,
        step_type=None,
        parameter_overrides=bundle.parameters or None,
        card_overrides=bundle.card_overrides or None,
        species_overrides=bundle.species_overrides or None,
    )

    typer.echo(f"Step finished: {result.step_type} -> {result.output_file}")
    typer.echo(f"Working dir: {prepared.working_dir}")


@run_app.command(
    "structure",
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

    bundle = _parse_override_args(ctx.args)
    if bundle.has_any():
        typer.echo(f"Applying overrides: {_render_override_summary(bundle)}")

    qe_input = generate_qe_input_from_structure(
        structure=struct,
        step_type=step_type,
        parameter_overrides=bundle.parameters,
    )
    apply_card_overrides_to_qe_input(qe_input, bundle.card_overrides)
    apply_species_overrides_to_qe_input(qe_input, bundle.species_overrides)

    generated_name = input_name or f"{struct_name}_{step_type}.pw.in"
    generated_input = workdir / generated_name
    QEInputGenerator.write_file(qe_input, generated_input)

    result, prepared = run_input_step(
        engine=engine.backend,
        input_file=generated_input,
        working_dir=workdir,
        project_root=project_root,
        step_type=None,
        parameter_overrides=None,
        card_overrides=None,
        species_overrides=None,
    )

    typer.echo(
        f"Structure run finished: {result.step_type} -> {result.output_file} "
        f"(input {generated_input})"
    )
    typer.echo(f"Working dir: {prepared.working_dir}")


@app.command("list")
def list_resources(
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show IDs"),
) -> None:
    """
    Display project resources (structures/workflows) as a tree.
    """

    project_root = project or _resolve_project_root()
    proj = Project.open(project_root)

    typer.echo(f"Project: {proj.meta.name} [{proj.meta.slug}] ({proj.root})")
    if verbose:
        typer.echo(f"  id: {proj.meta.id}")
    typer.echo("\nStructures:")
    structures = sorted(proj.structures.values(), key=lambda r: r.name)
    if not structures:
        typer.echo("  (none)")
    for ref in structures:
        line = f"  - {ref.name} [{ref.meta.slug}] -> {ref.meta.path}"
        if verbose:
            line += f" (id: {ref.meta.id})"
        typer.echo(line)

    typer.echo("\nWorkflows:")
    workflows = sorted(proj.workflows.values(), key=lambda r: r.name)
    if not workflows:
        typer.echo("  (none)")
    for wf in workflows:
        line = f"  - {wf.name} [{wf.meta.slug}] -> {wf.meta.path}"
        if verbose:
            line += f" (id: {wf.meta.id})"
        typer.echo(line)
        step_summaries = _workflow_step_summaries(wf.path)
        if not step_summaries:
            typer.echo("    (no steps)")
            continue
        for step_id, rel_path, step_meta in step_summaries:
            slug_display = step_meta.slug if step_meta else "-"
            step_line = f"    - {step_id} [{slug_display}] -> {rel_path or '(inline)'}"
            if verbose and step_meta:
                step_line += f" (id: {step_meta.id})"
            elif rel_path is None:
                step_line += " (missing step_file)"
            typer.echo(step_line)


def _workflow_step_summaries(workflow_dir: Path) -> list[tuple[str, Optional[str], Optional[ResourceMeta]]]:
    workflow_yaml = workflow_dir / "workflow.yaml"
    if not workflow_yaml.exists():
        return []
    try:
        data = yaml.safe_load(workflow_yaml.read_text()) or {}
    except Exception:
        return []
    summaries: list[tuple[str, Optional[str], Optional[ResourceMeta]]] = []
    for step_entry in data.get("steps", []):
        step_id = step_entry.get("id") or "(unnamed)"
        rel_path = step_entry.get("step_file")
        step_meta: Optional[ResourceMeta] = None
        if rel_path:
            spec_path = (workflow_dir / rel_path).resolve()
            if spec_path.exists():
                try:
                    spec = StructureStepSpec.from_yaml(spec_path)
                    step_meta = spec.meta
                except Exception:
                    step_meta = None
        summaries.append((step_id, rel_path, step_meta))
    return summaries


@rename_app.command("structure")
def rename_structure_command(
    identifier: str = typer.Argument(..., help="Structure name/slug/path"),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    name: Optional[str] = typer.Option(None, "--name", help="New display name"),
    slug: Optional[str] = typer.Option(None, "--slug", help="Custom slug"),
    path: Optional[Path] = typer.Option(
        None, "--path", help="New relative path for the structure file"
    ),
) -> None:
    """
    Rename a structure resource (updates name/slug/path).
    """

    project_root = project or _resolve_project_root()
    config = _load_project_config(project_root)
    entry = _find_structure_entry(config, identifier, project_root)

    _apply_structure_rename(
        project_root=project_root,
        config=config,
        entry=entry,
        new_name=name,
        new_slug=slug,
        new_path=path,
    )
    _save_project_config(project_root, config)

    typer.secho("Structure updated successfully.", fg=typer.colors.GREEN)


@rename_app.command("workflow")
def rename_workflow_command(
    identifier: str = typer.Argument(..., help="Workflow name/slug/path"),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    name: Optional[str] = typer.Option(None, "--name", help="New workflow name"),
    slug: Optional[str] = typer.Option(None, "--slug", help="Custom slug"),
    path: Optional[Path] = typer.Option(
        None, "--path", help="New relative path for the workflow directory"
    ),
) -> None:
    """
    Rename a workflow resource (updates name/slug/path).
    """

    project_root = project or _resolve_project_root()
    config = _load_project_config(project_root)
    entry = _find_workflow_entry(config, identifier, project_root)

    _apply_workflow_rename(
        project_root=project_root,
        config=config,
        entry=entry,
        new_name=name,
        new_slug=slug,
        new_path=path,
    )
    _save_project_config(project_root, config)

    typer.secho("Workflow updated successfully.", fg=typer.colors.GREEN)


@rename_app.command("project")
def rename_project_command(
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    name: Optional[str] = typer.Option(None, "--name", help="New project display name"),
    slug: Optional[str] = typer.Option(None, "--slug", help="Custom slug"),
    path: Optional[Path] = typer.Option(
        None, "--path", help="Move the entire project directory to this new location"
    ),
) -> None:
    """
    Rename or relocate the current project.
    """

    project_root = (project or _resolve_project_root()).resolve()
    config = _load_project_config(project_root)

    updated = False
    project_section = config.setdefault("project", {})
    meta = project_section.setdefault("meta", {})

    original_slug = meta.get("slug")
    slug_changed = False

    if name or slug:
        current_name = project_section.get("name") or meta.get("name") or "project"
        next_name = name or current_name
        slug_source = slug or next_name
        next_slug = slugify(slug_source)
        if not next_slug:
            raise typer.BadParameter("Slug cannot be empty.")
        project_section["name"] = next_name
        meta["name"] = next_name
        meta["slug"] = next_slug
        slug_changed = next_slug != original_slug
        updated = True

    destination_root = project_root
    if path is not None:
        destination_root = Path(path).expanduser().resolve()
        if destination_root.exists():
            raise typer.BadParameter(f"Destination '{destination_root}' already exists.")
        destination_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(project_root), str(destination_root))
        project_root = destination_root
        updated = True
    elif slug_changed and project_root.name != meta.get("slug"):
        destination_root = project_root.parent / meta["slug"]
        if destination_root.exists():
            raise typer.BadParameter(f"Destination '{destination_root}' already exists.")
        destination_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(project_root), str(destination_root))
        project_root = destination_root
        updated = True

    if updated:
        meta.setdefault("path", ".")
        _save_project_config(project_root, config)
        typer.secho("Project metadata updated.", fg=typer.colors.GREEN)
        if path is not None:
            typer.secho(f"Project moved to {project_root}", fg=typer.colors.GREEN)
    else:
        typer.secho("Nothing to update.", fg=typer.colors.YELLOW)


@rename_app.command("step")
def rename_step_command(
    workflow: str = typer.Argument(..., help="Workflow name/slug/path containing the step"),
    step_id: str = typer.Argument(..., help="Existing step id within the workflow"),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    new_id: Optional[str] = typer.Option(
        None, "--id", help="New step id (must be unique within the workflow)"
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        help="Rename or relocate the step spec file (relative to the workflow directory unless absolute).",
    ),
) -> None:
    """
    Rename a workflow step or move its spec file.
    """

    project_root = (project or _resolve_project_root()).resolve()
    config = _load_project_config(project_root)
    workflow_entry = _find_workflow_entry(config, workflow, project_root)
    workflow_path = workflow_entry.get("path") or (workflow_entry.get("meta") or {}).get("path")
    if not workflow_path:
        raise typer.BadParameter("Workflow entry is missing a path.")

    workflow_dir = (project_root / workflow_path).resolve()
    workflow_yaml = workflow_dir / "workflow.yaml"
    if not workflow_yaml.exists():
        raise typer.BadParameter(f"workflow.yaml not found at {workflow_yaml}")

    data = yaml.safe_load(workflow_yaml.read_text()) or {}
    steps: list[dict] = data.get("steps") or []
    target_step = next((step for step in steps if step.get("id") == step_id), None)
    if not target_step:
        raise typer.BadParameter(
            f"Step '{step_id}' not found in workflow '{workflow_entry.get('name')}'."
        )

    if new_id:
        if any(step.get("id") == new_id for step in steps if step is not target_step):
            raise typer.BadParameter(
                f"Step id '{new_id}' already exists in workflow '{workflow_entry.get('name')}'."
            )
        target_step["id"] = new_id

    source_rel = target_step.get("step_file")
    if not source_rel:
        raise typer.BadParameter("Step entry is missing its step_file.")
    source_path = (workflow_dir / source_rel).resolve()
    if not source_path.exists():
        raise typer.BadParameter(f"Step file '{source_rel}' does not exist.")
    spec = StructureStepSpec.from_yaml(source_path)

    destination_path = source_path
    if path is not None:
        destination_path = Path(path)
        if not destination_path.is_absolute():
            destination_path = (workflow_dir / destination_path).resolve()
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_path), str(destination_path))
        target_step["step_file"] = ensure_relative_path(destination_path, base=workflow_dir)
    elif new_id:
        rel_source = Path(source_rel)
        new_filename = rel_source.with_name(f"{new_id}.step.yaml")
        destination_path = (workflow_dir / new_filename).resolve()
        if destination_path.exists():
            raise typer.BadParameter(
                f"Step file '{new_filename}' already exists. Use --path to pick a custom filename."
            )
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_path), str(destination_path))
        target_step["step_file"] = ensure_relative_path(destination_path, base=workflow_dir)

    step_file_rel = target_step.get("step_file")
    if step_file_rel:
        spec_path = (workflow_dir / step_file_rel).resolve()
        relative_project = ensure_relative_path(spec_path, base=project_root)
        spec.meta = spec.meta.with_updates(
            name=new_id or spec.meta.name,
            path=relative_project,
        )
        spec_path.write_text(yaml.safe_dump(spec.to_dict(), sort_keys=False))

    workflow_yaml.write_text(yaml.safe_dump(data, sort_keys=False))
    typer.secho("Step updated successfully.", fg=typer.colors.GREEN)


@delete_app.command("structure")
def delete_structure_command(
    identifier: str = typer.Argument(..., help="Structure name/slug/path to delete"),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Delete even if workflows reference the structure (leaves broken references).",
    ),
    cascade: bool = typer.Option(
        False,
        "--cascade",
        help="Delete workflows referencing this structure before deleting the structure itself.",
    ),
) -> None:
    """
    Remove a structure entry and move its file (and optionally dependent workflows) to trash.
    """

    project_root = (project or _resolve_project_root()).resolve()
    config = _load_project_config(project_root)
    entry = _find_structure_entry(config, identifier, project_root)
    trash_dir = (project_root / "trash").resolve()

    referencing = _workflows_using_structure(project_root, config, entry)
    if referencing:
        if cascade:
            for wf_entry in list(referencing):
                _delete_workflow_entry(
                    project_root=project_root,
                    config=config,
                    entry=wf_entry,
                    trash_dir=trash_dir,
                    force=True,
                    cascade=True,
                )
        elif not force:
            names = ", ".join(_entry_display_name(wf) for wf in referencing)
            raise typer.BadParameter(
                f"Structure '{_entry_display_name(entry)}' is used by workflows: {names}. "
                "Use --force to remove anyway or --cascade to delete the workflows first."
            )

    file_rel = entry.get("file") or (entry.get("meta") or {}).get("path")
    if file_rel:
        file_path = (project_root / file_rel).resolve()
        if file_path.exists():
            _move_to_trash(file_path, trash_dir)

    structures = config.setdefault("structures", [])
    if entry in structures:
        structures.remove(entry)
    _save_project_config(project_root, config)
    typer.secho(f"Structure '{_entry_display_name(entry)}' moved to trash.", fg=typer.colors.GREEN)


@delete_app.command("workflow")
def delete_workflow_command(
    identifier: str = typer.Argument(..., help="Workflow name/slug/path to delete"),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    force: bool = typer.Option(
        False, "--force", help="Delete even if other workflows depend on this workflow."
    ),
    cascade: bool = typer.Option(
        False,
        "--cascade",
        help="Delete dependent workflows that reference this workflow as a parent.",
    ),
) -> None:
    """
    Remove a workflow entry and move its directory to trash.
    """

    project_root = (project or _resolve_project_root()).resolve()
    config = _load_project_config(project_root)
    entry = _find_workflow_entry(config, identifier, project_root)
    trash_dir = (project_root / "trash").resolve()

    _delete_workflow_entry(
        project_root=project_root,
        config=config,
        entry=entry,
        trash_dir=trash_dir,
        force=force,
        cascade=cascade,
    )
    _save_project_config(project_root, config)
    typer.secho(f"Workflow '{_entry_display_name(entry)}' moved to trash.", fg=typer.colors.GREEN)


@delete_app.command("step")
def delete_step_command(
    workflow: str = typer.Argument(..., help="Workflow name/slug/path containing the step"),
    step_id: str = typer.Argument(..., help="Step id to remove"),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
) -> None:
    """
    Remove a workflow step and move its step spec file to trash.
    """

    project_root = (project or _resolve_project_root()).resolve()
    config = _load_project_config(project_root)
    workflow_entry = _find_workflow_entry(config, workflow, project_root)
    workflow_dir = _workflow_directory(project_root, workflow_entry)
    workflow_yaml = workflow_dir / "workflow.yaml"
    if not workflow_yaml.exists():
        raise typer.BadParameter(f"workflow.yaml not found at {workflow_yaml}")

    data = yaml.safe_load(workflow_yaml.read_text()) or {}
    steps: list[dict] = data.get("steps") or []
    target_step = next((step for step in steps if step.get("id") == step_id), None)
    if not target_step:
        raise typer.BadParameter(f"Step '{step_id}' not found in workflow '{workflow}'.")

    trash_dir = (project_root / "trash").resolve()
    rel_file = target_step.get("step_file")
    if rel_file:
        spec_path = (workflow_dir / rel_file).resolve()
        if spec_path.exists():
            _move_to_trash(spec_path, trash_dir)

    steps.remove(target_step)
    workflow_yaml.write_text(yaml.safe_dump(data, sort_keys=False))
    typer.secho(
        f"Step '{step_id}' removed from workflow '{_entry_display_name(workflow_entry)}'.",
        fg=typer.colors.GREEN,
    )


@delete_app.command("project")
def delete_project_command(
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root to delete (defaults to auto-detect)"
    ),
) -> None:
    """
    Move an entire project directory into the parent trash folder.
    """

    project_root = (project or _resolve_project_root()).resolve()
    original_cwd = Path.cwd().resolve()
    inside_project = original_cwd == project_root or project_root in original_cwd.parents

    if inside_project:
        parent_dir = project_root.parent
        os.chdir(parent_dir)

    trash_dir = (project_root.parent / "trash").resolve()
    destination = _move_to_trash(project_root, trash_dir)
    typer.secho(f"Project moved to {destination}", fg=typer.colors.GREEN)
    if inside_project:
        typer.secho(
            f"Working directory switched to {project_root.parent}", fg=typer.colors.YELLOW
        )


@delete_app.command("trash")
def delete_trash_command(
    project: Optional[Path] = typer.Option(
        None,
        "--project",
        help="Project root whose trash directory should be removed (defaults to auto-detect).",
    ),
    path: Optional[Path] = typer.Option(
        None, "--path", help="Explicit trash directory to remove."
    ),
    parent: bool = typer.Option(
        False,
        "--parent",
        help="Clean the parent-level trash directory (used for deleted projects).",
    ),
) -> None:
    """
    Remove a trash directory.
    """

    if path is not None:
        trash_target = Path(path).expanduser().resolve()
    else:
        base = (project or _resolve_project_root()).resolve()
        trash_target = (base.parent / "trash").resolve() if parent else (base / "trash").resolve()

    if not trash_target.exists():
        typer.secho(f"No trash directory at {trash_target}", fg=typer.colors.YELLOW)
        return

    shutil.rmtree(trash_target)
    typer.secho(f"Removed trash at {trash_target}", fg=typer.colors.GREEN)


@configure_app.command(
    "step",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def configure_step_command(
    ctx: typer.Context,
    step_file: Path = typer.Argument(..., help="Step YAML file to modify"),
    remove: bool = typer.Option(
        False, "--remove", help="Remove the specified parameters instead of setting them"
    ),
) -> None:
    """
    Modify parameters stored in a StructureStepSpec YAML file.
    """

    bundle = _parse_override_args(ctx.args)
    if not bundle.has_any():
        raise typer.BadParameter("Provide at least one override.")

    try:
        spec = StructureStepSpec.from_yaml(step_file)
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"Step file not found: {step_file}") from exc

    parameters = spec.parameters or {}
    updates = _overrides_to_parameter_dict(bundle.parameters)
    _merge_parameter_updates(parameters, updates, remove=remove)
    spec.parameters = {k: v for k, v in parameters.items() if v}

    spec.cards = _merge_card_updates(spec.cards or {}, bundle.card_overrides, remove=remove)
    spec.species_overrides = _merge_species_updates(
        spec.species_overrides or {}, bundle.species_overrides, remove=remove
    )

    _write_step_spec(step_file, spec)

    action = "Removed" if remove else "Updated"
    typer.secho(f"{action} parameters in {step_file}", fg=typer.colors.GREEN)


@configure_app.command("project")
def configure_project_placeholder() -> None:
    typer.secho(
        "Project-level configure commands are not implemented yet.",
        fg=typer.colors.YELLOW,
    )


@configure_app.command("workflow")
def configure_workflow_placeholder() -> None:
    typer.secho(
        "Workflow-level configure commands are not implemented yet.",
        fg=typer.colors.YELLOW,
    )


@configure_app.command("structure")
def configure_structure_placeholder() -> None:
    typer.secho(
        "Structure-level configure commands are not implemented yet.",
        fg=typer.colors.YELLOW,
    )


@app.command("show-command")
def show_command(input_file: Path = typer.Argument(..., help="QE input file to inspect")) -> None:
    """
    Print example CLI commands for creating a step spec and tweaking parameters based on an input file.
    """

    if not input_file.exists():
        raise typer.BadParameter(f"{input_file} does not exist.")

    qe_input = QEInputParser.parse_file(input_file)
    parameter_dict = _qe_input_to_parameter_dict(qe_input)
    param_args = _parameter_dict_to_cli_args(parameter_dict)
    card_args = _card_cli_args_from_input(qe_input)
    species_args = _species_cli_args_from_input(qe_input)
    cli_args = param_args + card_args + species_args
    calculation = (
        parameter_dict.get("CONTROL", {}).get("calculation")
        or parameter_dict.get("CONTROL", {}).get("CALCULATION")
        or "scf"
    )

    step_file = f"{input_file.stem}.step.yaml"
    base_cmd = [
        "qv",
        "init",
        "step",
        "<structure-id>",
        "--type",
        str(calculation),
    ] + cli_args

    typer.echo("Example 1: create a step spec with all detected parameters")
    typer.echo("  " + shlex.join(base_cmd))

    modify_cmd = [
        "qv",
        "configure",
        "step",
        step_file,
    ]
    if cli_args:
        modify_cmd.append(cli_args[0])
    else:
        modify_cmd.append("--CONTROL.calculation=scf")

    typer.echo("\nExample 2: tweak a parameter inside the generated YAML")
    typer.echo("  " + shlex.join(modify_cmd))
    typer.echo("\nReplace <structure-id> and workflow options as needed.")


@app.command("get-command")
def get_command(input_file: Path = typer.Argument(..., help="QE input file to inspect")) -> None:
    """
    Alias for show-command.
    """

    show_command(input_file)


@run_app.command("workflow")
def run_workflow_command(
    workflow: str = typer.Argument(..., help="Workflow name/slug/path"),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    mode: Optional[str] = typer.Option(
        None, "--mode", help="Override workflow mode (normal or strict)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Print per-step summaries and metrics"
    ),
    strict: bool = typer.Option(
        False, "--strict", help="Force strict verification mode for this run"
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

    if strict:
        wf.mode = StepMode.STRICT
    elif mode:
        try:
            wf.mode = StepMode(mode.lower())
        except ValueError as exc:
            raise typer.BadParameter("Mode must be 'normal' or 'strict'.") from exc

    registry = create_default_registry()
    runner = WorkflowRunner(registry)
    result = runner.run(wf)

    typer.echo(f"Workflow {wf.id} status: StepStatus.{result.status.name}")
    if verbose:
        for step in result.steps:
            line = f"- {step.step_id}: {step.status.value}"
            if step.reference_file:
                line += f" (ref: {step.reference_file.name})"
            if step.message:
                line += f" [{step.message}]"
            typer.echo(line)
            if step.metrics:
                for key, value in step.metrics.items():
                    typer.echo(f"    {key}: {value}")


@app.command("run-workflow")
def legacy_run_workflow_command(
    workflow: str = typer.Argument(..., help="Workflow name/slug/path"),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    mode: Optional[str] = typer.Option(
        None, "--mode", help="Override workflow mode (normal or strict)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Print per-step summaries and metrics"
    ),
    strict: bool = typer.Option(
        False, "--strict", help="Force strict verification mode for this run"
    ),
) -> None:
    """
    Deprecated alias for ``qv run workflow``.
    """

    typer.secho(
        "`qv run-workflow` is deprecated; use `qv run workflow` instead.",
        fg=typer.colors.YELLOW,
    )
    run_workflow_command(
        workflow=workflow,
        project=project,
        mode=mode,
        strict=strict,
        verbose=verbose,
    )


@run_app.callback()
def run_auto_dispatch(
    ctx: typer.Context,
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect when needed)"
    ),
    workdir: Optional[Path] = typer.Option(
        None, "--workdir", help="Working directory override for step/structure runs"
    ),
    mode: Optional[str] = typer.Option(
        None, "--mode", help="Workflow mode override (normal/strict)"
    ),
    strict: bool = typer.Option(
        False, "--strict", help="Force strict verification when running workflows"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose workflow output"),
) -> None:
    if ctx.invoked_subcommand:
        return
    if not ctx.args:
        raise typer.BadParameter("Provide a target or choose 'qv run <subcommand>'.")

    original_args = list(ctx.args)
    target = original_args.pop(0)
    ctx.args = list(original_args)
    target_path = Path(target)
    if target_path.exists():
        if target_path.is_dir() and (target_path / "workflow.yaml").exists():
            ctx.args = list(original_args)
            ctx.invoke(
                run_workflow_command,
                workflow=str(target_path),
                project=project,
                mode=mode,
                strict=strict,
                verbose=verbose,
            )
            return
        if target_path.is_file() and target_path.suffix.lower() in {".yaml", ".yml", ".in"}:
            ctx.args = list(original_args)
            ctx.invoke(
                run_step_command,
                target=target_path,
                working_dir=workdir,
                project=project,
            )
            return

    project_root = _maybe_project_root(project)

    if project_root:
        config = _load_project_config(project_root)
        try:
            _find_workflow_entry(config, target, project_root)
            ctx.args = list(original_args)
            ctx.invoke(
                run_workflow_command,
                workflow=target,
                project=project,
                mode=mode,
                strict=strict,
                verbose=verbose,
            )
            return
        except typer.BadParameter:
            pass
        try:
            _find_structure_entry(config, target, project_root)
            ctx.args = list(original_args)
            ctx.invoke(
                run_structure_command,
                structure=target,
                working_dir=workdir,
                project=project,
            )
            return
        except typer.BadParameter:
            pass

    raise typer.BadParameter(
        f"Unable to determine how to run '{target}'. "
        "Use 'qv run step|workflow|structure' for explicit control."
    )


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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_project_config(project_root: Path) -> dict:
    config_file = project_root / "project.qv.yml"
    if not config_file.exists():
        raise typer.BadParameter(f"project.qv.yml not found under {project_root}")
    return yaml.safe_load(config_file.read_text()) or {}


def _save_project_config(project_root: Path, data: dict) -> None:
    config_file = project_root / "project.qv.yml"
    config_file.write_text(yaml.safe_dump(data, sort_keys=False))


def _collect_slugs(entries: list[dict], *, exclude: Optional[dict] = None) -> list[str]:
    slugs: list[str] = []
    for entry in entries:
        if exclude is not None and entry is exclude:
            continue
        meta = entry.get("meta") or {}
        slug = meta.get("slug") or slugify(entry.get("name") or entry.get("id") or "")
        if slug:
            slugs.append(slug)
    return slugs


def _entry_matches(entry: dict, identifier: str) -> bool:
    ident = identifier.lower()
    meta = entry.get("meta") or {}
    candidates = filter(
        None,
        [
            entry.get("name"),
            entry.get("file"),
            entry.get("path"),
            meta.get("slug"),
            meta.get("name"),
        ],
    )
    for candidate in candidates:
        if str(candidate).lower() == ident:
            return True
    return False


def _ensure_structure_entry_defaults(entry: dict) -> None:
    meta = entry.setdefault("meta", {})
    if not meta.get("id"):
        meta["id"] = generate_resource_id()
    name_candidate = entry.get("name") or meta.get("name") or entry.get("id") or "Structure"
    meta.setdefault("name", name_candidate)
    entry.setdefault("name", meta["name"])
    slug_candidate = meta.get("slug") or slugify(meta["name"])
    meta["slug"] = slug_candidate
    file_path = entry.get("file") or meta.get("path")
    if file_path:
        meta.setdefault("path", file_path)
    else:
        meta.setdefault("path", f"structures/{slug_candidate}.json")


def _ensure_workflow_entry_defaults(entry: dict) -> None:
    meta = entry.setdefault("meta", {})
    if not meta.get("id"):
        meta["id"] = generate_resource_id()
    name_candidate = entry.get("name") or meta.get("name") or entry.get("id") or "Workflow"
    meta.setdefault("name", name_candidate)
    entry.setdefault("name", meta["name"])
    slug_candidate = meta.get("slug") or slugify(meta["name"])
    meta["slug"] = slug_candidate
    path_value = entry.get("path") or meta.get("path") or f"workflows/{slug_candidate}"
    entry.setdefault("path", path_value)
    meta.setdefault("path", path_value)


def _find_structure_entry(
    config: dict, identifier: str, project_root: Optional[Path] = None
) -> dict:
    entries = config.setdefault("structures", [])
    for entry in entries:
        _ensure_structure_entry_defaults(entry)
        if _entry_matches(entry, identifier):
            return entry
    if project_root:
        candidates: list[Path] = []
        raw_candidate = Path(identifier).expanduser()
        if raw_candidate.is_absolute():
            candidates.append(raw_candidate)
        else:
            candidates.append((project_root / raw_candidate))
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except FileNotFoundError:
                continue
            if not resolved.exists():
                continue
            try:
                rel = ensure_relative_path(resolved, base=project_root)
            except ValueError:
                continue
            for entry in entries:
                file_rel = entry.get("file") or (entry.get("meta") or {}).get("path")
                if file_rel and Path(file_rel).as_posix() == rel:
                    return entry
    raise typer.BadParameter(f"Structure '{identifier}' not found.")


def _find_workflow_entry(
    config: dict, identifier: str, project_root: Optional[Path] = None
) -> dict:
    entries = config.setdefault("workflows", [])
    for entry in entries:
        _ensure_workflow_entry_defaults(entry)
        if _entry_matches(entry, identifier):
            return entry
    if project_root:
        candidates: list[Path] = []
        raw_candidate = Path(identifier).expanduser()
        if raw_candidate.is_absolute():
            candidates.append(raw_candidate)
        else:
            candidates.append((project_root / raw_candidate))
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except FileNotFoundError:
                continue
            if not resolved.exists():
                continue
            try:
                rel = ensure_relative_path(resolved, base=project_root)
            except ValueError:
                continue
            for entry in entries:
                wf_rel = entry.get("path") or (entry.get("meta") or {}).get("path")
                if wf_rel and Path(wf_rel).as_posix() == rel:
                    return entry
    raise typer.BadParameter(f"Workflow '{identifier}' not found.")


def _suggest_structure_name(structure: "PMGStructure", source_path: Path) -> str:
    formula = None
    try:
        formula = structure.composition.reduced_formula
    except Exception:
        formula = None
    if formula:
        return formula
    return source_path.stem or "Structure"


def _apply_structure_rename(
    *,
    project_root: Path,
    config: dict,
    entry: dict,
    new_name: Optional[str],
    new_slug: Optional[str],
    new_path: Optional[Path],
) -> None:
    structures = config.setdefault("structures", [])
    meta = entry.setdefault("meta", {})
    existing_slugs = _collect_slugs(structures, exclude=entry)
    previous_slug = meta.get("slug")
    slug_changed = False
    previous_path = entry.get("file") or meta.get("path")

    if new_name or new_slug:
        if new_slug:
            slug_candidate = slugify(new_slug)
            if slug_candidate in existing_slugs:
                raise typer.BadParameter(
                    f"Slug '{new_slug}' conflicts with an existing structure."
                )
            name_candidate = new_name or entry.get("name") or meta.get("name") or slug_candidate
        else:
            preferred = new_name or entry.get("name") or meta.get("name")
            name_candidate, slug_candidate = generate_unique_name_and_slug(
                kind="structure",
                preferred_name=preferred,
                existing_slugs=existing_slugs,
            )
        entry["name"] = name_candidate
        meta["name"] = name_candidate
        meta["slug"] = slug_candidate
        slug_changed = slug_candidate != previous_slug

    if new_path is not None:
        relative = ensure_relative_path(new_path, base=project_root)
        old_path = entry.get("file") or meta.get("path")
        if not old_path:
            raise typer.BadParameter("Structure entry is missing a file path.")
        old_abs = (project_root / old_path).resolve()
        if not old_abs.exists():
            raise typer.BadParameter(f"Structure file '{old_path}' does not exist.")
        new_abs = (project_root / relative).resolve()
        new_abs.parent.mkdir(parents=True, exist_ok=True)
        old_abs.rename(new_abs)
        entry["file"] = relative
        meta["path"] = relative
    elif slug_changed and previous_path:
        old_abs = (project_root / previous_path).resolve()
        if old_abs.exists():
            old_rel = Path(previous_path)
            suffix = "".join(old_rel.suffixes)
            parent = old_rel.parent
            new_rel_path = (parent / f"{meta['slug']}{suffix}")
            new_abs = (project_root / new_rel_path).resolve()
            if new_abs.exists():
                raise typer.BadParameter(
                    f"Cannot rename structure file to '{new_rel_path}': destination exists."
                )
            new_abs.parent.mkdir(parents=True, exist_ok=True)
            old_abs.rename(new_abs)
            rel_str = new_rel_path.as_posix()
            entry["file"] = rel_str
            meta["path"] = rel_str


def _apply_workflow_rename(
    *,
    project_root: Path,
    config: dict,
    entry: dict,
    new_name: Optional[str],
    new_slug: Optional[str],
    new_path: Optional[Path],
) -> None:
    workflows = config.setdefault("workflows", [])
    meta = entry.setdefault("meta", {})
    existing_slugs = _collect_slugs(workflows, exclude=entry)
    previous_slug = meta.get("slug")
    slug_changed = False
    previous_path = entry.get("path") or meta.get("path")

    if new_name or new_slug:
        if new_slug:
            slug_candidate = slugify(new_slug)
            if slug_candidate in existing_slugs:
                raise typer.BadParameter(
                    f"Slug '{new_slug}' conflicts with an existing workflow."
                )
            name_candidate = new_name or entry.get("name") or meta.get("name") or slug_candidate
        else:
            preferred = new_name or entry.get("name") or meta.get("name")
            name_candidate, slug_candidate = generate_unique_name_and_slug(
                kind="workflow",
                preferred_name=preferred,
                existing_slugs=existing_slugs,
            )
        entry["name"] = name_candidate
        meta["name"] = name_candidate
        meta["slug"] = slug_candidate
        if not entry.get("path"):
            entry["path"] = f"workflows/{slug_candidate}"
        slug_changed = slug_candidate != previous_slug

    if new_path is not None:
        relative = ensure_relative_path(new_path, base=project_root)
        old_path = entry.get("path") or meta.get("path")
        if not old_path:
            raise typer.BadParameter("Workflow entry is missing a path.")
        old_abs = (project_root / old_path).resolve()
        if not old_abs.exists():
            raise typer.BadParameter(f"Workflow directory '{old_path}' does not exist.")
        new_abs = (project_root / relative).resolve()
        if new_abs.exists():
            raise typer.BadParameter(f"Destination '{relative}' already exists.")
        new_abs.parent.mkdir(parents=True, exist_ok=True)
        old_abs.rename(new_abs)
        entry["path"] = relative
        meta["path"] = relative
    elif slug_changed and previous_path:
        old_abs = (project_root / previous_path).resolve()
        if old_abs.exists():
            old_rel = Path(previous_path)
            parent = old_rel.parent
            new_rel = (parent / meta["slug"])
            new_abs = (project_root / new_rel).resolve()
            if new_abs.exists():
                raise typer.BadParameter(
                    f"Cannot rename workflow directory to '{new_rel}': destination exists."
                )
            new_abs.parent.mkdir(parents=True, exist_ok=True)
            old_abs.rename(new_abs)
            rel_str = new_rel.as_posix()
            entry["path"] = rel_str
            meta["path"] = rel_str


def _entry_display_name(entry: dict, fallback: str = "resource") -> str:
    meta = entry.get("meta") or {}
    return entry.get("name") or meta.get("name") or entry.get("id") or fallback


def _structure_reference_tokens(entry: dict, project_root: Path) -> tuple[set[str], Optional[Path]]:
    meta = entry.get("meta") or {}
    aliases: set[str] = set()
    for candidate in (
        entry.get("name"),
        meta.get("name"),
        meta.get("slug"),
        meta.get("id"),
    ):
        if candidate:
            aliases.add(str(candidate).strip().lower())
    rel_path = entry.get("file") or meta.get("path")
    resolved = None
    if rel_path:
        resolved = (project_root / rel_path).resolve()
    return aliases, resolved


def _spec_uses_structure(
    spec: StructureStepSpec,
    spec_path: Path,
    aliases: set[str],
    resolved_path: Optional[Path],
) -> bool:
    identifier = (spec.structure or "").strip()
    if not identifier:
        return False
    if identifier.lower() in aliases:
        return True
    candidate = Path(identifier)
    if not candidate.is_absolute():
        candidate = (spec_path.parent / candidate).resolve()
    else:
        candidate = candidate.resolve()
    if resolved_path and candidate == resolved_path:
        return True
    return False


def _workflows_using_structure(
    project_root: Path, config: dict, entry: dict
) -> list[dict]:
    aliases, resolved_path = _structure_reference_tokens(entry, project_root)
    matches: list[dict] = []
    for workflow_entry in list(config.get("workflows", [])):
        workflow_path = workflow_entry.get("path") or (workflow_entry.get("meta") or {}).get("path")
        if not workflow_path:
            continue
        workflow_dir = (project_root / workflow_path).resolve()
        steps_dir = workflow_dir / "steps"
        if not steps_dir.exists():
            continue
        for spec_path in steps_dir.rglob("*.step.yaml"):
            try:
                spec = StructureStepSpec.from_yaml(spec_path)
            except Exception:
                continue
            if _spec_uses_structure(spec, spec_path, aliases, resolved_path):
                matches.append(workflow_entry)
                break
    return matches


def _workflow_identifiers(entry: dict) -> set[str]:
    meta = entry.get("meta") or {}
    identifiers = {
        entry.get("name"),
        meta.get("name"),
        meta.get("slug"),
        meta.get("id"),
    }
    return {str(value) for value in identifiers if value}


def _workflows_depending_on(config: dict, target_entry: dict) -> list[dict]:
    identifiers = _workflow_identifiers(target_entry)
    matches: list[dict] = []
    for workflow_entry in config.get("workflows", []):
        if workflow_entry is target_entry:
            continue
        meta = workflow_entry.get("meta") or {}
        parents = meta.get("parents") or []
        for parent in parents:
            if str(parent) in identifiers:
                matches.append(workflow_entry)
                break
    return matches


def _workflow_directory(project_root: Path, entry: dict) -> Path:
    rel_path = entry.get("path") or (entry.get("meta") or {}).get("path")
    if not rel_path:
        raise typer.BadParameter("Workflow entry is missing a path.")
    return (project_root / rel_path).resolve()


def _delete_workflow_entry(
    *,
    project_root: Path,
    config: dict,
    entry: dict,
    trash_dir: Path,
    force: bool,
    cascade: bool,
    visited: Optional[set[str]] = None,
) -> None:
    identifiers = _workflow_identifiers(entry)
    if visited is None:
        visited = set()
    if identifiers & visited:
        return
    visited.update(identifiers)

    dependents = _workflows_depending_on(config, entry)
    if dependents:
        if cascade:
            for dependent in list(dependents):
                _delete_workflow_entry(
                    project_root=project_root,
                    config=config,
                    entry=dependent,
                    trash_dir=trash_dir,
                    force=force,
                    cascade=True,
                    visited=visited,
                )
        elif not force:
            names = ", ".join(_entry_display_name(dep) for dep in dependents)
            raise typer.BadParameter(
                f"Workflow '{_entry_display_name(entry)}' is required by: {names}. "
                "Use --force to remove it anyway or --cascade to delete dependents."
            )

    workflow_dir = None
    rel_path = entry.get("path") or (entry.get("meta") or {}).get("path")
    if rel_path:
        workflow_dir = (project_root / rel_path).resolve()
        if workflow_dir.exists():
            _move_to_trash(workflow_dir, trash_dir)

    workflows = config.setdefault("workflows", [])
    if entry in workflows:
        workflows.remove(entry)


def _write_step_spec(
    path: Path, spec: StructureStepSpec, *, project_root: Optional[Path] = None
) -> None:
    if project_root:
        relative_path = ensure_relative_path(path, base=project_root)
    else:
        relative_path = path.name
    spec.meta = spec.meta.with_updates(path=relative_path)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(spec.to_dict(), sort_keys=False))


def _overrides_to_parameter_dict(
    overrides: Sequence[ParameterOverride],
) -> dict[str, dict[str, Any]]:
    parameters: dict[str, dict[str, Any]] = {}
    for override in overrides:
        section = (override.section or "CONTROL").upper()
        section_params = parameters.setdefault(section, {})
        section_params[override.name] = override.value
    return parameters


def _merge_parameter_updates(
    parameters: dict[str, dict[str, Any]],
    updates: dict[str, dict[str, Any]],
    *,
    remove: bool,
) -> None:
    for section, entries in updates.items():
        target = parameters.setdefault(section, {})
        if remove:
            for key in entries.keys():
                target.pop(key, None)
            if not target:
                parameters.pop(section, None)
        else:
            target.update(entries)


def _merge_card_updates(
    target: dict[str, dict[str, Any]],
    updates: dict[str, dict[str, Any]],
    *,
    remove: bool,
) -> dict[str, dict[str, Any]]:
    if not updates:
        return target
    for card_name, payload in updates.items():
        entry = target.setdefault(card_name, {})
        if "option" in payload:
            option_value = payload["option"]
            if remove and _is_empty_card_value(option_value):
                entry.pop("option", None)
            else:
                entry["option"] = option_value

        if "data" in payload:
            data_value = copy.deepcopy(payload["data"])
            if remove and _is_empty_card_value(data_value):
                entry.pop("data", None)
            else:
                entry["data"] = data_value

        if "rows" in payload:
            rows = entry.setdefault("rows", {})
            for row_key, row_value in payload["rows"].items():
                if remove and _is_empty_card_value(row_value):
                    rows.pop(row_key, None)
                else:
                    rows[row_key] = copy.deepcopy(row_value)
            if remove and not rows:
                entry.pop("rows", None)

        if not entry:
            target.pop(card_name, None)
    return target


def _merge_species_updates(
    target: dict[str, dict[str, Any]],
    updates: dict[str, dict[str, Any]],
    *,
    remove: bool,
) -> dict[str, dict[str, Any]]:
    if not updates:
        return target
    for symbol, payload in updates.items():
        entry = target.setdefault(symbol, {})
        if remove:
            for key in payload.keys():
                entry.pop(key, None)
            if not entry:
                target.pop(symbol, None)
        else:
            entry.update(payload)
    return target


def _qe_input_to_parameter_dict(qe_input: QEInput) -> dict[str, dict[str, Any]]:
    param_dict: dict[str, dict[str, Any]] = {}
    for namelist in qe_input.namelists:
        params = {}
        for key, value in namelist.parameters.items():
            params[str(key)] = value
        if params:
            param_dict[namelist.name.upper()] = params
    _strip_structural_system_params(param_dict, qe_input)
    return param_dict


def _strip_structural_system_params(
    parameter_dict: dict[str, dict[str, Any]],
    qe_input: Optional[QEInput] = None,
) -> None:
    from quantumvitas.workflow.importers import _needs_alat_preservation, _extract_alat_bohr
    
    system = parameter_dict.get("SYSTEM")
    if not system:
        return
    
    # Check if we need to preserve alat for k-point compatibility
    preserve_alat = _needs_alat_preservation(qe_input) if qe_input else False
    alat_bohr = _extract_alat_bohr(qe_input) if preserve_alat and qe_input else None
    
    for key in list(system.keys()):
        lower = str(key).lower()
        if lower in STRUCTURAL_SYSTEM_KEYS:
            system.pop(key, None)
        elif lower.startswith("celldm"):
            system.pop(key, None)
        elif lower in STRUCTURAL_LATTICE_KEYS:
            system.pop(key, None)
    
    # Add back celldm(1) if we need to preserve alat
    if alat_bohr is not None:
        system["celldm(1)"] = alat_bohr
    
    if not system:
        parameter_dict.pop("SYSTEM", None)


def _parameter_dict_to_cli_args(parameter_dict: dict[str, dict[str, Any]]) -> list[str]:
    cli_args: list[str] = []
    for section in sorted(parameter_dict.keys()):
        entries = parameter_dict[section]
        for key in sorted(entries.keys()):
            value = entries[key]
            formatted = _format_cli_value(value)
            cli_args.append(f"--{section}.{key}={formatted}")
    return cli_args


def _format_cli_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        if value == "" or any(c.isspace() for c in value):
            return json.dumps(value)
        return value
    if isinstance(value, list):
        inner = ",".join(_format_cli_value(v) for v in value)
        return f"[{inner}]"
    return json.dumps(value)

def _card_cli_args_from_input(qe_input: QEInput) -> list[str]:
    args: list[str] = []
    for card in qe_input.cards:
        if card.card_type == QECardType.ATOMIC_SPECIES:
            continue
        if card.card_type in {QECardType.ATOMIC_POSITIONS, QECardType.CELL_PARAMETERS}:
            continue
        
        payload: dict[str, Any] = {}
        if card.option:
            payload["option"] = card.option
        if card.data:
            payload["data"] = card.data
        
        if payload:
            args.append(
                f"--CARD.{card.card_type.name}="
                f"{json.dumps(payload, separators=(',', ':'))}"
            )
    return args


def _species_cli_args_from_input(qe_input: QEInput) -> list[str]:
    args: list[str] = []
    species_card = qe_input.get_card(QECardType.ATOMIC_SPECIES)
    if not species_card or not species_card.data:
        return args
    for row in species_card.data:
        if not row:
            continue
        symbol = row[0]
        if len(row) > 1 and row[1] not in (None, ""):
            args.append(f"--SPECIES.{symbol}.mass={row[1]}")
        if len(row) > 2 and row[2]:
            args.append(f"--SPECIES.{symbol}.pseudopot={row[2]}")
    return args


def _is_empty_card_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (list, tuple, dict)) and not value:
        return True
    return False


def _collect_qe_detection_info(backend) -> dict[str, Any]:
    env_home = _safe_path(os.getenv("QE_HOME"))
    installation = getattr(backend, "installation", None) or getattr(
        backend, "_installation", None
    )
    engine_home = _safe_path(getattr(installation, "qe_home", None))

    pw_path = backend.find_executable("pw.x") if hasattr(backend, "find_executable") else None
    if pw_path is None:
        which_path = shutil.which("pw.x")
        pw_path = Path(which_path).resolve() if which_path else None

    which_home = pw_path.parent.parent if pw_path else None
    resolved_home = engine_home or env_home or which_home
    bin_dir = None
    if resolved_home and (resolved_home / "bin").exists():
        bin_dir = resolved_home / "bin"
    elif pw_path:
        bin_dir = pw_path.parent

    test_suite = None
    if resolved_home:
        candidate = resolved_home / "test-suite"
        if candidate.exists():
            test_suite = candidate

    executables = {}
    for exe in ("pw.x", "ph.x", "dos.x", "bands.x"):
        path = backend.find_executable(exe) if hasattr(backend, "find_executable") else None
        if path is None:
            which_exec = shutil.which(exe)
            path = Path(which_exec).resolve() if which_exec else None
        executables[exe] = path

    return {
        "env_home": env_home,
        "engine_home": engine_home,
        "which_home": which_home,
        "qe_home": resolved_home,
        "bin_dir": bin_dir,
        "test_suite": test_suite,
        "executables": executables,
    }


def _safe_path(value: Optional[Any]) -> Optional[Path]:
    if not value:
        return None
    try:
        return Path(value).expanduser().resolve()
    except OSError:
        return None


def _execute_step_spec_path(
    spec_path: Path,
    bundle: ParsedOverrides,
    project_root: Path,
    working_dir: Optional[Path],
    engine_backend,
):
    spec = StructureStepSpec.from_yaml(spec_path)
    return _execute_step_spec(
        spec=spec,
        spec_path=spec_path,
        bundle=bundle,
        project_root=project_root,
        working_dir=working_dir,
        engine_backend=engine_backend,
    )


def _execute_step_spec(
    spec: StructureStepSpec,
    spec_path: Path,
    bundle: ParsedOverrides,
    project_root: Path,
    working_dir: Optional[Path],
    engine_backend,
):
    spec_copy = copy.deepcopy(spec)
    if bundle.card_overrides:
        spec_copy.cards = _merge_card_updates(
            spec_copy.cards or {}, bundle.card_overrides, remove=False
        )
    if bundle.species_overrides:
        spec_copy.species_overrides = _merge_species_updates(
            spec_copy.species_overrides or {}, bundle.species_overrides, remove=False
        )

    structure, struct_name = _resolve_structure_input(project_root, spec_copy.structure)
    qe_input, _ = generate_qe_input_from_spec(
        structure=structure,
        spec=spec_copy,
        extra_overrides=bundle.parameters,
    )

    workdir = working_dir or (Path("temp") / "cli_outputs" / struct_name)
    workdir = workdir.resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    input_name = spec_copy.input_name or f"{struct_name}_{spec_copy.step_type}.pw.in"
    generated_input = workdir / input_name
    QEInputGenerator.write_file(qe_input, generated_input)

    result, prepared = run_input_step(
        engine=engine_backend,
        input_file=generated_input,
        working_dir=workdir,
        project_root=project_root,
        step_type=None,
    )
    return result, prepared, generated_input

