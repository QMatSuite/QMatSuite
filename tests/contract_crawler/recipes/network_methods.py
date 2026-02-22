"""
Recipes for network-dependent RPC methods.

Uses HTTP recording to ensure reproducible results.
"""

from pathlib import Path
from typing import Any

from .base import Recipe
from .world import build_demo_world

# Try to import API
try:
    from qmatsuite.api import get_service, QMSService
except ImportError:
    try:
        from qmatsuite.api import QMSService
        def get_service(project_root):
            return QMSService(project_root)
    except ImportError:
        get_service = None
        QMSService = None


class NetworkMethodsRecipe(Recipe):
    """
    Recipe for network-dependent methods.
    
    Uses HTTP recording to ensure reproducible results.
    """
    
    method_name = ""
    description = "Network-dependent methods with HTTP recording"
    
    COVERED_METHODS = {
        "structure_search_online",
        "structure_get_online_candidate",
        "structure_import_online_candidate",
        "structure_list_providers",
        "structure_update_online_sources",
        "download_sssp_library",
        "download_all_sssp",
        "download_pseudo_by_filename",
        "download_pseudo_candidate",
        "search_legacy_pseudos",
    }
    
    def __init__(self, tmp_path: Path, method_name: str):
        super().__init__(tmp_path)
        self.method_name = method_name
        self.world: dict[str, Any] | None = None
    
    def setup(self) -> bool:
        """Enable HTTP recording and create project if needed."""
        # Enable HTTP recording
        try:
            from tests.contract_crawler.http_recording import enable_recording
            enable_recording()
        except Exception:
            pass  # If recording fails, continue anyway

        if QMSService is None:
            return False

        # Methods that need a project
        methods_needing_project = (
            "structure_search_online", "structure_get_online_candidate",
            "structure_import_online_candidate", "download_pseudo_by_filename",
            "download_pseudo_candidate"
        )
        if self.method_name in methods_needing_project:
            self.project_root = self.tmp_path / "demo_project"
            self.project_root.mkdir()
            QMSService.init_project(self.project_root, name="demo_project")

        return True
    
    def build_payload(self) -> dict[str, Any]:
        """Build payload based on method name."""
        base = {}
        
        if self.method_name == "structure_list_providers":
            return {
                "refresh_registry": False,
            }

        if self.method_name == "structure_update_online_sources":
            return {
                "patch": {
                    "pubchem_enabled": True,
                },
            }

        if self.method_name == "structure_search_online":
            return {
                "project_root": str(self.project_root),
                "query": "Si",  # Simple query
                "max_results": 5,
            }
        
        if self.method_name == "structure_get_online_candidate":
            # 0873ebf expects session_id and candidate_id
            return {
                "project_root": str(self.project_root),
                "session_id": "mock_session_id",  # 0873ebf expects session_id
                "candidate_id": "mp-149",  # Example Materials Project ID
            }

        if self.method_name == "structure_import_online_candidate":
            # 0873ebf expects session_id and candidate_id
            return {
                "project_root": str(self.project_root),
                "session_id": "mock_session_id",  # 0873ebf expects session_id
                "candidate_id": "mp-149",  # Example Materials Project ID
                "name": "imported_structure",
            }
        
        if self.method_name == "download_sssp_library":
            return {
                "store_dir": str(self.tmp_path / "pseudo_store"),
                "flavor": "efficiency",
                "version": "1.3.0",
                "allow_download": True,
            }
        
        if self.method_name == "download_all_sssp":
            return {
                "store_dir": str(self.tmp_path / "pseudo_store"),
                "allow_download": True,
            }
        
        if self.method_name == "download_pseudo_by_filename":
            # Create project for 0873ebf compatibility (must create in setup)
            return {
                "project_root": str(self.project_root) if hasattr(self, 'project_root') else str(self.tmp_path / "demo_project"),
                "filename": "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
                "dest_dir": str(self.tmp_path / "pseudo_dir"),
            }

        if self.method_name == "download_pseudo_candidate":
            return {
                "project_root": str(self.project_root) if hasattr(self, 'project_root') else str(self.tmp_path / "demo_project"),
                "candidate": {
                    "filename": "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
                    "url": "https://example.com/Si.pbe-n-rrkjus_psl.1.0.0.UPF",
                },
                "dest_dir": str(self.tmp_path / "pseudo_dir"),
            }
        
        if self.method_name == "search_legacy_pseudos":
            return {
                "element": "Si",
                "xc": "pbe",
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




