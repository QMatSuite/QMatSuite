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

# Analysis modules no longer imported directly (migrated to QVService/api)
# ResourceMeta removed - use dict[str, Any] for type hints
# API errors (PR10: kernel exceptions replaced with API errors)
from quantumvitas.api import (
    NotFoundError,  # Replaces NotFoundError, NotFoundError
    AmbiguousError,  # Replaces AmbiguousError
    ConfigError,  # Replaces ConfigError, ConfigError
    APIError,  # Replaces APIError
    QVService,
    get_service,
)
from quantumvitas.api.utils import (
    build_step_spec_from_qe_input,
    detect_runtime_control_keys,
    entry_display_name,
    entry_matches,
    extract_alat_bohr,
    extract_calculation_selector_from_entry,
    extract_step_selector_from_entry,
    find_path_context_ref,
    find_project_root,
    move_to_trash,
    needs_alat_preservation,
    write_qe_input_file,
)
# Kernel utility re-exported via API utils (avoids direct core.* imports per import rules)
from quantumvitas.api.utils import calculations_using_structure
from quantumvitas.api.utils import (
    get_module_doc_url,
    get_module_param_sections,
    list_supported_modules,
)
# Engine types and functions now via QVService
# EngineConfig removed - handled via API
# CalculationRunner now accessed via QVService.run_calculation()
# Calculation class removed - use API DTOs/dicts
# StepMode and StepStatus removed - use API types or strings
# # ParameterOverride removed - use dict[str, Any] removed - use dict[str, Any] or API DTOs
# Structure step specs now via QVService
# I/O operations via API submodule (not top-level re-export)
from quantumvitas.api.qe_io import QECardType, QEInputParser

if TYPE_CHECKING:
    from pymatgen.core import Structure as PMGStructure


@dataclass(slots=True)
class ParsedOverrides:
    parameters: List[dict[str, Any]]
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
analyze_app = typer.Typer(
    help="Analyze QE outputs and structures.",
    no_args_is_help=True,
    invoke_without_command=True,
)

app.add_typer(init_app, name="init")
app.add_typer(rename_app, name="rename")
app.add_typer(delete_app, name="delete")
app.add_typer(configure_app, name="configure")
app.add_typer(run_app, name="run")
app.add_typer(analyze_app, name="analyze")


def _svc_from_cwd(cwd: Optional[Path] = None) -> "QVService":
    """
    Get a QVService instance from the current working directory.
    
    Detects project root from cwd (or current working directory) and returns
    a QVService instance for that project.
    
    Args:
        cwd: Working directory (defaults to current working directory)
        
    Returns:
        QVService instance for the detected project
        
    Raises:
        typer.BadParameter: If no project root is found
    """
    from quantumvitas.api import get_service
    try:
        # Use get_service helper which handles project root detection
        return get_service(project_root=None)
    except ValueError as e:
        raise typer.BadParameter(str(e))


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


def _handle_legacy_project_error(e: ConfigError) -> None:
    """Handle ConfigError by printing a clear message and exiting."""
    typer.secho(
        f"\n❌ Legacy project detected at {e.project_root}",
        fg=typer.colors.RED,
        err=True,
    )
    typer.secho(
        f"\nThis project uses a legacy calculation format (structure selector / step_file / non-ULID step IDs).",
        err=True,
    )
    typer.secho(
        f"Please migrate it using:\n",
        err=True,
    )
    typer.secho(
        f"  python tools/qv_migrate_legacy_project.py --project-root {e.project_root}",
        fg=typer.colors.YELLOW,
        err=True,
    )
    raise typer.Exit(1)


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

    from quantumvitas.api.utils import slugify
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
    from quantumvitas.api import QVService
    preferred = (base_name or "step").strip() or "step"
    from quantumvitas.api.utils import slugify
    slug_candidate = slugify(preferred)
    display = preferred
    occupied = {value.lower() for value in existing_ids if value}
    suffix = 2
    while slug_candidate.lower() in occupied:
        display = f"{preferred}-{suffix}"
        from quantumvitas.api.utils import slugify
        slug_candidate = slugify(display)
        suffix += 1
    return display, slug_candidate


def _resolve_structure_reference(
    identifier: str, project_root: Optional[Path], config: Optional[dict]
) -> str:
    if project_root and config is not None:
        try:
            from quantumvitas.api import QVService
            svc = get_service(project_root)
            # Get structure DTO, then find entry in config
            struct_dto = svc.structure.get(identifier)
            entry = _find_entry_by_structure_id(config, struct_dto.meta.id if struct_dto.meta else "")
            meta = entry.get("meta") or {}
            return meta.get("slug") or entry.get("name") or identifier
        except Exception:
            pass

    candidate = Path(identifier)
    if candidate.exists():
        if project_root:
            try:
                from quantumvitas.api.utils import ensure_relative_path
                return ensure_relative_path(candidate, base=project_root)
            except ValueError:
                return candidate.as_posix()
        return candidate.as_posix()
    return identifier


def _find_entry_by_structure_id(config: dict, structure_id: str) -> dict:
    """
    Find structure entry in config by structure_id (ULID).
    
    Args:
        config: Project config dict
        structure_id: Structure ULID
        
    Returns:
        Structure entry dict
        
    Raises:
        ValueError: If entry not found
    """
    from quantumvitas.api.utils import extract_structure_selector_from_entry
    for entry in config.get("structures", []):
        entry_id = extract_structure_selector_from_entry(entry)
        if entry_id == structure_id:
            return entry
    raise ValueError(f"Structure entry with id '{structure_id}' not found in config")


def _find_entry_by_calc_id(config: dict, calc_id: str) -> dict:
    """
    Find calculation entry in config by calc_id (ULID).
    
    Args:
        config: Project config dict
        calc_id: Calculation ULID
        
    Returns:
        Calculation entry dict
        
    Raises:
        ValueError: If entry not found
    """
    from quantumvitas.api.utils import extract_calculation_selector_from_entry
    for entry in config.get("calculations", []):
        entry_id = extract_calculation_selector_from_entry(entry)
        if entry_id == calc_id:
            return entry
    raise ValueError(f"Calculation entry with id '{calc_id}' not found in config")


def _get_calc_id_from_entry(entry: dict) -> str:
    """
    Extract calculation ID from entry dict.
    
    Args:
        entry: Calculation entry dict
        
    Returns:
        Calculation ULID
    """
    from quantumvitas.api.utils import extract_calculation_selector_from_entry
    return extract_calculation_selector_from_entry(entry)


# Removed: _get_calculation_dir_from_entry - use ref.path from CalculationRefDTO instead


def _detect_enclosing_calculation(
    project_root: Path, current_dir: Path, calculations: Sequence[dict]
) -> Optional[str]:
    try:
        current_dir.relative_to(project_root)
    except ValueError:
        return None

    for entry in calculations:
        rel_path = entry.get("path") or (entry.get("meta") or {}).get("path")
        if not rel_path:
            continue
        calculation_dir = (project_root / rel_path).resolve()
        if current_dir == calculation_dir or current_dir.is_relative_to(calculation_dir):
            meta = entry.get("meta") or {}
            return meta.get("slug") or entry.get("name")
    return None


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


def _parse_override_args(extra_args: List[str]) -> ParsedOverrides:
    """
    Convert unknown CLI arguments (e.g., --ecutwfc=40) into overrides.
    """

    parameter_map: dict[str, dict[str, Any]] = {}
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

        parameter_map[normalized_param.lower()] = {
            "name": normalized_param,
            "value": _coerce_override_value(value or ""),
            "section": normalized_section,
        }
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
        section = override.get("section")
        prefix = f"{section}." if section else ""
        parts.append(f"{prefix}{override.get('name', '')}={override.get('value', '')}")
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
    project_root: Path, identifier: Optional[str]
) -> tuple[PMGStructure, str]:
    """
    Load a structure either from a file path or from project metadata.
    
    Args:
        project_root: Project root path
        identifier: Structure identifier (path, name, slug, or ULID), or None
        
    Returns:
        Tuple of (PMGStructure, structure_name)
    """
    if not identifier:
        raise ValueError("Structure identifier is required")
    
    candidate = Path(identifier)
    # Check if it's a file (not a directory)
    if candidate.exists() and candidate.is_file():
        from quantumvitas.api import QVService
        from quantumvitas.api.utils import read_structure
        structure = read_structure(candidate)
        return structure, candidate.stem

    # Try to resolve via registry-based resolution (ID-only model)
    try:
        from quantumvitas.api import get_service
        from quantumvitas.api.utils import read_structure
        svc = get_service(project_root)
        resolved = svc.structure.require_ref(identifier)
        structure = read_structure(resolved.absolute_path)
        return structure, resolved.meta.name or resolved.meta.slug or identifier
    except Exception as e:
        # No fallback - API should handle all resolution
        from quantumvitas.api.errors import NotFoundError
        if isinstance(e, NotFoundError):
            raise ValueError(f"Could not resolve structure '{identifier}': {e}") from e
        raise ValueError(f"Could not resolve structure '{identifier}': {e}") from e



@init_app.command("project")
def init_project_command(
    name: Optional[str] = typer.Option(None, "--name", help="Project display name"),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        help="Directory where the project should be created (defaults to ./projectN).",
    ),
    snapshot: Optional[Path] = typer.Option(
        None,
        "--snapshot",
        help="Path to a project snapshot YAML file to use as template",
    ),
) -> None:
    """
    Scaffold a new QuantumVITAS project skeleton (no calculations by default).
    
    Use --snapshot to create a project from a snapshot YAML file (exported via qv save project).
    When using --snapshot, --path is treated as the parent directory where the new project will be created.
    
    For demo projects with pre-populated calculations, use the GUI "Create Demo Project" button
    or call create_demo_project via the API.
    """
    # Handle snapshot first
    if snapshot:
        snapshot_path = Path(snapshot).expanduser().resolve()
        if not snapshot_path.exists():
            raise typer.BadParameter(f"Snapshot file not found: {snapshot_path}")
        
        # When using snapshot, path is the parent directory
        if path:
            parent_dir = Path(path).expanduser().resolve()
        else:
            parent_dir = Path.cwd()
        
        parent_dir.mkdir(parents=True, exist_ok=True)
        
        project_dir = QVService.create_project_from_snapshot(
            parent_dir=parent_dir,
            snapshot_path=snapshot_path,
            project_name=name,
        )
        
        typer.secho(
            f"Project created from snapshot at {project_dir}",
            fg=typer.colors.GREEN
        )
        return

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
    from quantumvitas.api.utils import meta_from_name
    project_meta_dict = meta_from_name("project", name=project_name, path=".")
    project_meta = project_meta_dict  # Use dict directly (no ResourceMeta dependency)

    project_config = {
        "project": {
            "name": project_meta["name"],
            "meta": project_meta,
            "structures_dir": "structures",
            "calculations_dir": "calculations",
        },
        "calculations": [],
        "structures": [],
        "settings": {},
    }

    (project_dir / "structures").mkdir(parents=True, exist_ok=True)
    (project_dir / "calculations").mkdir(parents=True, exist_ok=True)
    (project_dir / "project.qv.yml").write_text(
        yaml.safe_dump(project_config, sort_keys=False)
    )

    typer.secho(f"Project created at {project_dir}", fg=typer.colors.GREEN)


@init_app.command("calculation")
def init_calculation_command(
    calculation_id: str = typer.Argument(..., help="Calculation identifier to create"),
    structure: Optional[str] = typer.Option(
        None, "--structure", help="Structure id registered in the project"
    ),
    parent: List[str] = typer.Option(
        [],
        "--parent",
        help="Calculation ids/slugs that must finish before this calculation (metadata only).",
    ),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    template: Optional[str] = typer.Option(
        None, "--template", help="Calculation template to use (e.g., 'si-dos')"
    ),
    structure_kind: Optional[str] = typer.Option(
        None,
        "--structure-kind",
        help="Structure kind: 'periodic' or 'molecule' (default: 'periodic')",
    ),
    engine_family: Optional[str] = typer.Option(
        None,
        "--engine-family",
        help="Engine family: 'qe', 'pyscf', etc. (default: 'qe' for periodic, 'pyscf' for molecule)",
    ),
) -> None:
    """
    Scaffold a calculation folder with calculation.yaml and no pre-populated steps.
    
    Use --template to copy from a predefined calculation template with example steps.
    If using a template, --structure is optional (template's structure is used).
    """
    # Template functions now via QVService
    from quantumvitas.api import QVService

    project_root = (project or _resolve_project_root()).resolve()
    from quantumvitas.api import QVService
    svc = get_service(project_root)
    config = svc.project.get_config()
    calculations_section = config.setdefault("calculations", [])
    from quantumvitas.api.utils import slugify
    existing_slugs = {
        (entry.get("meta") or {}).get("slug") or slugify(entry.get("name") or "")
        for entry in calculations_section
    }

    calculation_slug = slugify(calculation_id)
    if calculation_slug in existing_slugs:
        raise typer.BadParameter(
            f"Calculation '{calculation_id}' already exists. Use qv configure calculation to modify it."
        )

    calculation_dir = (project_root / "calculations" / calculation_slug).resolve()
    if calculation_dir.exists():
        raise typer.BadParameter(
            f"Calculation directory '{calculation_dir}' already exists. Remove it or choose another name."
        )

    if template:
        from quantumvitas.api.utils import list_calculation_templates
        available_templates = list_calculation_templates()
        available = [t["name"] for t in available_templates]
        if template not in available:
            raise typer.BadParameter(
                f"Template '{template}' not found. Available: {', '.join(available) or 'none'}"
            )
        
        calculation_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate calculation meta first so we have the ULID
        from quantumvitas.api.utils import ensure_relative_path, meta_from_name
        rel_path = ensure_relative_path(calculation_dir, base=project_root)
        calculation_meta_dict = meta_from_name("calculation", name=calculation_id, path=rel_path)
        calculation_meta = calculation_meta_dict  # Use dict directly (no ResourceMeta dependency)
        
        # Pass the ULID to template copier so steps get the correct parent_calculation_id
        from quantumvitas.api.utils import copy_calculation_template
        _, structures_needed, _ = copy_calculation_template(
            template_name=template,
            dest_dir=calculation_dir,
            project_root=project_root,
            new_name=calculation_id,
            structure=structure,
            calculation_ulid=calculation_meta["id"],
        )
        
        # Copy missing structures from templates
        structures_dir = project_root / "structures"
        structures_section = config.setdefault("structures", [])
        from quantumvitas.api.utils import slugify, copy_structure_template
        existing_struct_slugs = {
            (entry.get("meta") or {}).get("slug") or slugify(entry.get("name") or "")
            for entry in structures_section
        }
        
        for struct_name in structures_needed:
            if struct_name not in existing_struct_slugs:
                try:
                    struct_path = copy_structure_template(struct_name, structures_dir)
                    from quantumvitas.api.utils import ensure_relative_path, meta_from_name
                    struct_rel_path = ensure_relative_path(struct_path, base=project_root)
                    struct_meta_dict = meta_from_name("structure", name=struct_name, path=struct_rel_path)
                    # DAG + ID-only: only structure_id, no meta duplication
                    structures_section.append({
                        "structure_id": struct_meta_dict.get("id"),  # ID-only reference (ULID)
                    })
                    typer.echo(f"Copied structure '{struct_name}' from template")
                except ValueError:
                    typer.secho(
                        f"Warning: Structure '{struct_name}' needed but not found in templates",
                        fg=typer.colors.YELLOW
                    )
        
        calculation_meta_dict = calculation_meta
        if parent:
            calculation_meta_dict["parents"] = parent

        # DAG + ID-only: only calculation_id, no meta duplication
        calculations_section.append({
            "calculation_id": calculation_meta["id"],  # ID-only reference (ULID)
        })
        svc.project.update_config(config)
        typer.secho(f"Calculation '{calculation_id}' created from template '{template}' at {calculation_dir}", fg=typer.colors.GREEN)
        return

    # Non-template calculation creation requires --structure
    if not structure:
        raise typer.BadParameter(
            "--structure is required when not using --template"
        )

    # Resolve structure selector to structure_id (ULID)
    resolved_structure = svc.structure.require_ref(structure, config=config)
    structure_id = resolved_structure.meta.id
    structure_name = resolved_structure.meta.name

    raw_dir = calculation_dir / "raw"
    steps_dir = calculation_dir / "steps"
    raw_dir.mkdir(parents=True, exist_ok=True)
    steps_dir.mkdir(parents=True, exist_ok=True)

    # Generate calculation meta with ULID
    from quantumvitas.api.utils import ensure_relative_path, meta_from_name
    rel_path = ensure_relative_path(calculation_dir, base=project_root)
    calculation_meta_dict = meta_from_name("calculation", name=calculation_id, path=str(rel_path))
    if parent:
        calculation_meta_dict["parents"] = parent

    # Phase 2: Determine structure_kind and engine_family
    # Default structure_kind to periodic if not provided
    if structure_kind is None:
        structure_kind = "periodic"
    elif structure_kind not in ("periodic", "molecule"):
        raise typer.BadParameter(
            f"Invalid structure_kind '{structure_kind}'. Must be 'periodic' or 'molecule'."
        )
    
    # Default engine_family based on structure_kind if not provided
    if engine_family is None:
        if structure_kind == "molecule":
            engine_family = "pyscf"
        else:
            engine_family = "qe"  # Default for periodic structures
    
    # Write calculation.yaml with proper meta section (contains ULID)
    # DAG + ID-only model: use structure_id (ULID) as canonical reference
    # Do NOT write structure_name or structure selector (violates DAG + ID-only constitution)
    calculation_payload = {
        "meta": calculation_meta_dict,
        "structure_id": structure_id,  # Canonical reference (ULID only)
        "mode": "normal",
        "working_dir": "raw",
        "steps": [],
        # Phase 2: Add structure_kind and engine_family
        "structure_kind": structure_kind,
        "engine_family": engine_family,
    }
    (calculation_dir / "calculation.yaml").write_text(yaml.safe_dump(calculation_payload, sort_keys=False))

    # Add to project.qv.yml (DAG + ID-only: only calculation_id, no meta duplication)
    calculations_section.append({
        "calculation_id": calculation_meta_dict["id"],  # ID-only reference (ULID)
    })
    svc.project.update_config(config)

    typer.secho(f"Calculation '{calculation_id}' created at {calculation_dir}", fg=typer.colors.GREEN)



# Known step types for validation (Phase 2: engine-prefixed + legacy backward compat)
KNOWN_STEP_TYPES = {
    # Engine-prefixed step types (Phase 2)
    "qe_scf", "qe_nscf", "qe_relax", "qe_vc_relax", "qe_md", "qe_vc_md",  # QE pw.x
    "qe_dos", "qe_bands", "qe_bands_pw",  # QE post-processing
    "qe_ph", "qe_q2r", "qe_matdyn", "qe_dynmat",  # QE phonon
    "qe_pp", "qe_projwfc",  # QE other post-processing
    "qe_pw2wannier90", "qe_custom",  # QE other
    "w90_preproc", "w90_run",  # Wannier90
    "pyscf_scf",  # PySCF molecular QC
    # Legacy step types (backward compatibility)
    "scf", "nscf", "relax", "vc-relax", "md", "vc-md",  # pw.x calculation types
    "dos", "bands", "bands_pw",  # post-processing
    "ph", "q2r", "matdyn", "dynmat",  # phonon
    "pp", "projwfc",  # other post-processing
    "pw2wannier90", "custom",  # escape hatch for unsupported types
}


