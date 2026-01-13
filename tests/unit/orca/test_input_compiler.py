"""Unit tests for ORCA input compiler."""
import pytest
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class MockStep:
    """Mock step for testing."""
    id: str
    public_type: str
    step_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MockMolecule:
    """Mock molecule for testing."""
    atoms: str = """O   0.000000   0.000000   0.117300
H   0.000000   0.756950  -0.469200
H   0.000000  -0.756950  -0.469200"""
    charge: int = 0
    multiplicity: int = 1


class TestORCAInputCompiler:
    """Tests for ORCA input file generation."""

    def test_scf_only_input(self):
        """Generate input for SCF-only chain."""
        from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "B3LYP", "basis": "def2-SVP"},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")
        molecule = MockMolecule()

        compiler = ORCAInputCompiler()
        input_text = compiler.compile(chain, molecule)

        assert "B3LYP" in input_text
        assert "def2-SVP" in input_text
        assert "* xyz 0 1" in input_text
        assert "O   0.000000" in input_text
        assert "$new_job" not in input_text  # NO multi-job

    def test_scf_td_fusion(self):
        """Generate fused input for SCF + TD chain."""
        from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "B3LYP", "basis": "def2-SVP"},
        )
        td_step = MockStep(
            id="s2",
            public_type="td",
            step_type="orca_td",
            parameters={"nroots": 5, "tda": True},
        )
        chain = QCChain(scf_root=scf_step, downstream=[td_step], key="chain01_scf_td")
        molecule = MockMolecule()

        compiler = ORCAInputCompiler()
        input_text = compiler.compile(chain, molecule)

        assert "B3LYP" in input_text
        assert "def2-SVP" in input_text
        assert "%tddft" in input_text
        assert "NRoots 5" in input_text
        assert "TDA true" in input_text
        assert "* xyz 0 1" in input_text
        assert "$new_job" not in input_text  # NO multi-job

    def test_hf_input(self):
        """Generate input for HF calculation."""
        from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler
        from quantumvitas.engine.qc_engine_base import QCChain

        hf_step = MockStep(
            id="s1",
            public_type="hf",
            step_type="orca_hf",
            parameters={"basis": "def2-TZVP"},
        )
        chain = QCChain(scf_root=hf_step, downstream=[], key="chain01_hf")
        molecule = MockMolecule()

        compiler = ORCAInputCompiler()
        input_text = compiler.compile(chain, molecule)

        assert "HF" in input_text
        assert "def2-TZVP" in input_text
        assert "* xyz 0 1" in input_text

    def test_tightscf_added(self):
        """TightSCF should be added for reliable convergence."""
        from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "B3LYP", "basis": "def2-SVP"},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        compiler = ORCAInputCompiler()
        input_text = compiler.compile(chain, MockMolecule())

        assert "TightSCF" in input_text

    def test_noautostart_when_fresh(self):
        """NoAutoStart keyword added when fresh=True."""
        from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "B3LYP", "basis": "def2-SVP"},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        compiler = ORCAInputCompiler()
        input_text = compiler.compile(chain, MockMolecule(), fresh=True)

        assert "NoAutoStart" in input_text

    def test_pal_block_with_nprocs(self):
        """Parallelism block added when nprocs specified."""
        from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "B3LYP", "basis": "def2-SVP", "nprocs": 4},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        compiler = ORCAInputCompiler()
        input_text = compiler.compile(chain, MockMolecule())

        assert "%pal nprocs 4 end" in input_text

    def test_chain_comment_header(self):
        """Input should have chain key in comment."""
        from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "B3LYP", "basis": "def2-SVP"},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        compiler = ORCAInputCompiler()
        input_text = compiler.compile(chain, MockMolecule())

        assert "# Chain: chain01_scf" in input_text

    def test_td_triplets(self):
        """TDDFT with triplet states."""
        from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "B3LYP", "basis": "def2-SVP"},
        )
        td_step = MockStep(
            id="s2",
            public_type="td",
            step_type="orca_td",
            parameters={"nroots": 3, "tda": False, "triplets": True},
        )
        chain = QCChain(scf_root=scf_step, downstream=[td_step], key="chain01_scf_td")

        compiler = ORCAInputCompiler()
        input_text = compiler.compile(chain, MockMolecule())

        assert "%tddft" in input_text
        assert "TDA false" in input_text
        assert "Triplets true" in input_text

    def test_molecule_charge_multiplicity(self):
        """Molecule charge and multiplicity are respected."""
        from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "B3LYP", "basis": "def2-SVP"},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")
        molecule = MockMolecule()
        molecule.charge = 1
        molecule.multiplicity = 2

        compiler = ORCAInputCompiler()
        input_text = compiler.compile(chain, molecule)

        assert "* xyz 1 2" in input_text

    def test_ri_approximation(self):
        """RI approximation keywords added."""
        from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "B3LYP", "basis": "def2-SVP", "rijcosx": True},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        compiler = ORCAInputCompiler()
        input_text = compiler.compile(chain, MockMolecule())

        assert "RIJCOSX" in input_text

    def test_custom_grid(self):
        """Custom grid settings."""
        from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "B3LYP", "basis": "def2-SVP", "grid": "Grid5"},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        compiler = ORCAInputCompiler()
        input_text = compiler.compile(chain, MockMolecule())

        assert "Grid5" in input_text
