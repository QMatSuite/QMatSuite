"""
Kernel-level utilities for QE input folder processing.

Provides species map extraction, merging, and file ordering utilities.
The facade-level orchestration function (materialize_project_from_qe_input_folder)
lives in quantumvitas.api.folder_import since it depends on QVService.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List


def extract_species_map_from_qe_input(qe_input) -> Dict[str, Dict[str, Any]]:
    """
    Extract species mapping (element -> {mass, pseudopot}) from a QE input.

    Args:
        qe_input: Parsed QE input object

    Returns:
        Dictionary mapping element symbol to {mass, pseudopot}
    """
    from quantumvitas.io.model import QECardType
    from quantumvitas.core.pseudo import is_missing_pseudo_placeholder

    species_map: Dict[str, Dict[str, Any]] = {}
    atomic_species_card = qe_input.get_card(QECardType.ATOMIC_SPECIES)

    if atomic_species_card and atomic_species_card.data:
        for row in atomic_species_card.data:
            if isinstance(row, list) and len(row) >= 3:
                element_symbol = str(row[0]).strip()
                mass = row[1] if len(row) > 1 else None
                pseudo_filename = str(row[2]).strip() if len(row) > 2 else None

                entry: Dict[str, Any] = {}
                if mass is not None:
                    try:
                        entry["mass"] = float(mass)
                    except (TypeError, ValueError):
                        entry["mass"] = mass
                if pseudo_filename:
                    # Skip placeholder names - they indicate missing configuration
                    if not is_missing_pseudo_placeholder(pseudo_filename):
                        entry["pseudopot"] = pseudo_filename

                if entry:
                    species_map[element_symbol] = entry

    return species_map


def merge_species_maps(
    existing_map: Dict[str, Dict[str, Any]],
    new_map: Dict[str, Dict[str, Any]],
    source_file: str = "",
) -> Dict[str, Dict[str, Any]]:
    """
    Merge a new species map into an existing one, checking for conflicts.

    Args:
        existing_map: The accumulated species map
        new_map: New species data to merge
        source_file: Source file name for error messages

    Returns:
        Merged species map

    Raises:
        ValueError: If conflicting pseudopotential mappings are detected
    """
    merged = dict(existing_map)  # Copy to avoid mutation

    for element, new_settings in new_map.items():
        if element not in merged:
            # New element - just add it
            merged[element] = dict(new_settings)
        else:
            # Element exists - check for conflicts
            existing_settings = merged[element]

            # Check pseudopot conflict
            if "pseudopot" in new_settings and "pseudopot" in existing_settings:
                new_pseudo = str(new_settings["pseudopot"])
                old_pseudo = str(existing_settings["pseudopot"])
                if new_pseudo != old_pseudo:
                    raise ValueError(
                        f"Conflicting pseudopotential mapping for element {element}: "
                        f"'{old_pseudo}' (earlier file) vs '{new_pseudo}'"
                        + (f" in file '{source_file}'" if source_file else "")
                        + ". All files in a calculation must use the same pseudopotential for each element."
                    )

            # Check mass conflict (allow small floating point differences)
            if "mass" in new_settings and "mass" in existing_settings:
                try:
                    new_mass = float(new_settings["mass"])
                    old_mass = float(existing_settings["mass"])
                    if abs(new_mass - old_mass) > 1e-6:
                        raise ValueError(
                            f"Conflicting mass for element {element}: "
                            f"{old_mass} (earlier file) vs {new_mass}"
                            + (f" in file '{source_file}'" if source_file else "")
                        )
                except (TypeError, ValueError):
                    pass  # Ignore conversion errors

            # Add any new keys not in existing
            for key, value in new_settings.items():
                if key not in existing_settings:
                    merged[element][key] = value

    return merged


def sort_input_files_by_execution_order(input_files: List[Path]) -> List[Path]:
    """
    Sort QE input files by execution order using filename heuristics.

    Prefers explicit numeric order tokens (e.g., ".1_", "_1_", ".1.", "_1." patterns).
    If ambiguous, files are sorted by filename.

    Args:
        input_files: List of input file paths

    Returns:
        Sorted list of input files in execution order
    """
    def extract_order_number(filepath: Path) -> tuple[int, str]:
        """Extract order number from filename, return (order, filename) for stable sort."""
        stem = filepath.stem
        # Try to find numeric order patterns: .1_, _1_, .1., _1.
        patterns = [
            r"\.(\d+)_",  # .1_scf, .2_nscf
            r"_(\d+)_",   # si_1_scf, si_2_nscf
            r"\.(\d+)\.", # si.1.scf, si.2.nscf
            r"_(\d+)\.",  # si_1.scf, si_2.nscf
        ]
        for pattern in patterns:
            match = re.search(pattern, stem)
            if match:
                return (int(match.group(1)), str(filepath))
        # If no pattern found, use filename for stable sort
        return (999999, str(filepath))

    return sorted(input_files, key=extract_order_number)
