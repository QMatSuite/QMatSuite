"""CP2K input file writer utilities.

This module provides helpers for writing CP2K hierarchical input format.
"""

import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def write_section(
    name: str,
    content: Dict[str, Any],
    indent: int = 0,
) -> str:
    """Write a CP2K input section.

    Args:
        name: Section name (e.g., "FORCE_EVAL")
        content: Section content as nested dict
        indent: Current indentation level

    Returns:
        Formatted section string
    """
    lines = []
    prefix = "  " * indent

    lines.append(f"{prefix}&{name}")

    for key, value in content.items():
        if isinstance(value, dict):
            # Nested section
            lines.append(write_section(key, value, indent + 1))
        elif isinstance(value, list):
            # Multiple values or repeated sections
            for item in value:
                if isinstance(item, dict):
                    lines.append(write_section(key, item, indent + 1))
                else:
                    lines.append(f"{prefix}  {key} {item}")
        else:
            lines.append(f"{prefix}  {key} {value}")

    lines.append(f"{prefix}&END {name}")

    return "\n".join(lines)

