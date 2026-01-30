"""
Manifest reconciliation logic.

Reconciles old manifest with current calculation topology (step list).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Tuple

from quantumvitas.calculation.manifest import (
    Manifest,
    ManifestStepEntry,
    load_manifest,
    save_manifest_atomic,
    now_iso8601,
    should_skip_step,
)
from quantumvitas.calculation.hash_utils import (
    compute_structure_sha,
    compute_step_sha,
    compute_pseudo_set_sha,
)
from quantumvitas.calculation.step_done import is_step_done

logger = logging.getLogger(__name__)


def reconcile_manifest(
    calc_dir: Path,
    project_root: Path,
    calculation_steps: List[Any],  # List[Step] but avoid circular import
    current_pseudo_set_sha: str,
    structure_path: Path,
) -> Tuple[Manifest, int]:
    """
    Reconcile manifest with current calculation topology.
    
    Args:
        calc_dir: Calculation directory
        project_root: Project root path
        calculation_steps: List of Step objects (current topology)
        current_pseudo_set_sha: Fresh pseudo set SHA (computed in preflight)
        structure_path: Path to structure JSON file
        
    Returns:
        Tuple of (reconciled_manifest, first_changed_index)
        first_changed_index is the first step that needs rerun (or len(steps) if all done)
    """
    # Load old manifest (if exists)
    old_manifest = load_manifest(calc_dir)
    
    # Compute structure SHA once
    structure_sha = compute_structure_sha(structure_path)
    
    # Load calculation ID once (used for resolving steps)
    from quantumvitas.core.models import load_calculation
    from quantumvitas.core.resolution import require_step
    from quantumvitas.core.project_utils import load_project_config
    
    calc_model = load_calculation(calc_dir / "calculation.yaml", project_root=project_root)
    calculation_id = calc_model.meta.ulid
    config = load_project_config(project_root)
    
    # Build new manifest aligned to current topology
    new_steps: List[ManifestStepEntry] = []
    first_changed_idx = len(calculation_steps)  # Default: all done
    
    # Process all steps in topology (even if old manifest is shorter)
    for i, step in enumerate(calculation_steps):
        # Get step kind (step type)
        step_kind = str(step.step_type_spec) if step.step_type_spec else "unknown"
        # Use step.meta.ulid (ULID) instead of step.id (slug)
        step_ulid = step.meta.ulid
        
        # Load step YAML to compute step_sha
        from quantumvitas.core.yamldoc import StepDoc
        
        # Resolve the step using calculation_id and step ULID
        step_resolved = require_step(project_root, calculation_id, step_ulid, config=config)
        step_yaml_path = step_resolved.absolute_path
        
        try:
            step_doc_dict = StepDoc.load(step_yaml_path).to_dict()
            step_sha = compute_step_sha(step_doc_dict)
        except Exception as e:
            logger.warning(f"Failed to compute step_sha for step {step.meta.slug} (ulid={step.meta.ulid}): {e}")
            step_sha = ""
        
        # Check if old manifest has matching entry
        if old_manifest and i < len(old_manifest.steps):
            old_entry = old_manifest.steps[i]
            
            # Check kind match
            if old_entry.kind == step_kind:
                # Kind matches: check if SHAs match
                shas_match = (
                    old_entry.pseudo_set_sha == current_pseudo_set_sha and
                    old_entry.structure_sha == structure_sha and
                    old_entry.step_sha == step_sha
                )
                
                if shas_match:
                    # SHAs match: verify step is actually done using StepDonePolicy
                    # Phase 3C: Also check if step supports incremental skip
                    from quantumvitas.core.yamldoc import StepDoc
                    from quantumvitas.core.resolution import require_step
                    from quantumvitas.core.project_utils import load_project_config
                    from quantumvitas.workflow.registry import get_registry
                    
                    try:
                        # Use same calculation_id and config from above, with step ULID
                        step_resolved = require_step(project_root, calculation_id, step_ulid, config=config)
                        step_doc = StepDoc.load(step_resolved.absolute_path)
                        step_doc_dict = step_doc.to_dict()
                        
                        # Phase 3C: Check if step supports incremental skip
                        registry = get_registry()
                        spec = registry.get(step_kind)
                        supports_skip = spec.supports_incremental_skip if spec else True  # Default to True for backward compat
                        
                        if not supports_skip:
                            # Step does not support incremental skip - force rerun even if SHAs match
                            new_entry = ManifestStepEntry(
                                kind=step_kind,
                                step_ulid=step_ulid,
                                pseudo_set_sha=current_pseudo_set_sha,
                                structure_sha=structure_sha,
                                step_sha=step_sha,
                                run_ulid=old_entry.run_ulid,
                                done=False,  # Force rerun
                                started_at=None,
                                done_at=None,
                            )
                            new_steps.append(new_entry)
                            if first_changed_idx > i:
                                first_changed_idx = i
                            continue
                        
                        # Check if step is actually done (verify output file exists and contains success marker)
                        calc_raw_dir = calc_dir / "raw"
                        actually_done = is_step_done(calc_dir, step_kind, calc_raw_dir=calc_raw_dir, step_doc=step_doc_dict)
                        
                        if actually_done:
                            # All match and actually done: keep old entry (update ULID and SHAs but keep done/run_id/timestamps)
                            new_entry = ManifestStepEntry(
                                kind=step_kind,
                                step_ulid=step_ulid,  # Update ULID to current
                                pseudo_set_sha=current_pseudo_set_sha,
                                structure_sha=structure_sha,
                                step_sha=step_sha,
                                run_ulid=old_entry.run_ulid,  # Keep old run_id
                                done=True,  # Verified as done
                                started_at=old_entry.started_at,  # Keep timestamps
                                done_at=old_entry.done_at,
                            )
                            new_steps.append(new_entry)
                            # Don't update first_changed_idx (step is skipped)
                            continue
                        else:
                            # SHAs match but step not actually done: mark as not done
                            new_entry = ManifestStepEntry(
                                kind=step_kind,
                                step_ulid=step_ulid,
                                pseudo_set_sha=current_pseudo_set_sha,
                                structure_sha=structure_sha,
                                step_sha=step_sha,
                                run_ulid=old_entry.run_ulid,
                                done=False,  # Not actually done
                                started_at=None,
                                done_at=None,
                            )
                            new_steps.append(new_entry)
                            if first_changed_idx > i:
                                first_changed_idx = i
                            continue
                    except Exception as e:
                        logger.warning(f"Failed to verify step done status for step {step.meta.slug} (ulid={step.meta.ulid}): {e}, marking as not done")
                        # On error, mark as not done
                        new_entry = ManifestStepEntry(
                            kind=step_kind,
                            step_ulid=step_ulid,
                            pseudo_set_sha=current_pseudo_set_sha,
                            structure_sha=structure_sha,
                            step_sha=step_sha,
                            run_ulid=old_entry.run_ulid,
                            done=False,
                            started_at=None,
                            done_at=None,
                        )
                        new_steps.append(new_entry)
                        if first_changed_idx > i:
                            first_changed_idx = i
                        continue
                else:
                    # SHAs changed: mark as not done (must rerun)
                    new_entry = ManifestStepEntry(
                        kind=step_kind,
                        step_ulid=step_ulid,
                        pseudo_set_sha=current_pseudo_set_sha,
                        structure_sha=structure_sha,
                        step_sha=step_sha,
                        run_ulid=old_entry.run_ulid,  # Keep run_id but done=false
                        done=False,  # Force rerun
                        started_at=None,
                        done_at=None,
                    )
                    new_steps.append(new_entry)
                    if first_changed_idx > i:
                        first_changed_idx = i
                    continue
            else:
                # Kind mismatch: from this index onward, create fresh entries with done=false
                if first_changed_idx > i:
                    first_changed_idx = i
                # Continue to create fresh entries for remaining steps (don't break)
                # Clear run_id and timestamps on kind mismatch
                new_entry = ManifestStepEntry(
                    kind=step_kind,
                    step_ulid=step_ulid,
                    pseudo_set_sha=current_pseudo_set_sha,
                    structure_sha=structure_sha,
                    step_sha=step_sha,
                    run_ulid=None,  # Clear run_ulid on kind mismatch
                    done=False,
                    started_at=None,  # Clear timestamps on kind mismatch
                    done_at=None,
                )
                new_steps.append(new_entry)
                continue
        else:
            # Old manifest shorter or missing: create fresh entry
            new_entry = ManifestStepEntry(
                kind=step_kind,
                step_ulid=step_ulid,
                pseudo_set_sha=current_pseudo_set_sha,
                structure_sha=structure_sha,
                step_sha=step_sha,
                run_ulid=None,
                done=False,
                started_at=None,
                done_at=None,
            )
            new_steps.append(new_entry)
            if first_changed_idx > i:
                first_changed_idx = i
    
    # Create new manifest (only contains entries up to len(calculation_steps))
    # Topo shorter than old manifest is handled by only processing len(calculation_steps) entries
    new_manifest = Manifest(steps=new_steps)
    
    # Ensure we have exactly len(calculation_steps) entries (should already be true, but double-check)
    assert len(new_manifest.steps) == len(calculation_steps), \
        f"Manifest length mismatch: {len(new_manifest.steps)} != {len(calculation_steps)}"
    
    # Save reconciled manifest
    save_manifest_atomic(calc_dir, new_manifest)
    
    return new_manifest, first_changed_idx

