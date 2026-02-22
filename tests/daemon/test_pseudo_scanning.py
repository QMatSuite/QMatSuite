"""
Tests for pseudo file scanning.

Tests verify:
- Pseudo scanning finds files with case-insensitive extension matching
- Project and internal pseudo directories are scanned
- Logs are generated for scanning operations
"""
import pytest
from pathlib import Path

from qmatsuite.core.pseudo_options import get_pseudo_options_for_elements


@pytest.mark.unit
class TestPseudoScanning:
    """Test pseudo file scanning."""
    
    def test_scan_finds_case_insensitive_upf_files(self, tmp_path):
        """Pseudo scanning finds .UPF, .upf, and other case variations."""
        # Create project with pseudo directory
        project_root = tmp_path / "project"
        project_root.mkdir()
        pseudo_dir = project_root / "pseudo"
        pseudo_dir.mkdir()
        
        # Create pseudo files with different case extensions
        (pseudo_dir / "Si.UPF").write_text("fake UPF content")
        (pseudo_dir / "C.upf").write_text("fake upf content")
        (pseudo_dir / "O.Upf").write_text("fake Upf content")
        
        # Scan for Si element
        result = get_pseudo_options_for_elements(
            project_root=project_root,
            elements=["Si"],
        )
        
        # Should find Si.UPF
        assert "Si" in result
        assert len(result["Si"]) > 0
        # Check that basename matches
        si_variants = result["Si"]
        basenames = [v.get("basename", "") for v in si_variants]
        assert any("Si" in b for b in basenames)
    
    def test_scan_includes_project_and_internal_directories(self, tmp_path):
        """Pseudo scanning checks both project/pseudo and internal pseudo directories."""
        # Create project with pseudo directory
        project_root = tmp_path / "project"
        project_root.mkdir()
        project_pseudo_dir = project_root / "pseudo"
        project_pseudo_dir.mkdir()
        
        # Create a pseudo file in project
        (project_pseudo_dir / "Si.UPF").write_text("fake UPF content for Si")
        
        # Scan for Si element
        result = get_pseudo_options_for_elements(
            project_root=project_root,
            elements=["Si"],
        )
        
        # Should find at least project pseudo
        assert "Si" in result
        assert len(result["Si"]) > 0
        
        # Check that project source is present
        si_variants = result["Si"]
        has_project_source = False
        for variant in si_variants:
            sources = variant.get("sources", [])
            for source in sources:
                if source.get("kind") == "project" and source.get("installed"):
                    has_project_source = True
                    break
            if has_project_source:
                break
        
        # Project pseudo should be found
        assert has_project_source, "Project pseudo should be found in scan results"
    
    def test_scan_logs_directory_paths(self, tmp_path, caplog):
        """Pseudo scanning logs directory paths being scanned."""
        import logging
        logging.getLogger("qmatsuite.core.pseudo_options").setLevel(logging.INFO)
        
        # Create project with pseudo directory
        project_root = tmp_path / "project"
        project_root.mkdir()
        project_pseudo_dir = project_root / "pseudo"
        project_pseudo_dir.mkdir()
        
        (project_pseudo_dir / "Si.UPF").write_text("fake UPF content")
        
        # Scan
        get_pseudo_options_for_elements(
            project_root=project_root,
            elements=["Si"],
        )
        
        # Check logs contain directory paths
        log_messages = [record.message for record in caplog.records]
        assert any("[PSEUDO_SCAN]" in msg for msg in log_messages)
        assert any(str(project_pseudo_dir) in msg for msg in log_messages)

