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
from pathlib import Path

# Add src to path so we can import quantumvitas
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "src"))

from quantumvitas.project.snapshot import export_project_to_snapshot
import yaml


def main():
    """Regenerate si_bands_demo.yml from project2_bands."""
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
    
    # Export project to snapshot
    snapshot = export_project_to_snapshot(source_path)
    
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
    main()

