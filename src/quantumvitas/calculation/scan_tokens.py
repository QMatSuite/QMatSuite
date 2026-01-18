"""
Scan token utilities for parameter scan feature.

ScanRef is represented as a token string: "@scan:<scan_id>"
This preserves StepDoc invariants (leaf values are scalar/list, not dict).
"""

from __future__ import annotations

# Token prefix
SCAN_TOKEN_PREFIX = "@scan:"


def is_scan_token(value: Any) -> bool:
    """
    Check if a value is a scan token string.
    
    Args:
        value: Value to check
        
    Returns:
        True if value is a scan token string, False otherwise
    """
    return isinstance(value, str) and value.startswith(SCAN_TOKEN_PREFIX) and len(value) > len(SCAN_TOKEN_PREFIX)


def parse_scan_id(token: str) -> str:
    """
    Extract scan_id from a scan token string.
    
    Args:
        token: Scan token string (e.g., "@scan:scan001")
        
    Returns:
        scan_id (e.g., "scan001")
        
    Raises:
        ValueError: If token is not a valid scan token
    """
    if not is_scan_token(token):
        raise ValueError(f"Not a valid scan token: {token}")
    return token[len(SCAN_TOKEN_PREFIX):]


def make_scan_token(scan_id: str) -> str:
    """
    Create a scan token string from a scan_id.
    
    Args:
        scan_id: Scan ID (e.g., "scan001")
        
    Returns:
        Scan token string (e.g., "@scan:scan001")
    """
    return SCAN_TOKEN_PREFIX + scan_id

