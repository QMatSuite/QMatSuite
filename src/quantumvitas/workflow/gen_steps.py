"""
GenStepRegistry: Single source of truth for all valid GEN step names.

GEN steps are engine-agnostic, underscore-free identifiers.
SPEC steps are created by: {engine_prefix}_{gen_step}
"""

from typing import FrozenSet


class GenStepRegistry:
    """Central registry of all valid GEN step names."""

    # All valid GEN steps (NO underscores allowed by constitution)
    GEN_STEPS: FrozenSet[str] = frozenset({
        # SCF-family (PBC and molecular)
        "scf",
        "hf",
        "nscf",
        # Optimization
        "relax",
        # Electronic structure (QE post-processing)
        "bands",
        "bandspw",
        "dos",
        "projwfc",
        "pp",
        # Wannier
        "wannierprep",
        "pw2wannier",
        "wannier",
        # Phonon
        "ph",
        "q2r",
        "matdyn",
        "dynmat",
        # Dynamics
        "md",
        "vc-md",
        # Post-HF (molecular)
        "mp2",
        "td",
        # Escape hatch
        "custom",
    })

    @classmethod
    def is_valid(cls, gen: str) -> bool:
        """Check if gen step is in registry."""
        return gen.lower() in {g.lower() for g in cls.GEN_STEPS}

    @classmethod
    def validate(cls, gen: str) -> None:
        """Validate gen step, raise if invalid."""
        if not cls.is_valid(gen):
            raise ValueError(f"GEN step '{gen}' not in registry")

    @classmethod
    def get_all(cls) -> FrozenSet[str]:
        """Get all registered GEN steps."""
        return cls.GEN_STEPS

