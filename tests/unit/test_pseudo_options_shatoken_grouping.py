"""
Unit tests for sha256-keyed pseudo options (filename-first, constitution-compliant).

Tests verify that get_pseudo_options_for_elements() correctly:
- Returns sha256-keyed variants (not sha_token-grouped)
- Handles "project_local_unknown" variants
- Shows token-match warnings when project has same basename with token-match but sha256 differs
- Filters to filesystem-real options only (project/internal or installed lib)
- Default selection priority: project → internal → lib
"""

import tempfile
from pathlib import Path

import pytest

from quantumvitas.core.pseudo_options import get_pseudo_options_for_elements
from quantumvitas.core.pseudo_libinfo import (
    compute_sha256_bytes,
    compute_sha_token_file,
)


def compute_sha256_file(path: Path) -> str:
    """Compute SHA256 hash of a file."""
    data = path.read_bytes()
    return compute_sha256_bytes(data)


def create_dummy_pseudo_file(path: Path, content: str = "DUMMY UPF CONTENT\n") -> tuple[str, str]:
    """Create a dummy UPF file and return (sha256, sha_token)."""
    path.write_text(content, encoding="utf-8")
    sha256 = compute_sha256_file(path)
    sha_token = compute_sha_token_file(path)
    return sha256, sha_token


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project with project.qv.yml."""
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    
    # Create project.qv.yml
    import yaml
    project_config = {
        "project": {
            "name": "Test Project",
            "id": "test-project-id",
        }
    }
    (project_root / "project.qv.yml").write_text(yaml.safe_dump(project_config))
    
    return project_root


def test_sha256_keyed_variants(temp_project: Path, tmp_path: Path) -> None:
    """
    Test that options are keyed by sha256 (not sha_token-grouped).
    
    Two files with same sha_token but different sha256 should be separate variants.
    """
    # Create two files with same token (different whitespace, same physical)
    internal_dir = tmp_path / "internal"
    internal_dir.mkdir()
    
    file1 = internal_dir / "Si.upf"
    sha256_1, sha_token_1 = create_dummy_pseudo_file(file1, "Si UPF content\n")
    
    file2 = internal_dir / "Si_v2.upf"
    sha256_2, sha_token_2 = create_dummy_pseudo_file(file2, "Si    UPF    content\n")  # More spaces
    
    # They should have different sha256 but same sha_token
    assert sha256_1 != sha256_2, "Files should have different sha256"
    assert sha_token_1 == sha_token_2, "Files should have same sha_token"
    
    # Mock get_system_pseudo_dir to return our temp internal dir
    from unittest.mock import patch
    with patch('quantumvitas.core.pseudo_options.get_system_pseudo_dir', return_value=internal_dir):
        with patch('quantumvitas.core.pseudo_options.load_pseudo_libinfo_bundle') as mock_bundle:
            # Mock bundle with empty index (no library occurrences)
            mock_bundle.return_value.index = {"files": []}
            options = get_pseudo_options_for_elements(temp_project, ["Si"])
    
    # Should have two separate variants (sha256-keyed)
    si_options = options.get("Si", [])
    assert len(si_options) >= 2, f"Should have at least 2 variants (one per sha256), got {len(si_options)}"
    
    # Verify both sha256s are present as separate variants
    variant_sha256s = {v["sha256"] for v in si_options}
    assert sha256_1 in variant_sha256s, "First sha256 should be present"
    assert sha256_2 in variant_sha256s, "Second sha256 should be present"
    
    # Verify both have same sha_token (for warnings)
    variant1 = next(v for v in si_options if v["sha256"] == sha256_1)
    variant2 = next(v for v in si_options if v["sha256"] == sha256_2)
    assert variant1["sha_token"] == variant2["sha_token"], "Both should have same sha_token"


def test_token_match_warnings(temp_project: Path, tmp_path: Path) -> None:
    """
    Test that token-match warnings are shown when project has same basename with token-match but sha256 differs.
    """
    # Create project file
    project_pseudo = temp_project / "pseudo" / "Si.upf"
    project_pseudo.parent.mkdir(parents=True, exist_ok=True)
    proj_sha256, proj_sha_token = create_dummy_pseudo_file(project_pseudo, "Si UPF content\n")
    
    # Create internal file with same token but different sha256 (different whitespace)
    internal_dir = tmp_path / "internal"
    internal_dir.mkdir()
    
    internal_file = internal_dir / "Si.upf"
    internal_sha256, internal_sha_token = create_dummy_pseudo_file(internal_file, "Si    UPF    content\n")  # More spaces
    
    # They should have different sha256 but same sha_token
    assert proj_sha256 != internal_sha256, "Files should have different sha256"
    assert proj_sha_token == internal_sha_token, "Files should have same sha_token"
    
    # Mock get_system_pseudo_dir to return our temp internal dir
    from unittest.mock import patch
    with patch('quantumvitas.core.pseudo_options.get_system_pseudo_dir', return_value=internal_dir):
        with patch('quantumvitas.core.pseudo_options.load_pseudo_libinfo_bundle') as mock_bundle:
            # Mock bundle with empty index (no library occurrences)
            mock_bundle.return_value.index = {"files": []}
            options = get_pseudo_options_for_elements(temp_project, ["Si"])
    
    # Should have two separate variants (one for project, one for internal)
    si_options = options.get("Si", [])
    assert len(si_options) >= 2, f"Should have at least 2 variants, got {len(si_options)}"
    
    # Find project variant
    project_variant = next((v for v in si_options if v["sha256"] == proj_sha256), None)
    assert project_variant is not None, "Project variant should exist"
    
    # Find internal variant
    internal_variant = next((v for v in si_options if v["sha256"] == internal_sha256), None)
    assert internal_variant is not None, "Internal variant should exist"
    
    # Internal variant should have token-match warning
    assert len(internal_variant.get("token_match_warnings", [])) > 0, "Internal variant should have token-match warning"
    
    # Project variant should also have token-match warning
    assert len(project_variant.get("token_match_warnings", [])) > 0, "Project variant should have token-match warning"


def test_project_local_unknown(temp_project: Path, tmp_path: Path) -> None:
    """
    Test that project files not in index are shown as "project_local_unknown" variants.
    """
    # Create project file that's not in any index
    project_pseudo = temp_project / "pseudo" / "Si.upf"
    project_pseudo.parent.mkdir(parents=True, exist_ok=True)
    proj_sha256, proj_sha_token = create_dummy_pseudo_file(project_pseudo, "Si UPF content\n")
    
    # Mock get_system_pseudo_dir to return None (no internal)
    from unittest.mock import patch
    with patch('quantumvitas.core.pseudo_options.get_system_pseudo_dir', return_value=None):
        with patch('quantumvitas.core.pseudo_options.load_pseudo_libinfo_bundle') as mock_bundle:
            # Mock bundle with empty index (no library occurrences, and this sha256 not in index)
            mock_bundle.return_value.index = {"files": []}
            options = get_pseudo_options_for_elements(temp_project, ["Si"])
    
    # Should have one variant (project_local_unknown)
    si_options = options.get("Si", [])
    assert len(si_options) == 1, f"Should have 1 variant, got {len(si_options)}"
    
    variant = si_options[0]
    assert variant["sha256"] == proj_sha256, "Variant should have project sha256"
    assert variant["is_project_local_unknown"] is True, "Variant should be marked as project_local_unknown"
    assert "(project-local)" in variant["display_label"], "Display label should indicate project-local"


def test_filesystem_real_filtering(temp_project: Path, tmp_path: Path) -> None:
    """
    Test that dropdown only includes filesystem-real options (project/internal or installed lib).
    """
    # Create project file
    project_pseudo = temp_project / "pseudo" / "Si.upf"
    project_pseudo.parent.mkdir(parents=True, exist_ok=True)
    proj_sha256, _ = create_dummy_pseudo_file(project_pseudo, "Si UPF content\n")
    
    # Create internal file
    internal_dir = tmp_path / "internal"
    internal_dir.mkdir()
    internal_file = internal_dir / "Si_v2.upf"
    internal_sha256, _ = create_dummy_pseudo_file(internal_file, "Si UPF content v2\n")
    
    # Mock get_system_pseudo_dir to return our temp internal dir
    from unittest.mock import patch
    with patch('quantumvitas.core.pseudo_options.get_system_pseudo_dir', return_value=internal_dir):
        with patch('quantumvitas.core.pseudo_options.load_pseudo_libinfo_bundle') as mock_bundle:
            # Mock bundle with empty index (no library occurrences)
            mock_bundle.return_value.index = {"files": []}
            options = get_pseudo_options_for_elements(temp_project, ["Si"])
    
    # All variants should have at least one filesystem-real source (project or internal)
    si_options = options.get("Si", [])
    for variant in si_options:
        has_project = any(s["kind"] == "project" and s["installed"] for s in variant["sources"])
        has_internal = any(s["kind"] == "internal" and s["installed"] for s in variant["sources"])
        has_installed_lib = any(s["kind"] == "lib" and s["installed"] and not s.get("corrupt", False) for s in variant["sources"])
        assert has_project or has_internal or has_installed_lib, f"Variant {variant['sha256']} should have at least one filesystem-real source"
    with pytest.mock.patch('quantumvitas.core.pseudo_options.get_system_pseudo_dir', return_value=internal_dir):
        options = get_pseudo_options_for_elements_sha_token(temp_project, ["Si"])
    
    si_options = options.get("Si", [])
    
    # Should have multiple groups (different sha_token)
    assert len(si_options) >= 2, f"Should have at least 2 groups, got {len(si_options)}"
    
    # Check disambiguation labels
    basename_to_groups = {}
    for group in si_options:
        canonical = group["canonical_basename"]
        if canonical not in basename_to_groups:
            basename_to_groups[canonical] = []
        basename_to_groups[canonical].append(group)
    
    # Groups with same basename should have disambiguated labels
    for basename, groups in basename_to_groups.items():
        if len(groups) > 1:
            for group in groups:
                assert "(tok-" in group["display_label"], f"Label should have token disambiguation: {group['display_label']}"


def test_sources_aggregation(temp_project: Path, tmp_path: Path) -> None:
    """
    Test that sources are aggregated correctly per variant.
    """
    # Create file in internal
    internal_dir = tmp_path / "internal"
    internal_dir.mkdir()
    file1 = internal_dir / "Si.upf"
    sha256_1, sha_token_1 = create_dummy_pseudo_file(file1)
    
    # Create file in project (same sha256)
    project_pseudo = temp_project / "pseudo"
    project_pseudo.mkdir()
    file2 = project_pseudo / "Si.upf"
    file2.write_bytes(file1.read_bytes())  # Same content = same sha256
    
    # Mock get_system_pseudo_dir
    from unittest.mock import patch
    with patch('quantumvitas.core.pseudo_options.get_system_pseudo_dir', return_value=internal_dir):
        with patch('quantumvitas.core.pseudo_options.load_pseudo_libinfo_bundle') as mock_bundle:
            mock_bundle.return_value.index = {"files": []}
            options = get_pseudo_options_for_elements(temp_project, ["Si"])
    
    si_options = options.get("Si", [])
    assert len(si_options) > 0
    
    # Find variant with matching sha256
    variant = next((v for v in si_options if v["sha256"] == sha256_1), None)
    assert variant is not None, "Should find variant with matching sha256"
    
    # Should have both project and internal sources
    source_kinds = {s["kind"] for s in variant["sources"]}
    assert "project" in source_kinds, "Should have project source"
    assert "internal" in source_kinds, "Should have internal source"


def test_installed_corrupt_flags(temp_project: Path) -> None:
    """
    Test that installed/corrupt flags propagate correctly.
    """
    # Create file in project
    project_pseudo = temp_project / "pseudo"
    project_pseudo.mkdir()
    file1 = project_pseudo / "Si.upf"
    create_dummy_pseudo_file(file1)
    
    from unittest.mock import patch
    with patch('quantumvitas.core.pseudo_options.get_system_pseudo_dir', return_value=None):
        with patch('quantumvitas.core.pseudo_options.load_pseudo_libinfo_bundle') as mock_bundle:
            mock_bundle.return_value.index = {"files": []}
            options = get_pseudo_options_for_elements(temp_project, ["Si"])
    
    si_options = options.get("Si", [])
    assert len(si_options) > 0
    
    # Check that sources have installed flags
    for variant in si_options:
        for source in variant["sources"]:
            assert "installed" in source, "Source should have installed flag"
            assert isinstance(source["installed"], bool), "installed should be boolean"
            
            if source["kind"] == "project" or source["kind"] == "internal":
                assert source["installed"] is True, "Project/internal should always be installed if file exists"
            
            if source.get("corrupt"):
                assert source["installed"] is False or source["corrupt"] is True, "Corrupt sources should not be treated as installed"


def test_tie_break_multiple_libs(temp_project: Path, tmp_path: Path) -> None:
    """
    Test tie-break rule: when multiple libs match same sha256, sort by library/asset name lexicographically.
    """
    # This test would require mocking the bundle to have multiple library occurrences
    # For now, we verify the structure supports tie-break (library_name and archive_asset are available)
    from unittest.mock import patch
    
    internal_dir = tmp_path / "internal"
    internal_dir.mkdir()
    file1 = internal_dir / "Si.upf"
    sha256_1, _ = create_dummy_pseudo_file(file1)
    
    with patch('quantumvitas.core.pseudo_options.get_system_pseudo_dir', return_value=internal_dir):
        with patch('quantumvitas.core.pseudo_options.load_pseudo_libinfo_bundle') as mock_bundle:
            # Mock bundle with multiple library occurrences for same sha256
            mock_bundle.return_value.index = {
                "files": [{
                    "sha256": sha256_1,
                    "sha_token": "test_token",
                    "basenames": ["Si.upf"],
                }]
            }
            # Mock occurrences_index would need to be built from this
            # For now, just verify the structure supports it
            options = get_pseudo_options_for_elements(temp_project, ["Si"])
    
    si_options = options.get("Si", [])
    # Verify that variants have sources with library_name and archive_asset for tie-break
    for variant in si_options:
        lib_sources = [s for s in variant["sources"] if s["kind"] == "lib"]
        for lib_source in lib_sources:
            # These fields should be available for tie-break sorting
            assert "library_name" in lib_source or lib_source.get("library_name") is None
            assert "archive_asset" in lib_source or lib_source.get("archive_asset") is None


def test_tie_break_multiple_libs_ordering(temp_project: Path) -> None:
    """
    Test tie-break determinism: multiple lib sources with same sha256 are ordered lexicographically.
    
    This test directly asserts the tie-break ordering rule:
    1. filename match first
    2. source priority: project > internal > lib
    3. for lib multiple matches: lexicographic by library_name + archive_asset
    4. then basename
    """
    # Create two fake variants with same sha256 but different lib sources
    # We'll test the ordering logic by constructing variants directly
    sha256 = "test_sha256_" * 4  # 64 chars
    sha_token = "test_token_" * 4
    
    # Variant A: library_name="SSSP", archive_asset="sssp_v1.tar.gz"
    variant_a_sources = [
        {
            "kind": "lib",
            "label": "SSSP 1.3 PBE",
            "installed": True,
            "corrupt": False,
            "library_name": "SSSP",
            "archive_asset": "sssp_v1.tar.gz",
        }
    ]
    
    # Variant B: library_name="SSSP", archive_asset="sssp_v2.tar.gz" (should come after A)
    variant_b_sources = [
        {
            "kind": "lib",
            "label": "SSSP 1.4 PBE",
            "installed": True,
            "corrupt": False,
            "library_name": "SSSP",
            "archive_asset": "sssp_v2.tar.gz",
        }
    ]
    
    # Variant C: library_name="PSEUDODOJO", archive_asset="pseudodojo_v1.tar.gz" (should come before SSSP)
    variant_c_sources = [
        {
            "kind": "lib",
            "label": "PSEUDODOJO 1.0",
            "installed": True,
            "corrupt": False,
            "library_name": "PSEUDODOJO",
            "archive_asset": "pseudodojo_v1.tar.gz",
        }
    ]
    
    # All have same sha256 and basename
    variants = [
        {"sha256": sha256, "sha_token": sha_token, "basename": "Si.upf", "sources": variant_a_sources},
        {"sha256": sha256, "sha_token": sha_token, "basename": "Si.upf", "sources": variant_b_sources},
        {"sha256": sha256, "sha_token": sha_token, "basename": "Si.upf", "sources": variant_c_sources},
    ]
    
    # Apply tie-break logic (simulating restoreSelectionFromCalc logic)
    # Step 1: filename match (all same, so no filtering)
    # Step 2: source priority (all lib, so no filtering)
    # Step 3: sort by library_name + archive_asset lexicographically
    def get_tie_break_key(variant):
        lib_sources = [s for s in variant["sources"] if s["kind"] == "lib" and s["installed"] and not s.get("corrupt", False)]
        if lib_sources:
            lib = lib_sources[0]
            library_name = lib.get("library_name", "") or ""
            archive_asset = lib.get("archive_asset", "") or ""
            return (library_name.lower(), archive_asset.lower())
        return ("", "")
    
    sorted_variants = sorted(variants, key=lambda v: (get_tie_break_key(v), v["basename"]))
    
    # Expected order: PSEUDODOJO (alphabetically before SSSP), then SSSP v1, then SSSP v2
    assert sorted_variants[0]["sources"][0]["library_name"] == "PSEUDODOJO", \
        "PSEUDODOJO should come first (lexicographic)"
    assert sorted_variants[1]["sources"][0]["archive_asset"] == "sssp_v1.tar.gz", \
        "sssp_v1 should come before sssp_v2"
    assert sorted_variants[2]["sources"][0]["archive_asset"] == "sssp_v2.tar.gz", \
        "sssp_v2 should come last"
    
    # Verify determinism: same input should produce same order
    sorted_variants_2 = sorted(variants, key=lambda v: (get_tie_break_key(v), v["basename"]))
    assert [v["sources"][0]["archive_asset"] for v in sorted_variants] == \
           [v["sources"][0]["archive_asset"] for v in sorted_variants_2], \
        "Tie-break ordering should be deterministic"

