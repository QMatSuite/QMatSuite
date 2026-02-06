"""Universal engine input format package.

This package provides engine-agnostic types and orchestration for writing
engine input files from SSOT data. It is a leaf package with NO imports
from drivers/, core/, engine/, or calculation/.

Phase A: custom_writer-based dispatch only (no family writers yet).
"""

from quantumvitas.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    ResourceRefSpec,
    SSOTMappingSpec,
)
from quantumvitas.inputformat.writer import write_engine_inputs

__all__ = [
    "EngineInputSpec",
    "InputFileSpec",
    "ResourceRefSpec",
    "SSOTMappingSpec",
    "write_engine_inputs",
]
