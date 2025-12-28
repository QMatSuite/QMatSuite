"""
Unit tests for sha_token normalization functions.

Tests verify that sha_token is stable across whitespace-only changes
and line ending differences, but changes when token boundaries change.
"""

import tempfile
from pathlib import Path

import pytest

from quantumvitas.core.pseudo_libinfo import (
    compute_sha256_bytes,
    compute_sha_token_file,
    compute_sha_token_text,
)


def test_whitespace_only_change(tmp_path: Path) -> None:
    """
    Test that sha_token is stable across whitespace-only changes.
    
    Assertions:
    1. sha256(raw_bytes) != sha256(modified_ws_bytes)  (raw hash differs)
    2. sha_token(orig_text) == sha_token(modified_ws_text)  (normalized hash same)
    """
    # Find a pseudo file from resources/pseudo/
    repo_root = Path(__file__).parent.parent.parent
    pseudo_dir = repo_root / "resources" / "pseudo"
    
    # Find first .UPF or .upf file
    pseudo_file = None
    for ext in [".UPF", ".upf"]:
        candidates = list(pseudo_dir.glob(f"*{ext}"))
        if candidates:
            pseudo_file = candidates[0]
            break
    
    if pseudo_file is None:
        pytest.skip("No pseudo files found in resources/pseudo/")
    
    # Read original
    original_bytes = pseudo_file.read_bytes()
    original_text = pseudo_file.read_text(encoding="utf-8", errors="replace")
    
    # Create modified version with whitespace changes
    # a) Replace " " with "    " (multiple spaces)
    # b) Insert extra blank lines
    modified_text = original_text.replace(" ", "    ")  # Multiple spaces
    # Insert blank lines after some newlines
    lines = modified_text.split("\n")
    modified_lines = []
    for i, line in enumerate(lines):
        modified_lines.append(line)
        # Insert blank line every 10 lines (but not at the end)
        if (i + 1) % 10 == 0 and i < len(lines) - 1:
            modified_lines.append("")
    modified_text = "\n".join(modified_lines)
    
    # Write both to temp files
    orig_path = tmp_path / "orig.upf"
    modified_ws_path = tmp_path / "modified_ws.upf"
    
    orig_path.write_bytes(original_bytes)
    modified_ws_path.write_text(modified_text, encoding="utf-8", errors="replace")
    
    modified_ws_bytes = modified_ws_path.read_bytes()
    
    # Assertions
    orig_sha256 = compute_sha256_bytes(original_bytes)
    modified_ws_sha256 = compute_sha256_bytes(modified_ws_bytes)
    assert orig_sha256 != modified_ws_sha256, "Raw SHA256 should differ with whitespace changes"
    
    orig_sha_token = compute_sha_token_text(original_text)
    modified_ws_sha_token = compute_sha_token_text(modified_text)
    assert orig_sha_token == modified_ws_sha_token, "sha_token should be stable across whitespace-only changes"


def test_lf_to_crlf_change(tmp_path: Path) -> None:
    """
    Test that sha_token is stable across LF -> CRLF line ending changes.
    
    Assertions:
    1. sha256(orig_bytes) != sha256(crlf_bytes)  (raw hash differs)
    2. sha_token(orig_text) == sha_token(crlf_text)  (normalized hash same)
    """
    # Find a pseudo file from resources/pseudo/
    repo_root = Path(__file__).parent.parent.parent
    pseudo_dir = repo_root / "resources" / "pseudo"
    
    # Find first .UPF or .upf file
    pseudo_file = None
    for ext in [".UPF", ".upf"]:
        candidates = list(pseudo_dir.glob(f"*{ext}"))
        if candidates:
            pseudo_file = candidates[0]
            break
    
    if pseudo_file is None:
        pytest.skip("No pseudo files found in resources/pseudo/")
    
    # Read original
    original_bytes = pseudo_file.read_bytes()
    original_text = pseudo_file.read_text(encoding="utf-8", errors="replace")
    
    # Ensure original has LF (not CRLF already)
    if "\r\n" in original_text:
        # Replace CRLF with LF first
        original_text = original_text.replace("\r\n", "\n")
    
    # Create CRLF version
    crlf_text = original_text.replace("\n", "\r\n")
    
    # Write both to temp files
    orig_path = tmp_path / "orig.upf"
    modified_crlf_path = tmp_path / "modified_crlf.upf"
    
    orig_path.write_bytes(original_bytes)
    modified_crlf_path.write_bytes(crlf_text.encode("utf-8", errors="replace"))
    
    crlf_bytes = modified_crlf_path.read_bytes()
    
    # Assertions
    orig_sha256 = compute_sha256_bytes(original_bytes)
    crlf_sha256 = compute_sha256_bytes(crlf_bytes)
    assert orig_sha256 != crlf_sha256, "Raw SHA256 should differ with CRLF vs LF"
    
    orig_sha_token = compute_sha_token_text(original_text)
    crlf_sha_token = compute_sha_token_text(crlf_text)
    assert orig_sha_token == crlf_sha_token, "sha_token should be stable across LF/CRLF changes"


def test_token_boundary_change_must_change_sha_token(tmp_path: Path) -> None:
    """
    Test that token-boundary changes MUST change sha_token.
    
    Create two files with different token boundaries:
    a) "1 23\n"  -> tokens: ["1", "23"]
    b) "12 3\n"  -> tokens: ["12", "3"]
    
    Assertion:
    sha_token(a) != sha_token(b)
    """
    # Create two tiny temp files with different token boundaries
    file_a_path = tmp_path / "a.upf"
    file_b_path = tmp_path / "b.upf"
    
    file_a_path.write_text("1 23\n", encoding="utf-8")
    file_b_path.write_text("12 3\n", encoding="utf-8")
    
    # Compute sha_tokens
    sha_token_a = compute_sha_token_file(file_a_path)
    sha_token_b = compute_sha_token_file(file_b_path)
    
    # Assertion
    assert sha_token_a != sha_token_b, "sha_token must differ when token boundaries change"


def test_sha_token_file_helper(tmp_path: Path) -> None:
    """Test that compute_sha_token_file works correctly."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello world\n", encoding="utf-8")
    
    sha_token = compute_sha_token_file(test_file)
    assert isinstance(sha_token, str)
    assert len(sha_token) == 64  # SHA256 hex digest length
    assert all(c in "0123456789abcdef" for c in sha_token)


def test_sha_token_text_helper() -> None:
    """Test that compute_sha_token_text works correctly."""
    text = "hello world\n"
    sha_token = compute_sha_token_text(text)
    assert isinstance(sha_token, str)
    assert len(sha_token) == 64  # SHA256 hex digest length
    assert all(c in "0123456789abcdef" for c in sha_token)
    
    # Should be deterministic
    sha_token2 = compute_sha_token_text(text)
    assert sha_token == sha_token2


def test_sha256_bytes_helper() -> None:
    """Test that compute_sha256_bytes works correctly."""
    data = b"hello world"
    sha256 = compute_sha256_bytes(data)
    assert isinstance(sha256, str)
    assert len(sha256) == 64  # SHA256 hex digest length
    assert all(c in "0123456789abcdef" for c in sha256)
    
    # Should be deterministic
    sha2562 = compute_sha256_bytes(data)
    assert sha256 == sha2562

