"""
Parameterized recipes that reuse the world factory.

These recipes cover multiple methods by only changing the payload builder.
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


class ProjectMethodsRecipe(Recipe):
    """
    Recipe for project-scoped read-only methods.
    
    Covers: get_project_summary, list_structures, list_calculations,
            get_project_history, list_journal_entries, rebuild_project_registry
    """
    
    method_name = ""  # Set per instance
    description = "Project-scoped read-only methods"
    
    # Methods this recipe can cover
    COVERED_METHODS = {
        "get_project_summary",
        "list_structures",
        "list_calculations",
        "get_project_history",
        "list_journal_entries",
        "rebuild_project_registry",
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
        
        base_payload = {"project_root": self.world["project_root"]}
        
        # Methods that only need project_root
        if self.method_name in ("get_project_summary", "list_structures", "list_calculations",
                                 "rebuild_project_registry"):
            return base_payload
        
        # Methods that might need additional params
        if self.method_name == "get_project_history":
            return base_payload  # Optional: limit, calc_id
        
        if self.method_name == "list_journal_entries":
            return base_payload
        
        return base_payload
    
    def validate_response(self, response_data: dict[str, Any]) -> tuple[bool, str | None]:
        """Basic validation - JSON serializable and has expected structure."""
        import json
        try:
            json.dumps(response_data)
        except (TypeError, ValueError) as e:
            return False, f"Not JSON serializable: {e}"
        
        # Basic structure checks
        if self.method_name == "get_project_summary":
            # Should have project info
            if not isinstance(response_data, dict):
                return False, "Response must be dict"
        
        if self.method_name in ("list_structures", "list_calculations"):
            # Should have list and count
            if "count" not in response_data:
                return False, "Missing 'count' field"
        
        return True, None


class CalculationMethodsRecipe(Recipe):
    """
    Recipe for calculation-scoped read-only methods.
    
    Covers: get_calculation_detail, get_calculation_pseudo_mapping,
            get_pseudo_options_for_calculation, detect_presets,
            detect_workflow_for_calculation, get_step_preset_footprints,
            preflight_check
    """
    
    method_name = ""
    description = "Calculation-scoped read-only methods"
    
    COVERED_METHODS = {
        "get_calculation_detail",
        "get_calculation_pseudo_mapping",
        "get_pseudo_options_for_calculation",
        "detect_presets",
        "detect_workflow_for_calculation",
        "get_step_preset_footprints",
        "preflight_check",
        "can_delete_calculation",  # Read-only check
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
        """Build payload with calculation selector."""
        if self.world is None:
            return {}
        
        base_payload = {
            "project_root": self.world["project_root"],
            "calculation": self.world["calculation_selector"],
        }
        
        # Methods that only need project_root + calculation
        if self.method_name in ("get_calculation_detail", "get_calculation_pseudo_mapping",
                                "get_pseudo_options_for_calculation", "detect_presets",
                                "detect_workflow_for_calculation", "get_step_preset_footprints"):
            return base_payload
        
        if self.method_name == "preflight_check":
            # Optional: step parameter
            return base_payload
        
        return base_payload
    
    def validate_response(self, response_data: dict[str, Any]) -> tuple[bool, str | None]:
        """Basic validation."""
        import json
        try:
            json.dumps(response_data)
        except (TypeError, ValueError) as e:
            return False, f"Not JSON serializable: {e}"
        
        return True, None


class StepMethodsRecipe(Recipe):
    """
    Recipe for step-scoped read-only methods.
    
    Covers: get_step_detail, get_common_cards, get_pseudo_mapping,
            list_step_artifacts, read_step_artifact_text,
            get_relax_final_structure_preview
    """
    
    method_name = ""
    description = "Step-scoped read-only methods"
    
    COVERED_METHODS = {
        "get_step_detail",
        "get_common_cards",
        "get_pseudo_mapping",
        "list_step_artifacts",
        "read_step_artifact_text",
        "get_relax_final_structure_preview",
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
        
        # For read_step_artifact_text, create a dummy artifact file
        if self.method_name == "read_step_artifact_text":
            calc_dir = Path(self.world["project_root"]) / "calculations" / self.world["calc_slug"]
            raw_dir = calc_dir / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            # Create a dummy output file
            (raw_dir / "scf.out").write_text("# Dummy SCF output\n")
        
        return True
    
    def build_payload(self) -> dict[str, Any]:
        """Build payload with calculation and step selectors."""
        if self.world is None:
            return {}
        
        base_payload = {
            "project_root": self.world["project_root"],
            "calculation": self.world["calculation_selector"],
            "step": self.world["step_selector"],
        }
        
        if self.method_name == "read_step_artifact_text":
            # Need artifact_path
            base_payload["artifact_path"] = "scf.out"
        
        return base_payload
    
    def validate_response(self, response_data: dict[str, Any]) -> tuple[bool, str | None]:
        """Basic validation."""
        import json
        try:
            json.dumps(response_data)
        except (TypeError, ValueError) as e:
            return False, f"Not JSON serializable: {e}"
        
        if self.method_name == "get_step_detail":
            if "step_type" not in response_data:
                return False, "Missing 'step_type' field"
        
        if self.method_name == "list_step_artifacts":
            if "artifacts" not in response_data:
                return False, "Missing 'artifacts' field"
        
        return True, None


class ProjectMutationsRecipe(Recipe):
    """
    Recipe for project-level mutation methods.

    Covers: create_project, create_demo_project, import_structure, rename_structure
    """

    method_name = ""
    description = "Project-level mutation methods"

    COVERED_METHODS = {
        "create_project",
        "create_demo_project",
        "import_structure",
        "rename_structure",
    }

    def __init__(self, tmp_path: Path, method_name: str):
        super().__init__(tmp_path)
        self.method_name = method_name
        self.world: dict[str, Any] | None = None

    def setup(self) -> bool:
        """Create minimal project world."""
        if QVService is None:
            return False

        # For create_* methods, we need a parent directory
        if self.method_name in ("create_project", "create_demo_project"):
            self.project_root = self.tmp_path / "new_project"
            return True

        # For structure operations, need existing project with structure
        self.project_root = self.tmp_path / "demo_project"
        self.project_root.mkdir()
        QVService.init_project(self.project_root, name="demo_project")

        self.world = build_demo_world(self.project_root)
        return True

    def build_payload(self) -> dict[str, Any]:
        """Build payload based on method name."""
        if self.method_name == "create_project":
            return {
                "destination": str(self.project_root),
                "name": "test_project",
            }

        if self.method_name == "create_demo_project":
            return {
                "target_dir": str(self.tmp_path),  # Parent must exist
            }

        if self.world is None:
            return {}

        # Use centralized v0 payload builders for methods with defined schemas
        if self.method_name in V0_PAYLOAD_BUILDERS:
            # For import_structure, need to create the file first
            if self.method_name == "import_structure":
                from pymatgen.core import Structure, Lattice
                structure = Structure(Lattice.cubic(4.0), ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]])
                struct_file = self.tmp_path / "nacl_import.cif"
                structure.to(fmt="cif", filename=str(struct_file))
                return build_v0_payload(
                    self.method_name,
                    self.world,
                    source_file=str(struct_file),
                    name="nacl_import"
                )
            return build_v0_payload(self.method_name, self.world, new_name="silicon_renamed")

        return {}

    def validate_response(self, response_data: dict[str, Any]) -> tuple[bool, str | None]:
        """Basic validation."""
        import json
        try:
            json.dumps(response_data)
        except (TypeError, ValueError) as e:
            return False, f"Not JSON serializable: {e}"
        return True, None


class CalculationMutationsRecipe(Recipe):
    """
    Recipe for calculation-level mutation methods.

    Covers: create_calculation, add_step_to_calculation, rename_calculation,
            reorder_calculation_steps, apply_presets_to_calculation,
            change_calculation_structure
    """

    method_name = ""
    description = "Calculation-level mutation methods"

    COVERED_METHODS = {
        "create_calculation",
        "add_step_to_calculation",
        "rename_calculation",
        "reorder_calculation_steps",
        "apply_presets_to_calculation",
        "change_calculation_structure",
    }

    def __init__(self, tmp_path: Path, method_name: str):
        super().__init__(tmp_path)
        self.method_name = method_name
        self.world: dict[str, Any] | None = None
        self.second_structure_id: str | None = None

    def setup(self) -> bool:
        """Create minimal project world."""
        if QVService is None:
            return False

        self.project_root = self.tmp_path / "demo_project"
        self.project_root.mkdir()
        QVService.init_project(self.project_root, name="demo_project")

        self.world = build_demo_world(self.project_root)

        # For change_calculation_structure, need a second structure
        if self.method_name == "change_calculation_structure":
            from pymatgen.core import Structure, Lattice
            import tempfile
            structure = Structure(Lattice.cubic(4.0), ["Ge"], [[0, 0, 0]])
            with tempfile.NamedTemporaryFile(mode='w', suffix='.cif', delete=False) as f:
                structure.to(fmt="cif", filename=f.name)
                struct_file = Path(f.name)

            try:
                # Check for static vs instance API
                try:
                    svc = QVService(self.project_root)
                    struct_dto = svc.structure.import_file(source=struct_file, name="germanium")
                    self.second_structure_id = struct_dto.structure_id
                except (TypeError, AttributeError):
                    result = QVService.import_structure(self.project_root, struct_file, name="germanium")
                    self.second_structure_id = result.id if hasattr(result, 'id') else result.structure_id
            finally:
                struct_file.unlink()

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

        if self.method_name == "create_calculation":
            return {
                **base,
                "engine": "qe",
                "name": "new_calc",
                "structure_selector": self.world["structure_id"],
            }

        if self.method_name == "add_step_to_calculation":
            return {
                **base,
                "calculation": self.world["calculation_selector"],
                "step_type_gen": "qe_bands",
                "step_name": "bands",
            }

        if self.method_name == "rename_calculation":
            return {
                **base,
                "calculation_ulid": self.world["calculation_selector"],
                "new_name": "renamed_calc",
            }

        if self.method_name == "apply_presets_to_calculation":
            return {
                **base,
                "calculation": self.world["calculation_selector"],
                "preset": "default",
            }

        if self.method_name == "change_calculation_structure":
            return {
                **base,
                "calculation": self.world["calculation_selector"],
                "new_structure": self.second_structure_id,
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


class StepMutationsRecipe(Recipe):
    """
    Recipe for step-level mutation methods.

    Covers: update_step_params, reset_step_params
    """

    method_name = ""
    description = "Step-level mutation methods"

    COVERED_METHODS = {
        "update_step_params",
        "reset_step_params",
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
        base = {
            "project_root": self.world["project_root"],
            "calculation": self.world["calculation_selector"],
            "step": self.world["step_selector"],
        }

        if self.method_name == "update_step_params":
            # Match v0 golden payload - use 'parameters' key with namelist format
            # Set CONTROL.outdir to trigger runtime-managed key warning
            return {
                **base,
                "parameters": {
                    "CONTROL": {
                        "outdir": "./outdir",  # Triggers warning about runtime-managed key
                    },
                },
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


class WorkflowRecipe(Recipe):
    """
    Recipe for workflow methods.

    Covers: detect_workflow, instantiate_workflow
    """

    method_name = ""
    description = "Workflow methods"

    COVERED_METHODS = {
        "detect_workflow",
        "instantiate_workflow",
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
        base = {
            "project_root": self.world["project_root"],
            "structure": self.world["structure_id"],
        }

        if self.method_name == "detect_workflow":
            calc_path = f"{self.world['project_root']}/calculations/{self.world['calc_slug']}"
            return {
                **base,
                "calculation_path": calc_path,
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


class ImportStepRecipe(Recipe):
    """
    Recipe for import_step_from_qe_input method.

    Requires a QE input file to import.
    """

    method_name = "import_step_from_qe_input"
    description = "Import step from QE input file"

    COVERED_METHODS = {
        "import_step_from_qe_input",
    }

    def __init__(self, tmp_path: Path, method_name: str = "import_step_from_qe_input"):
        super().__init__(tmp_path)
        self.method_name = method_name
        self.world: dict[str, Any] | None = None
        self.input_file: str | None = None

    def setup(self) -> bool:
        """Create minimal project world and QE input file."""
        if QVService is None:
            return False

        self.project_root = self.tmp_path / "demo_project"
        self.project_root.mkdir()
        QVService.init_project(self.project_root, name="demo_project")

        self.world = build_demo_world(self.project_root)

        # Create a minimal QE input file
        qe_input = """&CONTROL
    calculation = 'scf'
    prefix = 'si'
    outdir = './tmp'
    pseudo_dir = './pseudo'
