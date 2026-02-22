"""
ABINIT Output File Parser

This module provides utilities for parsing ABINIT output files (.abo).

ABINIT output structure:
1. Header with version, date, file info
2. Echoed input variables section
3. Per-dataset results:
   - SCF iteration log (ETOT lines)
   - ResultsGS YAML block with total energy, forces, stress
   - EnergyTerms YAML block with energy components
4. Final echoed variables (post-computation)
5. Timing summary

Key data to extract:
- Total energy (etotal)
- Forces (cartesian_forces)
- Stress tensor (cartesian_stress_tensor, pressure_GPa)
- Eigenvalues (from EIG file or output)
- Final structure (acell, rprim, xred)
- SCF convergence (ETOT iterations)

Reference: https://docs.abinit.org/guide/abinit/
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SCFIteration:
    """Single SCF iteration data."""

    iteration: int
    energy: float  # Ha
    delta_e: float  # Energy change
    residual: float  # Wavefunction residual
    potential_residual: float  # vres2


@dataclass
class AbinitForces:
    """Atomic forces."""

    cartesian: List[List[float]]  # Ha/Bohr
    max_force: float
    rms_force: float


@dataclass
class AbinitStress:
    """Stress tensor."""

    cartesian: List[List[float]]  # Ha/Bohr^3
    pressure_gpa: float


@dataclass
class AbinitStructure:
    """Final structure from output."""

    acell: Tuple[float, float, float]  # Bohr
    rprim: List[List[float]]  # 3x3
    xred: List[List[float]]
    xcart: Optional[List[List[float]]] = None
    volume: Optional[float] = None


@dataclass
class EnergyComponents:
    """Energy breakdown."""

    kinetic: float
    hartree: float
    xc: float
    ewald: float
    psp_core: float
    local_psp: float
    nonlocal_psp: float
    total: float
    total_eV: float


@dataclass
class DatasetResult:
    """Results for one dataset."""

    dataset_index: int
    total_energy: float  # Ha
    total_energy_eV: float
    fermi_energy: Optional[float] = None
    scf_iterations: List[SCFIteration] = field(default_factory=list)
    forces: Optional[AbinitForces] = None
    stress: Optional[AbinitStress] = None
    final_structure: Optional[AbinitStructure] = None
    energy_components: Optional[EnergyComponents] = None
    converged: bool = True
    n_iterations: int = 0


@dataclass
class AbinitOutput:
    """Complete parsed ABINIT output."""

    version: str
    calculation_type: str  # scf, relax, nscf, etc.
    n_datasets: int
    datasets: Dict[int, DatasetResult]
    wall_time: float
    cpu_time: float
    warnings: int
    comments: int


def parse_scf_iterations(text: str) -> List[SCFIteration]:
    """
    Parse SCF iteration lines (ETOT lines).

    Format: ETOT  N  energy  delta_e  residual  vres2
    Example: ETOT  1  -8.8606750188494  -8.861E+00 1.762E-02 1.041E+01
    """
    iterations = []
    pattern = r"ETOT\s+(\d+)\s+([-\d.E+]+)\s+([-\d.E+]+)\s+([-\d.E+]+)\s+([-\d.E+]+)"

    for match in re.finditer(pattern, text):
        iterations.append(
            SCFIteration(
                iteration=int(match.group(1)),
                energy=float(match.group(2)),
                delta_e=float(match.group(3)),
                residual=float(match.group(4)),
                potential_residual=float(match.group(5)),
            )
        )

    return iterations


def parse_results_gs_block(text: str) -> Optional[Dict[str, Any]]:
    """
    Parse the --- !ResultsGS YAML block.

    Returns dict with: etotal, fermie, pressure_GPa, cartesian_forces, etc.
    """
    # Find the ResultsGS block
    pattern = r"--- !ResultsGS\n(.*?)^\.\.\."
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    if not match:
        return None

    block = match.group(1)
    result = {}

    # Extract etotal
    etotal_match = re.search(r"etotal\s*:\s*([-\d.E+]+)", block)
    if etotal_match:
        result["etotal"] = float(etotal_match.group(1))

    # Extract fermie
    fermie_match = re.search(r"fermie\s*:\s*([-\d.E+]+)", block)
    if fermie_match:
        result["fermie"] = float(fermie_match.group(1))

    # Extract pressure
    pressure_match = re.search(r"pressure_GPa\s*:\s*([-\d.E+]+)", block)
    if pressure_match:
        result["pressure_GPa"] = float(pressure_match.group(1))

    # Extract convergence info
    convergence_match = re.search(r"convergence:\s*\{([^}]+)\}", block)
    if convergence_match:
        conv_str = convergence_match.group(1)
        deltae_match = re.search(r"deltae:\s*([-\d.E+]+)", conv_str)
        if deltae_match:
            result["deltae"] = float(deltae_match.group(1))

    # Extract cartesian forces
    # Format: - [ 1.234E-05, 2.345E-05, 3.456E-05, ]
    forces_match = re.search(
        r"cartesian_forces:.*?\n((?:\s*-\s*\[.*?\]\n)+)", block, re.DOTALL
    )
    if forces_match:
        forces_block = forces_match.group(1)
        forces = []
        for line in forces_block.strip().split("\n"):
            # Parse scientific notation numbers only (not the leading -)
            nums = re.findall(r"[-+]?\d+\.?\d*[Ee]?[-+]?\d*", line)
            valid_nums = [float(n) for n in nums if n and n not in ("-", "+")]
            if len(valid_nums) >= 3:
                forces.append(valid_nums[:3])
        result["cartesian_forces"] = forces

    # Extract stress tensor
    stress_match = re.search(
        r"cartesian_stress_tensor:.*?\n((?:\s*-\s*\[.*?\]\n)+)", block, re.DOTALL
    )
    if stress_match:
        stress_block = stress_match.group(1)
        stress = []
        for line in stress_block.strip().split("\n"):
            nums = re.findall(r"[-+]?\d+\.?\d*[Ee]?[-+]?\d*", line)
            valid_nums = [float(n) for n in nums if n and n not in ("-", "+")]
            if len(valid_nums) >= 3:
                stress.append(valid_nums[:3])
        result["cartesian_stress_tensor"] = stress

    return result


def parse_energy_terms_block(text: str) -> Optional[EnergyComponents]:
    """
    Parse the --- !EnergyTerms YAML block.
    """
    pattern = r"--- !EnergyTerms\n(.*?)^\.\.\."
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    if not match:
        return None

    block = match.group(1)

    def extract_value(name: str) -> float:
        m = re.search(rf"{name}\s*:\s*([-\d.E+]+)", block)
        return float(m.group(1)) if m else 0.0

    return EnergyComponents(
        kinetic=extract_value("kinetic"),
        hartree=extract_value("hartree"),
        xc=extract_value("xc"),
        ewald=extract_value("Ewald energy"),
        psp_core=extract_value("psp_core"),
        local_psp=extract_value("local_psp"),
        nonlocal_psp=extract_value("non_local_psp"),
        total=extract_value("total_energy"),
        total_eV=extract_value("total_energy_eV"),
    )


def parse_final_etotal(text: str) -> Optional[float]:
    """
    Parse the final etotal from the echoed output variables.

    Looks for: etotal  -8.8664649025E+00
    """
    # Final etotal appears after "echo values of variables after computation"
    pattern = r"-outvars: echo values of variables after computation.*?etotal\s+([-\d.E+]+)"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return float(match.group(1))

    # Fallback: look for last etotal line
    pattern = r"^\s+etotal\s+([-\d.E+]+)"
    matches = list(re.finditer(pattern, text, re.MULTILINE))
    if matches:
        return float(matches[-1].group(1))

    return None


def parse_final_structure(text: str) -> Optional[AbinitStructure]:
    """
    Parse the final structure from echoed output variables.
    """
    # Find the post-computation section
    pattern = r"-outvars: echo values of variables after computation(.*)"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return None

    block = match.group(1)

    # Parse acell
    acell_match = re.search(
        r"acell\s+([-\d.E+]+)\s+([-\d.E+]+)\s+([-\d.E+]+)", block
    )
    if not acell_match:
        return None

    acell = (
        float(acell_match.group(1)),
        float(acell_match.group(2)),
        float(acell_match.group(3)),
    )

    # Parse rprim
    rprim_match = re.search(
        r"rprim\s+([-\d.E+]+)\s+([-\d.E+]+)\s+([-\d.E+]+)\s+"
        r"([-\d.E+]+)\s+([-\d.E+]+)\s+([-\d.E+]+)\s+"
        r"([-\d.E+]+)\s+([-\d.E+]+)\s+([-\d.E+]+)",
        block,
    )
    if not rprim_match:
        return None

    rprim = [
        [float(rprim_match.group(i)) for i in range(1, 4)],
        [float(rprim_match.group(i)) for i in range(4, 7)],
        [float(rprim_match.group(i)) for i in range(7, 10)],
    ]

    # Parse xred
    xred = []
    xred_pattern = r"xred\s+((?:[-\d.E+]+\s+[-\d.E+]+\s+[-\d.E+]+\s*)+)"
    xred_match = re.search(xred_pattern, block)
    if xred_match:
        xred_text = xred_match.group(1)
        nums = re.findall(r"[-\d.E+]+", xred_text)
        for i in range(0, len(nums), 3):
            if i + 2 < len(nums):
                xred.append([float(nums[i]), float(nums[i + 1]), float(nums[i + 2])])

    return AbinitStructure(acell=acell, rprim=rprim, xred=xred)


def parse_timing(text: str) -> Tuple[float, float]:
    """
    Parse CPU and wall time.

    Looks for: +Overall time at end (sec) : cpu=  0.3  wall=  0.3
    """
    pattern = r"\+Overall time at end \(sec\)\s*:\s*cpu=\s*([\d.]+)\s+wall=\s*([\d.]+)"
    match = re.search(pattern, text)
    if match:
        return float(match.group(1)), float(match.group(2))
    return 0.0, 0.0


def parse_warnings_comments(text: str) -> Tuple[int, int]:
    """
    Parse warning and comment counts.

    Looks for: .Delivered  N WARNINGs and  M COMMENTs to log file.
    """
    pattern = r"\.Delivered\s+(\d+)\s+WARNINGs?\s+and\s+(\d+)\s+COMMENTs?"
    match = re.search(pattern, text)
    if match:
        return int(match.group(1)), int(match.group(2))
    return 0, 0


def parse_version(text: str) -> str:
    """Parse ABINIT version."""
    pattern = r"\.Version\s+([\d.]+[^\s]*)\s+of ABINIT"
    match = re.search(pattern, text)
    return match.group(1) if match else "unknown"


def detect_calculation_type(text: str) -> str:
    """
    Detect calculation type from input echo.

    Based on ionmov, optdriver, iscf values.
    """
    # Check ionmov for relaxation/MD
    ionmov_match = re.search(r"ionmov\s+(\d+)", text)
    if ionmov_match:
        ionmov = int(ionmov_match.group(1))
        if ionmov in (2, 3, 4, 5, 7, 10, 11, 20, 22):
            optcell_match = re.search(r"optcell\s+(\d+)", text)
            optcell = int(optcell_match.group(1)) if optcell_match else 0
            if optcell > 0:
                return "vc_relax"  # Variable-cell relaxation
            return "relax"
        elif ionmov in (1, 6, 8, 9, 12, 13, 14, 23):
            return "md"

    # Check iscf for NSCF
    iscf_match = re.search(r"iscf\s+(-?\d+)", text)
    if iscf_match and int(iscf_match.group(1)) < 0:
        return "nscf"

    # Check optdriver for response/GW
    optdriver_match = re.search(r"optdriver\s+(\d+)", text)
    if optdriver_match:
        optdriver = int(optdriver_match.group(1))
        if optdriver == 1:
            return "dfpt"
        elif optdriver == 3:
            return "screening"
        elif optdriver == 4:
            return "sigma"
        elif optdriver == 7:
            return "eph"

    return "scf"


def parse_abinit_output(filepath: Path) -> AbinitOutput:
    """
    Parse a complete ABINIT output file.

    Args:
        filepath: Path to .abo file

    Returns:
        AbinitOutput with all extracted data
    """
    text = filepath.read_text()

    version = parse_version(text)
    calc_type = detect_calculation_type(text)
    cpu_time, wall_time = parse_timing(text)
    warnings, comments = parse_warnings_comments(text)

    # Count datasets
    ndtset_match = re.search(r"ndtset\s+(\d+)", text)
    n_datasets = int(ndtset_match.group(1)) if ndtset_match else 1

    datasets = {}

    if n_datasets == 1:
        # Single dataset
        scf_iters = parse_scf_iterations(text)
        results_gs = parse_results_gs_block(text)
        energy_terms = parse_energy_terms_block(text)
        final_structure = parse_final_structure(text)
        final_energy = parse_final_etotal(text)

        forces = None
        stress = None
        if results_gs:
            if "cartesian_forces" in results_gs:
                cart_forces = results_gs["cartesian_forces"]
                max_f = max(
                    (sum(f**2 for f in atom) ** 0.5 for atom in cart_forces), default=0.0
                )
                rms_f = (
                    sum(sum(f**2 for f in atom) for atom in cart_forces) / len(cart_forces)
                ) ** 0.5 if cart_forces else 0.0
                forces = AbinitForces(
                    cartesian=cart_forces, max_force=max_f, rms_force=rms_f
                )
            if "cartesian_stress_tensor" in results_gs:
                stress = AbinitStress(
                    cartesian=results_gs["cartesian_stress_tensor"],
                    pressure_gpa=results_gs.get("pressure_GPa", 0.0),
                )

        datasets[1] = DatasetResult(
            dataset_index=1,
            total_energy=final_energy or (results_gs.get("etotal") if results_gs else 0.0),
            total_energy_eV=energy_terms.total_eV if energy_terms else 0.0,
            fermi_energy=results_gs.get("fermie") if results_gs else None,
            scf_iterations=scf_iters,
            forces=forces,
            stress=stress,
            final_structure=final_structure,
            energy_components=energy_terms,
            converged=True,
            n_iterations=len(scf_iters),
        )
    else:
        # Multi-dataset - parse each
        for ds in range(1, n_datasets + 1):
            # Find dataset section
            ds_pattern = rf"== DATASET\s+{ds}\s+=="
            ds_match = re.search(ds_pattern, text)
            if ds_match:
                # Find end of this dataset
                next_ds_pattern = rf"== DATASET\s+{ds + 1}\s+=="
                next_match = re.search(next_ds_pattern, text)
                end_pos = next_match.start() if next_match else len(text)

                ds_text = text[ds_match.start() : end_pos]

                scf_iters = parse_scf_iterations(ds_text)
                results_gs = parse_results_gs_block(ds_text)
                energy_terms = parse_energy_terms_block(ds_text)

                etotal = results_gs.get("etotal", 0.0) if results_gs else 0.0

                datasets[ds] = DatasetResult(
                    dataset_index=ds,
                    total_energy=etotal,
                    total_energy_eV=energy_terms.total_eV if energy_terms else 0.0,
                    fermi_energy=results_gs.get("fermie") if results_gs else None,
                    scf_iterations=scf_iters,
                    energy_components=energy_terms,
                    converged=True,
                    n_iterations=len(scf_iters),
                )

    return AbinitOutput(
        version=version,
        calculation_type=calc_type,
        n_datasets=n_datasets,
        datasets=datasets,
        wall_time=wall_time,
        cpu_time=cpu_time,
        warnings=warnings,
        comments=comments,
    )


def parse_eig_file(filepath: Path) -> Dict[int, List[List[float]]]:
    """
    Parse ABINIT eigenvalue file (_EIG).

    Returns: {kpt_index: [eigenvalues]} where eigenvalues are in Ha.
    """
    text = filepath.read_text()
    result = {}

    # Pattern: kpt# N, nband= M, wtk= W, kpt= x y z (reduced coord)
    #          eigenvalue1 eigenvalue2 ...
    kpt_pattern = r"kpt#\s+(\d+),\s+nband=\s+(\d+).*?\n((?:\s+[-\d.E+]+)+)"

    for match in re.finditer(kpt_pattern, text):
        kpt_idx = int(match.group(1))
        eigenvalues_text = match.group(3)
        eigenvalues = [float(x) for x in eigenvalues_text.split()]
        result[kpt_idx] = eigenvalues

    return result


if __name__ == "__main__":
    # Test with golden reference
    import sys

    if len(sys.argv) > 1:
        filepath = Path(sys.argv[1])
    else:
        filepath = Path(__file__).parent / "golden_refs" / "si_scf.abo"

    if filepath.exists():
        output = parse_abinit_output(filepath)
        print(f"ABINIT version: {output.version}")
        print(f"Calculation type: {output.calculation_type}")
        print(f"Number of datasets: {output.n_datasets}")
        print(f"Wall time: {output.wall_time:.2f} s")
        print(f"Warnings: {output.warnings}, Comments: {output.comments}")

        for ds_idx, ds in output.datasets.items():
            print(f"\n--- Dataset {ds_idx} ---")
            print(f"Total energy: {ds.total_energy:.10f} Ha")
            print(f"Total energy: {ds.total_energy_eV:.6f} eV")
            if ds.fermi_energy:
                print(f"Fermi energy: {ds.fermi_energy:.6f} Ha")
            print(f"SCF iterations: {ds.n_iterations}")
            if ds.forces:
                print(f"Max force: {ds.forces.max_force:.6e} Ha/Bohr")
            if ds.stress:
                print(f"Pressure: {ds.stress.pressure_gpa:.4f} GPa")
    else:
        print(f"File not found: {filepath}")
