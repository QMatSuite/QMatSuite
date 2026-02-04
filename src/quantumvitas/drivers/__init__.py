"""Engine driver bundles.

This package contains all engine driver implementations.
Drivers are registered with the DriverRegistry at import time.

To ensure all drivers are registered, import this package:
    import quantumvitas.drivers

Or import specific drivers:
    from quantumvitas.drivers import qe
"""

import logging

logger = logging.getLogger(__name__)

# Import all driver packages to trigger registration
# Each driver's __init__.py calls DriverRegistry.register()

# QE driver (migrated)
from quantumvitas.drivers import qe

# VASP driver (migrated)
from quantumvitas.drivers import vasp

# LAMMPS driver (migrated)
from quantumvitas.drivers import lammps

# CP2K driver (migrated)
from quantumvitas.drivers import cp2k

# Wannier90 driver (migrated)
from quantumvitas.drivers import w90

# ORCA driver (migrated)
from quantumvitas.drivers import orca

# PySCF driver (migrated)
from quantumvitas.drivers import pyscf

# QMCPACK driver
from quantumvitas.drivers import qmcpack

# Psi4 driver
from quantumvitas.drivers import psi4

# GPAW driver
from quantumvitas.drivers import gpaw

# Siesta driver
from quantumvitas.drivers import siesta

# Note: All major drivers have been migrated

logger.debug("Driver packages imported")

