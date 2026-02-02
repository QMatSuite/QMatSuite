"""
In-code default parameters for QuantumVITAS step types.

This module provides default parameter dictionaries for each step type,
replacing the legacy step template files from templates/step/.
"""

from typing import Any, Dict

# Default parameters for each step type
DEFAULT_STEP_PARAMS: Dict[str, Dict[str, Any]] = {
    "scf": {
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
    "nscf": {
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
                # occupations: removed from defaults - only include if explicitly set
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
    "dos": {
        "parameters": {
            "DOS": {
                "emax": 16.0,
                "emin": -9.0,
                "fildos": "dos.dat",
                "outdir": "./outdir/",
            },
        },
        "cards": {},
        "species_overrides": {},
    },
    "bands": {
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
    "bandspw": {
        "parameters": {
            "CONTROL": {
                "calculation": "bands",  # bandspw step uses calculation='bands' (not 'nscf')
                "outdir": "./outdir",
                "restart_mode": "from_scratch",
            },
            "ELECTRONS": {
                "conv_thr": 1.0e-08,
            },
            "SYSTEM": {
                "ecutwfc": 50,
                # occupations: removed from defaults - only include if explicitly set
            },
        },
        "cards": {
            # K_POINTS is not set by default - must be provided via --auto-kpath or manual --CARD.K_POINTS
            # (Setting option='crystal_b' without data would create invalid K_POINTS)
        },
        "species_overrides": {},
    },
    "relax": {
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
    "md": {
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
    # Legacy mapping for PySCF steps (for backward compatibility)
    "mp2": {
        "parameters": {},
        "cards": {},
        "species_overrides": {},
    },
}


def get_default_step_params(step_type_gen: str) -> Dict[str, Any]:
    """
    Get default parameters for a gen step type.

    Args:
        step_type_gen: GEN step type (e.g., "scf", "nscf", "relax", "md")

    Returns:
        Dict with "parameters", "cards", and "species_overrides" keys.
        Returns empty dicts if step_type_gen is not recognized.
    """
    step_type_lower = step_type_gen.lower()
    
    # Direct lookup (gen types are stored directly in DEFAULT_STEP_PARAMS)
    defaults = DEFAULT_STEP_PARAMS.get(step_type_lower, {})
    
    return {
        "parameters": defaults.get("parameters", {}),
        "cards": defaults.get("cards", {}),
        "species_overrides": defaults.get("species_overrides", {}),
    }

