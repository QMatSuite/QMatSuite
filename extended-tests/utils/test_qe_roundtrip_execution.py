#!/usr/bin/env python3
"""
Test QE input roundtrip execution: parse -> generate -> run -> verify.

This script:
1. Reads QE input files from the official test suite
2. Parses them using QEInputParser
3. Generates new input files using QEInputGenerator
4. Runs pw.x with the generated input
5. Verifies the calculation completes successfully (JOB DONE)
6. Has a 1-minute timeout per test
"""

import sys
import subprocess
import signal
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
import time
import shutil
import urllib.request
import urllib.error
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig
from quantumvitas.core.engines.qe_input import QEInputParser, QEInputGenerator, QECardType


class TimeoutError(Exception):
    """Raised when a test times out."""
    pass


def run_with_timeout(command: list, cwd: Path, timeout: int = 60, env: Optional[Dict[str, str]] = None) -> tuple[int, str, str]:
    """
    Run command with timeout.
    
    Args:
        command: Command to run
        cwd: Working directory
        timeout: Timeout in seconds
        env: Optional environment variables dict
        
    Returns:
        Tuple of (returncode, stdout, stderr)
        
    Raises:
        TimeoutError: If command exceeds timeout
    """
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            preexec_fn=None if sys.platform == "win32" else lambda: signal.signal(signal.SIGINT, signal.SIG_IGN)
        )
        
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            return process.returncode, stdout, stderr
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise TimeoutError(f"Command exceeded {timeout}s timeout")
    except Exception as e:
        raise TimeoutError(f"Error running command: {e}")


def download_pseudopotential(pp_name: str, pseudo_dir: Path, network_url: str = "https://pseudopotentials.quantum-espresso.org/upf_files/") -> bool:
    """
    Download pseudopotential file if not present.
    
    Args:
        pp_name: Pseudopotential filename
        pseudo_dir: Directory to store pseudopotentials
        network_url: URL base for downloading pseudopotentials
        
    Returns:
        True if file exists or was successfully downloaded
    """
    pseudo_dir.mkdir(parents=True, exist_ok=True)
    pp_path = pseudo_dir / pp_name
    
    # Check if already exists
    if pp_path.exists():
        return True
    
    # Try to download
    download_url = network_url + pp_name
    try:
        print(f"  Downloading {pp_name}...")
        urllib.request.urlretrieve(download_url, pp_path)
        return pp_path.exists()
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        print(f"  Warning: Failed to download {pp_name}: {e}")
        return False


def ensure_pseudopotentials(input_file: Path, working_dir: Path, test_suite_dir: Optional[Path] = None) -> bool:
    """
    Ensure all required pseudopotentials are available.
    
    Args:
        input_file: QE input file path
        working_dir: Working directory for calculation
        test_suite_dir: Optional test suite directory (for finding pseudo directory)
        
    Returns:
        True if all pseudopotentials are available
    """
    from quantumvitas.core.engines.qe_input import QEInputParser, QECardType
    
    # Parse input to find required pseudopotentials
    qe_input = QEInputParser.parse_file(input_file)
    atomic_species = qe_input.get_card(QECardType.ATOMIC_SPECIES)
    
    if not atomic_species or not atomic_species.data:
        return True  # No pseudopotentials needed
    
    # Determine pseudo directory
    if test_suite_dir:
        # Use test suite pseudo directory
        pseudo_dir = test_suite_dir.parent / "pseudo"
    else:
        # Use working directory
        pseudo_dir = working_dir / "pseudo"
    
    # Network URL for downloading
    network_url = "https://pseudopotentials.quantum-espresso.org/upf_files/"
    
    # Collect all required pseudopotentials
    required_pps = []
    for line in atomic_species.data:
        if len(line) >= 3:
            required_pps.append(line[2])  # Pseudopotential filename
    
    # Check and download each pseudopotential
    all_available = True
    for pp_name in required_pps:
        # First check in test suite directory structure
        found = False
        
        if test_suite_dir:
            # Check common locations
            search_dirs = [
                test_suite_dir.parent / "pseudo",
                test_suite_dir / "pseudo",
                test_suite_dir.parent.parent / "pseudo",
            ]
            
            for search_dir in search_dirs:
                pp_file = search_dir / pp_name
                if pp_file.exists():
                    # Copy to working directory
                    (working_dir / pp_name).write_bytes(pp_file.read_bytes())
                    found = True
                    break
        
        # If not found, try downloading
        if not found:
            if download_pseudopotential(pp_name, pseudo_dir, network_url):
                # Copy to working directory
                (working_dir / pp_name).write_bytes((pseudo_dir / pp_name).read_bytes())
                found = True
        
        if not found:
            print(f"  Error: Pseudopotential {pp_name} not found and download failed")
            all_available = False
    
    return all_available


