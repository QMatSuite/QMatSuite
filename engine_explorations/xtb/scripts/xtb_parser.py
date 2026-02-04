"""xTB output parser utility.

Parses xTB calculation results from:
- stdout/xtb.out (regex-based)
- xtbopt.xyz (optimized geometry with energy)
- charges file (Mulliken charges)
- wbo file (Wiberg bond orders)
- energy file (Turbomole format)
- vibspectrum file (vibrational frequencies)
- .xtboptok / xtbmdok (success markers)

Designed as a standalone exploration utility. When integrating into
QMatSuite, this will be adapted into src/quantumvitas/drivers/xtb/parser.py
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def parse_xtb_stdout(text: str) -> dict[str, Any]:
    """Parse xTB stdout/xtb.out for key results.

    Extracts:
    - total_energy_Eh: Total energy in Hartree
    - gradient_norm: Gradient norm in Eh/a0
    - homo_lumo_gap_eV: HOMO-LUMO gap in eV
    - converged: Whether optimization converged
    - opt_cycles: Number of optimization cycles
    - energy_gain_Eh: Energy gain from optimization
    - normal_termination: Whether run terminated normally
    """
    result: dict[str, Any] = {}

    # Total energy
    m = re.search(
        r"\|\s*TOTAL ENERGY\s+([-\d.]+)\s+Eh\s*\|", text
    )
    if m:
        result["total_energy_Eh"] = float(m.group(1))

    # Gradient norm
    m = re.search(
        r"\|\s*GRADIENT NORM\s+([-\d.]+)\s+Eh/", text
    )
    if m:
        result["gradient_norm"] = float(m.group(1))

    # HOMO-LUMO gap
    m = re.search(
        r"\|\s*HOMO-LUMO GAP\s+([-\d.]+)\s+eV\s*\|", text
    )
    if m:
        result["homo_lumo_gap_eV"] = float(m.group(1))

    # Optimization convergence
    m = re.search(
        r"GEOMETRY OPTIMIZATION CONVERGED AFTER\s+(\d+)\s+ITERATIONS", text
    )
    if m:
        result["converged"] = True
        result["opt_cycles"] = int(m.group(1))
    elif "FAILED TO CONVERGE" in text.upper():
        result["converged"] = False

    # Energy gain
    m = re.search(
        r"total energy gain\s*:\s+([-\d.]+)\s+Eh\s+([-\d.]+)\s+kcal/mol", text
    )
    if m:
        result["energy_gain_Eh"] = float(m.group(1))
        result["energy_gain_kcal_mol"] = float(m.group(2))

    # Normal termination
    result["normal_termination"] = "normal termination of xtb" in text

    # Thermodynamic data (from --ohess)
    m = re.search(
        r"total free energy\s+([-\d.]+)\s+Eh", text
    )
    if m:
        result["free_energy_Eh"] = float(m.group(1))

    m = re.search(
        r"zero point energy\s+([-\d.]+)\s+Eh", text
    )
    if m:
        result["zpe_Eh"] = float(m.group(1))

    return result


def parse_xtbopt_xyz(path: Path) -> dict[str, Any]:
    """Parse xtbopt.xyz for optimized geometry.

    Returns dict with:
    - energy_Eh: Energy from comment line
    - gnorm: Gradient norm from comment line
    - atoms: list of {"element": str, "x": float, "y": float, "z": float}
    - n_atoms: number of atoms
    """
    text = path.read_text().strip()
    lines = text.split("\n")

    result: dict[str, Any] = {}

    if len(lines) < 3:
        raise ValueError(f"xtbopt.xyz too short ({len(lines)} lines)")

    n_atoms = int(lines[0].strip())
    result["n_atoms"] = n_atoms

    # Parse comment line for energy and gnorm
    comment = lines[1]
    m = re.search(r"energy:\s+([-\d.]+)", comment)
    if m:
        result["energy_Eh"] = float(m.group(1))

    m = re.search(r"gnorm:\s+([-\d.]+)", comment)
    if m:
        result["gnorm"] = float(m.group(1))

    # Parse atomic coordinates
    atoms = []
    for i in range(2, 2 + n_atoms):
        parts = lines[i].split()
        if len(parts) >= 4:
            atoms.append({
                "element": parts[0],
                "x": float(parts[1]),
                "y": float(parts[2]),
                "z": float(parts[3]),
            })
    result["atoms"] = atoms

    return result


def parse_charges(path: Path) -> list[float]:
    """Parse charges file (one charge per line)."""
    text = path.read_text().strip()
    return [float(line.strip()) for line in text.split("\n") if line.strip()]


def parse_wbo(path: Path) -> list[dict[str, Any]]:
    """Parse wbo file (atom_i, atom_j, bond_order per line)."""
    text = path.read_text().strip()
    bonds = []
    for line in text.split("\n"):
        parts = line.split()
        if len(parts) >= 3:
            bonds.append({
                "atom_i": int(parts[0]),
                "atom_j": int(parts[1]),
                "bond_order": float(parts[2]),
            })
    return bonds


def parse_energy_file(path: Path) -> float | None:
    """Parse energy file (Turbomole format).

    Returns total energy in Hartree.
    """
    text = path.read_text()
    m = re.search(r"^\s+\d+\s+([-\d.]+)", text, re.MULTILINE)
    if m:
        return float(m.group(1))
    return None


def parse_vibspectrum(path: Path) -> list[dict[str, Any]]:
    """Parse vibspectrum file for vibrational frequencies.

    Returns list of dicts with:
    - mode: int
    - frequency_cm1: float
    - ir_intensity: float
    - ir_active: bool
    """
    text = path.read_text()
    modes = []
    for line in text.split("\n"):
        if line.startswith("$") or line.startswith("#") or not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 4:
            try:
                mode_num = int(parts[0])
                # Check if symmetry label is present
                if parts[1].replace(".", "").replace("-", "").isdigit():
                    freq = float(parts[1])
                    ir_int = float(parts[2])
                    ir_active = parts[3] == "YES"
                else:
                    freq = float(parts[2])
                    ir_int = float(parts[3])
                    ir_active = parts[4] == "YES" if len(parts) > 4 else False
                modes.append({
                    "mode": mode_num,
                    "frequency_cm1": freq,
                    "ir_intensity": ir_int,
                    "ir_active": ir_active,
                })
            except (ValueError, IndexError):
                continue
    return modes


def check_success(working_dir: Path, calc_type: str = "opt") -> bool:
    """Check if xTB calculation succeeded.

    For optimization: checks .xtboptok marker file
    For MD: checks xtbmdok marker file
    For single-point: checks exit code (not available here, check stdout)
    """
    if calc_type == "opt":
        return (working_dir / ".xtboptok").exists()
    elif calc_type == "md":
        return (working_dir / "xtbmdok").exists()
    else:
        return True  # Single-point success determined by exit code


def parse_full_results(
    working_dir: Path,
    calc_type: str = "opt",
    stdout_file: str = "xtb.out",
) -> dict[str, Any]:
    """Parse all available xTB outputs from a working directory.

    Args:
        working_dir: Directory containing xTB output files
        calc_type: "sp" (single-point), "opt" (optimization), "md" (dynamics),
                   "freq" (frequencies), "grad" (gradient)
        stdout_file: Name of the stdout capture file

    Returns:
        Dict with all parsed results
    """
    result: dict[str, Any] = {"calc_type": calc_type}

    # Parse stdout if available
    stdout_path = working_dir / stdout_file
    if stdout_path.exists():
        result["stdout"] = parse_xtb_stdout(stdout_path.read_text())

    # Parse optimized geometry
    xtbopt = working_dir / "xtbopt.xyz"
    if xtbopt.exists():
        result["optimized_geometry"] = parse_xtbopt_xyz(xtbopt)

    # Parse charges
    charges_path = working_dir / "charges"
    if charges_path.exists():
        result["charges"] = parse_charges(charges_path)

    # Parse bond orders
    wbo_path = working_dir / "wbo"
    if wbo_path.exists():
        result["bond_orders"] = parse_wbo(wbo_path)

    # Parse energy file
    energy_path = working_dir / "energy"
    if energy_path.exists():
        result["energy_Eh"] = parse_energy_file(energy_path)

    # Parse vibspectrum
    vib_path = working_dir / "vibspectrum"
    if vib_path.exists():
        result["vibrational_modes"] = parse_vibspectrum(vib_path)

    # Check success marker
    result["success"] = check_success(working_dir, calc_type)

    return result


# ===========================================================================
# Standalone test: run against golden artifacts
# ===========================================================================
if __name__ == "__main__":
    import json
    import sys

    artifacts_dir = Path(__file__).parent.parent / "artifacts"
    if not artifacts_dir.exists():
        print(f"Artifacts directory not found: {artifacts_dir}")
        sys.exit(1)

    print("=" * 60)
    print("xTB Parser Test Against Golden Artifacts")
    print("=" * 60)

    # Test 1: Single-point water
    print("\n--- Test 1: Single-Point Water ---")
    sp_dir = artifacts_dir / "singlepoint_water"
    charges = parse_charges(sp_dir / "charges")
    bonds = parse_wbo(sp_dir / "wbo")
    print(f"  Charges: {charges}")
    print(f"  Bond orders ({len(bonds)} bonds): {bonds}")
    assert len(charges) == 3, f"Expected 3 charges, got {len(charges)}"
    assert abs(sum(charges)) < 0.01, f"Charges don't sum to ~0: {sum(charges)}"
    print("  PASS")

    # Test 2: Optimized water
    print("\n--- Test 2: Optimized Water ---")
    opt_dir = artifacts_dir / "opt_water"
    stdout_result = parse_xtb_stdout((opt_dir / "xtb.out").read_text())
    geo = parse_xtbopt_xyz(opt_dir / "xtbopt.xyz")
    print(f"  Total energy: {stdout_result.get('total_energy_Eh', 'N/A')} Eh")
    print(f"  Converged: {stdout_result.get('converged', 'N/A')}")
    print(f"  Opt cycles: {stdout_result.get('opt_cycles', 'N/A')}")
    print(f"  Optimized geo energy: {geo.get('energy_Eh', 'N/A')} Eh")
    print(f"  N atoms: {geo.get('n_atoms', 'N/A')}")
    print(f"  Normal termination: {stdout_result.get('normal_termination', 'N/A')}")
    assert stdout_result["converged"] is True
    assert stdout_result["opt_cycles"] == 4
    assert geo["n_atoms"] == 3
    assert abs(geo["energy_Eh"] - (-5.070544)) < 0.001
    print("  PASS")

    # Test 3: Optimized ethanol
    print("\n--- Test 3: Optimized Ethanol ---")
    eth_dir = artifacts_dir / "opt_ethanol"
    geo = parse_xtbopt_xyz(eth_dir / "xtbopt.xyz")
    charges = parse_charges(eth_dir / "charges")
    print(f"  Energy: {geo['energy_Eh']} Eh")
    print(f"  N atoms: {geo['n_atoms']}")
    print(f"  Charges: {charges}")
    assert geo["n_atoms"] == 9
    assert abs(geo["energy_Eh"] - (-11.394339)) < 0.001
    assert len(charges) == 9
    print("  PASS")

    # Test 4: Frequency water
    print("\n--- Test 4: Frequency Water ---")
    freq_dir = artifacts_dir / "freq_water"
    modes = parse_vibspectrum(freq_dir / "vibspectrum")
    active_modes = [m for m in modes if m["ir_active"]]
    print(f"  Total modes: {len(modes)}")
    print(f"  Active modes: {len(active_modes)}")
    for m in active_modes:
        print(f"    Mode {m['mode']}: {m['frequency_cm1']:.1f} cm-1, IR={m['ir_intensity']:.3f}")
    assert len(active_modes) == 3
    assert abs(active_modes[0]["frequency_cm1"] - 1539.08) < 1.0
    print("  PASS")

    # Test 5: Gradient caffeine
    print("\n--- Test 5: Gradient Caffeine ---")
    grad_dir = artifacts_dir / "grad_caffeine"
    energy = parse_energy_file(grad_dir / "energy")
    print(f"  Energy: {energy} Eh")
    assert energy is not None
    assert abs(energy - (-41.82150596)) < 0.001
    print("  PASS")

    print("\n" + "=" * 60)
    print("ALL PARSER TESTS PASSED")
    print("=" * 60)
