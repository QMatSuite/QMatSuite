"""
Enums shared across calculation modules.
"""

from __future__ import annotations

from enum import Enum


class StepMode(str, Enum):
    NORMAL = "normal"          # only require JOB DONE
    STRICT = "strict"          # verify against reference


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"  # Step was not executed because a previous step failed