@init_app.command(
    "step",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def init_step_command(
    ctx: typer.Context,
    step_type: str = typer.Argument(..., help="QE calculation type (scf, nscf, relax, dos, etc.)"),
    structure: Optional[str] = typer.Option(
        None, "--structure", "-s", help="Structure id (optional if inside a calculation)"
    ),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    calculation: Optional[str] = typer.Option(
        None, "--calculation", help="Calculation id/slug to attach this step to"
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        help="Step display name/slug (defaults to step type or next available value)",
    ),
    index: Optional[int] = typer.Option(
        None,
        "--index",
        help="Insert position when attaching to a calculation (0-indexed, defaults to append).",
    ),
    auto_kpath: bool = typer.Option(
        False, "--auto-kpath", 
        help="Auto-generate high-symmetry k-path for band structure calculations (requires structure)"
    ),
    kpath_points: int = typer.Option(
        20, "--kpath-points",
        help="Number of k-points per segment when using --auto-kpath"
    ),
    no_defaults: bool = typer.Option(
        False, "--no-defaults",
        help="Do not apply in-code default parameters. Use only explicitly provided parameters. "
             "Useful when importing from an existing QE input file to preserve original parameters."
    ),
) -> None:
    """Create a StructureStepSpec YAML file and optionally attach it to a calculation.
    
    Step type is required and must be a known QE calculation type.
    Structure is optional if inside a calculation directory (inherits from calculation).
    
    By default, step is created with QV's in-code default parameters (outdir, restart_mode, 
    conv_thr, etc.) merged with any explicitly provided parameters. Use --no-defaults to create
    a step with only the explicitly provided parameters (useful for importing from existing QE inputs).
    
    For band structure steps, use --auto-kpath to automatically generate a 
    high-symmetry k-path using the structure's symmetry.
    
    Examples:
        qv init step scf --structure si                    # Uses defaults
        qv init step nscf                                  # inside calculation, inherits structure, uses defaults
        qv init step relax --structure si --calculation my_calculation
        qv init step bands --structure si --auto-kpath
        qv init step scf --no-defaults --CONTROL.calculation=scf  # Import mode, no defaults
    """
    # Validate step type
    if step_type.lower() not in KNOWN_STEP_TYPES:
        raise typer.BadParameter(
            f"Unknown step type '{step_type}'. "
            f"Known types: {', '.join(sorted(KNOWN_STEP_TYPES))}"
        )

    bundle = _parse_override_args(ctx.args)
    if bundle.has_any():
        typer.echo(f"Applying overrides: {_render_override_summary(bundle)}")

    # Determine project root: explicit --project, or auto-detect from cwd
    if project:
        project_root = Path(project).expanduser().resolve()
    else:
        try:
            project_root = _resolve_project_root()
        except typer.BadParameter:
            project_root = None

    # Determine calculation: explicit --calculation, or auto-detect from cwd using PathContext
    # Ensure svc is defined when project_root exists
    from quantumvitas.api import QVService
    if project_root:
        svc = get_service(project_root)
        config = svc.project.get_config()
    else:
        svc = None
        config = {"structures": [], "calculations": []}
    
    calculation_entry = None
    calculation_dir: Optional[Path] = None
    calculation_steps: list[dict] | None = None
    calculation_data = None
    existing_step_ids: list[str] = []
    parent_calculation_id: Optional[str] = None
    calculation_structure: Optional[str] = None

    if calculation:
        if not project_root:
            raise typer.BadParameter("Specify --project when using --calculation.")
        # Get calculation ref
        calc_resolved = svc.calculation.require_ref(calculation)
        calc_id = calc_resolved.meta.id if calc_resolved.meta else ""
        calculation_entry = _find_entry_by_calc_id(config, calc_id)
        # Get calculation directory from resolved resource
        if calc_resolved.absolute_path.name == "calculation.yaml":
            calculation_dir = calc_resolved.absolute_path.parent
        else:
            calculation_dir = calc_resolved.absolute_path
    elif project_root:
        # Try to detect enclosing calculation from cwd
        calc_ref = svc.calculation.resolve_enclosing_path(Path.cwd())
        if calc_ref:
            calc_id = calc_ref.calc_id
            calculation_entry = _find_entry_by_calc_id(config, calc_id)
            calculation_dir = (project_root / calc_ref.path).resolve()
        else:
            # Fall back to old method if resolve_enclosing_path fails
            detected = _detect_enclosing_calculation(
                project_root, Path.cwd().resolve(), config.get("calculations", [])
            )
            if detected:
                calc_ref = svc.calculation.require_ref(detected)
                calc_id = calc_ref.meta.id if calc_ref.meta else ""
                calculation_entry = _find_entry_by_calc_id(config, calc_id)
                calculation_dir = (project_root / calc_ref.absolute_path.parent).resolve() if calc_ref.absolute_path.name == "calculation.yaml" else calc_ref.absolute_path
    
    # If we still don't have a calculation, try fallback detection
    if not calculation_entry and project_root:
        # Fallback: check if we're inside a calculation directory by looking for calculation.yaml
        cwd_resolved = Path.cwd().resolve()
        project_root_resolved = project_root.resolve()
        
        # Check current directory and parent directories for calculation.yaml
        check_path = cwd_resolved
        found_calc_data = None
        found_calc_dir = None
        while check_path != project_root_resolved.parent and check_path != project_root_resolved:
            calc_yaml = check_path / "calculation.yaml"
            if calc_yaml.exists():
                # Found calculation.yaml - try to read it directly
                try:
                    calc_data = yaml.safe_load(calc_yaml.read_text()) or {}
                    calc_id = calc_data.get("meta", {}).get("id")
                    if calc_id:
                        # Try to find the entry by ID
                        calculation_entry = _find_entry_by_calc_id(config, calc_id)
                        calculation_dir = check_path
                        calculation_data = calc_data
                        break
                    else:
                        # No ID in calculation.yaml, but we can still use it for structure detection
                        found_calc_data = calc_data
                        found_calc_dir = check_path
                except Exception:
                    pass
            check_path = check_path.parent
        
        # If we found calculation.yaml but no entry, use the data we found
        if not calculation_entry and found_calc_data:
            calculation_data = found_calc_data
            calculation_dir = found_calc_dir
        
        # If still no calculation, check if we're at project root
        is_at_project_root = False
        if not calculation_entry:
            try:
                path_ctx = find_path_context_ref()
                # Compare resolved paths to handle symlinks and path differences
                if cwd_resolved == project_root_resolved and not path_ctx["is_inside_calculation"]:
                    is_at_project_root = True
            except APIError:
                # If we can't determine context but we have project_root, check if cwd matches project_root
                if cwd_resolved == project_root_resolved:
                    is_at_project_root = True
            
            # CRITICAL: disallow init step at project root without explicit calculation
            if is_at_project_root:
                typer.echo(
                    "Cannot initialize a step at the project root; "
                    "please run this command inside a calculation directory "
                    "or specify --calculation explicitly."
                )
                # The test inspects stdout, so we must echo to stdout, not stderr,
                # and then exit with a non-zero code.
                raise typer.Exit(code=1)

    if calculation_entry and project_root:
        # calculation_dir should already be set above
        if 'calculation_dir' not in locals():
            # Fallback: get from entry if not set
            calc_id = _get_calc_id_from_entry(calculation_entry)
            calc_ref = svc.calculation.require_ref(calc_id)
            calculation_dir = (project_root / calc_ref.absolute_path.parent).resolve() if calc_ref.absolute_path.name == "calculation.yaml" else calc_ref.absolute_path
        calculation_yaml = calculation_dir / "calculation.yaml"
        if not calculation_yaml.exists():
            raise typer.BadParameter(f"calculation.yaml not found under {calculation_dir}")
        calculation_data = yaml.safe_load(calculation_yaml.read_text()) or {}
        calculation_steps = calculation_data.setdefault("steps", [])
        existing_step_ids = [
            extract_step_selector_from_entry(step) 
            for step in calculation_steps 
            if extract_step_selector_from_entry(step)
        ]
        
        # Get parent calculation id and structure
        parent_calculation_id = extract_calculation_selector_from_entry(calculation_entry)
        if not parent_calculation_id:
            # Fallback to calculation.yaml meta.id
            parent_calculation_id = calculation_data.get("meta", {}).get("id") or calculation_data.get("id")
        # Structure: prefer structure_id (canonical), fall back to structure selector (legacy)
        calculation_structure_id = calculation_data.get("structure_id")
        calculation_structure = calculation_data.get("structure") or calculation_data.get("calculation", {}).get("structure")
    elif calculation_data and project_root:
        # We have calculation_data from fallback detection but no entry
        # This can happen if calculation.yaml exists but entry is missing from project.qv.yml
        calculation_structure_id = calculation_data.get("structure_id")
        calculation_structure = calculation_data.get("structure") or calculation_data.get("calculation", {}).get("structure")
        # Set calculation_steps and existing_step_ids for step creation
        calculation_steps = calculation_data.setdefault("steps", [])
        existing_step_ids = [
            extract_step_selector_from_entry(step) 
            for step in calculation_steps 
            if extract_step_selector_from_entry(step)
        ]
    else:
        calculation_structure_id = None
        calculation_structure = None

    # Resolve structure: use provided, or inherit from parent calculation
    if structure:
        structure_value = _resolve_structure_reference(
            structure, project_root, config if project_root else None
        )
    elif calculation_structure_id:
        # Calculation has structure_id - resolve it to get the selector for display
        try:
            resolved = svc.structure.require_ref(calculation_structure_id, config=config if project_root else None)
            structure_value = resolved.meta.slug or resolved.meta.name
            typer.echo(f"Using structure '{structure_value}' from calculation")
        except NotFoundError as e:
            raise typer.BadParameter(f"Calculation references structure_id '{calculation_structure_id}' which cannot be resolved: {e}") from e
    elif calculation_structure:
        structure_value = calculation_structure
        typer.echo(f"Using structure '{structure_value}' from calculation")
    else:
        raise typer.BadParameter(
            "Structure required. Either:\n"
            "  - Provide --structure <name>\n"
            "  - Run inside a calculation directory\n"
            "  - Use --calculation to specify a calculation that has a structure"
        )

    step_display_name, step_slug = _derive_step_identity(name or step_type, existing_step_ids)

    if calculation_dir is not None:
        spec_path = (calculation_dir / "steps" / f"{step_slug}.step.yaml").resolve()
    else:
        spec_path = (Path.cwd() / f"{step_slug}.step.yaml").resolve()

    if spec_path.exists():
        raise typer.BadParameter(
            f"Step spec '{spec_path}' already exists. Use qv configure step to modify it."
        )

    spec_path.parent.mkdir(parents=True, exist_ok=True)
    
    # If using a template, copy and modify it
    # Handle auto-kpath for band structure steps
    kpath_result = None
    kpath_card_overrides = {}
    if auto_kpath:
        if step_type.lower() not in ("bands", "bands_pw"):
            typer.secho(
                f"Warning: --auto-kpath is intended for band structure steps, not '{step_type}'",
                fg=typer.colors.YELLOW
            )
        
        # Load the structure to generate k-path
        try:
            pmg_struct, _ = _resolve_structure_input(project_root, structure_value)
        except Exception as exc:
            raise typer.BadParameter(
                f"--auto-kpath requires a valid structure. Error loading '{structure_value}': {exc}"
            ) from exc
        
        from quantumvitas.api import QVService
        
        try:
            kpath_result = QVService.generate_kpath(pmg_struct, points_per_segment=kpath_points)
            kpath_card = kpath_result.to_qe_kpoints_crystal_b()
            kpath_card_overrides["K_POINTS"] = kpath_card
            
            typer.echo(f"Generated k-path: {kpath_result.path_string()}")
            typer.echo(f"  Lattice type: {kpath_result.lattice_type}")
            typer.echo(f"  Spacegroup: {kpath_result.spacegroup_symbol} (#{kpath_result.spacegroup_number})")
            typer.echo(f"  {len(kpath_result.segments)} segments, {kpath_points} points each")
        except APIError as exc:
            raise typer.BadParameter(
                f"Failed to generate k-path for structure: {exc}"
            ) from exc

    # Get default parameters for this step type (if not in --no-defaults mode)
    from quantumvitas.api import QVService
    
    apply_defaults = not no_defaults
    
    if apply_defaults:
        defaults = QVService.get_default_step_params(step_type)
        default_params = defaults.get("parameters", {})
        default_cards = defaults.get("cards", {})
        default_species = defaults.get("species_overrides", {})
    else:
        # No defaults: start with empty dicts
        default_params = {}
        default_cards = {}
        default_species = {}
    
    # Merge user overrides with defaults (user overrides take precedence)
    params = dict(default_params)
    for section, section_params in _overrides_to_parameter_dict(bundle.parameters).items():
        if section not in params:
            params[section] = {}
        params[section].update(section_params)
    
    # Merge card overrides with defaults and auto-kpath (manual takes precedence)
    cards = dict(default_cards)
    if bundle.card_overrides:
        cards.update(bundle.card_overrides)
    for card_name, card_data in kpath_card_overrides.items():
        if card_name not in cards:  # Don't override manual K_POINTS
            cards[card_name] = card_data
    
    # Merge species overrides with defaults
    species = dict(default_species)
    if bundle.species_overrides:
        species.update(bundle.species_overrides)
        # Warn if step-level species_overrides are used in project runs
        import warnings
        warnings.warn(
            "Step-level species_overrides detected (--SPECIES.* flags). "
            "Project runs ignore step-level species_overrides and use calculation.yaml species_map instead. "
            "Configure species via `qv configure species ...` to set calculation-level species_map.",
            UserWarning,
            stacklevel=2,
        )
    
    # Resolve structure selector to structure_id
    # If calculation has structure_id, use that directly (canonical)
    structure_id = None
    if calculation_structure_id and project_root:
        # Calculation already has structure_id - use it directly (canonical reference)
        structure_id = calculation_structure_id
    elif structure_value and project_root:
        # Resolve structure selector to structure_id
        try:
            resolved_structure = svc.structure.require_ref(structure_value, config=config if project_root else None)
            structure_id = resolved_structure.meta.id
        except NotFoundError as e:
            # Structure is required - fail clearly
            raise typer.BadParameter(f"Structure not found: {e}")
    
    from quantumvitas.api.utils import meta_from_name
    step_meta_dict = meta_from_name("step", name=step_display_name, path="")
    # Build step spec as dict (no StructureStepSpec dependency)
    # DAG model: Step YAML does NOT contain structure_id or parent_calculation_id
    # Step inherits structure from calculation.structure_id at runtime
    # Step is associated with calculation via calculation.yaml's steps array
    spec: dict[str, Any] = {
        "meta": step_meta_dict,
        "step_type": step_type,
        "parameters": params,
        "cards": cards,
        "species_overrides": species,
    }
    # NOTE: Do NOT add structure, structure_id, or parent_calculation_id to spec
    # These are DAG relationships resolved at runtime
    if kpath_result:
        spec["kpath_metadata"] = kpath_result.to_dict()
    _write_step_spec(spec_path, spec, project_root=project_root)

    if calculation_entry and calculation_steps is not None and calculation_data is not None:
        assert calculation_dir is not None
        from quantumvitas.api.utils import ensure_relative_path
        rel_step_path = ensure_relative_path(spec_path, base=calculation_dir)
        insertion_index = (
            max(0, min(len(calculation_steps), index))
            if index is not None
            else len(calculation_steps)
        )
        # Use step_id (ULID) from step spec meta (canonical reference)
        # CalculationStepEntry removed - use dict directly
        # rel_step_path is already a relative path string from ensure_relative_path
        # Create step entry with only step_id (ULID) - no step_file (resolved via registry)
        step_entry = {
            "step_id": spec.get("meta", {}).get("id"),  # Use ULID from step spec meta (canonical reference)
            "type": step_type,
            # step_file is NOT stored - step location resolved via registry using step_id
        }
        calculation_steps.insert(
            insertion_index,
            step_entry,
        )
        # Remove legacy structure_name and structure fields before writing (DAG + ID-only constitution)
        calculation_data.pop("structure_name", None)
        calculation_data.pop("structure", None)
        if "calculation" in calculation_data:
            calculation_data["calculation"].pop("structure_name", None)
            calculation_data["calculation"].pop("structure", None)
        calculation_yaml = calculation_dir / "calculation.yaml"
        calculation_yaml.write_text(yaml.safe_dump(calculation_data, sort_keys=False))
        from quantumvitas.api import QVService
        typer.echo(
            f"Calculation '{entry_display_name(calculation_entry)}' updated with step id '{step_slug}'."
        )

    typer.echo(f"Step spec created at {spec_path}")


@app.command("save-project")
def save_project_command(
    output: Path = typer.Argument(..., help="Path to output YAML snapshot file"),
    project: Optional[Path] = typer.Option(
        None,
        "--project",
        help="Project root; if omitted, auto-detect from CWD",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Overwrite existing snapshot file if it exists",
    ),
) -> None:
    """
    Export the current project to a snapshot YAML file.
    
    The snapshot contains all project metadata, structures, calculations, and steps
    needed to recreate the project. Pseudopotential filenames are preserved
    but file contents are NOT embedded.
    
    Examples:
        qv save-project snapshot.yml
        qv save-project my-project-snapshot.yml --overwrite
    """
    from quantumvitas.api import QVService
    
    # Determine project root
    if project:
        project_root = Path(project).expanduser().resolve()
    else:
        ctx = find_path_context_ref()
        project_root = ctx["project_root"]
    
    if not (project_root / "project.qv.yml").exists():
        raise typer.BadParameter(f"Not a project: {project_root}")
    
    # Export snapshot
    output_path = Path(output).expanduser().resolve()
    try:
        QVService.save_project_snapshot(
            project_root=project_root,
            output_path=output_path,
            overwrite=overwrite,
        )
        typer.secho(
            f"Project snapshot saved to {output_path}",
            fg=typer.colors.GREEN
        )
    except APIError as e:
        raise typer.BadParameter(str(e))


@app.command("import-structure")
def import_structure_command(
    structure_file: Path = typer.Argument(
        ..., help="Input structure file (.cif, POSCAR, QE .in, .json, etc.)"
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
    # Resolve project root: if not explicitly provided, try cwd first, then fall back to structure file's directory
    # This is more robust: cwd is usually the project root when called from tests, but structure file's parent
    # works better when the file is outside the project or cwd is unstable in parallel execution
    if project:
        project_root = Path(project).resolve()
    else:
        try:
            # First try cwd (most common case, especially in tests with explicit cwd)
            project_root = _resolve_project_root()
        except typer.BadParameter:
            # Fall back to searching from structure file's directory
            structure_file_resolved = Path(structure_file).resolve()
            project_root = _resolve_project_root(start=structure_file_resolved.parent)
    project_root = project_root.resolve()

    from quantumvitas.api import get_service
    from quantumvitas.api.utils import read_structure, write_structure, slugify, generate_unique_name_and_slug, ensure_relative_path, meta_from_name
    from quantumvitas.api import QVService
    
    # Read structure from file
    struct = read_structure(structure_file)
    svc = get_service(project_root=project_root)
    config = svc.project.get_config()
    structures_section = config.setdefault("structures", [])
    existing_slugs = svc.project.collect_slugs(structures_section)

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

    metadata_dict = meta_from_name("structure", name=structure_name, path=write_rel)
    write_structure(struct, out_path, format=output_format, metadata=metadata_dict)

    # DAG + ID-only: only structure_id, no meta duplication
    structures_section.append({
        "structure_id": metadata_dict.get("id"),  # ID-only reference (ULID)
    })
    svc.project.update_config(config)

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
    # Engine config is handled via API, not direct EngineConfig
    config_dict = None
    if path:
        config_dict = {"name": "qe", "qe_home": str(path)}
    registry = QVService.create_default_registry(config_dict)
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
    target: Optional[Path] = typer.Argument(
        None, help="[DEPRECATED] Step spec (.yaml) or QE input (.in). Use --calculation + --step instead."
    ),
    calculation: Optional[str] = typer.Option(
        None, "--calculation", "-w", help="Calculation selector (name, slug, path, or ULID). Auto-detected from cwd if omitted."
    ),
    step: Optional[str] = typer.Option(
        None, "--step", "-s", help="Step selector (name, slug, ULID, or step_type). Auto-detected from cwd if omitted."
    ),
    working_dir: Optional[Path] = typer.Option(
        None, "--workdir", help="Temporary working directory (project mode only)"
    ),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root. Auto-detected from cwd if omitted."
    ),
    standalone: bool = typer.Option(
        False, "--standalone", help="Run in standalone mode (no project context)"
    ),
    input: Optional[Path] = typer.Option(
        None, "--input", help="QE input file (required in standalone mode)"
    ),
    engine: Optional[str] = typer.Option(
        None, "--engine", help="Engine name (standalone mode only, default: auto-detect from input)"
    ),
    bidirectional: bool = typer.Option(
        False, "--bidirectional", help="[DEPRECATED] Standalone mode always does roundtrip. This flag is ignored."
    ),
) -> None:
    """
    Run a single QE input file or step spec.
    
    Two execution modes:
    
    1. Project mode (default):
       - Requires: --project (or auto-detect) + --calculation + --step selectors
       - Uses registry-based resolution: calculation → step → structure (via calculation.structure_id)
       - Structure is resolved from calculation.structure_id (DAG model: calculation owns structure)
       - Deprecated: bare step YAML file path (target argument)
         - When provided, calculation is inferred from step path via registry
         - Structure is still resolved from calculation.structure_id (not from step YAML)
    
    2. Standalone mode (--standalone):
       - Requires: --standalone + --input (QE input file)
       - No project context: parses → overrides → pseudo → generates → runs
       - Always performs full roundtrip: original input preserved as <stem>.raw.in
    """
    # Validate mutual exclusion
    if standalone:
        # Standalone mode: require --input, disallow project-related options
        if project:
            raise typer.BadParameter(
                "--project cannot be used with --standalone. "
                "Standalone mode does not use project context."
            )
        if not input:
            raise typer.BadParameter(
                "--input is required in standalone mode. "
                "Example: qv run step --standalone --input pw.in"
            )
        if target:
            raise typer.BadParameter(
                "Positional argument (target) cannot be used with --standalone. "
                "Use --input instead."
            )
        
        # Run standalone mode (bidirectional flag is ignored - standalone always does roundtrip)
        _run_standalone_step(
            input_file=input,
            workdir=working_dir,
            engine_name=engine,
        )
        return
    
    # Project mode: disallow standalone-only flags
    if bidirectional:
        typer.echo("Warning: --bidirectional is only meaningful in standalone mode (which always does roundtrip). Ignoring flag.")
    
    # Project context functions now via QVService
    from quantumvitas.api import QVService, NotFoundError, get_service

    cwd = Path.cwd()
    try:
        # ProjectContext removed - use QVService methods directly
        svc = get_service(project or cwd)
        project_root = svc.project_root
    except NotFoundError as e:
        raise typer.BadParameter(
            f"Project not found: {e}. "
            "Run inside a project directory or specify --project <path>. "
            "For standalone execution, use --standalone --input <file>."
        ) from e

    # If target is provided (legacy support), try to resolve step from it
    # This will also resolve the calculation from the step path
    if target:
        # Legacy: if target is a step YAML, try to resolve it via registry
        if target.suffix.lower() in {".yaml", ".yml"}:
            typer.echo(
                "Warning: Using step YAML file directly is deprecated. "
                "Use --calculation <selector> --step <selector> instead.",
                err=True
            )
            # Try to find the step in the registry by path
            step_path = target.resolve()
            try:
                rel_path = step_path.relative_to(project_root)
                # Extract calculation and step from path (e.g., calculations/wf/steps/scf.step.yaml)
                if "calculations" in rel_path.parts and "steps" in rel_path.parts:
                    # Find calculation slug from path
                    calculations_idx = rel_path.parts.index("calculations")
                    if calculations_idx + 1 < len(rel_path.parts):
                        calculation_slug = rel_path.parts[calculations_idx + 1]
                        # Resolve calculation from slug
                        calculation_resolved = svc.calculation.require_ref(calculation_slug)
                        # Extract step selector from filename
                        step_selector = step_path.stem.replace(".step", "")
                        calc_selector = calculation_resolved.meta.id if calculation_resolved.meta else calculation_slug
                        step_resolved = svc.calculation.require_step_ref(calc_selector, step_selector)
                    else:
                        raise typer.BadParameter(
                            f"Step file {target} path is invalid. "
                            "Please use --calculation <selector> --step <selector> instead."
                        )
                else:
                    # Try to find step in registry by absolute path
                    registry = svc.project.build_resource_index()
                    # Look for step by path in registry
                    step_found = None
                    for path, resource_id in registry.by_path.items():
                        if path == step_path:
                            meta = registry.by_id.get(resource_id)
                            if meta and meta.kind == "step":
                                # Find parent calculation from step path
                                step_rel = Path(path).relative_to(project_root)
                                if "calculations" in step_rel.parts and "steps" in step_rel.parts:
                                    calculations_idx = step_rel.parts.index("calculations")
                                    if calculations_idx + 1 < len(step_rel.parts):
                                        calculation_slug = step_rel.parts[calculations_idx + 1]
                                        calculation_resolved = svc.calculation.require_ref(calculation_slug)
                                        calc_selector = calculation_resolved.meta.id if calculation_resolved.meta else calculation_slug
                                        step_resolved = svc.calculation.require_step_ref(calc_selector, meta.slug or meta.name or meta.id)
                                        step_found = True
                                        break
                    if not step_found:
                        raise typer.BadParameter(
                            f"Step file {target} is not in a calculation steps directory. "
                            "Please use --calculation <selector> --step <selector> instead."
                        )
            except (ValueError, NotFoundError) as e:
                raise typer.BadParameter(
                    f"Cannot resolve step from {target}: {e}. "
                    "Please use --calculation <selector> --step <selector> instead."
                ) from e
        else:
            # Target is a QE input file - not supported in project mode
            raise typer.BadParameter(
                f"QE input file '{target}' cannot be used in project mode. "
                "Use --calculation <selector> --step <selector> to run a step, "
                "or use --standalone --input <file> for standalone execution."
            )
    else:
        # No target - resolve calculation first, then step
        try:
            calculation_resolved = svc.calculation.require_ref(calculation)
        except Exception as e:
            from quantumvitas.api.errors import NotFoundError
            if isinstance(e, NotFoundError):
                raise typer.BadParameter(str(e)) from e
            raise

        # Use --step option or auto-detect
        try:
            calc_selector = calculation_resolved.meta.id if calculation_resolved.meta else calculation
            step_resolved = svc.calculation.require_step_ref(calc_selector, step)
        except Exception as e:
            from quantumvitas.api.errors import NotFoundError
            if isinstance(e, NotFoundError):
                raise typer.BadParameter(str(e)) from e
            raise

    # Run step via QVService (registry-based, uses calculation.structure_id)
    from quantumvitas.api import QVService

    try:
        result = QVService.run_step(
            project_root=project_root,
            calculation_selector=calculation_resolved.meta.slug or calculation_resolved.meta.name or calculation_resolved.meta.id,
            step_selector=step_resolved.meta.slug or step_resolved.meta.name or step_resolved.meta.id,
        )
        
        # Always print "Step finished" line as CLI contract (test requirement)
        # Match expected test output format: "Step finished: <output> -> (input <input>)"
        input_file = result.get("input_file") or step_resolved.absolute_path
        
        # Priority-based output file selection (no filename inference):
        # 1. primary output_file (from StepResult.output_file)
        # 2. stdout_file (from StepResult.stdout_file)
        # 3. input_file (last resort, with warning)
        output_file = result.get("output_file")
        if not output_file:
            output_file = result.get("stdout_file")
        if not output_file:
            # Last resort: use input_file, but this should be rare
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"No output file provided for step {step_resolved.meta.name or step_resolved.meta.slug}, using input_file as fallback")
            output_file = str(input_file)
        
        typer.echo(f"Step finished: {output_file} -> (input {input_file})")
        if result.get("error"):
            typer.echo(f"Error: {result['error']}", err=True)
            raise typer.Exit(1)
    except Exception as e:
        raise typer.BadParameter(f"Failed to run step: {e}") from e


