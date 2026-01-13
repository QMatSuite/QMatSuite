#!/usr/bin/env python3
"""
Manual tool to download/snapshot ORCA documentation to a local directory.

This script downloads ORCA documentation pages from:
- ORCA Input Library: https://sites.google.com/site/orcainputlibrary/home
- ORCA 6.0 Manual: https://www.faccts.de/docs/orca/6.0/manual/
- ORCA 6.0 Tutorials: https://www.faccts.de/docs/orca/6.0/tutorials/index.html

**IMPORTANT**: This is a tooling/development script, NOT used at runtime or in tests.
The snapshots are intended for:
- Offline reference during ORCA integration planning
- Understanding ORCA workflow patterns and file formats
- Reference when the ORCA documentation sites are unavailable

Usage:
    python tools/scrape_orca_docs.py [--output-dir .tmp/orca_docs]

The output directory will preserve a folder structure like:
    manual/
    tutorials/
    input_library/
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
        description="Snapshot ORCA documentation for offline reference"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent.parent / ".tmp" / "orca_docs",
        help="Output directory for documentation snapshots (default: .tmp/orca_docs)",
    )
    
    args = parser.parse_args()
    output_dir = args.output_dir
    
    print("ORCA Documentation Snapshot Tool")
    print("=" * 50)
    print(f"Output directory: {output_dir}")
    print()
    print("NOTE: This is a stub implementation.")
    print("Future versions will download documentation from:")
    print("  - ORCA Input Library: https://sites.google.com/site/orcainputlibrary/home")
    print("  - ORCA 6.0 Manual: https://www.faccts.de/docs/orca/6.0/manual/")
    print("  - ORCA 6.0 Tutorials: https://www.faccts.de/docs/orca/6.0/tutorials/index.html")
    print()
    print("To implement full functionality, add:")
    print("  - HTTP requests to fetch HTML/PDF pages")
    print("  - Recursive link following for tutorials/manual sections")
    print("  - Error handling for missing/updated URLs")
    print("  - Optional: HTML validation/checksums")
    print("  - Folder structure preservation")
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nOutput directory created: {output_dir}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

