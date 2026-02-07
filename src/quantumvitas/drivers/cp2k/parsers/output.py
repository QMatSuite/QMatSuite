"""CP2K output parser: .out text digest.

Parses CP2K calculation outputs into a canonical CP2KDigest dataclass.
Primary source: .out text file (regex on structured output lines).

Registers with the parser registry as ("cp2k", "scf_digest").

Stdlib only — no kernel imports except quantumvitas.parsers.registry.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from quantumvitas.parsers.registry import register_parser

logger = logging.getLogger(__name__)

# CP2K energy unit: 1 Ha = 27.211386245988 eV
_HA_TO_EV = 27.211386245988


@dataclass
class CP2KDigest:
    """Canonical digest of a CP2K calculation output."""

    final_energy_eV: Optional[float] = None
    energy_per_atom_eV: Optional[float] = None
    n_atoms: int = 0
    converged_electronic: bool = False
    converged_ionic: bool = False
    n_ionic_steps: int = 0
    n_electronic_steps: int = 0
    cp2k_version: Optional[str] = None
    run_type: Optional[str] = None
    final_species: Optional[list[str]] = None
    final_cart_coords: Optional[list[list[float]]] = None
    max_force_eV_A: Optional[float] = None
    max_step_size: Optional[float] = None
    rms_gradient: Optional[float] = None
    elapsed_time_s: Optional[float] = None
    method: Optional[str] = None
    total_charge: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to plain dict (JSON-serialisable)."""
        return asdict(self)


@register_parser("cp2k", "scf_digest")
class CP2KOutputParser:
    """Parse CP2K outputs into a CP2KDigest.

    Looks for *.out files in the raw directory.
    """

    engine = "cp2k"
    object_type = "scf_digest"

    def can_parse(self, raw_dir: Path) -> bool:
        """Check if the directory contains parseable CP2K output."""
        return any(raw_dir.glob("*.out"))

    def parse(self, raw_dir: Path, **kwargs: Any) -> CP2KDigest:
        """Parse CP2K output into a CP2KDigest."""
        out_files = sorted(raw_dir.glob("*.out"))
        if not out_files:
            logger.warning("No .out files found in %s", raw_dir)
            return CP2KDigest()

        text = out_files[0].read_text(errors="replace")
        return self._parse_output_text(text)

    def _parse_output_text(self, text: str) -> CP2KDigest:
        """Parse CP2K output text into a digest."""
        digest = CP2KDigest()

        # Version
        digest.cp2k_version = _parse_version(text)

        # Run type
        digest.run_type = _parse_run_type(text)

        # Method
        digest.method = _parse_method(text)

        # Number of atoms
        digest.n_atoms = _parse_n_atoms(text)

        # SCF convergence and iterations
        scf_info = _parse_scf_info(text)
        digest.converged_electronic = scf_info["converged"]
        digest.n_electronic_steps = scf_info["n_steps"]

        # Total energy (last FORCE_EVAL energy in Hartree)
        energy_ha = _parse_total_energy(text)
        if energy_ha is not None:
            digest.final_energy_eV = energy_ha * _HA_TO_EV
            if digest.n_atoms > 0:
                digest.energy_per_atom_eV = digest.final_energy_eV / digest.n_atoms

        # Optimization convergence
        opt_info = _parse_optimization_info(text)
        digest.converged_ionic = opt_info["converged"]
        digest.n_ionic_steps = opt_info["n_steps"]
        if opt_info.get("max_gradient") is not None:
            # Convert Ha/Bohr to eV/Angstrom: 1 Ha/Bohr = 51.42206313 eV/A
            digest.max_force_eV_A = opt_info["max_gradient"] * _HA_TO_EV / 0.529177249
        digest.max_step_size = opt_info.get("max_step")
        digest.rms_gradient = opt_info.get("rms_gradient")

        # Mulliken charges (total charge)
        digest.total_charge = _parse_total_charge(text)

        # Timing
        digest.elapsed_time_s = _parse_timing(text)

        return digest


# ── Helper functions ────────────────────────────────────────────────────


def _parse_version(text: str) -> Optional[str]:
    """Extract CP2K version string."""
    m = re.search(r"CP2K\| version string:\s+CP2K version\s+([\d.]+)", text)
    return m.group(1) if m else None


def _parse_run_type(text: str) -> Optional[str]:
    """Extract run type from GLOBAL section echo."""
    m = re.search(r"GLOBAL\| Run type\s+(\S+)", text)
    return m.group(1) if m else None


def _parse_method(text: str) -> Optional[str]:
    """Extract method from GLOBAL section echo."""
    m = re.search(r"GLOBAL\| Method name\s+(\S+)", text)
    return m.group(1) if m else None


def _parse_n_atoms(text: str) -> int:
    """Extract number of atoms from output."""
    m = re.search(r"Total number of\s+- Atoms:\s+(\d+)", text)
    if m:
        return int(m.group(1))
    # Fallback: count from Mulliken analysis
    matches = list(re.finditer(r"#\s+Atom\s+Element\s+Kind", text))
    if matches:
        # Count atom lines after the header
        block_start = matches[-1].end()
        atom_lines = re.findall(
            r"^\s+\d+\s+\w+\s+\d+\s+", text[block_start:], re.MULTILINE
        )
        return len(atom_lines)
    return 0


