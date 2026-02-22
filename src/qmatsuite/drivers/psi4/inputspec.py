"""Psi4 engine input specification for the universal writer.

Psi4 is a Python-native engine — no external input files to write.
"""

from __future__ import annotations

from typing import Any

from qmatsuite.inputformat.core import EngineInputSpec


def get_psi4_input_spec(**context: Any) -> EngineInputSpec:
    """Return the Psi4 EngineInputSpec (empty — no input files)."""
    return EngineInputSpec(
        engine_family="psi4",
        syntax_family="python-script",
        input_files=(),
    )
