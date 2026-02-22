"""xTB input writer utility.

Generates input files for xTB calculations:
- XYZ structure files (input.xyz)
- xcontrol files (for advanced settings like MD, constraints)
- Command-line argument construction

Designed as a standalone exploration utility. When integrating into
QMatSuite, this will be adapted into src/qmatsuite/drivers/xtb/writer.py

xTB input model:
  - Structure: standard XYZ file
  - Method/runtype: command-line flags (--gfn 2, --opt tight, etc.)
  - Advanced settings: xcontrol file ($md, $opt, $constrain blocks)
  - Charge/multiplicity: -c and -u flags (or .CHRG/.UHF files)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence


def write_xyz_file(
    symbols: Sequence[str],
    positions: Sequence[Sequence[float]],
    output_path: Path,
    comment: str = "",
) -> Path:
    """Write a standard XYZ file.

    Args:
        symbols: Element symbols (e.g., ["O", "H", "H"])
        positions: Cartesian coordinates in Angstrom, shape (n_atoms, 3)
        output_path: Path to write the file
        comment: Comment line (line 2 of XYZ file)

    Returns:
        Path to written file
    """
    n_atoms = len(symbols)
    lines = [str(n_atoms), comment]
    for sym, pos in zip(symbols, positions):
        lines.append(f"{sym:>2s}  {pos[0]:16.10f}  {pos[1]:16.10f}  {pos[2]:16.10f}")
    output_path.write_text("\n".join(lines) + "\n")
    return output_path


def write_xyz_from_pymatgen(
    structure: Any,
    output_path: Path,
    comment: str = "",
) -> Path:
    """Write XYZ file from a pymatgen Structure or Molecule.

    Args:
        structure: pymatgen Structure or Molecule object
        output_path: Path to write the file
        comment: Comment line

    Returns:
        Path to written file
    """
    symbols = [str(site.specie) for site in structure]
    positions = [list(site.coords) for site in structure]
    return write_xyz_file(symbols, positions, output_path, comment)


def build_xtb_command(
    input_file: str = "input.xyz",
    runtype: str = "opt",
    gfn_level: int = 2,
    opt_level: str | None = None,
    charge: int = 0,
    uhf: int = 0,
    solvent: str | None = None,
    solvent_model: str = "alpb",
    xcontrol_file: str | None = None,
    json_output: bool = False,
    extra_flags: list[str] | None = None,
) -> list[str]:
    """Build xTB command-line arguments.

    Args:
        input_file: Path to input XYZ file
        runtype: Calculation type: "sp", "opt", "grad", "hess", "ohess", "md"
        gfn_level: GFN parametrization level (0, 1, 2) or -1 for GFN-FF
        opt_level: Optimization level (crude/sloppy/loose/normal/tight/verytight/extreme)
        charge: Molecular charge
        uhf: Number of unpaired electrons
        solvent: Solvent name for implicit solvation
        solvent_model: "alpb" or "gbsa"
        xcontrol_file: Path to xcontrol input file
        json_output: Whether to write xtbout.json
        extra_flags: Additional command-line flags

    Returns:
        List of command-line arguments (including "xtb" as first element)
    """
    cmd = ["xtb", input_file]

    # Method
    if gfn_level == -1:
        cmd.append("--gfnff")
    else:
        cmd.extend(["--gfn", str(gfn_level)])

    # Runtype
    if runtype == "sp":
        cmd.append("--sp")
    elif runtype == "opt":
        if opt_level:
            cmd.extend(["--opt", opt_level])
        else:
            cmd.append("--opt")
    elif runtype == "grad":
        cmd.append("--grad")
    elif runtype == "hess":
        cmd.append("--hess")
    elif runtype == "ohess":
        if opt_level:
            cmd.extend(["--ohess", opt_level])
        else:
            cmd.append("--ohess")
    elif runtype == "md":
        cmd.append("--md")

    # Charge and spin
    if charge != 0:
        cmd.extend(["-c", str(charge)])
    if uhf != 0:
        cmd.extend(["-u", str(uhf)])

    # Solvation
    if solvent:
        cmd.extend([f"--{solvent_model}", solvent])

    # xcontrol input
    if xcontrol_file:
        cmd.extend(["-I", xcontrol_file])

    # JSON output
    if json_output:
        cmd.append("--json")

    # Extra flags
    if extra_flags:
        cmd.extend(extra_flags)

    return cmd


def write_xcontrol(
    output_path: Path,
    md_settings: dict[str, Any] | None = None,
    opt_settings: dict[str, Any] | None = None,
    constrain_settings: dict[str, Any] | None = None,
) -> Path:
    """Write an xcontrol file for advanced xTB settings.

    Args:
        output_path: Path to write the xcontrol file
        md_settings: Dict of MD settings (temp, time, dump, step, hmass, shake, etc.)
        opt_settings: Dict of optimization settings (optlevel, maxcycle, etc.)
        constrain_settings: Dict of constraint settings

    Returns:
        Path to written file
    """
    blocks = []

    if md_settings:
        lines = ["$md"]
        for key, value in md_settings.items():
            lines.append(f"   {key}={value}")
        lines.append("$end")
        blocks.append("\n".join(lines))

    if opt_settings:
        lines = ["$opt"]
        for key, value in opt_settings.items():
            lines.append(f"   {key}={value}")
        lines.append("$end")
        blocks.append("\n".join(lines))

    if constrain_settings:
        lines = ["$constrain"]
        for key, value in constrain_settings.items():
            if key == "atoms":
                # Atom list for constraints
                lines.append(f"   atoms: {value}")
            else:
                lines.append(f"   {key}={value}")
        lines.append("$end")
        blocks.append("\n".join(lines))

    content = "\n\n".join(blocks) + "\n"
    output_path.write_text(content)
    return output_path


def prepare_xtb_inputs(
    working_dir: Path,
    symbols: Sequence[str],
    positions: Sequence[Sequence[float]],
    params: dict[str, Any] | None = None,
) -> tuple[Path, list[str]]:
    """Prepare all input files and command for an xTB calculation.

    This is the main entry point for the input writer. It:
    1. Writes the input XYZ file
    2. Writes an xcontrol file if needed
    3. Builds the command line

    Args:
        working_dir: Directory to write input files
        symbols: Element symbols
        positions: Cartesian coordinates in Angstrom
        params: Calculation parameters dict with keys:
            - runtype: "sp", "opt", "grad", "hess", "ohess", "md"
            - gfn_level: 0, 1, 2, or -1 for GFN-FF
            - opt_level: optimization convergence level
            - charge: molecular charge
            - uhf: unpaired electrons
            - solvent: solvent name
            - solvent_model: "alpb" or "gbsa"
            - md_temp, md_time, md_step, md_dump: MD parameters
            - json_output: whether to produce JSON output

    Returns:
        Tuple of (input_xyz_path, command_list)
    """
    if params is None:
        params = {}

    working_dir.mkdir(parents=True, exist_ok=True)

    # Write structure
    input_path = write_xyz_file(symbols, positions, working_dir / "input.xyz")

    # Determine if we need an xcontrol file
    xcontrol_file = None
    md_settings = {}
    opt_settings = {}

    runtype = params.get("runtype", "opt")

    if runtype == "md":
        md_settings = {
            k: v for k, v in {
                "temp": params.get("md_temp", 300),
                "time": params.get("md_time", 1.0),
                "step": params.get("md_step", 1.0),
                "dump": params.get("md_dump", 50.0),
                "hmass": params.get("md_hmass", 4),
                "shake": params.get("md_shake", 1),
            }.items()
        }

    if params.get("opt_maxcycle"):
        opt_settings["maxcycle"] = params["opt_maxcycle"]

    if md_settings or opt_settings:
        xcontrol_path = working_dir / "xcontrol.inp"
        write_xcontrol(
            xcontrol_path,
            md_settings=md_settings or None,
            opt_settings=opt_settings or None,
        )
        xcontrol_file = "xcontrol.inp"

    # Build command
    cmd = build_xtb_command(
        input_file="input.xyz",
        runtype=runtype,
        gfn_level=params.get("gfn_level", 2),
        opt_level=params.get("opt_level"),
        charge=params.get("charge", 0),
        uhf=params.get("uhf", 0),
        solvent=params.get("solvent"),
        solvent_model=params.get("solvent_model", "alpb"),
        xcontrol_file=xcontrol_file,
        json_output=params.get("json_output", False),
    )

    return input_path, cmd


# ===========================================================================
# Standalone test
# ===========================================================================
if __name__ == "__main__":
    import tempfile

    print("=" * 60)
    print("xTB Input Writer Test")
    print("=" * 60)

    # Test 1: Simple optimization command
    print("\n--- Test 1: Simple Optimization ---")
    cmd = build_xtb_command(runtype="opt", gfn_level=2)
    print(f"  Command: {' '.join(cmd)}")
    assert cmd == ["xtb", "input.xyz", "--gfn", "2", "--opt"]
    print("  PASS")

    # Test 2: Tight optimization with solvation
    print("\n--- Test 2: Tight Opt + Solvation ---")
    cmd = build_xtb_command(
        runtype="opt", gfn_level=2, opt_level="tight",
        solvent="water", charge=-1,
    )
    print(f"  Command: {' '.join(cmd)}")
    assert "--opt" in cmd and "tight" in cmd
    assert "--alpb" in cmd and "water" in cmd
    assert "-c" in cmd and "-1" in cmd
    print("  PASS")

    # Test 3: XYZ file writing
    print("\n--- Test 3: XYZ File Writing ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        xyz_path = write_xyz_file(
            symbols=["O", "H", "H"],
            positions=[[0.0, 0.0, 0.117], [0.0, 0.757, -0.469], [0.0, -0.757, -0.469]],
            output_path=Path(tmpdir) / "test.xyz",
            comment="water molecule",
        )
        content = xyz_path.read_text()
        lines = content.strip().split("\n")
        assert lines[0].strip() == "3"
        assert lines[1] == "water molecule"
        assert "O" in lines[2]
        print(f"  Written to: {xyz_path}")
        print(f"  Content:\n{content}")
    print("  PASS")

    # Test 4: Full input preparation
    print("\n--- Test 4: Full Input Preparation ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path, cmd = prepare_xtb_inputs(
            working_dir=Path(tmpdir),
            symbols=["O", "H", "H"],
            positions=[[0.0, 0.0, 0.117], [0.0, 0.757, -0.469], [0.0, -0.757, -0.469]],
            params={"runtype": "opt", "gfn_level": 2, "opt_level": "tight"},
        )
        print(f"  Input: {input_path}")
        print(f"  Command: {' '.join(cmd)}")
        assert input_path.exists()
    print("  PASS")

    # Test 5: MD input preparation (with xcontrol)
    print("\n--- Test 5: MD Input Preparation ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path, cmd = prepare_xtb_inputs(
            working_dir=Path(tmpdir),
            symbols=["C", "C", "O", "H", "H", "H", "H", "H", "H"],
            positions=[
                [-0.748, 0.015, 0.024], [0.748, -0.015, -0.024],
                [1.168, 0.754, 1.101], [-1.148, 1.025, -0.094],
                [-1.098, -0.584, -0.822], [-1.138, -0.420, 0.956],
                [1.103, -1.045, 0.063], [1.126, 0.458, -0.944],
                [0.815, 0.268, 1.940],
            ],
            params={"runtype": "md", "md_temp": 300, "md_time": 0.5, "md_step": 1.0},
        )
        xcontrol_path = Path(tmpdir) / "xcontrol.inp"
        assert xcontrol_path.exists()
        print(f"  xcontrol content:\n{xcontrol_path.read_text()}")
        print(f"  Command: {' '.join(cmd)}")
        assert "-I" in cmd
    print("  PASS")

    # Test 6: GFN-FF
    print("\n--- Test 6: GFN-FF Command ---")
    cmd = build_xtb_command(runtype="opt", gfn_level=-1)
    print(f"  Command: {' '.join(cmd)}")
    assert "--gfnff" in cmd
    print("  PASS")

    print("\n" + "=" * 60)
    print("ALL INPUT WRITER TESTS PASSED")
    print("=" * 60)