def _run_standalone_step(
    input_file: Path,
    workdir: Optional[Path],
    engine_name: Optional[str],
) -> None:
    """
    Run a step in standalone mode.
    
    Standalone mode performs roundtrip: import .in to YAML, then run from YAML.
    This ensures standalone uses the same production run pipeline (YAML SSOT → clean rewrite .in).
    See docs/dev/exec-pipeline-ssot-contract.md for details.
    
    Args:
        input_file: Path to QE input file
        workdir: Working directory (defaults to current directory)
        engine_name: Engine name (defaults to "qe")
    """
    import tempfile
    import shutil
    from quantumvitas.api import QVService
    
    input_path = Path(input_file).resolve()
    if not input_path.exists():
        raise typer.BadParameter(f"Input file not found: {input_path}")
    
    # Default workdir to current directory
    if workdir:
        workdir_path = Path(workdir).resolve()
    else:
        workdir_path = Path.cwd()
    workdir_path.mkdir(parents=True, exist_ok=True)
    
    # Create engine (for now, only QE is supported)
    if engine_name and engine_name != "qe":
        raise typer.BadParameter(
            f"Engine '{engine_name}' not supported in standalone mode. "
            "Only 'qe' is currently supported."
        )
    
    # Engine config handled via API (no EngineConfig dependency)
    
    # Step 1: Import .in to YAML (roundtrip: import→YAML→run)
    typer.echo("Standalone QE run (import→YAML→run):")
    typer.echo(f"  workdir: {workdir_path}")
    typer.echo(f"  input:   {input_path}")
    
    # Create temporary directory for import (we'll clean it up after)
    temp_import_dir = workdir_path / ".qv_standalone_import"
    temp_import_dir.mkdir(exist_ok=True)
    temp_structure_dir = temp_import_dir / "structures"
    temp_structure_dir.mkdir(exist_ok=True)
    
    try:
        # Import .in to step.yaml
        import_result = build_step_spec_from_qe_input(
            input_file=input_path,
            destination_dir=temp_import_dir,
            structure_dir=temp_structure_dir,
            step_id=None,  # Will generate ULID
            structure_id=None,  # Will be auto-generated from input
            reference_structure_by="id",
            apply_defaults=False,  # Preserve original parameters
        )
        
        spec = import_result.spec
        spec_path = import_result.spec_path
        
        # Step 2: Materialize step from YAML (generates .in from step.yaml)
        # Use a temporary calculation_dir (doesn't need to exist, just for naming)
        temp_calc_dir = temp_import_dir / "calc"
        temp_calc_dir.mkdir(exist_ok=True)
        
        # Resolve structure for materialization
        structure = None
        if import_result.structure_path and import_result.structure_path.exists():
            structure = read_structure(import_result.structure_path)
        
        # Materialize step (generates .in from step.yaml)
        # For standalone, use workdir as project_root for pseudo resolution (workdir/pseudo)
        # Create QVService instance for materialize_step_spec
        svc = get_service(workdir_path)  # Standalone: use workdir as project root
        generated_input, materialized_spec = svc.materialize_step_spec(
            spec=spec,
            output_dir=workdir_path,
            calculation_dir=temp_calc_dir,
            project=None,  # Standalone: no project context
            spec_path=spec_path,
            input_name=None,  # Use default naming
            project_root=workdir_path,  # Standalone: use workdir as pseudo base (workdir/pseudo)
        )
        
        # Step 3: Run step using production pipeline (Step.run() → engine directly)
        # Create Step object
        # Create step dict for execution (no Step object dependency)
        step_meta = spec.get("meta", {})
        step_dict = {
            "meta": step_meta,
            "input_file": str(generated_input),
            "engine": "qe",
            "step_type": spec.get("step_type"),
            "options": {},
        }
        # Note: Step execution is handled via API, not direct Step object
        
        # Run using production pipeline via API
        result, prepared = QVService.run_input_step(
            engine="qe",
            input_file=generated_input,
            working_dir=workdir_path,
            project_root=workdir_path,  # Standalone: use workdir as pseudo base (workdir/pseudo)
            step_type=spec.get("step_type"),
            keep_original=False,
        )
        
        typer.echo(f"Step finished: {result.output_file}")
        
    finally:
        # Clean up temporary import directory
        if temp_import_dir.exists():
            shutil.rmtree(temp_import_dir, ignore_errors=True)


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
        "--type",
        help="QE calculation type (scf, nscf, relax, etc.).",
    ),
) -> None:
    """
    Generate a QE input from a stored structure + CLI parameters, then run it.
    """
    registry = QVService.create_default_registry()
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

    from quantumvitas.api import QVService
    svc = get_service(project_root)
    qe_input = svc.generate_qe_input_from_structure(
        structure=struct,
        step_type=step_type,
        parameter_overrides=bundle.parameters,
    )
    QVService.apply_card_overrides_to_qe_input(qe_input, bundle.card_overrides)
    QVService.apply_species_overrides_to_qe_input(qe_input, bundle.species_overrides)

    generated_name = input_name or f"{struct_name}_{step_type}.pw.in"
    generated_input = workdir / generated_name
    write_qe_input_file(qe_input, generated_input)

    result, prepared = QVService.run_input_step(
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
    Display project resources (structures/calculations) as a tree.
    """

    project_root = project or _resolve_project_root()
    from quantumvitas.api import get_service
    from quantumvitas.api.utils import slugify
    svc = get_service(project_root)
    config = svc.project.get_config()
    
    # Get project metadata from config
    project_section = config.get("project", {})
    project_meta = project_section.get("meta", {})
    project_name = project_section.get("name") or project_root.name
    project_slug = project_meta.get("slug") or slugify(project_name)
    project_id = project_meta.get("id") or ""
    
    typer.echo(f"Project: {project_name} [{project_slug}] ({project_root})")
    if verbose:
        typer.echo(f"  id: {project_id}")
    
    typer.echo("\nStructures:")
    structures = svc.structure.list()
    if not structures:
        typer.echo("  (none)")
    for struct_dto in sorted(structures, key=lambda s: s.meta.name if s.meta else ""):
        # Find calculations using this structure
        struct_entry = None
        struct_slug = struct_dto.meta.slug if struct_dto.meta else ""
        struct_name = struct_dto.meta.name if struct_dto.meta else ""
        for entry in config.get("structures", []):
            if entry_matches(entry, struct_slug) or entry_matches(entry, struct_name):
                struct_entry = entry
                break
        
        using_calculations = []
        if struct_entry:
            using_wfs = calculations_using_structure(project_root, config, struct_entry)
            using_calculations = [
                (wf.get("meta") or {}).get("slug") or wf.get("name")
                for wf in using_wfs
            ]
        
        struct_path = struct_dto.meta.path if struct_dto.meta else ""
        line = f"  - {struct_name} [{struct_slug}] -> {struct_path}"
        if using_calculations:
            line += f"  (used by: {', '.join(using_calculations)})"
        if verbose:
            struct_id = struct_dto.meta.id if struct_dto.meta else ""
            line += f" (id: {struct_id})"
        typer.echo(line)

    typer.echo("\nCalculations:")
    calculations = svc.calculation.list()
    if not calculations:
        typer.echo("  (none)")
    for calc_dto in sorted(calculations, key=lambda c: c.meta.name if c.meta else ""):
        # Find structures used by this calculation
        calc_id = calc_dto.calc_id
        # Resolve calculation to get directory
        calc_resolved = svc.calculation.require_ref(calc_id, config=config)
        calc_dir = calc_resolved.absolute_path
        if calc_dir.name == "calculation.yaml":
            calc_dir = calc_dir.parent
        wf_structures = _find_calculation_structures(calc_dir, project_root, config)
        struct_info = f"  (structure: {', '.join(wf_structures)})" if wf_structures else ""
        
        calc_slug = calc_dto.meta.slug if calc_dto.meta else ""
        calc_path = calc_dto.meta.path if calc_dto.meta else ""
        line = f"  - {calc_dto.meta.name if calc_dto.meta else ''} [{calc_slug}] -> {calc_path}{struct_info}"
        if verbose:
            line += f" (id: {calc_id})"
        typer.echo(line)
        step_summaries = _calculation_step_summaries(calc_dir)
        if not step_summaries:
            typer.echo("    (no steps)")
            continue
        for step_display_name, rel_path, step_meta in step_summaries:
            # Display: step name [ULID] -> step_file
            # ULID is the canonical identifier for qv delete step
            step_id_display = step_meta.id if step_meta else "-"
            step_line = f"    - {step_display_name} [{step_id_display}] -> {rel_path or '(inline)'}"
            if verbose and step_meta:
                # In verbose mode, also show slug if different from name
                if step_meta.slug and step_meta.slug != step_meta.name:
                    step_line += f" (slug: {step_meta.slug})"
            elif rel_path is None:
                step_line += " (missing step_file)"
            typer.echo(step_line)


def _find_calculation_structures(calculation_dir: Path, project_root: Path, config: dict) -> list[str]:
    """
    Find all structures referenced by a calculation.
    
    In the new DAG model, structure is resolved via calculation.structure_id,
    not from individual step files.
    """
    import yaml
    structures: set[str] = set()
    
    # First, check calculation.yaml for structure_id (canonical reference)
    calculation_yaml = calculation_dir / "calculation.yaml"
    if calculation_yaml.exists():
        try:
            data = yaml.safe_load(calculation_yaml.read_text()) or {}
            structure_id = data.get("structure_id")
            if structure_id:
                # Resolve structure_id to structure name/slug via API
                from quantumvitas.api import get_service
                svc = get_service(project_root)
                try:
                    struct_resolved = svc.structure.require_ref(structure_id, config=config)
                    if struct_resolved.meta:
                        structures.add(struct_resolved.meta.name or struct_resolved.meta.slug or structure_id)
                except Exception:
                    # Fallback to structure_id if resolution fails
                    structures.add(structure_id)
        except Exception:
            pass
    
    # Also check legacy structure field for backwards compatibility
    if calculation_yaml.exists():
        try:
            data = yaml.safe_load(calculation_yaml.read_text()) or {}
            legacy_structure = data.get("structure")
            if legacy_structure:
                structures.add(legacy_structure)
        except Exception:
            pass
    
    return sorted(structures)


def _calculation_step_summaries(calculation_dir: Path) -> list[tuple[str, Optional[str], Optional[dict[str, Any]]]]:
    """
    Get step summaries for a calculation.
    
    Returns list of (step_display_name, step_file, step_meta) tuples.
    step_display_name: from step's meta.name if available, otherwise step type or "(unnamed)"
    step_meta: dict[str, Any] from step file (contains ULID)
    
    In the new DAG + ID-only model:
    - Steps in calculation.yaml have step_id (ULID), not step_file
    - Step file location is resolved via ResourceIndex using step_id
    """
    calculation_yaml = calculation_dir / "calculation.yaml"
    if not calculation_yaml.exists():
        return []
    try:
        data = yaml.safe_load(calculation_yaml.read_text()) or {}
    except Exception:
        return []
    
    # Get project root to build ResourceIndex
    project_root = calculation_dir.parent.parent  # calculations/<slug> -> calculations -> project_root
    if not (project_root / "project.qv.yml").exists():
        # Fallback: try parent of calculations dir
        project_root = calculation_dir.parent
        if not (project_root / "project.qv.yml").exists():
            project_root = None
    
    # Build ResourceIndex to resolve step_id (ULID) to step files
    index = None
    config = None
    if project_root:
        try:
            from quantumvitas.api import QVService
            svc = get_service(project_root)
            index = svc.project.build_resource_index()
            config = svc.project.get_config()
        except Exception:
            pass
    
    # Get calculation selector for require_step
    calculation_meta = data.get("meta", {})
    calculation_slug = calculation_meta.get("slug") or calculation_dir.name
    
    summaries: list[tuple[str, Optional[str], Optional[dict[str, Any]]]] = []
    for step_entry in data.get("steps", []):
        rel_path: Optional[str] = None
        step_meta: Optional[dict[str, Any]] = None
        step_display_name = "(unnamed)"
        
        # New DAG model: step_id (ULID) is the canonical reference
        step_id_ulid = extract_step_selector_from_entry(step_entry)
        
        # Legacy: step_file (for backwards compatibility)
        legacy_step_file = step_entry.get("step_file")
        
        # Try to resolve step file using ResourceIndex
        if step_id_ulid and index and project_root:
            try:
                # Use QVService to resolve step
                from quantumvitas.api import QVService
                svc = get_service(project_root)
                step_resolved = svc.calculation.require_step_ref(calculation_slug, step_id_ulid, config=config)
                if step_resolved.absolute_path:
                    # Calculate relative path from calculation_dir
                    try:
                        rel_path = str(step_resolved.absolute_path.relative_to(calculation_dir))
                    except ValueError:
                        # If not relative, use absolute path
                        rel_path = str(step_resolved.absolute_path)
                    
                    # Load step spec to get meta (dict-based, no StructureStepSpec)
                    try:
                        spec_dict = yaml.safe_load(step_resolved.absolute_path.read_text())
                        if spec_dict:
                            meta = spec_dict.get("meta", {})
                            step_display_name = meta.get("name") or spec_dict.get("step_type") or "(unnamed)"
                        else:
                            step_display_name = step_resolved.absolute_path.stem.replace(".step", "") or "(unnamed)"
                    except Exception:
                        # If we can't load, infer from filename
                        step_display_name = step_resolved.absolute_path.stem.replace(".step", "") or "(unnamed)"
            except Exception as e:
                # Resolution failed - mark as missing
                step_display_name = f"(missing: {step_id_ulid[:8]}...)"
        elif legacy_step_file:
            # Legacy: use step_file if available
            spec_path = (calculation_dir / legacy_step_file).resolve()
            if spec_path.exists():
                try:
                    spec_dict = yaml.safe_load(spec_path.read_text())
                    if spec_dict:
                        step_meta = spec_dict.get("meta", {})
                        step_display_name = step_meta.get("name") or spec_dict.get("step_type") or "(unnamed)"
                    else:
                        step_display_name = spec_path.stem.replace(".step", "") or "(unnamed)"
                    rel_path = legacy_step_file
                except Exception:
                    step_display_name = spec_path.stem.replace(".step", "") or "(unnamed)"
                    rel_path = legacy_step_file
        elif step_id_ulid:
            # Have ULID but couldn't resolve - mark as missing
            step_display_name = f"(missing: {step_id_ulid[:8]}...)"
        else:
            # Legacy: try old id field (already handled by extract_step_selector_from_entry)
            # If we got here, step_id_ulid is None, so no valid selector found
            step_display_name = "(invalid entry)"
        
        summaries.append((step_display_name, rel_path, step_meta))
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
    [DEPRECATED] Rename a structure resource (updates name/slug/path).
    
    Use 'qv configure structure' instead:
        qv configure structure <identifier> --name "New Name"
    """
    typer.secho(
        "DEPRECATED: 'qv rename structure' is deprecated. Use:\n"
        f"  qv configure structure {identifier} --name \"<new_name>\"\n",
        fg=typer.colors.YELLOW,
    )

    project_root = project or _resolve_project_root()
    from quantumvitas.api import QVService
    from quantumvitas.api.errors import ConfigError, NotFoundError
    
    try:
        svc = get_service(project_root)
        # Resolve structure via domain method (handles registry sync)
        ref = svc.structure.require_ref(identifier)
        structure_id = ref.meta.id if ref.meta else None
        if not structure_id:
            raise typer.BadParameter(f"Structure '{identifier}' has no ID")
        
        # Get config and find entry by structure_id
        config = svc.project.get_config()
        entry = _find_entry_by_structure_id(config, structure_id)

        # Apply rename via domain method (guarantees index consistency)
        svc.project.apply_structure_rename(
            entry=entry,
            new_name=name,
            new_slug=slug,
            new_path=path,
            config=config,
        )
        svc.project.update_config(config)
    except (ConfigError, NotFoundError) as e:
        # Registry sync or not found errors - provide user-friendly message
        if isinstance(e, ConfigError) and e.code == "REGISTRY_OUT_OF_SYNC":
            typer.secho(
                f"\n❌ Registry Out of Sync",
                fg=typer.colors.RED,
                bold=True,
            )
            typer.echo(f"\n{e.message}")
            if e.context.get("expected_path"):
                typer.echo(f"\nExpected path: {e.context['expected_path']}")
            typer.echo(
                "\n💡 To fix this, refresh the project registry:\n"
                "   - In the GUI: Click the 'Refresh' button in the Structures panel\n"
                "   - Or reopen the project in the GUI (registry rebuilds on project load)"
            )
            raise typer.Exit(1)
        raise typer.BadParameter(str(e)) from e
    except Exception as e:
        if os.environ.get("QV_DEBUG_CLI") == "1":
            import sys
            print(f"DEBUG: rename_structure error: {type(e).__name__}: {e}", file=sys.stderr)
            print(f"DEBUG: identifier={identifier}, project_root={project_root}", file=sys.stderr)
            if hasattr(e, 'cause'):
                print(f"DEBUG: cause={e.cause}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
        raise

    typer.secho("Structure updated successfully.", fg=typer.colors.GREEN)


@rename_app.command("calculation")
def rename_calculation_command(
    identifier: str = typer.Argument(..., help="Calculation name/slug/path"),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    name: Optional[str] = typer.Option(None, "--name", help="New calculation name"),
    slug: Optional[str] = typer.Option(None, "--slug", help="Custom slug"),
    path: Optional[Path] = typer.Option(
        None, "--path", help="New relative path for the calculation directory"
    ),
) -> None:
    """
    [DEPRECATED] Rename a calculation resource (updates name/slug/path).
    
    Use 'qv configure calculation' instead:
        qv configure calculation <identifier> --name "New Name"
    """
    typer.secho(
        "DEPRECATED: 'qv rename calculation' is deprecated. Use:\n"
        f"  qv configure calculation {identifier} --name \"<new_name>\"\n",
        fg=typer.colors.YELLOW,
    )

    project_root = project or _resolve_project_root()
    from quantumvitas.api import QVService
    svc = get_service(project_root)
    config = svc.project.get_config()
    calc_dto = svc.calculation.get(identifier)
    entry = _find_entry_by_calc_id(config, calc_dto.calc_id)

    svc.project.apply_calculation_rename(
        entry=entry,
        new_name=name,
        new_slug=slug,
        new_path=path,
        config=config,
    )
    svc.project.update_config(config)

    typer.secho("Calculation updated successfully.", fg=typer.colors.GREEN)


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
    from quantumvitas.api import QVService
    svc = get_service(project_root)
    config = svc.project.get_config()

    updated = False
    project_section = config.setdefault("project", {})
    meta = project_section.setdefault("meta", {})

    original_slug = meta.get("slug")
    slug_changed = False

    if name or slug:
        current_name = project_section.get("name") or meta.get("name") or "project"
        next_name = name or current_name
        slug_source = slug or next_name
        from quantumvitas.api.utils import slugify
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
        svc.project.update_config(config)
        typer.secho("Project metadata updated.", fg=typer.colors.GREEN)
        if path is not None:
            typer.secho(f"Project moved to {project_root}", fg=typer.colors.GREEN)
    else:
        typer.secho("Nothing to update.", fg=typer.colors.YELLOW)


@rename_app.command("step")
def rename_step_command(
    calculation: str = typer.Argument(..., help="Calculation name/slug/path containing the step"),
    step_id: str = typer.Argument(..., help="Existing step id within the calculation"),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    new_id: Optional[str] = typer.Option(
        None, "--id", help="New step id (must be unique within the calculation)"
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        help="Rename or relocate the step spec file (relative to the calculation directory unless absolute).",
    ),
) -> None:
    """
    Rename a calculation step or move its spec file.
    """

    project_root = (project or _resolve_project_root()).resolve()
    from quantumvitas.api import QVService
    svc = get_service(project_root)
    config = svc.project.get_config()
    calc_dto = svc.calculation.get(calculation)
    calculation_entry = _find_entry_by_calc_id(config, calc_dto.calc_id)
    # Get calculation directory from calc_id
    calc_id = _get_calc_id_from_entry(calculation_entry)
    calc_resolved = svc.calculation.require_ref(calc_id)
    if calc_resolved.absolute_path.name == "calculation.yaml":
        calculation_dir = calc_resolved.absolute_path.parent
    else:
        calculation_dir = calc_resolved.absolute_path
    calculation_yaml = calculation_dir / "calculation.yaml"
    if not calculation_yaml.exists():
        raise typer.BadParameter(f"calculation.yaml not found at {calculation_yaml}")

    data = yaml.safe_load(calculation_yaml.read_text()) or {}
    steps: list[dict] = data.get("steps") or []
    
    # Find step by matching selector (ID-only model uses step_id)
    target_step = None
    for step in steps:
        step_selector = extract_step_selector_from_entry(step)
        if step_selector == step_id:
            target_step = step
            break
    
    if not target_step:
        raise typer.BadParameter(
            f"Step '{step_id}' not found in calculation '{calculation_entry.get('name')}'."
        )

    if new_id:
        # Check for duplicate step_id
        if any(extract_step_selector_from_entry(step) == new_id for step in steps if step is not target_step):
            raise typer.BadParameter(
                f"Step id '{new_id}' already exists in calculation '{calculation_entry.get('name')}'."
            )
        # Update step_id (ID-only model)
        target_step["step_id"] = new_id
        # Also update legacy id for backwards compatibility
        target_step["id"] = new_id

    source_rel = target_step.get("step_file")
    if not source_rel:
        raise typer.BadParameter("Step entry is missing its step_file.")
    source_path = (calculation_dir / source_rel).resolve()
    if not source_path.exists():
        raise typer.BadParameter(f"Step file '{source_rel}' does not exist.")
    # Load step spec as dict (no StructureStepSpec dependency)
    spec_dict = yaml.safe_load(source_path.read_text())
    if not spec_dict:
        raise typer.BadParameter(f"Step file '{source_rel}' is empty or invalid.")
    spec = spec_dict

    destination_path = source_path
    if path is not None:
        destination_path = Path(path)
        if not destination_path.is_absolute():
            destination_path = (calculation_dir / destination_path).resolve()
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_path), str(destination_path))
        from quantumvitas.api.utils import ensure_relative_path
        target_step["step_file"] = ensure_relative_path(destination_path, base=calculation_dir)
    elif new_id:
        rel_source = Path(source_rel)
        new_filename = rel_source.with_name(f"{new_id}.step.yaml")
        destination_path = (calculation_dir / new_filename).resolve()
        if destination_path.exists():
            raise typer.BadParameter(
                f"Step file '{new_filename}' already exists. Use --path to pick a custom filename."
            )
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_path), str(destination_path))
        from quantumvitas.api.utils import ensure_relative_path
        target_step["step_file"] = ensure_relative_path(destination_path, base=calculation_dir)

    step_file_rel = target_step.get("step_file")
    if step_file_rel:
        spec_path = (calculation_dir / step_file_rel).resolve()
        from quantumvitas.api.utils import ensure_relative_path
        relative_project = ensure_relative_path(spec_path, base=project_root)
        # Update meta in dict
        if "meta" not in spec:
            spec["meta"] = {}
        if new_id:
            spec["meta"]["name"] = new_id
        spec["meta"]["path"] = relative_project
        spec_path.write_text(yaml.safe_dump(spec, sort_keys=False))

    # Remove legacy structure_name and structure fields before writing (DAG + ID-only constitution)
    data.pop("structure_name", None)
    data.pop("structure", None)
    if "calculation" in data:
        data["calculation"].pop("structure_name", None)
        data["calculation"].pop("structure", None)
    calculation_yaml.write_text(yaml.safe_dump(data, sort_keys=False))
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
        help="Delete even if calculations reference the structure (leaves broken references).",
    ),
    cascade: bool = typer.Option(
        False,
        "--cascade",
        help="Delete calculations referencing this structure before deleting the structure itself.",
    ),
) -> None:
    """
    Remove a structure entry and move its file (and optionally dependent calculations) to trash.
    """

    project_root = (project or _resolve_project_root()).resolve()
    from quantumvitas.api import QVService
    from quantumvitas.api.errors import InternalError
    
    from quantumvitas.api.errors import ConfigError, NotFoundError
    
    try:
        svc = get_service(project_root)
        # Resolve structure via domain method (handles registry sync)
        ref = svc.structure.require_ref(identifier)
        structure_id = ref.meta.id if ref.meta else None
        if not structure_id:
            raise typer.BadParameter(f"Structure '{identifier}' has no ID")
        
        # Get config and find entry by structure_id
        config = svc.project.get_config()
        entry = _find_entry_by_structure_id(config, structure_id)
        trash_dir = (project_root / "trash").resolve()

        # Find calculations using this structure
        # Schema-agnostic implementation (no kernel types)
        import yaml
        from pathlib import Path
        
        def _structure_reference_tokens(entry: dict, project_root: Path) -> tuple[set[str], Path | None]:
            """Get all identifiers and resolved path for a structure entry."""
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
            spec: object,
            spec_path: Path,
            aliases: set[str],
            resolved_path: Path | None,
        ) -> bool:
            """Check if a step spec (dict) references a structure by recursively scanning for matching tokens."""
            def _scan_value(value: object) -> bool:
                """Recursively scan a value for structure references."""
                if isinstance(value, str):
                    # Check if string equals any token or contains token as path segment
                    value_lower = value.strip().lower()
                    if value_lower in aliases:
                        return True
                    # Check if string is a path that matches resolved_path
                    if resolved_path:
                        try:
                            candidate = Path(value)
                            if not candidate.is_absolute():
                                candidate = (spec_path.parent / candidate).resolve()
                            else:
                                candidate = candidate.resolve()
                            if candidate == resolved_path:
                                return True
                        except (ValueError, OSError):
                            pass
                    # Check if string contains any token (conservative: only if token appears as whole word/path segment)
                    for token in aliases:
                        if token and (value_lower == token or f"/{token}" in value_lower or value_lower.endswith(f"/{token}")):
                            return True
                    return False
                elif isinstance(value, dict):
                    # Recursively check all values in dict
                    return any(_scan_value(v) for v in value.values())
                elif isinstance(value, (list, tuple)):
                    # Recursively check all items in list/tuple
                    return any(_scan_value(item) for item in value)
                else:
                    return False
            
            return _scan_value(spec)
        
        def _calculations_using_structure(
            project_root: Path, config: dict, entry: dict
        ) -> list[dict]:
            """Find all calculations that reference a given structure."""
            aliases, resolved_path = _structure_reference_tokens(entry, project_root)
            matches: list[dict] = []
            for calculation_entry in list(config.get("calculations", [])):
                calculation_path = calculation_entry.get("path") or (calculation_entry.get("meta") or {}).get("path")
                if not calculation_path:
                    continue
                calculation_dir = (project_root / calculation_path).resolve()
                steps_dir = calculation_dir / "steps"
                if not steps_dir.exists():
                    continue
                for spec_path in steps_dir.rglob("*.step.yaml"):
                    try:
                        # Load as plain dict (no StructureStepSpec dependency)
                        spec_dict = yaml.safe_load(spec_path.read_text())
                        if spec_dict is None:
                            continue
                    except Exception:
                        continue
                    if _spec_uses_structure(spec_dict, spec_path, aliases, resolved_path):
                        matches.append(calculation_entry)
                        break
            return matches
        
        referencing = _calculations_using_structure(project_root, config, entry)
        if referencing:
            if cascade:
                for wf_entry in list(referencing):
                    calc_id = _get_calc_id_from_entry(wf_entry)
                    # Delete calculation (moves to trash internally)
                    svc.calculation.delete(calc_id)
                    # Also move directory to trash explicitly
                    calc_resolved = svc.calculation.require_ref(calc_id)
                    if calc_resolved.absolute_path.name == "calculation.yaml":
                        calc_dir = calc_resolved.absolute_path.parent
                    else:
                        calc_dir = calc_resolved.absolute_path
                    if calc_dir.exists():
                        move_to_trash(calc_dir, trash_dir)
                    # Remove from config
                    calculations = config.setdefault("calculations", [])
                    calculations[:] = [
                        e for e in calculations
                        if _get_calc_id_from_entry(e) != calc_id
                    ]
            elif not force:
                names = ", ".join(entry_display_name(wf) for wf in referencing)
                raise typer.BadParameter(
                    f"Structure '{entry_display_name(entry)}' is used by calculations: {names}. "
                    "Use --force to remove anyway or --cascade to delete the calculations first."
                )

        # Resolve structure to get path before moving file to trash
        resolved = svc.structure.require_ref(identifier)
        
        # Move file to trash
        file_rel = entry.get("file") or (entry.get("meta") or {}).get("path") or (resolved.meta.path if resolved.meta else None)
        if file_rel:
            file_path = (project_root / file_rel).resolve()
            if file_path.exists():
                move_to_trash(file_path, trash_dir)

        # Remove from config by structure_id (ID-only model)
        structures = config.setdefault("structures", [])
        structures[:] = [
            e for e in structures
            if (e.get("structure_id") or e.get("id") or (e.get("meta") or {}).get("id")) != structure_id
        ]
        svc.project.update_config(config)
        typer.secho(f"Structure '{entry_display_name(entry)}' moved to trash.", fg=typer.colors.GREEN)
    except (ConfigError, NotFoundError) as e:
        # Registry sync or not found errors - provide user-friendly message
        if isinstance(e, ConfigError) and e.code == "REGISTRY_OUT_OF_SYNC":
            typer.secho(
                f"\n❌ Registry Out of Sync",
                fg=typer.colors.RED,
                bold=True,
            )
            typer.echo(f"\n{e.message}")
            if e.context.get("expected_path"):
                typer.echo(f"\nExpected path: {e.context['expected_path']}")
            typer.echo(
                "\n💡 To fix this, refresh the project registry:\n"
                "   - In the GUI: Click the 'Refresh' button in the Structures panel\n"
                "   - Or reopen the project in the GUI (registry rebuilds on project load)"
            )
            raise typer.Exit(1)
        raise typer.BadParameter(str(e)) from e
    except Exception as e:
        if os.environ.get("QV_DEBUG_CLI") == "1":
            import sys
            print(f"DEBUG: delete_structure error: {type(e).__name__}: {e}", file=sys.stderr)
            print(f"DEBUG: identifier={identifier}, project_root={project_root}", file=sys.stderr)
            if hasattr(e, 'cause'):
                print(f"DEBUG: cause={e.cause}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
        raise


@delete_app.command("calculation")
def delete_calculation_command(
    identifier: Optional[str] = typer.Argument(
        None, help="Calculation id/name/slug/path (auto-detects from pwd if omitted)"
    ),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    force: bool = typer.Option(
        False, "--force", help="Delete even if other calculations depend on this calculation."
    ),
    cascade: bool = typer.Option(
        False,
        "--cascade",
        help="Delete dependent calculations that reference this calculation as a parent.",
    ),
) -> None:
    """
    Remove a calculation entry and move its directory to trash.
    
    If no identifier is given, auto-detects the enclosing calculation from pwd.
    """
    from quantumvitas.api import QVService
    from quantumvitas.api.errors import NotFoundError
    
    # Resolve project root
    if project:
        project_root = Path(project).expanduser().resolve()
    else:
        project_root = _resolve_project_root()
    
    svc = get_service(project_root)
    config = svc.project.get_config()
    
    # Resolve calculation
    if identifier:
        calc_dto = svc.calculation.get(identifier)
        calc_id = calc_dto.calc_id
    else:
        # Auto-detect from pwd
        calc_ref = svc.calculation.resolve_enclosing_path()
        if calc_ref:
            calc_id = calc_ref.calc_id
        else:
            raise typer.BadParameter(
                "No calculation specified and not inside a calculation directory. "
                "Specify calculation id/name/slug/path or cd into a calculation folder."
            )
    
    # Find entry for display name
    entry = _find_entry_by_calc_id(config, calc_id)
    
    # Delete calculation (moves to trash internally)
    # Note: calculation.delete() doesn't support force/cascade yet, so we use it as-is
    # TODO: Add force/cascade support to calculation.delete() if needed
    svc.calculation.delete(calc_id)
    
    # Update config to remove entry
    calculations = config.setdefault("calculations", [])
    calculations[:] = [
        e for e in calculations
        if _get_calc_id_from_entry(e) != calc_id
    ]
    svc.project.update_config(config)
    
    entry_name = entry_display_name(entry) if entry else calc_id
    typer.secho(f"Calculation '{entry_name}' moved to trash.", fg=typer.colors.GREEN)


@delete_app.command("step")
def delete_step_command(
    step_id: str = typer.Argument(..., help="Step id to remove"),
    calculation: Optional[str] = typer.Option(
        None, "--calculation", help="Calculation id/name/slug/path (auto-detects from pwd if omitted)"
    ),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
) -> None:
    """
    Remove a calculation step and move its step spec file to trash.
    
    The calculation is auto-detected from pwd if not specified with --calculation.
    Step can be identified by ULID (step_id), step filename, or legacy slug.
    """
    from quantumvitas.api import QVService
    
    # Determine project root
    if project:
        project_root = Path(project).expanduser().resolve()
    else:
        try:
            project_root = _resolve_project_root()
        except Exception as exc:
            raise typer.BadParameter(str(exc)) from exc
    
    svc = get_service(project_root)
    config = svc.project.get_config()
    
    # Determine calculation
    calculation_selector: Optional[str] = calculation
    if not calculation_selector:
        # Auto-detect from pwd
        try:
            calc_ref = svc.calculation.resolve_enclosing_path()
            if calc_ref:
                wf_entry = _find_entry_by_calc_id(config, calc_ref.calc_id)
            else:
                wf_entry = None
            if wf_entry:
                # Use centralized selector extraction - single selector, single resolution pattern
                calculation_selector = extract_calculation_selector_from_entry(wf_entry)
                if not calculation_selector:
                    raise typer.BadParameter(
                        "Calculation entry found but no valid identifier. "
                        "This may indicate a corrupted project.qv.yml."
                    )
        except Exception:
            pass
    
    if not calculation_selector:
        raise typer.BadParameter(
            "No calculation specified and not inside a calculation directory. "
            "Specify --calculation <calculation> or run from inside a calculation directory."
        )
    
    # Use require_step to find the step (handles ULID, filename, legacy slug)
    try:
        step_resolved = svc.calculation.require_step_ref(calculation_selector, step_id, config=config)
    except NotFoundError as e:
        raise typer.BadParameter(str(e)) from e
    
    # Get calculation entry for display
    calc_dto = svc.calculation.get(calculation_selector)
    calculation_entry = _find_entry_by_calc_id(config, calc_dto.calc_id)
    # Get calculation directory from calc_id
    calc_id = _get_calc_id_from_entry(calculation_entry)
    calc_resolved = svc.calculation.require_ref(calc_id)
    if calc_resolved.absolute_path.name == "calculation.yaml":
        calculation_dir = calc_resolved.absolute_path.parent
    else:
        calculation_dir = calc_resolved.absolute_path
    calculation_yaml = calculation_dir / "calculation.yaml"
    
    if not calculation_yaml.exists():
        raise typer.BadParameter(f"calculation.yaml not found at {calculation_yaml}")

    data = yaml.safe_load(calculation_yaml.read_text()) or {}
    steps: list[dict] = data.get("steps") or []
    
    # Find step by step_id (ULID) - this is the canonical reference
    step_id_to_find = step_resolved.meta.id
    target_step = None
    for step in steps:
        # Use centralized selector extraction to get step_id
        step_id = extract_step_selector_from_entry(step)
        if step_id == step_id_to_find:
            target_step = step
            break
    
    if not target_step:
        from quantumvitas.api import QVService
        wf_name = entry_display_name(calculation_entry)
        raise typer.BadParameter(f"Step '{step_id}' not found in calculation '{wf_name}'.")

    trash_dir = (project_root / "trash").resolve()
    # In ID-only model, step_resolved.absolute_path is the canonical step file location
    # (step entries in calculation.yaml only have step_id, not step_file)
    spec_path = step_resolved.absolute_path
    if spec_path.exists():
        move_to_trash(spec_path, trash_dir)

    steps.remove(target_step)
    # Remove legacy structure_name and structure fields before writing (DAG + ID-only constitution)
    data.pop("structure_name", None)
    data.pop("structure", None)
    if "calculation" in data:
        data["calculation"].pop("structure_name", None)
        data["calculation"].pop("structure", None)
    calculation_yaml.write_text(yaml.safe_dump(data, sort_keys=False))
    typer.secho(
        f"Step '{step_id}' removed from calculation '{entry_display_name(calculation_entry)}'.",
        fg=typer.colors.GREEN,
    )


@delete_app.command("project")
def delete_project_command(
    identifier: Optional[str] = typer.Argument(
        None, help="Project name/slug/path (auto-detects from pwd if omitted)"
    ),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root to delete (alias for positional arg)"
    ),
) -> None:
    """
    Move an entire project directory into the parent trash folder.
    
    Can specify project by name, slug, or path. If omitted, uses current directory.
    """
    from quantumvitas.api import QVService
    
    # Resolve project path from identifier or --project option
    if identifier:
        # Could be a path or name/slug
        candidate = Path(identifier).expanduser()
        if candidate.exists() and (candidate / "project.qv.yml").exists():
            project_root = candidate.resolve()
        elif project:
            # Search in explicit project path
            project_root = Path(project).expanduser().resolve()
        else:
            # Identifier might be a name/slug - search in current parent
            project_root = Path(identifier).expanduser().resolve()
            if not (project_root / "project.qv.yml").exists():
                raise typer.BadParameter(
                    f"Project '{identifier}' not found. Provide a valid path or run inside a project."
                )
    elif project:
        project_root = Path(project).expanduser().resolve()
    else:
        try:
            project_root = _resolve_project_root()
        except ConfigError as exc:
            # Registry out of sync - provide clear user-facing message
            typer.secho(
                f"\n❌ Registry Out of Sync",
                fg=typer.colors.RED,
                bold=True,
            )
            typer.echo(f"\n{exc}")
            if exc.expected_path:
                typer.echo(f"\nExpected path: {exc.expected_path}")
            typer.echo(
                "\n💡 To fix this, refresh the project registry:\n"
                "   - In the GUI: Click the 'Refresh' button in the Calculations or Structures panel\n"
                "   - Or reopen the project in the GUI (registry rebuilds on project load)"
            )
            raise typer.Exit(1)
        except NotFoundError as exc:
            raise typer.BadParameter(str(exc)) from exc
    
    if not (project_root / "project.qv.yml").exists():
        raise typer.BadParameter(f"No project.qv.yml found in {project_root}")
    
    original_cwd = Path.cwd().resolve()
    inside_project = original_cwd == project_root or project_root in original_cwd.parents

    # Note: We don't actually change the working directory since that can cause issues
    # The shell's cwd is managed by the shell, not Python

    trash_dir = (project_root.parent / "trash").resolve()
    destination = move_to_trash(project_root, trash_dir)
    typer.secho(f"Project moved to {destination}", fg=typer.colors.GREEN)
    if inside_project:
        typer.secho(
            f"Note: Current directory is now inside trash. Use 'cd ..' to navigate out.",
            fg=typer.colors.YELLOW
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
    step_identifier: str = typer.Argument(
        ..., help="Step id, name, or path to .step.yaml"
    ),
    calculation: Optional[str] = typer.Option(
        None, "--calculation", help="Calculation id/name/slug/path (auto-detects from pwd)"
    ),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (auto-detects from pwd)"
    ),
    name: Optional[str] = typer.Option(
        None, "--name", help="Rename the step to a new name/id"
    ),
    remove: bool = typer.Option(
        False, "--remove", help="Remove the specified parameters instead of setting them"
    ),
) -> None:
    """
    Modify step settings: rename or change parameters.
    
    Step can be specified by id, name, or path. If using id/name, the calculation
    is auto-detected from pwd if not specified with --calculation.
    
    Examples:
        qv configure step scf --name "new_scf"
        qv configure step scf --SYSTEM.ecutwfc=70
    """
    bundle = _parse_override_args(ctx.args)
    if not bundle.has_any() and not name:
        raise typer.BadParameter("Provide --name or at least one parameter override.")

    # Check if it's a direct path first
    step_file = Path(step_identifier)
    calculation_yaml = None
    calculation_dir = None
    project_root_resolved = project
    
    if step_file.exists() and step_file.suffix in (".yaml", ".yml"):
        # For direct paths, try to auto-detect project_root
        if not project_root_resolved:
            try:
                project_root_resolved = _resolve_project_root(start=step_file.parent)
            except Exception:
                pass  # No project found, that's OK for standalone step files
    else:
        # Resolve using QVService
        try:
            from quantumvitas.api import QVService
            if not project:
                project = find_project_root(step_file.parent if step_file.exists() else None)
            if not project:
                raise typer.BadParameter("Could not determine project root for step resolution")
            svc_resolve = get_service(project)
            ctx_res = svc_resolve.resolve_resource(
                resource_type="step",
                identifier=step_identifier,
                parent_identifier=calculation,
                cwd=step_file.parent if step_file.exists() else None,
            )
            step_file = ctx_res.resource_path
            # Also get calculation directory for step renaming
            if ctx_res.parent_entry:
                project_root_resolved = ctx_res.project_root
                svc_temp = get_service(project_root_resolved)
                # Get calculation directory from calc_id
                calc_id = _get_calc_id_from_entry(ctx_res.parent_entry)
                calc_resolved = svc_temp.calculation.require_ref(calc_id)
                if calc_resolved.absolute_path.name == "calculation.yaml":
                    calculation_dir = calc_resolved.absolute_path.parent
                else:
                    calculation_dir = calc_resolved.absolute_path
                calculation_yaml = calculation_dir / "calculation.yaml"
        except ConfigError as exc:
            # Registry out of sync - provide clear user-facing message
            typer.secho(
                f"\n❌ Registry Out of Sync",
                fg=typer.colors.RED,
                bold=True,
            )
            typer.echo(f"\n{exc}")
            if exc.expected_path:
                typer.echo(f"\nExpected path: {exc.expected_path}")
            typer.echo(
                "\n💡 To fix this, refresh the project registry:\n"
                "   - In the GUI: Click the 'Refresh' button in the Calculations or Structures panel\n"
                "   - Or reopen the project in the GUI (registry rebuilds on project load)"
            )
            raise typer.Exit(1)
        except NotFoundError as exc:
            raise typer.BadParameter(str(exc)) from exc

    # Load step spec with resolver to normalize legacy structure selectors
    resolve_structure_selector = None
    if project_root_resolved:
        try:
            from quantumvitas.api import QVService
            svc = get_service(project_root_resolved)
            resolve_structure_selector = svc.make_structure_selector_resolver_ref()
        except Exception:
            pass
    
    try:
        # Load step spec as dict (no StructureStepSpec dependency)
        spec_dict = yaml.safe_load(step_file.read_text())
        if not spec_dict:
            raise typer.BadParameter(f"Step file '{step_file}' is empty or invalid.")
        spec = spec_dict
        # Note: resolve_structure_selector is not used with dict-based approach
        # Structure selectors are resolved via API when needed
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"Step file not found: {step_file}") from exc

    modified = False
    
    # Handle name change (rename step)
    if name:
        meta = spec.get("meta", {})
        old_name = meta.get("name")
        from quantumvitas.api.utils import slugify
        new_slug = slugify(name)
        spec["meta"] = {
            "id": meta.get("id"),
            "name": name,
            "slug": new_slug,
            "path": meta.get("path"),
            "kind": "step",
        }
        
        # Update calculation.yaml if we have it
        if calculation_yaml and calculation_yaml.exists():
            wf_data = yaml.safe_load(calculation_yaml.read_text()) or {}
            for step_entry in wf_data.get("steps", []):
                if step_entry.get("id") == step_identifier or step_entry.get("id") == old_name:
                    step_entry["id"] = new_slug
                    break
            # Remove legacy structure_name and structure fields before writing (DAG + ID-only constitution)
            wf_data.pop("structure_name", None)
            wf_data.pop("structure", None)
            if "calculation" in wf_data:
                wf_data["calculation"].pop("structure_name", None)
                wf_data["calculation"].pop("structure", None)
            calculation_yaml.write_text(yaml.safe_dump(wf_data, sort_keys=False))
        
        typer.secho(f"Step renamed from '{old_name}' to '{name}'", fg=typer.colors.GREEN)
        modified = True

    # Handle parameter overrides
    if bundle.has_any():
        parameters = spec.get("parameters") or {}
        updates = _overrides_to_parameter_dict(bundle.parameters)
        _merge_parameter_updates(parameters, updates, remove=remove)
        spec["parameters"] = {k: v for k, v in parameters.items() if v}

        spec["cards"] = _merge_card_updates(spec.get("cards") or {}, bundle.card_overrides, remove=remove)
        spec["species_overrides"] = _merge_species_updates(
            spec.get("species_overrides") or {}, bundle.species_overrides, remove=remove
        )
        
        action = "Removed" if remove else "Updated"
        typer.secho(f"{action} parameters in {step_file}", fg=typer.colors.GREEN)
        modified = True

    if modified:
        # Warnings are computed and printed by _write_step_spec
        _write_step_spec(step_file, spec)


