"""Project context for MCP configuration tools.

Provides ``get_project_root()`` and ``get_service()`` that all
configuration tools share.  ``set_project_root()`` allows tests to
override the auto-detection with a tmp_path.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quantumvitas.api import QVService

_project_root_override: Path | None = None


class ProjectNotFoundError(Exception):
    """Raised when no QMatSuite project can be located."""


def set_project_root(path: Path | None) -> None:
    """Override auto-detection (for tests)."""
    global _project_root_override
    _project_root_override = path


def get_project_root() -> Path:
    """Return the active project root, auto-detecting if not overridden."""
    if _project_root_override is not None:
        return _project_root_override
    from quantumvitas.core.project_utils import find_project_root

    root = find_project_root()
    if root is None:
        raise ProjectNotFoundError(
            "No QMatSuite project found. Run from inside a project directory "
            "or create one with QVService.init_project()."
        )
    return root


def get_service() -> QVService:
    """Return a QVService bound to the active project root."""
    from quantumvitas.api import QVService

    try:
        return QVService(get_project_root())
    except ValueError as exc:
        raise ProjectNotFoundError(str(exc)) from exc
