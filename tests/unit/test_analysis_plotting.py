"""
Tests for the analysis plotting module.

Generates plots to temp/matplotlib_tests/ and verifies:
- Files are created
- Files have non-zero size
"""

import os
from pathlib import Path
import shutil

import pytest

from quantumvitas.analysis.parsers import (
    parse_scf_output,
    parse_dos_data,
    parse_bands_gnu,
)
from quantumvitas.analysis.plotting import (
    plot_dos,
    plot_bands,
    plot_scf_convergence,
    save_figure,
)

# Test data directory
TEST_DATA_DIR = Path(__file__).parent.parent / "data"
# Output directory for generated plots
PLOT_OUTPUT_DIR = Path(__file__).parent.parent.parent / "temp" / "matplotlib_tests"


@pytest.fixture(scope="module", autouse=True)
def setup_plot_dir():
    """Create/clean plot output directory."""
    if PLOT_OUTPUT_DIR.exists():
        shutil.rmtree(PLOT_OUTPUT_DIR)
    PLOT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    yield
    # Optionally clean up after tests
    # shutil.rmtree(PLOT_OUTPUT_DIR, ignore_errors=True)


class TestDOSPlotting:
    """Tests for DOS plotting."""
    
    @pytest.fixture
    def dos_data(self):
        dos_file = TEST_DATA_DIR / "analysis_dos" / "si.dos.dat"
        if not dos_file.exists():
            pytest.skip(f"Test data not found: {dos_file}")
        return parse_dos_data(dos_file)
    
    def test_plot_dos_creates_file(self, dos_data):
        """Test that DOS plot creates a file."""
        fig, ax = plot_dos(dos_data)
        
        output_path = PLOT_OUTPUT_DIR / "dos_test.png"
        saved = save_figure(fig, output_path)
        
        assert len(saved) == 1
        assert saved[0].exists()
        assert saved[0].stat().st_size > 0
    
    def test_plot_dos_with_fermi_shift(self, dos_data):
        """Test DOS plot with Fermi energy shift."""
        fig, ax = plot_dos(dos_data, shift_fermi=True)
        
        output_path = PLOT_OUTPUT_DIR / "dos_fermi_shifted.png"
        saved = save_figure(fig, output_path)
        
        assert saved[0].exists()
        assert saved[0].stat().st_size > 0
    
    def test_plot_dos_energy_range(self, dos_data):
        """Test DOS plot with custom energy range."""
        fig, ax = plot_dos(dos_data, energy_range=(-5, 5))
        
        output_path = PLOT_OUTPUT_DIR / "dos_energy_range.png"
        saved = save_figure(fig, output_path)
        
        assert saved[0].exists()
        assert saved[0].stat().st_size > 0
    
    def test_plot_dos_multiple_formats(self, dos_data):
        """Test saving DOS plot in multiple formats."""
        fig, ax = plot_dos(dos_data)
        
        output_path = PLOT_OUTPUT_DIR / "dos_multi"
        saved = save_figure(fig, output_path, formats=["png", "svg"])
        
        assert len(saved) == 2
        for path in saved:
            assert path.exists()
            assert path.stat().st_size > 0


class TestBandsPlotting:
    """Tests for band structure plotting."""
    
    @pytest.fixture
    def bands_data(self):
        bands_file = TEST_DATA_DIR / "analysis_bands" / "si.bands.dat.gnu"
        symmetry_file = TEST_DATA_DIR / "analysis_bands" / "si.3_bands.pp.out"
        if not bands_file.exists():
            pytest.skip(f"Test data not found: {bands_file}")
        return parse_bands_gnu(
            bands_file,
            symmetry_file=symmetry_file if symmetry_file.exists() else None,
            fermi_energy=5.76  # Approximate Si Fermi energy
        )
    
    def test_plot_bands_creates_file(self, bands_data):
        """Test that bands plot creates a file."""
        fig, ax = plot_bands(bands_data)
        
        output_path = PLOT_OUTPUT_DIR / "bands_test.png"
        saved = save_figure(fig, output_path)
        
        assert len(saved) == 1
        assert saved[0].exists()
        assert saved[0].stat().st_size > 0
    
    def test_plot_bands_with_fermi_shift(self, bands_data):
        """Test bands plot with Fermi energy shift."""
        fig, ax = plot_bands(bands_data, shift_fermi=True)
        
        output_path = PLOT_OUTPUT_DIR / "bands_fermi_shifted.png"
        saved = save_figure(fig, output_path)
        
        assert saved[0].exists()
        assert saved[0].stat().st_size > 0
    
    def test_plot_bands_energy_range(self, bands_data):
        """Test bands plot with custom energy range."""
        fig, ax = plot_bands(bands_data, energy_range=(-10, 10))
        
        output_path = PLOT_OUTPUT_DIR / "bands_energy_range.png"
        saved = save_figure(fig, output_path)
        
        assert saved[0].exists()
        assert saved[0].stat().st_size > 0
    
    def test_plot_bands_symmetry_labels(self, bands_data):
        """Test that symmetry labels are shown."""
        fig, ax = plot_bands(bands_data, show_symmetry_lines=True)
        
        output_path = PLOT_OUTPUT_DIR / "bands_symmetry.png"
        saved = save_figure(fig, output_path)
        
        assert saved[0].exists()
        # With symmetry points, the file should have labels
        if bands_data.high_symmetry_points:
            # Check that x-axis has tick labels
            tick_labels = [t.get_text() for t in ax.get_xticklabels()]
            # At least some labels should be non-empty
            assert any(label for label in tick_labels)
    
    def test_plot_bands_line_count(self, bands_data):
        """Test that correct number of band lines are plotted."""
        fig, ax = plot_bands(bands_data)
        
        # Count Line2D objects (each band is a line)
        lines = [c for c in ax.get_children() 
                 if hasattr(c, 'get_linestyle') and c.get_linestyle() == '-']
        # Should have at least n_bands lines (+ possibly Fermi line)
        assert len(lines) >= bands_data.n_bands


