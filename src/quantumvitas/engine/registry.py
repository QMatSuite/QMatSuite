"""
Simple engine registry mapping names to engine instances.
"""

from __future__ import annotations

from typing import Dict

from .base import Engine


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

