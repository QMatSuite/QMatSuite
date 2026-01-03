"""
Unit tests for pseudopotential resolution using calculation-level species_map.

These tests verify that ensure_qe_pseudos correctly uses species_map as the primary
source of truth for pseudo filenames, even when the QE input file has placeholders.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any

from quantumvitas.core.pseudo import ensure_qe_pseudos, PseudoResolutionResult
from quantumvitas.io.model import QEInput, QENamelist, QECard, QECardType
from quantumvitas.io.generator.qe_generator import QEInputGenerator


@pytest.fixture
def temp_project():
    """Create a temporary project directory structure."""
    tmpdir = tempfile.mkdtemp()
    project_root = Path(tmpdir) / "test_project"
    project_root.mkdir()
    pseudo_dir = project_root / "pseudo"
    pseudo_dir.mkdir()
    
    yield project_root
    
    shutil.rmtree(tmpdir)


@pytest.fixture
def temp_system_pseudo():
    """Create a temporary system pseudo directory."""
    tmpdir = tempfile.mkdtemp()
    pseudo_dir = Path(tmpdir) / "resources" / "pseudo"
    pseudo_dir.mkdir(parents=True)
    
    yield pseudo_dir
    
    shutil.rmtree(tmpdir)


@pytest.fixture
def sample_pseudo_file(temp_system_pseudo):
    """Create a sample pseudo file in system directory."""
    pseudo_file = temp_system_pseudo / "Si.pbe-n-van.UPF"
    pseudo_file.write_text("# Sample pseudo file\nSi 28.0\n")
    return pseudo_file


def create_qe_input_with_placeholders(output_path: Path):
    """Create a QE input file with placeholder pseudos in ATOMIC_SPECIES."""
    control = QENamelist(name="CONTROL", parameters={"calculation": "scf"})
    system = QENamelist(name="SYSTEM", parameters={"ibrav": 0, "nat": 2, "ntyp": 1})
    
    # ATOMIC_SPECIES with placeholder (like what qe_input_from_structure creates)
    from quantumvitas.core.pseudo import make_missing_pseudo_placeholder
    atomic_species_data = [
        ["Si", 28.0, make_missing_pseudo_placeholder("Si")]  # __MISSING_PSEUDO__Si
    ]
    atomic_species_card = QECard(
        card_type=QECardType.ATOMIC_SPECIES,
        option=None,
        data=atomic_species_data,
    )
    
    qe_input = QEInput(
        namelists=[control, system],
        cards=[atomic_species_card],
    )
    
    QEInputGenerator.write_file(qe_input, output_path)
    return output_path


def create_qe_input_with_real_pseudos(output_path: Path):
    """Create a QE input file with real pseudo filenames in ATOMIC_SPECIES."""
    control = QENamelist(name="CONTROL", parameters={"calculation": "scf"})
    system = QENamelist(name="SYSTEM", parameters={"ibrav": 0, "nat": 2, "ntyp": 1})
    
    atomic_species_data = [
        ["Si", 28.0, "Si.pbe-n-van.UPF"]  # Real filename
    ]
    atomic_species_card = QECard(
        card_type=QECardType.ATOMIC_SPECIES,
        option=None,
        data=atomic_species_data,
    )
    
    qe_input = QEInput(
        namelists=[control, system],
        cards=[atomic_species_card],
    )
    
    QEInputGenerator.write_file(qe_input, output_path)
    return output_path


def test_ensure_qe_pseudos_with_species_map_primary(temp_project, temp_system_pseudo, sample_pseudo_file):
    """
    Test that species_map is used as PRIMARY source even if QE input has placeholders.
    
    This is the core fix: calculation-level species_map should be honored even when
    the temporary QE input file (generated during materialization) contains placeholders.
    """
    # Create QE input with placeholders (simulating what generate_qe_input_from_spec creates)
    qe_input_file = temp_project / "temp_input.in"
    create_qe_input_with_placeholders(qe_input_file)
    
    # Species map with pseudo_basename (calculation-level authority)
    species_map: Dict[str, Dict[str, Any]] = {
        "Si": {
            "pseudo_basename": "Si.pbe-n-van.UPF",
            "pseudopot": "Si.pbe-n-van.UPF",  # Also include legacy key
            "mass": 28.0,
        }
    }
    
    project_pseudo_dir = temp_project / "pseudo"
    
    # Call ensure_qe_pseudos with species_map
    result = ensure_qe_pseudos(
        qe_input_file=qe_input_file,
        project_pseudo_dir=project_pseudo_dir,
        system_pseudo_dir=temp_system_pseudo,
        species_map=species_map,
    )
    
    # Should succeed: species_map provides the pseudo filename
    assert result.all_available
    assert "Si.pbe-n-van.UPF" in result.resolved_pseudos
    assert (project_pseudo_dir / "Si.pbe-n-van.UPF").exists()


def test_ensure_qe_pseudos_with_species_map_pseudo_basename_only(temp_project, temp_system_pseudo, sample_pseudo_file):
    """Test that pseudo_basename is recognized even without pseudopot key."""
    qe_input_file = temp_project / "temp_input.in"
    create_qe_input_with_placeholders(qe_input_file)
    
    # Species map with only pseudo_basename (new format)
    species_map: Dict[str, Dict[str, Any]] = {
        "Si": {
            "pseudo_basename": "Si.pbe-n-van.UPF",
            "mass": 28.0,
        }
    }
    
    project_pseudo_dir = temp_project / "pseudo"
    
    result = ensure_qe_pseudos(
        qe_input_file=qe_input_file,
        project_pseudo_dir=project_pseudo_dir,
        system_pseudo_dir=temp_system_pseudo,
        species_map=species_map,
    )
    
    assert result.all_available
    assert "Si.pbe-n-van.UPF" in result.resolved_pseudos


def test_ensure_qe_pseudos_without_species_map_legacy_path(temp_project, temp_system_pseudo, sample_pseudo_file):
    """
    Test that legacy path (parsing QE input) still works when species_map is not provided.
    
    This ensures backward compatibility for standalone QE input execution.
    """
    # Create QE input with real pseudo filenames
    qe_input_file = temp_project / "temp_input.in"
    create_qe_input_with_real_pseudos(qe_input_file)
    
    project_pseudo_dir = temp_project / "pseudo"
    
    # Call without species_map (legacy path)
    result = ensure_qe_pseudos(
        qe_input_file=qe_input_file,
        project_pseudo_dir=project_pseudo_dir,
        system_pseudo_dir=temp_system_pseudo,
        species_map=None,  # No species_map
    )
    
    # Should succeed: QE input has real pseudo filenames
    assert result.all_available
    assert "Si.pbe-n-van.UPF" in result.resolved_pseudos


def test_ensure_qe_pseudos_species_map_missing_element_raises(temp_project, temp_system_pseudo):
    """
    Test that missing element in species_map raises configuration error.
    
    If QE input requires Si but species_map doesn't have it, should raise ValueError.
    """
    qe_input_file = temp_project / "temp_input.in"
    create_qe_input_with_placeholders(qe_input_file)
    
    # Species map missing Si (or empty)
    species_map: Dict[str, Dict[str, Any]] = {}
    
    project_pseudo_dir = temp_project / "pseudo"
    
    # Should raise ValueError (configuration error, not file error)
    with pytest.raises(ValueError, match="Pseudopotential not configured for element\\(s\\): Si"):
        ensure_qe_pseudos(
            qe_input_file=qe_input_file,
            project_pseudo_dir=project_pseudo_dir,
            system_pseudo_dir=temp_system_pseudo,
            species_map=species_map,
        )


def test_ensure_qe_pseudos_species_map_placeholder_in_map_raises(temp_project, temp_system_pseudo):
    """
    Test that placeholder in species_map itself raises configuration error.
    """
    qe_input_file = temp_project / "temp_input.in"
    create_qe_input_with_placeholders(qe_input_file)
    
    from quantumvitas.core.pseudo import make_missing_pseudo_placeholder
    
    # Species map with placeholder (invalid configuration)
    species_map: Dict[str, Dict[str, Any]] = {
        "Si": {
            "pseudopot": make_missing_pseudo_placeholder("Si"),
            "mass": 28.0,
        }
    }
    
    project_pseudo_dir = temp_project / "pseudo"
    
    # Should raise ValueError
    with pytest.raises(ValueError, match="Pseudopotential not configured for element\\(s\\): Si"):
        ensure_qe_pseudos(
            qe_input_file=qe_input_file,
            project_pseudo_dir=project_pseudo_dir,
            system_pseudo_dir=temp_system_pseudo,
            species_map=species_map,
        )


def test_apply_species_overrides_pseudo_basename(temp_project):
    """Test that apply_species_overrides_to_qe_input handles pseudo_basename."""
    from quantumvitas.calculation.input_runner import apply_species_overrides_to_qe_input
    from quantumvitas.io.model import QEInput, QENamelist, QECard, QECardType
    
    # Create QE input with placeholder
    control = QENamelist(name="CONTROL", parameters={"calculation": "scf"})
    system = QENamelist(name="SYSTEM", parameters={"ibrav": 0, "nat": 2, "ntyp": 1})
    from quantumvitas.core.pseudo import make_missing_pseudo_placeholder
    atomic_species_data = [["Si", 28.0, make_missing_pseudo_placeholder("Si")]]
    atomic_species_card = QECard(
        card_type=QECardType.ATOMIC_SPECIES,
        option=None,
        data=atomic_species_data,
    )
    qe_input = QEInput(namelists=[control, system], cards=[atomic_species_card])
    
    # Apply override with pseudo_basename
    overrides = {
        "Si": {
            "pseudo_basename": "Si.pbe-n-van.UPF",
            "mass": 28.0,
        }
    }
    
    apply_species_overrides_to_qe_input(qe_input, overrides)
    
    # Check that ATOMIC_SPECIES was updated
    atomic_species = qe_input.get_card(QECardType.ATOMIC_SPECIES)
    assert atomic_species is not None
    assert len(atomic_species.data) == 1
    row = atomic_species.data[0]
    assert row[0] == "Si"
    assert row[2] == "Si.pbe-n-van.UPF"  # Placeholder replaced


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

