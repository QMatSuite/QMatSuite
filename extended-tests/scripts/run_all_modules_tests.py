#!/usr/bin/env python3
"""
Run all QE module tests with NPROCS=4.

This script runs tests for all QE modules:
- ph (phonon)
- pp (post-processing)
- cp (Car-Parrinello MD)
- hp (Hubbard U)
- tddfpt (time-dependent DFT)
- kcw (koopmans)
- epw (electron-phonon)
- zg (z2pack)
- all_currents
- xsd-pw (XML schema validation)
"""

import sys
import subprocess
import time
import os
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "extended-tests"))


def run_module_test(script_name: str, nprocs: int = 4, timeout: int = 600):
    """
    Run a module test script.
    
    Args:
        script_name: Name of the test script (e.g., 'run_ph_tests.py')
        nprocs: Number of processors
        timeout: Timeout in seconds
    
    Returns:
        dict with results
    """
    script_path = Path(__file__).parent / script_name
    
    if not script_path.exists():
        return {
            "module": script_name.replace("run_", "").replace("_tests.py", ""),
            "status": "SKIPPED",
            "error": f"Script not found: {script_name}",
            "duration": 0
        }
    
    print(f"\n{'=' * 70}")
    print(f"Running {script_name}")
    print(f"{'=' * 70}")
    
    start_time = time.time()
    
    try:
        # Run the script with nprocs via environment variable
        env = os.environ.copy()
        env['NPROCS'] = str(nprocs)
        
        # Check if script accepts --nprocs argument
        # Most scripts use NPROCS environment variable instead
        script_args = []
        
        # Try to detect if script accepts --nprocs
        help_result = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if "--nprocs" in help_result.stdout:
            script_args = ["--nprocs", str(nprocs)]
        
        result = subprocess.run(
            [sys.executable, str(script_path)] + script_args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=project_root,
            env=env
        )
        
        duration = time.time() - start_time
        
        if result.returncode == 0:
            status = "PASSED"
            error = None
        else:
            status = "FAILED"
            error = result.stderr[:500] if result.stderr else "Unknown error"
        
        return {
            "module": script_name.replace("run_", "").replace("_tests.py", ""),
            "status": status,
            "error": error,
            "duration": duration,
            "stdout": result.stdout[:1000] if result.stdout else None
        }
    
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        return {
            "module": script_name.replace("run_", "").replace("_tests.py", ""),
            "status": "TIMEOUT",
            "error": f"Timeout after {timeout} seconds",
            "duration": duration
        }
    
    except Exception as e:
        duration = time.time() - start_time
        return {
            "module": script_name.replace("run_", "").replace("_tests.py", ""),
            "status": "ERROR",
            "error": str(e)[:500],
            "duration": duration
        }


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Run all QE module tests with NPROCS=4"
    )
    parser.add_argument(
        "--nprocs",
        type=int,
        default=4,
        help="Number of processors (default: 4)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Timeout per module in seconds (default: 600)"
    )
    parser.add_argument(
        "--modules",
        nargs="+",
        default=None,
        help="Specific modules to test (default: all)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file for results (default: extended-tests/all_modules_results.json)"
    )
    
    args = parser.parse_args()
    
    # List of all module test scripts
    all_modules = [
        "run_ph_tests.py",
        "run_pp_tests.py",
        "run_cp_tests.py",
        "run_hp_tests.py",
        "run_tddfpt_tests.py",
        "run_kcw_tests.py",
        "run_epw_tests.py",
        "run_zg_tests.py",
        "run_all_currents_tests.py",
        "run_xsd_pw_tests.py",
    ]
    
    # Filter modules if specified
    if args.modules:
        all_modules = [
            m for m in all_modules
            if any(mod in m for mod in args.modules)
        ]
    
    print("=" * 70)
    print("QE Module Tests - All Modules")
    print("=" * 70)
    print(f"Number of processors: {args.nprocs}")
    print(f"Timeout per module: {args.timeout} seconds")
    print(f"Modules to test: {len(all_modules)}")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    results = []
    
    for script_name in all_modules:
        result = run_module_test(script_name, args.nprocs, args.timeout)
        results.append(result)
        
        # Print summary
        status_symbol = {
            "PASSED": "✅",
            "FAILED": "❌",
            "TIMEOUT": "⏱️",
            "ERROR": "⚠️",
            "SKIPPED": "⏭️"
        }.get(result["status"], "❓")
        
        print(f"{status_symbol} {result['module']:15s} - {result['status']:10s} ({result['duration']:.1f}s)")
        if result.get("error"):
            print(f"   Error: {result['error'][:100]}")
    
    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    
    total_time = sum(r["duration"] for r in results)
    passed = sum(1 for r in results if r["status"] == "PASSED")
    failed = sum(1 for r in results if r["status"] == "FAILED")
    timeout = sum(1 for r in results if r["status"] == "TIMEOUT")
    error = sum(1 for r in results if r["status"] == "ERROR")
    skipped = sum(1 for r in results if r["status"] == "SKIPPED")
    
    print(f"Total modules: {len(results)}")
    print(f"  ✅ Passed:  {passed}")
    print(f"  ❌ Failed:  {failed}")
    print(f"  ⏱️  Timeout: {timeout}")
    print(f"  ⚠️  Error:   {error}")
    print(f"  ⏭️  Skipped: {skipped}")
    print(f"Total time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
    print()
    
    # Save results
    import json
    output_file = args.output or project_root / "extended-tests" / "all_modules_results.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    summary = {
        "timestamp": datetime.now().isoformat(),
        "nprocs": args.nprocs,
        "timeout": args.timeout,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "timeout": timeout,
            "error": error,
            "skipped": skipped,
            "total_time": total_time
        },
        "results": results
    }
    
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"Results saved to: {output_file}")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Exit code
    if failed > 0 or error > 0:
        sys.exit(1)
    elif timeout > 0:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()

