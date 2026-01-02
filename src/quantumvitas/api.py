"""
QVService: Clean service layer between CLI and core.

This module provides a stable interface that both CLI and GUI can use.
All functions:
- Receive project_root explicitly (never look at cwd)
- Receive other resources via selector strings
- Internally call resolution.* to turn selectors into resource models
- Operate on dataclasses → save back to YAML
"""

from __future__ import annotations

import dataclasses
import json
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple, TYPE_CHECKING

import numpy as np
import yaml

from quantumvitas.core.resources import (
    ResourceMeta,
    ensure_relative_path,
    generate_resource_id,
    generate_unique_name_and_slug,
    meta_from_name,
    slugify,
)
from quantumvitas.core.resolution import (
    AmbiguousSelectorError,
    ResolvedResource,
    ResourceNotFoundError,
    SelectorNotFoundError,
    resolve_project,
    resolve_structure,
    resolve_calculation,
    resolve_step,
    require_structure,
    require_calculation,
    require_step,
    list_structures,
    list_calculations,
    list_steps,
)
from quantumvitas.core.selectors import (
    extract_calculation_selector_from_entry,
    extract_structure_selector_from_entry,
    extract_step_selector_from_entry,
)
from quantumvitas.core.context import detect_enclosing_project
from quantumvitas.core.project_utils import (
    ProjectConfigError,
    ResourceNotFoundError as ProjectResourceNotFoundError,  # Legacy error from project_utils
    load_project_config,
    save_project_config,
    collect_slugs,
    ensure_structure_entry_defaults,
    ensure_calculation_entry_defaults,
    find_structure_entry,
    find_calculation_entry,
    calculation_directory,
    move_to_trash,
    apply_structure_rename,
    apply_calculation_rename,
    delete_calculation_entry,
    calculations_using_structure,
    calculations_depending_on,
)

if TYPE_CHECKING:
    from quantumvitas.calculation.structure_steps import StructureStepSpec
    from quantumvitas.core.resolution import ResourceIndex


# =============================================================================
# JSON Serialization Helper
# =============================================================================

def to_jsonable(x: Any) -> Any:
    """
    Recursively convert objects to JSON-serializable types.
    
    Converts:
    - np.ndarray → list
    - np.integer → int
    - np.floating → float
    - Path → str
    - dataclasses → dict (then recursively convert)
    - dict/list/tuple → recursively convert values
    
    This is the single source of truth for JSON conversion at API boundaries.
    
    Args:
        x: Any object to convert
        
    Returns:
        JSON-serializable equivalent
    """
    # Handle numpy arrays
    if isinstance(x, np.ndarray):
        return x.tolist()
    
    # Handle numpy scalars
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x)
    
    # Handle Path objects
    if isinstance(x, Path):
        return str(x)
    
    # Handle dataclasses
    if dataclasses.is_dataclass(x) and not isinstance(x, type):
        return to_jsonable(dataclasses.asdict(x))
    
    # Handle dicts
    if isinstance(x, dict):
        return {k: to_jsonable(v) for k, v in x.items()}
    
    # Handle lists and tuples
    if isinstance(x, (list, tuple)):
        return [to_jsonable(v) for v in x]
    
    # Return primitives unchanged
    return x


class QVServiceError(Exception):
    """Base exception for QVService operations."""
    pass


