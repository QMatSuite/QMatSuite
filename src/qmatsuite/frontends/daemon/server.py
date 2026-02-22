"""
DEPRECATED: This module is a compatibility shim only.

Do not add logic here. The canonical implementation lives in:
    qmatsuite.daemon.server

This shim exists only for backwards compatibility with any code that
may have imported from this path. All classes and functions are
re-exported from the canonical module.

Migration: Change imports from
    from qmatsuite.frontends.daemon.server import X
to
    from qmatsuite.daemon.server import X
"""

import warnings

warnings.warn(
    "qmatsuite.frontends.daemon.server is deprecated. "
    "Import from qmatsuite.daemon.server instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export all public symbols from the canonical module
from qmatsuite.daemon.server import (  # noqa: F401, E402
    RPCRequest,
    RPCResponse,
    ProjectCache,
    DaemonState,
    QMSDaemon,
)

__all__ = [
    "RPCRequest",
    "RPCResponse",
    "ProjectCache",
    "DaemonState",
    "QMSDaemon",
]
