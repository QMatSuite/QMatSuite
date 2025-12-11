#!/usr/bin/env python3
"""
Manual tool to download/snapshot QE HTML documentation to a local directory.

This script downloads Quantum ESPRESSO input documentation HTML files
from https://www.quantum-espresso.org/Doc/INPUT_{MODULE}.html and saves
them locally for offline parsing.

**IMPORTANT**: This is a tooling/development script, NOT used at runtime or in tests.
The snapshots are intended for:
- Offline regeneration of qe_module_parameters.json
- Future documentation parsing/extraction work
- Reference when the QE website is unavailable

Usage:
    python tools/snapshot_qe_docs.py [--output-dir resources/qe_docs_raw]

The output directory will contain HTML files like:
    INPUT_PW.html
    INPUT_PH.html
    INPUT_DOS.html
    etc.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

# Note: This is a stub implementation. Full download logic would go here.
# For now, we're just establishing the structure and intent.


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Snapshot QE documentation HTML files for offline parsing"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent.parent / "resources" / "qe_docs_raw",
        help="Output directory for HTML snapshots (default: resources/qe_docs_raw)",
    )
    parser.add_argument(
        "--modules",
        nargs="*",
        help="Specific modules to snapshot (default: all supported modules)",
    )
    
    args = parser.parse_args()
    output_dir = args.output_dir
    
    print("QE Documentation Snapshot Tool")
    print("=" * 50)
    print(f"Output directory: {output_dir}")
    print()
    print("NOTE: This is a stub implementation.")
    print("Future versions will download HTML files from:")
    print("  https://www.quantum-espresso.org/Doc/INPUT_{MODULE}.html")
    print()
    print("To implement full functionality, add:")
    print("  - HTTP requests to fetch HTML")
    print("  - Module list from qe_module_parameters.json or qe_metadata.py")
    print("  - Error handling for missing/updated URLs")
    print("  - Optional: HTML validation/checksums")
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nOutput directory created: {output_dir}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
