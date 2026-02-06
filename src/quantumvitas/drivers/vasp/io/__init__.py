"""VASP input file I/O: pure text <-> dict mapping functions.

This module provides engine-specific parse/write functions for VASP input
files that have their own format (POSCAR, KPOINTS). INCAR uses the
flat-keyval family parser and is NOT handled here.

These are pure mapping functions (stdlib only, no pymatgen) that convert
between SSOT-compatible dicts and VASP-native text. They are kernel-internal
and not part of the public API facade.
"""

from quantumvitas.drivers.vasp.io.poscar import (
    write_poscar_text,
    parse_poscar_text,
)
from quantumvitas.drivers.vasp.io.kpoints import (
    write_kpoints_text,
    parse_kpoints_text,
)

__all__ = [
    "write_poscar_text",
    "parse_poscar_text",
    "write_kpoints_text",
    "parse_kpoints_text",
]
