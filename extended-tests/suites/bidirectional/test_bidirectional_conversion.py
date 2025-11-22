#!/usr/bin/env python3
"""
Test bidirectional conversion: parse -> generate -> parse.

This script tests that input files can be:
1. Parsed from .in files
2. Generated back to .in files
3. Parsed again successfully
4. Key parameters are preserved

This is an extended test that requires QE test-suite.
"""

import sys
from pathlib import Path
from collections import defaultdict
import tempfile
import shutil

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from quantumvitas.core.engines.qe_input import QEInputParser, QEInputGenerator, QEModule, QECardType


def compare_namelists(nl1, nl2, name: str) -> tuple[bool, list[str]]:
    """Compare two namelists and return differences."""
    if nl1 is None and nl2 is None:
        return True, []
    if nl1 is None or nl2 is None:
        return False, [f"{name}: one is None"]
    
    differences = []
    all_keys = set(nl1.parameters.keys()) | set(nl2.parameters.keys())
    
    for key in all_keys:
        val1 = nl1.parameters.get(key)
        val2 = nl2.parameters.get(key)
        
        # Normalize values for comparison
        # Handle numeric types (int, float, and string representations)
        try:
            # Try to convert both to float for comparison
            val1_num = float(val1) if not isinstance(val1, (int, float)) else val1
            val2_num = float(val2) if not isinstance(val2, (int, float)) else val2
            # If both can be converted to numbers, compare numerically
            if abs(val1_num - val2_num) > 1e-10:
                differences.append(f"{name}.{key}: {val1} != {val2}")
            continue
        except (ValueError, TypeError):
            # Not numeric, continue with other comparisons
            pass
        
        if isinstance(val1, float) and isinstance(val2, float):
            # For floats, allow small numerical differences
            if abs(val1 - val2) > 1e-10:
                differences.append(f"{name}.{key}: {val1} != {val2}")
        elif isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            # For numbers, compare directly
            if abs(float(val1) - float(val2)) > 1e-10:
                differences.append(f"{name}.{key}: {val1} != {val2}")
        elif isinstance(val1, str) and isinstance(val2, str):
            # For strings, compare normalized (case-insensitive, whitespace)
            # Also handle scientific notation differences (1e-08 vs 1.0e-08)
            val1_norm = val1.strip().lower().replace('1.0e-', '1e-').replace('1.0e+', '1e+')
            val2_norm = val2.strip().lower().replace('1.0e-', '1e-').replace('1.0e+', '1e+')
            if val1_norm != val2_norm:
                differences.append(f"{name}.{key}: '{val1}' != '{val2}'")
        elif val1 != val2:
            differences.append(f"{name}.{key}: {val1} != {val2}")
    
    return len(differences) == 0, differences


def compare_cards(card1, card2, card_type: QECardType) -> tuple[bool, list[str]]:
    """Compare two cards and return differences."""
    if card1 is None and card2 is None:
        return True, []
    if card1 is None or card2 is None:
        return False, [f"{card_type.value}: one is None"]
    
    differences = []
    
    if card1.option != card2.option:
        differences.append(f"{card_type.value} option: {card1.option} != {card2.option}")
    
    if len(card1.data) != len(card2.data):
        differences.append(f"{card_type.value} data length: {len(card1.data)} != {len(card2.data)}")
    else:
        for i, (line1, line2) in enumerate(zip(card1.data, card2.data)):
            if line1 != line2:
                differences.append(f"{card_type.value} line {i}: {line1} != {line2}")
    
    return len(differences) == 0, differences


def test_roundtrip(input_file: Path, temp_dir: Path) -> tuple[bool, str, dict]:
    """
    Test roundtrip conversion: parse -> generate -> parse.
    
    Returns:
        (success, message, stats)
    """
    stats = {
        'namelists_match': True,
        'cards_match': True,
        'module_match': True,
        'differences': []
    }
    
    try:
        # Step 1: Parse original file
        qe_input1 = QEInputParser.parse_file(input_file)
        
        if not qe_input1.namelists and not qe_input1.cards:
            return False, "Original file has no namelists or cards", stats
        
        # Step 2: Generate new file
        output_file = temp_dir / f"roundtrip_{input_file.name}"
        QEInputGenerator.write_file(qe_input1, output_file)
        
        # Step 3: Parse generated file
        qe_input2 = QEInputParser.parse_file(output_file)
        
        # Step 4: Compare
        # Compare modules
        if qe_input1.module != qe_input2.module:
            stats['module_match'] = False
            stats['differences'].append(f"Module: {qe_input1.module} != {qe_input2.module}")
        
        # Compare namelists
        nl_names = set()
        for nl in qe_input1.namelists:
            nl_names.add(nl.name.lower())
        for nl in qe_input2.namelists:
            nl_names.add(nl.name.lower())
        
        for nl_name in nl_names:
            nl1 = qe_input1.get_namelist(nl_name)
            nl2 = qe_input2.get_namelist(nl_name)
            match, diffs = compare_namelists(nl1, nl2, nl_name)
            if not match:
                stats['namelists_match'] = False
                stats['differences'].extend(diffs)
        
        # Compare cards
        card_types = set()
        for card in qe_input1.cards:
            card_types.add(card.card_type)
        for card in qe_input2.cards:
            card_types.add(card.card_type)
        
        for card_type in card_types:
            card1 = qe_input1.get_card(card_type)
            card2 = qe_input2.get_card(card_type)
            match, diffs = compare_cards(card1, card2, card_type)
            if not match:
                stats['cards_match'] = False
                stats['differences'].extend(diffs)
        
        # Overall success
        success = stats['namelists_match'] and stats['cards_match'] and stats['module_match']
        
        if success:
            message = f"OK (module: {qe_input1.module.value if qe_input1.module else 'unknown'}, {len(qe_input1.namelists)} namelists, {len(qe_input1.cards)} cards)"
        else:
            message = f"Differences found: {len(stats['differences'])} issues"
        
        return success, message, stats
        
    except Exception as e:
        return False, f"Error: {str(e)}", stats


