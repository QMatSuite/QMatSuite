#!/usr/bin/env python3
"""
Test QE input parser with official QE test-suite files.

This script parses all input files from the official QE test-suite
and reports any parsing errors or issues.

This is an extended test that requires QE test-suite.
"""

import sys
from pathlib import Path
from collections import defaultdict
import traceback

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

from qmatsuite.io import QEInputParser, QEModule


def test_parse_file(filepath: Path) -> tuple[bool, str, Exception]:
    """
    Test parsing a single file.
    
    Returns:
        (success, message, exception)
    """
    try:
        qe_input = QEInputParser.parse_file(filepath)
        
        # Basic validation
        if not qe_input.namelists and not qe_input.cards:
            return False, "No namelists or cards found", None
        
        # Check module detection
        module = qe_input.module or QEModule.UNKNOWN
        
        return True, f"OK (module: {module.value}, {len(qe_input.namelists)} namelists, {len(qe_input.cards)} cards)", None
        
    except Exception as e:
        return False, str(e), e


def main():
    """Main test function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test QE input parser with official test-suite")
    parser.add_argument(
        "--qe-home",
        type=Path,
        default=None,
        help="Path to QE home directory (contains bin/ and test-suite/). If not specified, will auto-detect."
    )
    parser.add_argument(
        "--test-dir",
        type=Path,
        default=None,
        help="Path to QE test suite directory (default: auto-detected from QE installation)"
    )
    args = parser.parse_args()
    
    # Setup QE engine (auto-detect if not provided)
    if args.qe_home:
        config = EngineConfig(name="qe", executable_path=args.qe_home)
    else:
        config = EngineConfig(name="qe")
    engine = QuantumEspressoEngine(config)
    
    if not engine.installation.is_valid():
        print("ERROR: QE installation not found.")
        print("Please specify --qe-home or ensure QE is installed and accessible.")
        sys.exit(1)
    
    # Use auto-detected test-suite directory if not provided
    if args.test_dir is None:
        args.test_dir = engine.test_suite_dir
    
    test_suite_dir = args.test_dir
    
    if not test_suite_dir or not test_suite_dir.exists():
        print(f"❌ Test-suite directory not found: {test_suite_dir}")
        print(f"   Please specify --test-dir or ensure QE is installed with test-suite")
        print(f"   Expected location: {test_suite_dir}")
        sys.exit(1)
    
    # Find all .in files
    input_files = list(test_suite_dir.rglob("*.in"))
    
    if not input_files:
        print(f"❌ No .in files found in {test_suite_dir}")
        sys.exit(1)
    
    print(f"Found {len(input_files)} input files in test-suite")
    print("=" * 80)
    
    # Statistics
    stats = {
        'total': len(input_files),
        'success': 0,
        'failed': 0,
        'errors_by_type': defaultdict(int),
        'modules': defaultdict(int),
    }
    
    failed_files = []
    
    # Test each file
    for i, input_file in enumerate(input_files, 1):
        rel_path = input_file.relative_to(test_suite_dir)
        print(f"[{i}/{len(input_files)}] {rel_path} ... ", end="", flush=True)
        
        success, message, exception = test_parse_file(input_file)
        
        if success:
            stats['success'] += 1
            print(f"✓ {message}")
            
            # Try to detect module
            try:
                qe_input = QEInputParser.parse_file(input_file)
                if qe_input.module:
                    stats['modules'][qe_input.module.value] += 1
            except:
                pass
        else:
            stats['failed'] += 1
            error_type = type(exception).__name__ if exception else "Unknown"
            stats['errors_by_type'][error_type] += 1
            failed_files.append((rel_path, message, exception))
            print(f"✗ {message}")
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total files: {stats['total']}")
    print(f"Success: {stats['success']} ({stats['success']/stats['total']*100:.1f}%)")
    print(f"Failed: {stats['failed']} ({stats['failed']/stats['total']*100:.1f}%)")
    
    if stats['modules']:
        print("\nDetected modules:")
        for module, count in sorted(stats['modules'].items()):
            print(f"  {module}: {count}")
    
    if stats['errors_by_type']:
        print("\nError types:")
        for error_type, count in sorted(stats['errors_by_type'].items()):
            print(f"  {error_type}: {count}")
    
    # Print failed files details
    if failed_files:
        print(f"\nFailed files ({len(failed_files)}):")
        for rel_path, message, exception in failed_files[:20]:  # Show first 20
            print(f"  {rel_path}: {message}")
            if exception and len(failed_files) <= 10:
                print(f"    {traceback.format_exception_only(type(exception), exception)[0].strip()}")
        
        if len(failed_files) > 20:
            print(f"  ... and {len(failed_files) - 20} more")
    
    # Save failed files list
    if failed_files:
        failed_list_file = Path(__file__).parent / "failed_parses.txt"
        with open(failed_list_file, 'w') as f:
            f.write("Failed to parse files:\n\n")
            for rel_path, message, exception in failed_files:
                f.write(f"{rel_path}\n")
                f.write(f"  Error: {message}\n")
                if exception:
                    f.write(f"  Exception: {type(exception).__name__}\n")
                f.write("\n")
        print(f"\nFailed files list saved to: {failed_list_file}")
    
    return 0 if stats['failed'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

