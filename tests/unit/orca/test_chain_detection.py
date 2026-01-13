"""Unit tests for QC chain detection."""
import pytest
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class MockStep:
    """Mock step for testing."""
    id: str
    public_type: str
    step_type: str
    parameters: Dict[str, Any] = None

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


class TestChainDetection:
    """Tests for chain detection logic."""

    def test_single_scf_forms_one_chain(self):
        """Single SCF step forms one chain."""
        from quantumvitas.engine.qc_engine_base import detect_chains

        steps = [MockStep(id="s1", public_type="scf", step_type="orca_scf")]
        chains = detect_chains(steps)

        assert len(chains) == 1
        assert chains[0].scf_root.id == "s1"
        assert len(chains[0].downstream) == 0

    def test_scf_td_forms_one_chain(self):
        """SCF + TD forms one chain with TD as downstream."""
        from quantumvitas.engine.qc_engine_base import detect_chains

        steps = [
            MockStep(id="s1", public_type="scf", step_type="orca_scf"),
            MockStep(id="s2", public_type="td", step_type="orca_td"),
        ]
        chains = detect_chains(steps)

        assert len(chains) == 1
        assert chains[0].scf_root.id == "s1"
        assert len(chains[0].downstream) == 1
        assert chains[0].downstream[0].id == "s2"

    def test_two_scf_forms_two_chains(self):
        """Two SCF steps form two separate chains."""
        from quantumvitas.engine.qc_engine_base import detect_chains

        steps = [
            MockStep(id="s1", public_type="scf", step_type="orca_scf"),
            MockStep(id="s2", public_type="td", step_type="orca_td"),
            MockStep(id="s3", public_type="scf", step_type="orca_scf"),
            MockStep(id="s4", public_type="td", step_type="orca_td"),
        ]
        chains = detect_chains(steps)

        assert len(chains) == 2
        assert chains[0].scf_root.id == "s1"
        assert chains[1].scf_root.id == "s3"

    def test_hf_also_starts_chain(self):
        """HF step also starts a new chain (like SCF)."""
        from quantumvitas.engine.qc_engine_base import detect_chains

        steps = [
            MockStep(id="s1", public_type="hf", step_type="orca_hf"),
            MockStep(id="s2", public_type="td", step_type="orca_td"),
        ]
        chains = detect_chains(steps)

        assert len(chains) == 1
        assert chains[0].scf_root.id == "s1"

    def test_chain_key_derivation(self):
        """Chain key derived from step types."""
        from quantumvitas.engine.qc_engine_base import QCChain, derive_chain_key

        chain = QCChain(
            scf_root=MockStep(id="s1", public_type="scf", step_type="orca_scf"),
            downstream=[MockStep(id="s2", public_type="td", step_type="orca_td")],
        )

        key = derive_chain_key(chain, chain_index=1)
        assert key == "chain01_scf_td"

    def test_chain_key_scf_only(self):
        """Chain key for SCF-only chain."""
        from quantumvitas.engine.qc_engine_base import QCChain, derive_chain_key

        chain = QCChain(
            scf_root=MockStep(id="s1", public_type="scf", step_type="orca_scf"),
            downstream=[],
        )

        key = derive_chain_key(chain, chain_index=1)
        assert key == "chain01_scf"

    def test_chain_key_collision_resolution(self):
        """Multiple chains with same structure get unique keys."""
        from quantumvitas.engine.qc_engine_base import detect_chains

        steps = [
            MockStep(id="s1", public_type="scf", step_type="orca_scf"),
            MockStep(id="s2", public_type="td", step_type="orca_td"),
            MockStep(id="s3", public_type="scf", step_type="orca_scf"),
            MockStep(id="s4", public_type="td", step_type="orca_td"),
        ]
        chains = detect_chains(steps)

        assert chains[0].key == "chain01_scf_td"
        assert chains[1].key == "chain02_scf_td"

    def test_all_steps_property(self):
        """all_steps returns SCF root + downstream in order."""
        from quantumvitas.engine.qc_engine_base import QCChain

        chain = QCChain(
            scf_root=MockStep(id="s1", public_type="scf", step_type="orca_scf"),
            downstream=[
                MockStep(id="s2", public_type="td", step_type="orca_td"),
                MockStep(id="s3", public_type="freq", step_type="orca_freq"),
            ],
            key="chain01_scf_td_freq",
        )

        all_steps = chain.all_steps
        assert len(all_steps) == 3
        assert all_steps[0].id == "s1"
        assert all_steps[1].id == "s2"
        assert all_steps[2].id == "s3"