@configure_app.command("project")
def configure_project_placeholder() -> None:
    typer.secho(
        "Project-level configure commands are not implemented yet.",
        fg=typer.colors.YELLOW,
    )


@configure_app.command("calculation")
def configure_calculation_command(
    calculation_identifier: Optional[str] = typer.Argument(
        None, help="Calculation id/name/slug/path (auto-detects from pwd if omitted)"
    ),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (auto-detects from pwd)"
    ),
    name: Optional[str] = typer.Option(
        None, "--name", help="Rename the calculation to a new name"
    ),
    structure: Optional[str] = typer.Option(
        None, "--structure", help="Change the structure used by this calculation (updates all steps)"
    ),
    reorder: Optional[str] = typer.Option(
        None, "--reorder", help="Reorder steps as comma-separated list of step ids (e.g., scf,nscf,dos)"
    ),
) -> None:
    """
    Modify calculation settings: rename, change structure, or reorder steps.
    
    Calculation can be specified by id/name/slug/path, or auto-detected from current directory.
    
    Examples:
        qv configure calculation --name "New Name"
        qv configure calculation --structure si
        qv configure calculation --reorder scf,nscf,dos
    """
    from quantumvitas.api import QVService
    
    # Find project root
    if project:
        project_root = Path(project).expanduser().resolve()
    else:
        try:
            project_root = _resolve_project_root()
        except Exception as exc:
            # Fallback: if we're inside a calculation directory, try to find project root
            # This handles cases where CliRunner doesn't respect os.chdir()
            # Strategy: look for calculation.yaml, then walk up to find project.qv.yml
            cwd = Path.cwd().resolve()
            check_path = cwd
            found_project_root = None
            
            # First, try walking up from current directory looking for project.qv.yml
            while check_path != check_path.parent:
                if (check_path / "project.qv.yml").exists():
                    found_project_root = check_path
                    break
                check_path = check_path.parent
            
            # If that didn't work, try finding calculation.yaml and walking up from there
            if not found_project_root:
                check_path = cwd
                while check_path != check_path.parent:
                    calc_yaml = check_path / "calculation.yaml"
                    if calc_yaml.exists():
                        # Found calculation.yaml, now walk up from its parent to find project.qv.yml
                        parent_path = check_path.parent
                        while parent_path != parent_path.parent:
                            if (parent_path / "project.qv.yml").exists():
                                found_project_root = parent_path
                                break
                            parent_path = parent_path.parent
                        break
                    check_path = check_path.parent
            
            if found_project_root:
                project_root = found_project_root
            else:
                raise typer.BadParameter(str(exc)) from exc
    
    svc = get_service(project_root)
    config = svc.project.get_config()
    
    # Resolve calculation
    if calculation_identifier:
        calc_dto = svc.calculation.get(calculation_identifier)
        calculation_entry = _find_entry_by_calc_id(config, calc_dto.calc_id)
    else:
        calc_ref = svc.calculation.resolve_enclosing_path()
        if calc_ref:
            calculation_entry = _find_entry_by_calc_id(config, calc_ref.calc_id)
        else:
            # Fallback: if resolve_enclosing_path fails (e.g., CliRunner doesn't respect os.chdir()),
            # try to find calculation.yaml in current directory and parent directories
            cwd = Path.cwd().resolve()
            check_path = cwd
            found_calc_id = None
            while check_path != project_root.parent and check_path != project_root:
                calc_yaml = check_path / "calculation.yaml"
                if calc_yaml.exists():
                    try:
                        import yaml
                        calc_data = yaml.safe_load(calc_yaml.read_text()) or {}
                        found_calc_id = calc_data.get("meta", {}).get("id")
                        if found_calc_id:
                            calculation_entry = _find_entry_by_calc_id(config, found_calc_id)
                            if calculation_entry:
                                break
                    except Exception:
                        pass
                check_path = check_path.parent
            
            if not calculation_entry:
                raise typer.BadParameter(
                    "No calculation specified and not inside a calculation directory. "
                    "Specify calculation id/name/slug/path or cd into a calculation folder."
                )
    
    # Get calculation directory from calc_id
    calc_id = _get_calc_id_from_entry(calculation_entry)
    calc_resolved = svc.calculation.require_ref(calc_id)
    if calc_resolved.absolute_path.name == "calculation.yaml":
        calculation_dir = calc_resolved.absolute_path.parent
    else:
        calculation_dir = calc_resolved.absolute_path
    calculation_yaml = calculation_dir / "calculation.yaml"
    
    if not calculation_yaml.exists():
        raise typer.BadParameter(f"calculation.yaml not found at {calculation_yaml}")
    
    calculation_data = yaml.safe_load(calculation_yaml.read_text()) or {}
    modified = False
    
    # Handle name change (rename)
    if name:
        # Store old path to detect if directory was moved
        old_calculation_dir = calculation_dir
        old_calculation_yaml = calculation_yaml
        
        svc.project.apply_calculation_rename(
            entry=calculation_entry,
            new_name=name,
            new_slug=None,
            new_path=None,
            config=config,
        )
        svc.project.update_config(config)
        
        # Re-resolve calculation directory in case it was moved
        # After rename, the entry might have updated path, so resolve via registry if needed
        try:
            # Get calculation directory from calc_id
            calc_id = _get_calc_id_from_entry(calculation_entry)
            calc_resolved = svc.calculation.require_ref(calc_id)
            if calc_resolved.absolute_path.name == "calculation.yaml":
                calculation_dir = calc_resolved.absolute_path.parent
            else:
                calculation_dir = calc_resolved.absolute_path
        except ConfigError:
            # Entry might not have path yet - try to resolve via registry
            calculation_id = extract_calculation_selector_from_entry(calculation_entry)
            if calculation_id:
                resolved = svc.calculation.require_ref(calculation_id)
                calculation_dir = resolved.absolute_path.parent if resolved.absolute_path.name == "calculation.yaml" else resolved.absolute_path
            else:
                raise typer.BadParameter(f"Could not resolve calculation directory after rename")
        
        calculation_yaml = calculation_dir / "calculation.yaml"
        
        # Re-read calculation.yaml if directory was moved
        # Note: apply_calculation_rename should have moved the directory, so calculation.yaml should exist
        # But if it doesn't, try to reload from the new location
        if calculation_dir != old_calculation_dir:
            # Directory was moved - calculation.yaml should be at the new location
            if not calculation_yaml.exists():
                # Try to find it in the new directory
                if calculation_dir.exists():
                    # Directory exists but calculation.yaml doesn't - this shouldn't happen
                    # but let's try to reload it anyway
                    raise typer.BadParameter(
                        f"calculation.yaml not found at {calculation_yaml} after rename. "
                        f"Directory was moved from {old_calculation_dir} to {calculation_dir}, "
                        f"but calculation.yaml is missing."
                    )
                else:
                    raise typer.BadParameter(
                        f"Calculation directory not found at {calculation_dir} after rename. "
                        f"Expected to be moved from {old_calculation_dir}."
                    )
            calculation_data = yaml.safe_load(calculation_yaml.read_text()) or {}
        
        # Update meta in calculation.yaml
        if "meta" in calculation_data:
            calculation_data["meta"]["name"] = name
            # Use the slug from the entry (which was updated by apply_calculation_rename)
            from quantumvitas.api.utils import slugify
            new_slug = (calculation_entry.get("meta") or {}).get("slug") or slugify(name)
            calculation_data["meta"]["slug"] = new_slug
        
        modified = True
        typer.secho(f"Calculation renamed to '{name}'", fg=typer.colors.GREEN)
    
    # Handle structure change
    if structure:
        # Validate structure exists
        struct_dto = svc.structure.get(structure)
        _find_entry_by_structure_id(config, struct_dto.meta.id if struct_dto.meta else "")
        
        # Update calculation.yaml
        calculation_section = calculation_data.setdefault("calculation", {})
        old_structure = calculation_section.get("structure")
        calculation_section["structure"] = structure
        modified = True
        
        # Update all step yaml files
        steps_updated = 0
        index = svc.project.build_resource_index()
        
        for step_entry in calculation_data.get("steps", []):
            # With ID-only model, resolve step file via step_id
            step_id = extract_step_selector_from_entry(step_entry)
            if not step_id:
                continue
            
            try:
                # Resolve step file path via step_id
                # Use centralized selector extraction for calculation selector
                calculation_selector = extract_calculation_selector_from_entry(calculation_entry)
                if not calculation_selector:
                    continue  # Skip if no valid selector
                step_resolved = svc.calculation.require_step_ref(calculation_selector, step_id, config=config)
                step_path = step_resolved.absolute_path
                
                if not step_path.exists():
                    continue
                
                # Load step spec as dict (no StructureStepSpec dependency)
                spec_dict = yaml.safe_load(step_path.read_text())
                if not spec_dict:
                    continue
                spec = spec_dict
                # Note: Structure selectors are resolved via API when needed
                
                # Update structure_id (canonical reference) - structure selector is not written
                resolved = svc.structure.require_ref(structure, config=config)
                spec["structure_id"] = resolved.meta.id
                # Clear legacy structure field (not written to YAML)
                spec["structure"] = ""
                step_path.write_text(yaml.safe_dump(spec, sort_keys=False))
                steps_updated += 1
            except Exception as e:
                typer.secho(f"  Warning: Could not update step {step_id}: {e}", fg=typer.colors.YELLOW)
        
        typer.secho(
            f"Structure changed from '{old_structure}' to '{structure}' ({steps_updated} steps updated)",
            fg=typer.colors.GREEN
        )
    
    # Handle reorder
    if reorder:
        step_selectors = [s.strip() for s in reorder.split(",") if s.strip()]
        if not step_selectors:
            raise typer.BadParameter("--reorder requires a comma-separated list of step identifiers (slug, name, type, or ULID)")
        
        current_steps = calculation_data.get("steps", [])
        
        # Build index for step resolution
        from quantumvitas.api import QVService
        svc = get_service(project_root)
        index = svc.project.build_resource_index()
        
        # Match each selector to a step entry using centralized helper
        reordered_entries = []
        seen_ulids = set()
        
        for selector in step_selectors:
            try:
                step_entry = svc.match_step_selector(
                    calculation_dir=calculation_dir,
                    steps=current_steps,
                    selector=selector,
                    index=index,
                    config=config,
                )
                step_ulid = extract_step_selector_from_entry(step_entry)
                if step_ulid and step_ulid not in seen_ulids:
                    reordered_entries.append(step_entry)
                    seen_ulids.add(step_ulid)
                elif step_ulid in seen_ulids:
                    raise typer.BadParameter(
                        f"Step '{selector}' appears multiple times in reorder list. "
                        f"Each step can only appear once."
                    )
            except (NotFoundError, AmbiguousError) as e:
                raise typer.BadParameter(str(e)) from e
        
        # Check if all current steps are accounted for
        current_ulids = {
            extract_step_selector_from_entry(step) 
            for step in current_steps 
            if extract_step_selector_from_entry(step)
        }
        if seen_ulids != current_ulids:
            missing_ulids = current_ulids - seen_ulids
            missing_identifiers = []
            calculation_slug = (calculation_entry.get("meta") or {}).get("slug") or calculation_entry.get("name") or calculation_dir.name
            for missing_ulid in missing_ulids:
                # Try to get a friendly identifier for the missing step
                try:
                    from quantumvitas.api import QVService
                    svc = get_service(project_root)
                    step_resolved = svc.calculation.require_step_ref(calculation_slug, missing_ulid, config=config, index=index)
                    missing_identifiers.append(step_resolved.meta.slug or step_resolved.meta.name or missing_ulid[:8])
                except Exception:
                    missing_identifiers.append(missing_ulid[:8])
            raise typer.BadParameter(
                f"All steps must be included in reorder. Missing: {', '.join(missing_identifiers)}"
            )
        
        # Reorder
        calculation_data["steps"] = reordered_entries
        modified = True
        
        typer.secho(f"Steps reordered: {' -> '.join(step_selectors)}", fg=typer.colors.GREEN)
    
    if modified:
        # Remove legacy structure_name and structure fields before writing (DAG + ID-only constitution)
        calculation_data.pop("structure_name", None)
        calculation_data.pop("structure", None)
        if "calculation" in calculation_data:
            calculation_data["calculation"].pop("structure_name", None)
            calculation_data["calculation"].pop("structure", None)
        calculation_yaml.write_text(yaml.safe_dump(calculation_data, sort_keys=False))
        typer.secho(f"Calculation updated: {calculation_yaml}", fg=typer.colors.GREEN)
    else:
        typer.secho("No changes specified. Use --structure or --reorder.", fg=typer.colors.YELLOW)


