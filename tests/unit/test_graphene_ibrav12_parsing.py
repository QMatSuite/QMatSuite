"""
Unit tests for ibrav=12/-12 structure parsing (monoclinic lattices).

Tests that graphene structure (ibrav=12) is correctly parsed and converted
to a valid lattice.
"""

import pytest
import numpy as np
from pathlib import Path
from pymatgen.core import Lattice, Structure

from quantumvitas.io.parser.qe_parser import QEInputParser
from quantumvitas.io.structure_io import (
    structure_from_qe_input,
    _get_system_namelist,
    _extract_ibrav_parameters,
    _ibrav_vectors,
)


# Repo root for test data
REPO_ROOT = Path(__file__).parent.parent.parent
GRAPHENE_INPUT = REPO_ROOT / "tests" / "data" / "13_graphene" / "graphene.1_vc_relax.in"


def test_graphene_input_has_correct_system_parameters():
    """Test that graphene input file has expected SYSTEM parameters."""
    qe_input = QEInputParser.parse_file(GRAPHENE_INPUT)
    system_dict = _get_system_namelist(qe_input)
    
    assert system_dict is not None
    assert system_dict.get("ibrav") == 12
    assert abs(system_dict.get("a", 0) - 2.46) < 1e-3
    assert abs(system_dict.get("b", 0) - 2.46) < 1e-3
    assert abs(system_dict.get("c", 0) - 20.0) < 1e-3
    assert abs(system_dict.get("cosab", 0) - (-0.5)) < 1e-3


def test_extract_ibrav_parameters_for_graphene():
    """Test that ibrav parameters are correctly extracted from graphene input."""
    qe_input = QEInputParser.parse_file(GRAPHENE_INPUT)
    system_dict = _get_system_namelist(qe_input)
    params = _extract_ibrav_parameters(system_dict)
    
    assert params.get("a") is not None
    assert abs(params["a"] - 2.46) < 1e-3
    assert params.get("b") is not None
    assert abs(params["b"] - 2.46) < 1e-3
    assert params.get("c") is not None
    assert abs(params["c"] - 20.0) < 1e-3
    assert params.get("cosab") is not None
    assert abs(params["cosab"] - (-0.5)) < 1e-3


def test_ibrav12_vectors_for_graphene():
    """Test that ibrav=12 generates correct lattice vectors for graphene."""
    qe_input = QEInputParser.parse_file(GRAPHENE_INPUT)
    system_dict = _get_system_namelist(qe_input)
    params = _extract_ibrav_parameters(system_dict)
    
    vectors = _ibrav_vectors(12, params)
    
    assert len(vectors) == 3
    assert len(vectors[0]) == 3
    assert len(vectors[1]) == 3
    assert len(vectors[2]) == 3
    
    # v1 = (a, 0, 0)
    assert abs(vectors[0][0] - 2.46) < 1e-3
    assert abs(vectors[0][1]) < 1e-6
    assert abs(vectors[0][2]) < 1e-6
    
    # v2 = (b*cos(gamma), b*sin(gamma), 0) where cos(gamma) = -0.5
    # cos(120°) = -0.5, sin(120°) = sqrt(3)/2
    expected_v2_x = 2.46 * (-0.5)  # = -1.23
    expected_v2_y = 2.46 * (np.sqrt(3) / 2)  # ≈ 2.130
    assert abs(vectors[1][0] - expected_v2_x) < 1e-3
    assert abs(vectors[1][1] - expected_v2_y) < 1e-3
    assert abs(vectors[1][2]) < 1e-6
    
    # v3 = (0, 0, c)
    assert abs(vectors[2][0]) < 1e-6
    assert abs(vectors[2][1]) < 1e-6
    assert abs(vectors[2][2] - 20.0) < 1e-3


def test_graphene_structure_creation():
    """Test that graphene input file can be parsed into a valid Structure."""
    qe_input = QEInputParser.parse_file(GRAPHENE_INPUT)
    struct = structure_from_qe_input(qe_input)
    
    assert struct is not None
    assert len(struct) == 2  # 2 carbon atoms
    assert all(site.specie.symbol == "C" for site in struct)
    
    # Verify lattice vectors
    lattice = struct.lattice
    matrix = lattice.matrix
    
    # v1 = (a, 0, 0)
    assert abs(matrix[0, 0] - 2.46) < 1e-3
    assert abs(matrix[0, 1]) < 1e-6
    assert abs(matrix[0, 2]) < 1e-6
    
    # v2 = (b*cos(120°), b*sin(120°), 0)
    expected_v2_x = 2.46 * (-0.5)  # -1.23
    expected_v2_y = 2.46 * (np.sqrt(3) / 2)  # ≈ 2.130
    assert abs(matrix[1, 0] - expected_v2_x) < 1e-3
    assert abs(matrix[1, 1] - expected_v2_y) < 1e-3
    assert abs(matrix[1, 2]) < 1e-6
    
    # v3 = (0, 0, c)
    assert abs(matrix[2, 0]) < 1e-6
    assert abs(matrix[2, 1]) < 1e-6
    assert abs(matrix[2, 2] - 20.0) < 1e-3


def test_ibrav12_case_insensitive_parameters():
    """Test that parameter names are case-insensitive (A, B, C, cosAB, etc.)."""
    from quantumvitas.io.model import QEInput, QENamelist
    
    # Create a QE input with uppercase parameter names
    system_namelist = QENamelist(
        name="SYSTEM",
        parameters={
            "ibrav": 12,
            "A": 2.46,  # uppercase
            "B": 2.46,  # uppercase
            "C": 20.0,  # uppercase
            "COSAB": -0.5,  # uppercase
        },
    )
    qe_input = QEInput(namelists=[system_namelist])
    
    system_dict = _get_system_namelist(qe_input)
    assert system_dict is not None
    assert abs(system_dict.get("a", 0) - 2.46) < 1e-3
    assert abs(system_dict.get("b", 0) - 2.46) < 1e-3
    assert abs(system_dict.get("c", 0) - 20.0) < 1e-3
    assert abs(system_dict.get("cosab", 0) - (-0.5)) < 1e-3


def test_ibrav_minus12_uses_cosac():
    """Test that ibrav=-12 correctly uses cosac (not cosab)."""
    from quantumvitas.io.model import QEInput, QENamelist
    
    # ibrav=-12: Monoclinic, unique axis b, uses cos(beta) = cos(angle between a and c)
    system_namelist = QENamelist(
        name="SYSTEM",
        parameters={
            "ibrav": -12,
            "a": 5.0,
            "b": 6.0,
            "c": 7.0,
            "cosac": 0.5,  # cos(60°) between a and c
        },
    )
    qe_input = QEInput(namelists=[system_namelist])
    
    system_dict = _get_system_namelist(qe_input)
    params = _extract_ibrav_parameters(system_dict)
    vectors = _ibrav_vectors(-12, params)
    
    assert len(vectors) == 3
    # v1 = (a, 0, 0)
    assert abs(vectors[0][0] - 5.0) < 1e-3
    # v2 = (0, b, 0)
    assert abs(vectors[1][1] - 6.0) < 1e-3
    # v3 = (c*cos(beta), 0, c*sin(beta))
    # cos(beta) = 0.5, sin(beta) = sqrt(3)/2
    expected_v3_x = 7.0 * 0.5  # 3.5
    expected_v3_z = 7.0 * (np.sqrt(3) / 2)  # ≈ 6.062
    assert abs(vectors[2][0] - expected_v3_x) < 1e-3
    assert abs(vectors[2][2] - expected_v3_z) < 1e-3

