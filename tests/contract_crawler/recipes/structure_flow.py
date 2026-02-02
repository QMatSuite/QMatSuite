"""Recipes for structure-related RPC methods."""

from pathlib import Path
from typing import Any
import json
import tempfile

from pymatgen.core import Structure, Lattice

# Try to import API - may differ in baseline
try:
    from quantumvitas.api import get_service, QVService
except ImportError:
    # Fallback for baseline compatibility
    try:
        from quantumvitas.api import QVService
        # In baseline, QVService might be used directly
        def get_service(project_root):
            return QVService(project_root)
    except ImportError:
        # If all else fails, we'll handle in setup
        get_service = None
        QVService = None

from .base import Recipe


class GetStepDetailRecipe(Recipe):
    """Recipe for get_step_detail method."""

    method_name = "get_step_detail"
    description = "Get step configuration details"

    def __init__(self, tmp_path: Path):
        super().__init__(tmp_path)
        self.calc_id: str | None = None
        self.step_ulid: str | None = None

    def setup(self) -> bool:
        """Create project with structure, calculation, and step."""
        if QVService is None:
            return False  # API not available in this baseline
        
        # Create project
        self.project_root = self.tmp_path / "test_project"
        self.project_root.mkdir()
        QVService.init_project(self.project_root, name="test_project")

        # Check if QVService methods are static (baseline) or instance-based (current)
        is_static_api = True
        try:
            test_svc = QVService(self.project_root)
            is_static_api = False
        except (TypeError, AttributeError):
            is_static_api = True

        # Create structure by importing from a temporary file
        structure = Structure(Lattice.cubic(5.43), ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cif', delete=False) as f:
            structure.to(fmt="cif", filename=f.name)
            struct_file = Path(f.name)

        try:
            # Import structure using nested service method
            svc = QVService(self.project_root) if get_service is None else get_service(self.project_root)
            struct_dto = svc.structure.import_file(source=struct_file, name="silicon")
            structure_ulid = struct_dto.structure_ulid
        finally:
            struct_file.unlink()

        # Create calculation using nested service method
        svc = QVService(self.project_root) if get_service is None else get_service(self.project_root)
        calc_result = svc.project.init_calculation(
            name="test_calc",
            structure_selector=structure_ulid,
        )
        self.calc_id = calc_result.ulid if hasattr(calc_result, 'ulid') else None

        # Add SCF step
        if is_static_api:
            step_result = QVService.add_step_to_calculation(
                self.project_root,
                calculation_selector=self.calc_id,
                step_type_gen="scf",  # GEN type for UI layer
                step_name="scf",
            )
            # 0873ebf returns calculation dict with steps list
            if isinstance(step_result, dict) and "steps" in step_result:
                steps_list = step_result["steps"]
                if steps_list:
                    last_step = steps_list[-1]
                    if isinstance(last_step, dict):
                        self.step_ulid = last_step["step_ulid"]  # Canonical field only
                    else:
                        self.step_ulid = last_step.step_ulid  # Canonical attribute only
            elif isinstance(step_result, dict):
                self.step_ulid = step_result["step_ulid"]  # Canonical field only
            else:
                self.step_ulid = step_result.step_ulid  # Canonical attribute only
        else:
            svc = QVService(self.project_root) if get_service is None else get_service(self.project_root)
            step_dto = svc.calculation.add_step(
                calc_selector=self.calc_id,
                step_type_gen="scf",  # GEN type for UI layer
                name="scf",
            )
            self.step_ulid = step_dto.step_ulid

        return True

    def build_payload(self) -> dict[str, Any]:
        return {
            "project_root": str(self.project_root),
            "calculation": self.calc_id,
            "step": self.step_ulid,
        }

    def validate_response(self, response_data: dict[str, Any]) -> tuple[bool, str | None]:
        # Required keys (allow backwards compat)
        required = ["parameters"]
        for key in required:
            if key not in response_data:
                return False, f"Missing required key: {key}"
        # Check for step type fields (new or backwards compat)
        if "step_type_spec" not in response_data and "step_type" not in response_data:
            return False, "Missing step_type_spec or step_type"

        # JSON serializable check
        try:
            json.dumps(response_data)
        except (TypeError, ValueError) as e:
            return False, f"Not JSON serializable: {e}"

        return True, None

