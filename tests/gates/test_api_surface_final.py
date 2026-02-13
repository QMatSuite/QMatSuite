"""
PR10 Gate Tests: Final API Surface Contract Enforcement

These tests enforce the PR10 Definition of Done:
- Export count ≤30
- Zero kernel symbols in quantumvitas.api namespace
- All exports are API-owned (from quantumvitas.api.*)

Reference:
- docs/history/plans/API_FACADE_IMPLEMENTATION_PLAN.md §PR10
- docs/laws/L1/API_CONSTITUTION.md §Appendix E.4 (formerly API_FACADE_CONTRACT.md §6.1)
"""

import inspect
from typing import Any

import pytest


def test_api_export_count_final():
    """
    Final export count must be ≤30.
    
    Per API_FACADE_CONTRACT.md §6.1 and PR10 §Final __init__.py State.
    """
    import quantumvitas.api as api
    
    # Prefer __all__ if present (canonical intended export list)
    if hasattr(api, "__all__") and api.__all__:
        exports = list(api.__all__)
    else:
        # Fallback: all public names (not ideal, but catches if __all__ missing)
        exports = [x for x in dir(api) if not x.startswith("_")]
    
    export_count = len(exports)
    assert export_count <= 30, (
        f"Too many exports: {export_count} > 30. "
        f"Current exports: {exports}"
    )
    
    # Also verify __all__ exists (required for explicit export control)
    assert hasattr(api, "__all__"), "api.__all__ must be defined for explicit export control"
    assert isinstance(api.__all__, list), "api.__all__ must be a list"


def test_api_no_kernel_symbols():
    """
    No kernel symbols in api namespace.
    
    Per PR10 §test_no_kernel_symbols and API_FACADE_CONTRACT.md §7.
    Kernel types, exceptions, and constants must not leak through API.
    """
    import quantumvitas.api as api
    
    # Denylist of known kernel-leak names
    # Based on PR10 plan and progress review findings
    FORBIDDEN_KERNEL_TYPES = [
        # Core kernel dataclasses (should be DTOs)
        "Step",
        "Calculation",
        "CalculationStepEntry",
        "ResourceMeta",
        "EngineConfig",
        "ResourceIndex",
        "Manifest",
        "StepSpec",
        "StepResult",
        "CalculationModel",
        # Structure-related kernel types
        "Structure",
        "Atoms",
        "Lattice",
        "Cell",
        # Analysis-related kernel types
        "BandStructure",
        "DOS",
        "DOSData",
        "BandAnalysisFiles",
        # Execution-related kernel types
        "JobExecutor",
        "JobResult",
        # Project-related kernel types
        "ProjectConfig",
        "ProjectContext",
        "ResourceContext",
        # Engine-related kernel types
        "QeEngine",
        "DriverRegistry",
        # Preset-related kernel types
        "PrecisionOption",
        "DisplayModeParams",
        "ParameterOverride",
        # Step-related enums (should be API-owned if needed)
        "StepMode",
        "StepStatus",
    ]
    
    FORBIDDEN_KERNEL_EXCEPTIONS = [
        # Kernel exceptions that should not leak (only API-owned errors allowed)
        "ResourceNotFoundError",  # Should use API NotFoundError
        "AmbiguousSelectorError",  # Should use API AmbiguousError
        "SelectorNotFoundError",  # Should use API NotFoundError
        "ContextNotFoundError",  # Should use API NotFoundError
        "RegistryOutOfSyncError",  # Should use API ConfigError
        "ProjectConfigError",  # Should use API ConfigError
        "PresetCompilationError",  # Should use API ConfigError or ValidationError
        "PrecisionContextError",  # Should use API ConfigError or ValidationError
        "LegacyProjectError",  # Should use API ConfigError
        "VolumeParserError",  # Should use API EngineError
        "APIError",  # Legacy, should use API APIError
    ]
    
    FORBIDDEN_KERNEL_CONSTANTS = [
        "DIMENSION_PRECISION",  # Internal constant
    ]
    
    FORBIDDEN_OTHER = [
        "StructureStepSpec",  # Should be internal only
        "CandidateSummary",  # Kernel type
        "QECardType",  # Kernel type
        "QEModule",  # Kernel type
        "QEInputParser",  # Kernel type
    ]
    
    FORBIDDEN = (
        FORBIDDEN_KERNEL_TYPES +
        FORBIDDEN_KERNEL_EXCEPTIONS +
        FORBIDDEN_KERNEL_CONSTANTS +
        FORBIDDEN_OTHER
    )
    
    violations = []
    for name in FORBIDDEN:
        if hasattr(api, name):
            # Check if it's actually from a kernel module (not API-owned)
            obj = getattr(api, name)
            mod = getattr(obj, "__module__", "")
            # Allow API-owned symbols even if name matches forbidden list
            if mod.startswith("quantumvitas.api"):
                continue  # API-owned, not a violation
            violations.append(name)
    
    assert len(violations) == 0, (
        f"Found {len(violations)} forbidden kernel symbols in api namespace: {violations}. "
        f"These must be removed in PR10."
    )


