#!/usr/bin/env python3
"""
Compare QE parameter metadata maps (v1 vs current schema).

This script compares the legacy v1 snapshot against the current
qe_module_parameters.json and reports structural differences.

It is a pure tooling script and does not affect runtime or tests.

The current JSON may be v1 or v2 schema; this script derives sections
from either structure for comparison.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Set


def load_json(path: Path) -> dict:
    """Load JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def derive_sections_from_data(module_data: dict, schema_version: int) -> Dict[str, List[str]]:
    """
    Derive sections dict from module data (works for both v1 and v2 schema).
    
    Args:
        module_data: Module entry from JSON (v1 has "sections", v2 has "parameters")
        schema_version: Schema version (1 or 2)
        
    Returns:
        Dict mapping section names (normalized with '&' prefix) to lists of parameter names.
    """
    sections: Dict[str, List[str]] = {}
    
    if schema_version == 1:
        # v1: direct sections map (normalize to ensure '&' prefix)
        raw_sections = module_data.get("sections", {})
        for section_name, param_names in raw_sections.items():
            # Normalize section name to always have '&' prefix
            normalized = section_name if section_name.startswith("&") else f"&{section_name}"
            sections[normalized] = list(param_names)
    elif schema_version == 2:
        # v2: derive sections from parameters map
        parameters = module_data.get("parameters", {})
        for key, param_meta in parameters.items():
            namelist = param_meta.get("namelist", "")
            name = param_meta.get("name", "")
            if namelist and name:
                # Normalize namelist to always have '&' prefix
                if not namelist.startswith("&"):
                    namelist = f"&{namelist}"
                sections.setdefault(namelist, []).append(name)
        # Sort parameter lists for consistency
        sections = {k: sorted(v) for k, v in sections.items()}
    
    return sections


def compare_maps(legacy_data: dict, current_data: dict) -> dict:
    """
    Compare legacy v1 map against current map (v1 or v2 schema).
    
    Derives sections from current data regardless of schema version.
    """
    legacy_modules = set(legacy_data.get("modules", {}).keys())
    current_modules = set(current_data.get("modules", {}).keys())
    
    # Detect current schema version (default to 1 if not specified)
    current_schema_version = current_data.get("schema_version", 1)
    
    modules_only_in_legacy = sorted(legacy_modules - current_modules)
    modules_only_in_current = sorted(current_modules - legacy_modules)
    
    section_mismatches: Dict[str, Dict[str, Dict[str, List[str]]]] = {}
    
    common_modules = legacy_modules & current_modules
    for module in sorted(common_modules):
        legacy_mod = legacy_data["modules"][module]
        current_mod = current_data["modules"][module]
        
        # Derive sections for both legacy (always v1) and current (v1 or v2)
        legacy_sections_map = derive_sections_from_data(legacy_mod, 1)
        current_sections_map = derive_sections_from_data(current_mod, current_schema_version)
        
        legacy_sections = set(legacy_sections_map.keys())
        current_sections = set(current_sections_map.keys())
        
        if legacy_sections != current_sections:
            section_mismatches[module] = {}
        
        # Sections only in one or the other
        sections_only_in_legacy = sorted(legacy_sections - current_sections)
        sections_only_in_current = sorted(current_sections - legacy_sections)
        
        if sections_only_in_legacy or sections_only_in_current:
            section_mismatches[module] = {}
            if sections_only_in_legacy:
                section_mismatches[module]["_sections_only_in_legacy"] = sections_only_in_legacy
            if sections_only_in_current:
                section_mismatches[module]["_sections_only_in_current"] = sections_only_in_current
        
        # Compare parameters in common sections
        common_sections = legacy_sections & current_sections
        for section in sorted(common_sections):
            legacy_params = set(legacy_sections_map[section])
            current_params = set(current_sections_map[section])
            
            if legacy_params != current_params:
                if module not in section_mismatches:
                    section_mismatches[module] = {}
                if section not in section_mismatches[module]:
                    section_mismatches[module][section] = {}
                
                params_only_in_legacy = sorted(legacy_params - current_params)
                params_only_in_current = sorted(current_params - legacy_params)
                
                if params_only_in_legacy:
                    section_mismatches[module][section]["only_in_legacy"] = params_only_in_legacy
                if params_only_in_current:
                    section_mismatches[module][section]["only_in_current"] = params_only_in_current
    
    return {
        "modules_only_in_legacy": modules_only_in_legacy,
        "modules_only_in_current": modules_only_in_current,
        "section_mismatches": section_mismatches,
    }


def main() -> int:
    repo_root = Path(__file__).parent.parent
    legacy_path = repo_root / "src" / "qmatsuite" / "data" / "qe_module_parameters.legacy.json"
    current_path = repo_root / "src" / "qmatsuite" / "data" / "qe_module_parameters.json"
    
    if not legacy_path.exists():
        sys.stderr.write(f"Error: Legacy file not found: {legacy_path}\n")
        return 1
    
    if not current_path.exists():
        sys.stderr.write(f"Error: Current file not found: {current_path}\n")
        return 1
    
    legacy_data = load_json(legacy_path)
    current_data = load_json(current_path)
    
    diff = compare_maps(legacy_data, current_data)
    
    print("=== QE_PARAM_DIFF_SUMMARY_BEGIN ===")
    print(f"modules_only_in_legacy: {diff['modules_only_in_legacy']}")
    print(f"modules_only_in_current: {diff['modules_only_in_current']}")
    print("section_mismatches:")
    if diff["section_mismatches"]:
        import json as json_module
        print(json_module.dumps(diff["section_mismatches"], indent=2))
    else:
        print("  {}")
    print("=== QE_PARAM_DIFF_SUMMARY_END ===")
    
    # Exit with non-zero if there are any differences
    if (diff["modules_only_in_legacy"] or 
        diff["modules_only_in_current"] or 
        diff["section_mismatches"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

