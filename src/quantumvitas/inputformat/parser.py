"""Engine input file parser orchestrator.

Routes workdir files through per-file custom_parser functions based on content_role.
Produces a unified ParseResult with params, structure, and diagnostics.

This module has NO imports from drivers/, core/, engine/, or calculation/.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from quantumvitas.inputformat.core import EngineInputSpec


@dataclass(frozen=True)
class Diagnostic:
    """Parser diagnostic message.

    Attributes:
        level: Severity — "info", "warning", or "error".
        message: Human-readable description.
        file: Filename that produced this diagnostic.
        line: Line number (1-based), or None if unknown.
        code: Machine-readable code (e.g., "unrecognized_line").
    """

    level: str
    message: str
    file: str
    line: int | None = None
    code: str = ""


@dataclass
class ParseResult:
    """Unified result from parsing all engine input files.

    Mutable because the orchestrator builds it incrementally via
    per-file merges.

    Attributes:
        params: Recovered calculation parameters (from step.yaml engine_params).
        structure: Recovered StructureDoc dict, or None if no structure file.
        diagnostics: Warnings/errors produced during parsing.
    """

    params: dict[str, Any] = field(default_factory=dict)
    structure: dict[str, Any] | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)


def parse_engine_inputs(
    spec: EngineInputSpec,
    workdir: Path,
) -> ParseResult:
    """Parse engine input files from workdir into unified SSOT-compatible result.

    For each InputFileSpec in spec.input_files:
      1. Read the file from workdir.
      2. Dispatch to custom_parser.
      3. Merge result into unified ParseResult based on content_role.

    Args:
        spec: Engine input specification declaring files to parse.
        workdir: Directory containing engine input files.

    Returns:
        ParseResult with params dict, optional structure dict, and diagnostics.

    Raises:
        NotImplementedError: If a file has no custom_parser.
        FileNotFoundError: If a non-optional file is missing from workdir.
    """
    workdir = Path(workdir)
    result = ParseResult()

    for file_spec in spec.input_files:
        file_path = workdir / file_spec.filename

        if not file_path.exists():
            if file_spec.optional:
                result.diagnostics.append(
                    Diagnostic(
                        level="info",
                        message=f"Optional file not found: {file_spec.filename}",
                        file=file_spec.filename,
                        code="optional_file_missing",
                    )
                )
                continue
            raise FileNotFoundError(
                f"Required file not found: {file_path}"
            )

        if file_spec.custom_parser is None:
            raise NotImplementedError(
                f"No custom_parser for '{file_spec.filename}' "
                f"(engine={spec.engine_family}). "
                f"Family parsers are not yet implemented."
            )

        text = file_path.read_text()
        parsed = file_spec.custom_parser(text)

        _merge_parsed(result, file_spec.content_role, parsed, file_spec.filename)

    return result


def _merge_parsed(
    result: ParseResult,
    content_role: str,
    parsed: dict[str, Any],
    filename: str,
) -> None:
    """Merge a per-file parse result into the unified ParseResult.

    Dispatch rules mirror _extract_fragment in writer.py:
      - "parameters" → update result.params
      - "structure"  → set result.structure
      - "kpoints"    → inject into result.params["kpoints"]
      - "combined"   → update both params and structure
    """
    if content_role == "parameters":
        result.params.update(parsed)
    elif content_role == "structure":
        result.structure = parsed
    elif content_role == "kpoints":
        result.params["kpoints"] = parsed
    elif content_role == "combined":
        if "params" in parsed:
            result.params.update(parsed["params"])
        if "structure" in parsed:
            result.structure = parsed["structure"]
    else:
        raise ValueError(f"Unknown content_role: {content_role!r}")
