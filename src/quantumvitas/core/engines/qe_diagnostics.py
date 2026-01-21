"""Backward-compatibility re-export for qe_diagnostics (moved to drivers/qe/engine/)."""

from quantumvitas.drivers.qe.engine.qe_diagnostics import (
    diagnose_qe_resolution,
    check_settings_for_external_engines,
    check_environment_variables,
    check_managed_engines,
    QEResolutionReport,
)

__all__ = [
    "diagnose_qe_resolution",
    "check_settings_for_external_engines",
    "check_environment_variables",
    "check_managed_engines",
    "QEResolutionReport",
]

