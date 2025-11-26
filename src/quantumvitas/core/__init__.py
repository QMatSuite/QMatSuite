"""Legacy core namespace kept for backward-compatible imports.

Only the ``core.engines`` package remains active; all other components have
been migrated into the new layered architecture.
"""

from . import engines

__all__ = ["engines"]

