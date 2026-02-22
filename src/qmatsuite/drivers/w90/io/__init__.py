"""Wannier90 I/O functions (parse + write for .win files).

Pure stdlib — no kernel imports.
"""

from .win import parse_win_text, write_win_text

__all__ = ["parse_win_text", "write_win_text"]
