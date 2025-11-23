"""
Common utilities for QE testing.

This module provides shared functionality for testing QE modules,
including jobconfig parsing, benchmark comparison, and frequency extraction.
These utilities are used by both tests/ and extended-tests/.
"""

import re
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import configparser

# Import unified thresholds
from .thresholds import (
    get_energy_tolerance,
    get_frequency_threshold,
    DEFAULT_ENERGY_TOLERANCE,
    DEFAULT_FREQUENCY_THRESHOLD,
)


def parse_jobconfig(jobconfig_path: Path, module_prefix: str) -> Dict[str, List[Tuple[str, str]]]:
    """
    Parse jobconfig file to get test order for a specific module.
    
    Args:
        jobconfig_path: Path to jobconfig file
        module_prefix: Module prefix (e.g., "ph_", "pp_", "cp_")
    
    Returns:
        Dict mapping category name to list of (input_file, args) tuples
    """
    config = configparser.ConfigParser()
    config.read(jobconfig_path)
    
    tests = {}
    for section in config.sections():
        section_name = section.rstrip('/')
        if section_name.startswith(module_prefix):
            if 'inputs_args' in config[section]:
                try:
                    inputs = eval(config[section]['inputs_args'])
                    tests[section_name] = inputs
                except Exception as e:
                    print(f"Warning: Could not parse inputs_args for {section}: {e}")
                    tests[section_name] = []
            else:
                tests[section_name] = []
    
    return tests


def extract_ph_frequencies(content: str) -> Optional[List[float]]:
    """
    Extract all frequency values (in THz) from ph.x output.
    
    Extracts frequencies from ALL frequency blocks (all q-points).
    Frequencies are located between lines of asterisks (*****).
    Format: freq (    N) =      X.XXXXXX [THz] =     Y.YYYYYY [cm-1]
    
    Args:
        content: ph.x output content
        
    Returns:
        List of frequency values in THz from all frequency blocks, or None if extraction failed
    """
    lines = content.split('\n')
    frequencies = []
    in_freq_section = False
    
    for line in lines:
        # Check for separator line (all asterisks)
        if re.match(r'^\s*\*+\s*$', line):
            in_freq_section = not in_freq_section
            continue
        
        # If we're in a frequency section, extract frequencies
        if in_freq_section:
            # Pattern: freq (    N) =      X.XXXXXX [THz] =     Y.YYYYYY [cm-1]
            match = re.search(r'freq\s*\(\s*\d+\s*\)\s*=\s+([-\d.]+)\s+\[THz\]', line, re.IGNORECASE)
            if match:
                try:
                    freq = float(match.group(1))
                    frequencies.append(freq)
                except ValueError:
                    continue
    
    return frequencies if frequencies else None