/
&SYSTEM
    ibrav = 0
    nat = 2
    ntyp = 1
    ecutwfc = 30.0
/
&ELECTRONS
    conv_thr = 1.0d-8
/
ATOMIC_SPECIES
Si 28.086 Si.pbe-n-rrkjus_psl.1.0.0.UPF
ATOMIC_POSITIONS crystal
Si 0.0 0.0 0.0
Si 0.25 0.25 0.25
CELL_PARAMETERS angstrom
5.43 0.0 0.0
0.0 5.43 0.0
0.0 0.0 5.43
K_POINTS automatic
4 4 4 0 0 0
"""
        input_path = self.tmp_path / "scf.in"
        input_path.write_text(qe_input)
        self.input_file = str(input_path)

        return True

    def build_payload(self) -> dict[str, Any]:
        """Build payload."""
        if self.world is None or self.input_file is None:
            return {}

        return {
            "project_root": self.world["project_root"],
            "calculation": self.world["calculation_selector"],
            "input_file": self.input_file,
            "step_name": "imported_scf",
        }

    def validate_response(self, response_data: dict[str, Any]) -> tuple[bool, str | None]:
        """Basic validation."""
        import json
        try:
            json.dumps(response_data)
        except (TypeError, ValueError) as e:
            return False, f"Not JSON serializable: {e}"
        return True, None


# Import additional recipe classes
try:
    from .network_methods import NetworkMethodsRecipe
    from .pseudo_methods import PseudoMethodsRecipe
    from .other_methods import OtherMethodsRecipe
    from .destructive_methods import DestructiveMethodsRecipe
    from .engine_methods import EngineMethodsRecipe
    from .simple_queries import SimpleQueriesRecipe
except ImportError:
    # Fallback if modules don't exist yet
    NetworkMethodsRecipe = None
    PseudoMethodsRecipe = None
    OtherMethodsRecipe = None
    DestructiveMethodsRecipe = None
    EngineMethodsRecipe = None
    SimpleQueriesRecipe = None

# Registry of parameterized recipes
PARAMETERIZED_RECIPES = {
    ProjectMethodsRecipe,
    CalculationMethodsRecipe,
    StepMethodsRecipe,
    ProjectMutationsRecipe,
    CalculationMutationsRecipe,
    StepMutationsRecipe,
    WorkflowRecipe,
    ImportStepRecipe,
}

# Add additional recipes if available
if NetworkMethodsRecipe is not None:
    PARAMETERIZED_RECIPES.add(NetworkMethodsRecipe)
if PseudoMethodsRecipe is not None:
    PARAMETERIZED_RECIPES.add(PseudoMethodsRecipe)
if OtherMethodsRecipe is not None:
    PARAMETERIZED_RECIPES.add(OtherMethodsRecipe)
if DestructiveMethodsRecipe is not None:
    PARAMETERIZED_RECIPES.add(DestructiveMethodsRecipe)
if EngineMethodsRecipe is not None:
    PARAMETERIZED_RECIPES.add(EngineMethodsRecipe)
if SimpleQueriesRecipe is not None:
    PARAMETERIZED_RECIPES.add(SimpleQueriesRecipe)


def get_recipe_for_method(method_name: str) -> type[Recipe] | None:
    """
    Get the appropriate parameterized recipe class for a method.

    Returns:
        Recipe class that can cover this method, or None
    """
    for recipe_cls in PARAMETERIZED_RECIPES:
        if method_name in recipe_cls.COVERED_METHODS:
            return recipe_cls
    return None

