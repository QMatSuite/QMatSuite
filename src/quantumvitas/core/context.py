"""
PWD context helper for QuantumVITAS CLI.

Provides find_path_context_from_pwd() which scans upward from the current
directory to find the project root and any enclosing calculation/step context.

This module is the ONLY place that uses Path.cwd() for resource discovery.
The API layer and resolution layer never use cwd directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Literal, Optional


ContextNodeKind = Literal["project", "calculation", "step", "structure", "other"]


@dataclass(slots=True)
class ContextNode:
    """
    A node in the path context chain.
    
    Represents one level of the directory hierarchy that has semantic meaning
    (project root, calculation directory, step file, etc.).
    """
    kind: ContextNodeKind
    directory: Path
    yaml_path: Optional[Path] = None  # Path to the YAML file if applicable
    selector: Optional[str] = None  # Inferred slug or name for this resource
    
    def __repr__(self) -> str:
        return f"ContextNode(kind={self.kind!r}, dir={self.directory.name!r}, selector={self.selector!r})"


@dataclass
class PathContext:
    """
    Result of find_path_context_from_pwd().
    
    Contains the project root and an ordered list of context nodes from
    project → calculation → step (as applicable based on cwd location).
    """
    project_root: Path
    nodes: List[ContextNode] = field(default_factory=list)
    
    @property
    def calculation_node(self) -> Optional[ContextNode]:
        """Get the calculation node if we're inside a calculation."""
        for node in self.nodes:
            if node.kind == "calculation":
                return node
        return None
    
    @property
    def step_node(self) -> Optional[ContextNode]:
        """Get the step node if we're inside/at a step."""
        for node in self.nodes:
            if node.kind == "step":
                return node
        return None
    
    @property
    def calculation_selector(self) -> Optional[str]:
        """
        Get calculation selector if inside a calculation.
        
        .. deprecated:: 2025-12-XX
            This property reads the selector from calculation.yaml, which may be stale after renames.
            For CLI auto-detection, use `find_enclosing_calculation()` from `core/project_utils.py` instead,
            which uses directory path matching against project.qv.yml (the source of truth).
            
            This property is kept for backward compatibility but should not be used for calculation resolution.
        """
        node = self.calculation_node
        return node.selector if node else None
    
    @property
    def calculation_directory(self) -> Optional[Path]:
        """Get calculation directory if inside a calculation."""
        node = self.calculation_node
        return node.directory if node else None
    
    def is_inside_calculation(self) -> bool:
        """Check if cwd is inside a calculation directory."""
        return self.calculation_node is not None
    
    def is_inside_project(self) -> bool:
        """Check if a project was found."""
        return self.project_root is not None


class ContextNotFoundError(ValueError):
    """Raised when no project context can be found from cwd."""
    pass


def find_path_context_from_pwd(
    start: Optional[Path] = None,
    max_depth: int = 20,
) -> PathContext:
    """
    Scan upward from the current directory to find project context.
    
    This function walks up the directory tree looking for project.qv.yml.
    Once found, it examines the path from project root to start directory
    to identify any enclosing calculation or step context.
    
    Args:
        start: Starting directory (defaults to cwd)
        max_depth: Maximum directories to scan upward
        
    Returns:
        PathContext with project_root and context nodes
        
    Raises:
        ContextNotFoundError: If no project.qv.yml found within max_depth
    """
    start_path = Path(start or Path.cwd()).resolve()
    
    # Phase 1: Find project root by walking up
    project_root = _find_project_root(start_path, max_depth)
    if project_root is None:
        raise ContextNotFoundError(
            f"No project.qv.yml found within {max_depth} directories of {start_path}"
        )
    
    # Phase 2: Build context chain from project root to start
    nodes = _build_context_chain(project_root, start_path)
    
    return PathContext(project_root=project_root, nodes=nodes)


def _find_project_root(start: Path, max_depth: int) -> Optional[Path]:
    """Walk up to find project.qv.yml."""
    current = start
    depth = 0
    
    while depth <= max_depth:
        if (current / "project.qv.yml").exists():
            return current
        
        parent = current.parent
        if parent == current:
            # Reached filesystem root
            break
        
        current = parent
        depth += 1
    
    return None


def detect_enclosing_project(path: Path, max_depth: int = 20) -> Optional[Path]:
    """
    Walk upward from `path` looking for `project.qv.yml`.
    
    Return the project root if found, otherwise None.
    Does NOT look at cwd, only the given path.
    
    Args:
        path: Starting path to search from
        max_depth: Maximum directories to scan upward
        
    Returns:
        Path to project root if found, None otherwise
    """
    path = Path(path).resolve()
    return _find_project_root(path, max_depth)


def _build_context_chain(project_root: Path, start_path: Path) -> List[ContextNode]:
    """Build the context node chain from project root to start."""
    nodes: List[ContextNode] = []
    
    # Add project node
    project_yaml = project_root / "project.qv.yml"
    project_name = _extract_project_name(project_yaml)
    nodes.append(ContextNode(
        kind="project",
        directory=project_root,
        yaml_path=project_yaml,
        selector=project_name,
    ))
    
    # Check if start is inside project
    try:
        rel_path = start_path.relative_to(project_root)
    except ValueError:
        # Start is not inside project (shouldn't happen if project_root was found)
        return nodes
    
    # Check if inside calculations directory
    if _is_inside_directory(start_path, project_root / "calculations"):
        calculation_node = _find_calculation_context(project_root, start_path)
        if calculation_node:
            nodes.append(calculation_node)
            
            # Check if inside steps directory
            steps_dir = calculation_node.directory / "steps"
            if _is_inside_directory(start_path, steps_dir):
                step_node = _find_step_context(calculation_node.directory, start_path)
                if step_node:
                    nodes.append(step_node)
    
    # Check if inside structures directory
    elif _is_inside_directory(start_path, project_root / "structures"):
        structure_node = _find_structure_context(project_root, start_path)
        if structure_node:
            nodes.append(structure_node)
    
    return nodes


