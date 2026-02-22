"""VASP input file I/O: pure text <-> dict mapping functions.

This module provides engine-specific parse/write functions for VASP input
files (INCAR, POSCAR, KPOINTS).

These are pure mapping functions (stdlib only, no pymatgen) that convert
between SSOT-compatible dicts and VASP-native text. They are kernel-internal
and not part of the public API facade.
"""

from qmatsuite.drivers.vasp.io.incar import parse_incar_text, write_incar_text
from qmatsuite.drivers.vasp.io.poscar import (
    write_poscar_text,
    parse_poscar_text,
)
from qmatsuite.drivers.vasp.io.kpoints import (
    write_kpoints_text,
    parse_kpoints_text,
)

__all__ = [
    "parse_incar_text",
    "write_incar_text",
    "write_poscar_text",
    "parse_poscar_text",
    "write_kpoints_text",
    "parse_kpoints_text",
]
