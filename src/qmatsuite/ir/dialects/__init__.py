"""
IR Dialects module.

IR dialects represent computational paradigms, not specific engines:
- `ir.pw`: Plane-wave basis with periodic boundary conditions (PBC)
- `ir.qc`: Quantum chemistry with atomic orbitals (AO) and molecular systems (MOL)

Dialects are disjoint namespaces; do not mix `ir.pw` and `ir.qc` keys.
"""

from qmatsuite.ir.dialects import pw, qc

__all__ = ["pw", "qc"]

