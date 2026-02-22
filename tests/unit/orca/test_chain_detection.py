"""Unit tests for QC chain detection."""
import pytest
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class MockStep:
    """Mock step for testing."""
    ulid: str
    # public_type removed - use step_type_gen
    step_type_spec: str  # SPEC type (e.g., "orca_scf")
    step_type_gen: str = ""  # GEN type (e.g., "scf") - derived from spec
    parameters: Dict[str, Any] = None

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


class TestChainDetection:
    """Tests for chain detection logic."""

    def test_single_scf_forms_one_chain(self):
        """Single SCF step forms one chain."""
        from qmatsuite.engine.qc_engine_base import detect_chains

        steps = [MockStep(ulid="s1", step_type_gen="scf", step_type_spec="orca_scf", )]
        chains = detect_chains(steps)

        assert len(chains) == 1
        assert chains[0].scf_root.ulid == "s1"
        assert len(chains[0].downstream) == 0

    def test_scf_td_forms_one_chain(self):
        """SCF + TD forms one chain with TD as downstream."""
        from qmatsuite.engine.qc_engine_base import detect_chains

        steps = [
            MockStep(ulid="s1", step_type_gen="scf", step_type_spec="orca_scf", ),
            MockStep(ulid="s2", step_type_gen="td", step_type_spec="orca_td", ),
        ]
        chains = detect_chains(steps)

        assert len(chains) == 1
        assert chains[0].scf_root.ulid == "s1"
        assert len(chains[0].downstream) == 1
        assert chains[0].downstream[0].ulid == "s2"

    def test_two_scf_forms_two_chains(self):
        """Two SCF steps form two separate chains."""
        from qmatsuite.engine.qc_engine_base import detect_chains

        steps = [
            MockStep(ulid="s1", step_type_gen="scf", step_type_spec="orca_scf", ),
            MockStep(ulid="s2", step_type_gen="td", step_type_spec="orca_td", ),
            MockStep(ulid="s3", step_type_gen="scf", step_type_spec="orca_scf", ),
            MockStep(ulid="s4", step_type_gen="td", step_type_spec="orca_td", ),
        ]
        chains = detect_chains(steps)

        assert len(chains) == 2
        assert chains[0].scf_root.ulid == "s1"
        assert chains[1].scf_root.ulid == "s3"

    def test_hf_also_starts_chain(self):
        """HF step also starts a new chain (like SCF)."""
        from qmatsuite.engine.qc_engine_base import detect_chains

        steps = [
            MockStep(ulid="s1", step_type_gen="hf", step_type_spec="orca_hf", ),
            MockStep(ulid="s2", step_type_gen="td", step_type_spec="orca_td", ),
        ]
        chains = detect_chains(steps)

        assert len(chains) == 1
        assert chains[0].scf_root.ulid == "s1"

    def test_chain_key_derivation(self):
        """Chain key derived from step types."""
        from qmatsuite.engine.qc_engine_base import QCChain, derive_chain_key

        chain = QCChain(
            scf_root=MockStep(ulid="s1", step_type_gen="scf", step_type_spec="orca_scf", ),
            downstream=[MockStep(ulid="s2", step_type_gen="td", step_type_spec="orca_td", )],
        )

        key = derive_chain_key(chain, chain_index=1)
        assert key == "chain01_scf_td"

    def test_chain_key_scf_only(self):
        """Chain key for SCF-only chain."""
        from qmatsuite.engine.qc_engine_base import QCChain, derive_chain_key

        chain = QCChain(
            scf_root=MockStep(ulid="s1", step_type_gen="scf", step_type_spec="orca_scf", ),
            downstream=[],
        )

        key = derive_chain_key(chain, chain_index=1)
        assert key == "chain01_scf"

    def test_chain_key_collision_resolution(self):
        """Multiple chains with same structure get unique keys."""
        from qmatsuite.engine.qc_engine_base import detect_chains

        steps = [
            MockStep(ulid="s1", step_type_gen="scf", step_type_spec="orca_scf", ),
            MockStep(ulid="s2", step_type_gen="td", step_type_spec="orca_td", ),
            MockStep(ulid="s3", step_type_gen="scf", step_type_spec="orca_scf", ),
            MockStep(ulid="s4", step_type_gen="td", step_type_spec="orca_td", ),
        ]
        chains = detect_chains(steps)

        assert chains[0].key == "chain01_scf_td"
        assert chains[1].key == "chain02_scf_td"

    def test_all_steps_property(self):
        """all_steps returns SCF root + downstream in order."""
        from qmatsuite.engine.qc_engine_base import QCChain

        chain = QCChain(
            scf_root=MockStep(ulid="s1", step_type_gen="scf", step_type_spec="orca_scf", ),
            downstream=[
                MockStep(ulid="s2", step_type_gen="td", step_type_spec="orca_td", ),
                MockStep(ulid="s3", step_type_gen="freq", step_type_spec="orca_freq", ),
            ],
            key="chain01_scf_td_freq",
        )

        all_steps = chain.all_steps
        assert len(all_steps) == 3
        assert all_steps[0].ulid == "s1"
        assert all_steps[1].ulid == "s2"
        assert all_steps[2].ulid == "s3"


