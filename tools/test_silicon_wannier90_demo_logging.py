#!/usr/bin/env python3
"""
Test script to generate diagnostic logs for silicon-wannier90 demo.

This script loads the demo and triggers the code paths that should generate logs:
- get_calculation_pseudo_mapping
- materialize_steps (which calls ensure_qe_pseudos)
- _handle_get_pseudo_options_for_calculation

Run this script to see the diagnostic logs.
"""

from __future__ import annotations

import sys
import logging
from pathlib import Path

# Add src to path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "src"))

# Configure logging to see all our diagnostic messages
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s [%(name)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)

from quantumvitas.project.snapshot import ProjectSnapshot
from quantumvitas.project.snapshot import materialize_project_from_snapshot
import yaml

# Load demo
demo_file = repo_root / "resources" / "demo_projects" / "silicon_wannier90_demo.yml"
if not demo_file.exists():
    print(f"ERROR: Demo file not found: {demo_file}")
    sys.exit(1)

print("=" * 80)
print("Loading silicon-wannier90 demo snapshot...")
print("=" * 80)

with open(demo_file) as f:
    demo_data = yaml.safe_load(f)

snapshot = ProjectSnapshot.from_dict(demo_data)

print("\n" + "=" * 80)
print("Materializing project (this will trigger materialize_steps logs)...")
print("=" * 80)

# Create temp project
import tempfile
with tempfile.TemporaryDirectory() as tmpdir:
    project_root = Path(tmpdir) / "test_project"
    project_root.mkdir()
    
    # Materialize project (creates project.qv.yml)
    materialize_project_from_snapshot(snapshot, project_root)
    
    # Verify project was created
    if not (project_root / "project.qv.yml").exists():
        print(f"ERROR: Project was not properly materialized. project.qv.yml not found.")
        sys.exit(1)
    
    print("\n" + "=" * 80)
    print("Calling get_calculation_pseudo_mapping (this will trigger mapping logs)...")
    print("=" * 80)
    
    # Get calculation ULID
    calc = snapshot.calculations[0]
    calc_id = calc["meta"]["id"]
    
    from quantumvitas.api import QVService
    from quantumvitas.core.resolution import build_resource_index
    from quantumvitas.core.project_utils import load_project_config
    
    config = load_project_config(project_root)
    index = build_resource_index(project_root)
    
    try:
        result = QVService.get_calculation_pseudo_mapping(
            project_root=project_root,
            calculation_ulid=calc_id,
            index=index,
            config=config,
        )
        print(f"\nResult keys: {list(result.keys())}")
        print(f"Mapping: {result.get('mapping', {})}")
        print(f"Warnings: {result.get('warnings', [])}")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("Testing materialize_steps (this will trigger materialize logs)...")
    print("=" * 80)
    
    # Try to load calculation and materialize steps
    try:
        from quantumvitas.project.model import Project
        from quantumvitas.calculation.calculation import Calculation
        
        project = Project.open(project_root)
        calc_resolved = project.get_calculation_by_id(calc_id)
        if calc_resolved:
            # This will trigger materialize_steps logs
            calc_obj = Calculation.from_yaml(calc_resolved.absolute_path, project, materialize_steps=True)
            print(f"Loaded calculation with {len(calc_obj.steps)} steps")
    except Exception as e:
        print(f"Materialization test error (this may be expected if pseudos are missing): {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 80)
print("Done. Check logs above for diagnostic information.")
print("=" * 80)

