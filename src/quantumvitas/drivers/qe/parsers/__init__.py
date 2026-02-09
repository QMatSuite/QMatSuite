"""QE analysis parsers.

Importing this package triggers parser registration via @register_parser.
"""

from .bands import QEBandsProvider
from .output import QEOutputParser, QESCFDigest
from .trajectory import QETrajectoryParser

__all__ = ["QEBandsProvider", "QEOutputParser", "QESCFDigest", "QETrajectoryParser"]
