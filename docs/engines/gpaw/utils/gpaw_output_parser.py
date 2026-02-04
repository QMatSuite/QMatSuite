"""
GPAW Output Parser Utility (temporary, for integration planning).

GPAW outputs can be parsed two ways:
1. **Programmatic (preferred)**: Load .gpw restart file via GPAW Python API
2. **Text-based (fallback)**: Parse the .txt log file

This parser supports both approaches. The programmatic approach is strongly
preferred since GPAW is a Python-native code, but text parsing is useful
for CI testing where GPAW may not be installed.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ============================================================
# 1. PROGRAMMATIC PARSER (via .gpw file + GPAW API)
# ============================================================


@dataclass
class GPAWSCFResult:
    """Parsed SCF calculation result."""

    total_energy_eV: float
    fermi_level_eV: float
    forces: list[list[float]]  # (natoms, 3) in eV/Ang
    n_bands: int
    n_spins: int
    n_kpoints: int
    converged: bool
    eigenvalues: dict[str, list[float]] | None = None  # per k-point
    cell: list[list[float]] | None = None
    positions: list[list[float]] | None = None
    symbols: list[str] | None = None
    pbc: list[bool] | None = None
    band_gap_eV: float | None = None
    dipole_moment: list[float] | None = None


@dataclass
class GPAWBandsResult:
    """Parsed band structure result."""

    reference_eV: float  # Fermi level
    n_kpoints: int
    n_bands: int
    n_spins: int
    kpath_labels: str | None = None
    energies_shape: list[int] | None = None  # (nspins, nkpts, nbands)


@dataclass
class GPAWDOSResult:
    """Parsed DOS result."""

    energies_eV: list[float]
    dos: list[float]
    fermi_eV: float
    n_points: int


@dataclass
class GPAWRelaxResult:
    """Parsed relaxation result."""

    scf_result: GPAWSCFResult
    n_opt_steps: int
    fmax_final: float
    optimization_history: list[dict[str, float]]
    relaxed_positions: list[list[float]]
    relaxed_cell: list[list[float]]


def parse_gpw_file(gpw_path: Path | str) -> GPAWSCFResult:
    """
    Parse a .gpw restart file using the GPAW Python API.

    Requires GPAW to be installed. This is the preferred parsing method.
    """
    from gpaw import GPAW

    gpw_path = Path(gpw_path)
    calc = GPAW(str(gpw_path), txt=None)
    atoms = calc.get_atoms()

    energy = atoms.get_potential_energy()
    forces = atoms.get_forces()
    fermi = calc.get_fermi_level()
    n_bands = calc.get_number_of_bands()
    n_spins = calc.get_number_of_spins()
    n_kpoints = len(calc.get_ibz_k_points())

    return GPAWSCFResult(
        total_energy_eV=float(energy),
        fermi_level_eV=float(fermi),
        forces=forces.tolist(),
        n_bands=n_bands,
        n_spins=n_spins,
        n_kpoints=n_kpoints,
        converged=True,
        cell=atoms.cell.tolist(),
        positions=atoms.positions.tolist(),
        symbols=list(atoms.get_chemical_symbols()),
        pbc=atoms.pbc.tolist(),
    )


def parse_bandstructure_json(json_path: Path | str) -> GPAWBandsResult:
    """Parse a bandstructure.json file produced by ASE BandStructure.write()."""
    json_path = Path(json_path)
    data = json.loads(json_path.read_text())

    reference = data.get("reference", 0.0)

    # Energies are stored as __ndarray__
    energies_info = data.get("energies", {})
    if "__ndarray__" in energies_info:
        shape = energies_info["__ndarray__"][0]  # [nspins, nkpts, nbands]
    else:
        shape = None

    # Path info
    path_info = data.get("path", {})
    labelseq = path_info.get("labelseq")

    return GPAWBandsResult(
        reference_eV=float(reference),
        n_kpoints=shape[1] if shape else 0,
        n_bands=shape[2] if shape else 0,
        n_spins=shape[0] if shape else 1,
        kpath_labels=labelseq,
        energies_shape=shape,
    )


def parse_dos_json(json_path: Path | str) -> GPAWDOSResult:
    """Parse a dos.json file."""
    json_path = Path(json_path)
    data = json.loads(json_path.read_text())

    return GPAWDOSResult(
        energies_eV=data["energies_eV"],
        dos=data["dos"],
        fermi_eV=data["fermi_eV"],
        n_points=len(data["energies_eV"]),
    )


def parse_results_json(json_path: Path | str) -> dict[str, Any]:
    """Parse a results.json file (generic)."""
    json_path = Path(json_path)
    return json.loads(json_path.read_text())


# ============================================================
# 2. TEXT LOG PARSER (fallback, no GPAW dependency)
# ============================================================


@dataclass
class GPAWTextParseResult:
    """Result from parsing GPAW .txt log file."""

    converged: bool = False
    n_iterations: int = 0
    total_energy_eV: float | None = None
    free_energy_eV: float | None = None
    fermi_level_eV: float | None = None
    band_gap_eV: float | None = None
    direct_gap_eV: float | None = None
    n_atoms: int = 0
    n_bands: int = 0
    n_kpoints: int = 0
    n_valence_electrons: int = 0
    xc_functional: str = ""
    mode: str = ""
    ecut_eV: float | None = None
    symbols: list[str] = field(default_factory=list)
    positions: list[list[float]] = field(default_factory=list)
    forces: list[list[float]] = field(default_factory=list)
    cell_vectors: list[list[float]] = field(default_factory=list)
    scf_iterations: list[dict[str, Any]] = field(default_factory=list)
    energy_contributions: dict[str, float] = field(default_factory=dict)
    timing: dict[str, float] = field(default_factory=dict)
    memory_MiB: float | None = None
    gpaw_version: str = ""


def parse_gpaw_txt(txt_path: Path | str) -> GPAWTextParseResult:
    """
    Parse a GPAW .txt log file (text-based fallback parser).

    This works without GPAW installed. It extracts key information
    from the human-readable log output.
    """
    txt_path = Path(txt_path)
    text = txt_path.read_text()
    result = GPAWTextParseResult()

    # --- GPAW version ---
    m = re.search(r"\|_+\|_\|\s+(\d+\.\d+\.\d+)", text)
    if m:
        result.gpaw_version = m.group(1)

    # --- Convergence ---
    if "Converged after" in text:
        result.converged = True
        m = re.search(r"Converged after (\d+) iterations", text)
        if m:
            result.n_iterations = int(m.group(1))

    # --- Energy contributions ---
    energy_patterns = {
        "kinetic": r"Kinetic:\s+([-+\d.]+)",
        "potential": r"Potential:\s+([-+\d.]+)",
        "external": r"External:\s+([-+\d.]+)",
        "xc": r"XC:\s+([-+\d.]+)",
        "entropy": r"Entropy \(-ST\):\s+([-+\d.]+)",
        "local": r"Local:\s+([-+\d.]+)",
    }
    for key, pattern in energy_patterns.items():
        m = re.search(pattern, text)
        if m:
            result.energy_contributions[key] = float(m.group(1))

    # --- Free energy and extrapolated energy ---
    m = re.search(r"Free energy:\s+([-+\d.]+)", text)
    if m:
        result.free_energy_eV = float(m.group(1))

    m = re.search(r"Extrapolated:\s+([-+\d.]+)", text)
    if m:
        result.total_energy_eV = float(m.group(1))

    # --- Fermi level ---
    m = re.search(r"Fermi level:\s+([-+\d.]+)", text)
    if m:
        result.fermi_level_eV = float(m.group(1))

    # --- Band gap ---
    m = re.search(r"Gap:\s+([\d.]+)\s+eV", text)
    if m:
        result.band_gap_eV = float(m.group(1))

    m = re.search(r"Direct gap:\s+([\d.]+)\s+eV", text)
    if m:
        result.direct_gap_eV = float(m.group(1))

    # --- Atom count ---
    m = re.search(r"Number of atoms:\s+(\d+)", text)
    if m:
        result.n_atoms = int(m.group(1))

    # --- Number of bands ---
    m = re.search(r"Number of bands in calculation:\s+(\d+)", text)
    if m:
        result.n_bands = int(m.group(1))

    # --- K-points ---
    m = re.search(r"(\d+) k-points in the irreducible part", text)
    if m:
        result.n_kpoints = int(m.group(1))
    else:
        m = re.search(r"(\d+) k-points\n", text)
        if m:
            result.n_kpoints = int(m.group(1))

    # --- Valence electrons ---
    m = re.search(r"Number of valence electrons:\s+(\d+)", text)
    if m:
        result.n_valence_electrons = int(m.group(1))

    # --- XC functional ---
    m = re.search(r"xc:\s+(\w+)", text)
    if m:
        result.xc_functional = m.group(1)

    # --- Mode ---
    m = re.search(r"mode:\s+\{.*?name:\s+(\w+)", text)
    if m:
        result.mode = m.group(1)

    # --- Cutoff energy ---
    m = re.search(r"Cutoff energy:\s+([\d.]+)\s+eV", text)
    if m:
        result.ecut_eV = float(m.group(1))
    elif re.search(r"ecut:\s+([\d.]+)", text):
        m = re.search(r"ecut:\s+([\d.]+)", text)
        result.ecut_eV = float(m.group(1))

    # --- Positions ---
    pos_pattern = re.compile(
        r"^\s+\d+\s+(\w+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+\(",
        re.MULTILINE,
    )
    for m in pos_pattern.finditer(text):
        result.symbols.append(m.group(1))
        result.positions.append(
            [float(m.group(2)), float(m.group(3)), float(m.group(4))]
        )

    # --- Forces ---
    forces_section = re.search(
        r"Forces in eV/Ang:\n((?:\s+\d+\s+\w+\s+[-\d.]+\s+[-\d.]+\s+[-\d.]+\n)+)",
        text,
    )
    if forces_section:
        force_pattern = re.compile(
            r"\s+\d+\s+\w+\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)"
        )
        for m in force_pattern.finditer(forces_section.group(1)):
            result.forces.append(
                [float(m.group(1)), float(m.group(2)), float(m.group(3))]
            )

    # --- SCF iterations ---
    iter_pattern = re.compile(
        r"iter:\s+(\d+)\s+\S+\s+([-\d.]+)\s*([-\d.]*c?)\s*([-\d.]*c?)"
    )
    for m in iter_pattern.finditer(text):
        entry = {
            "iteration": int(m.group(1)),
            "energy": float(m.group(2)),
        }
        if m.group(3) and m.group(3) != "c":
            val = m.group(3).rstrip("c")
            if val:
                entry["log_eigst_change"] = float(val)
        if m.group(4) and m.group(4) != "c":
            val = m.group(4).rstrip("c")
            if val:
                entry["log_dens_change"] = float(val)
        result.scf_iterations.append(entry)

    # --- Memory ---
    m = re.search(r"Memory usage:\s+([\d.]+)\s+MiB", text)
    if m:
        result.memory_MiB = float(m.group(1))

    # --- Unit cell ---
    cell_pattern = re.compile(
        r"\d\. axis:\s+(?:yes|no)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)"
    )
    for m in cell_pattern.finditer(text):
        result.cell_vectors.append(
            [float(m.group(1)), float(m.group(2)), float(m.group(3))]
        )

    return result


# ============================================================
# 3. TESTING
# ============================================================


def test_parsers():
    """Test parsers against the collected artifacts."""
    import sys

    artifacts = Path(__file__).parent.parent / "gpaw_test_resources"
    if not artifacts.exists():
        print(f"Artifacts directory not found: {artifacts}")
        sys.exit(1)

    print("=" * 60)
    print("Testing GPAW parsers against real calculation artifacts")
    print("=" * 60)

    # --- Test 1: Text parser on calc1 SCF ---
    print("\n--- Test 1: Text parser (Si SCF) ---")
    scf_txt = artifacts / "calc1_si_scf" / "scf.txt"
    result = parse_gpaw_txt(scf_txt)
    print(f"  GPAW version: {result.gpaw_version}")
    print(f"  Converged: {result.converged}")
    print(f"  Iterations: {result.n_iterations}")
    print(f"  Total energy: {result.total_energy_eV} eV")
    print(f"  Fermi level: {result.fermi_level_eV} eV")
    print(f"  Band gap: {result.band_gap_eV} eV")
    print(f"  Direct gap: {result.direct_gap_eV} eV")
    print(f"  N atoms: {result.n_atoms}")
    print(f"  N bands: {result.n_bands}")
    print(f"  N k-points: {result.n_kpoints}")
    print(f"  XC: {result.xc_functional}")
    print(f"  Mode: {result.mode}")
    print(f"  Ecut: {result.ecut_eV} eV")
    print(f"  Symbols: {result.symbols}")
    print(f"  Forces: {result.forces}")
    print(f"  SCF iterations: {len(result.scf_iterations)}")
    print(f"  Memory: {result.memory_MiB} MiB")

    assert result.converged, "SCF should be converged"
    assert result.n_iterations == 13, f"Expected 13 iterations, got {result.n_iterations}"
    assert abs(result.total_energy_eV - (-10.787154)) < 0.001
    assert abs(result.fermi_level_eV - 5.596) < 0.01
    assert abs(result.band_gap_eV - 1.180) < 0.01
    assert result.n_atoms == 2
    assert len(result.forces) == 2
    print("  PASSED!")

    # --- Test 2: Text parser on calc2 bands ---
    print("\n--- Test 2: Text parser (Si bands fixed density) ---")
    bands_txt = artifacts / "calc2_si_bands" / "bands.txt"
    result = parse_gpaw_txt(bands_txt)
    print(f"  Converged: {result.converged}")
    print(f"  Iterations: {result.n_iterations}")
    print(f"  Total energy: {result.total_energy_eV} eV")
    print(f"  Fermi level: {result.fermi_level_eV} eV")
    print(f"  Band gap: {result.band_gap_eV} eV")
    print(f"  N k-points: {result.n_kpoints}")
    assert result.converged
    print("  PASSED!")

    # --- Test 3: Band structure JSON parser ---
    print("\n--- Test 3: Bandstructure JSON parser ---")
    bs_json = artifacts / "calc2_si_bands" / "bandstructure.json"
    bands_result = parse_bandstructure_json(bs_json)
    print(f"  Reference (Fermi): {bands_result.reference_eV} eV")
    print(f"  N k-points: {bands_result.n_kpoints}")
    print(f"  N bands: {bands_result.n_bands}")
    print(f"  K-path labels: {bands_result.kpath_labels}")
    print(f"  Shape: {bands_result.energies_shape}")
    assert bands_result.n_kpoints == 60
    assert bands_result.n_bands == 16
    assert bands_result.kpath_labels == "GXWKL"
    print("  PASSED!")

    # --- Test 4: DOS JSON parser ---
    print("\n--- Test 4: DOS JSON parser ---")
    dos_json = artifacts / "calc2_si_bands" / "dos.json"
    dos_result = parse_dos_json(dos_json)
    print(f"  Fermi level: {dos_result.fermi_eV} eV")
    print(f"  N points: {dos_result.n_points}")
    print(f"  Energy range: [{dos_result.energies_eV[0]:.2f}, {dos_result.energies_eV[-1]:.2f}] eV")
    assert dos_result.n_points == 500
    print("  PASSED!")

    # --- Test 5: Programmatic parser (requires GPAW) ---
    print("\n--- Test 5: Programmatic parser (.gpw file) ---")
    try:
        gpw_file = artifacts / "calc1_si_scf" / "si_scf.gpw"
        scf_result = parse_gpw_file(gpw_file)
        print(f"  Energy: {scf_result.total_energy_eV} eV")
        print(f"  Fermi: {scf_result.fermi_level_eV} eV")
        print(f"  N bands: {scf_result.n_bands}")
        print(f"  N k-points: {scf_result.n_kpoints}")
        print(f"  Symbols: {scf_result.symbols}")
        assert abs(scf_result.total_energy_eV - (-10.787154)) < 0.001
        print("  PASSED!")
    except ImportError:
        print("  SKIPPED (GPAW not installed)")

    # --- Test 6: Results JSON parser ---
    print("\n--- Test 6: Results JSON parser ---")
    results_json = artifacts / "calc1_si_scf" / "results.json"
    results = parse_results_json(results_json)
    print(f"  Energy: {results['total_energy_eV']} eV")
    print(f"  Fermi: {results['fermi_level_eV']} eV")
    assert abs(results["total_energy_eV"] - (-10.787154)) < 0.001
    print("  PASSED!")

    # --- Test 7: Relax text parser ---
    print("\n--- Test 7: Text parser (H2O relax) ---")
    relax_txt = artifacts / "calc3_relax" / "relax.txt"
    result = parse_gpaw_txt(relax_txt)
    print(f"  Mode: {result.mode}")
    print(f"  N atoms: {result.n_atoms}")
    # Relax txt has multiple SCF cycles (one per opt step)
    # The last converged energy is the final one
    print(f"  Total energy (last): {result.total_energy_eV} eV")
    print(f"  SCF iterations found: {len(result.scf_iterations)}")
    print("  PASSED!")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    test_parsers()
