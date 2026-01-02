#!/usr/bin/env python3
"""
Regenerate si_bands_demo.yml from tests/data/project_examples/project2_bands.

This is a minimal script that only regenerates si_bands_demo.yml.
Run this when project2_bands is updated.

Usage:
    python tools/regenerate_si_bands_demo.py
"""

from __future__ import annotations

import sys
# Add src to path so we can import quantumvitas
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "src"))

from quantumvitas.project.snapshot import export_project_to_snapshot
from quantumvitas.core.pseudo_provenance import compute_sha256_file
from quantumvitas.core.pseudo_libinfo import compute_sha_family_file
from quantumvitas.core.models import load_project, load_calculation
from quantumvitas.core.engines.qe_pseudopotentials import download_pseudopotential
from typing import Any, Dict, List, Optional, Tuple
import yaml


def compute_pseudo_identity(
    repo_root: Path,
    pseudo_filename: str,
    auto_download: bool = True,
) -> Optional[Tuple[str, str]]:
    """Compute pseudo identity triple (sha256, sha_family) from resources/pseudo/."""
    resources_pseudo_dir = repo_root / "resources" / "pseudo"
    pseudo_file = resources_pseudo_dir / pseudo_filename
    
    # If file doesn't exist and auto_download is enabled, try downloading
    if not pseudo_file.exists() and auto_download:
        resources_pseudo_dir.mkdir(parents=True, exist_ok=True)
        print(f"  Attempting to download {pseudo_filename} from QE repository...")
        if download_pseudopotential(pseudo_filename, resources_pseudo_dir):
            print(f"  ✓ Successfully downloaded {pseudo_filename}")
        else:
            print(f"  ✗ Failed to download {pseudo_filename}")
            return None
    
    if not pseudo_file.exists():
        return None
    
    try:
        sha256 = compute_sha256_file(pseudo_file)
        sha_family = compute_sha_family_file(pseudo_file)
        return (sha256, sha_family)
    except Exception as e:
        print(f"  ⚠️  Error computing hashes for {pseudo_filename}: {e}", file=sys.stderr)
        return None


def enhance_species_map_with_pseudo_identities(
    species_map: Dict[str, Dict[str, Any]],
    repo_root: Path,
    auto_download: bool = True,
) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """Enhance species_map with pseudo identity triple from resources/pseudo/."""
    enhanced = {}
    missing_pseudos = []
    
    for element, entry in species_map.items():
        if not isinstance(entry, dict):
            enhanced[element] = entry
            continue
        
        pseudo_filename = entry.get("pseudo_basename") or entry.get("pseudopot")
        if not pseudo_filename:
            enhanced[element] = entry
            continue
        
        identity = compute_pseudo_identity(repo_root, pseudo_filename, auto_download=auto_download)
        if identity is None:
            missing_pseudos.append(f"{element}: {pseudo_filename}")
            continue
        
        sha256, sha_family = identity
        enhanced_entry = dict(entry)
        enhanced_entry["pseudo_basename"] = pseudo_filename
        if "pseudopot" not in enhanced_entry:
            enhanced_entry["pseudopot"] = pseudo_filename
        enhanced_entry["pseudo_sha256"] = sha256
        enhanced_entry["pseudo_sha_family"] = sha_family
        enhanced[element] = enhanced_entry
    
    return enhanced, missing_pseudos


def main(auto_download: bool = True):
    """
    Regenerate si_bands_demo.yml from project2_bands.
    
    Args:
        auto_download: If True, automatically download missing pseudos from QE repository
    """
    repo_root = Path(__file__).resolve().parent.parent
    
    source_path = repo_root / "tests" / "data" / "project_examples" / "project2_bands"
    target_path = repo_root / "resources" / "demo_projects" / "si_bands_demo.yml"
    
    if not source_path.exists():
        print(f"Error: Source project not found: {source_path}", file=sys.stderr)
        sys.exit(1)
    
    if not (source_path / "project.qv.yml").exists():
        print(f"Error: Not a valid project (no project.qv.yml): {source_path}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Exporting {source_path.name} to {target_path.name}...")
    
    # Check for missing pseudos before export
    project_model = load_project(source_path)
    calculations_dir = source_path / "calculations"
    all_missing_pseudos = []
    
    if calculations_dir.exists():
        for calc_dir in calculations_dir.iterdir():
            if calc_dir.is_dir():
                calc_yaml = calc_dir / "calculation.yaml"
                if calc_yaml.exists():
                    calc_model = load_calculation(calc_yaml, source_path)
                    if calc_model.species_map:
                        enhanced_map, missing = enhance_species_map_with_pseudo_identities(
                            calc_model.species_map,
                            repo_root,
                            auto_download=auto_download,
                        )
                        all_missing_pseudos.extend(missing)
    
    # Skip demo if pseudos are missing
    if all_missing_pseudos:
        print(f"  ⚠️  SKIPPING si_bands_demo: Missing pseudos:", file=sys.stderr)
        for missing in all_missing_pseudos:
            print(f"      - {missing}", file=sys.stderr)
        sys.exit(1)
    
    # Export project to snapshot
    snapshot = export_project_to_snapshot(source_path)
    
    # Enhance species_map in snapshot calculations with pseudo identities
    for calc_data in snapshot.calculations:
        if "species_map" in calc_data:
            enhanced_map, missing = enhance_species_map_with_pseudo_identities(
                calc_data["species_map"],
                repo_root,
                auto_download=auto_download,
            )
            if missing:
                print(f"  ⚠️  Warning: Missing pseudos in snapshot: {missing}", file=sys.stderr)
            calc_data["species_map"] = enhanced_map
    
    # Preserve existing meta section if it exists
    existing_meta = None
    if target_path.exists():
        try:
            existing_data = yaml.safe_load(target_path.read_text())
            if existing_data and "meta" in existing_data:
                existing_meta = existing_data["meta"]
                print(f"  Preserving existing meta section: {existing_meta.get('id', 'unknown')}")
        except Exception as e:
            print(f"  Warning: Could not read existing meta: {e}")
    
    # Set meta if it exists, otherwise use defaults
    if existing_meta:
        snapshot.meta = existing_meta
    else:
        # Default meta for si_bands_demo
        snapshot.meta = {
            "id": "si_bands_demo",
            "title": "Silicon band structure",
            "subtitle": "SCF → NSCF → Bands",
            "tags": ["bands", "Si", "PW", "tutorial", "beginner"],
            "recommended_analysis": "bands",
            "difficulty": "beginner",
        }
    
    # Write snapshot YAML
    snapshot_dict = snapshot.to_dict()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        yaml.safe_dump(snapshot_dict, sort_keys=False, default_flow_style=False)
    )
    
    print(f"  ✓ Created {target_path}")
    print(f"    - {len(snapshot.structures)} structure(s)")
    print(f"    - {len(snapshot.calculations)} calculation(s)")
    if snapshot.pseudo:
        print(f"    - {len(snapshot.pseudo.get('files', []))} pseudo file(s)")
    if snapshot.meta:
        print(f"    - Meta: {snapshot.meta.get('title', snapshot.meta.get('id', 'unknown'))}")
    
    print("\n✓ si_bands_demo.yml regenerated successfully!")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Regenerate si_bands_demo.yml")
    parser.add_argument(
        "--no-auto-download",
        action="store_true",
        help="Disable automatic download of missing pseudos from QE repository",
    )
    args = parser.parse_args()
    main(auto_download=not args.no_auto_download)

