#!/usr/bin/env python3
"""
Run xsd-pw tests (XML schema validation for pw.x input files).

This test validates that pw.x input files conform to the XML schema.
Uses the validate_xsd_pw.py script from the test-suite.
"""

import sys
import subprocess
from pathlib import Path
import argparse

# Add src to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "extended-tests"))


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Run xsd-pw XML schema validation tests")
    parser.add_argument(
        "--test-dir",
        type=Path,
        default=None,
        help="Path to QE test suite directory (default: auto-detected from QE installation)"
    )
    parser.add_argument(
        "--qe-home",
        type=Path,
        default=None,
        help="Path to QE home directory (contains bin/ and test-suite/). If not specified, will auto-detect."
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout per test in seconds"
    )
    
    args = parser.parse_args()
    
    # Infer test-suite directory from QE path if not provided
    if args.test_dir is None:
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
        
        qe_bin = engine.installation.bin_dir
        if qe_bin.is_dir():
            qe_root = qe_bin.parent
        else:
            qe_root = qe_bin.parent.parent
        args.test_dir = qe_root / "test-suite"
    
    if not args.test_dir.exists():
        print(f"Error: Test suite directory not found: {args.test_dir}")
        sys.exit(1)
    
    # Find xsd_pw directory and validation script
    xsd_pw_dir = args.test_dir / "xsd_pw"
    validate_script = args.test_dir / "validate_xsd_pw.py"
    
    if not xsd_pw_dir.exists():
        print(f"Warning: xsd_pw directory not found: {xsd_pw_dir}")
        print("Skipping xsd-pw tests")
        sys.exit(0)
    
    if not validate_script.exists():
        print(f"Error: Validation script not found: {validate_script}")
        sys.exit(1)
    
    print(f"Test suite: {args.test_dir}")
    print(f"XSD validation script: {validate_script}")
    print(f"XSD test directory: {xsd_pw_dir}")
    print("=" * 60)
    
    # Find all .in files in xsd_pw directory
    input_files = sorted(xsd_pw_dir.glob("*.in"))
    
    if not input_files:
        print("No .in files found in xsd_pw directory")
        sys.exit(0)
    
    print(f"Running {len(input_files)} xsd-pw validation tests...")
    print("=" * 60)
    
    results = []
    for i, input_file in enumerate(input_files, 1):
        print(f"\n[{i}/{len(input_files)}] {input_file.name}")
        
        try:
            # Run validation script
            result = subprocess.run(
                [sys.executable, str(validate_script), str(input_file)],
                cwd=args.test_dir,
                capture_output=True,
                text=True,
                timeout=args.timeout
            )
            
            success = result.returncode == 0
            if success:
                print(f"  ✓ PASS: XML schema validation successful")
            else:
                print(f"  ✗ FAIL: XML schema validation failed")
                if result.stdout:
                    print(f"    Output: {result.stdout[:200]}")
                if result.stderr:
                    print(f"    Error: {result.stderr[:200]}")
            
            results.append({
                "file": input_file.name,
                "success": success,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            })
            
        except subprocess.TimeoutExpired:
            print(f"  ✗ FAIL: Test timed out after {args.timeout}s")
            results.append({
                "file": input_file.name,
                "success": False,
                "error": "Timeout"
            })
        except Exception as e:
            print(f"  ✗ FAIL: Error running test: {e}")
            results.append({
                "file": input_file.name,
                "success": False,
                "error": str(e)
            })
    
    # Overall summary
    print("\n" + "=" * 60)
    print("OVERALL SUMMARY")
    print("=" * 60)
    total = len(results)
    passed = sum(1 for r in results if r.get("success", False))
    failed = total - passed
    
    print(f"Total tests: {total}")
    print(f"Passed: {passed} ({passed/total*100:.1f}%)" if total > 0 else "Passed: 0")
    print(f"Failed: {failed} ({failed/total*100:.1f}%)" if total > 0 else "Failed: 0")
    
    if failed > 0:
        print("\nFailed tests:")
        for r in results:
            if not r.get("success", False):
                error = r.get("error") or "Validation failed"
                print(f"  - {r['file']}: {error}")
    
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()

