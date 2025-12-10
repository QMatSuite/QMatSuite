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

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple, TYPE_CHECKING

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
    resolve_workflow,
    resolve_step,
    require_structure,
    require_workflow,
    require_step,
    list_structures,
    list_workflows,
    list_steps,
)
from quantumvitas.core.context import detect_enclosing_project
from quantumvitas.core.project_utils import (
    ProjectConfigError,
    ResourceNotFoundError as ProjectResourceNotFoundError,  # Legacy error from project_utils
    load_project_config,
    save_project_config,
    collect_slugs,
    ensure_structure_entry_defaults,
    ensure_workflow_entry_defaults,
    find_structure_entry,
    find_workflow_entry,
    workflow_directory,
    move_to_trash,
    apply_structure_rename,
    apply_workflow_rename,
    delete_workflow_entry,
    workflows_using_structure,
    workflows_depending_on,
)

if TYPE_CHECKING:
    from quantumvitas.workflow.structure_steps import StructureStepSpec


class QVServiceError(Exception):
    """Base exception for QVService operations."""
    pass


class QVService:
    """
    Service layer for QuantumVITAS operations.
    
    Provides clean methods for managing projects, workflows, steps, and structures.
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
            "workflows": [],
        }
        
        save_project_config(target_dir, config)
        
        # Create standard directories
        (target_dir / "structures").mkdir(exist_ok=True)
        (target_dir / "workflows").mkdir(exist_ok=True)
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
    ) -> ResolvedResource:
        """
        Import a structure file into the project.
        
        Args:
            project_root: Project root path
            source: Path to source file (CIF, QE input, JSON, etc.)
            name: Name for the structure (defaults to filename stem)
            format: File format hint
            
        Returns:
            ResolvedResource for the imported structure
        """
        from quantumvitas.io import read_structure, write_structure
        
        source = Path(source).resolve()
        if not source.exists():
            raise QVServiceError(f"Source file not found: {source}")
        
        config = load_project_config(project_root)
        structures = config.setdefault("structures", [])
        existing_slugs = collect_slugs(structures)
        
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
        
        # Write to structures directory
        dest_path = project_root / "structures" / f"{final_slug}.json"
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        meta = meta_from_name(
            "structure",
            name=final_name,
            path=ensure_relative_path(dest_path, base=project_root),
        )
        write_structure(structure, dest_path, metadata=meta)
        
        # Add to config (DAG + ID-only: only structure_id, no meta duplication)
        entry = {
            "structure_id": meta.id,  # ID-only reference (ULID)
        }
        structures.append(entry)
        save_project_config(project_root, config)
        
        return require_structure(project_root, final_slug, config)
    
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
    ) -> None:
        """Delete a structure (move to trash)."""
        from quantumvitas.core.resolution import require_structure, build_resource_index
        
        config = load_project_config(project_root)
        registry = build_resource_index(project_root)
        
        # Resolve structure to get its ID (canonical)
        resolved = require_structure(project_root, selector, config=config, index=registry)
        structure_id = resolved.meta.id
        
        # Get entry for workflow dependency checking
        entry = find_structure_entry(config, selector, project_root)
        
        # Check for workflows using this structure
        if not force:
            using_workflows = workflows_using_structure(project_root, config, entry)
            if using_workflows:
                names = ", ".join(w.get("name", "?") for w in using_workflows)
                raise QVServiceError(
                    f"Structure is used by workflows: {names}. Use force to delete anyway."
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
            if (e.get("structure_id") or e.get("id") or (e.get("meta") or {}).get("id")) != structure_id
        ]
        save_project_config(project_root, config)
    
    @staticmethod
    def list_structures(project_root: Path) -> List[ResolvedResource]:
        """List all structures in a project."""
        return list_structures(project_root)
    
    @staticmethod
    def get_structure(project_root: Path, selector: str) -> ResolvedResource:
        """Get a structure by selector."""
        return require_structure(project_root, selector)
    
    # -------------------------------------------------------------------------
    # Workflow operations
    # -------------------------------------------------------------------------
    
    @staticmethod
    def init_workflow(
        project_root: Path,
        name: str,
        structure_selector: Optional[str] = None,
        template: Optional[str] = None,
    ) -> ResolvedResource:
        """
        Create a new workflow.
        
        Args:
            project_root: Project root path
            name: Workflow name
            structure_selector: Optional structure selector for workflow
            template: Optional template name
            
        Returns:
            ResolvedResource for the new workflow
        """
        config = load_project_config(project_root)
        workflows = config.setdefault("workflows", [])
        existing_slugs = collect_slugs(workflows)
        
        final_name, final_slug = generate_unique_name_and_slug(
            kind="workflow",
            preferred_name=name,
            existing_slugs=existing_slugs,
        )
        
        workflow_id = generate_resource_id()
        workflow_path = f"workflows/{final_slug}"
        workflow_dir = project_root / workflow_path
        
        if template:
            from quantumvitas.core.templates import copy_workflow_template
            workflow_dir, _, new_ulid = copy_workflow_template(
                template,
                workflow_dir,
                project_root,
                new_name=final_name,
                structure=structure_selector,
                workflow_ulid=workflow_id,
            )
            workflow_id = new_ulid
        else:
            from quantumvitas.core.models import WorkflowModel, save_workflow
            
            workflow_dir.mkdir(parents=True, exist_ok=True)
            (workflow_dir / "steps").mkdir(exist_ok=True)
            (workflow_dir / "raw").mkdir(exist_ok=True)
            (workflow_dir / "reference").mkdir(exist_ok=True)
            
            # Resolve structure selector to structure_id
            structure_id = None
            structure_name = None
            if structure_selector:
                resolved_structure = require_structure(project_root, structure_selector, config)
                structure_id = resolved_structure.meta.id
                structure_name = resolved_structure.meta.name
            
            # Create workflow using model
            workflow_meta = ResourceMeta(
                id=workflow_id,
                name=final_name,
                slug=final_slug,
                path=workflow_path,
                kind="workflow",
            )
            workflow_model = WorkflowModel(
                meta=workflow_meta,
                structure_id=structure_id,
                structure_name=structure_name,
                structure=structure_selector,  # Keep for backwards compat
            )
            save_workflow(workflow_model, workflow_dir)
        
        # Add to project config (DAG + ID-only: only workflow_id, no meta duplication)
        entry = {
            "workflow_id": workflow_id,  # ID-only reference (ULID)
        }
        workflows.append(entry)
        save_project_config(project_root, config)
        
        return require_workflow(project_root, final_slug, config)
    
    @staticmethod
    def configure_workflow(
        project_root: Path,
        selector: str,
        new_name: Optional[str] = None,
        new_structure: Optional[str] = None,
        new_step_order: Optional[List[str]] = None,
    ) -> None:
        """
        Configure a workflow.
        
        Args:
            project_root: Project root path
            selector: Workflow selector
            new_name: Optional new name
            new_structure: Optional new structure selector
            new_step_order: Optional new step order (list of step ids)
        """
        config = load_project_config(project_root)
        entry = find_workflow_entry(config, selector, project_root)
        
        if new_name:
            apply_workflow_rename(
                project_root=project_root,
                config=config,
                entry=entry,
                new_name=new_name,
                new_slug=None,
                new_path=None,
            )
        
        # Update workflow.yaml if needed
        workflow_dir = workflow_directory(project_root, entry)
        workflow_yaml_path = workflow_dir / "workflow.yaml"
        
        if workflow_yaml_path.exists() and (new_structure or new_step_order):
            from quantumvitas.core.models import load_workflow, save_workflow, WorkflowStepEntry
            
            model = load_workflow(workflow_dir, project_root)
            
            if new_structure:
                model.structure = new_structure
            
            if new_step_order:
                step_map = {s.id: s for s in model.steps}
                new_steps = []
                for step_id in new_step_order:
                    if step_id in step_map:
                        new_steps.append(step_map[step_id])
                model.steps = new_steps
            
            save_workflow(model, workflow_dir)
        
        save_project_config(project_root, config)
    
    @staticmethod
    def delete_workflow(
        project_root: Path,
        selector: str,
        force: bool = False,
        cascade: bool = False,
    ) -> None:
        """Delete a workflow (move to trash)."""
        config = load_project_config(project_root)
        entry = find_workflow_entry(config, selector, project_root)
        trash = project_root / "trash"
        
        delete_workflow_entry(
            project_root=project_root,
            config=config,
            entry=entry,
            trash_dir=trash,
            force=force,
            cascade=cascade,
        )
        
        save_project_config(project_root, config)
    
    @staticmethod
    def list_workflows(project_root: Path) -> List[ResolvedResource]:
        """List all workflows in a project."""
        return list_workflows(project_root)
    
    @staticmethod
    def get_workflow(project_root: Path, selector: str) -> ResolvedResource:
        """Get a workflow by selector."""
        return resolve_workflow(project_root, selector)
    
    # -------------------------------------------------------------------------
    # Step operations
    # -------------------------------------------------------------------------
    
    @staticmethod
    def init_step(
        project_root: Path,
        workflow_selector: str,
        step_type: str,
        name: Optional[str] = None,
        structure_selector: Optional[str] = None,
    ) -> ResolvedResource:
        """
        Create a new step in a workflow.
        
        Args:
            project_root: Project root path
            workflow_selector: Parent workflow selector
            step_type: Step type (scf, nscf, dos, bands, etc.)
            name: Optional step name (defaults to step_type)
            structure_selector: Optional structure (defaults to workflow's structure)
            
        Returns:
            ResolvedResource for the new step
        """
        from quantumvitas.workflow.structure_steps import StructureStepSpec
        from quantumvitas.workflow.step_defaults import get_default_step_params
        from quantumvitas.core.models import WorkflowModel
        import yaml
        
        workflow = resolve_workflow(project_root, workflow_selector)
        workflow_dir = workflow.absolute_path
        steps_dir = workflow_dir / "steps"
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
        
        # Determine structure from workflow if not specified
        from quantumvitas.core.models import load_workflow, save_workflow, WorkflowStepEntry
        
        workflow_yaml_path = workflow_dir / "workflow.yaml"
        if workflow_yaml_path.exists():
            wf_model = load_workflow(workflow_dir, project_root)
            if structure_selector is None:
                # Use structure_id if available, else fall back to legacy structure selector
                if wf_model.structure_id:
                    # Resolve structure_id to get selector for step
                    resolved = require_structure(project_root, wf_model.structure_id)
                    structure_selector = resolved.meta.slug
                else:
                    structure_selector = wf_model.structure
        else:
            # Create workflow model if it doesn't exist
            wf_model = WorkflowModel(
                meta=workflow.meta,
                structure=structure_selector,
            )
        
        # Get default parameters for this step type
        defaults = get_default_step_params(step_type)
        
        # Create step spec with defaults
        # Calculate relative path from project root
        step_yaml_path = step_yaml_path.resolve()
        project_root_resolved = project_root.resolve()
        rel_path = step_yaml_path.relative_to(project_root_resolved)
        # Resolve structure selector to structure_id
        structure_id = None
        if structure_selector:
            from quantumvitas.core.project_utils import load_project_config
            config = load_project_config(project_root)
            resolved_structure = require_structure(project_root, structure_selector, config)
            structure_id = resolved_structure.meta.id
        
        # DAG + ID-only model: Step YAML contains ONLY step-local configuration.
        # NO structure_id (inherits from workflow.structure_id at execution time).
        # NO parent_workflow_id (parent is implicit from step file location).
        spec = StructureStepSpec(
            meta=ResourceMeta(
                id=step_id,
                name=step_name,
                slug=step_slug,
                path=str(rel_path.as_posix()),
                kind="step",
            ),
            step_type=step_type,
            # Do NOT set structure_id (inherits from workflow)
            # Do NOT set parent_workflow_id (parent is implicit)
            structure="",  # Empty legacy field (not written to YAML)
            parameters=defaults.get("parameters", {}),
            cards=defaults.get("cards", {}),
            species_overrides=defaults.get("species_overrides", {}),
        )
        step_yaml_path.write_text(yaml.safe_dump(spec.to_dict(), sort_keys=False))
        
        # Add step to workflow model using step_id (ULID) from step spec meta
        wf_model.steps.append(WorkflowStepEntry(
            step_id=spec.meta.id,  # Use ULID from step spec meta (canonical reference)
            type=step_type,
            # step_file is NOT stored - step location resolved via registry using step_id
        ))
        save_workflow(wf_model, workflow_dir)
        
        return require_step(project_root, workflow_selector, step_slug)
    
    @staticmethod
    def configure_step(
        project_root: Path,
        workflow_selector: str,
        step_selector: str,
        **kwargs: Any,
    ) -> None:
        """Configure a step's parameters."""
        step = require_step(project_root, workflow_selector, step_selector)
        step_path = step.absolute_path
        
        data = yaml.safe_load(step_path.read_text()) or {}
        
        # Apply updates
        for key, value in kwargs.items():
            if value is not None:
                if key in ("parameters", "cards"):
                    data.setdefault(key, {}).update(value)
                else:
                    data[key] = value
        
        step_path.write_text(yaml.safe_dump(data, sort_keys=False))
    
    @staticmethod
    def delete_step(
        project_root: Path,
        workflow_selector: str,
        step_selector: str,
    ) -> None:
        """Delete a step (move to trash)."""
        workflow = require_workflow(project_root, workflow_selector)
        step = require_step(project_root, workflow_selector, step_selector)
        
        # Move file to trash
        trash = project_root / "trash"
        move_to_trash(step.absolute_path, trash)
        
        # Remove from workflow.yaml
        workflow_yaml_path = workflow.absolute_path / "workflow.yaml"
        if workflow_yaml_path.exists():
            wf_data = yaml.safe_load(workflow_yaml_path.read_text()) or {}
            steps = wf_data.get("steps", [])
            wf_data["steps"] = [
                s for s in steps 
                if s.get("id", "").lower() != step.meta.name.lower()
            ]
            workflow_yaml_path.write_text(yaml.safe_dump(wf_data, sort_keys=False))
    
    @staticmethod
    def list_steps(project_root: Path, workflow_selector: str) -> List[ResolvedResource]:
        """List all steps in a workflow."""
        return list_steps(project_root, workflow_selector)
    
    @staticmethod
    def get_step(
        project_root: Path,
        workflow_selector: str,
        step_selector: str,
    ) -> ResolvedResource:
        """Get a step by selector."""
        return require_step(project_root, workflow_selector, step_selector)
    
    # -------------------------------------------------------------------------
    # Run operations
    # -------------------------------------------------------------------------
    
    @staticmethod
    def run_workflow(
        project_root: Path,
        workflow_selector: str,
        strict: bool = False,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """
        Run all steps in a workflow.
        
        This method clears any existing analysis artifacts before running
        to ensure fresh analysis on completion.
        
        Args:
            project_root: Project root path
            workflow_selector: Workflow selector
            strict: If True, fail on first error
            verbose: If True, print detailed output
            
        Returns:
            Dict with run results
        """
        from quantumvitas.project.model import Project
        from quantumvitas.workflow.workflow import Workflow
        from quantumvitas.workflow.runner import WorkflowRunner
        from quantumvitas.engine.registry import create_default_registry
        from quantumvitas.analysis.artifacts import clear_analysis_artifacts
        
        # Use registry-based resolution
        from quantumvitas.core.resolution import build_resource_index
        from quantumvitas.core.project_utils import load_project_config
        
        config = load_project_config(project_root)
        registry = build_resource_index(project_root)
        
        # Resolve workflow via registry
        workflow_resolved = require_workflow(project_root, workflow_selector, config=config, index=registry)
        
        # Load workflow to check structure_id (canonical source in DAG model)
        project = Project.open(project_root)
        workflow = Workflow.from_yaml(workflow_resolved.absolute_path, project)
        
        if not workflow.structure_id:
            raise QVServiceError(
                f"Workflow '{workflow_selector}' has no structure. Please set a structure for the workflow first."
            )
        
        # Clear analysis artifacts before running (cache invalidation)
        # This ensures fresh analysis is generated after the run completes
        workflow_dir = workflow.dir
        if workflow_dir and workflow_dir.exists():
            clear_analysis_artifacts(workflow_dir)
        
        # WorkflowRunner expects an EngineRegistry with engines registered
        registry = create_default_registry()
        runner = WorkflowRunner(registry)
        
        results = runner.run(workflow)
        
        # Convert WorkflowResult to dict for JSON serialization
        return {
            "workflow": workflow_selector,
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
        }
    
    @staticmethod
    def run_step(
        project_root: Path,
        workflow_selector: str,
        step_selector: str,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """
        Run a single step in project mode.
        
        This method uses registry-based resolution and respects the DAG + ID-only model:
        - Structure comes from workflow.structure_id (canonical)
        - Step is resolved via registry using step_id
        - No bare step file execution in project mode
        
        Args:
            project_root: Project root path
            workflow_selector: Workflow selector (name, slug, path, or ULID)
            step_selector: Step selector (name, slug, ULID, or step_type)
            verbose: If True, print detailed output
            
        Returns:
            Dict with run results
        """
        from quantumvitas.project.model import Project
        from quantumvitas.workflow.workflow import Workflow
        from quantumvitas.workflow.input_runner import run_input_step
        from quantumvitas.core.engines.base import EngineConfig
        from quantumvitas.core.engines.qe import QuantumEspressoEngine
        from quantumvitas.io import read_structure
        
        project_root = Path(project_root).resolve()
        
        # Use registry-based resolution
        from quantumvitas.core.resolution import build_resource_index, require_workflow, require_step
        from quantumvitas.core.project_utils import load_project_config
        
        config = load_project_config(project_root)
        registry = build_resource_index(project_root)
        
        # Resolve workflow and step via registry
        workflow_resolved = require_workflow(project_root, workflow_selector, config=config, index=registry)
        step_resolved = require_step(project_root, workflow_selector, step_selector, config=config)
        
        # Load workflow to get structure_id (canonical source)
        project = Project.open(project_root)
        workflow = Workflow.from_yaml(workflow_resolved.absolute_path, project)
        
        # Structure comes from workflow.structure_id (DAG model)
        if not workflow.structure_id:
            raise QVServiceError(
                f"Workflow '{workflow_selector}' has no structure. Please set a structure for the workflow first."
            )
        
        structure_resolved = require_structure(project_root, workflow.structure_id, config=config, index=registry)
        structure = read_structure(structure_resolved.absolute_path)
        
        # Load step spec (for step_type and other step-local config)
        from quantumvitas.workflow.structure_steps import StructureStepSpec
        from quantumvitas.core.resolution import make_structure_selector_resolver
        resolver = make_structure_selector_resolver(project_root, config=config)
        spec = StructureStepSpec.from_yaml(step_resolved.absolute_path, resolve_structure_selector=resolver)
        
        # Generate QE input from structure + step spec
        from quantumvitas.workflow.structure_steps import generate_qe_input_from_spec
        from quantumvitas.io.generator import QEInputGenerator
        
        qe_input, _ = generate_qe_input_from_spec(structure, spec)
        
        # Write input file to workflow's raw directory
        workdir = workflow_resolved.absolute_path / "raw"
        workdir.mkdir(parents=True, exist_ok=True)
        
        # Use consistent naming: structure_slug.step_type.in
        from quantumvitas.workflow.naming import WorkflowFileNaming
        input_name = spec.input_name or WorkflowFileNaming.input_filename(
            step_resolved.meta.id,
            spec.step_type,
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
        
        return {
            "step": step_selector,
            "step_id": step_resolved.meta.id,
            "step_type": result.step_type.value if hasattr(result.step_type, 'value') else str(result.step_type),
            "output_file": str(result.output_file) if result.output_file else None,
            "success": result.error is None,
            "error": result.error,
            "input_file": str(input_path),
            "working_dir": str(workdir),
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
            # Try to detect workflow context from file location
            output_dir = QVService._detect_workflow_results_dir(project_root, scf_file)
        
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
            output_dir = QVService._detect_workflow_results_dir(project_root, dos_file)
        
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
        workflow_selector: Optional[str] = None,
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
            bands_file: Path to bands.dat.gnu file (auto-detected if workflow provided)
            workflow_selector: Workflow selector to auto-locate files
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
        from quantumvitas.workflow.naming import find_band_analysis_files, find_workflow_raw_dir, find_workflow_results_dir
        
        workflow_dir: Optional[Path] = None
        
        # Resolve workflow if selector provided
        if workflow_selector and project_root:
            try:
                workflow = resolve_workflow(project_root, workflow_selector)
                workflow_dir = workflow.absolute_path
            except (SelectorNotFoundError, AmbiguousSelectorError) as e:
                raise QVServiceError(f"Workflow not found: {workflow_selector}") from e
        
        # Auto-locate files from workflow if available
        search_dir: Optional[Path] = None
        if workflow_dir:
            search_dir = find_workflow_raw_dir(workflow_dir)
            if output_dir is None:
                output_dir = find_workflow_results_dir(workflow_dir)
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
                "No bands.dat.gnu file found. Provide bands_file argument or use workflow_selector."
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
            output_dir = QVService._detect_workflow_results_dir(project_root, bands_file)
        
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
    def _detect_workflow_results_dir(project_root: Path, file_path: Path) -> Optional[Path]:
        """
        Detect the workflow results directory from a file's location.
        
        Args:
            project_root: Project root path
            file_path: Path to a file within the workflow
            
        Returns:
            Path to results directory, or None if not in a workflow
        """
        try:
            file_path = file_path.resolve()
            config = load_project_config(project_root)
            
            for wf_entry in config.get("workflows", []):
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
            Dict with project name, id, structure count, workflow count, etc.
        """
        project_root = Path(project_root).resolve()
        config = load_project_config(project_root)
        
        project_info = config.get("project", {})
        meta = project_info.get("meta", {})
        structures = config.get("structures", [])
        workflows = config.get("workflows", [])
        
        # Use registry to resolve structure/workflow names (ID-only model)
        # Structures and workflows in config only have IDs, need to resolve via registry
        from quantumvitas.core.resolution import list_structures, list_workflows
        
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
        
        workflow_names = []
        try:
            resolved_workflows = list_workflows(project_root)
            workflow_names = [res.meta.name for res in resolved_workflows]
        except Exception:
            # Fallback: try to get names from workflow entries if they have meta
            workflow_names = [
                w.get("meta", {}).get("name") or w.get("name", "?")
                for w in workflows
            ]
        
        return {
            "id": meta.get("id"),
            "name": project_info.get("name") or meta.get("name") or project_root.name,
            "slug": meta.get("slug"),
            "path": str(project_root),
            "n_structures": len(structures),
            "n_workflows": len(workflows),
            "structure_names": structure_names,
            "workflow_names": workflow_names,
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
    def list_workflows_data(project_root: Path) -> List[Dict[str, Any]]:
        """
        List all workflows as JSON-serializable dicts.
        
        Uses Project.open() and Workflow.from_yaml() to ensure legacy workflows
        are automatically migrated to the ID-only model.
        
        Args:
            project_root: Project root path
            
        Returns:
            List of dicts, each with workflow metadata and step info
        """
        project_root = Path(project_root).resolve()
        
        # Use Project.open() to get workflow references
        from quantumvitas.project.model import Project
        try:
            project = Project.open(project_root)
        except Exception as e:
            # If project can't be opened, fall back to basic listing
            resolved_list = list_workflows(project_root)
            return [
                {
                    "id": res.meta.id,
                    "name": res.meta.name,
                    "slug": res.meta.slug,
                    "path": res.meta.path,
                    "absolute_path": str(res.absolute_path),
                }
                for res in resolved_list
            ]
        
        result = []
        for workflow_ref in project.workflows.values():
            entry = {
                "id": workflow_ref.meta.id,
                "name": workflow_ref.meta.name,
                "slug": workflow_ref.meta.slug,
                "path": workflow_ref.meta.path,
                "absolute_path": str(workflow_ref.absolute_path),
            }
            
            # Try to load workflow with migration support
            # This uses Workflow.from_yaml() which handles legacy step entries
            try:
                from quantumvitas.workflow.workflow import Workflow
                if workflow_ref.absolute_path.exists():
                    workflow = Workflow.from_yaml(workflow_ref.absolute_path, project)
                    
                    # Extract structure info
                    if workflow.structure:
                        entry["structure"] = workflow.structure.meta.name if hasattr(workflow.structure, 'meta') else str(workflow.structure)
                        entry["structure_id"] = workflow.structure.meta.id if hasattr(workflow.structure, 'meta') else None
                    else:
                        entry["structure"] = None
                        entry["structure_id"] = None
                    
                    entry["mode"] = workflow.mode.value if hasattr(workflow.mode, 'value') else str(workflow.mode)
                    entry["n_steps"] = len(workflow.steps)
                    
                    # Extract step info from actual Step objects (which have ULID meta.id)
                    entry["steps"] = [
                        {
                            "step_id": step.meta.id,  # ULID (canonical reference)
                            "id": step.meta.id,  # Use ULID for both fields
                            "type": step.step_type.value if hasattr(step.step_type, 'value') else str(step.step_type),
                            # step_file is NOT included - step location resolved via registry
                        }
                        for step in workflow.steps
                    ]
            except Exception as e:
                # If workflow loading fails, still return basic metadata
                # but log the error for debugging
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to load workflow details for {workflow_ref.meta.name}: {e}")
                # Workflow details are optional, continue with basic entry
            
            result.append(entry)
        
        return result
    
    @staticmethod
    def get_structure_vis_data(
        project_root: Path,
        selector: str,
        supercell: Tuple[int, int, int] = (1, 1, 1),
        repeat_boundary: bool = False,
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
            supercell: Tuple of (a, b, c) supercell scaling factors
            repeat_boundary: If True, include periodic images at boundaries
            
        Returns:
            Dict with all visualization data (JSON-serializable)
        """
        from quantumvitas.io import read_structure
        from quantumvitas.analysis.structure_viz import (
            detect_bonds,
            generate_boundary_atoms,
            get_element_color,
            get_element_radius,
            ELEMENT_COLORS,
        )
        
        project_root = Path(project_root).resolve()
        
        # Resolve structure
        resolved = resolve_structure(project_root, selector)
        if not resolved.absolute_path.exists():
            raise QVServiceError(f"Structure file not found: {resolved.absolute_path}")
        
        # Load structure
        structure = read_structure(resolved.absolute_path)
        
        # Apply supercell if needed
        if supercell != (1, 1, 1):
            structure = structure.copy()
            structure.make_supercell(supercell)
        
        # Get lattice info
        lattice = structure.lattice
        lattice_matrix = lattice.matrix.tolist()
        
        # Collect atoms
        atoms = []
        for i, site in enumerate(structure):
            symbol = site.specie.symbol
            atoms.append({
                "index": i,
                "element": symbol,
                "cart_coords": [float(c) for c in site.coords],
                "frac_coords": [float(f) for f in site.frac_coords],
                "color": get_element_color(symbol),
                "radius": get_element_radius(symbol),
            })
        
        # Generate boundary atoms if requested
        boundary_atoms = []
        if repeat_boundary:
            try:
                boundary_atom_list = generate_boundary_atoms(structure)
                for boundary_atom in boundary_atom_list:
                    frac = lattice.get_fractional_coords(boundary_atom.coords)
                    boundary_atoms.append({
                        "element": boundary_atom.symbol,
                        "cart_coords": [float(c) for c in boundary_atom.coords],
                        "frac_coords": [float(f) for f in frac],
                        "color": get_element_color(boundary_atom.symbol),
                        "radius": get_element_radius(boundary_atom.symbol),
                        "is_boundary": True,
                    })
            except Exception:
                pass  # Boundary atoms are optional
        
        # Detect bonds
        bonds = []
        try:
            detected_bonds = detect_bonds(
                structure,
                tolerance=0.3,
                include_periodic_images=repeat_boundary,
            )
            for bond in detected_bonds:
                bonds.append({
                    "idx1": int(bond.idx1),
                    "idx2": int(bond.idx2),
                    "coord1": [float(c) for c in bond.coord1],
                    "coord2": [float(c) for c in bond.coord2],
                    "distance": float(bond.distance),
                })
        except Exception:
            pass  # Bonds are optional
        
        return {
            "structure_id": resolved.meta.id,
            "structure_name": resolved.meta.name,
            "formula": structure.composition.reduced_formula,
            "n_atoms": len(structure),
            "n_boundary_atoms": len(boundary_atoms),
            "n_bonds": len(bonds),
            "supercell": list(supercell),
            "lattice": {
                "matrix": lattice_matrix,
                "a": float(lattice.a),
                "b": float(lattice.b),
                "c": float(lattice.c),
                "alpha": float(lattice.alpha),
                "beta": float(lattice.beta),
                "gamma": float(lattice.gamma),
                "volume": float(lattice.volume),
            },
            "atoms": atoms,
            "boundary_atoms": boundary_atoms,
            "bonds": bonds,
            "element_colors": ELEMENT_COLORS,
        }
    
    @staticmethod
    def ensure_workflow_analysis(
        project_root: Path,
        workflow_selector: str,
        analysis_type: str,
        step_selector: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Ensure analysis artifacts exist for a workflow.
        
        If JSON artifact exists and force=False, returns cached status.
        Otherwise, parses QE outputs and writes JSON artifact.
        
        The artifact is written to: <workflow>/analysis/<type>.json
        
        Args:
            project_root: Project root path
            workflow_selector: Workflow selector
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
        from quantumvitas.workflow.naming import find_workflow_raw_dir
        
        project_root = Path(project_root).resolve()
        workflow = require_workflow(project_root, workflow_selector)
        workflow_dir = workflow.absolute_path
        raw_dir = find_workflow_raw_dir(workflow_dir)
        
        if not raw_dir.exists():
            return {
                "ok": False,
                "analysis_type": analysis_type,
                "artifact_path": None,
                "parsed_fresh": False,
                "error": f"Workflow raw directory not found: {raw_dir}. The workflow may not have been run yet.",
                "summary": None,
            }
        
        # Delegate to the artifacts module
        status = ensure_analysis_artifact(
            analysis_type=analysis_type,
            workflow_dir=workflow_dir,
            raw_dir=raw_dir,
            step_selector=step_selector,
            force=force,
        )
        
        return status.to_dict()
    
    @staticmethod
    def get_scf_convergence_data(
        project_root: Path,
        workflow_selector: str,
        step_selector: str,
    ) -> Dict[str, Any]:
        """
        Get SCF convergence data for a specific step in a workflow.
        
        First attempts to load from JSON artifact (<workflow>/analysis/scf.json).
        If artifact doesn't exist, parses QE output directly and writes artifact.
        
        Args:
            project_root: Project root path
            workflow_selector: Workflow selector
            step_selector: Step selector
            
        Returns:
            Dict with SCF convergence data (iterations, energies, etc.)
        """
        from quantumvitas.analysis.artifacts import read_artifact, ensure_analysis_artifact, AnalysisType
        from quantumvitas.analysis.parsers import parse_scf_output
        from quantumvitas.workflow.naming import find_workflow_raw_dir
        
        project_root = Path(project_root).resolve()
        workflow = require_workflow(project_root, workflow_selector)
        workflow_dir = workflow.absolute_path
        raw_dir = find_workflow_raw_dir(workflow_dir)
        
        if not raw_dir.exists():
            raise QVServiceError(
                f"Workflow raw directory not found: {raw_dir}\n"
                f"The workflow may not have been run yet."
            )
        
        # Try to load from artifact first
        cached = read_artifact(workflow_dir, AnalysisType.SCF)
        if cached:
            # Return cached data (already in correct format)
            return {
                "workflow": workflow_selector,
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
            workflow_dir=workflow_dir,
            raw_dir=raw_dir,
            step_selector=step_selector,
            force=False,
        )
        
        if not status.ok:
            raise QVServiceError(status.error or "Failed to parse SCF output")
        
        # Now read the freshly created artifact
        cached = read_artifact(workflow_dir, AnalysisType.SCF)
        if not cached:
            raise QVServiceError("Failed to read SCF artifact after creation")
        
        return {
            "workflow": workflow_selector,
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
        workflow_selector: str,
        step_selector: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get DOS data for plotting in GUI.
        
        First attempts to load from JSON artifact (<workflow>/analysis/dos.json).
        If artifact doesn't exist, parses QE output directly and writes artifact.
        
        Args:
            project_root: Project root path
            workflow_selector: Workflow selector
            step_selector: Optional step selector (if None, searches for dos files)
            
        Returns:
            Dict with DOS data arrays and Fermi energy
        """
        from quantumvitas.analysis.artifacts import read_artifact, ensure_analysis_artifact, AnalysisType
        from quantumvitas.workflow.naming import find_workflow_raw_dir
        
        project_root = Path(project_root).resolve()
        workflow = require_workflow(project_root, workflow_selector)
        workflow_dir = workflow.absolute_path
        raw_dir = find_workflow_raw_dir(workflow_dir)
        
        if not raw_dir.exists():
            raise QVServiceError(
                f"Workflow raw directory not found: {raw_dir}\n"
                f"The workflow may not have been run yet."
            )
        
        # Try to load from artifact first
        cached = read_artifact(workflow_dir, AnalysisType.DOS)
        if cached:
            return {
                "workflow": workflow_selector,
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
            workflow_dir=workflow_dir,
            raw_dir=raw_dir,
            step_selector=step_selector,
            force=False,
        )
        
        if not status.ok:
            raise QVServiceError(status.error or "Failed to parse DOS data")
        
        # Now read the freshly created artifact
        cached = read_artifact(workflow_dir, AnalysisType.DOS)
        if not cached:
            raise QVServiceError("Failed to read DOS artifact after creation")
        
        return {
            "workflow": workflow_selector,
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
        workflow_selector: str,
        step_selector: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get band structure data for plotting in GUI.
        
        First attempts to load from JSON artifact (<workflow>/analysis/bands.json).
        If artifact doesn't exist, parses QE output directly and writes artifact.
        
        Args:
            project_root: Project root path
            workflow_selector: Workflow selector
            step_selector: Optional step selector
            
        Returns:
            Dict with band energies, k-distances, high-symmetry points, and Fermi energy
        """
        from quantumvitas.analysis.artifacts import read_artifact, ensure_analysis_artifact, AnalysisType
        from quantumvitas.workflow.naming import find_workflow_raw_dir
        
        project_root = Path(project_root).resolve()
        workflow = require_workflow(project_root, workflow_selector)
        workflow_dir = workflow.absolute_path
        raw_dir = find_workflow_raw_dir(workflow_dir)
        
        if not raw_dir.exists():
            raise QVServiceError(
                f"Workflow raw directory not found: {raw_dir}\n"
                f"The workflow may not have been run yet."
            )
        
        # Try to load from artifact first
        cached = read_artifact(workflow_dir, AnalysisType.BANDS)
        if cached:
            return {
                "workflow": workflow_selector,
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
            workflow_dir=workflow_dir,
            raw_dir=raw_dir,
            step_selector=step_selector,
            force=False,
        )
        
        if not status.ok:
            raise QVServiceError(status.error or "Failed to parse band structure data")
        
        # Now read the freshly created artifact
        cached = read_artifact(workflow_dir, AnalysisType.BANDS)
        if not cached:
            raise QVServiceError("Failed to read bands artifact after creation")
        
        return {
            "workflow": workflow_selector,
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
        workflow_selector: str,
        analysis_type: Literal["scf", "dos", "bands"],
    ) -> Optional[Dict[str, Any]]:
        """
        Get reference analysis data for demo projects.
        
        If the project was created from a demo snapshot that includes reference
        artifacts, this returns the reference data for comparison with user-generated
        analysis results.
        
        Args:
            project_root: Project root path
            workflow_selector: Workflow selector (used to match against demo workflow)
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
        # NOT project/workflow ULIDs. This allows reference analysis to work even though
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
        # NOT project/workflow ULIDs. The artifact filenames are stable identifiers.
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
                    "workflow": workflow_selector,
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
                    "workflow": workflow_selector,
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
                    "workflow": workflow_selector,
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
    def detect_qe() -> Dict[str, Any]:
        """
        Detect Quantum ESPRESSO installation.
        
        Returns:
            Dict with QE detection status, path, version, and available executables
        """
        from quantumvitas.core.engines.qe_installation import (
            get_qe_home,
            reset_qe_home,
            QEInstallation,
        )
        
        # Force re-detection
        reset_qe_home()
        qe_home = get_qe_home()
        
        result: Dict[str, Any] = {
            "found": qe_home is not None,
            "qe_home": str(qe_home) if qe_home else None,
            "version": None,
            "executables": [],
            "detection_source": None,
        }
        
        if qe_home:
            # Find available executables
            bin_dir = qe_home / "bin"
            if bin_dir.exists():
                executables = []
                for exe in ["pw.x", "ph.x", "dos.x", "bands.x", "projwfc.x", "pp.x"]:
                    if (bin_dir / exe).exists():
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
    ) -> Dict[str, Any]:
        """
        Rename a structure.
        
        Args:
            project_root: Project root path
            selector: Structure selector (name/slug/path)
            new_name: New name for the structure
            
        Returns:
            Dict with old_name, new_name, new_slug
        """
        resolved = resolve_structure(project_root, selector)
        old_name = resolved.meta.name
        
        QVService.configure_structure(
            project_root=project_root,
            selector=selector,
            new_name=new_name,
        )
        
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
            Dict with can_delete and list of workflows using this structure
        """
        config = load_project_config(project_root)
        entry = find_structure_entry(config, selector, project_root)
        
        using_workflows = workflows_using_structure(project_root, config, entry)
        workflow_names = [w.get("name", "?") for w in using_workflows]
        
        return {
            "can_delete": len(using_workflows) == 0,
            "using_workflows": workflow_names,
            "structure_name": entry.get("name") or (entry.get("meta") or {}).get("name"),
        }
    
    # -------------------------------------------------------------------------
    # Workflow CRUD Operations (Phase 3 - GUI Parity)
    # -------------------------------------------------------------------------
    
    @staticmethod
    def rename_workflow(
        project_root: Path,
        selector: str,
        new_name: str,
    ) -> Dict[str, Any]:
        """
        Rename a workflow.
        
        Args:
            project_root: Project root path
            selector: Workflow selector
            new_name: New name for the workflow
            
        Returns:
            Dict with old_name, new_name, new_slug
        """
        resolved = resolve_workflow(project_root, selector)
        old_name = resolved.meta.name
        
        QVService.configure_workflow(
            project_root=project_root,
            selector=selector,
            new_name=new_name,
        )
        
        return {
            "success": True,
            "old_name": old_name,
            "new_name": new_name,
            "new_slug": slugify(new_name),
        }
    
    @staticmethod
    def can_delete_workflow(
        project_root: Path,
        selector: str,
    ) -> Dict[str, Any]:
        """
        Check if a workflow can be safely deleted.
        
        Returns:
            Dict with workflow name and dependent workflows (if any)
        """
        config = load_project_config(project_root)
        entry = find_workflow_entry(config, selector, project_root)
        
        dependent_workflows = workflows_depending_on(config, entry)
        dep_names = [w.get("name", "?") for w in dependent_workflows]
        
        return {
            "workflow_name": entry.get("name") or (entry.get("meta") or {}).get("name"),
            "dependent_workflows": dep_names,
            "has_dependencies": len(dep_names) > 0,
        }
    
    # -------------------------------------------------------------------------
    # Step Operations (Phase 4 - GUI Parity)
    # -------------------------------------------------------------------------
    
    @staticmethod
    def get_step_detail(
        project_root: Path,
        workflow_selector: str,
        step_selector: str,
    ) -> Dict[str, Any]:
        """
        Get detailed information about a step.
        
        Args:
            project_root: Project root path
            workflow_selector: Workflow selector
            step_selector: Step selector
            
        Returns:
            Dict with step metadata, parameters, cards, etc.
        """
        from quantumvitas.workflow.structure_steps import StructureStepSpec
        
        step = resolve_step(project_root, workflow_selector, step_selector)
        
        # Load step spec; legacy 'structure' selectors (if present) are normalized to structure_id via the registry
        from quantumvitas.core.resolution import make_structure_selector_resolver
        from quantumvitas.core.project_utils import load_project_config
        config = load_project_config(project_root)
        resolver = make_structure_selector_resolver(project_root, config=config)
        spec = StructureStepSpec.from_yaml(step.absolute_path, resolve_structure_selector=resolver)
        
        return {
            "id": step.meta.id,
            "name": step.meta.name,
            "slug": step.meta.slug,
            "path": step.meta.path,
            "absolute_path": str(step.absolute_path),
            "step_type": spec.step_type,
            "structure": spec.structure,
            "parent_workflow_id": spec.parent_workflow_id,
            "parameters": spec.parameters,
            "cards": spec.cards,
            "species_overrides": spec.species_overrides,
        }
    
    @staticmethod
    def update_step_params(
        project_root: Path,
        workflow_selector: str,
        step_selector: str,
        parameters: Dict[str, Dict[str, Any]],
        cards: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Update step parameters safely.
        
        Only updates the specified parameters; does not clobber unknown options.
        Validates types for known parameters.
        
        Args:
            project_root: Project root path
            workflow_selector: Workflow selector
            step_selector: Step selector
            parameters: Dict of namelist -> {param: value} to update
            cards: Optional dict of card updates (e.g., K_POINTS)
            
        Returns:
            Updated step detail dict
        """
        from quantumvitas.workflow.structure_steps import StructureStepSpec
        
        step = resolve_step(project_root, workflow_selector, step_selector)
        # Load step spec; legacy 'structure' selectors (if present) are normalized to structure_id via the registry
        from quantumvitas.core.resolution import make_structure_selector_resolver
        from quantumvitas.core.project_utils import load_project_config
        config = load_project_config(project_root)
        resolver = make_structure_selector_resolver(project_root, config=config)
        spec = StructureStepSpec.from_yaml(step.absolute_path, resolve_structure_selector=resolver)
        
        # Validate and merge parameters
        for namelist, params in parameters.items():
            namelist_upper = namelist.upper()
            
            # Create namelist if it doesn't exist
            if namelist_upper not in spec.parameters:
                spec.parameters[namelist_upper] = {}
            
            for key, value in params.items():
                # Basic type validation for known parameters
                if key in ('ecutwfc', 'ecutrho', 'degauss', 'conv_thr'):
                    if value is not None:
                        try:
                            value = float(value)
                        except (TypeError, ValueError):
                            raise QVServiceError(f"Parameter '{key}' must be numeric, got: {value}")
                
                # Set or remove the parameter
                if value is None:
                    spec.parameters[namelist_upper].pop(key, None)
                else:
                    spec.parameters[namelist_upper][key] = value
            
            # Clean up empty namelists
            if not spec.parameters[namelist_upper]:
                del spec.parameters[namelist_upper]
        
        # Update cards if provided
        if cards:
            for card_name, card_data in cards.items():
                card_upper = card_name.upper()
                if card_data is None:
                    spec.cards.pop(card_upper, None)
                else:
                    spec.cards[card_upper] = card_data
        
        # Save the updated spec
        step.absolute_path.write_text(yaml.safe_dump(spec.to_dict(), sort_keys=False))
        
        # Return the updated step detail
        return {
            "id": step.meta.id,
            "name": step.meta.name,
            "slug": step.meta.slug,
            "path": step.meta.path,
            "absolute_path": str(step.absolute_path),
            "step_type": spec.step_type,
            "structure": spec.structure,
            "parent_workflow_id": spec.parent_workflow_id,
            "parameters": spec.parameters,
            "cards": spec.cards,
            "species_overrides": spec.species_overrides,
        }
    
    @staticmethod
    def import_step_from_qe_input(
        project_root: Path,
        workflow_selector: str,
        input_file: Path,
        step_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Import a QE input file as a step in a workflow (preserves original parameters).
        
        This uses apply_defaults=False to preserve the original QE input parameters
        without injecting QV defaults (outdir, restart_mode, conv_thr, etc.).
        
        Args:
            project_root: Project root path
            workflow_selector: Workflow selector (name, slug, or id)
            input_file: Path to QE input file (.in)
            step_name: Optional name for the new step (defaults to input file stem)
            
        Returns:
            Updated workflow info with the new step
        """
        from quantumvitas.workflow.importers import build_step_spec_from_qe_input
        from quantumvitas.core.models import load_workflow, save_workflow, WorkflowStepEntry
        import yaml
        
        project_root = Path(project_root).resolve()
        input_file = Path(input_file).resolve()
        
        if not input_file.exists():
            raise QVServiceError(f"QE input file not found: {input_file}")
        
        # Resolve workflow
        workflow = resolve_workflow(project_root, workflow_selector)
        workflow_dir = workflow.absolute_path
        steps_dir = workflow_dir / "steps"
        steps_dir.mkdir(exist_ok=True)
        
        # Load workflow model
        wf_model = load_workflow(workflow_dir, project_root)
        
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
        
        # Check if structure already exists in project
        config = load_project_config(project_root)
        structures = config.get("structures", [])
        structure_id_value = None
        for struct_entry in structures:
            struct_file = project_root / struct_entry.get("file", "")
            if struct_file.exists() and struct_file.samefile(structure_path):
                # Get structure ID (canonical reference)
                structure_id_value = struct_entry.get("meta", {}).get("id") or struct_entry.get("id")
                break
        
        if not structure_id_value:
            # Register structure in project
            from quantumvitas.core.resources import meta_from_name, ensure_relative_path
            from quantumvitas.io import write_structure, read_structure
            
            # Move structure to project structures directory
            project_structures_dir = project_root / "structures"
            project_structures_dir.mkdir(exist_ok=True)
            final_structure_path = project_structures_dir / f"{structure_id}.json"
            
            if not final_structure_path.exists():
                structure = read_structure(structure_path)
                meta = meta_from_name(
                    "structure",
                    name=structure_id,
                    path=ensure_relative_path(final_structure_path, base=project_root),
                )
                write_structure(structure, final_structure_path, metadata=meta)
            
            # Add to project config
            entry = {
                "name": structure_id,
                "file": ensure_relative_path(final_structure_path, base=project_root),
                "meta": meta.to_dict(),
            }
            structures.append(entry)
            save_project_config(project_root, config)
            structure_id_value = meta.id  # Use the structure's ULID (canonical reference)
        
        # Update step spec to reference structure by ID (canonical reference)
        spec.structure_id = structure_id_value
        spec_path = import_result.spec_path
        spec_path.write_text(yaml.safe_dump(spec.to_dict(), sort_keys=False))
        
        # Add step to workflow model using step_id (ULID) from step spec meta
        rel_step_path = spec_path.relative_to(workflow_dir)
        # step_file is NOT stored - step location resolved via registry using step_id
        wf_model.steps.append(WorkflowStepEntry(
            step_id=spec.meta.id,  # Use ULID from step spec meta (canonical reference)
            type=spec.step_type,
            # step_file is NOT stored - step location resolved via registry using step_id
        ))
        save_workflow(wf_model, workflow_dir)
        
        # Update workflow structure if not set (use structure_id, canonical reference)
        if not wf_model.structure_id:
            wf_model.structure_id = structure_id_value
            # Also set structure_name for display
            if structure_id_value:
                # Resolve structure to get name
                try:
                    resolved = resolve_structure(project_root, structure_id_value, config)
                    wf_model.structure_name = resolved.meta.name
                except Exception:
                    pass  # If resolution fails, structure_name stays None
            save_workflow(wf_model, workflow_dir)
        
        return QVService.get_workflow_detail(
            project_root=project_root,
            workflow_selector=workflow_selector,
        )
    
    @staticmethod
    def reset_step_params(
        project_root: Path,
        workflow_selector: str,
        step_selector: str,
    ) -> Dict[str, Any]:
        """
        Reset step parameters to in-code defaults based on step type.
        
        Args:
            project_root: Project root path
            workflow_selector: Workflow selector
            step_selector: Step selector
            
        Returns:
            Updated step detail dict
        """
        from quantumvitas.workflow.structure_steps import StructureStepSpec
        from quantumvitas.workflow.step_defaults import get_default_step_params
        import yaml
        
        step = resolve_step(project_root, workflow_selector, step_selector)
        # Load step spec; legacy 'structure' selectors (if present) are normalized to structure_id via the registry
        from quantumvitas.core.resolution import make_structure_selector_resolver
        from quantumvitas.core.project_utils import load_project_config
        config = load_project_config(project_root)
        resolver = make_structure_selector_resolver(project_root, config=config)
        spec = StructureStepSpec.from_yaml(step.absolute_path, resolve_structure_selector=resolver)
        
        # Get defaults for this step type
        defaults = get_default_step_params(spec.step_type)
        
        # Reset parameters and cards to defaults, keep meta/structure/parent_workflow_id
        spec.parameters = defaults.get("parameters", {})
        spec.cards = defaults.get("cards", {})
        spec.species_overrides = defaults.get("species_overrides", {})
        
        # Save the updated spec
        step.absolute_path.write_text(yaml.safe_dump(spec.to_dict(), sort_keys=False))
        
        return QVService.get_step_detail(project_root, workflow_selector, step_selector)
    
    # -------------------------------------------------------------------------
    # Workflow Configuration (Phase 4 - Reorder, Change Structure)
    # -------------------------------------------------------------------------
    
    @staticmethod
    def reorder_workflow_steps(
        project_root: Path,
        workflow_selector: str,
        new_order: List[str],
    ) -> Dict[str, Any]:
        """
        Reorder workflow steps.
        
        Args:
            project_root: Project root path
            workflow_selector: Workflow selector
            new_order: List of step IDs/slugs in the new order
            
        Returns:
            Updated workflow info
        """
        from quantumvitas.core.models import load_workflow
        
        workflow = resolve_workflow(project_root, workflow_selector)
        wf_path = workflow.absolute_path / "workflow.yaml"
        wf_model = load_workflow(wf_path)
        
        # Validate all step IDs exist
        existing_ids = {s.id for s in wf_model.steps}
        existing_slugs = {}
        for s in wf_model.steps:
            # Create a mapping from possible identifiers to step entries
            existing_slugs[s.id] = s
            if s.slug:
                existing_slugs[s.slug] = s
        
        # Resolve the new order
        reordered = []
        seen = set()
        for selector in new_order:
            if selector in existing_slugs:
                step = existing_slugs[selector]
                if step.id not in seen:
                    reordered.append(step)
                    seen.add(step.id)
            else:
                raise QVServiceError(f"Step '{selector}' not found in workflow")
        
        # Ensure all steps are accounted for
        if len(reordered) != len(wf_model.steps):
            missing = existing_ids - seen
            raise QVServiceError(f"New order missing steps: {missing}")
        
        # Update the model
        wf_model.steps = reordered
        wf_model.save(wf_path)
        
        # Return updated workflow info
        return QVService.get_workflow_detail(project_root, workflow_selector)
    
    @staticmethod
    def add_step_to_workflow(
        project_root: Path,
        workflow_selector: str,
        step_type: str,
        step_name: str = None,
    ) -> Dict[str, Any]:
        """
        Add a new step to a workflow.
        
        Args:
            project_root: Project root path
            workflow_selector: Workflow selector (name, slug, or id)
            step_type: Type of step (scf, nscf, relax, bands, dos, etc.)
            step_name: Name for the new step (defaults to step_type)
            
        Returns:
            Updated workflow info with the new step
        """
        from quantumvitas.core.models import WorkflowModel, WorkflowStepEntry
        from quantumvitas.workflow.structure_steps import StructureStepSpec
        import ulid as ulid_module
        from quantumvitas.core.models import load_workflow
        
        # Resolve workflow via registry (for consistent resolution)
        from quantumvitas.core.resolution import build_resource_index, require_workflow
        from quantumvitas.core.project_utils import load_project_config
        
        config = load_project_config(project_root)
        registry = build_resource_index(project_root)
        workflow = require_workflow(project_root, workflow_selector, config=config, index=registry)
        wf_path = workflow.absolute_path / "workflow.yaml"
        # Load workflow model; legacy 'structure' selectors (if present) are normalized to structure_id via the registry
        from quantumvitas.core.resolution import make_structure_selector_resolver
        resolver = make_structure_selector_resolver(project_root, config=config)
        wf_model = load_workflow(wf_path, project_root=project_root, resolve_structure_selector=resolver)
        
        # Determine step name
        if not step_name:
            step_name = step_type
        
        # Generate unique slug from name
        base_slug = slugify(step_name)
        
        # Check for duplicates and add suffix if needed
        existing_ids = {s.id for s in wf_model.steps}
        slug = base_slug
        counter = 1
        while slug in existing_ids:
            counter += 1
            slug = f"{base_slug}-{counter}"
        
        # Generate new step ID (use slug as the id in workflow.yaml)
        step_id = slug
        
        # Determine step file name
        step_file = f"steps/{slug}.step.yaml"
        
        # Get default parameters for this step type (from-scratch mode uses defaults)
        from quantumvitas.workflow.step_defaults import get_default_step_params
        from quantumvitas.core.models import ResourceMeta
        
        defaults = get_default_step_params(step_type)
        default_params = defaults.get("parameters", {})
        default_cards = defaults.get("cards", {})
        default_species = defaults.get("species_overrides", {})
        
        # Resolve structure from workflow to structure_id
        from quantumvitas.core.project_utils import load_project_config
        from quantumvitas.core.resolution import _is_path_like
        config = load_project_config(project_root)
        
        structure_id = None
        structure_selector = None
        if wf_model.structure_id:
            structure_id = wf_model.structure_id
            # Get selector for backwards compat
            try:
                resolved = resolve_structure(project_root, wf_model.structure_id, config)
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
                        resolved = resolve_structure(project_root, wf_model.structure, config)
                        structure_id = resolved.meta.id
                        structure_selector = resolved.meta.slug
                    except Exception:
                        # Not registered - use path directly (backwards compat)
                        structure_selector = wf_model.structure
                else:
                    # Path doesn't exist, try as selector
                    try:
                        resolved = resolve_structure(project_root, wf_model.structure, config)
                        structure_id = resolved.meta.id
                        structure_selector = resolved.meta.slug
                    except Exception:
                        # Resolution failed, use original value
                        structure_selector = wf_model.structure
            else:
                # Try to resolve as selector
                try:
                    resolved = resolve_structure(project_root, wf_model.structure, config)
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
                    resolved = resolve_structure(project_root, structure_selector, config)
                    structure_id = resolved.meta.id
                except Exception:
                    pass
            
            # If still no structure_id, try wf_model.structure as last resort
            if not structure_id and wf_model.structure:
                try:
                    resolved = resolve_structure(project_root, wf_model.structure, config)
                    structure_id = resolved.meta.id
                except Exception:
                    pass
            
            # If we still don't have structure_id, we cannot create the step spec
            if not structure_id:
                raise ValueError(
                    f"Workflow '{workflow_selector}' has no structure or structure cannot be resolved. "
                    "Please set a structure for the workflow first and ensure it is registered in the project."
                )
        
        # Step initialization: inherit structure_id from workflow if step doesn't have one
        # workflow.structure_id is canonical and must never be cleared by adding steps
        if not structure_id and wf_model.structure_id:
            # Inherit from workflow (copy the canonical ID, not a move)
            structure_id = wf_model.structure_id
        
        # DAG + ID-only model: Step YAML contains ONLY step-local configuration.
        # NO structure_id (inherits from workflow.structure_id at execution time).
        # NO parent_workflow_id (parent is implicit from step file location).
        # Structure is resolved via workflow.structure_id when the step is executed.
        step_meta = ResourceMeta(
            id=str(ulid_module.new()),  # Actual ULID for the step spec
            name=step_name,
            slug=slug,
            path=f"workflows/{wf_model.meta.slug}/{step_file}",
            kind="step",
        )
        step_spec = StructureStepSpec(
            meta=step_meta,
            step_type=step_type,
            # Do NOT set structure_id (inherits from workflow at execution time)
            # Do NOT set parent_workflow_id (parent is implicit)
            structure="",  # Empty legacy field (not written to YAML)
            parameters=default_params,
            cards=default_cards,
            species_overrides=default_species,
        )
        
        # Write step file
        steps_dir = workflow.absolute_path / "steps"
        steps_dir.mkdir(exist_ok=True)
        step_yaml_filename = f"{slug}.step.yaml"
        step_file_path = steps_dir / step_yaml_filename
        step_file_path.write_text(yaml.safe_dump(step_spec.to_dict(), sort_keys=False))
        
        # Create step entry for workflow.yaml using step_id (ULID) from step spec meta
        # step_file is NOT stored - step location resolved via registry using step_id
        new_step = WorkflowStepEntry(
            step_id=step_spec.meta.id,  # Use ULID from step spec meta (canonical reference)
            type=step_type,
            # step_file is NOT stored - step location resolved via registry using step_id
        )
        
        # Add step to workflow
        # CRITICAL: workflow.structure_id is canonical and must NEVER be cleared by adding steps
        # It remains set for the lifetime of the workflow
        from quantumvitas.core.models import save_workflow
        wf_model.steps.append(new_step)
        # Ensure workflow.structure_id is preserved (never cleared)
        assert wf_model.structure_id is not None, "Workflow structure_id must not be cleared when adding steps"
        save_workflow(wf_model, wf_path)
        
        # Return updated workflow info without materializing steps (avoids pseudo requirements)
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
    def change_workflow_structure(
        project_root: Path,
        workflow_selector: str,
        new_structure: str,
        update_steps: bool = True,
    ) -> Dict[str, Any]:
        """
        Change the structure associated with a workflow.
        
        Args:
            project_root: Project root path
            workflow_selector: Workflow selector
            new_structure: New structure selector
            update_steps: Whether to also update all steps' structure field
            
        Returns:
            Updated workflow info with any warnings
        """
        from quantumvitas.core.models import WorkflowModel
        from quantumvitas.workflow.structure_steps import StructureStepSpec
        
        # Validate structure exists
        resolved_structure = resolve_structure(project_root, new_structure)
        
        from quantumvitas.core.models import load_workflow, save_workflow
        from quantumvitas.core.resolution import make_structure_selector_resolver
        from quantumvitas.core.project_utils import load_project_config
        workflow = resolve_workflow(project_root, workflow_selector)
        wf_path = workflow.absolute_path / "workflow.yaml"
        # Load workflow model; legacy 'structure' selectors (if present) are normalized to structure_id via the registry
        config = load_project_config(project_root)
        resolver = make_structure_selector_resolver(project_root, config=config)
        wf_model = load_workflow(wf_path, project_root=project_root, resolve_structure_selector=resolver)
        
        old_structure = wf_model.structure_name or wf_model.structure
        # Update structure_id (canonical reference)
        wf_model.structure_id = resolved_structure.meta.id
        wf_model.structure_name = resolved_structure.meta.name
        # Keep structure for backwards compat (but it's not authoritative)
        wf_model.structure = resolved_structure.meta.slug
        save_workflow(wf_model, wf_path)
        
        warnings = []
        updated_steps = []
        
        if update_steps:
            # Update all step files
            steps_dir = workflow.absolute_path / "steps"
            if steps_dir.exists():
                # Create resolver for normalizing legacy structure selectors
                from quantumvitas.core.resolution import make_structure_selector_resolver
                from quantumvitas.core.project_utils import load_project_config
                config = load_project_config(project_root)
                resolver = make_structure_selector_resolver(project_root, config=config)
                
                for step_file in steps_dir.glob("*.step.yaml"):
                    try:
                        # Load step spec; legacy 'structure' selectors (if present) are normalized to structure_id via the registry
                        spec = StructureStepSpec.from_yaml(step_file, resolve_structure_selector=resolver)
                        # Check if step needs structure update (compare structure_id, not structure selector)
                        if spec.structure_id != resolved_structure.meta.id:
                            old_step_struct_id = spec.structure_id
                            # Update step spec structure_id (canonical reference)
                            spec.structure_id = resolved_structure.meta.id
                            # Clear legacy structure field (not written to YAML)
                            spec.structure = ""
                            step_file.write_text(yaml.safe_dump(spec.to_dict(), sort_keys=False))
                            updated_steps.append({
                                "step_id": spec.meta.id,
                                "old_structure_id": old_step_struct_id,
                                "new_structure_id": resolved_structure.meta.id,
                            })
                    except Exception as e:
                        warnings.append(f"Failed to update step {step_file.name}: {e}")
        
        result = QVService.get_workflow_detail(project_root, workflow_selector)
        result["old_structure"] = old_structure
        result["updated_steps"] = updated_steps
        result["warnings"] = warnings
        
        return result
    
    @staticmethod
    def get_workflow_detail(
        project_root: Path,
        workflow_selector: str,
    ) -> Dict[str, Any]:
        """
        Get detailed workflow information for GUI display.
        
        Uses Project.open() and Workflow.from_yaml() to ensure legacy workflows
        are automatically migrated to the ID-only model.
        
        Args:
            project_root: Project root path
            workflow_selector: Workflow selector
            
        Returns:
            Dict with workflow details including steps
        """
        from quantumvitas.project.model import Project
        from quantumvitas.workflow.workflow import Workflow
        from quantumvitas.core.resolution import ResourceNotFoundError, resolve_workflow
        
        project_root = Path(project_root).resolve()
        
        # Use Project.open() to get project context
        try:
            project = Project.open(project_root)
        except Exception as e:
            raise ResourceNotFoundError(
                kind="project",
                selector=str(project_root),
                id=None,
                project_root=project_root,
            ) from e
        
        # First resolve workflow to get the reference (handles name/slug/id selectors)
        try:
            workflow_resolved = resolve_workflow(project_root, workflow_selector)
        except Exception as e:
            raise ResourceNotFoundError(
                kind="workflow",
                selector=workflow_selector,
                id=None,
                project_root=project_root,
            ) from e
        
        # Load workflow using Workflow.from_yaml (which handles legacy migration)
        # Note: We catch exceptions here but only re-raise as ResourceNotFoundError if it's
        # a workflow loading issue. Structure resolution failures are handled gracefully.
        try:
            workflow = Workflow.from_yaml(workflow_resolved.absolute_path, project)
        except FileNotFoundError as e:
            # If workflow.yaml is missing, that's a real workflow not found error
            if "workflow.yaml" in str(e):
                raise ResourceNotFoundError(
                    kind="workflow",
                    selector=workflow_selector,
                    id=workflow_resolved.meta.id,
                    project_root=project_root,
                ) from e
            # Otherwise, it might be a structure file issue - continue and handle gracefully
            # Try to load workflow without structure resolution
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Structure resolution failed for workflow {workflow_selector}: {e}")
            # Re-raise as workflow not found for now, but this could be made more graceful
            raise ResourceNotFoundError(
                kind="workflow",
                selector=workflow_selector,
                id=workflow_resolved.meta.id,
                project_root=project_root,
            ) from e
        except Exception as e:
            # For other exceptions, check if it's a workflow loading issue
            # Structure resolution failures in Workflow.from_yaml are handled internally,
            # so if we get here it's likely a real workflow loading problem
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to load workflow {workflow_selector}: {e}")
            raise ResourceNotFoundError(
                kind="workflow",
                selector=workflow_selector,
                id=workflow_resolved.meta.id,
                project_root=project_root,
            ) from e
        
        # Extract structure info
        structure_name = None
        structure_id = None
        if workflow.structure:
            if hasattr(workflow.structure, 'meta'):
                structure_name = workflow.structure.meta.name
                structure_id = workflow.structure.meta.id
            else:
                structure_name = str(workflow.structure)
        
        # Extract step info from actual Step objects (which have ULID meta.id)
        steps = []
        for step in workflow.steps:
            step_type = step.step_type.value if hasattr(step.step_type, 'value') else str(step.step_type)
            steps.append({
                "step_id": step.meta.id,  # ULID (canonical reference)
                "id": step.meta.id,  # Use ULID for both fields
                "slug": step.meta.slug or step.meta.name,  # For display
                "type": step_type or "unknown",
                # step_file is NOT stored - step location resolved via registry using step_id
            })
        
        return {
            "id": workflow_resolved.meta.id,
            "name": workflow_resolved.meta.name,
            "slug": workflow_resolved.meta.slug,
            "path": workflow_resolved.meta.path,
            "absolute_path": str(workflow.dir),
            "structure": structure_name,
            "structure_id": structure_id,
            "mode": workflow.mode.value if hasattr(workflow.mode, 'value') else str(workflow.mode),
            "n_steps": len(steps),
            "steps": steps,
        }
    
    # -------------------------------------------------------------------------
    # Pre-flight Checks (Phase 4 - Validate before run)
    # -------------------------------------------------------------------------
    
    @staticmethod
    def preflight_check(
        project_root: Path,
        workflow_selector: Optional[str] = None,
        step_selector: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Perform pre-flight checks before running a workflow or step.
        
        Args:
            project_root: Project root path
            workflow_selector: Optional workflow selector
            step_selector: Optional step selector (requires workflow_selector)
            
        Returns:
            Dict with check results: {
                "ok": bool,
                "checks": [{"name": str, "ok": bool, "message": str}],
                "errors": [str],
                "warnings": [str],
            }
        """
        from quantumvitas.core.engines.qe_installation import get_qe_home, QEInstallation
        
        checks = []
        errors = []
        warnings = []
        
        # Check 1: QE installation
        qe_home = get_qe_home()
        if qe_home:
            try:
                qe = QEInstallation(qe_home)
                pw_x = qe.find_executable("pw.x")
                if pw_x and pw_x.exists():
                    checks.append({"name": "QE Installation", "ok": True, "message": f"pw.x found at {pw_x}"})
                else:
                    checks.append({"name": "QE Installation", "ok": False, "message": "pw.x not found"})
                    errors.append("Quantum ESPRESSO pw.x executable not found")
            except Exception as e:
                checks.append({"name": "QE Installation", "ok": False, "message": str(e)})
                errors.append(f"QE installation error: {e}")
        else:
            checks.append({"name": "QE Installation", "ok": False, "message": "QE not detected"})
            errors.append("Quantum ESPRESSO not detected. Use Settings to detect or configure QE.")
        
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
        
        # Check 3: Workflow exists
        workflow = None
        if workflow_selector:
            try:
                workflow = resolve_workflow(project_root, workflow_selector)
                checks.append({"name": "Workflow", "ok": True, "message": f"Workflow found: {workflow.meta.name}"})
            except Exception as e:
                checks.append({"name": "Workflow", "ok": False, "message": str(e)})
                errors.append(f"Workflow not found: {workflow_selector}")
        
        # Only continue with workflow-dependent checks if workflow was found
        if workflow:
            # Check 4: Structure exists
            try:
                from quantumvitas.core.models import load_workflow
                wf_path = workflow.absolute_path / "workflow.yaml"
                wf_model = load_workflow(wf_path)
                
                if wf_model.structure:
                    try:
                        structure = resolve_structure(project_root, wf_model.structure)
                        checks.append({"name": "Structure", "ok": True, "message": f"Structure found: {structure.meta.name}"})
                    except Exception:
                        checks.append({"name": "Structure", "ok": False, "message": f"Structure '{wf_model.structure}' not found"})
                        errors.append(f"Workflow references missing structure: {wf_model.structure}")
                else:
                    checks.append({"name": "Structure", "ok": False, "message": "No structure assigned"})
                    errors.append("Workflow has no structure assigned")
            except Exception as e:
                checks.append({"name": "Workflow Config", "ok": False, "message": f"Failed to parse workflow.yaml: {e}"})
                errors.append(f"Workflow configuration error: {e}")
            
            # Check 5: Pseudo directory
            pseudo_dir = project_path / "pseudo"
            if pseudo_dir.exists() and any(pseudo_dir.iterdir()):
                checks.append({"name": "Pseudopotentials", "ok": True, "message": "Pseudo directory has files"})
            else:
                checks.append({"name": "Pseudopotentials", "ok": False, "message": "No pseudopotentials found"})
                warnings.append("No pseudopotential files in pseudo/ directory - QE may fail")
            
            # Check 6: Working directory writable
            raw_dir = workflow.absolute_path / "raw"
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
        Create a demo Si project with a ready-to-run workflow.
        
        Creates a project from a snapshot in resources/demo_projects/.
        Default demo is si_bands_demo (Silicon band structure workflow).
        
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
        
        # Verify at least one structure or workflow exists
        structures_dir = project_root / "structures"
        workflows_dir = project_root / "workflows"
        if not structures_dir.exists() and not workflows_dir.exists():
            raise QVServiceError(
                f"Demo project was created but no structures or workflows found in {project_root}"
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
        
        # Extract structure and workflow info from snapshot
        structure_info = None
        workflow_info = None
        
        if snapshot.structures:
            struct_meta = snapshot.structures[0].get("meta", {})
            structure_info = {
                "id": struct_meta.get("id"),
                "name": struct_meta.get("name"),
            }
        
        if snapshot.workflows:
            wf_meta = snapshot.workflows[0].get("meta", {})
            workflow_info = {
                "id": wf_meta.get("id"),
                "name": wf_meta.get("name"),
            }
        
        return {
            "project_root": str(project_root),
            "project_id": project_summary.get("id"),
            "project_name": project_summary.get("name"),
            "structure": structure_info,
            "workflow": workflow_info,
            "ready_to_run": len(snapshot.workflows) > 0,
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
                "description": "Silicon density of states calculation with SCF, NSCF, and DOS steps. Demonstrates DOS analysis workflow.",
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


# Export the service as a singleton-like module-level instance
service = QVService()

