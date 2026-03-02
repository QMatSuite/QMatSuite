"""MACE engine input specification for the universal writer.

Two files: {gen_type}.py (Python script) and structure.json (structure).
Dynamic filename resolved via get_mace_input_spec(gen_type=...).
"""

from __future__ import annotations

import json
from typing import Any

from qmatsuite.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    SSOTMappingSpec,
)


def _write_mace_script_text(fragment: dict[str, Any]) -> str:
    """Write MACE Python script from combined params + structure."""
    params = fragment.get("params") or {}
    gen_type = params.get("gen_type", "scf")
    structure_file = params.get("structure_file", "structure.json")

    from qmatsuite.drivers.mace.io.mace_script import write_mace_script_text
    return write_mace_script_text(gen_type, params, structure_file)


def _write_structure_json(structure: dict[str, Any] | None) -> str:
    """Write structure as JSON for MACE to read."""
    if not structure:
        return "{}"
    return json.dumps(structure, indent=2) + "\n"


def get_mace_input_spec(**context: Any) -> EngineInputSpec:
    """Return the MACE EngineInputSpec.

    Args:
        **context: May contain gen_type for dynamic filename.
    """
    gen_type = context.get("gen_type", "scf")
    script_filename = f"{gen_type}.py"

    return EngineInputSpec(
        engine_family="mace",
        syntax_family="python-script",
        input_files=(
            InputFileSpec(
                filename=script_filename,
                content_role="combined",
                description="MACE Python calculation script",
                custom_writer=_write_mace_script_text,
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
