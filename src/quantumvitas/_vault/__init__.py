"""
VAULT: Legacy code preserved for reference only.

DO NOT IMPORT FROM THIS MODULE.

This code exists solely for:
1. Historical reference during migration
2. Documentation of legacy patterns
3. Emergency debugging if needed

Production code must NEVER import from _vault.
"""

import os

def _vault_import_guard():
    """Raise ImportError on any vault import unless escape hatch is enabled."""
    # ChatGPT suggestion (S1): HARD FAIL by default, with env-var escape hatch
    if os.getenv("QMATSUITE_ALLOW_VAULT") != "1":
        raise ImportError(
            "Importing from quantumvitas._vault is prohibited. "
            "This module contains deprecated legacy code for reference only. "
            "Use quantumvitas.api.QVService for all production code. "
            "If you are migration tooling, set QMATSUITE_ALLOW_VAULT=1 as a temporary escape hatch."
        )

_vault_import_guard()

# Explicitly export nothing
__all__ = []

