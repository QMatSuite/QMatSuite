"""
Unit tests for sha_family normalization functions.

Tests verify that sha_family is stable across whitespace-only changes
and line ending differences. sha_family is computed by stripping ALL whitespace
and hashing the result, so "12 3" and "1 23" produce the SAME sha_family.
"""

import tempfile
from pathlib import Path

import pytest

from quantumvitas.core.pseudo_libinfo import (
    compute_sha256_bytes,
    compute_sha_family_file,
    compute_sha_family_text,
)
from quantumvitas.core.resources import get_resources_dir


def test_whitespace_only_change(tmp_path: Path) -> None:
    """
    Test that sha_family is stable across whitespace-only changes.
    
    Assertions:
    1. sha256(raw_bytes) != sha256(modified_ws_bytes)  (raw hash differs)
    2. sha_family(orig_text) == sha_family(modified_ws_text)  (normalized hash same)
    """
    # Find a pseudo file from resources/pseudo/
    pseudo_dir = get_resources_dir() / "pseudo"
    
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
    
    orig_sha_family = compute_sha_family_text(original_text)
    modified_ws_sha_family = compute_sha_family_text(modified_text)
    assert orig_sha_family == modified_ws_sha_family, "sha_family should be stable across whitespace-only changes"


def test_lf_to_crlf_change(tmp_path: Path) -> None:
    """
    Test that sha_family is stable across LF -> CRLF line ending changes.
    
    Assertions:
    1. sha256(orig_bytes) != sha256(crlf_bytes)  (raw hash differs)
    2. sha_family(orig_text) == sha_family(crlf_text)  (normalized hash same)
    """
    # Find a pseudo file from resources/pseudo/
    pseudo_dir = get_resources_dir() / "pseudo"
    
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
    
    orig_sha_family = compute_sha_family_text(original_text)
    crlf_sha_family = compute_sha_family_text(crlf_text)
    assert orig_sha_family == crlf_sha_family, "sha_family should be stable across LF/CRLF changes"


def test_whitespace_position_does_not_change_sha_family(tmp_path: Path) -> None:
    """
    Test that whitespace position does NOT change sha_family (whitespace is stripped).
    
    sha_family strips ALL whitespace, so:
    a) "1 23\n"  -> stripped: "123"
    b) "12 3\n"  -> stripped: "123"
    
    Assertion:
    sha_family(a) == sha_family(b)  (both strip to "123")
    
    This is intentional: sha_family represents "whitespace-stripped identity",
    not full parse-semantic identity.
    """
    # Create two tiny temp files with different whitespace positions
    file_a_path = tmp_path / "a.upf"
    file_b_path = tmp_path / "b.upf"
    
    file_a_path.write_text("1 23\n", encoding="utf-8")
    file_b_path.write_text("12 3\n", encoding="utf-8")
    
    # Compute sha_family
    sha_family_a = compute_sha_family_file(file_a_path)
    sha_family_b = compute_sha_family_file(file_b_path)
    
    # Assertion: both should produce same sha_family (whitespace stripped)
    assert sha_family_a == sha_family_b, "sha_family should be same when whitespace position differs (whitespace is stripped)"


def test_sha_family_file_helper(tmp_path: Path) -> None:
    """Test that compute_sha_family_file works correctly."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello world\n", encoding="utf-8")
    
    sha_family = compute_sha_family_file(test_file)
    assert isinstance(sha_family, str)
    assert len(sha_family) == 64  # SHA256 hex digest length
    assert all(c in "0123456789abcdef" for c in sha_family)


def test_sha_family_text_helper() -> None:
    """Test that compute_sha_family_text works correctly."""
    text = "hello world\n"
    sha_family = compute_sha_family_text(text)
    assert isinstance(sha_family, str)
    assert len(sha_family) == 64  # SHA256 hex digest length
    assert all(c in "0123456789abcdef" for c in sha_family)
    
    # Should be deterministic
    sha_family2 = compute_sha_family_text(text)
    assert sha_family == sha_family2


def test_non_whitespace_change_must_change_sha_family(tmp_path: Path) -> None:
    """
    Test that any non-whitespace character change MUST change sha_family.
    
    Create two files that differ only in non-whitespace characters.
    
    Assertion:
    sha_family(a) != sha_family(b)
    """
    # Create two files with different content (non-whitespace difference)
    file_a_path = tmp_path / "a.upf"
    file_b_path = tmp_path / "b.upf"
    
    file_a_path.write_text("hello world\n", encoding="utf-8")
    file_b_path.write_text("hello  world\n", encoding="utf-8")  # Extra space (whitespace only)
    
    sha_family_a = compute_sha_family_file(file_a_path)
    sha_family_b = compute_sha_family_file(file_b_path)
    
    # Extra whitespace should NOT change sha_family
    assert sha_family_a == sha_family_b, "sha_family should be same with extra whitespace"
    
    # But changing a character should change sha_family
    file_c_path = tmp_path / "c.upf"
    file_c_path.write_text("hello xorld\n", encoding="utf-8")  # Changed 'w' to 'x'
    
    sha_family_c = compute_sha_family_file(file_c_path)
    assert sha_family_a != sha_family_c, "sha_family must differ when non-whitespace characters change"


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
