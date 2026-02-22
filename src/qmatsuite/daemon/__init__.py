"""
QMatSuite Daemon Package.

Provides a stdio JSON-RPC daemon for GUI integration.
The daemon calls QMSService rather than CLI commands.

Note: Imports are lazy to avoid the RuntimeWarning when running
the server module directly with `python -m qmatsuite.daemon.server`.
"""


def __getattr__(name: str):
    """Lazy import of daemon components."""
    if name == "QMSDaemon":
        from qmatsuite.daemon.server import QMSDaemon
        return QMSDaemon
    elif name == "JobManager":
        from qmatsuite.daemon.jobs import JobManager
        return JobManager
    elif name == "JobStatus":
        from qmatsuite.daemon.jobs import JobStatus
        return JobStatus
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["QMSDaemon", "JobManager", "JobStatus"]
