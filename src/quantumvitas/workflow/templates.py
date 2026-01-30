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
    step_type_gen: Optional[str] = None  # GEN step type that caused the issue


# =============================================================================
# Workflow Templates (v0)
# =============================================================================

_WORKFLOWS: Dict[str, WorkflowTemplate] = {
    # Phase 2: Workflows use public/generalized step keys (lowercase legacy names)
    # Materialization happens during instantiation based on calc.engine_family
    "scf": WorkflowTemplate(
        id="scf",
        name="SCF",
        description="Self-consistent field calculation (ground state energy)",
        step_sequence=("scf",),  # Public generalized step key
    ),
    "relax": WorkflowTemplate(
        id="relax",
        name="Relaxation",
        description="Atomic relaxation (optimize positions, fixed cell)",
        step_sequence=("relax",),  # Public generalized step key
    ),
    "vc-relax": WorkflowTemplate(
        id="vc-relax",
        name="Full Relaxation",
        description="Variable-cell relaxation (optimize positions and cell)",
        step_sequence=("vc-relax",),  # Public generalized step key
    ),
    "dos": WorkflowTemplate(
        id="dos",
        name="Density of States",
        description="Electronic density of states calculation",
        step_sequence=("scf", "nscf", "dos"),  # Public generalized step keys
    ),
    "bands": WorkflowTemplate(
        id="bands",
        name="Band Structure",
        description="Electronic band structure along k-path",
        step_sequence=("scf", "bands_pw", "bands"),  # Public generalized step keys
    ),
    "pdos": WorkflowTemplate(
        id="pdos",
        name="Projected DOS",
        description="Atom/orbital-resolved density of states",
        step_sequence=("scf", "nscf", "dos"),  # Public generalized step keys
    ),
    "wannier": WorkflowTemplate(
        id="wannier",
        name="Wannierization",
        description="Maximally localized Wannier functions",
        step_sequence=("scf", "nscf", "pw2wannier90", "w90_run"),  # Public generalized step keys
    ),
    "scf_mp2": WorkflowTemplate(
        id="scf_mp2",
        name="SCF + MP2",
        description="Self-consistent field calculation followed by MP2 correlation energy",
        step_sequence=("scf", "mp2"),  # Public generalized step keys
    ),
    "scf_td": WorkflowTemplate(
        id="scf_td",
        name="SCF + Excited States",
        description="Self-consistent field calculation followed by time-dependent excited states (TDDFT/TDHF)",
        step_sequence=("scf", "td"),  # Phase 3C: Generalized "td" key
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
        
        import logging
        from quantumvitas.core.debug import is_resolution_debug_enabled
        
        logger = logging.getLogger(__name__)
        debug_enabled = is_resolution_debug_enabled()
        
        # Collect step types in order from calculation.yaml.steps[] (authoritative)
        # Per Constitution: steps[] is single source of truth, do NOT scan filesystem
        present_steps: List[str] = []
        from quantumvitas.core.project_utils import find_project_root
        project_root = find_project_root(calc_dir)
        
        logger.info(
            f"[WORKFLOW_DETECT] Starting workflow detection for calc_dir={calc_dir}, "
            f"project_root={project_root}, steps_count={len(steps)}"
        )
        
        for i, step_entry in enumerate(steps):
            step_type = None
            step_ulid = step_entry.get("step_ulid")
            step_entry_type = step_entry.get("step_type_spec")
            
            logger.info(
                f"[WORKFLOW_DETECT] Processing step entry {i+1}/{len(steps)}: "
                f"step_ulid={step_ulid}, type_in_entry={step_entry_type}"
            )
            
            # Try new format first: step_ulid (ULID) -> resolve step -> get step_type
            # This requires project_root to be available
            if step_ulid and project_root:
                try:
                    from quantumvitas.core.resolution import resolve_step
                    from quantumvitas.core.project_utils import load_project_config
                    config = load_project_config(project_root)
                    
                    # Resolve calculation first to get calculation_ulid
                    # We need calc_dir to find the calculation
                    calc_yaml = calc_dir / "calculation.yaml"
                    if calc_yaml.exists():
                        from quantumvitas.core.yamldoc import CalcDoc
                        calc_doc = CalcDoc.load(calc_yaml)
                        calculation_ulid = calc_doc.get(["meta", "ulid"], default=None) or calc_doc.get(["meta", "id"], default=None)
                        
                        if calculation_ulid:
                            resolved_step = resolve_step(
                                project_root, 
                                calculation_ulid,  # Use calculation_ulid, not None
                                step_ulid, 
                                config=config
                            )
                            
                            # Load step YAML to get step_type
                            from quantumvitas.core.yamldoc import StepDoc
                            step_doc = StepDoc.load(resolved_step.absolute_path)
                            step_type = step_doc.get(["step_type_spec"], default=None)
                            if debug_enabled:
                                logger.info(
                                    f"[WORKFLOW_DETECT] Resolved step by ULID: step_ulid={step_ulid} -> "
                                    f"step_type={step_type} (from step YAML)"
                                )
                        else:
                            if debug_enabled:
                                logger.warning(
                                    f"[WORKFLOW_DETECT] Cannot resolve step by ULID: calculation_ulid not found in calculation.yaml"
                                )
                    else:
                        if debug_enabled:
                            logger.warning(
                                f"[WORKFLOW_DETECT] Cannot resolve step by ULID: calculation.yaml not found at {calc_yaml}"
                            )
                except Exception as e:
                    # Step file missing or invalid - skip it (ghost step)
                    if debug_enabled:
                        logger.warning(
                            f"[WORKFLOW_DETECT] Failed to resolve step by ULID: step_ulid={step_ulid}, "
                            f"error={type(e).__name__}: {e}"
                        )
                    pass
            
            # Fallback to legacy format: step_type directly in entry, or type field
            if not step_type:
                step_type = step_entry_type
                if step_type:
                    if debug_enabled:
                        logger.info(
                            f"[WORKFLOW_DETECT] Using type from calculation.yaml.steps[] entry: "
                            f"step_ulid={step_ulid}, type={step_type}"
                        )
                else:
                    # Always log warnings about missing type field (not gated)
                    logger.warning(
                        f"[WORKFLOW_DETECT] WARNING: Step entry has no type field! "
                        f"step_ulid={step_ulid}, entry_keys={list(step_entry.keys())}. "
                        f"Workflow detection may fail or be inaccurate."
                    )
            
            # Also try resolving by file path (legacy format)
            if not step_type:
                step_file = step_entry.get("file")
                if step_file:
                    step_path = calc_dir / step_file
                    if step_path.exists():
                        try:
                            from quantumvitas.core.yamldoc import StepDoc
                            step_doc = StepDoc.load(step_path)
                            step_type = step_doc.get(["step_type_spec"], default=None)
                            if debug_enabled:
                                logger.info(
                                    f"[WORKFLOW_DETECT] Resolved step by file path: "
                                    f"file={step_file} -> step_type={step_type}"
                                )
                        except Exception:
                            pass
            
            if step_type:
                # Phase 2: Map engine-specific step type (step_type_spec) to gen type for workflow detection
                from quantumvitas.workflow.registry import get_registry
                registry = get_registry()
                spec = registry.get(step_type)  # Accepts both gen and spec types
                if spec:
                    # Use gen type for workflow detection (workflows use gen types)
                    gen_type = spec.step_type_gen
                    present_steps.append(gen_type)
                    if debug_enabled:
                        logger.info(
                            f"[WORKFLOW_DETECT] Step {i+1} mapped: {step_type} -> {gen_type}"
                        )
                else:
                    # Fallback: use step_type as-is (may be public type already)
                    present_steps.append(step_type)
                    if debug_enabled:
                        logger.warning(
                            f"[WORKFLOW_DETECT] Step {i+1} not found in registry: {step_type}"
                        )
                if debug_enabled:
                    logger.info(
                        f"[WORKFLOW_DETECT] Step {i+1} added to present_steps: {present_steps[-1]}"
                    )
            else:
                if debug_enabled:
                    logger.warning(
                        f"[WORKFLOW_DETECT] Step {i+1} could not be resolved: "
                        f"step_ulid={step_ulid}, no step_type found"
                    )
        
        if debug_enabled:
            logger.info(
                f"[WORKFLOW_DETECT] Collected present_steps: {present_steps} "
                f"(from {len(steps)} step entries)"
            )
        
        # Find best matching workflow
        # Prefer: 1) 100% coverage, 2) longer workflow with 100% coverage, 3) highest coverage
        best_match: Optional[WorkflowMatch] = None
        best_score = (-1.0, 0)  # (coverage, workflow_length for tiebreaker)
        
        for workflow in self._workflows.values():
            # Phase 2: Workflow templates use generalized steps
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
        structure_ulid: str,
        parent_calculation_id: str,
        *,
        engine_family: Optional[str] = None,
    ) -> List[Path]:
        """
        Instantiate a workflow by creating its steps.
        
        Phase 2: Materializes generalized steps to engine-specific steps based on engine_family.
        
        Args:
            workflow_id: Workflow template id
            calc_dir: Path to calculation directory
            structure_ulid: Structure ULID
            parent_calculation_id: Parent calculation ULID
            engine_family: Engine family identifier (e.g., "qe", "pyscf")
                If None, attempts to load from calculation.yaml
            
        Returns:
            List of created step file paths
            
        Raises:
            ValueError: If workflow not found or materialization fails
        """
        from quantumvitas.workflow.step_factory import create_step_doc, save_step_doc
        from quantumvitas.workflow.generalized_steps import materialize_workflow
        from quantumvitas.core.models import CalculationModel
        
        workflow = self.get_template(workflow_id)
        if workflow is None:
            raise ValueError(f"Unknown workflow: {workflow_id}")
        
        calc_dir = Path(calc_dir).resolve()
        steps_dir = calc_dir / "steps"
        steps_dir.mkdir(exist_ok=True)
        
        # Get engine_family from calculation if not provided
        if engine_family is None:
            calc_yaml_path = calc_dir / "calculation.yaml"
            if calc_yaml_path.exists():
                import yaml
                calc_data = yaml.safe_load(calc_yaml_path.read_text())
                engine_family = calc_data.get("engine_family")
            
            # Fallback to default (qe)
            if engine_family is None:
                engine_family = "qe"
        
        # Phase 3B: Materialize PUBLIC step keys to MACHINE step types using engine_family
        # Workflow templates use PUBLIC step keys (lowercase like "scf"), materialize to MACHINE types (like "qe_scf")
        from quantumvitas.workflow.generalized_steps import materialize_public_step_key
        
        machine_steps = []
        unsupported_steps = []
        for public_step_key in workflow.step_sequence:
            # Materialize PUBLIC key to MACHINE type using engine_family
            machine_step = materialize_public_step_key(public_step_key, engine_family)
            if machine_step is None:
                unsupported_steps.append(public_step_key)
            else:
                machine_steps.append(machine_step)
        
        # Phase 3B: Raise clear error if any steps are unsupported
        if unsupported_steps:
            raise ValueError(
                f"Workflow '{workflow_id}' contains steps not supported by engine family '{engine_family}': {unsupported_steps}"
            )
        
        # Keep public steps for calculation.yaml (templates already use PUBLIC keys)
        public_steps = list(workflow.step_sequence)
        
        created_paths: List[Path] = []
        created_step_ulids: List[str] = []
        
        for machine_step in machine_steps:
            # Create step document with machine step type (for step.yaml)
            step_doc = create_step_doc(
                step_type=machine_step,  # Machine type goes to step.yaml
                name=machine_step,  # TODO: Use public step name for display
                structure_ulid=structure_ulid,
                parent_calculation_id=parent_calculation_id,
            )
            
            # Determine path
            slug = step_doc.get(["meta", "slug"])
            step_path = steps_dir / f"{slug}.step.yaml"
            
            # Save (journaled)
            save_step_doc(step_doc, step_path)
            created_paths.append(step_path)
            
            # Collect step ULID for calc steps[] update
            step_ulid = step_doc.get(["meta", "ulid"])
            created_step_ulids.append(step_ulid)
        
        # Update calculation.yaml.steps[] with created steps (authoritative)
        # Per Constitution: steps[] is single source of truth
        from quantumvitas.core.models import set_calculation_steps
        from quantumvitas.core.project_utils import find_project_root

        # Find project root (calc_dir is calculations/{slug}/)
        project_root = find_project_root(calc_dir)
        if project_root is None:
            raise ValueError(f"Cannot find project root from {calc_dir}")

        # Build step_types mapping: step_ulid -> PUBLIC step_type (for calculation.yaml)
        # calculation.yaml stores public types, step.yaml stores machine types
        step_types = {}
        for public_step, step_ulid in zip(public_steps, created_step_ulids):
            step_types[step_ulid] = public_step  # Store public type in calculation.yaml

        set_calculation_steps(
            project_root=project_root,
            calculation_ulid=parent_calculation_id,
            ordered_step_ulids=created_step_ulids,
            step_types=step_types,  # Provide step types for canonical metadata
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
                    step_type_gen=step,
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
                    step_type_gen=step_type,
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