def main():
    """Main test function."""
    # Find test-suite directory
    import argparse
    
    parser = argparse.ArgumentParser(description="Test bidirectional QE input conversion")
    parser.add_argument(
        "--qe-path",
        type=Path,
        default=Path.home() / "src" / "q-e-qe-7.5" / "bin",
        help="Path to QE bin directory"
    )
    parser.add_argument(
        "--test-dir",
        type=Path,
        default=None,
        help="Path to QE test suite directory (default: inferred from --qe-path)"
    )
    args = parser.parse_args()
    
    # Infer test-suite directory from QE path if not provided
    if args.test_dir is None:
        # QE bin is typically at $QE_ROOT/bin, test-suite is at $QE_ROOT/test-suite
        qe_bin = args.qe_path
        if qe_bin.is_dir():
            # If qe_path is a directory (bin), go up one level
            qe_root = qe_bin.parent
        else:
            # If qe_path is a file (pw.x), go up two levels
            qe_root = qe_bin.parent.parent
        args.test_dir = qe_root / "test-suite"
    
    test_suite_dir = args.test_dir
    
    if not test_suite_dir.exists():
        print(f"❌ Test-suite directory not found: {test_suite_dir}")
        print(f"   Please specify --test-dir or ensure QE is installed with test-suite")
        print(f"   Expected location: {test_suite_dir}")
        sys.exit(1)
    
    # Find all .in files (exclude benchmark output files)
    input_files = [
        f for f in test_suite_dir.rglob("*.in")
        if "benchmark.out.git.inp=" not in str(f)
    ]
    
    if not input_files:
        print(f"❌ No .in files found in {test_suite_dir}")
        sys.exit(1)
    
    print(f"Testing bidirectional conversion on {len(input_files)} input files")
    print("=" * 80)
    
    # Create temporary directory for generated files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Statistics
        stats = {
            'total': len(input_files),
            'success': 0,
            'failed': 0,
            'errors': 0,
            'differences': 0,
            'modules': defaultdict(int),
        }
        
        failed_files = []
        files_with_differences = []
        
        # Test each file
        for i, input_file in enumerate(input_files, 1):
            rel_path = input_file.relative_to(test_suite_dir)
            print(f"[{i}/{len(input_files)}] {rel_path} ... ", end="", flush=True)
            
            success, message, file_stats = test_roundtrip(input_file, temp_path)
            
            if success:
                stats['success'] += 1
                print(f"✓ {message}")
                
                # Count module
                try:
                    qe_input = QEInputParser.parse_file(input_file)
                    if qe_input.module:
                        stats['modules'][qe_input.module.value] += 1
                except:
                    pass
            else:
                if "Error:" in message:
                    stats['errors'] += 1
                    stats['failed'] += 1
                elif "Differences" in message:
                    stats['differences'] += 1
                    stats['failed'] += 1
                    files_with_differences.append((rel_path, message, file_stats))
                else:
                    stats['failed'] += 1
                
                failed_files.append((rel_path, message, file_stats))
                print(f"✗ {message}")
        
        # Print summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Total files: {stats['total']}")
        print(f"Success: {stats['success']} ({stats['success']/stats['total']*100:.1f}%)")
        print(f"Failed: {stats['failed']} ({stats['failed']/stats['total']*100:.1f}%)")
        print(f"  - Errors: {stats['errors']}")
        print(f"  - Differences: {stats['differences']}")
        
        if stats['modules']:
            print("\nModules tested:")
            for module, count in sorted(stats['modules'].items()):
                print(f"  {module}: {count}")
        
        # Print files with differences
        if files_with_differences:
            print(f"\nFiles with differences ({len(files_with_differences)}):")
            for rel_path, message, file_stats in files_with_differences[:20]:
                print(f"  {rel_path}: {message}")
                if file_stats['differences']:
                    for diff in file_stats['differences'][:3]:
                        print(f"    - {diff}")
                    if len(file_stats['differences']) > 3:
                        print(f"    ... and {len(file_stats['differences']) - 3} more")
            
            if len(files_with_differences) > 20:
                print(f"  ... and {len(files_with_differences) - 20} more")
        
        # Save detailed results
        if failed_files:
            results_file = Path(__file__).parent / "bidirectional_test_results.txt"
            with open(results_file, 'w') as f:
                f.write("Bidirectional Conversion Test Results\n")
                f.write("=" * 80 + "\n\n")
                for rel_path, message, file_stats in failed_files:
                    f.write(f"{rel_path}\n")
                    f.write(f"  {message}\n")
                    if file_stats['differences']:
                        f.write("  Differences:\n")
                        for diff in file_stats['differences']:
                            f.write(f"    - {diff}\n")
                    f.write("\n")
            print(f"\nDetailed results saved to: {results_file}")
        
        return 0 if stats['failed'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

