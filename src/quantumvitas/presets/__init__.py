"""
Preset detection and compilation for QMatSuite.

This module implements runtime-only preset/workflow interpretation
per Constitution Chapter 10. Presets are never persisted - they are
inferred from step parameters (Detector B) or used to generate
step parameters (Compiler).

Key invariants:
- step.yml is the only executable truth (10.1.1)
- Presets/workflows are not persistent entities (10.2.1)
- Detector B is the sole legitimate state source (10.4.1)
- No "Unknown" state - either single value or Custom (10.5.1)
- Compiler uses canonical encoding (10.3.4)
- Equivalence: detect(compile(options)) == options (10.6.2)
"""

from quantumvitas.presets.dimensions import (
    SpinOption,
    SOCOption,
    MaterialOption,
    CUSTOM,
)
from quantumvitas.presets.detector import (
    detect_spin,
    detect_soc,
    detect_material,
    detect_all_presets,
)
from quantumvitas.presets.compiler import (
    compile_spin,
    compile_soc,
    compile_material,
    compile_presets,
    compile_presets_for_step,
    PresetCompilationError,
)
from quantumvitas.presets.integration import (
    detect_presets_from_calculation,
    detect_presets_from_calculation_typed,
    apply_presets_to_step,
    detect_workflow_type,
)

__all__ = [
    # Dimension enums
    "SpinOption",
    "SOCOption",
    "MaterialOption",
    "CUSTOM",
    # Detector functions
    "detect_spin",
    "detect_soc",
    "detect_material",
    "detect_all_presets",
    # Compiler functions
    "compile_spin",
    "compile_soc",
    "compile_material",
    "compile_presets",
    "compile_presets_for_step",
    "PresetCompilationError",
    # Integration functions
    "detect_presets_from_calculation",
    "detect_presets_from_calculation_typed",
    "apply_presets_to_step",
    "detect_workflow_type",
]

