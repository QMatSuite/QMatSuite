"""QE Driver Bundle."""

from quantumvitas.core.driver_registry import DriverRegistry
from .driver import QEDriver

__all__ = ["QEDriver"]

# Register on import
DriverRegistry.register(QEDriver())

