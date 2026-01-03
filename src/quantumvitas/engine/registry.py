"""
Simple engine registry mapping names to engine instances.
"""

from __future__ import annotations

from typing import Dict, Optional

from .base import Engine, EngineConfig
from .qe_engine import QeEngine
from .pyscf_engine import PySCFEngine


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


def create_default_registry(config: Optional[EngineConfig] = None) -> EngineRegistry:
    """
    Convenience helper returning a registry with QE and PySCF engines registered.
    
    Args:
        config: Optional engine configuration (used for QE engine)
        
    Returns:
        EngineRegistry with qe and pyscf engines
    """
    registry = EngineRegistry()
    registry.register(QeEngine(config))
    registry.register(PySCFEngine())
    return registry

