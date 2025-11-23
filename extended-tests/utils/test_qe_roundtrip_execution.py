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
    
    All pseudopotentials are downloaded to temp/pseudo/ and then copied to working_dir.
    
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
    
    # Unified pseudo directory: temp/pseudo/
    project_root = Path(__file__).parent.parent.parent
    unified_pseudo_dir = project_root / "temp" / "pseudo"
    unified_pseudo_dir.mkdir(parents=True, exist_ok=True)
    
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
        found = False
        
        # First check in unified pseudo directory
        unified_pp_path = unified_pseudo_dir / pp_name
        if unified_pp_path.exists():
            # Copy to working directory
            (working_dir / pp_name).write_bytes(unified_pp_path.read_bytes())
            found = True
        else:
            # Check in test suite directory structure (if available)
            if test_suite_dir:
                search_dirs = [
                    test_suite_dir.parent / "pseudo",
                    test_suite_dir / "pseudo",
                    test_suite_dir.parent.parent / "pseudo",
                ]
                
                for search_dir in search_dirs:
                    pp_file = search_dir / pp_name
                    if pp_file.exists():
                        # Copy to unified directory first, then to working directory
                        unified_pp_path.write_bytes(pp_file.read_bytes())
                        (working_dir / pp_name).write_bytes(pp_file.read_bytes())
                        found = True
                        break
            
            # If not found, try downloading to unified directory
            if not found:
                if download_pseudopotential(pp_name, unified_pseudo_dir, network_url):
                    # Copy to working directory
                    (working_dir / pp_name).write_bytes(unified_pp_path.read_bytes())
                    found = True
        
        if not found:
            print(f"  Error: Pseudopotential {pp_name} not found and download failed")
            all_available = False
    
    return all_available


def verify_qe_output(output_file: Path) -> tuple[bool, str]:
    """
    Verify QE output file indicates successful completion.
    
    Priority: For pw.x (SCF calculations), check for "! total energy" first (most reliable).
    If not found, fall back to JOB DONE check.
    
    Args:
        output_file: Path to QE output file
        
    Returns:
        Tuple of (success, message)
    """
    if not output_file.exists():
        return False, "Output file not found"
    
    try:
        content = output_file.read_text()
        
        # Priority 1: For SCF calculations, check for "! total energy" (most reliable)
        # Format: !    total energy              =     -26.70549012 Ry
        import re
        energy_pattern = r"!\s+total energy\s+=\s+([-\d.]+)\s+Ry"
        energy_match = re.search(energy_pattern, content, re.IGNORECASE)
        
        if energy_match:
            try:
                energy = float(energy_match.group(1))
                # If we have energy, calculation is successful (SCF always has this)
                return True, f"Total energy: {energy:.8f} Ry"
            except ValueError:
                pass
        else:
            # Fallback: If "! total energy" not found, look for other energy patterns
            # (for non-SCF pw.x calculations like nscf, bands, dos)
            energy_patterns = [
                # Pattern 1: "total energy" without "!" (nscf may have this)
                r"total energy\s+=\s+([-\d.]+)\s+Ry",
                # Pattern 2: "Final energy" (sometimes used)
                r"Final\s+energy\s+=\s+([-\d.]+)\s+Ry",
                # Pattern 3: "energy" near "Ry" (more general)
                r"energy\s+=\s+([-\d.]+)\s+Ry",
            ]
            
            for alt_pattern in energy_patterns:
                energy_match = re.search(alt_pattern, content, re.IGNORECASE)
                if energy_match:
                    try:
                        energy = float(energy_match.group(1))
                        return True, f"Energy: {energy:.8f} Ry"
                    except ValueError:
                        continue
        
        # Priority 2: Check for JOB DONE (standard QE completion marker)
        if "JOB DONE" in content:
            # Check for errors
            if "error" in content.lower() and "convergence" not in content.lower():
                # Some errors are acceptable (like convergence issues)
                error_lines = [line for line in content.split('\n') if 'error' in line.lower() and 'convergence' not in line.lower()]
                if error_lines:
                    return False, f"Errors found: {error_lines[0][:100]}"
            
            # Try to extract energy from other patterns if "! total energy" not found
            energy = None
            if not energy_match:
                for line in content.split('\n'):
                    if 'total energy' in line.lower():
                        try:
                            # Look for pattern: total energy = -26.70549012 Ry
                            match = re.search(r'=\s+([-\d.]+)\s+Ry', line)
                            if match:
                                energy = float(match.group(1))
                                break
                        except (ValueError, IndexError):
                            continue
            
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
            
            # Save parsed input to temp for debugging
            project_root = Path(__file__).parent.parent.parent
            temp_output_dir = project_root / "temp" / "test_outputs"
            
            # Try to determine category from input_file path
            category = None
            input_path = Path(input_file)
            if "test-suite" in str(input_path):
                parts = input_path.parts
                for i, part in enumerate(parts):
                    if part == "test-suite" and i + 1 < len(parts):
                        category = parts[i + 1]  # Category is usually the first subdirectory
                        break
            
            if category:
                temp_output_dir = temp_output_dir / category
            temp_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Create parsed filename
            input_filename = input_path.name
            parsed_filename = input_filename.replace(".in", "_parsed.in")
            if not parsed_filename.endswith(".in"):
                parsed_filename = f"{input_filename}_parsed.in"
            
            if step_number:
                parsed_filename = f"{Path(input_filename).stem}_step{step_number}_parsed.in"
            
            temp_parsed_input = temp_output_dir / parsed_filename
            QEInputGenerator.write_file(qe_input, temp_parsed_input)
            result["parsed_input_file"] = str(temp_parsed_input)
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
        "--qe-home",
        type=Path,
        default=None,
        help="Path to QE home directory (contains bin/ and test-suite/). If not specified, will auto-detect."
    )
    parser.add_argument(
        "--test-dir",
        type=Path,
        default=None,
        help="Path to QE test suite directory (default: auto-detected from QE installation). Required for extended tests."
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
    
    if not args.test_dir or not args.test_dir.exists():
        print(f"Error: Test suite directory not found: {args.test_dir}")
        print(f"Please specify --test-dir or ensure QE is installed with test-suite")
        sys.exit(1)
    
    # Check if pw.x is available
    if not engine.detect_executable("pw.x"):
        print(f"ERROR: pw.x not found")
        sys.exit(1)
    
    print(f"QE home: {engine.installation.qe_home}")
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

