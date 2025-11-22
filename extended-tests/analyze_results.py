#!/usr/bin/env python3
"""
Analyze extended test results and generate success rate report.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List
from collections import defaultdict


def analyze_results(results_file: Path) -> Dict[str, Any]:
    """
    Analyze test results and generate statistics.
    
    Args:
        results_file: Path to JSON results file
    
    Returns:
        Dictionary with analysis results
    """
    with open(results_file) as f:
        data = json.load(f)
    
    analysis = {
        "overall": data.get("summary", {}),
        "by_suite": {},
        "by_status": defaultdict(int),
        "failures": []
    }
    
    # Analyze by suite
    for suite_name, results in data.get("suites", {}).items():
        suite_stats = {
            "total": len(results),
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "error": 0,
            "pass_rate": 0.0,
            "avg_time": 0.0
        }
        
        total_time = 0.0
        for result in results:
            status = result.get("status", "unknown")
            suite_stats[status] = suite_stats.get(status, 0) + 1
            analysis["by_status"][status] += 1
            
            if status == "passed":
                suite_stats["passed"] += 1
            elif status == "failed":
                suite_stats["failed"] += 1
                analysis["failures"].append({
                    "suite": suite_name,
                    "test": result.get("name"),
                    "error": result.get("error", result.get("message", ""))
                })
            elif status == "skipped":
                suite_stats["skipped"] += 1
            elif status == "error":
                suite_stats["error"] += 1
            
            total_time += result.get("time_taken", 0.0)
        
        if suite_stats["total"] > 0:
            suite_stats["pass_rate"] = suite_stats["passed"] / suite_stats["total"]
            suite_stats["avg_time"] = total_time / suite_stats["total"]
        
        analysis["by_suite"][suite_name] = suite_stats
    
    return analysis


def print_report(analysis: Dict[str, Any]) -> None:
    """Print analysis report."""
    print("=" * 80)
    print("EXTENDED TESTS ANALYSIS REPORT")
    print("=" * 80)
    
    # Overall summary
    overall = analysis["overall"]
    print(f"\nOverall Summary:")
    print(f"  Total tests: {overall.get('total', 0)}")
    print(f"  Passed: {overall.get('passed', 0)} ({overall.get('pass_rate', 0)*100:.1f}%)")
    print(f"  Failed: {overall.get('failed', 0)}")
    print(f"  Skipped: {overall.get('skipped', 0)}")
    print(f"  Errors: {overall.get('error', 0)}")
    
    # By suite
    print(f"\nBy Suite:")
    print("-" * 80)
    for suite_name, stats in sorted(analysis["by_suite"].items()):
        print(f"  {suite_name}:")
        print(f"    Total: {stats['total']}")
        print(f"    Passed: {stats['passed']} ({stats['pass_rate']*100:.1f}%)")
        print(f"    Failed: {stats['failed']}")
        print(f"    Avg time: {stats['avg_time']:.2f}s")
    
    # Failures
    if analysis["failures"]:
        print(f"\nFailures ({len(analysis['failures'])}):")
        print("-" * 80)
        for failure in analysis["failures"][:20]:  # Show first 20
            print(f"  {failure['suite']}/{failure['test']}")
            if failure['error']:
                print(f"    Error: {failure['error'][:100]}")
        if len(analysis["failures"]) > 20:
            print(f"  ... and {len(analysis['failures']) - 20} more failures")
    
    # Status breakdown
    print(f"\nStatus Breakdown:")
    for status, count in sorted(analysis["by_status"].items()):
        print(f"  {status}: {count}")


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze extended test results")
    parser.add_argument(
        "results_file",
        type=Path,
        help="Path to JSON results file"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Save analysis to file"
    )
    
    args = parser.parse_args()
    
    if not args.results_file.exists():
        print(f"Error: Results file not found: {args.results_file}")
        sys.exit(1)
    
    # Analyze
    analysis = analyze_results(args.results_file)
    
    # Print report
    print_report(analysis)
    
    # Save if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(analysis, f, indent=2)
        print(f"\nAnalysis saved to: {args.output}")
    
    # Exit code based on pass rate
    overall = analysis["overall"]
    pass_rate = overall.get("pass_rate", 0.0)
    if pass_rate < 0.8:  # Less than 80% pass rate
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()

