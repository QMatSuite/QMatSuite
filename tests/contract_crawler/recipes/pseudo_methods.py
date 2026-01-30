"""
Recipes for pseudo-related RPC methods.
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


class PseudoMethodsRecipe(Recipe):
    """
    Recipe for pseudo-related methods.
    """
    
    method_name = ""
    description = "Pseudo-related methods"
    
    COVERED_METHODS = {
        "get_library_status",
        "install_library",
        "remove_library",
        "repair_library",
        "import_pseudo_files",
        "import_seed_archives",
        "init_pseudo_dirs",
        "install_pseudo_archive",
        "install_seed_to_store",
        "materialize_pseudo_file",
        "set_pseudo_config",
        "validate_pseudo_config",
        "resolve_project_pseudo_provenance",
    }
    
    def __init__(self, tmp_path: Path, method_name: str):
        super().__init__(tmp_path)
        self.method_name = method_name
        self.world: dict[str, Any] | None = None
    
    def setup(self) -> bool:
        """Create minimal project world if needed."""
        if QVService is None:
            return False
        
        # Most pseudo methods need a project
        if self.method_name in ("resolve_project_pseudo_provenance", "materialize_pseudo_file"):
            self.project_root = self.tmp_path / "demo_project"
            self.project_root.mkdir()
            QVService.init_project(self.project_root, name="demo_project")
            self.world = build_demo_world(self.project_root)
        
        # For validate_pseudo_config, set up directories and config
        if self.method_name == "validate_pseudo_config":
            from quantumvitas.core.pseudo_config import PseudoConfig, save_pseudo_config
            store_dir = self.tmp_path / "pseudo_store"
            seed_dir = self.tmp_path / "pseudo_seed"
            store_dir.mkdir(exist_ok=True)
            seed_dir.mkdir(exist_ok=True)
            # Create SSSP directory structure to match golden
            (seed_dir / "sssp").mkdir(exist_ok=True)
            # Save config with these directories
            config = PseudoConfig(
                store_dir=str(store_dir),
                seed_dir=str(seed_dir),
                allow_download=True,
            )
            save_pseudo_config(config)
        
        return True
    
    def build_payload(self) -> dict[str, Any]:
        """Build payload based on method name."""
        base = {}
        
        if self.method_name == "get_library_status":
            return {
                "library_id": "sssp",
            }
        
        if self.method_name == "install_library":
            return {
                "library_id": "sssp",
                "variants": ["efficiency"],
                "allow_download": False,  # Use local if available
            }
        
        if self.method_name == "remove_library":
            return {
                "library_id": "sssp",
            }
        
        if self.method_name == "repair_library":
            return {
                "library_id": "sssp",
            }
        
        if self.method_name == "import_pseudo_files":
            # Create project for 0873ebf compatibility
            if self.world is None:
                project_root = self.tmp_path / "demo_project"
                project_root.mkdir(exist_ok=True)
                QVService.init_project(project_root, name="demo_project")
                self.world = {"project_root": str(project_root)}
            return {
                "project_root": self.world["project_root"],  # 0873ebf expects project_root
                "source_dir": str(self.tmp_path / "pseudo_source"),
                "dest_dir": str(self.tmp_path / "pseudo_dest"),
            }
        
        if self.method_name == "import_seed_archives":
            return {
                "source_dir": str(self.tmp_path / "seed_source"),
                "dest_dir": str(self.tmp_path / "seed_dest"),
            }
        
        if self.method_name == "init_pseudo_dirs":
            return {
                "project_root": str(self.tmp_path / "demo_project"),
            }
        
        if self.method_name == "install_pseudo_archive":
            return {
                "archive_path": str(self.tmp_path / "archive.tar.gz"),
                "dest_dir": str(self.tmp_path / "pseudo_dest"),
            }
        
        if self.method_name == "install_seed_to_store":
            return {
                "seed_path": str(self.tmp_path / "seed.json"),
                "store_dir": str(self.tmp_path / "pseudo_store"),
            }
        
        if self.method_name == "materialize_pseudo_file":
            if self.world is None:
                return {}
            return {
                "project_root": self.world["project_root"],
                "element": "Si",  # 0873ebf expects element
                "sha256": "a" * 64,  # Also provide sha256
                "dest_path": str(self.tmp_path / "pseudo_file.UPF"),
            }
        
        if self.method_name == "set_pseudo_config":
            return {
                "config": {
                    "default_xc": "pbe",
                },
            }
        
        if self.method_name == "validate_pseudo_config":
            return {
                "config": {
                    "default_xc": "pbe",
                },
            }
        
        if self.method_name == "resolve_project_pseudo_provenance":
            if self.world is None:
                return {}
            return {
                "project_root": self.world["project_root"],
                "pseudo_relpath": "Si.pbe-n-rrkjus_psl.1.0.0.UPF",  # 0873ebf expects pseudo_abspath or both project_root + pseudo_relpath
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

