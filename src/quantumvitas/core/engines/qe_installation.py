"""Backward-compatibility re-export for qe_installation (moved to drivers/qe/engine/)."""

from quantumvitas.drivers.qe.engine.qe_installation import (
    QEInstallation,
    get_qe_home,
    set_qe_home,
    reset_qe_home,
)

__all__ = ["QEInstallation", "get_qe_home", "set_qe_home", "reset_qe_home"]

