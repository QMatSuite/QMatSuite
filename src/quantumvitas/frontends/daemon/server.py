"""
DEPRECATED: This module is a compatibility shim only.

Do not add logic here. The canonical implementation lives in:
    quantumvitas.daemon.server

This shim exists only for backwards compatibility with any code that
may have imported from this path. All classes and functions are
re-exported from the canonical module.

Migration: Change imports from
    from quantumvitas.frontends.daemon.server import X
to
    from quantumvitas.daemon.server import X
"""

import warnings

warnings.warn(
    "quantumvitas.frontends.daemon.server is deprecated. "
    "Import from quantumvitas.daemon.server instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export all public symbols from the canonical module
from quantumvitas.daemon.server import (  # noqa: F401, E402
    RPCRequest,
    RPCResponse,
    ProjectCache,
    DaemonState,
    QVDaemon,
)

__all__ = [
    "RPCRequest",
    "RPCResponse",
    "ProjectCache",
    "DaemonState",
    "QVDaemon",
]
