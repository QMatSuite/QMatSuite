"""
Recipes for engine-dependent RPC methods.

Uses minimal engine runs and artifact pruning.
"""

from pathlib import Path
from typing import Any

from .base import Recipe
from .world import build_demo_world
from ..v0_payloads import build_v0_payload, V0_PAYLOAD_BUILDERS

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
    
    Runs minimal engine workflows and stores only essential artifacts.
    """
    
    method_name = ""
    description = "Engine-dependent methods with minimal runs"
    
    COVERED_METHODS = {
        "run_calculation",
        "run_step",
        "run_single_step",
        "get_latest_run_for_step",
        "get_band_structure_data",
        "get_dos_data",
        "get_scf_convergence",
        "get_reference_analysis",
        "ensure_calculation_analysis",
        "pin_analysis_to_history",
        "get_structure_vis",
    }
    
    def __init__(self, tmp_path: Path, method_name: str):
        super().__init__(tmp_path)
        self.method_name = method_name
        self.world: dict[str, Any] | None = None
        self.run_id: str | None = None
    
    def setup(self) -> bool:
        """Create project world and optionally run minimal engine workflow."""
        if QVService is None:
            return False
        
        self.project_root = self.tmp_path / "engine_project"
        self.project_root.mkdir()
        QVService.init_project(self.project_root, name="engine_project")
        
        self.world = build_demo_world(self.project_root)
        
        # For methods requiring completed runs, we would need to actually run
        # For now, we'll create minimal artifacts that represent a completed run
        # In a real scenario, this would trigger a minimal QE run
        
        # Create minimal output artifacts for testing
        if self.method_name in ("get_latest_run_for_step", "get_band_structure_data", 
                                "get_dos_data", "get_scf_convergence", "get_reference_analysis",
                                "ensure_calculation_analysis", "pin_analysis_to_history",
                                "get_structure_vis"):
            calc_dir = Path(self.world["project_root"]) / "calculations" / self.world["calc_slug"]
            raw_dir = calc_dir / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            
            # Create minimal output file
            (raw_dir / "scf.out").write_text("""     JOB DONE
     Final energy = -10.0 Ry
     convergence achieved
""")
        
        return True
    
    def build_payload(self) -> dict[str, Any]:
        """Build payload based on method name."""
        if self.world is None:
            return {}

        # Use centralized v0 payload builders for methods with defined schemas
        if self.method_name in V0_PAYLOAD_BUILDERS:
            return build_v0_payload(self.method_name, self.world)

        # Methods without v0 payload definitions
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
                "step_id": self.world.get("step_ids", [""])[0] if self.world.get("step_ids") else "",
            }

        if self.method_name == "get_band_structure_data":
            return {
                **base,
                "calculation": self.world["calculation_selector"],
            }

        if self.method_name == "get_dos_data":
            return {
                **base,
                "calculation": self.world["calculation_selector"],
            }

        if self.method_name == "get_scf_convergence":
            return {
                **base,
                "calculation": self.world["calculation_selector"],
                "step": self.world["step_selector"],
            }

        if self.method_name == "get_reference_analysis":
            return {
                **base,
                "calculation": self.world["calculation_selector"],
                "analysis_type": "scf",
            }

        if self.method_name == "ensure_calculation_analysis":
            return {
                **base,
                "calculation": self.world["calculation_selector"],
                "analysis_type": "scf",
            }

        if self.method_name == "pin_analysis_to_history":
            return {
                **base,
                "calculation": self.world["calculation_selector"],
                "step_id": self.world["step_selector"],
                "run_id": "mock_run_id",
                "analysis_kind": "scf",
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

