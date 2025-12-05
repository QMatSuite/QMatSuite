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
        from quantumvitas.engine.registry import create_default_registry
        
        project = Project.open(project_root)
        workflow = project.get_workflow(workflow_selector)
        
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
        
        return {
            "id": meta.get("id"),
            "name": project_info.get("name") or meta.get("name") or project_root.name,
            "slug": meta.get("slug"),
            "path": str(project_root),
            "n_structures": len(structures),
            "n_workflows": len(workflows),
            "structure_names": [s.get("name", "?") for s in structures],
            "workflow_names": [w.get("name", "?") for w in workflows],
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
        
        Args:
            project_root: Project root path
            
        Returns:
            List of dicts, each with workflow metadata and step info
        """
        project_root = Path(project_root).resolve()
        resolved_list = list_workflows(project_root)
        
        result = []
        for res in resolved_list:
            entry = {
                "id": res.meta.id,
                "name": res.meta.name,
                "slug": res.meta.slug,
                "path": res.meta.path,
                "absolute_path": str(res.absolute_path),
            }
            
            # Try to add workflow details
            try:
                from quantumvitas.core.models import load_workflow
                if res.absolute_path.exists():
                    wf_model = load_workflow(res.absolute_path, project_root)
                    entry["structure"] = wf_model.structure
                    entry["mode"] = wf_model.mode
                    entry["n_steps"] = len(wf_model.steps)
                    entry["steps"] = [
                        {
                            "id": s.id,
                            "type": s.type,
                            "step_file": s.step_file,
                        }
                        for s in wf_model.steps
                    ]
            except Exception:
                pass  # Workflow details are optional
            
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
                boundary_coords, boundary_elements = generate_boundary_atoms(structure)
                for coords, element in zip(boundary_coords, boundary_elements):
                    frac = lattice.get_fractional_coords(coords)
                    boundary_atoms.append({
                        "element": element,
                        "cart_coords": [float(c) for c in coords],
                        "frac_coords": [float(f) for f in frac],
                        "color": get_element_color(element),
                        "radius": get_element_radius(element),
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
    def get_scf_convergence_data(
        project_root: Path,
        workflow_selector: str,
        step_selector: str,
    ) -> Dict[str, Any]:
        """
        Get SCF convergence data for a specific step in a workflow.
        
        Args:
            project_root: Project root path
            workflow_selector: Workflow selector
            step_selector: Step selector
            
        Returns:
            Dict with SCF convergence data (iterations, energies, etc.)
        """
        from quantumvitas.analysis.parsers import parse_scf_output
        from quantumvitas.workflow.naming import find_workflow_raw_dir
        
        project_root = Path(project_root).resolve()
        workflow = resolve_workflow(project_root, workflow_selector)
        
        # Find output file in raw directory
        raw_dir = find_workflow_raw_dir(workflow.absolute_path)
        
        # Look for output files matching step selector
        scf_output = None
        for pattern in [f"*{step_selector}*.out", f"{step_selector}.out", "*scf*.out"]:
            matches = list(raw_dir.glob(pattern))
            if matches:
                scf_output = matches[0]
                break
        
        if scf_output is None or not scf_output.exists():
            raise QVServiceError(
                f"SCF output not found for step '{step_selector}' in workflow '{workflow_selector}'"
            )
        
        # Parse SCF output
        result = parse_scf_output(scf_output)
        
        # Build convergence series data
        iterations_data = []
        for it in result.iterations:
            iterations_data.append({
                "iteration": it.iteration,
                "total_energy_ry": it.total_energy,
                "scf_accuracy_ry": it.scf_accuracy,
            })
        
        return {
            "workflow": workflow_selector,
            "step": step_selector,
            "output_file": str(scf_output),
            "converged": result.converged,
            "n_iterations": len(result.iterations),
            "total_energy_ry": result.total_energy,
            "fermi_energy_ev": result.fermi_energy,
            "iterations": iterations_data,
            "calculation_type": result.calculation_type,
            "n_electrons": result.n_electrons,
            "n_kpoints": result.n_kpoints,
            "ecutwfc_ry": result.ecutwfc,
            "units": {
                "energy": "Ry",
                "fermi": "eV",
            },
        }
    
    @staticmethod
    def get_dos_data(
        project_root: Path,
        workflow_selector: str,
        step_selector: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get DOS data for plotting in GUI.
        
        Args:
            project_root: Project root path
            workflow_selector: Workflow selector
            step_selector: Optional step selector (if None, searches for dos files)
            
        Returns:
            Dict with DOS data arrays and Fermi energy
        """
        from quantumvitas.analysis.parsers import parse_dos_data, parse_scf_output
        from quantumvitas.workflow.naming import find_workflow_raw_dir
        
        project_root = Path(project_root).resolve()
        workflow = resolve_workflow(project_root, workflow_selector)
        raw_dir = find_workflow_raw_dir(workflow.absolute_path)
        
        # Find DOS data file
        dos_file = None
        patterns = ["*.dos.dat", "*dos*.dat", "*.dos"]
        if step_selector:
            patterns = [f"*{step_selector}*.dat", f"{step_selector}.dat"] + patterns
        
        for pattern in patterns:
            matches = list(raw_dir.glob(pattern))
            if matches:
                dos_file = matches[0]
                break
        
        if dos_file is None or not dos_file.exists():
            raise QVServiceError(
                f"DOS data file not found in workflow '{workflow_selector}'"
            )
        
        # Parse DOS data
        dos_data = parse_dos_data(dos_file)
        
        # Try to get Fermi energy from NSCF/SCF output
        fermi_energy = dos_data.fermi_energy
        if fermi_energy is None:
            for pattern in ["*nscf*.out", "*scf*.out"]:
                matches = list(raw_dir.glob(pattern))
                if matches:
                    try:
                        scf_result = parse_scf_output(matches[0])
                        fermi_energy = scf_result.fermi_energy
                        break
                    except Exception:
                        pass
        
        return {
            "workflow": workflow_selector,
            "step": step_selector,
            "data_file": str(dos_file),
            "n_points": len(dos_data.energies),
            "fermi_energy_ev": fermi_energy,
            "energy_range_ev": [float(dos_data.energies.min()), float(dos_data.energies.max())],
            "energies_ev": dos_data.energies.tolist(),
            "dos_states_per_ev": dos_data.dos.tolist(),
            "idos": dos_data.idos.tolist() if dos_data.idos is not None else None,
            "units": {
                "energy": "eV",
                "dos": "states/eV",
            },
        }
    
    @staticmethod
    def get_band_structure_data(
        project_root: Path,
        workflow_selector: str,
        step_selector: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get band structure data for plotting in GUI.
        
        Args:
            project_root: Project root path
            workflow_selector: Workflow selector
            step_selector: Optional step selector
            
        Returns:
            Dict with band energies, k-distances, high-symmetry points, and Fermi energy
        """
        from quantumvitas.analysis.parsers import parse_bands_gnu, parse_scf_output
        from quantumvitas.workflow.naming import find_band_analysis_files, find_workflow_raw_dir
        
        project_root = Path(project_root).resolve()
        workflow = resolve_workflow(project_root, workflow_selector)
        raw_dir = find_workflow_raw_dir(workflow.absolute_path)
        
        # Find band analysis files
        found_files = find_band_analysis_files(raw_dir)
        
        if found_files.bands_gnu is None:
            raise QVServiceError(
                f"Band structure data not found in workflow '{workflow_selector}'"
            )
        
        # Get Fermi energy from pw.x output if available
        fermi_energy = None
        if found_files.pw_output:
            try:
                scf_result = parse_scf_output(found_files.pw_output)
                fermi_energy = scf_result.fermi_energy
            except Exception:
                pass
        
        # Parse band data
        band_data = parse_bands_gnu(
            found_files.bands_gnu,
            symmetry_file=found_files.bands_pp_out,
            fermi_energy=fermi_energy,
            pw_output_file=found_files.pw_output,
        )
        
        # Format high-symmetry points (ensure JSON-serializable)
        high_sym_points = []
        for pt in band_data.high_symmetry_points:
            # Convert k_coords to list of floats (may be numpy array)
            k_coords = None
            if pt.k_coords is not None:
                k_coords = [float(x) for x in pt.k_coords]
            high_sym_points.append({
                "label": pt.label,
                "k_distance": float(pt.k_distance) if pt.k_distance is not None else None,
                "k_coords": k_coords,
            })
        
        return {
            "workflow": workflow_selector,
            "step": step_selector,
            "data_file": str(found_files.bands_gnu),
            "n_bands": band_data.n_bands,
            "n_kpoints": band_data.n_kpoints,
            "fermi_energy_ev": band_data.fermi_energy,
            "k_distances": band_data.k_distances.tolist(),
            "energies_ev": band_data.energies.tolist(),  # Shape: [n_bands, n_kpoints]
            "high_symmetry_points": high_sym_points,
            "units": {
                "energy": "eV",
                "k_distance": "2π/a",
            },
        }


# Export the service as a singleton-like module-level instance
service = QVService()

