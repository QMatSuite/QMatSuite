#!/usr/bin/env python3
"""
Check progress of PW test statistics collection.
"""

import json
from pathlib import Path
import time

stats_file = Path(__file__).parent.parent / "pw_test_stats.json"
log_file = Path(__file__).parent.parent / "pw_test_run.log"

print("=" * 60)
print("PW Test Statistics Collection Progress")
print("=" * 60)

# Check log file
if log_file.exists():
    with open(log_file) as f:
        lines = f.readlines()
        print(f"\nLog file: {len(lines)} lines")
        print("\nLast 10 lines:")
        for line in lines[-10:]:
            print(f"  {line.rstrip()}")
else:
    print("\n⚠ Log file not found. Script may not have started yet.")

# Check stats file
if stats_file.exists():
    print(f"\n✓ Statistics file found: {stats_file}")
    print(f"  Size: {stats_file.stat().st_size / 1024:.1f} KB")
    print(f"  Modified: {time.ctime(stats_file.stat().st_mtime)}")
    
    try:
        with open(stats_file) as f:
            data = json.load(f)
        
        overall = data.get("overall", {})
        print(f"\nCurrent Statistics:")
        print(f"  Categories: {overall.get('total_categories', 0)}")
        print(f"  Total Tests: {overall.get('total_tests', 0)}")
        print(f"  Passed: {overall.get('total_passed', 0)}")
        print(f"  Failed: {overall.get('total_failed', 0)}")
        if overall.get('total_tests', 0) > 0:
            print(f"  Success Rate: {overall.get('success_rate', 0)*100:.1f}%")
        print(f"  Total Time: {overall.get('total_time', 0):.2f}s")
        
        selected = data.get("selected_ci_tests", [])
        print(f"\n  Selected CI Tests: {len(selected)}")
        
        categories = data.get("categories", [])
        print(f"\n  Categories Completed: {len(categories)}")
        if categories:
            print(f"  Last Category: {categories[-1].get('category', 'unknown')}")
    except Exception as e:
        print(f"\n⚠ Error reading stats file: {e}")
else:
    print(f"\n⚠ Statistics file not found yet: {stats_file}")
    print("  Script is still running or hasn't started...")

print("\n" + "=" * 60)

