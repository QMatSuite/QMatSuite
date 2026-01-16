"""
Shared API for configuring calculation-level species_map.

This module provides a unified interface for updating calculation.yaml species_map,
used by both CLI and QVService/daemon.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from quantumvitas.core.project_utils import (
    find_calculation_entry,
    calculation_directory,
    load_project_config,
)


def configure_species_map(
    project_root: Path,
    calculation: str,
    *,
    from_qe_input: Optional[Path] = None,
    set_entries: Optional[List[Tuple[str, float, str]]] = None,
    merge: bool = True,
) -> Dict[str, Dict[str, Any]]:
    """
    Update calculation.yaml species_map.
    
    Args:
        project_root: Project root directory
        calculation: Calculation id/name/slug/path
        from_qe_input: Optional QE input file to extract ATOMIC_SPECIES from
        set_entries: Optional list of explicit (element, mass, pseudopot) triples
        merge: If True (default), merge with existing species_map. If False, replace.
        
    Returns:
        Updated species_map dictionary
        
    Raises:
        ValueError: If calculation not found or invalid arguments
    """
    # Validate inputs
    if not from_qe_input and not set_entries:
        raise ValueError(
            "Either from_qe_input or set_entries must be provided. "
            "Use from_qe_input to extract from a QE input file, "
            "or set_entries to specify explicit (element, mass, pseudopot) triples."
        )
    
    project_root = Path(project_root).expanduser().resolve()
    if not project_root.exists():
        raise ValueError(f"Project root not found: {project_root}")
    
    # Load project config and resolve calculation
    config = load_project_config(project_root)
    calculation_entry = find_calculation_entry(config, calculation, project_root)
    
    calculation_dir = calculation_directory(project_root, calculation_entry)
    calculation_yaml_path = calculation_dir / "calculation.yaml"
    
    if not calculation_yaml_path.exists():
        raise ValueError(f"calculation.yaml not found at {calculation_yaml_path}")
    
    # Load existing calculation.yaml
    calculation_data = yaml.safe_load(calculation_yaml_path.read_text()) or {}
    existing_species_map = calculation_data.get("species_map", {})
    
    if merge:
        merged_species_map = dict(existing_species_map)
    else:
        merged_species_map = {}
    
    # Step 1: Process from_qe_input if provided
    if from_qe_input:
        from quantumvitas.io.parser.qe_parser import QEInputParser
        from quantumvitas.calculation.folder_import import extract_species_map_from_qe_input
        
        input_path = Path(from_qe_input).expanduser().resolve()
        if not input_path.exists():
            raise ValueError(f"Input file not found: {input_path}")
        
        try:
            qe_input = QEInputParser.parse_file(input_path)
        except Exception as exc:
            raise ValueError(f"Failed to parse QE input file {input_path}: {exc}") from exc
        
        # Extract species map from input file
        input_species_map = extract_species_map_from_qe_input(qe_input)
        
        if input_species_map:
            # Merge input entries (preserves existing elements, updates matching ones)
            for element, entry in input_species_map.items():
                if element in merged_species_map:
                    # Update existing entry, preserving other keys
                    merged_species_map[element].update(entry)
                else:
                    # Add new entry
                    merged_species_map[element] = dict(entry)
    
    # Step 2: Process set_entries if provided (overrides same elements)
    if set_entries:
        for element, mass, pseudopot in set_entries:
            if not element:
                raise ValueError(f"Element cannot be empty in set_entries: {element}")
            if not pseudopot:
                raise ValueError(f"Pseudopotential filename cannot be empty in set_entries: {element}")
            
            # Ensure entry exists
            if element not in merged_species_map:
                merged_species_map[element] = {}
            
            # Set mass and pseudopot (preserve other keys)
            merged_species_map[element]["mass"] = mass
            merged_species_map[element]["pseudopot"] = pseudopot
    
    # Write back to calculation.yaml
    calculation_data["species_map"] = merged_species_map
    calculation_yaml_path.write_text(yaml.safe_dump(calculation_data, sort_keys=False))
    
    return merged_species_map