def verify_qe_output(output_file: Path) -> tuple[bool, str]:
    """
    Verify QE output file indicates successful completion.
    
    Args:
        output_file: Path to QE output file
        
    Returns:
        Tuple of (success, message)
    """
    if not output_file.exists():
        return False, "Output file not found"
    
    try:
        content = output_file.read_text()
        
        # Check for JOB DONE (standard QE completion marker)
        if "JOB DONE" in content:
            # Check for errors
            if "error" in content.lower() and "convergence" not in content.lower():
                # Some errors are acceptable (like convergence issues)
                error_lines = [line for line in content.split('\n') if 'error' in line.lower() and 'convergence' not in line.lower()]
                if error_lines:
                    return False, f"Errors found: {error_lines[0][:100]}"
            
            # Extract total energy if available
            energy = None
            for line in content.split('\n'):
                if 'total energy' in line.lower() or '!    total energy' in line.lower():
                    # Try to extract energy value
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if 'ry' in part.lower() or 'ev' in part.lower():
                            if i > 0:
                                try:
                                    energy = float(parts[i-1])
                                    break
                                except ValueError:
                                    pass
            
            return True, f"JOB DONE (energy: {energy} Ry)" if energy else "JOB DONE"
        else:
            # Check for specific error messages
            if "error" in content.lower():
                error_lines = [line for line in content.split('\n') if 'error' in line.lower()][:3]
                return False, f"Errors found: {'; '.join([l[:80] for l in error_lines])}"
            
            return False, "JOB DONE not found in output"
    except Exception as e:
        return False, f"Error reading output: {e}"


def test_input_roundtrip_execution(
    input_file: Path,
    qe_engine: QuantumEspressoEngine,
    timeout: int = 60,
    working_dir: Optional[Path] = None,
    step_number: Optional[str] = None
) -> Dict[str, Any]:
    """
    Test roundtrip execution: parse -> generate -> run -> verify.
    
    Args:
        input_file: Original QE input file
        qe_engine: Configured QE engine
        timeout: Timeout in seconds
        working_dir: Optional working directory (creates temp if None)
        
    Returns:
        Dictionary with test results
    """
    result = {
        "input_file": str(input_file),
        "success": False,
        "error": None,
        "parse_success": False,
        "generate_success": False,
        "run_success": False,
        "verify_success": False,
        "output_file": None,
        "time_taken": None,
        "message": None
    }
    
    start_time = time.time()
    
    # Use temporary directory if not provided
    if working_dir is None:
        working_dir = Path(tempfile.mkdtemp(prefix="qe_test_"))
        cleanup_temp = True
    else:
        cleanup_temp = False
        working_dir.mkdir(parents=True, exist_ok=True)
    
    # For workflow tests, step_number indicates which step this is
    # This can be used to determine input/output file names
    
    try:
        # Step 1: Parse input file
        try:
            qe_input = QEInputParser.parse_file(input_file)
            result["parse_success"] = True
        except Exception as e:
            result["error"] = f"Parse failed: {e}"
            return result
        
        # Step 2: Generate new input file
        try:
            # For workflow tests, use step-specific filename
            if step_number:
                generated_input = working_dir / f"test_input_step{step_number}.in"
            else:
                generated_input = working_dir / "test_input.in"
            QEInputGenerator.write_file(qe_input, generated_input)
            result["generate_success"] = True
        except Exception as e:
            result["error"] = f"Generate failed: {e}"
            return result
        
        # Step 3: Ensure pseudopotentials are available
        # Determine test suite directory from input_file path
        test_suite_dir = None
        input_path = Path(input_file)
        # Check if input_file is in test-suite directory
        if "test-suite" in str(input_path):
            # Find test-suite directory
            parts = input_path.parts
            for i, part in enumerate(parts):
                if part == "test-suite":
                    test_suite_dir = Path(*parts[:i+1])
                    break
        # If not found, try to infer from QE installation
        if test_suite_dir is None or not test_suite_dir.exists():
            # Try to find from environment or common locations
            # This is a fallback - ideally test-suite should be passed explicitly
            pass
        
        if not ensure_pseudopotentials(input_file, working_dir, test_suite_dir):
            result["error"] = "Failed to obtain required pseudopotentials"
            return result
        
        # Step 4: Build and run command
        try:
            command = qe_engine.build_command("scf", generated_input, working_dir)
            
            # Determine output file name
            # QE typically writes to stdout, but may also create files based on prefix
            # Check control namelist for prefix, otherwise use input filename
            prefix = None
            control_nl = qe_input.get_namelist("control")
            if control_nl:
                prefix = control_nl.parameters.get("prefix", None)
            
            if prefix:
                output_file = working_dir / f"{prefix}.out"
            else:
                # QE writes to stdout, so we'll check stdout.txt instead
                input_stem = generated_input.stem
                output_file = working_dir / f"{input_stem}.out"
            
            # QE actually writes to stdout, so the output is in stdout.txt
            # But we'll also check for prefix-based files
            stdout_file = working_dir / "stdout.txt"
            
            # Set ESPRESSO_PSEUDO environment variable to point to working directory
            # so pw.x can find the pseudopotentials
            env = os.environ.copy()
            env['ESPRESSO_PSEUDO'] = str(working_dir)
            
            # Run with timeout
            returncode, stdout, stderr = run_with_timeout(command, working_dir, timeout, env=env)
            
            # Write stdout/stderr to files for debugging
            (working_dir / "stdout.txt").write_text(stdout)
            (working_dir / "stderr.txt").write_text(stderr)
            
            # Also save generated input for debugging
            (working_dir / "generated_input.in").write_text(generated_input.read_text())
            
            result["run_success"] = (returncode == 0)
            result["returncode"] = returncode
            result["output_file"] = str(output_file)
            
            if not result["run_success"]:
                # Check if output file exists (might have been created before error)
                if output_file.exists():
                    output_preview = output_file.read_text()[:500]
                    result["error"] = f"pw.x returned {returncode}\nstderr: {stderr[:200]}\noutput preview: {output_preview}"
                else:
                    result["error"] = f"pw.x returned {returncode}\nstderr: {stderr[:200]}"
                return result
            
        except TimeoutError as e:
            result["error"] = str(e)
            return result
        except Exception as e:
            import traceback
            result["error"] = f"Run failed: {e}\n{traceback.format_exc()}"
            return result
        
        # Step 5: Verify output
        # QE writes to stdout, so check stdout.txt file
        stdout_file = working_dir / "stdout.txt"
        if stdout_file.exists():
            # Create a symlink or copy for verification
            verify_file = stdout_file
        else:
            verify_file = output_file
        
        verify_success, verify_message = verify_qe_output(verify_file)
        result["verify_success"] = verify_success
        result["message"] = verify_message
        
        result["success"] = result["verify_success"]
        
    finally:
        result["time_taken"] = time.time() - start_time
        # Optionally clean up temp directory
        # if cleanup_temp and working_dir.exists():
        #     import shutil
        #     shutil.rmtree(working_dir)
    
    return result


