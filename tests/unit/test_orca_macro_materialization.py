"""
Tests for ORCA macro materialization from engine-specific preset patches.

Verifies that engine.orca.scf.macro values are correctly read from step parameters
and mapped to ORCA keywords in the input file.
"""

import pytest
from dataclasses import dataclass
from typing import Any, Dict

from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler


@dataclass
class MockMolecule:
    """Mock molecule for testing."""
    atoms: str
    charge: int
    multiplicity: int


@dataclass
class MockStep:
    """Mock step for testing."""
    public_type: str
    parameters: Dict[str, Any]
    id: str = "test_step"


@dataclass
class MockChain:
    """Mock chain for testing."""
    key: str
    scf_root: MockStep
    downstream: list = None

    def __post_init__(self):
        if self.downstream is None:
            self.downstream = []

    @property
    def all_steps(self):
        """Return all steps in chain."""
        return [self.scf_root] + self.downstream


def test_tightscf_macro_materialization():
    """Test that 'tightscf' macro maps to 'TightSCF' keyword."""
    compiler = ORCAInputCompiler()
    
    # Create step with engine.orca.scf.macro = "tightscf"
    step = MockStep(
        public_type="scf",
        parameters={
            "functional": "B3LYP",
            "basis": "def2-SVP",
            "engine": {
                "orca": {
                    "scf": {
                        "macro": "tightscf"
                    }
                }
            }
        }
    )
    
    chain = MockChain(key="test_chain", scf_root=step)
    molecule = MockMolecule(atoms="H 0 0 0", charge=0, multiplicity=1)
    
    input_content = compiler.compile(chain, molecule)
    
    # Check that TightSCF keyword is present
    assert "TightSCF" in input_content
    # Check that it's in the keywords line (starts with !)
    lines = input_content.split("\n")
    keyword_line = [line for line in lines if line.startswith("!")][0]
    assert "TightSCF" in keyword_line


def test_normal_macro_no_keyword():
    """Test that 'normal' macro adds no extra keyword."""
    compiler = ORCAInputCompiler()
    
    # Create step with engine.orca.scf.macro = "normal"
    step = MockStep(
        public_type="scf",
        parameters={
            "functional": "B3LYP",
            "basis": "def2-SVP",
            "engine": {
                "orca": {
                    "scf": {
                        "macro": "normal"
                    }
                }
            }
        }
    )
    
    chain = MockChain(key="test_chain", scf_root=step)
    molecule = MockMolecule(atoms="H 0 0 0", charge=0, multiplicity=1)
    
    input_content = compiler.compile(chain, molecule)
    
    # Check that TightSCF keyword is NOT present (normal = no extra keyword)
    assert "TightSCF" not in input_content
    assert "LooseSCF" not in input_content


def test_loose_macro_materialization():
    """Test that 'loose' macro maps to 'LooseSCF' keyword."""
    compiler = ORCAInputCompiler()
    
    # Create step with engine.orca.scf.macro = "loose"
    step = MockStep(
        public_type="scf",
        parameters={
            "functional": "B3LYP",
            "basis": "def2-SVP",
            "engine": {
                "orca": {
                    "scf": {
                        "macro": "loose"
                    }
                }
            }
        }
    )
    
    chain = MockChain(key="test_chain", scf_root=step)
    molecule = MockMolecule(atoms="H 0 0 0", charge=0, multiplicity=1)
    
    input_content = compiler.compile(chain, molecule)
    
    # Check that LooseSCF keyword is present
    assert "LooseSCF" in input_content
    # Check that TightSCF is NOT present
    assert "TightSCF" not in input_content


def test_no_macro_defaults_to_no_keyword():
    """Test that when no macro is present, no SCF keyword is added."""
    compiler = ORCAInputCompiler()
    
    # Create step without engine.orca.scf.macro
    step = MockStep(
        public_type="scf",
        parameters={
            "functional": "B3LYP",
            "basis": "def2-SVP",
        }
    )
    
    chain = MockChain(key="test_chain", scf_root=step)
    molecule = MockMolecule(atoms="H 0 0 0", charge=0, multiplicity=1)
    
    input_content = compiler.compile(chain, molecule)
    
    # Check that no SCF macro keywords are present
    assert "TightSCF" not in input_content
    assert "LooseSCF" not in input_content