def _is_inside_directory(path: Path, directory: Path) -> bool:
    """Check if path is inside or equal to directory."""
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def _extract_project_name(yaml_path: Path) -> str:
    """Extract project name from project.qv.yml."""
    try:
        from quantumvitas.core.yamldoc import ProjectDoc
        data = ProjectDoc.load(yaml_path).to_dict()
        project_section = data.get("project", {})
        meta = project_section.get("meta") or {}
        return meta.get("name") or project_section.get("name") or yaml_path.parent.name
    except Exception:
        return yaml_path.parent.name


def _find_calculation_context(project_root: Path, start_path: Path) -> Optional[ContextNode]:
    """Find the calculation context if start is inside a calculation."""
    calculations_dir = project_root / "calculations"
    
    # Get path relative to calculations dir
    try:
        rel_to_calculations = start_path.relative_to(calculations_dir)
    except ValueError:
        return None
    
    # First part of the relative path is the calculation directory name
    parts = rel_to_calculations.parts
    if not parts:
        # We're at calculations/ directory itself
        return None
    
    calculation_dir_name = parts[0]
    calculation_dir = calculations_dir / calculation_dir_name
    
    if not calculation_dir.is_dir():
        return None
    
    # Look for calculation.yaml
    calculation_yaml = calculation_dir / "calculation.yaml"
    selector = _extract_calculation_selector(calculation_yaml, calculation_dir_name)
    
    return ContextNode(
        kind="calculation",
        directory=calculation_dir,
        yaml_path=calculation_yaml if calculation_yaml.exists() else None,
        selector=selector,
    )


def _extract_calculation_selector(yaml_path: Path, fallback: str) -> str:
    """Extract calculation slug/name from calculation.yaml."""
    if not yaml_path.exists():
        return fallback
    
    try:
        from quantumvitas.core.yaml_io import load_yaml_doc
        data = load_yaml_doc(yaml_path).to_dict()
        meta = data.get("meta") or {}
        return meta.get("slug") or meta.get("name") or fallback
    except Exception:
        return fallback


def _find_step_context(calculation_dir: Path, start_path: Path) -> Optional[ContextNode]:
    """Find step context if start is at or inside steps directory."""
    steps_dir = calculation_dir / "steps"
    
    try:
        rel_to_steps = start_path.relative_to(steps_dir)
    except ValueError:
        return None
    
    # If we're inside steps dir but not at a specific step file
    if not rel_to_steps.parts:
        return None
    
    # Check if we're at a specific step
    first_part = rel_to_steps.parts[0]
    
    # Could be a directory or we might find a matching .step.yaml
    candidate_yaml = steps_dir / f"{first_part}.step.yaml"
    if candidate_yaml.exists():
        selector = _extract_step_selector(candidate_yaml, first_part)
        return ContextNode(
            kind="step",
            directory=steps_dir,
            yaml_path=candidate_yaml,
            selector=selector,
        )
    
    # Check if start_path itself is a step yaml
    if start_path.suffix in (".yaml", ".yml") and ".step" in start_path.name:
        selector = _extract_step_selector(start_path, start_path.stem.replace(".step", ""))
        return ContextNode(
            kind="step",
            directory=steps_dir,
            yaml_path=start_path,
            selector=selector,
        )
    
    return None


def _extract_step_selector(yaml_path: Path, fallback: str) -> str:
    """Extract step id/type from step.yaml."""
    if not yaml_path.exists():
        return fallback
    
    try:
        from quantumvitas.core.yaml_io import load_yaml_doc
        data = load_yaml_doc(yaml_path).to_dict()
        return data.get("ulid") or data.get("step_type_spec") or fallback
    except Exception:
        return fallback


def _find_structure_context(project_root: Path, start_path: Path) -> Optional[ContextNode]:
    """Find structure context if start is inside structures directory."""
    structures_dir = project_root / "structures"
    
    try:
        rel_to_structures = start_path.relative_to(structures_dir)
    except ValueError:
        return None
    
    # If start is a structure file
    if start_path.is_file() and start_path.suffix in (".json", ".yaml", ".yml", ".cif"):
        return ContextNode(
            kind="structure",
            directory=structures_dir,
            yaml_path=start_path if start_path.suffix in (".json", ".yaml", ".yml") else None,
            selector=start_path.stem,
        )
    
    return None


# ---------------------------------------------------------------------------
# Convenience functions for CLI
# ---------------------------------------------------------------------------


def get_project_root_from_pwd(start: Optional[Path] = None, max_depth: int = 20) -> Path:
    """
    Get just the project root from pwd, without full context.
    
    Raises:
        ContextNotFoundError: If no project found
    """
    ctx = find_path_context_from_pwd(start, max_depth)
    return ctx.project_root


def get_calculation_from_pwd(start: Optional[Path] = None) -> Optional[str]:
    """
    Get calculation selector if cwd is inside a calculation, None otherwise.
    
    .. deprecated:: 2025-12-XX
        This function uses `PathContext.calculation_selector`, which reads from calculation.yaml
        and may be stale after renames. Use `find_enclosing_calculation()` from `core/project_utils.py`
        instead, which uses directory path matching against project.qv.yml.
        
        This function is kept for backward compatibility but should not be used for calculation resolution.
    """
    try:
        ctx = find_path_context_from_pwd(start)
        return ctx.calculation_selector
    except ContextNotFoundError:
        return None