def main():
    """Main test function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test QE input roundtrip execution")
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
        help="Path to QE test suite directory (default: inferred from --qe-path). Required for extended tests."
    )
    parser.add_argument(
        "--download-pseudo",
        action="store_true",
        default=True,
        help="Automatically download missing pseudopotentials"
    )
    parser.add_argument(
        "--test-category",
        type=str,
        default="pw_dft",
        help="Test category (e.g., pw_dft, pw_scf)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout per test in seconds"
    )
    parser.add_argument(
        "--max-tests",
        type=int,
        default=5,
        help="Maximum number of tests to run"
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
    
    if not args.test_dir.exists():
        print(f"Error: Test suite directory not found: {args.test_dir}")
        print(f"Please specify --test-dir or ensure QE is installed with test-suite")
        sys.exit(1)
    
    # Setup QE engine
    config = EngineConfig(name="qe", executable_path=args.qe_path)
    engine = QuantumEspressoEngine(config)
    
    # Check if pw.x is available
    if not engine.detect_executable("pw.x"):
        print(f"ERROR: pw.x not found at {args.qe_path}")
        print("Please specify correct path with --qe-path")
        sys.exit(1)
    
    print(f"QE Engine configured: {engine.get_executable_path('pw.x')}")
    print(f"Test directory: {args.test_dir}")
    print(f"Test category: {args.test_category}")
    print(f"Timeout: {args.timeout}s per test")
    print("=" * 60)
    
    # Find test input files
    test_dir = args.test_dir / args.test_category
    if not test_dir.exists():
        print(f"ERROR: Test directory not found: {test_dir}")
        sys.exit(1)
    
    input_files = sorted([f for f in test_dir.glob("*.in") if not f.name.startswith("benchmark")])
    
    if not input_files:
        print(f"ERROR: No .in files found in {test_dir}")
        sys.exit(1)
    
    print(f"Found {len(input_files)} test files")
    print(f"Running first {min(args.max_tests, len(input_files))} tests...\n")
    
    # Run tests
    results = []
    for i, input_file in enumerate(input_files[:args.max_tests]):
        print(f"[{i+1}/{min(args.max_tests, len(input_files))}] Testing {input_file.name}...")
        
        result = test_input_roundtrip_execution(input_file, engine, args.timeout)
        results.append(result)
        
        if result["success"]:
            print(f"  ✓ PASS ({result['time_taken']:.1f}s): {result['message']}")
        else:
            print(f"  ✗ FAIL ({result['time_taken']:.1f}s): {result.get('error', result.get('message', 'Unknown error'))}")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for r in results if r["success"])
    failed = len(results) - passed
    
    print(f"Total: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed > 0:
        print("\nFailed tests:")
        for r in results:
            if not r["success"]:
                print(f"  - {Path(r['input_file']).name}: {r.get('error', r.get('message', 'Unknown'))}")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

