"""
Centralized QE step verification functions.

This module provides standardized verification for QE calculation steps:
- SCF: Compare total energy
- NSCF: Compare Fermi energy
- Other: Check JOB DONE

All tests should use these functions instead of implementing their own verification logic.
"""

import re
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from src.quantumvitas.core.engines.qe_calculation import StepResult
from .thresholds import (
    get_energy_tolerance,
    get_fermi_energy_tolerance,
    get_frequency_threshold,
)
from .qe_test_utils import extract_ph_frequencies


def verify_step_result(
    step_result: StepResult,
    reference_file: Optional[Path] = None,
    category: Optional[str] = None,
    tolerance: Optional[float] = None
) -> Tuple[bool, str]:
    """
    Verify a QE step result based on step type.
    
    Verification logic:
    - scf: Compare total energy with reference
    - nscf: Compare Fermi energy with reference
    - ph: Compare frequencies with reference (if available)
    - Other: Check JOB DONE
    
    Args:
        step_result: StepResult from run_step()
        reference_file: Optional reference output file for comparison
        category: Test category name (e.g., "pw_scf", "ph_1d") for threshold selection
        tolerance: Optional custom tolerance (overrides category-based threshold)
    
    Returns:
        (success, message) tuple
    """
    # Check if step succeeded
    if not step_result.success:
        return False, f"Step {step_result.step_type_spec} failed: {step_result.error}"
    
    # Check output file exists
    if not step_result.output_file or not step_result.output_file.exists():
        return False, f"Output file not found for step {step_result.step_type_spec}"
    
    output_content = step_result.output_file.read_text()
    
    # Always check for JOB DONE first
    if "JOB DONE" not in output_content:
        return False, f"JOB DONE not found in output for step {step_result.step_type_spec}"
    
    # If no reference file, just check JOB DONE
    if reference_file is None or not reference_file.exists():
        return True, f"JOB DONE (no reference file to compare)"
    
    # Read reference file
    try:
        reference_content = reference_file.read_text()
    except Exception as e:
        return False, f"Error reading reference file: {e}"
    
    # Route to appropriate verification based on step type
    step_type = step_result.step_type_spec.lower()
    
    if step_type == "scf":
        return _verify_scf_energy(
            output_content, reference_content, category, tolerance
        )
    elif step_type == "nscf":
        return _verify_nscf_fermi_energy(
            output_content, reference_content, category, tolerance
        )
    elif step_type == "ph":
        return _verify_ph_frequencies(
            output_content, reference_content, category, tolerance
        )
    else:
        # For other step types, just verify JOB DONE (already checked above)
        return True, f"JOB DONE (no specific verification for step type {step_type})"


def _verify_scf_energy(
    output_content: str,
    reference_content: str,
    category: Optional[str] = None,
    tolerance: Optional[float] = None
) -> Tuple[bool, str]:
    """Verify SCF total energy."""
    if tolerance is None:
        tolerance = get_energy_tolerance(category, "pw.x")
    
    # Extract total energy from output
    energy_pattern = r"!\s+total energy\s+=\s+([-\d.]+)\s+Ry"
    output_match = re.search(energy_pattern, output_content, re.IGNORECASE)
    reference_match = re.search(energy_pattern, reference_content, re.IGNORECASE)
    
    if not output_match:
        return False, "Could not extract total energy from output"
    if not reference_match:
        return False, "Could not extract total energy from reference"
    
    try:
        output_energy = float(output_match.group(1))
        reference_energy = float(reference_match.group(1))
        energy_diff = abs(output_energy - reference_energy)
        
        if energy_diff <= tolerance:
            return True, (
                f"Total energy matches: {output_energy:.8f} Ry "
                f"(diff: {energy_diff:.2e}, tolerance: {tolerance:.2e})"
            )
        else:
            return False, (
                f"Total energy mismatch: {output_energy:.8f} vs {reference_energy:.8f} Ry "
                f"(diff: {energy_diff:.2e}, tolerance: {tolerance:.2e})"
            )
    except ValueError as e:
        return False, f"Error parsing energy values: {e}"


