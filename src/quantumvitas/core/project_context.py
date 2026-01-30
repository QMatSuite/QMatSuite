"""
Project context helpers for CLI and service layer.

Provides ProjectContext and helpers for loading project context with registry,
resolving calculations/steps from CLI arguments, and detecting current context from cwd.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from quantumvitas.core.resolution import ResourceIndex, build_resource_index
from quantumvitas.core.project_utils import find_project_root, load_project_config
from quantumvitas.core.resolution import resolve_calculation, require_calculation, require_step
from quantumvitas.core.resolution import ResolvedResource, ResourceNotFoundError
from quantumvitas.core.selectors import extract_calculation_selector_from_entry


@dataclass
class ProjectContext:
    """
    Project context with registry for resource resolution.
    
    This is the canonical way to work with a project in CLI and service layer.
    It combines project_root, registry, and optional current calculation/step context.
    """
    project_root: Path
    registry: ResourceIndex
    config: dict
    current_calculation_id: Optional[str] = None
    current_step_ulid: Optional[str] = None
    
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
            project_root = require_project_root(cwd)
        
        # Load config and build registry
        config = load_project_config(project_root)
        registry = build_resource_index(project_root)
        
        # Try to detect current calculation/step from cwd
        current_calculation_id = None
        current_step_ulid = None
        
        try:
            rel_path = cwd.resolve().relative_to(project_root)
            # Check if inside calculations directory
            if str(rel_path).startswith("calculations/"):
                parts = rel_path.parts
                if len(parts) >= 2:
                    calculation_dir_name = parts[1]
                    calculation_dir = project_root / "calculations" / calculation_dir_name
                    if calculation_dir.exists():
                        calculation_yaml = calculation_dir / "calculation.yaml"
                        if calculation_yaml.exists():
                            import yaml
                            try:
                                wf_data = yaml.safe_load(calculation_yaml.read_text()) or {}
                                wf_meta = wf_data.get("meta") or {}
                                current_calculation_id = wf_meta.get("ulid")
                                
                                # Check if inside steps directory
                                if len(parts) >= 3 and parts[2] == "steps":
                                    if len(parts) >= 4:
                                        step_file_name = parts[3]
                                        if step_file_name.endswith(".step.yaml"):
                                            step_ulid = step_file_name.replace(".step.yaml", "")
                                            # Try to resolve step to get its ULID
                                            try:
                                                # require_step takes calculation_selector (string), not calculation_id
                                                # We need to find the calculation slug/name from the directory
                                                calculation_slug = calculation_dir_name
                                                step_resolved = require_step(
                                                    project_root,
                                                    calculation_slug,
                                                    step_ulid,
                                                    config=config,
                                                )
                                                current_step_ulid = step_resolved.meta.ulid
                                            except Exception:
                                                pass  # Step not found, that's OK
                            except Exception:
                                pass  # Failed to parse calculation.yaml, that's OK
        except (ValueError, Exception):
            pass  # Not inside project or failed to detect, that's OK
        
        return cls(
            project_root=project_root,
            registry=registry,
            config=config,
            current_calculation_id=current_calculation_id,
            current_step_ulid=current_step_ulid,
        )


def resolve_calculation_for_cli(
    ctx: ProjectContext,
    calculation_option: Optional[str] = None,
) -> ResolvedResource:
    """
    Resolve calculation for CLI command.
    
    Resolution order:
    1. If calculation_option provided:
       - If ULID (26 chars starting with "01") → resolve by ID
       - If path-like → resolve by path
       - Otherwise → resolve by selector (slug/name)
    2. If no calculation_option:
       - If ctx.current_calculation_id → use that
       - If project has exactly one calculation → use that
       - Otherwise → raise error
    
    Args:
        ctx: ProjectContext
        calculation_option: Optional calculation selector/ID/path
        
    Returns:
        ResolvedResource for the calculation
        
    Raises:
        ResourceNotFoundError: If calculation not found or ambiguous
    """
    if calculation_option:
        # Check if it's a ULID
        calculation_option = calculation_option.strip()
        if len(calculation_option) == 26 and calculation_option.startswith("01"):
            # Treat as ULID
            return require_calculation(
                ctx.project_root,
                calculation_option,
                config=ctx.config,
                index=ctx.registry,
            )
        
        # Check if it's a path
        if "/" in calculation_option or calculation_option.startswith("calculations/"):
            # Try to resolve by path
            for calculation_id, meta in ctx.registry.by_id.items():
                if meta.kind == "calculation":
                    if meta.path == calculation_option or meta.path.endswith(f"/{calculation_option}"):
                        return require_calculation(
                            ctx.project_root,
                            calculation_id,
                            config=ctx.config,
                            index=ctx.registry,
                        )
        
        # Treat as selector (slug/name)
        return require_calculation(
            ctx.project_root,
            calculation_option,
            config=ctx.config,
            index=ctx.registry,
        )
    
    # No calculation_option provided - try auto-detection
    if ctx.current_calculation_id:
        return require_calculation(
            ctx.project_root,
            ctx.current_calculation_id,
            config=ctx.config,
            index=ctx.registry,
        )
    
    # Check if project has exactly one calculation
    calculations = ctx.config.get("calculations", [])
    if len(calculations) == 1:
        # Use centralized selector extraction - single selector, single resolution pattern
        calculation_id = extract_calculation_selector_from_entry(calculations[0])
        if calculation_id:
            return require_calculation(
                ctx.project_root,
                calculation_id,
                config=ctx.config,
                index=ctx.registry,
            )
    
    # Ambiguous - need explicit calculation
    raise ResourceNotFoundError(
        kind="calculation",
        selector=None,
        project_root=ctx.project_root,
    )


def resolve_step_for_cli(
    ctx: ProjectContext,
    calculation_resolved: ResolvedResource,
    step_option: Optional[str] = None,
) -> ResolvedResource:
    """
    Resolve step for CLI command.
    
    Resolution order:
    1. If step_option provided:
       - If ULID → resolve by ID
       - Otherwise → resolve by selector (slug/name/type)
    2. If no step_option:
       - If ctx.current_step_ulid → use that
       - If calculation has exactly one step → use that
       - Otherwise → raise error
    
    Args:
        ctx: ProjectContext
        calculation_resolved: Resolved calculation resource
        step_option: Optional step selector/ID
        
    Returns:
        ResolvedResource for the step
        
    Raises:
        ResourceNotFoundError: If step not found or ambiguous
    """
    calculation_id = calculation_resolved.meta.ulid
    
    if step_option:
        step_option = step_option.strip()
        # require_step takes calculation_selector (string), not calculation_id
        # Use calculation's slug or name as selector
        calculation_selector = calculation_resolved.meta.slug or calculation_resolved.meta.name or calculation_id
        
        # Check if it's a ULID
        if len(step_option) == 26 and step_option.startswith("01"):
            return require_step(
                ctx.project_root,
                calculation_selector,
                step_option,
                config=ctx.config,
            )
        
        # Treat as selector
        return require_step(
            ctx.project_root,
            calculation_selector,
            step_option,
            config=ctx.config,
        )
    
    # No step_option provided - try auto-detection
    if ctx.current_step_ulid:
        calculation_selector = calculation_resolved.meta.slug or calculation_resolved.meta.name or calculation_id
        return require_step(
            ctx.project_root,
            calculation_selector,
            ctx.current_step_ulid,
            config=ctx.config,
        )
    
    # Check if calculation has exactly one step
    from quantumvitas.project.model import Project
    from quantumvitas.calculation.calculation import Calculation
    
    project = Project.open(ctx.project_root)
    # Use calculation selector (slug/name) to get calculation, not calculation_id
    calculation_selector = calculation_resolved.meta.slug or calculation_resolved.meta.name or calculation_id
    # Use inspection mode (no step materialization) for context resolution
    calculation = Calculation.from_yaml(calculation_resolved.absolute_path, project, materialize_steps=False)
    
    if len(calculation.steps) == 1:
        return require_step(
            ctx.project_root,
            calculation_selector,
            calculation.steps[0].meta.ulid,
            config=ctx.config,
        )
    
    # Ambiguous - need explicit step
    raise ResourceNotFoundError(
        kind="step",
        selector=None,
        project_root=ctx.project_root,
    )

