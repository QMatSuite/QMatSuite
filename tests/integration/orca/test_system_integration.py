"""System-level integration tests for ORCA engine.

These tests verify end-to-end ORCA execution through the engine API,
including chain folder outputs, manifest-like tracking, and result extraction.

Run with:
    pytest tests/integration/orca/test_system_integration.py -v -m integration

The tests will automatically find ORCA from:
1. QMATSUITE_ORCA_BIN environment variable
2. Bundled ORCA in .qmatsuite/engines/orca/
"""
import json
import pytest
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional


def get_orca_path() -> Optional[Path]:
    """Get ORCA path using the resolver."""
    try:
        from quantumvitas.core.engines.orca_resolver import resolve_orca_bin
        return resolve_orca_bin()
    except RuntimeError:
        return None


ORCA_BIN = get_orca_path()


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


@pytest.fixture
def calc_structure(tmp_path):
    """Create a mock calculation directory structure."""
    calc_dir = tmp_path / "calc_01"
    raw_dir = calc_dir / "raw"
    chains_dir = raw_dir / "chains"
    chains_dir.mkdir(parents=True)
    return {
        "calc_dir": calc_dir,
        "raw_dir": raw_dir,
        "chains_dir": chains_dir,
    }


@pytest.mark.integration
@pytest.mark.orca
class TestSystemIntegration:
    """System-level integration tests for ORCA engine."""

    def test_chain_folder_structure(self, orca_engine, calc_structure):
        """Verify chain folder outputs under calc/raw/chains."""
        from quantumvitas.engine.qc_engine_base import QCChain

        # Create chain
        scf_step = MockStep(
            id="step_01",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "HF", "basis": "def2-SVP"},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        # Execute chain in chains directory
        chain_dir = calc_structure["chains_dir"] / chain.key
        results = orca_engine.run_chain(chain, chain_dir, WATER)

        # Verify chain folder structure
        assert chain_dir.exists(), "Chain directory not created"
        assert (chain_dir / "chain01_scf.inp").exists(), "Input file missing"
        assert (chain_dir / "chain01_scf.out").exists(), "Output file missing"

        # Verify results
        assert len(results) == 1
        assert results[0].success
        assert "energy" in results[0].metrics

    def test_scf_td_chain_artifacts(self, orca_engine, calc_structure):
        """Verify SCF+TD chain produces all expected artifacts."""
        from quantumvitas.engine.qc_engine_base import QCChain

        # Create SCF + TD chain
        scf_step = MockStep(
            id="step_01",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "HF", "basis": "def2-SVP"},
        )
        td_step = MockStep(
            id="step_02",
            public_type="td",
            step_type="orca_td",
            parameters={"nroots": 3, "tda": True},
        )
        chain = QCChain(scf_root=scf_step, downstream=[td_step], key="chain01_scf_td")

        # Execute chain
        chain_dir = calc_structure["chains_dir"] / chain.key
        results = orca_engine.run_chain(chain, chain_dir, WATER)

        # Verify chain artifacts
        assert (chain_dir / "chain01_scf_td.inp").exists()
        assert (chain_dir / "chain01_scf_td.out").exists()
        assert (chain_dir / "chain01_scf_td.gbw").exists()

        # Verify both step results
        assert len(results) == 2
        assert results[0].step_id == "step_01"
        assert results[1].step_id == "step_02"
        assert results[0].success and results[1].success

    def test_manifest_like_tracking(self, orca_engine, calc_structure):
        """Verify chain-level done tracking (manifest-like behavior)."""
        from quantumvitas.engine.qc_engine_base import QCChain
        import json

        scf_step = MockStep(
            id="step_01",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "HF", "basis": "def2-SVP"},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        chain_dir = calc_structure["chains_dir"] / chain.key
        results = orca_engine.run_chain(chain, chain_dir, WATER)

        # Create a simple manifest-like tracking file
        manifest_data = {
            "chain_key": chain.key,
            "done": results[0].success,
            "step_results": [
                {
                    "step_id": r.step_id,
                    "success": r.success,
                    "metrics": r.metrics,
                }
                for r in results
            ],
        }
        manifest_file = chain_dir / "chain_manifest.json"
        manifest_file.write_text(json.dumps(manifest_data, indent=2))

        # Verify manifest content
        loaded = json.loads(manifest_file.read_text())
        assert loaded["done"] is True
        assert loaded["chain_key"] == "chain01_scf"
        assert len(loaded["step_results"]) == 1

    def test_energy_extraction_pipeline(self, orca_engine, calc_structure):
        """Verify energy is correctly extracted through the pipeline."""
        from quantumvitas.engine.qc_engine_base import QCChain
        from quantumvitas.engines.orca.property_parser import (
            parse_orca_property_txt,
            get_energy,
        )

        scf_step = MockStep(
            id="step_01",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "HF", "basis": "def2-SVP"},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        chain_dir = calc_structure["chains_dir"] / chain.key
        results = orca_engine.run_chain(chain, chain_dir, WATER)

        # Verify energy from step result
        step_energy = results[0].metrics.get("energy")
        assert step_energy is not None
        assert -77 < step_energy < -75  # Water HF/def2-SVP ~ -76 Hartree

        # Verify we can also parse directly from property file
        property_file = chain_dir / "chain01_scf.property.txt"
        if property_file.exists():
            parsed = parse_orca_property_txt(property_file)
            direct_energy = get_energy(parsed)
            assert direct_energy is not None
            assert abs(step_energy - direct_energy) < 1e-10

    def test_multiple_chains_isolation(self, orca_engine, calc_structure):
        """Verify multiple chains run in isolation."""
        from quantumvitas.engine.qc_engine_base import QCChain

        # Create two chains with different parameters
        chain1 = QCChain(
            scf_root=MockStep(
                id="step_01",
                public_type="scf",
                step_type="orca_scf",
                parameters={"functional": "HF", "basis": "def2-SVP"},
            ),
            downstream=[],
            key="chain01_hf_svp",
        )
        chain2 = QCChain(
            scf_root=MockStep(
                id="step_02",
                public_type="scf",
                step_type="orca_scf",
                parameters={"functional": "HF", "basis": "STO-3G"},
            ),
            downstream=[],
            key="chain02_hf_sto3g",
        )

        # Execute chains in separate directories
        chain1_dir = calc_structure["chains_dir"] / chain1.key
        chain2_dir = calc_structure["chains_dir"] / chain2.key

        results1 = orca_engine.run_chain(chain1, chain1_dir, WATER)
        results2 = orca_engine.run_chain(chain2, chain2_dir, WATER)

        # Verify isolation
        assert chain1_dir.exists() and chain2_dir.exists()
        assert (chain1_dir / "chain01_hf_svp.inp").exists()
        assert (chain2_dir / "chain02_hf_sto3g.inp").exists()

        # Verify different results
        e1 = results1[0].metrics["energy"]
        e2 = results2[0].metrics["energy"]
        assert abs(e1 - e2) > 0.5  # Different basis sets = different energies

    def test_tddft_excitation_extraction(self, orca_engine, calc_structure):
        """Verify TDDFT excitation energies are correctly extracted."""
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="step_01",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "HF", "basis": "def2-SVP"},
        )
        td_step = MockStep(
            id="step_02",
            public_type="td",
            step_type="orca_td",
            parameters={"nroots": 3, "tda": True},
        )
        chain = QCChain(scf_root=scf_step, downstream=[td_step], key="chain01_scf_td")

        chain_dir = calc_structure["chains_dir"] / chain.key
        results = orca_engine.run_chain(chain, chain_dir, WATER)

        # Verify TD step has excitation data
        td_result = results[1]
        assert td_result.success

        excitations = td_result.metrics.get("excitation_energies")
        if excitations:
            # Should have 3 roots
            assert len(excitations) >= 1
            # All excitation energies should be positive
            for e in excitations:
                assert e > 0

    def test_engine_registry_integration(self, calc_structure):
        """Verify ORCA engine works through the registry."""
        if not ORCA_BIN:
            pytest.skip("QMATSUITE_ORCA_BIN not set")

        from quantumvitas.engine.registry import create_default_registry
        from quantumvitas.engine.qc_engine_base import QCChain

        registry = create_default_registry()

        # Verify ORCA is registered
        assert registry.has("orca"), "ORCA not in registry"

        orca_engine = registry.get("orca")
        assert orca_engine.name == "orca"

        # Run a simple calculation through the registry-obtained engine
        scf_step = MockStep(
            id="step_01",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "HF", "basis": "STO-3G"},  # Fast
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        chain_dir = calc_structure["chains_dir"] / chain.key
        results = orca_engine.run_chain(chain, chain_dir, WATER)

        assert len(results) == 1
        assert results[0].success

    def test_fresh_vs_reuse_behavior(self, orca_engine, calc_structure):
        """Verify fresh=True prevents wavefunction reuse."""
        from quantumvitas.engine.qc_engine_base import QCChain

        scf_step = MockStep(
            id="step_01",
            public_type="scf",
            step_type="orca_scf",
            parameters={"functional": "HF", "basis": "STO-3G"},
        )
        chain = QCChain(scf_root=scf_step, downstream=[], key="chain01_scf")

        chain_dir = calc_structure["chains_dir"] / chain.key

        # Run with fresh=True
        results = orca_engine.run_chain(chain, chain_dir, WATER, fresh=True)
        assert results[0].success

        # Check input file contains NoAutoStart
        input_content = (chain_dir / "chain01_scf.inp").read_text()
        assert "NoAutoStart" in input_content
