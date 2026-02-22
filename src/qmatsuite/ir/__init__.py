"""
IR (Intermediate Representation) module.

IR is a minimal rename/indirection layer that mediates between ParamSpace
and engine-specific parameter keys. In v0, IR is QE-equivalent (mostly same
names as QE keys) and exists ONLY to mediate ParamSpace ↔ QE parameter keys.

IR is NOT directly exposed to users in v0 (no user-facing editing or API);
it is an internal mediation layer.

IR Dialects:
- `ir.pw`: Plane-wave basis with periodic boundary conditions (PBC)
- `ir.qc`: Quantum chemistry with atomic orbitals (AO) and molecular systems (MOL)
"""

from qmatsuite.ir import dialects

__all__ = ["dialects"]

