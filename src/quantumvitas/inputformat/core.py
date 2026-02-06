"""Core data types for the universal input format system.

All types are frozen dataclasses. This module has NO imports from
drivers/, core/, engine/, or calculation/ — it is a leaf dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class InputFileSpec:
    """Specification for a single engine input file.

    Attributes:
        filename: Output filename (e.g., "INCAR", "pw.in").
        content_role: What SSOT data this file encodes.
            "parameters" — custom_writer receives params dict.
            "structure" — custom_writer receives structure dict.
            "kpoints" — custom_writer receives params dict (writer extracts kpoints subset).
            "combined" — custom_writer receives {"params": params, "structure": structure}.
        description: Human-readable description of this file.
        optional: If True, skip this file when its data fragment is empty/None.
        custom_writer: Callable(fragment) -> str. Returns file content as text.
            Required in Phase A (no family writers yet).
        custom_parser: Callable(text) -> dict. Parses file content. Optional.
    """

    filename: str
    content_role: str
    description: str = ""
    optional: bool = False
    custom_writer: Optional[Callable[..., str]] = None
    custom_parser: Optional[Callable[..., dict]] = None

    def __post_init__(self):
        if self.content_role not in (
            "parameters", "structure", "kpoints", "combined",
        ):
            raise ValueError(
                f"Invalid content_role '{self.content_role}'. "
                "Must be one of: parameters, structure, kpoints, combined"
            )


@dataclass(frozen=True)
class ResourceRefSpec:
    """Specification for a staged external file (not parsed/written).

    Examples: pseudopotentials, force-field files, wavefunction HDF5.

    Attributes:
        name: Identifier (e.g., "potcar", "pseudopotentials").
        description: Human-readable description.
        staging_policy: How to stage: "copy", "symlink", "reference".
        source: Where to find the resource (engine-specific).
    """

    name: str
    description: str = ""
    staging_policy: str = "copy"
    source: str = ""


@dataclass(frozen=True)
class SSOTMappingSpec:
    """Describes which SSOT fields map to which input files.

    Attributes:
        structure_in: Filename(s) that embed structure data.
        kpoints_in: Filename(s) that embed k-point data.
        params_in: Filename(s) that embed calculation parameters.
    """

    structure_in: tuple[str, ...] = ()
    kpoints_in: tuple[str, ...] = ()
    params_in: tuple[str, ...] = ()


@dataclass(frozen=True)
class EngineInputSpec:
    """Complete input format specification for one engine.

    This is the per-engine declaration that tells the write_engine_inputs
    orchestrator what files to produce and how.

    Phase A fields only — no DialectSpec, hooks, metadata_source, or
    corpus_config (those are future phases).

    Attributes:
        engine_family: Engine identifier (e.g., "vasp", "qe").
        syntax_family: Syntax family ID (e.g., "flat-keyval", "fortran-namelist").
        input_files: Tuple of InputFileSpec — files to write.
        resource_refs: Tuple of ResourceRefSpec — files to stage.
        ssot_mapping: Which SSOT fields map where.
    """

    engine_family: str
    syntax_family: str
    input_files: tuple[InputFileSpec, ...] = ()
    resource_refs: tuple[ResourceRefSpec, ...] = ()
    ssot_mapping: SSOTMappingSpec = field(default_factory=SSOTMappingSpec)