@configure_app.command("species")
def configure_species_command(
    from_input: Optional[Path] = typer.Option(
        None, "--from-input", help="QE input file (.in) to extract ATOMIC_SPECIES from"
    ),
    set_value: Optional[List[str]] = typer.Option(
        None, "--set", help="Explicit species triple: ELEMENT:MASS:PSEUDOPOT (repeatable)"
    ),
    calculation: Optional[str] = typer.Option(
        None, "--calc", "--calculation", help="Calculation id/name/slug/path (auto-detects from pwd if omitted)"
    ),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (auto-detects from pwd)"
    ),
) -> None:
    """
    Configure calculation.yaml species_map from ATOMIC_SPECIES in a QE input file or explicit triples.
    
    Either --from-input or --set (or both) must be provided.
    If both are provided, --from-input is processed first, then --set overrides same elements.
    
    Examples:
        qv configure species --from-input scf.in
        qv configure species --set "Si:28.0855:Si.pbe-n-rrkjus_psl.1.0.0.UPF"
        qv configure species --set "Si:28.0855:Si...UPF" --set "O:15.999:O...UPF" --calc si_bands
        qv configure species --from-input scf.in --set "Si:28.086:Si.new.UPF"  # --set overrides Si from input
    """
    from quantumvitas.api import QVService
    
    # Find project root
    if project:
        project_root = Path(project).expanduser().resolve()
    else:
        try:
            project_root = _resolve_project_root()
        except Exception as exc:
            raise typer.BadParameter(str(exc)) from exc
    
    # Resolve calculation
    if not calculation:
        svc = get_service(project_root)
        config = svc.project.get_config()
        calc_ref = svc.calculation.resolve_enclosing_path()
        if calc_ref:
            calculation_entry = _find_entry_by_calc_id(config, calc_ref.calc_id)
        else:
            calculation_entry = None
        if not calculation_entry:
            raise typer.BadParameter(
                "No calculation specified and not inside a calculation directory. "
                "Specify calculation id/name/slug/path or cd into a calculation folder."
            )
        calculation = extract_calculation_selector_from_entry(calculation_entry)
    
    # Parse --set entries into triples
    set_entries = None
    if set_value:
        set_entries = []
        for triple in set_value:
            # Parse triple: ELEMENT:MASS:PSEUDOPOT
            parts = triple.split(":", 2)  # Split into max 3 parts
            if len(parts) != 3:
                raise typer.BadParameter(
                    f"Invalid --set format: '{triple}'. Expected format: ELEMENT:MASS:PSEUDOPOT\n"
                    f"Example: --set \"Si:28.0855:Si.pbe-n-rrkjus_psl.1.0.0.UPF\""
                )
            
            element = parts[0].strip()
            mass_str = parts[1].strip()
            pseudopot = parts[2].strip()
            
            if not element:
                raise typer.BadParameter(f"Element cannot be empty in --set '{triple}'")
            if not pseudopot:
                raise typer.BadParameter(f"Pseudopotential filename cannot be empty in --set '{triple}'")
            
            # Parse mass as float
            try:
                mass = float(mass_str)
            except ValueError as exc:
                raise typer.BadParameter(f"Invalid mass '{mass_str}' in --set '{triple}': {exc}")
            
            set_entries.append((element, mass, pseudopot))
    
    # Call shared API
    try:
        updated_species_map = QVService.configure_species_map(
            project_root=project_root,
            calculation=calculation,
            from_qe_input=from_input,
            set_entries=set_entries,
            merge=True,
        )
    except APIError as exc:
        raise typer.BadParameter(str(exc)) from exc
    
    # Print summary
    elements = sorted(updated_species_map.keys())
    typer.secho(f"Configured species_map for element(s): {', '.join(elements)}", fg=typer.colors.GREEN)
    for element in elements:
        entry = updated_species_map[element]
        mass = entry.get("mass")
        pseudo_filename = entry.get("pseudopot")
        if mass is not None and pseudo_filename:
            typer.secho(f"  {element}: mass={mass}, pseudopot={pseudo_filename}", fg=typer.colors.GREEN)
        elif pseudo_filename:
            typer.secho(f"  {element}: pseudopot={pseudo_filename}", fg=typer.colors.GREEN)
    
    # Get calculation_yaml path for summary
    svc = get_service(project_root)
    config = svc.project.get_config()
    calc_dto = svc.calculation.get(calculation)
    calculation_entry = _find_entry_by_calc_id(config, calc_dto.calc_id)
    # Get calculation directory from calc_id
    calc_id = _get_calc_id_from_entry(calculation_entry)
    calc_resolved = svc.calculation.require_ref(calc_id)
    if calc_resolved.absolute_path.name == "calculation.yaml":
        calculation_dir = calc_resolved.absolute_path.parent
    else:
        calculation_dir = calc_resolved.absolute_path
    calculation_yaml = calculation_dir / "calculation.yaml"
    typer.secho(f"Updated: {calculation_yaml}", fg=typer.colors.GREEN)


