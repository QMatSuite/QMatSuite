"""QE engine implementation."""

# Re-exports for backward compatibility
from qmatsuite.drivers.qe.engine.qe_engine import QuantumEspressoEngine
from qmatsuite.drivers.qe.engine.qe_calculation import QECalculationRunner
from qmatsuite.drivers.qe.engine.qe_installation import QEInstallation
from qmatsuite.drivers.qe.engine.qe_resolver import resolve_qe_bin_dir
from qmatsuite.drivers.qe.engine.qe_binary_locator import locate_qe_executable, locate_pw2wannier90
from qmatsuite.drivers.qe.engine.qe_diagnostics import diagnose_qe_resolution, QEResolutionReport
from qmatsuite.drivers.qe.engine.qe_pseudopotentials import download_pseudopotential, PseudoManager

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

