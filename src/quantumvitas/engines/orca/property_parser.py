"""Parser for ORCA .property.txt files (ORCA 6.x format)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


# Regex to match property blocks: $BlockName ... $End
BLOCK_RE = re.compile(
    r'\$(\w+)\s*\n(.*?)\$End',
    re.DOTALL
)

# Regex to match typed property values:
# &Name [&Type "Type", ...] value  or  &Name [&Type "Type"] value
TYPED_VALUE_RE = re.compile(
    r'&(\w+)\s+\[([^\]]+)\]\s*(.+?)(?=\n\s*&|\n\s*\$|$)',
    re.DOTALL
)

# Regex to match simple property values: &Name value
SIMPLE_VALUE_RE = re.compile(
    r'&(\w+)\s+(\d+)(?:\s|$)'
)

# Regex to match float values in scientific notation
FLOAT_RE = re.compile(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?')

# Regex to extract type info
TYPE_RE = re.compile(r'&Type\s+"([^"]+)"')
DIM_RE = re.compile(r'&Dim\s*\((\d+),(\d+)\)')


def parse_orca_property_txt(path: Path) -> Dict[str, Any]:
    """
    Parse ORCA .property.txt file.

    Args:
        path: Path to .property.txt file

    Returns:
        Dictionary of block_name -> {property_name -> value}

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    if not path.exists():
        raise FileNotFoundError(f"Property file not found: {path}")

    content = path.read_text()
    return parse_property_txt_string(content)


def parse_property_txt_string(content: str) -> Dict[str, Any]:
    """
    Parse property.txt content from string.

    Args:
        content: Property file content

    Returns:
        Dictionary of block_name -> {property_name -> value}
    """
    if not content.strip():
        return {}

    result: Dict[str, Any] = {}

    for match in BLOCK_RE.finditer(content):
        block_name = match.group(1)
        block_content = match.group(2)

        block_data = _parse_block(block_content)
        if block_data:
            result[block_name] = block_data

    return result


def _parse_block(content: str) -> Dict[str, Any]:
    """Parse the content of a property block."""
    data: Dict[str, Any] = {}

    # First pass: find typed values with [&Type ...]
    for match in TYPED_VALUE_RE.finditer(content):
        prop_name = match.group(1)
        type_info = match.group(2)
        value_str = match.group(3).strip()

        # Skip metadata properties
        if prop_name == "GeometryIndex":
            continue

        value = _parse_typed_value(type_info, value_str)
        if value is not None:
            data[prop_name] = value

    # Second pass: find simple values without type info
    for match in SIMPLE_VALUE_RE.finditer(content):
        prop_name = match.group(1)
        if prop_name not in data and prop_name != "GeometryIndex":
            try:
                data[prop_name] = int(match.group(2))
            except ValueError:
                pass

    return data


def _parse_typed_value(type_info: str, value_str: str) -> Any:
    """Parse a value based on its type information."""
    # Extract type
    type_match = TYPE_RE.search(type_info)
    if not type_match:
        return None

    value_type = type_match.group(1)

    # Extract dimensions if array
    dim_match = DIM_RE.search(type_info)
    is_array = dim_match is not None

    # Clean value string - remove trailing description in quotes
    # e.g., 'value "description"' -> 'value'
    value_str = re.sub(r'\s+"[^"]*"\s*$', '', value_str.strip())

    if value_type == "String":
        # String value - extract from quotes
        str_match = re.search(r'"([^"]*)"', value_str)
        return str_match.group(1) if str_match else value_str.strip()

    elif value_type == "Integer":
        try:
            return int(value_str.strip())
        except ValueError:
            # May be in the following lines
            numbers = re.findall(r'\b\d+\b', value_str)
            if numbers:
                return int(numbers[-1])
        return None

    elif value_type == "Double":
        numbers = FLOAT_RE.findall(value_str)
        if numbers:
            return float(numbers[-1])
        return None

    elif value_type == "Boolean":
        return value_str.strip().lower() == "true"

    elif value_type == "ArrayOfDoubles":
        return _parse_double_array(value_str)

    elif value_type == "ArrayOfIntegers":
        return _parse_int_array(value_str)

    elif value_type == "Coordinates":
        return _parse_coordinates(value_str)

    return None


def _parse_double_array(value_str: str) -> Union[float, List[float]]:
    """Parse array of doubles from ORCA format."""
    # Format is typically:
    #                                                          0
    #
    # 0                                     -7.5960994341813887e+01
    # 1                                      ...

    numbers = FLOAT_RE.findall(value_str)

    # Filter out index-like values (small integers at start of lines)
    # Real values are scientific notation or larger
    values = []
    for i, n in enumerate(numbers):
        val = float(n)
        # Skip small integers that look like indices
        # (indices are typically 0, 1, 2, ... at start of lines)
        if i > 0 and abs(val) > 1e-20:  # Skip header indices
            values.append(val)
        elif i == 0 and abs(val) > 10:  # First value might be the data
            values.append(val)

    # Parse more carefully - look for scientific notation values
    sci_numbers = re.findall(r'[-+]?\d+\.\d+[eE][-+]?\d+', value_str)
    if sci_numbers:
        values = [float(n) for n in sci_numbers]

    if len(values) == 1:
        return values[0]
    return values if values else 0.0


