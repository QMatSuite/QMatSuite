"""
Project context helpers for CLI and service layer.

Provides ProjectContext and helpers for loading project context with registry,
resolving workflows/steps from CLI arguments, and detecting current context from cwd.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from quantumvitas.core.resolution import ResourceIndex, build_resource_index
from quantumvitas.core.project_utils import find_project_root, load_project_config
from quantumvitas.core.resolution import resolve_workflow, require_workflow, require_step
from quantumvitas.core.resolution import ResolvedResource, ResourceNotFoundError


@dataclass
class ProjectContext:
    """
    Project context with registry for resource resolution.
    
    This is the canonical way to work with a project in CLI and service layer.
    It combines project_root, registry, and optional current workflow/step context.
    """
    project_root: Path
    registry: ResourceIndex
    config: dict
    current_workflow_id: Optional[str] = None
    current_step_id: Optional[str] = None
    
    @classmethod
    def load(
        cls,
        cwd: Path,
        project_arg: Optional[Path | str] = None,
    ) -> "ProjectContext":
        """
        Load project context from cwd and optional project argument.
        
        Args:
            cwd: Current working directory (for auto-detection)
            project_arg: Optional project root path or file path
            
        Returns:
            ProjectContext with project_root, registry, and config
            
        Raises:
            ResourceNotFoundError: If project not found
        """
        # Resolve project_root
        if project_arg:
            project_path = Path(project_arg).resolve()
            if project_path.is_file():
                project_root = project_path.parent
            else:
                project_root = project_path
            
            if not (project_root / "project.qv.yml").exists():
                raise ResourceNotFoundError(
                    kind="project",
                    selector=str(project_arg),
                    project_root=None,
                )
        else:
            # Auto-detect from cwd
            project_root = find_project_root(cwd)
        
        # Load config and build registry
        config = load_project_config(project_root)
        registry = build_resource_index(project_root)
        
        # Try to detect current workflow/step from cwd
        current_workflow_id = None
        current_step_id = None
        
        try:
            rel_path = cwd.resolve().relative_to(project_root)
            # Check if inside workflows directory
            if str(rel_path).startswith("workflows/"):
                parts = rel_path.parts
                if len(parts) >= 2:
                    workflow_dir_name = parts[1]
                    workflow_dir = project_root / "workflows" / workflow_dir_name
                    if workflow_dir.exists():
                        workflow_yaml = workflow_dir / "workflow.yaml"
                        if workflow_yaml.exists():
                            import yaml
                            try:
                                wf_data = yaml.safe_load(workflow_yaml.read_text()) or {}
                                wf_meta = wf_data.get("meta") or {}
                                current_workflow_id = wf_meta.get("id")
                                
                                # Check if inside steps directory
                                if len(parts) >= 3 and parts[2] == "steps":
                                    if len(parts) >= 4:
                                        step_file_name = parts[3]
                                        if step_file_name.endswith(".step.yaml"):
                                            step_id = step_file_name.replace(".step.yaml", "")
                                            # Try to resolve step to get its ULID
                                            try:
                                                # require_step takes workflow_selector (string), not workflow_id
                                                # We need to find the workflow slug/name from the directory
                                                workflow_slug = workflow_dir_name
                                                step_resolved = require_step(
                                                    project_root,
                                                    workflow_slug,
                                                    step_id,
                                                    config=config,
                                                )
                                                current_step_id = step_resolved.meta.id
                                            except Exception:
                                                pass  # Step not found, that's OK
                            except Exception:
                                pass  # Failed to parse workflow.yaml, that's OK
        except (ValueError, Exception):
            pass  # Not inside project or failed to detect, that's OK
        
        return cls(
            project_root=project_root,
            registry=registry,
            config=config,
            current_workflow_id=current_workflow_id,
            current_step_id=current_step_id,
        )


def resolve_workflow_for_cli(
    ctx: ProjectContext,
    workflow_option: Optional[str] = None,
) -> ResolvedResource:
    """
    Resolve workflow for CLI command.
    
    Resolution order:
    1. If workflow_option provided:
       - If ULID (26 chars starting with "01") → resolve by ID
       - If path-like → resolve by path
       - Otherwise → resolve by selector (slug/name)
    2. If no workflow_option:
       - If ctx.current_workflow_id → use that
       - If project has exactly one workflow → use that
       - Otherwise → raise error
    
    Args:
        ctx: ProjectContext
        workflow_option: Optional workflow selector/ID/path
        
    Returns:
        ResolvedResource for the workflow
        
    Raises:
        ResourceNotFoundError: If workflow not found or ambiguous
    """
    if workflow_option:
        # Check if it's a ULID
        workflow_option = workflow_option.strip()
        if len(workflow_option) == 26 and workflow_option.startswith("01"):
            # Treat as ULID
            return require_workflow(
                ctx.project_root,
                workflow_option,
                config=ctx.config,
                index=ctx.registry,
            )
        
        # Check if it's a path
        if "/" in workflow_option or workflow_option.startswith("workflows/"):
            # Try to resolve by path
            for workflow_id, meta in ctx.registry.by_id.items():
                if meta.kind == "workflow":
                    if meta.path == workflow_option or meta.path.endswith(f"/{workflow_option}"):
                        return require_workflow(
                            ctx.project_root,
                            workflow_id,
                            config=ctx.config,
                            index=ctx.registry,
                        )
        
        # Treat as selector (slug/name)
        return require_workflow(
            ctx.project_root,
            workflow_option,
            config=ctx.config,
            index=ctx.registry,
        )
    
    # No workflow_option provided - try auto-detection
    if ctx.current_workflow_id:
        return require_workflow(
            ctx.project_root,
            ctx.current_workflow_id,
            config=ctx.config,
            index=ctx.registry,
        )
    
    # Check if project has exactly one workflow
    workflows = ctx.config.get("workflows", [])
    if len(workflows) == 1:
        workflow_id = workflows[0].get("id") or workflows[0].get("workflow_id")
        if workflow_id:
            return require_workflow(
                ctx.project_root,
                workflow_id,
                config=ctx.config,
                index=ctx.registry,
            )
    
    # Ambiguous - need explicit workflow
    raise ResourceNotFoundError(
        kind="workflow",
        selector=None,
        project_root=ctx.project_root,
    )


def resolve_step_for_cli(
    ctx: ProjectContext,
    workflow_resolved: ResolvedResource,
    step_option: Optional[str] = None,
) -> ResolvedResource:
    """
    Resolve step for CLI command.
    
    Resolution order:
    1. If step_option provided:
       - If ULID → resolve by ID
       - Otherwise → resolve by selector (slug/name/type)
    2. If no step_option:
       - If ctx.current_step_id → use that
       - If workflow has exactly one step → use that
       - Otherwise → raise error
    
    Args:
        ctx: ProjectContext
        workflow_resolved: Resolved workflow resource
        step_option: Optional step selector/ID
        
    Returns:
        ResolvedResource for the step
        
    Raises:
        ResourceNotFoundError: If step not found or ambiguous
    """
    workflow_id = workflow_resolved.meta.id
    
    if step_option:
        step_option = step_option.strip()
        # require_step takes workflow_selector (string), not workflow_id
        # Use workflow's slug or name as selector
        workflow_selector = workflow_resolved.meta.slug or workflow_resolved.meta.name or workflow_id
        
        # Check if it's a ULID
        if len(step_option) == 26 and step_option.startswith("01"):
            return require_step(
                ctx.project_root,
                workflow_selector,
                step_option,
                config=ctx.config,
            )
        
        # Treat as selector
        return require_step(
            ctx.project_root,
            workflow_selector,
            step_option,
            config=ctx.config,
        )
    
    # No step_option provided - try auto-detection
    if ctx.current_step_id:
        workflow_selector = workflow_resolved.meta.slug or workflow_resolved.meta.name or workflow_id
        return require_step(
            ctx.project_root,
            workflow_selector,
            ctx.current_step_id,
            config=ctx.config,
        )
    
    # Check if workflow has exactly one step
    from quantumvitas.project.model import Project
    from quantumvitas.workflow.workflow import Workflow
    
    project = Project.open(ctx.project_root)
    # Use workflow selector (slug/name) to get workflow, not workflow_id
    workflow_selector = workflow_resolved.meta.slug or workflow_resolved.meta.name or workflow_id
    # Use inspection mode (no step materialization) for context resolution
    workflow = Workflow.from_yaml(workflow_resolved.absolute_path, project, materialize_steps=False)
    
    if len(workflow.steps) == 1:
        return require_step(
            ctx.project_root,
            workflow_selector,
            workflow.steps[0].meta.id,
            config=ctx.config,
        )
    
    # Ambiguous - need explicit step
    raise ResourceNotFoundError(
        kind="step",
        selector=None,
        project_root=ctx.project_root,
    )

