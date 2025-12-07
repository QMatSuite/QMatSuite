"""
QuantumVITAS Daemon Package.

Provides a stdio JSON-RPC daemon for GUI integration.
The daemon calls QVService rather than CLI commands.

Note: Imports are lazy to avoid the RuntimeWarning when running
the server module directly with `python -m quantumvitas.daemon.server`.
"""


def __getattr__(name: str):
    """Lazy import of daemon components."""
    if name == "QVDaemon":
        from quantumvitas.daemon.server import QVDaemon
        return QVDaemon
    elif name == "JobManager":
        from quantumvitas.daemon.jobs import JobManager
        return JobManager
    elif name == "JobStatus":
        from quantumvitas.daemon.jobs import JobStatus
        return JobStatus
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["QVDaemon", "JobManager", "JobStatus"]
