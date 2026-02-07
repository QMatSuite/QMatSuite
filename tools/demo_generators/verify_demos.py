#!/usr/bin/env python3
"""
Verify demo project integrity: check pseudo identity triple completeness.

This tool validates that all generated demos have complete pseudo identity triple
(pseudo_basename, pseudo_sha256, pseudo_sha_family) and that referenced pseudo
files exist in resources/pseudo/.

Usage:
    python tools/demo_generators/verify_demos.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

import yaml

# Add src to path
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root / "src"))


def verify_demo(demo_file: Path, resources_pseudo_dir: Path) -> Tuple[bool, List[str]]:
    """
    Verify a single demo file.
    
    Args:
        demo_file: Path to demo YAML file
        resources_pseudo_dir: Path to resources/pseudo/ directory
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    try:
        data = yaml.safe_load(demo_file.read_text())
        if not data:
            errors.append("Empty or invalid YAML")
            return False, errors
        
        calculations = data.get("calculations", [])
        if not calculations:
            errors.append("No calculations found")
            return False, errors
        
        for calc_idx, calc in enumerate(calculations):
            species_map = calc.get("species_map", {})
            if not species_map:
                continue  # No species_map is OK (legacy)
            
            for element, entry in species_map.items():
                if not isinstance(entry, dict):
                    continue
                
                # Check required fields
                pseudo_filename = entry.get("pseudo_basename") or entry.get("pseudopot")
                if not pseudo_filename:
                    errors.append(
                        f"Calc {calc_idx}: {element}: Missing pseudo filename"
                    )
                    continue
                
                # Check pseudo file exists
                pseudo_file = resources_pseudo_dir / pseudo_filename
                if not pseudo_file.exists():
                    errors.append(
                        f"Calc {calc_idx}: {element}: Pseudo file not found: {pseudo_filename}"
                    )
                    continue
                
                # Check sha256
                sha256 = entry.get("pseudo_sha256")
                if not sha256:
                    errors.append(
                        f"Calc {calc_idx}: {element}: Missing pseudo_sha256"
                    )
                elif not isinstance(sha256, str) or len(sha256) != 64:
                    errors.append(
                        f"Calc {calc_idx}: {element}: Invalid pseudo_sha256 (must be 64 hex chars): {sha256[:20]}..."
                    )
                
                # Check sha_family
                sha_family = entry.get("pseudo_sha_family")
                if not sha_family:
                    errors.append(
                        f"Calc {calc_idx}: {element}: Missing pseudo_sha_family"
                    )
                elif not isinstance(sha_family, str) or len(sha_family) != 64:
                    errors.append(
                        f"Calc {calc_idx}: {element}: Invalid pseudo_sha_family (must be 64 hex chars): {sha_family[:20]}..."
                    )
        
        return len(errors) == 0, errors
    
    except Exception as e:
        errors.append(f"Error reading demo file: {e}")
        return False, errors


def main():
    """Verify all demo projects."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    demo_dir = repo_root / "resources" / "demo_projects"
    resources_pseudo_dir = repo_root / "resources" / "pseudo"
    
    if not demo_dir.exists():
        print(f"Error: Demo directory not found: {demo_dir}", file=sys.stderr)
        sys.exit(1)
    
    if not resources_pseudo_dir.exists():
        print(f"Error: Resources pseudo directory not found: {resources_pseudo_dir}", file=sys.stderr)
        sys.exit(1)
    
    # Find all demo YAML files
    demo_files = sorted(demo_dir.glob("*.yml"))
    
    if not demo_files:
        print("No demo files found", file=sys.stderr)
        sys.exit(1)
    
    print(f"Verifying {len(demo_files)} demo file(s)...")
    print()
    
    all_valid = True
    for demo_file in demo_files:
        is_valid, errors = verify_demo(demo_file, resources_pseudo_dir)
        
        if is_valid:
            print(f"✓ {demo_file.name}")
        else:
            all_valid = False
            print(f"✗ {demo_file.name}")
            for error in errors:
                print(f"    {error}")
    
    print()
    if all_valid:
        print("✓ All demos are valid")
        sys.exit(0)
    else:
        print("✗ Some demos have errors")
        sys.exit(1)


if __name__ == "__main__":
    main()

