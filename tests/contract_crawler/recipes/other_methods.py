"""
Recipes for other uncovered RPC methods.
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


class OtherMethodsRecipe(Recipe):
    """
    Recipe for other uncovered methods.
    """
    
    method_name = ""
    description = "Other uncovered methods"
    
    COVERED_METHODS = {
        "analyze_project_pseudo_effects",
        "apply_presets_to_step",
        "can_delete_structure",
        "can_pin_to_run",
        "get_journal_entry",
        "get_pin_data",
        "get_run_revision",
        "list_project_runs",
        "promote_relax_structure",
        "save_relax_final_structure",
        "set_common_card",
        "set_pseudo_mapping",
        "update_calculation_species_map",
    }
    
    def __init__(self, tmp_path: Path, method_name: str):
        super().__init__(tmp_path)
        self.method_name = method_name
        self.world: dict[str, Any] | None = None
    
    def setup(self) -> bool:
        """Create minimal project world."""
        if QVService is None:
            return False
        
        self.project_root = self.tmp_path / "demo_project"
        self.project_root.mkdir()
        QVService.init_project(self.project_root, name="demo_project")
        
        self.world = build_demo_world(self.project_root)
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

        if self.method_name == "analyze_project_pseudo_effects":
            return base

        if self.method_name == "apply_presets_to_step":
            return {
                **base,
                "calculation": self.world["calculation_selector"],
                "step": self.world["step_selector"],
                "preset": "default",
            }

        if self.method_name == "can_pin_to_run":
            return {
                **base,
                "run_ulid": "mock_run_ulid",  # canonical field name
                "step_ulid": self.world.get("step_ids", [""])[0] if self.world.get("step_ids") else "",
            }

        if self.method_name == "get_journal_entry":
            return {
                **base,
                "entry_id": "test_entry_id",
            }

        if self.method_name == "get_pin_data":
            return {
                **base,
                "step_ulid": self.world.get("step_ids", [""])[0] if self.world.get("step_ids") else "",
                "run_ulid": "test_run_ulid",  # canonical field name
                "analysis_kind": "scf",
            }

        if self.method_name == "get_run_revision":
            return {
                **base,
                "run_ulid": "test_run_ulid",  # canonical field name
            }

        if self.method_name == "list_project_runs":
            return base

        if self.method_name == "promote_relax_structure":
            return {
                **base,
                "calculation": self.world["calculation_selector"],
                "step": self.world["step_selector"],
            }

        if self.method_name == "save_relax_final_structure":
            return {
                **base,
                "calculation": self.world["calculation_selector"],
                "step": self.world["step_selector"],
                "parent_structure_ulid": self.world["structure_ulid"],
            }

        if self.method_name == "set_pseudo_mapping":
            return {
                **base,
                "calculation": self.world["calculation_selector"],
                "step": self.world["step_selector"],
                "mapping": {"Si": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"},
            }

        if self.method_name == "update_calculation_species_map":
            return {
                **base,
                "calculation": self.world["calculation_selector"],
                "species_map": {"Si": "Si"},
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




