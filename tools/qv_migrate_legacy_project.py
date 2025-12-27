#!/usr/bin/env python3
"""
CLI entry point for legacy project migration.

Usage:
    python tools/qv_migrate_legacy_project.py --project-root /path/to/project
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from quantumvitas.legacy.migrate import migrate_legacy_project

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate a legacy QuantumVITAS project to DAG + ULID model")
    parser.add_argument(
        "--project-root",
        type=str,
        required=True,
        help="Path to the project root directory",
    )
    
    args = parser.parse_args()
    
    try:
        migrate_legacy_project(Path(args.project_root))
    except Exception as e:
        print(f"Migration failed: {e}", file=sys.stderr)
        sys.exit(1)
