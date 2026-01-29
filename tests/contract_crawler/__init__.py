"""
Contract crawler for daemon RPC methods.

This package provides tools to:
1. Enumerate all RPC methods programmatically
2. Auto-call methods and validate JSON-serializable outputs
3. Compare current outputs against golden fixtures from commit 0873ebf
4. Ensure no silent contract drift occurs
"""