class TestPartialChain:
    """Tests for partial chain extraction (for Run Step)."""

    def test_partial_chain_to_target(self):
        """Extract partial chain from SCF root to target."""
        from qmatsuite.engine.qc_engine_base import QCChain

        chain = QCChain(
            scf_root=MockStep(ulid="s1", step_type_gen="scf", step_type_spec="orca_scf", ),
            downstream=[
                MockStep(ulid="s2", step_type_gen="td", step_type_spec="orca_td", ),
                MockStep(ulid="s3", step_type_gen="freq", step_type_spec="orca_freq", ),
            ],
            key="chain01_scf_td_freq",
        )

        partial = chain.to_partial_chain(target_step_ulid="s2")

        assert partial.scf_root.ulid == "s1"
        assert len(partial.downstream) == 1
        assert partial.downstream[0].ulid == "s2"

    def test_partial_chain_to_scf_root(self):
        """Partial chain to SCF root includes only SCF."""
        from qmatsuite.engine.qc_engine_base import QCChain

        chain = QCChain(
            scf_root=MockStep(ulid="s1", step_type_gen="scf", step_type_spec="orca_scf", ),
            downstream=[MockStep(ulid="s2", step_type_gen="td", step_type_spec="orca_td", )],
            key="chain01_scf_td",
        )

        partial = chain.to_partial_chain(target_step_ulid="s1")

        assert partial.scf_root.ulid == "s1"
        assert len(partial.downstream) == 0

    def test_partial_chain_invalid_target_raises(self):
        """Invalid target step raises ValueError."""
        from qmatsuite.engine.qc_engine_base import QCChain

        chain = QCChain(
            scf_root=MockStep(ulid="s1", step_type_gen="scf", step_type_spec="orca_scf", ),
            downstream=[],
            key="chain01_scf",
        )

        with pytest.raises(ValueError):
            chain.to_partial_chain(target_step_ulid="nonexistent")


class TestFindChainForStep:
    """Tests for finding which chain contains a step."""

    def test_find_chain_for_scf_root(self):
        """Find chain containing SCF root step."""
        from qmatsuite.engine.qc_engine_base import detect_chains, find_chain_for_step

        steps = [
            MockStep(ulid="s1", step_type_gen="scf", step_type_spec="orca_scf", ),
            MockStep(ulid="s2", step_type_gen="td", step_type_spec="orca_td", ),
        ]
        chains = detect_chains(steps)

        chain = find_chain_for_step("s1", chains)

        assert chain is not None
        assert chain.scf_root.ulid == "s1"

    def test_find_chain_for_downstream_step(self):
        """Find chain containing downstream step."""
        from qmatsuite.engine.qc_engine_base import detect_chains, find_chain_for_step

        steps = [
            MockStep(ulid="s1", step_type_gen="scf", step_type_spec="orca_scf", ),
            MockStep(ulid="s2", step_type_gen="td", step_type_spec="orca_td", ),
        ]
        chains = detect_chains(steps)

        chain = find_chain_for_step("s2", chains)

        assert chain is not None
        assert chain.scf_root.ulid == "s1"

    def test_find_chain_for_nonexistent_step(self):
        """Find chain for nonexistent step returns None."""
        from qmatsuite.engine.qc_engine_base import detect_chains, find_chain_for_step

        steps = [MockStep(ulid="s1", step_type_gen="scf", step_type_spec="orca_scf", )]
        chains = detect_chains(steps)

        chain = find_chain_for_step("nonexistent", chains)

        assert chain is None