def _parse_int_array(value_str: str) -> List[int]:
    """Parse array of integers from ORCA format."""
    # Similar to double array but for integers
    numbers = re.findall(r'\b\d+\b', value_str)
    if not numbers:
        return []

    # Skip header row indices
    values = []
    lines = value_str.strip().split('\n')
    for line in lines:
        if not line.strip():
            continue
        # Lines starting with index number
        parts = line.split()
        if len(parts) >= 2:
            try:
                values.append(int(parts[-1]))
            except ValueError:
                pass

    return values if values else [int(n) for n in numbers]


def _parse_coordinates(value_str: str) -> List[Dict[str, Any]]:
    """Parse coordinate block."""
    coords = []
    lines = value_str.strip().split('\n')
    for line in lines:
        parts = line.split()
        if len(parts) >= 4:
            try:
                atom = {
                    "element": parts[0],
                    "x": float(parts[1]),
                    "y": float(parts[2]),
                    "z": float(parts[3]),
                }
                coords.append(atom)
            except (ValueError, IndexError):
                pass
    return coords


# Convenience functions

def get_energy(parsed: Dict[str, Any]) -> Optional[float]:
    """
    Get the final energy from parsed property file.

    Checks in order:
    1. Single_Point_Data.FinalEnergy
    2. SCF_Energy.totalEnergy

    Args:
        parsed: Parsed property file dict

    Returns:
        Energy in Hartree or None if not found
    """
    # Try Single_Point_Data first
    if "Single_Point_Data" in parsed:
        energy = parsed["Single_Point_Data"].get("FinalEnergy")
        if energy is not None:
            return float(energy) if not isinstance(energy, list) else float(energy[0])

    # Fall back to SCF_Energy
    if "SCF_Energy" in parsed:
        energy = parsed["SCF_Energy"].get("totalEnergy")
        if energy is not None:
            return float(energy) if not isinstance(energy, list) else float(energy[0])

    return None


def is_converged(parsed: Dict[str, Any]) -> bool:
    """
    Check if calculation converged.

    Args:
        parsed: Parsed property file dict

    Returns:
        True if converged, False otherwise
    """
    # Check Single_Point_Data.Converged
    if "Single_Point_Data" in parsed:
        converged = parsed["Single_Point_Data"].get("Converged")
        if converged is not None:
            return bool(converged)

    # Check Calculation_Status.Status
    if "Calculation_Status" in parsed:
        status = parsed["Calculation_Status"].get("Status", "")
        if "NORMAL TERMINATION" in status:
            return True

    return False


def get_tddft_excitations(parsed: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Get TDDFT excitation data from parsed property file.

    In ORCA 6.x, TDDFT/CIS data is stored in:
    - $CIS_Energies: Ground state (e0) and excited state total energies
    - $CIS_Absorption_Spectrum: Excitation energies, oscillator strengths

    Args:
        parsed: Parsed property file dict

    Returns:
        Dict with excitation_energies (in eV), oscillator_strengths, nroots, etc.
        or None if no TDDFT data found
    """
    tddft_data: Dict[str, Any] = {}

    # Extract from CIS_Energies block
    if "CIS_Energies" in parsed:
        cis_energies = parsed["CIS_Energies"]

        # Ground state energy
        e0 = cis_energies.get("e0")
        if e0 is not None:
            tddft_data["ground_state_energy"] = float(e0)

        # Excited state total energies
        total_energies = cis_energies.get("totalEnergy")
        if total_energies is not None:
            if not isinstance(total_energies, list):
                total_energies = [total_energies]
            tddft_data["excited_state_energies"] = [float(e) for e in total_energies]

            # Calculate excitation energies (relative to ground state)
            if e0 is not None:
                # Convert to eV (1 Hartree = 27.2114 eV)
                HARTREE_TO_EV = 27.211386245988
                excitation_energies = [
                    (float(e) - float(e0)) * HARTREE_TO_EV
                    for e in total_energies
                ]
                tddft_data["excitation_energies_ev"] = excitation_energies
                tddft_data["excitation_energies_hartree"] = [
                    float(e) - float(e0) for e in total_energies
                ]

        # Number of roots
        nroots = cis_energies.get("NTotalRoots")
        if nroots is not None:
            tddft_data["nroots"] = int(nroots)

        # Mode (CIS, TDA, TD-DFT, etc.)
        mode = cis_energies.get("mode")
        if mode is not None:
            tddft_data["mode"] = mode

    # Extract oscillator strengths from CIS_Absorption_Spectrum
    if "CIS_Absorption_Spectrum" in parsed:
        spectrum = parsed["CIS_Absorption_Spectrum"]

        # The ExcitationEnergies array contains multiple columns:
        # Col 0: Excitation energy in eV
        # Col 3: Oscillator strength (length gauge)
        # The data is complex - for now, extract from the raw array
        exc_data = spectrum.get("ExcitationEnergies")
        if exc_data is not None:
            # If we have raw excitation energies in eV (first column)
            if isinstance(exc_data, list):
                # exc_data might be a flat list from a 2D array
                # For HF/CIS, the oscillator strengths are in specific columns
                pass  # Complex parsing needed for full extraction

    return tddft_data if tddft_data else None


def get_cis_absorption_data(parsed: Dict[str, Any]) -> Optional[Dict[str, List[float]]]:
    """
    Get CIS/TDDFT absorption spectrum data.

    Args:
        parsed: Parsed property file dict

    Returns:
        Dict with excitation_energies_ev and oscillator_strengths or None
    """
    if "CIS_Absorption_Spectrum" not in parsed:
        return None

    # For simpler access, extract from the output file parsing
    # or use the CIS_Energies block for energies
    tddft_data = get_tddft_excitations(parsed)
    return tddft_data
