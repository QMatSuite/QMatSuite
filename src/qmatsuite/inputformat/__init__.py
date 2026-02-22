"""Universal engine input format package.

This package provides engine-agnostic types and orchestration for writing
and parsing engine input files from SSOT data. It is a leaf package with
NO imports from drivers/, core/, engine/, or calculation/.
"""

from qmatsuite.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    ResourceRefSpec,
    SSOTMappingSpec,
)
from qmatsuite.inputformat.parser import (
    Diagnostic,
    ParseResult,
    parse_engine_inputs,
)
from qmatsuite.inputformat.writer import write_engine_inputs

__all__ = [
    "Diagnostic",
    "EngineInputSpec",
    "InputFileSpec",
    "ParseResult",
    "ResourceRefSpec",
    "SSOTMappingSpec",
    "parse_engine_inputs",
    "write_engine_inputs",
]