@configure_app.command("structure")
def configure_structure_command(
    identifier: str = typer.Argument(..., help="Structure name/slug/path"),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (auto-detects from pwd)"
    ),
    name: Optional[str] = typer.Option(
        None, "--name", help="New name for the structure"
    ),
) -> None:
    """
    Modify structure settings (currently supports renaming).
    
    For more complex structure modifications, use pymatgen directly or re-import.
    """
    from quantumvitas.api import QVService
    
    if project:
        project_root = Path(project).expanduser().resolve()
    else:
        try:
            project_root = _resolve_project_root()
        except Exception as exc:
            raise typer.BadParameter(str(exc)) from exc
    
    svc = get_service(project_root)
    config = svc.project.get_config()
    
    # Find structure entry
    try:
        struct_dto = svc.structure.get(identifier)
        entry = _find_entry_by_structure_id(config, struct_dto.meta.id if struct_dto.meta else "")
    except ConfigError as exc:
        # Registry out of sync - provide clear user-facing message
        typer.secho(
            f"\n❌ Registry Out of Sync",
            fg=typer.colors.RED,
            bold=True,
        )
        typer.echo(f"\n{exc}")
        if exc.expected_path:
            typer.echo(f"\nExpected path: {exc.expected_path}")
        typer.echo(
            "\n💡 To fix this, refresh the project registry:\n"
            "   - In the GUI: Click the 'Refresh' button in the Calculations or Structures panel\n"
            "   - Or reopen the project in the GUI (registry rebuilds on project load)"
        )
        raise typer.Exit(1)
    except NotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc
    
    if not name:
        typer.secho("No changes specified. Use --name to rename the structure.", fg=typer.colors.YELLOW)
        return
    
    # Use rename logic
    meta = entry.get("meta") or {}
    old_name = meta.get("name") or entry.get("name") or identifier
    
    # Update metadata
    from quantumvitas.api.utils import slugify
    new_slug = slugify(name)
    meta["name"] = name
    meta["slug"] = new_slug
    entry["meta"] = meta
    entry["name"] = name
    
    # Rename file if needed
    old_file = entry.get("file") or meta.get("path")
    if old_file:
        old_path = project_root / old_file
        new_filename = f"{new_slug}.json"
        new_path = old_path.parent / new_filename
        
        if old_path.exists() and old_path != new_path:
            if new_path.exists():
                raise typer.BadParameter(f"Cannot rename: {new_path} already exists")
            
            # Update structure metadata inside the JSON file
            try:
                from quantumvitas.api import QVService
                struct = read_structure(old_path)
                # Update the meta stored in the structure
                struct_dict = struct.as_dict()
                if "_meta" in struct_dict:
                    struct_dict["_meta"]["name"] = name
                    struct_dict["_meta"]["slug"] = new_slug
                    struct_dict["_meta"]["path"] = f"structures/{new_filename}"
                old_path.rename(new_path)
                new_path.write_text(json.dumps(struct_dict, indent=2))
            except Exception:
                # Fallback: just rename without updating internal metadata
                old_path.rename(new_path)
            
            from quantumvitas.api.utils import ensure_relative_path
            new_rel = ensure_relative_path(new_path, base=project_root)
            entry["file"] = new_rel
            meta["path"] = new_rel
    
    svc.project.update_config(config)
    typer.secho(f"Structure renamed from '{old_name}' to '{name}'", fg=typer.colors.GREEN)


@app.command("show-command")
def show_command(input_file: Path = typer.Argument(..., help="QE input file to inspect")) -> None:
    """
    Print example CLI commands for creating a step spec and tweaking parameters based on an input file.
    
    Automatically detects the QE module type (pw.x, bands.x, dos.x, etc.) and suggests
    the appropriate step type.
    """
    from quantumvitas.api.qe_io import QEModule

    if not input_file.exists():
        raise typer.BadParameter(f"{input_file} does not exist.")

    qe_input = QEInputParser.parse_file(input_file)
    parameter_dict = _qe_input_to_parameter_dict(qe_input)
    param_args = _parameter_dict_to_cli_args(parameter_dict)
    card_args = _card_cli_args_from_input(qe_input)
    species_args = _species_cli_args_from_input(qe_input)
    cli_args = param_args + card_args + species_args
    
    # Detect the module type to determine step type
    detected_module = qe_input.detect_module()
    
    # Map module to step type
    MODULE_TO_STEP_TYPE = {
        QEModule.BANDS: "bands",      # bands.x post-processing
        QEModule.DOS: "dos",          # dos.x post-processing
        QEModule.PROJWFC: "projwfc",  # projwfc.x
        QEModule.PP: "pp",            # pp.x
        QEModule.Q2R: "q2r",          # q2r.x
        QEModule.MATDYN: "matdyn",    # matdyn.x
        QEModule.DYNMAT: "dynmat",    # dynmat.x
        QEModule.PH: "ph",            # ph.x
    }
    
    step_type: str
    if detected_module in MODULE_TO_STEP_TYPE:
        # Post-processing or phonon module
        step_type = MODULE_TO_STEP_TYPE[detected_module]
    else:
        # pw.x or cp.x - use calculation type
        calculation = (
            parameter_dict.get("CONTROL", {}).get("calculation")
            or parameter_dict.get("CONTROL", {}).get("CALCULATION")
            or "scf"
        )
        # For pw.x bands calculation, use bands_pw to distinguish from bands.x
        if calculation == "bands":
            step_type = "bands_pw"
        else:
            step_type = str(calculation)

    step_file = f"{input_file.stem}.step.yaml"
    base_cmd = [
        "qv",
        "init",
        "step",
        step_type,
        "--no-defaults",  # Preserve original parameters, don't inject QV defaults
    ] + cli_args

    typer.echo("Example 1: create a step spec preserving original parameters (import mode)")
    typer.echo("  # --no-defaults preserves the QE input exactly (no QV default parameters added)")
    typer.echo("  " + shlex.join(base_cmd))
    
    # Different hint based on whether this is a post-processing step
    if detected_module in MODULE_TO_STEP_TYPE:
        typer.echo("  (Post-processing step: no --structure needed)")
    else:
        typer.echo("  (Run inside a calculation directory, or add --structure <name> --calculation <name>)")

    modify_cmd = [
        "qv",
        "configure",
        "step",
        step_file,
    ]
    if cli_args:
        modify_cmd.append(cli_args[0])
    else:
        # Suggest appropriate parameter based on step type
        if detected_module == QEModule.BANDS:
            modify_cmd.append("--BANDS.filband=mybands.dat")
        elif detected_module == QEModule.DOS:
            modify_cmd.append("--DOS.fildos=mydos.dat")
        else:
            modify_cmd.append("--CONTROL.calculation=scf")

    typer.echo("\nExample 2: tweak a parameter inside the generated YAML")
    typer.echo("  " + shlex.join(modify_cmd))


@app.command("get-command")
def get_command(input_file: Path = typer.Argument(..., help="QE input file to inspect")) -> None:
    """
    Alias for show-command.
    """

    show_command(input_file)


