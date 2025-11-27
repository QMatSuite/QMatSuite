"""Utility function to copy input-reference output pairs from QE test-suite.

This module provides a general function to copy test files from the QE test-suite
based on step type detection and optional filename filtering.
"""

import shutil
import re
from pathlib import Path
from typing import Optional, Tuple, List, Callable


def find_test_suite_dir() -> Optional[Path]:
    """Find QE test-suite directory based on QE_BIN_DIR or default layout."""
    import os

    qe_bin = os.environ.get("QE_BIN_DIR")
    if qe_bin:
        qe_bin = Path(qe_bin)
    else:
        qe_bin = Path.home() / "src" / "q-e-qe-7.5" / "bin"

    if not qe_bin.exists():
        return None

    qe_root = qe_bin if qe_bin.is_dir() else qe_bin.parent
    test_suite = qe_root.parent / "test-suite"
    if test_suite.exists():
        return test_suite

    return None


def is_step_type(input_file: Path, step_type: str) -> bool:
    """
    Detect if an input file matches the specified step type.
    
    Args:
        input_file: Path to QE input file
        step_type: Step type to check (e.g., "scf", "nscf", "ph", etc.)
        
    Returns:
        True if the file matches the step type, False otherwise
    """
    try:
        # Import here to avoid circular dependencies
        import sys
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root / "src"))
        
        from quantumvitas.io import QEInputParser, QEModule
        from quantumvitas.core.engines.qe_workflow import QEWorkflowRunner
        
        qe_input = QEInputParser.parse_file(input_file)
        module = qe_input.detect_module()
        
        # For pw.x, detect calculation type from control namelist
        if module == QEModule.PW:
            control = qe_input.get_namelist('control')
            if control:
                calculation = control.get('calculation', 'scf').lower()
                # Map QE calculation types to step types
                calculation_map = {
                    'scf': 'scf',
                    'nscf': 'nscf',
                    'bands': 'bands_pw',
                    'relax': 'opt',
                    'vc-relax': 'opt',
                    'md': 'md',
                    'vc-md': 'md',
                }
                detected_step = calculation_map.get(calculation, 'scf')
                return detected_step == step_type.lower()
            # Default for pw.x without explicit calculation is SCF
            return step_type.lower() == 'scf'
        
        # For other modules, use module name as step type
        module_to_step = {
            QEModule.PH: 'ph',
            QEModule.DOS: 'dos',
            QEModule.BANDS: 'bands',
            QEModule.PROJWFC: 'projwfc',
            QEModule.Q2R: 'q2r',
            QEModule.MATDYN: 'matdyn',
            QEModule.PP: 'pp',
            QEModule.NEB: 'neb',
            QEModule.CP: 'cp',
            QEModule.LD1: 'ld1',
            QEModule.HP: 'hp',
            QEModule.PWCOND: 'pwcond',
            QEModule.DYNMAT: 'dynmat',
            QEModule.GIPAW: 'gipaw',
        }
        
        detected_step = module_to_step.get(module, 'unknown')
        return detected_step == step_type.lower()
        
    except Exception as e:
        # If parsing fails, skip this file
        return False


def find_benchmark_file(category_dir: Path, input_filename: str) -> Optional[Path]:
    """
    Find benchmark output file for an input file.
    
    Looks for files matching pattern: benchmark.out.git.inp={input_filename}*
    
    Args:
        category_dir: Directory containing the input file
        input_filename: Name of the input file
        
    Returns:
        Path to benchmark file if found, None otherwise
    """
    # Pattern: benchmark.out.git.inp={input_filename} or with .args=...
    exact_match = category_dir / f"benchmark.out.git.inp={input_filename}"
    if exact_match.exists():
        return exact_match
    
    # Try glob pattern
    matches = list(category_dir.glob(f"benchmark.out.git.inp={input_filename}*"))
    if matches:
        # Return the first match (usually there's only one)
        return matches[0]
    
    return None


def copy_test_files(
    test_suite_dir: Path,
    output_dir: Path,
    step_type: str,
    filename_filter: Optional[Callable[[str], bool]] = None,
    verbose: bool = True
) -> Tuple[int, int, List[Tuple[str, str]]]:
    """
    Copy test files from test-suite to output directory.
    
    Args:
        test_suite_dir: Path to QE test-suite directory
        output_dir: Output directory (full path where files will be copied)
        step_type: Step type to filter (e.g., "scf", "nscf", "ph", etc.)
        filename_filter: Optional function to filter filenames (returns True to include)
        verbose: Print progress messages
        
    Returns:
        Tuple of (copied_count, skipped_count, copied_files_list)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    copied_count = 0
    skipped_count = 0
    copied_files: List[Tuple[str, str]] = []
    
    if verbose:
        print(f"Scanning test-suite: {test_suite_dir}")
        print(f"Step type: {step_type}")
        if filename_filter:
            print(f"Filename filter: enabled")
        print(f"Output directory: {output_dir}\n")
    
    # Iterate through all directories in test-suite
    for category_dir in sorted(test_suite_dir.iterdir()):
        if not category_dir.is_dir():
            continue
        
        category_name = category_dir.name
        if verbose:
            print(f"Scanning category: {category_name}")
        
        # Find all .in files (excluding those with "benchmark" in name)
        input_files = [
            f for f in category_dir.glob("*.in")
            if "benchmark" not in f.name.lower()
        ]
        
        if not input_files:
            continue
        
        category_count = 0
        for input_file in sorted(input_files):
            # Apply filename filter if provided
            if filename_filter and not filename_filter(input_file.name):
                continue
            
            # Check if it matches the step type
            if not is_step_type(input_file, step_type):
                continue
            
            # Find corresponding benchmark file
            benchmark_file = find_benchmark_file(category_dir, input_file.name)
            if not benchmark_file:
                skipped_count += 1
                if verbose:
                    print(f"  ⏭️  Skipped {input_file.name} (no benchmark found)")
                continue
            
            # Copy input file
            dest_input = output_dir / input_file.name
            shutil.copy2(input_file, dest_input)
            
            # Copy benchmark file
            dest_benchmark = output_dir / benchmark_file.name
            shutil.copy2(benchmark_file, dest_benchmark)
            
            copied_count += 1
            category_count += 1
            copied_files.append((category_name, input_file.name))
            
            if verbose:
                print(f"  ✓ Copied {input_file.name} + {benchmark_file.name}")
        
        if verbose and category_count > 0:
            print(f"  → Found {category_count} {step_type} test(s) in {category_name}\n")
    
    return copied_count, skipped_count, copied_files