class QVService:
    """
    Service layer for QuantumVITAS operations.
    
    Provides clean methods for managing projects, calculations, steps, and structures.
    All methods receive project_root explicitly and use selectors for resources.
    """
    
    # -------------------------------------------------------------------------
    # Project operations
    # -------------------------------------------------------------------------
    
    @staticmethod
    def init_project(
        target_dir: Path,
        name: Optional[str] = None,
        template: Optional[str] = None,
    ) -> Path:
        """
        Initialize a new QuantumVITAS project.
        
        Args:
            target_dir: Directory to create the project in
            name: Project name (defaults to directory name)
            template: Optional template name (deprecated, not used)
            
        Returns:
            Path to project root
            
        Raises:
            ValueError: If target_dir is inside an existing project
        """
        target_dir = Path(target_dir).resolve()
        
        # Check if target_dir is inside an existing project
        enclosing_project = detect_enclosing_project(target_dir)
        if enclosing_project:
            raise ValueError(
                f"Cannot create a new project inside an existing QuantumVITAS project. "
                f"The selected folder is inside a project at: {enclosing_project}. "
                f"Please choose a parent folder above your current project directory."
            )
        
        target_dir.mkdir(parents=True, exist_ok=True)
        
        project_name = name or target_dir.name
        project_slug = slugify(project_name)
        project_id = generate_resource_id()
        
        config = {
            "project": {
                "name": project_name,
                "meta": {
                    "id": project_id,
                    "name": project_name,
                    "slug": project_slug,
                    "path": ".",
                    "kind": "project",
                },
            },
            "structures": [],
            "calculations": [],
        }
        
        save_project_config(target_dir, config)
        
        # Create standard directories
        (target_dir / "structures").mkdir(exist_ok=True)
        (target_dir / "calculations").mkdir(exist_ok=True)
        (target_dir / "pseudo").mkdir(exist_ok=True)
        (target_dir / "trash").mkdir(exist_ok=True)
        
        return target_dir
    
    @staticmethod
    def configure_project(
        project_root: Path,
        new_name: Optional[str] = None,
    ) -> None:
        """Configure project settings."""
        config = load_project_config(project_root)
        project = config.setdefault("project", {})
        meta = project.setdefault("meta", {})
        
        if new_name:
            project["name"] = new_name
            meta["name"] = new_name
            meta["slug"] = slugify(new_name)
        
        save_project_config(project_root, config)
    
    @staticmethod
    def delete_project(project_root: Path, force: bool = False) -> None:
        """Delete a project (move to parent's trash)."""
        project_root = Path(project_root).resolve()
        if not (project_root / "project.qv.yml").exists():
            raise QVServiceError(f"Not a project: {project_root}")
        
        parent = project_root.parent
        trash = parent / "trash"
        move_to_trash(project_root, trash)
    
    @staticmethod
    def export_project_snapshot(
        project_root: Path,
    ) -> Dict[str, Any]:
        """
        Export project into a snapshot dict (ready to dump as YAML).
        
        Args:
            project_root: Path to project root
            
        Returns:
            Dictionary representation of the snapshot
        """
        from quantumvitas.project.snapshot import export_project_to_snapshot
        
        project_root = Path(project_root).resolve()
        if not (project_root / "project.qv.yml").exists():
            raise QVServiceError(f"Not a project: {project_root}")
        
        snapshot = export_project_to_snapshot(project_root)
        return snapshot.to_dict()
    
    @staticmethod
    def save_project_snapshot(
        project_root: Path,
        output_path: Path,
        overwrite: bool = False,
    ) -> Path:
        """
        Export project and write snapshot YAML to output_path.
        
        Args:
            project_root: Path to project root
            output_path: Path where snapshot YAML will be written
            overwrite: If False, raise error if output_path exists
            
        Returns:
            Path to the written snapshot file
        """
        import yaml
        
        output_path = Path(output_path).resolve()
        
        if output_path.exists() and not overwrite:
            raise QVServiceError(f"Snapshot file already exists: {output_path}. Use overwrite=True to replace.")
        
        snapshot_dict = QVService.export_project_snapshot(project_root)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(yaml.safe_dump(snapshot_dict, sort_keys=False, default_flow_style=False))
        
        return output_path
    
    @staticmethod
    def create_project_from_snapshot(
        parent_dir: Path,
        snapshot_path: Path,
        project_name: Optional[str] = None,
    ) -> Path:
        """
        Read snapshot YAML and create a new project directory under parent_dir.
        
        Args:
            parent_dir: Directory where the new project will be created
            snapshot_path: Path to snapshot YAML file
            project_name: Optional name for the new project (defaults to snapshot name)
            
        Returns:
            Path to the new project root
        """
        import yaml
        from quantumvitas.project.snapshot import ProjectSnapshot, materialize_project_from_snapshot
        
        snapshot_path = Path(snapshot_path).resolve()
        if not snapshot_path.exists():
            raise QVServiceError(f"Snapshot file not found: {snapshot_path}")
        
        parent_dir = Path(parent_dir).resolve()
        parent_dir.mkdir(parents=True, exist_ok=True)
        
        # Load snapshot
        snapshot_data = yaml.safe_load(snapshot_path.read_text())
        snapshot = ProjectSnapshot.from_dict(snapshot_data)
        
        # Materialize project
        project_dir = materialize_project_from_snapshot(
            snapshot=snapshot,
            parent_dir=parent_dir,
            new_project_name=project_name,
        )
        
        return project_dir
    
    # -------------------------------------------------------------------------
    # Structure operations
    # -------------------------------------------------------------------------
    
    @staticmethod
    def import_structure(
        project_root: Path,
        source: Path,
        name: Optional[str] = None,
        format: str = "auto",
        *,
        index: Optional["ResourceIndex"] = None,
        dedup_by_fingerprint: bool = False,
    ) -> ResolvedResource:
        """
        Import a structure file into the project.
        
        Args:
            project_root: Project root path
            source: Path to source file (CIF, QE input, JSON, etc.)
            name: Name for the structure (defaults to filename stem)
            format: File format hint
            index: Optional resource index for registry update
            dedup_by_fingerprint: If True, reuse existing structure with same content fingerprint.
                                  If False (default), always create a new structure resource
                                  with unique name/slug (e.g. silicon, silicon-2, ...).
            
        Returns:
            ResolvedResource for the imported structure
        """
        from quantumvitas.io import read_structure, write_structure
        
        source = Path(source).resolve()
        if not source.exists():
            raise QVServiceError(f"Source file not found: {source}")
        
        config = load_project_config(project_root)
        structures = config.setdefault("structures", [])
        existing_slugs = collect_slugs(structures, project_root=project_root)
        
        # Also check existing structure files for slugs (ID-only model: config only has structure_id)
        structures_dir = project_root / "structures"
        if structures_dir.exists():
            for struct_file in structures_dir.glob("*.json"):
                try:
                    import json
                    struct_data = json.loads(struct_file.read_text())
                    struct_meta = struct_data.get("__qv_meta__") or struct_data.get("meta") or {}
                    if struct_meta.get("slug"):
                        existing_slugs.append(struct_meta["slug"])
                except Exception:
                    pass  # Skip invalid files
        
        structure_name = name or source.stem
        final_name, final_slug = generate_unique_name_and_slug(
            kind="structure",
            preferred_name=structure_name,
            existing_slugs=existing_slugs,
        )
        
        # Read and convert structure
        structure = read_structure(source)
        
        # Check existing structures for same fingerprint (content-based dedup)
        # Only when dedup_by_fingerprint=True (opt-in for demo tooling)
        if dedup_by_fingerprint:
            # Compute fingerprint for content-based deduplication
            from quantumvitas.core.structure_fingerprint import structure_fingerprint
            fingerprint = structure_fingerprint(structure)
            
            structures_dir = project_root / "structures"
            if structures_dir.exists():
                for struct_file in structures_dir.glob("*.json"):
                    try:
                        import json
                        struct_data = json.loads(struct_file.read_text())
                        struct_meta = struct_data.get("__qv_meta__") or struct_data.get("meta") or {}
                        existing_fingerprint = struct_meta.get("fingerprint")
                        if existing_fingerprint == fingerprint:
                            # Found matching structure by fingerprint
                            existing_fingerprint_id = struct_meta.get("id")
                            if existing_fingerprint_id:
                                # Verify with semantic equality as belt-and-suspenders
                                from quantumvitas.core.structure_fingerprint import structures_semantically_equal
                                existing_structure = read_structure(struct_file)
                                if structures_semantically_equal(structure, existing_structure):
                                    # Reuse existing structure
                                    from quantumvitas.core.resolution import require_structure
                                    resolved = require_structure(
                                        project_root, existing_fingerprint_id, config=config, index=index
                                    )
                                    return resolved
                    except Exception:
                        pass  # Skip invalid files
        
        # Compute fingerprint for storage (even if not using for dedup)
        from quantumvitas.core.structure_fingerprint import structure_fingerprint
        fingerprint = structure_fingerprint(structure)
        
        # Write to structures directory
        dest_path = project_root / "structures" / f"{final_slug}.json"
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        meta = meta_from_name(
            "structure",
            name=final_name,
            path=ensure_relative_path(dest_path, base=project_root),
        )
        # Store fingerprint in metadata (add to meta dict)
        meta_dict = meta.to_dict()
        meta_dict["fingerprint"] = fingerprint
        write_structure(structure, dest_path, metadata=meta_dict)
        
        # Add to config (DAG + ID-only: only structure_id, no meta duplication)
        entry = {
            "structure_id": meta.id,  # ID-only reference (ULID)
        }
        structures.append(entry)
        save_project_config(project_root, config)
        
        # Update registry in-place if index is provided (do NOT rebuild)
        # Note: This requires the structure to be resolved to get its meta
        from quantumvitas.core.resolution import require_structure
        resolved = require_structure(project_root, final_slug, config=config, index=index)
        if index is not None:
            from quantumvitas.core.resolution import update_registry_add_structure
            update_registry_add_structure(index, resolved.meta, dest_path)
        
        return resolved
    
    @staticmethod
    def configure_structure(
        project_root: Path,
        selector: str,
        new_name: Optional[str] = None,
        new_slug: Optional[str] = None,
        new_path: Optional[Path] = None,
    ) -> None:
        """Configure/rename a structure."""
        config = load_project_config(project_root)
        entry = find_structure_entry(config, selector, project_root)
        
        apply_structure_rename(
            project_root=project_root,
            config=config,
            entry=entry,
            new_name=new_name,
            new_slug=new_slug,
            new_path=new_path,
        )
        
        save_project_config(project_root, config)
    
    @staticmethod
    def delete_structure(
        project_root: Path,
        selector: str,
        force: bool = False,
        *,
        index: Optional["ResourceIndex"] = None,
    ) -> None:
        """Delete a structure (move to trash)."""
        from quantumvitas.core.resolution import require_structure, build_resource_index
        
        config = load_project_config(project_root)
        registry = build_resource_index(project_root) if index is None else index
        
        # Resolve structure to get its ID (canonical)
        resolved = require_structure(project_root, selector, config=config, index=registry)
        structure_id = resolved.meta.id
        
        # Get entry for calculation dependency checking
        entry = find_structure_entry(config, selector, project_root)
        
        # Check for calculations using this structure
        if not force:
            using_calculations = calculations_using_structure(project_root, config, entry)
            if using_calculations:
                names = ", ".join(w.get("name", "?") for w in using_calculations)
                raise QVServiceError(
                    f"Structure is used by calculations: {names}. Use force to delete anyway."
                )
        
        # Move file to trash
        file_path = entry.get("file") or (entry.get("meta") or {}).get("path") or resolved.meta.path
        if file_path:
            abs_path = (project_root / file_path).resolve()
            if abs_path.exists():
                trash = project_root / "trash"
                move_to_trash(abs_path, trash)
        
        # Remove from config by structure_id (ID-only model)
        structures = config.get("structures", [])
        structures[:] = [
            e for e in structures
            if extract_structure_selector_from_entry(e) != structure_id
        ]
        save_project_config(project_root, config)
        
        # Update registry in-place (remove structure, do NOT rebuild)
        # Only update if index was provided (not if we built a local registry)
        if index is not None:
            from quantumvitas.core.resolution import update_registry_remove_structure
            update_registry_remove_structure(index, structure_id)
    
    @staticmethod
    def list_structures(project_root: Path) -> List[ResolvedResource]:
        """List all structures in a project."""
        return list_structures(project_root)
    
    @staticmethod
    def get_structure(project_root: Path, selector: str) -> ResolvedResource:
        """Get a structure by selector."""
        return require_structure(project_root, selector)
    
    # -------------------------------------------------------------------------
    # Calculation operations
    # -------------------------------------------------------------------------
    
    @staticmethod
    def init_calculation(
        project_root: Path,
        name: str,
        structure_selector: Optional[str] = None,
        template: Optional[str] = None,
        *,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> ResolvedResource:
        """
        Create a new calculation.
        
        Args:
            project_root: Project root path
            name: Calculation name
            structure_selector: Optional structure selector for calculation
            template: Optional template name
            
        Returns:
            ResolvedResource for the new calculation
        """
        config = load_project_config(project_root)
        calculations = config.setdefault("calculations", [])
        existing_slugs = collect_slugs(calculations, project_root=project_root)
        
        final_name, final_slug = generate_unique_name_and_slug(
            kind="calculation",
            preferred_name=name,
            existing_slugs=existing_slugs,
        )
        
        calculation_id = generate_resource_id()
        calculation_path = f"calculations/{final_slug}"
        calculation_dir = project_root / calculation_path
        
        if template:
            from quantumvitas.core.templates import copy_calculation_template
            calculation_dir, _, new_ulid = copy_calculation_template(
                template,
                calculation_dir,
                project_root,
                new_name=final_name,
                structure=structure_selector,
                calculation_ulid=calculation_id,
            )
            calculation_id = new_ulid
            # Create meta for the template-based calculation
            calculation_meta = ResourceMeta(
                id=calculation_id,
                name=final_name,
                slug=final_slug,
                path=calculation_path,
                kind="calculation",
            )
        else:
            from quantumvitas.core.models import CalculationModel, save_calculation
            
            calculation_dir.mkdir(parents=True, exist_ok=True)
            (calculation_dir / "steps").mkdir(exist_ok=True)
            (calculation_dir / "raw").mkdir(exist_ok=True)
            (calculation_dir / "reference").mkdir(exist_ok=True)
            
            # Resolve structure selector to structure_id
            structure_id = None
            structure_name = None
            if structure_selector:
                resolved_structure = require_structure(project_root, structure_selector, config=config, index=index)
                structure_id = resolved_structure.meta.id
                structure_name = resolved_structure.meta.name
            
            # Create calculation using model
            calculation_meta = ResourceMeta(
                id=calculation_id,
                name=final_name,
                slug=final_slug,
                path=calculation_path,
                kind="calculation",
            )
            calculation_model = CalculationModel(
                meta=calculation_meta,
                structure_id=structure_id,
                structure_name=structure_name,
            )
            save_calculation(calculation_model, calculation_dir)
        
        # Add to project config (DAG + ID-only: only calculation_id, no meta duplication)
        entry = {
            "calculation_id": calculation_id,  # ID-only reference (ULID)
        }
        calculations.append(entry)
        save_project_config(project_root, config)
        
        # Build ResolvedResource directly (don't use require_calculation which needs updated index)
        # We have all the information needed: calculation_meta was created above
        calculation_yaml_path = calculation_dir / "calculation.yaml"
        resolved = ResolvedResource(
            meta=calculation_meta,
            entry=entry,  # The entry dict we just added to config
            absolute_path=calculation_dir,
        )
        
        # Update registry in-place if index is provided (do NOT rebuild)
        if index is not None:
            from quantumvitas.core.resolution import update_registry_add_calculation
            update_registry_add_calculation(index, calculation_meta, calculation_yaml_path)
        
        return resolved
    
    @staticmethod
    def configure_calculation(
        project_root: Path,
        selector: str,
        new_name: Optional[str] = None,
        new_structure: Optional[str] = None,
        new_step_order: Optional[List[str]] = None,
    ) -> None:
        """
        Configure a calculation.
        
        Args:
            project_root: Project root path
            selector: Calculation selector
            new_name: Optional new name
            new_structure: Optional new structure selector
            new_step_order: Optional new step order (list of step ids)
        """
        config = load_project_config(project_root)
        entry = find_calculation_entry(config, selector, project_root)
        
        if new_name:
            apply_calculation_rename(
                project_root=project_root,
                config=config,
                entry=entry,
                new_name=new_name,
                new_slug=None,
                new_path=None,
            )
        
        # Update calculation.yaml if needed
        calculation_dir = calculation_directory(project_root, entry)
        calculation_yaml_path = calculation_dir / "calculation.yaml"
        
        if calculation_yaml_path.exists() and (new_structure or new_step_order):
            from quantumvitas.core.models import load_calculation, save_calculation, CalculationStepEntry
            
            model = load_calculation(calculation_dir, project_root)
            
            if new_structure:
                model.structure = new_structure
            
            if new_step_order:
                step_map = {s.step_id: s for s in model.steps}
                new_steps = []
                for step_id in new_step_order:
                    if step_id in step_map:
                        new_steps.append(step_map[step_id])
                model.steps = new_steps
            
            save_calculation(model, calculation_dir)
        
        save_project_config(project_root, config)
    
    @staticmethod
    def delete_calculation(
        project_root: Path,
        calculation_ulid: str,
        force: bool = False,
        cascade: bool = False,
        *,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> None:
        """
        Delete a calculation (move to trash).
        
        Args:
            project_root: Project root path
            calculation_ulid: Calculation ULID (core service requires ULID only)
            force: Force delete
            cascade: Cascade delete dependent calculations
            index: Optional ResourceIndex
            config: Optional project config
        """
        from quantumvitas.core.resolution import validate_ulid, resolve_calculation
        
        # Validate ULID
        calculation_ulid = validate_ulid(calculation_ulid, kind="calculation")
        
        if config is None:
            config = load_project_config(project_root)
        
        # Resolve calculation to get entry
        calculation = resolve_calculation(project_root, calculation_ulid, config=config, index=index)
        
        # Get entry from config for backwards compatibility
        entry = None
        for calc_entry in config.get("calculations", []):
            calc_id = (calc_entry.get("meta") or {}).get("id") or calc_entry.get("calculation_id")
            if calc_id == calculation_ulid:
                entry = calc_entry
                break
        
        if entry is None:
            # Fallback: create minimal entry from resolved calculation
            entry = {
                "meta": calculation.meta.to_dict(),
                "calculation_id": calculation_ulid,
            }
        
        calculation_id = calculation_ulid
        trash = project_root / "trash"
        
        # If cascade=True, we need to collect all calculation IDs that will be deleted
        calculation_ids_to_remove = [calculation_id] if calculation_id else []
        if cascade and index is not None:
            # Find dependent calculations
            from quantumvitas.core.project_utils import calculations_depending_on
            dependents = calculations_depending_on(config, entry)
            for dep in dependents:
                dep_id = (dep.get("meta") or {}).get("id") or dep.get("calculation_id")
                if dep_id:
                    calculation_ids_to_remove.append(dep_id)
        
        delete_calculation_entry(
            project_root=project_root,
            config=config,
            entry=entry,
            trash_dir=trash,
            force=force,
            cascade=cascade,
        )
        
        save_project_config(project_root, config)
        
        # Update registry in-place (remove calculations, do NOT rebuild)
        if index is not None:
            from quantumvitas.core.resolution import update_registry_remove_calculation
            for wf_id in calculation_ids_to_remove:
                if wf_id:
                    update_registry_remove_calculation(index, wf_id)
    
    @staticmethod
    def list_calculations(project_root: Path) -> List[ResolvedResource]:
        """List all calculations in a project."""
        return list_calculations(project_root)
    
    @staticmethod
    def get_calculation(project_root: Path, selector: str) -> ResolvedResource:
        """Get a calculation by selector."""
        return resolve_calculation(project_root, selector)
    
    # -------------------------------------------------------------------------
    # Step operations
    # -------------------------------------------------------------------------
    
    @staticmethod
    def init_step(
        project_root: Path,
        calculation_selector: str,
        step_type: str,
        name: Optional[str] = None,
        structure_selector: Optional[str] = None,
    ) -> ResolvedResource:
        """
        Create a new step in a calculation.
        
        Args:
            project_root: Project root path
            calculation_selector: Parent calculation selector
            step_type: Step type (scf, nscf, dos, bands, etc.)
            name: Optional step name (defaults to step_type)
            structure_selector: Optional structure (defaults to calculation's structure)
            
        Returns:
            ResolvedResource for the new step
        """
        from quantumvitas.calculation.structure_steps import StructureStepSpec
        from quantumvitas.calculation.step_defaults import get_default_step_params
        from quantumvitas.core.models import CalculationModel
        import yaml
        
        calculation = resolve_calculation(project_root, calculation_selector)
        calculation_dir = calculation.absolute_path
        steps_dir = calculation_dir / "steps"
        steps_dir.mkdir(exist_ok=True)
        
        step_name = name or step_type
        step_id = generate_resource_id()
        step_slug = slugify(step_name)
        
        # Generate unique filename
        base_name = step_slug
        suffix = 1
        while (steps_dir / f"{base_name}.step.yaml").exists():
            base_name = f"{step_slug}-{suffix}"
            suffix += 1
        
        step_yaml_path = steps_dir / f"{base_name}.step.yaml"
        
        # Determine structure from calculation if not specified
        from quantumvitas.core.models import load_calculation, save_calculation, CalculationStepEntry
        
        calculation_yaml_path = calculation_dir / "calculation.yaml"
        if calculation_yaml_path.exists():
            wf_model = load_calculation(calculation_dir, project_root)
            if structure_selector is None:
                # Use structure_id if available, else fall back to legacy structure selector
                if wf_model.structure_id:
                    # Resolve structure_id to get selector for step
                    resolved = require_structure(project_root, wf_model.structure_id)
                    structure_selector = resolved.meta.slug
                else:
                    structure_selector = wf_model.structure
        else:
            # Create calculation model if it doesn't exist
            wf_model = CalculationModel(
                meta=calculation.meta,
                structure=structure_selector,
            )
        
        # Use step factory to create and save step (journaled via yaml_io)
        from quantumvitas.workflow.step_factory import create_step_doc, save_step_doc
        from quantumvitas.core.yamldoc import StepDoc
        
        # Resolve structure selector to structure_id if provided
        structure_id = None
        if structure_selector:
            from quantumvitas.core.project_utils import load_project_config
            config = load_project_config(project_root)
            resolved_structure = require_structure(project_root, structure_selector, config)
            structure_id = resolved_structure.meta.id
        
        # Get defaults for step type
        defaults = get_default_step_params(step_type)
        
        # Create step doc using factory (ensures Journal integration)
        step_doc = create_step_doc(
            step_type=step_type,
            name=step_name,
            structure_id=structure_id,  # Will be stored but not authoritative (DAG model)
            parent_calculation_id=calculation.meta.id if hasattr(calculation, 'meta') else None,
            overrides={
                "parameters": defaults.get("parameters", {}),
                "cards": defaults.get("cards", {}),
                "species_overrides": defaults.get("species_overrides", {}),
            },
        )
        
        # Override meta.id and slug to match what was generated above
        step_doc.set(["meta", "id"], step_id)
        step_doc.set(["meta", "slug"], step_slug)
        
        # Calculate relative path for meta.path
        step_yaml_path = step_yaml_path.resolve()
        project_root_resolved = project_root.resolve()
        rel_path = step_yaml_path.relative_to(project_root_resolved)
        step_doc.set(["meta", "path"], str(rel_path.as_posix()))
        
        # Save using factory (goes through yaml_io.save_yaml_doc -> Journal)
        save_step_doc(step_doc, step_yaml_path)
        
        # Add step to calculation model using helper (updates calculation.yaml.steps[])
        step_id_from_doc = step_doc.get(["meta", "id"])
        QVService.calc_add_step(
            project_root=project_root,
            calculation_ulid=calculation.meta.id,
            step_ulid=step_id_from_doc,
            step_type=step_type,
        )
        
        return require_step(project_root, calculation_selector, step_slug)
    
    @staticmethod
    def configure_step(
        project_root: Path,
        calculation_selector: str,
        step_selector: str,
        **kwargs: Any,
    ) -> None:
        """Configure a step's parameters."""
        from quantumvitas.core.yamldoc import StepDoc
        from quantumvitas.workflow.step_factory import save_step_doc
        
        step = require_step(project_root, calculation_selector, step_selector)
        step_path = step.absolute_path
        
        # Load as StepDoc
        step_doc = StepDoc.load(step_path)
        
        # Apply updates via StepDoc API
        for key, value in kwargs.items():
            if value is not None:
                if key in ("parameters", "cards", "species_overrides"):
                    # Use apply_patch for nested dicts
                    step_doc.apply_patch({key: value})
                else:
                    step_doc.set([key], value)
        
        # Save via factory (journaled)
        save_step_doc(step_doc, step_path)
    
    @staticmethod
    def delete_step(
        project_root: Path,
        calculation_selector: str,
        step_selector: str,
    ) -> None:
        """Delete a step (move to trash)."""
        calculation = require_calculation(project_root, calculation_selector)
        step = require_step(project_root, calculation_selector, step_selector)
        
        # Move file to trash
        trash = project_root / "trash"
        move_to_trash(step.absolute_path, trash)
        
        # Remove from calculation.yaml
        calculation_yaml_path = calculation.absolute_path / "calculation.yaml"
        if calculation_yaml_path.exists():
            wf_data = yaml.safe_load(calculation_yaml_path.read_text()) or {}
            steps = wf_data.get("steps", [])
            wf_data["steps"] = [
                s for s in steps 
                if s.get("id", "").lower() != step.meta.name.lower()
            ]
            # Do not write structure_name or structure selector (DAG + ID-only model: only structure_id is written)
            wf_data.pop("structure_name", None)
            wf_data.pop("structure", None)
            if "calculation" in wf_data:
                wf_data["calculation"].pop("structure_name", None)
                wf_data["calculation"].pop("structure", None)
            calculation_yaml_path.write_text(yaml.safe_dump(wf_data, sort_keys=False))
    
    @staticmethod
    def delete_step_from_calculation(
        project_root: Path,
        calculation_selector: str,
        step_selector: str,
        *,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> None:
        """
        Delete a step from a calculation in the DAG + ID-only model.
        
        CRITICAL: Uses calculation.yaml's steps array as the ONLY source of truth.
        - calculation_selector: slug or ULID for the calculation
        - step_selector: ULID for the step (no slug/name/index matching here in the GUI path)
        - Removes step entry from calculation.yaml's steps array
        - Moves the step YAML file into the project's trash folder (with timestamped/unique name),
          using the same helper used by CLI delete commands.
        - If the step YAML file is already missing (ghost step), still remove from calculation.yaml
          and do NOT treat it as an error.
        
        Args:
            project_root: Project root path
            calculation_selector: Calculation selector (slug or ULID)
            step_selector: Step selector (ULID from calculation.yaml)
            index: Optional ResourceIndex (avoids rebuilding if provided)
            config: Optional project config (avoids reloading if provided)
        
        Raises:
            ResourceNotFoundError: If calculation or step not found in calculation.yaml
        """
        from quantumvitas.core.resolution import ResourceNotFoundError, require_calculation, require_step
        from quantumvitas.core.models import load_calculation, save_calculation
        from quantumvitas.core.project_utils import load_project_config
        from quantumvitas.core.resolution import make_structure_selector_resolver
        
        project_root = Path(project_root).resolve()
        
        # Resolve calculation
        calculation_resolved = require_calculation(project_root, calculation_selector, config=config, index=index)
        
        # Determine calculation directory and YAML path
        if calculation_resolved.absolute_path.name == "calculation.yaml":
            calculation_dir = calculation_resolved.absolute_path.parent
            calculation_yaml_path = calculation_resolved.absolute_path
        else:
            calculation_dir = calculation_resolved.absolute_path
            calculation_yaml_path = calculation_dir / "calculation.yaml"
        
        # Load calculation model to get canonical steps list
        if config is None:
            config = load_project_config(project_root)
        resolver = make_structure_selector_resolver(project_root, config=config)
        wf_model = load_calculation(calculation_yaml_path, project_root=project_root, resolve_structure_selector=resolver)
        
        # CRITICAL: Verify step_selector exists in calculation.yaml's steps array
        # This ensures the step belongs to this calculation's DAG
        step_id = step_selector
        entry = next((e for e in wf_model.steps if e.step_id == step_id), None)
        if entry is None:
            # Step not in this calculation's DAG
            raise ResourceNotFoundError(
                kind="step",
                selector=step_selector,
                id=step_selector,
                project_root=project_root,
                message=f"Step '{step_selector}' not found in calculation '{wf_model.meta.name or wf_model.meta.slug or calculation_selector}'. "
                        f"The step must be listed in calculation.yaml's steps array.",
            )
        
        # Remove the step entry from calculation model using helper
        QVService.calc_remove_step(
            project_root=project_root,
            calculation_ulid=calculation_resolved.meta.id,
            step_ulid=step_id,
            index=index,
            config=config,
        )
        
        # Try to resolve and move step file to trash (handle ghost steps gracefully)
        # For ghost steps, require_step may fail, but we've already removed the entry from calculation.yaml
        # We try to resolve the step file path directly from the ResourceIndex to avoid require_step validation
        trash_dir = (project_root / "trash").resolve()
        step_file_moved = False
        
        try:
            # Try to resolve step via ResourceIndex to get file path
            if index is not None:
                # Look up step by ULID in the index
                resource_id = index.resolve_id(step_id, project_root)
                if resource_id:
                    meta = index.by_id.get(resource_id)
                    if meta and meta.kind == "step":
                        # Find absolute path
                        step_path = None
                        for path, path_id in index.by_path.items():
                            if path_id == resource_id:
                                step_path = path
                                break
                        if step_path is None:
                            step_path = (project_root / meta.path).resolve()
                        
                        # Check if file exists and is within the calculation directory
                        if step_path.exists() and step_path.is_relative_to(calculation_dir):
                            move_to_trash(step_path, trash_dir)
                            step_file_moved = True
        except Exception:
            # If index lookup fails, try require_step as fallback
            try:
                step_resolved = require_step(project_root, calculation_selector, step_id, config=config, index=index)
                if step_resolved.absolute_path.exists():
                    move_to_trash(step_resolved.absolute_path, trash_dir)
                    step_file_moved = True
            except (ResourceNotFoundError, SelectorNotFoundError):
                # Step file is missing (ghost step) - this is OK, we've already removed it from calculation.yaml
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(
                    f"Step file for '{step_id}' not found (ghost step). "
                    f"Step entry has been removed from calculation.yaml."
                )
        
        # If we couldn't move the file, it's a ghost step - that's fine, entry is already removed
    
    @staticmethod
    def list_steps(project_root: Path, calculation_selector: str) -> List[ResolvedResource]:
        """List all steps in a calculation."""
        return list_steps(project_root, calculation_selector)
    
    @staticmethod
    def get_step(
        project_root: Path,
        calculation_selector: str,
        step_selector: str,
    ) -> ResolvedResource:
        """Get a step by selector."""
        return require_step(project_root, calculation_selector, step_selector)
    
    # -------------------------------------------------------------------------
    # Run operations
    # -------------------------------------------------------------------------
    
    @staticmethod
    def run_calculation(
        project_root: Path,
        calculation_selector: str,
        strict: bool = False,
        verbose: bool = False,
        *,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Run all steps in a calculation.
        
        This method clears any existing analysis artifacts before running
        to ensure fresh analysis on completion.
        
        Args:
            project_root: Project root path
            calculation_selector: Calculation selector
            strict: If True, fail on first error
            verbose: If True, print detailed output
            
        Returns:
            Dict with run results
        """
        from quantumvitas.project.model import Project
        from quantumvitas.calculation.calculation import Calculation
        from quantumvitas.calculation.runner import CalculationRunner
        from quantumvitas.engine.registry import create_default_registry
        from quantumvitas.analysis.artifacts import clear_analysis_artifacts
        
        # Use registry-based resolution
        from quantumvitas.core.resolution import build_resource_index
        from quantumvitas.core.project_utils import load_project_config
        
        if config is None:
            config = load_project_config(project_root)
        # If index is None, build it (project load scenario)
        if index is None:
            index = build_resource_index(project_root)
        
        # Resolve calculation via registry
        calculation_resolved = require_calculation(project_root, calculation_selector, config=config, index=index)
        
        # Load calculation to check structure_id (canonical source in DAG model)
        project = Project.open(project_root)
        calculation = Calculation.from_yaml(calculation_resolved.absolute_path, project)
        
        if not calculation.structure_id:
            raise QVServiceError(
                f"Calculation '{calculation_selector}' has no structure. Please set a structure for the calculation first."
            )
        
        # Clear analysis artifacts before running (cache invalidation)
        # This ensures fresh analysis is generated after the run completes
        calculation_dir = calculation.dir
        if calculation_dir and calculation_dir.exists():
            clear_analysis_artifacts(calculation_dir)
        
        # CalculationRunner expects an EngineRegistry with engines registered
        registry = create_default_registry()
        runner = CalculationRunner(registry)
        
        results = runner.run(calculation)
        
        # Runner is the source of truth for io_dir - it returns the actual I/O directory used
        # Do NOT construct paths here; use what the runner provides
        result_dict = results.to_dict()
        io_dir = result_dict.get("io_dir")
        
        # Log for debugging
        if io_dir:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[INFO] run_calculation io_dir={io_dir}")
        
        # Convert CalculationResult to dict for JSON serialization
        return {
            "calculation": calculation_selector,
            "status": results.status.value,
            "n_steps": len(results.steps),
            "steps": [
                {
                    "step_id": s.step_id,
                    "step_type": s.step_type.value if hasattr(s.step_type, 'value') else str(s.step_type),
                    "status": s.status.value,
                    "message": s.message,
                    "metrics": s.metrics,
                }
                for s in results.steps
            ],
            "io_dir": io_dir,  # I/O directory from runner (source of truth)
        }
    
    @staticmethod
    def run_step(
        project_root: Path,
        calculation_selector: str,
        step_selector: str,
        verbose: bool = False,
        *,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Run a single step in project mode.
        
        This method uses registry-based resolution and respects the DAG + ID-only model:
        - Structure comes from calculation.structure_id (canonical)
        - Step is resolved via registry using step_id
        - No bare step file execution in project mode
        
        Args:
            project_root: Project root path
            calculation_selector: Calculation selector (name, slug, path, or ULID)
            step_selector: Step selector (name, slug, ULID, or step_type)
            verbose: If True, print detailed output
            
        Returns:
            Dict with run results
        """
        from quantumvitas.project.model import Project
        from quantumvitas.calculation.calculation import Calculation
        from quantumvitas.calculation.input_runner import run_input_step
        from quantumvitas.core.engines.base import EngineConfig
        from quantumvitas.core.engines.qe import QuantumEspressoEngine
        from quantumvitas.io import read_structure
        
        project_root = Path(project_root).resolve()
        
        # Use registry-based resolution
        from quantumvitas.core.resolution import build_resource_index, require_calculation, require_step
        from quantumvitas.core.project_utils import load_project_config
        
        if config is None:
            config = load_project_config(project_root)
        # If index is None, build it (project load scenario)
        if index is None:
            index = build_resource_index(project_root)
        
        # Resolve calculation and step via registry
        calculation_resolved = require_calculation(project_root, calculation_selector, config=config, index=index)
        step_resolved = require_step(project_root, calculation_selector, step_selector, config=config, index=index)
        
        # Load calculation to get structure_id (canonical source)
        project = Project.open(project_root)
        calculation = Calculation.from_yaml(calculation_resolved.absolute_path, project)
        
        # Structure comes from calculation.structure_id (DAG model)
        if not calculation.structure_id:
            raise QVServiceError(
                f"Calculation '{calculation_selector}' has no structure. Please set a structure for the calculation first."
            )
        
        structure_resolved = require_structure(project_root, calculation.structure_id, config=config, index=index)
        structure = read_structure(structure_resolved.absolute_path)
        
        # Load step spec (for step_type and other step-local config)
        from quantumvitas.calculation.structure_steps import StructureStepSpec
        from quantumvitas.core.resolution import make_structure_selector_resolver
        resolver = make_structure_selector_resolver(project_root, config=config)
        spec = StructureStepSpec.from_yaml(step_resolved.absolute_path, resolve_structure_selector=resolver)
        
        # Generate QE input from structure + step spec
        # Use calc-level species_map if available (authoritative source for pseudopot mapping)
        from quantumvitas.calculation.structure_steps import generate_qe_input_from_spec
        from quantumvitas.io.generator import QEInputGenerator
        
        qe_input, _ = generate_qe_input_from_spec(
            structure, spec, species_map=calculation.species_map
        )
        
        # Write input file to calculation's raw directory
        workdir = calculation_resolved.absolute_path / "raw"
        workdir.mkdir(parents=True, exist_ok=True)
        
        # Use human-readable naming based on step_type (not ULID)
        # If multiple steps of same type exist, they will be numbered (e.g., "scf-1.in", "scf-2.in")
        from quantumvitas.calculation.naming import CalculationFileNaming
        input_name = spec.input_name or CalculationFileNaming.input_filename(
            spec.step_type or "scf",
            working_dir=workdir,
        )
        input_path = workdir / input_name
        QEInputGenerator.write_file(qe_input, input_path)
        
        # Create engine - use the core engine directly (not the wrapper)
        engine_config = EngineConfig(name="qe")
        engine = QuantumEspressoEngine(engine_config)
        
        # Run the step
        result, prepared = run_input_step(
            engine=engine,
            input_file=input_path,
            working_dir=workdir,
            project_root=project_root,
            step_type=spec.step_type,
            keep_original=False,
        )
        
        # The runner uses workdir as the I/O directory (source of truth)
        io_dir = str(workdir.resolve())
        
        return {
            "step": step_selector,
            "step_id": step_resolved.meta.id,
            "step_type": result.step_type.value if hasattr(result.step_type, 'value') else str(result.step_type),
            "output_file": str(result.output_file.resolve()) if result.output_file and result.output_file.exists() else None,
            "success": result.error is None,
            "error": result.error,
            "input_file": str(input_path),
            "io_dir": io_dir,  # I/O directory from runner (source of truth)
            # Keep working_dir for backward compatibility during migration
            "working_dir": io_dir,
        }
    
    # -------------------------------------------------------------------------
    # Analysis operations
    # -------------------------------------------------------------------------
    
    @staticmethod
    def visualize_structure(
        project_root: Path,
        structure_selector: str,
        output_path: Optional[Path] = None,
        supercell: Tuple[int, int, int] = (1, 1, 1),
        repeat_boundary: bool = False,
        show: bool = False,
        plot_format: str = "png",
    ) -> Dict[str, Any]:
        """
        Visualize a structure as a 3D ball-and-stick plot.
        
        Args:
            project_root: Project root path
            structure_selector: Structure selector (name/slug/path)
            output_path: Path to save the plot (None for default)
            supercell: Tuple of (a, b, c) supercell scaling factors
            repeat_boundary: If True, show periodic images at cell boundaries
            show: If True, attempt to display interactively
            plot_format: Output format (png, svg, pdf)
            
        Returns:
            Dict with visualization result metadata
        """
        from quantumvitas.io import read_structure
        from quantumvitas.analysis.structure_viz import visualize_structure as viz_structure
        
        # Resolve structure
        resolved = resolve_structure(project_root, structure_selector)
        structure_path = resolved.absolute_path
        
        if not structure_path.exists():
            raise QVServiceError(f"Structure file not found: {structure_path}")
        
        # Load structure
        structure = read_structure(structure_path)
        
        # Determine output path
        if output_path is None:
            output_path = project_root / "results" / f"{resolved.meta.slug}_structure.{plot_format}"
        
        output_path = Path(output_path)
        
        # Visualize
        result = viz_structure(
            structure=structure,
            output_path=output_path,
            supercell=supercell,
            repeat_boundary=repeat_boundary,
            show=show,
            plot_format=plot_format,
        )
        
        return {
            "structure": structure_selector,
            "output_path": str(result.output_path) if result.output_path else None,
            "n_atoms": result.n_atoms,
            "n_bonds": result.n_bonds,
            "supercell": list(supercell),
            "repeat_boundary": repeat_boundary,
        }
    
    @staticmethod
    def analyze_scf(
        project_root: Optional[Path],
        scf_file: Path,
        plot: bool = False,
        output_dir: Optional[Path] = None,
        plot_format: str = "png",
    ) -> Dict[str, Any]:
        """
        Analyze SCF output file for energies and convergence.
        
        Args:
            project_root: Project root path (can be None for standalone analysis)
            scf_file: Path to SCF output file (.out)
            plot: If True, generate convergence plot
            output_dir: Directory for output files (None for auto-detect)
            plot_format: Plot format (png, svg, pdf)
            
        Returns:
            Dict with SCF analysis results
        """
        from quantumvitas.analysis.parsers import parse_scf_output
        from quantumvitas.analysis.plotting import plot_scf_convergence, save_figure
        
        scf_file = Path(scf_file).resolve()
        if not scf_file.exists():
            raise QVServiceError(f"SCF output file not found: {scf_file}")
        
        # Parse SCF output
        result = parse_scf_output(scf_file)
        data = result.to_dict()
        
        # Determine output directory
        if output_dir is None and project_root:
            # Try to detect calculation context from file location
            output_dir = QVService._detect_calculation_results_dir(project_root, scf_file)
        
        # Generate plot if requested
        plot_path = None
        if plot and result.iterations:
            fig, ax = plot_scf_convergence(result)
            if output_dir:
                output_dir = Path(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
                plot_path = output_dir / f"scf_convergence.{plot_format}"
                save_figure(fig, plot_path)
        
        return {
            "data": data,
            "plot_path": str(plot_path) if plot_path else None,
            "converged": result.converged,
            "total_energy_ry": result.total_energy,
            "fermi_energy_ev": result.fermi_energy,
            "n_iterations": len(result.iterations),
        }
    
    @staticmethod
    def analyze_dos(
        project_root: Optional[Path],
        dos_file: Path,
        fermi_energy: Optional[float] = None,
        scf_file: Optional[Path] = None,
        plot: bool = False,
        output_dir: Optional[Path] = None,
        plot_format: str = "png",
        energy_range: Optional[Tuple[float, float]] = None,
        shift_fermi: bool = True,
    ) -> Dict[str, Any]:
        """
        Analyze DOS data file.
        
        Args:
            project_root: Project root path (can be None for standalone analysis)
            dos_file: Path to DOS data file (.dat)
            fermi_energy: Override Fermi energy in eV
            scf_file: Path to SCF/NSCF output to extract Fermi energy
            plot: If True, generate DOS plot
            output_dir: Directory for output files (None for auto-detect)
            plot_format: Plot format (png, svg, pdf)
            energy_range: Energy range for plot (min, max) in eV
            shift_fermi: If True, shift energies to Fermi level
            
        Returns:
            Dict with DOS analysis results
        """
        from quantumvitas.analysis.parsers import parse_dos_data, parse_scf_output, DOSData
        from quantumvitas.analysis.plotting import plot_dos, save_figure
        
        dos_file = Path(dos_file).resolve()
        if not dos_file.exists():
            raise QVServiceError(f"DOS file not found: {dos_file}")
        
        # Parse DOS data
        dos_data = parse_dos_data(dos_file)
        
        # Get Fermi energy from SCF if not provided
        if fermi_energy is None and scf_file:
            scf_path = Path(scf_file)
            if scf_path.exists():
                scf_result = parse_scf_output(scf_path)
                fermi_energy = scf_result.fermi_energy
        
        # Override Fermi energy if provided
        if fermi_energy is not None:
            dos_data = DOSData(
                energies=dos_data.energies,
                dos=dos_data.dos,
                idos=dos_data.idos,
                fermi_energy=fermi_energy,
            )
        
        data = dos_data.to_dict()
        
        # Determine output directory
        if output_dir is None and project_root:
            output_dir = QVService._detect_calculation_results_dir(project_root, dos_file)
        
        # Generate plot if requested
        plot_path = None
        if plot:
            fig, ax = plot_dos(
                dos_data,
                shift_fermi=shift_fermi,
                energy_range=energy_range,
            )
            if output_dir:
                output_dir = Path(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
                plot_path = output_dir / f"dos.{plot_format}"
                save_figure(fig, plot_path)
        
        # Save data file if output_dir specified
        if output_dir:
            import json
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "dos_data.json").write_text(json.dumps(data, indent=2))
        
        return {
            "data": data,
            "plot_path": str(plot_path) if plot_path else None,
            "n_points": len(dos_data.energies),
            "fermi_energy_ev": dos_data.fermi_energy,
            "energy_range_ev": data.get("energy_range_ev"),
        }
    
    @staticmethod
    def analyze_band(
        project_root: Optional[Path],
        bands_file: Optional[Path] = None,
        calculation_selector: Optional[str] = None,
        symmetry_file: Optional[Path] = None,
        scf_file: Optional[Path] = None,
        fermi_energy: Optional[float] = None,
        plot: bool = False,
        output_dir: Optional[Path] = None,
        plot_format: str = "png",
        energy_range: Optional[Tuple[float, float]] = None,
        shift_fermi: bool = True,
    ) -> Dict[str, Any]:
        """
        Analyze band structure data.
        
        Args:
            project_root: Project root path (can be None for standalone analysis)
            bands_file: Path to bands.dat.gnu file (auto-detected if calculation provided)
            calculation_selector: Calculation selector to auto-locate files
            symmetry_file: Path to bands.x output with high-symmetry points
            scf_file: Path to pw.x output (NSCF/SCF) for Fermi energy and reciprocal lattice
            fermi_energy: Override Fermi energy in eV
            plot: If True, generate band structure plot
            output_dir: Directory for output files (None for auto-detect)
            plot_format: Plot format (png, svg, pdf)
            energy_range: Energy range for plot (min, max) in eV
            shift_fermi: If True, shift energies to Fermi level
            
        Returns:
            Dict with band analysis results
        """
        from quantumvitas.analysis.parsers import parse_bands_gnu, parse_scf_output
        from quantumvitas.analysis.plotting import plot_bands, save_figure
        from quantumvitas.calculation.naming import find_band_analysis_files, find_calculation_raw_dir, find_calculation_results_dir
        
        calculation_dir: Optional[Path] = None
        
        # Resolve calculation if selector provided
        if calculation_selector and project_root:
            try:
                calculation = resolve_calculation(project_root, calculation_selector)
                calculation_dir = calculation.absolute_path
            except (SelectorNotFoundError, AmbiguousSelectorError) as e:
                raise QVServiceError(f"Calculation not found: {calculation_selector}") from e
        
        # Auto-locate files from calculation if available
        search_dir: Optional[Path] = None
        if calculation_dir:
            search_dir = find_calculation_raw_dir(calculation_dir)
            if output_dir is None:
                output_dir = find_calculation_results_dir(calculation_dir)
        elif bands_file:
            search_dir = Path(bands_file).resolve().parent
        
        # Find analysis files
        if search_dir and search_dir.exists():
            found_files = find_band_analysis_files(search_dir)
            
            if bands_file is None and found_files.bands_gnu:
                bands_file = found_files.bands_gnu
            
            if symmetry_file is None and found_files.bands_pp_out:
                symmetry_file = found_files.bands_pp_out
            
            if scf_file is None and found_files.pw_output:
                scf_file = found_files.pw_output
        
        # Validate bands file
        if bands_file is None:
            raise QVServiceError(
                "No bands.dat.gnu file found. Provide bands_file argument or use calculation_selector."
            )
        
        bands_file = Path(bands_file).resolve()
        if not bands_file.exists():
            raise QVServiceError(f"Bands file not found: {bands_file}")
        
        # Get Fermi energy from SCF if not provided
        if fermi_energy is None and scf_file:
            scf_path = Path(scf_file)
            if scf_path.exists():
                scf_result = parse_scf_output(scf_path)
                fermi_energy = scf_result.fermi_energy
        
        # Parse bands data
        band_data = parse_bands_gnu(
            bands_file,
            symmetry_file=symmetry_file,
            fermi_energy=fermi_energy,
            pw_output_file=scf_file,  # Provides reciprocal lattice vectors for k-point conversion
        )
        
        data = band_data.to_dict()
        
        # Determine output directory if still None
        if output_dir is None and project_root:
            output_dir = QVService._detect_calculation_results_dir(project_root, bands_file)
        
        # Generate plot if requested
        plot_path = None
        if plot:
            fig, ax = plot_bands(
                band_data,
                shift_fermi=shift_fermi,
                energy_range=energy_range,
            )
            if output_dir:
                output_dir = Path(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
                plot_path = output_dir / f"bands.{plot_format}"
                save_figure(fig, plot_path)
        
        # Save data file if output_dir specified
        if output_dir:
            import json
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "bands_data.json").write_text(json.dumps(data, indent=2))
        
        return {
            "data": data,
            "plot_path": str(plot_path) if plot_path else None,
            "n_bands": band_data.n_bands,
            "n_kpoints": band_data.n_kpoints,
            "fermi_energy_ev": band_data.fermi_energy,
            "high_symmetry_points": [pt.label for pt in band_data.high_symmetry_points],
        }
    
    @staticmethod
    def _detect_calculation_results_dir(
        project_root: Path, 
        file_path: Path,
        *,
        index: Optional["ResourceIndex"] = None,
    ) -> Optional[Path]:
        """
        Detect the calculation results directory from a file's location.
        
        Uses ResourceIndex to resolve calculation paths in the DAG + ID-only model.
        
        Args:
            project_root: Project root path
            file_path: Path to a file within the calculation
            
        Returns:
            Path to results directory, or None if not in a calculation
        """
        try:
            file_path = file_path.resolve()
            project_root = project_root.resolve()
            
            # Use ResourceIndex to find all calculations (DAG + ID-only model)
            # NOTE: This is a read operation that needs the registry. If index is not provided,
            # we build it here (project load scenario). In daemon context, index should be provided.
            from quantumvitas.core.resolution import build_resource_index
            
            # If index is None, build it (project load scenario)
            if index is None:
                index = build_resource_index(project_root)
            
            # Check if file is within any calculation directory
            # ResourceIndex stores calculations in by_id, need to check meta.kind
            for calculation_id, calculation_meta in index.by_id.items():
                kind_str = calculation_meta.kind.value if hasattr(calculation_meta.kind, 'value') else str(calculation_meta.kind)
                if kind_str != "calculation":
                    continue
                
                # Find the calculation directory from the calculation.yaml path
                calculation_path = None
                for path, resource_id in index.by_path.items():
                    if resource_id == calculation_id:
                        calculation_path = path
                        break
                
                if calculation_path:
                    if calculation_path.is_file() and calculation_path.name == "calculation.yaml":
                        # calculation.yaml path - get parent directory
                        calculation_dir = calculation_path.parent
                    else:
                        # Directory path
                        calculation_dir = calculation_path
                    
                    if file_path.is_relative_to(calculation_dir):
                        results_dir = calculation_dir / "results"
                        results_dir.mkdir(parents=True, exist_ok=True)
                        return results_dir
            
            # Fallback: try legacy path-based lookup (for backwards compatibility)
            config = load_project_config(project_root)
            for wf_entry in config.get("calculations", []):
                wf_path = wf_entry.get("path") or (wf_entry.get("meta") or {}).get("path")
                if wf_path:
                    wf_dir = (project_root / wf_path).resolve()
                    if file_path.is_relative_to(wf_dir):
                        results_dir = wf_dir / "results"
                        results_dir.mkdir(parents=True, exist_ok=True)
                        return results_dir
        except Exception:
            pass
        return None


    # -------------------------------------------------------------------------
    # GUI-Ready Data Methods (Phase 1)
    # 
    # These methods return pure JSON-serializable data with no matplotlib objects.
    # Designed for use by both CLI and GUI (via JSON-RPC daemon).
    # -------------------------------------------------------------------------
    
    @staticmethod
    def get_project_summary(project_root: Path) -> Dict[str, Any]:
        """
        Get a high-level summary of a project.
        
        Args:
            project_root: Project root path
            
        Returns:
            Dict with project name, id, structure count, calculation count, etc.
        """
        project_root = Path(project_root).resolve()
        config = load_project_config(project_root)
        
        project_info = config.get("project", {})
        meta = project_info.get("meta", {})
        structures = config.get("structures", [])
        calculations = config.get("calculations", [])
        
        # Use registry to resolve structure/calculation names (ID-only model)
        # Structures and calculations in config only have IDs, need to resolve via registry
        from quantumvitas.core.resolution import list_structures, list_calculations
        
        structure_names = []
        try:
            resolved_structures = list_structures(project_root)
            structure_names = [res.meta.name for res in resolved_structures]
        except Exception:
            # Fallback: try to get names from structure entries if they have meta
            structure_names = [
                s.get("meta", {}).get("name") or s.get("name", "?")
                for s in structures
            ]
        
        calculation_names = []
        try:
            resolved_calculations = list_calculations(project_root)
            calculation_names = [res.meta.name for res in resolved_calculations]
        except Exception:
            # Fallback: try to get names from calculation entries if they have meta
            calculation_names = [
                w.get("meta", {}).get("name") or w.get("name", "?")
                for w in calculations
            ]
        
        return {
            "id": meta.get("id"),
            "name": project_info.get("name") or meta.get("name") or project_root.name,
            "slug": meta.get("slug"),
            "path": str(project_root),
            "n_structures": len(structures),
            "n_calculations": len(calculations),
            "structure_names": structure_names,
            "calculation_names": calculation_names,
        }
    
    @staticmethod
    def list_structures_data(project_root: Path) -> List[Dict[str, Any]]:
        """
        List all structures as JSON-serializable dicts.
        
        Args:
            project_root: Project root path
            
        Returns:
            List of dicts, each with id, name, slug, path, and structure metadata
        """
        project_root = Path(project_root).resolve()
        resolved_list = list_structures(project_root)
        
        result = []
        for res in resolved_list:
            entry = {
                "id": res.meta.id,
                "name": res.meta.name,
                "slug": res.meta.slug,
                "path": res.meta.path,
                "absolute_path": str(res.absolute_path),
            }
            
            # Try to add structure metadata (formula, n_atoms, etc.)
            try:
                from quantumvitas.io import read_structure
                if res.absolute_path.exists():
                    struct = read_structure(res.absolute_path)
                    entry["formula"] = struct.composition.reduced_formula
                    entry["n_atoms"] = len(struct)
                    entry["n_species"] = len(struct.composition.elements)
                    entry["lattice_type"] = struct.lattice.pbc.__class__.__name__ if hasattr(struct.lattice, 'pbc') else "3D"
                    # Lattice parameters
                    latt = struct.lattice
                    entry["lattice_params"] = {
                        "a": float(latt.a),
                        "b": float(latt.b),
                        "c": float(latt.c),
                        "alpha": float(latt.alpha),
                        "beta": float(latt.beta),
                        "gamma": float(latt.gamma),
                        "volume": float(latt.volume),
                    }
            except Exception:
                pass  # Structure metadata is optional
            
            result.append(entry)
        
        return result
    
    @staticmethod
    def list_calculations_data(
        project_root: Path,
    ) -> List[Dict[str, Any]]:
        """
        List all calculations as JSON-serializable dicts.
        
        Uses Project.open() and Calculation.from_yaml() to ensure legacy calculations
        are automatically migrated to the ID-only model.
        
        Args:
            project_root: Project root path
            
        Returns:
            List of dicts, each with calculation metadata and step info
        """
        project_root = Path(project_root).resolve()
        
        # Use Project.open() to get calculation references
        # Project.open() builds its own index internally (keeps it self-contained)
        from quantumvitas.project.model import Project
        try:
            project = Project.open(project_root)
        except Exception as e:
            # If project can't be opened, fall back to basic listing
            resolved_list = list_calculations(project_root)
            return [
                {
                    "id": res.meta.id,
                    "name": res.meta.name,
                    "slug": res.meta.slug,
                    "path": res.meta.path,
                    "absolute_path": str(res.absolute_path),
                    "mode": "normal",  # Default mode
                    "n_steps": 0,
                    "steps": [],
                }
                for res in resolved_list
            ]
        
        result = []
        for calculation_ref in project.calculations.values():
            entry = {
                "id": calculation_ref.meta.id,
                "name": calculation_ref.meta.name,
                "slug": calculation_ref.meta.slug,
                "path": calculation_ref.meta.path,
                "absolute_path": str(calculation_ref.absolute_path),
                "mode": "normal",  # Default mode (will be overridden if calculation loads successfully)
                "n_steps": 0,  # Default (will be overridden if calculation loads successfully)
                "steps": [],  # Default (will be overridden if calculation loads successfully)
            }
            
            # Try to load calculation with migration support (inspection mode)
            # This uses Calculation.from_yaml() which handles legacy step entries
            try:
                from quantumvitas.calculation.calculation import Calculation
                if calculation_ref.absolute_path.exists():
                    calculation = Calculation.from_yaml(calculation_ref.absolute_path, project, materialize_steps=False)
                    
                    # Extract structure info
                    if calculation.structure:
                        entry["structure"] = calculation.structure.meta.name if hasattr(calculation.structure, 'meta') else str(calculation.structure)
                        entry["structure_id"] = calculation.structure.meta.id if hasattr(calculation.structure, 'meta') else None
                    else:
                        entry["structure"] = None
                        entry["structure_id"] = None
                    
                    # Ensure mode is always present (default to "normal" if not set)
                    entry["mode"] = calculation.mode.value if hasattr(calculation.mode, 'value') else (str(calculation.mode) if calculation.mode else "normal")
                    entry["n_steps"] = len(calculation.steps)
                    
                    # Extract step info from actual Step objects (which have ULID meta.id)
                    entry["steps"] = [
                        {
                            "step_id": step.meta.id,  # ULID (canonical reference)
                            "id": step.meta.id,  # Also include as 'id' for backwards compatibility in API response
                            "type": step.step_type.value if hasattr(step.step_type, 'value') else str(step.step_type),
                            # step_file is NOT included - step location resolved via registry
                        }
                        for step in calculation.steps
                    ]
            except Exception as e:
                # If calculation loading fails, still return basic metadata
                # but log the error for debugging
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to load calculation details for {calculation_ref.meta.name}: {e}")
                # Calculation details are optional, but mode/n_steps/steps are already set to defaults above
            
            result.append(entry)
        
        return result
    
    @staticmethod
    def _build_structure_vis_payload(
        structure: Any,  # PMGStructure
        params: Any,  # DisplayModeParams
        structure_meta: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Shared helper to build structure visualization payload with performance timing.
        
        Args:
            structure: pymatgen Structure object
            params: DisplayModeParams
            structure_meta: Optional metadata dict (structure_id, structure_name, formula)
            trace_id: Optional trace ID for performance logging
            
        Returns:
            Dict with visualization data and perf metrics
        """
        from quantumvitas.analysis.structure_viz import (
            build_bonds,
            build_display_atoms,
            get_element_color,
            get_element_radius,
            ELEMENT_COLORS,
            DisplayModeParams,
        )
        import numpy as np
        import logging
        
        logger = logging.getLogger(__name__)
        total_start = time.time()
        
        # Determine kind (project vs online) for debug logging
        kind = "project"
        if structure_meta and "structure_id" in structure_meta:
            if structure_meta["structure_id"].startswith("online:"):
                kind = "online"
        
        # DEBUG: Log canonical structure state (before build_display_atoms)
        # This is the structure that enters the shared pipeline
        canonical_lattice = structure.lattice.matrix
        canonical_nsites = len(structure)
        canonical_species = [str(site.specie) for site in structure]
        canonical_frac_coords = structure.frac_coords
        
        logger.info(
            f"[PIPELINE] kind={kind} mode={params.mode} "
            f"supercell={params.supercell if params.supercell else '1x1x1'} "
            f"repeat_boundary={params.repeat_boundary}"
        )
        logger.info(
            f"[PIPELINE] canonical_structure: nsites={canonical_nsites} "
            f"lattice_shape={canonical_lattice.shape} "
            f"species_first10={canonical_species[:10]}"
        )
        if len(canonical_frac_coords) > 0:
            frac_sample = canonical_frac_coords[:5]
            # P2: Removed INFO-level canonical_frac_coords_first5 dump (reduce noise)
        
        # Measure prep time (display atoms)
        prep_start = time.time()
        display_atoms_list, display_structure = build_display_atoms(
            structure,
            params,
            wrap_coords=True,
        )
        prep_end = time.time()
        prep_ms = (prep_end - prep_start) * 1000
        
        # DEBUG: Log display atoms state
        display_atoms_count = len(display_atoms_list)
        if display_atoms_count > 0:
            # Sample first 5 display atoms
            sample_atoms = display_atoms_list[:5]
            atom_samples = []
            for da in sample_atoms:
                atom_samples.append(
                    f"{da.element}:frac[{da.frac_coords[0]:.6f},{da.frac_coords[1]:.6f},{da.frac_coords[2]:.6f}]"
                    f":cart[{da.cart_coords[0]:.6f},{da.cart_coords[1]:.6f},{da.cart_coords[2]:.6f}]"
                )
            logger.info(
                f"[PIPELINE] display_atoms: count={display_atoms_count} "
                f"first5={atom_samples}"
            )
            
            # Compute cartesian bbox
            all_cart = np.array([da.cart_coords for da in display_atoms_list])
            cart_min = all_cart.min(axis=0)
            cart_max = all_cart.max(axis=0)
            # P2: Removed INFO-level display_atoms_cart_bbox dump (reduce noise)
        
        # P2: Removed INFO-level boundary_atoms first5 dump (reduce noise)
        # Boundary count is included in summary log below
        
        # Get lattice info
        lattice = display_structure.lattice
        
        # CRITICAL: Payload contract - atoms must contain ALL display atoms (for rendering + bonds)
        # boundary_atoms is optional UI metadata only, bonds cannot reference it
        atoms = []  # ALL display atoms (canonical + supercell + boundary)
        boundary_atoms = []  # UI metadata only (for visual distinction)
        for da in display_atoms_list:
            atom_dict = {
                "index": len(atoms),  # Index in the atoms array (0-based, sequential)
                "original_idx": da.original_idx,  # Original canonical index
                "element": da.element,
                "cart_coords": [float(c) for c in da.cart_coords],
                "frac_coords": [float(f) for f in da.frac_coords],
                "color": get_element_color(da.element),
                "radius": get_element_radius(da.element),
            }
            # Mark boundary atoms for UI, but include them in main atoms array
            if "boundary" in da.stable_id:
                atom_dict["is_boundary"] = True
                boundary_atoms.append(atom_dict)  # For UI reference
            atoms.append(atom_dict)  # Always add to main atoms array
        
        # Measure bond building time
        bonds_start = time.time()
        bonds = []
        try:
            # CRITICAL: Use the exact same atom list that will be rendered
            # Extract cartesian coordinates from display atoms (these are the final positions)
            atoms_cart = np.array([da.cart_coords for da in display_atoms_list])
            species = [da.element for da in display_atoms_list]
            
            # Validate: all cart_coords should be finite and reasonable
            if len(atoms_cart) > 0:
                cart_max = np.abs(atoms_cart).max()
                if cart_max > 1e6:
                    logger.warning(
                        f"Unreasonable cartesian coordinates detected: max abs = {cart_max:.2f}. "
                        f"This may indicate a coordinate system mismatch."
                    )
            
            # Build bonds using ONLY cartesian distances (no PBC wrapping)
            # The display_atoms_list already includes all repeated/boundary atoms
            detected_bonds = build_bonds(
                atoms_cart,
                species=species,
                max_factor=1.2,
                tolerance=0.3,
                max_cutoff=3.5,
            )
            
            # Convert to dict format and compute diagnostics
            # CRITICAL: bonds.idx1/idx2 must reference atoms array (0 to len(atoms)-1)
            bond_distances = []
            max_bond_idx = -1
            for bond in detected_bonds:
                distance = float(bond.distance)
                bond_distances.append(distance)
                idx1 = int(bond.idx1)
                idx2 = int(bond.idx2)
                max_bond_idx = max(max_bond_idx, idx1, idx2)
                bonds.append({
                    "idx1": idx1,
                    "idx2": idx2,
                    "coord1": [float(c) for c in bond.coord1],
                    "coord2": [float(c) for c in bond.coord2],
                    "distance": distance,
                })
            
            # HARD ASSERT: bonds must only reference atoms array
            atoms_len = len(atoms)
            if bonds and max_bond_idx >= atoms_len:
                error_msg = (
                    f"INVALID PAYLOAD: bonds reference invalid atom indices. "
                    f"maxBondIndex={max_bond_idx} >= atoms_len={atoms_len}. "
                    f"Bonds must only reference payload.atoms (0 to {atoms_len-1})."
                )
                logger.error(f"[PIPELINE] {error_msg}")
                raise ValueError(error_msg)
            
            # P2: Only log PAYLOAD_EVIDENCE on assertion failure (reduce noise)
            # Summary log is below
            
            # Diagnostics: log bond statistics
            if bond_distances:
                bond_distances_sorted = sorted(bond_distances)
                max_bond = max(bond_distances)
                p99_bond = bond_distances_sorted[int(len(bond_distances) * 0.99)] if len(bond_distances) > 0 else 0
                
                # Compute atom degrees (how many bonds per atom)
                atom_degrees = [0] * len(display_atoms_list)
                for bond in detected_bonds:
                    atom_degrees[bond.idx1] += 1
                    atom_degrees[bond.idx2] += 1
                max_degree = max(atom_degrees) if atom_degrees else 0
                max_degree_atom_idx = atom_degrees.index(max_degree) if max_degree > 0 else -1
                
                # Find most anomalous bond (longest)
                most_anomalous_bond = None
                if bonds:
                    most_anomalous_bond = max(bonds, key=lambda b: b["distance"])
                
                # P2: Removed INFO-level detailed bond diagnostics (reduce noise)
                # Summary is logged below, warnings are logged on anomalies
                
                # P2: Summary will be logged after total_ms and payload_kb are computed (see below)
                
                # Warning if bonds seem unreasonable
                if max_bond > 6.0:  # Conservative threshold for typical materials
                    # Find the problematic bond(s)
                    problematic_bonds = [b for b in bonds if b["distance"] > 6.0]
                    problematic_atoms = set()
                    for pb in problematic_bonds[:5]:  # Limit to first 5 for logging
                        problematic_atoms.add(pb["idx1"])
                        problematic_atoms.add(pb["idx2"])
                    
                    logger.warning(
                        f"[viz] WARNING: Unusually long bonds detected (max={max_bond:.3f}Å). "
                        f"Problematic atom indices: {sorted(problematic_atoms)[:10]}. "
                        f"This may indicate a coordinate system mismatch or incorrect atom repetition."
                    )
                
                if max_degree > 24:
                    # Find atom(s) with high degree
                    high_degree_atoms = [i for i, deg in enumerate(atom_degrees) if deg > 24]
                    logger.warning(
                        f"[viz] WARNING: Atom(s) with excessive bond count (max degree={max_degree}). "
                        f"High-degree atom indices: {high_degree_atoms[:10]}. "
                        f"This may indicate incorrect atom repetition or coordinate wrapping."
                    )
        except Exception as e:
            logger.warning(f"Failed to build bonds: {e}", exc_info=True)
        bonds_end = time.time()
        bonds_ms = (bonds_end - bonds_start) * 1000
        
        # HARD ASSERT: Final payload contract validation
        atoms_len = len(atoms)
        if bonds:
            max_bond_idx = max(max(b["idx1"], b["idx2"]) for b in bonds)
            if max_bond_idx >= atoms_len:
                error_msg = (
                    f"INVALID PAYLOAD CONTRACT: bonds reference invalid indices. "
                    f"maxBondIndex={max_bond_idx} >= atoms_len={atoms_len}. "
                    f"Contract: bonds.idx1/idx2 must reference payload.atoms[0..{atoms_len-1}]."
                )
                logger.error(f"[PIPELINE] {error_msg}")
                raise ValueError(error_msg)
        
        # Build result dict
        # CONTRACT: atoms contains ALL display atoms (for rendering + bonds)
        # P1: atoms is the single source of truth - all display atoms with is_boundary flag
        # boundary_atoms removed (compatibility: keep empty list for now, will remove later)
        result = {
            "n_atoms": atoms_len,  # Total display atoms (canonical + supercell + boundary)
            "n_boundary_atoms": 0,  # DEPRECATED: Use atoms.filter(a=>a.is_boundary) instead
            "n_bonds": len(bonds),
            "lattice": {
                "matrix": lattice.matrix,
                "a": lattice.a,
                "b": lattice.b,
                "c": lattice.c,
                "alpha": lattice.alpha,
                "beta": lattice.beta,
                "gamma": lattice.gamma,
                "volume": lattice.volume,
            },
            "atoms": atoms,  # ALL display atoms (bonds reference this array), use is_boundary flag
            "boundary_atoms": [],  # DEPRECATED: Use atoms.filter(a=>a.is_boundary) instead. Empty for compatibility.
            "bonds": bonds,  # idx1/idx2 reference atoms[0..len(atoms)-1]
            "element_colors": ELEMENT_COLORS,
        }
        
        # Add metadata if provided (structure_id, structure_name, formula, etc.)
        if structure_meta:
            result.update(structure_meta)
        
        # Ensure required fields exist (for compatibility with StructureVisData interface)
        if "structure_id" not in result:
            result["structure_id"] = structure_meta.get("structure_id", "unknown") if structure_meta else "unknown"
        if "structure_name" not in result:
            result["structure_name"] = structure_meta.get("structure_name", "") if structure_meta else ""
        if "formula" not in result:
            # Try to get formula from structure_meta or compute from atoms
            if structure_meta and "formula" in structure_meta:
                result["formula"] = structure_meta["formula"]
            else:
                # Compute from atoms
                from collections import Counter
                element_counts = Counter(atom["element"] for atom in atoms)
                formula_parts = []
                for element, count in sorted(element_counts.items()):
                    if count == 1:
                        formula_parts.append(element)
                    else:
                        formula_parts.append(f"{element}{count}")
                result["formula"] = "".join(formula_parts)
        if "supercell" not in result:
            result["supercell"] = list(params.supercell) if params.supercell else [1, 1, 1]
        if "display_mode" not in result:
            result["display_mode"] = params.mode
        
        # Measure serialization time
        ser_start = time.time()
        result_jsonable = to_jsonable(result)
        # Measure actual JSON bytes
        json_str = json.dumps(result_jsonable)
        json_bytes = len(json_str.encode('utf-8'))
        ser_end = time.time()
        ser_ms = (ser_end - ser_start) * 1000
        
        total_end = time.time()
        total_ms = (total_end - total_start) * 1000
        
        # Add perf metrics to response
        n_display_atoms = len(display_atoms_list)
        n_bonds_count = len(bonds)
        result_jsonable["perf"] = {
            "trace_id": trace_id or "",
            "prep_ms": round(prep_ms, 2),
            "bonds_ms": round(bonds_ms, 2),
            "ser_ms": round(ser_ms, 2),
            "total_ms": round(total_ms, 2),
            "atoms": n_display_atoms,
            "bonds": n_bonds_count,
            "bytes": json_bytes,
        }
        
        # Emit viewer summary log (one line, always visible in GUI)
        # Format: [viewer] kind=online mode=supercell sc=2x2x2 repeat=1 atoms=3->24 bonds=84 prep=8ms bonds=120ms total=135ms payload=420KB
        try:
            kind = "project"
            if structure_meta and "structure_id" in structure_meta:
                if structure_meta["structure_id"].startswith("online:"):
                    kind = "online"
            
            mode_str = params.mode
            sc_str = f"{params.supercell[0]}x{params.supercell[1]}x{params.supercell[2]}" if params.supercell else "1x1x1"
            repeat_str = "1" if params.repeat_boundary else "0"
            
            # Calculate atoms_in (original structure) and atoms_out (display atoms)
            atoms_in = len(structure)
            atoms_out = n_display_atoms
            
            # Format payload size (KB)
            payload_kb = json_bytes / 1024.0
            
            # Format timing (ms, integer)
            t_prep_ms = int(round(prep_ms))
            t_bonds_ms = int(round(bonds_ms))
            t_total_ms = int(round(total_ms))
            
            # P2: 1-line summary with all metrics (reduced noise)
            boundary_count = sum(1 for a in atoms if a.get("is_boundary", False))
            canonical_count = atoms_in
            # Calculate max bond, p99, max degree from bonds
            if bonds:
                bond_distances = [b["distance"] for b in bonds]
                max_bond_val = max(bond_distances)
                bond_distances_sorted = sorted(bond_distances)
                p99_idx = int(len(bond_distances_sorted) * 0.99)
                p99_bond_val = bond_distances_sorted[p99_idx] if p99_idx < len(bond_distances_sorted) else bond_distances_sorted[-1]
                # Calculate max degree
                atom_degrees = [0] * len(atoms)
                for bond in bonds:
                    atom_degrees[bond["idx1"]] += 1
                    atom_degrees[bond["idx2"]] += 1
                max_degree_val = max(atom_degrees) if atom_degrees else 0
            else:
                max_bond_val = 0.0
                p99_bond_val = 0.0
                max_degree_val = 0
            
            logger.info(
                f"[viz] kind={kind} mode={mode_str} "
                f"supercell={sc_str} repeat={repeat_str} "
                f"atoms: {canonical_count}->{atoms_out} "
                f"boundaryCount={boundary_count} bondsCount={n_bonds_count} "
                f"prep={t_prep_ms}ms bonds={t_bonds_ms}ms total={t_total_ms}ms "
                f"payload={payload_kb:.1f}KB maxBond={max_bond_val:.3f}Å p99={p99_bond_val:.3f}Å maxDeg={max_degree_val}"
            )
        except Exception:
            pass  # Never crash on logging
        
        return result_jsonable
    
    @staticmethod
    def get_structure_vis_data(
        project_root: Path,
        selector: str,
        supercell: Tuple[int, int, int] = (1, 1, 1),
        repeat_boundary: bool = False,
        display_mode: str = "primitive",
        box_bounds: Optional[Tuple[float, float, float, float, float, float]] = None,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get pure visualization data for a structure (no matplotlib).
        
        Returns all data needed for 3D rendering in a GUI:
        - Lattice vectors and parameters
        - Atom positions (Cartesian and fractional)
        - Element information and colors
        - Detected bonds
        
        Args:
            project_root: Project root path
            selector: Structure selector (name/slug/path)
            supercell: Tuple of (a, b, c) supercell scaling factors (for supercell mode)
            repeat_boundary: If True, include periodic images at boundaries
            display_mode: One of "primitive", "supercell", "conventional", "box"
            box_bounds: For box mode: (xmin, xmax, ymin, ymax, zmin, zmax)
            
        Returns:
            Dict with all visualization data (JSON-serializable)
        """
        from quantumvitas.io import read_structure
        from quantumvitas.analysis.structure_viz import (
            build_bonds,
            build_display_atoms,
            DisplayModeParams,
            get_element_color,
            get_element_radius,
            ELEMENT_COLORS,
        )
        import numpy as np
        import logging
        
        logger = logging.getLogger(__name__)
        
        project_root = Path(project_root).resolve()
        
        # Resolve structure
        resolved = resolve_structure(project_root, selector)
        if not resolved.absolute_path.exists():
            raise QVServiceError(f"Structure file not found: {resolved.absolute_path}")
        
        # Load structure
        original_structure = read_structure(resolved.absolute_path)
        
        # Normalize supercell input
        from quantumvitas.analysis.structure_viz import _normalize_supercell
        supercell_normalized = _normalize_supercell(supercell)
        
        # Determine effective display mode and supercell
        # If supercell != (1,1,1) and mode is primitive, apply supercell expansion
        # (backward compatibility: supercell parameter should always expand structure)
        effective_mode = display_mode
        effective_supercell = None
        if display_mode == "supercell":
            effective_supercell = supercell_normalized
        elif display_mode != "box" and supercell_normalized != (1, 1, 1):
            # Apply supercell expansion for primitive/conventional modes when supercell is specified
            effective_supercell = supercell_normalized
            # If mode was primitive and supercell is specified, treat as supercell mode
            if display_mode == "primitive":
                effective_mode = "supercell"
        
        # For box mode, ALWAYS ignore repeat_boundary from client (enforce False)
        # This is the single source of truth: Box mode is non-periodic
        if effective_mode == "box":
            effective_repeat_boundary = False
            if repeat_boundary:
                logger.debug(
                    f"Box mode: ignoring client boundaryRepeat={repeat_boundary}, "
                    f"enforcing False (non-periodic)"
                )
        else:
            effective_repeat_boundary = repeat_boundary
        
        # Build display mode params
        params = DisplayModeParams(
            mode=effective_mode,
            supercell=effective_supercell,
            box_bounds=box_bounds if effective_mode == "box" else None,
            repeat_boundary=effective_repeat_boundary,
        )
        
        # Debug logging (dev mode)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"get_structure_vis_data: mode={display_mode}, "
                f"client_repeat_boundary={repeat_boundary}, "
                f"effective_repeat_boundary={effective_repeat_boundary}, "
                f"box_bounds={box_bounds}"
            )
        
        # Use shared payload builder with timing
        structure_meta = {
            "structure_id": resolved.meta.id,
            "structure_name": resolved.meta.name,
            "formula": original_structure.composition.reduced_formula,
            "supercell": list(supercell_normalized),
            "display_mode": effective_mode,
        }
        
        return QVService._build_structure_vis_payload(
            original_structure,
            params,
            structure_meta=structure_meta,
            trace_id=trace_id,
        )
    
    @staticmethod
    def ensure_calculation_analysis(
        project_root: Path,
        calculation_selector: str,
        analysis_type: str,
        step_selector: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Ensure analysis artifacts exist for a calculation.
        
        If JSON artifact exists and force=False, returns cached status.
        Otherwise, parses QE outputs and writes JSON artifact.
        
        The artifact is written to: <calculation>/analysis/<type>.json
        
        Args:
            project_root: Project root path
            calculation_selector: Calculation selector
            analysis_type: Type of analysis ("scf", "dos", "bands")
            step_selector: Optional step selector (used for SCF step identification)
            force: Force re-parse even if artifact exists
            
        Returns:
            Dict with:
                ok: bool - Whether analysis succeeded
                analysis_type: str - Type of analysis
                artifact_path: str | None - Path to JSON artifact
                parsed_fresh: bool - True if just parsed (vs loaded from cache)
                error: str | None - Error message if failed
                summary: dict | None - Quick summary data
        """
        from quantumvitas.analysis.artifacts import ensure_analysis_artifact
        from quantumvitas.calculation.naming import find_calculation_raw_dir
        
        project_root = Path(project_root).resolve()
        calculation = require_calculation(project_root, calculation_selector)
        calculation_dir = calculation.absolute_path
        raw_dir = find_calculation_raw_dir(calculation_dir)
        
        if not raw_dir.exists():
            return {
                "ok": False,
                "analysis_type": analysis_type,
                "artifact_path": None,
                "parsed_fresh": False,
                "error": f"Calculation raw directory not found: {raw_dir}. The calculation may not have been run yet.",
                "summary": None,
            }
        
        # Delegate to the artifacts module
        status = ensure_analysis_artifact(
            analysis_type=analysis_type,
            calculation_dir=calculation_dir,
            raw_dir=raw_dir,
            step_selector=step_selector,
            force=force,
        )
        
        return status.to_dict()
    
    @staticmethod
    def get_scf_convergence_data(
        project_root: Path,
        calculation_selector: str,
        step_selector: str,
    ) -> Dict[str, Any]:
        """
        Get SCF convergence data for a specific step in a calculation.
        
        First attempts to load from JSON artifact (<calculation>/analysis/scf.json).
        If artifact doesn't exist, parses QE output directly and writes artifact.
        
        Args:
            project_root: Project root path
            calculation_selector: Calculation selector
            step_selector: Step selector
            
        Returns:
            Dict with SCF convergence data (iterations, energies, etc.)
        """
        from quantumvitas.analysis.artifacts import read_artifact, ensure_analysis_artifact, AnalysisType
        from quantumvitas.analysis.parsers import parse_scf_output
        from quantumvitas.calculation.naming import find_calculation_raw_dir
        
        project_root = Path(project_root).resolve()
        calculation = require_calculation(project_root, calculation_selector)
        calculation_dir = calculation.absolute_path
        raw_dir = find_calculation_raw_dir(calculation_dir)
        
        if not raw_dir.exists():
            raise QVServiceError(
                f"Calculation raw directory not found: {raw_dir}\n"
                f"The calculation may not have been run yet."
            )
        
        # Try to load from artifact first
        cached = read_artifact(calculation_dir, AnalysisType.SCF)
        if cached:
            # Return cached data (already in correct format)
            return {
                "calculation": calculation_selector,
                "step": step_selector,
                "output_file": cached.get("source_file", ""),
                "converged": cached.get("converged", False),
                "n_iterations": len(cached.get("iterations", [])),
                "total_energy_ry": cached.get("total_energy_ry"),
                "fermi_energy_ev": cached.get("fermi_energy_ev"),
                "iterations": cached.get("iterations", []),
                "calculation_type": cached.get("calculation_type"),
                "n_electrons": cached.get("n_electrons"),
                "n_kpoints": cached.get("n_kpoints"),
                "ecutwfc_ry": cached.get("ecutwfc_ry"),
                "units": cached.get("units", {"energy": "Ry", "fermi": "eV"}),
            }
        
        # No artifact - parse and create one
        status = ensure_analysis_artifact(
            analysis_type=AnalysisType.SCF,
            calculation_dir=calculation_dir,
            raw_dir=raw_dir,
            step_selector=step_selector,
            force=False,
        )
        
        if not status.ok:
            raise QVServiceError(status.error or "Failed to parse SCF output")
        
        # Now read the freshly created artifact
        cached = read_artifact(calculation_dir, AnalysisType.SCF)
        if not cached:
            raise QVServiceError("Failed to read SCF artifact after creation")
        
        return {
            "calculation": calculation_selector,
            "step": step_selector,
            "output_file": cached.get("source_file", ""),
            "converged": cached.get("converged", False),
            "n_iterations": len(cached.get("iterations", [])),
            "total_energy_ry": cached.get("total_energy_ry"),
            "fermi_energy_ev": cached.get("fermi_energy_ev"),
            "iterations": cached.get("iterations", []),
            "calculation_type": cached.get("calculation_type"),
            "n_electrons": cached.get("n_electrons"),
            "n_kpoints": cached.get("n_kpoints"),
            "ecutwfc_ry": cached.get("ecutwfc_ry"),
            "units": cached.get("units", {"energy": "Ry", "fermi": "eV"}),
        }
    
    @staticmethod
    def get_dos_data(
        project_root: Path,
        calculation_selector: str,
        step_selector: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get DOS data for plotting in GUI.
        
        First attempts to load from JSON artifact (<calculation>/analysis/dos.json).
        If artifact doesn't exist, parses QE output directly and writes artifact.
        
        Args:
            project_root: Project root path
            calculation_selector: Calculation selector
            step_selector: Optional step selector (if None, searches for dos files)
            
        Returns:
            Dict with DOS data arrays and Fermi energy
        """
        from quantumvitas.analysis.artifacts import read_artifact, ensure_analysis_artifact, AnalysisType
        from quantumvitas.calculation.naming import find_calculation_raw_dir
        
        project_root = Path(project_root).resolve()
        calculation = require_calculation(project_root, calculation_selector)
        calculation_dir = calculation.absolute_path
        raw_dir = find_calculation_raw_dir(calculation_dir)
        
        if not raw_dir.exists():
            raise QVServiceError(
                f"Calculation raw directory not found: {raw_dir}\n"
                f"The calculation may not have been run yet."
            )
        
        # Try to load from artifact first
        cached = read_artifact(calculation_dir, AnalysisType.DOS)
        if cached:
            return {
                "calculation": calculation_selector,
                "step": step_selector,
                "data_file": cached.get("source_file", ""),
                "n_points": cached.get("n_points", 0),
                "fermi_energy_ev": cached.get("fermi_energy_ev"),
                "energy_range_ev": cached.get("energy_range_ev", [0, 0]),
                "energies_ev": cached.get("energies_ev", []),
                "dos_states_per_ev": cached.get("dos_states_per_ev", []),
                "idos": cached.get("idos"),
                "units": cached.get("units", {"energy": "eV", "dos": "states/eV"}),
            }
        
        # No artifact - parse and create one
        status = ensure_analysis_artifact(
            analysis_type=AnalysisType.DOS,
            calculation_dir=calculation_dir,
            raw_dir=raw_dir,
            step_selector=step_selector,
            force=False,
        )
        
        if not status.ok:
            raise QVServiceError(status.error or "Failed to parse DOS data")
        
        # Now read the freshly created artifact
        cached = read_artifact(calculation_dir, AnalysisType.DOS)
        if not cached:
            raise QVServiceError("Failed to read DOS artifact after creation")
        
        return {
            "calculation": calculation_selector,
            "step": step_selector,
            "data_file": cached.get("source_file", ""),
            "n_points": cached.get("n_points", 0),
            "fermi_energy_ev": cached.get("fermi_energy_ev"),
            "energy_range_ev": cached.get("energy_range_ev", [0, 0]),
            "energies_ev": cached.get("energies_ev", []),
            "dos_states_per_ev": cached.get("dos_states_per_ev", []),
            "idos": cached.get("idos"),
            "units": cached.get("units", {"energy": "eV", "dos": "states/eV"}),
        }
    
    @staticmethod
    def get_band_structure_data(
        project_root: Path,
        calculation_selector: str,
        step_selector: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get band structure data for plotting in GUI.
        
        First attempts to load from JSON artifact (<calculation>/analysis/bands.json).
        If artifact doesn't exist, parses QE output directly and writes artifact.
        
        Args:
            project_root: Project root path
            calculation_selector: Calculation selector
            step_selector: Optional step selector
            
        Returns:
            Dict with band energies, k-distances, high-symmetry points, and Fermi energy
        """
        from quantumvitas.analysis.artifacts import read_artifact, ensure_analysis_artifact, AnalysisType
        from quantumvitas.calculation.naming import find_calculation_raw_dir
        
        project_root = Path(project_root).resolve()
        calculation = require_calculation(project_root, calculation_selector)
        calculation_dir = calculation.absolute_path
        raw_dir = find_calculation_raw_dir(calculation_dir)
        
        if not raw_dir.exists():
            raise QVServiceError(
                f"Calculation raw directory not found: {raw_dir}\n"
                f"The calculation may not have been run yet."
            )
        
        # Try to load from artifact first
        cached = read_artifact(calculation_dir, AnalysisType.BANDS)
        if cached:
            return {
                "calculation": calculation_selector,
                "step": step_selector,
                "data_file": cached.get("source_file", ""),
                "n_bands": cached.get("n_bands", 0),
                "n_kpoints": cached.get("n_kpoints", 0),
                "fermi_energy_ev": cached.get("fermi_energy_ev"),
                "k_distances": cached.get("k_distances", []),
                "energies_ev": cached.get("energies_ev", []),
                "high_symmetry_points": cached.get("high_symmetry_points", []),
                "units": cached.get("units", {"energy": "eV", "k_distance": "2π/a"}),
            }
        
        # No artifact - parse and create one
        status = ensure_analysis_artifact(
            analysis_type=AnalysisType.BANDS,
            calculation_dir=calculation_dir,
            raw_dir=raw_dir,
            step_selector=step_selector,
            force=False,
        )
        
        if not status.ok:
            raise QVServiceError(status.error or "Failed to parse band structure data")
        
        # Now read the freshly created artifact
        cached = read_artifact(calculation_dir, AnalysisType.BANDS)
        if not cached:
            raise QVServiceError("Failed to read bands artifact after creation")
        
        return {
            "calculation": calculation_selector,
            "step": step_selector,
            "data_file": cached.get("source_file", ""),
            "n_bands": cached.get("n_bands", 0),
            "n_kpoints": cached.get("n_kpoints", 0),
            "fermi_energy_ev": cached.get("fermi_energy_ev"),
            "k_distances": cached.get("k_distances", []),
            "energies_ev": cached.get("energies_ev", []),
            "high_symmetry_points": cached.get("high_symmetry_points", []),
            "units": cached.get("units", {"energy": "eV", "k_distance": "2π/a"}),
        }

    @staticmethod
    def get_reference_analysis(
        project_root: Path,
        calculation_selector: str,
        analysis_type: Literal["scf", "dos", "bands"],
    ) -> Optional[Dict[str, Any]]:
        """
        Get reference analysis data for demo projects.
        
        If the project was created from a demo snapshot that includes reference
        artifacts, this returns the reference data for comparison with user-generated
        analysis results.
        
        Args:
            project_root: Project root path
            calculation_selector: Calculation selector (used to match against demo calculation)
            analysis_type: Type of analysis ("scf", "dos", "bands")
            
        Returns:
            Dict with reference analysis data (same format as get_*_data methods),
            or None if project is not from a demo or no reference data exists.
        """
        import json
        from quantumvitas.core.project_utils import load_project_config
        from quantumvitas.core.resources import get_resources_dir
        
        project_root = Path(project_root).resolve()
        config = load_project_config(project_root)
        
        # Check if project has demo origin
        # NOTE: Demo recognition uses origin.kind == "demo" and origin.demo_id (stable identifier),
        # NOT project/calculation ULIDs. This allows reference analysis to work even though
        # materialized projects have fresh ULIDs that differ from the snapshot.
        project_settings = config.get("project", {}).get("settings", {})
        origin = project_settings.get("origin", {})
        
        if origin.get("kind") != "demo":
            return None
        
        demo_id = origin.get("demo_id")  # Stable demo identifier (not a ULID)
        if not demo_id:
            return None
        
        # Get reference_artifacts mapping
        # NOTE: Reference lookup uses origin.reference_artifacts or snapshot.meta.reference_artifacts,
        # NOT project/calculation ULIDs. The artifact filenames are stable identifiers.
        reference_artifacts = origin.get("reference_artifacts", {})
        
        # If no reference_artifacts in project settings, try to load from snapshot meta
        if not reference_artifacts:
            resources_dir = get_resources_dir()
            demo_snapshot_path = resources_dir / "demo_projects" / f"{demo_id}.yml"
            if demo_snapshot_path.exists():
                import yaml
                try:
                    snapshot_data = yaml.safe_load(demo_snapshot_path.read_text())
                    snapshot_meta = snapshot_data.get("meta", {})
                    reference_artifacts = snapshot_meta.get("reference_artifacts", {})
                except Exception:
                    pass
        
        # Check if reference artifact exists for this analysis type
        artifact_filename = reference_artifacts.get(analysis_type)
        if not artifact_filename:
            return None
        
        # Load reference JSON from demo_projects directory
        resources_dir = get_resources_dir()
        reference_path = resources_dir / "demo_projects" / artifact_filename
        
        if not reference_path.exists():
            return None
        
        try:
            data = json.loads(reference_path.read_text())
            
            # Add metadata indicating this is reference data
            data["_is_reference"] = True
            data["_reference_source"] = demo_id
            
            # Return in format compatible with get_*_data methods
            if analysis_type == "scf":
                return {
                    "calculation": calculation_selector,
                    "step": None,
                    "output_file": str(reference_path),
                    "converged": data.get("converged"),
                    "n_iterations": len(data.get("iterations", [])),
                    "total_energy_ry": data.get("total_energy_ry"),
                    "fermi_energy_ev": data.get("fermi_energy_ev"),
                    "iterations": data.get("iterations", []),
                    "calculation_type": data.get("calculation_type"),
                    "n_electrons": data.get("n_electrons"),
                    "n_kpoints": data.get("n_kpoints"),
                    "ecutwfc_ry": data.get("ecutwfc_ry"),
                    "units": data.get("units", {"energy": "Ry", "fermi": "eV"}),
                    "_is_reference": True,
                    "_reference_source": demo_id,
                }
            elif analysis_type == "dos":
                return {
                    "calculation": calculation_selector,
                    "step": None,
                    "data_file": str(reference_path),
                    "n_points": data.get("n_points", len(data.get("energies_ev", []))),
                    "fermi_energy_ev": data.get("fermi_energy_ev"),
                    "energy_range_ev": data.get("energy_range_ev"),
                    "energies_ev": data.get("energies_ev", []),
                    "dos_states_per_ev": data.get("dos_states_per_ev", []),
                    "idos": data.get("idos"),
                    "units": data.get("units", {"energy": "eV", "dos": "states/eV"}),
                    "_is_reference": True,
                    "_reference_source": demo_id,
                }
            elif analysis_type == "bands":
                return {
                    "calculation": calculation_selector,
                    "step": None,
                    "data_file": str(reference_path),
                    "n_bands": data.get("n_bands", 0),
                    "n_kpoints": data.get("n_kpoints", 0),
                    "fermi_energy_ev": data.get("fermi_energy_ev"),
                    "k_distances": data.get("k_distances", []),
                    "energies_ev": data.get("energies_ev", []),
                    "high_symmetry_points": data.get("high_symmetry_points", []),
                    "units": data.get("units", {"energy": "eV", "k_distance": "2π/a"}),
                    "_is_reference": True,
                    "_reference_source": demo_id,
                }
            
            return None
            
        except (json.JSONDecodeError, OSError) as e:
            return None


    # -------------------------------------------------------------------------
    # Environment and Settings (Phase 2 - GUI Parity)
    # -------------------------------------------------------------------------
    
    @staticmethod
    def list_qe_engines() -> Dict[str, Any]:
        """
        List available QE engines (two-state model).
        
        Returns:
            Dict with current_mode, current_bin_dir, and internal_engines list
        """
        from quantumvitas.core.settings import load_settings
        from quantumvitas.core.engines.qe_resolver import find_internal_qe_bin_dir, resolve_qe_bin_dir
        
        settings = load_settings()
        
        # Get current mode
        current_bin_dir = None
        current_mode = "internal"
        resolved_bin_dir = None
        
        try:
            resolved_bin_dir = resolve_qe_bin_dir(settings)
            current_bin_dir = str(resolved_bin_dir)
            if settings.qe.bin_dir:
                current_mode = "external"
            else:
                current_mode = "internal"
        except RuntimeError:
            # No QE found
            pass
        
        # List internal engines
        from quantumvitas.core.paths import home_qe_engines_dir
        engines_base = home_qe_engines_dir()
        internal_engines = []
        
        if engines_base.exists():
            for engine_dir in engines_base.rglob("bin"):
                if not engine_dir.is_dir():
                    continue
                pw_x = engine_dir / "pw.x"
                pw_exe = engine_dir / "pw.x.exe"
                if pw_x.exists() or pw_exe.exists():
                    parent_engine = engine_dir.parent
                    internal_engines.append({
                        "bin_dir": str(engine_dir),
                        "engine_path": str(parent_engine),
                        "pw_path": str(pw_x if pw_x.exists() else pw_exe),
                    })
        
        return {
            "current_mode": current_mode,
            "current_bin_dir": current_bin_dir,
            "internal_engines": internal_engines,
        }
    
    @staticmethod
    def discover_qe_engines() -> Dict[str, Any]:
        """
        Auto-discover QE engines on the system (full disk search).
        
        Results are cached in .tmp/probe/qe_discovery.json.
        
        Returns:
            Dict with discovered engines list
        """
        import json
        import platform
        import time
        from pathlib import Path
        from quantumvitas.core.paths import tmp_probe_dir
        from quantumvitas.core.engines.qe_installation import QEInstallation
        
        cache_path = tmp_probe_dir() / "qe_discovery.json"
        
        # Check cache first
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    # Return cached if less than 1 hour old
                    if time.time() - cached.get("cached_at", 0) < 3600:
                        return cached
            except Exception:
                pass
        
        # Perform discovery
        discovered = []
        
        # Search common locations
        search_paths = []
        if platform.system() == "Windows":
            search_paths.extend([
                Path("C:/Program Files"),
                Path.home() / "AppData" / "Local",
            ])
        else:
            search_paths.extend([
                Path.home() / "src",
                Path.home() / "local",
                Path("/usr/local"),
                Path("/opt"),
            ])
        
        # Also check PATH
        import shutil
        pw_path = shutil.which("pw.x")
        if pw_path:
            qe_home = QEInstallation.qe_home_from_binary(Path(pw_path))
            if qe_home:
                discovered.append({
                    "engine_id": f"external:path:{qe_home.name}",
                    "label": f"QE from PATH ({qe_home})",
                    "qe_home": str(qe_home),
                    "pw_path": pw_path,
                })
        
        # Search filesystem (limited depth to avoid being too slow)
        for search_root in search_paths[:3]:  # Limit to first 3 to avoid timeout
            if not search_root.exists():
                continue
            try:
                for qe_dir in search_root.rglob("q-e-qe-*"):
                    if (qe_dir / "bin" / "pw.x").exists() or (qe_dir / "bin" / "pw.x.exe").exists():
                        pw_path = qe_dir / "bin" / "pw.x"
                        if not pw_path.exists():
                            pw_path = qe_dir / "bin" / "pw.x.exe"
                        discovered.append({
                            "engine_id": f"external:discovered:{qe_dir.name}",
                            "label": f"QE {qe_dir.name} ({qe_dir})",
                            "qe_home": str(qe_dir),
                            "pw_path": str(pw_path),
                        })
                        # Limit results
                        if len(discovered) >= 10:
                            break
                if len(discovered) >= 10:
                    break
            except (PermissionError, OSError):
                continue
        
        result = {
            "discovered_engines": discovered,
            "cached_at": time.time(),
        }
        
        # Save cache
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
        except Exception:
            pass
        
        return result
    
    @staticmethod
    def set_qe_engine(bin_dir: Optional[str]) -> Dict[str, Any]:
        """
        Set QE bin directory (two-state model).
        
        Args:
            bin_dir: Absolute path to QE bin directory, or None to use internal QE
        
        Returns:
            Success status
        """
        from quantumvitas.core.settings import load_settings, save_settings
        from quantumvitas.core.engines.qe_resolver import validate_qe_bin_dir
        from pathlib import Path
        
        settings = load_settings()
        
        if bin_dir:
            # Validate external QE bin directory
            bin_path = Path(bin_dir).resolve()
            validate_qe_bin_dir(bin_path)
            settings.qe.bin_dir = str(bin_path)
        else:
            # Use internal QE
            settings.qe.bin_dir = None
        
        save_settings(settings)
        
        return {"success": True}
    
    @staticmethod
    def detect_qe() -> Dict[str, Any]:
        """
        Detect current QE installation (two-state model).
        
        Returns:
            Dict with QE detection status, path, version, and available executables
        """
        from quantumvitas.core.engines.qe_resolver import resolve_qe_bin_dir
        from quantumvitas.core.engines.qe_installation import QEInstallation
        from quantumvitas.core.settings import load_settings
        from pathlib import Path
        
        try:
            settings = load_settings()
            qe_bin_dir = resolve_qe_bin_dir(settings)
            qe_home = qe_bin_dir.parent  # bin_dir.parent is qe_home
            
            result: Dict[str, Any] = {
                "found": True,
                "qe_home": str(qe_home),
                "qe_bin_dir": str(qe_bin_dir),
                "version": None,
                "executables": [],
                "mode": "external" if settings.qe.bin_dir else "internal",
            }
            
            # Find available executables
            if qe_bin_dir.exists():
                executables = []
                for exe in ["pw.x", "ph.x", "dos.x", "bands.x", "projwfc.x", "pp.x"]:
                    if (qe_bin_dir / exe).exists():
                        executables.append(exe)
                result["executables"] = executables
            
            # Try to get version
            try:
                installation = QEInstallation(qe_home)
                version = installation.version
                if version:
                    result["version"] = version
            except Exception:
                pass
            
            return result
        except RuntimeError as e:
            return {
                "found": False,
                "qe_home": None,
                "qe_bin_dir": None,
                "version": None,
                "executables": [],
                "error": str(e),
            }
    
    @staticmethod
    def get_environment_info() -> Dict[str, Any]:
        """
        Get environment information for the GUI.
        
        Returns:
            Dict with Python version, QV version, QE status, daemon info
        """
        import sys
        from quantumvitas.core.engines.qe_installation import get_qe_home
        
        # Get QE home (may trigger auto-detection)
        qe_home = get_qe_home()
        
        return {
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "python_executable": sys.executable,
            "qv_version": "2.0.0",  # Could read from package metadata
            "qe_home": str(qe_home) if qe_home else None,
            "qe_found": qe_home is not None,
        }
    
    # -------------------------------------------------------------------------
    # Structure CRUD Operations (Phase 3 - GUI Parity)
    # -------------------------------------------------------------------------
    
    @staticmethod
    def rename_structure(
        project_root: Path,
        selector: str,
        new_name: str,
        *,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Rename a structure.
        
        Args:
            project_root: Project root path
            selector: Structure selector (name/slug/path)
            new_name: New name for the structure
            index: Optional ResourceIndex to update in-place
            config: Optional project config
            
        Returns:
            Dict with old_name, new_name, new_slug
        """
        resolved = resolve_structure(project_root, selector, config=config, index=index)
        old_name = resolved.meta.name
        old_path = resolved.absolute_path
        structure_id = resolved.meta.id
        old_meta = resolved.meta
        
        # Get config entry to see what will be updated
        entry = find_structure_entry(config, selector, project_root)
        old_entry_meta = (entry.get("meta") or {}).copy()
        
        QVService.configure_structure(
            project_root=project_root,
            selector=selector,
            new_name=new_name,
        )
        
        # Update registry in-place (do NOT rebuild)
        if index is not None:
            from quantumvitas.core.resolution import update_registry_rename_structure
            from quantumvitas.core.resources import ResourceMeta
            # Get updated metadata from entry (apply_structure_rename updated it)
            new_entry_meta = entry.get("meta") or {}
            new_path_str = entry.get("file") or new_entry_meta.get("path")
            new_path = (project_root / new_path_str).resolve() if new_path_str else old_path
            
            # Construct new ResourceMeta from updated entry
            # Ensure ID is preserved (it should be in the entry or we use the old one)
            new_entry_meta["id"] = new_entry_meta.get("id") or structure_id
            new_meta = ResourceMeta.from_dict(
                new_entry_meta,
                kind="structure",
                default_name=new_entry_meta.get("name", new_name),
                default_path=new_path_str or str(new_path.relative_to(project_root)),
            )
            
            update_registry_rename_structure(index, structure_id, new_meta, old_path, new_path)
        
        return {
            "success": True,
            "old_name": old_name,
            "new_name": new_name,
            "new_slug": slugify(new_name),
        }
    
    @staticmethod
    def can_delete_structure(
        project_root: Path,
        selector: str,
    ) -> Dict[str, Any]:
        """
        Check if a structure can be safely deleted.
        
        Returns:
            Dict with can_delete and list of calculations using this structure
        """
        config = load_project_config(project_root)
        entry = find_structure_entry(config, selector, project_root)
        
        using_calculations = calculations_using_structure(project_root, config, entry)
        calculation_names = [w.get("name", "?") for w in using_calculations]
        
        return {
            "can_delete": len(using_calculations) == 0,
            "using_calculations": calculation_names,
            "structure_name": (entry.get("meta") or {}).get("name") or entry.get("name"),
        }
    
    # -------------------------------------------------------------------------
    # Calculation CRUD Operations (Phase 3 - GUI Parity)
    # -------------------------------------------------------------------------
    
    @staticmethod
    def rename_calculation(
        project_root: Path,
        selector: str,
        new_name: str,
        *,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Rename a calculation.
        
        Args:
            project_root: Project root path
            selector: Calculation selector
            new_name: New name for the calculation
            index: Optional ResourceIndex to update in-place
            config: Optional project config
            
        Returns:
            Dict with old_name, new_name, new_slug
        """
        resolved = resolve_calculation(project_root, selector, config=config, index=index)
        old_name = resolved.meta.name
        calculation_id = resolved.meta.id
        # Get calculation.yaml path (not directory)
        old_calculation_yaml = resolved.absolute_path / "calculation.yaml" if resolved.absolute_path.is_dir() else resolved.absolute_path
        
        # Get config entry to see what will be updated
        if config is None:
            config = load_project_config(project_root)
        entry = find_calculation_entry(config, selector, project_root)
        old_entry_meta = (entry.get("meta") or {}).copy()
        old_entry_path = entry.get("path") or old_entry_meta.get("path")
        
        QVService.configure_calculation(
            project_root=project_root,
            selector=selector,
            new_name=new_name,
        )
        
        # Update registry in-place (do NOT rebuild)
        if index is not None:
            from quantumvitas.core.resolution import update_registry_rename_calculation
            from quantumvitas.core.resources import ResourceMeta
            # Get updated metadata from entry (apply_calculation_rename updated it)
            new_entry_meta = entry.get("meta") or {}
            new_path_str = entry.get("path") or new_entry_meta.get("path")
            new_calculation_dir = (project_root / new_path_str).resolve() if new_path_str else old_calculation_yaml.parent
            new_calculation_yaml = new_calculation_dir / "calculation.yaml"
            
            # Construct new ResourceMeta from updated entry
            # Ensure ID is preserved (it should be in the entry or we use the old one)
            new_entry_meta["id"] = new_entry_meta.get("id") or calculation_id
            new_meta = ResourceMeta.from_dict(
                new_entry_meta,
                kind="calculation",
                default_name=new_entry_meta.get("name", new_name),
                default_path=new_path_str or str(new_calculation_dir.relative_to(project_root)),
            )
            
            update_registry_rename_calculation(index, calculation_id, new_meta, old_calculation_yaml, new_calculation_yaml)
        
        return {
            "success": True,
            "old_name": old_name,
            "new_name": new_name,
            "new_slug": slugify(new_name),
        }
    
    @staticmethod
    def can_delete_calculation(
        project_root: Path,
        calculation_ulid: str,
        *,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Check if a calculation can be safely deleted.
        
        Args:
            project_root: Project root path
            calculation_ulid: Calculation ULID (core service requires ULID only)
            index: Optional ResourceIndex
            config: Optional project config
        
        Returns:
            Dict with calculation name and dependent calculations (if any)
        """
        from quantumvitas.core.resolution import validate_ulid, resolve_calculation
        
        # Validate ULID
        calculation_ulid = validate_ulid(calculation_ulid, kind="calculation")
        
        if config is None:
            config = load_project_config(project_root)
        
        # Resolve calculation to get entry
        calculation = resolve_calculation(project_root, calculation_ulid, config=config, index=index)
        
        # Get entry from config for backwards compatibility with calculations_depending_on
        entry = None
        for calc_entry in config.get("calculations", []):
            calc_id = (calc_entry.get("meta") or {}).get("id") or calc_entry.get("calculation_id")
            if calc_id == calculation_ulid:
                entry = calc_entry
                break
        
        if entry is None:
            # Fallback: create minimal entry from resolved calculation
            entry = {
                "meta": calculation.meta.to_dict(),
                "calculation_id": calculation_ulid,
            }
        
        dependent_calculations = calculations_depending_on(config, entry)
        dep_names = [w.get("name", "?") for w in dependent_calculations]
        
        return {
            "calculation_name": calculation.meta.name,
            "dependent_calculations": dep_names,
            "has_dependencies": len(dep_names) > 0,
        }
    
    # -------------------------------------------------------------------------
    # Step Operations (Phase 4 - GUI Parity)
    # -------------------------------------------------------------------------
    
    @staticmethod
    def get_step_detail(
        project_root: Path,
        calculation_ulid: str,
        step_selector: str,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Get detailed information about a step.
        
        CRITICAL: calculation_ulid MUST be a ULID (not slug/name).
        CRITICAL: For GUI path, step_selector MUST be a ULID that exists in calculation.yaml's steps array.
        We verify this BEFORE resolving via ResourceIndex to ensure the step belongs to this calculation.
        
        Args:
            project_root: Project root path
            calculation_ulid: Calculation ULID (required, not slug/name)
            step_selector: Step selector (for GUI: must be ULID from calculation.yaml)
            index: Optional ResourceIndex (avoids rebuilding if provided)
            config: Optional project config (avoids reloading if provided)
            
        Returns:
            Dict with step metadata, parameters, cards, etc.
            
        Raises:
            ValueError: If calculation_ulid is not a valid ULID
            ResourceNotFoundError: If step_selector is not in calculation.yaml's steps array
        """
        import logging
        from quantumvitas.calculation.structure_steps import StructureStepSpec
        from quantumvitas.core.resolution import ResourceNotFoundError, resolve_calculation, validate_ulid
        from quantumvitas.core.models import load_calculation
        from quantumvitas.core.project_utils import load_project_config
        from quantumvitas.core.resolution import make_structure_selector_resolver
        
        logger = logging.getLogger(__name__)
        
        # Validate calculation_ulid is actually a ULID
        try:
            calculation_ulid = validate_ulid(calculation_ulid, kind="calculation")
        except ValueError as e:
            logger.warning(
                f"[GET_STEP_DETAIL] WARNING: Non-ULID calculation identifier received: '{calculation_ulid}'. "
                f"Core endpoint requires ULID. Error: {e}"
            )
            raise
        
        project_root = Path(project_root).resolve()
        
        # Resolve calculation by ULID (already validated)
        calculation_resolved = resolve_calculation(project_root, calculation_ulid, config=config, index=index)
        
        # Determine calculation directory and YAML path
        if calculation_resolved.absolute_path.name == "calculation.yaml":
            calculation_dir = calculation_resolved.absolute_path.parent
            calculation_yaml_path = calculation_resolved.absolute_path
        else:
            calculation_dir = calculation_resolved.absolute_path
            calculation_yaml_path = calculation_dir / "calculation.yaml"
        
        # Load calculation model to get canonical steps list
        if config is None:
            config = load_project_config(project_root)
        resolver = make_structure_selector_resolver(project_root, config=config)
        wf_model = load_calculation(calculation_yaml_path, project_root=project_root, resolve_structure_selector=resolver)
        
        import logging
        from quantumvitas.core.debug import is_resolution_debug_enabled
        
        logger = logging.getLogger(__name__)
        debug_enabled = is_resolution_debug_enabled()
        
        if debug_enabled:
            logger.info(
                f"[GET_STEP_DETAIL] Resolving step detail: "
                f"calculation_ulid='{calculation_ulid}', step_selector='{step_selector}' "
                f"(is_ulid={len(step_selector) == 26 and step_selector.startswith('01')})"
            )
            
            # Log calculation.yaml steps entries
            logger.info(
                f"[GET_STEP_DETAIL] calculation.yaml.steps[] entries: "
                f"{[(e.step_id, e.type) for e in wf_model.steps]}"
            )
        
        # CRITICAL: Verify step_selector exists in calculation.yaml's steps array
        # This ensures the step belongs to this calculation's DAG
        step_id = step_selector
        entry = next((e for e in wf_model.steps if e.step_id == step_id), None)
        if entry is None:
            # Step not in this calculation's DAG
            logger.error(
                f"[GET_STEP_DETAIL] ERROR: Step selector '{step_selector}' not found in "
                f"calculation.yaml.steps[]. Available step_ids: {[e.step_id for e in wf_model.steps]}"
            )
            raise ResourceNotFoundError(
                kind="step",
                selector=step_selector,
                id=step_selector,
                project_root=project_root,
                message=f"Step '{step_selector}' not found in calculation '{wf_model.meta.name or wf_model.meta.slug or calculation_selector}'. "
                        f"The step must be listed in calculation.yaml's steps array.",
            )
        
        if debug_enabled:
            logger.info(
                f"[GET_STEP_DETAIL] Step entry found in calculation.yaml: "
                f"step_id={entry.step_id}, type={entry.type}"
            )
        
        # Now that we know the step belongs to this calculation, resolve it via ResourceIndex
        step = resolve_step(project_root, calculation_ulid, step_id, config=config, index=index)
        
        if debug_enabled:
            logger.info(
                f"[GET_STEP_DETAIL] Step resolved via ResourceIndex: "
                f"id={step.meta.id}, slug={step.meta.slug}, kind={step.meta.kind}, "
                f"path={step.absolute_path}"
            )
        
        # CRITICAL: Verify the step file actually exists on disk.
        # If calculation.yaml has a step entry but the step file is missing (ghost step),
        # this will raise FileNotFoundError which we convert to a clear error.
        if not step.absolute_path.exists():
            from quantumvitas.core.resolution import ResourceNotFoundError
            error = ResourceNotFoundError(
                kind="step",
                selector=step_selector,
                id=step.meta.id if step.meta else None,
                project_root=project_root,
                        message=f"Step '{step_selector[:8]}...{step_selector[-6:]}' is listed in calculation '{wf_model.meta.name or wf_model.meta.slug or calculation_ulid}', "
                        f"but the expected step YAML file '{step.absolute_path}' "
                        f"does not exist. Registry and filesystem are out of sync. Try refreshing the project registry.",
            )
            error.details = {
                "calculation_path": str(calculation_yaml_path),
                "expected_step_path": str(step.absolute_path),
                "reason": "step_file_missing",
            }
            raise error
        
        # Load step spec (DAG + ULID model: structure_id is already in spec)
        try:
            spec = StructureStepSpec.from_yaml(step.absolute_path, resolve_structure_selector=None)
        except FileNotFoundError:
            # Step file was deleted or never created (ghost step)
            from quantumvitas.core.resolution import ResourceNotFoundError
            error = ResourceNotFoundError(
                kind="step",
                selector=step_selector,
                id=step.meta.id if step.meta else None,
                project_root=project_root,
                        message=f"Step '{step_selector[:8] if len(step_selector) > 14 else step_selector}...{step_selector[-6:] if len(step_selector) > 6 else step_selector}' is listed in calculation '{wf_model.meta.name or wf_model.meta.slug or calculation_ulid}', "
                        f"but the expected step YAML file '{step.absolute_path}' "
                        f"does not exist. Registry and filesystem are out of sync. Try refreshing the project registry.",
            )
            error.details = {
                "calculation_path": str(calculation_yaml_path),
                "expected_step_path": str(step.absolute_path),
                "reason": "step_file_missing",
            }
            raise error
        
        return {
            "id": step.meta.id,
            "name": step.meta.name,
            "slug": step.meta.slug,
            "path": step.meta.path,
            "absolute_path": str(step.absolute_path),
            "step_type": spec.step_type,
            "structure": spec.structure,
            "parent_calculation_id": spec.parent_calculation_id,
            "parameters": spec.parameters,
            "cards": spec.cards,
            "species_overrides": spec.species_overrides,
        }
    
    @staticmethod
    def update_step_params(
        project_root: Path,
        calculation_ulid: str,
        step_selector: str,
        parameters: Dict[str, Dict[str, Any]],
        cards: Optional[Dict[str, Dict[str, Any]]] = None,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Update step parameters safely.
        
        Args:
            project_root: Project root path
            calculation_ulid: Calculation ULID (core service requires ULID only)
            step_selector: Step selector (ULID, slug, or name)
            parameters: Parameters to update
            cards: Optional cards to update
            index: Optional ResourceIndex
            config: Optional project config
        
        Only updates the specified parameters; does not clobber unknown options.
        Validates types for known parameters.
        
        Args:
            project_root: Project root path
            calculation_selector: Calculation selector
            step_selector: Step selector
            parameters: Dict of namelist -> {param: value} to update
            cards: Optional dict of card updates (e.g., K_POINTS)
            index: Optional ResourceIndex (avoids rebuilding if provided)
            config: Optional project config (avoids reloading if provided)
            
        Returns:
            Updated step detail dict
        """
        from quantumvitas.core.resolution import validate_ulid
        from quantumvitas.core.yamldoc import StepDoc
        from quantumvitas.workflow.step_factory import save_step_doc
        
        # Validate ULID
        calculation_ulid = validate_ulid(calculation_ulid, kind="calculation")
        
        step = resolve_step(project_root, calculation_ulid, step_selector, config=config, index=index)
        
        # Load as StepDoc
        step_doc = StepDoc.load(step.absolute_path)
        
        # Build patch for parameters
        param_patch = {}
        for namelist, params in parameters.items():
            namelist_upper = namelist.upper()
            param_patch[namelist_upper] = {}
            
            for key, value in params.items():
                # Set or remove the parameter
                if value is None:
                    param_patch[namelist_upper][key] = None  # None means delete in apply_patch
                else:
                    # STRING-ONLY: Convert all values to strings for YAML storage
                    param_patch[namelist_upper][key] = str(value)
            
        # Apply parameter patch
        if param_patch:
            step_doc.apply_patch({"parameters": param_patch})
        
        # Update cards if provided
        if cards:
            card_patch = {}
            for card_name, card_data in cards.items():
                card_upper = card_name.upper()
                if card_data is None:
                    card_patch[card_upper] = None  # Delete
                else:
                    card_patch[card_upper] = card_data
            step_doc.apply_patch({"cards": card_patch})
        
        # Save via factory (journaled)
        save_step_doc(step_doc, step.absolute_path)
        
        # Return the updated step detail (pass cached index/config to avoid rebuilding)
        return QVService.get_step_detail(
            project_root=project_root,
            calculation_ulid=calculation_ulid,
            step_selector=step_selector,
            index=index,
            config=config,
        )
    
    @staticmethod
    def get_common_cards(
        project_root: Path,
        calculation_ulid: str,
        step_selector: str,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Get view models for common cards (K_POINTS, etc.).
        
        Args:
            project_root: Project root path
            calculation_ulid: Calculation ULID (core service requires ULID only)
            step_selector: Step selector (ULID, slug, or name)
            index: Optional ResourceIndex
            config: Optional project config
            
        Returns:
            Dict with card view models, e.g. {"k_points": KPointsViewModel}
        """
        from quantumvitas.core.resolution import validate_ulid
        from quantumvitas.calculation.k_points_view import parse_k_points, k_points_from_card_data
        
        # Validate ULID
        calculation_ulid = validate_ulid(calculation_ulid, kind="calculation")
        
        # Get step detail to access cards
        step_detail = QVService.get_step_detail(
            project_root=project_root,
            calculation_ulid=calculation_ulid,
            step_selector=step_selector,
            index=index,
            config=config,
        )
        
        result: Dict[str, Any] = {}
        
        # Parse K_POINTS if present
        cards = step_detail.get("cards", {})
        if "K_POINTS" in cards:
            card_data = cards["K_POINTS"]
            # Convert card data to raw text
            raw = k_points_from_card_data(card_data)
            # Parse to view model
            view_model = parse_k_points(raw)
            # Convert to dict for JSON serialization
            result["k_points"] = {
                "raw": view_model.raw,
                "mode": view_model.mode,
                "automatic": {
                    "nk1": view_model.automatic.nk1,
                    "nk2": view_model.automatic.nk2,
                    "nk3": view_model.automatic.nk3,
                    "sk1": view_model.automatic.sk1,
                    "sk2": view_model.automatic.sk2,
                    "sk3": view_model.automatic.sk3,
                } if view_model.automatic else None,
                "points": [
                    {"x": p.x, "y": p.y, "z": p.z, "w": p.w}
                    for p in (view_model.points or [])
                ],
                "parse_ok": view_model.parse_ok,
                "canonical_raw": view_model.canonical_raw,
                "warnings": view_model.warnings,
                "errors": view_model.errors,
                "summary": view_model.summary,
            }
        
        return result
    
    @staticmethod
    def set_common_card(
        project_root: Path,
        calculation_ulid: str,
        step_selector: str,
        card_name: str,
        view_model: Dict[str, Any],
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Set a common card from view model.
        
        Args:
            project_root: Project root path
            calculation_ulid: Calculation ULID (core service requires ULID only)
            step_selector: Step selector (ULID, slug, or name)
            card_name: Card name (e.g., "K_POINTS")
            view_model: View model dict (from UI)
            index: Optional ResourceIndex
            config: Optional project config
            
        Returns:
            Updated step detail dict
        """
        from quantumvitas.core.resolution import validate_ulid
        from quantumvitas.calculation.k_points_view import (
            KPointsViewModel,
            KPointsAutomatic,
            KPointsPoint,
            format_k_points,
            k_points_to_card_data,
        )
        from quantumvitas.calculation.structure_steps import StructureStepSpec
        from quantumvitas.core.resolution import resolve_step, make_structure_selector_resolver
        from quantumvitas.core.project_utils import load_project_config
        import yaml
        
        # Validate ULID
        calculation_ulid = validate_ulid(calculation_ulid, kind="calculation")
        
        step = resolve_step(project_root, calculation_ulid, step_selector, config=config, index=index)
        
        # Load step spec
        if config is None:
            config = load_project_config(project_root)
        resolver = make_structure_selector_resolver(project_root, config=config)
        spec = StructureStepSpec.from_yaml(step.absolute_path, resolve_structure_selector=resolver)
        
        # Convert view model to raw text based on card type
        if card_name.upper() == "K_POINTS":
            # Reconstruct view model object
            kp_vm = KPointsViewModel(
                raw=view_model.get("raw", ""),
                mode=view_model.get("mode", "custom"),
                automatic=KPointsAutomatic(**view_model["automatic"]) if view_model.get("automatic") else None,
                points=[
                    KPointsPoint(x=p["x"], y=p["y"], z=p["z"], w=p["w"])
                    for p in (view_model.get("points") or [])
                ] if view_model.get("points") else None,
                warnings=view_model.get("warnings"),
            )
            
            # Format to raw text
            raw = format_k_points(kp_vm)
            
            # Convert raw text to card data dict
            card_data = k_points_to_card_data(raw)
            
            # Update via StepDoc
            from quantumvitas.core.yamldoc import StepDoc
            from quantumvitas.workflow.step_factory import save_step_doc
            
            step_doc = StepDoc.load(step.absolute_path)
            step_doc.set(["cards", "K_POINTS"], card_data)
            save_step_doc(step_doc, step.absolute_path)
        else:
            raise ValueError(f"Unsupported card: {card_name}")
        
        # Return updated step detail
        return QVService.get_step_detail(
            project_root=project_root,
            calculation_ulid=calculation_ulid,
            step_selector=step_selector,
            index=index,
            config=config,
        )
    
    @staticmethod
    def get_pseudo_mapping(
        project_root: Path,
        calculation_ulid: str,
        step_selector: str,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Get pseudopotential mapping for a step.
        
        Args:
            project_root: Project root path
            calculation_ulid: Calculation ULID (core service requires ULID only)
            step_selector: Step selector (ULID, slug, or name)
            index: Optional ResourceIndex
            config: Optional project config
            
        Returns:
            Dict with:
            - species: List of species symbols from structure
            - mapping: Dict[str, str] of species -> pseudo filename
            - pseudo_dir: String path to pseudo directory (from CONTROL namelist)
            - available_pseudos: List of available UPF files in project
            - warnings: List of warnings (missing pseudos, etc.)
        """
        from quantumvitas.core.resolution import validate_ulid, resolve_structure
        
        # Validate ULID
        calculation_ulid = validate_ulid(calculation_ulid, kind="calculation")
        
        # Get step detail
        step_detail = QVService.get_step_detail(
            project_root=project_root,
            calculation_ulid=calculation_ulid,
            step_selector=step_selector,
            index=index,
            config=config,
        )
        
        # Get structure to find species
        structure_id = None
        if step_detail.get("structure"):
            # Resolve structure to get species
            try:
                if config is None:
                    from quantumvitas.core.project_utils import load_project_config
                    config = load_project_config(project_root)
                structure = resolve_structure(project_root, step_detail["structure"], config=config, index=index)
                structure_id = structure.meta.id
            except Exception:
                pass
        
        # Get species list from structure
        species_list: List[str] = []
        if structure_id:
            try:
                from quantumvitas.io import read_structure
                structure_file = project_root / "structures" / f"{structure_id}.json"
                if structure_file.exists():
                    structure_obj = read_structure(structure_file)
                    # Preserve original order of elements as they appear in structure
                    # (first occurrence order, not alphabetical)
                    species_set = set()
                    species_list = []
                    for site in structure_obj.sites:
                        symbol = site.specie.symbol
                        if symbol not in species_set:
                            species_set.add(symbol)
                            species_list.append(symbol)
            except Exception:
                pass
        
        # Get current mapping from species_overrides
        mapping: Dict[str, str] = {}
        species_overrides = step_detail.get("species_overrides", {})
        for species, overrides in species_overrides.items():
            if isinstance(overrides, dict) and "pseudopot" in overrides:
                mapping[species] = str(overrides["pseudopot"])
        
        # Get pseudo_dir from CONTROL namelist
        pseudo_dir = ""
        parameters = step_detail.get("parameters", {})
        control_params = parameters.get("CONTROL", {})
        if isinstance(control_params, dict) and "pseudo_dir" in control_params:
            pseudo_dir = str(control_params["pseudo_dir"])
        
        # List available UPF files in project
        available_pseudos: List[str] = []
        project_pseudo_dir = project_root / "pseudo"
        if project_pseudo_dir.exists():
            for file in project_pseudo_dir.iterdir():
                if file.is_file() and file.suffix.lower() in (".upf",):
                    available_pseudos.append(file.name)
        available_pseudos.sort()
        
        # Get SSSP defaults for auto-fill using cutoffs.json (authoritative mapping)
        sssp_defaults: Dict[str, Dict[str, str]] = {}
        sssp_installed: Dict[str, bool] = {"precision": False, "efficiency": False}
        try:
            from quantumvitas.core.pseudo_config import (
                PseudoConfig,
                get_sssp_library_path,
            )
            import json
            
            pseudo_config = PseudoConfig.with_defaults()
            store_dir = Path(pseudo_config.store_dir) if pseudo_config.store_dir else None
            
            if store_dir:
                # Check both precision and efficiency libraries
                for flavor in ["precision", "efficiency"]:
                    lib_base = get_sssp_library_path(store_dir, "1.3.0", flavor)
                    lib_path = lib_base / "library"
                    cutoffs_path = lib_base / "cutoffs.json"
                    
                    # Mark as installed if library directory has UPF files
                    if lib_path.exists() and any(lib_path.glob("*.upf")) or any(lib_path.glob("*.UPF")):
                        sssp_installed[flavor] = True
                    
                    # Use cutoffs.json for authoritative element -> filename mapping
                    if cutoffs_path.exists():
                        try:
                            cutoffs_data = json.loads(cutoffs_path.read_text())
                            # cutoffs.json format: {"Element": {"filename": "...", ...}, ...}
                            for species in species_list:
                                if species not in sssp_defaults:
                                    sssp_defaults[species] = {"precision": "", "efficiency": ""}
                                
                                # Look up element in cutoffs.json
                                element_data = cutoffs_data.get(species, {})
                                filename = element_data.get("filename", "")
                                
                                if filename:
                                    # Verify file actually exists in library
                                    if (lib_path / filename).exists():
                                        sssp_defaults[species][flavor] = filename
                                    else:
                                        # Try case-insensitive match
                                        for actual_file in lib_path.iterdir():
                                            if actual_file.name.lower() == filename.lower():
                                                sssp_defaults[species][flavor] = actual_file.name
                                                break
                        except (json.JSONDecodeError, KeyError):
                            pass
                    
                    # Fallback: if cutoffs.json didn't work, try glob pattern
                    if lib_path.exists():
                        for species in species_list:
                            if species not in sssp_defaults:
                                sssp_defaults[species] = {"precision": "", "efficiency": ""}
                            if not sssp_defaults[species].get(flavor):
                                # Fallback: glob for files starting with element symbol
                                for pp_file in lib_path.glob(f"{species}*.UPF"):
                                    sssp_defaults[species][flavor] = pp_file.name
                                    break
                                if not sssp_defaults[species].get(flavor):
                                    for pp_file in lib_path.glob(f"{species}*.upf"):
                                        sssp_defaults[species][flavor] = pp_file.name
                                        break
        except Exception:
            # If SSSP lookup fails, just return empty defaults
            pass
        
        # Generate warnings
        warnings: List[str] = []
        for species in species_list:
            if species not in mapping:
                warnings.append(f"Missing pseudopotential for {species}")
            elif mapping[species] and mapping[species] not in available_pseudos:
                warnings.append(f"Pseudopotential file '{mapping[species]}' not found in project")
        
        return {
            "species": species_list,
            "mapping": mapping,
            "pseudo_dir": pseudo_dir,
            "available_pseudos": available_pseudos,
            "warnings": warnings,
            "sssp_defaults": sssp_defaults,
            "sssp_installed": sssp_installed,
        }
    
    @staticmethod
    def set_pseudo_mapping(
        project_root: Path,
        calculation_ulid: str,
        step_selector: str,
        mapping: Dict[str, str],
        library_preference: Optional[str] = None,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Set pseudopotential mapping for a step.
        
        Args:
            project_root: Project root path
            calculation_ulid: Calculation ULID (core service requires ULID only)
            step_selector: Step selector (ULID, slug, or name)
            mapping: Dict[str, str] of species -> pseudo filename (empty string to unset)
            library_preference: Optional library preference ('precision' or 'efficiency')
            index: Optional ResourceIndex
            config: Optional project config
            
        Returns:
            Updated step detail dict
        
        Note: pseudo_dir is NOT configurable via UI. Runtime always uses ../pseudo.
        """
        from quantumvitas.core.resolution import validate_ulid
        from quantumvitas.calculation.structure_steps import StructureStepSpec
        from quantumvitas.core.resolution import resolve_step, make_structure_selector_resolver
        from quantumvitas.core.project_utils import load_project_config
        import yaml
        
        # Validate ULID
        calculation_ulid = validate_ulid(calculation_ulid, kind="calculation")
        
        step = resolve_step(project_root, calculation_ulid, step_selector, config=config, index=index)
        
        # Load step spec
        if config is None:
            config = load_project_config(project_root)
        resolver = make_structure_selector_resolver(project_root, config=config)
        spec = StructureStepSpec.from_yaml(step.absolute_path, resolve_structure_selector=resolver)
        
        # Update species_overrides
        if not spec.species_overrides:
            spec.species_overrides = {}
        
        for species, pseudo_filename in mapping.items():
            if species not in spec.species_overrides:
                spec.species_overrides[species] = {}
            
            if pseudo_filename:
                spec.species_overrides[species]["pseudopot"] = str(pseudo_filename)
            else:
                # Remove pseudopot if empty string
                if "pseudopot" in spec.species_overrides[species]:
                    del spec.species_overrides[species]["pseudopot"]
                # Clean up empty overrides
                if not spec.species_overrides[species]:
                    del spec.species_overrides[species]
        
        # Note: pseudo_dir is NOT set from UI - runtime always uses ../pseudo
        # The library_preference is stored for future auto-fill operations but
        # doesn't affect the actual pseudo_dir which is enforced at runtime
        
        # Save via StepDoc (journaled)
        from quantumvitas.core.yamldoc import StepDoc
        from quantumvitas.workflow.step_factory import save_step_doc
        
        step_doc = StepDoc.load(step.absolute_path)
        # Use apply_patch for dict subtree updates
        step_doc.apply_patch({"species_overrides": spec.species_overrides})
        save_step_doc(step_doc, step.absolute_path)
        
        # Return updated step detail
        return QVService.get_step_detail(
            project_root=project_root,
            calculation_ulid=calculation_ulid,
            step_selector=step_selector,
            index=index,
            config=config,
        )
    
    @staticmethod
    def import_pseudo_files(
        project_root: Path,
        file_paths: List[str],
    ) -> Dict[str, Any]:
        """
        Import pseudopotential files into the project pseudo directory.
        
        Handles filename conflicts by auto-renaming with deterministic suffix.
        Project becomes self-contained with all required pseudos in project/pseudo/.
        
        Args:
            project_root: Project root path
            file_paths: List of source file paths to import
            
        Returns:
            Dict with:
            - imported: List of successfully imported filenames (in project/pseudo)
            - renamed: Dict of original_name -> new_name for files that were renamed
            - skipped: List of files skipped due to SHA256 duplicate
            - errors: List of error messages
        """
        import shutil
        import hashlib
        
        def compute_sha256(file_path: Path) -> str:
            """Compute SHA256 hash of a file."""
            sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()
        
        project_root = Path(project_root).resolve()
        project_pseudo_dir = project_root / "pseudo"
        project_pseudo_dir.mkdir(parents=True, exist_ok=True)
        
        # Build SHA256 index of existing pseudos for deduplication
        existing_hashes: Dict[str, str] = {}  # sha256 -> filename
        for existing_file in project_pseudo_dir.iterdir():
            if existing_file.is_file() and existing_file.suffix.lower() in ('.upf',):
                try:
                    existing_hashes[compute_sha256(existing_file)] = existing_file.name
                except Exception:
                    pass  # Skip files that can't be hashed
        
        imported: List[str] = []
        renamed: Dict[str, str] = {}
        skipped: List[str] = []
        errors: List[str] = []
        
        for file_path_str in file_paths:
            try:
                source_path = Path(file_path_str).resolve()
                
                if not source_path.exists():
                    errors.append(f"File not found: {file_path_str}")
                    continue
                
                if not source_path.is_file():
                    errors.append(f"Not a file: {file_path_str}")
                    continue
                
                # Check for valid pseudo file extension
                suffix_lower = source_path.suffix.lower()
                if suffix_lower not in ('.upf',):
                    errors.append(f"Invalid file type (expected .UPF): {source_path.name}")
                    continue
                
                # Compute SHA256 for deduplication
                source_hash = compute_sha256(source_path)
                
                # Check if file with same SHA256 already exists (content duplicate)
                if source_hash in existing_hashes:
                    existing_name = existing_hashes[source_hash]
                    skipped.append(f"{source_path.name} (identical to {existing_name})")
                    # Report the existing filename so UI knows it's available
                    imported.append(existing_name)
                    continue
                
                # Determine target filename with conflict resolution
                original_name = source_path.name
                target_name = original_name
                target_path = project_pseudo_dir / target_name
                
                # If filename already exists (but different content), rename
                if target_path.exists():
                    # Deterministic renaming: add _1, _2, etc. suffix
                    base_name = source_path.stem
                    extension = source_path.suffix
                    counter = 1
                    while target_path.exists():
                        target_name = f"{base_name}_{counter}{extension}"
                        target_path = project_pseudo_dir / target_name
                        counter += 1
                    
                    renamed[original_name] = target_name
                
                # Copy file to project pseudo directory
                shutil.copy2(source_path, target_path)
                imported.append(target_name)
                
                # Update hash index for subsequent files in batch
                existing_hashes[source_hash] = target_name
                
            except Exception as e:
                errors.append(f"Error importing {file_path_str}: {e}")
        
        return {
            "imported": imported,
            "renamed": renamed,
            "skipped": skipped,
            "errors": errors,
        }
    
    @staticmethod
    def search_legacy_pseudos(
        element: str,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Search for pseudopotentials by element using QE legacy tables.
        
        Fetches the element page from QE legacy tables and extracts candidate
        pseudopotential filenames and download URLs.
        
        Args:
            element: Element symbol (e.g., "Si", "Mo")
            config: Optional project config (for network URLs)
            
        Returns:
            Dict with:
            - candidates: List of dicts with filename, url, metadata
            - errors: List of error messages
        """
        import urllib.request
        import urllib.error
        import re
        from quantumvitas.core.pseudo_config import PseudoConfig, get_ssl_context, load_pseudo_config
        
        # Load pseudo config (network URLs are user-level, not project-level)
        pseudo_config = load_pseudo_config()
        
        element_lower = element.lower()
        legacy_url = f"{pseudo_config.legacy_tables_base_url}/ps-library/{element_lower}"
        
        candidates: List[Dict[str, Any]] = []
        errors: List[str] = []
        
        try:
            # Fetch the element page
            req = urllib.request.Request(legacy_url)
            req.add_header('User-Agent', 'QuantumVITAS/1.0')
            
            from quantumvitas.core.pseudo_config import get_ssl_context
            from quantumvitas.core.pseudo_config import get_ssl_context
            with urllib.request.urlopen(req, context=get_ssl_context(), timeout=30) as response:
                html_content = response.read().decode('utf-8', errors='ignore')
            
            # Parse HTML to extract pseudo candidates
            # QE legacy tables typically have links to .UPF files
            # Pattern: look for links ending in .UPF or .upf
            upf_pattern = re.compile(r'href=["\']([^"\']*\.(?:UPF|upf))["\']', re.IGNORECASE)
            filename_pattern = re.compile(r'([^/]+\.(?:UPF|upf))', re.IGNORECASE)
            
            # Find all UPF links
            seen_filenames = set()
            for match in upf_pattern.finditer(html_content):
                url = match.group(1)
                # Extract filename from URL
                filename_match = filename_pattern.search(url)
                if filename_match:
                    filename = filename_match.group(1)
                    if filename not in seen_filenames:
                        seen_filenames.add(filename)
                        
                        # Build full URL if relative
                        if url.startswith('http'):
                            full_url = url
                        elif url.startswith('/'):
                            # Absolute path on same domain
                            base = pseudo_config.legacy_tables_base_url.rsplit('/', 1)[0]
                            full_url = f"{base}{url}"
                        else:
                            # Relative path
                            full_url = f"{legacy_url.rsplit('/', 1)[0]}/{url}"
                        
                        # Try to extract metadata from surrounding HTML
                        # Look for table rows or list items containing the link
                        context_start = max(0, match.start() - 200)
                        context_end = min(len(html_content), match.end() + 200)
                        context = html_content[context_start:context_end]
                        
                        # Extract any text that might indicate XC functional or type
                        xc_match = re.search(r'(pbe|lda|pz|pw|blyp|hse|pbe0)', context, re.IGNORECASE)
                        xc = xc_match.group(1).lower() if xc_match else None
                        
                        candidates.append({
                            "filename": filename,
                            "url": full_url,
                            "element": element,
                            "xc": xc,
                        })
            
            # If no candidates found via links, try alternative patterns
            # Some pages might list filenames in text
            if not candidates:
                # Look for filenames in text content
                text_upf_pattern = re.compile(r'\b([A-Z][a-z]?\.[\w\-]+\.(?:UPF|upf))\b')
                for match in text_upf_pattern.finditer(html_content):
                    filename = match.group(1)
                    if filename not in seen_filenames and filename.lower().startswith(element_lower):
                        seen_filenames.add(filename)
                        # Construct download URL from NETWORK_PSEUDO base
                        download_url = f"{pseudo_config.network_pseudo_base_url}/{filename}"
                        candidates.append({
                            "filename": filename,
                            "url": download_url,
                            "element": element,
                            "xc": None,
                        })
        
        except urllib.error.URLError as e:
            errors.append(f"Network error: {e}")
        except Exception as e:
            errors.append(f"Error parsing legacy tables: {e}")
        
        return {
            "candidates": candidates,
            "errors": errors,
        }
    
    @staticmethod
    def download_pseudo_by_filename(
        project_root: Path,
        filename: str,
        dest_dir: Optional[Path] = None,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Download a pseudopotential by filename from QE network repository.
        
        Args:
            project_root: Project root path
            filename: Exact UPF filename (e.g., "Si.pbe-n-rrkjus_psl.1.0.0.UPF")
            dest_dir: Optional destination directory (default: project_root/pseudo)
            config: Optional project config (for network URLs)
            
        Returns:
            Dict with:
            - filename: Final filename in destination (may be renamed if conflict)
            - renamed: True if filename was changed due to conflict
            - skipped: True if file already exists with same SHA256
            - errors: List of error messages
        """
        import urllib.request
        import urllib.error
        import hashlib
        import tempfile
        from quantumvitas.core.pseudo_config import get_ssl_context, load_pseudo_config
        
        if dest_dir is None:
            dest_dir = project_root / "pseudo"
        dest_dir = Path(dest_dir).resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        # Load pseudo config (network URLs are user-level, not project-level)
        pseudo_config = load_pseudo_config()
        
        download_url = f"{pseudo_config.network_pseudo_base_url}/{filename}"
        
        def compute_sha256(file_path: Path) -> str:
            """Compute SHA256 hash of a file."""
            sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()
        
        # Build SHA256 index of existing pseudos
        existing_hashes: Dict[str, str] = {}
        for existing_file in dest_dir.iterdir():
            if existing_file.is_file() and existing_file.suffix.lower() in ('.upf',):
                try:
                    existing_hashes[compute_sha256(existing_file)] = existing_file.name
                except Exception:
                    pass
        
        result = {
            "filename": filename,
            "renamed": False,
            "skipped": False,
            "errors": [],
        }
        
        try:
            # Download to temporary file first
            with tempfile.NamedTemporaryFile(delete=False, suffix='.upf') as tmp_file:
                tmp_path = Path(tmp_file.name)
            
            req = urllib.request.Request(download_url)
            req.add_header('User-Agent', 'QuantumVITAS/1.0')
            
            from quantumvitas.core.pseudo_config import get_ssl_context
            from quantumvitas.core.pseudo_config import get_ssl_context
            with urllib.request.urlopen(req, context=get_ssl_context(), timeout=30) as response:
                with open(tmp_path, 'wb') as f:
                    shutil.copyfileobj(response, f)
            
            # Compute SHA256 of downloaded file
            downloaded_hash = compute_sha256(tmp_path)
            
            # Check for duplicate content
            if downloaded_hash in existing_hashes:
                existing_name = existing_hashes[downloaded_hash]
                tmp_path.unlink()
                result["skipped"] = True
                result["filename"] = existing_name
                return result
            
            # Determine final filename with conflict resolution
            final_filename = filename
            final_path = dest_dir / final_filename
            
            if final_path.exists():
                # Different content - rename deterministically
                base_name = Path(filename).stem
                extension = Path(filename).suffix
                counter = 1
                while final_path.exists():
                    final_filename = f"{base_name}_{counter}{extension}"
                    final_path = dest_dir / final_filename
                    counter += 1
                result["renamed"] = True
                result["filename"] = final_filename
            
            # Move temp file to final location
            shutil.move(str(tmp_path), str(final_path))
            
        except urllib.error.HTTPError as e:
            result["errors"].append(f"HTTP error {e.code}: {e.reason}")
            if tmp_path.exists():
                tmp_path.unlink()
        except urllib.error.URLError as e:
            result["errors"].append(f"Network error: {e}")
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception as e:
            result["errors"].append(f"Error downloading {filename}: {e}")
            if tmp_path.exists():
                tmp_path.unlink()
        
        return result
    
    @staticmethod
    @staticmethod
    def resolve_pseudo_provenance(
        pseudo_path: str,
        project_root: Optional[str] = None,
    ) -> dict:
        """
        Resolve pseudo provenance by matching against libinfo index.
        
        Args:
            pseudo_path: Path to pseudo file (absolute or relative to project_root)
            project_root: Optional project root (for resolving relative paths)
            
        Returns:
            Dict with provenance information (serialized PseudoProvenanceResult)
        """
        from quantumvitas.core.pseudo_provenance import resolve_pseudo_provenance
        from pathlib import Path
        
        pseudo_path_obj = Path(pseudo_path)
        if not pseudo_path_obj.is_absolute() and project_root:
            pseudo_path_obj = Path(project_root) / pseudo_path_obj
        
        result = resolve_pseudo_provenance(pseudo_path_obj)
        
        # Serialize to dict
        return to_jsonable({
            "path": result.path,
            "element": result.element,
            "basename": result.basename,
            "sha256": result.sha256,
            "sha_family": result.sha_family,
            "match_kind": result.match_kind,
            "matches": [
                {
                    "archive_name": m.archive_name,
                    "archive_sha256": m.archive_sha256,
                    "library_name": m.library_name,
                    "category": m.category,
                    "library_version": m.library_version,
                    "xc": m.xc,
                    "quality": m.quality,
                    "type": m.type,
                    "relativistic": m.relativistic,
                    "path_in_archive": m.path_in_archive,
                    "basename": m.basename,
                }
                for m in result.matches
            ],
            "warnings": result.warnings,
        })
    
    @staticmethod
    def get_pseudo_options_for_elements(
        project_root: Path,
        elements: List[str],
        config: Optional[dict] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get pseudo options for a list of elements (sha256-keyed, filename-first).
        
        Args:
            project_root: Project root path
            elements: List of element symbols
            config: Optional project config
            
        Returns:
            Dict mapping element -> List[PseudoVariant dict] (sha256-keyed)
        """
        from quantumvitas.core.pseudo_options import get_pseudo_options_for_elements as get_options
        
        return get_options(project_root, elements, config=config)
    
    def download_pseudo_from_url(
        project_root: Path,
        url: str,
        dest_dir: Optional[Path] = None,
        preferred_filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Download a pseudopotential from any URL.
        
        Args:
            project_root: Project root path
            url: Full URL to download from
            dest_dir: Optional destination directory (default: project_root/pseudo)
            preferred_filename: Optional preferred filename (extracted from URL if not provided)
            
        Returns:
            Dict with same structure as download_pseudo_by_filename
        """
        import urllib.request
        import urllib.error
        import hashlib
        import tempfile
        from quantumvitas.core.pseudo_config import get_ssl_context
        
        if dest_dir is None:
            dest_dir = project_root / "pseudo"
        dest_dir = Path(dest_dir).resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract filename from URL if not provided
        if preferred_filename is None:
            preferred_filename = url.split('/')[-1]
            # Clean up URL-encoded characters
            import urllib.parse
            preferred_filename = urllib.parse.unquote(preferred_filename)
        
        def compute_sha256(file_path: Path) -> str:
            """Compute SHA256 hash of a file."""
            sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()
        
        # Build SHA256 index of existing pseudos
        existing_hashes: Dict[str, str] = {}
        for existing_file in dest_dir.iterdir():
            if existing_file.is_file() and existing_file.suffix.lower() in ('.upf',):
                try:
                    existing_hashes[compute_sha256(existing_file)] = existing_file.name
                except Exception:
                    pass
        
        result = {
            "filename": preferred_filename,
            "renamed": False,
            "skipped": False,
            "errors": [],
        }
        
        try:
            # Download to temporary file first
            with tempfile.NamedTemporaryFile(delete=False, suffix='.upf') as tmp_file:
                tmp_path = Path(tmp_file.name)
            
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'QuantumVITAS/1.0')
            
            from quantumvitas.core.pseudo_config import get_ssl_context
            from quantumvitas.core.pseudo_config import get_ssl_context
            with urllib.request.urlopen(req, context=get_ssl_context(), timeout=30) as response:
                with open(tmp_path, 'wb') as f:
                    shutil.copyfileobj(response, f)
            
            # Compute SHA256 of downloaded file
            downloaded_hash = compute_sha256(tmp_path)
            
            # Check for duplicate content
            if downloaded_hash in existing_hashes:
                existing_name = existing_hashes[downloaded_hash]
                tmp_path.unlink()
                result["skipped"] = True
                result["filename"] = existing_name
                return result
            
            # Determine final filename with conflict resolution
            final_filename = preferred_filename
            final_path = dest_dir / final_filename
            
            if final_path.exists():
                # Different content - rename deterministically
                base_name = Path(preferred_filename).stem
                extension = Path(preferred_filename).suffix
                counter = 1
                while final_path.exists():
                    final_filename = f"{base_name}_{counter}{extension}"
                    final_path = dest_dir / final_filename
                    counter += 1
                result["renamed"] = True
                result["filename"] = final_filename
            
            # Move temp file to final location
            shutil.move(str(tmp_path), str(final_path))
            
        except urllib.error.HTTPError as e:
            result["errors"].append(f"HTTP error {e.code}: {e.reason}")
            if tmp_path.exists():
                tmp_path.unlink()
        except urllib.error.URLError as e:
            result["errors"].append(f"Network error: {e}")
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception as e:
            result["errors"].append(f"Error downloading from {url}: {e}")
            if tmp_path.exists():
                tmp_path.unlink()
        
        return result
    
    @staticmethod
    def import_step_from_qe_input(
        project_root: Path,
        calculation_ulid: str,
        input_file: Path,
        step_name: Optional[str] = None,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Import a QE input file as a step in a calculation (preserves original parameters).
        
        This uses apply_defaults=False to preserve the original QE input parameters
        without injecting QV defaults (outdir, restart_mode, conv_thr, etc.).
        
        Args:
            project_root: Project root path
            calculation_ulid: Calculation ULID (core service requires ULID only)
            input_file: Path to QE input file (.in)
            step_name: Optional name for the new step (defaults to input file stem)
            index: Optional ResourceIndex
            config: Optional project config
            
        Returns:
            Updated calculation info with the new step
        """
        from quantumvitas.core.resolution import validate_ulid
        
        # Validate ULID
        calculation_ulid = validate_ulid(calculation_ulid, kind="calculation")
        from quantumvitas.calculation.importers import build_step_spec_from_qe_input
        from quantumvitas.core.models import load_calculation, save_calculation, CalculationStepEntry
        import yaml
        
        project_root = Path(project_root).resolve()
        input_file = Path(input_file).resolve()
        
        if not input_file.exists():
            raise QVServiceError(f"QE input file not found: {input_file}")
        
        # Resolve calculation (use cached index if provided)
        from quantumvitas.core.resolution import resolve_calculation
        from quantumvitas.core.project_utils import load_project_config
        if config is None:
            config = load_project_config(project_root)
        calculation = resolve_calculation(project_root, calculation_ulid, config=config, index=index)
        calculation_dir = calculation.absolute_path
        steps_dir = calculation_dir / "steps"
        steps_dir.mkdir(exist_ok=True)
        
        # Load calculation model
        wf_model = load_calculation(calculation_dir, project_root)
        
        # Determine step name
        step_name = step_name or input_file.stem
        
        # Import step spec from QE input (apply_defaults=False for import mode)
        import_result = build_step_spec_from_qe_input(
            input_file=input_file,
            destination_dir=steps_dir,
            structure_dir=project_root / "structures",
            step_id=step_name,
            structure_id=None,  # Will be auto-generated from input
            reference_structure_by="id",  # Reference by structure ID in project
            apply_defaults=False,  # IMPORTANT: Preserve original parameters
        )
        
        # Load the created spec to get step type
        spec = import_result.spec
        
        # Import structure into project if not already present
        structure_id = import_result.structure_id
        structure_path = import_result.structure_path
        
        # Read structure to compute fingerprint
        from quantumvitas.io import read_structure
        structure = read_structure(structure_path)
        
        # Compute fingerprint for content-based deduplication
        from quantumvitas.core.structure_fingerprint import structure_fingerprint, structures_semantically_equal
        fingerprint = structure_fingerprint(structure)
        
        # Check existing structures for same fingerprint (content-based dedup)
        structures = config.get("structures", [])
        structures_dir = project_root / "structures"
        structure_id_value = None
        
        # First check by fingerprint (canonical key)
        if structures_dir.exists():
            for struct_file in structures_dir.glob("*.json"):
                try:
                    import json
                    struct_data = json.loads(struct_file.read_text())
                    struct_meta = struct_data.get("__qv_meta__") or struct_data.get("meta") or {}
                    existing_fingerprint = struct_meta.get("fingerprint")
                    if existing_fingerprint == fingerprint:
                        # Found matching structure by fingerprint
                        existing_id = struct_meta.get("id")
                        if existing_id:
                            # Verify with semantic equality as belt-and-suspenders
                            existing_structure = read_structure(struct_file)
                            if structures_semantically_equal(structure, existing_structure):
                                structure_id_value = existing_id
                                break
                except Exception:
                    pass  # Skip invalid files
        
        # Fallback: check by samefile(path) as optimization (legacy compatibility)
        if not structure_id_value:
            for struct_entry in structures:
                struct_file = project_root / struct_entry.get("file", "")
                if struct_file.exists() and struct_file.samefile(structure_path):
                    # Get structure ID (canonical reference) using centralized selector extraction
                    structure_id_value = extract_structure_selector_from_entry(struct_entry)
                    break
        
        if not structure_id_value:
            # Register structure in project
            from quantumvitas.core.resources import meta_from_name, ensure_relative_path, generate_unique_name_and_slug
            from quantumvitas.core.project_utils import collect_slugs
            from quantumvitas.io import write_structure
            
            # Get structure name from the original file (human-readable name based on QE input filename)
            structure_name = structure_path.stem  # e.g., "si_scf" from "si_scf.json"
            
            # Generate unique name and slug to avoid conflicts
            existing_slugs = collect_slugs(structures, project_root=project_root)
            final_name, final_slug = generate_unique_name_and_slug(
                kind="structure",
                preferred_name=structure_name,
                existing_slugs=existing_slugs,
            )
            
            # Move structure to project structures directory
            project_structures_dir = project_root / "structures"
            project_structures_dir.mkdir(exist_ok=True)
            final_structure_path = project_structures_dir / f"{final_slug}.json"
            
            if not final_structure_path.exists():
                meta = meta_from_name(
                    "structure",
                    name=final_name,  # Use human-readable name, not ULID
                    path=ensure_relative_path(final_structure_path, base=project_root),
                )
                # Store fingerprint in metadata
                meta_dict = meta.to_dict()
                meta_dict["fingerprint"] = fingerprint
                write_structure(structure, final_structure_path, metadata=meta_dict)
            else:
                # Read existing meta if file exists
                import json
                existing_data = json.loads(final_structure_path.read_text())
                existing_meta = existing_data.get("__qv_meta__") or existing_data.get("meta") or {}
                from quantumvitas.core.resources import ResourceMeta
                meta = ResourceMeta.from_dict(existing_meta, kind="structure", default_name=final_name, default_path=ensure_relative_path(final_structure_path, base=project_root))
                # Update fingerprint if not present
                if "fingerprint" not in existing_meta:
                    meta_dict = meta.to_dict()
                    meta_dict["fingerprint"] = fingerprint
                    write_structure(structure, final_structure_path, metadata=meta_dict)
            
            # Add to project config (ID-only model: only structure_id)
            entry = {
                "structure_id": meta.id,  # ID-only reference (ULID)
            }
            structures.append(entry)
            save_project_config(project_root, config)
            structure_id_value = meta.id  # Use the structure's ULID (canonical reference)
        
        # Update step spec to reference structure by ID via StepDoc (journaled)
        from quantumvitas.core.yamldoc import StepDoc
        from quantumvitas.workflow.step_factory import save_step_doc
        
        step_doc = StepDoc.load(import_result.spec_path)
        step_doc.set(["structure_id"], structure_id_value)
        save_step_doc(step_doc, import_result.spec_path)
        
        # Add step to calculation model using step_id (ULID) from step spec meta
        # step_file is NOT stored - step location resolved via registry using step_id
        wf_model.steps.append(CalculationStepEntry(
            step_id=spec.meta.id,  # Use ULID from step spec meta (canonical reference)
            type=spec.step_type,
            # step_file is NOT stored - step location resolved via registry using step_id
        ))
        save_calculation(wf_model, calculation_dir)
        
        # Update calculation structure if not set (use structure_id, canonical reference)
        if not wf_model.structure_id:
            wf_model.structure_id = structure_id_value
            # Also set structure_name for display
            if structure_id_value:
                # Resolve structure to get name (use provided index/config if available)
                try:
                    resolved = resolve_structure(project_root, structure_id_value, config=config, index=index)
                    wf_model.structure_name = resolved.meta.name
                except Exception:
                    pass  # If resolution fails, structure_name stays None
            save_calculation(wf_model, calculation_dir)
        
        # Update registry in-place (add step, do NOT rebuild)
        if index is not None:
            from quantumvitas.core.resolution import update_registry_add_step
            update_registry_add_step(index, spec.meta, import_result.spec_path)
            # Also add structure if it was newly imported
            if structure_id_value and not structure_id_value in [m.id for m in index.by_id.values() if m.kind == "structure"]:
                from quantumvitas.core.resolution import update_registry_add_structure
                # Get structure meta from the file
                try:
                    import json
                    struct_data = json.loads(final_structure_path.read_text())
                    struct_meta_dict = struct_data.get("__qv_meta__") or struct_data.get("meta") or {}
                    from quantumvitas.core.resources import ResourceMeta
                    struct_meta = ResourceMeta.from_dict(struct_meta_dict, kind="structure", default_name=structure_id, default_path=f"structures/{final_structure_path.name}")
                    update_registry_add_structure(index, struct_meta, final_structure_path)
                except Exception:
                    pass  # If we can't add structure to registry, continue (it will be picked up on next refresh)
        
        # Pass cached index to avoid rebuilding ResourceIndex
        return QVService.get_calculation_detail(
            project_root=project_root,
            calculation_ulid=calculation_ulid,
            index=index,
            config=config,
        )
    
    @staticmethod
    def reset_step_params(
        project_root: Path,
        calculation_selector: str,
        step_selector: str,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Reset step parameters to in-code defaults based on step type.
        
        Args:
            project_root: Project root path
            calculation_selector: Calculation selector
            step_selector: Step selector
            index: Optional ResourceIndex (avoids rebuilding if provided)
            config: Optional project config (avoids reloading if provided)
            
        Returns:
            Updated step detail dict
        """
        from quantumvitas.calculation.structure_steps import StructureStepSpec
        from quantumvitas.calculation.step_defaults import get_default_step_params
        import yaml
        
        step = resolve_step(project_root, calculation_selector, step_selector, config=config, index=index)
        # Load step spec (DAG + ULID model: structure_id is already in spec)
        from quantumvitas.core.resolution import make_structure_selector_resolver
        from quantumvitas.core.project_utils import load_project_config
        if config is None:
            config = load_project_config(project_root)
        resolver = make_structure_selector_resolver(project_root, config=config)
        spec = StructureStepSpec.from_yaml(step.absolute_path, resolve_structure_selector=resolver)
        
        # Get defaults for this step type
        defaults = get_default_step_params(spec.step_type)
        
        # Reset parameters and cards to defaults via StepDoc (journaled)
        from quantumvitas.core.yamldoc import StepDoc
        from quantumvitas.workflow.step_factory import save_step_doc
        
        step_doc = StepDoc.load(step.absolute_path)
        # Use apply_patch for dict subtree updates
        step_doc.apply_patch({
            "parameters": defaults.get("parameters", {}),
            "cards": defaults.get("cards", {}),
            "species_overrides": defaults.get("species_overrides", {}),
        })
        save_step_doc(step_doc, step.absolute_path)
        
        # Return the updated step detail (pass cached index/config to avoid rebuilding)
        return QVService.get_step_detail(
            project_root=project_root,
            calculation_ulid=calculation_ulid,
            step_selector=step_selector,
            index=index,
            config=config,
        )
    
    # -------------------------------------------------------------------------
    # Calculation Step Membership Helpers (Authoritative: calculation.yaml.steps[])
    # -------------------------------------------------------------------------
    
    @staticmethod
    def _update_calculation_steps(
        project_root: Path,
        calculation_ulid: str,
        steps_updater: callable,
        *,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> None:
        """
        Internal helper to update calculation.yaml.steps[] atomically.
        
        Per Constitution: calculation.yaml.steps[] is the single source of truth.
        All step membership changes must go through this helper.
        
        Args:
            project_root: Project root path
            calculation_ulid: Calculation ULID (not selector)
            steps_updater: Function that takes list[CalculationStepEntry] and returns updated list
            index: Optional ResourceIndex
            config: Optional project config
        """
        from quantumvitas.core.models import load_calculation, save_calculation
        from quantumvitas.core.project_utils import load_project_config
        from quantumvitas.core.resolution import resolve_calculation
        
        if config is None:
            config = load_project_config(project_root)
        
        # Resolve by ULID
        calculation = resolve_calculation(project_root, calculation_ulid, config=config, index=index)
        if calculation.meta.id != calculation_ulid:
            raise QVServiceError(f"Calculation ULID mismatch: expected {calculation_ulid}, got {calculation.meta.id}")
        
        calc_path = calculation.absolute_path / "calculation.yaml"
        wf_model = load_calculation(calc_path, project_root)
        
        # Update steps
        wf_model.steps = steps_updater(wf_model.steps)
        
        # Save via CalcDoc + yaml_io (journaled)
        save_calculation(wf_model, calc_path)
    
    @staticmethod
    def calc_add_step(
        project_root: Path,
        calculation_ulid: str,
        step_ulid: str,
        step_type: str,
        *,
        position: Optional[int] = None,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> None:
        """
        Add a step to calculation.yaml.steps[].
        
        Args:
            project_root: Project root path
            calculation_ulid: Calculation ULID
            step_ulid: Step ULID
            step_type: Step type (for display)
            position: Optional position to insert (default: append)
            index: Optional ResourceIndex
            config: Optional project config
        """
        from quantumvitas.core.models import CalculationStepEntry
        
        def updater(steps: List) -> List:
            # Verify step_ulid not already present
            if any(s.step_id == step_ulid for s in steps):
                raise QVServiceError(f"Step {step_ulid} already in calculation")
            
            new_entry = CalculationStepEntry(step_id=step_ulid, type=step_type)
            if position is None:
                return steps + [new_entry]
            else:
                result = list(steps)
                result.insert(position, new_entry)
                return result
        
        QVService._update_calculation_steps(
            project_root, calculation_ulid, updater, index=index, config=config
        )
    
    @staticmethod
    def calc_remove_step(
        project_root: Path,
        calculation_ulid: str,
        step_ulid: str,
        *,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> None:
        """
        Remove a step from calculation.yaml.steps[].
        
        Args:
            project_root: Project root path
            calculation_ulid: Calculation ULID
            step_ulid: Step ULID to remove
            index: Optional ResourceIndex
            config: Optional project config
        """
        def updater(steps: List) -> List:
            return [s for s in steps if s.step_id != step_ulid]
        
        QVService._update_calculation_steps(
            project_root, calculation_ulid, updater, index=index, config=config
        )
    
    @staticmethod
    def calc_set_steps(
        project_root: Path,
        calculation_ulid: str,
        ordered_step_ulids: List[str],
        *,
        step_types: Optional[Dict[str, str]] = None,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> None:
        """
        Set calculation.yaml.steps[] to an ordered list of step ULIDs.
        
        CRITICAL: This function preserves step type metadata in calculation.yaml.
        If step_types mapping is provided, it will be used. Otherwise, step types
        are resolved from step YAML files or preserved from existing entries.
        
        Args:
            project_root: Project root path
            calculation_ulid: Calculation ULID
            ordered_step_ulids: Ordered list of step ULIDs
            step_types: Optional mapping of step_ulid -> step_type (for new steps)
            index: Optional ResourceIndex
            config: Optional project config
        """
        from quantumvitas.core.models import load_calculation, CalculationStepEntry
        from quantumvitas.core.resolution import resolve_calculation, resolve_step
        from quantumvitas.core.yamldoc import StepDoc
        
        if config is None:
            from quantumvitas.core.project_utils import load_project_config
            config = load_project_config(project_root)
        
        # Resolve calculation to get current model
        calculation = resolve_calculation(project_root, calculation_ulid, config=config, index=index)
        calc_path = calculation.absolute_path / "calculation.yaml"
        wf_model = load_calculation(calc_path, project_root)
        
        # Build mapping of step_ulid -> step entry
        step_map = {s.step_id: s for s in wf_model.steps if s.step_id}
        
        # Build new steps list preserving type info
        new_steps = []
        for step_ulid in ordered_step_ulids:
            if step_ulid in step_map:
                # Preserve existing entry (includes type if present)
                new_steps.append(step_map[step_ulid])
            else:
                # Step not in current model - resolve step_type
                step_type = None
                
                # Try step_types mapping first (provided by caller)
                if step_types and step_ulid in step_types:
                    step_type = step_types[step_ulid]
                
                # If not provided, try to resolve from step YAML file
                if not step_type:
                    try:
                        # Resolve step to get file path
                        step_resolved = resolve_step(
                            project_root,
                            calculation_ulid,
                            step_ulid,
                            config=config,
                            index=index,
                        )
                        # Load step YAML to get step_type
                        step_doc = StepDoc.load(step_resolved.absolute_path)
                        step_type = step_doc.get(["step_type"], default=None)
                    except Exception:
                        # Step file missing or invalid - leave type as None
                        # This will be resolved later when step is loaded
                        pass
                
                # Create entry with step_type if available
                new_steps.append(CalculationStepEntry(step_id=step_ulid, type=step_type))
        
        wf_model.steps = new_steps
        # Save via CalcDoc + yaml_io (journaled)
        from quantumvitas.core.models import save_calculation
        save_calculation(wf_model, calc_path)
    
    # -------------------------------------------------------------------------
    # Calculation Configuration (Phase 4 - Reorder, Change Structure)
    # -------------------------------------------------------------------------
    
    @staticmethod
    def reorder_calculation_steps(
        project_root: Path,
        calculation_selector: str,
        new_order: List[str],
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Reorder calculation steps.
        
        Args:
            project_root: Project root path
            calculation_selector: Calculation selector
            new_order: List of step IDs/slugs in the new order
            
        Returns:
            Updated calculation info
        """
        from quantumvitas.core.models import load_calculation
        from quantumvitas.core.project_utils import load_project_config
        
        if config is None:
            config = load_project_config(project_root)
        calculation = resolve_calculation(project_root, calculation_selector, config=config, index=index)
        wf_path = calculation.absolute_path / "calculation.yaml"
        wf_model = load_calculation(wf_path)
        
        # Validate all step IDs exist
        existing_ids = {s.step_id for s in wf_model.steps}
        existing_slugs = {}
        for s in wf_model.steps:
            # Create a mapping from possible identifiers to step entries
            # Use step_id (ULID) as primary key
            if s.step_id:
                existing_slugs[s.step_id] = s
            # Also allow matching by type for convenience (if unique)
            if s.type:
                existing_slugs[s.type] = s
        
        # Resolve the new order
        reordered = []
        seen = set()
        for selector in new_order:
            if selector in existing_slugs:
                step = existing_slugs[selector]
                if step.step_id not in seen:
                    reordered.append(step)
                    seen.add(step.step_id)
            else:
                raise QVServiceError(f"Step '{selector}' not found in calculation")
        
        # Ensure all steps are accounted for
        if len(reordered) != len(wf_model.steps):
            missing = existing_ids - seen
            raise QVServiceError(f"New order missing steps: {missing}")
        
        # Update the model using helper
        ordered_step_ulids = [s.step_id for s in reordered if s.step_id]
        QVService.calc_set_steps(
            project_root=project_root,
            calculation_ulid=calculation.meta.id,
            ordered_step_ulids=ordered_step_ulids,
            index=index,
            config=config,
        )
        
        # Return updated calculation info (pass cached index to avoid rebuilding)
        return QVService.get_calculation_detail(
            project_root,
            calculation_selector,
            index=index,
            config=config,
        )
    
    @staticmethod
    def add_step_to_calculation(
        project_root: Path,
        calculation_selector: str,
        step_type: str,
        step_name: str = None,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Add a new step to a calculation.
        
        Args:
            project_root: Project root path
            calculation_selector: Calculation selector (name, slug, or id)
            step_type: Type of step (scf, nscf, relax, bands, dos, etc.)
            step_name: Name for the new step (defaults to step_type)
            
        Returns:
            Updated calculation info with the new step
        """
        from quantumvitas.core.models import CalculationModel, CalculationStepEntry
        from quantumvitas.calculation.structure_steps import StructureStepSpec
        import ulid as ulid_module
        from quantumvitas.core.models import load_calculation
        
        # Resolve calculation via registry (for consistent resolution)
        from quantumvitas.core.resolution import build_resource_index, require_calculation
        from quantumvitas.core.project_utils import load_project_config
        
        if config is None:
            config = load_project_config(project_root)
        if index is None:
            index = build_resource_index(project_root)
        calculation = require_calculation(project_root, calculation_selector, config=config, index=index)
        wf_path = calculation.absolute_path / "calculation.yaml"
        # Load calculation model; legacy 'structure' selectors (if present) are normalized to structure_id via the registry
        from quantumvitas.core.resolution import make_structure_selector_resolver
        resolver = make_structure_selector_resolver(project_root, config=config)
        wf_model = load_calculation(wf_path, project_root=project_root, resolve_structure_selector=resolver)
        
        # Determine step name
        if not step_name:
            step_name = step_type
        
        # Generate unique slug from name
        base_slug = slugify(step_name)
        
        # Check for duplicates and add suffix if needed
        existing_ids = {s.step_id for s in wf_model.steps if s.step_id}
        existing_types = {s.type for s in wf_model.steps if s.type}
        slug = base_slug
        counter = 1
        while slug in existing_types:
            counter += 1
            slug = f"{base_slug}-{counter}"
        
        # Generate new step ID (ULID) - slug is only for display/naming
        step_id = generate_resource_id()
        
        # Determine step file name
        step_file = f"steps/{slug}.step.yaml"
        
        # Get default parameters for this step type (from-scratch mode uses defaults)
        from quantumvitas.calculation.step_defaults import get_default_step_params
        from quantumvitas.core.models import ResourceMeta
        
        defaults = get_default_step_params(step_type)
        default_params = defaults.get("parameters", {})
        default_cards = defaults.get("cards", {})
        default_species = defaults.get("species_overrides", {})
        
        # Resolve structure from calculation to structure_id
        from quantumvitas.core.project_utils import load_project_config
        from quantumvitas.core.resolution import _is_path_like
        if config is None:
            config = load_project_config(project_root)
        
        structure_id = None
        structure_selector = None
        if wf_model.structure_id:
            structure_id = wf_model.structure_id
            # Get selector for backwards compat
            try:
                resolved = resolve_structure(project_root, wf_model.structure_id, config=config, index=index)
                structure_selector = resolved.meta.slug
            except Exception:
                # If resolution fails, use structure_name or fall back to structure
                structure_selector = wf_model.structure_name or wf_model.structure or ""
        elif wf_model.structure:
            # Legacy: try to resolve selector to structure_id
            # If it's a path and not registered, we can't get structure_id, so keep the path
            if _is_path_like(wf_model.structure):
                # It's a path - check if file exists
                structure_path = Path(wf_model.structure)
                if not structure_path.is_absolute():
                    structure_path = project_root / structure_path
                if structure_path.exists():
                    # Path exists - try to resolve it to get structure_id
                    # First check if it's registered in the project
                    try:
                        resolved = resolve_structure(project_root, wf_model.structure, config=config, index=index)
                        structure_id = resolved.meta.id
                        structure_selector = resolved.meta.slug
                    except Exception:
                        # Not registered - use path directly (backwards compat)
                        structure_selector = wf_model.structure
                else:
                    # Path doesn't exist, try as selector
                    try:
                        resolved = resolve_structure(project_root, wf_model.structure, config=config, index=index)
                        structure_id = resolved.meta.id
                        structure_selector = resolved.meta.slug
                    except Exception:
                        # Resolution failed, use original value
                        structure_selector = wf_model.structure
            else:
                # Try to resolve as selector
                try:
                    resolved = resolve_structure(project_root, wf_model.structure, config=config, index=index)
                    structure_id = resolved.meta.id
                    structure_selector = resolved.meta.slug
                except Exception:
                    # Resolution failed, use original value
                    structure_selector = wf_model.structure
        
        # Ensure we have structure_id (required for ID-only model)
        if not structure_id:
            # Try to resolve structure_selector to structure_id
            if structure_selector:
                try:
                    resolved = resolve_structure(project_root, structure_selector, config=config, index=index)
                    structure_id = resolved.meta.id
                except Exception:
                    pass
            
            # If still no structure_id, try wf_model.structure as last resort
            if not structure_id and wf_model.structure:
                try:
                    resolved = resolve_structure(project_root, wf_model.structure, config=config, index=index)
                    structure_id = resolved.meta.id
                except Exception:
                    pass
            
            # If we still don't have structure_id, we cannot create the step spec
            if not structure_id:
                raise ValueError(
                    f"Calculation '{calculation_selector}' has no structure or structure cannot be resolved. "
                    "Please set a structure for the calculation first and ensure it is registered in the project."
                )
        
        # Step initialization: inherit structure_id from calculation if step doesn't have one
        # calculation.structure_id is canonical and must never be cleared by adding steps
        if not structure_id and wf_model.structure_id:
            # Inherit from calculation (copy the canonical ID, not a move)
            structure_id = wf_model.structure_id
        
        # DAG + ID-only model: Step YAML contains ONLY step-local configuration.
        # NO structure_id (inherits from calculation.structure_id at execution time).
        # NO parent_calculation_id (parent is implicit from step file location).
        # Structure is resolved via calculation.structure_id when the step is executed.
        step_meta = ResourceMeta(
            id=str(ulid_module.new()),  # Actual ULID for the step spec
            name=step_name,
            slug=slug,
            path=f"calculations/{wf_model.meta.slug}/{step_file}",
            kind="step",
        )
        step_spec = StructureStepSpec(
            meta=step_meta,
            step_type=step_type,
            # Do NOT set structure_id (inherits from calculation at execution time)
            # Do NOT set parent_calculation_id (parent is implicit)
            structure="",  # Empty legacy field (not written to YAML)
            parameters=default_params,
            cards=default_cards,
            species_overrides=default_species,
        )
        
        # Write step file via StepFactory (journaled)
        # CRITICAL: Ensure calculation.absolute_path is the calculation directory, not calculation.yaml
        if calculation.absolute_path.name == "calculation.yaml":
            calculation_dir = calculation.absolute_path.parent
        else:
            calculation_dir = calculation.absolute_path
        
        steps_dir = calculation_dir / "steps"
        steps_dir.mkdir(parents=True, exist_ok=True)
        step_yaml_filename = f"{slug}.step.yaml"
        step_file_path = steps_dir / step_yaml_filename
        
        # Create StepDoc from spec and save via factory
        from quantumvitas.core.yamldoc import StepDoc
        from quantumvitas.workflow.step_factory import save_step_doc
        
        step_doc = StepDoc(step_spec.to_dict())
        save_step_doc(step_doc, step_file_path)
        
        # Verify the file was created (defensive check)
        if not step_file_path.exists():
            raise QVServiceError(
                f"Failed to create step file: {step_file_path}. "
                f"Directory exists: {steps_dir.exists()}, writable: {steps_dir.is_dir()}"
            )
        
        # Create step entry for calculation.yaml using step_id (ULID) from step spec meta
        # step_file is NOT stored - step location resolved via registry using step_id
        new_step = CalculationStepEntry(
            step_id=step_spec.meta.id,  # Use ULID from step spec meta (canonical reference)
            type=step_type,
            # step_file is NOT stored - step location resolved via registry using step_id
        )
        
        # Add step to calculation
        # CRITICAL: calculation.structure_id is canonical and must NEVER be cleared by adding steps
        # It remains set for the lifetime of the calculation
        from quantumvitas.core.models import save_calculation
        wf_model.steps.append(new_step)
        # Ensure calculation.structure_id is preserved (never cleared)
        assert wf_model.structure_id is not None, "Calculation structure_id must not be cleared when adding steps"
        save_calculation(wf_model, wf_path)
        
        # Update registry in-place (do NOT rebuild)
        if index is not None:
            from quantumvitas.core.resolution import update_registry_add_step
            update_registry_add_step(index, step_meta, step_file_path)
        
        # Return updated calculation info without materializing steps (avoids pseudo requirements)
        # This is sufficient for tests and most use cases
        return {
            "id": wf_model.meta.id,
            "name": wf_model.meta.name,
            "slug": wf_model.meta.slug,
            "structure_id": wf_model.structure_id,
            "steps": [
                {
                    "step_id": step.step_id,
                    "type": step.type,
                    "input": step.input,
                    "reference": step.reference,
                }
                for step in wf_model.steps
            ],
        }
    
    @staticmethod
    def change_calculation_structure(
        project_root: Path,
        calculation_ulid: str,
        new_structure_ulid: str,
        update_steps: bool = True,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Change the structure associated with a calculation.
        
        Args:
            project_root: Project root path
            calculation_ulid: Calculation ULID (core service requires ULID only)
            new_structure_ulid: New structure ULID (core service requires ULID only)
            update_steps: Whether to also update all steps' structure field
            index: Optional ResourceIndex (avoids rebuilding if provided)
            config: Optional project config (avoids reloading if provided)
            
        Returns:
            Updated calculation info with any warnings
        """
        import logging
        from quantumvitas.core.resolution import validate_ulid, resolve_calculation, resolve_structure
        
        logger = logging.getLogger(__name__)
        
        # Validate ULIDs
        calculation_ulid = validate_ulid(calculation_ulid, kind="calculation")
        structure_ulid = validate_ulid(new_structure_ulid, kind="structure")
        
        from quantumvitas.core.models import CalculationModel
        from quantumvitas.calculation.structure_steps import StructureStepSpec
        
        # Resolve structure by ULID
        resolved_structure = resolve_structure(project_root, structure_ulid, config=config, index=index)
        
        from quantumvitas.core.models import load_calculation, save_calculation
        from quantumvitas.core.resolution import make_structure_selector_resolver
        from quantumvitas.core.project_utils import load_project_config
        if config is None:
            config = load_project_config(project_root)
        calculation = resolve_calculation(project_root, calculation_ulid, config=config, index=index)
        wf_path = calculation.absolute_path / "calculation.yaml"
        # Load calculation model; legacy 'structure' selectors (if present) are normalized to structure_id via the registry
        config = load_project_config(project_root)
        resolver = make_structure_selector_resolver(project_root, config=config)
        wf_model = load_calculation(wf_path, project_root=project_root, resolve_structure_selector=resolver)
        
        old_structure = wf_model.structure_name or wf_model.structure
        # Update structure_id (canonical reference)
        wf_model.structure_id = resolved_structure.meta.id
        wf_model.structure_name = resolved_structure.meta.name
        # Keep structure for backwards compat (but it's not authoritative)
        wf_model.structure = resolved_structure.meta.slug
        save_calculation(wf_model, wf_path)
        
        warnings = []
        updated_steps = []
        
        if update_steps:
            # Update all step files
            steps_dir = calculation.absolute_path / "steps"
            if steps_dir.exists():
                # Create resolver for structure selector resolution (if needed)
                from quantumvitas.core.resolution import make_structure_selector_resolver
                from quantumvitas.core.project_utils import load_project_config
                if config is None:
                    config = load_project_config(project_root)
                resolver = make_structure_selector_resolver(project_root, config=config)
                
                for step_file in steps_dir.glob("*.step.yaml"):
                    try:
                        # Load step spec (DAG + ULID model: structure_id is already in spec)
                        spec = StructureStepSpec.from_yaml(step_file, resolve_structure_selector=resolver)
                        # Check if step needs structure update (compare structure_id, not structure selector)
                        from quantumvitas.core.yamldoc import StepDoc
                        from quantumvitas.workflow.step_factory import save_step_doc
                        
                        step_doc = StepDoc.load(step_file)
                        current_structure_id = step_doc.get(["structure_id"], default=None)
                        
                        if current_structure_id != resolved_structure.meta.id:
                            old_step_struct_id = current_structure_id
                            # Update step structure_id via StepDoc (journaled)
                            step_doc.set(["structure_id"], resolved_structure.meta.id)
                            # Do not write structure selector (DAG + ID-only model: only structure_id is written)
                            step_doc.set(["structure"], "")
                            save_step_doc(step_doc, step_file)
                            updated_steps.append({
                                "step_id": spec.meta.id,
                                "old_structure_id": old_step_struct_id,
                                "new_structure_id": resolved_structure.meta.id,
                            })
                    except Exception as e:
                        warnings.append(f"Failed to update step {step_file.name}: {e}")
        
        # Pass cached index and config to avoid rebuilding ResourceIndex
        result = QVService.get_calculation_detail(
            project_root,
            calculation_ulid,
            index=index,
            config=config,
        )
        result["old_structure"] = old_structure
        result["updated_steps"] = updated_steps
        result["warnings"] = warnings
        
        return result
    
    @staticmethod
    def get_calculation_pseudo_mapping(
        project_root: Path,
        calculation_ulid: str,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Get pseudopotential mapping for a calculation.
        
        CRITICAL: calculation_ulid MUST be a ULID (not slug/name).
        
        This is the calculation-level equivalent of get_pseudo_mapping (which is step-level).
        It returns the authoritative species_map from calculation.yaml, along with
        structure-derived element list and available pseudos.
        
        Args:
            project_root: Project root path
            calculation_ulid: Calculation ULID (required, not slug/name)
            index: Optional ResourceIndex
            config: Optional project config
            
        Returns:
            Dict with:
            - species: List of element symbols from structure
            - mapping: Dict[element, pseudopot] from species_map
            - species_map: Full species_map dict (with mass etc.)
            - available_pseudos: List of UPF files in project/pseudo
            - pseudo_dir: Path to pseudo directory
            - warnings: List of warnings
            - sssp_defaults: SSSP default mappings if available
            - sssp_installed: Which SSSP libraries are installed
        """
        import logging
        from quantumvitas.core.models import load_calculation
        from quantumvitas.core.resolution import make_structure_selector_resolver, resolve_structure, validate_ulid
        from quantumvitas.core.project_utils import load_project_config
        from quantumvitas.io import read_structure
        
        logger = logging.getLogger(__name__)
        
        # Validate calculation_ulid is actually a ULID
        try:
            calculation_ulid = validate_ulid(calculation_ulid, kind="calculation")
        except ValueError as e:
            logger.warning(
                f"[GET_CALCULATION_PSEUDO_MAPPING] WARNING: Non-ULID calculation identifier received: '{calculation_ulid}'. "
                f"Core endpoint requires ULID. Error: {e}"
            )
            raise
        
        project_root = Path(project_root).resolve()
        
        if config is None:
            config = load_project_config(project_root)
        
        calculation = resolve_calculation(project_root, calculation_ulid, config=config, index=index)
        wf_path = calculation.absolute_path / "calculation.yaml"
        
        resolver = make_structure_selector_resolver(project_root, config=config)
        wf_model = load_calculation(wf_path, project_root=project_root, resolve_structure_selector=resolver)
        
        # Get element list from structure
        species_list: List[str] = []
        if wf_model.structure_id:
            try:
                struct_resolved = resolve_structure(project_root, wf_model.structure_id, config=config, index=index)
                if struct_resolved.absolute_path.exists():
                    structure = read_structure(struct_resolved.absolute_path)
                    species_list = sorted(set(str(el) for el in structure.composition.elements))
            except Exception:
                pass
        
        # Build mapping dict (element -> pseudopot filename) from species_map
        mapping: Dict[str, str] = {}
        if wf_model.species_map:
            for element, settings in wf_model.species_map.items():
                pseudo = settings.get("pseudopot", "")
                if pseudo:
                    mapping[element] = pseudo
        
        # Get available pseudos in project
        pseudo_dir = project_root / "pseudo"
        available_pseudos: List[str] = []
        if pseudo_dir.exists():
            available_pseudos = sorted([
                f.name for f in pseudo_dir.iterdir() 
                if f.is_file() and f.suffix.lower() == ".upf"
            ])
        
        # Get INTERNAL (resources/pseudo) directory
        from quantumvitas.core.pseudo import get_system_pseudo_dir
        from quantumvitas.core.pseudo_config import _find_quantumvitas_root, get_sssp_library_path, load_pseudo_config, PseudoConfig
        internal_pseudo_dir = get_system_pseudo_dir()
        internal_pseudos: List[str] = []
        if internal_pseudo_dir and internal_pseudo_dir.exists():
            internal_pseudos = sorted([
                f.name for f in internal_pseudo_dir.iterdir()
                if f.is_file() and f.suffix.lower() == ".upf"
            ])
        
        # Check SSSP libraries
        sssp_defaults: Dict[str, Dict[str, str]] = {}
        sssp_installed = {"precision": False, "efficiency": False}
        sssp_precision_pseudos: List[str] = []
        sssp_efficiency_pseudos: List[str] = []
        
        try:
            pseudo_config = load_pseudo_config()
            store_dir = Path(pseudo_config.store_dir) if pseudo_config.store_dir else None
            
            if store_dir:
                # Check SSSP precision
                precision_lib_path = get_sssp_library_path(store_dir, "1.3.0", "precision") / "library"
                if precision_lib_path.exists():
                    sssp_installed["precision"] = True
                    sssp_precision_pseudos = sorted([
                        f.name for f in precision_lib_path.iterdir()
                        if f.is_file() and f.suffix.lower() == ".upf"
                    ])
                
                # Check SSSP efficiency
                efficiency_lib_path = get_sssp_library_path(store_dir, "1.3.0", "efficiency") / "library"
                if efficiency_lib_path.exists():
                    sssp_installed["efficiency"] = True
                    sssp_efficiency_pseudos = sorted([
                        f.name for f in efficiency_lib_path.iterdir()
                        if f.is_file() and f.suffix.lower() == ".upf"
                    ])
                
                # Build SSSP defaults from cutoffs.json if available
                for flavor in ["precision", "efficiency"]:
                    if sssp_installed[flavor]:
                        lib_path = get_sssp_library_path(store_dir, "1.3.0", flavor)
                        cutoffs_path = lib_path / "cutoffs.json"
                        if cutoffs_path.exists():
                            try:
                                import json
                                cutoffs_data = json.loads(cutoffs_path.read_text())
                                # SSSP cutoffs.json format: list of {element, filename, ...}
                                if isinstance(cutoffs_data, list):
                                    for entry in cutoffs_data:
                                        if isinstance(entry, dict) and "element" in entry and "filename" in entry:
                                            elem = str(entry["element"])
                                            filename = str(entry["filename"])
                                            if elem in species_list:
                                                if elem not in sssp_defaults:
                                                    sssp_defaults[elem] = {}
                                                sssp_defaults[elem][flavor] = filename
                            except Exception:
                                pass
        except Exception:
            pass
        
        # Build candidates_by_element: all available pseudos from all sources
        # Element matching: match files that start with element symbol (case-insensitive)
        # e.g., "Si" matches "Si.pbe-n-rrkjus_psl.1.0.0.UPF", "si.pbe...", etc.
        candidates_by_element: Dict[str, List[Dict[str, Any]]] = {}
        for element in species_list:
            candidates: List[Dict[str, Any]] = []
            element_upper = element.upper()
            element_lower = element.lower()
            
            # Helper to check if pseudo matches element
            def matches_element(pseudo_name: str) -> bool:
                # Check exact match (case-insensitive)
                if pseudo_name.upper().startswith(element_upper + '.') or \
                   pseudo_name.upper().startswith(element_upper + '_'):
                    return True
                # Check case variations
                if pseudo_name.startswith(element + '.') or \
                   pseudo_name.startswith(element + '_') or \
                   pseudo_name.startswith(element_upper + '.') or \
                   pseudo_name.startswith(element_upper + '_') or \
                   pseudo_name.startswith(element_lower + '.') or \
                   pseudo_name.startswith(element_lower + '_'):
                    return True
                return False
            
            # INTERNAL source
            if internal_pseudo_dir and internal_pseudo_dir.exists():
                for pseudo in internal_pseudos:
                    if matches_element(pseudo):
                        candidates.append({
                            "filename": pseudo,
                            "source": "internal",
                            "path": str(internal_pseudo_dir / pseudo),
                        })
            
            # SSSP Precision
            for pseudo in sssp_precision_pseudos:
                if matches_element(pseudo):
                    candidates.append({
                        "filename": pseudo,
                        "source": "sssp_precision",
                        "path": None,  # Path in store, not exposed
                    })
            
            # SSSP Efficiency
            for pseudo in sssp_efficiency_pseudos:
                if matches_element(pseudo):
                    candidates.append({
                        "filename": pseudo,
                        "source": "sssp_efficiency",
                        "path": None,
                    })
            
            # Project source
            for pseudo in available_pseudos:
                if matches_element(pseudo):
                    candidates.append({
                        "filename": pseudo,
                        "source": "project",
                        "path": str(pseudo_dir / pseudo),
                    })
            
            # Deduplicate by filename (keep first occurrence, prefer internal > sssp > project)
            seen = set()
            unique_candidates = []
            source_priority = {"internal": 0, "sssp_precision": 1, "sssp_efficiency": 2, "project": 3}
            for cand in sorted(candidates, key=lambda x: (x["filename"], source_priority.get(x["source"], 99))):
                if cand["filename"] not in seen:
                    seen.add(cand["filename"])
                    unique_candidates.append(cand)
            
            candidates_by_element[element] = sorted(unique_candidates, key=lambda x: (source_priority.get(x["source"], 99), x["filename"]))
        
        # Build resolved_by_element: check if current mapping is resolvable
        resolved_by_element: Dict[str, Dict[str, Any]] = {}
        for element in species_list:
            pseudo = mapping.get(element, "")
            if not pseudo:
                resolved_by_element[element] = {
                    "filename": "",
                    "source": None,
                    "resolved": False,
                }
            else:
                # Check if pseudo is resolvable from any source
                resolved = False
                source = None
                
                # Resolution order: INTERNAL > SSSP Precision > SSSP Efficiency > Project
                # Check INTERNAL first
                if internal_pseudo_dir and (internal_pseudo_dir / pseudo).exists():
                    resolved = True
                    source = "internal"
                # Check SSSP Precision
                elif store_dir and sssp_installed["precision"]:
                    precision_lib_path = get_sssp_library_path(store_dir, "1.3.0", "precision") / "library"
                    if (precision_lib_path / pseudo).exists():
                        resolved = True
                        source = "sssp_precision"
                # Check SSSP Efficiency
                elif store_dir and sssp_installed["efficiency"]:
                    efficiency_lib_path = get_sssp_library_path(store_dir, "1.3.0", "efficiency") / "library"
                    if (efficiency_lib_path / pseudo).exists():
                        resolved = True
                        source = "sssp_efficiency"
                # Check Project last
                elif pseudo in available_pseudos:
                    resolved = True
                    source = "project"
                
                resolved_by_element[element] = {
                    "filename": pseudo,
                    "source": source,
                    "resolved": resolved,
                    "in_project": pseudo in available_pseudos,
                }
        
        # Build warnings: only warn if truly unresolved
        warnings: List[str] = []
        for element in species_list:
            resolved_info = resolved_by_element[element]
            if not resolved_info["resolved"]:
                pseudo = resolved_info["filename"]
                if not pseudo:
                    warnings.append(f"No pseudopotential set for {element}")
                else:
                    warnings.append(f"Pseudopotential {pseudo} for {element} not found in any source")
        
        # Build installed_sources
        installed_sources = {
            "internal": internal_pseudo_dir is not None and internal_pseudo_dir.exists(),
            "sssp_precision": sssp_installed["precision"],
            "sssp_efficiency": sssp_installed["efficiency"],
        }
        
        return {
            "species": species_list,
            "mapping": mapping,
            "species_map": wf_model.species_map,
            "available_pseudos": available_pseudos,
            "pseudo_dir": str(pseudo_dir),
            "warnings": warnings,
            "sssp_defaults": sssp_defaults if sssp_defaults else None,
            "sssp_installed": sssp_installed,
            "installed_sources": installed_sources,
            "candidates_by_element": candidates_by_element,
            "resolved_by_element": resolved_by_element,
        }
    
    @staticmethod
    def update_calculation_species_map(
        project_root: Path,
        calculation_selector: str,
        species_map: Dict[str, Dict[str, Any]],
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Update the species_map (pseudopotential mapping) for a calculation.
        
        Args:
            project_root: Project root path
            calculation_selector: Calculation selector
            species_map: New species mapping (element -> {
                pseudopot: str (legacy filename, for backward compat),
                pseudo_sha256: str (primary identity, new),
                pseudo_sha_family: str (secondary, new),
                pseudo_basename: str (display + file naming, new),
                mass: float? (optional)
            })
            index: Optional ResourceIndex (avoids rebuilding if provided)
            config: Optional project config (avoids reloading if provided)
            
        Returns:
            Updated calculation info
            
        Note:
            - If pseudo_sha256 is provided, it is the primary identity (pinned selection)
            - Legacy filename-only entries (no sha256) are treated as "un-pinned"
            - All fields are stored for backward compatibility
        """
        from quantumvitas.core.models import load_calculation, save_calculation
        from quantumvitas.core.resolution import make_structure_selector_resolver
        from quantumvitas.core.project_utils import load_project_config
        
        project_root = Path(project_root).resolve()
        
        if config is None:
            config = load_project_config(project_root)
        
        calculation = resolve_calculation(project_root, calculation_selector, config=config, index=index)
        wf_path = calculation.absolute_path / "calculation.yaml"
        
        resolver = make_structure_selector_resolver(project_root, config=config)
        wf_model = load_calculation(wf_path, project_root=project_root, resolve_structure_selector=resolver)
        
        old_species_map = wf_model.species_map
        wf_model.species_map = species_map
        save_calculation(wf_model, wf_path)
        
        # Pass cached index and config to avoid rebuilding ResourceIndex
        result = QVService.get_calculation_detail(
            project_root,
            calculation_selector,
            index=index,
            config=config,
        )
        result["old_species_map"] = old_species_map
        
        return result
    
    @staticmethod
    def get_calculation_detail(
        project_root: Path,
        calculation_ulid: str,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Get detailed calculation information for GUI display.
        
        CRITICAL: calculation_ulid MUST be a ULID (not slug/name).
        CRITICAL: Uses calculation.yaml's steps array as the ONLY source of truth for:
        - Which steps belong to the calculation
        - The order of steps
        - The ULID (step_id) used as the canonical identifier
        
        ResourceIndex is used ONLY to map step_id → file path/metadata, NOT for ordering or selector guessing.
        
        Args:
            project_root: Project root path
            calculation_ulid: Calculation ULID (required, not slug/name)
            index: Optional ResourceIndex (avoids rebuilding if provided)
            config: Optional project config (avoids reloading if provided)
            
        Returns:
            Dict with calculation details including steps (in calculation.yaml order)
            
        Raises:
            ValueError: If calculation_ulid is not a valid ULID
        """
        import logging
        from quantumvitas.core.resolution import ResourceNotFoundError, resolve_calculation, validate_ulid
        from quantumvitas.core.models import load_calculation
        from quantumvitas.core.project_utils import load_project_config
        from quantumvitas.calculation.structure_steps import StructureStepSpec
        from quantumvitas.core.resolution import make_structure_selector_resolver
        
        logger = logging.getLogger(__name__)
        
        # Validate calculation_ulid is actually a ULID
        try:
            calculation_ulid = validate_ulid(calculation_ulid, kind="calculation")
        except ValueError as e:
            # Always log warnings (not gated by debug flag)
            logger.warning(
                f"[GET_CALCULATION_DETAIL] WARNING: Non-ULID calculation identifier received: '{calculation_ulid}'. "
                f"Core endpoint requires ULID. Error: {e}"
            )
            raise
        
        project_root = Path(project_root).resolve()
        
        # Resolve calculation by ULID (already validated)
        try:
            calculation_resolved = resolve_calculation(project_root, calculation_ulid, config=config, index=index)
        except Exception as e:
            raise ResourceNotFoundError(
                kind="calculation",
                selector=calculation_ulid,
                id=calculation_ulid,
                project_root=project_root,
            ) from e
        
        # Determine calculation directory
        # calculation_resolved.absolute_path may be the directory or calculation.yaml file
        if calculation_resolved.absolute_path.name == "calculation.yaml":
            calculation_dir = calculation_resolved.absolute_path.parent
            calculation_yaml_path = calculation_resolved.absolute_path
        else:
            calculation_dir = calculation_resolved.absolute_path
            calculation_yaml_path = calculation_dir / "calculation.yaml"
        
        # Load calculation model directly from YAML (this is the canonical source)
        if not calculation_yaml_path.exists():
            raise ResourceNotFoundError(
                kind="calculation",
                selector=calculation_selector,
                id=calculation_resolved.meta.id,
                project_root=project_root,
                message=f"Calculation YAML not found: {calculation_yaml_path}",
            )
        
        # Load config if not provided
        if config is None:
            config = load_project_config(project_root)
        
        # Create resolver for structure selectors (needed for load_calculation)
        resolver = make_structure_selector_resolver(project_root, config=config)
        
        # Load calculation model - this gives us the canonical steps list from calculation.yaml
        wf_model = load_calculation(calculation_yaml_path, project_root=project_root, resolve_structure_selector=resolver)
        
        # Extract structure info from model
        structure_name = None
        structure_id = wf_model.structure_id
        structure_elements: List[str] = []  # Element symbols from structure composition
        if structure_id and index:
            # Try to get structure name and elements from index
            try:
                from quantumvitas.core.resolution import resolve_structure
                from quantumvitas.io import read_structure
                struct_resolved = resolve_structure(project_root, structure_id, config=config, index=index)
                structure_name = struct_resolved.meta.name if struct_resolved.meta else None
                # Read structure to get element composition
                if struct_resolved.absolute_path.exists():
                    structure = read_structure(struct_resolved.absolute_path)
                    # Get unique element symbols from structure composition
                    structure_elements = sorted(set(str(el) for el in structure.composition.elements))
            except Exception:
                pass
        
        # CRITICAL: Build step summaries STRICTLY from wf_model.steps in order
        # This is the ONLY source of truth for step identity and order
        step_summaries = []
        for idx, entry in enumerate(wf_model.steps):
            step_id = entry.step_id  # ULID from calculation.yaml (canonical)
            
            # Use ResourceIndex ONLY to resolve path/meta, NOT for ordering or selector guessing
            step_resolved = None
            step_spec = None
            missing = False
            
            if index is not None:
                try:
                    # Resolve step using the ULID from calculation.yaml
                    from quantumvitas.core.resolution import resolve_step
                    step_resolved = resolve_step(
                        project_root,
                        calculation_ulid,  # calculation_selector parameter accepts ULID
                        step_id,  # step_selector parameter
                        config=config,
                        index=index,
                    )
                    
                    # Check if step file exists
                    if step_resolved.absolute_path.exists():
                        # Load spec to get step_type and metadata
                        step_spec = StructureStepSpec.from_yaml(
                            step_resolved.absolute_path,
                            resolve_structure_selector=resolver
                        )
                    else:
                        missing = True
                except Exception:
                    # Step cannot be resolved or file doesn't exist (ghost step)
                    missing = True
            
            # Build summary dict - id MUST be step_id from calculation.yaml
            if step_spec and step_resolved:
                meta = step_resolved.meta or (step_spec.meta if hasattr(step_spec, 'meta') else None)
                step_type = step_spec.step_type if hasattr(step_spec, 'step_type') else None
                step_file = str(step_resolved.absolute_path.relative_to(calculation_dir)) if step_resolved.absolute_path.is_relative_to(calculation_dir) else str(step_resolved.absolute_path)
                
                step_summaries.append({
                    "id": step_id,  # Canonical ULID from calculation.yaml
                    "slug": meta.slug if meta else None,
                    "name": meta.name if meta else None,
                    "type": str(step_type) if step_type else None,
                    "step_file": step_file,
                    "missing": False,
                })
            else:
                # Step entry exists in calculation.yaml but file is missing (ghost step)
                step_summaries.append({
                    "id": step_id,  # Still the same ULID from calculation.yaml
                    "slug": None,
                    "name": None,
                    "type": entry.type if hasattr(entry, 'type') else None,
                    "step_file": None,
                    "missing": True,
                })
        
        return {
            "id": calculation_resolved.meta.id,
            "name": calculation_resolved.meta.name,
            "slug": calculation_resolved.meta.slug,
            "path": calculation_resolved.meta.path,
            "absolute_path": str(calculation_dir),
            "structure": structure_name,
            "structure_id": structure_id,
            "structure_elements": structure_elements,  # Element symbols for pseudo mapping UI
            "mode": wf_model.mode,
            "n_steps": len(step_summaries),
            "steps": step_summaries,
            # Calculation-level pseudo mapping (authoritative source)
            "species_map": wf_model.species_map,
        }
    
    # -------------------------------------------------------------------------
    # Pre-flight Checks (Phase 4 - Validate before run)
    # -------------------------------------------------------------------------
    
    @staticmethod
    def preflight_check(
        project_root: Path,
        calculation_selector: Optional[str] = None,
        step_selector: Optional[str] = None,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Perform pre-flight checks before running a calculation or step.
        
        Args:
            project_root: Project root path
            calculation_selector: Optional calculation selector
            step_selector: Optional step selector (requires calculation_selector)
            
        Returns:
            Dict with check results: {
                "ok": bool,
                "checks": [{"name": str, "ok": bool, "message": str}],
                "errors": [str],
                "warnings": [str],
            }
        """
        import logging
        from quantumvitas.core.engines.qe_resolver import resolve_qe_bin_dir
        from quantumvitas.core.engines.qe_installation import QEInstallation
        from quantumvitas.core.settings import load_settings
        
        logger = logging.getLogger(__name__)
        
        checks = []
        errors = []
        warnings = []
        
        # Check 1: QE installation (use two-state resolver)
        logger.info("[PREFLIGHT] Starting QE check")
        try:
            # Ensure QE is initialized using two-state model
            settings = load_settings()
            qe_bin_dir = resolve_qe_bin_dir(settings)
            qe_home = qe_bin_dir.parent
            
            # Validate executables exist
            pw_x = qe_bin_dir / "pw.x"
            pw_exe = qe_bin_dir / "pw.x.exe"
            
            if pw_x.exists() or pw_exe.exists():
                executable_path = pw_x if pw_x.exists() else pw_exe
                logger.info(
                    f"[PREFLIGHT] qe_detected=true reason='Found pw.x at {executable_path}' "
                    f"qe_bin_dir={qe_bin_dir} mode={'external' if settings.qe.bin_dir else 'internal'}"
                )
                checks.append({"name": "QE Installation", "ok": True, "message": f"QE: pw.x found at {executable_path}"})
            else:
                logger.warning(
                    f"[PREFLIGHT] qe_detected=false reason='pw.x not found in {qe_bin_dir}' "
                    f"qe_bin_dir={qe_bin_dir}"
                )
                checks.append({"name": "QE Installation", "ok": False, "message": "pw.x not found"})
                errors.append("Quantum ESPRESSO pw.x executable not found")
        except RuntimeError as e:
            logger.warning(
                f"[PREFLIGHT] qe_detected=false reason='{str(e)}' qe_bin_dir=None"
            )
            checks.append({"name": "QE Installation", "ok": False, "message": str(e)})
            errors.append("Quantum ESPRESSO not detected. Use Settings to detect or configure QE.")
        except Exception as e:
            logger.error(
                f"[PREFLIGHT] qe_detected=error reason='{str(e)}' qe_bin_dir=None"
            )
            checks.append({"name": "QE Installation", "ok": False, "message": str(e)})
            errors.append(f"QE installation error: {e}")
        
        # Check 2: Project path
        project_path = Path(project_root)
        if project_path.exists():
            if project_path.is_dir():
                checks.append({"name": "Project Path", "ok": True, "message": f"Project exists: {project_path}"})
            else:
                checks.append({"name": "Project Path", "ok": False, "message": "Project path is not a directory"})
                errors.append("Project path is not a directory")
        else:
            checks.append({"name": "Project Path", "ok": False, "message": "Project path does not exist"})
            errors.append(f"Project path does not exist: {project_path}")
        
        # Check 3: Calculation exists
        calculation = None
        if calculation_selector:
            try:
                calculation = resolve_calculation(project_root, calculation_selector, config=config, index=index)
                checks.append({"name": "Calculation", "ok": True, "message": f"Calculation found: {calculation.meta.name}"})
            except Exception as e:
                checks.append({"name": "Calculation", "ok": False, "message": str(e)})
                errors.append(f"Calculation not found: {calculation_selector}")
        
        # Only continue with calculation-dependent checks if calculation was found
        if calculation:
            # Check 4: Structure exists
            try:
                from quantumvitas.core.models import load_calculation
                wf_path = calculation.absolute_path / "calculation.yaml"
                wf_model = load_calculation(wf_path)
                
                # DAG + ID-only model: check structure_id (ULID)
                structure_id = wf_model.structure_id
                
                if structure_id:
                    # Resolve structure by ID (ULID) via registry
                    try:
                        from quantumvitas.core.resolution import build_resource_index, require_structure
                        # Use provided index or build one if needed
                        if index is None:
                            index = build_resource_index(project_root)
                        structure = require_structure(project_root, structure_id, index=index, config=config)
                        checks.append({"name": "Structure", "ok": True, "message": f"Structure found: {structure.meta.name}"})
                    except Exception as e:
                        checks.append({"name": "Structure", "ok": False, "message": f"Structure with ID '{structure_id}' not found: {e}"})
                        errors.append(f"Calculation references missing structure (ID: {structure_id})")
                else:
                    # No structure_id - this is OK (calculation may not need a structure)
                    checks.append({"name": "Structure", "ok": True, "message": "No structure referenced"})
            except Exception as e:
                checks.append({"name": "Calculation Config", "ok": False, "message": f"Failed to parse calculation.yaml: {e}"})
                errors.append(f"Calculation configuration error: {e}")
            
            # Check 5: Pseudo directory
            pseudo_dir = project_path / "pseudo"
            if pseudo_dir.exists() and any(pseudo_dir.iterdir()):
                checks.append({"name": "Pseudopotentials", "ok": True, "message": "Pseudo directory has files"})
            else:
                checks.append({"name": "Pseudopotentials", "ok": False, "message": "No pseudopotentials found"})
                warnings.append("No pseudopotential files in pseudo/ directory - QE may fail")
            
            # Check 6: Working directory writable
            raw_dir = calculation.absolute_path / "raw"
            if not raw_dir.exists():
                try:
                    raw_dir.mkdir(parents=True)
                    checks.append({"name": "Working Directory", "ok": True, "message": "Working directory created"})
                except Exception as e:
                    checks.append({"name": "Working Directory", "ok": False, "message": f"Cannot create: {e}"})
                    errors.append(f"Cannot create working directory: {e}")
            else:
                checks.append({"name": "Working Directory", "ok": True, "message": "Working directory exists"})
        
        return {
            "ok": len(errors) == 0,
            "checks": checks,
            "errors": errors,
            "warnings": warnings,
        }
    
    # -------------------------------------------------------------------------
    # Demo Project (Phase 5 - Onboarding)
    # -------------------------------------------------------------------------
    
    @staticmethod
    def create_demo_project(
        target_dir: Path,
        name: str = "demo-si-project",
        demo_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a demo Si project with a ready-to-run calculation.
        
        Creates a project from a snapshot in resources/demo_projects/.
        Default demo is si_bands_demo (Silicon band structure calculation).
        
        Args:
            target_dir: Directory to create the project in
            name: Project name
            demo_id: Name of demo snapshot (without .yml extension). Defaults to "si_bands_demo".
            
        Returns:
            Dict with project info
            
        Raises:
            ValueError: If target_dir is inside an existing project
        """
        from quantumvitas.core.resources import get_resources_dir
        from quantumvitas.project.snapshot import (
            ProjectSnapshot,
            materialize_project_from_snapshot,
        )
        import yaml
        
        target_dir = Path(target_dir).resolve()
        
        # Check if target_dir is inside an existing project
        enclosing_project = detect_enclosing_project(target_dir)
        if enclosing_project:
            raise ValueError(
                f"The selected folder is inside an existing QuantumVITAS project at: {enclosing_project}. "
                "Please choose a parent workspace folder, not a project folder."
            )
        
        # Use default demo if not specified
        demo_name = demo_id or "si_bands_demo"
        
        # Locate demo snapshot
        resources_dir = get_resources_dir()
        demo_snapshot_path = resources_dir / "demo_projects" / f"{demo_name}.yml"
        
        if not demo_snapshot_path.exists():
            raise QVServiceError(
                f"Demo snapshot '{demo_name}' not found at {demo_snapshot_path}. "
                f"Available demos: {', '.join([f.stem for f in (resources_dir / 'demo_projects').glob('*.yml')]) or 'none'}"
            )
        
        # Load snapshot
        try:
            with open(demo_snapshot_path, "r") as f:
                snapshot_data = yaml.safe_load(f)
            
            if not snapshot_data:
                raise QVServiceError(f"Demo snapshot '{demo_name}' is empty or invalid")
            
            snapshot = ProjectSnapshot.from_dict(snapshot_data)
        except Exception as e:
            raise QVServiceError(
                f"Failed to load demo snapshot '{demo_name}': {e}"
            ) from e
        
        # Materialize project from snapshot
        try:
            project_root = materialize_project_from_snapshot(
                snapshot=snapshot,
                parent_dir=Path(target_dir),
                new_project_name=name,
            )
        except Exception as e:
            # If materialization fails, provide a clear error
            raise QVServiceError(
                f"Failed to create demo project from snapshot '{demo_name}': {e}"
            ) from e
        
        # Verify that the project was created correctly
        if not project_root.exists():
            raise QVServiceError(
                f"Demo project directory was not created: {project_root}"
            )
        
        project_config_path = project_root / "project.qv.yml"
        if not project_config_path.exists():
            raise QVServiceError(
                f"Demo project was created but project.qv.yml is missing: {project_config_path}"
            )
        
        # Verify at least one structure or calculation exists
        structures_dir = project_root / "structures"
        calculations_dir = project_root / "calculations"
        if not structures_dir.exists() and not calculations_dir.exists():
            raise QVServiceError(
                f"Demo project was created but no structures or calculations found in {project_root}"
            )
        
        # Store demo origin info in project settings
        # NOTE: Demo recognition relies on origin.kind and demo_id, NOT on preserving snapshot ULIDs.
        # Materialized projects have fresh ULIDs, but demo_id is a stable identifier from snapshot meta.
        from quantumvitas.core.project_utils import load_project_config, save_project_config
        config = load_project_config(project_root)
        if "project" not in config:
            config["project"] = {}
        if "settings" not in config["project"]:
            config["project"]["settings"] = {}
        config["project"]["settings"]["origin"] = {
            "kind": "demo",
            "demo_id": demo_name,  # Stable demo identifier (not a ULID)
        }
        # Also store reference_artifacts info if present in snapshot meta
        # NOTE: Reference analysis lookup uses origin.reference_artifacts or snapshot.meta.reference_artifacts,
        # NOT project ULIDs. This allows reference data to work even though materialized projects have fresh IDs.
        snapshot_meta = snapshot_data.get("meta", {})
        if snapshot_meta.get("reference_artifacts"):
            config["project"]["settings"]["origin"]["reference_artifacts"] = snapshot_meta["reference_artifacts"]
        save_project_config(project_root, config)
        
        # Get project summary
        project_summary = QVService.get_project_summary(project_root)
        
        # Extract structure and calculation info from snapshot
        structure_info = None
        calculation_info = None
        
        if snapshot.structures:
            struct_meta = snapshot.structures[0].get("meta", {})
            structure_info = {
                "id": struct_meta.get("id"),
                "name": struct_meta.get("name"),
            }
        
        if snapshot.calculations:
            wf_meta = snapshot.calculations[0].get("meta", {})
            calculation_info = {
                "id": wf_meta.get("id"),
                "name": wf_meta.get("name"),
            }
        
        return {
            "project_root": str(project_root),
            "project_id": project_summary.get("id"),
            "project_name": project_summary.get("name"),
            "structure": structure_info,
            "calculation": calculation_info,
            "ready_to_run": len(snapshot.calculations) > 0,
        }
    
    @staticmethod
    def list_demo_projects() -> List[Dict[str, Any]]:
        """
        List available demo project snapshots.
        
        Reads metadata from snapshot files (meta section) with fallback to defaults.
        
        Returns:
            List of demo project info dicts (JSON-serializable)
        """
        from quantumvitas.core.resources import get_resources_dir
        from quantumvitas.project.snapshot import ProjectSnapshot
        import yaml
        
        # Default metadata fallback (for backward compatibility)
        DEFAULT_METADATA = {
            "si_bands_demo": {
                "id": "si_bands_demo",
                "name": "Si Band Structure",
                "title": "Silicon band structure",
                "subtitle": "SCF → NSCF → Bands",
                "description": "Silicon band structure calculation with SCF, NSCF, and bands steps. Demonstrates k-path generation and band structure analysis.",
                "recommended_use": "Band structure analysis",
                "recommended_analysis": "bands",
                "tags": ["bands", "Si", "PW", "tutorial"],
                "difficulty": "beginner",
                "estimated_runtime_scf": None,
            },
            "si_dos_demo": {
                "id": "si_dos_demo",
                "name": "Si DOS",
                "title": "Silicon density of states",
                "subtitle": "SCF → NSCF → DOS",
                "description": "Silicon density of states calculation with SCF, NSCF, and DOS steps. Demonstrates DOS analysis calculation.",
                "recommended_use": "Density of states analysis",
                "recommended_analysis": "dos",
                "tags": ["dos", "Si", "PW", "tutorial"],
                "difficulty": "beginner",
                "estimated_runtime_scf": None,
            },
        }
        
        # Scan resources/demo_projects/*.yml
        resources_dir = get_resources_dir()
        demo_projects_dir = resources_dir / "demo_projects"
        
        if not demo_projects_dir.exists():
            return []
        
        demos = []
        for snapshot_file in demo_projects_dir.glob("*.yml"):
            demo_id = snapshot_file.stem
            
            # Start with defaults
            demo_info = DEFAULT_METADATA.get(demo_id, {
                "id": demo_id,
                "name": demo_id.replace("_", " ").title(),
                "title": demo_id.replace("_", " ").title(),
                "subtitle": "",
                "description": f"Demo project: {demo_id}",
                "recommended_use": "General",
                "recommended_analysis": None,
                "tags": [],
                "difficulty": "beginner",
                "estimated_runtime_scf": None,
            }).copy()
            
            # Try to read metadata from snapshot file
            try:
                snapshot_data = yaml.safe_load(snapshot_file.read_text())
                snapshot_meta = snapshot_data.get("meta", {})
                
                # Merge snapshot metadata (overrides defaults)
                if snapshot_meta:
                    demo_info.update({
                        "title": snapshot_meta.get("title", demo_info.get("title", demo_info["name"])),
                        "subtitle": snapshot_meta.get("subtitle", demo_info.get("subtitle", "")),
                        "tags": snapshot_meta.get("tags", demo_info.get("tags", [])),
                        "recommended_analysis": snapshot_meta.get("recommended_analysis", demo_info.get("recommended_analysis")),
                        "difficulty": snapshot_meta.get("difficulty", demo_info.get("difficulty", "beginner")),
                    })
                    # Keep description from defaults if not in snapshot
                    if "description" in snapshot_meta:
                        demo_info["description"] = snapshot_meta["description"]
            except Exception:
                # If reading fails, use defaults
                pass
            
            demos.append(demo_info)
        
        return sorted(demos, key=lambda d: d["id"])
    
    @staticmethod
    def import_structure_from_template(
        project_root: Path,
        template_name: str,
        name: Optional[str] = None,
    ) -> ResolvedResource:
        """
        Import a structure from the structure library.
        
        Reads from resources/structure_library/ (public API).
        Reads from resources/structure_library/ only.
        
        Args:
            project_root: Project root path
            template_name: Structure name (e.g., "si", "graphene")
            name: Optional custom name for the structure
            
        Returns:
            ResolvedResource for the imported structure
        """
        from quantumvitas.core.templates import get_structure_library_path
        
        template_path = get_structure_library_path(template_name)
        if not template_path or not template_path.exists():
            raise QVServiceError(f"Structure '{template_name}' not found in structure library")
        
        return QVService.import_structure(
            project_root=project_root,
            source=template_path,
            name=name or template_name,
        )


    @staticmethod
    def get_relax_final_structure_preview(
        project_root: Path,
        calculation_selector: str,
        step_selector: str,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Preview the final structure from a relax/vc-relax step output (NO SIDE EFFECTS).
        
        Parses the QE output file to extract the final coordinates block and returns
        a preview payload suitable for display. Does NOT create any Structure resource.
        
        Args:
            project_root: Project root path
            calculation_selector: Calculation selector
            step_selector: Step selector (ULID)
            index: Optional ResourceIndex
            config: Optional project config
            
        Returns:
            Dict with cell (angstrom), species, positions (angstrom), volume, etc.
            
        Raises:
            QVServiceError: If step not found, not completed, or parsing fails
        """
        from quantumvitas.calculation.geometry import (
            read_final_geometry_from_output_text,
            structure_from_qe_geometry_snapshot,
        )
        from quantumvitas.calculation.naming import CalculationFileNaming, find_calculation_raw_dir
        from quantumvitas.core.models import load_calculation
        from quantumvitas.core.project_utils import load_project_config
        from quantumvitas.core.resolution import resolve_calculation, resolve_step
        
        project_root = Path(project_root).resolve()
        
        # Resolve calculation and step
        calculation_resolved = resolve_calculation(project_root, calculation_selector, config=config, index=index)
        calculation_dir = calculation_resolved.absolute_path.parent if calculation_resolved.absolute_path.name == "calculation.yaml" else calculation_resolved.absolute_path
        
        if config is None:
            config = load_project_config(project_root)
        
        # Load calculation to get working_dir
        wf_model = load_calculation(calculation_dir / "calculation.yaml", project_root=project_root)
        working_dir_name = wf_model.working_dir
        raw_dir = find_calculation_raw_dir(calculation_dir, working_dir_name)
        
        # Resolve step to get step_type
        step_resolved = resolve_step(project_root, calculation_selector, step_selector, config=config, index=index)
        
        # Load step spec to get step_type
        from quantumvitas.calculation.structure_steps import StructureStepSpec
        spec = StructureStepSpec.from_yaml(step_resolved.absolute_path, resolve_structure_selector=None)
        step_type = spec.step_type
        
        # Validate step type
        from quantumvitas.calculation.types import StepType
        if step_type not in (StepType.RELAX.value, StepType.VC_RELAX.value):
            raise QVServiceError(
                f"Step '{step_selector}' is not a relax/vc-relax step (type: {step_type})"
            )
        
        # Find output file
        output_filename = CalculationFileNaming.output_filename(step_type, working_dir=raw_dir)
        output_file = raw_dir / output_filename
        
        if not output_file.exists():
            raise QVServiceError(
                f"Output file not found for step '{step_selector}': {output_file}. "
                f"Step may not have completed successfully."
            )
        
        # Parse final geometry
        try:
            output_text = output_file.read_text()
            snapshot, species = read_final_geometry_from_output_text(output_text)
        except Exception as e:
            raise QVServiceError(
                f"Failed to parse final coordinates from output: {e}"
            ) from e
        
        # Convert to structure for preview (this applies canonization)
        structure = structure_from_qe_geometry_snapshot(snapshot, species)
        
        # Build preview payload (frontend expects angstrom for positions)
        cell_ang = structure.lattice.matrix.tolist()
        positions_ang = structure.cart_coords.tolist()
        volume = structure.volume
        
        return {
            "cell": cell_ang,  # 3x3 matrix in Angstrom
            "species": species,
            "positions": positions_ang,  # Nx3 in Angstrom (Cartesian)
            "volume": volume,  # Angstrom^3
            "n_atoms": len(species),
        }
    
    @staticmethod
    def save_relax_final_structure(
        project_root: Path,
        calculation_selector: str,
        step_selector: str,
        parent_structure_ulid: str,
        slug_hint: Optional[str] = None,
        index: Optional["ResourceIndex"] = None,
        config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Save the final structure from a relax/vc-relax step as a new Structure resource.
        
        IDEMPOTENT: For a given (calculation_ulid, step_ulid), at most ONE structure
        may ever be created. Repeated calls return the existing structure ULID.
        
        Args:
            project_root: Project root path
            calculation_selector: Calculation selector
            step_selector: Step selector (ULID)
            parent_structure_ulid: ULID of the input structure (for provenance)
            slug_hint: Optional hint for structure slug/name
            index: Optional ResourceIndex
            config: Optional project config
            
        Returns:
            Dict with structure_ulid and already_exists flag
        """
        from quantumvitas.calculation.geometry import (
            read_final_geometry_from_output_text,
            structure_from_qe_geometry_snapshot,
        )
        from quantumvitas.calculation.naming import CalculationFileNaming, find_calculation_raw_dir
        from quantumvitas.calculation.structure_steps import StructureStepSpec
        from quantumvitas.core.models import load_calculation
        from quantumvitas.core.project_utils import load_project_config, save_project_config
        from quantumvitas.core.resolution import resolve_calculation, resolve_step
        from quantumvitas.core.resources import (
            ensure_relative_path,
            generate_unique_name_and_slug,
            meta_from_name,
        )
        from quantumvitas.io.structure_io import write_structure
        import yaml
        
        project_root = Path(project_root).resolve()
        
        # Resolve calculation and step
        calculation_resolved = resolve_calculation(project_root, calculation_selector, config=config, index=index)
        calculation_dir = calculation_resolved.absolute_path.parent if calculation_resolved.absolute_path.name == "calculation.yaml" else calculation_resolved.absolute_path
        calculation_ulid = calculation_resolved.meta.id
        
        if config is None:
            config = load_project_config(project_root)
        
        # Load calculation to get working_dir
        wf_model = load_calculation(calculation_dir / "calculation.yaml", project_root=project_root)
        working_dir_name = wf_model.working_dir
        raw_dir = find_calculation_raw_dir(calculation_dir, working_dir_name)
        
        # Resolve step
        step_resolved = resolve_step(project_root, calculation_selector, step_selector, config=config, index=index)
        step_ulid = step_resolved.meta.id
        
        # Load step spec
        spec = StructureStepSpec.from_yaml(step_resolved.absolute_path, resolve_structure_selector=None)
        step_type = spec.step_type
        
        # Validate step type
        from quantumvitas.calculation.types import StepType
        if step_type not in (StepType.RELAX.value, StepType.VC_RELAX.value):
            raise QVServiceError(
                f"Step '{step_selector}' is not a relax/vc-relax step (type: {step_type})"
            )
        
        # Check if structure already created (idempotency check)
        # Read step YAML to check for produced_structure_ulid
        step_yaml_data = yaml.safe_load(step_resolved.absolute_path.read_text()) or {}
        existing_structure_ulid = step_yaml_data.get("produced_structure_ulid")
        
        if existing_structure_ulid:
            # Already exists - return it
            return {
                "structure_ulid": existing_structure_ulid,
                "already_exists": True,
            }
        
        # Optional: Check if structure already exists with same (source_run_ulid, source_step_ulid)
        # This is extra safety but may be expensive - skip for MVP
        
        # Find output file
        # Try base name first, then check numbered versions if base doesn't exist
        base_output = raw_dir / CalculationFileNaming.output_filename(step_type, working_dir=None)
        if base_output.exists():
            output_file = base_output
        else:
            # Try numbered versions (output_filename with working_dir will check for existing files)
            output_filename = CalculationFileNaming.output_filename(step_type, working_dir=raw_dir)
            output_file = raw_dir / output_filename
        
        if not output_file.exists():
            raise QVServiceError(
                f"Output file not found for step '{step_selector}': {output_file}. "
                f"Step may not have completed successfully."
            )
        
        # Parse final geometry
        try:
            output_text = output_file.read_text()
            snapshot, species = read_final_geometry_from_output_text(output_text)
        except Exception as e:
            raise QVServiceError(
                f"Failed to parse final coordinates from output: {e}"
            ) from e
        
        # Convert to structure (applies canonization)
        structure = structure_from_qe_geometry_snapshot(snapshot, species)
        
        # Generate structure name/slug
        from quantumvitas.core.project_utils import collect_slugs
        structures = config.setdefault("structures", [])
        existing_slugs = collect_slugs(structures, project_root=project_root)
        
        if slug_hint:
            preferred_name = slug_hint
        else:
            # Generate from step name + " relaxed"
            step_name = spec.meta.name or step_type
            preferred_name = f"{step_name} relaxed"
        
        final_name, final_slug = generate_unique_name_and_slug(
            kind="structure",
            preferred_name=preferred_name,
            existing_slugs=existing_slugs,
        )
        
        # Write structure file
        dest_path = project_root / "structures" / f"{final_slug}.json"
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        meta = meta_from_name(
            "structure",
            name=final_name,
            path=ensure_relative_path(dest_path, base=project_root),
        )
        
        # Write structure with provenance in __qv_meta__
        write_structure(structure, dest_path, metadata=meta)
        
        # Add provenance to structure JSON (store ONLY ULIDs)
        import json
        structure_data = json.loads(dest_path.read_text())
        if "extra" not in structure_data:
            structure_data["extra"] = {}
        structure_data["extra"]["relax_provenance"] = {
            "parent_structure_ulid": parent_structure_ulid,
            "source_calculation_ulid": calculation_ulid,
            "source_step_ulid": step_ulid,
        }
        dest_path.write_text(json.dumps(structure_data, indent=2))
        
        # Add to project config
        entry = {
            "structure_id": meta.id,  # ID-only reference (ULID)
        }
        structures.append(entry)
        save_project_config(project_root, config)
        
        # Update step YAML with produced_structure_ulid via StepDoc (journaled)
        from quantumvitas.core.yamldoc import StepDoc
        from quantumvitas.workflow.step_factory import save_step_doc
        
        step_doc = StepDoc.load(step_resolved.absolute_path)
        step_doc.set(["produced_structure_ulid"], meta.id)
        save_step_doc(step_doc, step_resolved.absolute_path)
        
        # Update registry in-place if index is provided
        if index is not None:
            from quantumvitas.core.resolution import update_registry_add_structure
            update_registry_add_structure(index, meta, dest_path)
        
        return {
            "structure_ulid": meta.id,
            "already_exists": False,
        }


# Export the service as a singleton-like module-level instance
service = QVService()

