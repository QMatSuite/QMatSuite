"""
Engine subprocess runners.

This package contains subprocess entrypoints for engines that require
isolation from the daemon process (e.g., PySCF which imports heavy libraries).

The daemon never imports these modules directly. Instead, engines execute
them via subprocess.
"""


