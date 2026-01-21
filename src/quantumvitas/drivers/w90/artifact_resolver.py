"""Wannier90 artifact resolution.

This module handles resolution of W90 input artifacts from
preprocessing steps executed by DFT engines.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, TYPE_CHECKING

from quantumvitas.core.driver_registry import DriverRegistry

if TYPE_CHECKING:
    from quantumvitas.core.step_context import StepContext

logger = logging.getLogger(__name__)


def resolve_w90_inputs(
    context: "StepContext",
    explicit_source: Optional[str] = None,
) -> Dict[str, Path]:
    """Resolve Wannier90 input artifacts from preprocessing.

    Searches for .amn, .mmn, .eig files from w90_preproc step
    or any other step that produces them.

    Args:
        context: Step context with calculation info
        explicit_source: Explicitly specified source step

    Returns:
        Dict mapping artifact type to path

    Raises:
        FileNotFoundError: If required artifacts not found
    """
    required_artifacts = ["w90_amn", "w90_mmn", "w90_eig"]
    found = {}

    # Try explicit source first
    if explicit_source:
        step_dir = context.get_step_dir(explicit_source)
        if step_dir:
            found = _find_artifacts_in_dir(step_dir, required_artifacts)
            if len(found) == len(required_artifacts):
                return found
            logger.warning(
                f"Not all artifacts found in explicit source '{explicit_source}'"
            )

    # Search completed steps for w90_preproc or any step with artifacts
    for prev_step in reversed(context.completed_steps):
        step_dir = context.get_step_dir(prev_step)
        if not step_dir:
            continue

        # Check if this step has W90 artifacts
        step_artifacts = _find_artifacts_in_dir(step_dir, required_artifacts)
        if step_artifacts:
            for art_type, path in step_artifacts.items():
                if art_type not in found:
                    found[art_type] = path
                    logger.debug(f"Found {art_type} in {prev_step}")

        if len(found) == len(required_artifacts):
            break

    # Verify all required artifacts found
    missing = [a for a in required_artifacts if a not in found]
    if missing:
        raise FileNotFoundError(
            f"Missing Wannier90 artifacts: {', '.join(missing)}. "
            "Ensure w90_preproc step completed successfully."
        )

    return found


def _find_artifacts_in_dir(
    directory: Path,
    artifact_types: list[str],
) -> Dict[str, Path]:
    """Find artifacts in a directory.

    Args:
        directory: Directory to search
        artifact_types: List of artifact types to find

    Returns:
        Dict mapping found artifact types to paths
    """
    # Get patterns from W90 driver
    try:
        driver = DriverRegistry.get_driver("w90")
        patterns = driver.get_artifact_patterns()
    except Exception:
        # Fallback patterns if driver not available
        patterns = {
            "w90_amn": "*.amn",
            "w90_mmn": "*.mmn",
            "w90_eig": "*.eig",
        }

    found = {}
    for art_type in artifact_types:
        pattern = patterns.get(art_type)
        if not pattern:
            continue

        matches = list(directory.glob(pattern))
        if matches:
            found[art_type] = matches[0]

    return found

