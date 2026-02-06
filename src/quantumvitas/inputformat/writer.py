"""Engine input file writer orchestrator.

Routes SSOT data to per-file custom_writer functions based on content_role.
This module has NO imports from drivers/, core/, engine/, or calculation/.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quantumvitas.inputformat.core import EngineInputSpec


def write_engine_inputs(
    spec: EngineInputSpec,
    workdir: Path,
    params: dict[str, Any] | None = None,
    structure: dict[str, Any] | None = None,
) -> list[Path]:
    """Write engine input files to workdir from SSOT data.

    For each InputFileSpec in spec.input_files, extracts the appropriate
    data fragment based on content_role, calls the custom_writer, and
    writes the result to workdir/filename.

    Args:
        spec: Engine input specification declaring files to write.
        workdir: Directory to write files into (created if needed).
        params: Parameter dict from step.yaml engine_params.
        structure: StructureDoc dict with lattice/species/frac_coords.

    Returns:
        List of Paths to written files.

    Raises:
        NotImplementedError: If a file has no custom_writer (family writers
            are not yet implemented in Phase A).
        ValueError: If content_role is unrecognized.
    """
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []

    for file_spec in spec.input_files:
        # Extract the data fragment based on content_role
        fragment = _extract_fragment(
            file_spec.content_role, params, structure,
        )

        # Skip optional files when their data is empty
        if file_spec.optional and fragment is None:
            continue

        if file_spec.custom_writer is None:
            raise NotImplementedError(
                f"No custom_writer for '{file_spec.filename}' "
                f"(engine={spec.engine_family}). "
                f"Family writers are not yet implemented."
            )

        content = file_spec.custom_writer(fragment)
        out_path = workdir / file_spec.filename
        out_path.write_text(content)
        written.append(out_path)

    return written


def _extract_fragment(
    content_role: str,
    params: dict[str, Any] | None,
    structure: dict[str, Any] | None,
) -> Any:
    """Extract the data fragment for a given content_role.

    Returns:
        The fragment to pass to custom_writer, or None if data is missing.
    """
    if content_role == "parameters":
        return params
    elif content_role == "structure":
        return structure
    elif content_role == "kpoints":
        return params
    elif content_role == "combined":
        return {"params": params, "structure": structure}
    else:
        raise ValueError(f"Unknown content_role: {content_role!r}")
