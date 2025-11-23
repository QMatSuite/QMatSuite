#!/usr/bin/env python3
"""
Run all PW tests with statistics collection.

This script:
1. Runs all PW test categories from QE test-suite
2. Collects timing and success rate for each test
3. Outputs detailed statistics
4. Identifies shortest, representative tests for CI
"""

import sys
import subprocess
import configparser
import tempfile
from pathlib import Path
from typing import List, Tuple, Dict, Any
import os
import time
import json
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "extended-tests"))

from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig
from utils.qe_module_base import run_test_category
from tests.core.qe_test_utils import parse_jobconfig


def run_pw_test_with_stats(
    category: str,
    test_files: List[Tuple[str, str]],
    test_suite_dir: Path,
    qe_engine: QuantumEspressoEngine,
    nprocs: int = 4,
    timeout: int = 300
) -> Dict[str, Any]:
    """
    Run a single test category and collect statistics.
    
    Returns:
        Dictionary with test results and statistics
    """
    print(f"\n{'='*60}")
    print(f"Running category: {category}")
    print(f"{'='*60}")
    
    category_stats = {
        "category": category,
        "total_tests": len(test_files),
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "total_time": 0.0,
        "test_details": [],
        "avg_time": 0.0,
        "success_rate": 0.0
    }
    
    start_time = time.time()
    
    try:
        results = run_test_category(
            category,
            test_files,
            test_suite_dir,
            qe_engine,
            {"default": "pw.x"},
            timeout=timeout,
            max_tests=None  # Run all tests
        )
        
        category_stats["total_time"] = time.time() - start_time
        
        for result in results:
            test_file = result.get("file", result.get("input_file", "unknown"))
            test_time = result.get("time_taken", 0.0)
            
            test_detail = {
                "test_file": test_file,
                "success": result.get("success", False),
                "time": test_time,
                "error": result.get("error", "")
            }
            category_stats["test_details"].append(test_detail)
            
            if result.get("success", False):
                category_stats["passed"] += 1
            else:
                category_stats["failed"] += 1
                if result.get("error", ""):
                    print(f"  ✗ {test_file}: {result.get('error', '')[:100]}")
        
        if category_stats["total_tests"] > 0:
            category_stats["success_rate"] = category_stats["passed"] / category_stats["total_tests"]
            category_stats["avg_time"] = category_stats["total_time"] / category_stats["total_tests"]
        
        print(f"  Results: {category_stats['passed']}/{category_stats['total_tests']} passed "
              f"({category_stats['success_rate']*100:.1f}%) "
              f"in {category_stats['total_time']:.2f}s")
        
    except Exception as e:
        category_stats["error"] = str(e)
        category_stats["total_time"] = time.time() - start_time
        print(f"  ✗ Error: {e}")
    
    return category_stats


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Run all PW tests with statistics",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
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
        help="Path to QE test suite directory"
    )
    parser.add_argument(
        "--nprocs",
        type=int,
        default=4,
        help="Number of processors (NPROCS)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Timeout per test in seconds"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Save statistics to JSON file"
    )
    parser.add_argument(
        "--max-categories",
        type=int,
        help="Maximum number of categories to run (for testing)"
    )
    
    args = parser.parse_args()
    
    # Setup QE engine (auto-detect if not provided)
    if args.qe_home:
        config = EngineConfig(name="qe", executable_path=args.qe_home)
    else:
        config = EngineConfig(name="qe")
    qe_engine = QuantumEspressoEngine(config)
    
    if not qe_engine.installation.is_valid():
        print("ERROR: QE installation not found.")
        print("Please specify --qe-home or ensure QE is installed and accessible.")
        sys.exit(1)
    
    # Use auto-detected test-suite directory if not provided
    if args.test_dir is None:
        args.test_dir = qe_engine.test_suite_dir
    
    if not args.test_dir or not args.test_dir.exists():
        print(f"Error: Test suite directory not found: {args.test_dir}")
        sys.exit(1)
    
    # Set NPROCS in environment
    os.environ["NPROCS"] = str(args.nprocs)
    
    # Parse jobconfig
    jobconfig_path = args.test_dir / "jobconfig"
    if not jobconfig_path.exists():
        print(f"Error: jobconfig not found: {jobconfig_path}")
        sys.exit(1)
    
    categories = parse_jobconfig(jobconfig_path, module_prefix="pw_")
    
    # Convert to list of (name, test_files) tuples for easier handling
    category_list = list(categories.items())
    
    if args.max_categories:
        category_list = category_list[:args.max_categories]
        print(f"Running first {args.max_categories} categories for testing...")
    
    print(f"\n{'='*60}")
    print(f"Running PW Tests with Statistics")
    print(f"{'='*60}")
    print(f"QE home: {qe_engine.installation.qe_home}")
    print(f"Test Suite: {args.test_dir}")
    print(f"NPROCS: {args.nprocs}")
    print(f"Total Categories: {len(category_list)}")
    print(f"{'='*60}\n")
    
    all_stats = []
    overall_start = time.time()
    
    for category_name, test_files in category_list:
        stats = run_pw_test_with_stats(
            category_name,
            test_files,
            args.test_dir,
            qe_engine,
            nprocs=args.nprocs,
            timeout=args.timeout
        )
        all_stats.append(stats)
    
    overall_time = time.time() - overall_start
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"OVERALL SUMMARY")
    print(f"{'='*60}")
    
    total_tests = sum(s["total_tests"] for s in all_stats)
    total_passed = sum(s["passed"] for s in all_stats)
    total_failed = sum(s["failed"] for s in all_stats)
    
    print(f"Total Categories: {len(all_stats)}")
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {total_passed} ({total_passed/total_tests*100:.1f}%)")
    print(f"Failed: {total_failed} ({total_failed/total_tests*100:.1f}%)")
    print(f"Total Time: {overall_time:.2f}s")
    print(f"Average Time per Test: {overall_time/total_tests:.2f}s")
    
    # Find shortest, representative tests
    print(f"\n{'='*60}")
    print(f"ANALYZING FOR CI QUICK TESTS")
    print(f"{'='*60}")
    
    # Collect all individual test results
    all_test_results = []
    for stats in all_stats:
        for test_detail in stats["test_details"]:
            if test_detail["success"]:  # Only consider passing tests
                all_test_results.append({
                    "category": stats["category"],
                    "test_file": test_detail["test_file"],
                    "time": test_detail["time"],
                    "category_time": stats["avg_time"]
                })
    
    # Sort by time
    all_test_results.sort(key=lambda x: x["time"])
    
    # Select representative tests (diverse categories, short time)
    selected_tests = []
    selected_categories = set()
    
    for test_result in all_test_results:
        if len(selected_tests) >= 10:
            break
        
        category = test_result["category"]
        # Prefer tests from different categories
        if category not in selected_categories or len(selected_tests) < 5:
            selected_tests.append(test_result)
            selected_categories.add(category)
    
    # Fill remaining slots with shortest tests
    for test_result in all_test_results:
        if len(selected_tests) >= 10:
            break
        if test_result not in selected_tests:
            selected_tests.append(test_result)
    
    print(f"\nSelected {len(selected_tests)} representative tests for CI:")
    print("-" * 60)
    for i, test in enumerate(selected_tests, 1):
        print(f"{i:2d}. {test['category']:20s} | {test['test_file']:30s} | {test['time']:6.2f}s")
    
    # Save statistics
    output_data = {
        "overall": {
            "total_categories": len(all_stats),
            "total_tests": total_tests,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "success_rate": total_passed / total_tests if total_tests > 0 else 0,
            "total_time": overall_time,
            "avg_time_per_test": overall_time / total_tests if total_tests > 0 else 0
        },
        "categories": all_stats,
        "selected_ci_tests": selected_tests
    }
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"\nStatistics saved to: {args.output}")
    else:
        # Save to default location
        output_file = project_root / "extended-tests" / "pw_test_stats.json"
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"\nStatistics saved to: {output_file}")
    
    # Print category breakdown
    print(f"\n{'='*60}")
    print(f"CATEGORY BREAKDOWN")
    print(f"{'='*60}")
    print(f"{'Category':<25s} {'Tests':<8s} {'Passed':<8s} {'Rate':<8s} {'Time':<10s}")
    print("-" * 60)
    
    for stats in sorted(all_stats, key=lambda x: x["success_rate"], reverse=True):
        print(f"{stats['category']:<25s} {stats['total_tests']:<8d} "
              f"{stats['passed']:<8d} {stats['success_rate']*100:>6.1f}% "
              f"{stats['total_time']:>8.2f}s")
    
    sys.exit(0 if total_failed == 0 else 1)


if __name__ == "__main__":
    main()

