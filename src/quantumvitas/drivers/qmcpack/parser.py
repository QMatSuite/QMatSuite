"""QMCPACK output parser.

Parses scalar.dat and dmc.dat output files from QMCPACK.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class QMCPACKScalarData:
    """Parsed data from a QMCPACK scalar.dat file."""
    columns: list[str]
    data: list[dict[str, float]]
    num_blocks: int

    @property
    def mean_energy(self) -> float:
        """Mean LocalEnergy across all blocks."""
        if not self.data:
            return float('nan')
        energies = [row["LocalEnergy"] for row in self.data]
        return sum(energies) / len(energies)

    @property
    def energy_variance(self) -> float:
        """Variance of LocalEnergy across blocks."""
        if len(self.data) < 2:
            return float('nan')
        mean = self.mean_energy
        energies = [row["LocalEnergy"] for row in self.data]
        return sum((e - mean) ** 2 for e in energies) / (len(energies) - 1)

    @property
    def energy_error(self) -> float:
        """Standard error of the mean energy."""
        if len(self.data) < 2:
            return float('nan')
        return math.sqrt(self.energy_variance / len(self.data))

    @property
    def mean_accept_ratio(self) -> float:
        """Mean acceptance ratio."""
        if not self.data or "AcceptRatio" not in self.data[0]:
            return float('nan')
        ratios = [row["AcceptRatio"] for row in self.data]
        return sum(ratios) / len(ratios)


@dataclass
class QMCPACKDMCData:
    """Parsed data from a QMCPACK dmc.dat file."""
    columns: list[str]
    data: list[dict[str, float]]
    num_steps: int

    @property
    def mean_energy(self) -> float:
        if not self.data:
            return float('nan')
        energies = [row["LocalEnergy"] for row in self.data]
        return sum(energies) / len(energies)


@dataclass
class QMCPACKRunResult:
    """Complete parsed result from a QMCPACK run."""
    project_tag: str
    series: list[dict]
    success: bool
    raw_stdout: Optional[str] = None

    @property
    def final_energy(self) -> float:
        """Energy from the last series."""
        if not self.series:
            return float('nan')
        last = self.series[-1]
        if last.get("scalar_data"):
            return last["scalar_data"].mean_energy
        return float('nan')

    @property
    def final_energy_error(self) -> float:
        if not self.series:
            return float('nan')
        last = self.series[-1]
        if last.get("scalar_data"):
            return last["scalar_data"].energy_error
        return float('nan')


def parse_scalar_dat(filepath: Path) -> QMCPACKScalarData:
    """Parse a QMCPACK scalar.dat file.

    Format: header line starting with # followed by whitespace-separated
    column names, then data rows with index + float values.
    """
    text = filepath.read_text()
    lines = text.strip().split("\n")

    if not lines:
        raise ValueError(f"Empty scalar.dat file: {filepath}")

    header_line = lines[0]
    if not header_line.startswith("#"):
        raise ValueError(f"Expected header starting with #, got: {header_line[:80]}")

    columns = header_line.lstrip("#").split()
    data_columns = columns[1:]  # skip 'index'

    data = []
    for line in lines[1:]:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        values = line.split()
        if len(values) < len(data_columns) + 1:
            continue
        row = {}
        for i, col in enumerate(data_columns):
            try:
                row[col] = float(values[i + 1])
            except (ValueError, IndexError):
                row[col] = float('nan')
        data.append(row)

    return QMCPACKScalarData(
        columns=data_columns,
        data=data,
        num_blocks=len(data),
    )


def parse_dmc_dat(filepath: Path) -> QMCPACKDMCData:
    """Parse a QMCPACK dmc.dat file.

    Similar format to scalar.dat but with DMC-specific columns
    (NumOfWalkers, TrialEnergy, etc.) and per-step data.
    """
    text = filepath.read_text()
    lines = text.strip().split("\n")

    if not lines:
        raise ValueError(f"Empty dmc.dat file: {filepath}")

    header_line = lines[0]
    if not header_line.startswith("#"):
        raise ValueError(f"Expected header starting with #, got: {header_line[:80]}")

    columns = header_line.lstrip("#").split()
    data_columns = columns[1:]

    data = []
    for line in lines[1:]:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        values = line.split()
        if len(values) < len(data_columns) + 1:
            continue
        row = {}
        for i, col in enumerate(data_columns):
            try:
                row[col] = float(values[i + 1])
            except (ValueError, IndexError):
                row[col] = float('nan')
        data.append(row)

    return QMCPACKDMCData(
        columns=data_columns,
        data=data,
        num_steps=len(data),
    )


def parse_qmcpack_stdout(stdout: str) -> dict:
    """Parse QMCPACK stdout for key information.

    Returns dict with:
    - success: bool
    - sections: list of {method, reference_energy, reference_variance}
    """
    result = {
        "success": "QMCPACK execution completed successfully" in stdout,
        "sections": [],
    }

    section_pattern = re.compile(
        r"End of a (\w+) section.*?"
        r"reference energy\s*=\s*([0-9eE.+-]+).*?"
        r"reference variance\s*=\s*([0-9eE.+-]+)",
        re.DOTALL,
    )

    for match in section_pattern.finditer(stdout):
        result["sections"].append({
            "method": match.group(1),
            "reference_energy": float(match.group(2)),
            "reference_variance": float(match.group(3)),
        })

    return result


def parse_qmcpack_run(
    workdir: Path,
    project_tag: str,
    stdout: Optional[str] = None,
) -> QMCPACKRunResult:
    """Parse a complete QMCPACK run from a working directory.

    Scans for all series files (s000, s001, ...) and parses each.
    """
    series_list = []

    scalar_files = sorted(workdir.glob(f"{project_tag}.s*.scalar.dat"))

    for sf in scalar_files:
        match = re.search(r"\.s(\d+)\.scalar\.dat$", sf.name)
        if not match:
            continue
        series_idx = int(match.group(1))

        scalar_data = parse_scalar_dat(sf)

        dmc_file = workdir / f"{project_tag}.s{series_idx:03d}.dmc.dat"
        dmc_data = None
        if dmc_file.exists():
            dmc_data = parse_dmc_dat(dmc_file)

        method = "vmc"
        opt_file = workdir / f"{project_tag}.s{series_idx:03d}.opt.xml"
        if opt_file.exists():
            method = "optimization"
        elif dmc_data is not None:
            method = "dmc"

        series_list.append({
            "series_idx": series_idx,
            "method": method,
            "scalar_data": scalar_data,
            "dmc_data": dmc_data,
        })

    stdout_info = parse_qmcpack_stdout(stdout) if stdout else {"success": True}

    return QMCPACKRunResult(
        project_tag=project_tag,
        series=series_list,
        success=stdout_info.get("success", bool(series_list)),
        raw_stdout=stdout,
    )
