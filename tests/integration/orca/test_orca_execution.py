"""Integration tests for ORCA engine (require ORCA binary).

Run with:
    export QMATSUITE_ORCA_BIN=/path/to/orca
    pytest tests/integration/orca/ -v -m integration
"""
import os
import pytest
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any


ORCA_BIN = os.environ.get("QMATSUITE_ORCA_BIN")


@dataclass
class SimpleMolecule:
    """Simple molecule for testing."""
    atoms: str
    charge: int
    multiplicity: int


WATER = SimpleMolecule(
    atoms="""O   0.000000   0.000000   0.117300
H   0.000000   0.756950  -0.469200
H   0.000000  -0.756950  -0.469200""",
    charge=0,
    multiplicity=1,
)


@dataclass
class MockStep:
    """Mock step for testing."""
    id: str
    public_type: str
    step_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)


@pytest.fixture
def orca_engine():
    """Get ORCA engine if available."""
    if not ORCA_BIN:
        pytest.skip("QMATSUITE_ORCA_BIN not set")

    orca_path = Path(ORCA_BIN)
    if not orca_path.exists():
        pytest.skip(f"ORCA binary not found at {ORCA_BIN}")

    from quantumvitas.engine.orca_engine import ORCAEngine
    return ORCAEngine(orca_bin=orca_path)


@pytest.mark.integration
@pytest.mark.orca
class TestORCAExecution:
    """Integration tests for ORCA execution."""

    def test_scf_execution(self, orca_engine, tmp_path):
        """Test basic SCF calculation."""
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "HF", "basis": "def2-SVP"},  # HF is faster
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        results = orca_engine.run_chain(chain, tmp_path, WATER)

        assert len(results) == 1
        assert results[0].success, f"SCF failed: check {tmp_path / 'chain01_scf.out'}"
        assert (tmp_path / "chain01_scf.out").exists()
        assert (tmp_path / "chain01_scf.gbw").exists()
        assert "energy" in results[0].metrics
        assert results[0].metrics["energy"] < 0  # Energy should be negative

    def test_scf_td_chain(self, orca_engine, tmp_path):
        """Test SCF + TDDFT chain."""
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "HF", "basis": "def2-SVP"},
        )
        td_step = MockStep(
            id="s2",
            public_type="td",
            step_type="orca_td",
            parameters={"nroots": 3, "tda": True},
        )
        chain = QCChain(scf_root=scf_step, downstream=[td_step], key="chain01_scf_td")

        results = orca_engine.run_chain(chain, tmp_path, WATER)

        assert len(results) == 2
        assert results[0].success, f"SCF failed: check {tmp_path / 'chain01_scf_td.out'}"
        assert results[1].success, f"TD failed: check {tmp_path / 'chain01_scf_td.out'}"
        assert "energy" in results[0].metrics
        assert (tmp_path / "chain01_scf_td.out").exists()

    def test_property_file_generated(self, orca_engine, tmp_path):
        """Verify property.txt is generated."""
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "HF", "basis": "def2-SVP"},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        orca_engine.run_chain(chain, tmp_path, WATER)

        property_file = tmp_path / "chain01_scf.property.txt"
        assert property_file.exists(), "Property file not generated"
        content = property_file.read_text()
        assert len(content) > 0, "Property file is empty"

    def test_fresh_run_uses_noautostart(self, orca_engine, tmp_path):
        """Verify fresh=True generates NoAutoStart in input."""
        from quantumvitas.engine.qc_engine_base import QCChain
        from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "HF", "basis": "def2-SVP"},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        compiler = ORCAInputCompiler()
        input_text = compiler.compile(chain, WATER, fresh=True)

        assert "NoAutoStart" in input_text

    def test_chain_artifacts_exist(self, orca_engine, tmp_path):
        """Verify all required chain artifacts are created."""
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "HF", "basis": "def2-SVP"},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        orca_engine.run_chain(chain, tmp_path, WATER)

        # Required artifacts
        assert (tmp_path / "chain01_scf.inp").exists(), "Input file missing"
        assert (tmp_path / "chain01_scf.out").exists(), "Output file missing"
        # property.txt is expected but not strictly required
        # gbw is produced by ORCA

    def test_dft_calculation(self, orca_engine, tmp_path):
        """Test DFT (B3LYP) calculation."""
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "B3LYP", "basis": "def2-SVP"},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        results = orca_engine.run_chain(chain, tmp_path, WATER)

        assert len(results) == 1
        assert results[0].success
        assert "energy" in results[0].metrics

    def test_energy_parsing(self, orca_engine, tmp_path):
        """Test that energy is correctly parsed from output."""
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "HF", "basis": "def2-SVP"},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        results = orca_engine.run_chain(chain, tmp_path, WATER)

        assert results[0].success
        energy = results[0].metrics.get("energy")
        assert energy is not None
        # Water HF/def2-SVP energy should be around -76 Hartree
        assert -77 < energy < -75, f"Unexpected energy: {energy}"

    def test_tddft_excitation_energies(self, orca_engine, tmp_path):
        """Test TDDFT excitation energy extraction."""
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "HF", "basis": "def2-SVP"},
        )
        td_step = MockStep(
            id="s2",
            public_type="td",
            step_type="orca_td",
            parameters={"nroots": 3, "tda": True},
        )
        chain = QCChain(scf_root=scf_step, downstream=[td_step], key="chain01_scf_td")

        results = orca_engine.run_chain(chain, tmp_path, WATER)

        assert results[1].success
        # TD step should have excitation energies
        excitations = results[1].metrics.get("excitation_energies")
        if excitations:
            assert len(excitations) >= 1
            for e in excitations:
                assert e > 0  # Excitation energies should be positive


@pytest.mark.integration
@pytest.mark.orca
class TestORCAChainBehavior:
    """Tests for ORCA chain-specific behavior."""

    def test_chain_key_in_filenames(self, orca_engine, tmp_path):
        """Verify chain key is used in output filenames."""
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="s1",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "HF", "basis": "def2-SVP"},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="test_chain_key")

        orca_engine.run_chain(chain, tmp_path, WATER)

        assert (tmp_path / "test_chain_key.inp").exists()
        assert (tmp_path / "test_chain_key.out").exists()

    def test_multiple_chains_independent(self, orca_engine, tmp_path):
        """Test that multiple chains can run independently."""
        from quantumvitas.engine.qc_engine_base import QCChain

        # Create two chains
        chain1 = QCChain(
            scf_root=MockStep(
                id="s1",
                public_type="scf",
                step_type="orca_scf",
                parameters={"functional": "HF", "basis": "def2-SVP"},
            ),
            downstream=[],
            key="chain01_scf",
        )
        chain2 = QCChain(
            scf_root=MockStep(
                id="s2",
                public_type="scf",
                step_type="orca_scf",
                parameters={"functional": "HF", "basis": "STO-3G"},  # Different basis
            ),
            downstream=[],
            key="chain02_scf",
        )

        # Run both chains
        results1 = orca_engine.run_chain(chain1, tmp_path, WATER)
        results2 = orca_engine.run_chain(chain2, tmp_path, WATER)

        # Both should succeed independently
        assert results1[0].success
        assert results2[0].success

        # Outputs should be separate
        assert (tmp_path / "chain01_scf.out").exists()
        assert (tmp_path / "chain02_scf.out").exists()

        # Energies should be different (different basis sets)
        e1 = results1[0].metrics["energy"]
        e2 = results2[0].metrics["energy"]
        assert abs(e1 - e2) > 0.01, "Energies should differ between basis sets"
