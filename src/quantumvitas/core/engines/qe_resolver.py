"""Backward-compatibility re-export for qe_resolver (moved to drivers/qe/engine/)."""

from quantumvitas.drivers.qe.engine.qe_resolver import (
    resolve_qe_bin_dir,
    find_internal_qe_bin_dir,
    validate_qe_bin_dir,
)
# Compat re-export: tests monkeypatch this attribute
from quantumvitas.core.paths import home_qe_engines_dir

__all__ = ["resolve_qe_bin_dir", "find_internal_qe_bin_dir", "validate_qe_bin_dir", "home_qe_engines_dir"]

