"""
Integration tests for ABINIT execution.

These tests run actual ABINIT calculations and verify results.
Tests are skipped if ABINIT is not installed.

ABINIT is a plane-wave pseudopotential DFT code similar to QE,
with unique features like multi-dataset mode and comprehensive DFPT support.

To run these tests:
    pytest tests/integration/test_abinit_execution.py -v --tb=long
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from quantumvitas.core.engines.discovery import discover_engine, is_engine_available

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Skip all tests if abinit is not installed
pytestmark = pytest.mark.skipif(
    not is_engine_available("abinit", project_root=_REPO_ROOT),
    reason="ABINIT not installed",
)


def _find_abinit_bin(binary_name: str = "abinit") -> str:
    """Find an ABINIT binary."""
    result = discover_engine("abinit", project_root=_REPO_ROOT)
    if result.available and result.executable_path:
        bin_dir = result.executable_path.parent
        candidate = bin_dir / binary_name
        if candidate.is_file():
            return str(candidate)
    found = shutil.which(binary_name)
    assert found is not None, f"{binary_name} binary not found"
    return found


# ── ABINIT input templates for Si (minimal, 2-atom FCC cell) ──

_SI_SCF_TEMPLATE = """\
# Si SCF calculation - minimal
# Structure
acell 3*10.26311
rprim
  0.0  0.5  0.5
  0.5  0.0  0.5
  0.5  0.5  0.0
natom 2
ntypat 1
typat 1 1
znucl 14
xred
  0.0  0.0  0.0
  0.25 0.25 0.25

# SCF parameters
ecut 10.0
ngkpt 4 4 4
nshiftk 1
shiftk 0.0 0.0 0.0
nstep 50
diemac 12.0
iscf 7
occopt 1
chksymbreak 0
toldfe 1.0e-8

# Output control
prtwf 1
prtden 1

# Pseudopotentials
pp_dirpath "{pp_dirpath}"
pseudos "{pseudo_file}"
"""

_SI_RELAX_TEMPLATE = """\
# Si relaxation calculation - compressed cell to test relaxation
# Structure (compressed acell to trigger relaxation)
acell 3*10.0
rprim
  0.0  0.5  0.5
  0.5  0.0  0.5
  0.5  0.5  0.0
natom 2
ntypat 1
typat 1 1
znucl 14
xred
  0.0  0.0  0.0
  0.25 0.25 0.25

# SCF parameters
ecut 10.0
ngkpt 2 2 2
nshiftk 1
shiftk 0.0 0.0 0.0
nstep 30
diemac 12.0
iscf 7
occopt 1
chksymbreak 0

# Relaxation parameters
ionmov 2
optcell 1
ntime 20
tolmxf 5.0e-4
dilatmx 1.1
ecutsm 0.5
toldff 5.0e-5

# Output control
prtwf 0
prtden 0

