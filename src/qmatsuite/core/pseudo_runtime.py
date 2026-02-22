"""
Pseudo runtime preparation (Step0) - Constitution-compliant implementation.

This module is the ONLY place allowed to mutate project/pseudo.
All filesystem operations that touch project/pseudo must happen here, during Step0.

Constitution rules:
- Only 3 sources: internal (qmatsuite/resources/pseudo), lib (.qmatsuite/libraries/pseudo/...), project (project/pseudo)
- QE runtime only reads project/pseudo
- sha_family is primary for physical equivalence
- sha256 is strict bytes identity
- All mutations happen in Step0 only (before first QE step)
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from qmatsuite.core.pseudo import get_system_pseudo_dir
from qmatsuite.core.pseudo_config import load_pseudo_config
from qmatsuite.core.pseudo_libinfo import load_pseudo_libinfo_bundle
from qmatsuite.core.pseudo_provenance import (
    _build_occurrences_index,
    compute_sha256_file,
    compute_sha_family_file,
)
from qmatsuite.core.paths import home_pseudo_libraries_dir


class PseudoSourceKind(str, Enum):
    """The three allowed pseudo sources per constitution."""
    PROJECT = "project"  # project/pseudo
    INTERNAL = "internal"  # qmatsuite/resources/pseudo
    LIB = "lib"  # .qmatsuite/libraries/pseudo/... (installed libraries)


@dataclass
class PseudoSelection:
    """
    A pseudo selection for an element (input to Step0).
    
    Represents what the user selected for a given element.
    """
    element: str
    requested_basename: str  # Filename to appear in project/pseudo
    requested_sha256: Optional[str] = None  # Optional: if provided, must match
    requested_sha_family: Optional[str] = None  # Optional: if provided, used for physical equivalence
    source_kind: Literal["project", "internal", "lib"] = "project"
    source_path: Optional[Path] = None  # For internal/lib; None for project selection


@dataclass
class PseudoPrepareAction:
    """A single action taken during Step0 preparation (loggable)."""
    action: Literal["noop", "copy", "overwrite", "rename_existing", "error"]
    element: str
    detail: str
    source_path: Optional[Path] = None
    dest_path: Optional[Path] = None
    renamed_from: Optional[Path] = None
    renamed_to: Optional[Path] = None


@dataclass
class PseudoPrepareReport:
    """Report of Step0 preparation actions."""
    actions: List[PseudoPrepareAction] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    def has_errors(self) -> bool:
        """Check if report contains errors."""
        return len(self.errors) > 0


def _resolve_lib_source_path(
    element: str,
    requested_basename: str,
    requested_sha_family: Optional[str],
    config: Any,
) -> Optional[Path]:
    """
    Resolve a lib source path for a given element/basename/sha_family.

    Searches installed pseudo libraries (NEW layout) for matching UPF file.

    Returns:
        Path to source file if found, None otherwise
    """
    from qmatsuite.pseudo.layout import iter_installed_libraries

    libraries_root = home_pseudo_libraries_dir()
    for lib in iter_installed_libraries(libraries_root):
        upf_path = lib.install_dir / requested_basename
        if not upf_path.is_file():
            # Try case-insensitive match
            target_lower = requested_basename.lower()
            for f in lib.install_dir.iterdir():
                if f.name.lower() == target_lower and f.is_file():
                    upf_path = f
                    break
            else:
                continue
        # Optionally verify sha_family
        if requested_sha_family:
            file_sha_family = compute_sha_family_file(upf_path)
            if file_sha_family != requested_sha_family:
                continue
        return upf_path

    return None


def _resolve_internal_source_path(
    element: str,
    requested_basename: str,
    requested_sha_family: Optional[str],
) -> Optional[Path]:
    """
    Resolve an internal source path for a given element/basename/sha_family.
    
    Searches qmatsuite/resources/pseudo for matching pseudo.
    
    Returns:
        Path to source file if found, None otherwise
    """
    internal_pseudo_dir = get_system_pseudo_dir()
    if not internal_pseudo_dir or not internal_pseudo_dir.exists():
        return None
    
    # Search by basename
    for pseudo_file in internal_pseudo_dir.glob(f"{requested_basename}"):
        if pseudo_file.is_file():
            # Optionally verify sha_family
            if requested_sha_family:
                file_sha_family = compute_sha_family_file(pseudo_file)
                if file_sha_family != requested_sha_family:
                    continue
            return pseudo_file
    
    # Try case-insensitive
    for pseudo_file in internal_pseudo_dir.glob("*.UPF"):
        if pseudo_file.name.lower() == requested_basename.lower():
            if requested_sha_family:
                file_sha_family = compute_sha_family_file(pseudo_file)
                if file_sha_family != requested_sha_family:
                    continue
            return pseudo_file
    
    return None


def analyze_project_pseudo_effects(
    project_root: Path,
    selections: List[PseudoSelection],
) -> PseudoPrepareReport:
    """
    Read-only analyzer for pseudo preparation effects (safe for UI).
    
    This function does NOT modify the filesystem. It analyzes what would happen
    if prepare_project_pseudos_for_run() were called with these selections.
    
    Args:
        project_root: Project root path
        selections: List of pseudo selections
        
    Returns:
        PseudoPrepareReport with actions/warnings/errors (no mutations performed)
    """
    report = PseudoPrepareReport()
    project_pseudo_dir = project_root / "pseudo"
    
    config = load_pseudo_config()
    
    for selection in selections:
        dst = project_pseudo_dir / selection.requested_basename
        
        # Check if destination exists
        if dst.exists():
            existing_sha256 = compute_sha256_file(dst)
            existing_sha_family = compute_sha_family_file(dst)
            
            # Resolve source if needed
            source_path = selection.source_path
            if selection.source_kind == "internal" and not source_path:
                source_path = _resolve_internal_source_path(
                    selection.element,
                    selection.requested_basename,
                    selection.requested_sha_family,
                )
            elif selection.source_kind == "lib" and not source_path:
                source_path = _resolve_lib_source_path(
                    selection.element,
                    selection.requested_basename,
                    selection.requested_sha_family,
                    config,
                )
            
            if source_path and source_path.exists():
                source_sha256 = compute_sha256_file(source_path)
                source_sha_family = compute_sha_family_file(source_path)
                
                # Apply collision rules
                if existing_sha256 == source_sha256:
                    report.actions.append(PseudoPrepareAction(
                        action="noop",
                        element=selection.element,
                        detail=f"File already exists with same sha256",
                        dest_path=dst,
                    ))
                elif existing_sha_family == source_sha_family:
                    # Same physical, different bytes - overwrite
                    report.actions.append(PseudoPrepareAction(
                        action="overwrite",
                        element=selection.element,
                        detail=f"Same sha_family but different sha256; will overwrite with canonical",
                        source_path=source_path,
                        dest_path=dst,
                    ))
                    report.warnings.append(
                        f"{selection.element}: Project pseudo will be overwritten with canonical library/internal version "
                        f"(sha_family same but sha256 differs)"
                    )
                else:
                    # Different sha_family - must rename
                    report.actions.append(PseudoPrepareAction(
                        action="rename_existing",
                        element=selection.element,
                        detail=f"Different sha_family; will rename existing file",
                        dest_path=dst,
                    ))
                    report.warnings.append(
                        f"{selection.element}: Project pseudo '{selection.requested_basename}' exists with different sha_family. "
                        f"Run will rename existing file and update affected calcs."
                    )
            else:
                if selection.source_kind != "project":
                    report.errors.append(
                        f"{selection.element}: Source file not found for {selection.source_kind} selection"
                    )
        else:
            # Destination doesn't exist - will copy
            if selection.source_kind == "project":
                report.errors.append(
                    f"{selection.element}: Project selection but file not found at {dst}"
                )
            else:
                report.actions.append(PseudoPrepareAction(
                    action="copy",
                    element=selection.element,
                    detail=f"Will copy from {selection.source_kind}",
                    source_path=source_path,
                    dest_path=dst,
                ))
    
    return report


def prepare_project_pseudos_for_run(
    project_root: Path,
    selections: List[PseudoSelection],
) -> PseudoPrepareReport:
    """
    Step0 executor: Prepare pseudos in project/pseudo for QE execution.
    
    This is the ONLY function allowed to mutate project/pseudo.
    Must be called before any QE step execution.
    
    Args:
        project_root: Project root path
        selections: List of pseudo selections
        
    Returns:
        PseudoPrepareReport with actions taken
        
    Raises:
        RuntimeError: If preparation fails (errors in report)
    """
    report = PseudoPrepareReport()
    project_pseudo_dir = project_root / "pseudo"
    
    # Ensure project/pseudo exists (only mkdir allowed here)
    project_pseudo_dir.mkdir(parents=True, exist_ok=True)
    
    # GUARD: Never use repo_root/pseudo
    from qmatsuite.core.pseudo_config import _find_qmatsuite_root
    repo_root = _find_qmatsuite_root()
    if repo_root:
        repo_pseudo = (repo_root / "pseudo").resolve()
        project_pseudo_resolved = project_pseudo_dir.resolve()
        if project_pseudo_resolved == repo_pseudo:
            raise RuntimeError(
                f"BUG: prepare_project_pseudos_for_run attempted to use repo_root/pseudo at {project_pseudo_dir}. "
                f"Internal pseudo library must be at resources/pseudo, not repo_root/pseudo."
            )
    
    config = load_pseudo_config()
    
    for selection in selections:
        dst = project_pseudo_dir / selection.requested_basename
        
        # Resolve source path if needed
        source_path = selection.source_path
        if selection.source_kind == "project":
            # Project selection: verify file exists
            if not dst.exists():
                report.errors.append(
                    f"{selection.element}: Project pseudo '{selection.requested_basename}' not found at {dst}"
                )
                continue
            # No copy needed for project selection
            report.actions.append(PseudoPrepareAction(
                action="noop",
                element=selection.element,
                detail=f"Using existing project pseudo",
                dest_path=dst,
            ))
            continue
        
        elif selection.source_kind in ("internal", "lib"):
            # Try internal first, then lib
            if not source_path:
                source_path = _resolve_internal_source_path(
                    selection.element,
                    selection.requested_basename,
                    selection.requested_sha_family,
                )
                if source_path and source_path.exists():
                    selection.source_kind = "internal"
                else:
                    # Try lib
                    source_path = _resolve_lib_source_path(
                        selection.element,
                        selection.requested_basename,
                        selection.requested_sha_family,
                        config,
                    )
                    if source_path and source_path.exists():
                        selection.source_kind = "lib"
            
            if not source_path or not source_path.exists():
                report.errors.append(
                    f"{selection.element}: Pseudo '{selection.requested_basename}' not found in internal or installed libraries"
                )
                continue
        
        # Compute source hashes
        source_sha256 = compute_sha256_file(source_path)
        source_sha_family = compute_sha_family_file(source_path)
        
        # Verify requested hashes if provided
        if selection.requested_sha256 and source_sha256 != selection.requested_sha256:
            report.errors.append(
                f"{selection.element}: Source sha256 mismatch: expected {selection.requested_sha256[:16]}..., "
                f"got {source_sha256[:16]}..."
            )
            continue
        
        if selection.requested_sha_family and source_sha_family != selection.requested_sha_family:
            report.errors.append(
                f"{selection.element}: Source sha_family mismatch: expected {selection.requested_sha_family[:16]}..., "
                f"got {source_sha_family[:16]}..."
            )
            continue
        
        # Apply collision rules (only for internal/lib selections; project selections already handled above)
        if dst.exists():
            existing_sha256 = compute_sha256_file(dst)
            existing_sha_family = compute_sha_family_file(dst)
            
            if existing_sha256 == source_sha256:
                # Same sha256: noop
                report.actions.append(PseudoPrepareAction(
                    action="noop",
                    element=selection.element,
                    detail=f"File already exists with same sha256",
                    dest_path=dst,
                ))
                continue
            
            elif existing_sha_family == source_sha_family:
                # Same sha_family, different sha256: overwrite with canonical (no rename)
                shutil.copy2(source_path, dst)
                report.actions.append(PseudoPrepareAction(
                    action="overwrite",
                    element=selection.element,
                    detail=f"Overwritten with canonical version (sha_family same, sha256 differs)",
                    source_path=source_path,
                    dest_path=dst,
                ))
                continue
            
            else:
                # Different sha_family: rename existing
                # Deterministic rename: <basename>__fam-<sha_family[:10]>.upf
                stem = dst.stem
                suffix = dst.suffix
                renamed_to = project_pseudo_dir / f"{stem}__fam-{existing_sha_family[:10]}{suffix}"
                
                # Ensure renamed filename is unique
                counter = 1
                while renamed_to.exists():
                    renamed_to = project_pseudo_dir / f"{stem}__fam-{existing_sha_family[:10]}_{counter}{suffix}"
                    counter += 1
                
                dst.rename(renamed_to)
                report.actions.append(PseudoPrepareAction(
                    action="rename_existing",
                    element=selection.element,
                    detail=f"Renamed existing file due to sha_family mismatch",
                    renamed_from=dst,
                    renamed_to=renamed_to,
                ))
                
                # Update project calcs by sha_family
                updated_count = update_project_calcs_filename_by_sha_family(
                    project_root,
                    existing_sha_family,
                    selection.requested_basename,
                    renamed_to.name,
                )
                report.warnings.append(
                    f"{selection.element}: Renamed existing '{selection.requested_basename}' to '{renamed_to.name}'. "
                    f"Updated {updated_count} calculation(s) by sha_family."
                )
        
        # Copy source to destination
        shutil.copy2(source_path, dst)
        report.actions.append(PseudoPrepareAction(
            action="copy",
            element=selection.element,
            detail=f"Copied from {selection.source_kind}",
            source_path=source_path,
            dest_path=dst,
        ))
    
    if report.has_errors():
        raise RuntimeError(
            f"Step0 pseudo preparation failed:\n" + "\n".join(report.errors)
        )
    
    return report


def update_project_calcs_filename_by_sha_family(
    project_root: Path,
    sha_family: str,
    old_filename: str,
    new_filename: str,
) -> int:
    """
    Update project calculations that reference a pseudo by sha_family.
    
    When a file is renamed due to sha_family collision, this function finds all
    calculations in the project that reference the old filename with matching
    sha_family and updates only their filename field (not sha256/sha_family).
    
    Args:
        project_root: Project root path
        sha_family: The sha_family of the renamed file
        old_filename: Old filename (before rename)
        new_filename: New filename (after rename)
        
    Returns:
        Number of calculations updated
    """
    from qmatsuite.core.resolution import build_resource_index
    from qmatsuite.core.models import load_calculation, save_calculation
    from qmatsuite.core.project_utils import load_project_config
    
    config = load_project_config(project_root)
    index = build_resource_index(project_root)
    
    updated_count = 0
    
    # Scan all calculations
    calculations_dir = project_root / "calculations"
    if not calculations_dir.exists():
        return 0
    
    for calculation_dir in calculations_dir.iterdir():
        if not calculation_dir.is_dir():
            continue
        
        calculation_yaml = calculation_dir / "calculation.yaml"
        if not calculation_yaml.exists():
            continue
        
        try:
            wf_model = load_calculation(calculation_yaml, project_root=project_root)
            
            if not wf_model.species_map:
                continue
            
            # Check each element in species_map
            updated = False
            for element, entry in wf_model.species_map.items():
                if not isinstance(entry, dict):
                    continue
                
                # Check if this entry references the old filename with matching sha_family
                entry_filename = entry.get("pseudopot") or entry.get("pseudo_basename")
                entry_sha_family = entry.get("pseudo_sha_family")
                
                if (entry_filename == old_filename and 
                    entry_sha_family == sha_family):
                    # Update filename only (keep sha256/sha_family unchanged)
                    entry["pseudopot"] = new_filename
                    if "pseudo_basename" in entry:
                        entry["pseudo_basename"] = new_filename
                    updated = True
            
            if updated:
                save_calculation(wf_model, calculation_yaml)
                updated_count += 1
        
        except Exception:
            # Skip calculations that fail to load
            continue
    
    return updated_count


def species_map_to_selections(
    project_root: Path,
    species_map: Dict[str, Dict[str, Any]],
) -> List[PseudoSelection]:
    """
    Convert a calculation's species_map to PseudoSelection list for Step0.
    
    Args:
        project_root: Project root path
        species_map: Species mapping from calculation (element -> {pseudopot, pseudo_sha256, ...})
        
    Returns:
        List of PseudoSelection objects
    """
    selections: List[PseudoSelection] = []
    project_pseudo_dir = project_root / "pseudo"
    
    for element, entry in species_map.items():
        if not isinstance(entry, dict):
            continue
        
        # Determine basename
        basename = entry.get("pseudo_basename") or entry.get("pseudopot") or f"{element}.upf"
        sha256 = entry.get("pseudo_sha256")
        sha_family = entry.get("pseudo_sha_family")
        
        # Determine source kind based on sha256
        # If project/pseudo has file with matching sha256, it's a project selection
        source_kind: Literal["project", "internal", "lib"] = "internal"  # Default to internal
        source_path: Optional[Path] = None
        
        project_file = project_pseudo_dir / basename
        if project_file.exists() and sha256:
            # Check if project file matches the requested sha256
            try:
                file_sha256 = compute_sha256_file(project_file)
                if file_sha256 == sha256:
                    # Project file matches sha256: it's a project selection
                    source_kind = "project"
                    source_path = None  # Project selection doesn't need source_path
            except Exception:
                # Can't compute hash - treat as external
                pass
        
        # If not project, will be resolved in prepare_project_pseudos_for_run()
        
        selections.append(PseudoSelection(
            element=element,
            requested_basename=basename,
            requested_sha256=sha256,
            requested_sha_family=sha_family,
            source_kind=source_kind,
            source_path=source_path,
        ))
    
    return selections


def refresh_calc_pseudo_records_after_step0(
    project_root: Path,
    calculation_dir: Path,
    species_map: Dict[str, Dict[str, Any]],
) -> None:
    """
    Refresh calculation pseudo records (filename, sha256, sha_family) after Step0.
    
    This updates the calculation's species_map with the actual files in project/pseudo
    after Step0 preparation.
    
    Args:
        project_root: Project root path
        calculation_dir: Calculation directory
        species_map: Species map from calculation (will be updated in-place)
    """
    from qmatsuite.core.models import load_calculation, save_calculation
    
    calculation_yaml = calculation_dir / "calculation.yaml"
    if not calculation_yaml.exists():
        return
    
    wf_model = load_calculation(calculation_yaml, project_root=project_root)
    if not wf_model.species_map:
        return
    
    project_pseudo_dir = project_root / "pseudo"
    
    # Update each element's record with actual file info
    import logging
    logger = logging.getLogger(__name__)
    
    for element, entry in species_map.items():
        if element not in wf_model.species_map:
            continue
        
        calc_entry = wf_model.species_map[element]
        if not isinstance(calc_entry, dict):
            continue
        
        # Get basename from entry
        basename = entry.get("pseudo_basename") or entry.get("pseudopot") or f"{element}.upf"
        
        # Check actual file in project/pseudo
        actual_file = project_pseudo_dir / basename
        if actual_file.exists():
            actual_sha256 = compute_sha256_file(actual_file)
            actual_sha_family = compute_sha_family_file(actual_file)
            
            # Update record
            calc_entry["pseudopot"] = basename
            calc_entry["pseudo_basename"] = basename
            calc_entry["pseudo_sha256"] = actual_sha256
            calc_entry["pseudo_sha_family"] = actual_sha_family
        else:
            # File missing: log warning and keep stored triplet unchanged (preserves current semantics)
            # This can happen if Step0 failed or file was manually deleted after Step0
            logger.warning(
                f"refresh_calc_pseudo_records_after_step0: "
                f"Pseudo file '{basename}' for element '{element}' not found in {project_pseudo_dir}. "
                f"Keeping stored triplet unchanged."
            )
            # Keep existing values in calc_entry (no mutation)
    
    # Save updated species_map (atomic records only)
    # Note: pseudo_set_sha is derived and stored only in manifest, not in calc.yaml
    save_calculation(wf_model, calculation_yaml)
