#!/usr/bin/env python3
"""
Generate demo project snapshots from test example projects.

This script exports test projects to snapshot YAML files in resources/demo_projects/.
It also extracts reference JSON artifacts (SCF, DOS, bands) from workflow results.

Run this when test example projects are updated to regenerate the demo snapshots.

Usage:
    python scripts/generate_demo_snapshots.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

# Add src to path so we can import quantumvitas
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "src"))

from quantumvitas.project.snapshot import export_project_to_snapshot
import yaml


def find_workflow_dirs(project_path: Path) -> list[Path]:
    """Find all workflow directories in a project."""
    workflows_dir = project_path / "workflows"
    if not workflows_dir.exists():
        return []
    
    workflow_dirs = []
    for item in workflows_dir.iterdir():
        if item.is_dir() and (item / "workflow.yaml").exists():
            workflow_dirs.append(item)
    
    return workflow_dirs


def extract_reference_artifacts(
    workflow_dir: Path,
    demo_id: str,
    target_dir: Path,
) -> dict[str, str]:
    """
    Extract reference JSON artifacts from workflow results directory.
    
    Returns:
        Dict mapping analysis_type -> artifact_filename
    """
    reference_artifacts = {}
    results_dir = workflow_dir / "results"
    
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
    
    # Extract SCF data from workflow steps
    # Look for SCF step output and parse it
    raw_dir = workflow_dir / "raw"
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


def main():
    """Generate demo snapshots from test projects."""
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
        
        # Export project to snapshot
        snapshot = export_project_to_snapshot(source_path)
        
        # Extract reference artifacts from workflow results
        workflow_dirs = find_workflow_dirs(source_path)
        reference_artifacts = {}
        if workflow_dirs:
            # Use the first workflow (should be the main one)
            reference_artifacts = extract_reference_artifacts(
                workflow_dirs[0],
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
        print(f"    - {len(snapshot.workflows)} workflow(s)")
        if snapshot.pseudo:
            print(f"    - {len(snapshot.pseudo.get('files', []))} pseudo file(s)")
        if reference_artifacts:
            print(f"    - {len(reference_artifacts)} reference artifact(s)")
    
    print("\n✓ Demo snapshots generated successfully!")


if __name__ == "__main__":
    main()

