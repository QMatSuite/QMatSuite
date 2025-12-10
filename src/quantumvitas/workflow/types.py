"""
Enums shared across workflow modules.
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

