"""GPAW engine input specification for the universal writer.

Two files: {gen_type}.py (Python script) and structure.json (structure).
Dynamic filename resolved via get_input_spec(gen_type=...).
"""

from __future__ import annotations

from typing import Any
import json

from quantumvitas.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    SSOTMappingSpec,
)


def _write_gpaw_script_text(fragment: dict[str, Any]) -> str:
    """Write GPAW Python script from combined params + structure.

    Delegates to the existing write_gpaw_script logic but returns
    text instead of writing to a file.
    """
    params = fragment.get("params") or {}
    structure = fragment.get("structure") or {}

    gen_type = params.get("gen_type", "scf")
    structure_file = params.get("structure_file", "structure.json")
    restart_from = params.get("restart_from")

    try:
        from quantumvitas.drivers.gpaw.writer import write_gpaw_script
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            tmp_path = Path(f.name)
        write_gpaw_script(gen_type, params, tmp_path, structure_file, restart_from)
        content = tmp_path.read_text()
        tmp_path.unlink()
        return content
    except ImportError:
        pass

    # Fallback: generate minimal GPAW script
    lines = [
        "from ase.io import read",
        "from gpaw import GPAW, PW",
        "",
        f"atoms = read('{structure_file}')",
        "",
    ]

    mode = params.get("mode", "PW(300)")
    xc = params.get("xc", "PBE")
    kpts = params.get("kpts", {"size": (4, 4, 4)})

    lines.append(f"calc = GPAW(mode={mode},")
    lines.append(f"            xc='{xc}',")
    if isinstance(kpts, dict):
        lines.append(f"            kpts={kpts},")
    lines.append(f"            txt='{gen_type}.txt')")
    lines.append("")
    lines.append("atoms.calc = calc")
    lines.append("energy = atoms.get_potential_energy()")
    lines.append(f"print(f'Energy: {{energy}} eV')")

    return "\n".join(lines) + "\n"


def _write_structure_json(structure: dict[str, Any] | None) -> str:
    """Write structure as JSON for GPAW to read."""
    if not structure:
        return "{}"
    return json.dumps(structure, indent=2) + "\n"


def get_gpaw_input_spec(**context: Any) -> EngineInputSpec:
    """Return the GPAW EngineInputSpec.

    Args:
        **context: May contain gen_type for dynamic filename.
    """
    gen_type = context.get("gen_type", "scf")
    script_filename = f"{gen_type}.py"

    return EngineInputSpec(
        engine_family="gpaw",
        syntax_family="python-script",
        input_files=(
            InputFileSpec(
                filename=script_filename,
                content_role="combined",
                description="GPAW Python calculation script",
                custom_writer=_write_gpaw_script_text,
            ),
            InputFileSpec(
                filename="structure.json",
                content_role="structure",
                description="Structure data in JSON format",
                custom_writer=_write_structure_json,
            ),
        ),
        ssot_mapping=SSOTMappingSpec(
            structure_in=("structure.json",),
            params_in=(script_filename,),
        ),
    )
