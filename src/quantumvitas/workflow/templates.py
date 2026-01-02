"""
Workflow templates and detection.

This module provides:
- WorkflowTemplate: Definition of calculation workflows
- WorkflowMatch: Result of workflow detection
- WorkflowService: Detection, instantiation, validation

Per docs/workflow_refactor_plan.md:
- Workflows are runtime interpretations, never persisted
- Detection derives workflow from YAML on disk
- Instantiation creates steps through step factory (journaled)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Tuple


@dataclass(frozen=True)
class WorkflowTemplate:
    """
    Definition of a calculation workflow.
    
    Attributes:
        id: Workflow identifier (e.g., "dos", "bands")
        name: Human-readable name
        description: Description of what the workflow computes
        step_sequence: Ordered tuple of step_type ids
        optional_steps: Step types that may be omitted
    """
    id: str
    name: str
    description: str
    step_sequence: Tuple[str, ...]
    optional_steps: FrozenSet[str] = field(default_factory=frozenset)


@dataclass
class WorkflowMatch:
    """
    Result of workflow detection.
    
    Attributes:
        workflow_id: Best matching workflow (None if no match)
        workflow_name: Human-readable name
        coverage: Match coverage (0.0 to 1.0)
        present_steps: Step types found in calculation
        missing_steps: Required steps not found
        extra_steps: Steps not in template
        ordering_valid: Whether step order matches template
    """
    workflow_id: Optional[str]
    workflow_name: str
    coverage: float
    present_steps: List[str]
    missing_steps: List[str]
    extra_steps: List[str]
    ordering_valid: bool


@dataclass
class WorkflowIssue:
    """A workflow validation issue."""
    severity: str  # "error", "warning"
    message: str
    step_type: Optional[str] = None


# =============================================================================
# Workflow Templates (v0)
# =============================================================================

_WORKFLOWS: Dict[str, WorkflowTemplate] = {
    "scf": WorkflowTemplate(
        id="scf",
        name="SCF",
        description="Self-consistent field calculation (ground state energy)",
        step_sequence=("scf",),
    ),
    "relax": WorkflowTemplate(
        id="relax",
        name="Relaxation",
        description="Atomic relaxation (optimize positions, fixed cell)",
        step_sequence=("relax",),
    ),
    "vc-relax": WorkflowTemplate(
        id="vc-relax",
        name="Full Relaxation",
        description="Variable-cell relaxation (optimize positions and cell)",
        step_sequence=("vc-relax",),
    ),
    "dos": WorkflowTemplate(
        id="dos",
        name="Density of States",
        description="Electronic density of states calculation",
        step_sequence=("scf", "nscf", "dos"),
    ),
    "bands": WorkflowTemplate(
        id="bands",
        name="Band Structure",
        description="Electronic band structure along k-path",
        step_sequence=("scf", "bands_pw", "bands"),
    ),
    "pdos": WorkflowTemplate(
        id="pdos",
        name="Projected DOS",
        description="Atom/orbital-resolved density of states",
        step_sequence=("scf", "nscf", "projwfc"),
    ),
}


# =============================================================================
# WorkflowService
# =============================================================================


class WorkflowService:
    """
    Service for workflow operations.
    
    Provides:
    - List available workflow templates
    - Detect workflow from existing calculation
    - Instantiate workflow (create steps)
    - Validate workflow consistency
    """
    
    def __init__(self, workflows: Optional[Dict[str, WorkflowTemplate]] = None):
        """
        Initialize service.
        
        Args:
            workflows: Optional custom workflows (for testing)
        """
        self._workflows = workflows if workflows is not None else _WORKFLOWS.copy()
    
    def list_templates(self) -> List[WorkflowTemplate]:
        """List all available workflow templates."""
        return sorted(self._workflows.values(), key=lambda w: w.id)
    
    def get_template(self, workflow_id: str) -> Optional[WorkflowTemplate]:
        """Get a workflow template by id."""
        return self._workflows.get(workflow_id)
    
    def detect_workflow(self, calc_dir: Path) -> WorkflowMatch:
        """
        Detect workflow type from a calculation's step sequence.
        
        Args:
            calc_dir: Path to calculation directory
            
        Returns:
            WorkflowMatch with best matching workflow
        """
        from quantumvitas.core.yamldoc import CalcDoc
        
        calc_dir = Path(calc_dir).resolve()
        
        # Load calculation.yaml
        calc_yaml = calc_dir / "calculation.yaml"
        if not calc_yaml.exists():
            return WorkflowMatch(
                workflow_id=None,
                workflow_name="Unknown",
                coverage=0.0,
                present_steps=[],
                missing_steps=[],
                extra_steps=[],
                ordering_valid=False,
            )
        
        try:
            calc_doc = CalcDoc.load(calc_yaml)
            steps = calc_doc.export_copy(["steps"]) if calc_doc.has(["steps"]) else []
        except Exception:
            return WorkflowMatch(
                workflow_id=None,
                workflow_name="Unknown",
                coverage=0.0,
                present_steps=[],
                missing_steps=[],
                extra_steps=[],
                ordering_valid=False,
            )
        
        # Collect step types in order from calculation.yaml.steps[] (authoritative)
        # Per Constitution: steps[] is single source of truth, do NOT scan filesystem
        present_steps: List[str] = []
        from quantumvitas.core.project_utils import find_project_root
        project_root = find_project_root(calc_dir)
        
        for step_entry in steps:
            step_type = None
            
            # Try new format first: step_id (ULID) -> resolve step -> get step_type
            # This requires project_root to be available
            step_ulid = step_entry.get("step_id")
            if step_ulid and project_root:
                try:
                    from quantumvitas.core.resolution import resolve_step
                    from quantumvitas.core.project_utils import load_project_config
                    config = load_project_config(project_root)
                    resolved_step = resolve_step(project_root, None, step_ulid, config=config)
                    
                    # Load step YAML to get step_type
                    from quantumvitas.core.yamldoc import StepDoc
                    step_doc = StepDoc.load(resolved_step.absolute_path)
                    step_type = step_doc.get(["step_type"], default=None)
                except Exception:
                    # Step file missing or invalid - skip it (ghost step)
                    pass
            
            # Fallback to legacy format: step_type directly in entry, or type field
            if not step_type:
                step_type = step_entry.get("step_type") or step_entry.get("type")
            
            # Also try resolving by file path (legacy format)
            if not step_type:
                step_file = step_entry.get("file")
                if step_file:
                    step_path = calc_dir / step_file
                    if step_path.exists():
                        try:
                            from quantumvitas.core.yamldoc import StepDoc
                            step_doc = StepDoc.load(step_path)
                            step_type = step_doc.get(["step_type"], default=None)
                        except Exception:
                            pass
            
            if step_type:
                present_steps.append(step_type)
        
        # Find best matching workflow
        # Prefer: 1) 100% coverage, 2) longer workflow with 100% coverage, 3) highest coverage
        best_match: Optional[WorkflowMatch] = None
        best_score = (-1.0, 0)  # (coverage, workflow_length for tiebreaker)
        
        for workflow in self._workflows.values():
            required_steps = set(workflow.step_sequence) - workflow.optional_steps
            present_set = set(present_steps)
            
            # Calculate coverage
            if required_steps:
                covered = len(required_steps & present_set) / len(required_steps)
            else:
                covered = 1.0 if present_set <= set(workflow.step_sequence) else 0.0
            
            missing = list(required_steps - present_set)
            extra = list(present_set - set(workflow.step_sequence))
            
            # Check ordering (for matching steps)
            ordering_valid = self._check_ordering(present_steps, workflow.step_sequence)
            
            # Score: prefer 100% coverage, then longer workflows
            workflow_len = len(workflow.step_sequence)
            score = (covered, workflow_len if covered == 1.0 else 0)
            
            if score > best_score:
                best_score = score
                best_match = WorkflowMatch(
                    workflow_id=workflow.id,
                    workflow_name=workflow.name,
                    coverage=covered,
                    present_steps=present_steps,
                    missing_steps=missing,
                    extra_steps=extra,
                    ordering_valid=ordering_valid,
                )
        
        if best_match is None:
            return WorkflowMatch(
                workflow_id=None,
                workflow_name="Unknown",
                coverage=0.0,
                present_steps=present_steps,
                missing_steps=[],
                extra_steps=present_steps,
                ordering_valid=False,
            )
        
        return best_match
    
    def _check_ordering(self, present: List[str], template: Tuple[str, ...]) -> bool:
        """Check if present steps maintain template ordering."""
        if not present:
            return True
        
        template_indices = {step: i for i, step in enumerate(template)}
        
        # Filter to steps in template
        filtered = [s for s in present if s in template_indices]
        if not filtered:
            return True
        
        # Check ordering
        prev_idx = -1
        for step in filtered:
            idx = template_indices[step]
            if idx < prev_idx:
                return False
            prev_idx = idx
        
        return True
    
    def instantiate_workflow(
        self,
        workflow_id: str,
        calc_dir: Path,
        structure_id: str,
        parent_calculation_id: str,
    ) -> List[Path]:
        """
        Instantiate a workflow by creating its steps.
        
        Args:
            workflow_id: Workflow template id
            calc_dir: Path to calculation directory
            structure_id: Structure ULID
            parent_calculation_id: Parent calculation ULID
            
        Returns:
            List of created step file paths
            
        Raises:
            ValueError: If workflow not found
        """
        from quantumvitas.workflow.step_factory import create_step_doc, save_step_doc
        
        workflow = self.get_template(workflow_id)
        if workflow is None:
            raise ValueError(f"Unknown workflow: {workflow_id}")
        
        calc_dir = Path(calc_dir).resolve()
        steps_dir = calc_dir / "steps"
        steps_dir.mkdir(exist_ok=True)
        
        created_paths: List[Path] = []
        created_step_ulids: List[str] = []
        
        for step_type in workflow.step_sequence:
            # Create step document
            step_doc = create_step_doc(
                step_type=step_type,
                name=step_type,
                structure_id=structure_id,
                parent_calculation_id=parent_calculation_id,
            )
            
            # Determine path
            slug = step_doc.get(["meta", "slug"])
            step_path = steps_dir / f"{slug}.step.yaml"
            
            # Save (journaled)
            save_step_doc(step_doc, step_path)
            created_paths.append(step_path)
            
            # Collect step ULID for calc steps[] update
            step_ulid = step_doc.get(["meta", "id"])
            created_step_ulids.append(step_ulid)
        
        # Update calculation.yaml.steps[] with created steps (authoritative)
        # Per Constitution: steps[] is single source of truth
        from quantumvitas.api import QVService
        from quantumvitas.core.project_utils import find_project_root
        
        # Find project root (calc_dir is calculations/{slug}/)
        project_root = find_project_root(calc_dir)
        if project_root is None:
            raise ValueError(f"Cannot find project root from {calc_dir}")
        
        QVService.calc_set_steps(
            project_root=project_root,
            calculation_ulid=parent_calculation_id,
            ordered_step_ulids=created_step_ulids,
        )
        
        return created_paths
    
    def validate_workflow(
        self,
        calc_dir: Path,
        workflow_id: Optional[str] = None,
    ) -> List[WorkflowIssue]:
        """
        Validate workflow consistency.
        
        Args:
            calc_dir: Path to calculation directory
            workflow_id: Optional workflow to validate against
            
        Returns:
            List of validation issues
        """
        issues: List[WorkflowIssue] = []
        
        # Detect current workflow
        match = self.detect_workflow(calc_dir)
        
        if workflow_id:
            workflow = self.get_template(workflow_id)
            if workflow is None:
                issues.append(WorkflowIssue(
                    severity="error",
                    message=f"Unknown workflow: {workflow_id}",
                ))
                return issues
            
            # Check for missing steps
            required_steps = set(workflow.step_sequence) - workflow.optional_steps
            present_set = set(match.present_steps)
            
            for step in required_steps - present_set:
                issues.append(WorkflowIssue(
                    severity="error",
                    message=f"Missing required step: {step}",
                    step_type=step,
                ))
            
            # Check for ordering
            if not match.ordering_valid:
                issues.append(WorkflowIssue(
                    severity="warning",
                    message="Step ordering does not match workflow template",
                ))
        
        # General validation
        from quantumvitas.workflow.registry import get_registry
        registry = get_registry()
        
        for step_type in match.present_steps:
            if not registry.has(step_type):
                issues.append(WorkflowIssue(
                    severity="warning",
                    message=f"Unknown step type: {step_type}",
                    step_type=step_type,
                ))
        
        return issues


# =============================================================================
# Global Service Instance
# =============================================================================

_service: Optional[WorkflowService] = None


def get_workflow_service() -> WorkflowService:
    """Get the global workflow service."""
    global _service
    if _service is None:
        _service = WorkflowService()
    return _service


def reset_workflow_service() -> None:
    """Reset global service (for testing)."""
    global _service
    _service = None

