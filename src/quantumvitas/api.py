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
from typing import Any, Dict, List, Optional, Sequence, Tuple, TYPE_CHECKING

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
    SelectorNotFoundError,
    resolve_project,
    resolve_structure,
    resolve_workflow,
    resolve_step,
    list_structures,
    list_workflows,
    list_steps,
)
from quantumvitas.core.project_utils import (
    ProjectConfigError,
    ResourceNotFoundError,
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
            template: Optional template name to use
            
        Returns:
            Path to project root
        """
        target_dir = Path(target_dir).resolve()
        
        if template:
            from quantumvitas.core.templates import copy_project_template
            return copy_project_template(template, target_dir, name)
        
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
        
        # Add to config
        entry = {
            "name": final_name,
            "file": meta.path,
            "meta": meta.to_dict(),
        }
        structures.append(entry)
        save_project_config(project_root, config)
        
        return resolve_structure(project_root, final_slug, config)
    
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
        config = load_project_config(project_root)
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
        file_path = entry.get("file") or (entry.get("meta") or {}).get("path")
        if file_path:
            abs_path = (project_root / file_path).resolve()
            if abs_path.exists():
                trash = project_root / "trash"
                move_to_trash(abs_path, trash)
        
        # Remove from config
        structures = config.get("structures", [])
        if entry in structures:
            structures.remove(entry)
        save_project_config(project_root, config)
    
    @staticmethod
    def list_structures(project_root: Path) -> List[ResolvedResource]:
        """List all structures in a project."""
        return list_structures(project_root)
    
    @staticmethod
    def get_structure(project_root: Path, selector: str) -> ResolvedResource:
        """Get a structure by selector."""
        return resolve_structure(project_root, selector)
    
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
                structure=structure_selector,
            )
            save_workflow(workflow_model, workflow_dir)
        
        # Add to project config
        entry = {
            "name": final_name,
            "path": workflow_path,
            "meta": {
                "id": workflow_id,
                "name": final_name,
                "slug": final_slug,
                "path": workflow_path,
                "kind": "workflow",
            },
        }
        workflows.append(entry)
        save_project_config(project_root, config)
        
        return resolve_workflow(project_root, final_slug, config)
    
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
        template: Optional[str] = None,
    ) -> ResolvedResource:
        """
        Create a new step in a workflow.
        
        Args:
            project_root: Project root path
            workflow_selector: Parent workflow selector
            step_type: Step type (scf, nscf, dos, bands, etc.)
            name: Optional step name (defaults to step_type)
            structure_selector: Optional structure (defaults to workflow's structure)
            template: Optional template name
            
        Returns:
            ResolvedResource for the new step
        """
        from quantumvitas.workflow.structure_steps import StructureStepSpec
        from quantumvitas.core.models import WorkflowModel
        
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
                structure_selector = wf_model.structure
        else:
            # Create workflow model if it doesn't exist
            wf_model = WorkflowModel(
                meta=workflow.meta,
                structure=structure_selector,
            )
        
        if template:
            from quantumvitas.core.templates import copy_step_template
            copy_step_template(
                template,
                step_yaml_path.parent,
                project_root,
                workflow_ulid=workflow.meta.id,
                structure=structure_selector,
            )
        else:
            # Create step spec
            spec = StructureStepSpec(
                meta=ResourceMeta(
                    id=step_id,
                    name=step_name,
                    slug=step_slug,
                    path=ensure_relative_path(step_yaml_path, base=project_root),
                    kind="step",
                ),
                step_type=step_type,
                structure=structure_selector,
                parent_workflow_id=workflow.meta.id,
            )
            step_yaml_path.write_text(yaml.safe_dump(spec.to_dict(), sort_keys=False))
        
        # Add step to workflow model
        wf_model.steps.append(WorkflowStepEntry(
            id=step_name,
            type=step_type,
            step_file=f"steps/{base_name}.step.yaml",
        ))
        save_workflow(wf_model, workflow_dir)
        
        return resolve_step(project_root, workflow_selector, step_slug)
    
    @staticmethod
    def configure_step(
        project_root: Path,
        workflow_selector: str,
        step_selector: str,
        **kwargs: Any,
    ) -> None:
        """Configure a step's parameters."""
        step = resolve_step(project_root, workflow_selector, step_selector)
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
        workflow = resolve_workflow(project_root, workflow_selector)
        step = resolve_step(project_root, workflow_selector, step_selector)
        
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
        return resolve_step(project_root, workflow_selector, step_selector)
    
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
        
        Args:
            project_root: Project root path
            workflow_selector: Workflow selector
            strict: If True, fail on first error
            verbose: If True, print detailed output
            
        Returns:
            Dict with run results
        """
        from quantumvitas.project.model import Project
        from quantumvitas.workflow.runner import WorkflowRunner
        from quantumvitas.core.engines.base import EngineConfig
        from quantumvitas.core.engines.qe import QuantumEspressoEngine
        
        project = Project.open(project_root)
        workflow = project.get_workflow(workflow_selector)
        
        config = EngineConfig(name="qe")
        engine = QuantumEspressoEngine(config)
        runner = WorkflowRunner(engine)
        
        results = runner.run(workflow)
        
        return {
            "workflow": workflow_selector,
            "steps": len(results),
            "results": results,
        }
    
    @staticmethod
    def run_step(
        project_root: Path,
        workflow_selector: str,
        step_selector: str,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """
        Run a single step.
        
        Args:
            project_root: Project root path
            workflow_selector: Workflow selector
            step_selector: Step selector
            verbose: If True, print detailed output
            
        Returns:
            Dict with run results
        """
        from quantumvitas.workflow.input_runner import run_input_step
        from quantumvitas.workflow.structure_steps import (
            StructureStepSpec,
            generate_qe_input_from_spec,
        )
        from quantumvitas.core.engines.base import EngineConfig
        from quantumvitas.core.engines.qe import QuantumEspressoEngine
        
        step = resolve_step(project_root, workflow_selector, step_selector)
        workflow = resolve_workflow(project_root, workflow_selector)
        
        spec = StructureStepSpec.from_yaml(step.absolute_path)
        qe_input = generate_qe_input_from_spec(spec, project_root)
        
        config = EngineConfig(name="qe")
        engine = QuantumEspressoEngine(config)
        
        result = run_input_step(
            qe_input=qe_input,
            step_spec=spec,
            step_type=spec.step_type,
            project_root=project_root,
            workdir=workflow.absolute_path / "raw",
            engine=engine,
            keep_original=False,
        )
        
        return {
            "step": step_selector,
            "result": result,
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


# Export the service as a singleton-like module-level instance
service = QVService()

