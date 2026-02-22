"""VASP artifact staging: CHGCAR and WAVECAR copying from reference SCF.

Implements the staging rules from VASP integration plan v2.0:
- Non-SCF steps: CHGCAR is prerequisite (done==True AND file exists) → hard error if fail
- SCF steps: CHGCAR is optional → skip silently if fail
- WAVECAR: Optional for all steps, warning if copy fails
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from qmatsuite.calculation.manifest import ManifestStepEntry
    from qmatsuite.calculation.step import Step

logger = logging.getLogger(__name__)


class MissingPrerequisiteError(Exception):
    """Raised when a prerequisite step is not done."""
    pass


class MissingArtifactError(Exception):
    """Raised when a required artifact file is missing."""
    pass


def is_scf_step(step: "Step", registry=None) -> bool:
    """
    Check if step is an SCF step.

    Args:
        step: Step object
        registry: Optional StepTypeRegistry

    Returns:
        True if step is SCF, False otherwise
    """
    if registry is None:
        from qmatsuite.workflow.registry import get_registry
        registry = get_registry()

    from qmatsuite.workflow.step_type_convert import is_spec
    from qmatsuite.execution.step_type_unpack import unpack_step_type, unpack_step_type_safe

    step_type_spec = getattr(step, 'step_type_spec', None)
    if not step_type_spec:
        return False

    step_type_str = str(step_type_spec)

    # Per constitution, registry.get() only accepts GEN types
    # Convert SPEC to GEN via centralized choke point (Constitution §4.3)
    if is_spec(step_type_str):
        unpacked = unpack_step_type(step_type_str)
        spec = registry.get_for_engine(unpacked.gen, unpacked.prefix)
    else:
        spec = registry.get(step_type_str)

    if spec:
        return spec.step_type_gen == "scf"

    # Fallback: use unpack_step_type_safe for either SPEC or GEN
    unpacked = unpack_step_type_safe(step_type_str)
    return unpacked.gen == "scf"


def stage_chgcar(
    current_step: "Step",
    reference_scf_step: "Step",
    manifest_entry: Optional["ManifestStepEntry"],
    calc_raw_dir: Path,
    target_workdir: Path,
) -> None:
    """
    Stage CHGCAR from reference SCF to current step workdir.
    
    Rules:
    - Non-SCF steps: Prerequisite (done==True AND file exists) → hard error if fail
    - SCF steps: Optional → skip silently if fail
    
    Args:
        current_step: Current step that needs CHGCAR
        reference_scf_step: Reference SCF step
        manifest_entry: Manifest entry for reference SCF step (None if not found)
        calc_raw_dir: Calculation raw directory (contains step workdirs)
        target_workdir: Target workdir for current step
    
    Raises:
        MissingPrerequisiteError: If non-SCF step and reference is not done
        MissingArtifactError: If non-SCF step and CHGCAR file is missing
    """
    is_current_scf = is_scf_step(current_step)
    
    # Check manifest entry
    # If manifest_entry is None, try to check if step is actually done by checking output files
    if manifest_entry is None or not manifest_entry.done:
        # For non-SCF steps, also check if reference SCF output files exist
        # This handles the case where manifest hasn't been updated yet
        if not is_current_scf:
            ref_workdir = calc_raw_dir / reference_scf_step.meta.ulid
            chgcar_src = ref_workdir / "CHGCAR"
            outcar_src = ref_workdir / "OUTCAR"
            
            # If CHGCAR and OUTCAR exist, consider SCF done even if manifest says otherwise
            if chgcar_src.exists() and outcar_src.exists():
                # Check if OUTCAR has energy (indicates successful completion)
                try:
                    outcar_text = outcar_src.read_text()
                    if "free  energy   TOTEN" in outcar_text:
                        logger.info(
                            f"Reference SCF step {reference_scf_step.meta.ulid} appears done "
                            f"(output files exist) even though manifest says not done. Proceeding."
                        )
                        # Proceed with staging
                    else:
                        # OUTCAR exists but no energy - not done
                        raise MissingPrerequisiteError(
                            f"Reference SCF step {reference_scf_step.meta.ulid} is not done. "
                            f"Run SCF first before running {current_step.step_type_spec}."
                        )
                except Exception as e:
                    # Error reading OUTCAR - assume not done
                    raise MissingPrerequisiteError(
                        f"Reference SCF step {reference_scf_step.meta.ulid} is not done. "
                        f"Run SCF first before running {current_step.step_type_spec}."
                    ) from e
            else:
                # Output files don't exist - definitely not done
                raise MissingPrerequisiteError(
                    f"Reference SCF step {reference_scf_step.meta.ulid} is not done. "
                    f"Run SCF first before running {current_step.step_type_spec}."
                )
        else:
            # SCF: optional, skip silently
            logger.debug(
                f"CHGCAR staging skipped for SCF step {current_step.meta.ulid}: "
                f"reference SCF {reference_scf_step.meta.ulid} is not done"
            )
            return
    
    # Check file exists
    ref_workdir = calc_raw_dir / reference_scf_step.meta.ulid
    chgcar_src = ref_workdir / "CHGCAR"
    
    if not chgcar_src.exists():
        if is_current_scf:
            # SCF: optional, skip silently
            logger.debug(
                f"CHGCAR staging skipped for SCF step {current_step.meta.ulid}: "
                f"CHGCAR not found in reference SCF workdir {ref_workdir}"
            )
            return
        else:
            # Non-SCF: prerequisite, hard error
            raise MissingArtifactError(
                f"CHGCAR not found in reference SCF workdir: {ref_workdir}. "
                f"Reference SCF step {reference_scf_step.meta.ulid} must produce CHGCAR "
                f"before running {current_step.step_type_spec}."
            )
    
    # Copy CHGCAR
    chgcar_dst = target_workdir / "CHGCAR"
    try:
        shutil.copy2(chgcar_src, chgcar_dst)
        logger.info(
            f"Copied CHGCAR from {reference_scf_step.meta.ulid} to {current_step.meta.ulid}"
        )
    except Exception as e:
        if is_current_scf:
            # SCF: optional, log warning but don't fail
            logger.warning(
                f"Failed to copy CHGCAR for SCF step {current_step.meta.ulid}: {e}"
            )
            return
        else:
            # Non-SCF: prerequisite, hard error
            raise MissingArtifactError(
                f"Failed to copy CHGCAR from {ref_workdir} to {target_workdir}: {e}"
            ) from e


def stage_wavecar(
    current_step: "Step",
    reference_scf_step: "Step",
    manifest_entry: Optional["ManifestStepEntry"],
    calc_raw_dir: Path,
    target_workdir: Path,
    required: bool = False,
) -> bool:
    """
    Stage WAVECAR from reference SCF to current step workdir.
    
    WAVECAR is optional for all steps. If copy fails, log warning and return False.
    If required=True, raise error on failure.
    
    Args:
        current_step: Current step that needs WAVECAR
        reference_scf_step: Reference SCF step
        manifest_entry: Manifest entry for reference SCF step (None if not found)
        calc_raw_dir: Calculation raw directory (contains step workdirs)
        target_workdir: Target workdir for current step
        required: If True, raise error on failure; if False, log warning and return False
    
    Returns:
        True if WAVECAR was successfully copied, False otherwise
    
    Raises:
        MissingArtifactError: If required=True and copy fails
    """
    # Check manifest entry
    if manifest_entry is None or not manifest_entry.done:
        if required:
            raise MissingPrerequisiteError(
                f"Reference SCF step {reference_scf_step.meta.ulid} is not done. "
                f"Cannot copy WAVECAR for {current_step.step_type_spec}."
            )
        logger.debug(
            f"WAVECAR staging skipped: reference SCF {reference_scf_step.meta.ulid} is not done"
        )
        return False
    
    # Check file exists
    ref_workdir = calc_raw_dir / reference_scf_step.meta.ulid
    wavecar_src = ref_workdir / "WAVECAR"
    
    if not wavecar_src.exists():
        if required:
            raise MissingArtifactError(
                f"WAVECAR not found in reference SCF workdir: {ref_workdir}"
            )
        logger.debug(
            f"WAVECAR staging skipped: WAVECAR not found in {ref_workdir}"
        )
        return False
    
    # Copy WAVECAR
    wavecar_dst = target_workdir / "WAVECAR"
    try:
        shutil.copy2(wavecar_src, wavecar_dst)
        logger.info(
            f"Copied WAVECAR from {reference_scf_step.meta.ulid} to {current_step.meta.ulid}"
        )
        return True
    except Exception as e:
        if required:
            raise MissingArtifactError(
                f"Failed to copy WAVECAR from {ref_workdir} to {target_workdir}: {e}"
            ) from e
        logger.warning(
            f"Failed to copy WAVECAR for step {current_step.meta.ulid}: {e}"
        )
        return False

