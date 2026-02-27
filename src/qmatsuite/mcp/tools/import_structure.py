"""import_structure tool — import a structure from file path or inline content."""

from __future__ import annotations

import tempfile
from pathlib import Path

from qmatsuite.mcp.app import mcp
from qmatsuite.mcp.envelope import make_error, make_response

# Format → tempfile extension mapping
_FORMAT_EXT: dict[str, str] = {
    "cif": ".cif",
    "poscar": ".vasp",
    "vasp": ".vasp",
    "xyz": ".xyz",
    "json": ".json",
    "qe": ".in",
}


def _unescape_content(text: str) -> str:
    """Decode double-encoded escape sequences from MCP JSON transport.

    If the text contains literal backslash-n but no real newlines,
    decode common C escape sequences. If real newlines already exist,
    leave the text untouched.
    """
    if "\n" not in text and "\\n" in text:
        text = (
            text
            .replace("\\r\\n", "\r\n")
            .replace("\\n", "\n")
            .replace("\\r", "\r")
            .replace("\\t", "\t")
        )
    return text


@mcp.tool
def import_structure(
    file_path: str = "",
    file_content: str = "",
    format: str = "cif",
    name: str = "",
) -> dict:
    """Import a structure into the current project.

    Two modes:

    1. **From file**: provide ``file_path`` pointing to a CIF / POSCAR /
       XYZ / JSON / QE-input file on disk.
    2. **From content**: provide ``file_content`` (the raw text) and
       ``format`` (one of cif, poscar, xyz, json, qe).

    At least one of ``file_path`` or ``file_content`` must be given.

    Args:
        file_path: Path to a structure file on disk.
        file_content: Raw file content as a string.
        format: File format when using ``file_content`` (default 'cif').
            One of: cif, poscar, vasp, xyz, json, qe.
        name: Optional human-readable name for the structure.
    """
    from qmatsuite.mcp.project import ProjectNotFoundError, get_service

    try:
        svc = get_service()
    except ProjectNotFoundError as exc:
        return make_error("no_project", str(exc))

    # --- resolve source path ---
    tmp_file = None
    if file_path:
        source = Path(file_path)
        if not source.exists():
            return make_error(
                "not_found",
                f"File not found: {file_path}",
            )
    elif file_content:
        file_content = _unescape_content(file_content)
        fmt = format.lower()
        ext = _FORMAT_EXT.get(fmt, ".cif")
        tmp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=ext, delete=False,
        )
        tmp_file.write(file_content)
        tmp_file.flush()
        tmp_file.close()
        source = Path(tmp_file.name)
    else:
        return make_error(
            "missing_input",
            "Provide either file_path or file_content.",
        )

    # --- import ---
    try:
        dto = svc.structure.import_file(
            source=source,
            name=name or None,
            format="auto",
        )
    except Exception as exc:
        # Clean up temp file on failure
        if tmp_file is not None:
            Path(tmp_file.name).unlink(missing_ok=True)
        msg = str(exc)
        fmt_lower = format.lower() if format else ""
        is_cif = "cif" in fmt_lower or (file_path and file_path.endswith(".cif"))
        if is_cif:
            hint = (
                "CIF parse failed. Common issues: missing _atom_site_label column, "
                "missing _cell_length_a, or incorrect symmetry tags. "
                "Try POSCAR format for simple crystals, or use search_demos() "
                "to find calculations with pre-configured structures."
            )
        else:
            hint = (
                "Check the structure file format. Use search_demos() "
                "to find calculations with pre-configured structures."
            )
        return make_error("import_failed", f"Failed to import structure: {msg}", context_hint=hint)
    finally:
        # Always clean up temp file
        if tmp_file is not None:
            Path(tmp_file.name).unlink(missing_ok=True)

    ulid = dto.structure_ulid
    return make_response(
        {
            "structure_ulid": ulid,
            "name": dto.name,
            "formula": dto.formula,
            "n_atoms": dto.num_atoms,
            "space_group": dto.space_group,
            "cell_volume_ang3": dto.cell_volume_ang3,
            "lattice_abc": dto.lattice_abc,
            "lattice_angles": dto.lattice_angles,
        },
        context_hint=(
            f"Structure imported. Use create_calculation("
            f"structure_ulid='{ulid}', engine='...', workflow='...') "
            f"to start a calculation."
        ),
    )
