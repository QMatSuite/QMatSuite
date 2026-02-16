"""
Recipes for destructive RPC methods.

These methods can be safely tested in isolated temporary project worlds.
"""

from pathlib import Path
from typing import Any

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


class DestructiveMethodsRecipe(Recipe):
    """
    Recipe for destructive methods.
    
    These methods modify or delete resources, but can be safely tested
    in isolated temporary project worlds.
    """
    
    method_name = ""
    description = "Destructive methods (tested in isolated worlds)"
    
    COVERED_METHODS = {
        "delete_calculation",
        "delete_structure",
        "delete_step",
        "delete_project_history",
    }
    
    def __init__(self, tmp_path: Path, method_name: str):
        super().__init__(tmp_path)
        self.method_name = method_name
        self.world: dict[str, Any] | None = None
    
    def setup(self) -> bool:
        """Create isolated project world for destructive operations."""
        if QVService is None:
            return False
        
        self.project_root = self.tmp_path / "isolated_project"
        self.project_root.mkdir()
        QVService.init_project(self.project_root, name="isolated_project")
        
        self.world = build_demo_world(self.project_root)
        return True
    
    def build_payload(self) -> dict[str, Any]:
        """Build payload based on method name."""
        if self.world is None:
            return {}

        base = {"project_root": self.world["project_root"]}

        if self.method_name == "delete_calculation":
            return {
                **base,
                "calculation": self.world["calculation_selector"],
            }

        if self.method_name == "delete_step":
            return {
                **base,
                "calculation": self.world["calculation_selector"],
                "step": self.world["step_selector"],
            }

        if self.method_name == "delete_structure":
            return {
                **base,
                "selector": {"ulid": self.world["structure_ulid"]},
            }

        if self.method_name == "delete_project_history":
            return base

        return base
    
    def validate_response(self, response_data: dict[str, Any]) -> tuple[bool, str | None]:
        """Basic validation."""
        import json
        try:
            json.dumps(response_data)
        except (TypeError, ValueError) as e:
            return False, f"Not JSON serializable: {e}"
        return True, None




