"""
Recipes for simple methods that don't need complex setup.
"""

from pathlib import Path
from typing import Any

from .base import Recipe


class SimpleMethodsRecipe(Recipe):
    """
    Recipe for simple methods that need minimal or no setup.
    """
    
    method_name = ""
    description = "Simple methods with minimal setup"
    
    COVERED_METHODS = {
        # Note: shutdown is exempt as it terminates the daemon
        # Other simple methods can be added here if needed
    }
    
    def __init__(self, tmp_path: Path, method_name: str):
        super().__init__(tmp_path)
        self.method_name = method_name
    
    def setup(self) -> bool:
        """Minimal setup."""
        return True
    
    def build_payload(self) -> dict[str, Any]:
        """Build payload based on method name."""
        return {}
    
    def validate_response(self, response_data: dict[str, Any]) -> tuple[bool, str | None]:
        """Basic validation."""
        import json
        try:
            json.dumps(response_data)
        except (TypeError, ValueError) as e:
            return False, f"Not JSON serializable: {e}"
        return True, None




