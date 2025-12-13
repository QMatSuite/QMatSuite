#!/usr/bin/env python3
"""
Test bidirectional conversion for failed PH test categories.

This script:
1. Tests parse -> generate -> parse for all input files in failed categories
2. Identifies files with conversion issues
3. Reports detailed differences

Calculation Note:
  QE calculations run sequentially where:
  - pw.x (arg=1) generates .save directory (filename from prefix/outdir in input)
  - ph.x (arg=2) reads from .save (filename determined by pw.x input)
  - q2r.x (arg=3) reads dyn files (filename from ph.x input fildyn parameter)
  - matdyn.x (arg=4) reads .fc file (filename from q2r.x input flfrc parameter)
  
  Documentation:
  - pw.x: https://www.quantum-espresso.org/Doc/INPUT_PW.html
  - ph.x: https://www.quantum-espresso.org/Doc/INPUT_PH.html
  - q2r.x: https://www.quantum-espresso.org/Doc/INPUT_Q2R.html
  - matdyn.x: https://www.quantum-espresso.org/Doc/INPUT_MATDYN.html
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Add src to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from quantumvitas.io import QEInputParser, QEInputGenerator, QEModule


def compare_dicts(d1: Dict[str, Any], d2: Dict[str, Any], path: str = "") -> List[str]:
    """Compare two dictionaries and return list of differences."""
    differences = []
    
    # Compare namelists
    nl1 = d1.get('namelists', {})
    nl2 = d2.get('namelists', {})
    
    all_nl_names = set(nl1.keys()) | set(nl2.keys())
    for nl_name in all_nl_names:
        if nl_name not in nl1:
            differences.append(f"{path}.namelists.{nl_name}: missing in original")
        elif nl_name not in nl2:
            differences.append(f"{path}.namelists.{nl_name}: missing in regenerated")
        else:
            params1 = nl1[nl_name]
            params2 = nl2[nl_name]
            
            all_params = set(params1.keys()) | set(params2.keys())
            for param in all_params:
                if param not in params1:
                    differences.append(f"{path}.namelists.{nl_name}.{param}: missing in original")
                elif param not in params2:
                    differences.append(f"{path}.namelists.{nl_name}.{param}: missing in regenerated")
                elif params1[param] != params2[param]:
                    # Try to handle float comparison with tolerance
                    try:
                        v1 = float(params1[param]) if isinstance(params1[param], (int, float, str)) else params1[param]
                        v2 = float(params2[param]) if isinstance(params2[param], (int, float, str)) else params2[param]
                        if isinstance(v1, float) and isinstance(v2, float):
                            if abs(v1 - v2) > 1e-10:
                                differences.append(f"{path}.namelists.{nl_name}.{param}: {params1[param]} != {params2[param]} (diff: {abs(v1-v2):.2e})")
                        else:
                            differences.append(f"{path}.namelists.{nl_name}.{param}: {params1[param]} != {params2[param]}")
                    except (ValueError, TypeError):
                        # For non-numeric values, check string representation
                        if str(params1[param]) != str(params2[param]):
                            differences.append(f"{path}.namelists.{nl_name}.{param}: {params1[param]} != {params2[param]}")
    
    # Compare cards
    cards1 = d1.get('cards', [])
    cards2 = d2.get('cards', [])
    
    if len(cards1) != len(cards2):
        differences.append(f"{path}.cards: count {len(cards1)} != {len(cards2)}")
    else:
        for i, (c1, c2) in enumerate(zip(cards1, cards2)):
            if c1.get('type') != c2.get('type'):
                differences.append(f"{path}.cards[{i}].type: {c1.get('type')} != {c2.get('type')}")
            if c1.get('option') != c2.get('option'):
                differences.append(f"{path}.cards[{i}].option: {c1.get('option')} != {c2.get('option')}")
            # Compare data (simplified)
            if str(c1.get('data')) != str(c2.get('data')):
                differences.append(f"{path}.cards[{i}].data: different")
    
    return differences


def test_file_bidirectional(input_file: Path) -> Tuple[bool, str, List[str]]:
    """
    Test bidirectional conversion for a single file.
    
    Returns:
        (success, message, differences)
    """
    try:
        # Parse
        qe_input = QEInputParser.parse_file(input_file)
        detected_module = qe_input.detect_module()
        
        # Generate
        generated = QEInputGenerator.generate(qe_input)
        
        # Re-parse
        re_parsed = QEInputParser.parse_string(generated)
        
        # Compare - use JSON serialization for more reliable comparison
        import json
        original_dict = qe_input.to_dict()
        re_parsed_dict = re_parsed.to_dict()
        
        # Convert to JSON strings for comparison (handles float precision issues)
        orig_json = json.dumps(original_dict, sort_keys=True, default=str)
        repr_json = json.dumps(re_parsed_dict, sort_keys=True, default=str)
        
        if orig_json == repr_json:
            return True, f"{detected_module.value}", []
        else:
            differences = compare_dicts(original_dict, re_parsed_dict)
            return False, f"{detected_module.value}", differences
            
    except Exception as e:
        return False, f"ERROR: {str(e)[:80]}", []


def main():
    """Test bidirectional conversion for failed categories."""
    test_suite_dir = Path("<HOME>/src/q-e-qe-7.5/test-suite")
    
    # Failed categories from PH tests
    failed_categories = [
        'ph_base',
        'ph_2d',
        'ph_metal',
        'ph_ahc_bas',
        'ph_ahc_diam',
        'ph_interpol_metal',
        'ph_multipole',
        'ph_restart',
        'ph_U_insulator_paw',
        'ph_U_insulator_us',
        'ph_U_metal_paw',
        'ph_U_metal_us',
        'ph_Ni_nc_spinorbit_mag',
    ]
    
    print("=" * 70)
    print("测试失败类别的 Bidirectional 转换")
    print("=" * 70)
    print()
    print("Calculation 说明:")
    print("  - pw.x 生成 .save 目录 (文件名由 prefix/outdir 决定)")
    print("  - ph.x 读取 .save (文件名由 pw.x 输入决定)")
    print("  - q2r.x 读取 dyn 文件 (文件名由 ph.x 输入的 fildyn 参数决定)")
    print("  - matdyn.x 读取 .fc 文件 (文件名由 q2r.x 输入的 flfrc 参数决定)")
    print()
    print("官方文档:")
    print("  - pw.x: https://www.quantum-espresso.org/Doc/INPUT_PW.html")
    print("  - ph.x: https://www.quantum-espresso.org/Doc/INPUT_PH.html")
    print("  - q2r.x: https://www.quantum-espresso.org/Doc/INPUT_Q2R.html")
    print("  - matdyn.x: https://www.quantum-espresso.org/Doc/INPUT_MATDYN.html")
    print()
    print("=" * 70)
    print()
    
    total_files = 0
    passed_files = 0
    failed_files = []
    
    for category in failed_categories:
        category_dir = test_suite_dir / category
        if not category_dir.exists():
            print(f"类别: {category} - 目录不存在")
            continue
        
        print(f"类别: {category}")
        print("-" * 70)
        
        # Find all .in files
        input_files = sorted(category_dir.glob("*.in"))
        
        if not input_files:
            print("  无输入文件")
            print()
            continue
        
        category_passed = 0
        category_failed = []
        
        for input_file in input_files:
            total_files += 1
            success, message, differences = test_file_bidirectional(input_file)
            
            if success:
                print(f"  ✅ {input_file.name:30s} ({message})")
                passed_files += 1
                category_passed += 1
            else:
                print(f"  ❌ {input_file.name:30s} ({message})")
                if differences:
                    for diff in differences[:3]:  # Show first 3 differences
                        print(f"      - {diff}")
                    if len(differences) > 3:
                        print(f"      ... 还有 {len(differences) - 3} 个差异")
                category_failed.append((input_file.name, differences))
                failed_files.append((category, input_file.name, differences))
        
        print(f"  类别统计: {category_passed}/{len(input_files)} 通过")
        print()
    
    # Summary
    print("=" * 70)
    print("总结")
    print("=" * 70)
    print(f"总文件数: {total_files}")
    print(f"通过: {passed_files} ({passed_files/total_files*100:.1f}%)")
    print(f"失败: {total_files - passed_files} ({(total_files - passed_files)/total_files*100:.1f}%)")
    print()
    
    if failed_files:
        print("失败的文件:")
        for category, filename, differences in failed_files[:20]:  # Show first 20
            print(f"  - {category}/{filename}: {len(differences)} 个差异")
        if len(failed_files) > 20:
            print(f"  ... 还有 {len(failed_files) - 20} 个失败的文件")
    
    return 0 if passed_files == total_files else 1


if __name__ == "__main__":
    sys.exit(main())