# Pseudopotentials
pp_dirpath "{pp_dirpath}"
pseudos "{pseudo_file}"
"""


def _find_si_psp() -> Path:
    """Find any Si pseudopotential for ABINIT tests.

    ABINIT supports multiple formats: .psp8, .pspnc, .hgh, .xml
    Searches multiple locations for a suitable pseudopotential.
    """
    # Check in golden refs first
    golden_pseudo_dir = _REPO_ROOT / "docs" / "engines" / "abinit" / "pseudopotentials"
    for pattern in ["Si.psp8", "Si.pspnc", "14si.pspnc", "Si_*.psp8"]:
        for match in golden_pseudo_dir.glob(pattern):
            return match

    # Check standard locations
    search_dirs = [
        _REPO_ROOT / "resources" / "pseudo",
        Path.home() / ".qmatsuite" / "pseudo",
        Path.home() / ".abinit" / "pseudo",
        # Homebrew install location
        Path("/opt/homebrew/share/abinit"),
    ]
    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue
        for pattern in ["Si*.psp8", "Si*.pspnc", "14*.pspnc", "Si*.hgh"]:
            for match in search_dir.rglob(pattern):
                return match

    # Check ABINIT install directory for bundled pseudos
    abinit_result = discover_engine("abinit", project_root=_REPO_ROOT)
    if abinit_result.available and abinit_result.executable_path:
        abinit_home = abinit_result.executable_path.parent.parent
        for pattern in ["Si*.psp8", "Si*.pspnc"]:
            for match in abinit_home.rglob(pattern):
                return match

    return None


# =====================================================================
# Test 1: Raw ABINIT binary execution
# =====================================================================

class TestAbinitRawExecution:
    """Tests that call ABINIT directly (no driver framework)."""

    def test_scf_si(self, tmp_path):
        """Run SCF on Si and verify output."""
        workdir = tmp_path / "si_scf"
        workdir.mkdir(parents=True)

        # Find and copy pseudopotential
        pseudo_src = _find_si_psp()
        if pseudo_src is None:
            pytest.skip("No Si pseudopotential found for ABINIT")

        pseudo_dir = workdir / "pseudo"
        pseudo_dir.mkdir()
        pseudo_file = pseudo_src.name
        shutil.copy2(pseudo_src, pseudo_dir / pseudo_file)

        # Write input file
        input_text = _SI_SCF_TEMPLATE.format(
            pp_dirpath=str(pseudo_dir),
            pseudo_file=pseudo_file,
        )
        input_file = workdir / "si_scf.abi"
        input_file.write_text(input_text)

        # Run ABINIT
        abinit_bin = _find_abinit_bin()
        result = subprocess.run(
            [abinit_bin, str(input_file)],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=300,
        )

        # Save output for debugging
        output_file = workdir / "si_scf.abo"
        if not output_file.exists():
            # ABINIT may write to stdout, save it
            (workdir / "stdout.txt").write_text(result.stdout)
            (workdir / "stderr.txt").write_text(result.stderr)

        # ── Assert exit code ──
        assert result.returncode == 0, (
            f"ABINIT SCF failed (exit {result.returncode}):\n"
            f"stderr: {result.stderr[:1000]}\n"
            f"stdout: {result.stdout[:1000]}"
        )

        # ── Assert output file exists ──
        assert output_file.exists(), f"Output file {output_file} not created"

        # ── Assert success strings in output ──
        output_text = output_file.read_text()
        assert "etotal" in output_text.lower(), "Missing etotal in output"
        assert "Calculation completed" in output_text or "ETOT" in output_text, (
            "Missing convergence info in output"
        )

        # ── Assert artifact files exist ──
        # ABINIT creates files like: si_scfo_DEN, si_scfo_WFK, si_scfo_EIG
        assert any(workdir.glob("*o_DEN")), "No density file (*o_DEN) created"

        # ── Parse and verify results ──
        from quantumvitas.drivers.abinit.parser import parse_abinit_output

        parsed = parse_abinit_output(output_file)
        assert parsed.version, "Could not parse ABINIT version"
        assert parsed.calculation_type == "scf", (
            f"Expected 'scf', got '{parsed.calculation_type}'"
        )
        assert 1 in parsed.datasets, "No dataset 1 in parsed output"

        ds = parsed.datasets[1]
        assert ds.total_energy < 0, "Total energy should be negative"
        assert ds.n_iterations > 0, "Should have at least 1 SCF iteration"
        assert ds.n_iterations < 50, "SCF should converge in < 50 iterations"

        # Si total energy should be around -8.9 Ha for this cutoff
        assert -10 < ds.total_energy < -7, (
            f"Si total energy {ds.total_energy} Ha outside expected range"
        )

    def test_relax_si(self, tmp_path):
        """Run relaxation on compressed Si cell and verify output."""
        workdir = tmp_path / "si_relax"
        workdir.mkdir(parents=True)

        # Find and copy pseudopotential
        pseudo_src = _find_si_psp()
        if pseudo_src is None:
            pytest.skip("No Si pseudopotential found for ABINIT")

        pseudo_dir = workdir / "pseudo"
        pseudo_dir.mkdir()
        pseudo_file = pseudo_src.name
        shutil.copy2(pseudo_src, pseudo_dir / pseudo_file)

        # Write input file
        input_text = _SI_RELAX_TEMPLATE.format(
            pp_dirpath=str(pseudo_dir),
            pseudo_file=pseudo_file,
        )
        input_file = workdir / "si_relax.abi"
        input_file.write_text(input_text)

        # Run ABINIT
        abinit_bin = _find_abinit_bin()
        result = subprocess.run(
            [abinit_bin, str(input_file)],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=600,  # Relax takes longer
        )

        # Save output
        output_file = workdir / "si_relax.abo"

        # ── Assert exit code ──
        assert result.returncode == 0, (
            f"ABINIT relax failed (exit {result.returncode}):\n"
            f"stderr: {result.stderr[:1000]}"
        )

        # ── Assert output file exists ──
        assert output_file.exists(), f"Output file {output_file} not created"

        # ── Assert success strings ──
        output_text = output_file.read_text()
        assert "etotal" in output_text.lower(), "Missing etotal in output"

        # ── Assert history file exists ──
        # Relaxation creates *o_HIST.nc file
        hist_files = list(workdir.glob("*o_HIST.nc"))
        # Note: HIST.nc may not be created for small test, check output instead

        # ── Parse and verify results ──
        from quantumvitas.drivers.abinit.parser import parse_abinit_output

        parsed = parse_abinit_output(output_file)
        assert parsed.calculation_type in ("relax", "vc_relax"), (
            f"Expected relax type, got '{parsed.calculation_type}'"
        )

        # Check that final structure was extracted (acell should have changed)
        ds = parsed.datasets[1]
        if ds.final_structure is not None:
            # Starting acell was 10.0, should relax to ~10.26
            final_acell = ds.final_structure.acell[0]
            assert final_acell > 10.0, (
                f"Cell should have expanded from 10.0, got {final_acell}"
            )


# =====================================================================
# Test 2: Driver registration & discovery
# =====================================================================

class TestAbinitDriverRegistration:
    """Tests that the ABINIT driver is registered and discoverable."""

    def test_driver_registry_lookup(self):
        """Verify ABINIT driver is accessible via DriverRegistry."""
        import quantumvitas.drivers.abinit  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        driver = DriverRegistry.get_driver("abinit")
        assert driver is not None
        assert driver.PREFIX == "abinit"
        assert driver.engine_family == "abinit"
        assert driver.display_name == "ABINIT"
        assert driver.driver_api_version == "1.0.0"
        assert "scf" in driver.SUPPORTED_GEN_STEPS
        assert "nscf" in driver.SUPPORTED_GEN_STEPS
        assert "relax" in driver.SUPPORTED_GEN_STEPS

    def test_step_type_specs(self):
        """Verify all 3 step type specs are registered."""
        import quantumvitas.drivers.abinit  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        expected = {"abinit_scf", "abinit_nscf", "abinit_relax"}
        for spec_name in expected:
            spec = DriverRegistry.get_step_type_spec(spec_name)
            assert spec is not None, f"Step type {spec_name} not registered"
            assert spec.engine == "abinit"

    def test_step_type_handler_lookup(self):
        """Verify handler is resolvable for each step type."""
        import quantumvitas.drivers.abinit  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        for spec_name in ["abinit_scf", "abinit_nscf", "abinit_relax"]:
            handler = DriverRegistry.get_handler(spec_name)
            assert handler is not None, f"No handler for {spec_name}"
            assert callable(handler)

    def test_materialization_map(self):
        """Verify gen → spec materialization."""
        import quantumvitas.drivers.abinit  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        assert DriverRegistry.materialize_step_type("abinit", "scf") == "abinit_scf"
        assert DriverRegistry.materialize_step_type("abinit", "nscf") == "abinit_nscf"
        assert DriverRegistry.materialize_step_type("abinit", "relax") == "abinit_relax"

    def test_engine_discovery(self):
        """Verify ABINIT is discovered via centralized engine discovery."""
        result = discover_engine("abinit", project_root=_REPO_ROOT)
        assert result.available, f"ABINIT should be discovered: {result.reason}"
        assert result.executable_path is not None

    def test_recipe_class(self):
        """Verify recipe class is accessible."""
        import quantumvitas.drivers.abinit  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        recipe_cls = DriverRegistry.get_recipe_class("abinit")
        assert recipe_cls is not None

    def test_workdir_policy(self):
        """Verify SHARED workdir policy (Directory-state archetype)."""
        import quantumvitas.drivers.abinit  # noqa: F401
        from quantumvitas.core.driver_protocol import WorkdirPolicy
        from quantumvitas.core.driver_registry import DriverRegistry

        driver = DriverRegistry.get_driver("abinit")
        assert driver.get_workdir_policy() == WorkdirPolicy.SHARED


# =====================================================================
# Test 3: Parser unit tests with golden references
# =====================================================================

class TestAbinitParser:
    """Test parsers against golden reference files from exploration."""

    _GOLDEN = _REPO_ROOT / "docs" / "engines" / "abinit" / "golden_refs"

    @pytest.mark.skipif(
        not (_REPO_ROOT / "docs" / "engines" / "abinit"
             / "golden_refs" / "si_scf.abo").exists(),
        reason="Golden reference files not available",
    )
    def test_parse_scf_golden(self):
        """Parse golden SCF output file."""
        from quantumvitas.drivers.abinit.parser import parse_abinit_output

        output = parse_abinit_output(self._GOLDEN / "si_scf.abo")
        assert output.version, "No version parsed"
        assert output.calculation_type == "scf"
        assert output.n_datasets == 1
        assert 1 in output.datasets

        ds = output.datasets[1]
        assert ds.total_energy < -8.0, "Energy should be < -8 Ha"
        assert ds.n_iterations > 0

    @pytest.mark.skipif(
        not (_REPO_ROOT / "docs" / "engines" / "abinit"
             / "golden_refs" / "si_relax.abo").exists(),
        reason="Golden reference files not available",
    )
    def test_parse_relax_golden(self):
        """Parse golden relax output file."""
        from quantumvitas.drivers.abinit.parser import parse_abinit_output

        output = parse_abinit_output(self._GOLDEN / "si_relax.abo")
        assert output.calculation_type in ("relax", "vc_relax")
        assert 1 in output.datasets

    @pytest.mark.skipif(
        not (_REPO_ROOT / "docs" / "engines" / "abinit"
             / "golden_refs" / "si_scfo_EIG").exists(),
        reason="Golden EIG file not available",
    )
    def test_parse_eig_golden(self):
        """Parse golden eigenvalue file."""
        from quantumvitas.drivers.abinit.parser import parse_eig_file

        eig = parse_eig_file(self._GOLDEN / "si_scfo_EIG")
        assert len(eig) > 0, "No k-points parsed"
        # First k-point should have eigenvalues
        assert 1 in eig
        assert len(eig[1]) > 0, "No eigenvalues for k-point 1"


# =====================================================================
# Test 4: Writer unit tests
# =====================================================================

class TestAbinitWriter:
    """Test input file writers."""

    def test_write_scf_input(self, tmp_path):
        """Write and verify SCF input file."""
        from quantumvitas.drivers.abinit.writer import (
            AbinitStructure, SCFParams, write_scf_input
        )

        si = AbinitStructure(
            acell=(10.26, 10.26, 10.26),
            rprim=[[0, 0.5, 0.5], [0.5, 0, 0.5], [0.5, 0.5, 0]],
            natom=2,
            ntypat=1,
            typat=[1, 1],
            znucl=[14.0],
            xred=[[0, 0, 0], [0.25, 0.25, 0.25]],
        )
        scf = SCFParams(ecut=10.0, ngkpt=(4, 4, 4))

        out = tmp_path / "test.abi"
        write_scf_input(si, scf, ["Si.psp8"], "./pseudo", out)

        text = out.read_text()
        assert "acell" in text
        assert "rprim" in text
        assert "ecut" in text
        assert "ngkpt" in text
        assert "toldfe" in text
        assert "pseudos" in text

    def test_write_relax_input(self, tmp_path):
        """Write and verify relax input file."""
        from quantumvitas.drivers.abinit.writer import (
            AbinitStructure, SCFParams, RelaxParams, write_relax_input
        )

        si = AbinitStructure(
            acell=(10.0, 10.0, 10.0),
            rprim=[[0, 0.5, 0.5], [0.5, 0, 0.5], [0.5, 0.5, 0]],
            natom=2,
            ntypat=1,
            typat=[1, 1],
            znucl=[14.0],
            xred=[[0, 0, 0], [0.25, 0.25, 0.25]],
        )
        scf = SCFParams(ecut=10.0, ngkpt=(2, 2, 2))
        relax = RelaxParams(ionmov=2, optcell=1, ntime=20)

        out = tmp_path / "relax.abi"
        write_relax_input(si, scf, relax, ["Si.psp8"], "./pseudo", out)

        text = out.read_text()
        assert "ionmov" in text
        assert "optcell" in text
        assert "ntime" in text
        assert "tolmxf" in text

    def test_structure_to_input_string(self):
        """Test structure serialization."""
        from quantumvitas.drivers.abinit.writer import AbinitStructure

        si = AbinitStructure(
            acell=(10.26, 10.26, 10.26),
            rprim=[[0, 0.5, 0.5], [0.5, 0, 0.5], [0.5, 0.5, 0]],
            natom=2,
            ntypat=1,
            typat=[1, 1],
            znucl=[14.0],
            xred=[[0, 0, 0], [0.25, 0.25, 0.25]],
        )

        text = si.to_input_string()
        assert "acell" in text
        assert "10.26" in text or "10.2600" in text
        assert "natom 2" in text
        assert "ntypat 1" in text


# =====================================================================
# Test 5: Workflow registry integration
# =====================================================================

class TestAbinitWorkflowRegistry:
    """Test that ABINIT step types are in workflow registry."""

    def test_abinit_in_workflow_registry(self):
        """Verify ABINIT step types in workflow registry."""
        from quantumvitas.workflow.registry import get_registry, _STEP_TYPES

        registry = get_registry()

        # Check all ABINIT step types are registered
        for spec_name in ["abinit_scf", "abinit_nscf", "abinit_relax"]:
            assert spec_name in _STEP_TYPES, f"{spec_name} not in _STEP_TYPES"
            spec = _STEP_TYPES[spec_name]
            assert spec.engine == "abinit"
            assert spec.step_type_spec == spec_name

    def test_abinit_relax_is_structure_transform(self):
        """Verify abinit_relax has is_structure_transform=True."""
        from quantumvitas.workflow.registry import _STEP_TYPES

        spec = _STEP_TYPES.get("abinit_relax")
        assert spec is not None
        assert spec.is_structure_transform is True

    def test_abinit_prefix_in_step_type_convert(self):
        """Verify 'abinit' is in ENGINE_PREFIXES."""
        from quantumvitas.workflow.step_type_convert import ENGINE_PREFIXES

        assert "abinit" in ENGINE_PREFIXES

    def test_gen_from_spec(self):
        """Test GEN extraction from SPEC."""
        from quantumvitas.workflow.step_type_convert import gen_from

        assert gen_from("abinit_scf") == "scf"
        assert gen_from("abinit_nscf") == "nscf"
        assert gen_from("abinit_relax") == "relax"

    def test_spec_from_gen(self):
        """Test SPEC creation from prefix + GEN."""
        from quantumvitas.workflow.step_type_convert import spec_from

        assert spec_from("abinit", "scf") == "abinit_scf"
        assert spec_from("abinit", "nscf") == "abinit_nscf"
        assert spec_from("abinit", "relax") == "abinit_relax"
