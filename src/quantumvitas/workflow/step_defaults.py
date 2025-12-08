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
                "occupations": "tetrahedra",
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
            "K_POINTS": {
                "option": "crystal_b",
            },
        },
        "species_overrides": {},
    },
    "bands_pw": {
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
                "occupations": "tetrahedra",
            },
        },
        "cards": {
            "K_POINTS": {
                "option": "crystal_b",
            },
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
}


def get_default_step_params(step_type: str) -> Dict[str, Any]:
    """
    Get default parameters for a step type.
    
    Args:
        step_type: Step type (e.g., "scf", "nscf", "dos", "bands")
        
    Returns:
        Dict with "parameters", "cards", and "species_overrides" keys.
        Returns empty dicts if step_type is not recognized.
    """
    defaults = DEFAULT_STEP_PARAMS.get(step_type.lower(), {})
    return {
        "parameters": defaults.get("parameters", {}),
        "cards": defaults.get("cards", {}),
        "species_overrides": defaults.get("species_overrides", {}),
    }

