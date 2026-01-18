"""
Unified canonicalization for Structure and Molecule.

This module provides the ONLY place where geometry transforms happen.
Called at import/read/parse time.
"""

from __future__ import annotations

import numpy as np
from pymatgen.core import Structure as PMGStructure
from pymatgen.core import Molecule as PMGMolecule
from typing import Union

from quantumvitas.analysis.structure_viz import canonicalize_structure_in_place


def canonicalize_structure_like_in_place(obj: Union[PMGStructure, PMGMolecule]) -> None:
    """
    Canonicalize a structure-like object in place.
    
    For Structure: wraps frac coords to [-WRAP_TOL, 1-WRAP_TOL)
    For Molecule: centers at origin (COG shift)
    
    This is the ONLY place geometry transforms happen.
    Must be called at import/read/parse time BEFORE fingerprinting.
    
    Args:
        obj: pymatgen Structure or Molecule (modified in place)
    """
    if isinstance(obj, PMGMolecule):
        _canonicalize_molecule_in_place(obj)
    elif isinstance(obj, PMGStructure):
        canonicalize_structure_in_place(obj)  # existing function
    # else: pass silently for other types (or raise TypeError if strict)


def _canonicalize_molecule_in_place(molecule: PMGMolecule) -> None:
    """
    Canonicalize a Molecule by centering at origin (COG shift).
    
    Computes center-of-geometry and subtracts from all positions.
    This ensures translation invariance for fingerprinting.
    
    Args:
        molecule: pymatgen Molecule (modified in place)
    """
    if len(molecule) == 0:
        return
    
    # Compute center-of-geometry
    coords = np.array([site.coords for site in molecule])
    cog = coords.mean(axis=0)
    
    # Shift all sites by -COG using translate_sites
    # translate_sites takes indices and a vector, translates all specified sites
    molecule.translate_sites(list(range(len(molecule))), -cog)