def test_all_exports_are_api_owned():
    """
    Every export must be from quantumvitas.api.*
    
    Per PR10 §test_all_exports_are_api_owned.
    All symbols in __all__ must come from quantumvitas.api modules,
    not from kernel modules (core, calculation, drivers, etc.).
    """
    import quantumvitas.api as api
    
    # Whitelist of allowed non-api.* modules (builtins, typing, etc.)
    # Per contract, only explicit exceptions allowed
    ALLOWED_MODULE_PREFIXES = [
        "quantumvitas.api",  # Required: all must be from api.*
        "builtins",  # Built-in types (int, str, etc.)
        "typing",  # Typing constructs (Optional, Union, etc.)
    ]
    
    # Special handling for types that might be re-exported from typing
    # Path from pathlib is allowed if explicitly in contract
    ALLOWED_TYPING_REEXPORTS = [
        "Path",  # pathlib.Path - if contract allows it
        "Optional",  # typing.Optional
    ]
    
    if not hasattr(api, "__all__") or not api.__all__:
        pytest.skip("api.__all__ not defined or empty")
    
    violations = []
    for name in api.__all__:
        try:
            obj = getattr(api, name)
        except AttributeError:
            violations.append((name, None, "in __all__ but not available in api namespace (missing import?)"))
            continue
        
        # Skip if it's a builtin type or typing construct
        if name in ALLOWED_TYPING_REEXPORTS:
            # Verify it's actually from typing/pathlib, not kernel
            mod = getattr(obj, "__module__", "")
            if mod.startswith("quantumvitas.") and not mod.startswith("quantumvitas.api"):
                violations.append((name, mod, "kernel re-export of typing/pathlib symbol"))
            continue
        
        # For classes and functions, check module
        if inspect.isclass(obj) or inspect.isfunction(obj) or inspect.ismethod(obj):
            mod = getattr(obj, "__module__", "")
            
            # Check if module is allowed
            is_allowed = any(mod.startswith(prefix) for prefix in ALLOWED_MODULE_PREFIXES)
            
            if not is_allowed:
                violations.append((name, mod, f"from {mod}, not api.*"))
        
        # For constants/variables, try to get module from type
        elif not inspect.isclass(obj) and not inspect.isfunction(obj):
            # For constants, check if the value itself is from a kernel module
            obj_type = type(obj)
            mod = getattr(obj_type, "__module__", "")
            
            # If it's a kernel type, that's a violation
            if mod.startswith("quantumvitas.") and not mod.startswith("quantumvitas.api"):
                violations.append((name, mod, f"constant of kernel type {obj_type.__name__}"))
    
    assert len(violations) == 0, (
        f"Found {len(violations)} exports not from quantumvitas.api.*:\n" +
        "\n".join(
            f"  - {name}: {reason}" + (f" (module: {mod})" if mod else "")
            for name, mod, reason in violations
        )
    )