def _verify_nscf_fermi_energy(
    output_content: str,
    reference_content: str,
    category: Optional[str] = None,
    tolerance: Optional[float] = None
) -> Tuple[bool, str]:
    """Verify NSCF Fermi energy."""
    if tolerance is None:
        tolerance = get_fermi_energy_tolerance()
    
    # Extract Fermi energy from output (multiple patterns)
    fermi_patterns = [
        r"the\s+Fermi\s+energy\s+is\s+([-\d.]+)\s+ev",
        r"Fermi\s+energy\s*=\s*([-\d.]+)\s+Ry",
        r"the\s+Fermi\s+energy\s+is\s+([-\d.]+)\s+Ry",
    ]
    
    output_fermi = None
    for pattern in fermi_patterns:
        match = re.search(pattern, output_content, re.IGNORECASE)
        if match:
            try:
                output_fermi = float(match.group(1))
                # Convert eV to Ry if needed (1 Ry = 13.6057 eV)
                if "ev" in pattern.lower():
                    output_fermi = output_fermi / 13.6057
                break
            except ValueError:
                continue
    
    reference_fermi = None
    for pattern in fermi_patterns:
        match = re.search(pattern, reference_content, re.IGNORECASE)
        if match:
            try:
                reference_fermi = float(match.group(1))
                if "ev" in pattern.lower():
                    reference_fermi = reference_fermi / 13.6057
                break
            except ValueError:
                continue
    
    if output_fermi is None:
        return False, "Could not extract Fermi energy from output"
    if reference_fermi is None:
        return False, "Could not extract Fermi energy from reference"
    
    fermi_diff = abs(output_fermi - reference_fermi)
    
    if fermi_diff <= tolerance:
        return True, (
            f"Fermi energy matches: {output_fermi:.8f} Ry "
            f"(diff: {fermi_diff:.2e}, tolerance: {tolerance:.2e})"
        )
    else:
        return False, (
            f"Fermi energy mismatch: {output_fermi:.8f} vs {reference_fermi:.8f} Ry "
            f"(diff: {fermi_diff:.2e}, tolerance: {tolerance:.2e})"
        )


def _verify_ph_frequencies(
    output_content: str,
    reference_content: str,
    category: Optional[str] = None,
    tolerance: Optional[float] = None
) -> Tuple[bool, str]:
    """Verify PH frequencies."""
    if tolerance is None:
        tolerance = get_frequency_threshold(category)
    
    output_freqs = extract_ph_frequencies(output_content)
    reference_freqs = extract_ph_frequencies(reference_content)
    
    if output_freqs is None:
        return True, "JOB DONE (frequency extraction failed)"
    
    if reference_freqs is None:
        return True, "JOB DONE (no frequencies found in reference)"
    
    if len(output_freqs) != len(reference_freqs):
        return False, (
            f"Frequency count mismatch: {len(output_freqs)} vs {len(reference_freqs)}"
        )
    
    # Compare frequencies
    max_diff = 0.0
    for out_freq, ref_freq in zip(output_freqs, reference_freqs):
        diff = abs(out_freq - ref_freq)
        if diff > max_diff:
            max_diff = diff
    
    if max_diff <= tolerance:
        return True, (
            f"Frequencies match: max diff {max_diff:.6f} THz "
            f"(tolerance: {tolerance:.6f} THz)"
        )
    else:
        return False, (
            f"Frequency mismatch: max diff {max_diff:.6f} THz "
            f"(tolerance: {tolerance:.6f} THz)"
        )


def verify_step_with_reference(
    step_result: StepResult,
    reference_file: Path,
    category: Optional[str] = None,
    tolerance: Optional[float] = None
) -> None:
    """
    Verify step result and raise AssertionError if verification fails.
    
    This is a convenience function for use in pytest tests.
    
    Args:
        step_result: StepResult from run_step()
        reference_file: Reference output file for comparison
        category: Test category name for threshold selection
        tolerance: Optional custom tolerance
    
    Raises:
        AssertionError: If verification fails
    """
    success, message = verify_step_result(
        step_result, reference_file, category, tolerance
    )
    assert success, f"Step {step_result.step_type_spec} verification failed: {message}"

