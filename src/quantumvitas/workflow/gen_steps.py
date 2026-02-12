"""
GenStepRegistry: Single source of truth for all valid GEN step names.

GEN steps are engine-agnostic, underscore-free identifiers.
SPEC steps are created by: {engine_prefix}_{gen_step}
"""

from typing import FrozenSet


class GenStepRegistry:
    """Central registry of all valid GEN step names."""

    # All valid GEN steps (NO underscores allowed by constitution)
    # VC is a parameter, NOT a gen step (see constitution §7.1, §7.2)
    GEN_STEPS: FrozenSet[str] = frozenset({
        # SCF-family (PBC and molecular)
        "scf",
        "hf",
        "nscf",
        # Optimization
        "relax",  # VC vs non-VC is a parameter, not a separate gen step
        # Electronic structure
        "bands",  # Post-processing (bands.x)
        "bandspw",  # Computation (pw.x with calculation='bands')
        "dos",
        "projwfc",
        "pp",
        # Wannier
        "wannierprep",
        "pw2wannier",
        "wannier",
        # QE->QMCPACK interface
        "pw2qmcpack",
        # Phonon
        "ph",  # ph.x uses "ph" not "phonon"
        "q2r",
        "matdyn",
        "dynmat",
        "gipaw",  # gipaw.x — NMR chemical shifts, EPR g-tensor
        # Dynamics
        "md",  # VC vs non-VC is a parameter, not a separate gen step
        "minimize",  # Energy minimization (LAMMPS, etc.)
        "neb",  # Nudged elastic band
        # Post-HF (molecular)
        "mp2",
        "td",
        # Frequency/vibrational
        "freq",
        # Quantum Monte Carlo
        "vmc",       # Variational Monte Carlo
        "dmc",       # Diffusion Monte Carlo
        "wfopt",     # Wavefunction optimization
        # Many-body perturbation theory (yambo)
        "setup",     # Converter + initialization (p2y + yambo init)
        "gw",        # GW quasiparticle corrections
        "bse",       # Bethe-Salpeter equation (optical spectra)
        "optics",    # IP/RPA/TDDFT optical properties
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

