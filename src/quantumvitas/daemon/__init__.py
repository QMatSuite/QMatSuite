"""
QuantumVITAS Daemon Package.

Provides a stdio JSON-RPC daemon for GUI integration.
The daemon calls QVService rather than CLI commands.
"""

from quantumvitas.daemon.server import QVDaemon
from quantumvitas.daemon.jobs import JobManager, JobStatus

__all__ = ["QVDaemon", "JobManager", "JobStatus"]

