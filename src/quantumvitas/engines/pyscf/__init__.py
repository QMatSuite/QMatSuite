"""
PySCF subprocess runner package.

This module is executed via subprocess, NOT imported by the daemon.
It contains the logic that actually imports and runs PySCF.

Usage:
    python -m quantumvitas.engines.pyscf.runner job.json
"""


