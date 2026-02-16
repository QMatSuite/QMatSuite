"""
Recipes for engine-dependent RPC methods.

Uses minimal engine runs and artifact pruning.
"""

from pathlib import Path
from typing import Any
import yaml

from .base import Recipe
from .world import build_demo_world

# Try to import API
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


class EngineMethodsRecipe(Recipe):
    """
    Recipe for engine-dependent methods.

    Creates minimal project world for engine-dependent endpoints.
    """

    method_name = ""
    description = "Engine-dependent methods with synthetic artifacts"

    COVERED_METHODS = {
        "run_calculation",
        "run_step",
        "run_single_step",
        "get_latest_run_for_step",
        "get_reference_analysis",
        "pin_analysis_to_history",
        "get_structure_vis",
    }

    def __init__(self, tmp_path: Path, method_name: str):
        super().__init__(tmp_path)
        self.method_name = method_name
        self.world: dict[str, Any] | None = None
        self.run_ulid: str | None = None

    def setup(self) -> bool:
        """Create project world with proper step types and synthetic data files."""
        if QVService is None:
            return False

        self.project_root = self.tmp_path / "engine_project"
        self.project_root.mkdir()
        QVService.init_project(self.project_root, name="engine_project")

        self.world = build_demo_world(self.project_root)

        calc_dir = Path(self.world["project_root"]) / "calculations" / self.world["calc_slug"]
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        # Create minimal scf.out for general analysis
        (raw_dir / "scf.out").write_text("""     JOB DONE
     Final energy = -10.0 Ry
     convergence achieved
""")

        return True
    
    def build_payload(self) -> dict[str, Any]:
        """Build payload based on method name."""
        if self.world is None:
            return {}

        base = {"project_root": self.world["project_root"]}

        if self.method_name == "run_calculation":
            return {
                **base,
                "calculation": self.world["calculation_selector"],
            }

        if self.method_name == "run_step":
            return {
                **base,
                "calculation": self.world["calculation_selector"],
                "step": self.world["step_selector"],
            }

        if self.method_name == "get_latest_run_for_step":
            return {
                **base,
                "step_ulid": self.world.get("step_ids", [""])[0] if self.world.get("step_ids") else "",
            }

        if self.method_name == "get_reference_analysis":
            return {
                **base,
                "calculation": self.world["calculation_selector"],
                "analysis_type": "scf",
            }

        if self.method_name == "pin_analysis_to_history":
            return {
                **base,
                "calculation": self.world["calculation_selector"],
                "step_ulid": self.world["step_selector"],
                "run_ulid": "mock_run_ulid",  # canonical field name
                "analysis_kind": "scf",
            }

        if self.method_name == "run_single_step":
            return {
                **base,
                "calculation": self.world["calculation_selector"],
                "step_ulid": self.world["step_selector"],
            }

        if self.method_name == "get_structure_vis":
            return {
                **base,
                "selector": {"ulid": self.world["structure_ulid"]},
            }

        return base
    
    def validate_response(self, response_data: dict[str, Any]) -> tuple[bool, str | None]:
        """Basic validation."""
        import json
        try:
            json.dumps(response_data)
        except (TypeError, ValueError) as e:
            return False, f"Not JSON serializable: {e}"
        return True, None
