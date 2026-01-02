"""
Enums shared across calculation modules.
"""

from __future__ import annotations

from enum import Enum


class StepType(str, Enum):
    SCF = "scf"
    NSCF = "nscf"
    DOS = "dos"
    BANDS_PW = "bands_pw"      # pw.x calculation with calculation='bands'
    BANDS = "bands"            # bands.x post-processing
    PH = "ph"
    Q2R = "q2r"
    MATDYN = "matdyn"
    DYNMAT = "dynmat"
    PP = "pp"
    PROJWFC = "projwfc"
    RELAX = "relax"            # pw.x calculation with calculation='relax'
    VC_RELAX = "vc-relax"      # pw.x calculation with calculation='vc-relax'
    # Wannier90 step types
    W90_PREPROC = "w90_preproc"      # wannier90.x -pp (generate .nnkp)
    PW2WANNIER90 = "pw2wannier90"    # pw2wannier90.x (compute overlaps)
    W90_RUN = "w90_run"              # wannier90.x (main MLWF optimization)
    CUSTOM = "custom"


class StepMode(str, Enum):
    NORMAL = "normal"          # only require JOB DONE
    STRICT = "strict"          # verify against reference


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"  # Step was not executed because a previous step failed

