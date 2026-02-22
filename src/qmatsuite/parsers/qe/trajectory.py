"""Backward-compatibility re-export for QE trajectory parser (moved to drivers/qe/parsers/)."""

from qmatsuite.drivers.qe.parsers.trajectory import QETrajectoryParser, RY_TO_EV

__all__ = ["QETrajectoryParser", "RY_TO_EV"]

