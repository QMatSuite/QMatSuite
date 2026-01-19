"""
Simple engine registry mapping names to engine instances.
"""

from __future__ import annotations

from typing import Dict, Optional

from .base import Engine, EngineConfig
from .qe_engine import QeEngine
from .pyscf_engine import PySCFEngine
from .orca_engine import ORCAEngine, ORCAEngineConfig
from .vasp_engine import VaspEngine


class EngineRegistry:
    def __init__(self):
        self._engines: Dict[str, Engine] = {}

    def register(self, engine: Engine) -> None:
        self._engines[engine.name] = engine

    def get(self, name: str) -> Engine:
        try:
            return self._engines[name]
        except KeyError as exc:
            raise KeyError(f"Engine '{name}' not registered") from exc
    
    def list_engines(self) -> list:
        """List all registered engine names."""
        return list(self._engines.keys())
    
    def has(self, name: str) -> bool:
        """Check if an engine is registered."""
        return name in self._engines


def create_default_registry(
    config: Optional[EngineConfig] = None,
    include_orca: bool = True,
    include_vasp: bool = True,
) -> EngineRegistry:
    """
    Convenience helper returning a registry with QE, PySCF, optionally ORCA, and optionally VASP engines.

    Args:
        config: Optional engine configuration (used for QE engine)
        include_orca: If True (default), register ORCA engine (even if binary not available).
            Binary availability is checked only at execution time, not during registration.
        include_vasp: If True (default), register VASP engine (even if binary not available).
            Binary availability is checked only at execution time, not during registration.

    Returns:
        EngineRegistry with qe, pyscf, and optionally orca/vasp engines.
        ORCA/VASP are always registered if requested, even if binary is not found.
        Binary resolution is deferred until execution.
    """
    registry = EngineRegistry()
    registry.register(QeEngine(config))
    registry.register(PySCFEngine())

    # Always register ORCA if requested (binary resolution is deferred)
    if include_orca:
        # Use defer_binary_resolution=True so capability queries work without binary
        registry.register(ORCAEngine(defer_binary_resolution=True))
    
    # Always register VASP if requested (binary resolution is deferred)
    if include_vasp:
        registry.register(VaspEngine())

    return registry