class TestPartialChain:
    """Tests for partial chain extraction (for Run Step)."""

    def test_partial_chain_to_target(self):
        """Extract partial chain from SCF root to target."""
        from quantumvitas.engine.qc_engine_base import QCChain

        chain = QCChain(
            scf_root=MockStep(id="s1", public_type="scf", step_type="orca_scf"),
            downstream=[
                MockStep(id="s2", public_type="td", step_type="orca_td"),
                MockStep(id="s3", public_type="freq", step_type="orca_freq"),
            ],
            key="chain01_scf_td_freq",
        )

        partial = chain.to_partial_chain(target_step_id="s2")

        assert partial.scf_root.id == "s1"
        assert len(partial.downstream) == 1
        assert partial.downstream[0].id == "s2"

    def test_partial_chain_to_scf_root(self):
        """Partial chain to SCF root includes only SCF."""
        from quantumvitas.engine.qc_engine_base import QCChain

        chain = QCChain(
            scf_root=MockStep(id="s1", public_type="scf", step_type="orca_scf"),
            downstream=[MockStep(id="s2", public_type="td", step_type="orca_td")],
            key="chain01_scf_td",
        )

        partial = chain.to_partial_chain(target_step_id="s1")

        assert partial.scf_root.id == "s1"
        assert len(partial.downstream) == 0

    def test_partial_chain_invalid_target_raises(self):
        """Invalid target step raises ValueError."""
        from quantumvitas.engine.qc_engine_base import QCChain

        chain = QCChain(
            scf_root=MockStep(id="s1", public_type="scf", step_type="orca_scf"),
            downstream=[],
            key="chain01_scf",
        )

        with pytest.raises(ValueError):
            chain.to_partial_chain(target_step_id="nonexistent")


class TestFindChainForStep:
    """Tests for finding which chain contains a step."""

    def test_find_chain_for_scf_root(self):
        """Find chain containing SCF root step."""
        from quantumvitas.engine.qc_engine_base import detect_chains, find_chain_for_step

        steps = [
            MockStep(id="s1", public_type="scf", step_type="orca_scf"),
            MockStep(id="s2", public_type="td", step_type="orca_td"),
        ]
        chains = detect_chains(steps)

        chain = find_chain_for_step("s1", chains)

        assert chain is not None
        assert chain.scf_root.id == "s1"

    def test_find_chain_for_downstream_step(self):
        """Find chain containing downstream step."""
        from quantumvitas.engine.qc_engine_base import detect_chains, find_chain_for_step

        steps = [
            MockStep(id="s1", public_type="scf", step_type="orca_scf"),
            MockStep(id="s2", public_type="td", step_type="orca_td"),
        ]
        chains = detect_chains(steps)

        chain = find_chain_for_step("s2", chains)

        assert chain is not None
        assert chain.scf_root.id == "s1"

    def test_find_chain_for_nonexistent_step(self):
        """Find chain for nonexistent step returns None."""
        from quantumvitas.engine.qc_engine_base import detect_chains, find_chain_for_step

        steps = [MockStep(id="s1", public_type="scf", step_type="orca_scf")]
        chains = detect_chains(steps)

        chain = find_chain_for_step("nonexistent", chains)

        assert chain is None
