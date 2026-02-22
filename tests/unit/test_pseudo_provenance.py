"""
Unit tests for pseudo provenance recognition.

Tests verify that provenance resolution works correctly and handles
whitespace-invariant sha_family matching.
"""

from pathlib import Path

import pytest

from qmatsuite.core.pseudo_provenance import (
    compute_sha256_file,
    compute_sha_family_file,
    parse_element_from_upf_text,
    resolve_pseudo_provenance,
)
from qmatsuite.core.pseudo_libinfo import compute_sha_family_text
from qmatsuite.core.resources import get_resources_dir


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
      - sha_family computed is 64 hex
      - match_kind is in {"sha256","sha_family","none"}
      - element parsing works
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
    
    # Copy to project structure
    proj_pseudo_dir = tmp_path / "proj" / "pseudo"
    proj_pseudo_dir.mkdir(parents=True, exist_ok=True)
    proj_pseudo_file = proj_pseudo_dir / pseudo_file.name
    proj_pseudo_file.write_bytes(pseudo_file.read_bytes())
    
    # Resolve provenance
    result = resolve_pseudo_provenance(proj_pseudo_file, repo_root=get_resources_dir().parent)
    
    # Assertions
    assert result.sha256 is not None
    assert len(result.sha256) == 64  # SHA256 hex digest length
    assert all(c in "0123456789abcdef" for c in result.sha256)
    
    assert result.sha_family is not None
    assert len(result.sha_family) == 64  # SHA256 hex digest length
    assert all(c in "0123456789abcdef" for c in result.sha_family)
    
    assert result.match_kind in {"sha256", "sha_family", "none"}
    
    # Element parsing should work (even if not in index)
    assert result.element is not None, "Element should be parsed from file or filename"
    assert len(result.element) >= 1
    assert len(result.element) <= 2  # Element symbols are 1-2 characters
    
    # Basename should match
    assert result.basename == pseudo_file.name


def test_sha_family_whitespace_invariance(tmp_path: Path) -> None:
    """
    Test that sha_family is invariant to whitespace-only changes.
    
    Strategy:
    - Copy a pseudo file to tmp
    - Create modified version with whitespace changes (LF->CRLF or extra spaces)
    - Assert:
      - sha256 changes (bytes changed)
      - sha_family stays the same (whitespace is stripped)
    """
    # Find a pseudo file
    pseudo_dir = get_resources_dir() / "pseudo"
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
    
    orig_sha_family = compute_sha_family_file(orig_path)
    crlf_sha_family = compute_sha_family_file(crlf_path)
    
    # Assertions
    assert orig_sha256 != crlf_sha256, "SHA256 should differ with CRLF vs LF"
    assert orig_sha_family == crlf_sha_family, "sha_family should be invariant to LF/CRLF changes"
    
    # Also test with extra spaces
    extra_spaces_text = original_text.replace(" ", "    ")  # Multiple spaces
    extra_spaces_path = tmp_path / "extra_spaces.upf"
    extra_spaces_path.write_text(extra_spaces_text, encoding="utf-8", errors="replace")
    
    extra_spaces_sha256 = compute_sha256_file(extra_spaces_path)
    extra_spaces_sha_family = compute_sha_family_file(extra_spaces_path)
    
    assert orig_sha256 != extra_spaces_sha256, "SHA256 should differ with extra spaces"
    assert orig_sha_family == extra_spaces_sha_family, "sha_family should be invariant to whitespace changes"


def test_sha_family_whitespace_position_insensitivity() -> None:
    """
    Test that sha_family is NOT sensitive to whitespace position (whitespace is stripped).
    
    Strategy:
    - Create two text snippets with different whitespace positions:
      - "1 23" -> stripped: "123"
      - "12 3" -> stripped: "123"
    - Assert sha_family is the SAME (both strip to "123")
    
    This is intentional: sha_family represents "whitespace-stripped identity",
    not full parse-semantic identity.
    """
    text1 = "1 23\n"
    text2 = "12 3\n"
    
    sha_family1 = compute_sha_family_text(text1)
    sha_family2 = compute_sha_family_text(text2)
    
    assert sha_family1 == sha_family2, "sha_family should be same when whitespace position differs (whitespace is stripped)"


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
    pseudo_dir = get_resources_dir() / "pseudo"
    
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
    result = resolve_pseudo_provenance(test_file, repo_root=get_resources_dir().parent)
    
    # Basic assertions
    assert result.path == str(test_file)
    assert result.basename == pseudo_file.name
    assert result.sha256 is not None
    assert result.sha_family is not None
    assert result.match_kind in {"sha256", "sha_family", "none"}
    assert isinstance(result.matches, list)
    assert isinstance(result.warnings, list)
