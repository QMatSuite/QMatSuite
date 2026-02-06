"""PySCF engine input specification for the universal writer.

PySCF is a Python-native engine — no external input files to write.
"""

from __future__ import annotations

from typing import Any

from quantumvitas.inputformat.core import EngineInputSpec


def get_pyscf_input_spec(**context: Any) -> EngineInputSpec:
    """Return the PySCF EngineInputSpec (empty — no input files)."""
    return EngineInputSpec(
        engine_family="pyscf",
        syntax_family="python-script",
        input_files=(),
    )
