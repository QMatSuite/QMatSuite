"""QE engine implementation."""

# Re-exports for backward compatibility
from quantumvitas.drivers.qe.engine.qe_engine import QuantumEspressoEngine
from quantumvitas.drivers.qe.engine.qe_calculation import QECalculationRunner
from quantumvitas.drivers.qe.engine.qe_installation import QEInstallation
from quantumvitas.drivers.qe.engine.qe_resolver import resolve_qe_bin_dir
from quantumvitas.drivers.qe.engine.qe_binary_locator import locate_qe_executable, locate_pw2wannier90
from quantumvitas.drivers.qe.engine.qe_diagnostics import diagnose_qe_resolution, QEResolutionReport
from quantumvitas.drivers.qe.engine.qe_pseudopotentials import download_pseudopotential, PseudoManager

__all__ = [
    "QuantumEspressoEngine",
    "QECalculationRunner",
    "QEInstallation",
    "resolve_qe_bin_dir",
    "locate_qe_executable",
    "locate_pw2wannier90",
    "diagnose_qe_resolution",
    "QEResolutionReport",
    "download_pseudopotential",
    "PseudoManager",
]

