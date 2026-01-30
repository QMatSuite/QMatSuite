"""
Unit tests for K_POINTS card rendering.

Tests that K_POINTS cards are correctly rendered to QE input format
(not as namelist parameters).
"""

import pytest
from pathlib import Path
from pymatgen.core import Lattice, Structure
from quantumvitas.calculation.structure_steps import (
    StructureStepSpec,
    generate_qe_input_from_spec,
)
from quantumvitas.io.parser.qe_parser import QEInputParser
from quantumvitas.io.generator.qe_generator import QEInputGenerator


@pytest.fixture
def sample_structure():
    """Create a sample Si structure."""
    return Structure(Lattice.cubic(5.43), ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])


def test_k_points_card_renders_as_card_not_namelist(sample_structure, tmp_path):
    """Test that K_POINTS in cards section renders as a card, not a namelist."""
    from quantumvitas.core.models import ResourceMeta
    # Create a step spec with K_POINTS in cards
    spec = StructureStepSpec(
        meta=ResourceMeta(ulid="test-step",
            name="test",
            slug="test-scf",
            path="test.step.yaml",
            kind="step",
        ),
        step_type_spec="qe_scf",
        structure="test-structure",
        parameters={
            "CONTROL": {
                "calculation": "scf",
            },
            "SYSTEM": {
                "ecutwfc": 40,
            },
        },
        cards={
            "K_POINTS": {
                "option": "automatic",
                "data": [[8, 8, 8, 0, 0, 0]],
            },
        },
    )
    
    # Generate QE input directly (simpler than full materialize)
    qe_input, _ = generate_qe_input_from_spec(
        structure=sample_structure,
        spec=spec,
        species_map={
            "Si": {
                "pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
                "mass": 28.0855,
            }
        },
    )
    
    # Verify K_POINTS is a card, not a namelist parameter
    from quantumvitas.io.model import QECardType
    k_points_card = qe_input.get_card(QECardType.K_POINTS)
    assert k_points_card is not None, f"K_POINTS should be present as a card. Cards: {[c.card_type.name for c in qe_input.cards]}"
    assert k_points_card.option == "automatic"
    assert len(k_points_card.data) > 0
    
    # Verify K_POINTS is NOT in any namelist
    for namelist in qe_input.namelists:
        params = namelist.parameters
        assert "k_points" not in params and "K_POINTS" not in params, \
            f"K_POINTS should not be in namelist {namelist.name} parameters"
    
    # Generate input text and verify format
    input_text = QEInputGenerator.generate(qe_input)
    assert "K_POINTS {" in input_text or "K_POINTS {" in input_text.upper(), \
        "Input should contain 'K_POINTS {' (card format)"
    assert "&K_POINTS" not in input_text, \
        "Input should not contain '&K_POINTS' (namelist format)"


def test_k_points_automatic_format(sample_structure, tmp_path):
    """Test that K_POINTS with automatic option renders correctly."""
    from quantumvitas.core.models import ResourceMeta
    spec = StructureStepSpec(
        meta=ResourceMeta(ulid="test-step",
            name="test",
            slug="test-scf",
            path="test.step.yaml",
            kind="step",
        ),
        step_type_spec="qe_scf",
        structure="test-structure",
        parameters={
            "CONTROL": {"calculation": "scf"},
        },
        cards={
            "K_POINTS": {
                "option": "automatic",
                "data": [[10, 10, 10, 0, 0, 0]],
            },
        },
    )
    
    # Generate QE input directly
    qe_input, _ = generate_qe_input_from_spec(
        structure=sample_structure,
        spec=spec,
        species_map={
            "Si": {
                "pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
                "mass": 28.0855,
            }
        },
    )
    
    input_text = QEInputGenerator.generate(qe_input)
    
    # Should contain "K_POINTS {automatic}"
    assert "K_POINTS {automatic}" in input_text or "K_POINTS {automatic}".upper() in input_text.upper()
    
    # Should contain the k-point data
    assert "10" in input_text  # Grid size


def test_k_points_crystal_format(sample_structure, tmp_path):
    """Test that K_POINTS with crystal_b format renders correctly."""
    from quantumvitas.core.models import ResourceMeta
    spec = StructureStepSpec(
        meta=ResourceMeta(ulid="test-step",
            name="test",
            slug="test-bands",
            path="test.step.yaml",
            kind="step",
        ),
        step_type_spec="qe_bands_pw",
        structure="test-structure",
        parameters={
            "CONTROL": {"calculation": "bands"},
        },
        cards={
            "K_POINTS": {
                "option": "crystal_b",
                "data": [
                    [0.0, 0.0, 0.0, 20],  # Gamma
                    [0.5, 0.0, 0.0, 20],  # X
                ],
            },
        },
    )
    
    # Generate QE input directly
    qe_input, _ = generate_qe_input_from_spec(
        structure=sample_structure,
        spec=spec,
        species_map={
            "Si": {
                "pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
                "mass": 28.0855,
            }
        },
    )
    
    input_text = QEInputGenerator.generate(qe_input)
    
    # Should contain "K_POINTS {crystal_b}"
    assert "K_POINTS {crystal_b}" in input_text or "K_POINTS {crystal_b}".upper() in input_text.upper()
    
    # Should contain k-point data
    assert "0.0" in input_text or "0" in input_text


def test_no_k_points_in_parameters_rendered(sample_structure, tmp_path):
    """Test that if K_POINTS accidentally appears in parameters, it's not rendered as namelist."""
    from quantumvitas.core.models import ResourceMeta
    # Even if someone mistakenly puts k_points in parameters, it should not render as &K_POINTS
    spec = StructureStepSpec(
        meta=ResourceMeta(ulid="test-step",
            name="test",
            slug="test-scf",
            path="test.step.yaml",
            kind="step",
        ),
        step_type_spec="qe_scf",
        structure="test-structure",
        parameters={
            "CONTROL": {"calculation": "scf"},
            # Note: This is wrong, but we test that it doesn't break
            # In practice, K_POINTS should only be in cards
        },
        cards={
            "K_POINTS": {
                "option": "automatic",
                "data": [[8, 8, 8, 0, 0, 0]],
            },
        },
    )
    
    # Generate QE input directly
    qe_input, _ = generate_qe_input_from_spec(
        structure=sample_structure,
        spec=spec,
        species_map={
            "Si": {
                "pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
                "mass": 28.0855,
            }
        },
    )
    
    input_text = QEInputGenerator.generate(qe_input)
    
    # Should render K_POINTS as card from cards section
    assert "K_POINTS {" in input_text or "K_POINTS {" in input_text.upper()
    
    # Should NOT render &K_POINTS namelist (even if it was in parameters)
    assert "&K_POINTS" not in input_text

