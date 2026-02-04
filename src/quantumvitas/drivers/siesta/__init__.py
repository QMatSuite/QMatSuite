"""Siesta engine driver registration."""

from quantumvitas.core.driver_registry import DriverRegistry

from .driver import SiestaDriver

DriverRegistry.register(SiestaDriver())
