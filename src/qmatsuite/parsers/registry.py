"""
Parser registry for automatic parser selection.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from qmatsuite.core.analysis.base import AnalysisObjectMeta

# Registry: (engine, object_type) -> parser class
_PARSERS: Dict[Tuple[str, str], type] = {}


def register_parser(engine: str, object_type: str):
    """Decorator to register a parser class."""
    def decorator(cls):
        _PARSERS[(engine.lower(), object_type.lower())] = cls
        return cls
    return decorator


def get_parser(engine: str, object_type: str):
    """Get parser class for engine and object type."""
    return _PARSERS.get((engine.lower(), object_type.lower()))


def find_parser_for_raw(raw_dir: Path, object_type: str):
    """
    Auto-detect parser based on raw directory contents.
    
    Returns:
        Parser class or None
    """
    for (engine, obj_type), parser_cls in _PARSERS.items():
        if obj_type == object_type.lower():
            parser = parser_cls()
            if hasattr(parser, "can_parse") and parser.can_parse(raw_dir):
                return parser_cls
    return None


class ParserRegistry:
    """Registry facade."""
    
    @staticmethod
    def register(engine: str, object_type: str):
        return register_parser(engine, object_type)
    
    @staticmethod
    def get(engine: str, object_type: str):
        return get_parser(engine, object_type)
    
    @staticmethod
    def find_for_raw(raw_dir: Path, object_type: str):
        return find_parser_for_raw(raw_dir, object_type)

