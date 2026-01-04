"""
Allow running the PySCF runner as a module.

Usage:
    python -m quantumvitas.engines.pyscf job.json
"""

from .runner import main

if __name__ == "__main__":
    main()


