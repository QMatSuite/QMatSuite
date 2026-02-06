"""QMCPACK output parser: extract energy, convergence, timing from QMCPACK runs.

Parses QMCPACK calculation outputs into a canonical QMCPACKDigest dataclass.
Primary sources: *.scalar.dat, *.dmc.dat, stdout log.

Registers with the parser registry as ("qmcpack", "scf_digest").
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from quantumvitas.parsers.registry import register_parser


@dataclass
class QMCPACKDigest:
    """Canonical digest of a QMCPACK calculation output.

    Attributes:
        success: True if QMCPACK completed successfully.
        method: Last QMC method run (vmc, dmc, optimization).
        energy_Ha: Final mean LocalEnergy in Hartree.
        energy_error_Ha: Standard error of mean energy.
        energy_variance: Variance of LocalEnergy.
        accept_ratio: Mean acceptance ratio.
        n_blocks: Number of blocks in final series.
        n_walkers: Number of walkers reported.
        wall_time_s: Total execution time in seconds.
        project_tag: Project ID from input.
        n_series: Number of QMC series found.
        dmc_energy_Ha: DMC energy if DMC was run.
        optimization_final_energy: Energy from final optimization series.
        error_message: Error message if calculation failed.
    """

    success: bool = False
    method: Optional[str] = None
    energy_Ha: Optional[float] = None
    energy_error_Ha: Optional[float] = None
    energy_variance: Optional[float] = None
    accept_ratio: Optional[float] = None
    n_blocks: Optional[int] = None
    n_walkers: Optional[int] = None
    wall_time_s: Optional[float] = None
    project_tag: Optional[str] = None
    n_series: Optional[int] = None
    dmc_energy_Ha: Optional[float] = None
    optimization_final_energy: Optional[float] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to plain dict (JSON-serialisable)."""
        return asdict(self)


@register_parser("qmcpack", "scf_digest")
class QMCPACKOutputParser:
    """Parse QMCPACK outputs into a QMCPACKDigest.

    Looks for *.scalar.dat files and stdout log in the directory.
    """

    engine = "qmcpack"
    object_type = "scf_digest"

    def can_parse(self, raw_dir: Path) -> bool:
        """Check if the directory contains parseable QMCPACK output."""
        return bool(list(raw_dir.glob("*.scalar.dat")))

    def parse(self, raw_dir: Path, **kwargs: Any) -> QMCPACKDigest:
        """Parse QMCPACK output directory into a QMCPACKDigest."""
        from quantumvitas.drivers.qmcpack.parser import (
            parse_qmcpack_run,
        )

        # Find project tag from scalar.dat filenames
        scalar_files = sorted(raw_dir.glob("*.scalar.dat"))
        if not scalar_files:
            return QMCPACKDigest(error_message="No *.scalar.dat files found")

        # Derive project tag: "He.s000.scalar.dat" → "He"
        first_name = scalar_files[0].name
        match = re.match(r"^(.+?)\.s\d+\.scalar\.dat$", first_name)
        if not match:
            return QMCPACKDigest(
                error_message=f"Cannot parse project tag from {first_name}"
            )
        project_tag = match.group(1)

        # Find stdout log
        stdout = None
        for log_name in ("stdout.log", "qmcpack.out", "output"):
            log_path = raw_dir / log_name
            if log_path.is_file():
                try:
                    stdout = log_path.read_text(errors="replace")
                except OSError:
                    pass
                break

        # Delegate to existing parser
        try:
            run_result = parse_qmcpack_run(raw_dir, project_tag, stdout)
        except Exception as e:
            return QMCPACKDigest(error_message=f"Parse error: {e}")

        return _run_result_to_digest(run_result, stdout)


def parse_qmcpack_output(raw_dir: Path) -> QMCPACKDigest:
    """Convenience function to parse QMCPACK output directory."""
    parser = QMCPACKOutputParser()
    return parser.parse(raw_dir)


def parse_qmcpack_stdout_text(text: str) -> QMCPACKDigest:
    """Parse QMCPACK stdout text directly into a QMCPACKDigest.

    Useful for unit testing with inline log strings.
    """
    from quantumvitas.drivers.qmcpack.parser import parse_qmcpack_stdout

    info = parse_qmcpack_stdout(text)
    digest = QMCPACKDigest()
    digest.success = info.get("success", False)

    # Extract wall time
    time_match = re.search(
        r"Total Execution time\s*=\s*([\d.eE+-]+)\s*secs", text
    )
    if time_match:
        try:
            digest.wall_time_s = float(time_match.group(1))
        except ValueError:
            pass

    # Extract walker count
    walker_match = re.search(r"total_walkers\s*=\s*(\d+)", text)
    if walker_match:
        digest.n_walkers = int(walker_match.group(1))

    # Extract method and reference energy from sections
    sections = info.get("sections", [])
    if sections:
        last_section = sections[-1]
        digest.method = last_section.get("method", "").lower()
        digest.energy_Ha = last_section.get("reference_energy")
        digest.energy_variance = last_section.get("reference_variance")
        digest.n_series = len(sections)

    return digest


def _run_result_to_digest(
    run_result: Any,
    stdout: str | None,
) -> QMCPACKDigest:
    """Convert a QMCPACKRunResult to a QMCPACKDigest."""
    digest = QMCPACKDigest()
    digest.success = run_result.success
    digest.project_tag = run_result.project_tag
    digest.n_series = len(run_result.series)

    if not run_result.series:
        if not run_result.success:
            digest.error_message = "No QMC series found"
        return digest

    # Last series determines primary results
    last = run_result.series[-1]
    digest.method = last.get("method", "vmc")

    scalar_data = last.get("scalar_data")
    if scalar_data is not None:
        digest.energy_Ha = scalar_data.mean_energy
        digest.energy_error_Ha = scalar_data.energy_error
        digest.energy_variance = scalar_data.energy_variance
        digest.accept_ratio = scalar_data.mean_accept_ratio
        digest.n_blocks = scalar_data.num_blocks

    # DMC energy from last DMC series
    for s in reversed(run_result.series):
        if s.get("method") == "dmc" and s.get("dmc_data") is not None:
            digest.dmc_energy_Ha = s["dmc_data"].mean_energy
            break

    # Optimization final energy
    for s in reversed(run_result.series):
        if s.get("method") == "optimization" and s.get("scalar_data") is not None:
            digest.optimization_final_energy = s["scalar_data"].mean_energy
            break

    # Wall time from stdout
    if stdout:
        time_match = re.search(
            r"Total Execution time\s*=\s*([\d.eE+-]+)\s*secs", stdout
        )
        if time_match:
            try:
                digest.wall_time_s = float(time_match.group(1))
            except ValueError:
                pass
        walker_match = re.search(r"total_walkers\s*=\s*(\d+)", stdout)
        if walker_match:
            digest.n_walkers = int(walker_match.group(1))

    return digest