@run_app.command("calculation")
def run_calculation_command(
    calculation: Optional[str] = typer.Argument(
        None, help="Calculation name/slug/path (auto-detects from pwd if omitted)"
    ),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    mode: Optional[str] = typer.Option(
        None, "--mode", help="Override calculation mode (normal or strict)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Print per-step summaries and metrics"
    ),
    strict: bool = typer.Option(
        False, "--strict", help="Force strict verification mode for this run"
    ),
) -> None:
    """
    Execute a calculation defined in project.qv.yml.
    
    If no calculation is specified, auto-detects from current directory
    (must be inside a calculation folder).
    """
    from quantumvitas.api import QVService
    
    # Find project root
    if project:
        project_root = Path(project).expanduser().resolve()
    else:
        try:
            project_root = _resolve_project_root()
        except Exception as exc:
            raise typer.BadParameter(str(exc)) from exc
    
    svc = get_service(project_root)
    config = svc.project.get_config()
    
    # Resolve calculation via registry (for consistent resolution)
    registry = svc.project.build_resource_index()
    
    # Resolve calculation selector (for use with QVService.run_calculation static method)
    if calculation:
        # Accept either calculation id or direct path
        calculation_path = Path(calculation)
        if calculation_path.exists():
            # For direct path, get ID from calculation.yaml
            import yaml
            if calculation_path.name == "calculation.yaml":
                calc_dir = calculation_path.parent
                calc_yaml = calculation_path
            else:
                calc_dir = calculation_path
                calc_yaml = calc_dir / "calculation.yaml"
            
            if calc_yaml.exists():
                data = yaml.safe_load(calc_yaml.read_text()) or {}
                calc_selector = data.get("id") or (data.get("meta") or {}).get("id") or calc_dir.name
            else:
                raise typer.BadParameter(f"calculation.yaml not found in {calculation_path}")
        else:
            # Use the provided selector directly
            calc_selector = calculation
            # Resolve to get calc_dir for mode setting
            calculation_resolved = svc.calculation.require_ref(calc_selector)
            # absolute_path points to the calculation directory
            calc_dir = calculation_resolved.absolute_path
            if calc_dir.name == "calculation.yaml":
                calc_dir = calc_dir.parent
    else:
        # Auto-detect enclosing calculation from pwd
        calc_dto = svc.calculation.resolve_enclosing_path()
        if calc_dto:
            wf_entry = _find_entry_by_calc_id(config, calc_dto.calc_id)
        else:
            wf_entry = None
        if not wf_entry:
            raise typer.BadParameter(
                "No calculation specified and not inside a calculation directory. "
                "Specify calculation name/slug/path or cd into a calculation folder."
            )
        # Use centralized selector extraction - single selector, single resolution pattern
        calc_selector = extract_calculation_selector_from_entry(wf_entry)
        if not calc_selector:
            raise typer.BadParameter(
                "Calculation entry found but no valid identifier. "
                "This may indicate a corrupted project.qv.yml."
            )
        calculation_resolved = svc.calculation.require_ref(calc_selector, config=config, index=registry)
        # absolute_path points to the calculation directory
        calc_dir = calculation_resolved.absolute_path
        if calc_dir.name == "calculation.yaml":
            calc_dir = calc_dir.parent

    # Set mode if needed (must be done before calling run_calculation)
    if strict or mode:
        # Model I/O functions re-exported via API utils (avoids direct core.* imports)
        from quantumvitas.api.utils import load_calculation, save_calculation

        # Load the model, update mode, and save
        calc_model = load_calculation(calc_dir, project_root)
        if strict:
            calc_model.mode = "strict"
        elif mode:
            try:
                calc_model.mode = mode.lower()
            except ValueError as exc:
                raise typer.BadParameter("Mode must be 'normal' or 'strict'.") from exc

        save_calculation(calc_model, calc_dir)

    # Use QVService static method which wraps CalculationRunner internally
    result_dict = QVService.run_calculation(
        project_root=project_root,
        calculation_selector=calc_selector,
        strict=strict,
        verbose=verbose,
        config=config,
        index=registry,
    )
    
    # The static method returns a dict with status and steps
    # Work with the dict directly instead of converting back to CalculationResult
    status_str = result_dict.get("status", "SUCCESS")
    steps_list = result_dict.get("steps", [])

    typer.echo(f"Calculation {calc_selector} status: {status_str.upper()}")
    if verbose:
        for step_dict in steps_list:
            line = f"- {step_dict.get('step_id', 'unknown')}: {step_dict.get('status', 'unknown')}"
            if step_dict.get("reference_file"):
                ref_path = Path(step_dict["reference_file"])
                line += f" (ref: {ref_path.name})"
            if step_dict.get("message"):
                line += f" [{step_dict['message']}]"
            typer.echo(line)
            # Print step_type for each step (contract requirement)
            typer.echo(f"step_type: {step_dict.get('step_type', 'unknown')}")
            if step_dict.get("metrics"):
                for key, value in step_dict["metrics"].items():
                    typer.echo(f"  {key}: {value}")
    else:
        # Even when not verbose, print step_type for each step (contract requirement)
        for step_dict in steps_list:
            typer.echo(f"step_type: {step_dict.get('step_type', 'unknown')}")


