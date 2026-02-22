"""
In-code default parameters for QMatSuite step types.

This module provides default parameter dictionaries for each step type,
replacing the legacy step template files from templates/step/.

Keys are SPEC step types (e.g., "qe_scf", not "scf").
No GEN-keyed fallback — unknown spec types get empty defaults.
"""

from typing import Any, Dict

# Default parameters keyed by step_type_spec (engine-specific)
DEFAULT_STEP_PARAMS: Dict[str, Dict[str, Any]] = {
    "qe_scf": {
        "parameters": {
            "CONTROL": {
                "calculation": "scf",
                "outdir": "./outdir",
                "restart_mode": "from_scratch",
            },
            "ELECTRONS": {
                "conv_thr": 1.0e-08,
            },
            "SYSTEM": {
                "ecutwfc": 50,
                "occupations": "smearing",
                "smearing": "gaussian",
                "degauss": 0.01,
            },
        },
        "cards": {
            "K_POINTS": {
                "option": "automatic",
                "data": [[8, 8, 8, 0, 0, 0]],
            },
        },
        "species_overrides": {},
    },
    "qe_nscf": {
        "parameters": {
            "CONTROL": {
                "calculation": "nscf",
                "outdir": "./outdir",
                "restart_mode": "from_scratch",
            },
            "ELECTRONS": {
                "conv_thr": 1.0e-08,
            },
            "SYSTEM": {
                "ecutwfc": 50,
                "occupations": "smearing",
                "smearing": "gaussian",
                "degauss": 0.01,
            },
        },
        "cards": {
            "K_POINTS": {
                "option": "automatic",
                "data": [[12, 12, 12, 0, 0, 0]],
            },
        },
        "species_overrides": {},
    },
    "qe_dos": {
        "parameters": {
            "DOS": {
                "emax": 16.0,
                "emin": -9.0,
                "outdir": "./outdir/",
            },
        },
        "cards": {},
        "species_overrides": {},
    },
    "qe_bands": {
        "parameters": {
            "CONTROL": {
                "calculation": "bands",
                "outdir": "./outdir",
                "restart_mode": "from_scratch",
            },
            "ELECTRONS": {
                "conv_thr": 1.0e-08,
            },
            "SYSTEM": {
                "ecutwfc": 50,
            },
        },
        "cards": {
            # K_POINTS is not needed for bands.x post-processing step
            # (bands.x reads from bandspw output, not from input)
        },
        "species_overrides": {},
    },
    "qe_bandspw": {
        "parameters": {
            "CONTROL": {
                "calculation": "bands",  # bandspw step uses calculation='bands' (not 'nscf')
                "outdir": "./outdir",
                "restart_mode": "from_scratch",
            },
            "ELECTRONS": {
                "conv_thr": 1.0e-08,
                "diago_full_acc": True,
            },
            "SYSTEM": {
                "ecutwfc": 50,
                "occupations": "smearing",
                "smearing": "gaussian",
                "degauss": 0.01,
            },
        },
        "cards": {
            # K_POINTS is not set by default - must be provided via --auto-kpath or manual --CARD.K_POINTS
            # (Setting option='crystal_b' without data would create invalid K_POINTS)
        },
        "species_overrides": {},
    },
    "qe_relax": {
        # Covers both fixed-cell and variable-cell relaxation.
        # VC is controlled via CONTROL.calculation parameter ('relax' or 'vc-relax').
        "parameters": {
            "CONTROL": {
                "calculation": "relax",  # User can override to 'vc-relax' for variable-cell
                "outdir": "./outdir",
                "restart_mode": "from_scratch",
            },
            "ELECTRONS": {
                "conv_thr": 1.0e-08,
            },
            "SYSTEM": {
                "ecutwfc": 50,
                "occupations": "smearing",
                "smearing": "gaussian",
                "degauss": 0.01,
            },
            "IONS": {
                "ion_dynamics": "bfgs",
            },
            # CELL namelist: user adds via parameters if needed for vc-relax
        },
        "cards": {
            "K_POINTS": {
                "option": "automatic",
                "data": [[8, 8, 8, 0, 0, 0]],
            },
        },
        "species_overrides": {},
    },
    # Note: NO "vc-relax" entry - VC is a parameter, not a separate step type
    "qe_md": {
        "parameters": {
            "CONTROL": {
                "calculation": "md",
                "outdir": "./outdir",
                "restart_mode": "from_scratch",
            },
            "ELECTRONS": {
                "conv_thr": 1.0e-08,
            },
            "SYSTEM": {
                "ecutwfc": 50,
                "occupations": "smearing",
                "smearing": "gaussian",
                "degauss": 0.01,
            },
            "IONS": {
                "ion_dynamics": "verlet",
            },
        },
        "cards": {
            "K_POINTS": {
                "option": "automatic",
                "data": [[8, 8, 8, 0, 0, 0]],
            },
        },
        "species_overrides": {},
    },
    # PySCF step types (Phase 3C)
    "pyscf_scf": {
        "parameters": {
            "method": "rhf",  # rhf, uhf, rohf, rks, uks, roks
            "basis": "sto-3g",
            "max_cycle": 50,
            "conv_tol": 1e-9,
            "verbose": 4,
            "xc": "pbe",  # For DFT methods
        },
        "cards": {},  # PySCF doesn't use cards
        "species_overrides": {},
    },
    "pyscf_mp2": {
        "parameters": {
            # MP2 uses SCF checkpoint, no additional parameters needed
        },
        "cards": {},
        "species_overrides": {},
    },
}


def get_default_step_params(step_type_spec: str) -> Dict[str, Any]:
    """
    Get default parameters for a step type (SPEC-keyed, no GEN fallback).

    Args:
        step_type_spec: SPEC step type (e.g., "qe_scf", "pyscf_scf").
            Non-QE engines return empty defaults (by design).

    Returns:
        Dict with "parameters", "cards", and "species_overrides" keys.
        Returns empty dicts if step_type_spec is not recognized.
    """
    step_type_lower = step_type_spec.lower()

    # Direct lookup by spec type only — no GEN fallback
    defaults = DEFAULT_STEP_PARAMS.get(step_type_lower, {})
    
    return {
        "parameters": defaults.get("parameters", {}),
        "cards": defaults.get("cards", {}),
        "species_overrides": defaults.get("species_overrides", {}),
    }

