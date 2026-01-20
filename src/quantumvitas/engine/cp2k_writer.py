"""CP2K input file writer."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

from pymatgen.core import Structure

if TYPE_CHECKING:
    from quantumvitas.calculation.structure_steps import StructureStepSpec

logger = logging.getLogger(__name__)


def write_cp2k_input(
    step: "StructureStepSpec",
    structure: Structure,
    output_path: Path,
) -> None:
    """
    Write CP2K input file from step specification and structure.

    Args:
        step: Step specification with parameters
        structure: Pymatgen Structure object
        output_path: Path to write input.inp
    """
    step_type = getattr(step, "step_type", None) or ""
    params = getattr(step, "parameters", None) or {}

    with open(output_path, "w") as f:
        # GLOBAL section (needs params to check for cell optimization)
        _write_global_section(f, step_type, params)

        # MOTION section (for relax/md)
        if step_type in ("cp2k_relax", "cp2k_md"):
            _write_motion_section(f, step_type, params)

        # FORCE_EVAL section
        _write_force_eval_section(f, params, structure, step_type)

    logger.debug(f"Generated CP2K input file: {output_path}")


def _write_global_section(f, step_type: str, params: Dict[str, Any]) -> None:
    """Write &GLOBAL section."""
    f.write("&GLOBAL\n")
    f.write("  PROJECT cp2k_calc\n")

    # RUN_TYPE based on step_type
    if step_type == "cp2k_scf":
        run_type = "ENERGY_FORCE"
    elif step_type == "cp2k_relax":
        # Check if cell optimization is requested
        optimize_cell = params.get("optimize_cell", False)
        run_type = "CELL_OPT" if optimize_cell else "GEO_OPT"
    elif step_type == "cp2k_md":
        run_type = "MD"
    else:
        run_type = "ENERGY_FORCE"  # Default

    f.write(f"  RUN_TYPE {run_type}\n")
    f.write("  PRINT_LEVEL MEDIUM\n")
    f.write("&END GLOBAL\n")
    f.write("\n")


def _write_force_eval_section(
    f,
    params: Dict[str, Any],
    structure: Structure,
    step_type: str,
) -> None:
    """Write &FORCE_EVAL section."""
    f.write("&FORCE_EVAL\n")
    f.write("  METHOD Quickstep\n")

    # DFT subsection
    _write_dft_section(f, params)

    # SUBSYS subsection (structure)
    _write_subsys_section(f, params, structure)

    # PRINT subsection (forces, etc.)
    _write_force_eval_print_section(f, params)

    f.write("&END FORCE_EVAL\n")
    f.write("\n")


def _write_dft_section(f, params: Dict[str, Any]) -> None:
    """Write &DFT subsection."""
    f.write("  &DFT\n")

    # Basis set and potential files
    basis_file = params.get("basis_set_file_name", "BASIS_MOLOPT")
    potential_file = params.get("potential_file_name", "GTH_POTENTIALS")
    f.write(f"    BASIS_SET_FILE_NAME {basis_file}\n")
    f.write(f"    POTENTIAL_FILE_NAME {potential_file}\n")

    # MGRID
    f.write("    &MGRID\n")
    cutoff = params.get("cutoff", 400)
    rel_cutoff = params.get("rel_cutoff", 60)
    f.write(f"      CUTOFF {cutoff}\n")
    f.write(f"      REL_CUTOFF {rel_cutoff}\n")
    f.write("    &END MGRID\n")

    # QS (Quickstep settings)
    f.write("    &QS\n")
    eps_default = params.get("eps_default", 1.0e-10)
    f.write(f"      EPS_DEFAULT {eps_default}\n")
    f.write("    &END QS\n")

    # SCF
    _write_scf_section(f, params)

    # XC functional
    _write_xc_section(f, params)

    f.write("  &END DFT\n")


def _write_scf_section(f, params: Dict[str, Any]) -> None:
    """Write &SCF subsection."""
    f.write("    &SCF\n")
    eps_scf = params.get("eps_scf", 1.0e-6)
    max_scf = params.get("max_scf", 50)
    f.write(f"      EPS_SCF {eps_scf}\n")
    f.write(f"      MAX_SCF {max_scf}\n")

    # Diagonalization
    f.write("      &DIAGONALIZATION\n")
    algorithm = params.get("diagonalization", {}).get("algorithm", "STANDARD")
    f.write(f"        ALGORITHM {algorithm}\n")
    f.write("      &END DIAGONALIZATION\n")

    # Mixing
    f.write("      &MIXING\n")
    mixing_method = params.get("mixing", {}).get("method", "BROYDEN_MIXING")
    mixing_alpha = params.get("mixing", {}).get("alpha", 0.4)
    f.write(f"        METHOD {mixing_method}\n")
    f.write(f"        ALPHA {mixing_alpha}\n")
    f.write("      &END MIXING\n")

    # Smearing (if specified)
    smearing = params.get("smearing", {})
    if smearing:
        f.write("      &SMEAR ON\n")
        method = smearing.get("method", "FERMI_DIRAC")
        electronic_temp = smearing.get("electronic_temperature", 300)
        f.write(f"        METHOD {method}\n")
        f.write(f"        ELECTRONIC_TEMPERATURE [K] {electronic_temp}\n")
        added_mos = smearing.get("added_mos", 0)
        if added_mos > 0:
            f.write(f"        ADDED_MOS {added_mos}\n")
        f.write("      &END SMEAR\n")

    # SCF_GUESS (restart handling) - must be inside &SCF section
    restart_policy = params.get("restart_policy", {})
    if restart_policy.get("use_wfn_guess"):
        f.write("      SCF_GUESS RESTART\n")
        # WFN_RESTART_FILE_NAME will be set at runtime if needed
    else:
        f.write("      SCF_GUESS ATOMIC\n")

    # IGNORE_CONVERGENCE_FAILURE (for testing/debugging)
    if params.get("ignore_convergence_failure", False):
        f.write("      IGNORE_CONVERGENCE_FAILURE TRUE\n")

    f.write("    &END SCF\n")


def _write_xc_section(f, params: Dict[str, Any]) -> None:
    """Write &XC subsection."""
    f.write("    &XC\n")
    functional = params.get("functional", "PBE")
    f.write(f"      &XC_FUNCTIONAL {functional}\n")
    f.write("      &END XC_FUNCTIONAL\n")
    f.write("    &END XC\n")


def _write_subsys_section(
    f,
    params: Dict[str, Any],
    structure: Structure,
) -> None:
    """Write &SUBSYS section (structure)."""
    f.write("  &SUBSYS\n")

    # CELL
    _write_cell_block(f, structure)

    # COORD
    _write_coord_block(f, structure)

    # KIND blocks (species definitions)
    _write_kind_blocks(f, params, structure)

    f.write("  &END SUBSYS\n")


def _write_cell_block(f, structure: Structure) -> None:
    """Write &CELL block with lattice vectors."""
    f.write("    &CELL\n")
    lattice = structure.lattice
    # CP2K expects cell vectors in Angstrom
    a = lattice.matrix[0]
    b = lattice.matrix[1]
    c = lattice.matrix[2]
    f.write(f"      A {a[0]:.6f} {a[1]:.6f} {a[2]:.6f}\n")
    f.write(f"      B {b[0]:.6f} {b[1]:.6f} {b[2]:.6f}\n")
    f.write(f"      C {c[0]:.6f} {c[1]:.6f} {c[2]:.6f}\n")
    f.write("    &END CELL\n")


def _write_coord_block(f, structure: Structure) -> None:
    """Write &COORD block with atomic positions."""
    f.write("    &COORD\n")
    # CP2K expects coordinates in Angstrom
    for site in structure:
        symbol = site.specie.symbol
        coords = site.coords
        f.write(f"      {symbol} {coords[0]:.10f} {coords[1]:.10f} {coords[2]:.10f}\n")
    f.write("    &END COORD\n")


def _write_kind_blocks(
    f,
    params: Dict[str, Any],
    structure: Structure,
) -> None:
    """Write &KIND blocks for each unique species."""
    # Get unique species
    species_set = set(site.specie.symbol for site in structure)

    # Default basis/potential mapping
    default_basis = params.get("basis_set", "DZVP-MOLOPT-SR-GTH")
    default_potential = params.get("potential", "GTH-PBE")

    # Per-species overrides from params
    species_params = params.get("species", {})

    for symbol in sorted(species_set):
        f.write(f"    &KIND {symbol}\n")

        # Basis set (per-species or default)
        basis = species_params.get(symbol, {}).get("basis_set", default_basis)
        # Handle charge suffix (e.g., GTH-PBE-q4)
        if symbol in species_params:
            potential = species_params[symbol].get("potential", default_potential)
        else:
            # Try to infer charge from common patterns
            potential = default_potential
            # Common charge patterns (can be overridden)
            charge_map = {
                "Si": "GTH-PBE-q4",
                "C": "GTH-PBE-q4",
                "O": "GTH-PBE-q6",
                "H": "GTH-PBE-q1",
            }
            if symbol in charge_map:
                potential = charge_map[symbol]

        f.write(f"      BASIS_SET {basis}\n")
        f.write(f"      POTENTIAL {potential}\n")
        f.write(f"    &END KIND\n")


def _write_force_eval_print_section(f, params: Dict[str, Any]) -> None:
    """Write &PRINT subsection in FORCE_EVAL."""
    print_forces = params.get("print_forces", True)
    print_stress = params.get("print_stress", False)

    if print_forces or print_stress:
        f.write("  &PRINT\n")
        if print_forces:
            f.write("    &FORCES ON\n")
            f.write("    &END FORCES\n")
        if print_stress:
            f.write("    &STRESS ON\n")
            f.write("    &END STRESS\n")
        f.write("  &END PRINT\n")


def _write_motion_section(f, step_type: str, params: Dict[str, Any]) -> None:
    """Write &MOTION section for relax/md."""
    f.write("&MOTION\n")

    if step_type == "cp2k_relax":
        _write_geo_opt_section(f, params)
    elif step_type == "cp2k_md":
        _write_md_section(f, params)

    # PRINT subsection (trajectory, cell, restart, energy)
    _write_print_section(f, step_type, params)

    f.write("&END MOTION\n")
    f.write("\n")


def _write_geo_opt_section(f, params: Dict[str, Any]) -> None:
    """Write &GEO_OPT subsection."""
    f.write("  &GEO_OPT\n")
    optimizer = params.get("optimizer", "BFGS")
    max_iter = params.get("max_iter", 50)
    max_force = params.get("max_force", 1.0e-4)
    max_dr = params.get("max_dr", 1.0e-3)
    rms_force = params.get("rms_force", 5.0e-5)
    rms_dr = params.get("rms_dr", 5.0e-4)

    f.write(f"    OPTIMIZER {optimizer}\n")
    f.write(f"    MAX_ITER {max_iter}\n")
    f.write(f"    MAX_FORCE {max_force}\n")
    f.write(f"    MAX_DR {max_dr}\n")
    f.write(f"    RMS_FORCE {rms_force}\n")
    f.write(f"    RMS_DR {rms_dr}\n")

    # Cell optimization (if requested)
    optimize_cell = params.get("optimize_cell", False)
    if optimize_cell:
        # Change RUN_TYPE to CELL_OPT (this should be done in global section)
        # For now, we'll note it but the global section already wrote GEO_OPT
        # In a full implementation, we'd need to rewrite or handle this differently
        cell_opt_type = params.get("cell_opt_type", "DIRECT_CELL_OPT")
        f.write(f"    TYPE {cell_opt_type}\n")

    f.write("  &END GEO_OPT\n")


def _write_md_section(f, params: Dict[str, Any]) -> None:
    """Write &MD subsection."""
    f.write("  &MD\n")
    ensemble = params.get("ensemble", "NVT")
    timestep = params.get("timestep", 1.0)
    steps = params.get("steps", 1000)
    temperature = params.get("temperature", 300)

    f.write(f"    ENSEMBLE {ensemble}\n")
    f.write(f"    STEPS {steps}\n")
    f.write(f"    TIMESTEP [fs] {timestep}\n")
    f.write(f"    TEMPERATURE [K] {temperature}\n")

    # Thermostat (for NVT/NPT)
    if ensemble in ("NVT", "NPT_F", "NPT_I"):
        _write_thermostat_section(f, params)

    # Barostat (for NPT)
    if ensemble in ("NPT_F", "NPT_I"):
        _write_barostat_section(f, params)

    f.write("  &END MD\n")


def _write_thermostat_section(f, params: Dict[str, Any]) -> None:
    """Write &THERMOSTAT subsection."""
    f.write("    &THERMOSTAT\n")
    thermostat_type = params.get("thermostat", "CSVR")
    f.write(f"      TYPE {thermostat_type}\n")

    if thermostat_type == "CSVR":
        f.write("      &CSVR\n")
        timecon = params.get("thermostat_timecon", 50)
        f.write(f"        TIMECON [fs] {timecon}\n")
        f.write("      &END CSVR\n")
    elif thermostat_type == "NOSE":
        f.write("      &NOSE\n")
        timecon = params.get("thermostat_timecon", 100)
        f.write(f"        TIMECON [fs] {timecon}\n")
        f.write("      &END NOSE\n")

    f.write("    &END THERMOSTAT\n")


def _write_barostat_section(f, params: Dict[str, Any]) -> None:
    """Write &BAROSTAT subsection."""
    f.write("    &BAROSTAT\n")
    barostat_type = params.get("barostat", "ISOTROPIC")
    pressure = params.get("pressure", 1.0)
    timecon = params.get("barostat_timecon", 1000)

    f.write(f"      TYPE {barostat_type}\n")
    f.write(f"      PRESSURE [bar] {pressure}\n")
    f.write(f"      TIMECON [fs] {timecon}\n")
    f.write("    &END BAROSTAT\n")


def _write_print_section(f, step_type: str, params: Dict[str, Any]) -> None:
    """Write MOTION/PRINT section."""
    f.write("  &PRINT\n")

    # Trajectory
    f.write("    &TRAJECTORY\n")
    f.write("      FORMAT XYZ\n")
    # Frequency
    traj_freq = params.get("trajectory_freq", 1)
    if step_type == "cp2k_md":
        f.write("      &EACH\n")
        f.write(f"        MD {traj_freq}\n")
        f.write("      &END EACH\n")
    elif step_type == "cp2k_relax":
        f.write("      &EACH\n")
        f.write(f"        GEO_OPT {traj_freq}\n")
        f.write("      &END EACH\n")
    f.write("    &END TRAJECTORY\n")

    # CELL - ALWAYS enabled for relax/md
    if step_type in ("cp2k_relax", "cp2k_md"):
        f.write("    &CELL\n")
        f.write("      &EACH\n")
        cell_freq = params.get("cell_freq", 1)
        if step_type == "cp2k_md":
            f.write(f"        MD {cell_freq}\n")
        else:
            f.write(f"        GEO_OPT {cell_freq}\n")
        f.write("      &END EACH\n")
        f.write("    &END CELL\n")

    # RESTART
    restart_freq = params.get("restart_freq", None)
    if restart_freq is not None:
        f.write("    &RESTART\n")
        f.write("      &EACH\n")
        if step_type == "cp2k_md":
            f.write(f"        MD {restart_freq}\n")
        else:
            f.write(f"        GEO_OPT {restart_freq}\n")
        f.write("      &END EACH\n")
        f.write("    &END RESTART\n")

    # ENERGY (for MD)
    if step_type == "cp2k_md":
        energy_freq = params.get("energy_freq", 1)
        f.write("    &ENERGY\n")
        f.write("      &EACH\n")
        f.write(f"        MD {energy_freq}\n")
        f.write("      &END EACH\n")
        f.write("    &END ENERGY\n")

    f.write("  &END PRINT\n")

