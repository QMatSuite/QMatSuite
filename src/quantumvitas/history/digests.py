"""
Digest computation for step and run results.

Digests are computed automatically at the end of each run (success or failure).
They extract key metrics from QE outputs in a robust, best-effort manner.

Design invariants:
- Never crash if expected fields are missing
- Return unknown/NA markers for missing data
- If one metric fails, others should still be computed
- Degrade gracefully for incomplete/failed runs
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class DigestValue:
    """
    A single metric value with status tracking.
    
    Allows distinguishing between:
    - value present and valid
    - value missing (file not found, etc.)
    - value unknown (parsing failed, etc.)
    - value not applicable (e.g., Fermi energy for insulator)
    """
    value: Optional[Any] = None
    status: str = "ok"  # "ok", "missing", "unknown", "na", "error"
    unit: Optional[str] = None
    message: Optional[str] = None
    
    @classmethod
    def ok(cls, value: Any, unit: Optional[str] = None) -> "DigestValue":
        """Create a successful digest value."""
        return cls(value=value, status="ok", unit=unit)
    
    @classmethod
    def missing(cls, message: str = "Output file not found") -> "DigestValue":
        """Create a missing value marker."""
        return cls(value=None, status="missing", message=message)
    
    @classmethod
    def unknown(cls, message: str = "Could not parse value") -> "DigestValue":
        """Create an unknown value marker."""
        return cls(value=None, status="unknown", message=message)
    
    @classmethod
    def na(cls, message: str = "Not applicable") -> "DigestValue":
        """Create a not-applicable marker."""
        return cls(value=None, status="na", message=message)
    
    @classmethod
    def error(cls, message: str) -> "DigestValue":
        """Create an error marker."""
        return cls(value=None, status="error", message=message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = {"value": self.value, "status": self.status}
        if self.unit:
            d["unit"] = self.unit
        if self.message:
            d["message"] = self.message
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DigestValue":
        """Create from dictionary."""
        return cls(
            value=data.get("value"),
            status=data.get("status", "ok"),
            unit=data.get("unit"),
            message=data.get("message"),
        )


@dataclass
class StepDigest:
    """
    Digest of a single step's results.
    
    Contains key metrics extracted from the step's output files.
    All metrics are DigestValue objects for consistent status tracking.
    """
    step_id: str
    step_type: str
    step_name: Optional[str] = None
    status: str = "success"  # "success", "failed", "skipped"
    
    # Common metrics (present for most step types)
    converged: Optional[DigestValue] = None
    total_energy: Optional[DigestValue] = None  # Ry
    fermi_energy: Optional[DigestValue] = None  # eV
    
    # SCF-specific
    scf_iterations: Optional[DigestValue] = None
    scf_accuracy: Optional[DigestValue] = None  # Ry
    
    # Band gap info (insulators/semiconductors)
    homo: Optional[DigestValue] = None  # eV
    lumo: Optional[DigestValue] = None  # eV
    band_gap: Optional[DigestValue] = None  # eV
    
    # Bands-specific
    n_bands: Optional[DigestValue] = None
    n_kpoints: Optional[DigestValue] = None
    
    # DOS-specific
    dos_energy_range: Optional[DigestValue] = None  # [min, max] eV
    
    # Relaxation-specific
    n_relax_steps: Optional[DigestValue] = None
    final_forces_max: Optional[DigestValue] = None  # Ry/Bohr
    final_pressure: Optional[DigestValue] = None  # kbar
    
    # Phonon-specific
    n_modes: Optional[DigestValue] = None
    gamma_frequencies: Optional[DigestValue] = None  # cm^-1
    
    # Timing
    wall_time: Optional[DigestValue] = None  # seconds
    cpu_time: Optional[DigestValue] = None  # seconds
    
    # Output file info
    output_file: Optional[str] = None
    output_exists: bool = False
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = {
            "step_id": self.step_id,
            "step_type": self.step_type,
            "step_name": self.step_name,
            "status": self.status,
            "output_file": self.output_file,
            "output_exists": self.output_exists,
        }
        
        # Add all DigestValue fields
        for field_name in [
            "converged", "total_energy", "fermi_energy",
            "scf_iterations", "scf_accuracy",
            "homo", "lumo", "band_gap",
            "n_bands", "n_kpoints",
            "dos_energy_range",
            "n_relax_steps", "final_forces_max", "final_pressure",
            "n_modes", "gamma_frequencies",
            "wall_time", "cpu_time",
        ]:
            value = getattr(self, field_name)
            if value is not None:
                d[field_name] = value.to_dict()
        
        if self.error_message:
            d["error_message"] = self.error_message
        
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StepDigest":
        """Create from dictionary."""
        digest = cls(
            step_id=data.get("step_id", ""),
            step_type=data.get("step_type", ""),
            step_name=data.get("step_name"),
            status=data.get("status", "success"),
            output_file=data.get("output_file"),
            output_exists=data.get("output_exists", False),
            error_message=data.get("error_message"),
        )
        
        # Parse DigestValue fields
        for field_name in [
            "converged", "total_energy", "fermi_energy",
            "scf_iterations", "scf_accuracy",
            "homo", "lumo", "band_gap",
            "n_bands", "n_kpoints",
            "dos_energy_range",
            "n_relax_steps", "final_forces_max", "final_pressure",
            "n_modes", "gamma_frequencies",
            "wall_time", "cpu_time",
        ]:
            if field_name in data and data[field_name] is not None:
                setattr(digest, field_name, DigestValue.from_dict(data[field_name]))
        
        return digest


def compute_step_digest(
    step_id: str,
    step_type: str,
    working_dir: Path,
    step_name: Optional[str] = None,
    step_status: str = "success",
    error_message: Optional[str] = None,
) -> StepDigest:
    """
    Compute digest for a step's results.
    
    This is the main entry point for step digest computation.
    It dispatches to type-specific parsers based on step_type.
    
    Args:
        step_id: ULID of the step
        step_type: Type of step (scf, nscf, bands, dos, relax, etc.)
        working_dir: Path to working directory containing output files
        step_name: Human-readable step name
        step_status: Step execution status
        error_message: Optional error message if step failed
        
    Returns:
        StepDigest with computed metrics
    """
    digest = StepDigest(
        step_id=step_id,
        step_type=step_type,
        step_name=step_name,
        status=step_status,
        error_message=error_message,
    )
    
    working_dir = Path(working_dir)
    
    # Find output file based on step type
    output_file = _find_output_file(working_dir, step_type)
    
    if output_file:
        digest.output_file = str(output_file.relative_to(working_dir) if output_file.is_relative_to(working_dir) else output_file)
        digest.output_exists = True
    else:
        digest.output_exists = False
    
    # Dispatch to type-specific parser
    step_type_lower = step_type.lower() if step_type else ""
    
    try:
        if step_type_lower in ("scf", "relax", "vc-relax", "vc_relax", "md", "vc-md"):
            _parse_scf_digest(digest, output_file)
        elif step_type_lower == "nscf":
            _parse_nscf_digest(digest, output_file)
        elif step_type_lower in ("bands", "bands_pw"):
            _parse_bands_digest(digest, working_dir, output_file)
        elif step_type_lower == "dos":
            _parse_dos_digest(digest, working_dir, output_file)
        elif step_type_lower == "ph":
            _parse_ph_digest(digest, output_file)
        else:
            # Generic parsing for unknown step types
            if output_file:
                _parse_generic_digest(digest, output_file)
    except Exception as e:
        logger.warning(f"Error computing digest for step {step_id} ({step_type}): {e}")
        digest.error_message = str(e)
    
    return digest


def _find_output_file(working_dir: Path, step_type: str) -> Optional[Path]:
    """
    Find the output file for a step type.
    
    Tries multiple naming conventions:
    - <step_type>.out (new convention)
    - <step_type>.pw_run.out (QE wrapper output)
    - <prefix>.<step_type>.out (legacy)
    """
    if not working_dir.exists():
        return None
    
    step_type_lower = step_type.lower() if step_type else ""
    
    # Try exact matches first
    candidates = [
        working_dir / f"{step_type_lower}.out",
        working_dir / f"{step_type_lower}.pw_run.out",
    ]
    
    for candidate in candidates:
        if candidate.exists():
            return candidate
    
    # Try pattern matching
    for f in working_dir.glob("*.out"):
        name_lower = f.name.lower()
        if step_type_lower in name_lower:
            return f
    
    # For bands, also check for bands.x output
    if step_type_lower in ("bands", "bands_pw"):
        for f in working_dir.glob("*bands*.out"):
            return f
    
    return None


def _parse_scf_digest(digest: StepDigest, output_file: Optional[Path]) -> None:
    """Parse SCF/relax output file for digest metrics."""
    if not output_file or not output_file.exists():
        digest.converged = DigestValue.missing()
        digest.total_energy = DigestValue.missing()
        return
    
    try:
        from quantumvitas.analysis.parsers import parse_scf_output_path
        result = parse_scf_output_path(output_file)
        
        digest.converged = DigestValue.ok(result.converged)
        
        if result.total_energy is not None:
            digest.total_energy = DigestValue.ok(result.total_energy, "Ry")
        else:
            digest.total_energy = DigestValue.unknown("Total energy not found in output")
        
        if result.fermi_energy is not None:
            digest.fermi_energy = DigestValue.ok(result.fermi_energy, "eV")
        elif result.homo is not None:
            # Use HOMO for insulators
            digest.fermi_energy = DigestValue.ok(result.homo, "eV")
        else:
            digest.fermi_energy = DigestValue.na("Fermi energy not found (may be insulator)")
        
        if result.iterations:
            digest.scf_iterations = DigestValue.ok(len(result.iterations))
            if result.iterations[-1].scf_accuracy:
                digest.scf_accuracy = DigestValue.ok(result.iterations[-1].scf_accuracy, "Ry")
        
        if result.homo is not None:
            digest.homo = DigestValue.ok(result.homo, "eV")
        if result.lumo is not None:
            digest.lumo = DigestValue.ok(result.lumo, "eV")
        if result.band_gap is not None:
            digest.band_gap = DigestValue.ok(result.band_gap, "eV")
        
        if result.total_wall_time is not None:
            digest.wall_time = DigestValue.ok(result.total_wall_time, "s")
        if result.total_cpu_time is not None:
            digest.cpu_time = DigestValue.ok(result.total_cpu_time, "s")
        
        # Check for relax-specific info
        if digest.step_type in ("relax", "vc-relax", "vc_relax"):
            _parse_relax_specific(digest, output_file)
        
    except Exception as e:
        logger.warning(f"Error parsing SCF output {output_file}: {e}")
        digest.converged = DigestValue.error(str(e))


def _parse_relax_specific(digest: StepDigest, output_file: Path) -> None:
    """Parse relaxation-specific metrics."""
    try:
        text = output_file.read_text()
        
        # Count BFGS steps
        bfgs_count = len(re.findall(r"number of scf cycles\s*=\s*\d+", text))
        if bfgs_count > 0:
            digest.n_relax_steps = DigestValue.ok(bfgs_count)
        
        # Find final forces
        force_pattern = re.compile(r"Total force\s*=\s*([\d.]+)")
        forces = force_pattern.findall(text)
        if forces:
            digest.final_forces_max = DigestValue.ok(float(forces[-1]), "Ry/Bohr")
        
        # Find final pressure (vc-relax)
        pressure_pattern = re.compile(r"P=\s*([-\d.]+)")
        pressures = pressure_pattern.findall(text)
        if pressures:
            digest.final_pressure = DigestValue.ok(float(pressures[-1]), "kbar")
        
    except Exception as e:
        logger.debug(f"Error parsing relax-specific metrics: {e}")


def _parse_nscf_digest(digest: StepDigest, output_file: Optional[Path]) -> None:
    """Parse NSCF output file for digest metrics."""
    if not output_file or not output_file.exists():
        digest.fermi_energy = DigestValue.missing()
        return
    
    try:
        from quantumvitas.analysis.parsers import parse_scf_output_path
        result = parse_scf_output_path(output_file)
        
        digest.converged = DigestValue.ok(result.converged)
        
        if result.fermi_energy is not None:
            digest.fermi_energy = DigestValue.ok(result.fermi_energy, "eV")
        elif result.homo is not None:
            digest.fermi_energy = DigestValue.ok(result.homo, "eV")
        else:
            digest.fermi_energy = DigestValue.unknown("Fermi energy not found")
        
        if result.n_bands is not None:
            digest.n_bands = DigestValue.ok(result.n_bands)
        if result.n_kpoints is not None:
            digest.n_kpoints = DigestValue.ok(result.n_kpoints)
        
        if result.homo is not None:
            digest.homo = DigestValue.ok(result.homo, "eV")
        if result.lumo is not None:
            digest.lumo = DigestValue.ok(result.lumo, "eV")
        if result.band_gap is not None:
            digest.band_gap = DigestValue.ok(result.band_gap, "eV")
        
        if result.total_wall_time is not None:
            digest.wall_time = DigestValue.ok(result.total_wall_time, "s")
        
    except Exception as e:
        logger.warning(f"Error parsing NSCF output {output_file}: {e}")
        digest.fermi_energy = DigestValue.error(str(e))


def _parse_bands_digest(digest: StepDigest, working_dir: Path, output_file: Optional[Path]) -> None:
    """Parse bands calculation output for digest metrics."""
    # For bands, the important file is bands.dat.gnu
    bands_gnu = None
    for f in working_dir.glob("*.dat.gnu"):
        bands_gnu = f
        break
    
    if bands_gnu and bands_gnu.exists():
        try:
            from quantumvitas.analysis.parsers import parse_bands_gnu
            bands_data = parse_bands_gnu(bands_gnu)
            
            digest.n_bands = DigestValue.ok(bands_data.n_bands)
            digest.n_kpoints = DigestValue.ok(bands_data.n_kpoints)
            
        except Exception as e:
            logger.warning(f"Error parsing bands data: {e}")
            digest.n_bands = DigestValue.error(str(e))
    else:
        digest.n_bands = DigestValue.missing("bands.dat.gnu not found")
    
    # Also try to parse the bands.x output for Fermi energy
    if output_file and output_file.exists():
        try:
            text = output_file.read_text()
            fermi_match = re.search(r"Fermi energy\s*[=:]\s*([-\d.]+)", text, re.IGNORECASE)
            if fermi_match:
                digest.fermi_energy = DigestValue.ok(float(fermi_match.group(1)), "eV")
        except Exception:
            pass


def _parse_dos_digest(digest: StepDigest, working_dir: Path, output_file: Optional[Path]) -> None:
    """Parse DOS calculation output for digest metrics."""
    # Find DOS data file
    dos_file = None
    for f in working_dir.glob("*.dos.dat"):
        dos_file = f
        break
    
    if not dos_file:
        for f in working_dir.glob("*dos*.dat"):
            dos_file = f
            break
    
    if dos_file and dos_file.exists():
        try:
            from quantumvitas.analysis.parsers import parse_dos_data
            dos_data = parse_dos_data(dos_file)
            
            if dos_data.fermi_energy is not None:
                digest.fermi_energy = DigestValue.ok(dos_data.fermi_energy, "eV")
            
            e_min = float(dos_data.energies.min())
            e_max = float(dos_data.energies.max())
            digest.dos_energy_range = DigestValue.ok([e_min, e_max], "eV")
            
        except Exception as e:
            logger.warning(f"Error parsing DOS data: {e}")
            digest.dos_energy_range = DigestValue.error(str(e))
    else:
        digest.dos_energy_range = DigestValue.missing("DOS data file not found")


def _parse_ph_digest(digest: StepDigest, output_file: Optional[Path]) -> None:
    """Parse phonon calculation output for digest metrics."""
    if not output_file or not output_file.exists():
        digest.n_modes = DigestValue.missing()
        return
    
    try:
        text = output_file.read_text()
        
        # Count modes
        mode_pattern = re.compile(r"mode\s+#\s*(\d+)")
        modes = mode_pattern.findall(text)
        if modes:
            digest.n_modes = DigestValue.ok(max(int(m) for m in modes))
        
        # Find gamma frequencies
        freq_pattern = re.compile(r"freq\s*\(\s*\d+\)\s*=\s*([-\d.]+)\s*\[cm-1\]")
        freqs = freq_pattern.findall(text)
        if freqs:
            digest.gamma_frequencies = DigestValue.ok([float(f) for f in freqs[-3:]], "cm-1")
        
    except Exception as e:
        logger.warning(f"Error parsing phonon output: {e}")
        digest.n_modes = DigestValue.error(str(e))


def _parse_generic_digest(digest: StepDigest, output_file: Path) -> None:
    """Generic parsing for unknown step types - extract timing and success."""
    try:
        text = output_file.read_text()
        
        # Check for JOB DONE marker
        if "JOB DONE" in text:
            digest.converged = DigestValue.ok(True)
        else:
            digest.converged = DigestValue.unknown("JOB DONE marker not found")
        
        # Try to extract timing
        time_pattern = re.compile(r"(\w+)\s*:\s*([\d.]+)\s*s\s*CPU\s+([\d.]+)\s*s\s*WALL")
        time_match = time_pattern.search(text)
        if time_match:
            digest.cpu_time = DigestValue.ok(float(time_match.group(2)), "s")
            digest.wall_time = DigestValue.ok(float(time_match.group(3)), "s")
        
    except Exception as e:
        logger.debug(f"Error in generic parsing: {e}")


def compute_run_digest(
    run_id: str,
    calc_id: str,
    status: str,
    started_at: datetime,
    finished_at: datetime,
    step_digests: List[StepDigest],
    error_summary: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compute overall run digest from step digests.
    
    Args:
        run_id: ULID of the run
        calc_id: ULID of the calculation
        status: Overall run status ("success", "failed", "cancelled")
        started_at: Run start time
        finished_at: Run end time
        step_digests: List of step digests
        error_summary: Optional error description
        
    Returns:
        Run digest dictionary
    """
    duration = (finished_at - started_at).total_seconds()
    
    success_count = sum(1 for d in step_digests if d.status == "success")
    failed_count = sum(1 for d in step_digests if d.status == "failed")
    skipped_count = sum(1 for d in step_digests if d.status == "skipped")
    
    # Extract key metrics from step digests
    total_energy = None
    fermi_energy = None
    converged = True
    
    for digest in step_digests:
        if digest.total_energy and digest.total_energy.status == "ok":
            total_energy = digest.total_energy.value
        if digest.fermi_energy and digest.fermi_energy.status == "ok":
            fermi_energy = digest.fermi_energy.value
        if digest.converged and digest.converged.status == "ok":
            if not digest.converged.value:
                converged = False
    
    return {
        "run_id": run_id,
        "calc_id": calc_id,
        "status": status,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": duration,
        "step_count": len(step_digests),
        "success_count": success_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "converged": converged,
        "total_energy_ry": total_energy,
        "fermi_energy_ev": fermi_energy,
        "error_summary": error_summary,
        "step_digests": [d.to_dict() for d in step_digests],
    }

