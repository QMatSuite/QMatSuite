"""
Unified test thresholds and tolerances for QE testing.

This module centralizes all test thresholds used by both tests/ and extended-tests/.
All thresholds should be defined here and imported from this module.
"""

# ============================================================================
# Energy comparison thresholds (for pw.x and other energy-based tests)
# ============================================================================

# Default energy tolerance for pw.x SCF calculations (in Ry)
DEFAULT_ENERGY_TOLERANCE: float = 3e-6

# Energy tolerance for specific test types
ENERGY_TOLERANCE_PW_SCF: float = 3e-6
ENERGY_TOLERANCE_PW_NSCF: float = 1e-6
ENERGY_TOLERANCE_PW_RELAX: float = 3e-6

# Fermi energy tolerance for NSCF calculations (in Ry)
# NSCF calculations should compare Fermi energy instead of total energy
FERMI_ENERGY_TOLERANCE: float = 0.01  # 0.01 Ry tolerance for Fermi energy

# ============================================================================
# Frequency comparison thresholds (for ph.x and phonon-related tests)
# ============================================================================

# Default frequency threshold for ph.x tests (in THz)
# This threshold tolerates parallel/serial calculation differences
DEFAULT_FREQUENCY_THRESHOLD: float = 0.015

# Frequency thresholds for specific test categories
FREQUENCY_THRESHOLD_PH_1D: float = 0.015  # Tolerates NPROCS=1 vs NPROCS=4 differences
FREQUENCY_THRESHOLD_PH_2D: float = 0.015
FREQUENCY_THRESHOLD_PH_BASE: float = 0.015
FREQUENCY_THRESHOLD_PH_METAL: float = 0.015
FREQUENCY_THRESHOLD_PH_ALL: float = 0.015  # All ph.x tests use this threshold

# ============================================================================
# Helper functions to get thresholds
# ============================================================================

def get_energy_tolerance(category: str = None, executable_name: str = "pw.x") -> float:
    """
    Get energy tolerance for a specific test category or executable.
    
    Args:
        category: Test category name (e.g., "pw_scf", "pw_nscf")
        executable_name: QE executable name (e.g., "pw.x", "cp.x")
    
    Returns:
        Energy tolerance value (in Ry)
    """
    if category:
        category_lower = category.lower()
        if "nscf" in category_lower:
            return ENERGY_TOLERANCE_PW_NSCF
        elif "relax" in category_lower:
            return ENERGY_TOLERANCE_PW_RELAX
        elif "scf" in category_lower:
            return ENERGY_TOLERANCE_PW_SCF
    
    # Default based on executable
    if executable_name == "pw.x":
        return ENERGY_TOLERANCE_PW_SCF
    
    return DEFAULT_ENERGY_TOLERANCE


def get_frequency_threshold(category: str = None) -> float:
    """
    Get frequency threshold for a specific test category.
    
    Args:
        category: Test category name (e.g., "ph_1d", "ph_2d", "ph_base")
    
    Returns:
        Frequency threshold value (in THz)
    """
    if category:
        category_lower = category.lower()
        if category_lower.startswith("ph_1d"):
            return FREQUENCY_THRESHOLD_PH_1D
        elif category_lower.startswith("ph_2d"):
            return FREQUENCY_THRESHOLD_PH_2D
        elif category_lower.startswith("ph_base"):
            return FREQUENCY_THRESHOLD_PH_BASE
        elif category_lower.startswith("ph_metal"):
            return FREQUENCY_THRESHOLD_PH_METAL
        elif category_lower.startswith("ph_"):
            # All other ph categories use the default
            return FREQUENCY_THRESHOLD_PH_ALL
    
    return DEFAULT_FREQUENCY_THRESHOLD


def get_fermi_energy_tolerance() -> float:
    """
    Get Fermi energy tolerance for NSCF calculations.
    
    Returns:
        Fermi energy tolerance value (in Ry)
    """
    return FERMI_ENERGY_TOLERANCE

