"""Static metadata for distribution-managed engine discovery."""

from __future__ import annotations

import sys
from typing import Any, Dict, List

ENGINE_META: Dict[str, Dict[str, Any]] = {
    "qe": {
        "display_name": "Quantum ESPRESSO",
        "engine_type": "binary",
        "required_binaries": ["pw.x"],
        "optional_binaries": [
            "ph.x",
            "pp.x",
            "bands.x",
            "dos.x",
            "projwfc.x",
            "wannier90.x",
            "pw2wannier90.x",
            "pw2qmcpack.x",
        ],
        "primary_binary_unix": "pw.x",
        "primary_binary_windows": "pw.exe",
        "version_command": ["pw.x", "--version"],
        "version_regex": r"v\.?(\d+\.\d+(?:\.\d+)?)",
        "conda_package": "qe",
        "conda_channel": "conda-forge",
        "env_vars": {},
        "bundleable": True,
        "pip_requirements": {},
    },
    "vasp": {
        "display_name": "VASP",
        "engine_type": "binary",
        "required_binaries": ["vasp_std"],
        "optional_binaries": ["vasp_gam", "vasp_ncl"],
        "primary_binary_unix": "vasp_std",
        "primary_binary_windows": "vasp_std.exe",
        "version_command": None,
        "version_regex": None,
        "conda_package": None,
        "conda_channel": None,
        "env_vars": {"VASP_PP_PATH": "Path to POTCAR library"},
        "bundleable": False,
        "pip_requirements": {},
    },
    "xtb": {
        "display_name": "xTB",
        "engine_type": "binary",
        "required_binaries": ["xtb"],
        "optional_binaries": [],
        "primary_binary_unix": "xtb",
        "primary_binary_windows": "xtb.exe",
        "version_command": ["xtb", "--version"],
        "version_regex": r"xtb version (\S+)",
        "conda_package": "xtb",
        "conda_channel": "conda-forge",
        "env_vars": {},
        "bundleable": False,
        "pip_requirements": {},
    },
    "lammps": {
        "display_name": "LAMMPS",
        "engine_type": "binary",
        "required_binaries": ["lmp"],
        "optional_binaries": ["lmp_mpi", "lmp_serial"],
        "primary_binary_unix": "lmp",
        "primary_binary_windows": "lmp.exe",
        "version_command": ["lmp", "-h"],
        "version_regex": r"LAMMPS \((.+)\)",
        "conda_package": "lammps",
        "conda_channel": "conda-forge",
        "env_vars": {},
        "bundleable": False,
        "pip_requirements": {},
    },
    "orca": {
        "display_name": "ORCA",
        "engine_type": "binary",
        "required_binaries": ["orca"],
        "optional_binaries": [],
        "primary_binary_unix": "orca",
        "primary_binary_windows": "orca.exe",
        "version_command": None,
        "version_regex": None,
        "conda_package": None,
        "conda_channel": None,
        "env_vars": {},
        "bundleable": False,
        "pip_requirements": {},
    },
    "gaussian": {
        "display_name": "Gaussian",
        "engine_type": "binary",
        "required_binaries": ["g16"],
        "optional_binaries": ["g09", "g03"],
        "primary_binary_unix": "g16",
        "primary_binary_windows": "g16.exe",
        "version_command": None,
        "version_regex": None,
        "conda_package": None,
        "conda_channel": None,
        "env_vars": {
            "g16root": "Gaussian root directory",
            "GAUSS_SCRDIR": "Gaussian scratch directory",
        },
        "bundleable": False,
        "pip_requirements": {},
    },
    "abinit": {
        "display_name": "ABINIT",
        "engine_type": "binary",
        "required_binaries": ["abinit"],
        "optional_binaries": [],
        "primary_binary_unix": "abinit",
        "primary_binary_windows": "abinit.exe",
        "version_command": ["abinit", "--version"],
        "version_regex": r"(\d+\.\d+(?:\.\d+)?)",
        "conda_package": "abinit",
        "conda_channel": "conda-forge",
        "env_vars": {},
        "bundleable": False,
        "pip_requirements": {},
    },
    "cp2k": {
        "display_name": "CP2K",
        "engine_type": "binary",
        "required_binaries": ["cp2k.ssmp"],
        "optional_binaries": ["cp2k.psmp", "cp2k.popt", "cp2k.sopt", "cp2k"],
        "binary_detection_order": ["cp2k.psmp", "cp2k.popt", "cp2k.ssmp", "cp2k.sopt", "cp2k"],
        "primary_binary_unix": "cp2k.ssmp",
        "primary_binary_windows": "cp2k.ssmp.exe",
        "version_command": ["cp2k.ssmp", "--version"],
        "version_regex": r"CP2K version (\S+)",
        "conda_package": "cp2k",
        "conda_channel": "conda-forge",
        "env_vars": {},
        "bundleable": False,
        "pip_requirements": {},
    },
    "siesta": {
        "display_name": "Siesta",
        "engine_type": "binary",
        "required_binaries": ["siesta"],
        "optional_binaries": [],
        "primary_binary_unix": "siesta",
        "primary_binary_windows": "siesta.exe",
        "version_command": ["siesta", "--version"],
        "version_regex": r"(\d+\.\d+(?:\.\d+)?)",
        "conda_package": "siesta",
        "conda_channel": "conda-forge",
        "env_vars": {},
        "bundleable": False,
        "pip_requirements": {},
    },
    "w90": {
        "display_name": "Wannier90",
        "engine_type": "binary",
        "required_binaries": ["wannier90.x"],
        "optional_binaries": ["wannier90"],
        "primary_binary_unix": "wannier90.x",
        "primary_binary_windows": "wannier90.x.exe",
        "version_command": None,
        "version_regex": None,
        "conda_package": None,
        "conda_channel": None,
        "env_vars": {},
        "bundleable": False,
        "pip_requirements": {},
    },
    "yambo": {
        "display_name": "Yambo",
        "engine_type": "binary",
        "required_binaries": ["yambo"],
        "optional_binaries": ["p2y", "ypp"],
        "primary_binary_unix": "yambo",
        "primary_binary_windows": "yambo.exe",
        "version_command": ["yambo", "-h"],
        "version_regex": None,
        "conda_package": None,
        "conda_channel": None,
        "env_vars": {},
        "bundleable": False,
        "pip_requirements": {},
    },
    "qmcpack": {
        "display_name": "QMCPACK",
        "engine_type": "binary",
        "required_binaries": ["qmcpack"],
        "optional_binaries": [],
        "primary_binary_unix": "qmcpack",
        "primary_binary_windows": "qmcpack.exe",
        "version_command": None,
        "version_regex": None,
        "conda_package": "qmcpack",
        "conda_channel": "conda-forge",
        "env_vars": {},
        "bundleable": False,
        "pip_requirements": {},
    },
    "pyscf": {
        "display_name": "PySCF",
        "engine_type": "python",
        "required_binaries": [],
        "optional_binaries": [],
        "primary_binary_unix": None,
        "primary_binary_windows": None,
        "python_import": "pyscf",
        "version_command": "import pyscf; print(pyscf.__version__)",
        "version_regex": None,
        "conda_package": "pyscf",
        "conda_channel": "conda-forge",
        "env_vars": {},
        "bundleable": False,
        "pip_requirements": {"pyberny": "berny", "geometric": "geometric"},
    },
    "psi4": {
        "display_name": "Psi4",
        "engine_type": "python",
        "required_binaries": [],
        "optional_binaries": [],
        "primary_binary_unix": None,
        "primary_binary_windows": None,
        "python_import": "psi4",
        "version_command": "import psi4; print(psi4.__version__)",
        "version_regex": None,
        "conda_package": "psi4",
        "conda_channel": "conda-forge",
        "env_vars": {},
        "bundleable": False,
        "pip_requirements": {},
    },
    "gpaw": {
        "display_name": "GPAW",
        "engine_type": "python",
        "required_binaries": [],
        "optional_binaries": [],
        "primary_binary_unix": None,
        "primary_binary_windows": None,
        "python_import": "gpaw",
        "version_command": "import gpaw; print(gpaw.__version__)",
        "version_regex": None,
        "conda_package": "gpaw",
        "conda_channel": "conda-forge",
        "env_vars": {},
        "bundleable": False,
        "pip_requirements": {},
    },
    "mace": {
        "display_name": "MACE",
        "engine_type": "python",
        "required_binaries": [],
        "optional_binaries": [],
        "primary_binary_unix": None,
        "primary_binary_windows": None,
        "python_import": "mace",
        "version_command": "import mace; print(mace.__version__)",
        "version_regex": None,
        "conda_package": None,
        "conda_channel": None,
        "env_vars": {},
        "bundleable": False,
        "pip_requirements": {"mace-torch": "mace"},
    },
}


def get_platform_primary_binary(engine_family: str) -> str | None:
    """Return primary executable name for current platform."""
    meta = ENGINE_META.get(engine_family, {})
    if sys.platform.startswith("win"):
        return meta.get("primary_binary_windows")
    return meta.get("primary_binary_unix")


def get_detection_binaries(engine_family: str) -> List[str]:
    """Return candidate binary names in search priority order."""
    meta = ENGINE_META.get(engine_family, {})
    detection = list(meta.get("binary_detection_order") or [])
    if detection:
        return detection

    primary = get_platform_primary_binary(engine_family)
    required = list(meta.get("required_binaries") or [])
    optional = list(meta.get("optional_binaries") or [])
    ordered: List[str] = []
    if primary:
        ordered.append(primary)
    ordered.extend(required)
    ordered.extend(optional)
    out: List[str] = []
    seen = set()
    for name in ordered:
        if name and name not in seen:
            out.append(name)
            seen.add(name)
    return out
