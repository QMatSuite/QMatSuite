"""Backward-compatibility re-export for QE trajectory parser (moved to drivers/qe/parsers/)."""

from quantumvitas.drivers.qe.parsers.trajectory import QETrajectoryParser, RY_TO_EV

__all__ = ["QETrajectoryParser", "RY_TO_EV"]

