"""Generalized QC engine base with chain detection.

This module provides base classes and utilities for quantum chemistry engines
that work with dependency chains rooted at SCF/HF calculations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Protocol, Sequence


class StepLike(Protocol):
    """Protocol for step-like objects."""
    id: str
    public_type: str
    step_type: str


# Step types that start a new chain (SCF roots)
# These are steps that produce a wavefunction from scratch
SCF_ROOT_TYPES = {"scf", "hf", "dft", "rhf", "uhf", "rks", "uks"}


@dataclass
class QCChain:
    """
    Represents a dependency chain rooted at an SCF step.

    All downstream steps depend on the SCF root's wavefunction.
    For ORCA, chains are atomic units of execution - one chain = one ORCA job.
    """
    scf_root: Any  # StepLike
    downstream: List[Any] = field(default_factory=list)  # List[StepLike]
    key: str = ""

    @property
    def all_steps(self) -> List[Any]:
        """Return all steps in chain order (root first)."""
        return [self.scf_root] + self.downstream

    @property
    def step_ids(self) -> List[str]:
        """Return all step IDs in chain order."""
        return [self.scf_root.id] + [s.id for s in self.downstream]

    def contains_step(self, step_id: str) -> bool:
        """Check if chain contains a step with given ID."""
        if self.scf_root.id == step_id:
            return True
        return any(s.id == step_id for s in self.downstream)

    def to_partial_chain(self, target_step_id: str) -> "QCChain":
        """
        Extract partial chain from SCF root to target step (inclusive).

        This is used for "Run Step" semantics where we only need to execute
        up to and including the target step.

        Args:
            target_step_id: ID of target step

        Returns:
            New QCChain containing only steps up to target

        Raises:
            ValueError: If target not in chain
        """
        # Check if target is SCF root
        if self.scf_root.id == target_step_id:
            return QCChain(
                scf_root=self.scf_root,
                downstream=[],
                key=self.key,
            )

        # Find target in downstream
        partial_downstream = []
        found = False
        for step in self.downstream:
            partial_downstream.append(step)
            if step.id == target_step_id:
                found = True
                break

        if not found:
            raise ValueError(f"Step {target_step_id} not found in chain {self.key}")

        return QCChain(
            scf_root=self.scf_root,
            downstream=partial_downstream,
            key=self.key,
        )


def detect_chains(steps: Sequence[Any]) -> List[QCChain]:
    """
    Detect chains from a sequence of steps.

    Chains are separated by SCF/HF root steps. Each chain starts with
    an SCF root and includes all subsequent steps until the next SCF root.

    Args:
        steps: Sequence of step-like objects (must have id, public_type, step_type)

    Returns:
        List of QCChain objects with keys assigned
    """
    if not steps:
        return []

    chains: List[QCChain] = []
    current_chain: Optional[QCChain] = None

    for step in steps:
        if step.public_type in SCF_ROOT_TYPES:
            # Start a new chain
            if current_chain is not None:
                chains.append(current_chain)
            current_chain = QCChain(scf_root=step, downstream=[])
        else:
            # Add to current chain (if exists)
            if current_chain is not None:
                current_chain.downstream.append(step)
            # else: orphan step before first SCF - this is an error case
            # In a well-formed calculation, there should always be an SCF first

    # Don't forget the last chain
    if current_chain is not None:
        chains.append(current_chain)

    # Assign keys to all chains
    for i, chain in enumerate(chains):
        chain.key = derive_chain_key(chain, chain_index=i + 1)

    return chains


def derive_chain_key(chain: QCChain, chain_index: int) -> str:
    """
    Derive human-readable chain key from step sequence.

    Format: chain{NN}_{step1}_{step2}_...

    Examples:
        [scf] -> "chain01_scf"
        [scf, td] -> "chain01_scf_td"
        [hf, mp2] -> "chain01_hf_mp2"

    Args:
        chain: QCChain object
        chain_index: 1-based index for this chain

    Returns:
        Chain key string
    """
    step_types = [chain.scf_root.public_type]
    step_types.extend(step.public_type for step in chain.downstream)

    base_key = "_".join(step_types)
    return f"chain{chain_index:02d}_{base_key}"


def find_chain_for_step(step_id: str, chains: List[QCChain]) -> Optional[QCChain]:
    """
    Find which chain contains a given step.

    Args:
        step_id: ID of the step to find
        chains: List of QCChain objects to search

    Returns:
        QCChain containing the step, or None if not found
    """
    for chain in chains:
        if chain.contains_step(step_id):
            return chain
    return None


def get_chain_working_dir_name(chain: QCChain) -> str:
    """
    Get the working directory name for a chain.

    For ORCA, chains run in their own subdirectory under calc/raw/chains/.

    Args:
        chain: QCChain object

    Returns:
        Directory name (just the name, not full path)
    """
    return chain.key