@app.command("run-calculation")
def legacy_run_calculation_command(
    calculation: str = typer.Argument(..., help="Calculation name/slug/path"),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    mode: Optional[str] = typer.Option(
        None, "--mode", help="Override calculation mode (normal or strict)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Print per-step summaries and metrics"
    ),
    strict: bool = typer.Option(
        False, "--strict", help="Force strict verification mode for this run"
    ),
) -> None:
    """
    Deprecated alias for ``qv run calculation``.
    """

    typer.secho(
        "`qv run-calculation` is deprecated; use `qv run calculation` instead.",
        fg=typer.colors.YELLOW,
    )
    run_calculation_command(
        calculation=calculation,
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
        None, "--mode", help="Calculation mode override (normal/strict)"
    ),
    strict: bool = typer.Option(
        False, "--strict", help="Force strict verification when running calculations"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose calculation output"),
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
        if target_path.is_dir() and (target_path / "calculation.yaml").exists():
            ctx.args = list(original_args)
            ctx.invoke(
                run_calculation_command,
                calculation=str(target_path),
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
        from quantumvitas.api import QVService
        svc = get_service(project_root)
        config = svc.project.get_config()
        try:
            calc_dto = svc.calculation.get(target)
            _find_entry_by_calc_id(config, calc_dto.calc_id)
            ctx.args = list(original_args)
            ctx.invoke(
                run_calculation_command,
                calculation=target,
                project=project,
                mode=mode,
                strict=strict,
                verbose=verbose,
            )
            return
        except typer.BadParameter:
            pass
        try:
            struct_dto = svc.structure.get(target)
            _find_entry_by_structure_id(config, struct_dto.meta.id if struct_dto.meta else "")
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
        "Use 'qv run step|calculation|structure' for explicit control."
    )


@analyze_app.command("output", deprecated=True)
def analyze_output_command(
    kind: str = typer.Argument(..., help="energy, band, dos, or scf"),
    input_file: Optional[Path] = typer.Argument(
        None, help="Output/data file to analyze (optional for 'band' if --calculation or inside calculation)"
    ),
    calculation: Optional[str] = typer.Option(
        None, "--calculation", "-w",
        help="Calculation selector to auto-locate files from its raw/ directory"
    ),
    symmetry_file: Optional[Path] = typer.Option(
        None, "--symmetry", "-s", 
        help="bands.x output file containing high-symmetry points (for band analysis)"
    ),
    fermi: Optional[float] = typer.Option(
        None, "--fermi", "-f", help="Fermi energy in eV (overrides extraction)"
    ),
    scf_file: Optional[Path] = typer.Option(
        None, "--scf", help="SCF/NSCF output file to extract Fermi energy from"
    ),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    plot: bool = typer.Option(False, "--plot", "-p", help="Generate a plot"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output directory for plots and data"
    ),
    plot_format: str = typer.Option("png", "--format", help="Plot format (png, svg, pdf)"),
    energy_range: Optional[str] = typer.Option(
        None, "--energy-range", help="Energy range for plots, e.g., '-5,5'"
    ),
    no_shift: bool = typer.Option(
        False, "--no-shift", help="Don't shift energies to Fermi level"
    ),
) -> None:
    """
    [DEPRECATED] Analyze QE outputs. Use 'qv analyze band/dos/energy' instead.
    
    This command is deprecated. Please use the direct commands:
    - qv analyze band <file> --plot
    - qv analyze dos <file> --plot  
    - qv analyze energy <file> --plot
    - qv analyze scf <file> --plot
    
    The new commands use QVService API layer for better architecture.
    """
    # Show deprecation warning
    typer.secho(
        "Warning: 'qv analyze output' is deprecated. Use 'qv analyze band/dos/energy/scf' instead.",
        fg=typer.colors.YELLOW,
        err=True,
    )
    # Analysis parsers and plotting now via QVService
    from quantumvitas.api import QVService, APIError
    
    # Instantiate QVService for parser wrappers
    project_root = project or _resolve_project_root()
    from quantumvitas.api import get_service
    svc = get_service(project_root=project_root) if project_root else get_service()
    if isinstance(svc, Path):
        svc = get_service(svc)
    
    normalized = kind.lower()
    e_range = None
    if energy_range:
        try:
            parts = energy_range.split(",")
            e_range = (float(parts[0]), float(parts[1]))
        except (ValueError, IndexError):
            raise typer.BadParameter("--energy-range must be like '-5,5'")
    
    # Auto-detection context for band analysis
    calculation_dir: Optional[Path] = None
    project_root: Optional[Path] = None
    
    # Resolve calculation context
    from quantumvitas.api import QVService
    if calculation:
        # Explicit --calculation option
        try:
            from quantumvitas.api import get_service
            project_root = Path(project).resolve() if project else get_service().project_root
            svc = get_service(project_root)
            config = svc.project.get_config()
            calc_dto = svc.calculation.get(calculation)
            wf_entry = _find_entry_by_calc_id(config, calc_dto.calc_id)
            # Get calculation directory from calc_id
            calc_id = _get_calc_id_from_entry(wf_entry)
            calc_resolved = svc.calculation.require_ref(calc_id)
            if calc_resolved.absolute_path.name == "calculation.yaml":
                calculation_dir = calc_resolved.absolute_path.parent
            else:
                calculation_dir = calc_resolved.absolute_path
            typer.echo(f"Using calculation: {calc_dto.meta.name if calc_dto.meta else calculation}")
        except (NotFoundError, FileNotFoundError) as e:
            raise typer.BadParameter(f"Calculation not found: {calculation}")
    elif input_file is None and normalized == "band":
        # Try to auto-detect calculation from pwd
        try:
            ctx = find_path_context_ref()
            project_root = ctx["project_root"]
            if ctx["is_inside_calculation"]:
                # Use resolve_enclosing_path for reliable detection
                from quantumvitas.api import QVService
                svc = get_service(project_root)
                config = svc.project.get_config()
                calc_dto = svc.calculation.resolve_enclosing_path()
                if calc_dto:
                    calculation_dir = ctx["calculation_directory"]
                    calculation_selector = calc_ref.calc_id
                    if calculation_selector:
                        # For display, resolve to get user-friendly name
                        try:
                            from quantumvitas.api import QVService
                            svc = get_service(project_root)
                            resolved = svc.calculation.require_ref(calculation_selector, config=config)
                            calculation_name = resolved.meta.name or resolved.meta.slug or calculation_selector
                        except Exception:
                            calculation_name = calculation_selector
                        typer.echo(f"Detected calculation: {calculation_name}")
        except APIError:
            pass  # Not inside a project/calculation, will search pwd
    
    # For band analysis, auto-locate files if not all provided
    if normalized == "band":
        search_dir: Optional[Path] = None
        
        if calculation_dir:
            search_dir = QVService.find_calculation_raw_dir(calculation_dir)
        elif input_file:
            # Use input file's directory as search dir
            search_dir = Path(input_file).resolve().parent
        else:
            # Search current directory
            search_dir = Path.cwd()
        
        if search_dir and search_dir.exists():
            found_files = QVService.find_band_analysis_files(search_dir)
            
            # Use found files if not explicitly provided
            if input_file is None:
                if found_files.bands_gnu:
                    input_file = found_files.bands_gnu
                    typer.echo(f"Found bands data: {input_file.name}")
                else:
                    raise typer.BadParameter(
                        "No bands.dat.gnu file found. "
                        "Provide input_file argument or use --calculation to specify a calculation."
                    )
            
            if symmetry_file is None and found_files.bands_pp_out:
                symmetry_file = found_files.bands_pp_out
                typer.echo(f"Found symmetry file: {symmetry_file.name}")
            
            if scf_file is None and found_files.pw_output:
                scf_file = found_files.pw_output
                typer.echo(f"Found pw.x output: {scf_file.name}")
    
    # Validate input_file is provided for non-band analysis
    if input_file is None:
        raise typer.BadParameter(
            f"input_file is required for '{kind}' analysis"
        )
    
    # Determine Fermi energy
    fermi_energy = fermi
    if fermi_energy is None and scf_file:
        scf_result = svc.parse_scf_output(scf_file)
        fermi_energy = scf_result.fermi_energy
    
    # Determine output directory: explicit > calculation results > None
    output_dir = Path(output) if output else None
    if output_dir is None and calculation_dir:
        output_dir = QVService.find_calculation_results_dir(calculation_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        typer.echo(f"Output directory: {output_dir}")
    elif output_dir is None:
        # Try to detect calculation from input file location
        input_path = Path(input_file).resolve()
        try:
            proj_root = _resolve_project_root(start=input_path.parent)
            from quantumvitas.api import QVService
            svc_temp = get_service(proj_root)
            config = svc_temp.load_project_config()
            # Check if input is inside a calculation directory
            for wf_entry in config.get("calculations", []):
                wf_path = wf_entry.get("path") or (wf_entry.get("meta") or {}).get("path")
                if wf_path:
                    wf_dir = (proj_root / wf_path).resolve()
                    if input_path.is_relative_to(wf_dir):
                        # Found enclosing calculation - use its results folder
                        output_dir = wf_dir / "results"
                        output_dir.mkdir(parents=True, exist_ok=True)
                        typer.echo(f"Output directory: {output_dir}")
                        break
        except (NotFoundError, FileNotFoundError, ValueError):
            pass  # Not in a project/calculation context, output_dir stays None
    
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
    
    if normalized in ("energy", "scf"):
        # Full SCF analysis
        result = svc.parse_scf_output(input_file)
        data = result.to_dict()
        
        if plot and result.iterations:
            fig, ax = svc.plot_scf_convergence(result)
            if output_dir:
                svc.save_figure(fig, output_dir / f"scf_convergence.{plot_format}")
                typer.echo(f"Plot saved to {output_dir / f'scf_convergence.{plot_format}'}")
            else:
                import matplotlib.pyplot as plt
                plt.show()
        
        typer.echo(json.dumps(data, indent=2, default=str))
        
    elif normalized == "band":
        # Band structure analysis
        # Use scf_file for both Fermi energy AND reciprocal lattice vectors
        # (needed for proper k-point coordinate conversion from Cartesian to crystal)
        band_data = svc.parse_bands_gnu(
            input_file,
            symmetry_file=symmetry_file,
            fermi_energy=fermi_energy,
            pw_output_file=scf_file,  # Provides reciprocal lattice vectors
        )
        data = band_data.to_dict()
        
        if plot:
            fig, ax = svc.plot_bands(
                band_data,
                shift_fermi=not no_shift,
                energy_range=e_range,
            )
            if output_dir:
                plot_path = output_dir / f"bands.{plot_format}"
                svc.save_figure(fig, plot_path)
                typer.echo(f"Plot saved to {plot_path}")
            else:
                import matplotlib.pyplot as plt
                plt.show()
        
        # Print summary (not full data which can be huge)
        summary = {
            "n_bands": band_data.n_bands,
            "n_kpoints": band_data.n_kpoints,
            "fermi_energy_ev": band_data.fermi_energy,
            "high_symmetry_points": [pt.label for pt in band_data.high_symmetry_points],
        }
        typer.echo(json.dumps(summary, indent=2))
        
        if output_dir:
            (output_dir / "bands_data.json").write_text(json.dumps(data, indent=2))
            typer.echo(f"Full data saved to {output_dir / 'bands_data.json'}")
        
    elif normalized == "dos":
        # DOS analysis
        dos_data = svc.parse_dos_data(input_file)
        
        # Override Fermi if provided
        if fermi_energy is not None:
            # DOSData removed - use dict directly
            if isinstance(dos_data, dict):
                dos_data = {**dos_data, "fermi_energy": fermi_energy}
            else:
                # If it's an object, convert to dict first
                dos_data = {
                    "energies": getattr(dos_data, "energies", []),
                    "dos": getattr(dos_data, "dos", []),
                    "idos": getattr(dos_data, "idos", []),
                    "fermi_energy": fermi_energy,
                }
        
        # Convert to dict if needed
        if not isinstance(dos_data, dict):
            data = dos_data.to_dict() if hasattr(dos_data, "to_dict") else dict(dos_data)
        else:
            data = dos_data
        
        if plot:
            fig, ax = svc.plot_dos(
                dos_data,
                shift_fermi=not no_shift,
                energy_range=e_range,
            )
            if output_dir:
                plot_path = output_dir / f"dos.{plot_format}"
                svc.save_figure(fig, plot_path)
                typer.echo(f"Plot saved to {plot_path}")
            else:
                import matplotlib.pyplot as plt
                plt.show()
        
        # Print summary
        summary = {
            "n_points": len(dos_data.energies),
            "energy_range": data["energy_range"],
            "fermi_energy_ev": dos_data.fermi_energy,
        }
        typer.echo(json.dumps(summary, indent=2))
        
        if output_dir:
            (output_dir / "dos_data.json").write_text(json.dumps(data, indent=2))
            typer.echo(f"Full data saved to {output_dir / 'dos_data.json'}")
        
    else:
        raise typer.BadParameter("kind must be one of: energy, scf, band, dos")


# =============================================================================
# Analyze commands - Using QVService API layer
# =============================================================================

@analyze_app.command("band")
def analyze_band_command(
    input_file: Optional[Path] = typer.Argument(
        None, help="Band data file (.dat.gnu) - optional if --calculation specified or inside calculation"
    ),
    calculation: Optional[str] = typer.Option(
        None, "--calculation", "-w",
        help="Calculation selector to auto-locate files from its raw/ directory"
    ),
    symmetry_file: Optional[Path] = typer.Option(
        None, "--symmetry", "-s", 
        help="bands.x output file containing high-symmetry points"
    ),
    fermi: Optional[float] = typer.Option(
        None, "--fermi", "-f", help="Fermi energy in eV (overrides extraction)"
    ),
    scf_file: Optional[Path] = typer.Option(
        None, "--scf", help="SCF/NSCF output file to extract Fermi energy from"
    ),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    plot: bool = typer.Option(False, "--plot", "-p", help="Generate a plot"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output directory for plots and data"
    ),
    plot_format: str = typer.Option("png", "--format", help="Plot format (png, svg, pdf)"),
    energy_range: Optional[str] = typer.Option(
        None, "--energy-range", help="Energy range for plots, e.g., '-5,5'"
    ),
    no_shift: bool = typer.Option(
        False, "--no-shift", help="Don't shift energies to Fermi level"
    ),
) -> None:
    """
    Analyze band structure data and generate plots.
    
    Parses QE bands.dat.gnu file and optionally creates a band structure plot.
    Files can be auto-detected from calculation context.
    
    Examples:
        qv analyze band si.bands.dat.gnu --plot
        qv analyze band --calculation si-bands --plot
        qv analyze band si.bands.dat.gnu --symmetry si.bands.out --scf si.nscf.out --plot
        qv analyze band --plot  # auto-detect files from pwd or enclosing calculation
    """
    from quantumvitas.api import QVService, APIError
    
    # Parse energy range
    e_range = None
    if energy_range:
        try:
            parts = energy_range.split(",")
            e_range = (float(parts[0]), float(parts[1]))
        except (ValueError, IndexError):
            raise typer.BadParameter("--energy-range must be like '-5,5'")
    
    # Determine project root and calculation context
    project_root: Optional[Path] = None
    calculation_selector: Optional[str] = calculation
    
    if project:
        project_root = Path(project).resolve()
    else:
        # Always try to detect project root from pwd
        try:
            ctx = find_path_context_ref()
            project_root = ctx["project_root"]
            # Only auto-detect calculation if no input file provided
            if input_file is None and ctx["is_inside_calculation"]:
                # Use resolve_enclosing_path to get the actual calculation
                # This is more reliable than using the selector from calculation.yaml
                # (which might be stale after a rename)
                from quantumvitas.api import QVService
                svc = get_service(project_root)
                config = svc.project.get_config()
                calc_dto = svc.calculation.resolve_enclosing_path()
                if calc_dto:
                    calculation_selector = calc_ref.calc_id
                    if calculation_selector:
                        # For display, resolve to get user-friendly name
                        try:
                            from quantumvitas.api import QVService
                            svc = get_service(project_root)
                            resolved = svc.calculation.require_ref(calculation_selector, config=config)
                            display_name = resolved.meta.name or resolved.meta.slug or calculation_selector
                            typer.echo(f"Detected calculation: {display_name}")
                        except Exception:
                            typer.echo(f"Detected calculation: {calculation_selector}")
        except APIError:
            pass  # Not inside a project
    
    # If calculation specified but no project found, error
    if calculation and project_root is None:
        raise typer.BadParameter(
            "Cannot resolve --calculation without being in a project. Use --project to specify project root."
        )
    
    # Call QVService (will raise NotFoundError if calculation not found)
    try:
        svc = QVService(project_root)
        result = svc.analysis.analyze_band(
            bands_file=input_file,
            calculation_selector=calculation_selector,
            symmetry_file=symmetry_file,
            scf_file=scf_file,
            fermi_energy=fermi,
            plot=plot,
            output_dir=output,
            plot_format=plot_format,
            energy_range=e_range,
            shift_fermi=not no_shift,
        )
        
        # Print summary
        summary = {
            "n_bands": result["n_bands"],
            "n_kpoints": result["n_kpoints"],
            "fermi_energy_ev": result["fermi_energy_ev"],
            "high_symmetry_points": result["high_symmetry_points"],
        }
        typer.echo(json.dumps(summary, indent=2))
        
        if result["plot_path"]:
            typer.echo(f"Plot saved to {result['plot_path']}")
            
    except APIError as e:
        raise typer.BadParameter(str(e))


@analyze_app.command("dos")
def analyze_dos_command(
    input_file: Path = typer.Argument(..., help="DOS data file (.dat)"),
    fermi: Optional[float] = typer.Option(
        None, "--fermi", "-f", help="Fermi energy in eV (overrides extraction)"
    ),
    scf_file: Optional[Path] = typer.Option(
        None, "--scf", help="SCF/NSCF output file to extract Fermi energy from"
    ),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    plot: bool = typer.Option(False, "--plot", "-p", help="Generate a plot"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output directory for plots and data"
    ),
    plot_format: str = typer.Option("png", "--format", help="Plot format (png, svg, pdf)"),
    energy_range: Optional[str] = typer.Option(
        None, "--energy-range", help="Energy range for plots, e.g., '-5,5'"
    ),
    no_shift: bool = typer.Option(
        False, "--no-shift", help="Don't shift energies to Fermi level"
    ),
) -> None:
    """
    Analyze DOS (density of states) data and generate plots.
    
    Parses QE DOS output file (.dat format) and optionally creates a DOS plot.
    
    Examples:
        qv analyze dos si.dos.dat --plot
        qv analyze dos si.dos.dat --scf si.nscf.out --plot --energy-range -5,5
    """
    from quantumvitas.api import QVService, APIError
    
    # Parse energy range
    e_range = None
    if energy_range:
        try:
            parts = energy_range.split(",")
            e_range = (float(parts[0]), float(parts[1]))
        except (ValueError, IndexError):
            raise typer.BadParameter("--energy-range must be like '-5,5'")
    
    # Determine project root (optional for DOS analysis, but helps with output dir)
    project_root: Optional[Path] = None
    if project:
        project_root = Path(project).resolve()
    else:
        try:
            ctx = find_path_context_ref()
            project_root = ctx["project_root"]
        except APIError:
            pass
    
    # Call QVService
    try:
        svc = QVService(project_root)
        result = svc.analysis.analyze_dos(
            dos_file=input_file,
            fermi_energy=fermi,
            scf_file=scf_file,
            plot=plot,
            output_dir=output,
            plot_format=plot_format,
            energy_range=e_range,
            shift_fermi=not no_shift,
        )
        
        # Print summary
        summary = {
            "n_points": result["n_points"],
            "energy_range_ev": result["energy_range_ev"],
            "fermi_energy_ev": result["fermi_energy_ev"],
        }
        typer.echo(json.dumps(summary, indent=2))
        
        if result["plot_path"]:
            typer.echo(f"Plot saved to {result['plot_path']}")
            
    except APIError as e:
        raise typer.BadParameter(str(e))


@analyze_app.command("energy")
def analyze_energy_command(
    input_file: Path = typer.Argument(..., help="SCF output file (.out)"),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    plot: bool = typer.Option(False, "--plot", "-p", help="Generate convergence plot"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output directory for plots and data"
    ),
    plot_format: str = typer.Option("png", "--format", help="Plot format (png, svg, pdf)"),
) -> None:
    """
    Analyze SCF output file for energies and convergence.
    
    Parses QE pw.x output file for total energy, Fermi energy,
    convergence info, and optionally plots SCF convergence.
    
    Examples:
        qv analyze energy si.scf.out
        qv analyze energy si.scf.out --plot
    """
    from quantumvitas.api import QVService, APIError
    
    # Determine project root (optional for SCF analysis, but helps with output dir)
    project_root: Optional[Path] = None
    if project:
        project_root = Path(project).resolve()
    else:
        try:
            ctx = find_path_context_ref()
            project_root = ctx["project_root"]
        except APIError:
            pass
    
    # Call QVService
    try:
        result = QVService.analyze_scf(
            project_root=project_root,
            scf_file=input_file,
            plot=plot,
            output_dir=output,
            plot_format=plot_format,
        )
        
        # Print full SCF data
        typer.echo(json.dumps(result["data"], indent=2, default=str))
        
        if result["plot_path"]:
            typer.echo(f"Plot saved to {result['plot_path']}")
            
    except APIError as e:
        raise typer.BadParameter(str(e))


@analyze_app.command("scf")
def analyze_scf_command(
    input_file: Path = typer.Argument(..., help="SCF output file (.out)"),
    project: Optional[Path] = typer.Option(
        None, "--project", help="Project root (defaults to auto-detect)"
    ),
    plot: bool = typer.Option(False, "--plot", "-p", help="Generate convergence plot"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output directory for plots and data"
    ),
    plot_format: str = typer.Option("png", "--format", help="Plot format (png, svg, pdf)"),
) -> None:
    """
    Analyze SCF output file for energies and convergence (alias for 'analyze energy').
    
    Examples:
        qv analyze scf si.scf.out
        qv analyze scf si.scf.out --plot
    """
    # Delegate to analyze_energy_command
    analyze_energy_command(
        input_file=input_file,
        project=project,
        plot=plot,
        output=output,
        plot_format=plot_format,
    )


@analyze_app.command("structure")
def analyze_structure_command(
    structure_selector: str = typer.Argument(..., help="Structure selector (name/slug/path)"),
    supercell: Optional[str] = typer.Option(
        None, "--supercell", "-s",
        help="Supercell dimensions as 'a b c', e.g., '2 2 2'"
    ),
    repeat_boundary: bool = typer.Option(
        False, "--repeat-boundary", "-r",
        help="Show periodic images of atoms at cell boundaries"
    ),
    no_repeat_boundary: bool = typer.Option(
        False, "--no-repeat-boundary",
        help="Don't show periodic images at boundaries (default)"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Output file path (default: structure.png in current directory)"
    ),
    project: Optional[Path] = typer.Option(
        None, "--project", "-p",
        help="Project root (defaults to auto-detect)"
    ),
    plot_format: str = typer.Option(
        "png", "--format", "-f",
        help="Output format (png, svg, pdf)"
    ),
    show: bool = typer.Option(
        False, "--show",
        help="Attempt to display plot interactively (may not work headless)"
    ),
) -> None:
    """
    Visualize a crystal structure as a 3D ball-and-stick plot.
    
    Creates a 3D visualization of the crystal structure with:
    - Atoms shown as spheres (colored by element)
    - Bonds shown as lines (based on covalent radii)
    - Unit cell wireframe
    
    Supports supercell expansion and boundary repetition for
    standard crystallographic visualization.
    
    Examples:
        qv analyze structure si
        qv analyze structure si --output si_structure.png
        qv analyze structure si --supercell "2 2 2"
        qv analyze structure si --supercell "2 2 2" --repeat-boundary
        qv analyze structure si --show
    """
    from quantumvitas.api import QVService
    
    # Resolve project root
    try:
        project_root = Path(project).resolve() if project else _resolve_project_root()
    except typer.BadParameter:
        # Not in a project - try to load structure directly as file
        structure_path = Path(structure_selector)
        if structure_path.exists():
            structure = read_structure(structure_path)
            struct_name = structure_path.stem
            project_root = None
        else:
            raise typer.BadParameter(
                f"Not in a project and '{structure_selector}' is not a valid file path. "
                "Use --project to specify a project root, or provide a direct file path."
            )
    else:
        # Inside a project - resolve structure
        struct, struct_name = _resolve_structure_input(project_root, structure_selector)
        structure = struct
    
    # Parse supercell
    if supercell:
        try:
            parts = supercell.strip().split()
            if len(parts) != 3:
                raise ValueError()
            supercell_tuple = (int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            raise typer.BadParameter(
                "--supercell must be three integers like '2 2 2'"
            )
    else:
        supercell_tuple = (1, 1, 1)
    
    # Handle repeat_boundary flags
    boundary = repeat_boundary and not no_repeat_boundary
    
    # Determine output path
    if output:
        output_path = Path(output).resolve()
    else:
        output_path = Path.cwd() / f"{struct_name}_structure.{plot_format}"
    
    # Visualize
    result = QVService.visualize_structure_direct(
        structure=structure,
        output_path=output_path,
        supercell=supercell_tuple,
        repeat_boundary=boundary,
        show=show,
        plot_format=plot_format,
    )
    
    # Print summary
    typer.secho(f"✓ Structure visualization saved to: {result.output_path}", fg=typer.colors.GREEN)
    typer.echo(f"  Atoms: {result.n_atoms}")
    typer.echo(f"  Bonds: {result.n_bonds}")
    if supercell_tuple != (1, 1, 1):
        typer.echo(f"  Supercell: {supercell_tuple[0]}×{supercell_tuple[1]}×{supercell_tuple[2]}")
    if boundary:
        typer.echo("  Boundary repetition: enabled")


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
    # Use the centralized helper instead of direct JSON access
    supported_modules = list_supported_modules()
    if module_key not in supported_modules:
        raise typer.BadParameter(
            f"Unknown module '{module}'. Available: {', '.join(sorted(supported_modules))}"
        )

    sections = get_module_param_sections(module_key)
    doc_url = get_module_doc_url(module_key)

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

    if doc_url:
        typer.echo(f"Documentation: {doc_url}")
    for sec_name, params in filtered.items():
        typer.echo(f"\n{sec_name}:")
        for param in params:
            typer.echo(f"  - {param}")


def main() -> None:
    app()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _suggest_structure_name(structure: "PMGStructure", source_path: Path) -> str:
    formula = None
    try:
        formula = structure.composition.reduced_formula
    except Exception:
        formula = None
    if formula:
        return formula
    return source_path.stem or "Structure"


def _write_step_spec(
    path: Path, spec: dict[str, Any], *, project_root: Optional[Path] = None
) -> None:
    """Write a step spec dict to a YAML file."""
    from quantumvitas.api import QVService
    if project_root:
        from quantumvitas.api.utils import ensure_relative_path
        relative_path = ensure_relative_path(path, base=project_root)
    else:
        relative_path = path.name
    
    # Update meta path in the dict
    if "meta" not in spec:
        spec["meta"] = {}
    spec["meta"]["path"] = relative_path

    # Compute warnings before writing (pure keyword matching, no engine detection)
    warnings: list[str] = []
    
    parameters = spec.get("parameters") or {}
    runtime_keys = detect_runtime_control_keys(parameters)
    if runtime_keys:
        for key in runtime_keys:
            warnings.append(
                f"CONTROL.{key} looks like a runtime-managed key. "
                f"For QE it is protected and will be overridden at run time "
                f"(default outdir=./outdir, pseudo_dir=project/pseudo, prefix is engine-managed). "
                f"If you are not using QE, you can ignore this warning."
            )
    
    # Print warnings to stderr (non-blocking)
    if warnings:
        for warning in warnings:
            typer.secho(f"⚠️  WARNING: {warning}", fg=typer.colors.YELLOW, err=True)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(spec, sort_keys=False))


def _overrides_to_parameter_dict(
    overrides: Sequence[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    parameters: dict[str, dict[str, Any]] = {}
    for override in overrides:
        section = (override.get("section") or "CONTROL").upper()
        section_params = parameters.setdefault(section, {})
        section_params[override.get("name", "")] = override.get("value")
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
    from quantumvitas.api import QVService
    
    system = parameter_dict.get("SYSTEM")
    if not system:
        return
    
    # Check if we need to preserve alat for k-point compatibility
    preserve_alat = needs_alat_preservation(qe_input) if qe_input else False
    alat_bohr = extract_alat_bohr(qe_input) if preserve_alat and qe_input else None
    
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
    # Show env var for debugging (what user set), but use internal registry for resolution
    env_home = _safe_path(os.getenv("QE_HOME"))
    registry_home = _safe_path(QVService.get_qe_home())  # Internal registry (preferred)
    
    installation = getattr(backend, "installation", None) or getattr(
        backend, "_installation", None
    )
    engine_home = _safe_path(getattr(installation, "qe_home", None))

    pw_path = backend.find_executable("pw.x") if hasattr(backend, "find_executable") else None
    if pw_path is None:
        which_path = shutil.which("pw.x")
        pw_path = Path(which_path).resolve() if which_path else None

    which_home = pw_path.parent.parent if pw_path else None
    # Use internal registry as primary source, fall back to others
    resolved_home = registry_home or engine_home or which_home
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
    # Load step spec as dict (no StructureStepSpec dependency)
    spec = yaml.safe_load(spec_path.read_text()) or {}
    
    # Validate structure consistency with parent calculation if present
    parent_calculation_id = spec.get("parent_calculation_id")
    if parent_calculation_id and project_root:
        _validate_step_structure_consistency(spec, spec_path, project_root)
    
    return _execute_step_spec(
        spec=spec,
        spec_path=spec_path,
        bundle=bundle,
        project_root=project_root,
        working_dir=working_dir,
        engine_backend=engine_backend,
    )


def _validate_step_structure_consistency(
    spec: dict[str, Any],
    spec_path: Path,
    project_root: Path,
) -> None:
    """
    Validate that the step's structure matches its parent calculation's structure.
    
    Raises typer.BadParameter if there's a mismatch.
    """
    try:
        from quantumvitas.api import QVService
        svc = get_service(project_root)
        config = svc.project.get_config()
    except Exception:
        return  # Can't validate without project config
    
    # Find parent calculation by looking at the spec path (should be inside calculation dir)
    # or by using the parent_calculation_id
    parent_calculation_id = spec.get("parent_calculation_id")
    if not parent_calculation_id:
        return
    
    # Try to find the calculation entry
    try:
        calc_dto = svc.calculation.get(parent_calculation_id)
        calculation_entry = _find_entry_by_calc_id(config, calc_dto.calc_id)
    except Exception:
        # Parent calculation not found in project, might be standalone
        return
    
    # Get calculation directory from calc_id
    calc_id = _get_calc_id_from_entry(calculation_entry)
    calc_resolved = svc.calculation.require_ref(calc_id)
    if calc_resolved.absolute_path.name == "calculation.yaml":
        calculation_dir = calc_resolved.absolute_path.parent
    else:
        calculation_dir = calc_resolved.absolute_path
    calculation_yaml = calculation_dir / "calculation.yaml"
    
    if not calculation_yaml.exists():
        return
    
    calculation_data = yaml.safe_load(calculation_yaml.read_text()) or {}
    calculation_section = calculation_data.get("calculation", {})
    calculation_structure = calculation_section.get("structure")
    
    if not calculation_structure:
        return
    
    # Compare structures (by slug/name/id)
    step_structure = spec.get("structure") or spec.get("structure_id")
    if step_structure and step_structure != calculation_structure:
        typer.secho(
            f"Warning: Step structure '{step_structure}' differs from parent calculation structure "
            f"'{calculation_structure}'. Using step's structure.",
            fg=typer.colors.YELLOW
        )


def _execute_step_spec(
    spec: dict[str, Any],
    spec_path: Path,
    bundle: ParsedOverrides,
    project_root: Path,
    working_dir: Optional[Path],
    engine_backend,
):
    """Execute a step spec (dict-based, no StructureStepSpec dependency)."""
    spec_copy = copy.deepcopy(spec)
    if bundle.card_overrides:
        spec_copy["cards"] = _merge_card_updates(
            spec_copy.get("cards") or {}, bundle.card_overrides, remove=False
        )
    if bundle.species_overrides:
        spec_copy["species_overrides"] = _merge_species_updates(
            spec_copy.get("species_overrides") or {}, bundle.species_overrides, remove=False
        )

    # Resolve structure: prefer structure_id (canonical), fall back to structure selector (legacy)
    structure_identifier = None
    if spec_copy.get("structure_id"):
        # Use structure_id to resolve structure
        try:
            svc = get_service(project_root)
            resolved = svc.structure.require_ref(spec_copy["structure_id"])
            structure_identifier = resolved.meta.slug or resolved.meta.name
        except NotFoundError:
            # Fall back to structure selector if structure_id resolution fails
            structure_identifier = spec_copy.get("structure")
    else:
        structure_identifier = spec_copy.get("structure")
    
    if not structure_identifier:
        raise typer.BadParameter(
            f"Step spec at {spec_path} has no structure defined. "
            "Please set a structure for the step or its parent calculation."
        )
    
    structure, struct_name = _resolve_structure_input(project_root, structure_identifier)
    qe_input, _ = svc.generate_qe_input_from_spec(
        structure=structure,
        spec=spec_copy,
        extra_overrides=bundle.parameters,
    )

    workdir = working_dir or (Path("temp") / "cli_outputs" / struct_name)
    workdir = workdir.resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    input_name = spec_copy.get("input_name") or f"{struct_name}_{spec_copy.get('step_type', 'scf')}.pw.in"
    generated_input = workdir / input_name
    from quantumvitas.api import QVService
    write_qe_input_file(qe_input, generated_input)

    result, prepared = QVService.run_input_step(
        engine=engine_backend,
        input_file=generated_input,
        working_dir=workdir,
        project_root=project_root,
        step_type=None,
        keep_original=False,  # Step spec serves as the source of truth
    )
    return result, prepared, generated_input


# ---------------------------------------------------------------------------
# Entry point (must be at end of file to ensure all helpers are defined)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()

