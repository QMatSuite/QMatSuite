"""QE Driver Bundle."""

from qmatsuite.core.driver_registry import DriverRegistry
from .driver import QEDriver
from . import parsers  # noqa: F401, E402

__all__ = ["QEDriver"]

# Register on import
DriverRegistry.register(QEDriver())
