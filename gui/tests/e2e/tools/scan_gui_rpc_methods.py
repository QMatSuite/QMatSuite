"""
GUI Static Scanner: Extract RPC method names used by the Electron GUI.

This scanner walks the GUI source tree and extracts method names from:
- qv.call('method_name', ...)
- window.qv.request('method_name', ...)
- Other RPC call patterns

Outputs both plain text and JSON formats.
"""

import json
import re
from pathlib import Path
from typing import Set


GUI_SRC_DIR = Path(__file__).parent.parent.parent.parent / "src"
GUI_TESTS_DIR = Path(__file__).parent.parent
OUTPUT_TXT = Path(__file__).parent / "gui_rpc_methods.txt"
OUTPUT_JSON = Path(__file__).parent / "gui_rpc_methods.json"


# Patterns to match RPC method calls
PATTERNS = [
    # Pattern 1: qv.call('method_name', ...)
    re.compile(r"qv\.call\(['\"]([^'\"]+)['\"]"),
    # Pattern 2: window.qv.request('method_name', ...)
    re.compile(r"window\.qv\.request(?:<[^>]+>)?\(['\"]([^'\"]+)['\"]"),
    # Pattern 3: qv.request('method_name', ...) (if used directly)
    re.compile(r"qv\.request(?:<[^>]+>)?\(['\"]([^'\"]+)['\"]"),
]


def scan_file(file_path: Path) -> Set[str]:
    """
    Scan a single file for RPC method names.
    
    Returns:
        Set of method names found in this file.
    """
    methods = set()
    
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
        
        for pattern in PATTERNS:
            matches = pattern.findall(content)
            for match in matches:
                # Clean up the method name
                method_name = match.strip()
                if method_name:
                    methods.add(method_name)
    
    except Exception as e:
        print(f"Warning: Failed to scan {file_path}: {e}", file=__import__("sys").stderr)
    
    return methods


def scan_directory(directory: Path, extensions: tuple = ('.ts', '.tsx', '.js', '.jsx')) -> Set[str]:
    """
    Recursively scan a directory for RPC method calls.
    
    Returns:
        Set of all method names found.
    """
    all_methods = set()
    file_count = 0
    
    if not directory.exists():
        return all_methods
    
    for file_path in directory.rglob('*'):
        if file_path.is_file() and file_path.suffix in extensions:
            methods = scan_file(file_path)
            all_methods.update(methods)
            file_count += 1
    
    return all_methods, file_count


def main():
    """Scan GUI source and write output files."""
    print("Scanning GUI source for RPC method calls...")
    
    # Scan both src and tests directories
    src_methods, src_count = scan_directory(GUI_SRC_DIR)
    test_methods, test_count = scan_directory(GUI_TESTS_DIR)
    
    # Combine results
    all_methods = src_methods | test_methods
    total_files = src_count + test_count
    
    # Sort for deterministic output
    sorted_methods = sorted(all_methods)
    
    # Write plain text output
    OUTPUT_TXT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_TXT, "w") as f:
        for method in sorted_methods:
            f.write(f"{method}\n")
    
    # Write JSON output
    output_data = {
        "methods": sorted_methods,
        "extracted_from_patterns": [
            "qv.call('method_name', ...)",
            "window.qv.request('method_name', ...)",
            "qv.request('method_name', ...)",
        ],
        "file_count_scanned": total_files,
        "src_files": src_count,
        "test_files": test_count,
    }
    
    with open(OUTPUT_JSON, "w") as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\nScan complete:")
    print(f"  Files scanned: {total_files} (src: {src_count}, tests: {test_count})")
    print(f"  Methods found: {len(sorted_methods)}")
    print(f"  Output text: {OUTPUT_TXT}")
    print(f"  Output JSON: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()