def _parse_scf_info(text: str) -> dict[str, Any]:
    """Parse SCF convergence information."""
    result: dict[str, Any] = {"converged": False, "n_steps": 0}

    # Find all "SCF run converged in N steps" lines
    matches = list(re.finditer(r"\*\*\* SCF run converged in\s+(\d+) steps", text))
    if matches:
        result["converged"] = True
        # Total SCF steps across all force evaluations
        result["n_steps"] = sum(int(m.group(1)) for m in matches)
    else:
        # Count SCF iteration lines
        step_lines = re.findall(
            r"^\s+\d+\s+\S+/\S+\.\s+\S+\s+\S+\s+\S+\s+[-\d.]+\s+[-\d.E+]+",
            text, re.MULTILINE,
        )
        result["n_steps"] = len(step_lines)
        # Check for non-convergence warning
        if "SCF run NOT converged" in text:
            result["converged"] = False
        elif result["n_steps"] > 0:
            result["converged"] = True

    return result


def _parse_total_energy(text: str) -> Optional[float]:
    """Extract total energy in Hartree from CP2K output.

    Primary: ``ENERGY| Total FORCE_EVAL ( QS ) energy [hartree]``
    Fallback: ``Total energy:`` line
    """
    # Primary: ENERGY| line (most reliable)
    matches = list(re.finditer(
        r"ENERGY\| Total FORCE_EVAL \( \w+ \) energy \[hartree\]\s+([-\d.]+)",
        text,
    ))
    if matches:
        return float(matches[-1].group(1))

    # Fallback: "Total energy:" line
    matches = list(re.finditer(r"Total energy:\s+([-\d.]+)", text))
    if matches:
        return float(matches[-1].group(1))

    return None


def _parse_optimization_info(text: str) -> dict[str, Any]:
    """Parse geometry/cell optimization convergence."""
    result: dict[str, Any] = {
        "converged": False,
        "n_steps": 0,
        "max_gradient": None,
        "max_step": None,
        "rms_gradient": None,
    }

    # Find optimization step blocks
    step_matches = list(re.finditer(r"OPT\| Step number\s+(\d+)", text))
    if step_matches:
        result["n_steps"] = int(step_matches[-1].group(1))

    # Check convergence
    if re.search(r"GEOMETRY OPTIMIZATION COMPLETED", text):
        result["converged"] = True

    # Check for max iteration reached (not converged)
    if re.search(r"MAXIMUM NUMBER OF OPTIMIZATION STEPS REACHED", text):
        result["converged"] = False

    # Extract last OPT block metrics
    # Maximum gradient
    grad_matches = list(re.finditer(
        r"OPT\| Maximum gradient\s+([-\d.E+]+)", text
    ))
    if grad_matches:
        result["max_gradient"] = float(grad_matches[-1].group(1))

    # Maximum step size
    step_matches_val = list(re.finditer(
        r"OPT\| Maximum step size\s+([-\d.E+]+)", text
    ))
    if step_matches_val:
        result["max_step"] = float(step_matches_val[-1].group(1))

    # RMS gradient
    rms_matches = list(re.finditer(
        r"OPT\| RMS gradient\s+([-\d.E+]+)", text
    ))
    if rms_matches:
        result["rms_gradient"] = float(rms_matches[-1].group(1))

    return result


def _parse_total_charge(text: str) -> Optional[float]:
    """Extract total charge from Mulliken analysis."""
    m = re.search(
        r"# Total charge\s+([-\d.]+)\s+([-\d.]+)",
        text,
    )
    if m:
        return float(m.group(2))  # Net charge column
    return None


def _parse_timing(text: str) -> Optional[float]:
    """Extract elapsed wall time from output.

    CP2K reports timing via PROGRAM STARTED AT / PROGRAM ENDED AT timestamps.
    """
    start_m = re.search(
        r"PROGRAM STARTED AT\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)",
        text,
    )
    end_m = re.search(
        r"PROGRAM ENDED AT\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)",
        text,
    )

    if start_m and end_m:
        from datetime import datetime
        try:
            fmt = "%Y-%m-%d %H:%M:%S.%f"
            start = datetime.strptime(start_m.group(1), fmt)
            end = datetime.strptime(end_m.group(1), fmt)
            return (end - start).total_seconds()
        except ValueError:
            pass

    return None


# ── Convenience functions ───────────────────────────────────────────────


def parse_cp2k_output(raw_dir: Path) -> CP2KDigest:
    """Convenience wrapper for CP2K output parsing."""
    parser = CP2KOutputParser()
    return parser.parse(raw_dir)


def parse_cp2k_output_text(text: str) -> CP2KDigest:
    """Direct text parsing for testing."""
    parser = CP2KOutputParser()
    return parser._parse_output_text(text)
