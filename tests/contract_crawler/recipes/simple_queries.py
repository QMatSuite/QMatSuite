"""
Recipes for simple query methods that need minimal parameters.
"""

from pathlib import Path
from typing import Any

from .base import Recipe
from ..v0_payloads import build_v0_payload, V0_PAYLOAD_BUILDERS


class SimpleQueriesRecipe(Recipe):
    """
    Recipe for simple query methods requiring minimal parameters.
    """

    method_name = ""
    description = "Simple query methods with minimal parameters"

    COVERED_METHODS = {
        "list_installed_sssp",
        "list_qe_parameter_metadata",
        "list_qe_ui_parameters",
        "find_project_root",  # Needs isolated tmp_path to avoid CWD variance in parallel runs
    }

    def __init__(self, tmp_path: Path, method_name: str):
        super().__init__(tmp_path)
        self.method_name = method_name
        # Create minimal world for v0 payloads
        self._world = {"project_root": str(tmp_path)}

    def setup(self) -> bool:
        """Minimal setup."""
        return True

    def build_payload(self) -> dict[str, Any]:
        """Build payload based on method name."""
        # Use centralized v0 payload builders for methods with defined schemas
        if self.method_name in V0_PAYLOAD_BUILDERS:
            return build_v0_payload(self.method_name, self._world)

        # Methods without v0 payload definitions
        if self.method_name == "list_installed_sssp":
            return {
                "store_dir": str(self.tmp_path / "pseudo_store"),
            }

        if self.method_name == "list_qe_parameter_metadata":
            return {
                "operation": "list_modules",
            }

        if self.method_name == "find_project_root":
            # Use isolated tmp_path for deterministic results in parallel runs
            # Create a unique search directory without project markers
            import os
            worker_id = os.environ.get("PYTEST_XDIST_WORKER", "gw0")
            search_dir = self.tmp_path / f"find_root_{worker_id}"
            search_dir.mkdir(parents=True, exist_ok=True)
            return {"cwd": str(search_dir)}

        return {}
    
    def validate_response(self, response_data: dict[str, Any]) -> tuple[bool, str | None]:
        """Basic validation."""
        import json
        try:
            json.dumps(response_data)
        except (TypeError, ValueError) as e:
            return False, f"Not JSON serializable: {e}"
        return True, None