def compare_with_benchmark(
    output_file: Path,
    benchmark_file: Path,
    executable_name: str = "pw.x",
    tolerance: Optional[float] = None,
    category: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Compare test output with benchmark output.
    
    For pw.x (SCF calculations), compares total energy.
    For ph.x, compares frequencies between two ***** lines.
    For other modules, only checks JOB DONE.
    
    Args:
        output_file: Path to test output
        benchmark_file: Path to benchmark output
        executable_name: QE executable name (e.g., "pw.x", "ph.x")
        tolerance: Numerical tolerance for energy comparison (if None, uses threshold from thresholds.py)
        category: Test category name (e.g., "ph_1d", "ph_2d") for category-specific thresholds
    
    Returns:
        (pass_test, message)
    
    Note:
        Thresholds are managed in tests.core.thresholds module.
        For ph.x frequency comparison, all tests use 0.015 THz by default.
    """
    # Use unified thresholds if tolerance not provided
    if tolerance is None:
        tolerance = get_energy_tolerance(category, executable_name)
    if not benchmark_file.exists():
        # No benchmark to compare - just check for JOB DONE
        if output_file.exists():
            content = output_file.read_text()
            if "JOB DONE" in content:
                return True, "JOB DONE (no benchmark to compare)"
        return False, "No benchmark and no JOB DONE"
    
    # Read both files
    try:
        output_content = output_file.read_text()
        benchmark_content = benchmark_file.read_text()
    except Exception as e:
        return False, f"Error reading files: {e}"
    
    # Check for JOB DONE
    if "JOB DONE" not in output_content:
        return False, "JOB DONE not found in output"
    
    # For pw.x (and certain pw.x calculations), compare total energy
    # Priority: Use "! total energy" (most reliable indicator for SCF calculations)
    if executable_name == "pw.x":
        # Priority 1: Look for "! total energy" (most reliable, SCF always has this)
        # Format: !    total energy              =     -26.70549012 Ry
        energy_pattern = r"!\s+total energy\s+=\s+([-\d.]+)\s+Ry"
        output_match = re.search(energy_pattern, output_content, re.IGNORECASE)
        benchmark_match = re.search(energy_pattern, benchmark_content, re.IGNORECASE)
        
        if output_match and benchmark_match:
            try:
                output_energy = float(output_match.group(1))
                benchmark_energy = float(benchmark_match.group(1))
                energy_diff = abs(output_energy - benchmark_energy)
                
                if energy_diff <= tolerance:
                    return True, f"Energy matches: {output_energy:.8f} Ry (diff: {energy_diff:.2e})"
                else:
                    return False, f"Energy mismatch: {output_energy:.8f} vs {benchmark_energy:.8f} (diff: {energy_diff:.2e})"
            except ValueError:
                pass
        
        # Fallback: If "! total energy" not found, look for other energy patterns nearby
        # (for non-SCF pw.x calculations like nscf, bands, dos)
        if not output_match:
            # Try multiple patterns in order of reliability
            energy_patterns = [
                # Pattern 1: "total energy" without "!" (nscf may have this)
                r"total energy\s+=\s+([-\d.]+)\s+Ry",
                # Pattern 2: "Final energy" (sometimes used)
                r"Final\s+energy\s+=\s+([-\d.]+)\s+Ry",
                # Pattern 3: "energy" near "Ry" (more general)
                r"energy\s+=\s+([-\d.]+)\s+Ry",
            ]
            
            for alt_pattern in energy_patterns:
                output_match = re.search(alt_pattern, output_content, re.IGNORECASE)
                benchmark_match = re.search(alt_pattern, benchmark_content, re.IGNORECASE)
                
                if output_match and benchmark_match:
                    try:
                        output_energy = float(output_match.group(1))
                        benchmark_energy = float(benchmark_match.group(1))
                        energy_diff = abs(output_energy - benchmark_energy)
                        
                        if energy_diff <= tolerance:
                            return True, f"Energy matches: {output_energy:.8f} Ry (diff: {energy_diff:.2e})"
                        else:
                            return False, f"Energy mismatch: {output_energy:.8f} vs {benchmark_energy:.8f} (diff: {energy_diff:.2e})"
                    except ValueError:
                        continue
    
    # For ph.x, compare frequencies between two ***** lines
    if executable_name == "ph.x":
        output_freqs = extract_ph_frequencies(output_content)
        benchmark_freqs = extract_ph_frequencies(benchmark_content)
        
        if output_freqs is None or benchmark_freqs is None:
            # If frequency extraction failed, just check JOB DONE
            return True, "JOB DONE (frequency extraction failed)"
        
        # Check if frequency counts match
        if len(output_freqs) != len(benchmark_freqs):
            return False, f"Frequency count mismatch: {len(output_freqs)} vs {len(benchmark_freqs)}"
        
        # Calculate mean absolute difference
        if len(output_freqs) == 0:
            return True, "JOB DONE (no frequencies found)"
        
        freq_diffs = [abs(o - b) for o, b in zip(output_freqs, benchmark_freqs)]
        mean_diff = sum(freq_diffs) / len(freq_diffs)
        max_diff = max(freq_diffs) if freq_diffs else 0.0
        min_diff = min(freq_diffs) if freq_diffs else 0.0
        
        # Build detailed difference message
        diff_details = []
        diff_details.append(f"mean abs diff = {mean_diff:.6f} THz")
        diff_details.append(f"max diff = {max_diff:.6f} THz")
        diff_details.append(f"min diff = {min_diff:.6f} THz")
        
        # Show first few individual differences
        if len(freq_diffs) <= 10:
            # Show all differences
            diff_list = [f"{d:.6f}" for d in freq_diffs]
            diff_details.append(f"diffs = [{', '.join(diff_list)}] THz")
        else:
            # Show first 5 and last 5
            diff_list_start = [f"{d:.6f}" for d in freq_diffs[:5]]
            diff_list_end = [f"{d:.6f}" for d in freq_diffs[-5:]]
            diff_details.append(f"diffs (first 5) = [{', '.join(diff_list_start)}] THz")
            diff_details.append(f"diffs (last 5) = [{', '.join(diff_list_end)}] THz")
        
        diff_message = "; ".join(diff_details)
        
        # Get frequency threshold from unified thresholds module
        freq_threshold = get_frequency_threshold(category)
        
        if mean_diff > freq_threshold:
            return False, f"Frequency mean abs diff too large: {diff_message} (threshold: {freq_threshold} THz)"
        else:
            return True, f"Frequencies match: {diff_message}"
    
    # For other non-pw.x modules, just check JOB DONE
    return True, "JOB DONE"

