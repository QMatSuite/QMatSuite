"""
Recipes for engine-dependent RPC methods.

Uses minimal engine runs and artifact pruning.
"""

from pathlib import Path
from typing import Any
import yaml

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


def create_minimal_bands_gnu(path: Path, n_bands: int = 4, n_kpoints: int = 50) -> None:
    """Create a minimal synthetic bands.dat.gnu file for testing."""
    lines = []
    for band_idx in range(n_bands):
        for k_idx in range(n_kpoints):
            k_dist = k_idx * 0.02  # Linear k-path
            energy = -2.0 + band_idx * 2.0 + k_dist * 0.1  # Bands separated by 2 eV
            lines.append(f"{k_dist:.6f}  {energy:.6f}")
        if band_idx < n_bands - 1:
            lines.append("")  # Blank line between bands
    path.write_text("\n".join(lines))


def create_bands_stdout(path: Path) -> None:
    """Create a bands.out file with high-symmetry point markers."""
    content = """high-symmetry point:  0.5000 0.5000 0.5000   x coordinate   0.0000
high-symmetry point:  0.0000 0.0000 0.0000   x coordinate   0.4000
high-symmetry point:  0.5000 0.0000 0.5000   x coordinate   0.8000

Plottable bands (eV) written to file si.bands.dat.gnu
Bands written to file si.bands.dat
"""
    path.write_text(content)


def create_minimal_dos_dat(path: Path, n_points: int = 50, fermi_ev: float = 6.5) -> None:
    """Create a minimal synthetic DOS .dat file for testing."""
    lines = []
    # Header
    lines.append(f"#  E (eV)   dos(E)     Int dos(E) EFermi =   {fermi_ev:.3f} eV")
    # Data
    for i in range(n_points):
        energy = fermi_ev - 5.0 + i * 10.0 / n_points
        dos_val = max(0, 2.0 - abs(energy - fermi_ev) * 0.3)  # Peak at Fermi
        idos_val = max(0, (energy - (fermi_ev - 5.0)) * dos_val * 0.1)  # Integrated
        lines.append(f"{energy:8.3f}  {dos_val:.4E}  {idos_val:.4E}")
    path.write_text("\n".join(lines))


class EngineMethodsRecipe(Recipe):
    """
    Recipe for engine-dependent methods.

    Creates synthetic output files (bands.dat.gnu, dos.dat) that can be parsed
    by the analysis methods without requiring actual QE runs.
    """

    method_name = ""
    description = "Engine-dependent methods with synthetic artifacts"

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
        self.run_ulid: str | None = None
        self.bands_step_id: str | None = None
        self.dos_step_id: str | None = None

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
        steps_dir = calc_dir / "steps"
        raw_dir.mkdir(parents=True, exist_ok=True)
        steps_dir.mkdir(parents=True, exist_ok=True)

        # Create minimal scf.out for general analysis
        (raw_dir / "scf.out").write_text("""     JOB DONE
     Final energy = -10.0 Ry
     convergence achieved
""")

        # Detect API style (static vs instance-based)
        is_static_api = True
        try:
            test_svc = QVService(self.project_root)
            is_static_api = False
        except (TypeError, AttributeError):
            is_static_api = True

        # For bands data, add a bands step and create synthetic files
        if self.method_name == "get_band_structure_data":
            # Add a bands step to the calculation
            if is_static_api:
                # Baseline 0873ebf: static API
                try:
                    result = QVService.add_step_to_calculation(
                        self.project_root,
                        calculation_selector=self.world["calc_id"],
                        step_type_gen="bands",  # GEN type for UI layer
                        step_name="bands",
                    )
                    if isinstance(result, dict) and "steps" in result and result["steps"]:
                        last_step = result["steps"][-1]
                        if isinstance(last_step, dict):
                            self.bands_step_id = last_step["step_ulid"]  # Canonical field only
                        else:
                            self.bands_step_id = last_step.step_ulid  # Canonical attribute only
                except Exception:
                    self.bands_step_id = self.world.get("step_ids", [None])[0]
            else:
                # Current HEAD: instance-based API
                svc = QVService(self.project_root) if get_service is None else get_service(self.project_root)
                try:
                    step_dto = svc.calculation.add_step(
                        calc_selector=self.world["calc_id"],
                        step_type_gen="bands",
                        name="bands",
                    )
                    self.bands_step_id = step_dto.step_ulid
                except Exception:
                    self.bands_step_id = self.world.get("step_ids", [None])[0]

            # Create bands data files
            create_minimal_bands_gnu(raw_dir / "si.bands.dat.gnu")
            create_bands_stdout(raw_dir / "bands.out")

            # Update step YAML with filband parameter if step file exists
            if self.bands_step_id:
                step_yaml = steps_dir / f"{self.bands_step_id}.step.yaml"
                if step_yaml.exists():
                    step_data = yaml.safe_load(step_yaml.read_text()) or {}
                    if "parameters" not in step_data:
                        step_data["parameters"] = {}
                    step_data["parameters"]["filband"] = "si.bands.dat"
                    step_yaml.write_text(yaml.dump(step_data))

        # For DOS data, add a dos step and create synthetic files
        if self.method_name == "get_dos_data":
            # Add a dos step to the calculation
            if is_static_api:
                # Baseline 0873ebf: static API
                try:
                    result = QVService.add_step_to_calculation(
                        self.project_root,
                        calculation_selector=self.world["calc_id"],
                        step_type_gen="dos",  # GEN type for UI layer
                        step_name="dos",
                    )
                    if isinstance(result, dict) and "steps" in result and result["steps"]:
                        last_step = result["steps"][-1]
                        if isinstance(last_step, dict):
                            self.dos_step_id = last_step["step_ulid"]  # Canonical field only
                        else:
                            self.dos_step_id = last_step.step_ulid  # Canonical attribute only
                except Exception:
                    self.dos_step_id = self.world.get("step_ids", [None])[0]
            else:
                # Current HEAD: instance-based API
                svc = QVService(self.project_root) if get_service is None else get_service(self.project_root)
                try:
                    step_dto = svc.calculation.add_step(
                        calc_selector=self.world["calc_id"],
                        step_type_gen="dos",
                        name="dos",
                    )
                    self.dos_step_id = step_dto.step_ulid
                except Exception:
                    self.dos_step_id = self.world.get("step_ids", [None])[0]

            # Create DOS data file
            create_minimal_dos_dat(raw_dir / "si.dos.dat")

            # Update step YAML with fildos parameter if step file exists
            if self.dos_step_id:
                step_yaml = steps_dir / f"{self.dos_step_id}.step.yaml"
                if step_yaml.exists():
                    step_data = yaml.safe_load(step_yaml.read_text()) or {}
                    if "parameters" not in step_data:
                        step_data["parameters"] = {}
                    if "DOS" not in step_data["parameters"]:
                        step_data["parameters"]["DOS"] = {}
                    step_data["parameters"]["DOS"]["fildos"] = "si.dos.dat"
                    step_yaml.write_text(yaml.dump(step_data))

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
                "step_ulid": self.world.get("step_ids", [""])[0] if self.world.get("step_ids") else "",
            }

        if self.method_name == "get_band_structure_data":
            return {
                **base,
                "calculation": self.world["calculation_selector"],
                "step": self.bands_step_id,  # Use the bands step we created
            }

        if self.method_name == "get_dos_data":
            return {
                **base,
                "calculation": self.world["calculation_selector"],
                "step": self.dos_step_id,  # Use the DOS step we created
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
                "step_ulid": self.world["step_selector"],
                "run_ulid": "mock_run_ulid",  # canonical field name
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

