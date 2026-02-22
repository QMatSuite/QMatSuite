"""Engine driver bundles.

This package contains all engine driver implementations.
Drivers are registered with the DriverRegistry at import time.

To ensure all drivers are registered, import this package:
    import qmatsuite.drivers

Or import specific drivers:
    from qmatsuite.drivers import qe
"""

import logging

logger = logging.getLogger(__name__)

# Import all driver packages to trigger registration
# Each driver's __init__.py calls DriverRegistry.register()

# QE driver (migrated)
from qmatsuite.drivers import qe

# VASP driver (migrated)
from qmatsuite.drivers import vasp

# LAMMPS driver (migrated)
from qmatsuite.drivers import lammps

# CP2K driver (migrated)
from qmatsuite.drivers import cp2k

# Wannier90 driver (migrated)
from qmatsuite.drivers import w90

# ORCA driver (migrated)
from qmatsuite.drivers import orca

# PySCF driver (migrated)
from qmatsuite.drivers import pyscf

# QMCPACK driver
from qmatsuite.drivers import qmcpack

# Psi4 driver
from qmatsuite.drivers import psi4

# GPAW driver
from qmatsuite.drivers import gpaw

# Siesta driver
from qmatsuite.drivers import siesta

# xTB driver
from qmatsuite.drivers import xtb

# Yambo driver (MBPT: GW, BSE, TDDFT)
from qmatsuite.drivers import yambo

# ABINIT driver (plane-wave DFT)
from qmatsuite.drivers import abinit

# Gaussian driver (molecular quantum chemistry)
from qmatsuite.drivers import gaussian

# Note: All major drivers have been migrated

logger.debug("Driver packages imported")

