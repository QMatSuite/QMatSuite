"""Engine implementations for computational codes."""

from .base import Engine, EngineConfig

# Backward-compatibility re-exports for QE engine (moved to drivers/qe/engine/)
def __getattr__(name: str):
    """Lazy import for backward-compatibility re-exports."""
    import importlib
    
    qe_exports = {
        "QuantumEspressoEngine": ("quantumvitas.drivers.qe.engine.qe_engine", "QuantumEspressoEngine"),
        "QEInstallation": ("quantumvitas.drivers.qe.engine.qe_installation", "QEInstallation"),
        "get_qe_home": ("quantumvitas.drivers.qe.engine.qe_installation", "get_qe_home"),
        "set_qe_home": ("quantumvitas.drivers.qe.engine.qe_installation", "set_qe_home"),
        "reset_qe_home": ("quantumvitas.drivers.qe.engine.qe_installation", "reset_qe_home"),
        "resolve_qe_bin_dir": ("quantumvitas.drivers.qe.engine.qe_resolver", "resolve_qe_bin_dir"),
        "find_internal_qe_bin_dir": ("quantumvitas.drivers.qe.engine.qe_resolver", "find_internal_qe_bin_dir"),
        "validate_qe_bin_dir": ("quantumvitas.drivers.qe.engine.qe_resolver", "validate_qe_bin_dir"),
        "download_pseudopotential": ("quantumvitas.drivers.qe.engine.qe_pseudopotentials", "download_pseudopotential"),
        "PseudoManager": ("quantumvitas.drivers.qe.engine.qe_pseudopotentials", "PseudoManager"),
        "StepResult": ("quantumvitas.drivers.qe.engine.qe_calculation", "StepResult"),
        "CalculationResult": ("quantumvitas.drivers.qe.engine.qe_calculation", "CalculationResult"),
        "QECalculationRunner": ("quantumvitas.drivers.qe.engine.qe_calculation", "QECalculationRunner"),
    }
    
    if name in qe_exports:
        module_path, attr_name = qe_exports[name]
        module = importlib.import_module(module_path)
        return getattr(module, attr_name)
    
    # I/O exports (still in io/ for now, will move in PR 6)
    from quantumvitas.io import (
        QEInputParser,
        QEInputGenerator,
        QEInput,
        QENamelist,
        QECard,
        QECardType,
        QEModule,
    )
    io_exports = {
        "QEInputParser": QEInputParser,
        "QEInputGenerator": QEInputGenerator,
        "QEInput": QEInput,
        "QENamelist": QENamelist,
        "QECard": QECard,
        "QECardType": QECardType,
        "QEModule": QEModule,
    }
    
    if name in io_exports:
        return io_exports[name]
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "Engine",
    "EngineConfig",
    # QE exports available via __getattr__
    "QuantumEspressoEngine",
    "QEInstallation",
    "get_qe_home",
    "set_qe_home",
    "reset_qe_home",
    "resolve_qe_bin_dir",
    "find_internal_qe_bin_dir",
    "validate_qe_bin_dir",
    "QEInputParser",
    "QEInputGenerator",
    "QEInput",
    "QENamelist",
    "QECard",
    "QECardType",
    "QEModule",
    "download_pseudopotential",
]

