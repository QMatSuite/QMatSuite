"""
Unit tests for pseudo provenance recognition.

Tests verify that provenance resolution works correctly and handles
whitespace-invariant sha_token matching.
"""

from pathlib import Path

import pytest

from quantumvitas.core.pseudo_provenance import (
    compute_sha256_file,
    compute_sha_token_file,
    parse_element_from_upf_text,
    resolve_pseudo_provenance,
)
from quantumvitas.core.pseudo_libinfo import compute_sha_token_text


def test_provenance_matches_internal_resources_pseudo_by_sha256_or_token(
    tmp_path: Path
) -> None:
    """
    Test provenance matching using internal resources/pseudo/ pseudos.
    
    Strategy:
    - Use one known pseudo from resources/pseudo/
    - Copy it into tmp_path / "proj" / "pseudo" / "<same filename>"
    - Call resolve_pseudo_provenance() and assert:
      - sha256 computed is 64 hex
      - sha_token computed is 64 hex
      - match_kind is in {"sha256","sha_token","none"}
      - element parsing works
    """
    # Find repo root
    repo_root = Path(__file__).parent.parent.parent
    
    # Find a pseudo file from resources/pseudo/
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
    
    # Copy to project structure
    proj_pseudo_dir = tmp_path / "proj" / "pseudo"
    proj_pseudo_dir.mkdir(parents=True, exist_ok=True)
    proj_pseudo_file = proj_pseudo_dir / pseudo_file.name
    proj_pseudo_file.write_bytes(pseudo_file.read_bytes())
    
    # Resolve provenance
    result = resolve_pseudo_provenance(proj_pseudo_file, repo_root=repo_root)
    
    # Assertions
    assert result.sha256 is not None
    assert len(result.sha256) == 64  # SHA256 hex digest length
    assert all(c in "0123456789abcdef" for c in result.sha256)
    
    assert result.sha_token is not None
    assert len(result.sha_token) == 64  # SHA256 hex digest length
    assert all(c in "0123456789abcdef" for c in result.sha_token)
    
    assert result.match_kind in {"sha256", "sha_token", "none"}
    
    # Element parsing should work (even if not in index)
    assert result.element is not None, "Element should be parsed from file or filename"
    assert len(result.element) >= 1
    assert len(result.element) <= 2  # Element symbols are 1-2 characters
    
    # Basename should match
    assert result.basename == pseudo_file.name


def test_sha_token_whitespace_invariance(tmp_path: Path) -> None:
    """
    Test that sha_token is invariant to whitespace-only changes.
    
    Strategy:
    - Copy a pseudo file to tmp
    - Create modified version with whitespace changes (LF->CRLF or extra spaces)
    - Assert:
      - sha256 changes (bytes changed)
      - sha_token stays the same
    """
    # Find repo root
    repo_root = Path(__file__).parent.parent.parent
    
    # Find a pseudo file
    pseudo_dir = repo_root / "resources" / "pseudo"
    pseudo_file = None
    for ext in [".UPF", ".upf"]:
        candidates = list(pseudo_dir.glob(f"*{ext}"))
        if candidates:
            pseudo_file = candidates[0]
            break
    
    if pseudo_file is None:
        pytest.skip("No pseudo files found in resources/pseudo/")
    
    # Read original
    original_text = pseudo_file.read_text(encoding="utf-8", errors="replace")
    
    # Ensure original has LF (not CRLF)
    if "\r\n" in original_text:
        original_text = original_text.replace("\r\n", "\n")
    
    # Create CRLF version
    crlf_text = original_text.replace("\n", "\r\n")
    
    # Write both to tmp
    orig_path = tmp_path / "orig.upf"
    crlf_path = tmp_path / "crlf.upf"
    
    orig_path.write_text(original_text, encoding="utf-8", errors="replace")
    crlf_path.write_bytes(crlf_text.encode("utf-8", errors="replace"))
    
    # Compute hashes
    orig_sha256 = compute_sha256_file(orig_path)
    crlf_sha256 = compute_sha256_file(crlf_path)
    
    orig_sha_token = compute_sha_token_file(orig_path)
    crlf_sha_token = compute_sha_token_file(crlf_path)
    
    # Assertions
    assert orig_sha256 != crlf_sha256, "SHA256 should differ with CRLF vs LF"
    assert orig_sha_token == crlf_sha_token, "sha_token should be invariant to LF/CRLF changes"
    
    # Also test with extra spaces
    extra_spaces_text = original_text.replace(" ", "    ")  # Multiple spaces
    extra_spaces_path = tmp_path / "extra_spaces.upf"
    extra_spaces_path.write_text(extra_spaces_text, encoding="utf-8", errors="replace")
    
    extra_spaces_sha256 = compute_sha256_file(extra_spaces_path)
    extra_spaces_sha_token = compute_sha_token_file(extra_spaces_path)
    
    assert orig_sha256 != extra_spaces_sha256, "SHA256 should differ with extra spaces"
    assert orig_sha_token == extra_spaces_sha_token, "sha_token should be invariant to whitespace changes"


def test_sha_token_token_boundary_sensitivity() -> None:
    """
    Test that sha_token is sensitive to token boundary changes.
    
    Strategy:
    - Create two text snippets with different token boundaries:
      - "1 23" vs "12 3"
    - Assert sha_token differs
    """
    text1 = "1 23\n"
    text2 = "12 3\n"
    
    sha_token1 = compute_sha_token_text(text1)
    sha_token2 = compute_sha_token_text(text2)
    
    assert sha_token1 != sha_token2, "sha_token must differ when token boundaries change"


def test_parse_element_from_upf_text() -> None:
    """Test element parsing from UPF text."""
    # Test UPF v2 format
    upf2_text = '<PP_HEADER element="Si " pseudo_type="NC" .../>'
    element = parse_element_from_upf_text(upf2_text)
    assert element == "Si"
    
    # Test legacy format with "Element: X"
    legacy_text1 = "<PP_INFO>\nElement: Al\n</PP_INFO>"
    element = parse_element_from_upf_text(legacy_text1)
    assert element == "Al"
    
    # Test legacy format with "  X   Element"
    legacy_text2 = "<PP_INFO>\n  Br   Element\n</PP_INFO>"
    element = parse_element_from_upf_text(legacy_text2)
    assert element == "Br"
    
    # Test fallback (no element found)
    no_element_text = "<PP_INFO>\nSome other content\n</PP_INFO>"
    element = parse_element_from_upf_text(no_element_text)
    assert element is None


def test_resolve_pseudo_provenance_with_real_file(tmp_path: Path) -> None:
    """Test resolve_pseudo_provenance with a real pseudo file."""
    repo_root = Path(__file__).parent.parent.parent
    pseudo_dir = repo_root / "resources" / "pseudo"
    
    # Find a pseudo file
    pseudo_file = None
    for ext in [".UPF", ".upf"]:
        candidates = list(pseudo_dir.glob(f"*{ext}"))
        if candidates:
            pseudo_file = candidates[0]
            break
    
    if pseudo_file is None:
        pytest.skip("No pseudo files found in resources/pseudo/")
    
    # Copy to tmp
    test_file = tmp_path / pseudo_file.name
    test_file.write_bytes(pseudo_file.read_bytes())
    
    # Resolve
    result = resolve_pseudo_provenance(test_file, repo_root=repo_root)
    
    # Basic assertions
    assert result.path == str(test_file)
    assert result.basename == pseudo_file.name
    assert result.sha256 is not None
    assert result.sha_token is not None
    assert result.match_kind in {"sha256", "sha_token", "none"}
    assert isinstance(result.matches, list)
    assert isinstance(result.warnings, list)

