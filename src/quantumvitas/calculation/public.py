from quantumvitas.calculation.calculation import Calculation
from quantumvitas.calculation.step import Step
from quantumvitas.calculation.structure_steps import StructureStepSpec, detect_runtime_control_keys
from quantumvitas.calculation.manifest import ManifestStepEntry, Manifest, load_manifest
from quantumvitas.calculation.hash_utils import compute_step_sha
from quantumvitas.calculation.scan_validation import find_all_scan_refs, is_scan_ref
from quantumvitas.calculation.scan_tokens import parse_scan_id
from quantumvitas.calculation.step_defaults import get_default_step_params
from quantumvitas.calculation.results import CalculationResult


# Lazy imports — CalculationRunner triggers verification → analysis cycle
def __getattr__(name):
    _LAZY_MAP = {
        "CalculationRunner": ("quantumvitas.calculation.runner", "CalculationRunner"),
    }
    if name in _LAZY_MAP:
        mod_path, attr = _LAZY_MAP[name]
        import importlib
        mod = importlib.import_module(mod_path)
        return getattr(mod, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
