"""
Simple engine registry mapping names to engine instances.
"""

from __future__ import annotations

from typing import Dict, Optional

from .base import Engine, EngineConfig
from .qe_engine import QeEngine


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


def create_default_registry(config: Optional[EngineConfig] = None) -> EngineRegistry:
    """
    Convenience helper returning a registry with the QE engine registered.
    """
    registry = EngineRegistry()
    registry.register(QeEngine(config))
    return registry

