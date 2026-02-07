"""Siesta engine driver registration."""

from quantumvitas.core.driver_registry import DriverRegistry

from .driver import SiestaDriver

DriverRegistry.register(SiestaDriver())

# Trigger parser registration (SiestaOutputParser -> parser registry)
from . import parsers  # noqa: F401, E402
