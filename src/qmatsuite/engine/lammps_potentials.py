"""LAMMPS potential file staging and management."""

from __future__ import annotations

import hashlib
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from pymatgen.core import Structure

logger = logging.getLogger(__name__)


@dataclass
class StagedPotentials:
    """Staged potential files for a LAMMPS step."""
    
    staged_files: List[Tuple[str, Path]]  # (name, path) tuples
    digest: str  # SHA256 of concatenated file contents
    style: str  # pair_style name
    elements: List[str]  # Elements covered by this potential
    pair_style_block: str  # Generated pair_style/pair_coeff commands


def stage_potentials(
    calculation: "Calculation",
    potential_ref: str,
    target_dir: Path,
    structure: Structure,
) -> StagedPotentials:
    """
    Stage potential files from potential_map to working directory.
    
    Args:
        calculation: Calculation context (has potential_map)
        potential_ref: Key in potential_map
        target_dir: Destination (calc/raw/<step>/potentials/)
        structure: Structure for element ordering
    
    Returns:
        StagedPotentials with:
        - staged_files: List[(name, path)]
        - digest: SHA256 of file contents
        - pair_style_block: Generated pair_style/pair_coeff commands
    
    Raises:
        ValueError: potential_ref not in map
        ValueError: Potential doesn't cover structure elements
        FileNotFoundError: Source file missing
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Get potential_map from calculation
    potential_map = getattr(calculation, "potential_map", None)
    if not potential_map:
        raise ValueError("calculation has no potential_map")
    
    # Resolve potential definition
    pot_def = potential_map.get(potential_ref)
    if not pot_def:
        raise ValueError(f"Potential '{potential_ref}' not found in potential_map")
    
    style = pot_def.get("style")
    if not style:
        raise ValueError(f"Potential '{potential_ref}' missing 'style' field")
    
    # Get source files
    project_root = calculation.project.root if hasattr(calculation, "project") else Path.cwd()
    
    # Handle single file or multiple files
    if "file" in pot_def:
        source_files = [(Path(pot_def["file"]).name, project_root / pot_def["file"])]
    elif "files" in pot_def:
        source_files = [(Path(f).name, project_root / f) for f in pot_def["files"]]
    else:
        # Inline potential (e.g., lj/cut) - no files to stage
        source_files = []
    
    # Validate files exist
    for name, src_path in source_files:
        if not src_path.exists():
            raise FileNotFoundError(f"Potential file not found: {src_path}")
    
    # Stage files
    staged = []
    for name, src_path in source_files:
        dst_path = target_dir / name
        shutil.copy2(src_path, dst_path)
        staged.append((name, dst_path))
        logger.debug(f"Staged potential file: {src_path} -> {dst_path}")
    
    # Compute digest
    digest = compute_potential_digest(staged)
    
    # Get elements from potential definition or structure
    potential_elements = pot_def.get("elements", [])
    structure_elements = list(set(str(site.specie) for site in structure))
    
    # Validate element coverage
    if potential_elements:
        missing = set(structure_elements) - set(potential_elements)
        if missing:
            raise ValueError(
                f"Potential '{potential_ref}' does not cover elements: {missing}. "
                f"Potential covers: {potential_elements}, structure has: {structure_elements}"
            )
    
    # Generate pair_style block
    pair_style_block = generate_pair_style_block(
        pot_def=pot_def,
        staged_files=staged,
        structure=structure,
        potentials_dir="potentials",
    )
    
    return StagedPotentials(
        staged_files=staged,
        digest=digest,
        style=style,
        elements=potential_elements or structure_elements,
        pair_style_block=pair_style_block,
    )


def compute_potential_digest(staged_files: List[Tuple[str, Path]]) -> str:
    """
    Compute deterministic digest of potential files.
    
    Order-independent: sort by filename before hashing.
    
    Args:
        staged_files: List of (name, path) tuples
    
    Returns:
        SHA256 hex digest
    """
    hasher = hashlib.sha256()
    
    for name, path in sorted(staged_files):
        hasher.update(name.encode())
        hasher.update(path.read_bytes())
    
    return hasher.hexdigest()


def generate_pair_style_block(
    pot_def: Dict,
    staged_files: List[Tuple[str, Path]],
    structure: Structure,
    potentials_dir: str = "potentials",
) -> str:
    """
    Generate pair_style/pair_coeff commands for a potential.
    
    Args:
        pot_def: Potential definition from potential_map
        staged_files: List of staged (name, path) tuples
        structure: Structure for element ordering
        potentials_dir: Relative path to potentials directory
    
    Returns:
        Multi-line string with pair_style and pair_coeff commands
    """
    style = pot_def["style"]
    lines = []
    
    # Get unique elements in order of first appearance in structure
    unique_elements = []
    seen = set()
    for site in structure:
        element = str(site.specie)
        if element not in seen:
            unique_elements.append(element)
            seen.add(element)
    
    # Generate pair_style command
    if style == "lj/cut":
        cutoff = pot_def.get("cutoff", 2.5)
        lines.append(f"pair_style lj/cut {cutoff}")
        
        # Generate pair_coeff from params
        params = pot_def.get("params", {})
        for type_pair, values in params.items():
            # type_pair is "1 1" or similar
            lines.append(f"pair_coeff {type_pair} {values}")
    elif style in ("eam", "eam/fs"):
        # Single file EAM
        if staged_files:
            filename = staged_files[0][0]
            lines.append(f"pair_style {style}")
            lines.append(f"pair_coeff * * {potentials_dir}/{filename}")
        else:
            raise ValueError(f"EAM potential requires file, but none staged")
    elif style == "eam/alloy":
        # Multi-element EAM
        if staged_files:
            filename = staged_files[0][0]
            elements_str = " ".join(unique_elements)
            lines.append(f"pair_style eam/alloy")
            lines.append(f"pair_coeff * * {potentials_dir}/{filename} {elements_str}")
        else:
            raise ValueError(f"EAM/alloy potential requires file, but none staged")
    elif style == "tersoff":
        if staged_files:
            filename = staged_files[0][0]
            elements_str = " ".join(unique_elements)
            lines.append(f"pair_style tersoff")
            lines.append(f"pair_coeff * * {potentials_dir}/{filename} {elements_str}")
        else:
            raise ValueError(f"Tersoff potential requires file, but none staged")
    elif style == "reaxff":
        if staged_files:
            # ReaxFF uses first file as main parameter file
            filename = staged_files[0][0]
            elements_str = " ".join(unique_elements)
            lines.append(f"pair_style reaxff NULL")
            lines.append(f"pair_coeff * * {potentials_dir}/{filename} {elements_str}")
            lines.append(f"fix qeq all qeq/reaxff 1 0.0 10.0 1.0e-6 reaxff")
        else:
            raise ValueError(f"ReaxFF potential requires file, but none staged")
    elif style == "deepmd":
        if staged_files:
            filename = staged_files[0][0]
            lines.append(f"pair_style deepmd {potentials_dir}/{filename}")
            lines.append(f"pair_coeff * *")
        else:
            raise ValueError(f"DeepMD potential requires model file, but none staged")
    else:
        # Generic fallback
        lines.append(f"pair_style {style}")
        if staged_files:
            filename = staged_files[0][0]
            elements_str = " ".join(unique_elements) if unique_elements else ""
            if elements_str:
                lines.append(f"pair_coeff * * {potentials_dir}/{filename} {elements_str}")
            else:
                lines.append(f"pair_coeff * * {potentials_dir}/{filename}")
    
    return "\n".join(lines)


def validate_custom_script_assets(step_params: dict) -> None:
    """
    Validate custom_script mode has required_files.
    
    Constitution requirement: custom_script MUST declare assets.required_files
    or it's a hard error. We refuse to copy entire potential library.
    
    Raises:
        ValueError: If custom_script present but assets.required_files missing
    """
    if "custom_script" in step_params:
        assets = step_params.get("assets", {})
        if not assets.get("required_files"):
            raise ValueError(
                "custom_script mode requires explicit assets.required_files. "
                "Specify which potential/asset files the script needs."
            )
