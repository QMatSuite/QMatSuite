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
        "parameters": {
            "CONTROL": {
                "calculation": "relax",
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
        },
        "cards": {
            "K_POINTS": {
                "option": "automatic",
                "data": [[8, 8, 8, 0, 0, 0]],
            },
        },
        "species_overrides": {},
    },
    "vc-relax": {
        "parameters": {
            "CONTROL": {
                "calculation": "vc-relax",
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
            "CELL": {
                "cell_dynamics": "bfgs",
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


def get_default_step_params(step_type: str) -> Dict[str, Any]:
    """
    Get default parameters for a step type.
    
    Supports Phase 2 engine-prefixed step types (e.g., "qe_scf", "qe_nscf")
    with backward compatibility for legacy step types (e.g., "scf", "nscf").
    
    Args:
        step_type: Step type (e.g., "qe_scf", "qe_nscf", "scf", "nscf")
        
    Returns:
        Dict with "parameters", "cards", and "species_overrides" keys.
        Returns empty dicts if step_type is not recognized.
    """
    step_type_lower = step_type.lower()
    
    # Try direct lookup first (for legacy step types)
    if step_type_lower in DEFAULT_STEP_PARAMS:
        defaults = DEFAULT_STEP_PARAMS[step_type_lower]
    else:
        # Phase 2: Map engine-prefixed step types to legacy names
        # Extract step name by removing engine prefix (e.g., "qe_scf" -> "scf")
        legacy_mapping = {
            "qe_scf": "scf",
            "qe_nscf": "nscf",
            "qe_relax": "relax",
            "qe_vc_relax": "vc-relax",
            "qe_md": "md",
            "qe_vc_md": "vc-md",
            "qe_dos": "dos",
            "qe_bands": "bands",
            "qe_bandspw": "bandspw",
            # PySCF step types
            "pyscf_scf": "pyscf_scf",
            "pyscf_mp2": "pyscf_mp2",
            # Other QE step types don't have defaults yet
        }
        legacy_name = legacy_mapping.get(step_type_lower)
        if legacy_name:
            defaults = DEFAULT_STEP_PARAMS.get(legacy_name, {})
        else:
            defaults = {}
    
    return {
        "parameters": defaults.get("parameters", {}),
        "cards": defaults.get("cards", {}),
        "species_overrides": defaults.get("species_overrides", {}),
    }

