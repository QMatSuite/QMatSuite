#!/usr/bin/env python3
"""
Generate demo project snapshots from test example projects.

This script exports test projects to snapshot YAML files in resources/demo_projects/.
It also extracts reference JSON artifacts (SCF, DOS, bands) from calculation results.

Run this when test example projects are updated to regenerate the demo snapshots.

Usage:
    python tools/generate_demo_snapshots.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

# Add src to path so we can import quantumvitas
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "src"))

from quantumvitas.project.snapshot import export_project_to_snapshot
from quantumvitas.core.pseudo_provenance import compute_sha256_file
from quantumvitas.core.pseudo_libinfo import compute_sha_family_file
from quantumvitas.core.engines.qe_pseudopotentials import download_pseudopotential
import yaml


def find_calculation_dirs(project_path: Path) -> list[Path]:
    """Find all calculation directories in a project."""
    workflows_dir = project_path / "calculations"
    if not workflows_dir.exists():
        return []
    
    calculation_dirs = []
    for item in workflows_dir.iterdir():
        if item.is_dir() and (item / "calculation.yaml").exists():
            calculation_dirs.append(item)
    
    return calculation_dirs


def compute_pseudo_identity(
    repo_root: Path,
    pseudo_filename: str,
    auto_download: bool = True,
) -> tuple[str, str] | None:
    """
    Compute pseudo identity triple (sha256, sha_family) from resources/pseudo/.
    If file is missing and auto_download=True, attempts to download from QE repository.
    
    Args:
        repo_root: Repository root directory
        pseudo_filename: Filename of pseudopotential (e.g., "Si.pbe-n-rrkjus_psl.1.0.0.UPF")
        auto_download: If True and file missing, attempt to download from QE repository
        
    Returns:
        Tuple of (sha256, sha_family) if file exists or was downloaded, None otherwise
    """
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
    species_map: dict[str, dict[str, Any]],
    repo_root: Path,
    auto_download: bool = True,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """
    Enhance species_map with pseudo identity triple from resources/pseudo/.
    
    Args:
        species_map: Species mapping dict (element -> {mass, pseudopot, ...})
        repo_root: Repository root directory
        
    Returns:
        Tuple of (enhanced_species_map, missing_pseudos_list)
    """
    enhanced = {}
    missing_pseudos = []
    
    for element, entry in species_map.items():
        if not isinstance(entry, dict):
            enhanced[element] = entry
            continue
        
        # Get pseudo filename
        pseudo_filename = entry.get("pseudo_basename") or entry.get("pseudopot")
        if not pseudo_filename:
            enhanced[element] = entry
            continue
        
        # Compute identity triple
        identity = compute_pseudo_identity(repo_root, pseudo_filename, auto_download=auto_download)
        if identity is None:
            missing_pseudos.append(f"{element}: {pseudo_filename}")
            continue
        
        sha256, sha_family = identity
        
        # Enhance entry
        enhanced_entry = dict(entry)
        enhanced_entry["pseudo_basename"] = pseudo_filename
        if "pseudopot" not in enhanced_entry:
            enhanced_entry["pseudopot"] = pseudo_filename
        enhanced_entry["pseudo_sha256"] = sha256
        enhanced_entry["pseudo_sha_family"] = sha_family
        
        enhanced[element] = enhanced_entry
    
    return enhanced, missing_pseudos


def extract_reference_artifacts(
    calculation_dir: Path,
    demo_id: str,
    target_dir: Path,
) -> dict[str, str]:
    """
    Extract reference JSON artifacts from calculation results directory.
    
    Returns:
        Dict mapping analysis_type -> artifact_filename
    """
    reference_artifacts = {}
    results_dir = calculation_dir / "results"
    
    if not results_dir.exists():
        return reference_artifacts
    
    # Map of results JSON files to demo artifact names
    artifact_mappings = {
        "dos_data.json": f"{demo_id}.dos.json",
        "bands_data.json": f"{demo_id}.bands.json",
    }
    
    # Copy analysis artifacts
    for source_name, target_name in artifact_mappings.items():
        source_path = results_dir / source_name
        if source_path.exists():
            target_path = target_dir / target_name
            shutil.copy2(source_path, target_path)
            analysis_type = source_name.replace("_data.json", "").replace(".json", "")
            reference_artifacts[analysis_type] = target_name
            print(f"  ✓ Extracted {analysis_type} artifact: {target_name}")
    
    # Extract SCF data from calculation steps
    # Look for SCF step output and parse it
    raw_dir = calculation_dir / "raw"
    if raw_dir.exists():
        # Find SCF output file (usually scf.out or similar)
        scf_outputs = list(raw_dir.glob("*scf*.out"))
        if scf_outputs:
            try:
                from quantumvitas.analysis.parsers import parse_scf_output
                scf_result = parse_scf_output(scf_outputs[0])
                if scf_result:
                    # Convert SCFResult dataclass to dict
                    if hasattr(scf_result, 'to_dict'):
                        scf_data = scf_result.to_dict()
                    else:
                        # Fallback: use dataclass.asdict
                        from dataclasses import asdict
                        scf_data = asdict(scf_result)
                    
                    scf_artifact = f"{demo_id}.scf.json"
                    scf_path = target_dir / scf_artifact
                    scf_path.write_text(json.dumps(scf_data, indent=2))
                    reference_artifacts["scf"] = scf_artifact
                    print(f"  ✓ Extracted SCF artifact: {scf_artifact}")
            except Exception as e:
                print(f"  ⚠️  Could not extract SCF data: {e}")
    
    return reference_artifacts


def main(auto_download: bool = True):
    """
    Generate demo snapshots from test projects.
    
    Args:
        auto_download: If True, automatically download missing pseudos from QE repository
    """
    repo_root = Path(__file__).resolve().parent.parent
    
    # Define source projects and target snapshots
    projects = [
        {
            "source": repo_root / "tests" / "data" / "project_examples" / "project2_bands",
            "target": repo_root / "resources" / "demo_projects" / "si_bands_demo.yml",
            "demo_id": "si_bands_demo",
        },
        {
            "source": repo_root / "tests" / "data" / "project_examples" / "project1",
            "target": repo_root / "resources" / "demo_projects" / "si_dos_demo.yml",
            "demo_id": "si_dos_demo",
        },
    ]
    
    # Ensure target directory exists
    target_dir = repo_root / "resources" / "demo_projects"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    for project in projects:
        source_path = project["source"]
        target_path = project["target"]
        demo_id = project["demo_id"]
        
        if not source_path.exists():
            print(f"Warning: Source project not found: {source_path}", file=sys.stderr)
            continue
        
        if not (source_path / "project.qv.yml").exists():
            print(f"Warning: Not a valid project (no project.qv.yml): {source_path}", file=sys.stderr)
            continue
        
        print(f"Exporting {source_path.name} to {target_path.name}...")
        
        # Load project to check species_map before export
        from quantumvitas.core.models import load_project
        from quantumvitas.core.models import load_calculation
        
        project_model = load_project(source_path)
        calculation_dirs = find_calculation_dirs(source_path)
        
        # Check for missing pseudos before export
        all_missing_pseudos = []
        for calc_dir in calculation_dirs:
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
            print(f"  ⚠️  SKIPPING {demo_id}: Missing pseudos:")
            for missing in all_missing_pseudos:
                print(f"      - {missing}")
            continue
        
        # Export project to snapshot
        snapshot = export_project_to_snapshot(source_path)
        
        # Enhance species_map in snapshot calculations with pseudo identities
        # (export_project_to_snapshot may have computed them, but we ensure they're from resources/pseudo/)
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
        
        # Extract reference artifacts from calculation results
        reference_artifacts = {}
        if calculation_dirs:
            # Use the first calculation (should be the main one)
            reference_artifacts = extract_reference_artifacts(
                calculation_dirs[0],
                demo_id,
                target_dir,
            )
        
        # Add reference_artifacts to snapshot meta if any were found
        if reference_artifacts:
            # Ensure meta section exists
            if not hasattr(snapshot, 'meta') or snapshot.meta is None:
                snapshot.meta = {}
            elif not isinstance(snapshot.meta, dict):
                # If meta is not a dict, convert it
                snapshot.meta = {}
            
            # Set default meta fields if not present
            if "id" not in snapshot.meta:
                snapshot.meta["id"] = demo_id
            
            # Set demo-specific metadata
            if demo_id == "si_dos_demo":
                snapshot.meta.setdefault("title", "Silicon density of states")
                snapshot.meta.setdefault("subtitle", "SCF → NSCF → DOS")
                snapshot.meta.setdefault("tags", ["dos", "Si", "PW", "tutorial"])
                snapshot.meta.setdefault("recommended_analysis", "dos")
                snapshot.meta.setdefault("difficulty", "beginner")
            elif demo_id == "si_bands_demo":
                snapshot.meta.setdefault("title", "Silicon band structure")
                snapshot.meta.setdefault("subtitle", "SCF → NSCF → Bands")
                snapshot.meta.setdefault("tags", ["bands", "Si", "PW", "tutorial", "beginner"])
                snapshot.meta.setdefault("recommended_analysis", "bands")
                snapshot.meta.setdefault("difficulty", "beginner")
            
            snapshot.meta["reference_artifacts"] = reference_artifacts
        
        # Write snapshot YAML
        snapshot_dict = snapshot.to_dict()
        target_path.write_text(
            yaml.safe_dump(snapshot_dict, sort_keys=False, default_flow_style=False)
        )
        
        print(f"  ✓ Created {target_path.name}")
        print(f"    - {len(snapshot.structures)} structure(s)")
        print(f"    - {len(snapshot.calculations)} calculation(s)")
        if snapshot.pseudo:
            print(f"    - {len(snapshot.pseudo.get('files', []))} pseudo file(s)")
        if reference_artifacts:
            print(f"    - {len(reference_artifacts)} reference artifact(s)")
    
    print("\n✓ Demo snapshots generated successfully!")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate demo project snapshots")
    parser.add_argument(
        "--no-auto-download",
        action="store_true",
        help="Disable automatic download of missing pseudos from QE repository",
    )
    args = parser.parse_args()
    main(auto_download=not args.no_auto_download)