def test_macro_validation_lowercase():
    """Test that macro values must be lower-case."""
    compiler = ORCAInputCompiler()
    
    # Create step with uppercase macro (should raise error)
    step = MockStep(
        public_type="scf",
        parameters={
            "functional": "B3LYP",
            "basis": "def2-SVP",
            "engine": {
                "orca": {
                    "scf": {
                        "macro": "TightSCF"  # Uppercase - should fail
                    }
                }
            }
        }
    )
    
    chain = MockChain(key="test_chain", scf_root=step)
    molecule = MockMolecule(atoms="H 0 0 0", charge=0, multiplicity=1)
    
    # Should raise ValueError for uppercase macro
    with pytest.raises(ValueError, match="must be lower-case"):
        compiler.compile(chain, molecule)


def test_unknown_macro_raises_error():
    """Test that unknown macro values raise an error."""
    compiler = ORCAInputCompiler()
    
    # Create step with unknown macro
    step = MockStep(
        public_type="scf",
        parameters={
            "functional": "B3LYP",
            "basis": "def2-SVP",
            "engine": {
                "orca": {
                    "scf": {
                        "macro": "unknown"  # Unknown value
                    }
                }
            }
        }
    )
    
    chain = MockChain(key="test_chain", scf_root=step)
    molecule = MockMolecule(atoms="H 0 0 0", charge=0, multiplicity=1)
    
    # Should raise ValueError for unknown macro
    with pytest.raises(ValueError, match="Unknown ORCA SCF macro"):
        compiler.compile(chain, molecule)


def test_macro_with_other_keywords():
    """Test that macro works alongside other keywords."""
    compiler = ORCAInputCompiler()
    
    # Create step with macro and other SCF settings
    step = MockStep(
        public_type="scf",
        parameters={
            "functional": "B3LYP",
            "basis": "def2-SVP",
            "ri": True,
            "rijcosx": True,
            "engine": {
                "orca": {
                    "scf": {
                        "macro": "tightscf"
                    }
                }
            }
        }
    )
    
    chain = MockChain(key="test_chain", scf_root=step)
    molecule = MockMolecule(atoms="H 0 0 0", charge=0, multiplicity=1)
    
    input_content = compiler.compile(chain, molecule)
    
    # Check that all keywords are present
    assert "TightSCF" in input_content
    assert "RI" in input_content
    assert "RIJCOSX" in input_content
    assert "B3LYP" in input_content
    assert "def2-SVP" in input_content


def test_get_orca_scf_macro_helper():
    """Test the _get_orca_scf_macro helper method."""
    compiler = ORCAInputCompiler()
    
    # Test nested structure
    params = {
        "engine": {
            "orca": {
                "scf": {
                    "macro": "tightscf"
                }
            }
        }
    }
    macro = compiler._get_orca_scf_macro(params)
    assert macro == "tightscf"
    
    # Test missing macro
    params_no_macro = {
        "engine": {
            "orca": {
                "scf": {}
            }
        }
    }
    macro = compiler._get_orca_scf_macro(params_no_macro)
    assert macro is None
    
    # Test missing engine section
    params_no_engine = {}
    macro = compiler._get_orca_scf_macro(params_no_engine)
    assert macro is None


def test_map_macro_to_keyword_helper():
    """Test the _map_macro_to_keyword helper method."""
    compiler = ORCAInputCompiler()
    
    assert compiler._map_macro_to_keyword("tightscf") == "TightSCF"
    assert compiler._map_macro_to_keyword("loose") == "LooseSCF"
    assert compiler._map_macro_to_keyword("normal") is None
    
    # Test case-insensitive
    assert compiler._map_macro_to_keyword("TIGHTSCF") == "TightSCF"
    assert compiler._map_macro_to_keyword("LOOSE") == "LooseSCF"
    
    # Test unknown macro
    with pytest.raises(ValueError, match="Unknown ORCA SCF macro"):
        compiler._map_macro_to_keyword("unknown")

