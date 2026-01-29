"""
Reusable minimal world factory for recipe tests.

Creates a minimal but complete project with:
- Project with structure
- Calculation with multiple steps
- Required directories (raw/, etc.)
"""

from pathlib import Path
from typing import Any
import tempfile

from pymatgen.core import Structure, Lattice

# Try to import API - may differ in baseline
try:
    from quantumvitas.api import get_service, QVService
except ImportError:
    try:
        from quantumvitas.api import QVService
        def get_service(project_root):
            return QVService(project_root)
    except ImportError:
        get_service = None
        QVService = None


def build_demo_world(project_root: Path) -> dict[str, Any]:
    """
    Build a minimal demo world with project, structure, calculation, and steps.
    
    Args:
        project_root: Path to project root
    
    Returns:
        Dict with:
            project_root: str
            project_id: str (from project config if available)
            structure_id: str
            calc_id: str
            step_ids: list[str] (at least 2 steps)
            calculation_selector: str (can use calc_id or slug)
            step_selector: str (first step_id)
    """
    if QVService is None:
        raise RuntimeError("QVService not available")
    
    # Check if QVService methods are static (baseline) or instance-based (current)
    # Try to detect by checking if QVService can be instantiated
    is_static_api = True
    try:
        # Try to instantiate - if it fails, it's static API
        test_svc = QVService(project_root)
        is_static_api = False
    except (TypeError, AttributeError):
        # Static API - methods are @staticmethod
        is_static_api = True
    
    # Create structure by importing from a temporary file
    structure = Structure(Lattice.cubic(5.43), ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
    with tempfile.NamedTemporaryFile(mode='w', suffix='.cif', delete=False) as f:
        structure.to(fmt="cif", filename=f.name)
        struct_file = Path(f.name)
    
    try:
        if is_static_api:
            # Baseline: static methods
            struct_result = QVService.import_structure(project_root, struct_file, name="silicon")
            structure_id = struct_result.id if hasattr(struct_result, 'id') else struct_result.structure_id if hasattr(struct_result, 'structure_id') else None
        else:
            # Current: instance methods
            svc = QVService(project_root) if get_service is None else get_service(project_root)
            struct_dto = svc.structure.import_file(source=struct_file, name="silicon")
            structure_id = struct_dto.structure_id
    finally:
        struct_file.unlink()
    
    # Create calculation
    if is_static_api:
        # Baseline: use init_calculation
        calc_result = QVService.init_calculation(
            project_root,
            name="demo_calc",
            structure_selector=structure_id,
        )
        calc_id = calc_result.id if hasattr(calc_result, 'id') else None
        calc_slug = calc_result.slug if hasattr(calc_result, 'slug') else "demo_calc"
    else:
        svc = QVService(project_root) if get_service is None else get_service(project_root)
        calc_dto = svc.calculation.create(
            engine="qe",
            name="demo_calc",
            structure_selector=structure_id,
        )
        calc_id = calc_dto.calc_id
        calc_slug = calc_dto.meta.slug if hasattr(calc_dto, 'meta') and calc_dto.meta else "demo_calc"
    
    # Add multiple steps (at least 2)
    if is_static_api:
        # Baseline: static method returns Dict with calculation info
        step1_result = QVService.add_step_to_calculation(
            project_root,
            calculation_selector=calc_id,
            step_type="qe_scf",
            step_name="scf",
        )
        # Result is calculation dict, steps are in "steps" list
        # Get the last step (the one we just added)
        # In baseline, steps are ResolvedResource objects or dicts with 'id' field
        if isinstance(step1_result, dict) and "steps" in step1_result:
            steps_list = step1_result["steps"]
            if steps_list:
                last_step = steps_list[-1]
                # Try different ways to get step_id
                if isinstance(last_step, dict):
                    step1_id = last_step.get("id") or last_step.get("step_id")
                elif hasattr(last_step, 'id'):
                    step1_id = last_step.id
                elif hasattr(last_step, 'step_id'):
                    step1_id = last_step.step_id
                else:
                    step1_id = None
            else:
                step1_id = None
        else:
            step1_id = None
        
        step2_result = QVService.add_step_to_calculation(
            project_root,
            calculation_selector=calc_id,
            step_type="qe_nscf",
            step_name="nscf",
        )
        if isinstance(step2_result, dict) and "steps" in step2_result:
            steps_list = step2_result["steps"]
            if steps_list:
                last_step = steps_list[-1]
                if isinstance(last_step, dict):
                    step2_id = last_step.get("id") or last_step.get("step_id")
                elif hasattr(last_step, 'id'):
                    step2_id = last_step.id
                elif hasattr(last_step, 'step_id'):
                    step2_id = last_step.step_id
                else:
                    step2_id = None
            else:
                step2_id = None
        else:
            step2_id = None
    else:
        svc = QVService(project_root) if get_service is None else get_service(project_root)
        step1_dto = svc.calculation.add_step(
            calc_selector=calc_id,
            step_type="qe_scf",
            name="scf",
        )
        step1_id = step1_dto.step_id
        
        step2_dto = svc.calculation.add_step(
            calc_selector=calc_id,
            step_type="qe_nscf",
            name="nscf",
        )
        step2_id = step2_dto.step_id
    
    step_ids = [step1_id, step2_id] if step1_id and step2_id else []
    
    # Ensure raw directory exists for step artifacts
    calc_dir = project_root / "calculations" / calc_slug
    raw_dir = calc_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    # Try to get project_id from config
    project_id = None
    try:
        from quantumvitas.core.project_utils import load_project_config
        config = load_project_config(project_root)
        if "project" in config and "id" in config["project"]:
            project_id = config["project"]["id"]
    except Exception:
        pass
    
    return {
        "project_root": str(project_root),
        "project_id": project_id,
        "structure_id": structure_id,
        "calc_id": calc_id,
        "step_ids": step_ids,
        "calculation_selector": calc_id,  # Can use ULID
        "step_selector": step_ids[0] if step_ids else None,  # First step
        "calc_slug": calc_slug,
    }

