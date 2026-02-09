"""QE analysis parsers.

Importing this package triggers parser registration via @register_parser.
"""

from .bands import QEBandsProvider
from .dos import QEDOSProvider
from .output import QEOutputParser, QESCFDigest
from .trajectory import QETrajectoryParser

__all__ = ["QEBandsProvider", "QEDOSProvider", "QEOutputParser", "QESCFDigest", "QETrajectoryParser"]
