"""QMCPACK output parser — temporary utility for exploration.

Parses scalar.dat and dmc.dat output files from QMCPACK.
This is a standalone utility for testing; will be deleted after
integration into src/qmatsuite/drivers/qmcpack/.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
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
        import math
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
    project_id: str
    series: list[dict]  # list of {series_idx, method, scalar_data, dmc_data}
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

    # Parse header
    header_line = lines[0]
    if not header_line.startswith("#"):
        raise ValueError(f"Expected header starting with #, got: {header_line[:80]}")

    columns = header_line.lstrip("#").split()
    # First column is 'index', rest are data columns
    data_columns = columns[1:]  # skip 'index'

    # Parse data rows
    data = []
    for line in lines[1:]:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        values = line.split()
        if len(values) < len(data_columns) + 1:
            continue  # skip malformed lines
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
    # First column is 'Index' or 'index'
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

    # Find VMC/DMC section ends
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
    project_id: str,
    stdout: Optional[str] = None,
) -> QMCPACKRunResult:
    """Parse a complete QMCPACK run from a working directory.

    Scans for all series files (s000, s001, ...) and parses each.
    """
    series_list = []

    # Find all scalar.dat files
    scalar_files = sorted(workdir.glob(f"{project_id}.s*.scalar.dat"))

    for sf in scalar_files:
        # Extract series index from filename
        match = re.search(r"\.s(\d+)\.scalar\.dat$", sf.name)
        if not match:
            continue
        series_idx = int(match.group(1))

        scalar_data = parse_scalar_dat(sf)

        # Check for corresponding dmc.dat
        dmc_file = workdir / f"{project_id}.s{series_idx:03d}.dmc.dat"
        dmc_data = None
        if dmc_file.exists():
            dmc_data = parse_dmc_dat(dmc_file)

        # Determine method from opt.xml existence or dmc.dat
        method = "vmc"
        opt_file = workdir / f"{project_id}.s{series_idx:03d}.opt.xml"
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
        project_id=project_id,
        series=series_list,
        success=stdout_info.get("success", bool(series_list)),
        raw_stdout=stdout,
    )


# ─────────────────────────────────────────────────────────────────────
# Self-test
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    golden_dir = Path(__file__).parent / "golden_references"
    if not golden_dir.exists():
        print(f"Golden references not found at {golden_dir}")
        sys.exit(1)

    print("=" * 60)
    print("QMCPACK Parser Self-Test")
    print("=" * 60)

    # Test 1: VMC scalar.dat
    print("\n--- Test 1: VMC Diamond scalar.dat ---")
    vmc_scalar = parse_scalar_dat(golden_dir / "vmc_diamond_scalar.dat")
    print(f"  Columns: {vmc_scalar.columns}")
    print(f"  Num blocks: {vmc_scalar.num_blocks}")
    print(f"  Mean energy: {vmc_scalar.mean_energy:.6f} Ha")
    print(f"  Energy error: {vmc_scalar.energy_error:.6f} Ha")
    print(f"  Accept ratio: {vmc_scalar.mean_accept_ratio:.4f}")
    assert vmc_scalar.num_blocks == 200, f"Expected 200 blocks, got {vmc_scalar.num_blocks}"
    assert -11.0 < vmc_scalar.mean_energy < -10.0, f"Energy out of range: {vmc_scalar.mean_energy}"
    print("  PASSED")

    # Test 2: DMC scalar.dat + dmc.dat
    print("\n--- Test 2: DMC Diamond scalar.dat ---")
    dmc_scalar = parse_scalar_dat(golden_dir / "vmc_dmc_diamond_dmc_scalar.dat")
    print(f"  Num blocks: {dmc_scalar.num_blocks}")
    print(f"  Mean energy: {dmc_scalar.mean_energy:.6f} Ha")
    print(f"  Energy error: {dmc_scalar.energy_error:.6f} Ha")
    assert dmc_scalar.num_blocks == 100, f"Expected 100 blocks, got {dmc_scalar.num_blocks}"
    assert -11.0 < dmc_scalar.mean_energy < -10.0, f"Energy out of range: {dmc_scalar.mean_energy}"
    print("  PASSED")

    print("\n--- Test 2b: DMC dmc.dat ---")
    dmc_data = parse_dmc_dat(golden_dir / "vmc_dmc_diamond_dmc_dmc.dat")
    print(f"  Columns: {dmc_data.columns}")
    print(f"  Num steps: {dmc_data.num_steps}")
    print(f"  Mean energy: {dmc_data.mean_energy:.6f} Ha")
    assert dmc_data.num_steps > 0
    assert "NumOfWalkers" in dmc_data.columns
    print("  PASSED")

    # Test 3: Optimization + VMC
    print("\n--- Test 3: Opt+VMC H4 scalar.dat ---")
    opt_scalar = parse_scalar_dat(golden_dir / "opt_vmc_h4_vmc_scalar.dat")
    print(f"  Num blocks: {opt_scalar.num_blocks}")
    print(f"  Mean energy: {opt_scalar.mean_energy:.6f} Ha")
    print(f"  Energy error: {opt_scalar.energy_error:.6f} Ha")
    assert opt_scalar.num_blocks == 200, f"Expected 200 blocks, got {opt_scalar.num_blocks}"
    assert -3.0 < opt_scalar.mean_energy < -1.5, f"Energy out of range: {opt_scalar.mean_energy}"
    print("  PASSED")

    # Test stdout parsing
    print("\n--- Test 4: Stdout parsing ---")
    fake_stdout = """
====================================================
  End of a VMC section
    QMC counter        = 0
    time step          = 0.3
    reference energy   = -10.4905
    reference variance = 0.373664
====================================================
QMCPACK execution completed successfully
"""
    stdout_result = parse_qmcpack_stdout(fake_stdout)
    assert stdout_result["success"] is True
    assert len(stdout_result["sections"]) == 1
    assert stdout_result["sections"][0]["method"] == "VMC"
    assert abs(stdout_result["sections"][0]["reference_energy"] - (-10.4905)) < 1e-4
    print("  PASSED")

    print("\n" + "=" * 60)
    print("All parser tests PASSED")
    print("=" * 60)
