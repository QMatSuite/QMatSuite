#!/usr/bin/env python3
"""
Generate demo project snapshots from test example projects.

This script exports test projects to snapshot YAML files in resources/demo_projects/.
Run this when test example projects are updated to regenerate the demo snapshots.

Usage:
    python scripts/generate_demo_snapshots.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path so we can import quantumvitas
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "src"))

from quantumvitas.project.snapshot import export_project_to_snapshot
import yaml


def main():
    """Generate demo snapshots from test projects."""
    repo_root = Path(__file__).resolve().parent.parent
    
    # Define source projects and target snapshots
    projects = [
        {
            "source": repo_root / "tests" / "data" / "project_examples" / "project2_bands",
            "target": repo_root / "resources" / "demo_projects" / "si_bands_demo.yml",
        },
        {
            "source": repo_root / "tests" / "data" / "project_examples" / "project1",
            "target": repo_root / "resources" / "demo_projects" / "si_dos_demo.yml",
        },
    ]
    
    # Ensure target directory exists
    (repo_root / "resources" / "demo_projects").mkdir(parents=True, exist_ok=True)
    
    for project in projects:
        source_path = project["source"]
        target_path = project["target"]
        
        if not source_path.exists():
            print(f"Warning: Source project not found: {source_path}", file=sys.stderr)
            continue
        
        if not (source_path / "project.qv.yml").exists():
            print(f"Warning: Not a valid project (no project.qv.yml): {source_path}", file=sys.stderr)
            continue
        
        print(f"Exporting {source_path.name} to {target_path.name}...")
        
        # Export project to snapshot
        snapshot = export_project_to_snapshot(source_path)
        
        # Write snapshot YAML
        snapshot_dict = snapshot.to_dict()
        target_path.write_text(
            yaml.safe_dump(snapshot_dict, sort_keys=False, default_flow_style=False)
        )
        
        print(f"  ✓ Created {target_path}")
        print(f"    - {len(snapshot.structures)} structure(s)")
        print(f"    - {len(snapshot.workflows)} workflow(s)")
        if snapshot.pseudo:
            print(f"    - {len(snapshot.pseudo.get('files', []))} pseudo file(s)")
    
    print("\n✓ Demo snapshots generated successfully!")


if __name__ == "__main__":
    main()

