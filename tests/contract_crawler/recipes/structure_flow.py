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
        self.step_id: str | None = None

    def setup(self) -> bool:
        """Create project with structure, calculation, and step."""
        if QVService is None:
            return False  # API not available in this baseline
        
        # Create project
        self.project_root = self.tmp_path / "test_project"
        self.project_root.mkdir()
        QVService.init_project(self.project_root, name="test_project")

        # Get service
        if get_service is None:
            # Fallback: try direct instantiation
            svc = QVService(self.project_root)
        else:
            svc = get_service(self.project_root)

        # Create structure by importing from a temporary file
        structure = Structure(Lattice.cubic(5.43), ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cif', delete=False) as f:
            structure.to(fmt="cif", filename=f.name)
            struct_file = Path(f.name)

        try:
            struct_dto = svc.structure.import_file(source=struct_file, name="silicon")
        finally:
            struct_file.unlink()  # Clean up temp file

        # Create calculation
        calc_dto = svc.calculation.create(
            engine="qe",
            name="test_calc",
            structure_selector=struct_dto.structure_id,
        )
        self.calc_id = calc_dto.calc_id

        # Add SCF step
        step_dto = svc.calculation.add_step(
            calc_selector=self.calc_id,
            step_type="qe_scf",
            name="scf",
        )
        self.step_id = step_dto.step_id

        return True

    def build_payload(self) -> dict[str, Any]:
        return {
            "project_root": str(self.project_root),
            "calculation": self.calc_id,
            "step": self.step_id,
        }

    def validate_response(self, response_data: dict[str, Any]) -> tuple[bool, str | None]:
        # Required keys
        required = ["step_type", "parameters"]
        for key in required:
            if key not in response_data:
                return False, f"Missing required key: {key}"

        # JSON serializable check
        try:
            json.dumps(response_data)
        except (TypeError, ValueError) as e:
            return False, f"Not JSON serializable: {e}"

        return True, None

