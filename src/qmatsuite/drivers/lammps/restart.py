"""LAMMPS restart file handling.

This module manages LAMMPS restart/checkpoint files for
simulation continuation.
"""

import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from qmatsuite.core.step_context import StepContext

logger = logging.getLogger(__name__)


def find_restart_file(
    workdir: Path,
    pattern: str = "*.restart*",
) -> Optional[Path]:
    """Find the latest restart file in workdir.

    LAMMPS can write numbered restart files (e.g., restart.100000).
    This function finds the most recent one.

    Args:
        workdir: Directory to search
        pattern: Glob pattern for restart files

    Returns:
        Path to latest restart file, or None if not found
    """
    matches = list(workdir.glob(pattern))
    if not matches:
        return None

    # Sort by modification time, get most recent
    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0]


def stage_restart_file(
    source: Path,
    target_dir: Path,
    target_name: str = "restart.read",
) -> Path:
    """Stage restart file for reading.

    LAMMPS expects restart files with specific names for reading.

    Args:
        source: Source restart file path
        target_dir: Target directory
        target_name: Name for the staged file

    Returns:
        Path to staged restart file
    """
    import shutil

    target = target_dir / target_name
    shutil.copy2(source, target)
    logger.info(f"Staged restart file: {source} -> {target}")
    return target


def resolve_restart_source(
    context: "StepContext",
    explicit_source: Optional[str] = None,
) -> Optional[Path]:
    """Resolve source step for restart file.

    Args:
        context: Step context with calculation info
        explicit_source: Explicitly specified source step

    Returns:
        Path to restart file, or None if not found
    """
    if explicit_source:
        step_dir = context.get_step_dir(explicit_source)
        if step_dir:
            restart = find_restart_file(step_dir)
            if restart:
                return restart
        logger.warning(f"No restart file in explicit source '{explicit_source}'")

    # Auto-resolve: find previous step with restart file
    for prev_step in reversed(context.completed_steps):
        step_dir = context.get_step_dir(prev_step)
        if step_dir:
            restart = find_restart_file(step_dir)
            if restart:
                logger.debug(f"Auto-resolved restart from {prev_step}")
                return restart

    return None

