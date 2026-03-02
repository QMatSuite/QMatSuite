"""MACE input writer.

Generates Python scripts that set up ASE Atoms + MACE calculator
and execute the calculation. Thin wrapper around io/mace_script.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .io.mace_script import write_mace_script_text


def write_mace_script(
    gen_type: str,
    params: dict[str, Any],
    output_path: Path,
    structure_file: str = "structure.json",
) -> Path:
    """Generate a MACE calculation Python script.

    Args:
        gen_type: Generalized step type (scf, relax, md).
        params: Step parameters dict.
        output_path: Path to write the generated script.
        structure_file: Path to structure file (relative to working dir).

    Returns:
        The output_path.
    """
    script = write_mace_script_text(gen_type, params, structure_file)
    output_path.write_text(script)
    return output_path