class TestSCFConvergencePlotting:
    """Tests for SCF convergence plotting."""
    
    @pytest.fixture
    def scf_data(self):
        scf_file = TEST_DATA_DIR / "analysis_scf" / "si.0_scf.out"
        if not scf_file.exists():
            pytest.skip(f"Test data not found: {scf_file}")
        return parse_scf_output(scf_file)
    
    def test_plot_scf_convergence_creates_file(self, scf_data):
        """Test that SCF convergence plot creates a file."""
        if not scf_data.iterations:
            pytest.skip("No iterations in SCF data")
        
        fig, ax = plot_scf_convergence(scf_data)
        
        output_path = PLOT_OUTPUT_DIR / "scf_convergence.png"
        saved = save_figure(fig, output_path)
        
        assert len(saved) == 1
        assert saved[0].exists()
        assert saved[0].stat().st_size > 0
    
    def test_plot_scf_energy_only(self, scf_data):
        """Test SCF plot with only energy."""
        if not scf_data.iterations:
            pytest.skip("No iterations in SCF data")
        
        fig, ax = plot_scf_convergence(scf_data, show_energy=True, show_accuracy=False)
        
        output_path = PLOT_OUTPUT_DIR / "scf_energy_only.png"
        saved = save_figure(fig, output_path)
        
        assert saved[0].exists()
        assert saved[0].stat().st_size > 0
    
    def test_plot_scf_accuracy_only(self, scf_data):
        """Test SCF plot with only accuracy."""
        if not scf_data.iterations:
            pytest.skip("No iterations in SCF data")
        
        fig, ax = plot_scf_convergence(scf_data, show_energy=False, show_accuracy=True)
        
        output_path = PLOT_OUTPUT_DIR / "scf_accuracy_only.png"
        saved = save_figure(fig, output_path)
        
        assert saved[0].exists()
        assert saved[0].stat().st_size > 0


class TestPlotOutputFormats:
    """Tests for various output formats."""
    
    @pytest.fixture
    def dos_data(self):
        dos_file = TEST_DATA_DIR / "analysis_dos" / "si.dos.dat"
        if not dos_file.exists():
            pytest.skip(f"Test data not found: {dos_file}")
        return parse_dos_data(dos_file)
    
    def test_save_png(self, dos_data):
        """Test PNG output."""
        fig, ax = plot_dos(dos_data)
        output_path = PLOT_OUTPUT_DIR / "format_test.png"
        saved = save_figure(fig, output_path)
        
        assert saved[0].suffix == ".png"
        assert saved[0].exists()
    
    def test_save_svg(self, dos_data):
        """Test SVG output."""
        fig, ax = plot_dos(dos_data)
        output_path = PLOT_OUTPUT_DIR / "format_test.svg"
        saved = save_figure(fig, output_path)
        
        assert saved[0].suffix == ".svg"
        assert saved[0].exists()
    
    def test_save_pdf(self, dos_data):
        """Test PDF output."""
        fig, ax = plot_dos(dos_data)
        output_path = PLOT_OUTPUT_DIR / "format_test.pdf"
        saved = save_figure(fig, output_path)
        
        assert saved[0].suffix == ".pdf"
        assert saved[0].exists()

